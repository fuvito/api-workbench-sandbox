# ClearSignal Test Targets — Task List

**Rule:** Deliver a working vertical slice early. Do not write all specifications before the server can serve one API and pass one ClearSignal run.

Legend: `- [ ]` Not started · `- [x]` Complete

## Phase 0 — Decisions and repository

- [x] Repository name: `api-workbench-sandbox` (decided).
- [x] Select Python + FastAPI, served by Uvicorn.
- [ ] Confirm OpenAPI versions for the `ok` API (3.0, 3.1, or both).
- [ ] Confirm fixed test credentials for bearer, basic, and API-key examples. (In use pending your confirmation: `test-token`, `test-user`/`test-pass`, `test-api-key`; see README.)
- [x] Operation target: 60 to 70 operations (decided; source proposal was 80–120).
- [ ] Decide where the expected-results file lives and how it relates to the ClearSignal check catalog.
- [x] Python 3.13.1 (decided).
- [x] Dependency management: `uv` (`pyproject.toml` + committed `uv.lock`; decided).
- [x] Create the standalone repository (`api-workbench-sandbox`).
- [x] Add `README.md` (stub), `docs/PRD.md`, `docs/TASKLIST.md`, and `CLAUDE.md`.

**Exit criteria:** Decisions that affect project structure are recorded; repository exists.

## Phase 1 — Server skeleton (first vertical slice)

- [x] Create a Python application using FastAPI.
- [x] Configure Uvicorn as the ASGI server and define the local run command.
- [x] Add a minimal dependency manifest with FastAPI, Uvicorn, Pydantic, and test dependencies only as needed.
- [x] Create one application process and one HTTP listener.
- [x] Read `PORT` (default `8080`) and `HOST` (local default `127.0.0.1`).
- [x] Implement `GET /ok/health`.
- [x] Implement `GET /contract-fail/health`.
- [x] Implement `GET /conform-fail/health`.
- [x] Implement serving of `/ok/openapi.yaml`.
- [x] Implement serving of `/contract-fail/openapi.yaml`.
- [x] Implement serving of `/conform-fail/openapi.yaml`.
- [x] Implement `PUBLIC_BASE_URL` handling for OpenAPI `servers` values.
- [x] Add a generic in-memory store helper (create, get, update, delete, list).
- [x] Protect shared store mutations with `asyncio.Lock` or an equivalent concurrency-safe mechanism.
- [x] Use async handlers and `asyncio.sleep()` for simulated latency; do not block request workers with `time.sleep()`.
- [x] Add pytest/httpx tests for health, spec serving, reset, and one stateful request flow.
- [x] Implement independent per-family stores.
- [x] Implement each `POST <prefix>/__admin/reset` with seed restoration and `204`.
- [x] Protect admin endpoints when `ADMIN_TOKEN` is set.
- [x] Add request logging (method, path, status, duration, API prefix).
- [x] Add graceful shutdown (Uvicorn `timeout_graceful_shutdown`; verified: `docker stop` exits 0 after a clean shutdown).
- [x] Add Dockerfile and verify local container startup (verified: image builds, `clrsig conform` passes on all three families in the container, admin token enforced).
- [x] Run one real ClearSignal command against the local server.

**KT checkpoint:** write `docs/kts/phase-1-server-skeleton.md` and walk through it together. (Done.)

**Exit criteria:** One command starts the server; health/spec/reset work; one end-to-end ClearSignal check works.

## Phase 2 — `ok` baseline API

### First three resources
- [x] Choose three representative resources: products, orders, projects/tasks (decided).
- [x] Hand-write their OpenAPI specification (`specs/ok.yaml`, 21 operations incl. health).
- [x] Implement list and get operations.
- [x] Implement create, update, and delete operations (PUT only; PATCH comes with breadth).
- [x] Add deterministic seed records with stable IDs (sequential, never reused, reset with the store).
- [x] Implement declared success and error response shapes (400, 404, 422 with `{code, message}`).
- [x] Reject missing required fields and wrong input types (400; no type coercion, unknown fields rejected).
- [x] Add one CRUD scenario with variable extraction (`clrsig/scenarios/ok-crud.yaml`).
- [x] Verify `clrsig conform` passes (21/21, plus 28/28 negative probes) with released `clrsig` v0.7.1 (v0.5.0 failed; F-001 and F-002, now closed in `docs/clrsig-findings.md`).
- [x] Verify scenario passes after reset (scenario starts with reset; passes on v0.7.1).
- [x] Verify repeat execution is deterministic (two consecutive runs: 20/20 steps, 29/29 assertions).

**ClearSignal findings:** tracked in `docs/clrsig-findings.md` (F-001, F-002 closed with v0.7.1; F-003 to F-020 open). This repo does not work around ClearSignal issues. `conform` needs path-parameter values in `clrsig/environments/ok.yaml` (expected behavior).

### Expand breadth and schema coverage
- [x] Add remaining resource families (customers, payments, invoices, discount codes, notifications, reports, settings, secured examples), kept within the 60 to 70 operation target.
- [x] Add HTTP methods: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS (HEAD and OPTIONS on products only; PATCH on all four resources).
- [x] Add path, query, header, and cookie parameters: header (`X-Request-Id`, `Accept-Language`, `If-Match`, `Idempotency-Key`, `X-Client-Id`), required cookie (`theme`), array (form, explode false and true), integer, number, boolean, enum, `date`, `date-time`, `uuid`. `conform` cannot send the cookie or the explode-false array (F-008, F-009); the scenario does.
- [x] Add request-body constraints and formats (email, date, uuid, pattern, min/max, minItems/maxItems, uniqueItems, maxProperties).
- [x] Add response codes, default responses, and status ranges. (Done: 200, 201, 202, 204, 207, 400, 401, 403, 404, 409, 410, 412, 422, 428, 429, 503, `default`, `4XX`, `2XX`.)
- [x] Add response headers: `X-Total-Count`, `Allow`, `ETag`, `Location`, `Retry-After`, `WWW-Authenticate`, `X-RateLimit-*`, `X-Request-Id` (echoed or generated), optional `Cache-Control`.
- [ ] Add `$ref`, `allOf`, `oneOf`, `anyOf`, discriminators, nullable/type arrays, maps, and additionalProperties cases. (Done: all except 3.1 type arrays, which wait for the 3.0/3.1 decision; `nullable` uses 3.0.)
- [x] Add JSON, problem+json (customers), and text/plain (`GET /ok/version`) media types.
- [x] Add bearer, basic, and API-key (header and query) security examples. Verified by `ok-schemas-and-security.yaml`; `conform` only authenticates bearer (F-005).
- [x] Add pagination (offset and cursor), filtering, sorting, bulk operations (atomic create, partial delete with 200/207), sub-resources, and actions.
- [x] Add idempotency and ETag/If-Match examples.
- [x] Grow toward the agreed operation target: 65 operations (target 60 to 70).
- [ ] Verify every valid operation conforms. (`conform` passes 63 of 65 operations; the two failures are `GET /lookup` and `GET /preferences`, caused by `clrsig` findings F-009 and F-008, not by the server. The scenarios cover both operations.)

### Light business rules
- [x] Unique-value conflicts (`409`): customer email, case-insensitive, freed by soft delete. (Product SKU and tag name are not modeled.)
- [x] Stock checks (`422`) and stock restoration/decrement behavior: create checks stock, pay takes it, cancelling a paid order gives it back.
- [x] Order state transitions (`409` for illegal transitions): `pay`, `ship`, `deliver`, `cancel` actions; only pending orders are editable.
- [x] Computed totals (quantity x price + 10% tax), server timestamps, sequential invoice numbers (`INV-000001`...).
- [x] Project/task ownership and cascade behavior: `409` with open tasks, `?cascade=true` deletes them too.
- [x] Expiring code/token (`410`): discount codes, evaluated against an injectable clock.
- [x] ETag/If-Match (`412`, `428`): required on order PUT/PATCH, optional on tasks.
- [x] Idempotency-key behavior on `POST /payments` (replay `200`, different body `422`).
- [x] Async report progression (`202` then `200`), computed from poll counts.
- [x] Rate limiting (`429`, `Retry-After`) on `GET /ok/rate-limited` only: 5 calls per 60 s per client.
- [x] Soft delete and include-deleted behavior (customers).

### Baseline latency
- [x] Implement bounded `GET /ok/ok-slow/{ms}` (path confirmed: `/ok-slow/{ms}` relative to `/ok`; 0 to 10000 ms, `400` above the cap, `503` when too many slow requests run).
- [ ] Implement report polling delay. (Reports already progress by poll count, which the source notes allow: "N seconds or N polls". No wall-clock delay was added; decision pending.)
- [x] Implement optional bounded delay on list operations: `?delay=<ms>` (0 to 10000) on all eight list operations, declared in the spec.
- [x] Add `LATENCY_SCALE` (0 to 10, default 1; applied to every deliberate delay; the scaled sleep is capped at 30 s).
- [x] Verify default ClearSignal timeout passes and shorter configured timeout fails as expected: `ok-latency` passes by default; `--timeout 100` fails the two slow steps (exit 1); `conform --request-timeout 500` against a 1500 ms delay fails with `context deadline exceeded`.

**Exit criteria:** Baseline `ok` conformance and CRUD scenarios pass; reset produces repeatable state.

## Phase 3 — `contract-fail` response cases

- [x] Create the `contract-fail` OpenAPI specification.
- [x] Implement `CS-RESP-001` undeclared status.
- [x] Implement default-response control case that passes.
- [x] Implement `CS-RESP-002` wrong content type.
- [x] Implement `CS-RESP-003` missing required response header.
- [x] Implement `CS-RESP-004` wrong response-header type.
- [x] Implement `CS-RESP-005` missing required response field.
- [x] Implement `CS-RESP-006` wrong response field type.
- [x] Add array-for-object and nested wrong-type cases.
- [x] Add enum, numeric/string/array constraints, nullability, and format cases.
- [x] Add invalid JSON and empty-body cases.
- [x] Add oneOf/discriminator cases.
- [x] Add additionalProperties cases.
- [x] Add writeOnly leak case.
- [x] Add XML case (`resp-012-xml-valid`). The current catalog makes this "not checked" (CS-NC-009), not a failure as the source notes expected; the expectation follows the catalog.
- [x] Add multi-problem case and document first-reported behavior.
- [x] Add known-gap cases (`gap-format-email-uuid`, `gap-undeclared-header`, `gap-slow-response`) and not-checked cases (`nc-002-no-content-declared`, `nc-octet-stream`, `nc-no-content-type`, undocumented path). `nc-204-with-body` became `nc-002-no-content-declared`: HTTP forbids a body on a 204.
- [x] Add scenario/expectation for every case: `expectations/contract-fail.yaml` (35 cases) and `clrsig/scenarios/contract-fail-checkers.yaml` (both response checkers side by side).
- [x] Verify exact check IDs and exit codes: `scripts/check_expectations.py` runs every case, the whole spec and the scenario (35/35 cases, 14/14 steps). Verified through a spec copy because of F-010; IDs are recognized by finding kind and message because of F-012.

**ClearSignal findings from this phase:** F-010 (response checks silently skipped for specs with `servers`; the working copy `scripts/clrsig_spec_copy.py` is temporary), F-011 (imprecise kinds and messages), F-012 (no check IDs in output).

**Exit criteria:** Every listed case has a spec operation, handler behavior, expected result, and automated verification.

## Phase 4 — `conform-fail` API and run cases

### Negative probes and lenient/strict controls
- [x] Implement lenient missing-field case (`POST /conform-fail/lenient/missing-field`, fails CS-PROBE-001).
- [x] Implement lenient wrong-type case (fails CS-PROBE-002).
- [x] Implement lenient missing-query case (fails CS-PROBE-003).
- [x] Implement lenient no-auth case (fails CS-PROBE-004).
- [x] Add known-gap controls for wrong auth (CS-GAP-008), enum/boundary and unknown fields (CS-GAP-009): lenient, but not probed today, so they pass.
- [x] Implement strict control operations that correctly reject invalid requests (seven `/strict/*` twins; verified by `scripts/check_expectations.py --expectations expectations/conform-fail.yaml`: 26 probes, 4 fail, all as expected).

### Spec/server disagreement
- [x] Implement declared ghost route (`GET /ghost`: declared, not served; CS-RESP-001).
- [x] Implement orphan operation (`DELETE /orphan`: the server implements only POST, so 405; CS-RESP-001).
- [x] Implement undocumented route (`GET /undocumented`; a scenario step on it is the catalog's CS-NC-001, which no report format shows).
- [x] Implement wrong-method case (`PATCH /wrong-method`: the server implements only PUT; CS-RESP-001).
- [x] Implement path-parameter type mismatch (`GET /path-param/{id}`: integer in the spec, UUID on the server; CS-RESP-001).
- [x] Implement undeclared extra-header requirement (`POST /requires-extra-header`; CS-RESP-001).
- [x] Add form/multipart and callback known-gap fixtures: `POST /form` and `/multipart` (CS-GAP-006; they FAIL today with a request-body finding, F-015) and `POST /subscribe` with a callback (CS-GAP-010; passes). 3.1 `webhooks` are not covered (the spec is 3.0.3).

### Request construction and runtime failures
- [x] Add wrong parameter environment value (`conform-fail-bad-values.yaml`, `itemId=abc` on `GET /requests/param-type/{itemId}`; CS-REQ-001).
- [x] Add wrong body environment value (`amount=cheap` on `POST /requests/body-value`; CS-REQ-002, reported as a JSON syntax error, F-017).
- [x] Add missing placeholder case (`conform-fail-missing-value.yaml`: the request is not sent; CS-RUN-001).
- [x] Add bad dynamic function cases: through an environment value (exit 1) and in a scenario (the whole run aborts with exit 2, F-016); CS-RUN-002.
- [x] Add server-down/wrong-base-URL case (`-b http://localhost:1`; CS-RUN-003).
- [x] Add unreadable/invalid spec cases: invalid YAML, valid YAML that is not OpenAPI, a missing file, a URL that returns 404; all CS-RUN-004, exit code 2.
- [x] Add unset process-variable warning case (`conform-fail-unset-var.yaml`; CS-RUN-005, a warning, exit code unchanged).

### Timing and instability
- [x] Implement `/slow` (15 s times `LATENCY_SCALE`, past the default 10 s timeout; CS-RUN-003).
- [x] Implement deterministic `/flaky` counter (every 3rd call is a 500; pass, pass, fail repeating; reset restores it).
- [x] Implement `/rate-limited` (counter based: the 4th call and later get an undeclared 429 with `Retry-After`).
- [x] Implement fixed `/latency/{ms}` with a safe cap (0 to 30000 ms, 400 outside).
- [x] Implement jitter latency (a seeded sequence per call number, so a run after reset repeats exactly: 160, 906, 477, 477, 507, 264 ms with the defaults).
- [x] Implement degrading latency and reset behavior (100 ms, then +300 ms per call, capped at 5 s; reset restarts it).
- [x] Implement hanging request within hosting limits (`/timeout/hang`: 30 s times `LATENCY_SCALE`, then gives up; local only).
- [x] Implement slow headers (`/timeout/slow-headers`, 4 s) and slow body (`/timeout/slow-body`: headers at once, 50 bytes at 5 per second); local only.
- [x] Implement truncated body (declares 1000 bytes, sends 100; CS-RUN-003, not CS-RESP-008) and connection reset (a TCP reset through the live server's own connection); local only.
- [x] Implement write-then-timeout behavior (`POST /timeout/after-write`: the record is stored, the answer comes 15 s later; shown by a scenario).
- [x] Implement unavailable (`503` with `Retry-After`) and unavailable-then-OK (503 for the first 2 calls after reset) cases.
- [x] Implement redirect loop (`/redirect-loop` only ever redirects to itself; ClearSignal stops after 10 redirects; CS-RUN-003).
- [x] Implement bounded large responses around the client size cap (`/large` and `/large/json`, 0 to 60 MB; 49 MB passes, 51 MB is silently truncated, F-019); local only.
- [x] Add idempotency (`POST /idempotent`) and lost-update (`PUT /lost-update`) failure cases, visible only in `clrsig/scenarios/conform-fail-write-bugs.yaml`.
- [x] Mark transport cases that cannot be reproduced reliably on Cloud Run as local-only (`local_only: true` in the expectations; `--cloud` skips them). Nothing is claimed for Cloud Run until it is verified there (Phase 6).

### Drift, diff, coverage, and business-rule failures
- [x] Implement startup `DRIFT`/`--drift` behavior (`python -m app --drift=<n>`, the flag wins over the variable; level 1 breaks `GET /conform-fail/drift/report`).
- [x] Add drift 0 and drift 1 expectations: the baseline ratchet with a real server per level (3 known/0 new at drift 0; 3 known/1 new, exit 1, CS-RUN-006 at drift 1; 1 fixed in the other direction; a missing baseline is exit 2).
- [x] Add all spec-diff v1/v2 fixture pairs (13 under `specs/diff/`, one change each; `expectations/diff.yaml`). The notes' `deprecated-operation` is INFO in oasdiff, not WARN; the WARN case is `optional-param-removed`.
- [x] Add impact cases (`clrsig/scenarios/impact/`): a literal id and a `{{userId}}` placeholder are both matched (CS-IMP-001); the notes expected the placeholder to be missed (CS-GAP-007), but that gap is closed in v0.7.1 and the catalog.
- [x] Add coverage-signal scenarios (`clrsig/scenarios/coverage-gaps.yaml` with `specs/coverage/coverage.yaml`: one gap each of CS-COV-001 to 004). The command exits 1 on gaps (F-020); the standard spec matches nothing (F-010).
- [x] Add business-rule failure scenarios (`clrsig/scenarios/conform-fail-business-rules.yaml`): stock, state transition, duplicate email, insufficient funds answered 200, unstable pagination, expired token; the stale ETag rule is the existing `PUT /lost-update` scenario.

**Exit criteria:** Each case has an explicit expected result and is checked by the test harness.

## Phase 5 — Expectations and CI

- [x] Define the expectations format (`expectations/<family>.yaml`, one file per family; described in each file's header): command, expected exit code, expected check IDs. `expectations/ok.yaml` added for the `ok` API (F-008/F-009 pinned).
- [x] Support `local-only` cases and cloud-specific expectation overrides.
- [x] Write a script/runner that executes all fixture commands.
- [x] Compare actual exit codes and check IDs with expected values.
- [x] Fail CI when a case no longer produces its expected outcome.
- [x] Install pinned Python dependencies in CI.
- [x] Run pytest unit and integration tests.
- [x] Build and start server in CI.
- [x] Poll readiness endpoint before tests.
- [x] Run `ok`, `contract-fail`, and `conform-fail` checks, plus diff and scenario checks.
- [x] Add CI leg against released `clrsig`.
- [x] Add nightly leg against `api-workbench@main` where practical (cron 03:17 UTC; a manual run can pick `main` too; verified once by hand, the cron itself has not fired yet).
- [x] Document local test commands in README.

**Exit criteria:** CI detects both accidental fixture changes and ClearSignal regressions.

## Phase 6 — Cloud Run deployment

> Prepared, not started: `docs/cloud-run-prep.md` has the local verification, proposed settings and an unverified runbook. Everything that needs Google Cloud is still open.

- [ ] Confirm public versus private access.
- [ ] Confirm Google Cloud project and region.
- [ ] Configure billing budget alerts.
- [x] Build and test the production container image locally using the Python/FastAPI application and Uvicorn (run with `PORT=9000`, a token, a public URL, 512 MB: see `docs/cloud-run-prep.md`).
- [ ] Create Artifact Registry repository.
- [ ] Store `ADMIN_TOKEN` in Secret Manager.
- [ ] Deploy Cloud Run service with `max-instances=1` initially.
- [ ] Configure `PORT`, `HOST`, `PUBLIC_BASE_URL`, `DRIFT`, `LATENCY_SCALE`, and admin secret.
- [ ] Set request timeout based on longest intended cloud delay.
- [ ] Set appropriate concurrency and resource limits.
- [ ] Verify health and all OpenAPI documents.
- [ ] Verify reset requires the admin token.
- [ ] Run ClearSignal checks against deployed service.
- [ ] Record cloud-specific overrides for transport-sensitive cases.
- [ ] Verify two sequential scenarios produce expected results.
- [ ] Document scale-to-zero and in-memory state-loss behavior.
- [ ] Document that concurrent users share the same API stores in MVP.

**Exit criteria:** The same container runs locally and on Cloud Run; cloud expectations pass, with documented local-only exceptions.

## Phase 7 — Release readiness

- [x] Complete README with architecture, startup, reset, scenarios, and troubleshooting.
- [x] Document all fixed test credentials (never use real secrets). (README table; whether these are the final credentials is still an open decision).
- [x] Document admin-token setup.
- [x] Document request and latency caps. (README table).
- [x] Verify no outbound caller-controlled requests are possible. (no HTTP client in `app/`; the only redirect points at itself).
- [x] Verify request-body and response-size limits. (found no request-body cap: added a 1 MiB limit, `app/limits.py`; checked against the container; `/large` caps at 60 MB and streams).
- [x] Verify concurrent slow-request limits. (container: 25 parallel slow requests gave 20 x 200 and 5 x 503; later requests succeed).
- [ ] Tag first release.
- [x] Record known gaps and cloud-specific limitations. (README section).

## Knowledge transfer

At the end of every phase, add a note under `docs/kts/` (see `docs/kts/README.md`) and review it together before starting the next phase.

## Definition of done

A feature is done only when:
- Its behavior is represented in the relevant OpenAPI spec.
- Its handler is implemented.
- Its seed/reset behavior is deterministic where relevant.
- A ClearSignal scenario or automated check exercises it.
- Expected check IDs and exit codes are recorded.
- CI verifies the expectation.
- Local/cloud differences are documented where applicable.
