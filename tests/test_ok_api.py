"""HTTP-level tests of the strict `ok` API (products, orders, projects, tasks)."""

import pytest

ERROR_KEYS = {"code", "message"}


def assert_error(r, status):
    assert r.status_code == status
    assert r.headers["content-type"].startswith("application/json")
    assert set(r.json()) == ERROR_KEYS


# ---- products ----


async def test_product_crud_flow(client):
    r = await client.get("/ok/products")
    assert r.status_code == 200 and r.json()["total"] == 3

    r = await client.post("/ok/products", json={"name": "Doohickey", "price": 12.5, "stock": 7})
    assert r.status_code == 201
    created = r.json()
    assert created == {"id": "p-4", "name": "Doohickey", "price": 12.5, "stock": 7}

    assert (await client.get("/ok/products/p-4")).json() == created

    r = await client.put("/ok/products/p-4", json={"name": "D2", "price": 15, "stock": 3})
    assert r.status_code == 200 and r.json()["name"] == "D2"
    assert (await client.get("/ok/products/p-4")).json()["stock"] == 3

    assert (await client.delete("/ok/products/p-4")).status_code == 204
    assert_error(await client.get("/ok/products/p-4"), 404)
    # ids are never reused
    r = await client.post("/ok/products", json={"name": "Next", "price": 1, "stock": 1})
    assert r.json()["id"] == "p-5"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"name": "x", "price": 1},  # missing stock
        {"name": "x", "price": "1", "stock": 1},  # wrong type, no coercion
        {"name": "x", "price": 1, "stock": 1.5},  # integer expected
        {"name": "x", "price": -1, "stock": 1},  # minimum
        {"name": "", "price": 1, "stock": 1},  # minLength
        {"name": "x", "price": 1, "stock": 1, "extra": True},  # additionalProperties false
        {"name": "x", "price": True, "stock": 1},  # bool is not a number
    ],
)
async def test_product_invalid_body_is_400(client, body):
    assert_error(await client.post("/ok/products", json=body), 400)
    assert_error(await client.put("/ok/products/p-1", json=body), 400)


async def test_product_malformed_json_is_400(client):
    r = await client.post(
        "/ok/products", content=b"{not json", headers={"content-type": "application/json"}
    )
    assert_error(r, 400)


async def test_product_unknown_id_is_404(client):
    assert_error(await client.get("/ok/products/nope"), 404)
    assert_error(await client.put("/ok/products/nope", json={"name": "x", "price": 1, "stock": 1}), 404)
    assert_error(await client.delete("/ok/products/nope"), 404)


# ---- orders ----


async def test_order_flow_and_product_rule(client):
    r = await client.post("/ok/orders", json={"productId": "p-1", "quantity": 2})
    assert r.status_code == 201
    assert r.json() == {"id": "o-3", "productId": "p-1", "quantity": 2, "status": "pending"}

    assert_error(await client.post("/ok/orders", json={"productId": "nope", "quantity": 1}), 422)
    assert_error(await client.post("/ok/orders", json={"productId": "p-1", "quantity": 0}), 400)

    r = await client.put("/ok/orders/o-3", json={"productId": "p-2", "quantity": 5})
    assert r.status_code == 200
    assert r.json()["status"] == "pending"  # PUT does not touch status
    assert_error(await client.put("/ok/orders/o-3", json={"productId": "nope", "quantity": 1}), 422)
    assert_error(await client.put("/ok/orders/nope", json={"productId": "p-1", "quantity": 1}), 404)

    assert (await client.delete("/ok/orders/o-3")).status_code == 204
    assert_error(await client.get("/ok/orders/o-3"), 404)


# ---- projects and tasks ----


async def test_project_crud_and_optional_description(client):
    r = await client.post("/ok/projects", json={"name": "P"})
    assert r.status_code == 201
    assert r.json() == {"id": "pr-3", "name": "P"}  # no null description
    r = await client.put("/ok/projects/pr-3", json={"name": "P2", "description": "d"})
    assert r.json() == {"id": "pr-3", "name": "P2", "description": "d"}
    assert_error(await client.post("/ok/projects", json={"description": "x"}), 400)
    assert_error(await client.get("/ok/projects/nope"), 404)


async def test_task_ownership(client):
    r = await client.get("/ok/projects/pr-1/tasks")
    assert r.json()["total"] == 2

    r = await client.post("/ok/projects/pr-2/tasks", json={"title": "New"})
    assert r.status_code == 201
    task = r.json()
    assert task == {"id": "t-4", "projectId": "pr-2", "title": "New", "done": False}

    # A task is only reachable through its own project.
    assert_error(await client.get("/ok/projects/pr-1/tasks/t-4"), 404)
    assert (await client.get("/ok/projects/pr-2/tasks/t-4")).status_code == 200
    assert_error(await client.get("/ok/projects/nope/tasks"), 404)
    assert_error(await client.post("/ok/projects/nope/tasks", json={"title": "x"}), 404)

    r = await client.put("/ok/projects/pr-2/tasks/t-4", json={"title": "New", "done": True})
    assert r.json()["done"] is True
    assert (await client.delete("/ok/projects/pr-2/tasks/t-4")).status_code == 204
    assert_error(await client.delete("/ok/projects/pr-2/tasks/t-4"), 404)


async def test_deleting_project_removes_its_tasks(client):
    assert (await client.delete("/ok/projects/pr-1")).status_code == 204
    assert_error(await client.get("/ok/projects/pr-1/tasks"), 404)
    state = (await client.get("/ok/__admin/state")).json()
    assert set(state["tasks"]) == {"t-3"}


# ---- reset ----


async def test_reset_restores_seed_and_counters(client):
    await client.post("/ok/products", json={"name": "x", "price": 1, "stock": 1})
    await client.delete("/ok/products/p-1")
    assert (await client.post("/ok/__admin/reset")).status_code == 204
    r = await client.get("/ok/products")
    assert [p["id"] for p in r.json()["items"]] == ["p-1", "p-2", "p-3"]
    r = await client.post("/ok/products", json={"name": "x", "price": 1, "stock": 1})
    assert r.json()["id"] == "p-4"  # counter was reset too

