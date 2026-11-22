# KT — Phase 4d: timing and instability

Fourth slice of `conform-fail`: servers that are slow, flaky, throttled, unavailable, redirecting, or that cut the connection. `specs/conform-fail.yaml` goes from 25 to 47 operations. Everything here follows the project rules: every wait is a bounded, `LATENCY_SCALE`-scaled `await` that never holds the store lock; every state-dependent behavior is a counter in the family's store that `POST /conform-fail/__admin/reset` restores; nothing runs in the background; nothing contacts another host.

## The behaviors

| Operation | Does | ClearSignal result (v0.7.1) |
|---|---|---|
| `GET /slow` | answers after 15 s (times `LATENCY_SCALE`) | no response with the default 10 s timeout (CS-RUN-003) |
| `GET /flaky` | every 3rd call is an undeclared 500 | pass, pass, fail, repeating (CS-RESP-001) |
| `GET /rate-limited` | the 4th call and later get an undeclared 429 with `Retry-After` | P P P F F F (CS-RESP-001) |
| `GET /latency/{ms}` | answers after exactly `ms` (0 to 30000) | passes unless the timeout is shorter; time is not measured |
| `GET /latency/jitter` | a seeded delay per call number, defaults 100 to 1000 ms | the same sequence after every reset |
| `GET /latency/degrading` | 100 ms, then +300 ms per call, capped at 5 s | gets slower each call until a timeout fails it |
| `GET /unavailable`, `/unavailable-then-ok` | a 503 with `Retry-After` (always, or for the first 2 calls after reset) | undeclared 503 (CS-RESP-001); ClearSignal never retries |
| `GET /redirect-loop` | redirects only to itself | `no-response`, "stopped after 10 redirects" (CS-RUN-003) |
| `GET /large`, `/large/json` | a body of `mb` megabytes (0 to 60) | 49 MB passes; **51 MB is silently truncated** (F-019) |
| `POST /timeout/after-write` | stores a record, answers 15 s later | times out, and the record exists anyway |
| `POST /idempotent`, `PUT /lost-update` | ignore `Idempotency-Key` and `If-Match` | visible only in a scenario |
| `GET /timeout/hang`, `/slow-headers`, `/slow-body` | 30 s silence; 4 s before headers; headers at once then 5 bytes per second | `no-response` when the timeout is shorter |
| `GET /timeout/truncated-body`, `/connection-reset` | declares 1000 bytes and sends 100; a TCP reset with no answer | `no-response` ("unexpected EOF", "EOF"): **CS-RUN-003, not CS-RESP-008** (the notes asked to record which) |

The delays are constants in `app/conform_fail/timing.py` and are repeated in the spec descriptions; tests assert the exact values (`SLOW_MS`, `FLAKY_EVERY`, the jitter and degrading sequences).

## How timing is pinned without measuring it

ClearSignal measures no response time (CS-GAP-005; improvement request **F-018**), so slowness shows only through `--request-timeout`. Each timing case is chosen so that a pass and a failure are separated by a safe margin:

- degrading: delays 100, 400, 700, 1000, 1300 ms against an 850 ms timeout: P P P F F (150 ms margins);
- seeded jitter: delays 160, 906, 477, 477, 507, 264 ms against 700 ms: P F P P P P, and identical after another reset (at least 190 ms margins). The jitter default maximum was raised from 400 to 1000 ms for exactly this reason: with 400 the margins were 30 to 50 ms.
- fixed latency: 200 ms passes; 3000 ms fails with a 1 s timeout and passes with a 6 s one.

**These expectations must be run against the Docker container.** On my Windows host, with the server as a hidden background process, delays overshoot intermittently: there the degrading and jitter sequences came out wrong (call 2 of degrading, 400 ms against 850 ms, failed), while in the container they were exact. Everything else (counters, large bodies, transport cuts, the scenario) passed on both.

## Transport behaviors and `local_only`

The connection reset needs the socket, which ASGI never exposes. `app/transport.py` holds the live `uvicorn.Server` (set by `python -m app`); each connection knows its client address, so the handler finds its own connection and aborts it. Only that connection is touched, and with no real server (the in-process test client) it falls back to an empty 204. A test proves an unrelated open connection survives a reset, and that the server survives repeated resets and truncations.

Transport-level cases (`hang`, `slow-headers`, `slow-body`, `truncated-body`, `connection-reset`, `after-write`) and bodies over 32 MB are marked `local_only: true` in the expectations: nothing is claimed for Cloud Run until it is verified there (Phase 6, as the project rules require). `check_expectations.py --cloud` skips them.

## The scenario: three bugs only a scenario sees

`clrsig/scenarios/conform-fail-write-bugs.yaml` asserts the CORRECT behavior, so a step fails exactly where the server is wrong: after one `Idempotency-Key` used twice the record count is 2 (expected 1); a stale `If-Match` writer gets 200 (expected 412) and overwrites the first writer; a write that timed out still exists. The expectations record `passed: false` on precisely those steps.

## Runner additions

- `args` on a case (extra ClearSignal arguments such as a short timeout) and `local_only` plus `--cloud`.
- `sequences`: reset the family, call an operation N times, compare the outcome of every call; `repeat` runs the sequence again after another reset and demands the same result.
- `whole_spec`: reset first, a request timeout, and an explicit list of the paths that may fail (17 of 47).
- Scenario steps can expect `passed` and an `error` regex; a case can expect `operations: 2` for a path with two methods.
- `--paths` is a **prefix** filter, so `/unavailable` also runs `/unavailable-then-ok`. The runner now picks the operation by its exact path and judges the outcome from it, not from the whole command's exit code. The extra calls are harmless because every stateful case resets first. (Operations were not renamed to avoid this: that would bend the fixtures around the tool.)

## A fix made on the way

The spec declares `400` for invalid `mb`, `min`, `max` and `ms`, but FastAPI answered `422` with its own body. The validation handler that already mapped errors to 400 for `/ok` now covers `/conform-fail` too (`VALIDATED_400` in `app/ok/common.py`).

## ClearSignal findings raised

- **F-018** (improvement request): no way to assert or limit response time; `durationMs` is already in the JSON report, nothing can fail on it. Proposed: a `duration` assertion, a `--max-response-time` flag with a distinct finding, durations in baselines.
- **F-019** (bug): the 50 MB read limit silently truncates; valid JSON of 51 MB fails as "unexpected EOF" and the message never mentions the cap.

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 614 passed (67 new): 60 in-process tests with the sleep patched so the exact delays, sequences and resets are asserted, and 7 over a real socket (a truncated body is cut on the wire, a reset gives no answer and touches only its own connection, the server survives repeated cuts, a slow body sends its headers first, a hang outlasts a short client timeout).
- `scripts/check_expectations.py --expectations expectations/conform-fail.yaml` against the Docker container, **twice in a row**, about 2 minutes each: all as expected (27 response cases, the whole spec with 17 of 47 operations failing, 2 scenarios with 13 steps, the five sequences, 18 commands, request generation, 36 probes). `--cloud` skips the 11 local-only entries and passes. Contract-fail is unchanged. The container stops with exit code 0 even with slow requests in flight.
- Drift check: five deliberate mistakes (a case that no longer outlasts its timeout, the whole-spec failing set, a scenario step, a flaky sequence and a degrading sequence) produced five mismatches and exit 1.
- On the Windows host the two timing sequences did not match (the overshoot described above); every other part matched there too.

## Watch-outs

- A full expectations run takes about two minutes (the default-timeout case alone waits 10 s, and five cases wait out 3 s timeouts). The server keeps sleeping after a client gives up, using slow-request slots (20 at once), which free themselves within 30 s.
- `large-*` cases move up to 51 MB over loopback; keep them out of any slow or metered link.
- Remaining for Phase 4: drift (`DRIFT`/`--drift`), the spec-diff fixture pairs, coverage signals, impact cases and business-rule failures.
