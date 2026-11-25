# clrsig commands and flags exercised here

Beyond the check catalog, the fixtures pin what each `clrsig` command and flag does. The entries are in `expectations/ok.yaml` (section `runs`) and run with the other expectations in CI; when a release changes a flag, the entry flips and the file changes with it. Verified with `clrsig` v0.11.0.

| Command or flag | What is pinned | Entry |
|---|---|---|
| `conform --read-only` | only GET and HEAD are sent: 33 of 65 run, 32 are skipped | `conform-read-only` |
| `conform --tags` / `--paths` that match nothing | v0.8.9: `NOTHING CHECKED` and exit 2 (it was PASSED, exit 0); all operations skipped by `--read-only` is `NOTHING CHECKED` with exit 0 | `conform-tags-matches-nothing`, `conform-paths-matches-nothing`, `conform-read-only-checks-nothing` |
| `conform --tags` | `--tags products` runs 12 operations, skips 53 | `conform-tags` |
| `conform --explain` | adds `[CS-RESP-001] ...` and a reason under the failure | `conform-explain` |
| `conform --format github` | v0.10.0: a `::error file=...,line=N,title=CS-RESP-005 ...::` annotation on the spec line of the failed operation | `conform-format-github` |
| `conform --fail-on` | v0.9.0: only `failure` or `warning` are valid; anything else is exit 2 | `conform-fail-on-invalid` |
| `validate --spec` | v0.11.0: lints the OpenAPI document; the ok spec is clean. A `required` property that is not declared is an error (CS-SPEC-002); a missing `operationId` (CS-SPEC-001) and an example that breaks its format (CS-SPEC-003) are warnings, which fail only with `--strict` | `validate-spec-*` (documents in `specs/lint/`) |
| `validate --strict` | v0.9.1: lints a scenario beyond plain validation; the CRUD scenario is clean, an extraction nobody uses fails | `validate-strict-*` |
| `config show`, `--config`, `clrsig.yaml` | v0.9.1: the project file supplies spec, environment, base URL and `readOnly`; `config show` says where each value comes from | `config-show-*`, `conform-from-the-project-file` (`clrsig/fixtures/project/`) |
| `init --dry-run` | v0.9.1: lists what it would create | `init-dry-run-writes-nothing` |
| `init --spec` | v0.13.0: names the values the spec needs and says they would be listed as comments | `init-lists-the-values-the-spec-needs` |
| `conform --list` | v0.13.0: sends nothing (it runs against a closed port) and names the missing values; a flag that needs requests, such as `--negative`, is exit 2 | `conform-list-sends-nothing`, `conform-list-refuses-negative` |
| an empty value in `conform` | v0.13.0: empty in a path value, bearer token, API key or basic user name is "not sent"; an empty basic password is sent (CS-GAP-013) | `conform-an-empty-*` |
| `conform --paths` with a path parameter | v0.13.1: `{id}` and `{{id}}` select the same operations and negative probes (F-036) | `paths-with-a-parameter-written-*` |
| what reports quote (`conform` in five formats, `run --format json`) | v0.13.2: a response that breaks its schema is not quoted, so the token in it is not in the report; the missing field is still named (CS-RUN-011) | `*report-does-not-quote-the-token*` in `ok-features.yaml` |
| `conform --setup` | v0.9.1: a login scenario's extraction fills `{{token}}`; without it the operation is not sent; a failed setup is exit 2 and nothing is checked | `conform-without-the-setup-is-not-sent`, `conform-setup-supplies-the-token`, `conform-failed-setup-*` |
| `conform --changed-against` | v0.10.0: nothing changed against `HEAD` is `NOTHING CHECKED`, exit 0; an unknown git ref is exit 2 | `conform-changed-against-*` |
| `conform --write-baseline` with a filter | v0.10.0: refused, exit 2 | `write-baseline-is-refused-for-a-limited-run` |
| `run --format github` | v0.11.0: a summary notice (and an annotation per failed step) | `run-format-github` |
| `conform --fail-fast` | stops at the first violation (8 operations, 1 failed) | `conform-fail-fast` |
| `conform --max-response-time` | `slow-response`, CS-RESP-014 | `expectations/conform-fail.yaml` (`latency-over-limit`, `degrading-latency`, ...) |
| `conform --max-response-time-for` | a limit per path prefix (v0.8.8): it loosens, tightens or turns off (`0`) the global limit under `/latency`; another prefix changes nothing | `latency-path-limit-*` in `conform-fail.yaml` |
| `conform --negative`, `--paths`, `--format json/junit` | probes follow the filter and reach the reports (CS-PROBE-005) | `probe-005-*` in `conform-fail.yaml` |
| `conform --baseline`, `--write-baseline` | the drift ratchet (CS-RUN-006) | the `drift` section of `conform-fail.yaml` |
| `run --seed` | the same seed gives the same random value (33 for seed 7, 12 for seed 8), however the scenario path is written | `run-seed-7`, `run-seed-7-relative-path`, `run-seed-8` |
| `run --var` | replaces an environment variable for one run | `run-var-overrides-the-environment` |
| `run --timeout` | overrides every step timeout (CS-RUN-003) | `run-timeout-flag` |
| `run --coverage` | appends the operations the scenario exercised (16 of 65) | `run-coverage` |
| `run --format markdown/html/junit` | the three report formats | `run-format-*` |
| `run --fail-fast` | the second scenario is not run after the first fails | `run-fail-fast-stops-after-the-first-failing-scenario` |
| `run` without `--spec` | steps are not compared with the spec (CS-NC-005) | `nc-005-no-spec` in `conform-fail.yaml` |
| step `validateSpec: false`, a step that gets no response | counted as "not compared" in the summary (CS-NC-004, CS-NC-006) | `nc-004-*`, `nc-006-*` |
| `validate` | a good scenario is OK; a bad function in a step, and in the scenario's own variables, is reported (CS-RUN-007) | `validate-*` |
| `request` | runs one saved request file | `request-a-saved-request-file` |
| `import postman` | converts a collection (`--dry-run` lists the files); a non-collection exits 2 | `import-postman-*` |
| `bundle validate`, `bundle run` | one file with environments, requests and scenarios; an unknown field exits 2 | `bundle-*` |
| `generate` | the number of requests built per spec, and which carry a body | the `generation` section of every file |
| `diff`, `impact`, `coverage` | spec changes, scenario impact, coverage signals | `diff.yaml` and the `coverage` section |

## Not exercised, and why

- `import insomnia`, `bundle import`, `bundle export`, `run --workspace`, `--report` to a file: file-writing commands; the formats they write are the ones pinned above.
- `init` and `init github-actions --write` without `--dry-run`: file-writing commands.
- `--changed-against` with a changed operation: it needs two committed versions of a spec, and CI checks out one commit.
- `--fail-on warning`: in v0.13.0 every response finding is a failure, so no fixture can produce a warning from `conform`.
- `--ca-cert`, `--client-cert`, `--client-key` (TLS, mutual TLS): the server speaks plain HTTP on one port. Phase 6 (Cloud Run) is the first place TLS is involved.
- `mcp` (an MCP server over stdio), `telemetry`, `completion`: not behavior of an API under test.
- `--show-extracted`: needs a secret-looking extraction; the `oauth2` scenario extracts an access token, which clrsig masks (`***`) in its output.

Questions found while building these entries were recorded in `docs/clrsig-findings.md` and are closed with v0.8.4: F-023 (an undefined `{{name}}` was sent by `run`; now not sent, `run-001b-*`), F-024 (`--seed` and the path spelling), F-025 (a `TRACE` operation was dropped).
