from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import Field

from app.ok.common import Page, PatchModel, StrictModel, not_found, paged, unprocessable
from app.store import Store

COLLECTION = "orders"
Status = Literal["pending", "paid", "shipped", "delivered", "cancelled"]


class OrderInput(StrictModel):
    productId: str = Field(min_length=1)
    quantity: int = Field(ge=1)


class OrderPatch(PatchModel):
    productId: str = Field(default=None, min_length=1)
    quantity: int = Field(default=None, ge=1)


def build(store: Store) -> APIRouter:
    router = APIRouter()

    async def require_product(product_id: str) -> None:
        if await store.get("products", product_id) is None:
            raise unprocessable(f"product {product_id!r} does not exist")

    @router.get("/orders")
    async def list_orders(
        response: Response,
        page: Page = Depends(),
        status: Status | None = None,
        product_id: str | None = Query(None, alias="productId", min_length=1),
    ) -> dict:
        items = await store.list(COLLECTION)
        if status is not None:
            items = [o for o in items if o["status"] == status]
        if product_id is not None:
            items = [o for o in items if o["productId"] == product_id]
        return paged(items, page, response)

    @router.post("/orders", status_code=201)
    async def create_order(body: OrderInput) -> dict:
        await require_product(body.productId)
        return await store.create_auto(COLLECTION, "o", {**body.model_dump(), "status": "pending"})

    @router.get("/orders/{order_id}")
    async def get_order(order_id: str) -> dict:
        order = await store.get(COLLECTION, order_id)
        if order is None:
            raise not_found("order", order_id)
        return order

    @router.put("/orders/{order_id}")
    async def replace_order(order_id: str, body: OrderInput) -> dict:
        order = await store.get(COLLECTION, order_id)
        if order is None:
            raise not_found("order", order_id)
        await require_product(body.productId)
        order.update(body.model_dump())
        await store.update(COLLECTION, order_id, order)
        return order

    @router.patch("/orders/{order_id}")
    async def update_order(order_id: str, body: OrderPatch) -> dict:
        order = await store.get(COLLECTION, order_id)
        if order is None:
            raise not_found("order", order_id)
        changes = body.changes()
        if "productId" in changes:
            await require_product(changes["productId"])
        order.update(changes)
        await store.update(COLLECTION, order_id, order)
        return order

    @router.delete("/orders/{order_id}", status_code=204)
    async def delete_order(order_id: str) -> Response:
        if not await store.delete(COLLECTION, order_id):
            raise not_found("order", order_id)
        return Response(status_code=204)

    return router
