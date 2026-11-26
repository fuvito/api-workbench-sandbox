# KT — Moving to ClearSignal v0.13.4

## What changed an outcome

One pinned result: in `contract-fail`, the step `resp-001-undeclared-status` has a `schema` assertion by `operationId` and the server answers an undeclared `500`. Up to v0.13.3 the assertion passed without reading the body; from v0.13.4 it fails. While the pin was still v0.13.3 the expected value was written down for both versions; now there is one again.

## What was added

| Pins | Entries |
|---|---|
| A `schema` assertion reads the body of an error answer, with no spec to catch it (F-038) | `a-schema-assertion-on-an-error-answer-is-checked` |
| No `<nil>` as an expected value (F-037) | `a-schema-assertion-has-no-nil-expected-value` |
| `generate` leaves a file with other content alone | `generate-does-not-replace-an-edited-file` |
| No probes is `NOTHING CHECKED` | `no-negative-probes-is-nothing-checked` |

## Things to remember

- `clrsig/fixtures/generate-in-the-way/getHealth.yaml` is meant to be in the way. A `clrsig` that overwrites it (v0.13.3 or earlier) **changes the file** when the check runs: restore it with `git checkout` after trying an old release.
- `schema-on-an-error.yaml` runs without `--spec` on purpose.
- F-037 and F-038 are closed; no finding is open.
