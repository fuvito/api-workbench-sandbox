# contract-fail: expected outcomes

Generated from `expectations/contract-fail.yaml` by `uv run python scripts/check_expectations.py --expectations expectations/contract-fail.yaml --table`; do not edit by hand. Outcomes are for `clrsig` v0.7.1 and assume the F-010 spec copy (see `docs/clrsig-findings.md`). A case that "passes" is a control, a known gap, or a "not checked" outcome pinned on purpose.

| Case | Path (under `/contract-fail`) | Expected | Check | Exit code | ClearSignal reports (or why it passes) |
|---|---|---|---|---|---|
| `control-ok` | `/cases/control-ok` | passes | none | 0 | a fully conforming response |
| `resp-001b-default-response-ok` | `/cases/resp-001b-default-response-ok` | passes | CS-RESP-001 | 0 | an undeclared status covered by a default response counts as declared |
| `resp-010b-extra-property-open` | `/cases/resp-010b-extra-property-open` | passes | CS-GAP-002 | 0 | an extra property on an open schema is legal in OpenAPI |
| `resp-001-undeclared-status` | `/cases/resp-001-undeclared-status` | fails | CS-RESP-001 | 1 | answered 500, but the spec declares only 200, 404 |
| `resp-002-wrong-content-type` | `/cases/resp-002-wrong-content-type` | fails | CS-RESP-002 | 1 | Content-Type "text/plain" |
| `resp-003-missing-required-header` | `/cases/resp-003-missing-required-header` | fails | CS-RESP-003 | 1 | header "X-Total-Count" is required by the spec but was not sent |
| `resp-004-wrong-header-type` | `/cases/resp-004-wrong-header-type` | fails | CS-RESP-004 | 1 | has a value that does not fit the spec |
| `resp-005-missing-required-field` | `/cases/resp-005-missing-required-field` | fails | CS-RESP-005 | 1 | property "id" is missing |
| `resp-006-wrong-field-type` | `/cases/resp-006-wrong-field-type` | fails | CS-RESP-006 | 1 | value must be a number |
| `resp-006b-array-for-object` | `/cases/resp-006b-array-for-object` | fails | CS-RESP-006 | 1 | value must be an object |
| `resp-nested-wrong-type` | `/cases/resp-nested-wrong-type` | fails | CS-RESP-006 | 1 | value must be an integer |
| `resp-007-enum` | `/cases/resp-007-enum` | fails | CS-RESP-007 | 1 | not one of the allowed values |
| `resp-007b-minimum` | `/cases/resp-007b-minimum` | fails | CS-RESP-007 | 1 | number must be at least 0 |
| `resp-007f-maximum` | `/cases/resp-007f-maximum` | fails | CS-RESP-007 | 1 | number must be at most 100 |
| `resp-007c-pattern` | `/cases/resp-007c-pattern` | fails | CS-RESP-007 | 1 | doesn't match the regular expression |
| `resp-007c-minlength` | `/cases/resp-007c-minlength` | fails | CS-RESP-007 | 1 | minimum string length is 3 |
| `resp-007c-maxlength` | `/cases/resp-007c-maxlength` | fails | CS-RESP-007 | 1 | maximum string length is 5 |
| `resp-007c-minitems` | `/cases/resp-007c-minitems` | fails | CS-RESP-007 | 1 | minimum number of items is 1 |
| `resp-007c-uniqueitems` | `/cases/resp-007c-uniqueitems` | fails | CS-RESP-007 | 1 | duplicate items found |
| `resp-007d-null-not-nullable` | `/cases/resp-007d-null-not-nullable` | fails | CS-RESP-007 | 1 | Value is not nullable |
| `resp-007e-bad-datetime` | `/cases/resp-007e-bad-datetime` | fails | CS-RESP-007 | 1 | format "date-time" |
| `resp-008-invalid-json` | `/cases/resp-008-invalid-json` | fails | CS-RESP-008 | 1 | invalid character |
| `resp-008b-empty-body` | `/cases/resp-008b-empty-body` | fails | CS-RESP-008 | 1 | EOF |
| `resp-009-oneof-no-match` | `/cases/resp-009-oneof-no-match` | fails | CS-RESP-009 | 1 | doesn't match schema due to |
| `resp-poly-discriminator-wrong` | `/cases/resp-poly-discriminator-wrong` | fails | CS-RESP-009 | 1 | doesn't match schema due to |
| `resp-010-extra-property-closed` | `/cases/resp-010-extra-property-closed` | fails | CS-RESP-010 | 1 | property "extra" is unsupported |
| `resp-011-writeonly-leak` | `/cases/resp-011-writeonly-leak` | fails | CS-RESP-011 | 1 | writeOnly property "password" in response |
| `resp-012-xml-valid` | `/cases/resp-012-xml-valid` | passes | CS-NC-009 | 0 | application/xml has no decoder: the body is not compared and nothing is reported |
| `resp-multi-problem` | `/cases/resp-multi-problem` | fails | CS-RESP-003 | 1 | header "X-Total-Count" is required |
| `gap-format-email-uuid` | `/cases/gap-format-email-uuid` | passes | CS-GAP-001 | 0 | formats other than date-time are not validated |
| `gap-undeclared-header` | `/cases/gap-undeclared-header` | passes | CS-GAP-003 | 0 | a header the spec never mentions is not reported |
| `gap-slow-response` | `/cases/gap-slow-response` | passes | CS-GAP-005 | 0 | no response time is measured (the case waits 5 s, times LATENCY_SCALE) |
| `nc-002-no-content-declared` | `/cases/nc-002-no-content-declared` | passes | CS-NC-002 | 0 | the spec declares no response content, so any body is accepted |
| `nc-octet-stream` | `/cases/nc-octet-stream` | passes | CS-NC-003 | 0 | a binary media type has no structure to compare |
| `nc-no-content-type` | `/cases/nc-no-content-type` | passes | CS-NC-008 | 0 | a body without Content-Type is read as JSON leniently |
