# KT — Phase 2f: cursor paging, bulk operations, parameters and 403

Last breadth step of Phase 2. `ok.yaml` goes from 56 to **65 operations**, inside the decided 60 to 70 target (the source proposal of 80 to 120 was dropped because every feature area is already covered).

## What was added

| Area | Operations | Notes |
|---|---|---|
| Cursor pagination | `GET /notifications`, `GET /notifications/{id}`, `POST /notifications/{id}/read` | 12 seeded notifications; filters `unread`, `kind`, `since` (RFC 3339 date-time); `limit` 1 to 50 (default 5); optional `delay` |
| Bulk | `POST /products/bulk`, `POST /products/bulk-delete` | create is all or nothing (up to 20); delete answers `200` or `207`, declared once as the `2XX` range |
| Parameter types | `GET /request-info`, `GET /preferences`, `GET /lookup` | header, required cookie, array (explode false and true), date, date-time, number, enum |
| 403 | `GET /stats` | bearer token needs the `admin` scope: `test-token` is `403`, `admin-token` is `200`, none is `401` |
| Optional response header | `Cache-Control` on `GET /version` and `GET /settings` | declared `required: false` |

## How the cursor works

- The cursor is opaque to clients: base64url of `{"after": <last id number>}`. A bad cursor (not base64, not JSON, no `after`, negative, boolean) is `400`.
- Filters run first, then "id greater than `after`", then the page is cut at `limit`. `nextCursor` is `null` on the last page, and an exact multiple of the limit does not produce an empty extra page.
- Because it follows ids and not positions, it is stable while data changes. A test marks a notification read between two pages of the unread list: nothing repeats and nothing else is skipped (offset paging would shift).

## Notes on specific behaviors

- **Bulk create** relies on request validation running before the handler, so one bad item rejects the whole body (`400`) and no ids are consumed. The creation itself is one `store.tx()` block.
- **Bulk delete** reports `deleted` and `notFound`; `207` means at least one id was missing, and the others are still deleted.
- **Scopes:** `BEARER_TOKENS` maps token to scopes. `bearer_scopes()` compares the presented token with every known token (no early exit), then `require_admin_scope` turns "valid but lacking `admin`" into `403` and "unknown or missing" into `401`.
- **`X-Request-Id`:** echoed when it is a UUID, generated otherwise; the response header is always set. A malformed value is `400`.
- **`lookup`:** `ids=1,2,3` is parsed by hand (FastAPI only reads repeated parameters), strictly: no blanks, no spaces, integers only, 1 to 20 values. `tags` uses repeated parameters. The handler echoes what it parsed so clients can check every type.
- **Cookie:** `theme` is read with `Cookie()`; missing or not `light`/`dark` is `400`. Cookie names are case-sensitive.

## Code map

```
app/ok/notifications.py   cursor encode/decode, list, get, mark read
app/ok/params.py          request-info, preferences, lookup
app/ok/products.py        + bulk create / bulk delete (before /products/{id})
app/ok/security.py        BEARER_TOKENS, bearer_scopes, require_admin_scope, Forbidden, /stats
app/ok/common.py          + parse_date_time (RFC 3339 with offset only)
clrsig/scenarios/ok-parameters-and-paging.yaml   24 steps, 45 assertions
tests/test_ok_paging_bulk_params.py              97 tests
```

## Verified results (2026-11-21, `clrsig` v0.7.1, Docker image)

- `uv run pytest`: 344 passed.
- `conform`: **63 of 65** operations pass. The two failures are `clrsig` bugs, not server bugs (below). `--negative`: 44/44 probes.
- Five scenarios, each run twice: `ok-crud` 21 steps, `ok-schemas-and-security` 21, `ok-business-rules` 43, `ok-latency` 6, `ok-parameters-and-paging` 24. All pass.
- Container stop exits 0.

## ClearSignal findings raised (not worked around)

- **F-008:** a required cookie parameter is never sent, so `GET /preferences` fails in `conform` ("value is required but missing"). `clrsig` request building ignores `in: cookie`.
- **F-009:** an `explode: false` array query parameter is written as `[1 2 3]`, so `GET /lookup` fails its own check. Expected `ids=1,2,3`.
- Both are demonstrated by `clrsig generate`; the server answers correctly to the right input (`ids=1,2,3`, `Cookie: theme=dark`). The scenario sends those explicitly, and it also checks that the malformed `[1 2 3]` form is rejected with `400`.

## Watch-outs

- **`conform` is not clean on `ok` until F-008 and F-009 are fixed.** The Phase 5 expectations file must record "63 of 65, failures on `/lookup` and `/preferences`" for `clrsig` v0.7.1 and flip to clean when the findings close. Do not edit the spec to make them pass.
- `since` accepts only RFC 3339 with an offset (`...Z` or `+02:00`); a date alone is `400`.
- A `+` in a query string must be sent as `%2B` (the scenario does); an unescaped `+` becomes a space.
- `GET /products/bulk` is just an unknown product id (`404`); only `POST` is the bulk route.
- Phase 2 is now feature-complete against the decisions made. What is left is the phase exit review: confirm credentials, decide the report polling delay, and open the F-items with the `clrsig` side.
