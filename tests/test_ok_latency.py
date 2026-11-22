"""Baseline latency: ok-slow, the list `delay` parameter, LATENCY_SCALE, caps, non-blocking."""

import asyncio
import time

import pytest

from app import clock, latency
from app.config import Settings
from tests.conftest import make_client
from tests.test_ok_api import assert_error

LISTS = [
    "/ok/products",
    "/ok/orders",
    "/ok/projects",
    "/ok/projects/pr-1/tasks",
    "/ok/customers",
    "/ok/payments",
    "/ok/invoices",
]
AUDIT = ("/ok/audit-events", {"Authorization": "Basic dGVzdC11c2VyOnRlc3QtcGFzcw=="})


@pytest.fixture
def slept(monkeypatch):
    """Record requested sleep durations instead of really waiting."""
    calls: list[float] = []

    async def fake(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(clock, "sleep", fake)
    return calls


async def with_scale(scale):
    client, app = make_client(Settings(latency_scale=scale))
    return client, app


# ---- ok-slow ----


async def test_ok_slow_waits_the_requested_time_and_answers_per_spec(client, slept):
    r = await client.get("/ok/ok-slow/250")
    assert r.status_code == 200 and r.json() == {"requestedMs": 250}
    assert slept == [0.25]


async def test_zero_ms_does_not_sleep(client, slept):
    assert (await client.get("/ok/ok-slow/0")).status_code == 200
    assert slept == []


@pytest.mark.parametrize("ms", ["-1", "10001", "abc", "1.5", "99999999"])
async def test_ok_slow_rejects_out_of_range_input(client, slept, ms):
    assert_error(await client.get(f"/ok/ok-slow/{ms}"), 400)
    assert slept == []


async def test_cap_is_inclusive(client, slept):
    assert (await client.get("/ok/ok-slow/10000")).status_code == 200
    assert slept == [10.0]


# ---- LATENCY_SCALE ----


@pytest.mark.parametrize("scale,expected", [(0.5, 0.1), (2, 0.4), (0, 0.0), (1, 0.2)])
async def test_latency_scale_multiplies_every_delay(slept, scale, expected):
    client, _ = await with_scale(scale)
    async with client:
        await client.get("/ok/ok-slow/200")
        await client.get("/ok/products", params={"delay": 200})
    # scale 0 means "no waiting at all": nothing is slept or an instant sleep is requested
    assert [round(x, 6) for x in slept] == [expected, expected] or (scale == 0 and all(x == 0 for x in slept))


async def test_scaled_sleep_is_bounded(slept):
    client, _ = await with_scale(10)
    async with client:
        await client.get("/ok/ok-slow/10000")  # 10 s x 10 = 100 s, capped
    assert slept == [latency.MAX_SLEEP_SECONDS]


def test_settings_bound_the_scale():
    with pytest.raises(ValueError):
        Settings(latency_scale=11)
    with pytest.raises(ValueError):
        Settings(latency_scale=-1)
    assert Settings.from_env({"LATENCY_SCALE": "0"}).latency_scale == 0


# ---- list delay ----


@pytest.mark.parametrize("path", LISTS)
async def test_every_list_accepts_a_bounded_delay(client, slept, path):
    assert (await client.get(path)).status_code == 200
    assert slept == []  # absent means no delay
    r = await client.get(path, params={"delay": 150})
    assert r.status_code == 200 and slept == [0.15]


async def test_secured_list_also_takes_delay(client, slept):
    path, headers = AUDIT
    r = await client.get(path, params={"delay": 100}, headers=headers)
    assert r.status_code == 200 and slept == [0.1]


@pytest.mark.parametrize("delay", ["-1", "10001", "abc", "1.5", ""])
async def test_list_delay_is_validated(client, slept, delay):
    assert_error(await client.get("/ok/products", params={"delay": delay}), 400)
    assert slept == []


async def test_delay_does_not_change_the_result(client, slept):
    plain = await client.get("/ok/products", params={"sort": "name"})
    slow = await client.get("/ok/products", params={"sort": "name", "delay": 500})
    assert plain.json() == slow.json() and plain.headers["x-total-count"] == slow.headers["x-total-count"]


# ---- non-blocking, bounded concurrency, no lock held while sleeping ----


async def test_delays_run_concurrently_not_one_after_another():
    client, _ = await with_scale(1)
    async with client:
        start = time.perf_counter()
        results = await asyncio.gather(*(client.get("/ok/ok-slow/300") for _ in range(10)))
        elapsed = time.perf_counter() - start
    assert all(r.status_code == 200 for r in results)
    # blocking waits would take 10 x 0.3 s = 3 s; async waits overlap
    assert elapsed < 1.5


async def test_other_requests_are_served_while_one_is_sleeping():
    client, _ = await with_scale(1)
    async with client:
        slow = asyncio.create_task(client.get("/ok/ok-slow/600"))
        await asyncio.sleep(0.05)  # let it start sleeping
        start = time.perf_counter()
        assert (await client.get("/ok/health")).status_code == 200
        assert time.perf_counter() - start < 0.3
        assert (await slow).status_code == 200


async def test_store_lock_is_not_held_while_sleeping():
    client, _ = await with_scale(1)
    async with client:
        slow = asyncio.create_task(client.get("/ok/products", params={"delay": 600}))
        await asyncio.sleep(0.05)
        start = time.perf_counter()
        r = await client.post("/ok/products", json={"name": "Fast", "price": 1, "stock": 1})
        assert r.status_code == 201 and time.perf_counter() - start < 0.3  # writes are not blocked
        assert (await slow).status_code == 200


async def test_too_many_concurrent_slow_requests_get_503(monkeypatch):
    client, app = await with_scale(1)
    app.state.slow_slots = asyncio.Semaphore(2)  # shrink the cap for the test
    async with client:
        results = await asyncio.gather(*(client.get("/ok/ok-slow/300") for _ in range(4)))
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 200, 503, 503]
    rejected = next(r for r in results if r.status_code == 503)
    assert set(rejected.json()) == {"code", "message"}


async def test_slots_are_released_after_each_request(monkeypatch):
    client, app = await with_scale(1)
    app.state.slow_slots = asyncio.Semaphore(1)
    async with client:
        for _ in range(3):
            assert (await client.get("/ok/ok-slow/20")).status_code == 200


async def test_slot_is_released_when_the_client_gives_up(monkeypatch):
    client, app = await with_scale(1)
    app.state.slow_slots = asyncio.Semaphore(1)
    async with client:
        task = asyncio.create_task(client.get("/ok/ok-slow/2000"))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.05)
        assert (await client.get("/ok/ok-slow/10")).status_code == 200


def test_cap_constants_match_the_documented_limits():
    assert latency.MAX_DELAY_MS == 10_000
    assert latency.MAX_CONCURRENT_SLOW == 20
