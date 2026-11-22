"""Request-body limit, and the other caps the release review checks."""

import asyncio

import httpx
import pytest

from app import latency
from app.limits import MAX_BODY_BYTES
from tests.conftest import make_client
from app.config import Settings

OVER = b'{"name":"' + b"x" * MAX_BODY_BYTES + b'"}'


@pytest.mark.parametrize("path", ["/ok/products", "/contract-fail/cases/control-ok", "/conform-fail/lenient/missing-field", "/conform-fail/rules/orders"])
async def test_a_body_over_the_limit_is_413_in_every_family(client, path):
    r = await client.post(path, content=OVER, headers={"Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.json()["code"] == "payload_too_large"


async def test_a_body_at_the_limit_is_read(client):
    body = b'{"name":"' + b"x" * (MAX_BODY_BYTES - 20) + b'"}'
    assert len(body) <= MAX_BODY_BYTES
    r = await client.post("/ok/products", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code != 413  # refused for another reason (validation), but it was read


async def test_a_chunked_body_without_content_length_is_counted(client):
    async def chunks():
        for _ in range(MAX_BODY_BYTES // 1000 + 5):
            yield b"x" * 1000

    r = await client.post("/ok/products", content=chunks(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


async def test_a_refused_request_is_logged_and_changes_nothing(client, caplog):
    before = (await client.get("/ok/products")).json()
    with caplog.at_level("INFO"):
        await client.post("/ok/products", content=OVER, headers={"Content-Type": "application/json"})
    assert any('"status": 413' in m for m in caplog.messages)
    assert (await client.get("/ok/products")).json() == before


async def test_the_slow_request_limit_is_bounded_and_answers_503():
    client, app = make_client(Settings(latency_scale=0.01))
    async with client:
        assert latency.MAX_CONCURRENT_SLOW == 20
        slots = app.state.slow_slots
        held = [await slots.acquire() for _ in range(latency.MAX_CONCURRENT_SLOW)]
        r = await client.get("/ok/ok-slow/1000")
        assert r.status_code == 503, r.text
        for _ in held:
            slots.release()
        assert (await client.get("/ok/ok-slow/1")).status_code == 200


async def test_delays_above_the_cap_are_refused(client):
    assert (await client.get(f"/ok/ok-slow/{latency.MAX_DELAY_MS + 1}")).status_code == 400
    assert (await client.get("/conform-fail/large", params={"mb": 61})).status_code == 400
