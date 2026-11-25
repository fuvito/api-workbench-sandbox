# KT — Moving to ClearSignal v0.13.0

## What changed an outcome

Nothing that was already pinned. The one behaviour change in 0.13.0: in `conform`, a value that is defined but **empty** now counts as missing in the URL path and in credentials (bearer token, API key, basic user name), so the operation is "not sent" and its negative probes are skipped. No environment file in this repository had such a value.

## What was added (`expectations/ok.yaml`)

| Feature | Entries |
|---|---|
| `conform --list` (sends nothing; refuses flags that need requests) | `conform-list-*` |
| `init --spec` names the needed values | `init-lists-the-values-the-spec-needs` |
| Empty path value, bearer token, API key, basic user name are not sent | `conform-an-empty-*-is-not-sent` |
| An empty basic password **is** sent (CS-GAP-013) | `conform-an-empty-basic-password-is-sent` |

## Things to remember

- The password entry pins a **gap**: the server refuses the login with a `401` that the spec declares, so the operation passes. It is expected to change if clrsig closes the gap.
- **F-036 is open:** with a path parameter in `--paths`, operations and negative probes match different spellings. Filter with a prefix that stops before the parameter.
- `conform-list-sends-nothing` pins counts (25 ready, 40 not sent without an environment); a change to the `ok` spec's operations changes them.
