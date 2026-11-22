# KT — Moving to ClearSignal v0.8.2

`clrsig` v0.8.2 fixed 18 of the 19 findings that were open with v0.7.1 (F-003 to F-021). This note says what changed in the repository, what stayed open, and what to remember. The earlier KT notes describe the v0.7.1 behavior and stay as written; where they disagree with this note, this note wins.

## What was checked

Every finding was rerun against v0.8.2 with its own repro (2026-11-22), then all five expectation files that need a server. 31 mismatches appeared, every one explained by a fix; none was a regression. Results per finding are in `docs/clrsig-findings.md`.

| Closed | F-003, F-004, F-005, F-006, F-007, F-008, F-009, F-010, F-011, F-012, F-013, F-014, F-015, F-017, F-018, F-019, F-020, F-021 |
|---|---|
| Open | F-016 (a bad function in a scenario step still aborts the run with exit 2; `conform` has its own kind now) |
| New | F-022 (the `writeOnly` finding has no `checkId`, kind `other`) |

## What changed in the repository

- **No more spec copy.** `scripts/clrsig_spec_copy.py` is deleted. The runner passes the standard spec (with `servers`) and `-b <base>/<family>`; `--paths` takes the spec's own paths (no family prefix); report paths have no prefix, so the runner adds it back.
- **`checkId` instead of guessing.** A failing case passes when the finding's `checkId` equals `check`. `kind` is optional and kept only where it adds something. `reported:` records a `checkId` that differs from the catalog's (`null` for the `writeOnly` case, F-022).
- **Expectations flipped:** `ok` conforms 65 of 65 (no `failing` list); `ok-31` 15 of 15; `form-body` and `multipart-body` pass (CS-REQ-003, CS-GAP-006 closed); the large-JSON case is CS-RESP-013 `body-too-large`; `coverage quality` exits 0; the bad-function kind is `dynamic-value-failed`.
- **New probes:** `--negative` now runs 62 probes on `ok` (was 44): both `oneOf` branches of `/payments` (16) and a missing `If-Match` on the two order edits. On `conform-fail`, `PUT /lost-update` gets the `If-Match` probe and it **fails**: the server ignores the header entirely, so it accepts a request without a required header (CS-PROBE-003). This is a real new detection, not a drift.
- **CI** pins `CLRSIG_VERSION: v0.8.2`; the nightly `main` leg is unchanged.
- Docs, scenario comments and the generated case tables were updated; the scenario step "The array as ClearSignal v0.7.1 writes it is rejected (F-009)" is now "A bracketed array is rejected".

## Verified (v0.8.2, Docker container)

`ok`, `ok-31`, `contract-fail`, `conform-fail` and `diff`: all as expected; `uv run pytest`: 690 passed. A deliberate wrong check and a wrong probe count were each reported as one mismatch.

## To remember

- `seeded-jitter-repeats` (a timing sequence) failed once in one full run and passed in the next; timing cases can still be flaky under load. Watch it in CI before changing anything.
- F-018 is closed and used: `degrading-latency` and `seeded-jitter-repeats` assert `slow-response` (CS-RESP-014) through `--max-response-time` with the same margins; new cases `latency-within-limit`, `latency-over-limit`, `slow-headers-over-limit`; `ok-latency` has a `duration` assertion. Cases where no response arrives (`slow`, `hang`, ...) still use request timeouts (CS-RUN-003).
- v0.8.2 expectations will not hold for v0.7.1 or older.
