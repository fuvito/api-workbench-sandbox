# clrsig commands and flags exercised here

Beyond the check catalog, the fixtures pin what each `clrsig` command and flag does. The entries are in `expectations/ok.yaml` (section `runs`) and run with the other expectations in CI; when a release changes a flag, the entry flips and the file changes with it. Pinned for `clrsig` v0.8.4.

| Command or flag | What is pinned | Entry |
|---|---|---|
| `conform --read-only` | only GET and HEAD are sent: 33 of 65 run, 32 are skipped | `conform-read-only` |
| `conform --tags` | `--tags products` runs 12 operations, skips 53 | `conform-tags` |
| `conform --explain` | adds `[CS-RESP-001] ...` and a reason under the failure | `conform-explain` |
| `conform --fail-fast` | stops at the first violation (8 operations, 1 failed) | `conform-fail-fast` |
| `conform --max-response-time` | `slow-response`, CS-RESP-014 | `expectations/conform-fail.yaml` (`latency-over-limit`, `degrading-latency`, ...) |
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
- `--ca-cert`, `--client-cert`, `--client-key` (TLS, mutual TLS): the server speaks plain HTTP on one port. Phase 6 (Cloud Run) is the first place TLS is involved.
- `mcp` (an MCP server over stdio), `telemetry`, `completion`: not behavior of an API under test.
- `--show-extracted`: needs a secret-looking extraction; the `oauth2` scenario extracts an access token, which clrsig masks (`***`) in its output.

Questions found while building these entries were recorded in `docs/clrsig-findings.md` and are closed with v0.8.4: F-023 (an undefined `{{name}}` was sent by `run`; now not sent, `run-001b-*`), F-024 (`--seed` and the path spelling), F-025 (a `TRACE` operation was dropped).
