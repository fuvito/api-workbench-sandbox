# KT — Phase 5: expectations and CI

## What exists

| Piece | Where | Role |
|---|---|---|
| Expectation files | `expectations/{ok,contract-fail,conform-fail,diff}.yaml` | what ClearSignal must report; one per family, the format is described in each header |
| Runner | `scripts/check_expectations.py` | runs ClearSignal, compares, exits 1 on any mismatch (unexpected pass, other check, other exit code) |
| Workflow | `.github/workflows/ci.yml` | pytest, then the expectation runs against the Docker container |

`expectations/ok.yaml` is new: one whole-spec run where only `GET /preferences` (F-008) and `GET /lookup` (F-009) may fail, the five `ok` scenarios (every step passes) and the 44 probes (all pass). When those two findings are fixed, the `failing` list must be emptied in the same change.

## The workflow

- **`pytest`** job: `uv sync --frozen`, `uv run pytest` (675 tests, about 2 minutes).
- **`expectations`** job: install `clrsig`, build and start the image, poll `/health` of all three families, run the four files. The container (not a process on the runner) is used because timing expectations need it.
- **Which `clrsig`:** pushes and pull requests use the release pinned in `CLRSIG_VERSION` (v0.7.1, downloaded from the `api-workbench` release into `$RUNNER_TEMP`, because the repo has its own `clrsig/` directory). The nightly run (03:17 UTC) builds `api-workbench@main` with Go 1.26. A manual run can pick either (`gh workflow run ci.yml -f clrsig=main`).

Two questions, kept apart: a red push or PR means a change here broke a fixture; a red nightly means ClearSignal changed. Updating the pin and the expectations that encode known bugs is one change.

## Verified (2026-11-22)

- First run failed: the download wrote a file called `clrsig` where the checkout has a directory of that name. Fixed by downloading elsewhere.
- Released leg: pytest 675 passed; `ok`, `contract-fail`, `conform-fail` (on the runner, about 100 s) and `diff` all ALL AS EXPECTED.
- `main` leg run by hand: built from `api-workbench@main`, all four ALL AS EXPECTED, so `main` behaves like v0.7.1 on these fixtures today.
- Not verified: the cron trigger itself has not fired yet; neither leg has been shown to turn red on a real regression in CI (the runner's detection was shown locally with deliberate mistakes in every expectation file).

## Limits to know

- Timing expectations assume a Linux container; if CI runners get slow, `conform-fail` timing entries are where flakiness would show first.
- Failures print the mismatching case but not which `clrsig` commit the nightly built; the build step logs `api-workbench@<sha>` for that.
- The expectations hold for v0.7.1. When a `clrsig` release changes behavior, the nightly goes red until the release is pinned and the affected expectations (F-003 to F-020) are updated.
