from fastapi import APIRouter, Response
from pydantic import Field

from app.ok.common import StrictModel, not_found, unprocessable
from app.store import Store

COLLECTION = "orders"


class OrderInput(StrictModel):
    productId: str = Field(min_length=1)
    quantity: int = Field(ge=1)


def build(store: Store) -> APIRouter:
    router = APIRouter()

    async def require_product(product_id: str) -> None:
        if await store.get("products", product_id) is None:
            raise unprocessable(f"product {product_id!r} does not exist")

    @router.get("/orders")
    async def list_orders() -> dict:
        items = await store.list(COLLECTION)
        return {"items": items, "total": len(items)}

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

    @router.delete("/orders/{order_id}", status_code=204)
    async def delete_order(order_id: str) -> Response:
        if not await store.delete(COLLECTION, order_id):
            raise not_found("order", order_id)
        return Response(status_code=204)

    return router
