# conform-fail: expected outcomes (response cases; probes are in the expectations file)

Generated from `expectations/conform-fail.yaml` by `uv run python scripts/check_expectations.py --expectations expectations/conform-fail.yaml --table`; do not edit by hand. Outcomes are for `clrsig` v0.7.1 and assume the F-010 spec copy (see `docs/clrsig-findings.md`). A case that "passes" is a control, a known gap, or a "not checked" outcome pinned on purpose.

| Case | Path (under `/conform-fail`) | Expected | Check | Exit code | ClearSignal reports (or why it passes) |
|---|---|---|---|---|---|
| `ghost` | `/ghost` | fails | CS-RESP-001 | 1 | answered 404, but the spec declares only 200 |
| `orphan` | `/orphan` | fails | CS-RESP-001 | 1 | answered 405, but the spec declares only 204 |
| `wrong-method` | `/wrong-method` | fails | CS-RESP-001 | 1 | answered 405, but the spec declares only 200 |
| `path-param-type` | `/path-param/{id}` | fails | CS-RESP-001 | 1 | answered 400, but the spec declares only 200 |
| `requires-extra-header` | `/requires-extra-header` | fails | CS-RESP-001 | 1 | answered 400, but the spec declares only 201 |
| `form-body` | `/form` | fails | CS-REQ-002 | 1 | request body does not fit the spec: value is required but missing |
| `multipart-body` | `/multipart` | fails | CS-REQ-002 | 1 | request body does not fit the spec: value is required but missing |
| `subscribe-with-callback` | `/subscribe` | passes | CS-GAP-010 | 0 | the callback is not exercised and the server never contacts it |
