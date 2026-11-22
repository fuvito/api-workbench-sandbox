"""Step 1 of Phase 2 breadth: query parameters, X-Total-Count, PATCH, HEAD, OPTIONS."""

import pytest

from tests.test_ok_api import assert_error


def ids(r):
    return [i["id"] for i in r.json()["items"]]


# ---- pagination and the X-Total-Count header ----


async def test_total_count_header_matches_body_total(client):
    r = await client.get("/ok/products")
    assert r.headers["x-total-count"] == "3" and r.json()["total"] == 3


async def test_pagination_slices_but_total_is_unpaged(client):
    r = await client.get("/ok/products", params={"limit": 2, "offset": 1})
    assert ids(r) == ["p-2", "p-3"]
    assert r.json()["total"] == 3 and r.headers["x-total-count"] == "3"
    r = await client.get("/ok/products", params={"limit": 1, "offset": 5})
    assert ids(r) == [] and r.headers["x-total-count"] == "3"


@pytest.mark.parametrize(
    "path,params",
    [
        ("/ok/products", {"limit": 0}),
        ("/ok/products", {"limit": 101}),
        ("/ok/products", {"limit": "abc"}),
        ("/ok/products", {"limit": "1.5"}),
        ("/ok/products", {"offset": -1}),
        ("/ok/orders", {"limit": 0}),
        ("/ok/projects", {"offset": "x"}),
        ("/ok/projects/pr-1/tasks", {"limit": 101}),
    ],
)
async def test_invalid_paging_is_400(client, path, params):
    assert_error(await client.get(path, params=params), 400)


# ---- product filters and sorting ----


@pytest.mark.parametrize(
    "params,expected",
    [
        ({"q": "GAD"}, ["p-2"]),
        ({"minPrice": 5}, ["p-1", "p-2"]),
        ({"maxPrice": 9.99}, ["p-1", "p-3"]),
        ({"minPrice": 5, "maxPrice": 10}, ["p-1"]),
        ({"inStock": "true"}, ["p-1", "p-2"]),
        ({"inStock": "false"}, ["p-3"]),
        ({"sort": "name"}, ["p-2", "p-3", "p-1"]),  # Gadget, Gizmo, Widget
        ({"sort": "-price"}, ["p-2", "p-1", "p-3"]),
        ({"sort": "price", "limit": 1}, ["p-3"]),
    ],
)
async def test_product_filters_and_sort(client, params, expected):
    r = await client.get("/ok/products", params=params)
    assert r.status_code == 200 and ids(r) == expected


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "id"},
        {"inStock": "yes"},
        {"inStock": "1"},
        {"minPrice": "cheap"},
        {"minPrice": -1},
        {"minPrice": "nan"},
        {"q": ""},
    ],
)
async def test_invalid_product_query_is_400(client, params):
    assert_error(await client.get("/ok/products", params=params), 400)


async def test_filtered_total_counts_matches_only(client):
    r = await client.get("/ok/products", params={"inStock": "true", "limit": 1})
    assert len(r.json()["items"]) == 1 and r.json()["total"] == 2
    assert r.headers["x-total-count"] == "2"


# ---- order and task filters ----


async def test_order_filters(client):
    assert ids(await client.get("/ok/orders", params={"status": "paid"})) == ["o-2"]
    assert ids(await client.get("/ok/orders", params={"productId": "p-1"})) == ["o-1"]
    assert ids(await client.get("/ok/orders", params={"status": "shipped"})) == []
    assert_error(await client.get("/ok/orders", params={"status": "weird"}), 400)


async def test_task_done_filter(client):
    assert ids(await client.get("/ok/projects/pr-1/tasks", params={"done": "true"})) == ["t-2"]
    assert ids(await client.get("/ok/projects/pr-1/tasks", params={"done": "false"})) == ["t-1"]
    assert_error(await client.get("/ok/projects/pr-1/tasks", params={"done": "maybe"}), 400)
    r = await client.get("/ok/projects/pr-1/tasks")
    assert r.headers["x-total-count"] == "2"


# ---- PATCH ----


async def test_patch_product_changes_only_given_fields(client):
    r = await client.patch("/ok/products/p-2", json={"stock": 9})
    assert r.status_code == 200
    assert r.json() == {"id": "p-2", "name": "Gadget", "price": 24.5, "stock": 9}
    assert (await client.get("/ok/products/p-2")).json()["stock"] == 9


@pytest.mark.parametrize(
    "body",
    [
        {},  # at least one field
        {"stock": None},  # null is not allowed
        {"stock": "9"},  # no coercion
        {"price": -1},
        {"name": ""},
        {"unknown": 1},
    ],
)
async def test_patch_product_invalid_is_400(client, body):
    assert_error(await client.patch("/ok/products/p-1", json=body), 400)


async def test_patch_unknown_ids_are_404(client):
    assert_error(await client.patch("/ok/products/nope", json={"stock": 1}), 404)
    assert_error(await client.patch("/ok/orders/nope", json={"quantity": 1}), 404)
    assert_error(await client.patch("/ok/projects/nope", json={"name": "x"}), 404)
    assert_error(await client.patch("/ok/projects/pr-1/tasks/nope", json={"done": True}), 404)
    assert_error(await client.patch("/ok/projects/pr-2/tasks/t-1", json={"done": True}), 404)


async def test_patch_order_keeps_status_and_checks_product(client):
    r = await client.patch("/ok/orders/o-2", json={"quantity": 4})
    assert r.json() == {"id": "o-2", "productId": "p-2", "quantity": 4, "status": "paid"}
    assert_error(await client.patch("/ok/orders/o-2", json={"productId": "nope"}), 422)
    assert_error(await client.patch("/ok/orders/o-2", json={"status": "shipped"}), 400)


async def test_patch_project_and_task(client):
    r = await client.patch("/ok/projects/pr-2", json={"description": "now described"})
    assert r.json() == {"id": "pr-2", "name": "Cleanup", "description": "now described"}
    r = await client.patch("/ok/projects/pr-1/tasks/t-1", json={"done": True})
    assert r.json() == {"id": "t-1", "projectId": "pr-1", "title": "Write docs", "done": True}
    r = await client.patch("/ok/projects/pr-1/tasks/t-1", json={"done": False, "title": "T"})
    assert r.json()["title"] == "T" and r.json()["done"] is False


# ---- HEAD and OPTIONS ----


async def test_head_products(client):
    r = await client.head("/ok/products")
    assert r.status_code == 200 and r.headers["x-total-count"] == "3" and r.content == b""


async def test_head_product(client):
    assert (await client.head("/ok/products/p-1")).status_code == 200
    r = await client.head("/ok/products/nope")
    assert r.status_code == 404 and r.content == b""


async def test_options(client):
    r = await client.options("/ok/products")
    assert r.status_code == 204 and r.headers["allow"] == "GET, HEAD, POST, OPTIONS"
    r = await client.options("/ok/products/p-1")
    assert r.status_code == 204
    assert r.headers["allow"] == "GET, HEAD, PUT, PATCH, DELETE, OPTIONS"
