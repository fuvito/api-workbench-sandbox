# KT — Moving to ClearSignal v0.13.2

Takes in v0.13.1 and v0.13.2.

## What changed an outcome

Nothing that was already pinned: every expectation file, the random-spec run and pytest held on the released v0.13.2.

- **v0.13.1:** `--paths` selects the same operations and negative probes for `{id}` and `{{id}}`. F-036 is closed.
- **v0.13.2 (security):** reports no longer quote a response that breaks its schema. Up to v0.13.1 it was quoted in full, so a token the server had just sent was in the report.

## What was added

| Pins | Entries |
|---|---|
| Both spellings of a path parameter in `--paths` | `paths-with-a-parameter-written-*` in `expectations/ok.yaml` |
| The token is in no `conform` report (text, JSON, JUnit, HTML, Markdown) and the missing field is named | `report-does-not-quote-the-token-*` in `expectations/ok-features.yaml` |
| The same for a JSON `run` report, with a `schema` assertion that passes and one that fails | `run-report-does-not-quote-the-token` |

Run against the released v0.13.0, all eight new entries fail.

## Things to remember

- The leak entries use `clrsig/fixtures/token-endpoint-stricter.yaml` and `token-report.yaml` against the unchanged token endpoint. They run **without an environment file**: an older clrsig masks a value the environment holds, and the entry would then prove nothing.
- The rules for what is masked are rules of thumb (CS-GAP-017). These entries cover a token under a credential's name, not every secret.
- Markdown reports write `_` as `\_`.
- **F-037 is open:** a `schema` assertion in a JSON report says `"expected": "<nil>"`.
