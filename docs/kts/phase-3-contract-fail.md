# KT — Phase 3: `contract-fail`

The family whose responses are deliberately wrong, to exercise ClearSignal's API Contract Validation. 35 cases, each declared correctly in the spec and broken in exactly one way by the server. The most important result of this phase is not a case but a ClearSignal finding (F-010, below).

## Read this first: F-010

While testing the first case, every operation PASSED, including a `500` the spec does not declare. Reading ClearSignal's source showed why: response validation is silently skipped whenever the spec has a `servers` entry (and for scenario steps, whenever the URL path differs from the spec path, which a server base path always causes). Nothing in any output format says "not checked".

Consequences:
- Everything verified before this phase had its **request-side** checks but not its **response-side** checks. After building the workaround I re-ran `ok`: `conform` 63/65 (only F-008 and F-009), probes 44/44, all five scenarios pass. So the `ok` responses do conform, but that is now actually known, not assumed.
- The specs stay standard (`servers` present). `scripts/clrsig_spec_copy.py` writes a temporary copy with no `servers` and the base path baked into each path; `conform` runs on it with `-b http://localhost:8080`. It is a harness facility, not a fixture change, and is to be deleted when F-010 closes.
- Plain `clrsig conform specs/contract-fail.yaml` therefore reports 36/36 PASS. That is the bug, not a result.

## How a case works

```
specs/contract-fail.yaml          declares the CORRECT behavior, one operation per case
app/contract_fail/cases.py        one function per case, registered with @case("<slug>")
expectations/contract-fail.yaml   expected check, exit code and exact finding per case
scripts/check_expectations.py     runs everything and compares
docs/contract-fail-cases.md       the expected-outcome table (generated)
clrsig/scenarios/contract-fail-checkers.yaml   checker A and B side by side
```

- Paths follow `GET /contract-fail/cases/<check-id-lowercase>-<slug>`.
- Handlers build the bytes themselves (`json_response`, `Response`) so what goes on the wire is exactly the intended deviation, and everything else stays correct (a missing header case still has a correct body, a wrong Content-Type case still has valid JSON). `tests/test_contract_fail.py` asserts this for every case.
- `UNDOCUMENTED` holds routes the server has but the spec does not (`nc-undocumented-path`), for the "path not in the spec" outcome.
- No state: cases never touch a store, and `gap-slow-response` uses the bounded `deliberate_delay` (5 s times `LATENCY_SCALE`).

## The cases (full table: `docs/contract-fail-cases.md`)

| Group | Cases | Result |
|---|---|---|
| Controls | `control-ok`, `resp-001b-default-response-ok`, `resp-010b-extra-property-open` | pass |
| CS-RESP-001..006 | undeclared status, wrong Content-Type, missing and wrong-typed header, missing field, wrong type, array for object, nested wrong type (`lines[0].qty`) | fail with the matching check |
| CS-RESP-007 | enum, minimum, maximum, pattern, minLength, maxLength, minItems, uniqueItems, null not nullable, bad date-time | fail |
| CS-RESP-008 / 009 / 010 / 011 | invalid JSON, empty body, oneOf and discriminator mismatch, extra property on a closed schema, writeOnly leak | fail |
| Multi-problem | header and body both wrong | fails once, with the header (CS-RESP-003) first (CS-GAP-011) |
| XML | `resp-012-xml-valid` | **passes**: not checked (CS-NC-009) |
| Known gaps | email/uuid formats, undeclared header, slow response | pass: CS-GAP-001, 003, 005 |
| Not checked | no content declared, octet-stream, no Content-Type, undocumented path | pass: CS-NC-002, 003, 008, 001 |

## Decisions where the sources disagreed

- **XML (CS-RESP-012):** the source notes expected a false failure on valid XML; the current catalog (`what-we-check.md`) says it is "not checked" (CS-NC-009) since 0.6.0, and ClearSignal v0.7.1 behaves that way. I followed the catalog and observed behavior. Tell me if you want a different treatment.
- **`nc-204-with-body`:** HTTP forbids a body on a `204`, so the case is `nc-002-no-content-declared` (a `200` with no declared content and a body anyway), which is the catalog's CS-NC-002 as written ("204, or a description only").
- **Check IDs are not printed by ClearSignal** (F-012). A case is recognized by the JSON finding `kind`, its `where`, and a regex on the validator's message; the expectation file records all three.

## What the checkers do (verified)

`contract-fail-checkers.yaml` has one step per case with the step spec check (A, from `--spec`) and an explicit `schema` assertion (B, by operationId). Observed, matching the catalog: B ignores the status, Content-Type and headers (cases 001 to 004 pass B), does not look at `writeOnly` (011 passes B), and catches body problems (005 to 010 fail both). The one difference from the catalog: for an empty body B fails with "response body is empty" instead of "not checked" (F-011). B matches by operationId, so F-010 does not affect it.

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 454 tests (110 new for this family), all passing.
- `scripts/check_expectations.py`: 35 of 35 cases and 14 of 14 scenario steps as expected; the whole spec fails exactly the 25 expected cases. Breaking four expectations on purpose in a temporary copy made the runner report five mismatches and exit 1.
- The runner also passes against the Docker image at the default `LATENCY_SCALE` (the slow case really waits 5 s).

## ClearSignal findings raised

- **F-010** (serious): response checks silently skipped for specs with `servers`; the working copy is temporary.
- **F-011**: imprecise kinds and messages (oneOf as `missing-field`, root-level type mismatch as `other`, raw parser errors for invalid JSON and empty body, the empty-body catalog mismatch).
- **F-012**: no check ID in any report format.

## Watch-outs

- If you change a handler or the spec, the expectation file must still match ClearSignal's behavior, not the other way round. A mismatch means either you broke the case or ClearSignal changed.
- `gap-slow-response` makes the whole-spec run take 5 s (scaled).
- The expectations are for v0.7.1; they will need review on every ClearSignal release, which is what Phase 5's two CI legs are for.
- Phase 5 will move this runner into CI and add `local-only` / cloud overrides; its format already has room for them.
