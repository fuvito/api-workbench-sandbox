"""Step 2 of Phase 2 breadth: formats, nullable, maps, problem+json, text/plain, polymorphism."""

import pytest

VALID = {"email": "new@example.com", "name": "New"}


def assert_problem(r, status):
    assert r.status_code == status
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["status"] == status and body["type"] == "about:blank"
    assert {"title", "detail"} <= set(body)


# ---- customers: formats, nullable, optional, arrays, maps ----


async def test_customer_create_minimal_and_full(client):
    r = await client.post("/ok/customers", json=VALID)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "c-3" and body["email"] == "new@example.com"
    assert body["createdAt"].endswith("Z")
    assert "phone" not in body and "birthDate" not in body  # absent stays absent

    full = {
        **VALID,
        "phone": "+15550001111",
        "birthDate": "1985-03-09",
        "externalRef": "3f2b8c1e-5d4a-4c8e-9a7b-1e2d3c4b5a69",
        "tags": ["a", "b"],
        "preferences": {"lang": "en"},
    }
    r = await client.post("/ok/customers", json=full)
    assert r.status_code == 201
    assert {k: r.json()[k] for k in full} == full


async def test_customer_birthdate_is_nullable_but_nothing_else_is(client):
    r = await client.post("/ok/customers", json={**VALID, "birthDate": None})
    assert r.status_code == 201 and r.json()["birthDate"] is None
    assert_problem(await client.post("/ok/customers", json={**VALID, "phone": None}), 400)
    assert_problem(await client.post("/ok/customers", json={**VALID, "tags": None}), 400)


@pytest.mark.parametrize(
    "extra",
    [
        {"email": "not-an-email"},
        {"email": "a@b"},
        {"phone": "12345"},  # pattern: 7-15 digits
        {"phone": "+1555abc7890"},
        {"birthDate": "17/05/1990"},
        {"birthDate": "2026-02-31"},  # shaped like a date, not a date
        {"externalRef": "not-a-uuid"},
        {"tags": ["a", "a"]},  # uniqueItems
        {"tags": [""]},
        {"tags": [str(i) for i in range(11)]},  # maxItems
        {"preferences": {"k": 1}},  # additionalProperties: string
        {"preferences": {str(i): "v" for i in range(21)}},  # maxProperties
        {"id": "c-9"},  # readOnly property is not accepted in a request
        {"createdAt": "2026-01-01T00:00:00Z"},
    ],
)
async def test_customer_invalid_fields_are_problem_400(client, extra):
    assert_problem(await client.post("/ok/customers", json={**VALID, **extra}), 400)


async def test_customer_missing_required_and_unknown_ids(client):
    assert_problem(await client.post("/ok/customers", json={"email": "a@b.co"}), 400)
    assert_problem(await client.get("/ok/customers/nope"), 404)
    assert_problem(await client.delete("/ok/customers/nope"), 404)


async def test_customer_list_get_delete_and_seed_null(client):
    r = await client.get("/ok/customers")
    assert r.json()["total"] == 2 and r.headers["x-total-count"] == "2"
    assert (await client.get("/ok/customers/c-2")).json()["birthDate"] is None
    assert (await client.delete("/ok/customers/c-1")).status_code == 204
    assert_problem(await client.get("/ok/customers/c-1"), 404)


async def test_customer_list_paging_errors_are_problem(client):
    assert_problem(await client.get("/ok/customers", params={"limit": 0}), 400)


async def test_other_resources_keep_plain_error_shape(client):
    r = await client.get("/ok/products/nope")
    assert r.headers["content-type"].startswith("application/json")
    assert set(r.json()) == {"code", "message"}


# ---- settings (map) and version (text/plain) ----


async def test_settings_map_roundtrip(client):
    assert (await client.get("/ok/settings")).json() == {"theme": "light", "language": "en"}
    r = await client.put("/ok/settings", json={"a": "1", "b": "2"})
    assert r.status_code == 200 and r.json() == {"a": "1", "b": "2"}
    assert (await client.get("/ok/settings")).json() == {"a": "1", "b": "2"}
    assert (await client.put("/ok/settings", json={})).json() == {}


@pytest.mark.parametrize(
    "body",
    [{"a": 1}, {"a": None}, {"a": ["x"]}, [], "text", {str(i): "v" for i in range(21)}, {"a": "x" * 201}],
)
async def test_settings_invalid_is_400(client, body):
    r = await client.put("/ok/settings", json=body)
    assert r.status_code == 400 and set(r.json()) == {"code", "message"}


async def test_version_is_plain_text(client):
    r = await client.get("/ok/version")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert r.text == "1.0.0"


async def test_reset_restores_customers_and_settings(client):
    await client.post("/ok/customers", json=VALID)
    await client.put("/ok/settings", json={"x": "y"})
    await client.post("/ok/__admin/reset")
    assert (await client.get("/ok/customers")).json()["total"] == 2
    assert (await client.get("/ok/settings")).json() == {"theme": "light", "language": "en"}
    assert (await client.post("/ok/customers", json=VALID)).json()["id"] == "c-3"


# ---- payments: oneOf by discriminator, allOf responses, anyOf reference ----

CARD = {"method": "card", "amount": 19.99, "currency": "USD", "cardLast4": "4242"}
BANK = {"method": "bank", "amount": 250, "currency": "EUR", "iban": "DE89370400440532013000"}
UUID = "3f2b8c1e-5d4a-4c8e-9a7b-1e2d3c4b5a69"


async def test_payment_both_variants_are_accepted(client):
    r = await client.post("/ok/payments", json=CARD)
    assert r.status_code == 201
    assert r.json() == {"id": "pay-3", **CARD, "status": "authorized"}
    r = await client.post("/ok/payments", json=BANK)
    assert r.status_code == 201 and r.json()["iban"] == BANK["iban"]
    assert (await client.get("/ok/payments/pay-3")).json()["method"] == "card"
    assert (await client.get("/ok/payments")).headers["x-total-count"] == "4"


@pytest.mark.parametrize("reference", [42, UUID, 1])
async def test_payment_reference_anyof_accepts(client, reference):
    r = await client.post("/ok/payments", json={**CARD, "reference": reference})
    assert r.status_code == 201 and r.json()["reference"] == reference


@pytest.mark.parametrize("reference", ["42", 0, -1, 1.5, True, None, "not-a-uuid", [1]])
async def test_payment_reference_anyof_rejects(client, reference):
    r = await client.post("/ok/payments", json={**CARD, "reference": reference})
    assert r.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"amount": 5, "currency": "USD", "cardLast4": "4242"},  # no discriminator
        {**CARD, "method": "cash"},  # unknown discriminator value
        {**CARD, "iban": BANK["iban"]},  # bank field on a card payment
        {**BANK, "cardLast4": "4242"},  # card field on a bank payment
        {**CARD, "amount": 0},  # minimum 0.01
        {**CARD, "currency": "JPY"},  # enum
        {**CARD, "cardLast4": "42"},  # pattern
        {**BANK, "iban": "bad"},
        {"method": "card", "amount": 5, "currency": "USD"},  # missing cardLast4
    ],
)
async def test_payment_invalid_is_400(client, body):
    r = await client.post("/ok/payments", json=body)
    assert r.status_code == 400 and set(r.json()) == {"code", "message"}


async def test_payment_unknown_id_is_404(client):
    assert (await client.get("/ok/payments/nope")).status_code == 404


# ---- security: bearer, basic, API key (header, query) ----

BASIC_OK = "Basic dGVzdC11c2VyOnRlc3QtcGFzcw=="  # test-user:test-pass


def assert_challenge(r, scheme):
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith(scheme)
    assert set(r.json()) == {"code", "message"}


async def test_bearer(client):
    r = await client.get("/ok/me", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 200 and r.json() == {"user": "test-user", "scopes": ["read"]}
    assert_challenge(await client.get("/ok/me"), "Bearer")
    assert_challenge(await client.get("/ok/me", headers={"Authorization": "Bearer nope"}), "Bearer")
    assert_challenge(await client.get("/ok/me", headers={"Authorization": "test-token"}), "Bearer")
    assert_challenge(await client.get("/ok/me", headers={"Authorization": BASIC_OK}), "Bearer")


async def test_basic(client):
    r = await client.get("/ok/audit-events", headers={"Authorization": BASIC_OK})
    assert r.status_code == 200 and r.json()["total"] == 2
    assert r.headers["x-total-count"] == "2"
    assert_challenge(await client.get("/ok/audit-events"), "Basic")
    wrong = "Basic dGVzdC11c2VyOndyb25n"  # test-user:wrong
    assert_challenge(await client.get("/ok/audit-events", headers={"Authorization": wrong}), "Basic")
    junk = {"Authorization": "Basic !!!not-base64!!!"}
    assert_challenge(await client.get("/ok/audit-events", headers=junk), "Basic")
    bearer = {"Authorization": "Bearer test-token"}
    assert_challenge(await client.get("/ok/audit-events", headers=bearer), "Basic")


async def test_api_key_header(client):
    r = await client.get("/ok/partner-status", headers={"X-API-Key": "test-api-key"})
    assert r.status_code == 200 and r.json() == {"partner": "acme", "status": "active"}
    assert_challenge(await client.get("/ok/partner-status"), "ApiKey")
    assert_challenge(await client.get("/ok/partner-status", headers={"X-API-Key": "x"}), "ApiKey")
    # the key in the query string does not satisfy the header scheme
    assert_challenge(await client.get("/ok/partner-status", params={"api_key": "test-api-key"}), "ApiKey")


async def test_api_key_query(client):
    r = await client.get("/ok/feature-flags", params={"api_key": "test-api-key"})
    assert r.status_code == 200 and r.json() == {"beta": True, "legacy": False}
    assert_challenge(await client.get("/ok/feature-flags"), "ApiKey")
    assert_challenge(await client.get("/ok/feature-flags", params={"api_key": "x"}), "ApiKey")
    assert_challenge(await client.get("/ok/feature-flags", headers={"X-API-Key": "test-api-key"}), "ApiKey")


async def test_public_operations_need_no_credentials(client):
    for path in ("/ok/health", "/ok/products", "/ok/version", "/ok/settings", "/ok/customers"):
        assert (await client.get(path)).status_code == 200


async def test_admin_token_is_independent_of_api_credentials(client):
    # Reset has its own protection (ADMIN_TOKEN); API credentials are not involved.
    assert (await client.post("/ok/__admin/reset")).status_code == 204
