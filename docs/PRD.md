# ClearSignal Test Targets — Minimum PRD

**Status:** Draft  
**Source:** `docs/from-main/api-workbench-sandbox-project.md` (copied from https://github.com/fuvito/api-workbench/blob/main/docs/planning/api-workbench-sandbox-project.md (Draft v0.2, 2026-11-20))  
**Project repository:** `api-workbench-sandbox` (decided; no rename)  
**Delivery:** Local-first; Google Cloud Run deployment later

## 1. Product summary

Build one small, independent server that exposes several OpenAPI-described REST APIs from one running program. ClearSignal uses these APIs to exercise API Contract Validation and Spec Conformance Testing repeatedly, both manually and in CI.

This is a test fixture, not a general-purpose mock-server product.

## 2. Goals

- Provide a correct baseline API that produces no false failures.
- Provide deliberately incorrect responses that exercise `CS-RESP-*` checks.
- Provide deliberately non-conformant API behavior and run conditions that exercise `CS-REQ-*`, `CS-RUN-*`, `CS-PROBE-*`, `CS-DIFF-*`, coverage, and known-gap outcomes.
- Support realistic multi-step CRUD scenarios using in-memory state.
- Exercise latency, timeouts, intermittent failures, and a small set of business rules.
- Run locally with one command and one port.
- Be container-ready from the first working vertical slice and deployable to Cloud Run without application redesign.

## 3. Non-goals

- No production business logic.
- No database, migrations, external services, or authentication provider.
- No general-purpose mocking platform.
- No multi-tenant service or user-management system in the MVP.
- No persistent state across process restarts.
- No replacement for the separate failure-showcase project.

## 4. Users and primary workflow

**Primary user:** ClearSignal developer or CI job.

1. Start the test-target server.
2. Readiness-poll `/health`.
3. Fetch the relevant OpenAPI document.
4. Reset the relevant API to seed state.
5. Run ClearSignal `conform`, `run`, `diff`, or `impact` checks against the fixture.
6. Compare actual exit codes and check IDs with expected results.

The same server process exposes all three API families on one port.

## 5. MVP scope

### 5.1 API families

| Family | Prefix | Purpose | Expected outcome |
|---|---|---|---|
| `ok` | `/ok` | Correct, realistic API baseline | Checks and scenarios pass |
| `contract-fail` | `/contract-fail` | Deliberately incorrect responses | Expected `CS-RESP-*` failures |
| `conform-fail` | `/conform-fail` | Request, probe, run, API-shape, and behavior failures | Expected `CS-REQ-*`, `CS-RUN-*`, `CS-PROBE-*`, `CS-DIFF-*` outcomes |

Each family serves its OpenAPI document at `<prefix>/openapi.yaml` and exposes `GET <prefix>/health`.

### 5.2 `ok` API

- Start with three resources and a working end-to-end CRUD flow, then grow to **60 to 70 operations** (decided; the source document proposed 80–120). Current count: 65.
- Support GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS where specified.
- Exercise parameters, request bodies, response codes and headers, schema composition, media types, security schemes, pagination, filtering, sorting, bulk operations, sub-resources, actions, idempotency, and optimistic concurrency.
- Valid requests must match the OpenAPI specification.
- Invalid requests must be rejected with the declared 4xx response.
- Maintain small fixed seed data and per-API in-memory stores.
- Include only the small business-rule set listed below.

### 5.3 `contract-fail` API

Implement the response-failure cases in source document section 4. At minimum, the first vertical slice covers `CS-RESP-001` through `CS-RESP-006`; subsequent work adds remaining response checks, known gaps, and not-checked outcomes.

Each case must:
- Have an operation in the OpenAPI spec.
- Deliberately violate only its intended contract condition, except explicitly documented multi-problem cases.
- Have an expected check ID and expected exit code.
- Be exercised by a ClearSignal scenario or command.

### 5.4 `conform-fail` API

Implement the cases in source document section 5:
- Lenient request validation and negative probes.
- Spec/server route and method mismatches.
- Invalid environment/request values and runtime failures.
- Timing, instability, timeout, and availability behavior.
- Baseline drift modes.
- Coverage signals.
- Business-rule failures observable through scenario assertions.

Spec-to-spec `clrsig diff` fixtures are YAML pairs and do not require server routes.

### 5.5 In-memory state and reset

- Data is held in process memory and survives between requests while the process remains alive.
- Each API family has an independent store.
- Each API exposes `POST <prefix>/__admin/reset`, returning `204` and restoring seed data.
- Reset routes are deliberately absent from the public OpenAPI specifications.
- `GET <prefix>/__admin/state` is optional and intended only for local debugging.
- Reset and state endpoints require `Authorization: Bearer <ADMIN_TOKEN>` when `ADMIN_TOKEN` is configured. Always configure it in a deployed environment.
- The MVP does not promise isolation between concurrent users or persistence across restarts/instance replacement.

### 5.6 Latency and fault behavior

Implement bounded, reproducible behaviors needed by the fixture:
- Fixed and variable latency.
- Optional list-operation delay.
- Slow responses and client-timeout cases.
- Flaky responses and deterministic counters.
- Rate limiting.
- Unavailable-then-OK behavior.
- Connection/body edge cases where supported by the runtime and hosting platform.

Caps (implemented in `app/latency.py`): a requested delay is at most 10000 ms; `LATENCY_SCALE` is 0 to 10; the scaled sleep is at most 30 s; at most 20 deliberately slow requests run at once (more get `503`). On `ok`, `GET /ok-slow/{ms}` and the optional `?delay=<ms>` parameter on list operations use them.

The source document identifies some connection-level cases as potentially local-only on Cloud Run. Maintain local/cloud expectation differences where necessary. Bound delays and concurrent slow requests.

### 5.7 Light business rules

Keep rules small and limited to:
- Unique values return `409`.
- Stock checks and order quantity behavior return `422` when appropriate.
- Order state transitions reject illegal moves with `409`.
- Computed totals, timestamps, and sequential invoice numbers.
- Project/task ownership and cascade behavior.
- Expiring codes/tokens return `410`.
- ETag/If-Match concurrency (`412`, `428`).
- Idempotency-key behavior.
- Asynchronous report status progression.
- Rate limiting (`429`, `Retry-After`).
- Soft-delete behavior.

## 6. Technical requirements

### 6.1 Repository and runtime

- One repository, one application, one process, one listening port.
- Repository name: `api-workbench-sandbox` (decided).
- **Language/framework: Python + FastAPI.**
- ASGI server: Uvicorn.
- Dependency management: **uv** (`pyproject.toml`, `uv.lock`, `.python-version`).
- Python **3.13.1** (decided; matches the local `.venv`). The container base image must use the same version.
- Use Pydantic for application configuration and internal validation where useful.
- Use Starlette/FastAPI middleware for cross-cutting request concerns only.
- Use `pytest` and `httpx` for automated tests; use `pytest-asyncio` if async test support is needed.
- Port from `PORT`, default `8080`.
- Local bind defaults to `127.0.0.1`; container uses `HOST=0.0.0.0`.
- Use path prefixes `/ok`, `/contract-fail`, `/conform-fail`.
- OpenAPI specs are hand-written and are the source of truth.
- Include a Dockerfile in the first working vertical slice.

### 6.1.1 Python application stack

- Runtime/framework: Python + FastAPI.
- ASGI server: Uvicorn.
- Internal data/config validation: Pydantic where useful.
- Automated tests: pytest + httpx; pytest-asyncio where needed.
- YAML parsing: PyYAML only if runtime parsing is required.
- Keep dependencies minimal. Do not add an ORM, database client, task queue, or Redis client for the MVP.

### 6.2 Configuration

Read configuration from environment variables:
- `PORT` — default `8080`.
- `HOST` — local default `127.0.0.1`.
- `PUBLIC_BASE_URL` — optional public server URL used to render correct OpenAPI `servers` values.
- `DRIFT` — baseline drift level; default `0`.
- `ADMIN_TOKEN` — protects administrative endpoints when set.
- `LATENCY_SCALE` — optional multiplier for deliberate delays, 0 to 10, default 1.

Also support the source document's `--drift=<n>` startup flag if the chosen implementation supports it cleanly.

### 6.3 Operational behavior

- `GET` health endpoints return `200`.
- Log one structured line per request to stdout, including method, path, status, duration, and API prefix.
- Handle `SIGTERM` gracefully and finish in-flight requests within the shutdown grace period.
- Do not write runtime data to the container filesystem.
- Keep specs as checked-in YAML files copied read-only into the image; never generate them at runtime.
- Keep startup fast.
- Use concurrency-safe stores (`asyncio.Lock` per store or an equivalent approach); keep critical sections short.
- Use asynchronous request handlers for I/O-bound behavior and `asyncio.sleep()` for deliberate latency. Do not use blocking `time.sleep()` in request handlers.
- Use Pydantic for internal configuration and request models where useful, but do not let FastAPI-generated OpenAPI replace the hand-written fixture specifications.
- Use Starlette/FastAPI middleware only for cross-cutting concerns such as request IDs, logging, and admin authentication. Keep endpoint-specific fault behavior in handlers or a dedicated fault-injection component.
- Avoid outbound calls and open-relay behavior.

## 7. Security and abuse controls

- The fixture contains no real user data or real secrets; test credentials are documented fixtures only.
- Protect reset and optional state-inspection endpoints with the admin token in deployed environments.
- Bound request-body sizes, response sizes, delay parameters, and `/large` responses.
- Cap concurrent slow/hanging requests.
- Do not accept arbitrary user code or make caller-controlled outbound requests.
- If deployed publicly, use a low Cloud Run maximum-instance setting and configure a billing alert.
- Public versus private Cloud Run access remains a deployment decision to settle before exposing the service.

## 8. CI and quality requirements

CI must:
1. Build the server.
2. Start it locally.
3. Poll `/health` until ready.
4. Run the ClearSignal commands/scenarios.
5. Compare actual exit codes and check IDs against an expectations file.
6. Fail when a fixture stops producing its expected result.

Run two CI legs where practical:
- Against the released `clrsig`.
- Nightly against `api-workbench@main`.

The expectations file records command, expected exit code, expected check IDs, and optional cloud-specific overrides or `local-only` markers.

## 9. Cloud Run deployment requirements

Cloud deployment follows a successful local implementation.

- Build and publish the Docker image to Artifact Registry.
- Deploy one Cloud Run service listening on the configured `PORT`.
- Configure `max-instances=1` initially.
- Set a sensible concurrency value and request timeout.
- Set `PUBLIC_BASE_URL` to the deployed service URL.
- Store `ADMIN_TOKEN` in Secret Manager and inject it into the service.
- Run post-deployment health and ClearSignal checks.
- Record cloud-specific expected outcomes for transport cases affected by the Google front end.
- Treat scale-to-zero or instance replacement as a loss of in-memory state; scenarios must reset before use.
- A single instance does not provide session isolation between simultaneous users. Document this limitation.

## 10. Acceptance criteria

### Local MVP
- One command starts one process on one port.
- All three OpenAPI documents are served at their documented paths.
- All three health endpoints return `200`.
- Each API has an independent reset endpoint that restores deterministic seed data.
- The `ok` API supports at least three resources and a passing CRUD scenario.
- Initial `contract-fail` cases produce the expected response check IDs.
- Initial `conform-fail` cases produce their expected outcomes.
- CI compares actual results against an expectations file.
- Re-running scenarios after reset gives repeatable results.
- Docker image builds and runs locally.

### Cloud step
- Service deploys to Cloud Run from the same container image.
- Health and OpenAPI documents are reachable.
- Deployed reset requires the admin token.
- Cloud checks match local expectations except explicitly marked local-only or overridden cases.
- Two sequential scenario runs produce the expected results.

## 11. Decisions still open

Resolve these before or during the first implementation slice:
1. ~~Python version~~ — decided: 3.13.1. Dependency management: `uv` with `pyproject.toml` and a committed `uv.lock` (decided).
2. ~~Repository name~~ — decided: `api-workbench-sandbox`.
3. ~~Fixed credentials~~ — confirmed: `test-token`, `admin-token`, `test-user`/`test-pass`, `test-api-key`.
4. ~~OpenAPI versions~~ — decided: both. `ok` stays 3.0.3; a small 3.1 variant (`specs/ok-3.1.yaml`, served at `/ok/openapi-3.1.yaml`) describes a subset of the same API. It is an additional document of the `ok` family, not a fourth family.
5. ~~Operation target~~ — decided: 60 to 70 operations (65 now); every feature area of the source document is covered at that size.
6. Keep `contract-fail` and `conform-fail` specifications separate (current proposal).
7. ~~Expectations location and sync~~ — decided: `expectations/<family>.yaml` with catalog check IDs; the nightly CI leg against `api-workbench@main` catches drift.
8. Public versus private Cloud Run access.
9. Cloud project, region, and custom domain.
10. Which transport edge cases remain local-only.

## 12. Source-of-truth references

- ClearSignal check catalog: `apps/desktop/wails/help/what-we-check.md` in the api-workbench repository.
- Related planning document: `docs/planning/failure-showcase-repo.md`.
- Backlog: `docs/planning/backlog.md`.
- Original project notes: `docs/from-main/api-workbench-sandbox-project.md` (copy of the source notes).
