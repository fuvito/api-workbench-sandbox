"""conform-fail slice 2: the spec and the server disagree about what exists."""

import socket
from pathlib import Path

import yaml

from app.conform_fail import disagree

SPEC = yaml.safe_load((Path(__file__).parent.parent / "specs" / "conform-fail.yaml").read_text(encoding="utf-8"))
P = "/conform-fail"
UUID = "3f2b8c1e-5d4a-4c8e-9a7b-1e2d3c4b5a69"


def declared(method: str, path: str) -> bool:
    return method.lower() in SPEC["paths"].get(path, {})


# ---- what the spec declares and what the server really has ----


def test_the_spec_declares_what_the_cases_say():
    assert declared("get", "/ghost") and declared("delete", "/orphan") and declared("patch", "/wrong-method")
    assert SPEC["paths"]["/ghost"]["get"]["responses"].keys() == {"200"}  # 404 stays undeclared
    assert SPEC["paths"]["/orphan"]["delete"]["responses"].keys() == {"204"}
    assert SPEC["paths"]["/requires-extra-header"]["post"]["responses"].keys() == {"201"}
    assert "parameters" not in SPEC["paths"]["/requires-extra-header"]["post"]  # the header is never mentioned
    assert SPEC["paths"]["/path-param/{id}"]["get"]["parameters"][0]["schema"]["type"] == "integer"


def test_undocumented_operations_are_really_absent_from_the_spec():
    for method, path in disagree.UNDOCUMENTED_OPERATIONS:
        assert not declared(method, path), (method, path)


def test_the_form_bodies_are_required_and_the_callback_is_outside_paths():
    for path, media in (("/form", "application/x-www-form-urlencoded"), ("/multipart", "multipart/form-data")):
        body = SPEC["paths"][path]["post"]["requestBody"]
        assert body["required"] is True and list(body["content"]) == [media]
    assert "onEvent" in SPEC["paths"]["/subscribe"]["post"]["callbacks"]
    assert "webhooks" not in SPEC  # OpenAPI 3.0 has callbacks only


# ---- /ghost: declared, not served ----


async def test_ghost_has_no_route(client):
    assert (await client.get(f"{P}/ghost")).status_code == 404
    assert (await client.post(f"{P}/ghost")).status_code == 404


# ---- /orphan: DELETE is declared, only POST is implemented ----


async def test_orphan_delete_is_405_and_only_post_exists(client):
    r = await client.delete(f"{P}/orphan")
    assert r.status_code == 405 and r.headers["allow"] == "POST"
    assert (await client.post(f"{P}/orphan")).status_code == 200


# ---- /wrong-method: PATCH is declared, only PUT is implemented ----


async def test_wrong_method_patch_is_405_and_put_works(client):
    r = await client.patch(f"{P}/wrong-method", json={"name": "x"})
    assert r.status_code == 405 and r.headers["allow"] == "PUT"
    assert (await client.put(f"{P}/wrong-method", json={"name": "x"})).status_code == 200


# ---- /path-param/{id}: integer in the spec, UUID on the server ----


async def test_path_param_accepts_only_uuids(client):
    assert (await client.get(f"{P}/path-param/{UUID}")).json() == {"id": 1}
    assert (await client.get(f"{P}/path-param/{UUID.upper()}")).status_code == 200
    for bad in ("1", "42", "abc", UUID[:-1], UUID + "x", "not-a-uuid"):
        r = await client.get(f"{P}/path-param/{bad}")
        assert r.status_code == 400 and set(r.json()) == {"code", "message"}, bad


# ---- /requires-extra-header ----


async def test_extra_header_is_required_but_undeclared(client):
    r = await client.post(f"{P}/requires-extra-header")
    assert r.status_code == 400 and set(r.json()) == {"code", "message"}
    assert (await client.post(f"{P}/requires-extra-header", headers={"X-Tenant": ""})).status_code == 400
    r = await client.post(f"{P}/requires-extra-header", headers={"X-Tenant": "acme"})
    assert r.status_code == 201 and r.json() == {"id": 1}


# ---- /undocumented ----


async def test_undocumented_route_exists(client):
    assert (await client.get(f"{P}/undocumented")).json() == {"id": 1}
    assert "/undocumented" not in SPEC["paths"]


# ---- /form and /multipart: the server really does handle them ----


async def test_form_accepts_a_real_form_and_rejects_everything_else(client):
    assert (await client.post(f"{P}/form", data={"name": "Widget"})).status_code == 201
    for kwargs in (
        {},  # no body at all, which is what ClearSignal v0.7.1 sends
        {"data": {"other": "x"}},
        {"data": {"name": ""}},
        {"json": {"name": "Widget"}},  # right content, wrong media type
    ):
        r = await client.post(f"{P}/form", **kwargs)
        assert r.status_code == 400 and set(r.json()) == {"code", "message"}, kwargs


async def test_multipart_accepts_a_real_multipart_and_rejects_everything_else(client):
    assert (await client.post(f"{P}/multipart", files={"name": (None, "Widget")})).status_code == 201
    assert (await client.post(f"{P}/multipart", files={"name": (None, "Widget"), "extra": (None, "x")})).status_code == 201
    for kwargs in (
        {},
        {"files": {"other": (None, "x")}},
        {"data": {"name": "Widget"}},  # urlencoded, not multipart
        {"json": {"name": "Widget"}},
    ):
        assert (await client.post(f"{P}/multipart", **kwargs)).status_code == 400, kwargs


# ---- /subscribe: validated, and never contacted ----


async def test_subscribe_validates_the_url_and_never_calls_it(client, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("the server tried to open a network connection")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    for url in ("https://example.com/hook", "http://localhost:1/x", "http://169.254.169.254/latest"):
        r = await client.post(f"{P}/subscribe", json={"callbackUrl": url})
        assert r.status_code == 201 and r.json() == {"id": 1}  # accepted, never fetched
    for body in ({}, {"callbackUrl": 5}, {"callbackUrl": "ftp://x/y"}, {"callbackUrl": "not a url"}, [], {"url": "https://x.com"}):
        assert (await client.post(f"{P}/subscribe", json=body)).status_code == 400, body
    assert (await client.post(f"{P}/subscribe", content=b"{bad", headers={"Content-Type": "application/json"})).status_code == 400


# ---- the group keeps no state ----


async def test_slice_two_keeps_no_state(client):
    before = (await client.get(f"{P}/__admin/state")).json()
    await client.post(f"{P}/subscribe", json={"callbackUrl": "https://example.com/hook"})
    await client.post(f"{P}/form", data={"name": "x"})
    assert (await client.get(f"{P}/__admin/state")).json() == before
