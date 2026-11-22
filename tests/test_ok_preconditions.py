"""Step 3b: ETag/If-Match, idempotency keys, soft delete, expiring codes."""

import asyncio
from datetime import UTC, datetime

import pytest

from app import clock
from tests.test_ok_api import assert_error
from tests.test_ok_schemas import CARD, BANK, VALID, assert_problem


def freeze(monkeypatch, iso: str):
    moment = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC)
    monkeypatch.setattr(clock, "utcnow", lambda: moment)


async def etag(client, path):
    r = await client.get(path)
    assert r.status_code == 200
    return r.headers["etag"]


# ---- ETag on orders and tasks ----


async def test_etag_is_stable_and_changes_with_the_resource(client):
    first = await etag(client, "/ok/orders/o-1")
    assert first == await etag(client, "/ok/orders/o-1")
    assert first.startswith('"') and first.endswith('"')
    r = await client.patch("/ok/orders/o-1", json={"quantity": 3}, headers={"If-Match": first})
    assert r.status_code == 200
    assert r.headers["etag"] != first
    assert r.headers["etag"] == await etag(client, "/ok/orders/o-1")  # same as a fresh GET
    assert await etag(client, "/ok/orders/o-2") != first  # different resources differ


async def test_every_order_representation_carries_an_etag(client):
    created = await client.post("/ok/orders", json={"productId": "p-1", "quantity": 1})
    assert created.headers["etag"] == await etag(client, f"/ok/orders/{created.json()['id']}")
    for action in ("pay", "ship", "deliver"):
        r = await client.post(f"/ok/orders/{created.json()['id']}/{action}")
        assert r.headers["etag"] == await etag(client, f"/ok/orders/{created.json()['id']}")


async def test_missing_if_match_on_orders_is_428(client):
    assert_error(await client.put("/ok/orders/o-1", json={"productId": "p-1", "quantity": 1}), 428)
    assert_error(await client.patch("/ok/orders/o-1", json={"quantity": 1}), 428)
    assert (await client.get("/ok/orders/o-1")).json()["quantity"] == 2  # unchanged


async def test_stale_if_match_is_412_and_changes_nothing(client):
    old = await etag(client, "/ok/orders/o-1")
    await client.patch("/ok/orders/o-1", json={"quantity": 5}, headers={"If-Match": old})
    for call in (
        client.put("/ok/orders/o-1", json={"productId": "p-1", "quantity": 1}, headers={"If-Match": old}),
        client.patch("/ok/orders/o-1", json={"quantity": 1}, headers={"If-Match": old}),
    ):
        assert_error(await call, 412)
    assert (await client.get("/ok/orders/o-1")).json()["quantity"] == 5


@pytest.mark.parametrize(
    "header,expected",
    [("*", 200), ('"nope", CURRENT', 200), ('"nope"', 412), ("W/CURRENT", 412), ("", 412)],
)
async def test_if_match_forms(client, header, expected):
    current = await etag(client, "/ok/orders/o-1")
    value = header.replace("CURRENT", current)
    r = await client.patch("/ok/orders/o-1", json={"quantity": 1}, headers={"If-Match": value})
    assert r.status_code == expected


async def test_order_of_checks_404_then_precondition_then_rules(client):
    # unknown order: 404 even without If-Match
    assert_error(await client.patch("/ok/orders/nope", json={"quantity": 1}), 404)
    # o-2 is paid (not editable). The precondition is judged first.
    assert_error(await client.patch("/ok/orders/o-2", json={"quantity": 1}), 428)
    assert_error(await client.patch("/ok/orders/o-2", json={"quantity": 1}, headers={"If-Match": '"x"'}), 412)
    right = await etag(client, "/ok/orders/o-2")
    assert_error(await client.patch("/ok/orders/o-2", json={"quantity": 1}, headers={"If-Match": right}), 409)


async def test_lost_update_is_prevented(client):
    seen_by_alice = await etag(client, "/ok/orders/o-1")
    seen_by_bob = await etag(client, "/ok/orders/o-1")
    assert (await client.patch("/ok/orders/o-1", json={"quantity": 3}, headers={"If-Match": seen_by_alice})).status_code == 200
    assert_error(await client.patch("/ok/orders/o-1", json={"quantity": 4}, headers={"If-Match": seen_by_bob}), 412)
    assert (await client.get("/ok/orders/o-1")).json()["quantity"] == 3


async def test_concurrent_edits_with_the_same_etag_one_wins(client):
    tag = await etag(client, "/ok/orders/o-1")
    results = await asyncio.gather(
        *(client.patch("/ok/orders/o-1", json={"quantity": q}, headers={"If-Match": tag}) for q in range(1, 9))
    )
    assert sorted(r.status_code for r in results) == [200] + [412] * 7


async def test_task_if_match_is_optional_but_checked_when_sent(client):
    path = "/ok/projects/pr-1/tasks/t-1"
    tag = await etag(client, path)
    assert (await client.patch(path, json={"title": "no header"})).status_code == 200  # allowed
    assert_error(await client.put(path, json={"title": "x"}, headers={"If-Match": tag}), 412)  # tag is stale now
    fresh = await etag(client, path)
    r = await client.put(path, json={"title": "ok", "done": True}, headers={"If-Match": fresh})
    assert r.status_code == 200 and r.headers["etag"] == await etag(client, path)
    assert_error(await client.patch(path, json={"done": False}, headers={"If-Match": '"x"'}), 412)


async def test_task_create_returns_etag(client):
    r = await client.post("/ok/projects/pr-1/tasks", json={"title": "new"})
    assert r.headers["etag"] == await etag(client, f"/ok/projects/pr-1/tasks/{r.json()['id']}")


# ---- idempotency keys on payments ----


async def test_same_key_and_body_replays_the_first_payment(client):
    key = {"Idempotency-Key": "abc-123"}
    first = await client.post("/ok/payments", json=CARD, headers=key)
    again = await client.post("/ok/payments", json=CARD, headers=key)
    assert first.status_code == 201 and again.status_code == 200
    assert again.json() == first.json()
    assert (await client.get("/ok/payments")).json()["total"] == 3  # 2 seeded + 1


async def test_same_key_with_another_body_is_422(client):
    key = {"Idempotency-Key": "k1"}
    assert (await client.post("/ok/payments", json=CARD, headers=key)).status_code == 201
    assert_error(await client.post("/ok/payments", json={**CARD, "amount": 20}, headers=key), 422)
    assert_error(await client.post("/ok/payments", json=BANK, headers=key), 422)
    assert (await client.get("/ok/payments")).json()["total"] == 3


async def test_other_keys_and_no_key_create_new_payments(client):
    assert (await client.post("/ok/payments", json=CARD, headers={"Idempotency-Key": "a"})).status_code == 201
    assert (await client.post("/ok/payments", json=CARD, headers={"Idempotency-Key": "b"})).status_code == 201
    assert (await client.post("/ok/payments", json=CARD)).status_code == 201
    assert (await client.post("/ok/payments", json=CARD)).status_code == 201
    assert (await client.get("/ok/payments")).json()["total"] == 6


@pytest.mark.parametrize("key", ["", "x" * 65])
async def test_bad_key_length_is_400(client, key):
    assert_error(await client.post("/ok/payments", json=CARD, headers={"Idempotency-Key": key}), 400)


async def test_invalid_body_with_a_key_does_not_burn_the_key(client):
    key = {"Idempotency-Key": "k2"}
    assert_error(await client.post("/ok/payments", json={**CARD, "amount": 0}, headers=key), 400)
    assert (await client.post("/ok/payments", json=CARD, headers=key)).status_code == 201


async def test_concurrent_requests_with_one_key_create_one_payment(client):
    key = {"Idempotency-Key": "race"}
    results = await asyncio.gather(*(client.post("/ok/payments", json=CARD, headers=key) for _ in range(10)))
    assert sorted(r.status_code for r in results) == [200] * 9 + [201]
    assert len({r.json()["id"] for r in results}) == 1
    assert (await client.get("/ok/payments")).json()["total"] == 3


async def test_reset_forgets_idempotency_keys(client):
    key = {"Idempotency-Key": "k3"}
    await client.post("/ok/payments", json=CARD, headers=key)
    await client.post("/ok/__admin/reset")
    assert (await client.post("/ok/payments", json=CARD, headers=key)).status_code == 201


# ---- soft delete (customers) ----


async def test_soft_delete_hides_but_keeps_the_record(client):
    assert (await client.delete("/ok/customers/c-1")).status_code == 204
    assert_problem(await client.get("/ok/customers/c-1"), 404)
    listed = await client.get("/ok/customers")
    assert [c["id"] for c in listed.json()["items"]] == ["c-2"]
    assert listed.headers["x-total-count"] == "1"

    r = await client.get("/ok/customers/c-1", params={"includeDeleted": "true"})
    assert r.status_code == 200 and r.json()["deletedAt"].endswith("Z")
    listed = await client.get("/ok/customers", params={"includeDeleted": "true"})
    assert listed.json()["total"] == 2 and listed.headers["x-total-count"] == "2"
    assert "deletedAt" not in (await client.get("/ok/customers/c-2")).json()


async def test_deleting_twice_is_404_and_include_deleted_false_hides(client):
    await client.delete("/ok/customers/c-1")
    assert_problem(await client.delete("/ok/customers/c-1"), 404)
    assert_problem(await client.get("/ok/customers/c-1", params={"includeDeleted": "false"}), 404)
    assert_problem(await client.get("/ok/customers/c-1", params={"includeDeleted": "maybe"}), 400)


async def test_deleted_customer_frees_the_email(client):
    await client.delete("/ok/customers/c-1")
    r = await client.post("/ok/customers", json={**VALID, "email": "alice@example.com"})
    assert r.status_code == 201 and r.json()["id"] == "c-3"
    assert_problem(await client.post("/ok/customers", json={**VALID, "email": "alice@example.com"}), 409)


async def test_reset_brings_deleted_customers_back(client):
    await client.delete("/ok/customers/c-1")
    await client.post("/ok/__admin/reset")
    assert (await client.get("/ok/customers/c-1")).status_code == 200


# ---- expiring discount codes ----


async def test_valid_code_redeems_and_expired_code_is_410(client):
    r = await client.post("/ok/discount-codes/SAVE10/redeem")
    assert r.status_code == 200 and r.json()["percentOff"] == 10
    assert_error(await client.post("/ok/discount-codes/OLD5/redeem"), 410)
    assert_error(await client.post("/ok/discount-codes/NOPE/redeem"), 404)
    assert_error(await client.get("/ok/discount-codes/NOPE"), 404)


async def test_expired_code_can_still_be_read(client):
    r = await client.get("/ok/discount-codes/OLD5")
    assert r.status_code == 200 and r.json()["expiresAt"] == "2020-12-31T23:59:59Z"


async def test_expiry_follows_the_clock(client, monkeypatch):
    freeze(monkeypatch, "2100-01-01T00:00:00Z")
    assert_error(await client.post("/ok/discount-codes/SAVE10/redeem"), 410)  # now expired
    freeze(monkeypatch, "2020-06-01T00:00:00Z")
    assert (await client.post("/ok/discount-codes/OLD5/redeem")).status_code == 200  # not yet


async def test_expiry_boundary_is_exclusive(client, monkeypatch):
    freeze(monkeypatch, "2020-12-31T23:59:58Z")
    assert (await client.post("/ok/discount-codes/OLD5/redeem")).status_code == 200
    freeze(monkeypatch, "2020-12-31T23:59:59Z")  # the expiry instant itself is already expired
    assert_error(await client.post("/ok/discount-codes/OLD5/redeem"), 410)
