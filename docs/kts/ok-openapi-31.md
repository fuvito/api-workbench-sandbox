# KT — the OpenAPI 3.1 variant of `ok`

Decided 2026-11-22: `ok` ships both dialects. `specs/ok.yaml` stays 3.0.3; `specs/ok-3.1.yaml` is a small variant. This is an extra *document* of the `ok` family, not a fourth family and not new behavior.

## What it is

- 15 operations: `/health`, `/products` and `/products/{productId}`, `/customers` and `/customers/{customerId}`, with their parameters, headers, responses and schemas (closure of `$ref`s).
- Derived once from `ok.yaml` and then hand-maintained like every other spec. The 3.1 constructs: `openapi: 3.1.0`, `type: [string, "null"]` instead of `nullable: true`, `const: ok` instead of `enum: [ok]`, `examples: [...]` instead of a schema's `example`, `info.summary`, `license.identifier`.
- Served at `GET /ok/openapi-3.1.yaml` with the same `servers` rewrite as the main document; the other families have no variant (404). `build_family_router(..., extra_specs=...)` is the only code change.
- Tests (`tests/test_ok_31.py`): served and rewritten, nothing else differs from the file, every operation exists in the main spec with the same `operationId`, the document uses the 3.1 dialect and none of the 3.0 one, and the server really accepts the nullable field.

## What ClearSignal v0.7.1 does with it (F-021)

| | |
|---|---|
| Parsing, type arrays with `null`, `const`, `license.identifier` | fine |
| Probes | 16 of 16 pass |
| Operations | 11 of 15 pass |
| `POST /customers`, `POST /products`, `PUT /products/{id}` | "not sent: no value for {{name}}, ..." — the generated body holds placeholders |
| `PATCH /products/{id}` | sent an empty body, fails its own `minProperties: 1` |

Cause, isolated by hand: ClearSignal reads a schema's `example` but not 3.1's `examples` list. Changing only that in a scratch copy gives 15 of 15 operations and 16 of 16 probes. The spec is **not** changed to dodge it (CLAUDE.md); `expectations/ok-31.yaml` pins the four failing operations (by path: `/customers`, `/products`, `/products/{productId}`), and the finding says to empty the list when fixed.

## Decisions closed with this change (2026-11-22)

OpenAPI versions: both. Fake credentials confirmed as is. Report polling stays poll-count only. Expectation location and sync with the catalog: `expectations/<family>.yaml` plus the nightly leg.
