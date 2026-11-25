# KT — Moving to ClearSignal v0.12.0

This note covers releases 0.11.1 and 0.12.0.

## What changed an outcome

No expectation changed its result or exit code. One expected line changed wording:

- **0.12.0 counts operations that were never sent apart from failed ones.** `scale-500-conform-negative` sends none of its 500 operations, so its summary reads `0 failed · 500 not sent`. They still fail the run (exit 1).

## What else changed in these releases

- **0.12.0 names an operation by the spec's path** (`/users/{id}`) in Markdown, HTML, JUnit and coverage lists. JSON `path` keeps the generated request's `{{id}}` form, which `scripts/check_expectations.py` already normalizes, and gains `specPath`. No expectation depended on a changed name.
- **0.11.1 fixed the GitHub Action:** `fuvito/api-workbench/clrsig-action` was an old copy that ignored inputs such as `read-only` (this repository uses the root form, so it was not affected), and the download is now checked against the release's checksum.
- **0.11.1 added CS-GAP-012** to the catalog: a negative probe passes on any `4xx`. It is listed in `docs/clrsig-gaps.md`; no fixture pins it yet.

## Not pinned

- `specPath` and the spec-path names are covered by api-workbench's own tests, not by an expectation here.
