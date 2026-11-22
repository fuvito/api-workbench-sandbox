"""Orders: stock rules, state machine, computed totals.

States: pending -> paid -> shipped -> delivered, and pending/paid -> cancelled.
Paying takes stock, cancelling a paid order gives it back. Only pending orders can be edited.
Failed rules answer 409 (illegal move / not editable) or 422 (not enough stock, unknown product).
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import Field

from app.ok.common import (
    ApiError,
    Page,
    PatchModel,
    StrictModel,
    check_if_match,
    not_found,
    paged,
    unprocessable,
    utc_now,
    with_etag,
)
from app.store import Store, Tx

COLLECTION = "orders"
TAX_RATE = Decimal("0.10")
Status = Literal["pending", "paid", "shipped", "delivered", "cancelled"]

# action -> (states it may start from, state it leads to)
ACTIONS: dict[str, tuple[tuple[str, ...], str]] = {
    "pay": (("pending",), "paid"),
    "ship": (("paid",), "shipped"),
    "deliver": (("shipped",), "delivered"),
    "cancel": (("pending", "paid"), "cancelled"),
}


def compute_total(unit_price: float, quantity: int) -> float:
    """Subtotal plus a fixed 10% tax, rounded to cents."""
    amount = Decimal(str(unit_price)) * quantity * (1 + TAX_RATE)
    return float(amount.quantize(Decimal("0.01"), ROUND_HALF_UP))


class OrderInput(StrictModel):
    productId: str = Field(min_length=1)
    quantity: int = Field(ge=1)


class OrderPatch(PatchModel):
    productId: str = Field(default=None, min_length=1)
    quantity: int = Field(default=None, ge=1)


def _product_with_stock(tx: Tx, product_id: str, quantity: int) -> dict:
    product = tx.get("products", product_id)
    if product is None:
        raise unprocessable(f"product {product_id!r} does not exist")
    if quantity > product["stock"]:
        raise unprocessable(
            f"insufficient stock: {quantity} requested, {product['stock']} available"
        )
    return product


def _get_order(tx: Tx, order_id: str) -> dict:
    order = tx.get(COLLECTION, order_id)
    if order is None:
        raise not_found("order", order_id)
    return order


def build(store: Store) -> APIRouter:
    router = APIRouter()

    async def edit(order_id: str, changes: dict, if_match: str | None) -> dict:
        async with store.tx() as tx:
            order = _get_order(tx, order_id)
            # Order of checks: 404, then 428/412 (precondition), then 409, then 422.
            check_if_match(if_match, order, required=True)
            if order["status"] != "pending":
                raise ApiError(409, "not_editable", f"a {order['status']} order cannot be edited")
            order.update(changes)
            product = _product_with_stock(tx, order["productId"], order["quantity"])
            order["unitPrice"] = product["price"]
            order["total"] = compute_total(product["price"], order["quantity"])
            order["updatedAt"] = utc_now()
            tx.put(COLLECTION, order_id, order)
            return order

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
    async def create_order(body: OrderInput, response: Response) -> dict:
        async with store.tx() as tx:
            product = _product_with_stock(tx, body.productId, body.quantity)
            now = utc_now()
            order = {
                "id": tx.next_id(COLLECTION, "o"),
                "productId": body.productId,
                "quantity": body.quantity,
                "status": "pending",
                "unitPrice": product["price"],
                "total": compute_total(product["price"], body.quantity),
                "createdAt": now,
                "updatedAt": now,
            }
            tx.put(COLLECTION, order["id"], order)
            return with_etag(response, order)

    @router.get("/orders/{order_id}")
    async def get_order(order_id: str, response: Response) -> dict:
        order = await store.get(COLLECTION, order_id)
        if order is None:
            raise not_found("order", order_id)
        return with_etag(response, order)

    @router.put("/orders/{order_id}")
    async def replace_order(
        order_id: str,
        body: OrderInput,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> dict:
        return with_etag(response, await edit(order_id, body.model_dump(), if_match))

    @router.patch("/orders/{order_id}")
    async def update_order(
        order_id: str,
        body: OrderPatch,
        response: Response,
        if_match: str | None = Header(default=None),
    ) -> dict:
        return with_etag(response, await edit(order_id, body.changes(), if_match))

    @router.delete("/orders/{order_id}", status_code=204)
    async def delete_order(order_id: str) -> Response:
        async with store.tx() as tx:
            order = _get_order(tx, order_id)
            if order["status"] not in ("pending", "cancelled"):
                raise ApiError(409, "not_deletable", f"a {order['status']} order cannot be deleted")
            tx.delete(COLLECTION, order_id)
        return Response(status_code=204)

    async def act(order_id: str, action: str) -> dict:
        allowed_from, target = ACTIONS[action]
        async with store.tx() as tx:
            order = _get_order(tx, order_id)
            if order["status"] not in allowed_from:
                raise ApiError(
                    409, "illegal_transition", f"cannot {action} an order that is {order['status']}"
                )
            product = tx.get("products", order["productId"])
            if action == "pay":
                if product is None or product["stock"] < order["quantity"]:
                    raise unprocessable("insufficient stock to pay this order")
                product["stock"] -= order["quantity"]
                tx.put("products", product["id"], product)
            elif action == "cancel" and order["status"] == "paid" and product is not None:
                product["stock"] += order["quantity"]
                tx.put("products", product["id"], product)
            order["status"] = target
            order["updatedAt"] = utc_now()
            tx.put(COLLECTION, order_id, order)
            return order

    @router.post("/orders/{order_id}/pay")
    async def pay_order(order_id: str, response: Response) -> dict:
        return with_etag(response, await act(order_id, "pay"))

    @router.post("/orders/{order_id}/ship")
    async def ship_order(order_id: str, response: Response) -> dict:
        return with_etag(response, await act(order_id, "ship"))

    @router.post("/orders/{order_id}/deliver")
    async def deliver_order(order_id: str, response: Response) -> dict:
        return with_etag(response, await act(order_id, "deliver"))

    @router.post("/orders/{order_id}/cancel")
    async def cancel_order(order_id: str, response: Response) -> dict:
        return with_etag(response, await act(order_id, "cancel"))

    return router
