# KT — Phase 2b: methods, query parameters and headers

Step 1 of the Phase 2 breadth work. `ok.yaml` grows from 21 to 29 operations.

## What was added

| Area | Detail |
|---|---|
| Pagination | `limit` (1-100, default 20) and `offset` (>= 0) on every list; body `{items, total}` |
| `X-Total-Count` | Required response header on every list `200` and on `HEAD /products`; equals body `total` (count after filters, before paging) |
| Product filters | `q` (name substring, case-insensitive), `minPrice`, `maxPrice`, `inStock`, `sort` (`name`, `-name`, `price`, `-price`) |
| Order filters | `status` (enum), `productId` |
| Task filter | `done` |
| PATCH | products, orders, projects, tasks: every field optional, none may be null, at least one required (`minProperties: 1`) |
| HEAD | `/products` (headers only) and `/products/{productId}` (bare 200/404, no body) |
| OPTIONS | `/products` and `/products/{productId}`: `204` with a required `Allow` header |

## Code map

- `app/ok/common.py`: `Page` (limit/offset dependency), `paged()` (slice + header + total), `as_bool()`, `PatchModel`.
- `app/ok/products.py`, `orders.py`, `projects.py`: list handlers take query parameters; PATCH handlers use `model.changes()` (only the fields the client sent).
- `specs/ok.yaml`: shared `Limit`/`Offset` parameters, `TotalCount`/`Allow` headers, `OrderStatus` enum, `*Patch` schemas.

## Behaviors worth knowing

- **Strict query values:** `inStock`/`done` accept only `true` or `false` (FastAPI would also accept `yes`, `1`); `minPrice=nan` is rejected; unknown `sort` values are 400. Invalid query input uses the same 400 `Error` shape as bad bodies.
- **PATCH null handling:** the models declare `name: str = Field(default=None)`. The default only applies when the field is absent, so an explicit `null` still fails type validation. Documented in the model.
- **PATCH on orders** checks `productId` (422 if unknown) and cannot change `status`; status moves arrive with the business rules.
- **HEAD 404** is a bare response (no JSON body) because HEAD carries no body.
- **Unknown query parameters** are ignored, as most servers do.

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 72 passed (`tests/test_ok_lists_and_methods.py` is new).
- `conform` 29/29 operations; `--negative` 28/28 probes; `ok-crud` scenario 20/20 steps, 29/29 assertions.

## Watch-outs

- `conform` runs DELETE before HEAD in path order, so HEAD only sees the 404 branch there; the 200 branch is covered by pytest only. Negative probes do not cover PATCH (it has no required fields), so PATCH rejection is covered by pytest only.
- The scenario does not yet use filters, PATCH, HEAD or OPTIONS. Add steps when the scenario set is expanded.
- Still missing for the breadth items: header and cookie parameters, cursor pagination, bulk operations, actions, `Location`/`ETag` headers.
