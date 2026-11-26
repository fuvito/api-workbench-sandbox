# Contract and conformance testing: the problems, how clrsig finds them, and how to explain them

Written 2026-11-22 for developers, in plain language. Every example is a real fixture in this repository, and the `clrsig` results are for **clrsig v0.13.4**: the expected outcomes in `expectations/*.yaml` were rerun with it on 2026-11-25.

**How this guide is organized**

| Part | What it is |
|---|---|
| [Part 0](#part-0-the-basics-in-five-minutes) | The few ideas you need, and how to run the examples |
| [Part 1](#part-1-the-problems) | **The problems**: what goes wrong, why it hurts, an example (60 problems, P01 to P60) |
| [Part 2](#part-2-how-clrsig-finds-and-helps-solve-them) | **The solutions**: how clrsig finds each problem, what you do about it, and where it cannot help |
| [Part 3](#part-3-notes-for-the-video-explanations-notebooklm) | **Notes and instructions for the videos** (Google NotebookLM) |

Problem numbers (`P01`, `P02`, ...) are the same in Part 1 and Part 2, so you can jump between them.

---

## Part 0: The basics in five minutes

### The words you need

- **OpenAPI spec** (also "the spec", "the contract"): a YAML or JSON file that says what an API does: which URLs exist, what you send, what comes back (status codes, headers, JSON shape). It is a promise from the API to the people who call it.
- **Contract testing**: checking that **what the server really sends back** matches **what the spec promised**. Example: the spec says `id` is a number; the server sends `"id": "abc"`. That is a contract failure. The server and the spec disagree about the response.
- **Conformance testing**: a wider check that **the whole API behaves like its spec says**: the routes exist, the right requests are accepted, bad requests are refused, errors look right, it stays fast enough. The tool sends requests made from the spec and judges the answers.
- **Negative probe**: a request that is *wrong on purpose* (a missing field, a wrong type, no password). A good server must refuse it with a `4xx`. If the server says `200`, it is too lenient.
- **Scenario**: a short script of several requests in a row (log in, create an order, read it back) with checks after each step. Needed when a problem only shows across several calls.
- **Baseline**: a saved list of "known problems", so a run only fails on **new** ones. Useful when you cannot fix everything today.
- **Drift**: the API slowly stops matching its spec, because somebody changed the code and not the spec (or the other way round).

### What clrsig is

`clrsig` (Clear Signal) is a command-line tool. You give it the spec and the address of a running server. It builds requests from the spec, sends them, and checks every answer against the spec. It also compares two versions of a spec, runs scenarios, and reports what was never tested. Each kind of problem has a **check ID** like `CS-RESP-005` (RESP = response, REQ = request, RUN = the run itself, PROBE = negative probe, COV = coverage, DIFF/IMP = spec changes, NC = "not checked", GAP = known limit).

### The practice servers used in all examples

This repository (`api-workbench-sandbox`) runs one small server with three families of endpoints. Each family has its own spec:

| Family | Address prefix | What it is for |
|---|---|---|
| `ok` | `/ok` | Behaves exactly like its spec. The "good" example. (Also `/ok/openapi-3.1.yaml` and `/ok/openapi-features.yaml` for more OpenAPI features.) |
| `contract-fail` | `/contract-fail` | Each endpoint breaks the response contract in **one** way. |
| `conform-fail` | `/conform-fail` | The API behaves wrongly in other ways: missing routes, too lenient, slow, flaky, drifting, odd bodies (`/conform-fail/hostile/*`). |

Start it and run an example:

```
docker build -t api-workbench-sandbox .
docker run --rm -p 8080:8080 api-workbench-sandbox

clrsig conform specs/contract-fail.yaml -b http://localhost:8080/contract-fail \
  --paths /cases/resp-005-missing-required-field
```

Result: `FAIL GET /cases/resp-005-missing-required-field 200` and `property "id" is missing`. Every problem below names its fixture. The full list of expected results is in `docs/contract-fail-cases.md`, `docs/conform-fail-cases.md` and `docs/diff-cases.md`.

### How each problem is written

- **What goes wrong**: the problem in a few sentences.
- **Why it hurts**: what happens to the people or systems using the API.
- **Example**: a real fixture (endpoint, what the server sends, what the spec says).

---

## Part 1: The problems

The problems are grouped by where they come from. **Groups A to C** are about the answers the server sends. **Group D** is about routes that do not match. **Group E** is about the test request itself. **Group F** is about servers that accept too much. **Groups G and H** are about time and state. **Group I** is about change over time. **Group J** is about the spec file. **Groups K and L** are about what a test tool cannot see, and about test tools that give wrong answers.

### Group A: The response does not match the contract

#### P01. The server answers with a status code the spec never listed
- **What goes wrong:** the spec lists the status codes an operation can return (for example `200` and `404`). The server answers `500`, or `503`, or `429`.
- **Why it hurts:** clients are written from the spec. A status nobody planned for is often handled as success or crashes the client.
- **Example:** `GET /contract-fail/cases/resp-001-undeclared-status` answers `500`; the spec declares only `200` and `404`. (If the spec has a `default` response or a range like `2XX`, the status counts as declared: `resp-001b-default-response-ok`.)

#### P02. The `Content-Type` is not the one the spec promised
- **What goes wrong:** the spec says `application/json`; the server sends `text/plain` (often an error page from a proxy or framework).
- **Why it hurts:** a client that parses JSON on a `text/plain` body crashes. A checker that stops at this point never looks at the body at all.
- **Example:** `GET /contract-fail/cases/resp-002-wrong-content-type` sends `Content-Type: text/plain`.

#### P03. A required response header is missing
- **What goes wrong:** the spec marks a response header as required (for example `X-Total-Count`, `Location`, `Retry-After`). The server does not send it.
- **Why it hurts:** pagination, redirects and rate-limit handling depend on those headers.
- **Example:** `GET /contract-fail/cases/resp-003-missing-required-header`: the header `X-Total-Count` is required but not sent.

#### P04. A response header has a value of the wrong type
- **What goes wrong:** the spec says a header is an integer (`X-Total-Count: 3`); the server sends `X-Total-Count: many`.
- **Why it hurts:** the client cannot parse it and a loop or a page counter breaks.
- **Example:** `GET /contract-fail/cases/resp-004-wrong-header-type`.

#### P05. A required field is missing from the body
- **What goes wrong:** the schema lists `id` as required. The JSON has no `id`.
- **Why it hurts:** this is a very common contract break after a refactor. Clients that read `response.id` get `undefined` and fail later, far from the cause.
- **Example:** `GET /contract-fail/cases/resp-005-missing-required-field`: `property "id" is missing`.

#### P06. A field has the wrong type
- **What goes wrong:** the spec says `price` is a number; the server sends `"9.99"` (a string). Or the whole body is an array where the spec says object. Or the mistake is deep inside a nested object.
- **Why it hurts:** a typed client (Java, Go, TypeScript with generated code) fails to read the response, or silently converts the value wrongly.
- **Example:** `resp-006-wrong-field-type` (`value must be a number`), `resp-006b-array-for-object` (`value must be an object`), `resp-nested-wrong-type` (a wrong type inside a nested object).

#### P07. A value breaks a rule in the schema
- **What goes wrong:** the type is right but the value is not allowed: not in the `enum`, below `minimum` or above `maximum`, too short or too long, does not match the `pattern`, too few items, duplicate items in a `uniqueItems` list, `null` where `nullable` is not set, or a bad `date-time`.
- **Why it hurts:** clients validate or switch on these values. A status `"archived"` that is not in the enum falls into a `default:` branch nobody tested.
- **Example:** `resp-007-enum`, `resp-007b-minimum` (`number must be at least 0`), `resp-007f-maximum`, `resp-007c-pattern`, `resp-007c-minlength`, `resp-007c-maxlength`, `resp-007c-minitems`, `resp-007c-uniqueitems`, `resp-007d-null-not-nullable`, `resp-007e-bad-datetime`.

#### P08. The body is not valid JSON, or is empty
- **What goes wrong:** the server says `200` and `Content-Type: application/json` but the body is half a JSON document, an HTML error page, or empty.
- **Why it hurts:** every JSON parser throws. This happens when an upstream crash writes a partial answer, or a proxy injects its own page.
- **Example:** `resp-008-invalid-json` (`the response body is not valid JSON`), `resp-008b-empty-body` (`the response body is empty`).

#### P09. A body that can have several shapes fits none of them
- **What goes wrong:** the spec uses `oneOf` or `anyOf` (for example a `Cat` or a `Dog`, told apart by a `kind` field). The body matches neither, or matches more than one.
- **Why it hurts:** the client picks a branch by the `kind` field and then reads fields that are not there.
- **Example:** `resp-009-oneof-no-match` and `resp-poly-discriminator-wrong`: `matches none of the 2 shapes`.

#### P10. The body has a field the spec does not know
- **What goes wrong:** the schema is *closed* (`additionalProperties: false`) and the body has an extra field.
- **Why it hurts:** strict clients reject the whole response. Extra fields also often mean an internal field leaked.
- **Example:** `resp-010-extra-property-closed`: `property "extra" is unsupported`. Note: on an **open** schema (the OpenAPI default) an extra field is legal and is *not* a problem: `resp-010b-extra-property-open`.

#### P11. A secret field appears in a response
- **What goes wrong:** the spec marks `password` as `writeOnly` (you may send it, it must never come back). The response contains it.
- **Why it hurts:** a data leak. It is easy to miss in code review because the code "just returns the user object".
- **Example:** `GET /contract-fail/cases/resp-011-writeonly-leak`: `writeOnly property "password" in response`.

#### P12. Several things are wrong in the same response
- **What goes wrong:** one response has a header problem and a body problem. Many validators report only the first one.
- **Why it hurts:** you fix one, run again, find the next. It takes many rounds.
- **Example:** `resp-multi-problem`: both a missing header and a bad body; clrsig reports the header first (`header "X-Total-Count" is required`).

### Group B: Odd but valid answers (a test tool must not complain)

A good checker must accept everything that is correct, even when it looks strange. A false alarm wastes time and teaches the team to ignore failures.

#### P13. Valid JSON that looks unusual
- **What goes wrong:** nothing is wrong with the server. The JSON is just unusual: nested 200 levels, an object with 20,000 keys, accents and emoji, a number written `1.0` or `1e2` where the schema says `integer` (valid in JSON Schema), `-0`, or an integer larger than 64 bits.
- **Why it hurts:** a checker that fails these gives false alarms, or crashes.
- **Example:** `/conform-fail/hostile/deep-nesting`, `wide-object`, `unicode`, `integer-as-float`, `integer-exponent`, `big-integer`, `negative-zero`. All must pass.

#### P14. Compressed, chunked and header-heavy answers
- **What goes wrong:** nothing. The server compresses with gzip, sends the body in chunks without `Content-Length`, repeats a header or sends two `Set-Cookie` headers, or sends a 60,000-byte header.
- **Why it hurts:** a checker that cannot decode gzip or handle chunks reports a good server as broken.
- **Example:** `/conform-fail/hostile/gzip`, `chunked-stream`, `duplicate-headers`, `big-header`. All must pass.

#### P15. Bodies that are not JSON
- **What goes wrong:** the spec declares `application/xml`, `text/csv`, an image or a binary download. A JSON checker has nothing to compare.
- **Why it hurts:** two bad outcomes: the tool fails a good response (false alarm), or it quietly checks nothing and you think the body is verified.
- **Example:** `resp-012-xml-valid` (XML), `nc-octet-stream` (binary), `/ok/features/report.csv` (CSV), `/conform-fail/large` (a 1 MB binary file). clrsig does not compare these bodies; it still checks status, headers and `Content-Type`.

### Group C: Broken bodies and broken connections

#### P16. Malformed JSON that different parsers treat differently
- **What goes wrong:** the body is not strictly valid JSON, in a way that some parsers accept and some reject: a UTF-8 byte-order mark (BOM) at the start, bytes that are not valid UTF-8, text after the closing brace, `NaN`, a raw line break inside a string, the same key twice, a number too large for a 64-bit float (`1e400`), or a lone surrogate escape.
- **Why it hurts:** the same response works in your tests and fails in a customer's client written in another language.
- **Example:** `/conform-fail/hostile/bom`, `invalid-utf8`, `trailing-garbage`, `nan-literal`, `raw-newline-in-string`, `duplicate-keys` (`{"id":1,"id":"two"}`), `float-overflow`, `lone-surrogate`.

#### P17. The body is cut off, or the connection drops
- **What goes wrong:** the server announces a body length and sends less (`Content-Length` says 1000, 100 bytes arrive), or resets the TCP connection, or says `Content-Encoding: gzip` and sends plain text.
- **Why it hurts:** the client sees an I/O error, not a response. A retry may repeat a write that already happened.
- **Example:** `/conform-fail/timeout/truncated-body`, `/conform-fail/timeout/connection-reset`, `/conform-fail/hostile/gzip-lie`.

#### P18. A response so large the tool cannot read it all
- **What goes wrong:** a valid JSON body of 51 MB. Tools have a read limit (clrsig reads 50 MB). A tool that silently cuts the body then reports "invalid JSON" blames the server for a tool limit.
- **Why it hurts:** a confusing failure message sends you to debug the wrong thing.
- **Example:** `GET /conform-fail/large/json?mb=51` (with the over-the-cap environment). Under the cap (49 MB) it passes.

#### P19. A redirect that never ends
- **What goes wrong:** `/redirect-loop` answers `302` to itself. A client follows 10, 20, 1000 times.
- **Why it hurts:** hangs a client, or an automatic retry hammers the server.
- **Example:** `GET /conform-fail/redirect-loop`: `stopped after 10 redirects`.

### Group D: The spec and the server disagree about what exists

#### P20. A documented route does not exist
- **What goes wrong:** the spec describes `GET /ghost`. The server has no such route (`404`).
- **Why it hurts:** client code generated from the spec calls an endpoint that never worked. Often left over from a removed feature.
- **Example:** `GET /conform-fail/ghost`: `answered 404, but the spec declares only 200`.

#### P21. The route exists but not for that HTTP method
- **What goes wrong:** the spec says `DELETE /orphan`; the server implements only `POST /orphan` (answers `405`). Or the spec says `PATCH` and the server has only `PUT`.
- **Why it hurts:** the doc and the code drifted apart; the real behavior is the opposite of what is promised.
- **Example:** `/conform-fail/orphan` (`405`, spec declares only `204`), `/conform-fail/wrong-method`.

#### P22. A route exists on the server but is not in the spec
- **What goes wrong:** the server has `GET /undocumented` and the spec does not mention it.
- **Why it hurts:** nobody tests it, it has no documented contract, and it can leak internal behavior.
- **Example:** `GET /conform-fail/undocumented`. A tool that only walks the spec never calls it; a scenario step that calls it finds "no matching operation in the spec" (`CS-NC-001`).

#### P23. A path parameter has a different type than the spec says
- **What goes wrong:** the spec says `id` is an integer; the server only accepts UUIDs and answers `400` to anything else.
- **Why it hurts:** valid requests made from the spec are rejected.
- **Example:** `GET /conform-fail/path-param/{id}`: `answered 400, but the spec declares only 200`.

#### P24. The server needs something the spec never mentions
- **What goes wrong:** the server requires a header (`X-Tenant`) that is not in the spec. A client written from the spec always gets `400`.
- **Why it hurts:** the API is unusable for everybody except the team that wrote it.
- **Example:** `POST /conform-fail/requires-extra-header`: `answered 400, but the spec declares only 201`.

#### P25. Features the test tool does not exercise: callbacks, webhooks, links, XML bodies
- **What goes wrong:** OpenAPI can describe callbacks (the API calls *you*), webhooks, response `links` and XML request bodies. A conformance tool does not exercise all of them (form and multipart bodies it does build), so they stay untested without anyone noticing.
- **Why it hurts:** a green report hides a part of the API that nobody checked.
- **Example:** `POST /conform-fail/subscribe` (a callback), `/ok/openapi-3.1.yaml` (a webhook), `/ok/features/items` (a `link`), `POST /ok/features/xml-note` (an XML request body).

### Group E: The test request itself is wrong

A conformance tool sends requests that it builds from the spec **and** from values you supply (an environment file). Sometimes the test, not the server, is wrong. A good tool says so instead of blaming the server.

#### P26. A value you supplied does not fit the parameter
- **What goes wrong:** the spec says `itemId` is an integer; your environment says `itemId=abc`. The request is not valid, so nothing meaningful was tested.
- **Why it hurts:** the server "fails" and you waste time on a server that is fine.
- **Example:** `clrsig/environments/conform-fail-bad-values.yaml` on `GET /conform-fail/requests/param-type/{itemId}`: `path parameter "itemId" does not fit the spec: value abc`.

#### P27. A value you supplied breaks the request body
- **What goes wrong:** the body has `"amount": {{amount}}` and the environment says `amount=cheap`. The JSON is now invalid.
- **Example:** `POST /conform-fail/requests/body-value` with the bad environment: `request body field "amount" takes its value from {{amount}}, which is "cheap"`.

#### P28. A value is missing
- **What goes wrong:** the request needs `{{itemId}}` and nothing provides it. Some tools send the text `{{itemId}}` to the server.
- **Why it hurts:** the server answers `400` or `404` and you blame the server.
- **Example:** with the environment `clrsig/environments/conform-fail-missing-value.yaml`: `not sent: no value for {{itemId}}`. The scenario `clrsig/scenarios/conform-fail-missing-value.yaml` shows the same for one step: the step fails, the next step still runs.

#### P29. A dynamic value is wrong
- **What goes wrong:** you wrote `{{$randomInt 1 40}}` (a function that makes a value) and misspelled it, or used it wrongly.
- **Example:** `{{$noSuchFunction}}`: `unknown function $noSuchFunction` in an environment value, in a scenario step, and in a scenario's own `variables:` (which stops the whole scenario).

#### P30. The environment refers to a variable that is not set
- **What goes wrong:** the environment says `token: ${MY_TOKEN}` and `MY_TOKEN` is not set on the machine (typical in CI).
- **Example:** `environment variable CLRSIG_UNSET_FIXTURE_VAR is not set` (a warning; the value stays as written).

### Group F: The server accepts too much (it is too lenient)

#### P31. A request without a required field is accepted
- **What goes wrong:** the spec says `name` is required. `POST` without `name` returns `201`.
- **Why it hurts:** bad data enters the database. Later code assumes the field is there.
- **Example:** `POST /conform-fail/lenient/missing-field` accepts a body without `name`. The twin `POST /conform-fail/strict/missing-field` correctly answers `400`.

#### P32. A field of the wrong type is accepted
- **What goes wrong:** `quantity` is declared an integer and the server accepts `"five"`.
- **Example:** `POST /conform-fail/lenient/wrong-type` vs `strict/wrong-type`.

#### P33. A missing required query parameter or header is accepted
- **Example:** `GET /conform-fail/lenient/missing-query` answers `200` without the required `q`.

#### P34. A request without credentials is accepted
- **What goes wrong:** the operation is secured (bearer token, basic auth, API key) and answers `200` to an anonymous caller.
- **Why it hurts:** the most serious kind of bug here: an open door.
- **Example:** `GET /conform-fail/lenient/no-auth`.

#### P35. Wrong, expired, or under-privileged credentials are accepted or mishandled
- **What goes wrong:** the server checks "is there a token" but not "is it valid, current and allowed to do this". Typical bugs: an expired token still works; a read-only token can write; the unknown token gives `500`.
- **Why it hurts:** authorization bugs are hard to see and costly.
- **Example:** `/conform-fail/lenient/wrong-auth`, `/conform-fail/rules/protected` (expired token returns `200` instead of `401`), and the correct reference `/ok/features/credentials/profile` and `write-area` (valid, unknown, expired, read-only and writer tokens).

#### P36. Other loose validation: enums, boundaries, unknown fields
- **What goes wrong:** the server accepts a value outside the enum, an out-of-range number, or an unknown field in the request.
- **Example:** `POST /conform-fail/lenient/enum-and-boundary`, `lenient/unknown-fields`.

### Group G: Time and unstable behavior

#### P37. The server is slow
- **What goes wrong:** the answer is correct but takes 4, 15 or 30 seconds.
- **Why it hurts:** clients time out and retry; a "correct" API can be unusable.
- **Example:** `GET /conform-fail/slow` (15 s), `/conform-fail/latency/{ms}` (a delay you choose), `/conform-fail/timeout/slow-headers` (4 s before any answer).

#### P38. The server never answers, or answers too slowly in the body
- **Example:** `/conform-fail/timeout/hang` (never answers within the limit), `/conform-fail/timeout/slow-body` (headers at once, then the body arrives slowly in small pieces).

#### P39. The server fails every N calls (flaky)
- **What goes wrong:** every third call returns `500`.
- **Why it hurts:** one run passes, the next fails. A single request cannot show it; you must call several times.
- **Example:** `GET /conform-fail/flaky` (calls 1, 2 pass, 3 fails, 4, 5 pass, 6 fails).

#### P40. A rate limit hits unexpectedly
- **Example:** `GET /conform-fail/rate-limited`: after 3 calls it answers `429`.

#### P41. The server is down for a while and then recovers
- **Example:** `GET /conform-fail/unavailable-then-ok`: the first 2 calls give `503`, then `200`.

#### P42. The server gets slower with every call, or has random delays
- **Example:** `/conform-fail/latency/degrading` (100, 400, 700, 1000, 1300 ms) and `/conform-fail/latency/jitter` (a seeded series of delays, the same each run).

### Group H: State and business rules (visible only across several calls)

These problems cannot be seen in one request. Each response is valid by itself; the **behavior over time** is wrong. A scenario is needed.

#### P43. A repeated write creates duplicates (no idempotency)
- **What goes wrong:** the client sends the same `POST` with the same `Idempotency-Key` twice; the server creates two records.
- **Why it hurts:** a retry after a timeout charges the customer twice.
- **Example:** `POST /conform-fail/idempotent` and the scenario `conform-fail-write-bugs.yaml`.

#### P44. A stale update overwrites a newer one (lost update)
- **What goes wrong:** two clients read version 1. Client A saves; client B saves with the old version (`If-Match`). The server ignores `If-Match` and B overwrites A.
- **Example:** `PUT /conform-fail/lost-update`; also found by `conform --negative` as a missing `If-Match` probe.

#### P45. A write times out, yet it was done
- **What goes wrong:** the client gives up after 1.5 s, but the server finished the write after 15 s. A retry now duplicates it.
- **Example:** `POST /conform-fail/timeout/after-write`, then `GET .../after-write/records` shows the record.

#### P46. A business rule is broken although every response looks fine
- **What goes wrong:** the stock goes negative; a shipped order can be cancelled; a duplicate e-mail is accepted; withdrawing more than the balance returns `200` with an error body instead of `422`; page 2 repeats the last item of page 1; an expired token works.
- **Why it hurts:** schema validation passes all of them. Only a check of the *rule* finds them.
- **Example:** the seven rules under `/conform-fail/rules/*` and the scenario `conform-fail-business-rules.yaml`.

### Group I: Change over time

#### P47. A spec change breaks existing clients
- **What goes wrong:** somebody removes an endpoint, renames a field, makes an optional field required, narrows a type, or removes an enum value. Clients written for the old spec break.
- **Example:** the pairs in `specs/diff/`: `removed-endpoint`, `new-required-request-field`, `optional-to-required-param`, `enum-value-removed`, `renamed-field`, `type-narrowed`.

#### P48. Not every change is equally risky
- **What goes wrong:** teams either block all changes or let all pass. Some are safe (a new endpoint, a changed description), some are risky (a removed optional parameter), some break clients.
- **Example:** `optional-param-removed` (warning), `deprecated-operation`, `endpoint-added`, `non-success-response-removed` (info), `description-changed` (nothing).

#### P49. You do not know which of your tests the change will break
- **What goes wrong:** a spec change ships; your scenarios call the removed endpoint and fail the next day.
- **Example:** `clrsig impact` on the `impact-hit` pair finds the scenario step that calls the removed `GET /users/{id}`.

#### P50. The server drifts away from its spec
- **What goes wrong:** the code changes and the spec does not. Today three operations disagree; next week a fourth does. A team with many known problems cannot fail on all of them.
- **Why it hurts:** either the pipeline is always red (ignored) or never checked.
- **Example:** `/conform-fail/drift/report` returns a number at drift level 0 and a string at drift level 1. Running with a baseline: 3 known problems, 1 new one.

#### P51. You do not know what your tests never reached
- **What goes wrong:** the run is green but it only covered 3 of 100 operations. Or only the happy path; or no error response; or the secured endpoints were never called with credentials.
- **Example:** `specs/coverage/coverage.yaml` with `clrsig/scenarios/coverage-gaps.yaml`: one operation never exercised, one only on the happy path, one with an error response never triggered, one secured but never called with credentials.

### Group J: The spec file itself

#### P52. The spec cannot be read
- **What goes wrong:** the file is missing, not YAML, not an OpenAPI document, or a URL returns `404`.
- **Example:** `clrsig/fixtures/unreadable-yaml.yaml`, `not-openapi.yaml`; a missing file; a spec URL that answers `404`.

#### P53. The spec is broken in a way the tools must explain
- **What goes wrong:** a `$ref` to a schema that does not exist; two operations with the same `operationId`; a path `/u/{id}` where the parameter `id` is not declared.
- **Example:** `specs/hostile/missing-ref.yaml`, `duplicate-operation-id.yaml`, `undeclared-path-param.yaml`. They must fail with a clear message, not a crash.

A spec can also load and still be wrong, so that a response check blames the server: a `required` list naming a property the schema does not declare (`specs/lint/required-undeclared.yaml`), an operation with no `operationId`, an example that breaks its own format.

#### P54. The spec is valid but awkward
- **What goes wrong:** a schema that contains itself (a tree with `parent` and `children`), `allOf` that refers back to itself, a `oneOf` with 60 branches, a schema 120 levels deep, an `allOf` of a string and an integer (impossible), a JSON file instead of YAML, `openapi: 3.2.0`, no paths at all, odd paths (two parameters and a dot, a trailing slash, a non-ASCII path).
- **Why it hurts:** tools loop forever, run out of memory, or give up. The spec author did nothing wrong.
- **Example:** the documents in `specs/hostile/` (circular `$ref`, recursive `allOf`, a discriminator, a 60-branch `oneOf`, an impossible `allOf`, a deep schema, odd paths, no paths, a JSON file, `openapi: 3.2.0`).

#### P55. The spec is big
- **What goes wrong:** 500 or 2,000 operations. A tool that is quadratic becomes unusable.
- **Example:** a generated 500-operation spec (`scripts/make_specs.py`): generate, compare and probe all finish in well under a second.

### Group K: What a test tool cannot see (known limits)

Every tool has blind spots. It is better to know them than to trust a green run.

#### P56. Things clrsig knowingly does not check
- Formats outside `date`, `date-time`, `email`, `uuid`, `ipv4`, `ipv6` and `byte` (`uri`, `hostname`: `"link": "not a uri"` passes) (`CS-GAP-001`); `email` and `uuid` are checked since clrsig 0.9.0.
- Extra fields on open schemas (`CS-GAP-002`) and response headers the spec never mentions (`CS-GAP-003`).
- XML, CSV and other non-JSON response bodies (`CS-GAP-004`, `CS-NC-009`).
- A time limit for one method of a path (`CS-GAP-005`; since v0.8.8 a limit per path prefix exists).
- XML request bodies: the request goes out with no body (`CS-GAP-006`).
- Callbacks and webhooks (`CS-GAP-010`).
- Probes for wrong, expired or under-privileged credentials (`CS-GAP-008`) and for enum, boundary and unknown-field mistakes (`CS-GAP-009`).
- Only the first problem per response (`CS-GAP-011`).
- **Example:** one fixture each, listed in `docs/clrsig-gaps.md`.

#### P57. Responses that are "not checked" without you noticing
- **What goes wrong:** the report is green, but a response was not compared: the step had `validateSpec: false`, the scenario had no spec, the request never got an answer, an operation was skipped by `--tags`, `--paths` or `--read-only`, a body had no `Content-Type`, or no content was declared.
- **Example:** `CS-NC-001` to `CS-NC-009`; the scenario `conform-fail-spec-check-states.yaml` shows three of them and the summary line says how many responses were not compared.

#### P58. Things that are outside OpenAPI entirely
- A cookie that must be sent back automatically, following a `Link` header for pagination, an OAuth flow with a browser, WebSocket and server-sent events, gRPC and GraphQL, TLS and client certificates, load and concurrency, HTTP/2.
- **Example:** `/ok/features/session/*` (a cookie session) and `/ok/features/links/items` (Link-header pagination) show what a script can and cannot do today. See `docs/clrsig-gaps.md`.

### Group L: When the test tool gives a wrong answer

A green result is only as good as the tool. While building these fixtures we found cases where clrsig itself gave a wrong answer. They were reported, and all were fixed or are tracked in `docs/clrsig-findings.md`. They are good lessons for any team.

#### P59. A green result that is not true (false pass)
- **What goes wrong:** the tool accepts a body it should reject, or says `PASSED` when something failed.
- **Examples we found (and clrsig has since fixed):** a body with bytes that are not UTF-8 passed; text after the JSON passed; a failed extraction exited with `0` and `PASSED`; the probe summary said `PASSED` when every probe errored; a missing placeholder was sent literally.
- **Why it matters:** CI trusts the exit code. If the exit code is wrong, so is the pipeline.

#### P60. A red result that is not true, or data silently corrupted (false failure, wrong data)
- **What goes wrong:** the tool fails a correct response, or changes your data.
- **Examples:** an integer above 2^53 (a "snowflake" id) was rounded and printed as `9.2e+18`, so a request chained from it carried a wrong id (fixed in v0.8.5); a valid number `1e400` was a failure with no check ID (fixed); a repeated header showed only its first value (fixed); and, found in v0.8.5 and fixed in v0.8.6: a correct NDJSON response (`application/x-ndjson`) was read as one JSON document and failed; a valid XML `example` string made the whole spec unreadable; the "no credentials" probe still sent an API key kept in a cookie.
- **Why it matters:** do not trust a tool blindly. Keep a set of fixtures that **know the right answer** (this repository), and run it whenever the tool changes. That is what these fixtures are for.

---

## Part 2: How clrsig finds and helps solve them

Same numbers as Part 1. For each problem: **Check** (the ID in the report), **How it finds it** (the idea), **What you see** (real output), **What to do**, and **Limits** (where clrsig cannot help). Results are for clrsig v0.13.4 against the fixtures of this repository.

### The commands, once

| Command | What it does | Exit code |
|---|---|---|
| `clrsig conform SPEC -b URL` | Builds one request per operation from the spec, sends it, checks the answer. | `0` all good, `1` a problem found, `2` the spec or the setup is broken |
| `clrsig conform ... --negative` | Also sends requests that are wrong on purpose (negative probes). | same |
| `clrsig run SCENARIO --spec SPEC --env ENV` | Runs a script of steps with your own checks (assertions), and also checks each response against the spec. | same |
| `clrsig diff OLD.yaml NEW.yaml` | Lists what changed between two spec versions, sorted by how much it can hurt clients. | `1` if a change is at or above `--fail-on` (breaking / warning / info) |
| `clrsig impact OLD NEW SCENARIOS` | Says which of your scenarios call something that the change breaks. | `1` if any does |
| `clrsig coverage quality SPEC -w DIR` | Shows what your runs never proved. | `0` (gaps are signals) or `1` with `--fail-on-gaps` |
| `clrsig generate SPEC --dry-run` | Shows the requests it would build from the spec, without sending anything. | `2` if the spec is broken |
| `clrsig validate SCENARIO` | Checks scenario files for mistakes without running them. `--strict` also fails valid but weak ones (v0.9.1). | `1` if a file has a mistake |
| `clrsig validate --spec SPEC` | Checks the spec document itself (v0.11.0): `CS-SPEC-001` to `003`. | `1` on an error; on a warning only with `--strict` |
| `clrsig init`, `clrsig config show` | Creates a project file, `clrsig.yaml`, so the other commands need fewer flags; shows what they take from it (v0.9.1). | `2` if the file is broken |

Useful flags: `--paths /x,/y` and `--tags a,b` (choose operations; since v0.8.9 a filter that matches nothing is an error, `NOTHING CHECKED` and exit `2`, instead of a green run), `--env FILE` (values for placeholders), `--var name=value` (override one), `--explain` (plain-language reason under each failure), `--fail-fast`, `--read-only` (send only GET and HEAD), `--format json|junit|html|markdown` (reports for CI), `--max-response-time MS`, `--max-response-time-for /prefix=MS` (a different limit under a path prefix, from v0.8.8; `0` turns the limit off there), `--request-timeout MS`, `--baseline FILE` and `--write-baseline FILE` (since v0.10.0 a baseline can only be written from a full run, not with `--tags`, `--paths` or `--changed-against`), `--setup SCENARIO` (log in first; what it extracts fills the requests, v0.9.1), `--changed-against GIT-REF` (only new or changed operations, for pull requests, v0.10.0), `--format github` (annotations on a pull request, v0.10.0; also for `run` since v0.11.0), `--fail-on failure|warning` (v0.9.0). To repeat random values, `clrsig run` has `--seed N`.

The same checks are also available outside the terminal: `conform` is a tool of the clrsig MCP server (an AI agent can call it; it takes `spec`, `baseUrl`, `envFile` and, from v0.8.7, `maxResponseTime`, and from v0.8.8 `maxResponseTimeFor`), the GitHub Action has inputs for the main flags (including `max-response-time` and, from v0.8.8, `max-response-time-for`), and the desktop app has a Check Conformance page.

**How to read a result.** A line `FAIL GET /path 200` is one operation. The lines below it start with `✗` and say what is wrong, in words. With `--format json`, each finding has a `kind` and a `checkId` (for example `CS-RESP-005`) that a script can read. The last line is a summary (`FAILED 24 operations · 0 passed · ...`) and the exit code is what CI looks at.

### Group A: The response does not match the contract

**P01. Undeclared status code**
- **Check:** `CS-RESP-001`. **Finds it by:** comparing the status of the answer with the list of statuses in the spec for that operation (a `default` or `2XX` counts).
- **What you see:** `GET /cases/resp-001-undeclared-status answered 500, but the spec declares only 200, 404`.
- **What to do:** either handle the case in the code and declare it in the spec (a `500` or `503` should be declared if clients must know), or fix the bug that produces it. With `--explain` you also get the reason and a hint.
- **Limits:** none for the status itself.

**P02. Wrong `Content-Type`**
- **Check:** `CS-RESP-002`. **Finds it by:** comparing the `Content-Type` of the answer with the media types the spec declares for that response.
- **What you see:** the response has `Content-Type "text/plain"`, but the spec declares `application/json`.
- **What to do:** set the right header, or find the layer (proxy, error handler) that replaces the body. 
- **Limits:** when the type is wrong, clrsig does **not** compare the body (it would not know how to read it). Fix this first, then run again to see the body problems.

**P03. Required response header missing** and **P04. Header of the wrong type**
- **Check:** `CS-RESP-003` and `CS-RESP-004`. **Finds it by:** looking at every header the spec lists for the response: required ones must be there; every declared one must fit its schema.
- **What you see:** `header "X-Total-Count" is required by the spec but was not sent`; `... has a value that does not fit the spec`.
- **What to do:** add or correct the header. If the header is optional in practice, change the spec (`required: false`); the contract must tell the truth.
- **Limits:** a header the spec never mentions is not reported (`CS-GAP-003`).

**P05. Required field missing**, **P06. Wrong type**, **P07. Value breaks a rule**
- **Check:** `CS-RESP-005`, `CS-RESP-006`, `CS-RESP-007`. **Finds it by:** validating the body against the JSON Schema in the spec: required fields, types, and the rules (`enum`, `minimum`, `maximum`, `minLength`, `maxLength`, `pattern`, `minItems`, `uniqueItems`, `nullable`, `date-time`).
- **What you see:** `property "id" is missing`; `value must be a number`; `value must be an object`; `number must be at least 0`; `minimum string length is 3`; `duplicate items found`; `Value is not nullable`. The message includes the path to the bad value (for example `/items/0/price`). Since v0.13.2 the one value at fault may follow, shortened or masked (`***`); the schema and the body are no longer printed (earlier versions printed both, secrets included).
- **What to do:** fix the response code or the schema, whichever is wrong. A frequent cause: a database `NULL` that the schema does not allow (`nullable: true` is the fix when `null` is truly valid).
- **Limits:** formats outside the supported list (`uri`, `hostname`) are not validated (`CS-GAP-001`); `email`, `uuid`, `ipv4`, `ipv6`, `date` and `date-time` are.

**P08. Body not valid JSON, or empty**
- **Check:** `CS-RESP-008` (finding `invalid-body`). **Finds it by:** parsing the body as **strict** JSON.
- **What you see:** `the response body is not valid JSON (invalid character ...)`, or `the response body is empty`.
- **What to do:** look at the real body (`curl -i`). It is often an HTML error page from a proxy, or a partial write.
- **Limits:** none.

**P09. A `oneOf`/`anyOf` body fits no branch**
- **Check:** `CS-RESP-009` (finding `no-branch-matched`). **Finds it by:** trying the body against every allowed shape.
- **What you see:** `the response matches none of the 2 shapes the spec allows` (it does not blame one field).
- **What to do:** check that the discriminator field (`kind`) and the fields of that branch agree.
- **Limits:** none.

**P10. Extra field in a closed schema** and **P11. A `writeOnly` field in a response**
- **Check:** `CS-RESP-010` and `CS-RESP-011` (finding `write-only-property`). **Finds it by:** a closed schema (`additionalProperties: false`) rejects unknown fields; a `writeOnly` field must never be present.
- **What you see:** `property "extra" is unsupported`; `writeOnly property "password" in response`.
- **What to do:** remove the field from the response. For P11 treat it as a security incident and look at where else the object is serialized.
- **Limits:** on an **open** schema an extra field is legal and is not reported (`CS-GAP-002`). If you want strictness, close the schema in the spec.

**P12. Several problems in one response**
- **Check:** `CS-GAP-011` (a known limit). **What happens:** clrsig reports the first problem it finds (header before body). 
- **What to do:** fix it, run again, repeat. 
- **Limits:** this is the limit.

### Group B: Odd but valid answers

**P13. Valid JSON that looks unusual** and **P14. Compressed, chunked, header-heavy answers**
- **Check:** none: they **pass**. **How clrsig helps:** the fixtures `hostile-deep-nesting`, `wide-object`, `unicode`, `integer-as-float`, `integer-exponent`, `big-integer`, `negative-zero`, `gzip`, `chunked-stream`, `duplicate-headers` and `big-header` are pinned as "must pass". If a future clrsig release starts failing them, the expectations fail and you see it.
- **What to do:** if you build your own checker or wrapper, run these fixtures through it. They are the typical places where homemade validators break.
- **Limits:** none known in v0.13.4 for this group.

**P15. Bodies that are not JSON**
- **Check:** `CS-NC-009` and `CS-NC-003` ("not checked"), `CS-GAP-004`. **How it behaves:** for XML, CSV, images and binary, clrsig checks status, headers and `Content-Type` and does **not** compare the body; it reports nothing about the body.
- **What to do:** validate those bodies yourself (an XML schema, a CSV header check) or with a scenario assertion on a header or size.
- **Limits:** the body is **not** verified. Since v0.8.6 a type like `application/x-ndjson` is no longer read as one JSON document (F-033, see P60), but its lines are not checked either.

### Group C: Broken bodies and broken connections

**P16. Malformed JSON that parsers treat differently**
- **Check:** `CS-RESP-008` for the strict failures, `CS-RESP-006` for duplicate keys, `CS-RESP-015` for a number beyond a 64-bit float.
- **What you see:** a BOM: `invalid character 'ï'`; invalid UTF-8: `byte 0xff at offset 20 is not UTF-8`; trailing text: `text after the JSON value`; `NaN`: `invalid character 'N'`; a raw line break: `invalid character '\n' in string literal`; duplicate keys: the **last** key wins (`id` is the string `two`, so `value must be an integer`); `1e400`: its own finding `number-out-of-range` that says it is a clrsig limit; a lone surrogate: accepted (valid JSON text).
- **What to do:** serve strict JSON. Use your language's real serializer, never string concatenation.
- **Limits:** for a BOM and for duplicate keys the standards leave the behavior open. clrsig is strict; the fixtures record that choice, so it is not a surprise.

**P17. Body cut off or connection dropped**
- **Check:** `CS-RUN-003` ("no response"). **Finds it by:** a read error while getting the body.
- **What you see:** `reading response body: unexpected EOF` (cut off), `EOF` (reset), `context deadline exceeded` (too slow).
- **What to do:** check proxy and server timeouts and body-length handling. Check that retries are safe (see P43 and P45).
- **Limits:** there is no response to compare, so no other check runs.

**P18. A response over the read limit**
- **Check:** `CS-RESP-013`. **What you see:** `larger than the 50 MB Clear Signal reads` (it names the limit and the size), instead of a misleading "invalid JSON".
- **What to do:** paginate or stream the data. A 50 MB JSON body is a problem for clients too.
- **Limits:** a binary body above the limit passes (it is not compared).

**P19. A redirect loop**
- **Check:** `CS-RUN-003`. **What you see:** `stopped after 10 redirects`.
- **What to do:** fix the redirect rule (often `http` to `https` or a trailing slash rule that points back).

### Group D: The spec and the server disagree

**P20 to P24: ghost route, wrong method, undocumented route, path-parameter type, hidden header**
- **Check:** `CS-RESP-001` for P20, P21, P23, P24 (the real answer is `404`, `405` or `400`, which the spec does not declare), `CS-NC-001` for P22.
- **How it finds them:** it builds a request from the spec exactly as a client would. If the server answers with something the spec does not declare, that is the evidence. For a route the spec does not know (P22), a scenario step reports "no matching operation in the spec": there is nothing to compare with.
- **What you see:** `GET /ghost answered 404, but the spec declares only 200`; `DELETE /orphan answered 405, but the spec declares only 204`; `POST /requires-extra-header answered 400, but the spec declares only 201`.
- **What to do:** find the source of truth. Either the code is missing the route (fix the code) or the spec is outdated (fix the spec). Do not silence the check.
- **Limits:** P22 (undocumented routes) cannot be found by walking the spec; use `clrsig run` with a scenario that calls the URL, or compare with the routes your framework lists.

**P25. Callbacks, webhooks, links, XML bodies**
- **Check:** `CS-GAP-010` (callbacks, webhooks, links) and `CS-GAP-006` (XML request bodies). 
- **What you see:** the callback is never called. For an XML request body clrsig sends **no body**, and reports `the request body does not fit the spec: value is required but missing` (`POST /ok/features/xml-note`). Form (`application/x-www-form-urlencoded`) and multipart bodies **are** built from the spec.
- **What to do:** test callbacks and XML endpoints with a scenario that sends the body you want, or by hand.
- **Limits:** these are known gaps, pinned in the fixtures so you notice when they close.

### Group E: The test request itself is wrong

**P26 to P30: wrong value, broken body, missing value, wrong function, unset variable**
- **Check:** `CS-REQ-001` (parameter does not fit), `CS-REQ-002` (body does not fit), `CS-RUN-001` (no value), `CS-RUN-002` and `CS-RUN-007` (bad function), `CS-RUN-005` (unset `${NAME}`).
- **How it finds them:** before sending, it checks the request it built against the spec. A bad request is **not sent**, and the report says whose fault it is. This is the difference between "the server is wrong" and "the test is wrong".
- **What you see:** `path parameter "itemId" does not fit the spec: value abc`; `request body field "amount" takes its value from {{amount}}, which is "cheap"; that is not a valid JSON value (the spec declares a number)`; `not sent: no value for {{itemId}} (set it in the environment, with --var, in the scenario's variables, or extract it in an earlier step)`; `unknown function $noSuchFunction`; `environment variable ... is not set`.
- **What to do:** fix the environment file, pass `--var name=value`, or fix the function name. `clrsig validate` finds scenario mistakes before the run.
- **Limits:** in a scenario, a bad function in the scenario's own `variables:` stops the whole scenario (exit `2`); in a step it fails only that step (exit `1`).

### Group F: The server accepts too much

**P31 to P34: negative probes**
- **Check:** `CS-PROBE-001` (missing required field accepted), `CS-PROBE-002` (wrong type accepted), `CS-PROBE-003` (missing required query parameter or header accepted), `CS-PROBE-004` (no credentials accepted). 
- **How it finds them:** with `--negative`, clrsig sends requests that are wrong on purpose (it drops each required field one by one, sends a wrong type, drops the credentials) and expects `400`/`422` (or `401`/`403`). A `200` is the bug. For `oneOf`/`anyOf` bodies, every branch is probed.
- **What you see:** `FAIL POST /lenient/missing-field — missing required field 'name' (expect 400/422)` and `server accepted invalid request with 201`; the summary line `1 operation(s) accepted requests they should have rejected — fix server validation`.
- **What to do:** add the validation (a schema validator at the edge of the API). Run `--negative` in CI forever; this is the cheapest security test there is.
- **Limits:** see P35 and P36.

**P35. Wrong, expired or under-privileged credentials; P36. Other loose validation**
- **Check:** `CS-GAP-008` and `CS-GAP-009` (known gaps). **What clrsig does:** only the *absence* of credentials is probed; no probes for enum, boundary or unknown-field mistakes.
- **How you cover it:** write a **scenario** with one step per bad credential and an assertion on the status. The example is `clrsig/scenarios/ok-credentials-and-session.yaml`: unknown token `401`, expired token `401` (with `WWW-Authenticate` saying it expired), read-only token on a write operation `403`, writer token `200`.
- **Limits:** those probes are not automatic. Since v0.8.6 the "no credentials" probe also removes an API key sent **in a cookie** (F-035, see P60).

### Group G: Time and unstable behavior

**P37 to P42: slow, hanging, flaky, rate limit, outage, degrading**
- **Check:** `CS-RESP-014` (slower than your limit: the response is kept and still compared with the spec), `CS-RUN-003` (no answer at all: timeout), `CS-RESP-001` (`500`, `429`, `503` that the spec does not declare).
- **How it finds them:** `--max-response-time 500` fails any operation slower than 500 ms and says how long it took; `--request-timeout 2000` gives up on a request after 2 s. `--max-response-time-for /reports=2000` (v0.8.8) gives the operations under `/reports` their own limit: the longest matching prefix wins, `0` turns the limit off there (real cases: `latency-path-limit-*`). In a scenario, `{ type: duration, operator: lt, expected: 500 }` asserts the time of one step.
- **What you see:** `The response took 4810 ms, over the limit of 100 ms` (finding `slow-response`); `context deadline exceeded`; for flaky and rate-limited calls, `answered 500, but the spec declares only 200` on call 3, and `answered 429...` from call 4.
- **What to do:** set a time budget that matches your SLA. For flaky behavior, run the same operation several times (the fixtures call it in sequence and check each call).
- **Limits:** a limit is per path prefix, not per method of one path (`CS-GAP-005`). Timing results depend on the machine: run time-based checks in a container, not on a laptop that is busy.

### Group H: State and business rules

**P43 to P46: idempotency, lost update, write-then-timeout, business rules**
- **Check:** none of the response checks can see these, because every single response is valid. **How clrsig helps:** a **scenario** with **assertions** that say what the correct behavior is. The step fails exactly where the server is wrong.
- **What you see (from `conform-fail-business-rules.yaml`):** `an order above the stock is refused: FAIL (accepted 201 instead of 422)`, `the stock stays at zero or more: FAIL (the stock is -3)`, `a shipped order cannot be cancelled: FAIL (200 instead of 409)`, `a duplicate email is refused: FAIL (201 instead of 409)`, `page 2 does not repeat the last item of page 1: FAIL`, `an expired token is refused: FAIL (200 instead of 401)`.
- **For the lost update (P44):** `conform --negative` also reports a missing `If-Match` probe, because the server ignores that header.
- **What to do:** write the rule as a scenario: the same checks you would do by hand. Use `extractions` to carry an id or an ETag from one step to the next, and `failPolicy: continue` so one broken rule does not hide the others.
- **Limits:** the tool checks the rules you write; it cannot guess the rules.

### Group I: Change over time

**P47 and P48: breaking and non-breaking spec changes**
- **Check:** `CS-DIFF-001` (breaking, level ERR), `CS-DIFF-002` (warning), `CS-DIFF-003` (info).
- **Command:** `clrsig diff old.yaml new.yaml` (or `clrsig diff openapi.yaml --against origin/main` in a git repo). The exit code is `1` when a change is at or above `--fail-on` (`breaking` by default).
- **What you see:** for `renamed-field`: `response-required-property-added` and `response-required-property-removed`; for `removed-endpoint`: `api-path-removed-without-deprecation`; for `optional-param-removed`: a warning; for `endpoint-added` and `description-changed`: info or nothing.
- **What to do:** put `clrsig diff --against origin/main` in the pull-request pipeline. Breaking changes block the merge; warnings are discussed; info is listed.
- **Limits:** it compares **specs**. It does not know whether the server really implements the change (that is `conform`).

**P49. Which scenarios will the change break?**
- **Check:** `CS-IMP-001`. **Command:** `clrsig impact old.yaml new.yaml scenarios/`.
- **What you see:** `calls-removed-endpoint.yaml: Fetch user 1`. It also matches a step that uses a placeholder in the path (`/users/{{userId}}`).
- **What to do:** update those scenarios in the same pull request.

**P50. The server drifts from its spec**
- **Check:** `CS-RUN-006` (a new problem against a baseline). **Commands:** `clrsig conform ... --write-baseline known.yaml` once, then `clrsig conform ... --baseline known.yaml` in CI.
- **What you see:** `Baseline: 3 known, 1 new, 0 fixed` and exit `1` because of the one **new** problem; when somebody fixes one, `3 known, 0 new, 1 fixed`.
- **What to do:** adopt clrsig in an existing API without fixing everything first: known problems are recorded, new problems fail the build, fixed problems are celebrated. Shrink the baseline over time.
- **Limits:** a baseline can hide a problem forever if nobody reads the "fixed" and "known" numbers.

**P51. What the tests never reached**
- **Check:** `CS-COV-001` (never exercised), `CS-COV-002` (happy path only), `CS-COV-003` (declared error responses never triggered), `CS-COV-004` (secured but never called with credentials). **Command:** `clrsig run ... --workspace DIR` to collect, then `clrsig coverage quality SPEC -w DIR`.
- **What you see:** `NEVER EXERCISED (1): POST /strict/wrong-type`; `HAPPY PATH ONLY — no error responses ever triggered (1): GET /strict/missing-query, declared errors: 400`; `SECURED — never tested with credentials (1): GET /strict/no-auth`; `UNTESTED ERROR PATHS: GET /strict/missing-query → 400 never triggered`; and a last line `4 gap(s) found — add scenarios that trigger error paths and test authenticated+unauthenticated flows`.
- **What to do:** use it as a to-do list. Add `--fail-on-gaps` if you want a coverage bar in CI.
- **Limits:** these are signals, not failures (exit `0` unless you ask).

### Group J: The spec file itself

**P52. The spec cannot be read** and **P53. The spec is broken**
- **Check:** `CS-RUN-004` (exit `2`). **How it behaves:** a broken spec stops the run with a short, clear message and exit code `2`, which is different from `1` (a real finding). It never crashes and never sends a request.
- **What you see:** `parsing spec: loading spec: failed to unmarshal data ...`; `invalid OpenAPI spec: value of openapi must be a non-empty string`; `server returned 404`; `failed to resolve "components" in fragment ... #/components/schemas/Nope`; `operations "GET /one" and "GET /two" have the same operation id "same"`; `operation GET /u/{id} must define exactly all path parameters (missing: [id])`.
- **What to do:** run `clrsig generate SPEC --dry-run` as the first CI step: it loads the spec and builds requests without sending anything.
- **Limits:** a valid XML `example` string was rejected until v0.8.6 (F-034, see P60).

- **A spec that loads but is wrong:** `clrsig validate --spec SPEC` (v0.11.0) reports a `required` property that is not declared (`CS-SPEC-002`, exit `1`), and warns about a missing `operationId` (`CS-SPEC-001`) and an example that breaks its format (`CS-SPEC-003`); `--strict` fails on the warnings too. Fixtures: `specs/lint/`.

**P54. Valid but awkward specs** and **P55. Big specs**
- **How clrsig behaves:** loads and builds requests for circular references (`parent`/`children`), self-referencing `allOf`, a discriminator with a mapping (probes for **both** branches), 60 `oneOf` branches (120 probes), a schema 120 levels deep, an impossible `allOf` (a request is still generated, nothing hangs), a JSON spec, `openapi: 3.2.0`, no paths, and odd paths. A 500-operation spec generates, compares and probes in well under a second (2,000 operations in 0.3 s).
- **How we know:** the fixtures in `specs/hostile/` and a random-spec generator (`scripts/fuzz_specs.py`): about 970 random specs and 2,000 operations ran without a crash or a hang.
- **What to do:** nothing; this is reassurance. If you add a custom tool next to clrsig, test it with the same fixtures.

### Group K: What a test tool cannot see

**P56 to P58: known limits, "not checked" states, outside OpenAPI**
- **How clrsig helps:** it **tells you**. The catalog lists each limit with an ID (`CS-GAP-*`), and the summary of a scenario run says how many responses were **not compared** and why: `Spec: 2 of 4 responses were not compared with the spec (spec validation is turned off for this step: 1; the step did not complete: 1)` (`CS-NC-004`, `CS-NC-006`; `CS-NC-005` when the scenario has no spec at all).
- **What you do:** read `docs/clrsig-gaps.md`: it lists every gap, the fixture that pins it, and what would change when clrsig closes it. A green run means "no problem **in what was checked**".
- **For things outside OpenAPI** (cookies, `Link` headers, OAuth flows, WebSocket, gRPC, TLS): use a scenario for what you can (log in, extract the cookie from `Set-Cookie`, send it back in a `Cookie` header), and another tool for the rest. Today clrsig keeps **no cookie jar** between steps and cannot follow a `Link` header.

### Group L: When the test tool gives a wrong answer

**P59 and P60: false passes, false failures, corrupted data**
- **How we protect against it:** this repository is the answer: a fixture for every case **with the correct expected result written down**. `scripts/check_expectations.py` runs clrsig on all of them and compares. If a clrsig release changes any answer, the comparison fails, and you decide: is the new answer right (change the expectation) or wrong (report it)?
- **What happened in practice:** Thirty-five wrong answers or limits were found with these fixtures (F-001 to F-035 in `docs/clrsig-findings.md`). All were fixed quickly by the clrsig team (by v0.8.6). The seven false passes and data problems from the last round (P59 and most of P60) are fixed in v0.8.5. The last three were found while checking v0.8.5 and fixed in v0.8.6: an NDJSON response read as one JSON document (F-033); a valid XML `example` string making the spec unreadable (F-034); the "no credentials" probe keeping a cookie key (F-035).
- **What you do:** pin your tool version in CI (`CLRSIG_VERSION`), keep a fixture set with known answers, and read the release notes before upgrading. Never trust a single green run from a tool you have not tested.

### One page: which command for which question

| You want to know... | Use |
|---|---|
| Does the server answer like the spec says? | `clrsig conform SPEC -b URL` |
| Does the server refuse bad requests? | `clrsig conform ... --negative` |
| Does a multi-step flow (login, order, read) behave? | `clrsig run SCENARIO --spec SPEC` |
| Is it fast enough? | `--max-response-time`, or the `duration` assertion |
| Will this spec change break clients? | `clrsig diff OLD NEW` |
| Which of my tests will it break? | `clrsig impact OLD NEW SCENARIOS` |
| Can I adopt this without fixing everything today? | `--write-baseline` then `--baseline` |
| What have my tests never proven? | `clrsig coverage quality` |
| Is my spec even readable? | `clrsig generate SPEC --dry-run` |

---

## Part 3: Notes for the video explanations (NotebookLM)

This part is for you, the person making the videos with Google NotebookLM. It says what the videos are for, how to set up NotebookLM, a plan of episodes (each one points to problems in Parts 1 and 2), the demo commands to record, and a checklist before you publish. Where I say "the guide", I mean Parts 0 to 2 of this file.

### 3.1 Goal and audience

- **Goal:** a developer who has never done contract or conformance testing can, after the series, (1) name the common problems, (2) say which clrsig command finds each one, and (3) put the checks into CI.
- **Audience:** working developers (backend, frontend, mobile) with little testing background. They know HTTP, JSON and status codes. They may not know OpenAPI well, so the series explains it once in the first episode and then uses it.
- **Tone:** friendly, concrete, no jargon without a one-line explanation. Short sentences. "The server said X, the spec said Y" is the core story of almost every episode.
- **Length:** 5 to 8 minutes per episode. One idea per episode. Total series: 14 episodes, about 100 minutes.

### 3.2 Set up NotebookLM

1. **Create one notebook** called "Contract and conformance testing with clrsig".
2. **Add sources.** NotebookLM works best with several focused sources, not one giant file. Add:
   - this guide, **split into one source per episode** (see 3.7 for how to split);
   - `docs/clrsig-gaps.md` (what clrsig cannot do);
   - `docs/contract-fail-cases.md`, `docs/conform-fail-cases.md` and `docs/diff-cases.md` (the expected results, as tables);
   - `README.md` (how to run the practice server);
   - optionally `docs/clrsig-findings.md` (the story of the bugs found, for the "wrong answers" episode).
3. **Pick the sources per video.** In NotebookLM, tick only the sources for the episode you are generating. A Video Overview or Audio Overview then talks about those sources only.
4. **Use the "customize" box** of the Video/Audio Overview (its name and place in the page may change; look for "Customize" or "Focus"). Paste the **Series instructions** from 3.6, then add the **Episode focus** from the episode card in 3.4.
5. **Choose the output language** in NotebookLM's settings. The guide is written in English; NotebookLM can present in other languages, but check the technical words (status codes, `oneOf`, `Content-Type`) stay unchanged.
6. **Generate, then listen or watch once fully.** Compare the facts with the guide (checklist 3.8). NotebookLM can paraphrase and sometimes adds a detail that is not in the sources. Regenerate with a more specific focus if needed.

### 3.3 Rules for every episode (put these in the instructions)

1. **Start with a story, not a definition.** "A client calls `GET /orders/5`. The spec says the answer has an `id`. The server forgot it. Who finds out, and when?"
2. **One problem, three beats:** what goes wrong, why it hurts, how clrsig shows it. Always show the real line of clrsig output.
3. **Use the real fixtures.** Say the endpoint name (for example `/contract-fail/cases/resp-005-missing-required-field`). Viewers can repeat it.
4. **Explain each word once.** First use of *contract*, *conformance*, *negative probe*, *scenario*, *baseline*, *drift* gets a one-sentence meaning (glossary in 3.5).
5. **Be honest about limits.** Every episode ends with "what clrsig does *not* see here". Never say "clrsig catches everything". Say "in clrsig v0.13.4".
6. **Name the version and the date.** "Recorded with clrsig v0.13.4, November 2026." Results can change with new releases (see 3.8).
7. **Do not read tables aloud.** Show them, then say the one thing that matters.
8. **End with three recap questions** and the next episode's one-line teaser.

### 3.4 The series: 14 episodes

Each card gives the **goal**, the **problems** (numbers from Parts 1 and 2), the **sources** to tick, the **key sentences**, the **demo** (commands and what to show), the **analogy**, the **limits to say**, and **recap questions**.

#### Episode 0. The idea: a promise and a check (6 min)
- **Goal:** explain contract, conformance, and clrsig in plain words. **Problems:** none yet (Part 0). **Sources:** Part 0, README.
- **Key sentences:** "The spec is a promise. Contract testing checks the promise against what the server really sends. Conformance testing checks that the whole API behaves like the spec says." "clrsig builds requests from the spec, sends them, and compares every answer."
- **Demo:** start the practice server (`docker run --rm -p 8080:8080 api-workbench-sandbox`), run `clrsig conform specs/ok.yaml -b http://localhost:8080/ok --env clrsig/environments/ok.yaml`: all green (65 operations). Then run one failing fixture to show the difference: `clrsig conform specs/contract-fail.yaml -b http://localhost:8080/contract-fail --paths /cases/resp-005-missing-required-field`.
- **Analogy:** a restaurant menu (the spec) and the plate that arrives (the response). A food inspector compares them.
- **Limits to say:** a green run only means "nothing wrong in what was checked".
- **Recap questions:** What is the difference between contract and conformance testing? What does the exit code `1` mean? Where do the practice fixtures live?

#### Episode 1. The envelope: status, Content-Type and headers (7 min)
- **Problems:** P01 to P04. **Sources:** Part 1 group A (first half), Part 2 same, `docs/contract-fail-cases.md`.
- **Key sentences:** "Before the body, check the envelope." "A `Content-Type` mismatch stops all body checks, so fix it first."
- **Demo (all against `/contract-fail`):** `resp-001-undeclared-status` (500 not declared), `resp-001b-default-response-ok` (a `default` response makes it legal), `resp-002-wrong-content-type`, `resp-003-missing-required-header`, `resp-004-wrong-header-type`. Add `--explain` once to show the plain-language reason.
- **Analogy:** a parcel: the label (headers) must match before you open the box.
- **Limits:** undeclared extra headers are not reported (`CS-GAP-003`).
- **Recap:** Why do clients care about undeclared status codes? Why is the body not compared when the `Content-Type` is wrong? How do you make a `500` legal in the spec?

#### Episode 2. The body: fields, types, rules (8 min)
- **Problems:** P05 to P12. **Sources:** Part 1 and 2 group A (second half), `docs/contract-fail-cases.md`.
- **Key sentences:** "Required, type, rule: the three questions for every field." "`oneOf` fails as one message, not as a list of fields." "`writeOnly` leaks are a security problem, not a style problem."
- **Demo:** `resp-005-missing-required-field`, `resp-006-wrong-field-type`, `resp-006b-array-for-object`, `resp-007-enum`, `resp-007c-pattern`, `resp-009-oneof-no-match`, `resp-010-extra-property-closed` vs `resp-010b-extra-property-open` (open schema is legal), `resp-011-writeonly-leak`, `resp-multi-problem` (only the first problem).
- **Analogy:** a form: required boxes, the right kind of answer in each box, and rules like "at most 5 letters".
- **Limits:** formats like `uri` are not validated (`CS-GAP-001`): show `gap-format-uri` passing. `email` and `uuid` are (`resp-007g-format-email-uuid` fails with CS-RESP-007 since clrsig 0.9.0).
- **Recap:** What is the difference between a missing field and a wrong type? When is an extra field legal? Why can a `oneOf` error message not name a field?

#### Episode 3. Odd but valid, and broken JSON (8 min)
- **Problems:** P13, P14, P15, P16. **Sources:** Part 1 and 2 groups B and C (first part), `docs/conform-fail-cases.md` (the `hostile-*` rows).
- **Key sentences:** "A good checker accepts everything that is correct, even when it looks strange." "Strict JSON means: valid UTF-8, nothing after the closing brace, no `NaN`."
- **Demo (`/conform-fail/hostile/*`):** pass: `deep-nesting`, `unicode`, `integer-as-float`, `big-integer`, `gzip`, `chunked-stream`. Fail: `bom`, `invalid-utf8`, `trailing-garbage`, `nan-literal`, `raw-newline-in-string`. Special: `duplicate-keys` (last wins), `float-overflow` (its own finding `CS-RESP-015`).
- **Analogy:** handwriting: some handwriting is ugly but readable (accept), some is unreadable (reject), and some letters can be read two ways (the standard does not say).
- **Limits:** for a BOM and duplicate keys the standards are open; clrsig chose strict.
- **Recap:** Name two valid-but-unusual bodies. Why is trailing text a problem? What does `CS-RESP-015` mean?

#### Episode 4. Time and unstable servers (8 min)
- **Problems:** P17, P18, P19, P37 to P42. **Sources:** Part 1 and 2 groups C (rest) and G, `docs/conform-fail-cases.md`.
- **Key sentences:** "A correct answer that comes too late is a failure." "`--max-response-time` keeps the response and compares it; a timeout gives you nothing to compare." "Flaky means: you need several calls to see it."
- **Demo (run it in the container, not on a busy laptop; to save time start the server with `LATENCY_SCALE=0.2`):** `latency-over-limit` (`--max-response-time 50`), `slow` (`--request-timeout 1500`), `truncated-body`, `connection-reset`, `redirect-loop`, then the sequences `flaky-every-third-call`, `rate-limited-after-three-calls`, `unavailable-then-ok`, `degrading-latency`.
- **Analogy:** a waiter: right dish, but 45 minutes late; or a waiter who forgets every third table.
- **Limits:** a limit is per path prefix, not per method of one path (`CS-GAP-005`). Timing needs a quiet machine.
- **Recap:** What is the difference between `slow-response` and `no response`? Why does a flaky bug need a sequence? How can a retry after a timeout cause duplicates?

#### Episode 5. When the spec and the server disagree (7 min)
- **Problems:** P20 to P25. **Sources:** Part 1 and 2 group D, `docs/conform-fail-cases.md`.
- **Key sentences:** "Either the code or the spec is wrong. Find out which, but never silence the check." "A route that is not in the spec is invisible to a spec-walking tool."
- **Demo:** `/conform-fail/ghost`, `/orphan`, `/wrong-method`, `/path-param/{id}`, `/requires-extra-header`; the scenario `conform-fail-routes.yaml` for `/undocumented` (`CS-NC-001`). Then the forms: `/form` and `/multipart` pass (clrsig builds the bodies); `POST /ok/features/xml-note` shows the XML gap.
- **Analogy:** a map and the road: the map shows a bridge that is not there, or the road has a tunnel the map does not show.
- **Limits:** callbacks and webhooks are not exercised (`CS-GAP-010`); XML bodies are not built (`CS-GAP-006`).
- **Recap:** Which direction can the disagreement go? How would you find an undocumented route? Which body types does clrsig build?

#### Episode 6. When the test is wrong, not the server (6 min)
- **Problems:** P26 to P30. **Sources:** Part 1 and 2 group E, `docs/conform-fail-cases.md` (the `req-*` and `run-*` rows).
- **Key sentences:** "A good tool tells you when the test is wrong, and does not send the bad request." "`not sent` is not a server failure."
- **Demo:** the environments in `clrsig/environments/` named `conform-fail-bad-values`, `conform-fail-missing-value`, `conform-fail-bad-function`, `conform-fail-unset-var`; show each message. Show `clrsig validate` on a scenario with a bad function.
- **Analogy:** calling a friend with the wrong number: the friend did nothing wrong.
- **Limits:** none worth a slide; mention the exit code `2` vs `1`.
- **Recap:** What does `not sent` tell you? How do you give a value from the command line? Why is a bad scenario variable worse than a bad step?

#### Episode 7. Servers that accept too much: negative probes (8 min)
- **Problems:** P31 to P36. **Sources:** Part 1 and 2 group F, `docs/conform-fail-cases.md` (the `probes` part).
- **Key sentences:** "A good server says no. Negative probes check the no." "The cheapest security test is: ask without credentials."
- **Demo:** `--negative` on `/lenient/missing-field` (accepted, `201`) vs `/strict/missing-field` (refused, `400`); `/lenient/wrong-type`, `/lenient/missing-query`, `/lenient/no-auth`. Then the scenario `ok-credentials-and-session.yaml`: unknown, expired, read-only and writer tokens.
- **Analogy:** a bouncer who checks your ticket vs one who waves everybody in.
- **Limits:** only the *absence* of credentials is probed (`CS-GAP-008`); no enum or boundary probes (`CS-GAP-009`).
- **Recap:** What status do you expect to a missing required field? Name two credential mistakes clrsig does not probe by itself. How do you cover them?

#### Episode 8. State and business rules with scenarios (8 min)
- **Problems:** P43 to P46. **Sources:** Part 1 and 2 group H, `clrsig/scenarios/conform-fail-business-rules.yaml`, `conform-fail-write-bugs.yaml`.
- **Key sentences:** "Every response can be valid and the behavior still wrong." "Write the rule as a step that asserts the **correct** behavior; the step fails where the server is wrong."
- **Demo:** run `clrsig run clrsig/scenarios/conform-fail-business-rules.yaml --env clrsig/environments/conform-fail.yaml --spec specs/conform-fail.yaml`; show `an order above the stock is refused` fail, the stock `-3`; the idempotency and lost-update scenario. Show `extractions` (carry an id) and `failPolicy: continue`.
- **Analogy:** a bank: each receipt looks right, but the balance is wrong.
- **Limits:** the tool checks the rules you write down.
- **Recap:** Why can a schema check not find a negative stock? What does `failPolicy: continue` do? Why is a retry after a timeout dangerous?

#### Episode 9. Change: diff and impact (7 min)
- **Problems:** P47, P48, P49. **Sources:** Part 1 and 2 group I (first part), `docs/diff-cases.md`, `specs/diff/`.
- **Key sentences:** "Not every change is equal: breaking, warning, info." "Put `diff` in the pull request."
- **Demo:** `clrsig diff specs/diff/removed-endpoint/v1.yaml specs/diff/removed-endpoint/v2.yaml` (exit 1); `renamed-field`; `description-changed` (nothing); `--fail-on warning` on `optional-param-removed`. Then `clrsig impact` on `impact-hit` with the scenarios in `clrsig/scenarios/impact/`.
- **Analogy:** a recall notice: which products does the change affect, and which customers bought them.
- **Limits:** compares specs, not the real server.
- **Recap:** Which change levels exist? What does `impact` add to `diff`? Where do you run it?

#### Episode 10. Drift, baselines and coverage (7 min)
- **Problems:** P50, P51. **Sources:** Part 1 and 2 group I (second part), `docs/conform-fail-cases.md`, `specs/coverage/`.
- **Key sentences:** "A baseline lets you adopt the tool today: known problems are accepted, new problems fail." "Coverage tells you what you have not proven."
- **Demo:** write a baseline with the server at drift 0 (`docker run -e DRIFT=0 ...`, then `--write-baseline`), restart it at drift 1 (`-e DRIFT=1`) and run with `--baseline`: `Baseline: 3 known, 1 new, 0 fixed`, exit 1. Then `clrsig coverage quality` on the coverage fixture: the four signals.
- **Analogy:** a debt plan: the old debt is listed, new debt is not allowed, paid debt is celebrated.
- **Limits:** a baseline can hide a problem if nobody reads the numbers.
- **Recap:** What is a baseline for? What are the four coverage signals? Is a coverage gap a failure by default?

#### Episode 11. The spec file: broken, awkward and big (6 min)
- **Problems:** P52 to P55. **Sources:** Part 1 and 2 group J, `docs/conform-fail-cases.md` (the `hostile-spec-*` rows), `specs/hostile/`.
- **Key sentences:** "A broken spec stops the run with exit `2` and a clear message." "Awkward but valid specs must still work."
- **Demo:** `clrsig generate specs/hostile/missing-ref.yaml --dry-run` (exit 2), `duplicate-operation-id.yaml`; then the valid ones: `circular-ref.yaml`, `discriminator.yaml` with `--negative` (probes for both branches); the 500-operation spec from `scripts/make_specs.py`.
- **Analogy:** a book with a missing page vs a book with a very long chapter.
- **Limits:** no valid spec is rejected today (the XML `example` case, F-034, was fixed in v0.8.6).
- **Recap:** What does exit code `2` mean? Why start CI with `generate --dry-run`? Name one awkward-but-valid spec feature.

#### Episode 12. Blind spots and wrong answers (8 min)
- **Problems:** P56 to P60. **Sources:** Part 1 and 2 groups K and L, `docs/clrsig-gaps.md`, `docs/clrsig-findings.md`.
- **Key sentences:** "A green result means: nothing wrong in what was checked." "A test tool can lie. Test the tool."
- **Demo:** the "not compared" summary line from `conform-fail-spec-check-states.yaml`; the matrix of gaps; then three real stories: an id above 2^53 becoming `9.2e+18` (F-031); a failed extraction that exited `0` (F-032); an NDJSON response that failed in v0.8.5 (F-033, fixed in v0.8.6). Show `scripts/check_expectations.py` flipping when a release changes an answer.
- **Analogy:** a smoke detector: it is useless if nobody tests it.
- **Limits:** this episode is about limits. Keep the tone positive: the bugs were found because fixtures know the right answer, and most were fixed within days.
- **Recap:** What does a green run really mean? How do you protect yourself from a tool's bugs? Which things are outside OpenAPI?

#### Episode 13. Put it in CI: a recipe (7 min)
- **Problems:** all. **Sources:** Part 2 ("which command for which question"), `.github/workflows/ci.yml`, README.
- **Key sentences:** "Five steps: read the spec, test the server, probe the server, compare with main, remember the baseline." "Pin the version."
- **Demo:** show the repository's CI file: start the server, wait for `/health`, run the expectations, upload reports (`--format junit`). Then a minimal recipe for the viewer's own API:
  1. `clrsig generate openapi.yaml --dry-run` (the spec loads);
  2. `clrsig conform openapi.yaml -b $URL --env ci.yaml --negative` (server and probes);
  3. `clrsig diff openapi.yaml --against origin/main` (no breaking change);
  4. `clrsig run scenarios/ --spec openapi.yaml` (the business rules);
  5. `--baseline known.yaml` to adopt gradually.

  AI agents can run step 2 through the clrsig MCP server's `conform` tool instead of the command line.
- **Analogy:** an airport: ID check, security, boarding pass, each step catches different things.
- **Limits:** CI needs a running test server and test data that resets (`POST /__admin/reset` in the practice server).
- **Recap:** Which step catches a removed endpoint? Why pin the clrsig version? How do you adopt the tool on an API with many problems?

### 3.5 Glossary (use these exact one-line meanings in the narration)

| Word | One line |
|---|---|
| OpenAPI spec | A file that describes an API: its URLs, requests and responses. |
| Contract | The promise in the spec about what the API sends and accepts. |
| Contract testing | Checking that real answers match the promise. |
| Conformance testing | Checking that the whole API behaves like the spec says. |
| Operation | One method on one path, for example `GET /orders/{id}`. |
| Schema | The shape of JSON: fields, types, rules. |
| Required / optional | Must be there / may be missing. |
| `oneOf` / `anyOf` | The body may have one of several shapes. |
| `nullable` | The value may be `null`. |
| `writeOnly` | A field you may send but the API must never return. |
| Status code | The number in the answer: `200` ok, `404` not found, `500` server error. |
| Header | Extra information with the request or the answer. |
| Placeholder `{{name}}` | A value filled in from your environment file. |
| Environment file | The values clrsig uses in the requests it builds. |
| Negative probe | A request that is wrong on purpose. |
| Scenario | A script of steps with checks after each step. |
| Assertion | One check in a step, for example "status is 200". |
| Extraction | Taking a value from one answer to use in the next request. |
| Baseline | A saved list of known problems. |
| Drift | The code and the spec slowly stop matching. |
| Breaking change | A spec change that can break existing clients. |
| Coverage | How much of the API your tests reached. |
| Check ID | A code such as `CS-RESP-005` for one kind of problem. |
| Exit code | The number a command returns: `0` ok, `1` a finding, `2` the setup is broken. |
| False pass / false alarm | The tool says OK when it is not / says "problem" when it is fine. |

### 3.6 Instructions to paste into NotebookLM

**Series instructions** (paste into the customize box of every Video or Audio Overview):

> You are explaining API contract testing and conformance testing to working developers who have little testing background. Use simple, concrete language and short sentences. Explain each technical word once. Start with a short everyday story, then show the problem, why it hurts, and how the tool `clrsig` finds it. Use only facts that are in the selected sources. Quote the real `clrsig` output lines and the real fixture names (for example `/contract-fail/cases/resp-005-missing-required-field`). Do not invent commands, flags, check IDs or results. Say that results are for clrsig v0.11.0. End with the limits: what the tool does not see in this topic. End with three recap questions. Keep a friendly, calm tone. Do not read tables aloud; say the one point that matters.

**Episode focus** (add one line after the series instructions, taken from the episode card), for example:

> Focus on episode 2: the response body (problems P05 to P12): required fields, wrong types, rule violations, `oneOf`, extra fields, `writeOnly` leaks. Use the fixtures `resp-005` to `resp-011` and `resp-multi-problem`. About 8 minutes.

**If NotebookLM drifts**, use these corrections in the focus box: "Use only the selected sources." "Do not say clrsig finds everything; say what it does not see." "Use the exact check IDs from the sources." "Shorter: one idea per minute."

### 3.7 How to split the guide into sources for NotebookLM

Make one text or Markdown source per episode by copying the headings below into separate files named `ep00.md` to `ep13.md`, plus the shared parts.

| Source file | Copy these parts |
|---|---|
| `ep00.md` | Part 0 |
| `ep01.md` | Part 1 group A, P01 to P04, and the same problems in Part 2 |
| `ep02.md` | Part 1 and 2 group A, P05 to P12 |
| `ep03.md` | Part 1 and 2 groups B and C, P13 to P16 |
| `ep04.md` | Part 1 and 2: P17 to P19 (group C) and group G (P37 to P42) |
| `ep05.md` | Part 1 and 2 group D, P20 to P25 |
| `ep06.md` | Part 1 and 2 group E, P26 to P30 |
| `ep07.md` | Part 1 and 2 group F, P31 to P36 |
| `ep08.md` | Part 1 and 2 group H, P43 to P46 |
| `ep09.md` | Part 1 and 2 group I, P47 to P49 |
| `ep10.md` | Part 1 and 2 group I, P50 and P51 |
| `ep11.md` | Part 1 and 2 group J, P52 to P55 |
| `ep12.md` | Part 1 and 2 groups K and L, P56 to P60, and `docs/clrsig-gaps.md` |
| `ep13.md` | Part 2 ("which command for which question") and the CI file |

Add the glossary (3.5) to every source so the words are explained in each episode.

### 3.8 Recording the demos and checking the facts

**Set up once**
1. Install clrsig v0.13.4 (`scoop install clrsig`, `brew install fuvito/api-workbench/clrsig`, or the Docker image `ghcr.io/fuvito/api-workbench:v0.13.4`) and check `clrsig --version`.
2. Build and start the practice server: `docker build -t api-workbench-sandbox .` then `docker run --rm -p 8080:8080 api-workbench-sandbox`. Do **not** set `ADMIN_TOKEN` for the demos (the scenarios reset the server without a token).
3. Use a large terminal font, a dark theme with high contrast, and show **one command and its output per screen**.
4. Reset the server between demos: `curl -X POST http://localhost:8080/conform-fail/__admin/reset` (and `/ok/__admin/reset`).
5. For slow fixtures, start the server with `-e LATENCY_SCALE=0.2` to shorten delays; say on screen that the real delays are longer. Timing results are only reliable in the container.
6. Windows: if you use Git Bash, set `MSYS_NO_PATHCONV=1` so paths such as `/latency/` are not rewritten.

**Check the facts before you publish**
- [ ] The clrsig version on screen equals the version in the notes (`clrsig --version`).
- [ ] Every command in the episode ran as shown, and the output matches what the narration says. The expected results are in `docs/*-cases.md`; to check everything at once run `uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml` (about 3 minutes; all must say `ALL AS EXPECTED`).
- [ ] No claim says clrsig finds "everything". Each episode names its limits.
- [ ] F-033, F-034 and F-035 are fixed in v0.8.6; if you quote them, say "found, then fixed".
- [ ] No secrets on screen: the credentials in the examples are fake test values (`test-token`, `test-user`, `test-pass`, `test-api-key`).
- [ ] The date and version are in the video description.

### 3.9 After publishing

- Keep the guide and the expectations in step: when a new clrsig release changes an answer, `check_expectations.py` fails; update the expectation, the guide, and re-record only the affected episode (the episode cards say which problems each one covers).
- Pin the version in the video description: "Recorded with clrsig v0.13.4".
