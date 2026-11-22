# KT — Phase 4b: the spec and the server disagree

Second slice of `conform-fail`: instead of wrong responses (contract-fail) or too-lenient validation (4a), the server and the spec disagree about **what exists**. `specs/conform-fail.yaml` goes from 15 to 23 operations.

## The cases

| Operation | The spec says | The server does | ClearSignal result |
|---|---|---|---|
| `GET /ghost` | declared, 200 | no route: 404 | fails CS-RESP-001 (404 undeclared) |
| `DELETE /orphan` | declared, 204 | implements only `POST /orphan`: 405 | fails CS-RESP-001 (405 undeclared) |
| `PATCH /wrong-method` | declared, 200 | implements only `PUT`: 405 | fails CS-RESP-001 |
| `GET /path-param/{id}` | `id` is an integer | accepts only UUIDs: 400 | fails CS-RESP-001 (400 undeclared) |
| `POST /requires-extra-header` | no header, 201 only | needs `X-Tenant`: 400 without it | fails CS-RESP-001 |
| `GET /undocumented` | not described | exists | not exercised by `conform`; a scenario step on it is not compared (CS-NC-001) |
| `POST /form`, `POST /multipart` | required form / multipart body, 201 and 400 | handles real forms correctly | **fails** CS-REQ-002 today (F-015): ClearSignal sends no body (CS-GAP-006) |
| `POST /subscribe` | JSON body, plus a callback outside `paths` | validates the URL, never contacts it | passes; the callback is not exercised (CS-GAP-010) |

The 404 and 405 answers come from the framework on purpose: they are what a real server without that route or method says. `UNDOCUMENTED_OPERATIONS` in `app/conform_fail/disagree.py` lists the routes the server has that the spec does not (`PUT /wrong-method`, `POST /orphan`, `GET /undocumented`); a test asserts none of them is in the spec.

## The surprising one: form and multipart (F-015)

The source notes expected these to "pin CS-GAP-006" (bodies are generated without a body). What actually happens is worse: ClearSignal builds the request with no body, validates its own request against the spec (the body is `required: true`), and reports the operation as FAILED ("the request body does not fit the spec: value is required but missing", suggesting a fix through the environment that cannot work). A correct server and a correct spec fail through no fault of theirs.

- The spec keeps `required: true`, which is the right declaration. Making it optional would be shaping the fixture around ClearSignal.
- The server really does handle both forms (tests post real `data=` and `files=` requests and get 201, and reject every wrong variant).
- `expectations/conform-fail.yaml` records today's behavior: fail, kind `request`, check CS-REQ-002 (the closest catalog ID), noted as a consequence of CS-GAP-006. A new `generation` section pins the gap itself by reading what `clrsig generate` writes (no `body` for `formBody` and `multipartBody`, a body for the JSON controls).

## The callback (CS-GAP-010)

OpenAPI 3.0 has `callbacks` inside an operation (3.1 also has top-level `webhooks`; the spec is 3.0.3, so webhooks are not covered). `clrsig generate` writes 23 requests for 23 operations under `paths` and none for `onEventCallback`. The server never contacts `callbackUrl`: it only checks the URL's shape. A test blocks `socket.connect` and posts URLs such as `http://169.254.169.254/latest` to prove no outbound call happens (the project rule: no caller-controlled outbound requests).

## Runner changes

- Request-side problems (`requestViolations`) are now compared as well as response violations.
- Path parameters: ClearSignal writes `{{id}}` while the spec has `{id}`; the runner filters on the part before the first parameter and normalizes the rest.
- `generation` section: pins what `clrsig generate` builds (operation count, bodiless operations, operations that must carry a body, operations that must not be generated). A fix to CS-GAP-006 or CS-GAP-010 flips these and demands a review.
- Case tables for both families are generated (`docs/conform-fail-cases.md`, `docs/contract-fail-cases.md`).

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 511 passed (13 new).
- Runner, conform-fail: 8 response cases as expected, whole spec 7 of 23 operations fail (exactly the five CS-RESP-001 cases and the two form cases), 3 scenario steps, request generation, 30 probes over 16 operations.
- Drift check: a copy with a wrong message, a wrong operation count, a wrong "has a body" claim, a wrong scenario state and a passing case claimed to fail produced five mismatches and exit 1.

## ClearSignal findings raised

- **F-015**: operations with a form or multipart body fail in `conform` although server and spec agree.
- Observations that are not bugs: a negative probe on `PATCH /wrong-method` passes because 405 is a 4xx (the catalog says any 4xx passes); and, as in contract-fail, a scenario step on an undocumented route shows nothing special in any report.

## Watch-outs

- The two form cases fail in the whole-spec run, so the plain `conform` exit code for conform-fail is 1 for a reason that is ClearSignal's, not the server's (F-015). When it is fixed those two cases flip to pass and the expectations change with it.
- `/path-param/{id}` depends on the environment value `id: "1"` (a valid integer) in `clrsig/environments/conform-fail.yaml`.
- Slices 3 to 5 remain: request and run failures, timing and instability, drift and business-rule failures.
