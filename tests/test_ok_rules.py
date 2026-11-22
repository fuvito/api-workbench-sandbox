"""Phase 2 step 3: light business rules (unique values, stock, states, totals, ownership)."""

import asyncio

import pytest

from tests.test_ok_api import STAR, assert_error
from tests.test_ok_schemas import VALID, assert_problem


async def product(client, pid):
    return (await client.get(f"/ok/products/{pid}")).json()


async def new_order(client, product_id="p-1", quantity=2):
    r = await client.post("/ok/orders", json={"productId": product_id, "quantity": quantity})
    assert r.status_code == 201, r.text
    return r.json()


# ---- stock ----


async def test_order_over_stock_is_422_and_nothing_is_created(client):
    # p-2 has 5 in stock, p-3 has none
    assert_error(await client.post("/ok/orders", json={"productId": "p-2", "quantity": 6}), 422)
    assert_error(await client.post("/ok/orders", json={"productId": "p-3", "quantity": 1}), 422)
    assert (await client.get("/ok/orders")).json()["total"] == 2
    assert (await client.post("/ok/orders", json={"productId": "p-2", "quantity": 5})).status_code == 201


async def test_pay_takes_stock_cancel_gives_it_back(client):
    order = await new_order(client, "p-2", 3)
    assert (await product(client, "p-2"))["stock"] == 5  # creating does not reserve
    r = await client.post(f"/ok/orders/{order['id']}/pay")
    assert r.status_code == 200 and r.json()["status"] == "paid"
    assert (await product(client, "p-2"))["stock"] == 2
    r = await client.post(f"/ok/orders/{order['id']}/cancel")
    assert r.json()["status"] == "cancelled"
    assert (await product(client, "p-2"))["stock"] == 5


async def test_cancelling_a_pending_order_leaves_stock_alone(client):
    order = await new_order(client, "p-1", 2)
    await client.post(f"/ok/orders/{order['id']}/cancel")
    assert (await product(client, "p-1"))["stock"] == 100


async def test_pay_fails_422_when_stock_ran_out_in_between(client):
    first = await new_order(client, "p-2", 4)
    second = await new_order(client, "p-2", 3)
    assert (await client.post(f"/ok/orders/{first['id']}/pay")).status_code == 200  # 5 -> 1
    assert_error(await client.post(f"/ok/orders/{second['id']}/pay"), 422)
    assert (await client.get(f"/ok/orders/{second['id']}")).json()["status"] == "pending"
    assert (await product(client, "p-2"))["stock"] == 1


async def test_concurrent_pays_never_oversell(client):
    orders = [await new_order(client, "p-2", 2) for _ in range(5)]  # 10 wanted, 5 in stock
    results = await asyncio.gather(*(client.post(f"/ok/orders/{o['id']}/pay") for o in orders))
    codes = sorted(r.status_code for r in results)
    assert codes == [200, 200, 422, 422, 422]
    assert (await product(client, "p-2"))["stock"] == 1


# ---- state machine ----


async def test_happy_path_pending_to_delivered(client):
    oid = (await new_order(client))["id"]
    for action, status in [("pay", "paid"), ("ship", "shipped"), ("deliver", "delivered")]:
        r = await client.post(f"/ok/orders/{oid}/{action}")
        assert r.status_code == 200 and r.json()["status"] == status
    assert (await client.get(f"/ok/orders/{oid}")).json()["status"] == "delivered"


@pytest.mark.parametrize(
    "path,action",
    [
        (["ship"], "ship"),  # pending cannot ship
        (["deliver"], "deliver"),
        (["pay", "pay"], "pay"),  # pay twice
        (["pay", "deliver"], "deliver"),  # paid cannot deliver
        (["pay", "ship", "cancel"], "cancel"),  # cancel a shipped order
        (["pay", "ship", "deliver", "cancel"], "cancel"),
        (["cancel", "pay"], "pay"),  # cancelled is final
        (["cancel", "cancel"], "cancel"),
    ],
)
async def test_illegal_moves_are_409(client, path, action):
    oid = (await new_order(client))["id"]
    for step in path[:-1]:
        assert (await client.post(f"/ok/orders/{oid}/{step}")).status_code == 200
    before = (await client.get(f"/ok/orders/{oid}")).json()
    assert_error(await client.post(f"/ok/orders/{oid}/{path[-1]}"), 409)
    assert (await client.get(f"/ok/orders/{oid}")).json() == before  # unchanged


async def test_actions_on_unknown_order_are_404(client):
    for action in ("pay", "ship", "deliver", "cancel", "invoice"):
        assert_error(await client.post(f"/ok/orders/nope/{action}"), 404)


async def test_only_pending_orders_are_editable_and_deletable(client):
    paid = "o-2"  # seeded as paid
    assert_error(await client.put(f"/ok/orders/{paid}", json={"productId": "p-1", "quantity": 1}, headers=STAR), 409)
    assert_error(await client.patch(f"/ok/orders/{paid}", json={"quantity": 1}, headers=STAR), 409)
    assert_error(await client.delete(f"/ok/orders/{paid}"), 409)
    await client.post("/ok/orders/o-1/cancel")
    assert (await client.delete("/ok/orders/o-1")).status_code == 204  # cancelled may be deleted


async def test_edit_rechecks_stock_and_recomputes(client):
    r = await client.patch("/ok/orders/o-1", json={"quantity": 101}, headers=STAR)
    assert r.status_code == 422  # p-1 has 100
    r = await client.put("/ok/orders/o-1", json={"productId": "p-2", "quantity": 2}, headers=STAR)
    assert r.status_code == 200
    assert (r.json()["unitPrice"], r.json()["total"]) == (24.5, 53.9)  # 2 x 24.5 x 1.10


# ---- computed fields ----


@pytest.mark.parametrize(
    "product_id,qty,total",
    [("p-1", 1, 10.99), ("p-1", 3, 32.97), ("p-2", 2, 53.9), ("p-1", 7, 76.92)],
)
async def test_order_total_is_price_times_quantity_plus_ten_percent(client, product_id, qty, total):
    order = await new_order(client, product_id, qty)
    assert order["total"] == total


async def test_timestamps_are_set_by_the_server(client):
    order = await new_order(client)
    assert order["createdAt"] == order["updatedAt"] and order["createdAt"].endswith("Z")
    assert (await client.post("/ok/orders", json={"productId": "p-1", "quantity": 1,})).status_code == 201
    r = await client.post(f"/ok/orders/{order['id']}/pay")
    assert r.json()["createdAt"] == order["createdAt"]


async def test_client_cannot_set_computed_fields(client):
    body = {"productId": "p-1", "quantity": 1}
    for extra in ({"total": 1}, {"unitPrice": 1}, {"status": "paid"}, {"createdAt": "2026-01-01T00:00:00Z"}):
        assert_error(await client.post("/ok/orders", json={**body, **extra}), 400)


# ---- invoices ----


async def test_invoice_numbers_are_sequential_and_one_per_order(client):
    assert (await client.get("/ok/invoices/inv-1")).json()["number"] == "INV-000001"  # seeded
    a, b = (await new_order(client))["id"], (await new_order(client))["id"]
    assert_error(await client.post(f"/ok/orders/{a}/invoice"), 409)  # still pending
    for oid in (a, b):
        await client.post(f"/ok/orders/{oid}/pay")
    r1 = await client.post(f"/ok/orders/{b}/invoice")  # numbers follow issue order, not order id
    r2 = await client.post(f"/ok/orders/{a}/invoice")
    assert (r1.status_code, r1.json()["number"], r1.json()["id"]) == (201, "INV-000002", "inv-2")
    assert (r2.status_code, r2.json()["number"]) == (201, "INV-000003")
    assert r1.json()["orderId"] == b and r1.json()["total"] == 21.98
    assert_error(await client.post(f"/ok/orders/{a}/invoice"), 409)  # already invoiced
    listed = await client.get("/ok/invoices")
    assert listed.json()["total"] == 3 and listed.headers["x-total-count"] == "3"
    assert_error(await client.get("/ok/invoices/nope"), 404)


async def test_cancelled_orders_cannot_be_invoiced(client):
    oid = (await new_order(client))["id"]
    await client.post(f"/ok/orders/{oid}/cancel")
    assert_error(await client.post(f"/ok/orders/{oid}/invoice"), 409)


async def test_invoice_numbers_restart_after_reset(client):
    oid = (await new_order(client))["id"]
    await client.post(f"/ok/orders/{oid}/pay")
    assert (await client.post(f"/ok/orders/{oid}/invoice")).json()["number"] == "INV-000002"
    await client.post("/ok/__admin/reset")
    oid = (await new_order(client))["id"]
    await client.post(f"/ok/orders/{oid}/pay")
    assert (await client.post(f"/ok/orders/{oid}/invoice")).json()["number"] == "INV-000002"


# ---- unique values ----


async def test_duplicate_customer_email_is_409_case_insensitive(client):
    assert_problem(await client.post("/ok/customers", json={**VALID, "email": "ALICE@example.com"}), 409)
    assert (await client.post("/ok/customers", json=VALID)).status_code == 201
    assert_problem(await client.post("/ok/customers", json={**VALID, "name": "Other"}), 409)
    assert (await client.get("/ok/customers")).json()["total"] == 3  # only one was added


async def test_concurrent_duplicate_emails_create_one_customer(client):
    results = await asyncio.gather(*(client.post("/ok/customers", json=VALID) for _ in range(10)))
    assert sorted(r.status_code for r in results) == [201] + [409] * 9


# ---- ownership and cascade ----


async def test_project_with_open_tasks_cannot_be_deleted(client):
    assert_error(await client.delete("/ok/projects/pr-1"), 409)
    assert (await client.get("/ok/projects/pr-1")).status_code == 200  # still there
    assert (await client.get("/ok/projects/pr-1/tasks")).json()["total"] == 2


async def test_project_with_only_done_tasks_can_be_deleted(client):
    await client.patch("/ok/projects/pr-1/tasks/t-1", json={"done": True})
    assert (await client.delete("/ok/projects/pr-1")).status_code == 204
    assert_error(await client.get("/ok/projects/pr-1/tasks/t-1"), 404)
    assert set((await client.get("/ok/__admin/state")).json()["tasks"]) == {"t-3"}


async def test_cascade_true_deletes_open_tasks_too(client):
    assert (await client.delete("/ok/projects/pr-1", params={"cascade": "true"})).status_code == 204
    assert set((await client.get("/ok/__admin/state")).json()["tasks"]) == {"t-3"}


async def test_cascade_false_behaves_like_default_and_bad_value_is_400(client):
    assert_error(await client.delete("/ok/projects/pr-1", params={"cascade": "false"}), 409)
    assert_error(await client.delete("/ok/projects/pr-1", params={"cascade": "maybe"}), 400)
    assert_error(await client.delete("/ok/projects/nope", params={"cascade": "true"}), 404)


async def test_project_without_tasks_deletes_normally(client):
    pid = (await client.post("/ok/projects", json={"name": "Empty"})).json()["id"]
    assert (await client.delete(f"/ok/projects/{pid}")).status_code == 204
