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

- [ ] **F-007 — Empty base URL in `conform` output (v0.7.1)**
  - Type: cosmetic. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `conform` prints `Base URL:` with nothing after it, and when no operation gets an answer it says "No operation got an answer from : is the server running?" (empty address). The spec was loaded from `http://localhost:8080/ok/openapi.yaml` and its `servers[0].url` is `http://localhost:8080/ok`, and requests do go there.
  - Repro: `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml` (header line), or run it against a stopped server.
  - Expected: print the base URL actually used (the `servers[0].url` or `--base-url`).
  - Closed: —

- [ ] **F-008 — Required cookie parameter is never sent (v0.7.1)**
  - Type: bug (false failure). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `GET /preferences` declares a required cookie parameter `theme` (with an `example`). `conform` builds the request without any `Cookie` header and then reports "the request cookie parameter "theme" does not fit the spec: value is required but missing", so a correct operation fails. From reading the source (`packages/core/openapi/parser.go`), request building handles `path`, `query` and `header` parameters only; `cookie` is ignored.
  - Repro: `clrsig generate specs/ok.yaml -o <dir>` and read `getPreferences.yaml` (no cookie); or `conform` and look at `GET /preferences`.
  - Expected: send `Cookie: theme=<example or environment value>`.
  - Covered here instead by: pytest and the `ok-parameters-and-paging` scenario, which sets the `Cookie` header explicitly.
  - Closed: —

- [ ] **F-009 — Array query parameter is serialized as `[1 2 3]` (v0.7.1)**
  - Type: bug (false failure). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `GET /lookup` declares a required query parameter `ids`: array of integers, `style: form`, `explode: false`, `example: [1, 2, 3]`. `clrsig generate` writes `value: '[1 2 3]'` (Go slice formatting) and `conform` then fails its own check: "the request query parameter "ids" does not fit the spec: path 0: value [1 2 3]: an invalid integer". The request is sent with the malformed value and the server correctly answers 400.
  - Repro: `clrsig generate specs/ok.yaml -o <dir>` and read `lookup.yaml`; or `conform` and look at `GET /lookup`.
  - Expected: serialize by style and explode: `ids=1,2,3` (or `ids=1&ids=2&ids=3` with `explode: true`).
  - Covered here instead by: pytest and the `ok-parameters-and-paging` scenario, which writes the query string explicitly.
  - Closed: —

- [ ] **F-010 — Response validation is silently skipped when the spec has `servers` (v0.7.1)**
  - Type: **bug, false pass, high severity**. Found: 2026-11-21, `clrsig` v0.7.1, while building `contract-fail`.
  - Behavior: with the spec written the standard way (`servers: [{url: http://localhost:8080/contract-fail}]`, paths like `/cases/x`), `conform` reports PASS for every operation, including all eight deliberately broken `contract-fail` cases (undeclared 500, missing required header, wrong types, ...). Scenario steps run with `--spec` show PASS too. No output format (text, json, junit, html) says that nothing was compared.
  - Cause (from reading `packages/core/openapi/validator.go` and `scenario/runner.go`): `conform` calls `ValidateResponseByPath` with a bare path (no host); the router it builds from the spec honors `servers` (host and base path), so no route matches and the function returns "path not in spec - skip", i.e. no violations. The scenario runner compares the step's full URL path literally with the spec's paths (`/contract-fail/cases/x` is never equal to `/cases/x`), so the step is "not checked: no matching operation in the spec" (the catalog's CS-NC-001), which is not shown anywhere.
  - Repro: start the server, then `clrsig conform http://localhost:8080/contract-fail/openapi.yaml --paths /contract-fail/cases/resp-001-undeclared-status` -> `PASS GET /cases/resp-001-undeclared-status 500`.
  - Expected: honor `servers[].url` when matching (strip the server's base path, ignore the host), and always show "not checked" when a step or operation could not be compared.
  - Only shape that works today: a copy of the spec with no `servers` block and the base path baked into every path, run with `-b <scheme://host>` for `conform`. With that copy all eight failures are detected and the controls pass.
  - Handling here: the checked-in and served specs stay standard. `scripts/clrsig_spec_copy.py` writes the working copy for verification runs. It is a temporary concession to this bug; delete it when this item closes.
  - Impact on earlier results: everything verified before Phase 3 had its request-side checks but NOT its response-side checks. Re-verified with the copy on 2026-11-21: `ok` `conform` 63/65 (only F-008 and F-009 fail), `--negative` 44/44, and all five `ok` scenarios pass, so the `ok` responses do conform to `ok.yaml`.
  - Closed: —

- [ ] **F-011 — Response findings are imprecise for some failures (v0.7.1)**
  - Type: limitation (messages and kinds, the failures are caught). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior, all seen in the JSON report of `conform` on `contract-fail`:
    - A body that matches no `oneOf` branch (`resp-009-oneof-no-match`) is reported with kind `missing-field`, location `a`, "property "a" is missing ... Or property "b" is missing". It says a field is missing, not that no branch matched (the catalog's CS-RESP-009). The discriminator case reports the missing field of the branch named by `type` (`meows`).
    - A root-level type mismatch (`resp-006b-array-for-object`: an array where an object is declared) has kind `other` and no location, where the same mismatch on a field has kind `wrong-type`.
    - A body that is not JSON (`resp-008-invalid-json`) or empty (`resp-008b-empty-body`) is reported with the parser's own text ("invalid character 'n' looking for beginning of object key string", "EOF"), kind `other`, no location.
    - The catalog says the `schema` assertion does not check an empty body ("partly"); in fact it fails the step with "response body is empty".
  - Repro: `clrsig conform <spec copy> -b http://localhost:8080 --paths /contract-fail/cases/resp-009-oneof-no-match --format json` (and the other cases above); see `scripts/check_expectations.py`.
  - Expected: a distinct finding kind for "no oneOf branch matched", "body is not valid JSON" and "body is empty", with a clear message; the same kind for a wrong type at the root and at a field; the catalog row for the empty body matching the behavior.
  - Pinned here instead by: `expectations/contract-fail.yaml` records today's kinds and messages, so a change shows up as a mismatch.
  - Closed: —

- [ ] **F-012 — No check ID in any report format (v0.7.1)**
  - Type: enhancement. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: the catalog gives every check an ID (CS-RESP-001 ...), but no output of `conform` or `run` (text, JSON, JUnit, HTML) contains it. Findings carry a coarse `kind` (`undeclared-status`, `missing-header`, `other`, ...), and several IDs share one kind (CS-RESP-007, 008, 010 and 011 are all `other`). A CI job cannot compare actual and expected check IDs, as the project plan asks, without parsing message text.
  - Repro: any failing `conform --format json`; search the output for `CS-`.
  - Expected: a `checkId` field on each finding (and the ID in the text report).
  - Handled here instead by: matching `kind`, `where` and a regex on the validator message, all recorded per case in `expectations/contract-fail.yaml`. Replace with the ID when it exists.
  - Closed: —

---

## Baseline

Fixtures are verified against released `clrsig` **v0.7.1** (installed with Scoop). Open: F-003 to F-012 (all found with v0.7.1). F-010 is the serious one: response checks are skipped for specs with `servers`.

## Notes

- `conform` needs environment values for path parameters (`clrsig/environments/ok.yaml`). That is expected behavior, not a finding.
- `conform` exercises DELETE operations, so the store must be reset before each run. Later operations then see declared 404s. Expected behavior.
