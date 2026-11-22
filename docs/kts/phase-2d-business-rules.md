# KT — Phase 2d: business rules

Step 3 of the Phase 2 breadth work. `ok.yaml` grows from 43 to 55 operations. All rules are small and live next to the resource they belong to.

## The key mechanism: `Store.tx()`

Rules that read several records and then write (stock, state moves, cascades, idempotency) must be atomic. `store.tx()` holds the store lock for the whole block and gives a lock-free `Tx` view (`get`, `list`, `put`, `delete`, `next_n`, `next_id`).

```python
async with store.tx() as tx:
    order = tx.get("orders", order_id)
    ...checks that raise ApiError...
    tx.put("orders", order_id, order)
```

- Raising inside the block releases the lock and nothing is written after the raise, so a failed rule never leaves a half-done change.
- Keep the block short; never await anything slow inside it.
- This replaced the check-then-write pattern noted as a watch-out in the Phase 2a KT. Tests run 5 simultaneous pays, 10 duplicate emails, 10 same-key payments, 8 same-ETag edits and 12 rate-limited calls to prove it.

## Rules and where they live

| Rule | Behavior | Code |
|---|---|---|
| Unique email | duplicate (case-insensitive) is `409` problem+json; a soft-deleted customer frees its email | `customers.py` |
| Stock | create/edit checks `quantity <= stock` (`422`); **pay** takes stock, **cancel** of a paid order gives it back; paying can fail `422` if stock ran out meanwhile | `orders.py` |
| Order states | `pending -> paid -> shipped -> delivered`, `pending/paid -> cancelled`; anything else `409` and the order is unchanged | `orders.py` (`ACTIONS`) |
| Editing | only pending orders (`409` otherwise); only pending or cancelled orders can be deleted | `orders.py` |
| Computed fields | `unitPrice` snapshot, `total = round(qty x price x 1.10, 2)` using `Decimal` (half up), `createdAt`/`updatedAt` | `orders.py` |
| Invoices | one per paid/shipped/delivered order, numbers `INV-000001...` from a store counter (reset with the store) | `invoices.py` |
| Ownership | delete project with open tasks `409`; `?cascade=true` removes it and all its tasks; only done tasks: plain delete works | `projects.py` |
| ETag / If-Match | ETag = short hash of the returned JSON; required on order PUT/PATCH (`428`), optional on task PUT/PATCH; stale `412`; `*` and lists accepted; weak tags never match | `common.py`, `orders.py`, `projects.py` |
| Idempotency | `Idempotency-Key` on `POST /payments`: replay `200`, different body `422`, up to 1000 keys | `payments.py` |
| Soft delete | `DELETE /customers/{id}` sets `deletedAt`; hidden unless `?includeDeleted=true`; second delete `404` | `customers.py` |
| Expiry | discount codes `OLD5` (expired), `SAVE10`, `WELCOME5`; redeeming an expired code is `410`; evaluated against `clock.utcnow()` | `discounts.py` |
| Async job | `POST /reports` `202` + `Location`; `GET` answers `202` for the first two polls, then `200`; counted atomically | `reports.py` |
| Rate limit | `GET /ok/rate-limited`: 5 calls per 60 s per `X-Client-Id` (or address); `429` with `Retry-After`; only this endpoint throttles | `ratelimit.py` |

Order of checks on an order edit: `404`, then `428`/`412`, then `409`, then `422`.

## Time is injectable

`app/clock.py` has `utcnow()` and `monotonic()`. Everything time-based (timestamps, expiry, rate-limit windows) goes through it, so tests replace it with `monkeypatch`. Nothing runs in the background: progress and expiry are computed when a request arrives, as Cloud Run requires.

## Behavior changes to existing endpoints

- `Order` now has `unitPrice`, `total`, `createdAt`, `updatedAt`; `PUT`/`PATCH` on orders need `If-Match`.
- Project delete no longer cascades silently.
- Customer delete is soft.
- Old tests and `ok-crud.yaml` were updated for these rules (for example, the order update step now respects the stock of 3).

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 212 passed.
- `conform`: 55/55 operations; `--negative`: 38/38 probes.
- Scenarios, each run twice: `ok-crud` 21 steps, `ok-schemas-and-security` 21 steps, `ok-business-rules` 43 steps (60 assertions). Breaking two expectations in a temporary copy made the run fail with the actual values, so the assertions are real.
- Same checks pass against the Docker image.

## ClearSignal findings raised

- **F-006** `--negative` has no probe for a missing required header (`If-Match` should give `428`). Covered here by pytest and the scenario.
- Still open from before: F-003, F-004, F-005 (see `docs/clrsig-findings.md`).

## Lesson from this step

A new rule can break scenarios written for an earlier slice. Making `If-Match` mandatory on order edits (slice 3b) broke `ok-crud` with `428`, and it was only noticed in the final Docker run because the scenario had not been re-run after 3b. Re-run **every** scenario (not just the new one) after any rule change. The Phase 5 expectations runner and CI exist to make this automatic.

## Watch-outs

- `conform` runs DELETE before actions in path order, so order action operations only see `404` there; the rules scenario and pytest cover the real paths.
- `GET /ok/rate-limited` is stateful per client: repeated `conform` runs inside 60 s without a reset get `429`, which is declared, so they still pass. Reset first for a clean run.
- Rate-limit windows use a monotonic clock, so they are not visible in wall-clock terms and restart with the process.
- Product SKU and tag-name uniqueness from the source notes are not modeled; email uniqueness stands for the rule.
- Still open for Phase 2: baseline latency (`ok-slow`, `LATENCY_SCALE`), cursor pagination, bulk operations, header/cookie parameters, and the operation-count target.
