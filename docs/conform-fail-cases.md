# conform-fail: expected outcomes (response cases, sequences and commands; probes are in the expectations file)

Generated from `expectations/conform-fail.yaml` by `uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml --table`; do not edit by hand. Outcomes are for `clrsig` v0.7.1 and assume the F-010 spec copy (see `docs/clrsig-findings.md`). A case that "passes" is a control, a known gap, or a "not checked" outcome pinned on purpose. Timing outcomes were verified against the Docker container.

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
| `slow` | `/slow` | fails | CS-RUN-003 | 1 | context deadline exceeded (with --request-timeout 1500) |
| `latency-within-timeout` | `/latency/{ms}` | passes | CS-GAP-005 | 0 | 200 ms answered correctly; response time is not measured |
| `unavailable` | `/unavailable` | fails | CS-RESP-001 | 1 | answered 503, but the spec declares only 200 |
| `redirect-loop` | `/redirect-loop` | fails | CS-RUN-003 | 1 | stopped after 10 redirects |
| `hang` | `/timeout/hang` | fails | CS-RUN-003 | 1 | context deadline exceeded (with --request-timeout 1500) (local only) |
| `slow-headers-outlasts-timeout` | `/timeout/slow-headers` | fails | CS-RUN-003 | 1 | executing request.*context deadline exceeded (with --request-timeout 1500) (local only) |
| `slow-headers-within-timeout` | `/timeout/slow-headers` | passes | CS-GAP-005 | 0 | 4 s against the default 10 s timeout (local only) |
| `slow-body` | `/timeout/slow-body` | fails | CS-RUN-003 | 1 | reading response body: context deadline exceeded (with --request-timeout 3000) (local only) |
| `truncated-body` | `/timeout/truncated-body` | fails | CS-RUN-003 | 1 | reading response body: unexpected EOF (local only) |
| `connection-reset` | `/timeout/connection-reset` | fails | CS-RUN-003 | 1 | EOF (local only) |
| `large-1mb` | `/large` | passes | CS-NC-003 | 0 | a binary body is not compared |
| `large-json-1mb` | `/large/json` | passes | none | 0 | a valid 1 MB JSON body |
| `after-write-outlasts-timeout` | `/timeout/after-write` | fails | CS-RUN-003 | 1 | context deadline exceeded (with --request-timeout 1500) (local only) |
| `after-write-records` | `/timeout/after-write/records` | passes | none | 0 | the records written so far |
| `idempotent-create` | `/idempotent` | passes | none | 0 | a single request cannot show the missing idempotency; see the scenario |
| `idempotent-records` | `/idempotent/records` | passes | none | 0 | the records created so far |
| `lost-update` | `/lost-update` | passes | none | 0 | GET and PUT each conform; the lost update shows only in a scenario |
| `drift-report-at-drift-0` | `/drift/report` | passes | none | 0 | the default drift level: total is an integer; at drift 1 it becomes a string (see the drift section) |
| `rules-stock` | `/rules/stock` | passes | none | 0 | a correct response; the rule is broken elsewhere |
| `rules-create-order` | `/rules/orders` | passes | none | 0 | quantity 1 is within the stock; the response matches the spec |
| `rules-ship-order` | `/rules/orders/{orderId}/ship` | passes | none | 0 | 200 or the declared 409, whichever state o-1 is in |
| `rules-cancel-order` | `/rules/orders/{orderId}/cancel` | passes | none | 0 | 200 (also for a shipped order, the broken rule) or the declared 409 |
| `rules-create-customer` | `/rules/customers` | passes | none | 0 | the first customer; the duplicate is only visible in a scenario |
| `rules-items` | `/rules/items` | passes | none | 0 | a valid page; the repeat only shows across two pages |
| `rules-protected-token-not-known` | `/rules/protected` | passes | none | 0 | ClearSignal's test-token is unknown here: the declared 401 |
| `rules-withdraw-insufficient-funds` | `/rules/withdrawals` | fails | CS-RESP-005 | 1 | property "id" is missing |

### Sequences (reset first, then call by call)

| Sequence | Path | Outcomes (P = pass, F = fail) | Check on failure | Notes |
|---|---|---|---|---|
| `flaky-every-third-call` | `/flaky` | P P F P P F | CS-RESP-001 |  |
| `rate-limited-after-three-calls` | `/rate-limited` | P P P F F F | CS-RESP-001 |  |
| `unavailable-then-ok` | `/unavailable-then-ok` | F F P P | CS-RESP-001 |  |
| `degrading-latency` | `/latency/degrading` | P P P F F | CS-RUN-003 | with --request-timeout 850 |
| `seeded-jitter-repeats` | `/latency/jitter` | P F P P P P | CS-RUN-003 | with --request-timeout 700; repeated 2 times after a reset, identical |

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
| `slow-outlasts-the-default-timeout` | CS-RUN-003 | 1 | context deadline exceeded (takes about 10 s: the default request timeout) |
| `latency-3s-with-a-1s-timeout` | CS-RUN-003 | 1 | context deadline exceeded |
| `latency-3s-with-a-6s-timeout` | none | 0 |  |
| `large-binary-near-the-cap` | none | 0 |  |
| `large-binary-over-the-cap` | none | 0 |  (51 MB: silently truncated, still a pass because binary bodies are not compared (F-019)) |
| `large-json-near-the-cap` | none | 0 |  |
| `large-json-over-the-cap` | CS-RESP-008 | 1 | unexpected EOF (valid JSON cut at 50 MB is reported as unexpected EOF: a false failure (F-019)) |
| `run-005-unset-environment-variable` | CS-RUN-005 | 0 | environment variable CLRSIG_UNSET_FIXTURE_VAR is not set |
