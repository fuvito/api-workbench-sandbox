# What clrsig does not do, and where this repo stands on it

A map of the things clrsig cannot cover (yet), so that when it learns one, the fixture is ready or its absence is a decision. Three kinds, because each is handled differently. Written 2026-11-22 for `clrsig` v0.8.5; the catalog gaps (CS-GAP-001 to 006 and 008 to 011) were rechecked 2026-11-24 with v0.11.0. Gaps and capabilities are checked against the catalog (`what-we-check.md`) and by running the fixtures, not assumed.

## 1. Gaps the catalog names (CS-GAP-001 to 011)

Each has a fixture pinned as "passes, because of CS-GAP-0xx". When clrsig closes one, that case flips and the expectation changes with it (`CLAUDE.md`: change an expectation only when ClearSignal's behavior changed).

| Gap | What clrsig does not do | Fixture that pins it | When it is closed |
|---|---|---|---|
| CS-GAP-001 | validate formats outside `date`, `date-time`, `email`, `uuid`, `ipv4`, `ipv6` and `byte` (for example `uri`, `hostname`). `email` and `uuid` are checked since clrsig 0.9.0 (case `resp-007g-format-email-uuid` now fails with CS-RESP-007) | `contract-fail` case `gap-format-uri` | the case fails with a format check |
| CS-GAP-002 | warn about extra properties on open schemas | `resp-010b-extra-property-open` | a strict mode reports it |
| CS-GAP-003 | report a response header the spec never mentions | `gap-undeclared-header` | the case fails |
| CS-GAP-004 | compare non-JSON bodies (XML and other types; CS-NC-009) | `resp-012-xml-valid`, `/features/report.csv` | a decoder exists |
| CS-GAP-005 | a response-time limit per operation: since v0.8.8 `--max-response-time-for /prefix=ms` sets one per path prefix (the longest prefix wins, 0 = off); there is still no way to set one for a single method of a path | `latency-path-limit-*` cases (the prefix override), `gap-slow-response` (no limit given: passes) | a per-method limit exists |
| CS-GAP-006 | build XML request bodies (JSON, form, multipart are built) | `POST /features/xml-note` (the request goes out without a body: `the request body does not fit the spec: value is required but missing`) | the body is generated |
| CS-GAP-008 | probe wrong, expired or under-privileged credentials (only "no credentials" is probed) | `/lenient/wrong-auth`, `/rules/protected`, `/features/credentials/*` (expired, unknown, read-only, writer tokens), scenario `ok-credentials-and-session.yaml` | probes for them are added |
| CS-GAP-009 | more negative probes (wrong header or path types, boundaries, enums, unknown fields) | `/lenient/enum-and-boundary`, `/lenient/unknown-fields` | the probes exist |
| CS-GAP-010 | exercise callbacks, webhooks and links | `subscribe-with-callback`, `webhooks` in `ok-3.1.yaml`, the `links` of `/features/items` | they are run |
| CS-GAP-011 | report more than the first problem per response | `contract-fail` case `resp-multi-problem` | all problems are listed |
| CS-GAP-012 | tell why a negative probe was refused: any `4xx` passes it, so a `401`, `404` or `429` can pass a missing-field probe although the body was never validated (in the catalog since clrsig 0.11.1) | — (no fixture pins it yet) | an unexpected `4xx` is reported differently |
| CS-GAP-013 | treat an empty value as missing outside paths and credentials (since clrsig 0.13.0 those are "not sent"): an empty basic password is still sent, and here the server's declared `401` then shows as a pass | `ok` run `conform-an-empty-basic-password-is-sent` | the operation is not reported as a pass |
| CS-GAP-017 | recognise every secret in what it quotes (since 0.13.2): a secret in a field with an ordinary name, too plain to look like a token, is quoted when it is the value that broke the spec | — (no fixture pins it yet) | a report no longer quotes the offending value |

## 2. Capabilities clrsig does not have (not in the catalog)

Observed or documented, not assumed. "Fixture" says what we have; "—" means there is none, on purpose.

| Capability | Status in clrsig | Fixture here |
|---|---|---|
| Cookie jar: a cookie set by one step is sent by the next | no; the `Set-Cookie` header can be extracted and sent back by hand | `/features/session/*`, scenario `ok-credentials-and-session.yaml` (steps `Session without sending the cookie back`, `Session with the cookie sent back by hand`) |
| Follow a `Link` header (RFC 8288) for pagination | no; the whole header is one extracted value, there is no parser | `/features/links/items`, the `First page` step |
| Extract part of a header or of a string (a regex) | no; only a JSONPath on the body, a whole header, or the status | `Log in` (the whole `Set-Cookie`) |
| An API-key credential in a cookie | the operation is called with it and, since v0.8.6, the "no credentials" probe removes it (F-035 closed) | `/features/session/me` |
| Interactive OAuth2 and OIDC flows, token refresh | no; `conform` sends a fixed token. A client-credentials exchange can be a scenario step | `/features/oauth2/token`, `oauth2-profile`, `openid-profile` |
| A response declared `application/x-ndjson` (or another type containing `json` that is not one document) | a single JSON document is not assumed since v0.8.6, so a valid NDJSON body passes (F-033 closed); the body is not compared line by line | `/features/events.ndjson` |
| TLS verification, mutual TLS | flags exist (`--ca-cert`, `--client-cert`, `--client-key`); the server here is plain HTTP | — (Phase 6 is the first place TLS appears) |
| WebSocket, server-sent events, gRPC, GraphQL | no; OpenAPI cannot describe the first three, and GraphQL has no OpenAPI form | — |
| HTTP/2 and HTTP/3 behavior, trailers, 1xx responses | not exposed by clrsig; the server stack here (uvicorn, HTTP/1.1) cannot produce them either | — |
| Concurrent load, rate-limit adherence over time | no; requests are sent one after another | `/rate-limited` (state by call count) |
| Server-side state across many users | no isolation test | — (the MVP shares state, README) |

A "—" is a decision, not a hole: a fixture for something clrsig cannot test has nothing to compare against, and its shape would be a guess. Add one when clrsig announces the capability.

## 3. Things this sandbox cannot do on Cloud Run

Transport behavior the platform's front end may change: a TCP reset, a connection cut, bodies over 32 MB. They are marked `local_only` in the expectations and skipped with `--cloud`. Phase 6 decides each one after it is tried on the deployed service.

## How to use this file

- Closing a gap in section 1: re-run the expectations on the release; the pinned case flips; update the expectation and the row.
- A new capability in section 2: build the fixture, move the row's "Fixture" cell, and add it to the expectations.
- Do not add a family of endpoints for section 2: a family needs a spec that is the source of truth, and most of these have none.
