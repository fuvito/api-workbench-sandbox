# ClearSignal Test Targets — Task List

**Rule:** Deliver a working vertical slice early. Do not write all specifications before the server can serve one API and pass one ClearSignal run.

Legend: `- [ ]` Not started · `- [x]` Complete

## Phase 0 — Decisions and repository

- [x] Repository name: `api-workbench-sandbox` (decided).
- [x] Select Python + FastAPI, served by Uvicorn.
- [ ] Confirm OpenAPI versions for the `ok` API (3.0, 3.1, or both).
- [ ] Confirm fixed test credentials for bearer, basic, and API-key examples.
- [ ] Confirm initial resource/operation target; source proposal is 80–120 operations at full breadth.
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

**ClearSignal findings:** tracked in `docs/clrsig-findings.md` (F-001, F-002 closed with v0.7.1). This repo does not work around ClearSignal issues. `conform` needs path-parameter values in `clrsig/environments/ok.yaml` (expected behavior).

### Expand breadth and schema coverage
- [ ] Add remaining resource families from PRD.
- [ ] Add HTTP methods: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS.
- [ ] Add path, query, header, and cookie parameters.
- [ ] Add request-body constraints and formats.
- [ ] Add response codes, default responses, and status ranges.
- [ ] Add response headers.
- [ ] Add `$ref`, `allOf`, `oneOf`, `anyOf`, discriminators, nullable/type arrays, maps, and additionalProperties cases.
- [ ] Add JSON, problem+json, and text/plain media types.
- [ ] Add bearer, basic, and API-key security examples.
- [ ] Add pagination, filtering, sorting, bulk operations, sub-resources, and actions.
- [ ] Add idempotency and ETag/If-Match examples.
- [ ] Grow toward the agreed operation target (source proposal: 80–120).
- [ ] Verify every valid operation conforms.

### Light business rules
- [ ] Unique-value conflicts (`409`).
- [ ] Stock checks (`422`) and stock restoration/decrement behavior.
- [ ] Order state transitions (`409` for illegal transitions).
- [ ] Computed totals, timestamps, sequential invoice numbers.
- [ ] Project/task ownership and cascade behavior.
- [ ] Expiring code/token (`410`).
- [ ] ETag/If-Match (`412`, `428`).
- [ ] Idempotency-key behavior.
- [ ] Async report progression (`202` then `200`).
- [ ] Rate limiting (`429`, `Retry-After`).
- [ ] Soft delete and include-deleted behavior.

### Baseline latency
- [ ] Implement bounded `GET /ok/ok-slow/{ms}` (confirm exact path against spec; source notes use `/ok-slow/{ms}` relative to `/ok`).
- [ ] Implement report polling delay.
- [ ] Implement optional bounded delay on list operations.
- [ ] Add `LATENCY_SCALE`.
- [ ] Verify default ClearSignal timeout passes and shorter configured timeout fails as expected.

**Exit criteria:** Baseline `ok` conformance and CRUD scenarios pass; reset produces repeatable state.

## Phase 3 — `contract-fail` response cases

- [ ] Create the `contract-fail` OpenAPI specification.
- [ ] Implement `CS-RESP-001` undeclared status.
- [ ] Implement default-response control case that passes.
- [ ] Implement `CS-RESP-002` wrong content type.
- [ ] Implement `CS-RESP-003` missing required response header.
- [ ] Implement `CS-RESP-004` wrong response-header type.
- [ ] Implement `CS-RESP-005` missing required response field.
- [ ] Implement `CS-RESP-006` wrong response field type.
- [ ] Add array-for-object and nested wrong-type cases.
- [ ] Add enum, numeric/string/array constraints, nullability, and format cases.
- [ ] Add invalid JSON and empty-body cases.
- [ ] Add oneOf/discriminator cases.
- [ ] Add additionalProperties cases.
- [ ] Add writeOnly leak case.
- [ ] Add XML known-gap case.
- [ ] Add multi-problem case and document first-reported behavior.
- [ ] Add known-gap cases and not-checked cases from PRD.
- [ ] Add scenario/expectation for every case.
- [ ] Verify exact check IDs and exit codes.

**Exit criteria:** Every listed case has a spec operation, handler behavior, expected result, and automated verification.

## Phase 4 — `conform-fail` API and run cases

### Negative probes and lenient/strict controls
- [ ] Implement lenient missing-field case.
- [ ] Implement lenient wrong-type case.
- [ ] Implement lenient missing-query case.
- [ ] Implement lenient no-auth case.
- [ ] Add known-gap controls for wrong auth, enum/boundary, and unknown fields.
- [ ] Implement strict control operations that correctly reject invalid requests.

### Spec/server disagreement
- [ ] Implement declared ghost route.
- [ ] Implement orphan operation with no route.
- [ ] Implement undocumented route for scenario-only check.
- [ ] Implement wrong-method case.
- [ ] Implement path-parameter type mismatch.
- [ ] Implement undeclared extra-header requirement.
- [ ] Add form/multipart and webhook/callback known-gap fixtures.

### Request construction and runtime failures
- [ ] Add wrong parameter environment value.
- [ ] Add wrong body environment value.
- [ ] Add missing placeholder scenario.
- [ ] Add bad dynamic function scenario.
- [ ] Add server-down/wrong-base-URL case.
- [ ] Add unreadable/invalid spec case.
- [ ] Add unset process-variable warning case.

### Timing and instability
- [ ] Implement `/slow`.
- [ ] Implement deterministic `/flaky` counter.
- [ ] Implement `/rate-limited`.
- [ ] Implement fixed `/latency/{ms}` with a safe cap.
- [ ] Implement jitter latency.
- [ ] Implement degrading latency and reset behavior.
- [ ] Implement hanging request within hosting limits.
- [ ] Implement slow headers and slow body where supported.
- [ ] Implement truncated body and connection reset where supported.
- [ ] Implement write-then-timeout behavior.
- [ ] Implement unavailable (`503`) and unavailable-then-OK cases.
- [ ] Implement redirect loop.
- [ ] Implement bounded large responses around the client size cap.
- [ ] Add idempotency and lost-update failure cases.
- [ ] Mark transport cases that cannot be reproduced reliably on Cloud Run as local-only.

### Drift, diff, coverage, and business-rule failures
- [ ] Implement startup `DRIFT`/`--drift` behavior.
- [ ] Add drift 0 and drift 1 expectations.
- [ ] Add all spec-diff v1/v2 fixture pairs.
- [ ] Add impact cases, including placeholder-path known gap.
- [ ] Add coverage-signal scenarios.
- [ ] Add business-rule failure scenarios (stock, state transition, duplicate, stale ETag, pagination, expiry).

**Exit criteria:** Each case has an explicit expected result and is checked by the test harness.

## Phase 5 — Expectations and CI

- [ ] Define `expected.yaml` format: command, expected exit code, expected check IDs.
- [ ] Support `local-only` cases and cloud-specific expectation overrides.
- [ ] Write a script/runner that executes all fixture commands.
- [ ] Compare actual exit codes and check IDs with expected values.
- [ ] Fail CI when a case no longer produces its expected outcome.
- [ ] Install pinned Python dependencies in CI.
- [ ] Run pytest unit and integration tests.
- [ ] Build and start server in CI.
- [ ] Poll readiness endpoint before tests.
- [ ] Run `ok`, `contract-fail`, and `conform-fail` checks, plus diff and scenario checks.
- [ ] Add CI leg against released `clrsig`.
- [ ] Add nightly leg against `api-workbench@main` where practical.
- [ ] Document local test commands in README.

**Exit criteria:** CI detects both accidental fixture changes and ClearSignal regressions.

## Phase 6 — Cloud Run deployment

- [ ] Confirm public versus private access.
- [ ] Confirm Google Cloud project and region.
- [ ] Configure billing budget alerts.
- [ ] Build and test the production container image locally using the Python/FastAPI application and Uvicorn.
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

- [ ] Complete README with architecture, startup, reset, scenarios, and troubleshooting.
- [ ] Document all fixed test credentials (never use real secrets).
- [ ] Document admin-token setup.
- [ ] Document request and latency caps.
- [ ] Verify no outbound caller-controlled requests are possible.
- [ ] Verify request-body and response-size limits.
- [ ] Verify concurrent slow-request limits.
- [ ] Tag first release.
- [ ] Record known gaps and cloud-specific limitations.

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
