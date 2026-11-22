# api-workbench-sandbox

ClearSignal test targets: three REST API families served by one FastAPI process on one port, used to test API Contract Validation and Spec Conformance. A test fixture, not a production API. See `docs/PRD.md` and `docs/TASKLIST.md`.

## Run locally

```
uv sync
uv run python -m app          # http://127.0.0.1:8080
uv run pytest
```

Environment variables: `PORT` (8080), `HOST` (127.0.0.1), `PUBLIC_BASE_URL`, `DRIFT` (0), `ADMIN_TOKEN`, `LATENCY_SCALE`.

## APIs

| Family | Base path | Spec | Health | Reset |
|---|---|---|---|---|
| ok | `/ok` (products, orders, projects/tasks, customers, payments, settings, version, secured examples) | `/ok/openapi.yaml` | `GET /ok/health` | `POST /ok/__admin/reset` |
| contract-fail | `/contract-fail` | `/contract-fail/openapi.yaml` | `GET /contract-fail/health` | `POST /contract-fail/__admin/reset` |
| conform-fail | `/conform-fail` | `/conform-fail/openapi.yaml` | `GET /conform-fail/health` | `POST /conform-fail/__admin/reset` |

The `ok` family also serves a small OpenAPI 3.1 variant at `GET /ok/openapi-3.1.yaml` (`specs/ok-3.1.yaml`: health, products and customers in the 3.1 dialect: type arrays with `"null"`, `const`, `examples` lists). It describes the same behavior, so it must conform too (`expectations/ok-31.yaml`).

Reset returns `204` and is not declared in the public specs. When `ADMIN_TOKEN` is set, reset and `GET <prefix>/__admin/state` need `Authorization: Bearer <ADMIN_TOKEN>`. State is in memory, shared by all callers, and lost on restart.

## Run ClearSignal

Start the server, then (the scenario resets the `ok` store itself; reset before a conform run):

```
curl -X POST http://localhost:8080/ok/__admin/reset
clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml --negative
clrsig run clrsig/scenarios/ok-crud.yaml --env clrsig/environments/ok.yaml --spec http://localhost:8080/ok/openapi.yaml
clrsig run clrsig/scenarios/ok-schemas-and-security.yaml --env clrsig/environments/ok.yaml --spec http://localhost:8080/ok/openapi.yaml
clrsig run clrsig/scenarios/ok-business-rules.yaml --env clrsig/environments/ok.yaml --spec http://localhost:8080/ok/openapi.yaml
clrsig run clrsig/scenarios/ok-latency.yaml --env clrsig/environments/ok.yaml --spec http://localhost:8080/ok/openapi.yaml
clrsig run clrsig/scenarios/ok-parameters-and-paging.yaml --env clrsig/environments/ok.yaml --spec http://localhost:8080/ok/openapi.yaml
```

Expected with `clrsig` v0.8.3: all scenarios pass, `conform` reports 65 of 65 operations and `conform --negative` runs 62 probes that all pass. Latency timeout check: `clrsig run clrsig/scenarios/ok-latency.yaml ... --timeout 100` exits 1 (the two slow steps fail with "context deadline exceeded"); that is the intended result, it shows ClearSignal's timeout handling.

Verified with released `clrsig` v0.8.3 (earlier versions have known issues; see `docs/clrsig-findings.md`). With a spec that has `servers`, `-b` is the family's base (`http://localhost:8080/ok`) and `--paths` takes the spec's own paths.

## Run all the checks

```
uv run pytest                                   # unit and integration tests, no ClearSignal needed
uv run python -m app                            # the server, then in another terminal:
uv run python scripts/check_expectations.py --expectations expectations/ok.yaml
uv run python scripts/check_expectations.py --expectations expectations/ok-31.yaml
uv run python scripts/check_expectations.py --expectations expectations/contract-fail.yaml
uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml   # about 2 minutes
uv run python scripts/check_expectations.py --expectations expectations/diff.yaml           # no server
```

Each prints one line per case and ends with `ALL AS EXPECTED` (exit 0) or `<n> MISMATCH(ES)` (exit 1): a case that unexpectedly passes, fails with another check, or changes exit code is a mismatch. `--section`, `--only` and `--cloud` narrow a run. The plain commands in "Run ClearSignal" below do not verify response behavior (F-010); these runners do.

CI (`.github/workflows/ci.yml`): pytest, then the Docker image is built and started, `/health` of each family is polled, and the five expectation files run against the container (timing needs it). Pushes and pull requests use the released `clrsig` pinned in `CLRSIG_VERSION`; a nightly run builds `clrsig` from `api-workbench@main` to catch ClearSignal regressions. When a `clrsig` release changes behavior, the expectations that encode a known bug (today F-016 and F-022) must flip with it; update them in the same change that bumps `CLRSIG_VERSION`.

## `contract-fail` cases

35 operations under `GET /contract-fail/cases/<check-id>-<slug>`, each declaring the correct behavior in `specs/contract-fail.yaml` while the server breaks exactly one thing. The expected ClearSignal outcome of every case is in `expectations/contract-fail.yaml` (table: `docs/contract-fail-cases.md`).

```
uv run python scripts/check_expectations.py          # server running on :8080; exit 0 = all as expected
uv run python scripts/check_expectations.py --only resp-003-missing-required-header
```

A plain run works too: `clrsig conform specs/contract-fail.yaml -b http://localhost:8080/contract-fail` reports 25 of 36 operations failing. (`clrsig` v0.7.1 silently skipped response validation for specs with `servers`, F-010, and needed a generated copy of the spec; that is fixed in v0.8.2.)

## `conform-fail` cases

56 operations (`specs/conform-fail.yaml`) where the *behavior* is wrong rather than a response. The expected ClearSignal outcome of everything is in `expectations/conform-fail.yaml` (tables: `docs/conform-fail-cases.md`).

| Group | What it shows |
|---|---|
| `/lenient/*` and `/strict/*` | a server that accepts bad requests (negative probes, CS-PROBE-001 to 004) and its correct twins |
| `/ghost`, `/orphan`, `/wrong-method`, `/path-param/{id}`, `/requires-extra-header`, `/form`, `/multipart`, `/subscribe` | the spec and the server disagree about what exists |
| `/requests/*` with the wrong environments in `clrsig/environments/` | requests that do not fit (CS-REQ-001/002) and runs that cannot happen (CS-RUN-001 to 005); unreadable specs in `clrsig/fixtures/` |
| `/slow`, `/flaky`, `/rate-limited`, `/latency/*`, `/unavailable*`, `/redirect-loop`, `/large*`, `/timeout/*`, `/idempotent`, `/lost-update` | timing and instability; counters live in the family store and reset restores them |
| `/drift/report` with `--drift=1` | the baseline ratchet (CS-RUN-006) |
| `/rules/*` | seven business rules broken on purpose, visible only to scenarios |

Without a server: 13 spec-diff pairs in `specs/diff/` and the impact scenarios in `clrsig/scenarios/impact/` (`expectations/diff.yaml`, `docs/diff-cases.md`). Coverage signals: `clrsig/scenarios/coverage-gaps.yaml` with `specs/coverage/coverage.yaml`.

```
uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml   # about 2 minutes
uv run python scripts/check_expectations.py --expectations expectations/diff.yaml           # no server
uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml --section coverage,drift   # parts only
```

Read before trusting a result:
- **Timing expectations must run against the Docker container.** On a Windows host the server's delays overshoot intermittently, so the same expectations can fail there. Slowness is pinned with `--max-response-time` (a slow response is still compared with the spec, CS-RESP-014); a request timeout is used where the response never arrives (CS-RUN-003).
- Entries marked `local_only` (transport behavior, bodies over 32 MB) are not claimed for Cloud Run; `--cloud` skips them.
- Every wrong environment is marked DELIBERATELY WRONG. Run the drift cases with real servers: the runner starts them itself.

## Latency

`GET /ok/ok-slow/{ms}` (0 to 10000) answers correctly after the delay, and every list operation accepts an optional `?delay=<ms>` (0 to 10000). `LATENCY_SCALE` (0 to 10, default 1) multiplies every deliberate delay; use `0` for fast test runs. Caps: the scaled sleep is at most 30 s and at most 20 slow requests run at once (more get `503`). Delays never block other requests or the store.

Note for Windows hosts: when the server runs as a hidden background process, delays overshoot intermittently (a 2000 ms delay sometimes took 3.7 s). The same requests in the Docker container were exact (12 of 12 within 6 ms), so use the container or CI for timing-sensitive checks.

## Business rules in the `ok` API

Orders: `pending -> paid -> shipped -> delivered`, and `pending/paid -> cancelled` through `POST /orders/{id}/pay|ship|deliver|cancel`; paying takes stock, cancelling a paid order returns it; only pending orders can be edited (`PUT`/`PATCH` need `If-Match`, `428` if missing, `412` if stale). Totals are quantity x price + 10% tax. `POST /orders/{id}/invoice` issues sequential `INV-nnnnnn` numbers. Customer emails are unique (`409`) and customers are soft-deleted. A project with open tasks cannot be deleted unless `?cascade=true`. `POST /payments` honors `Idempotency-Key`. Discount code `OLD5` is expired (`410`). Reports are asynchronous (`202` twice, then `200`). `GET /ok/rate-limited` allows 5 calls per 60 s per client (`X-Client-Id`). Reset restores all of it.

## Test credentials (fake fixtures, not secrets)

Only the secured example operations of the `ok` API use them (`/me`, `/stats`, `/audit-events`, `/feature-flags`, `/partner-status`). Everything else is public.

| Scheme | Operation | Credential |
|---|---|---|
| HTTP bearer | `GET /ok/me` | `Authorization: Bearer test-token` (scope `read`) |
| HTTP bearer, admin scope | `GET /ok/stats` | `Authorization: Bearer admin-token` (scopes `read`, `admin`); `test-token` gets `403` |
| HTTP basic | `GET /ok/audit-events` | `test-user` / `test-pass` |
| API key (header) | `GET /ok/partner-status` | `X-API-Key: test-api-key` |
| API key (query) | `GET /ok/feature-flags` | `?api_key=test-api-key` |

The admin token (`ADMIN_TOKEN`) is separate and only protects `__admin` routes.

## Docker

```
docker build -t api-workbench-sandbox .
docker run --rm -p 8080:8080 api-workbench-sandbox
```

Set `ADMIN_TOKEN` when running anywhere other than your own machine.

## Architecture

One Python 3.13 / FastAPI process, served by Uvicorn on one port. Each family is a router under its own prefix with its own in-memory `Store` (`app/store.py`: one `asyncio.Lock` per store, atomic multi-step rules through `Store.tx()`, seed factories that reset restores). The OpenAPI specs in `specs/` are hand-written and are the source of truth: they are served as checked in, except that `servers[0].url` becomes `PUBLIC_BASE_URL` (or the request's own base URL). FastAPI's generated `/openapi.json` is not used. Layout: `app/ok/` (the conforming API), `app/contract_fail/` and `app/conform_fail/` (the deliberate deviations), `app/latency.py` (every deliberate delay), `app/limits.py` (request-body cap), `clrsig/` (environments and scenarios), `expectations/` and `scripts/` (what ClearSignal must report and the runner that checks it).

## Admin token

`ADMIN_TOKEN` is optional locally and mandatory anywhere shared. When set, `POST <prefix>/__admin/reset` and `GET <prefix>/__admin/state` answer `401` without `Authorization: Bearer <ADMIN_TOKEN>`; it is never logged. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`, pass it as an environment variable (a Secret Manager secret on Cloud Run), and export it for the expectations runner, which resets families with it.

## Limits and safety

| Limit | Value | Where |
|---|---|---|
| request body | 1 MiB, then `413` (also for chunked bodies) | `app/limits.py` |
| deliberate delay requested | 10 000 ms, then `400` | `app/latency.py` |
| scaled sleep | 30 s, after `LATENCY_SCALE` (0 to 10) | `app/latency.py` |
| simultaneous slow requests | 20, then `503` | `app/latency.py` |
| `/conform-fail/large` response | 60 MB, then `400`; streamed, so memory stays flat (a 60 MB answer used about 43 MiB) | `app/conform_fail/timing.py` |
| records per collection | bounded (200 in the business-rule cases), then `422` | handlers |

No handler makes an outbound request from caller input: there is no HTTP client in the application, and the only redirect (`/conform-fail/redirect-loop`) points at itself. Verified by reading the code and in `tests/test_limits.py`; the caps were also exercised against the Docker container.

## Troubleshooting

- **A response check passes in a plain `clrsig conform` run with an older `clrsig`:** v0.7.1 and earlier skip response validation for specs with `servers` (F-010). Use v0.8.3 or later.
- **Timing cases fail on Windows:** the host overshoots delays; run against the Docker container.
- **Reset answers `401`:** `ADMIN_TOKEN` is set; send the bearer token, and export `ADMIN_TOKEN` for the runner.
- **State looks wrong:** it is shared by every caller and lost on restart; reset the family first.
- **A run reports a case mismatch after a `clrsig` upgrade:** an expectation that encodes a known bug flipped; see `docs/clrsig-findings.md` and update the expectation in the same change that bumps `CLRSIG_VERSION`.
- **Port in use:** set `PORT`.

## Known gaps and Cloud Run

Known gaps: no open ClearSignal finding (`docs/clrsig-findings.md`), the `local_only` transport and large-body cases (not verified on Cloud Run), unconfirmed fake credentials, and the report polling delay (poll-count progression, not wall-clock). Cloud Run is not deployed yet; preparation, verified settings and an unverified runbook are in `docs/cloud-run-prep.md`. On Cloud Run, scale-to-zero, a restart or an instance replacement erases all state, and simultaneous users share the same stores and can interfere with one another.

## KT notes

Per-phase walkthroughs live in `docs/kts/` (index: `docs/kts/README.md`).
