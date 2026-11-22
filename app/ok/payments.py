"""Payments: oneOf by discriminator (`method`), allOf-composed responses, anyOf reference."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import Field, StringConstraints

from app.ok.common import Page, StrictModel, not_found, paged
from app.store import Store

COLLECTION = "payments"
UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"

# anyOf: a UUID string or a positive integer (strict mode keeps "42" and true out).
Reference = Annotated[str, StringConstraints(pattern=UUID)] | Annotated[int, Field(ge=1)]
Currency = Literal["USD", "EUR", "GBP"]


class CardPaymentInput(StrictModel):
    method: Literal["card"]
    amount: float = Field(ge=0.01)
    currency: Currency
    cardLast4: str = Field(pattern=r"^[0-9]{4}$")
    reference: Reference = Field(default=None)


class BankPaymentInput(StrictModel):
    method: Literal["bank"]
    amount: float = Field(ge=0.01)
    currency: Currency
    iban: str = Field(pattern=r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}$")
    reference: Reference = Field(default=None)


PaymentInput = Annotated[CardPaymentInput | BankPaymentInput, Field(discriminator="method")]


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/payments")
    async def list_payments(response: Response, page: Page = Depends()) -> dict:
        return paged(await store.list(COLLECTION), page, response)

    @router.post("/payments", status_code=201)
    async def create_payment(body: PaymentInput) -> dict:
        record = {**body.model_dump(exclude_unset=True), "status": "authorized"}
        return await store.create_auto(COLLECTION, "pay", record)

    @router.get("/payments/{payment_id}")
    async def get_payment(payment_id: str) -> dict:
        payment = await store.get(COLLECTION, payment_id)
        if payment is None:
            raise not_found("payment", payment_id)
        return payment

    return router
