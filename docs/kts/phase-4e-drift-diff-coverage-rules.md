# KT — Phase 4e: drift, spec changes, coverage signals and business rules

The last slice of Phase 4. `specs/conform-fail.yaml` goes from 47 to 56 operations; four new kinds of fixture sit beside it. Three of the notes' expectations turned out to be out of date, and two new findings came out (F-020, and coverage added to F-010).

## 1. Drift and the baseline ratchet

`python -m app --drift=<n>` (or `DRIFT=<n>`; the flag wins) sets a level at startup and it never changes while the server runs: there is no mode-switching endpoint. `GET /conform-fail/drift/report` is correct at drift 0 and returns `total` as a string at drift 1 or higher (one new violation, CS-RESP-006). An invalid level is refused by argparse (exit 2).

The ratchet uses `clrsig conform --baseline` and `--write-baseline` on a few operations (`/ghost`, `/orphan`, `/wrong-method`, `/drift/report`), observed in v0.7.1:

| Step | Result |
|---|---|
| record a baseline at drift 0 | exit 0, "3 violations recorded" |
| run at drift 0 against it | exit 0, "3 known, 0 new, 0 fixed" |
| run at drift 1 against it | exit **1**, "3 known, **1 new**, 0 fixed" and `NEW GET /conform-fail/drift/report` (CS-RUN-006) |
| record at drift 1 (4 violations), run at drift 0 | exit 0, "3 known, 0 new, **1 fixed**" and a `FIXED` line |
| a baseline file that does not exist | exit 2 |

The runner (`run_drift`) starts one real server per drift level on a free port with `python -m app --drift=<n>` and stops them afterwards, so the check also proves the flag works on a real process. Tests cover the flag and the variable, and that the flag wins.

## 2. Spec against spec (`clrsig diff` and `clrsig impact`)

13 pairs under `specs/diff/<case>/v1.yaml` and `v2.yaml`, written from one small base API (the same `v1` in every pair) with one change each; `expectations/diff.yaml` records oasdiff's exact change ids and the exit code at `--fail-on breaking`, `warning` and `info`. No server is involved.

| Level | Cases |
|---|---|
| ERR (CS-DIFF-001) | `removed-endpoint`, `new-required-request-field`, `optional-to-required-param`, `enum-value-removed`, `renamed-field`, `type-narrowed` |
| WARN (CS-DIFF-002) | `optional-param-removed` (exit 0 / 1 / 1) |
| INFO (CS-DIFF-003) | `deprecated-operation`, `endpoint-added`, `non-success-response-removed` |
| nothing | `description-changed` |
| impact | `impact-hit`, `impact-placeholder-path` (the pairs the scenarios use) |

`clrsig impact` is checked with three scenarios in `clrsig/scenarios/impact/`: a literal id, a `{{userId}}` placeholder in the path, and a control calling untouched operations; also the whole folder at once.

**Where the notes were out of date (the catalog and v0.7.1 agree with each other):**
- `deprecated-operation` is **INFO** in oasdiff (`endpoint-deprecated`), not WARN. The WARN case is a removed optional parameter.
- `impact-placeholder-path` was to "pin CS-GAP-007" (a placeholder in the step URL is missed). The gap is **closed**: the placeholder step is matched like the literal one (CS-IMP-001).

## 3. Coverage signals

A scenario that deliberately leaves one gap of each kind, with a four-operation subset of the strict group (`specs/coverage/coverage.yaml`, a faithful copy of those operations; a test asserts it). Run into a fresh workspace, `clrsig coverage quality --format json` gives exactly: never exercised `POST /strict/wrong-type` (CS-COV-001); happy path only `GET /strict/missing-query` (CS-COV-002) with its declared 400 never triggered (CS-COV-003); secured never authenticated `GET /strict/no-auth` (CS-COV-004). The control operation, answered 201 and 400, has no signal.

Two surprises: coverage has the **same problem as F-010** (with the standard spec it matches no operation: 0% covered and four "never exercised"), and the command **exits 1 when it finds gaps** while the catalog says coverage signals never change an exit code (**F-020**).

## 4. Business rules the server breaks

Seven rules, each broken in a way the spec does not describe, under `/conform-fail/rules/*`. The spec declares the correct rule (the 409, 422 or 401 it lists); every handler validates its input strictly (so the negative probes still pass) and breaks exactly one rule:

| Rule | The server | How it shows |
|---|---|---|
| stock never negative | accepts any quantity; the stock goes to -3 | steps "an order above the stock is refused" and "the stock stays at zero or more" fail |
| a shipped order cannot be cancelled | answers 200 | "a shipped order cannot be cancelled" fails (409 expected) |
| unique email | accepts the duplicate | "a duplicate email is refused" fails |
| insufficient funds is a 422 | answers **200 with an error body** | the step fails, and `conform` also reports CS-RESP-005 (the body has no `id`): the only one of the seven the contract check sees |
| stable pagination | page 1 makes another writer insert at the head; page 2 repeats `i-3` | "page 2 does not repeat the last item of page 1" fails |
| expired token refused | `expired-token` is accepted | "an expired token is refused" fails |
| stale `If-Match` | ignored | the existing `PUT /lost-update` scenario |

So, as the notes say, six of the seven are invisible to conformance and contract checks and need scenario assertions. State lives in the family store and is bounded; reset restores it (a test checks every collection).

## Runner changes

`--section` runs only some parts (`cases,whole,scenarios,generation,runs,sequences,coverage,drift,probes`); a no-server `diff` family; `run_diffs`, `run_impacts`, `run_coverage`, `run_drift`; a diff table generator.

## A slip of mine, found and fixed

Patching the runner with an inline script put a literal newline inside a `print("...")`, which broke the script; the docs generator that ran next then wrote **empty** case tables over `docs/conform-fail-cases.md` and `docs/contract-fail-cases.md`. I noticed because the files had become 4 lines long, fixed the script, regenerated all three tables, and checked that the contract-fail table is byte-identical to the committed one. Lesson: a generator that overwrites files must fail loudly when its input command fails (the regeneration now asserts a non-empty result).

## ClearSignal findings raised

- **F-020:** `coverage quality` exits 1 on gaps, contrary to the catalog.
- **F-010 extended:** coverage also silently matches nothing for specs with `servers`.

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 675 passed (61 new): every business-rule handler and its broken rule asserted exactly, input validation kept strict, reset restoring every collection, the drift level through `Settings` and through a real process with `--drift` and `DRIFT` (the flag wins; an invalid level exits 2), the 13 diff pairs share one base and each really differs, and the coverage spec is a faithful subset.
- `expectations/diff.yaml` (no server): 13 pairs with exact change ids and the three exit codes, and 4 impact cases, all as expected.
- `expectations/conform-fail.yaml` against the Docker container, 124 s: all as expected, including the 56 generated requests, 18 of 56 operations failing in the whole-spec run, 3 scenarios (3, 10 and 13 steps with their expected outcomes), coverage (one gap of each kind), drift (six steps over real servers at drift 0 and 1) and 43 probes over 24 operations. `expectations/contract-fail.yaml` is unchanged, and the container stops with exit code 0.
- Drift check: three mistakes in `diff.yaml` and three in `conform-fail.yaml` (a scenario step, the never-exercised operation, the drift-1 baseline result) produced three mismatches each.

## Phase 4 is functionally complete

Across 4a to 4e: `conform-fail` has 56 operations, three scenarios and an expectations file with nine sections (cases, sequences, whole spec, commands, coverage, drift, generation, scenarios, probes), next to the server-free `expectations/diff.yaml`. Eighteen ClearSignal findings are open (F-003 to F-020). What is left for Phase 4 is the exit review (README and task-list pass, an overview KT note, and the decision on how the expectations runner moves into CI in Phase 5).
