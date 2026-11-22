# conform-fail: expected outcomes (response cases, sequences and commands; probes are in the expectations file)

Generated from `expectations/conform-fail.yaml` by `uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml --table`; do not edit by hand. Outcomes are for `clrsig` v0.8.3 against the standard specs. A case that "passes" is a control, a known gap, or a "not checked" outcome pinned on purpose. Timing outcomes were verified against the Docker container.

| Case | Path (under `/conform-fail`) | Expected | Check | Exit code | ClearSignal reports (or why it passes) |
|---|---|---|---|---|---|
| `ghost` | `/ghost` | fails | CS-RESP-001 | 1 | answered 404, but the spec declares only 200 |
| `orphan` | `/orphan` | fails | CS-RESP-001 | 1 | answered 405, but the spec declares only 204 |
| `wrong-method` | `/wrong-method` | fails | CS-RESP-001 | 1 | answered 405, but the spec declares only 200 |
| `path-param-type` | `/path-param/{id}` | fails | CS-RESP-001 | 1 | answered 400, but the spec declares only 200 |
| `requires-extra-header` | `/requires-extra-header` | fails | CS-RESP-001 | 1 | answered 400, but the spec declares only 201 |
| `form-body` | `/form` | passes | CS-REQ-003 | 0 | the form fields are generated from the schema |
| `multipart-body` | `/multipart` | passes | CS-REQ-003 | 0 | the multipart parts are generated from the schema |
| `subscribe-with-callback` | `/subscribe` | passes | CS-GAP-010 | 0 | the callback is not exercised and the server never contacts it |
| `requests-param-type-ok` | `/requests/param-type/{itemId}` | passes | none | 0 | itemId=7 from the right environment: a valid request, a correct response |
| `requests-body-value-ok` | `/requests/body-value` | passes | none | 0 | amount=19.99 from the right environment |
| `slow` | `/slow` | fails | CS-RUN-003 | 1 | context deadline exceeded (with --request-timeout 1500) |
| `latency-within-timeout` | `/latency/{ms}` | passes | none | 0 | 200 ms answered correctly, and within the default timeout (no response-time limit given) |
| `latency-within-limit` | `/latency/{ms}` | passes | CS-RESP-014 | 0 | 200 ms against a 1000 ms limit (with --max-response-time 1000) |
| `latency-over-limit` | `/latency/{ms}` | fails | CS-RESP-014 | 1 | slower than the 50 ms limit (with --max-response-time 50) |
| `unavailable` | `/unavailable` | fails | CS-RESP-001 | 1 | answered 503, but the spec declares only 200 |
| `redirect-loop` | `/redirect-loop` | fails | CS-RUN-003 | 1 | stopped after 10 redirects |
| `hang` | `/timeout/hang` | fails | CS-RUN-003 | 1 | context deadline exceeded (with --request-timeout 1500) (local only) |
| `slow-headers-outlasts-timeout` | `/timeout/slow-headers` | fails | CS-RUN-003 | 1 | executing request.*context deadline exceeded (with --request-timeout 1500) (local only) |
| `slow-headers-within-timeout` | `/timeout/slow-headers` | passes | none | 0 | 4 s against the default 10 s timeout, no response-time limit (local only) |
| `slow-headers-over-limit` | `/timeout/slow-headers` | fails | CS-RESP-014 | 1 | slower than the 2000 ms limit (with --max-response-time 2000) (local only) |
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
| `degrading-latency` | `/latency/degrading` | P P P F F | CS-RESP-014 | with --max-response-time 850 |
| `seeded-jitter-repeats` | `/latency/jitter` | P F P P P P | CS-RESP-014 | with --max-response-time 700; repeated 2 times after a reset, identical |

### Commands (wrong environments, scenarios that cannot run, unreadable specs)

| Run | Check | Exit code | ClearSignal reports |
|---|---|---|---|
| `req-001-wrong-parameter-type` | CS-REQ-001 | 1 | path parameter "itemId" does not fit the spec: value abc |
| `req-002-wrong-body-value` | CS-REQ-002 | 1 | request body field "amount" takes its value from \{\{amount\}\}, which is "cheap" |
| `run-001-missing-placeholder` | CS-RUN-001 | 1 | not sent: no value for \{\{itemId\}\} |
| `run-002-bad-dynamic-function-in-environment` | CS-RUN-002 | 1 | unknown function \$noSuchFunction |
| `run-002b-bad-dynamic-function-in-scenario` | CS-RUN-002 | 1 | (?s)unknown function \$noSuchFunction.*PASS\s+good step (since v0.8.3 only that step fails (not sent) and the good step still runs; exit 1 (F-016)) |
| `run-003-server-down-wrong-base-url` | CS-RUN-003 | 1 | executing request |
| `run-004a-unreadable-yaml` | CS-RUN-004 | 2 | parsing spec: loading spec: failed to unmarshal data |
| `run-004b-not-an-openapi-document` | CS-RUN-004 | 2 | invalid OpenAPI spec: value of openapi must be a non-empty string |
| `run-004c-spec-file-missing` | CS-RUN-004 | 2 | reading spec: open  |
| `run-004d-spec-url-returns-404` | CS-RUN-004 | 2 | server returned 404 |
| `slow-outlasts-the-default-timeout` | CS-RUN-003 | 1 | context deadline exceeded (takes about 10 s: the default request timeout) |
| `latency-3s-with-a-1s-timeout` | CS-RUN-003 | 1 | context deadline exceeded |
| `latency-3s-with-a-6s-timeout` | none | 0 |  |
| `large-binary-near-the-cap` | none | 0 |  |
| `large-binary-over-the-cap` | none | 0 |  (51 MB: cut off, still a pass because binary bodies are not compared) |
| `large-json-near-the-cap` | none | 0 |  |
| `large-json-over-the-cap` | CS-RESP-013 | 1 | larger than the 50 MB Clear Signal reads (valid JSON over the 50 MB read limit is reported as too large, not as a syntax error) |
| `run-005-unset-environment-variable` | CS-RUN-005 | 0 | environment variable CLRSIG_UNSET_FIXTURE_VAR is not set |