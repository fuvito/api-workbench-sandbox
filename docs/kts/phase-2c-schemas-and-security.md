# KT — Phase 2c: schema features, media types and security

Step 2 of the Phase 2 breadth work. `ok.yaml` grows from 29 to 43 operations. Each feature lives on a small, isolated resource so older resources and their checks do not change.

## What was added

| Feature | Where | Notes |
|---|---|---|
| Formats and patterns | `Customer`: `email`, `date`, `uuid`, phone `pattern`, `date-time` | server validates shape and real calendar dates (`2026-02-31` is rejected) |
| `nullable` | `Customer.birthDate` | the only nullable field; `null` anywhere else is 400 |
| Arrays | `Customer.tags`: `maxItems`, `uniqueItems`, non-empty strings | |
| Maps / `additionalProperties` | `Customer.preferences`, `GET/PUT /settings`, `GET /feature-flags` (booleans) | `maxProperties` enforced |
| `readOnly` | `Customer.id`, `createdAt` | sent in responses; a request carrying them is rejected (400) |
| `problem+json` | all `/customers` errors | `Content-Type: application/problem+json` with `type`, `title`, `status`, `detail`; other resources keep `{code, message}` |
| `default` and `4XX` responses | `/customers` operations | |
| `text/plain` | `GET /version` | returns `1.0.0` |
| `oneOf` + discriminator | `POST /payments` request (`CardPaymentInput` / `BankPaymentInput`) and `Payment` response | variants are flat closed schemas (`additionalProperties: false`) |
| `allOf` | `CardPayment`, `BankPayment` = `PaymentCommon` + variant fields | used in responses only, because `allOf` cannot be closed in OpenAPI 3.0 |
| `anyOf` | `Payment.reference`: UUID string or positive integer | |
| Security | `/me` bearer, `/audit-events` basic, `/partner-status` API key (header), `/feature-flags` API key (query) | each answers 401 with `WWW-Authenticate` and the `Error` shape |

Fixed fake credentials: `test-token`, `test-user`/`test-pass`, `test-api-key` (README table).

## Code map

```
app/ok/customers.py   CustomerInput with patterns and validators; create stamps createdAt (UTC)
app/ok/payments.py    discriminated union (Field(discriminator="method")) and the Reference anyOf type
app/ok/security.py    require_bearer/basic/key_header/key_query dependencies, Unauthorized + handler
app/ok/misc.py        settings map and text/plain version
app/ok/common.py      error_body() now chooses problem+json for PROBLEM_PREFIXES (/ok/customers)
app/seeds.py          + customers, payments, audit_events, feature_flags, settings
clrsig/scenarios/ok-schemas-and-security.yaml   explicit credentials, both payment variants, problem+json, text/plain
```

## Design decisions

- **Why separate resources for security:** securing existing resources would make every earlier conform run depend on credential handling. Four small read-only endpoints keep the blast radius small.
- **Constant-time comparisons** (`secrets.compare_digest`) for all credentials; for basic auth both parts are compared before deciding.
- **The error format depends on the path** (`PROBLEM_PREFIXES`), mirroring what the spec declares per operation. When a later resource needs problem+json, add its prefix there and declare it in the spec.
- **Optional but never null:** optional fields are typed non-null with `default=None`, so absent is accepted and an explicit `null` is not, matching specs that do not say `nullable`.
- **oneOf variants are flat**, so the server's strictness matches the spec exactly (unknown fields rejected in both).

## Verified results (2026-11-21, `clrsig` v0.7.1)

- `uv run pytest`: 131 passed.
- `conform`: 43/43 operations. `--negative`: 36/36 probes (includes four "no credentials" probes, one per secured operation).
- `ok-crud` scenario: 20/20 steps, 29/29 assertions. `ok-schemas-and-security` scenario: 21/21 steps, 37/37 assertions, twice in a row.
- Same `conform`, probes and new scenario also pass against the Docker image.

## ClearSignal findings raised (not worked around)

See `docs/clrsig-findings.md`:
- **F-003** schema-level `example` on a `oneOf` body is ignored, so the environment must supply `amount` and `cardLast4`.
- **F-004** only the first `oneOf` branch is sent, and no negative probes exist for `oneOf` bodies.
- **F-005** `conform` sends credentials for bearer only. Basic and API-key operations return 401 during `conform` and still count as PASS because 401 is declared. The new scenario covers their authenticated paths.

## Watch-outs

- `conform` results for `/audit-events`, `/feature-flags` and `/partner-status` show PASS with a 401 until F-005 is fixed; do not read that as proof the authenticated path works.
- Still OpenAPI 3.0.3, so 3.1 type arrays are not covered.
- `createdAt` on new customers is the current time, so responses are not byte-for-byte reproducible; assertions do not depend on it.
- Customer uniqueness (409 on a duplicate email) and customer update operations come with the business rules.
