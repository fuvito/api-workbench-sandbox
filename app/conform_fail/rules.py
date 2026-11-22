"""Business rules the server breaks: they only show in scenario assertions.

The spec declares the CORRECT rule (a 409, a 422, a 401 it lists). Every handler validates its
input strictly (so negative probes still pass) and breaks exactly one rule:

    POST /rules/orders             above the stock is accepted; the stock goes negative
    POST /rules/orders/{id}/cancel a shipped order can be cancelled (200, not 409)
    POST /rules/customers          a duplicate email is accepted (201, not 409)
    POST /rules/withdrawals        insufficient funds answered 200 with an error body (not 422)
    GET  /rules/items              serving page 1 inserts an item at the head: page 2 repeats one
    GET  /rules/protected          the token `expired-token` is accepted although it expired

The stale `If-Match` rule is the existing PUT /lost-update. All state lives in the family's store
and is restored by `POST /conform-fail/__admin/reset`; every collection is bounded.
"""

from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.store import Store

MAX_RECORDS = 200
BALANCE = 100
FIRST_PAGE_INSERT_LIMIT = 40  # the "other writer" stops adding after this many extra items


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


async def read_object(request: Request) -> dict[str, Any] | None:
    try:
        data = await request.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def build_router(store: Store) -> APIRouter:
    router = APIRouter()

    # ---- stock and orders ----

    @router.get("/rules/stock")
    async def stock() -> JSONResponse:
        record = await store.get("rules_stock", "stock")
        return JSONResponse({"stock": record["n"]})

    @router.post("/rules/orders", status_code=201)
    async def create_order(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or set(body) != {"quantity"} or not is_int(body["quantity"]) or body["quantity"] < 1:
            return error(400, "invalid_request", "quantity must be an integer of at least 1")
        async with store.tx() as tx:
            if len(tx.list("rules_orders")) >= MAX_RECORDS:
                return error(422, "limit", "order limit reached; reset the family")
            level = tx.get("rules_stock", "stock")
            level["n"] -= body["quantity"]  # RULE BROKEN: no check against the stock
            tx.put("rules_stock", "stock", level)
            order = {"id": tx.next_id("rules_orders", "o"), "quantity": body["quantity"], "status": "pending"}
            tx.put("rules_orders", order["id"], order)
            return JSONResponse(status_code=201, content=order)

    @router.post("/rules/orders/{order_id}/ship")
    async def ship_order(order_id: str) -> JSONResponse:
        async with store.tx() as tx:
            order = tx.get("rules_orders", order_id)
            if order is None:
                return error(404, "not_found", f"order {order_id!r} does not exist")
            if order["status"] != "pending":
                return error(409, "illegal_transition", f"cannot ship a {order['status']} order")
            order["status"] = "shipped"
            tx.put("rules_orders", order_id, order)
            return JSONResponse(order)

    @router.post("/rules/orders/{order_id}/cancel")
    async def cancel_order(order_id: str) -> JSONResponse:
        async with store.tx() as tx:
            order = tx.get("rules_orders", order_id)
            if order is None:
                return error(404, "not_found", f"order {order_id!r} does not exist")
            if order["status"] == "cancelled":
                return error(409, "illegal_transition", "the order is already cancelled")
            order["status"] = "cancelled"  # RULE BROKEN: a shipped order is cancelled too
            tx.put("rules_orders", order_id, order)
            return JSONResponse(order)

    # ---- customers ----

    @router.post("/rules/customers", status_code=201)
    async def create_customer(request: Request) -> JSONResponse:
        body = await read_object(request)
        email = body.get("email") if body is not None and set(body) == {"email"} else None
        if not isinstance(email, str) or len(email) < 3:
            return error(400, "invalid_request", "email must be a string of at least 3 characters")
        async with store.tx() as tx:
            if len(tx.list("rules_customers")) >= MAX_RECORDS:
                return error(422, "limit", "customer limit reached; reset the family")
            customer_id = tx.next_id("rules_customers", "c")  # RULE BROKEN: the email is never compared
            tx.put("rules_customers", customer_id, {"id": customer_id, "email": email})
            return JSONResponse(status_code=201, content={"id": 1})

    # ---- withdrawals ----

    @router.post("/rules/withdrawals")
    async def withdraw(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or set(body) != {"amount"} or not is_int(body["amount"]) or body["amount"] < 1:
            return error(400, "invalid_request", "amount must be an integer of at least 1")
        async with store.tx() as tx:
            account = tx.get("rules_account", "main")
            if body["amount"] > account["balance"]:
                # RULE BROKEN: the refusal is a 200 with an error body, not the declared 422
                return JSONResponse({"error": "insufficient funds"})
            account["balance"] -= body["amount"]
            tx.put("rules_account", "main", account)
            return JSONResponse({"id": "w-1", "balance": account["balance"]})

    # ---- unstable pagination ----

    @router.get("/rules/items")
    async def items(
        limit: int = Query(3, ge=1, le=20),
        offset: int = Query(0, ge=0),
    ) -> JSONResponse:
        async with store.tx() as tx:
            ordered = sorted(tx.list("rules_items"), key=lambda i: i["order"])
            page = [{"id": i["id"]} for i in ordered[offset : offset + limit]]
            body = {"total": len(ordered), "items": page}
            if offset == 0 and len(ordered) < 6 + FIRST_PAGE_INSERT_LIMIT:
                # RULE BROKEN: another writer adds an item at the head right after page 1 is served
                new_id = tx.next_id("rules_items", "i")
                head = ordered[0]["order"] if ordered else 0
                tx.put("rules_items", new_id, {"id": new_id, "order": head - 1})
            return JSONResponse(body)

    # ---- expired token ----

    @router.get("/rules/protected")
    async def protected(request: Request) -> JSONResponse:
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or token not in ("valid-token", "expired-token"):
            return error(401, "unauthorized", "a valid bearer token is required")
        # RULE BROKEN: expired-token expired a day ago and is accepted anyway
        return JSONResponse({"secret": "s3cret"})

    return router
