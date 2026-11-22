# ClearSignal findings

Things found in `clrsig` while building these fixtures. **Rule: this repository does not work around ClearSignal.** Fixtures stay correct, and each problem is listed here for the api-workbench side to fix. When a fix ships, re-verify here and tick the item.

Legend: `- [ ]` open · `- [x]` closed (verified against the stated release)

How to close an item: install the fixed release, rerun the "Repro" command, confirm the "Expected" result, then fill in "Closed" and tick the box. Remove any matching caveat from `README.md`, `docs/TASKLIST.md` and the KT notes in the same change.

---

- [x] **F-001 — Typed request-body fields are sent as strings by `conform` (released v0.5.0)**
  - Found: 2026-11-21, `clrsig` v0.5.0 (Scoop). Fixed in v0.7.1.
  - Behavior: `conform` builds the body with every placeholder quoted (`"price": "{{price}}"`) and ignores schema `example`/`default`. Required `number`, `integer` and `boolean` properties are therefore sent as strings and reported as a request-body problem (CS-REQ-002 category), so `ok` fails although it conforms.
  - Repro: start the server, `POST /ok/__admin/reset`, then `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml`.
  - Expected: 21/21 operations pass.
  - Actual (v0.5.0): 15 passed, 6 failed (`POST`/`PUT` on products, orders, tasks).
  - Closed: 2026-11-21, verified with released `clrsig` v0.7.1: `conform` 21/21 operations and 28/28 negative probes pass; `ok-crud` scenario passes twice (20/20 steps, 29/29 assertions).

- [x] **F-002 — Path-level `parameters` are not substituted (released v0.5.0)**
  - Found: 2026-11-21, `clrsig` v0.5.0. Fixed in v0.7.1 (source commit `6f9d10b`, "path-level parameters in generated requests").
  - Behavior: a parameter declared once on the path item (`/products/{productId}: parameters: [...]`) is not seen, so the URL keeps a literal `{productId}`. `clrsig generate` writes `{productId}` instead of `{{productId}}`, and `conform` sends the literal text.
  - Repro: `clrsig generate specs/ok.yaml --dry-run` and look at `/products/{productId}`.
  - Expected: `.../products/{{productId}}`.
  - Closed: 2026-11-21, verified with released `clrsig` v0.7.1: `generate --dry-run` prints `.../products/{{productId}}`; `conform` resolves all path parameters.

- [ ] **F-003 — Schema-level `example` on a `oneOf` request body is ignored (v0.7.1)**
  - Type: limitation / enhancement. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: for `POST /payments` the request schema is `oneOf` (card | bank) with an `example` on the schema itself. The generated body ignores that example and uses only the first branch, taking each property's own `example`/`default`/`enum`. Properties without one (`amount`, `cardLast4`) become `{{placeholders}}`, so `conform` reports "not sent: no value for {{amount}}, {{cardLast4}}" until the environment supplies them.
  - Repro: `clrsig generate specs/ok.yaml -o <dir>` and read `createPayment.yaml`; or `conform` with an environment that lacks `amount` and `cardLast4`.
  - Expected: use the schema-level (or media-type-level) `example` as the body when present.
  - Workaround in this repo: none in the spec; `clrsig/environments/ok.yaml` supplies `amount` and `cardLast4`, which is the documented way to fill placeholders.
  - Closed: —

- [ ] **F-004 — `oneOf` request bodies: only the first branch is exercised, and no negative probes (v0.7.1)**
  - Type: limitation. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `conform` sends only the first `oneOf` branch (card), so the bank variant is never sent. `--negative` generates no missing-field or wrong-type probes for `POST /payments` (36 probes in total; none for payments), although each branch has required fields.
  - Repro: `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml --negative` and look for `/payments` probes.
  - Expected: exercise each branch (or say clearly that it is not covered), and probe required fields of the branches.
  - Covered here instead by: `clrsig/scenarios/ok-schemas-and-security.yaml` (both variants, discriminator and field errors).
  - Closed: —

- [ ] **F-005 — `conform` applies credentials for bearer only; basic and API-key schemes are not sent (v0.7.1)**
  - Type: bug (false pass). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `ok.yaml` declares `bearerAuth` (http bearer), `basicAuth` (http basic), `apiKeyHeader` (`X-API-Key`) and `apiKeyQuery` (`api_key`). With the environment variables `token`, `basicUser`, `basicPass` and `apiKey` set, only `GET /me` (bearer) is authenticated (200). `GET /audit-events`, `/partner-status` and `/feature-flags` are answered 401, and `conform` still reports PASS because 401 is a declared response, so the authenticated path of three secured operations is never exercised. From reading the source (`packages/core/openapi/parser.go`, main on 2026-11-21): auth is set only when a security requirement *name* contains "bearer" or "auth", always as a Bearer token; `apiKey` and `basic` are not translated for OpenAPI 3 (only the Swagger 2 importer handles `apiKey`). Because `basicAuth` contains "auth", a Bearer token is probably sent for the basic scheme; not confirmed at header level.
  - Repro: start the server, reset, run `conform` with `clrsig/environments/ok.yaml`, and compare the server log (`/ok/audit-events`, `/ok/feature-flags`, `/ok/partner-status` all 401, `/ok/me` 200).
  - Expected: read `components.securitySchemes`, apply the right scheme per operation from the environment (`basicUser`/`basicPass`, `apiKey`, `token`), so these operations return 200.
  - Covered here instead by: `clrsig/scenarios/ok-schemas-and-security.yaml`, which sets credentials explicitly per step.
  - Closed: —

- [ ] **F-006 — `--negative` does not probe a missing required header (v0.7.1)**
  - Type: limitation / enhancement. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `PUT` and `PATCH /orders/{orderId}` declare `If-Match` as a required header; the correct server answer to its absence is `428`. `--negative` generates probes that drop required body fields and send wrong types, plus "no credentials" probes, but none that omit a required header. Its help text promises "missing params".
  - Repro: `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml --negative` and list the probes for `PUT /orders/{orderId}` (only `missing required field` and `wrong type` probes appear).
  - Expected: one probe per required header (and per required query parameter), passing on any 4xx.
  - Covered here instead by: pytest (`tests/test_ok_preconditions.py`) and the `ok-business-rules` scenario ("Edit without If-Match is 428").
  - Closed: —

---

## Baseline

Fixtures are verified against released `clrsig` **v0.7.1** (installed with Scoop). Open: F-003, F-004, F-005, F-006 (all found with v0.7.1).

## Notes

- `conform` needs environment values for path parameters (`clrsig/environments/ok.yaml`). That is expected behavior, not a finding.
- `conform` exercises DELETE operations, so the store must be reset before each run. Later operations then see declared 404s. Expected behavior.
