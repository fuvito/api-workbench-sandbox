# KT — Phase 2e: baseline latency

Last functional piece of the `ok` baseline for timing. `ok.yaml` grows from 55 to 56 operations (`getSlow`) and every list operation gains an optional `delay` parameter.

## What was added

| Piece | Behavior |
|---|---|
| `GET /ok/ok-slow/{ms}` | waits `ms` (0 to 10000), then `200 {"requestedMs": ms}`; out of range or non-integer is `400` |
| `?delay=<ms>` | optional on all eight list operations (products, orders, projects, tasks, customers, payments, invoices, audit events); absent means no delay; same range and `400` rules |
| `LATENCY_SCALE` | multiplies every deliberate delay; 0 to 10, default 1; `0` removes waiting for fast runs |
| Caps | requested delay 10000 ms; scaled sleep at most 30 s; at most 20 slow requests at once, extra ones get `503` |

## Code map

```
app/latency.py       limits, deliberate_delay(request, ms), TooManySlowRequests, slot semaphore
app/ok/listing.py    get_page(): the dependency every list handler now uses (limit, offset, delay)
app/ok/misc.py       the ok-slow handler
app/ok/common.py     Page is now a plain value object; too_many_slow_handler -> 503 in the ok error shape
app/clock.py         + sleep(): the single place a deliberate delay waits
app/main.py          creates app.state.slow_slots, registers the 503 handler
clrsig/scenarios/ok-latency.yaml   slow but correct; used for the timeout checks
tests/test_ok_latency.py           35 tests
```

## How it works

- **Non-blocking:** `await clock.sleep(seconds)` (an `asyncio.sleep`), never `time.sleep`. Tests prove it: 10 concurrent 300 ms requests finish in well under 1.5 s (blocking would take 3 s), and `/ok/health` and `POST /products` answer quickly while another request is sleeping.
- **No lock held while sleeping:** the delay happens in the dependency or handler before any `store.tx()` block, so a slow list never blocks writes.
- **Cap on slow requests:** a semaphore of 20 slots. When none is free the request is refused with `503` (declared in the spec on `getSlow` and the list operations) instead of queueing without bound. The check `slots.locked()` and the acquire have no `await` between them, so they are atomic. A slot is released when the request ends or the client disconnects (tested).
- **Scale applied once:** `scaled_seconds(ms, scale) = min(ms/1000 * scale, 30)`. A test records the exact sleep for scales 0, 0.5, 1 and 2 and for the 30 s cap.
- **Why `clock.sleep`:** tests replace it to see the exact duration without waiting, the same way `utcnow` and `monotonic` are replaced.
- **No import cycle:** `app/latency.py` depends on nothing in `app.ok`; it raises its own exception and `app.ok.common` turns that into the `503` body. Keep it that way so `conform-fail` can reuse it later with its own error shape.

## Verified results (2026-11-21, `clrsig` v0.7.1, Docker image)

- `uv run pytest`: 247 passed.
- `conform` 56/56 operations (the `ok-slow` operation uses `ms=100` from the environment file); `--negative` 38/38 probes.
- All four scenarios pass twice in a row: `ok-crud`, `ok-schemas-and-security`, `ok-business-rules`, `ok-latency`.
- **Timeouts:** `ok-latency` with `--timeout 100` exits 1 and fails exactly the two slow steps ("context deadline exceeded"); the fast control and validation steps still pass. `conform --request-timeout 500` against a 1500 ms delay fails the same way; with the default timeout it passes. In the check catalog this is CS-RUN-003 (No response), but the CLI prints the error text, not the ID.
- **LATENCY_SCALE live:** `ok-slow/1000` took 0.04 s at scale 0, 0.55 s at 0.5, 1.06 s at 1.

## Environment caveat (not a code bug)

On the Windows host, with the server started as a hidden background process, a delay sometimes overshot badly (2000 ms took 3.7 s, 1500 ms took 3.3 s, intermittently). In the Linux container the same requests were exact: 12 of 12 within 6 ms of the requested delay. I believe Windows throttles timers for background processes, but I did not prove the cause. Use the container (or CI) for any timing-sensitive expectation.

## Decisions and open points

- **Report polling delay (task list):** reports progress by poll count (`202`, `202`, then `200`), which the source notes explicitly allow ("N seconds or N polls"). I did not add a wall-clock delay to `GET /reports/{id}`; the task item stays open pending your decision.
- **`503` for the slow-request cap** keeps `ok` deterministic under load by refusing rather than degrading; nothing in normal use reaches 20 concurrent slow requests.
- ClearSignal does not measure response time (CS-GAP-005), so latency is verified through timeouts, not duration assertions.

## ClearSignal finding raised

- **F-007** (cosmetic): `conform` prints an empty `Base URL:` and "No operation got an answer from : is the server running?". See `docs/clrsig-findings.md`.
