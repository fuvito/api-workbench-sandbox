# CLAUDE.md — ClearSignal Test Targets

## Project purpose

This repository contains a deliberately designed set of REST API test targets used to test ClearSignal's API Contract Validation and Spec Conformance Testing.

It is a test fixture, not a production API and not a general-purpose mock-server product.

Read `docs/PRD.md` and `docs/TASKLIST.md` before making substantial changes. The original design notes are `docs/from-main/api-workbench-sandbox-project.md`.

## Product invariants

1. One repository, one program, one process, one listening port.
2. Serve three API families under distinct path prefixes:
   - `/ok`
   - `/contract-fail`
   - `/conform-fail`
3. Each family serves its own OpenAPI document at `<prefix>/openapi.yaml`.
4. Each family exposes `GET <prefix>/health`.
5. Each family has an independent in-memory store and `POST <prefix>/__admin/reset`.
6. OpenAPI specifications are hand-written and are the source of truth.
7. The `ok` API must conform exactly. The other families deliberately deviate only in documented ways.
8. No database, external service, authentication provider, migrations, or real business domain.
9. Runtime data is in memory and is intentionally lost on process restart or instance replacement.
10. Local behavior is the primary baseline; Cloud Run is a later deployment target.

## ClearSignal problems are not worked around here

- Never shape specs, fixtures, environments or handlers to dodge a `clrsig` bug or limitation. ClearSignal must handle valid OpenAPI and valid servers.
- When `clrsig` behaves wrongly, stop, tell the user, and record it in `docs/clrsig-findings.md` (checklist; close when a fixed release is verified).

## Verifying response behavior with ClearSignal

- Expectations are written for `clrsig` v0.13.0 (pinned in CI). `clrsig` v0.7.1 and earlier skip response validation for specs with `servers` (F-010); never claim "conform passes" from a run with such a version. With a spec that has `servers`, `-b` is the family base (`http://localhost:8080/ok`) and `--paths` takes the spec's own paths.
- Timing expectations are verified against the Docker container, not a Windows host (delays overshoot there). Entries marked `local_only` are transport behavior not verified on Cloud Run.
- Expected outcomes of failure cases live in `expectations/*.yaml` and are checked by `scripts/check_expectations.py`. Change an expectation only when ClearSignal's behavior changed, never to match a handler you edited.

## Before coding

- Inspect the existing repository structure and current implementation.
- Read the relevant PRD and task-list phase.
- Identify the smallest vertical slice that can be completed and tested.
- The implementation decision is **Python + FastAPI**, served by Uvicorn. Do not switch to Go, Express, or another framework without an explicit product decision.
- Check actual `clrsig --help` output before relying on CLI flags. Names in planning documents may need confirmation.
- Check `apps/desktop/wails/help/what-we-check.md` in the api-workbench repository when implementing or changing expected check IDs. Do not invent check IDs.

## Implementation approach

- Implement incrementally. Get one API health endpoint, one served spec, one reset route, and one ClearSignal check working before expanding.
- Do not write all OpenAPI specifications before a working server exists.
- Keep the application as a modular monolith; do not introduce workspaces, multiple deployable services, or a plugin architecture.
- Keep handlers, stores, configuration, fault behaviors, and spec-serving responsibilities separated enough to test, without overengineering.
- Prefer a small dependency set. The expected core stack is Python, FastAPI, Uvicorn, and Pydantic.
- Use pytest and httpx for tests; add pytest-asyncio if async test support is needed.
- Use PyYAML only if runtime YAML parsing is required.
- Do not add SQLAlchemy, database drivers, Celery, Redis, PostgreSQL, or other persistence/task-queue infrastructure to the MVP.
- Keep business rules deliberately small and limited to the PRD.
- Do not add tenant management or per-user isolation to the MVP.
- Do not add arbitrary scripting or user-supplied code execution.

## Python and FastAPI conventions

- Use Python 3.13.1 (decided; matches the local `.venv` and the container base image).
- Use `uv` for dependencies (`uv sync`, `uv run pytest`, `uv run python -m app`); commit `pyproject.toml` and `uv.lock`. The repo-local `.venv` is git-ignored.
- The served spec's `servers[0].url` is rewritten to `PUBLIC_BASE_URL`, or to the request's own base URL when it is unset; nothing else in the YAML changes.
- Use FastAPI routers to organize the three API families; keep one application process and one listening port.
- Run through Uvicorn (ASGI).
- Prefer `async def` handlers for request paths that perform asynchronous work.
- Use `await asyncio.sleep(...)` for simulated delays. Never use blocking `time.sleep()` inside an async request handler.
- Protect shared in-memory state with `asyncio.Lock` or an equivalent concurrency-safe design. Keep lock-held sections short; do not hold a store lock while sleeping for injected latency.
- Use Pydantic for internal configuration and typed internal models where helpful. Do not automatically validate every deliberately lenient fixture request with Pydantic; some endpoints must intentionally accept invalid input.
- Keep FastAPI's automatically generated `/openapi.json` separate from the hand-written fixture specs. The checked-in YAML files are the source of truth and must be served at the documented paths.
- Use middleware for cross-cutting concerns (request IDs, logging, admin authentication). Put endpoint-specific failure behavior in route handlers or the fault-injection service.
- Keep dependencies minimal and pin them through the repository's chosen dependency-management convention.

## API and OpenAPI rules

- Keep the three API families separate in routing, specs, stores, and reset behavior.
- A reset of one family must not modify another family's state.
- Serve the exact checked-in OpenAPI document, except for the documented `servers` URL adjustment using `PUBLIC_BASE_URL`.
- Ensure the public spec does not declare the administrative reset route.
- Use deterministic seed IDs and small seed datasets.
- For `ok`, valid requests must match declared status, headers, body, and content type; invalid requests must be rejected as specified.
- For failure cases, make the smallest possible deliberate deviation and document the expected check ID.
- A case should normally break exactly one condition. Multi-problem cases are exceptions and must say which check is expected first.
- Keep `contract-fail` and `conform-fail` separate so their reports do not mix failure categories.
- Use stable operation IDs and descriptive paths. Follow the case naming convention in the PRD.

## State and concurrency

- State is process-local memory only.
- Stores must be safe for concurrent requests (mutex per store or an equivalent concurrency-safe design).
- Do not assume Cloud Run session affinity guarantees that a request reaches the same instance.
- Cloud Run must initially use `max-instances=1`, but this is an operational limit, not durable persistence or a guarantee against instance replacement.
- Scenarios must explicitly reset before relying on seed state.
- Document that simultaneous users share state in the MVP and can interfere with one another.
- Keep expiration, counters, rate-limit windows, drift, and degrading-latency state bounded and resettable.

## Configuration and portability

Read runtime configuration from environment variables:
- `PORT` (default `8080`)
- `HOST` (local default `127.0.0.1`; container sets `0.0.0.0`)
- `PUBLIC_BASE_URL` (optional)
- `DRIFT` (default `0`)
- `ADMIN_TOKEN` (optional locally; mandatory when deployed)
- `LATENCY_SCALE` (optional, 0 to 10, default 1)

Use one port and path prefixes so local and Cloud Run behavior share the same routing model.

Do not hard-code deployment URLs, credentials, ports, or secrets.

## Security and resource safety

- Use only documented fake test credentials. Never add real secrets or real user data.
- When `ADMIN_TOKEN` is set, require `Authorization: Bearer <ADMIN_TOKEN>` for reset and optional state-inspection routes.
- Always configure the admin token in deployed environments and source it from Secret Manager.
- Bound request body sizes, response sizes, latency parameters, `/large` output, and slow/hanging concurrency.
- Do not perform outbound HTTP requests based on caller input.
- Do not implement an open proxy, open redirect, or arbitrary URL fetcher.
- Redirect-loop fixtures may redirect only to themselves.
- Keep intentionally slow or hanging behaviors bounded and documented because they consume instance capacity and may incur hosting cost.

## Observability and process behavior

- Log one structured line per request to stdout with method, path, status, duration, and API family/prefix.
- Do not log authorization tokens or other secrets.
- Handle SIGTERM gracefully and allow in-flight requests to finish within the shutdown grace period.
- Do not write runtime state to the container filesystem.
- Keep startup fast and the image small.
- Provide a reliable readiness endpoint.

## Latency and failure injection

- Keep fault behavior explicit and deterministic where possible.
- Support a fixed delay, bounded variable delay, flaky counters, rate-limit counters, unavailable-then-OK, drift, and degrading latency as described in the PRD.
- Apply `LATENCY_SCALE` consistently to deliberate delays.
- Make reset restore counters and behavior state where the case expects reset semantics.
- Do not make the normal `ok` API randomly fail.
- Distinguish local-only transport behaviors from cloud-supported behaviors in expectations.
- Do not claim a Cloud Run transport edge case works until verified against the deployed service.

## Python test expectations

- Use pytest for unit and integration tests and httpx for ASGI/client requests.
- Test async handlers and shared-state behavior, including concurrent access.
- Test that injected latency uses non-blocking async waits.
- Keep test fixtures isolated; reset in-memory stores between tests.
- Do not rely on tests passing merely because FastAPI generated a matching OpenAPI schema; compare responses against the checked-in YAML fixtures through ClearSignal.

## Tests and CI

For each implemented case:
1. Add or update the OpenAPI operation.
2. Implement the server behavior.
3. Add or update the ClearSignal scenario/environment.
4. Record expected exit code and expected check ID(s).
5. Add it to the expectations runner.
6. Verify it locally.

CI must start the server, poll `/health`, run the checks, and compare actual outcomes to expected outcomes. A case that unexpectedly passes, fails with another ID, or changes exit code must fail CI.

Test:
- Reset restores deterministic seed data.
- Reset for one API does not affect other APIs.
- Multiple requests in a scenario share state.
- Concurrent store access is race-safe.
- OpenAPI server URLs are correct locally and when `PUBLIC_BASE_URL` is set.
- Admin routes reject missing/incorrect token when configured.
- Input and delay caps are enforced.

## Cloud Run constraints

- Build one container image and use it locally and in Cloud Run.
- Listen on the `PORT` environment variable.
- Bind to `0.0.0.0` in the container.
- Start with `max-instances=1`.
- Use a sensible concurrency limit and request timeout.
- Store `ADMIN_TOKEN` in Secret Manager.
- Set `PUBLIC_BASE_URL` to the deployed service URL.
- Expect scale-to-zero, replacement, or restart to erase in-memory state.
- Do not rely on background timers or background CPU for async-job simulation; compute progression from timestamps/poll counts on requests.
- Mark transport-sensitive cases local-only or add cloud-specific expected results after real verification.
- Configure budget alerts before public exposure.

## Documentation expectations

Keep README instructions accurate and concise:
- How to run locally.
- How to run in Docker.
- API base paths and spec URLs.
- Health and reset endpoints.
- Test credentials.
- How to run ClearSignal commands/scenarios.
- Expected outcomes.
- Known gaps and local-only cases.
- Cloud Run deployment and security notes when implemented.

At the end of each phase, add a KT note under `docs/kts/` and update its index.

Update `docs/TASKLIST.md` as work is completed. Do not mark tasks complete without running the relevant checks.

## Change discipline

- Avoid unrelated refactors.
- Do not silently change the intended check ID for a fixture.
- Do not change a spec to make an implementation bug disappear; investigate whether the spec or handler is wrong.
- If the PRD, source notes, check catalog, and current code disagree, report the conflict and ask for a decision rather than silently choosing.
- For new scope, explain why it is necessary and update PRD/task list before implementing.
- At the end of a task, report files changed, tests run, results, and remaining decisions.
