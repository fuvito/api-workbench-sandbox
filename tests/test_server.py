import asyncio

import pytest
import yaml

from app.config import Settings
from tests.conftest import make_client

PREFIXES = ["/ok", "/contract-fail", "/conform-fail"]


@pytest.mark.parametrize("prefix", PREFIXES)
async def test_health(client, prefix):
    r = await client.get(f"{prefix}/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.parametrize("prefix", PREFIXES)
async def test_spec_served_and_parses(client, prefix):
    r = await client.get(f"{prefix}/openapi.yaml")
    assert r.status_code == 200
    spec = yaml.safe_load(r.text)
    assert spec["openapi"].startswith("3.")
    assert "/__admin/reset" not in spec["paths"]
    assert spec["servers"][0]["url"] == f"http://testserver{prefix}"


async def test_fastapi_own_openapi_is_not_published(client):
    assert (await client.get("/openapi.json")).status_code == 404


async def test_public_base_url_rewrites_servers():
    client, _ = make_client(Settings(public_base_url="https://example.run.app/"))
    async with client:
        r = await client.get("/ok/openapi.yaml")
    assert yaml.safe_load(r.text)["servers"][0]["url"] == "https://example.run.app/ok"


async def test_reset_restores_seed_and_is_isolated(client_app):
    client, app = client_app
    stores = app.state.stores
    await stores["ok"].create("widgets", "w-9", {"id": "w-9"})
    await stores["ok"].delete("widgets", "w-1")
    await stores["conform-fail"].create("widgets", "w-9", {"id": "w-9"})

    assert (await client.post("/ok/__admin/reset")).status_code == 204

    ok_ids = {w["id"] for w in await stores["ok"].list("widgets")}
    assert ok_ids == {"w-1", "w-2"}
    # Another family is untouched by the reset.
    assert await stores["conform-fail"].get("widgets", "w-9") is not None


async def test_state_endpoint(client):
    r = await client.get("/ok/__admin/state")
    assert r.status_code == 200
    assert set(r.json()["widgets"]) == {"w-1", "w-2"}


async def test_admin_token_enforced():
    client, _ = make_client(Settings(admin_token="secret"))
    async with client:
        assert (await client.post("/ok/__admin/reset")).status_code == 401
        bad = await client.post("/ok/__admin/reset", headers={"Authorization": "Bearer no"})
        assert bad.status_code == 401
        good = await client.post("/ok/__admin/reset", headers={"Authorization": "Bearer secret"})
        assert good.status_code == 204
        # Public routes stay open.
        assert (await client.get("/ok/health")).status_code == 200


async def test_stateful_flow_shared_across_requests(client_app):
    client, app = client_app
    store = app.state.stores["ok"]
    assert await store.create("widgets", "w-3", {"id": "w-3", "name": "Gamma"})
    assert not await store.create("widgets", "w-3", {})
    assert (await store.get("widgets", "w-3"))["name"] == "Gamma"
    assert await store.update("widgets", "w-3", {"id": "w-3", "name": "Delta"})
    assert (await store.get("widgets", "w-3"))["name"] == "Delta"
    assert await store.delete("widgets", "w-3")
    assert await store.get("widgets", "w-3") is None
    await client.post("/ok/__admin/reset")
    assert len(await store.list("widgets")) == 2


async def test_concurrent_store_access(client_app):
    _, app = client_app
    store = app.state.stores["ok"]
    results = await asyncio.gather(
        *(store.create("widgets", "same", {"n": i}) for i in range(50))
    )
    assert results.count(True) == 1


def test_settings_from_env():
    s = Settings.from_env({"PORT": "9000", "ADMIN_TOKEN": "t", "LATENCY_SCALE": "0.5", "HOST": ""})
    assert (s.port, s.admin_token, s.latency_scale, s.host) == (9000, "t", 0.5, "127.0.0.1")
    assert Settings.from_env({}).port == 8080
