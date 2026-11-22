# conform-fail: expected outcomes (response cases and commands; probes are in the expectations file)

Generated from `expectations/conform-fail.yaml` by `uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml --table`; do not edit by hand. Outcomes are for `clrsig` v0.7.1 and assume the F-010 spec copy (see `docs/clrsig-findings.md`). A case that "passes" is a control, a known gap, or a "not checked" outcome pinned on purpose.

| Case | Path (under `/conform-fail`) | Expected | Check | Exit code | ClearSignal reports (or why it passes) |
|---|---|---|---|---|---|
| `ghost` | `/ghost` | fails | CS-RESP-001 | 1 | answered 404, but the spec declares only 200 |
| `orphan` | `/orphan` | fails | CS-RESP-001 | 1 | answered 405, but the spec declares only 204 |
| `wrong-method` | `/wrong-method` | fails | CS-RESP-001 | 1 | answered 405, but the spec declares only 200 |
| `path-param-type` | `/path-param/{id}` | fails | CS-RESP-001 | 1 | answered 400, but the spec declares only 200 |
| `requires-extra-header` | `/requires-extra-header` | fails | CS-RESP-001 | 1 | answered 400, but the spec declares only 201 |
| `form-body` | `/form` | fails | CS-REQ-002 | 1 | request body does not fit the spec: value is required but missing |
| `multipart-body` | `/multipart` | fails | CS-REQ-002 | 1 | request body does not fit the spec: value is required but missing |
| `subscribe-with-callback` | `/subscribe` | passes | CS-GAP-010 | 0 | the callback is not exercised and the server never contacts it |
| `requests-param-type-ok` | `/requests/param-type/{itemId}` | passes | none | 0 | itemId=7 from the right environment: a valid request, a correct response |
| `requests-body-value-ok` | `/requests/body-value` | passes | none | 0 | amount=19.99 from the right environment |

### Commands (wrong environments, scenarios that cannot run, unreadable specs)

| Run | Check | Exit code | ClearSignal reports |
|---|---|---|---|
| `req-001-wrong-parameter-type` | CS-REQ-001 | 1 | path parameter "itemId" does not fit the spec: value abc |
| `req-002-wrong-body-value` | CS-REQ-002 | 1 | request body does not fit the spec: invalid character (the body message is the JSON parser's text (F-017)) |
| `run-001-missing-placeholder` | CS-RUN-001 | 1 | not sent: no value for \{\{itemId\}\} |
| `run-002-bad-dynamic-function-in-environment` | CS-RUN-002 | 1 | unknown function \$noSuchFunction |
| `run-002b-bad-dynamic-function-in-scenario` | CS-RUN-002 | 2 | unknown function \$noSuchFunction (in a scenario the whole run aborts with exit 2 before any step (F-016)) |
| `run-003-server-down-wrong-base-url` | CS-RUN-003 | 1 | executing request |
| `run-004a-unreadable-yaml` | CS-RUN-004 | 2 | parsing spec: loading spec: failed to unmarshal data |
| `run-004b-not-an-openapi-document` | CS-RUN-004 | 2 | invalid OpenAPI spec: value of openapi must be a non-empty string |
| `run-004c-spec-file-missing` | CS-RUN-004 | 2 | reading spec: open  |
| `run-004d-spec-url-returns-404` | CS-RUN-004 | 2 | server returned 404 |
| `run-005-unset-environment-variable` | CS-RUN-005 | 0 | environment variable CLRSIG_UNSET_FIXTURE_VAR is not set |
