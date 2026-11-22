# ClearSignal findings

Things found in `clrsig` while building these fixtures. **Rule: this repository does not work around ClearSignal.** Fixtures stay correct, and each problem is listed here for the api-workbench side to fix. When a fix ships, re-verify here and tick the item.

Legend: `- [ ]` open · `- [x]` closed (verified against the stated release)

How to close an item: install the fixed release, rerun the "Repro" command, confirm the "Expected" result, then fill in "Closed" and tick the box. Remove any matching caveat from `README.md`, `docs/TASKLIST.md` and the KT notes in the same change.

---

- [x] **F-001 — Typed request-body fields are sent as strings by `conform` (released v0.5.0)**
  - Found: 2026-11-21, `clrsig` v0.5.0 (Scoop). Fixed in v0.7.1.
  - Behavior: `conform` builds the body with every placeholder quoted (`"price": "{{price}}"`) and ignores schema `example`/`default`. Required `number`, `integer` and `boolean` properties are therefore sent as strings and reported as a request-body problem (CS-REQ-002 category), so `ok` fails although it conforms.
  - Repro: start the server, `POST /ok/__admin/reset`, then `clrsig conform http://localhost:8080/ok/openapi.yaml --env clrsig/environments/ok.yaml`.
  - Expected: 21/21 operations pass.
  - Actual (v0.5.0): 15 passed, 6 failed (`POST`/`PUT` on products, orders, tasks).
  - Closed: 2026-11-21, verified with released `clrsig` v0.7.1: `conform` 21/21 operations and 28/28 negative probes pass; `ok-crud` scenario passes twice (20/20 steps, 29/29 assertions).

- [x] **F-002 — Path-level `parameters` are not substituted (released v0.5.0)**
  - Found: 2026-11-21, `clrsig` v0.5.0. Fixed in v0.7.1 (source commit `6f9d10b`, "path-level parameters in generated requests").
  - Behavior: a parameter declared once on the path item (`/products/{productId}: parameters: [...]`) is not seen, so the URL keeps a literal `{productId}`. `clrsig generate` writes `{productId}` instead of `{{productId}}`, and `conform` sends the literal text.
  - Repro: `clrsig generate specs/ok.yaml --dry-run` and look at `/products/{productId}`.
  - Expected: `.../products/{{productId}}`.
  - Closed: 2026-11-21, verified with released `clrsig` v0.7.1: `generate --dry-run` prints `.../products/{{productId}}`; `conform` resolves all path parameters.

---

## Baseline

Fixtures are verified against released `clrsig` **v0.7.1** (installed with Scoop). No open findings.

## Notes

- `conform` needs environment values for path parameters (`clrsig/environments/ok.yaml`). That is expected behavior, not a finding.
- `conform` exercises DELETE operations, so the store must be reset before each run. Later operations then see declared 404s. Expected behavior.
