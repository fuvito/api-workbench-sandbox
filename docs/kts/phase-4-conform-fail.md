# KT — Phase 4 overview: `conform-fail` and the spec-change fixtures

Read this first, then the five slice notes (4a to 4e). It says how the pieces fit, what to trust, and what is still open.

## What Phase 4 delivered

A family of fixtures where the server's *behavior*, the request ClearSignal builds, the run, or the spec itself is wrong. It is verified by one script against recorded expectations.

| Slice | Note | What |
|---|---|---|
| 4a | [phase-4a](phase-4a-lenient-and-probes.md) | lenient and strict operations for the negative probes (CS-PROBE-001 to 004) |
| 4b | [phase-4b](phase-4b-spec-server-disagreement.md) | spec and server disagree: ghost route, orphan, wrong method, path-parameter type, extra header, form/multipart, callback |
| 4c | [phase-4c](phase-4c-requests-and-runs.md) | requests that do not fit and runs that cannot happen (CS-REQ-001/002, CS-RUN-001 to 005) |
| 4d | [phase-4d](phase-4d-timing-and-instability.md) | timing, counters, transport cuts, large bodies, write bugs |
| 4e | [phase-4e](phase-4e-drift-diff-coverage-rules.md) | drift and the baseline ratchet, 13 spec-diff pairs, impact, coverage signals, business rules |

## How the verification is built

```
specs/*.yaml (standard, served)      ->  never edited to suit ClearSignal
specs/diff/<case>/v1,v2.yaml         ->  spec pairs, no server
clrsig/environments, scenarios, fixtures  ->  the wrong environments, the scenarios, the unreadable specs
expectations/<family>.yaml           ->  what ClearSignal must report, per case
scripts/check_expectations.py        ->  runs ClearSignal, compares, exits 1 on any mismatch
scripts/clrsig_spec_copy.py          ->  TEMPORARY copy workaround for F-010 (delete when it closes)
docs/*-cases.md                      ->  generated tables, never edited by hand
```

The runner understands nine kinds of expectation: response `cases`, `sequences` (state after a reset, call by call), `whole_spec` (one run, explicit failing list), `runs` (whole commands: exit code, finding, output), `scenarios` (step outcomes), `generation` (what `clrsig generate` builds), `probes` (parsed from the text report), `coverage` and `drift` (real servers per level). A separate no-server family covers `diff` and `impact`. Flags: `--section`, `--only`, `--cloud` (skip `local_only`), `--table`.

Every section was shown to detect drift: a copy of the expectations with deliberate mistakes must produce exactly those mismatches and exit 1.

## What to trust, and what not to

- **Response behavior is only verifiable through the spec copy** (F-010). A plain `clrsig conform specs/...` PASS means nothing for response correctness; coverage has the same problem.
- **Timing needs the Docker container.** A Windows host overshoots delays intermittently.
- **Check IDs are inferred** (F-012): ClearSignal prints none, so each case is recognized by finding kind, location and a regex on the validator's message.
- **Probes are read from the text report** (F-013, F-014).
- **`local_only` means "not verified on Cloud Run"**, not "does not work there". Phase 6 decides.

## Where the sources disagreed (resolved by following the catalog and observed behavior)

| Notes said | Actually (v0.7.1) |
|---|---|
| `resp-012-xml-valid` fails CS-RESP-012 | not checked (CS-NC-009) |
| `nc-204-with-body` | HTTP forbids a body on a 204: `nc-002-no-content-declared` |
| form/multipart bodies "pin CS-GAP-006" | the operations FAIL (F-015) |
| truncated body: CS-RUN-003 or CS-RESP-008 | CS-RUN-003 (no response) |
| `deprecated-operation` is WARN | INFO in oasdiff; the WARN case is a removed optional parameter |
| placeholder-in-path impact "pins CS-GAP-007" | the gap is closed; both steps match (CS-IMP-001) |
| coverage signals never change an exit code | `coverage quality` exits 1 on gaps (F-020) |

## ClearSignal findings (18 open, F-003 to F-020)

See `docs/clrsig-findings.md`; each has a repro and an expected result so it can be closed after a release. The serious ones: **F-010** (response validation silently skipped for specs with `servers`, also coverage), **F-015** (form/multipart operations fail although server and spec agree), **F-019** (a response over 50 MB is silently truncated and valid JSON fails as "unexpected EOF"). Improvement requests: **F-012** (no check IDs in output), **F-018** (no response-time assertion).

## Decisions still open (carried over)

1. The fake credentials (`test-token`, `test-user`/`test-pass`, `test-api-key`, `admin-token`) are in use but not confirmed.
2. Whether `GET /reports/{id}` needs a wall-clock delay or poll-count progression is enough.
3. Public versus private Cloud Run access, project and region (Phase 6).

## Numbers at the end of Phase 4

- `uv run pytest`: 675 tests.
- `expectations/conform-fail.yaml` against the Docker container: all as expected in about two minutes; `expectations/contract-fail.yaml` and `expectations/diff.yaml` as expected.
- Specs: `ok` 65 operations, `contract-fail` 36, `conform-fail` 56, 13 diff pairs.

## Next: Phase 5

Move the runner into CI: build and start the server, poll `/health`, run the expectation files, fail on any mismatch; one leg against released `clrsig`, one nightly against `api-workbench@main`; a cloud mode that skips `local_only`. The format already carries `local_only`, per-run arguments and `--cloud`; the open design question is how the expectations follow a ClearSignal release (they hold for v0.7.1 and several encode known bugs that should flip when fixed).
