"""conform-fail slice 1: lenient operations skip exactly one validation, strict ones enforce all."""

import pytest
import yaml
from pathlib import Path

SPEC = yaml.safe_load((Path(__file__).parent.parent / "specs" / "conform-fail.yaml").read_text(encoding="utf-8"))
P = "/conform-fail"
GOOD = {"Authorization": "Bearer test-token"}
JSON = {"Content-Type": "application/json"}


async def post(client, path, body):
    return await client.post(f"{P}{path}", json=body)


def error_shape(r):
    assert set(r.json()) == {"code", "message"}


# ---- the spec describes both groups the same way ----


def test_every_lenient_operation_has_a_strict_twin():
    paths = set(SPEC["paths"])
    lenient = {p.removeprefix("/lenient") for p in paths if p.startswith("/lenient/")}
    strict = {p.removeprefix("/strict") for p in paths if p.startswith("/strict/")}
    assert lenient == strict and len(lenient) == 7


def test_twins_declare_identical_requests_and_responses():
    for name in ("missing-field", "wrong-type", "missing-query", "no-auth", "wrong-auth", "enum-and-boundary", "unknown-fields"):
        lenient = next(iter(SPEC["paths"][f"/lenient/{name}"].values()))
        strict = next(iter(SPEC["paths"][f"/strict/{name}"].values()))
        for key in ("requestBody", "parameters", "responses", "security"):
            assert lenient.get(key) == strict.get(key), (name, key)  # only the server differs


# ---- (path, body, lenient status, strict status) ----

BODY_MATRIX = [
    # missing-field: the lenient server skips only the presence check
    ("/missing-field", {"name": "Widget"}, 201, 201),
    ("/missing-field", {}, 201, 400),
    ("/missing-field", {"other": 1}, 201, 400),
    ("/missing-field", {"name": 123}, 400, 400),  # types are still checked
    ("/missing-field", {"name": None}, 400, 400),
    ("/missing-field", {"name": ""}, 201, 400),  # minLength is a strict-only rule
    ("/missing-field", [], 400, 400),
    # wrong-type: the lenient server skips only the type check
    ("/wrong-type", {"quantity": 3}, 201, 201),
    ("/wrong-type", {}, 400, 400),  # presence is still checked
    ("/wrong-type", {"quantity": "lots"}, 201, 400),
    ("/wrong-type", {"quantity": True}, 201, 400),
    ("/wrong-type", {"quantity": 1.5}, 201, 400),
    ("/wrong-type", {"quantity": 0}, 201, 400),  # minimum 1
    ("/wrong-type", [], 400, 400),
    # enum-and-boundary: the lenient server checks presence and types, not values
    ("/enum-and-boundary", {"level": "low", "percent": 50}, 201, 201),
    ("/enum-and-boundary", {"level": "extreme", "percent": 50}, 201, 400),
    ("/enum-and-boundary", {"level": "low", "percent": 5000}, 201, 400),
    ("/enum-and-boundary", {"level": "low", "percent": -1}, 201, 400),
    ("/enum-and-boundary", {"percent": 50}, 400, 400),
    ("/enum-and-boundary", {"level": "low"}, 400, 400),
    ("/enum-and-boundary", {"level": 1, "percent": 50}, 400, 400),
    ("/enum-and-boundary", {"level": "low", "percent": "50"}, 400, 400),
    ("/enum-and-boundary", {"level": "low", "percent": True}, 400, 400),
    # unknown-fields: the lenient server ignores extra properties
    ("/unknown-fields", {"name": "Widget"}, 201, 201),
    ("/unknown-fields", {"name": "Widget", "extra": 1}, 201, 400),
    ("/unknown-fields", {}, 400, 400),
    ("/unknown-fields", {"name": 5}, 400, 400),
    ("/unknown-fields", {"name": ""}, 400, 400),
]


@pytest.mark.parametrize("path,body,lenient,strict", BODY_MATRIX)
async def test_body_operations(client, path, body, lenient, strict):
    r = await post(client, f"/lenient{path}", body)
    assert r.status_code == lenient, r.text
    r = await post(client, f"/strict{path}", body)
    assert r.status_code == strict, r.text


@pytest.mark.parametrize("path", ["missing-field", "wrong-type", "enum-and-boundary", "unknown-fields"])
@pytest.mark.parametrize("group", ["lenient", "strict"])
async def test_unreadable_bodies_are_always_400(client, group, path):
    url = f"{P}/{group}/{path}"
    for content in (b"{not json", b"", b"null", b"[1]", b'"text"'):
        r = await client.post(url, content=content, headers=JSON)
        assert r.status_code == 400, (content, r.text)
        error_shape(r)


async def test_created_responses_match_the_declared_shape(client):
    for group in ("lenient", "strict"):
        r = await post(client, f"/{group}/missing-field", {"name": "Widget"})
        assert r.status_code == 201 and r.json() == {"id": 1}


# ---- query parameter ----


async def test_missing_query(client):
    assert (await client.get(f"{P}/lenient/missing-query", params={"q": "abc"})).json() == {"q": "abc"}
    assert (await client.get(f"{P}/strict/missing-query", params={"q": "abc"})).json() == {"q": "abc"}
    lenient = await client.get(f"{P}/lenient/missing-query")
    assert lenient.status_code == 200 and lenient.json() == {"q": ""}  # answers without q
    for url in (f"{P}/strict/missing-query", f"{P}/strict/missing-query?q="):
        r = await client.get(url)
        assert r.status_code == 400
        error_shape(r)


# ---- credentials ----


async def test_no_auth_lenient_never_asks_and_strict_always_does(client):
    for headers in ({}, {"Authorization": "Bearer wrong"}, GOOD):
        assert (await client.get(f"{P}/lenient/no-auth", headers=headers)).status_code == 200
    assert (await client.get(f"{P}/strict/no-auth", headers=GOOD)).json() == {"secret": "s3cret"}
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic dGVzdDp0ZXN0"}, {"Authorization": "Bearer"}):
        r = await client.get(f"{P}/strict/no-auth", headers=headers)
        assert r.status_code == 401
        error_shape(r)


async def test_wrong_auth_lenient_rejects_missing_but_accepts_any_token(client):
    for headers in ({}, {"Authorization": "Basic dGVzdDp0ZXN0"}, {"Authorization": "Bearer"}):
        assert (await client.get(f"{P}/lenient/wrong-auth", headers=headers)).status_code == 401
    for token in ("test-token", "anything", "x"):
        assert (await client.get(f"{P}/lenient/wrong-auth", headers={"Authorization": f"Bearer {token}"})).status_code == 200


async def test_wrong_auth_strict_accepts_only_the_real_token(client):
    assert (await client.get(f"{P}/strict/wrong-auth", headers=GOOD)).status_code == 200
    for headers in ({}, {"Authorization": "Bearer anything"}, {"Authorization": "bearer test-token-x"}):
        assert (await client.get(f"{P}/strict/wrong-auth", headers=headers)).status_code == 401


# ---- the group is stateless and isolated ----


async def test_these_operations_keep_no_state(client):
    before = (await client.get(f"{P}/__admin/state")).json()
    await post(client, "/lenient/missing-field", {})
    await post(client, "/strict/wrong-type", {"quantity": 2})
    assert (await client.get(f"{P}/__admin/state")).json() == before
    assert (await client.post(f"{P}/__admin/reset")).status_code == 204
