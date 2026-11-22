# KT — Beyond the check catalog: OpenAPI features and CLI commands

Written 2026-11-22 for `clrsig` v0.8.3; updated the same day for v0.8.4, which fixed the three findings below. Read this to see what the fixtures cover outside the catalog's check IDs, and what they do not.

## What was added

- **Six catalog IDs that had no case** (CS-NC-004, -005, -006, CS-PROBE-005, CS-RUN-007, CS-GAP-004). The catalog (56 IDs) is now fully mentioned. New fixtures: `clrsig/scenarios/conform-fail-spec-check-states.yaml` and `conform-fail-bad-variable.yaml`; runs `run-007-*`, `nc-004/005/006-*`, `probe-005-*` in `expectations/conform-fail.yaml`. The runner gained `not_output` (a regex that must not match).
- **A second `ok` document, `specs/ok-features.yaml`** (19 operations, served at `GET /ok/openapi-features.yaml`, handlers in `app/ok/features.py`), one small operation per OpenAPI feature `ok.yaml` lacks: parameter styles (deepObject, pipeDelimited, spaceDelimited, label, matrix), allowEmptyValue, allowReserved, int64 / double / byte / password, multipleOf and exclusive bounds, `not`, `deprecated`, a response `link`, TRACE, text/csv, image/png, application/x-ndjson, a `components.requestBodies` reference, oauth2 and openIdConnect, top-level and tag `externalDocs`. It is a separate document so the 65-operation `ok` baseline did not change (the same choice as the 3.1 variant). Expectations: `expectations/ok-features.yaml` (19 of 19 operations, 18 probes, one scenario); CI runs it.
- **`webhooks` in `specs/ok-3.1.yaml`**: a 3.1 webhook is a request the API sends, so there is nothing to call; the document loads and the 15 operations are unchanged.
- **Commands and flags**: 21 entries under `runs` in `expectations/ok.yaml`, listed in `docs/commands-and-flags.md`.
- Tests: `tests/test_ok_features.py` (spec served and equal to the file, every operation routed, each feature strict).

## What it found (all closed in v0.8.4)

| Finding | Summary |
|---|---|
| F-023 | `clrsig run` sends a step whose `{{name}}` has no value, with the braces in the URL; `conform` does not send it (CS-RUN-001). |
| F-024 | `--seed` gives the same values only for the same spelling of the scenario path (`x.yaml`, `./x.yaml`, absolute: three results). |
| F-025 | A `TRACE` operation is silently left out of `conform` and `generate` (19 declared, 18 run, no SKIP line). |

The label and matrix styles were wrong in the first version of the server, not in `clrsig`: `style: label` with `explode: false` is `.1,2,3` (comma-separated), and `matrix` is prefixed with the parameter's own name (`;matrixIds=1,2,3`). `clrsig` checks path parameters against their style (CS-REQ-001) and said so; the server and the spec text were corrected, nothing was bent around it.

## Added later the same day: what clrsig cannot do (`docs/clrsig-gaps.md`)

A matrix of the catalog gaps (CS-GAP-001 to 011), capabilities clrsig lacks, and sandbox limits, each with the fixture that pins it. Three fixtures were added to `specs/ok-features.yaml` (26 operations now): **credentials** (`/features/credentials/profile`, `write-area`: valid, unknown, expired and read-only tokens, CS-GAP-008), a **cookie session** (`/features/session/login|me|logout`, an `apiKey` in a cookie, with a session seeded at every reset), **Link-header pagination** (`/features/links/items`), and an **XML request body** (`/features/xml-note`, CS-GAP-006, which had no fixture). Scenario: `clrsig/scenarios/ok-credentials-and-session.yaml`. Observed: clrsig keeps no cookie jar between steps and cannot follow a `Link` header or take part of a header value. Found with clrsig v0.8.5 and all fixed in v0.8.6: F-033 (an `application/x-ndjson` response is read as one JSON document and fails), F-034 (a valid XML `example` string is rejected, exit 2) and F-035 (the "no credentials" probe keeps an API key sent in a cookie).

## Not covered

- **Server variables** (`servers[].variables`): the served spec rewrites `servers[0].url` as plain text; a templated URL would break that rule.
- **External `$ref` files**: the spec is served as one URL, so it must be self-contained.
- **TLS and mutual TLS flags**: the server is plain HTTP; Phase 6 is the first place TLS is involved.
- **The oauth2 and openIdConnect URLs** in `ok-features.yaml` are absolute `http://localhost:8080/...`: under `PUBLIC_BASE_URL` (Cloud Run) they would point at the wrong host. ClearSignal does not call them, but Phase 6 should decide (relative URLs are valid in 3.1 only).
- Generated edge cases beyond one fixture per feature, large specs, and `mcp`.

## Numbers

- `ok-features`: 19 of 19 operations conform, 18 of 18 probes (v0.8.3: 18 of 18). `ok`: unchanged (65 operations, 62 probes); `runs` adds 21 command entries.
- Findings: F-023, F-024, F-025 were fixed in v0.8.4 and verified; none is open. With v0.8.4 `ok-features` is 19 of 19 operations (TRACE included), and the seed values are pinned (seed 7 gives 33, seed 8 gives 12).
