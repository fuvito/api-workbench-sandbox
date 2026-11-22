"""Discount codes: use after `expiresAt` answers 410 Gone.

Expiry is computed from the clock when a request arrives (no background timers).
"""

from datetime import datetime

from fastapi import APIRouter

from app import clock
from app.ok.common import ApiError, not_found
from app.store import Store

COLLECTION = "discount_codes"


def is_expired(record: dict) -> bool:
    expires = datetime.fromisoformat(record["expiresAt"].replace("Z", "+00:00"))
    return expires <= clock.utcnow()


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/discount-codes/{code}")
    async def get_discount_code(code: str) -> dict:
        record = await store.get(COLLECTION, code)
        if record is None:
            raise not_found("discount code", code)
        return record

    @router.post("/discount-codes/{code}/redeem")
    async def redeem_discount_code(code: str) -> dict:
        record = await store.get(COLLECTION, code)
        if record is None:
            raise not_found("discount code", code)
        if is_expired(record):
            raise ApiError(410, "expired", f"discount code {code!r} expired at {record['expiresAt']}")
        return record

    return router
