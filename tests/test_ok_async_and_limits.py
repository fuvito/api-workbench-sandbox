"""Step 3c: async report progression and the rate limit."""

import asyncio

import pytest

from app import clock
from tests.test_ok_api import assert_error


# ---- async report ----


async def test_report_runs_for_two_polls_then_completes(client):
    r = await client.post("/ok/reports", json={"type": "inventory"})
    assert r.status_code == 202
    assert r.json() == {"id": "rep-2", "type": "inventory", "status": "running"}
    assert r.headers["location"] == "/ok/reports/rep-2"
    assert r.headers["retry-after"] == "1"

    path = r.headers["location"]
    first = await client.get(path)
    second = await client.get(path)
    assert (first.status_code, second.status_code) == (202, 202)
    assert first.json()["status"] == "running" and "result" not in first.json()
    assert first.headers["retry-after"] == "1"

    third = await client.get(path)
    assert third.status_code == 200
    assert third.json() == {
        "id": "rep-2",
        "type": "inventory",
        "status": "done",
        "result": {"rows": 3, "report": "inventory"},
    }
    assert "retry-after" not in third.headers
    assert (await client.get(path)).status_code == 200  # stays done


async def test_posting_does_not_count_as_a_poll(client):
    r = await client.post("/ok/reports", json={"type": "sales"})
    statuses = [(await client.get(r.headers["location"])).status_code for _ in range(4)]
    assert statuses == [202, 202, 200, 200]


async def test_reports_progress_independently(client):
    a = (await client.post("/ok/reports", json={"type": "sales"})).headers["location"]
    b = (await client.post("/ok/reports", json={"type": "sales"})).headers["location"]
    for _ in range(3):
        await client.get(a)
    assert (await client.get(a)).status_code == 200
    assert (await client.get(b)).status_code == 202  # b was polled only once so far


async def test_seeded_report_and_reset(client):
    assert (await client.get("/ok/reports/rep-1")).status_code == 202
    for _ in range(3):
        await client.get("/ok/reports/rep-1")
    assert (await client.get("/ok/reports/rep-1")).status_code == 200
    await client.post("/ok/__admin/reset")
    assert (await client.get("/ok/reports/rep-1")).status_code == 202  # running again


async def test_concurrent_polls_each_count_once(client):
    results = await asyncio.gather(*(client.get("/ok/reports/rep-1") for _ in range(10)))
    assert sorted(r.status_code for r in results) == [200] * 8 + [202] * 2


@pytest.mark.parametrize("body", [{}, {"type": "weekly"}, {"type": "sales", "x": 1}, {"type": 1}])
async def test_invalid_report_request_is_400(client, body):
    assert_error(await client.post("/ok/reports", json=body), 400)


async def test_unknown_report_is_404(client):
    assert_error(await client.get("/ok/reports/nope"), 404)


# ---- rate limit ----


@pytest.fixture
def ticking(monkeypatch):
    """A controllable monotonic clock."""
    now = {"t": 1000.0}
    monkeypatch.setattr(clock, "monotonic", lambda: now["t"])
    return now


async def test_sixth_call_in_the_window_is_429(client, ticking):
    remaining = []
    for _ in range(5):
        r = await client.get("/ok/rate-limited")
        assert r.status_code == 200 and r.headers["x-ratelimit-limit"] == "5"
        remaining.append(int(r.headers["x-ratelimit-remaining"]))
        assert r.json()["remaining"] == remaining[-1]
    assert remaining == [4, 3, 2, 1, 0]

    r = await client.get("/ok/rate-limited")
    assert_error(r, 429)
    assert r.headers["retry-after"] == "60"
    assert r.headers["x-ratelimit-limit"] == "5" and r.headers["x-ratelimit-remaining"] == "0"


async def test_retry_after_shrinks_and_window_reopens(client, ticking):
    for _ in range(5):
        await client.get("/ok/rate-limited")
    ticking["t"] += 20
    assert (await client.get("/ok/rate-limited")).headers["retry-after"] == "40"
    ticking["t"] += 39.5
    assert (await client.get("/ok/rate-limited")).status_code == 429
    ticking["t"] += 0.5  # window is 60 s from the first call
    r = await client.get("/ok/rate-limited")
    assert r.status_code == 200 and r.headers["x-ratelimit-remaining"] == "4"


async def test_limits_are_per_client(client, ticking):
    for _ in range(5):
        await client.get("/ok/rate-limited", headers={"X-Client-Id": "alice"})
    assert_error(await client.get("/ok/rate-limited", headers={"X-Client-Id": "alice"}), 429)
    assert (await client.get("/ok/rate-limited", headers={"X-Client-Id": "bob"})).status_code == 200
    assert (await client.get("/ok/rate-limited")).status_code == 200  # the address is another client


async def test_reset_clears_every_counter(client, ticking):
    for _ in range(5):
        await client.get("/ok/rate-limited")
    assert (await client.get("/ok/rate-limited")).status_code == 429
    await client.post("/ok/__admin/reset")
    assert (await client.get("/ok/rate-limited")).status_code == 200


async def test_only_the_limited_endpoint_throttles(client, ticking):
    for _ in range(8):
        await client.get("/ok/rate-limited")
    for path in ("/ok/health", "/ok/products", "/ok/orders"):
        assert (await client.get(path)).status_code == 200


async def test_concurrent_calls_never_exceed_the_limit(client, ticking):
    results = await asyncio.gather(*(client.get("/ok/rate-limited") for _ in range(12)))
    assert sorted(r.status_code for r in results) == [200] * 5 + [429] * 7


@pytest.mark.parametrize("value", ["", "x" * 65])
async def test_bad_client_id_is_400(client, value):
    assert_error(await client.get("/ok/rate-limited", headers={"X-Client-Id": value}), 400)
