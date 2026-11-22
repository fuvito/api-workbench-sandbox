"""Payments: oneOf by discriminator (`method`), allOf-composed responses, anyOf reference."""

import hashlib
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import Field, StringConstraints

from app.ok.common import ApiError, Page, StrictModel, not_found, paged, unprocessable
from app.ok.listing import get_page
from app.store import Store

COLLECTION = "payments"
KEYS = "idempotency_keys"
MAX_KEYS = 1000  # bounded; reset clears them
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
    async def list_payments(response: Response, page: Page = Depends(get_page)) -> dict:
        return paged(await store.list(COLLECTION), page, response)

    @router.post("/payments", status_code=201)
    async def create_payment(
        body: PaymentInput,
        response: Response,
        idempotency_key: str | None = Header(default=None, min_length=1, max_length=64),
    ) -> dict:
        """Idempotency-Key: same key and body replays the first payment (200, no second
        record); same key with a different body is 422; no key behaves as before."""
        payload = body.model_dump(exclude_unset=True)
        fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        async with store.tx() as tx:
            if idempotency_key is not None:
                seen = tx.get(KEYS, idempotency_key)
                if seen is not None:
                    if seen["fingerprint"] != fingerprint:
                        raise unprocessable("Idempotency-Key was already used with a different body")
                    response.status_code = 200
                    return tx.get(COLLECTION, seen["paymentId"])
                if len(tx.list(KEYS)) >= MAX_KEYS:
                    raise ApiError(422, "too_many_keys", "idempotency key store is full; reset it")
            payment = {"id": tx.next_id(COLLECTION, "pay"), **payload, "status": "authorized"}
            tx.put(COLLECTION, payment["id"], payment)
            if idempotency_key is not None:
                tx.put(
                    KEYS,
                    idempotency_key,
                    {"id": idempotency_key, "fingerprint": fingerprint, "paymentId": payment["id"]},
                )
            return payment

    @router.get("/payments/{payment_id}")
    async def get_payment(payment_id: str) -> dict:
        payment = await store.get(COLLECTION, payment_id)
        if payment is None:
            raise not_found("payment", payment_id)
        return payment

    return router
