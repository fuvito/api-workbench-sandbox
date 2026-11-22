# KT — Phase 4a: lenient server and negative probes

First slice of `conform-fail`. Where `contract-fail` has wrong *responses*, this family has wrong *behavior*: here a server that accepts requests it should reject, found by `clrsig conform --negative`.

## What ClearSignal's probes do

`--negative` sends four kinds of deliberately wrong request and passes a probe when the server answers 4xx (catalog 2.2):

| Probe | Sends | ID |
|---|---|---|
| missing required field | a body without one required field | CS-PROBE-001 |
| wrong field type | a body with one field of the wrong type | CS-PROBE-002 |
| missing required query parameter | no value for a required query parameter | CS-PROBE-003 |
| missing credentials | no credentials on a secured operation | CS-PROBE-004 |

Not probed today (CS-GAP-008, 009): wrong credentials, enum and boundary values, unknown fields, wrong header or path-parameter types.

## The design: each lenient case breaks exactly one probe

`specs/conform-fail.yaml` has seven operation pairs, `/lenient/<x>` and `/strict/<x>`, with identical declarations. Only the server differs (`app/conform_fail/lenient.py`):

| Pair | Lenient server skips | Fails | Strict server |
|---|---|---|---|
| `missing-field` | the presence check on `name` (types still checked) | CS-PROBE-001 | rejects |
| `wrong-type` | the type check on `quantity` (presence still checked) | CS-PROBE-002 | rejects |
| `missing-query` | the required `q` | CS-PROBE-003 | rejects |
| `no-auth` | credentials entirely | CS-PROBE-004 | 401 unless `test-token` |
| `wrong-auth` | the token value (a missing token is still 401) | none: CS-GAP-008 | 401 unless `test-token` |
| `enum-and-boundary` | enum and maximum (presence and types still checked) | none: CS-GAP-009 | rejects |
| `unknown-fields` | the closed schema (everything else checked) | none: CS-GAP-009 | rejects |

So `clrsig conform --negative` over the whole spec reports 26 probes, exactly 4 failing (one per probe kind), and the exit code is 1. A lenient operation that failed two probe kinds would break the "one condition per case" rule, which is why each one still enforces everything it is not meant to skip.

Handlers read the body by hand (`read_object`) because FastAPI or Pydantic validation would reject what these operations must accept. The three "gap" operations are the interesting pins: they are wrong, and ClearSignal does not notice. The day it starts probing wrong tokens, enums or unknown fields, `/lenient/wrong-auth`, `/lenient/enum-and-boundary` and `/lenient/unknown-fields` begin to fail and the expectations flag it.

## Expectations and the runner

`expectations/conform-fail.yaml` has a `probes` section: per operation, how many probes ClearSignal generates (`probes: N`), which must fail (with the catalog ID), or a `reference` to the gap it pins. Counting the probes is deliberate: when ClearSignal adds probe kinds the count changes and the file demands a review, which is how a closed gap gets noticed.

`scripts/check_expectations.py` was generalized in this slice: it now understands `cases` (response cases, any path), `scenarios` and `probes`, requires the expectations and the spec to cover the same paths (with an `ignore` list), and generalizes the whole-spec acceptance (exit 0 when no case should fail). The contract-fail results are unchanged.

## ClearSignal findings raised

- **F-013:** `--paths` and `--tags` skip the normal operations but not the probes: all 26 still run and the exit code reflects them. A probe cannot be isolated per case, so the runner runs `--negative` once and attributes probes to operations from the output.
- **F-014:** probes are absent from the JSON and JUnit reports (JUnit even says `failures="0"` while the run exits 1). The runner parses the text report.
- Together with F-010 (spec copy) and F-012 (no IDs), these mean the whole conform-fail verification is a harness around ClearSignal's text output until they are fixed. All of it is recorded in the findings file and deletable when closed.

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 498 passed (44 new: the matrix of what each lenient and strict operation accepts, that unreadable bodies are always 400, the twins declare identical requests, and no state is kept).
- Runner, conform-fail: plain `conform` passes all 15 operations; 26 probes over 14 operations; the four expected failures and nothing else. Contract-fail through the generalized runner: still all as expected.
- Drift check: a copy of the expectations with a wrong probe count, a wrong check ID, a strict operation claimed to fail and a wrong count for a gap case produced four mismatches and exit 1.

## Watch-outs

- Probe expectations depend on the exact probe wording in ClearSignal's text report (`missing required field 'name'`, `no credentials`, ...). A wording change shows up as a mismatch, not a silent pass.
- The bearer scheme is named `bearerAuth` so ClearSignal applies the token during the normal `conform` pass (it only recognizes bearer, F-005); `clrsig/environments/conform-fail.yaml` supplies `token: test-token`.
- The next slices (spec and server disagreement, request and run failures, timing, drift) will add `cases` to this file, so its response-case table will follow the contract-fail layout.
