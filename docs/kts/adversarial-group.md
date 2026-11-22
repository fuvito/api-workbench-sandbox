# KT — The adversarial group: trying to break clrsig

Written 2026-11-22 for `clrsig` v0.8.4. Read this to see what was tried, what broke, and where it is pinned.

## Why

Every fixture before this tested something somebody thought of in advance (a catalog ID, an OpenAPI feature, a flag). The findings that mattered most came from poking at what nobody had planned. This group is that poking, kept: bounded, deterministic, and pinned in the expectations like everything else. It is **part of `conform-fail`** (PRD 5.4), not a fourth family: same prefix, store, reset and spec.

Rule for undefined behavior: where no standard says what clrsig should do (a duplicate JSON key, a BOM), the observed behavior is pinned with a note and is **not** called a bug. Where a standard is clear (invalid UTF-8, text after the JSON value), it is a finding.

## What it is

| Part | Where | What |
|---|---|---|
| Hostile responses | `app/conform_fail/hostile.py`, `GET /conform-fail/hostile/<case>` (20 operations; `conform-fail` is now 76) | deep (200 levels) and wide (20000 keys) JSON, unicode, `1.0` / `1e2` / above-int64 integers, `-0`, a BOM, invalid UTF-8, a raw newline in a string, `NaN`, trailing text, duplicate keys, `1e400`, a lone surrogate, gzip and a gzip lie, duplicate headers and cookies, a 60 KB header, a chunked body |
| Hostile documents | `specs/hostile/` (14 files), `hostile-spec-*` runs | circular `$ref`, recursive `allOf`, a discriminator with a mapping, 60-branch `oneOf`, an unsatisfiable `allOf`, a 120-level schema, odd paths, no paths, a JSON document, `openapi: 3.2.0`, and three invalid ones (missing `$ref`, duplicate operationId, undeclared path parameter) |
| Scale | `scripts/make_specs.py` `big_spec(500)`, `scale-500-*` runs | generate, diff and `conform --negative` on 500 operations, each under a time budget (`max_seconds`); 2000 operations take 0.3 s |
| Random specs | `scripts/fuzz_specs.py`, CI step (60 seeds) | random valid OpenAPI 3.0.3 documents; clrsig must load, generate, build every probe against a closed port and diff each with itself, with no crash or hang. 900 seeds were run when it was written: no failure |
| Scenario robustness | `clrsig/scenarios/conform-fail-edge-assertions.yaml` | JSON paths and headers on the hostile bodies, integers beyond 2^53, extractions that find nothing |

## What it found (all open, `docs/clrsig-findings.md`)

| Finding | Summary | Severity |
|---|---|---|
| F-026 | A body that is not valid UTF-8 passes | false pass |
| F-027 | Text after the JSON value is ignored by `conform` (a scenario rejects the same body) | false pass |
| F-028 | A valid JSON number beyond float64 is a failure with no check ID and a Go error message | false failure |
| F-029 | The probe summary says PASSED when every probe errored (exit code 1) | misleading |
| F-030 | A scenario sees only the first value of a repeated header (and the first `Set-Cookie`) | limitation |
| F-031 | Integers above 2^53 are rounded and printed as `9.2e+18` by `jsonpath` assertions and **extractions**, so a chained request sends a corrupted id | data corruption |
| F-032 | A failed extraction exits 0 and the headline says PASSED, next to "1 failed" in the same report | false pass |

F-031 and F-032 are the serious ones: a CI job that chains requests with extracted ids, or trusts the exit code of `run`, is wrong in both.

## What held

Everything unusual but valid passed: deep and wide JSON, unicode, `1.0` and `1e2` as integers, `-0`, gzip, duplicate headers, a 60 KB header, chunked bodies; every hostile document loaded or failed with a clean message (exit 2); 900 random specs and 2000 operations caused no crash; `TRACE` and `openapi: 3.2.0` work. A BOM and duplicate keys are strict and defensible.

## Not covered

- A fuzzer on the *server* side of conformance (random specs with a server that answers them): the random specs run only against a closed port.
- Concurrency inside clrsig, Windows versus Linux differences, and clrsig's own memory use (only elapsed time is bounded).
- HTTP/2, trailers, 1xx responses and `HEAD` with a body: not reachable through the server stack used here.
