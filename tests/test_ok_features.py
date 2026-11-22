"""The OpenAPI feature examples of the ok API (specs/ok-features.yaml): served, strict, correct."""

import base64
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
F = "/ok/features"
METHODS = ("get", "post", "put", "patch", "delete", "head", "options", "trace")


def load():
    return yaml.safe_load((ROOT / "specs" / "ok-features.yaml").read_text(encoding="utf-8"))


async def test_the_document_is_served_with_the_rewritten_server_url(client):
    r = await client.get("/ok/openapi-features.yaml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/yaml")
    doc = yaml.safe_load(r.text)
    assert doc["servers"] == [{"url": "http://testserver/ok"}]
    doc["servers"] = load()["servers"]
    assert doc == load()


@pytest.mark.parametrize("family", ["contract-fail", "conform-fail"])
async def test_only_the_ok_family_serves_it(client, family):
    assert (await client.get(f"/{family}/openapi-features.yaml")).status_code == 404


def test_the_document_uses_the_features_it_is_for():
    doc = load()
    text = (ROOT / "specs" / "ok-features.yaml").read_text(encoding="utf-8")
    for needle in ("deepObject", "pipeDelimited", "spaceDelimited", "style: label", "style: matrix", "allowEmptyValue",
                   "allowReserved", "multipleOf", "exclusiveMinimum", "format: int64", "format: double",
                   "format: byte", "format: password", "not:", "deprecated: true", "links:", "text/csv", "image/png",
                   "application/x-ndjson", "requestBodies", "type: oauth2", "type: openIdConnect", "externalDocs"):
        assert needle in text, needle
    assert doc["openapi"] == "3.0.3"
    assert "trace" in doc["paths"]["/features/trace"]


async def test_every_operation_of_the_document_is_implemented(client):
    """Each documented operation is routed (anything but 404/405 for a missing route)."""
    for path, item in load()["paths"].items():
        concrete = path.replace("{labelIds}", ".1,2").replace("{matrixIds}", ";matrixIds=1").replace("{itemId}", "item-1")
        for method in (m for m in item if m in METHODS):
            r = await client.request(method.upper(), f"/ok{concrete}")
            assert r.status_code != 405, (method, path)
            if r.status_code == 404:
                assert r.headers["content-type"].startswith("application/json"), (method, path)  # a declared 404


# ---- parameter styles ----


async def test_deep_object(client):
    assert (await client.get(f"{F}/deep-object", params={"filter[status]": "open", "filter[min]": "2"})).json() == {"status": "open", "min": 2}
    assert (await client.get(f"{F}/deep-object")).json() == {}
    for bad in ({"filter[status]": "x"}, {"filter[min]": "a"}, {"filter[other]": "1"}):
        assert (await client.get(f"{F}/deep-object", params=bad)).status_code == 400


async def test_pipe_and_space_delimited(client):
    assert (await client.get(f"{F}/pipe-delimited", params={"ids": "1|2|3"})).json() == {"ids": [1, 2, 3]}
    assert (await client.get(f"{F}/space-delimited?ids=1%202%203")).json() == {"ids": [1, 2, 3]}
    for path in ("pipe-delimited?ids=1,2", "pipe-delimited?ids=", "pipe-delimited", "space-delimited?ids=a%20b", "space-delimited"):
        assert (await client.get(f"{F}/{path}")).status_code == 400, path


async def test_label_and_matrix(client):
    assert (await client.get(f"{F}/label/.1,2,3")).json() == {"ids": [1, 2, 3]}
    assert (await client.get(f"{F}/matrix/;matrixIds=1,2,3")).json() == {"ids": [1, 2, 3]}
    for path in ("label/1,2,3", "label/.1.2.3", "matrix/;ids=1,2", "matrix/1,2"):
        assert (await client.get(f"{F}/{path}")).status_code == 400, path


async def test_flags_allow_an_empty_value_and_reserved_characters(client):
    assert (await client.get(f"{F}/flags")).json() == {"flag": None, "path": None}
    assert (await client.get(f"{F}/flags?flag=")).json() == {"flag": "", "path": None}
    assert (await client.get(f"{F}/flags?path=a/b:c@d")).json() == {"flag": None, "path": "a/b:c@d"}
    assert (await client.get(f"{F}/flags", params={"flag": "x" * 41})).status_code == 400


# ---- schemas ----


def numbers(**over):
    body = {"count": 15, "ratio": 0.25, "secret": "correct-horse", "blob": base64.b64encode(b"hello").decode()}
    return {**body, **over}


async def test_numbers_formats_and_bounds(client):
    r = await client.post(f"{F}/numbers", json=numbers())
    assert r.status_code == 200 and r.json() == {"count": 15, "ratio": 0.25, "secretLength": 13, "blobBytes": 5}
    assert (await client.post(f"{F}/numbers", json=numbers(count=9_000_000_000))).status_code == 400  # over the cap
    for over in ({"count": 7}, {"count": 0}, {"count": 1_000_005}, {"ratio": 0}, {"ratio": 1}, {"ratio": 1.5},
                 {"secret": "short"}, {"blob": "not base64!"}, {"count": "15"}, {"extra": 1}):
        assert (await client.post(f"{F}/numbers", json=numbers(**over))).status_code == 400, over


async def test_not_enum(client):
    assert (await client.post(f"{F}/names", json={"name": "alice"})).json() == {"name": "alice"}
    for name in ("admin", "root", "", "x" * 21):
        assert (await client.post(f"{F}/names", json={"name": name})).status_code == 400, name


async def test_deprecated_operation_still_works(client):
    assert (await client.get(f"{F}/greeting")).json() == {"message": "hello"}
    assert load()["paths"]["/features/greeting"]["get"]["deprecated"] is True


async def test_items_and_the_link(client):
    created = await client.post(f"{F}/items", json={"title": "First item"})
    assert created.status_code == 201 and created.json() == {"id": "item-1", "title": "First item"}
    assert created.headers["location"] == f"{F}/items/item-1"
    assert (await client.get(created.headers["location"])).json() == created.json()  # what the link says
    assert (await client.get(f"{F}/items/item-9")).status_code == 404
    assert (await client.post(f"{F}/items", json={"title": ""})).status_code == 400
    link = load()["paths"]["/features/items"]["post"]["responses"]["201"]["links"]["GetItem"]
    assert link["operationId"] == "featureGetItem" and link["parameters"] == {"itemId": "$response.body#/id"}


async def test_items_are_reset_with_the_family(client):
    await client.post(f"{F}/items", json={"title": "x"})
    assert (await client.post("/ok/__admin/reset")).status_code == 204
    assert (await client.get(f"{F}/items/item-1")).status_code == 404
    assert (await client.post(f"{F}/items", json={"title": "y"})).json()["id"] == "item-1"  # the counter restarts


async def test_trace_method(client):
    r = await client.request("TRACE", f"{F}/trace")
    assert r.status_code == 200 and r.text == "trace ok"


async def test_notes_use_the_request_body_component(client):
    assert (await client.post(f"{F}/notes", json={"text": "hello"})).json() == {"text": "hello", "length": 5}
    assert (await client.post(f"{F}/notes", json={"text": ""})).status_code == 400
    assert load()["paths"]["/features/notes"]["post"]["requestBody"] == {"$ref": "#/components/requestBodies/Note"}


# ---- media types ----


async def test_csv_png_ndjson(client):
    csv = await client.get(f"{F}/report.csv")
    assert csv.headers["content-type"].startswith("text/csv") and csv.text.splitlines()[0] == "id,name"
    png = await client.get(f"{F}/logo.png")
    assert png.headers["content-type"] == "image/png" and png.content.startswith(b"\x89PNG\r\n\x1a\n")
    nd = await client.get(f"{F}/events.ndjson")
    assert nd.headers["content-type"].startswith("application/x-ndjson")
    assert [line for line in nd.text.splitlines()] and all(line.startswith("{") for line in nd.text.splitlines())


# ---- security ----


async def test_oauth2_token_then_profile(client):
    token = await client.post(f"{F}/oauth2/token", content="grant_type=client_credentials",
                              headers={"content-type": "application/x-www-form-urlencoded"})
    assert token.status_code == 200
    body = token.json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 3600
    ok = await client.get(f"{F}/oauth2-profile", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert ok.json() == {"user": "test-user", "via": "oauth2"}
    bad = await client.post(f"{F}/oauth2/token", content="grant_type=password",
                            headers={"content-type": "application/x-www-form-urlencoded"})
    assert bad.status_code == 400


@pytest.mark.parametrize("path", ["oauth2-profile", "openid-profile"])
async def test_profiles_need_a_bearer_token(client, path):
    missing = await client.get(f"{F}/{path}")
    assert missing.status_code == 401 and missing.headers["www-authenticate"].startswith("Bearer")
    assert (await client.get(f"{F}/{path}", headers={"Authorization": "Bearer nope"})).status_code == 401
    assert (await client.get(f"{F}/{path}", headers={"Authorization": "Bearer test-token"})).status_code == 200


async def test_openid_discovery_document(client):
    doc = (await client.get(f"{F}/.well-known/openid-configuration")).json()
    assert doc["token_endpoint"].endswith("/ok/features/oauth2/token")
    assert "/features/.well-known/openid-configuration" not in str(load()["paths"])  # not an operation of the spec


# ---- credentials: valid, unknown, expired, under-privileged ----


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def test_credentials_profile(client):
    ok = await client.get(f"{F}/credentials/profile", headers=bearer("test-token"))
    assert ok.status_code == 200 and ok.json() == {"user": "test-user", "scopes": ["read"]}
    assert (await client.get(f"{F}/credentials/profile", headers=bearer("writer-token"))).json()["scopes"] == ["read", "write"]
    unknown = await client.get(f"{F}/credentials/profile", headers=bearer("nope"))
    assert unknown.status_code == 401 and unknown.headers["www-authenticate"] == 'Bearer realm="ok"'
    expired = await client.get(f"{F}/credentials/profile", headers=bearer("expired-token"))
    assert expired.status_code == 401 and "the access token expired" in expired.headers["www-authenticate"]
    assert (await client.get(f"{F}/credentials/profile")).status_code == 401


async def test_write_area_needs_the_write_scope(client):
    assert (await client.get(f"{F}/credentials/write-area", headers=bearer("writer-token"))).json() == {"area": "write", "ok": True}
    forbidden = await client.get(f"{F}/credentials/write-area", headers=bearer("test-token"))
    assert forbidden.status_code == 403 and forbidden.json()["code"] == "forbidden"
    assert (await client.get(f"{F}/credentials/write-area", headers=bearer("expired-token"))).status_code == 401
    assert (await client.get(f"{F}/credentials/write-area")).status_code == 401


# ---- a session in a cookie ----


async def login(client, **over):
    return await client.post(f"{F}/session/login", json={"user": "test-user", "password": "test-pass", **over})


async def test_login_sets_a_cookie_and_the_cookie_is_the_credential(client):
    r = await login(client)
    assert r.status_code == 204
    cookie = r.headers["set-cookie"]
    assert cookie.startswith("session=sess-") and "HttpOnly" in cookie and "Path=/ok/features" in cookie
    session = cookie.split(";")[0].split("=")[1]
    assert (await client.get(f"{F}/session/me", cookies={"session": session})).json() == {"user": "test-user", "session": session}
    client.cookies.clear()  # the test client keeps the login cookie, a real caller without it has none
    for cookies in (None, {"session": "nope"}):
        assert (await client.get(f"{F}/session/me", cookies=cookies)).status_code == 401


async def test_the_seeded_session_exists_after_every_reset(client):
    assert (await client.get(f"{F}/session/me", cookies={"session": "sess-seed"})).status_code == 200
    await client.post("/ok/__admin/reset")
    assert (await client.get(f"{F}/session/me", cookies={"session": "sess-seed"})).status_code == 200


async def test_wrong_login_is_refused_and_bad_input_is_400(client):
    assert (await login(client, password="wrong")).status_code == 401
    assert (await login(client, user="someone")).status_code == 401
    for bad in ({"user": ""}, {"password": ""}, {"extra": 1}):
        assert (await login(client, **bad)).status_code == 400, bad
    assert "set-cookie" not in (await login(client, password="wrong")).headers


async def test_logout_ends_the_session_and_clears_the_cookie(client):
    session = (await login(client)).headers["set-cookie"].split(";")[0].split("=")[1]
    out = await client.post(f"{F}/session/logout", cookies={"session": session})
    assert out.status_code == 204 and "Max-Age=0" in out.headers["set-cookie"]
    assert (await client.get(f"{F}/session/me", cookies={"session": session})).status_code == 401
    assert (await client.post(f"{F}/session/logout")).status_code == 204  # also when nobody was logged in


# ---- pagination with a Link header ----


def links(header):
    out = {}
    for part in header.split(", "):
        url, _, rel = part.partition("; rel=")
        out[rel.strip('"')] = url.strip("<>")
    return out


async def test_link_header_pages_through_ten_items(client):
    first = await client.get(f"{F}/links/items", params={"per_page": 4})
    assert [i["n"] for i in first.json()] == [1, 2, 3, 4] and first.headers["x-total-count"] == "10"
    ln = links(first.headers["link"])
    assert set(ln) == {"first", "last", "next"} and ln["next"].endswith("?page=2&per_page=4")
    seen, url = [], ln["next"]
    while url:
        page = await client.get(url)
        seen += [i["n"] for i in page.json()]
        url = links(page.headers["link"]).get("next")
    assert seen == [5, 6, 7, 8, 9, 10]


async def test_link_header_edges(client):
    last = await client.get(f"{F}/links/items", params={"page": 3, "per_page": 4})
    assert [i["n"] for i in last.json()] == [9, 10] and set(links(last.headers["link"])) == {"first", "last", "prev"}
    assert (await client.get(f"{F}/links/items", params={"page": 4, "per_page": 4})).status_code == 400
    for bad in ({"page": 0}, {"per_page": 6}, {"per_page": 0}, {"page": "x"}):
        assert (await client.get(f"{F}/links/items", params=bad)).status_code == 400, bad


# ---- an XML request body ----


async def test_xml_note(client):
    ok = await client.post(f"{F}/xml-note", content="<note><text>hello</text></note>", headers={"content-type": "application/xml"})
    assert ok.json() == {"text": "hello", "length": 5}
    for body in ("", "<note><text></text></note>", "<other><text>x</text></other>", "not xml", "<!DOCTYPE x><note><text>x</text></note>",
                 "<note><text>" + "x" * 201 + "</text></note>"):
        assert (await client.post(f"{F}/xml-note", content=body, headers={"content-type": "application/xml"})).status_code == 400, body[:20]
