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
```

Verified with released `clrsig` v0.7.1 (earlier versions have known issues; see `docs/clrsig-findings.md`).

## Business rules in the `ok` API

Orders: `pending -> paid -> shipped -> delivered`, and `pending/paid -> cancelled` through `POST /orders/{id}/pay|ship|deliver|cancel`; paying takes stock, cancelling a paid order returns it; only pending orders can be edited (`PUT`/`PATCH` need `If-Match`, `428` if missing, `412` if stale). Totals are quantity x price + 10% tax. `POST /orders/{id}/invoice` issues sequential `INV-nnnnnn` numbers. Customer emails are unique (`409`) and customers are soft-deleted. A project with open tasks cannot be deleted unless `?cascade=true`. `POST /payments` honors `Idempotency-Key`. Discount code `OLD5` is expired (`410`). Reports are asynchronous (`202` twice, then `200`). `GET /ok/rate-limited` allows 5 calls per 60 s per client (`X-Client-Id`). Reset restores all of it.

## Test credentials (fake fixtures, not secrets)

Only the secured example operations of the `ok` API use them (`/me`, `/audit-events`, `/feature-flags`, `/partner-status`). Everything else is public.

| Scheme | Operation | Credential |
|---|---|---|
| HTTP bearer | `GET /ok/me` | `Authorization: Bearer test-token` |
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
