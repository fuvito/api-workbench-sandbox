# KT — Phase 4c: requests that do not fit, and runs that cannot happen

Third slice of `conform-fail`. Here the **server and the spec are fine**. What goes wrong is the request ClearSignal builds (from the spec plus an environment file) or the run itself. `specs/conform-fail.yaml` goes from 23 to 25 operations.

## Why the cases need operations of their own

Reusing an operation that already fails for another reason would mix two conditions in one case. So two small, correct operations under `/requests` exist only to be driven by the environment:

- `GET /requests/param-type/{itemId}`: an integer path parameter. Correct for any integer; a declared `400` otherwise.
- `POST /requests/body-value`: a body with `amount`, a number with **no example**, so ClearSignal fills it from the environment variable `amount` (properties that have an example never reach the environment).

With the right environment (`clrsig/environments/conform-fail.yaml`: `itemId=7`, `amount=19.99`) both pass. The only thing that changes between a pass and each failure is the environment file.

## The cases (all in `expectations/conform-fail.yaml` under `runs:`)

| Case | How | Result today |
|---|---|---|
| Wrong parameter type | `conform-fail-bad-values.yaml`: `itemId=abc` | CS-REQ-001: `request` finding, "path parameter "itemId" does not fit the spec: value abc" (the request is still sent and the server's declared 400 is fine) |
| Wrong body value | same file: `amount=cheap` | CS-REQ-002: `request` finding, but the message is a JSON syntax error (F-017) |
| Missing placeholder | `conform-fail-missing-value.yaml`: neither variable defined | CS-RUN-001: `missing-value` finding, "not sent: no value for {{itemId}}"; the server log shows no request |
| Bad dynamic function | env value `{{$noSuchFunction}}` | CS-RUN-002: same kind `missing-value`, "unknown function $noSuchFunction", exit 1 |
| Bad dynamic function, in a scenario | `conform-fail-bad-function.yaml` scenario | exit **2**, the whole scenario aborts before any step, no JSON (F-016) |
| Server down | `-b http://localhost:1` | CS-RUN-003: `no-response` finding, exit 1 |
| Unreadable spec | invalid YAML, valid YAML that is not OpenAPI, a missing file, a URL that returns 404 | CS-RUN-004: exit **2** with a clear message, in all four forms |
| Unset `${NAME}` | `conform-fail-unset-var.yaml` | CS-RUN-005: a warning, exit code unchanged (0) |

Every wrong environment is named for its defect, starts with a comment saying it is DELIBERATELY wrong, and lives next to the right one. Unreadable specs are in `clrsig/fixtures/` and are never served. A test per file checks it is wrong in exactly the intended way (the bad-values file differs from the right one only in the two values; the unset-variable file names a variable nobody sets).

## Runner: the `runs` section

`scripts/check_expectations.py` gained `runs`: whole ClearSignal commands with `{spec}`, `{base}` and `{root}` placeholders, an expected exit code, an optional `finding` (kind plus a regex over the messages), an `output` regex over everything printed, a `passed` flag, and `unset` (process variables removed from the command's environment, which is how the CS-RUN-005 case is guaranteed to have an unset variable). The case tables now include a commands table.

## What the exit codes show

ClearSignal separates *failures* (exit 1: an operation did not conform, a request was not sent, no response) from *errors* (exit 2: the spec cannot be read, or a scenario is invalid). The only surprise is the scenario with a bad function, which is an error and not a failure (F-016).

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 547 passed (36 new: both operations on valid and invalid input, every environment file and fixture is wrong exactly as intended, the spec declares the operations and their 400s).
- Runner, conform-fail: 10 response cases, whole spec 7 of 25 operations fail (the same seven as before: the new operations pass), 3 scenario steps, request generation (25 requests), 11 commands, 32 probes over 17 operations, all as expected. Drift check: five deliberate mistakes in the commands section produced five mismatches and exit 1.
- While writing the tests I found and fixed a bug of mine: the parameter handler used `str.isdigit()` and rejected `-5`, a valid integer.

## ClearSignal findings raised

- **F-016**: a bad function in a scenario aborts the run with exit 2 (the catalog describes only the failure form); CS-RUN-001 and CS-RUN-002 share a finding kind.
- **F-017**: a wrong-typed body value is reported as "invalid character 'c' looking for beginning of value", with no field name or expected type.

## Watch-outs

- The messages for the OS-dependent cases vary: a missing file says "The system cannot find the file specified" on Windows and something else elsewhere, so that expectation matches only the stable prefix (`reading spec: open `).
- `run-003` relies on nothing listening on `localhost:1`.
- `run-005` must never run with `CLRSIG_UNSET_FIXTURE_VAR` set; the runner removes it from the command's environment.
- Remaining slices: timing and instability (`/slow`, `/flaky`, `/rate-limited`, jitter, degrading latency, hang, redirect loop, large response, unavailable-then-OK), then drift, diff, coverage and business-rule failures.
