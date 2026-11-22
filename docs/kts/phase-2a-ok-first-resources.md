# KT — Phase 2a: `ok` first three resources

Scope: the "First three resources" block of Phase 2. Breadth (more methods, schema features, business rules, latency) is the rest of Phase 2 and gets its own note.

## What exists

| Resource | Operations | Notes |
|---|---|---|
| products | list, create, get, replace (PUT), delete | fields `name`, `price`, `stock` |
| orders | list, create, get, replace (PUT), delete | `productId` must exist (422); `status` starts `pending`, PUT does not change it |
| projects | list, create, get, replace, delete | `description` optional; deleting a project also deletes its tasks (interim rule) |
| tasks (under a project) | list, create, get, replace, delete | `/projects/{projectId}/tasks[/{taskId}]`; a task is only reachable through its own project |

21 operations in `specs/ok.yaml` including `getHealth`.

## Code map

```
app/ok/__init__.py   build_ok_router(store): mounts the three routers under /ok
app/ok/common.py     StrictModel, ApiError, error handlers (400 mapping)
app/ok/products.py   products router + ProductInput
app/ok/orders.py     orders router + OrderInput
app/ok/projects.py   projects + tasks router
app/store.py         + create_auto(): sequential ids, counters reset with the store
app/seeds.py         ok seed: 3 products, 2 orders, 2 projects, 3 tasks
clrsig/environments/ok.yaml   baseUrl + path-parameter ids for conform
clrsig/scenarios/ok-crud.yaml CRUD scenario with variable extraction
tests/test_ok_api.py          HTTP tests of all of the above
```

## How strictness works

- Request models extend `StrictModel` (`strict=True`, `extra="forbid"`): `"1"` is not an integer, `true` is not a number, unknown fields are rejected. This is the `ok` rule "reject bad input" and matches `additionalProperties: false` in the spec.
- FastAPI answers invalid bodies with 422 and its own body shape. `validation_error_handler` converts that to **400** with the declared `Error` shape (`{code, message}`) for paths under `/ok/`; other paths keep the default.
- `ApiError(status, code, message)` is raised by handlers (404 not found, 422 business rule) and rendered by `api_error_handler` in the same shape.
- 422 is reserved for "well-formed but breaks a rule" (order for a product that does not exist). 400 is malformed or schema-invalid input.

## Ids and reset

`Store.create_auto(collection, prefix, record)` assigns `<prefix>-<n>` (`p-4`, `o-3`, `pr-3`, `t-4`). Counters start at the number of seed records, never go backwards (deleted ids are not reused), and are reset together with the data. Tests assert both behaviours.

## Spec decisions

- Path parameters are declared once per path item, which is valid OpenAPI. Released v0.5.0 did not handle that (F-002, fixed in v0.7.1); the spec was never bent around it.
- `example` values on input schemas document the fields; the spec is not written to suit any `clrsig` version.
- Shared `$ref` components: `Error`, `BadRequest/NotFound/Unprocessable` responses, `*List` envelopes (`{items, total}`).
- Still OpenAPI 3.0.3 (3.0 vs 3.1 decision open).

## Verified results (2026-11-21)

- `uv run pytest`: 30 passed.
- `clrsig conform ... --env clrsig/environments/ok.yaml --negative` with released `clrsig` v0.7.1: 21/21 operations, 28/28 negative probes, exit 0.
- `clrsig run clrsig/scenarios/ok-crud.yaml ... --spec <url>` twice in a row: 20/20 steps, 29/29 assertions each time (scenario resets first), on v0.7.1 (v0.5.0 also passed the scenario but failed 6 of 21 `conform` operations).

## Findings about ClearSignal

Tracked in `docs/clrsig-findings.md`: F-001 (typed body fields sent as strings) and F-002 (path-level parameters not substituted), both fixed in v0.7.1 and verified here, so closed. Nothing in this repo works around them.

## Watch-outs

- Each handler step (check then write) takes the store lock separately, so a concurrent delete between two steps can slip through. Single operations are atomic. Acceptable for a fixture; revisit if concurrency tests need it.
- Deleting a project currently cascades silently. The business-rules step changes this to `409` for open tasks and `?cascade=true` for `204`, which also changes the spec.
- No order status transitions, stock handling, uniqueness or ETags yet; those are listed under "Light business rules".
