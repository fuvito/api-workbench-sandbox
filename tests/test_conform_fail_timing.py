"""conform-fail slice 4: timing and instability, deterministic logic (the sleep is observed, not waited)."""

import json

import pytest

from app import clock
from app.conform_fail import timing
from tests.test_ok_api import assert_error

P = "/conform-fail"


@pytest.fixture
def slept(monkeypatch):
    """Record every deliberate sleep instead of waiting."""
    calls: list[float] = []

    async def fake(seconds: float) -> None:
        calls.append(seconds)

    monkeypatch.setattr(clock, "sleep", fake)
    return calls


async def statuses(client, path, n, **kwargs):
    return [(await client.get(f"{P}{path}", **kwargs)).status_code for _ in range(n)]


# ---- counted failures ----


async def test_flaky_fails_every_third_call(client):
    assert await statuses(client, "/flaky", 7) == [200, 200, 500, 200, 200, 500, 200]
    r = await client.get(f"{P}/flaky")  # call 8 passes, call 9 fails
    assert r.json() == {"ok": True, "call": 8}
    r = await client.get(f"{P}/flaky")
    assert r.status_code == 500 and set(r.json()) == {"code", "message"}


async def test_flaky_counter_is_restored_by_reset(client):
    await statuses(client, "/flaky", 2)
    assert (await client.post(f"{P}/__admin/reset")).status_code == 204
    assert await statuses(client, "/flaky", 3) == [200, 200, 500]  # the sequence starts over


async def test_rate_limited_after_three_calls(client):
    assert await statuses(client, "/rate-limited", 6) == [200, 200, 200, 429, 429, 429]
    r = await client.get(f"{P}/rate-limited")
    assert r.status_code == 429 and r.headers["retry-after"] == "60" and set(r.json()) == {"code", "message"}
    await client.post(f"{P}/__admin/reset")
    assert (await client.get(f"{P}/rate-limited")).status_code == 200


async def test_unavailable_is_always_503_with_retry_after(client):
    for _ in range(3):
        r = await client.get(f"{P}/unavailable")
        assert r.status_code == 503 and r.headers["retry-after"] == "1"


async def test_unavailable_then_ok(client):
    assert await statuses(client, "/unavailable-then-ok", 5) == [503, 503, 200, 200, 200]
    r = await client.get(f"{P}/unavailable-then-ok")
    assert r.json() == {"ok": True, "call": 6}
    await client.post(f"{P}/__admin/reset")
    assert await statuses(client, "/unavailable-then-ok", 3) == [503, 503, 200]


async def test_counters_are_independent(client):
    await statuses(client, "/flaky", 2)
    assert (await client.get(f"{P}/rate-limited")).json()["call"] == 1
    assert (await client.get(f"{P}/unavailable-then-ok")).status_code == 503
    assert (await client.get(f"{P}/flaky")).status_code == 500  # its own third call


# ---- delays ----


async def test_slow_waits_longer_than_the_default_client_timeout(client, slept):
    assert (await client.get(f"{P}/slow")).status_code == 200
    assert slept == [15.0] and slept[0] > 10  # ClearSignal's default timeout is 10 s


@pytest.mark.parametrize("ms,seconds", [(0, []), (1, [0.001]), (250, [0.25]), (30000, [30.0])])
async def test_fixed_latency(client, slept, ms, seconds):
    r = await client.get(f"{P}/latency/{ms}")
    assert r.status_code == 200 and r.json() == {"ok": True, "delayMs": ms}
    assert slept == seconds


@pytest.mark.parametrize("ms", ["30001", "-1", "abc", "1.5", "999999999"])
async def test_fixed_latency_is_bounded_and_validated(client, slept, ms):
    assert_error(await client.get(f"{P}/latency/{ms}"), 400)
    assert slept == []


async def test_jitter_is_a_fixed_sequence_that_reset_restores(client, slept):
    expected = [160, 906, 477, 477, 507, 264]  # seeded: the same on every machine
    first = [(await client.get(f"{P}/latency/jitter")).json()["delayMs"] for _ in expected]
    assert first == expected and slept == [d / 1000 for d in expected]
    await client.post(f"{P}/__admin/reset")
    again = [(await client.get(f"{P}/latency/jitter")).json()["delayMs"] for _ in expected]
    assert again == first


async def test_jitter_stays_inside_the_requested_range(client, slept):
    for _ in range(40):
        delay = (await client.get(f"{P}/latency/jitter", params={"min": 50, "max": 80})).json()["delayMs"]
        assert 50 <= delay <= 80
    r = await client.get(f"{P}/latency/jitter", params={"min": 70, "max": 70})
    assert r.json()["delayMs"] == 70  # a one-value range


@pytest.mark.parametrize("params", [{"min": 500, "max": 100}, {"min": -1}, {"max": 30001}, {"min": "x"}])
async def test_jitter_validates_its_range(client, slept, params):
    assert_error(await client.get(f"{P}/latency/jitter", params=params), 400)
    assert slept == []


async def test_degrading_latency_grows_and_is_capped(client, slept):
    delays = [(await client.get(f"{P}/latency/degrading")).json()["delayMs"] for _ in range(20)]
    assert delays[:7] == [100, 400, 700, 1000, 1300, 1600, 1900]
    assert delays[-1] == 5000 and max(delays) == 5000  # capped
    assert delays == sorted(delays)  # never faster than the call before
    assert slept == [d / 1000 for d in delays]


async def test_degrading_latency_restarts_after_reset(client, slept):
    for _ in range(4):
        await client.get(f"{P}/latency/degrading")
    await client.post(f"{P}/__admin/reset")
    assert (await client.get(f"{P}/latency/degrading")).json() == {"ok": True, "call": 1, "delayMs": 100}


async def test_delays_follow_latency_scale(slept):
    from app.config import Settings
    from tests.conftest import make_client

    client, _ = make_client(Settings(latency_scale=0.1))
    async with client:
        await client.get(f"{P}/slow")
        await client.get(f"{P}/latency/degrading")
    assert [round(s, 6) for s in slept] == [1.5, 0.01]


# ---- redirect loop ----


async def test_redirect_loop_only_ever_points_at_itself(client):
    r = await client.get(f"{P}/redirect-loop")
    assert r.status_code == 302 and r.headers["location"] == f"{P}/redirect-loop"
    assert "://" not in r.headers["location"]  # never another host


# ---- large bodies ----


@pytest.mark.parametrize("mb", [0, 1, 2])
async def test_large_binary_has_the_declared_size(client, mb):
    r = await client.get(f"{P}/large", params={"mb": mb})
    assert r.status_code == 200 and r.headers["content-type"] == "application/octet-stream"
    assert len(r.content) == mb * 1024 * 1024 == int(r.headers["content-length"])


@pytest.mark.parametrize("mb", [0, 1, 2])
async def test_large_json_is_valid_json_of_that_size(client, mb):
    r = await client.get(f"{P}/large/json", params={"mb": mb})
    assert int(r.headers["content-length"]) == len(r.content)
    data = json.loads(r.content)
    assert len(data["data"]) == mb * 1024 * 1024


@pytest.mark.parametrize("path", ["/large", "/large/json"])
@pytest.mark.parametrize("params", [{}, {"mb": 61}, {"mb": -1}, {"mb": "x"}])
async def test_large_is_bounded_and_validated(client, path, params):
    assert_error(await client.get(f"{P}{path}", params=params), 400)


def test_the_large_cap_sits_above_clearsignals_read_cap():
    assert timing.LARGE_MAX_MB > 50  # ClearSignal reads at most 50 MB; the cases must reach past it


# ---- write, then a late answer ----


async def test_the_write_happens_before_the_wait(client, monkeypatch):
    seen = []

    async def spy(seconds):
        seen.append((seconds, (await client.get(f"{P}/timeout/after-write/records")).json()["total"]))

    monkeypatch.setattr(clock, "sleep", spy)
    assert (await client.post(f"{P}/timeout/after-write")).status_code == 201
    assert seen == [(15.0, 1)]  # while the request was "stuck", the record already existed


async def test_after_write_records_accumulate_and_reset_clears_them(client, slept):
    for _ in range(3):
        await client.post(f"{P}/timeout/after-write")
    records = (await client.get(f"{P}/timeout/after-write/records")).json()
    assert records["total"] == 3 and [i["id"] for i in records["items"]] == ["w-1", "w-2", "w-3"]
    await client.post(f"{P}/__admin/reset")
    assert (await client.get(f"{P}/timeout/after-write/records")).json()["total"] == 0


async def test_record_cases_are_bounded(client, slept, monkeypatch):
    monkeypatch.setattr(timing, "MAX_RECORDS", 2)
    assert [(await client.post(f"{P}/timeout/after-write")).status_code for _ in range(3)] == [201, 201, 422]
    assert [(await client.post(f"{P}/idempotent")).status_code for _ in range(3)] == [201, 201, 422]


# ---- idempotency that is not, lost update ----


async def test_a_repeated_idempotency_key_creates_a_second_record(client):
    for _ in range(2):
        assert (await client.post(f"{P}/idempotent", headers={"Idempotency-Key": "order-42"})).status_code == 201
    records = (await client.get(f"{P}/idempotent/records")).json()
    assert records["total"] == 2  # the bug, on purpose: a correct server would have one
    assert [i["key"] for i in records["items"]] == ["order-42", "order-42"]


async def test_idempotent_without_a_key_and_with_a_bad_key(client):
    assert (await client.post(f"{P}/idempotent")).status_code == 201
    assert_error(await client.post(f"{P}/idempotent", headers={"Idempotency-Key": ""}), 400)
    assert_error(await client.post(f"{P}/idempotent", headers={"Idempotency-Key": "x" * 65}), 400)


async def test_lost_update_ignores_if_match(client):
    first = await client.get(f"{P}/lost-update")
    assert first.json() == {"value": "initial", "version": 1}
    stale = first.headers["etag"]
    a = await client.put(f"{P}/lost-update", json={"value": "alice"}, headers={"If-Match": stale})
    b = await client.put(f"{P}/lost-update", json={"value": "bob"}, headers={"If-Match": stale})  # stale now
    assert (a.status_code, b.status_code) == (200, 200)  # a correct server refuses the second with 412
    assert (await client.get(f"{P}/lost-update")).json() == {"value": "bob", "version": 3}
    assert a.headers["etag"] != b.headers["etag"] != stale


@pytest.mark.parametrize("headers", [{}, {"If-Match": '"garbage"'}, {"If-Match": "*"}])
async def test_lost_update_accepts_any_or_no_if_match(client, headers):
    assert (await client.put(f"{P}/lost-update", json={"value": "x"}, headers=headers)).status_code == 200


@pytest.mark.parametrize("body", [{}, {"value": ""}, {"value": 5}, [], None])
async def test_lost_update_validates_the_body(client, body):
    assert_error(await client.put(f"{P}/lost-update", json=body), 400)


# ---- transport cases, in-process view ----


async def test_hang_and_slow_headers_wait_before_answering(client, slept):
    assert (await client.get(f"{P}/timeout/hang")).status_code == 200
    assert (await client.get(f"{P}/timeout/slow-headers")).status_code == 200
    assert slept == [30.0, 4.0]


async def test_slow_body_trickles_one_byte_at_a_time(client, slept):
    r = await client.get(f"{P}/timeout/slow-body")
    assert len(r.content) == 50 == int(r.headers["content-length"])
    assert json.loads(r.content)["ok"] is True
    assert slept == [0.2] * 49  # a wait before every byte but the first (10 s in all)


async def test_truncated_body_declares_more_than_it_sends(client):
    r = await client.get(f"{P}/timeout/truncated-body")
    assert r.headers["content-length"] == "1000" and len(r.content) == 100


async def test_connection_reset_needs_a_real_server(client):
    # The in-process client has no socket to abort, so the handler falls back to an empty 204;
    # the real behavior is tested through a live server in test_conform_fail_transport.py.
    assert (await client.get(f"{P}/timeout/connection-reset")).status_code == 204


async def test_timing_cases_keep_no_state_besides_their_counters(client, slept):
    await statuses(client, "/flaky", 2)
    state = (await client.get(f"{P}/__admin/state")).json()
    assert state["counters"] == {"flaky": {"id": "flaky", "n": 2}}
    assert state["writes"] == {} and state["idempotent"] == {}
    await client.post(f"{P}/__admin/reset")
    assert (await client.get(f"{P}/__admin/state")).json()["counters"] == {}
