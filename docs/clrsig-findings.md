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

- [x] **F-003 — Schema-level `example` on a `oneOf` request body is ignored (v0.7.1)**
  - Type: limitation / enhancement. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: for `POST /payments` the request schema is `oneOf` (card | bank) with an `example` on the schema itself. The generated body ignores that example and uses only the first branch, taking each property's own `example`/`default`/`enum`. Properties without one (`amount`, `cardLast4`) become `{{placeholders}}`, so `conform` reports "not sent: no value for {{amount}}, {{cardLast4}}" until the environment supplies them.
  - Repro: `clrsig generate specs/ok.yaml -o <dir>` and read `createPayment.yaml`; or `conform` with an environment that lacks `amount` and `cardLast4`.
  - Expected: use the schema-level (or media-type-level) `example` as the body when present.
  - Workaround in this repo: none in the spec; `clrsig/environments/ok.yaml` supplies `amount` and `cardLast4`, which is the documented way to fill placeholders.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: the generated `createPayment.yaml` body is the schema-level example (`amount: 19.99`, `cardLast4: "4242"`).

- [x] **F-004 — `oneOf` request bodies: only the first branch is exercised, and no negative probes (v0.7.1)**
  - Type: limitation. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `conform` sends only the first `oneOf` branch (card), so the bank variant is never sent. `--negative` generates no missing-field or wrong-type probes for `POST /payments` (36 probes in total; none for payments), although each branch has required fields.
  - Repro: `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml --negative` and look for `/payments` probes.
  - Expected: exercise each branch (or say clearly that it is not covered), and probe required fields of the branches.
  - Covered here instead by: `clrsig/scenarios/ok-schemas-and-security.yaml` (both variants, discriminator and field errors).
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `--negative` probes required fields and wrong types of each branch (16 probes for `POST /payments`). `conform` still sends one body; the second branch is covered by `ok-schemas-and-security.yaml`.

- [x] **F-005 — `conform` applies credentials for bearer only; basic and API-key schemes are not sent (v0.7.1)**
  - Type: bug (false pass). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `ok.yaml` declares `bearerAuth` (http bearer), `basicAuth` (http basic), `apiKeyHeader` (`X-API-Key`) and `apiKeyQuery` (`api_key`). With the environment variables `token`, `basicUser`, `basicPass` and `apiKey` set, only `GET /me` (bearer) is authenticated (200). `GET /audit-events`, `/partner-status` and `/feature-flags` are answered 401, and `conform` still reports PASS because 401 is a declared response, so the authenticated path of three secured operations is never exercised. From reading the source (`packages/core/openapi/parser.go`, main on 2026-11-21): auth is set only when a security requirement *name* contains "bearer" or "auth", always as a Bearer token; `apiKey` and `basic` are not translated for OpenAPI 3 (only the Swagger 2 importer handles `apiKey`). Because `basicAuth` contains "auth", a Bearer token is probably sent for the basic scheme; not confirmed at header level.
  - Repro: start the server, reset, run `conform` with `clrsig/environments/ok.yaml`, and compare the server log (`/ok/audit-events`, `/ok/feature-flags`, `/ok/partner-status` all 401, `/ok/me` 200).
  - Expected: read `components.securitySchemes`, apply the right scheme per operation from the environment (`basicUser`/`basicPass`, `apiKey`, `token`), so these operations return 200.
  - Covered here instead by: `clrsig/scenarios/ok-schemas-and-security.yaml`, which sets credentials explicitly per step.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `conform` authenticates every scheme: `/audit-events`, `/feature-flags`, `/partner-status` answer 200 (server log).

- [x] **F-006 — `--negative` does not probe a missing required header (v0.7.1)**
  - Type: limitation / enhancement. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `PUT` and `PATCH /orders/{orderId}` declare `If-Match` as a required header; the correct server answer to its absence is `428`. `--negative` generates probes that drop required body fields and send wrong types, plus "no credentials" probes, but none that omit a required header. Its help text promises "missing params".
  - Repro: `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml --negative` and list the probes for `PUT /orders/{orderId}` (only `missing required field` and `wrong type` probes appear).
  - Expected: one probe per required header (and per required query parameter), passing on any 4xx.
  - Covered here instead by: pytest (`tests/test_ok_preconditions.py`) and the `ok-business-rules` scenario ("Edit without If-Match is 428").
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `--negative` adds `missing required header 'If-Match'` probes (CS-PROBE-003) for `PUT` and `PATCH /orders/{orderId}`.

- [x] **F-007 — Empty base URL in `conform` output (v0.7.1)**
  - Type: cosmetic. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `conform` prints `Base URL:` with nothing after it, and when no operation gets an answer it says "No operation got an answer from : is the server running?" (empty address). The spec was loaded from `http://localhost:8080/ok/openapi.yaml` and its `servers[0].url` is `http://localhost:8080/ok`, and requests do go there.
  - Repro: `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml` (header line), or run it against a stopped server.
  - Expected: print the base URL actually used (the `servers[0].url` or `--base-url`).
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `conform` prints `Base URL: http://localhost:8080/ok`.

- [x] **F-008 — Required cookie parameter is never sent (v0.7.1)**
  - Type: bug (false failure). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `GET /preferences` declares a required cookie parameter `theme` (with an `example`). `conform` builds the request without any `Cookie` header and then reports "the request cookie parameter "theme" does not fit the spec: value is required but missing", so a correct operation fails. From reading the source (`packages/core/openapi/parser.go`), request building handles `path`, `query` and `header` parameters only; `cookie` is ignored.
  - Repro: `clrsig generate specs/ok.yaml -o <dir>` and read `getPreferences.yaml` (no cookie); or `conform` and look at `GET /preferences`.
  - Expected: send `Cookie: theme=<example or environment value>`.
  - Covered here instead by: pytest and the `ok-parameters-and-paging` scenario, which sets the `Cookie` header explicitly.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: the generated request carries `Cookie: theme=dark`; `GET /preferences` passes.

- [x] **F-009 — Array query parameter is serialized as `[1 2 3]` (v0.7.1)**
  - Type: bug (false failure). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: `GET /lookup` declares a required query parameter `ids`: array of integers, `style: form`, `explode: false`, `example: [1, 2, 3]`. `clrsig generate` writes `value: '[1 2 3]'` (Go slice formatting) and `conform` then fails its own check: "the request query parameter "ids" does not fit the spec: path 0: value [1 2 3]: an invalid integer". The request is sent with the malformed value and the server correctly answers 400.
  - Repro: `clrsig generate specs/ok.yaml -o <dir>` and read `lookup.yaml`; or `conform` and look at `GET /lookup`.
  - Expected: serialize by style and explode: `ids=1,2,3` (or `ids=1&ids=2&ids=3` with `explode: true`).
  - Covered here instead by: pytest and the `ok-parameters-and-paging` scenario, which writes the query string explicitly.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: the generated query is `ids=1,2,3`; `GET /lookup` passes. `ok`: 65 of 65 operations.

- [x] **F-010 — Response validation is silently skipped when the spec has `servers` (v0.7.1)**
  - Type: **bug, false pass, high severity**. Found: 2026-11-21, `clrsig` v0.7.1, while building `contract-fail`.
  - Behavior: with the spec written the standard way (`servers: [{url: http://localhost:8080/contract-fail}]`, paths like `/cases/x`), `conform` reports PASS for every operation, including all eight deliberately broken `contract-fail` cases (undeclared 500, missing required header, wrong types, ...). Scenario steps run with `--spec` show PASS too. No output format (text, json, junit, html) says that nothing was compared.
  - Cause (from reading `packages/core/openapi/validator.go` and `scenario/runner.go`): `conform` calls `ValidateResponseByPath` with a bare path (no host); the router it builds from the spec honors `servers` (host and base path), so no route matches and the function returns "path not in spec - skip", i.e. no violations. The scenario runner compares the step's full URL path literally with the spec's paths (`/contract-fail/cases/x` is never equal to `/cases/x`), so the step is "not checked: no matching operation in the spec" (the catalog's CS-NC-001), which is not shown anywhere.
  - Repro: start the server, then `clrsig conform http://localhost:8080/contract-fail/openapi.yaml --paths /contract-fail/cases/resp-001-undeclared-status` -> `PASS GET /cases/resp-001-undeclared-status 500`.
  - Expected: honor `servers[].url` when matching (strip the server's base path, ignore the host), and always show "not checked" when a step or operation could not be compared.
  - Only shape that works today: a copy of the spec with no `servers` block and the base path baked into every path, run with `-b <scheme://host>` for `conform`. With that copy all eight failures are detected and the controls pass.
  - Coverage is affected the same way: run with the standard spec (servers present), `clrsig coverage quality` reports 0% covered and "never exercised" for all four operations although the scenario ran every one of them (pinned by `coverage.standard_spec` in `expectations/conform-fail.yaml`).
  - Handling here: the checked-in and served specs stay standard. `scripts/clrsig_spec_copy.py` writes the working copy for verification runs. It is a temporary concession to this bug; delete it when this item closes.
  - Impact on earlier results: everything verified before Phase 3 had its request-side checks but NOT its response-side checks. Re-verified with the copy on 2026-11-21: `ok` `conform` 63/65 (only F-008 and F-009 fail), `--negative` 44/44, and all five `ok` scenarios pass, so the `ok` responses do conform to `ok.yaml`.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: a plain `conform` on the standard `contract-fail` spec reports the same 25 of 36 failing operations as the old working copy; scenarios with `--spec` and `coverage quality` match operations of specs with `servers`. `scripts/clrsig_spec_copy.py` is deleted. Note `-b` now takes the family base (`http://localhost:8080/ok`) and `--paths` the spec's own paths.

- [x] **F-011 — Response findings are imprecise for some failures (v0.7.1)**
  - Type: limitation (messages and kinds, the failures are caught). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior, all seen in the JSON report of `conform` on `contract-fail`:
    - A body that matches no `oneOf` branch (`resp-009-oneof-no-match`) is reported with kind `missing-field`, location `a`, "property "a" is missing ... Or property "b" is missing". It says a field is missing, not that no branch matched (the catalog's CS-RESP-009). The discriminator case reports the missing field of the branch named by `type` (`meows`).
    - A root-level type mismatch (`resp-006b-array-for-object`: an array where an object is declared) has kind `other` and no location, where the same mismatch on a field has kind `wrong-type`.
    - A body that is not JSON (`resp-008-invalid-json`) or empty (`resp-008b-empty-body`) is reported with the parser's own text ("invalid character 'n' looking for beginning of object key string", "EOF"), kind `other`, no location.
    - The catalog says the `schema` assertion does not check an empty body ("partly"); in fact it fails the step with "response body is empty".
  - Repro: `clrsig conform <spec copy> -b http://localhost:8080 --paths /contract-fail/cases/resp-009-oneof-no-match --format json` (and the other cases above); see `scripts/check_expectations.py`.
  - Expected: a distinct finding kind for "no oneOf branch matched", "body is not valid JSON" and "body is empty", with a clear message; the same kind for a wrong type at the root and at a field; the catalog row for the empty body matching the behavior.
  - Pinned here instead by: `expectations/contract-fail.yaml` records today's kinds and messages, so a change shows up as a mismatch.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: distinct kinds `no-branch-matched`, `wrong-type` (also at the root), `constraint`, `invalid-body`, `empty-body`, `unexpected-property`; the catalog (CS-RESP-008) now describes the empty-body behavior.

- [x] **F-012 — No check ID in any report format (v0.7.1)**
  - Type: enhancement. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: the catalog gives every check an ID (CS-RESP-001 ...), but no output of `conform` or `run` (text, JSON, JUnit, HTML) contains it. Findings carry a coarse `kind` (`undeclared-status`, `missing-header`, `other`, ...), and several IDs share one kind (CS-RESP-007, 008, 010 and 011 are all `other`). A CI job cannot compare actual and expected check IDs, as the project plan asks, without parsing message text.
  - Repro: any failing `conform --format json`; search the output for `CS-`.
  - Expected: a `checkId` field on each finding (and the ID in the text report).
  - Handled here instead by: matching `kind`, `where` and a regex on the validator message, all recorded per case in `expectations/contract-fail.yaml`. Replace with the ID when it exists.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: every finding in the JSON report carries `checkId` (for example `CS-RESP-001`); the runner compares it. The text report still prints no ID, and a few findings carry none (F-022).

- [x] **F-013 — `--paths` and `--tags` do not filter the negative probes (v0.7.1)**
  - Type: bug / limitation. Found: 2026-11-21, `clrsig` v0.7.1, while building `conform-fail`.
  - Behavior: `clrsig conform ... --negative --paths /conform-fail/strict/missing-field` skips every other operation (shown as SKIP) but still runs all 26 negative probes of the whole spec, and the run exits 1 because other operations' probes fail. The catalog (CS-NC-007) says a filter leaves an operation out and "not sent".
  - Repro: `clrsig conform <spec copy> -b http://localhost:8080 --env clrsig/environments/conform-fail.yaml --negative --paths /conform-fail/strict/missing-field`; count the probe lines (28, not 2).
  - Expected: only the probes of the selected operations run, and the exit code reflects only those.
  - Handled here instead by: the runner runs `--negative` once for the whole spec and attributes each probe to its operation from the output text.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `--negative --paths /products` runs only the 16 probes of `/products`.

- [x] **F-014 — Negative probe results are missing from the JSON and JUnit reports (v0.7.1)**
  - Type: bug / limitation. Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: with `--negative`, the text and HTML reports list every probe (PASS or FAIL), but `--format json` and `--format junit` contain none of them. The JUnit report even says `failures="0"` while the run exits 1 because probes failed. A CI job that reads the machine-readable report cannot see probe failures.
  - Repro: the same command as F-013 with `--format json` or `--format junit`: no probe text, no `probes` field; compare with the text output.
  - Expected: probes (kind, operation, expected and actual status, pass or fail) in the JSON, and one JUnit test case per probe.
  - Handled here instead by: the runner parses the text report (`FAIL POST <path> - <probe> (expect ...)`). Replace with JSON once it carries probes.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `--format json` has a `probes` array and `--format junit` one test case per probe. The runner still reads the text report because the expectations quote its probe descriptions.

- [x] **F-015 — Operations with a form or multipart body fail in `conform` although server and spec agree (v0.7.1)**
  - Type: bug (false failure). Found: 2026-11-21, `clrsig` v0.7.1, while building `conform-fail`.
  - Behavior: `POST /form` (`application/x-www-form-urlencoded`) and `POST /multipart` (`multipart/form-data`) declare a `required: true` request body and a `400` response. The server handles both correctly. `conform` builds the request without a body (the catalog's CS-GAP-006), then checks its own request against the spec and reports "the request body does not fit the spec: value is required but missing" as a failure of the operation (finding kind `request`). The suggested fix ("Give the missing values in the environment, for example the path parameter used as {{id}}") cannot work for a body. The catalog says only that such bodies are "generated without a body", not that this fails the operation.
  - Repro: `clrsig generate <spec copy> -o <dir>` (no `body` in `formBody.yaml`), then `conform` on `/conform-fail/form`.
  - Expected: either generate a body from the schema (form fields, multipart parts), or skip the operation as "not exercised" and say so; never report a failure the user cannot fix.
  - Not worked around: the spec keeps `required: true` (the correct declaration). `expectations/conform-fail.yaml` records the failure as today's behavior.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `POST /form` and `POST /multipart` get generated bodies and pass; `generate` writes `formBody` and `multipartBody` with a body.

- [x] **F-016 — A bad dynamic function aborts a whole scenario with exit 2, and shares its finding kind with a missing value (v0.7.1)**
  - Type: limitation / catalog mismatch. Found: 2026-11-21, `clrsig` v0.7.1, while building `conform-fail`.
  - Behavior: `{{$noSuchFunction}}` in an environment value used through `conform` fails that one operation ("not sent: ... unknown function", exit 1), as the catalog's CS-RUN-002 says. The same function in a scenario step makes `clrsig run` print `Error: [step 1] bad function: {{$noSuchFunction}}: unknown function ...` and exit **2** before any step runs: a good step in the same scenario is never executed, and no JSON report is produced. The catalog describes only the failure form. Separately, CS-RUN-001 (no value) and CS-RUN-002 (function failed) both have the finding kind `missing-value`, distinguished only by the `blocked` text.
  - Repro: `clrsig run clrsig/scenarios/conform-fail-bad-function.yaml --env clrsig/environments/conform-fail.yaml --spec <spec copy>` (exit 2); and `conform` with `clrsig/environments/conform-fail-bad-function.yaml` (exit 1).
  - Expected: one documented behavior; ideally the step fails (exit 1) and the other steps still run, with a distinct finding kind for a failed function.
  - Pinned here instead by: `expectations/conform-fail.yaml` runs `run-002-bad-dynamic-function-in-environment` (exit 1) and `run-002b-bad-dynamic-function-in-scenario` (exit 2).
  - Status with v0.8.2: partly fixed. A failed dynamic function in `conform` has its own kind (`dynamic-value-failed`, CS-RUN-002). A bad function in a scenario step still aborts the whole run with exit 2 before any step.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.3: a bad function in a scenario step fails only that step (not sent, `unknown function $noSuchFunction`), the other steps run and `clrsig run` exits 1. A mistake in the scenario's own `variables:` still stops it with exit 2, by design.

- [x] **F-017 — A wrong-typed body value from the environment is reported as a JSON syntax error (v0.7.1)**
  - Type: limitation (message quality). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: with `amount: cheap` in the environment for a number field, the request check says "the request body does not fit the spec: invalid character 'c' looking for beginning of value". The value was inserted unquoted, so the body is not valid JSON, and the message names neither the field (`amount`) nor the expectation (a number). The catalog's example for CS-REQ-002 (`price="cheap"` where a number is declared) suggests a field-level message ("value must be a number"), which is what a path parameter gets ("path parameter "itemId" does not fit the spec: value abc: an invalid integer").
  - Repro: `conform --env clrsig/environments/conform-fail-bad-values.yaml --paths /conform-fail/requests/body-value` on the spec copy.
  - Expected: a message that names the field and the declared type, like the one for path parameters.
  - Pinned here by: `run req-002-wrong-body-value` in `expectations/conform-fail.yaml` records today's wording.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: the message is `the request body field "amount" takes its value from {{amount}}, which is "cheap"; that is not a valid JSON value (the spec declares a number)`.

- [x] **F-018 — Improvement request: no way to assert or limit response time (v0.7.1)**
  - Type: enhancement (the catalog already lists it as CS-GAP-005). Raised: 2026-11-21, while building the timing cases of `conform-fail`.
  - Today: a response that takes 4 seconds, or that gets slower with every call, passes as long as it arrives before the request timeout. The JSON report already carries `durationMs` per operation, but nothing can fail on it: scenario assertions are `status`, `header`, `jsonpath` and `schema` only. The only way to turn slowness into a failure is to set a shorter `--request-timeout`, which also aborts the request (no response to compare) and applies to every operation alike.
  - Request: (1) a scenario assertion such as `{ type: duration, operator: lt, expected: 500 }`; (2) a `conform` flag such as `--max-response-time <ms>` (and a per-operation override), reporting a distinct finding that keeps the response so it is still compared with the spec; (3) record the duration in baselines and coverage so a run that "gets slower" can be seen over time.
  - Why it matters here: `latency-within-timeout`, `degrading-latency` and `seeded-jitter-repeats` can only be pinned through timeouts today; with this feature they could assert the actual durations.
  - Pinned meanwhile by: `expectations/conform-fail.yaml` (`latency-within-timeout` references CS-GAP-005; the degrading and jitter sequences use `--request-timeout`).
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `conform --max-response-time <ms>` fails a slow response (`slow-response`, CS-RESP-014) and the scenario assertion `{ type: duration, operator: lt, expected: <ms> }` works. Used since: the degrading and jitter sequences, three limit cases and the `ok-latency` scenario assert response time; request timeouts remain only for responses that never arrive.

- [x] **F-019 — A response over 50 MB is silently truncated, and valid JSON then fails as "unexpected EOF" (v0.7.1)**
  - Type: bug (false failure, and a silent cap). Found: 2026-11-21, `clrsig` v0.7.1.
  - Behavior: the executor reads at most 50 MB + 1 byte of a response (`defaultMaxBodySize` in `executor/executor.go`) and keeps whatever it read, with no error, warning or note. `GET /conform-fail/large` (a 51 MB binary body) passes because binary bodies are not compared, so nothing shows that the body was cut. `GET /conform-fail/large/json` (a 51 MB body that is valid JSON, `Content-Length` correct) FAILS with "unexpected EOF" (finding kind `other`), as if the server had sent invalid JSON; the same endpoint at 49 MB passes. The message never mentions the size cap.
  - Repro: `clrsig conform <spec copy> -b http://localhost:8080 --env clrsig/environments/conform-fail-large-over-cap.yaml --paths /conform-fail/large/json` (and `...-near-cap.yaml` for the 49 MB pass).
  - Expected: say that the response exceeded the read limit (a distinct finding or a warning that names the limit and the real size from `Content-Length`), not a JSON syntax error; ideally make the limit configurable.
  - Pinned here by: `large-json-over-the-cap` and `large-binary-over-the-cap` in `expectations/conform-fail.yaml` (local only: Cloud Run does not pass bodies this large).
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: a response over 50 MB is reported as `body-too-large` (CS-RESP-013), naming the limit and the announced size, instead of "unexpected EOF".

- [x] **F-020 — `coverage quality` exits 1 when it finds gaps, although the catalog says coverage signals never change an exit code (v0.7.1)**
  - Type: catalog / behavior mismatch. Found: 2026-11-21, `clrsig` v0.7.1, while building the coverage cases.
  - Behavior: the catalog (section 2.3) says the four coverage signals "are signals, not failures: they never change an exit code". `clrsig coverage quality` documents and does the opposite: "Exit codes: 1 one or more gaps detected", and the run printed "4 gap(s) found" and exited 1. Only an empty workspace ("No coverage data found") exits 0. A CI step that runs it to read the signals therefore fails the build.
  - Repro: run `clrsig/scenarios/coverage-gaps.yaml` with `-w <fresh dir>` and `--spec <spec copy>`, then `clrsig coverage quality <spec copy> -w <dir>`; check the exit code.
  - Expected: one documented behavior. If signals are not failures, exit 0 (perhaps with a `--fail-on-gaps` flag); if gaps fail the run, the catalog should say so.
  - Pinned here by: `coverage.exit: 1` in `expectations/conform-fail.yaml`.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `coverage quality` finds the four gaps and exits 0.

- [x] **F-021 — OpenAPI 3.1 `examples` (a list) is ignored when building request bodies (v0.7.1)**
  - Type: bug (false failure). Found: 2026-11-22, `clrsig` v0.7.1, with `specs/ok-3.1.yaml`.
  - Behavior: in OpenAPI 3.1, `example` in a schema is deprecated and `examples` is a list. `clrsig generate`/`conform` only read `example`: for `POST /customers`, `POST /products`, `PUT /products/{id}` the generated bodies hold `{{email}}`, `{{name}}`, ... placeholders and `conform` reports "not sent: no value for {{name}}, {{price}}, {{stock}}"; `PATCH /products/{id}` is sent an empty body and fails its own `minProperties: 1`. 4 of 15 operations fail; 16 of 16 probes pass.
  - Isolated: the same spec with `examples: [x]` turned back into `example: x` (everything else 3.1: type arrays with "null", `const`, `license.identifier`) passes 15 of 15 operations and 16 of 16 probes. So type arrays, null and `const` are handled; only `examples` is not.
  - Repro: `uv run python scripts/clrsig_spec_copy.py specs/ok-3.1.yaml /ok <copy>` then `clrsig conform <copy> -b http://localhost:8080 --env clrsig/environments/ok.yaml`.
  - Expected: use the first entry of a schema's `examples` (3.1) when `example` is absent.
  - Pinned here by: `expectations/ok-31.yaml` (the four operations in `whole_spec.failing`).
  - Handling here: the 3.1 spec stays valid 3.1 and keeps `examples`; it is not bent to avoid the bug.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.2: `ok-3.1` passes 15 of 15 operations and 16 of 16 probes; the first entry of a schema's `examples` is used.

- [x] **F-022 — The `writeOnly` finding has no `checkId` and the generic kind `other` (v0.8.2)**
  - Type: limitation. Found: 2026-11-22, `clrsig` v0.8.2, while moving the expectations to `checkId`.
  - Behavior: every response finding of `contract-fail` carries a `checkId` except `resp-011-writeonly-leak` (a `writeOnly` property in a response, catalog CS-RESP-011): the finding is `{kind: other, where: password, summary: writeOnly property "password" in response}` with no `checkId`, and its `why` is the generic "The response does not match what the spec declares". The catalog lists CS-RESP-011 as caught.
  - Repro: `clrsig conform specs/contract-fail.yaml -b http://localhost:8080/contract-fail --paths /cases/resp-011-writeonly-leak --format json`; the finding has no `checkId`.
  - Expected: `checkId: CS-RESP-011` and its own kind, like the other response checks.
  - Pinned here by: `reported: null` on `resp-011-writeonly-leak` in `expectations/contract-fail.yaml`.
  - Closed: 2026-11-22, verified with released `clrsig` v0.8.3: the finding is kind `write-only-property` with `checkId` `CS-RESP-011`; the expectation now pins both.

---

## Baseline

Fixtures and expectations are verified against released `clrsig` **v0.8.3** (installed with Scoop; CI pins the same release). F-003 to F-021 were found with v0.7.1; v0.8.2 fixed all of them except F-016, and v0.8.3 fixed F-016 and F-022. No finding is open.

## Notes

- `conform` needs environment values for path parameters (`clrsig/environments/ok.yaml`). That is expected behavior, not a finding.
- `conform` exercises DELETE operations, so the store must be reset before each run. Later operations then see declared 404s. Expected behavior.
