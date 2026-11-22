# spec against spec: expected `clrsig diff` and `clrsig impact` outcomes

Generated from `expectations/diff.yaml` by `uv run python scripts/check_expectations.py --expectations expectations/diff.yaml --table`; do not edit by hand. Outcomes are for `clrsig` v0.8.5.

| Pair (`specs/diff/<case>/v1.yaml`, `v2.yaml`) | Highest level | Check | Exit code at --fail-on breaking / warning / info | Changes reported |
|---|---|---|---|---|
| `removed-endpoint` | ERR | CS-DIFF-001 | 1 / 1 / 1 | api-path-removed-without-deprecation |
| `new-required-request-field` | ERR | CS-DIFF-001 | 1 / 1 / 1 | request-property-became-required |
| `optional-to-required-param` | ERR | CS-DIFF-001 | 1 / 1 / 1 | request-parameter-became-required |
| `enum-value-removed` | ERR | CS-DIFF-001 | 1 / 1 / 1 | request-parameter-enum-value-removed |
| `renamed-field` | ERR | CS-DIFF-001 | 1 / 1 / 1 | response-required-property-added, response-required-property-removed |
| `type-narrowed` | ERR | CS-DIFF-001 | 1 / 1 / 1 | response-property-type-changed |
| `optional-param-removed` | WARN | CS-DIFF-002 | 0 / 1 / 1 | request-parameter-removed |
| `deprecated-operation` | INFO | CS-DIFF-003 | 0 / 0 / 1 | endpoint-deprecated |
| `endpoint-added` | INFO | CS-DIFF-003 | 0 / 0 / 1 | endpoint-added |
| `non-success-response-removed` | INFO | CS-DIFF-003 | 0 / 0 / 1 | response-non-success-status-removed |
| `description-changed` | none | none | 0 / 0 / 0 | nothing |
| `impact-hit` | ERR | CS-DIFF-001 | 1 / 1 / 1 | api-path-removed-without-deprecation |
| `impact-placeholder-path` | ERR | CS-DIFF-001 | 1 / 1 / 1 | api-path-removed-without-deprecation |

### clrsig impact

| Case | Pair | Check | Exit code | Steps that call a breaking change |
|---|---|---|---|---|
| `step-with-a-literal-id` | `impact-hit` | CS-IMP-001 | 1 | calls-removed-endpoint.yaml: Fetch user 1 |
| `step-with-a-placeholder-in-the-path` | `impact-placeholder-path` | CS-IMP-001 | 1 | calls-removed-endpoint-placeholder.yaml: Fetch a user by variable |
| `control-steps-on-untouched-operations` | `impact-hit` | none | 0 | none |
| `the-whole-folder-at-once` | `impact-hit` | CS-IMP-001 | 1 | calls-removed-endpoint.yaml: Fetch user 1; calls-removed-endpoint-placeholder.yaml: Fetch a user by variable |
