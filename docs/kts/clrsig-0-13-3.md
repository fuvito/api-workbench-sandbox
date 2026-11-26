# KT — Moving to ClearSignal v0.13.3

## What changed an outcome

Nothing that was already pinned: the expectation files and the random-spec run held on the released v0.13.3.

- **Baselines (fix of a v0.13.2 bug):** with OpenAPI 3.1, v0.13.2 usually let a new problem pass when another problem of the same response was in the baseline. v0.13.3 lists every problem on its own, in a fixed order, and matches them one by one.
- **Security:** a password written inside a text (an address with credentials, `password=`, `Pwd=`) is masked. This does not find every secret (CS-GAP-017).

## What was added

| Pins | Entries |
|---|---|
| Two problems of one response, one line each, in order | `two-problems-are-listed-one-each-in-order` |
| A second problem is new; an unchanged response matches | `a-second-problem-is-not-hidden-by-the-baseline`, `an-unchanged-response-with-two-problems-matches-its-baseline` |
| Passwords masked in `run` reports | `run-report-masks-written-out-passwords-text` / `-json` |
| A password in a request value that does not fit | `req-002-does-not-print-a-password-text` / `-json` |

Run three times against the released v0.13.2, all seven new entries failed each time.

## Things to remember

- `clrsig/fixtures/baseline-one-problem.yaml` and `baseline-two-problems.yaml` were recorded with v0.13.3. Do not record them again with another version without reading what changes.
- The two problems come from `clrsig/fixtures/token-two-problems.yaml`, stricter than the unchanged token endpoint.
- The password entries use made-up values (`pw-canary-*`); they cover these ways of writing a password, not every one.
- The message checks accept the wording of v0.13.3 and a shorter one a later release may use.
- **F-038 is open:** a `schema` assertion passes a status it does not know.
