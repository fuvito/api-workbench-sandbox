# KT — Moving to ClearSignal v0.11.0

This note covers releases 0.9.0 to 0.11.0: what changed an outcome, what was added to the fixtures, and what is still not pinned.

## What changed an outcome

- **0.9.0 checks `email` and `uuid` formats.** `gap-format-email-uuid` now fails (CS-RESP-007) and is named `resp-007g-format-email-uuid`. A `uri` case, `gap-format-uri`, is the CS-GAP-001 fixture. `contract-fail` has 36 cases; a plain `conform` reports 26 of 37 operations failing.
- **0.10.0 records a baseline from a full run only.** `--write-baseline` with `--paths`, `--tags` or `--changed-against` is refused; the expectations that did this changed to match.

## What was added

| Feature | Fixture | Entries in `expectations/ok.yaml` |
|---|---|---|
| `validate --spec` (CS-SPEC-001 to 003) | `specs/lint/` (not served) | `validate-spec-*` |
| `validate --strict` on a weak scenario | `conform-fail-failed-extraction.yaml` | `validate-strict-reports-an-unused-extraction` |
| Project file, `config show`, `init --dry-run` | `clrsig/fixtures/project/clrsig.yaml` | `config-show-*`, `conform-from-the-project-file`, `init-*` |
| `conform --setup` | `ok-setup-login.yaml`, `ok-features-no-token.yaml` | `conform-*setup*` |
| `conform --changed-against` | `specs/hostile/only-post.yaml` | `conform-changed-against-*` |
| Refused `--write-baseline` | the `contract-fail` spec | `write-baseline-is-refused-for-a-limited-run` |

All behaved as the release notes and the catalog say. No finding was added.

## Things to remember

- `--changed-against HEAD` is pinned on a spec that nobody edits: with `ok.yaml` the entry would fail while someone is editing that spec.
- The runner matches `output` against stdout followed by stderr. The `--setup` message ("values available to the check") is on stderr, so it comes after the summary.
- `args` are passed through Python's `format`, so a literal brace there must be doubled; `output` and `not_output` are plain regular expressions.
- The project file sits in `clrsig/fixtures/project/`, not at the repository root: a root `clrsig.yaml` would silently give every other command its defaults.
- Not pinned: `--changed-against` with a changed operation (needs history; CI checks out one commit), `--fail-on warning` (no `conform` finding is a warning yet), and the desktop app's baseline and spec-health views.
