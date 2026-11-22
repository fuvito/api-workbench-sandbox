# conform-fail: expected outcomes (response cases, sequences and commands; probes are in the expectations file)

Generated from `expectations/conform-fail.yaml` by `uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml --table`; do not edit by hand. Outcomes are for `clrsig` v0.8.5 against the standard specs. A case that "passes" is a control, a known gap, or a "not checked" outcome pinned on purpose. Timing outcomes were verified against the Docker container.

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
| `hostile-deep-nesting` | `/hostile/deep-nesting` | passes | none | 0 | JSON nested 200 levels deep |
| `hostile-wide-object` | `/hostile/wide-object` | passes | none | 0 | an object with 20000 keys |
| `hostile-unicode` | `/hostile/unicode` | passes | none | 0 | accents, Hebrew, an emoji, an escaped surrogate pair and an escaped NUL |
| `hostile-integer-as-float` | `/hostile/integer-as-float` | passes | none | 0 | id is 1.0: an integer in JSON Schema |
| `hostile-integer-exponent` | `/hostile/integer-exponent` | passes | none | 0 | id is 1e2: an integer in JSON Schema |
| `hostile-big-integer` | `/hostile/big-integer` | passes | none | 0 | id is one above int64: still an integer for an unbounded schema |
| `hostile-negative-zero` | `/hostile/negative-zero` | passes | none | 0 | id is -0 |
| `hostile-gzip` | `/hostile/gzip` | passes | none | 0 | a valid gzip body with Content-Encoding gzip is decoded |
| `hostile-duplicate-headers` | `/hostile/duplicate-headers` | passes | none | 0 | the same header twice and two Set-Cookie headers |
| `hostile-big-header` | `/hostile/big-header` | passes | none | 0 | a 60000-byte response header |
| `hostile-chunked-stream` | `/hostile/chunked-stream` | passes | none | 0 | no Content-Length: three chunks |
| `hostile-lone-surrogate` | `/hostile/lone-surrogate` | passes | none | 0 | an unpaired surrogate escape is valid JSON text; ClearSignal does not check that it is valid Unicode (undefined by the standard) |
| `hostile-invalid-utf8` | `/hostile/invalid-utf8` | fails | CS-RESP-008 | 1 | not valid JSON \(byte 0xff at offset 20 is not UTF-8\) |
| `hostile-trailing-garbage` | `/hostile/trailing-garbage` | fails | CS-RESP-008 | 1 | not valid JSON \(text after the JSON value\) |
| `hostile-raw-newline-in-string` | `/hostile/raw-newline-in-string` | fails | CS-RESP-008 | 1 | not valid JSON \(invalid character .\\n. in string literal |
| `hostile-nan-literal` | `/hostile/nan-literal` | fails | CS-RESP-008 | 1 | not valid JSON \(invalid character 'N' |
| `hostile-bom` | `/hostile/bom` | fails | CS-RESP-008 | 1 | not valid JSON \(invalid character |
| `hostile-duplicate-keys` | `/hostile/duplicate-keys` | fails | CS-RESP-006 | 1 | value must be an integer |
| `hostile-gzip-lie` | `/hostile/gzip-lie` | fails | CS-RUN-003 | 1 | reading response body: unexpected EOF |
| `hostile-float-overflow` | `/hostile/float-overflow` | fails | CS-RESP-015 | 1 | ParseFloat: parsing "1e400": value out of range |

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
| `run-002b-bad-dynamic-function-in-scenario` | CS-RUN-007 | 1 | (?s)unknown function \$noSuchFunction.*PASS\s+good step (since v0.8.3 only that step fails (not sent) and the good step still runs; exit 1 (F-016)) |
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
| `run-007-bad-function-in-a-scenario-variable` | CS-RUN-007 | 2 | variable "broken".*unknown function \$noSuchFunction |
| `run-001b-missing-value-in-a-scenario` | CS-RUN-001 | 1 | (?s)FAIL\s+missing value\s+error: not sent: no value for \{\{nothing\}\}.*PASS\s+good step |
| `nc-004-validate-spec-off` | none | 1 | (?s)PASS\s+validation off\s+404.*FAIL\s+ghost checked.*declares only 200.*spec validation is turned off for this step: 1 |
| `nc-006-step-did-not-complete` | none | 1 | the step did not complete: 1 |
| `nc-005-no-spec` | none | 1 | (?s)PASS\s+ghost checked\s+404 (without --spec the same /ghost step passes and no 'Spec:' summary line is printed) |
| `probe-005-paths-limit-the-probes` | none | 0 | PASSED\s+2 probes |
| `probe-005-json-report-has-the-probes` | none | 0 | "kind": "drop_required_field" |
| `probe-005-junit-report-has-the-probes` | none | 0 | missing required field (&#39;/')name |
| `hostile-spec-circular-ref` | none | 0 | 2 request\(s\) generated (a schema that contains itself (parent, children): both operations are generated) |
| `hostile-spec-recursive-allof` | none | 0 | 1 request\(s\) generated (allOf of a base and a schema that refers back to itself) |
| `hostile-spec-discriminator-probes-both-branches` | none | 1 | (?s)missing required field .kind. of branch 1.*missing required field .bark. of branch 2.*wrong type for field .bark. of branch 2 (oneOf with a discriminator and a mapping: probes for both branches (4 each)) |
| `hostile-spec-many-branches` | none | 1 | (?s)missing required field .f59. of branch 60 (oneOf with 60 branches: 120 probes, quickly) |
| `hostile-spec-unsatisfiable-schema` | none | 0 | 1 request\(s\) generated (allOf of a string and an integer can never be satisfied: a request is still generated, nothing hangs) |
| `hostile-spec-deep-schema` | none | 0 | 1 request\(s\) generated (a request body schema nested 120 levels) |
| `hostile-spec-path-templates` | none | 0 | 3 request\(s\) generated (two parameters and a dot, a trailing slash, a non-ASCII path) |
| `hostile-spec-no-paths` | none | 0 | 0 request\(s\) generated |
| `hostile-spec-json-file` | none | 0 | 1 request\(s\) generated (the spec is a JSON document) |
| `hostile-spec-openapi-3-2` | none | 0 | 1 request\(s\) generated (openapi 3.2.0 is newer than the catalog; it loads like 3.1) |
| `hostile-spec-missing-ref` | none | 2 | failed to resolve "components".*#/components/schemas/Nope (a $ref to a schema that does not exist: a clean error, exit 2) |
| `hostile-spec-xml-example` | none | 2 | invalid example: value must be an object (a valid XML example string is rejected as 'value must be an object' (F-034)) |
| `hostile-spec-duplicate-operation-id` | none | 2 | have the same operation id "same" |
| `hostile-spec-undeclared-path-parameter` | none | 2 | must define exactly all path parameters \(missing: \[id\]\) |
| `hostile-spec-identical-diff` | none | 0 | No changes (diff of a recursive spec with itself: no changes, no loop) |
| `failed-extraction-fails-the-run` | none | 1 | (?s)FAIL\s+extract nothing.*FAILED\s+0 passed, 1 failed (the only problem is an extraction that finds nothing: since v0.8.5 the run exits 1 and says FAILED (it exited 0, F-032)) |
| `probe-summary-says-failed-when-all-errored` | none | 1 | (?s)FAILED\s+2 probes\s+·\s+0 passed\s+·\s+0 failed\s+·\s+0 skipped\s+·\s+2 errors.*could not be judged (no server: every probe errors; since v0.8.5 the headline says FAILED, as the exit code does (F-029)) |
| `scale-500-generate` | none | 0 | 500 request\(s\) generated |
| `scale-500-diff-with-itself` | none | 0 | No changes |
| `scale-500-conform-negative` | none | 1 | FAILED\s+500 operations\s+·\s+0 passed\s+·\s+500 failed (against a closed port, with no values for the path parameters: nothing is sent and the run still finishes) |