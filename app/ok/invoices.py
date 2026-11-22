"""Invoices: one per paid order, with sequential numbers (INV-000001, INV-000002, ...)."""

from fastapi import APIRouter, Depends, Response

from app.ok.common import ApiError, Page, not_found, paged, utc_now
from app.store import Store

COLLECTION = "invoices"
BILLABLE = ("paid", "shipped", "delivered")


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.post("/orders/{order_id}/invoice", status_code=201)
    async def create_invoice(order_id: str) -> dict:
        async with store.tx() as tx:
            order = tx.get("orders", order_id)
            if order is None:
                raise not_found("order", order_id)
            if order["status"] not in BILLABLE:
                raise ApiError(409, "not_billable", f"a {order['status']} order cannot be invoiced")
            if any(i["orderId"] == order_id for i in tx.list(COLLECTION)):
                raise ApiError(409, "already_invoiced", f"order {order_id!r} already has an invoice")
            n = tx.next_n(COLLECTION)
            invoice = {
                "id": f"inv-{n}",
                "number": f"INV-{n:06d}",
                "orderId": order_id,
                "total": order["total"],
                "issuedAt": utc_now(),
            }
            tx.put(COLLECTION, invoice["id"], invoice)
            return invoice

    @router.get("/invoices")
    async def list_invoices(response: Response, page: Page = Depends()) -> dict:
        return paged(await store.list(COLLECTION), page, response)

    @router.get("/invoices/{invoice_id}")
    async def get_invoice(invoice_id: str) -> dict:
        invoice = await store.get(COLLECTION, invoice_id)
        if invoice is None:
            raise not_found("invoice", invoice_id)
        return invoice

    return router
