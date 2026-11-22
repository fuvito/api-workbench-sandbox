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

Expected with `clrsig` v0.7.1: all scenarios and `conform --negative`'s probes pass. `conform` itself reports 63 of 65 operations: `GET /lookup` and `GET /preferences` fail because `clrsig` cannot build an explode-false array or a required cookie (F-009, F-008 in `docs/clrsig-findings.md`); the server is correct and the scenarios cover both. Latency timeout check: `clrsig run clrsig/scenarios/ok-latency.yaml ... --timeout 100` exits 1 (the two slow steps fail with "context deadline exceeded"); that is the intended result, it shows ClearSignal's timeout handling.

Verified with released `clrsig` v0.7.1 (earlier versions have known issues; see `docs/clrsig-findings.md`).

## `contract-fail` cases

35 operations under `GET /contract-fail/cases/<check-id>-<slug>`, each declaring the correct behavior in `specs/contract-fail.yaml` while the server breaks exactly one thing. The expected ClearSignal outcome of every case is in `expectations/contract-fail.yaml` (table: `docs/contract-fail-cases.md`).

```
uv run python scripts/check_expectations.py          # server running on :8080; exit 0 = all as expected
uv run python scripts/check_expectations.py --only resp-003-missing-required-header
```

**Important (F-010 in `docs/clrsig-findings.md`):** `clrsig` v0.7.1 silently skips response validation for any spec that has a `servers` entry, so `clrsig conform specs/contract-fail.yaml` reports everything as PASS. The runner therefore checks a generated copy (`scripts/clrsig_spec_copy.py`: no `servers`, base path in each path, run with `-b`). Do not read a plain `clrsig conform` PASS on these specs as proof of anything.

## `conform-fail` cases (in progress; slices 1 and 2)

Slice 1 is in: seven `/conform-fail/lenient/*` operations that accept bad requests and seven `/conform-fail/strict/*` twins that reject them, so `clrsig conform --negative` finds exactly four failed probes (CS-PROBE-001 to 004) and passes everything else. The expected outcome of every case is in `expectations/conform-fail.yaml`.

```
uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml
```

Slice 2 adds operations where the spec and the server disagree: a declared route the server does not serve, a declared method it does not implement, a path parameter typed differently, a header only the server knows, form and multipart bodies, and a callback. The case table is `docs/conform-fail-cases.md`.

Same caveat as `contract-fail` (F-010), plus two about probes: `clrsig` ignores `--paths` for probes (F-013) and leaves them out of the JSON and JUnit reports (F-014), so the runner reads the text report.

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

## KT notes

Per-phase walkthroughs live in `docs/kts/` (index: `docs/kts/README.md`).
