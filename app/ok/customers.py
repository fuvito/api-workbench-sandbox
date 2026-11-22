"""Customers: format/pattern constraints, nullable and optional fields, maps, unique arrays."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, Response
from pydantic import Field, field_validator

from app.ok.common import Page, StrictModel, not_found, paged
from app.store import Store

COLLECTION = "customers"
EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE = r"^\+?[0-9]{7,15}$"
DATE = r"^\d{4}-\d{2}-\d{2}$"
UUID = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class CustomerInput(StrictModel):
    """Optional fields use `default=None` with a non-null type, so absent is fine and null is
    rejected. Only birthDate is declared nullable in the spec."""

    email: str = Field(pattern=EMAIL, max_length=254)
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(default=None, pattern=PHONE)
    birthDate: str | None = Field(default=None, pattern=DATE)
    externalRef: str = Field(default=None, pattern=UUID)
    tags: list[str] = Field(default=None, max_length=10)
    preferences: dict[str, str] = Field(default=None, max_length=20)

    @field_validator("birthDate")
    @classmethod
    def _real_date(cls, v: str | None) -> str | None:
        if v is not None:
            date.fromisoformat(v)  # "2026-02-31" matches the pattern but is not a date
        return v

    @field_validator("tags")
    @classmethod
    def _unique_non_empty(cls, v: list[str]) -> list[str]:
        if any(not t for t in v):
            raise ValueError("tags must not be empty strings")
        if len(set(v)) != len(v):
            raise ValueError("tags must be unique")
        return v


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/customers")
    async def list_customers(response: Response, page: Page = Depends()) -> dict:
        return paged(await store.list(COLLECTION), page, response)

    @router.post("/customers", status_code=201)
    async def create_customer(body: CustomerInput) -> dict:
        now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        record = {**body.model_dump(exclude_unset=True), "createdAt": now}
        return await store.create_auto(COLLECTION, "c", record)

    @router.get("/customers/{customer_id}")
    async def get_customer(customer_id: str) -> dict:
        customer = await store.get(COLLECTION, customer_id)
        if customer is None:
            raise not_found("customer", customer_id)
        return customer

    @router.delete("/customers/{customer_id}", status_code=204)
    async def delete_customer(customer_id: str) -> Response:
        if not await store.delete(COLLECTION, customer_id):
            raise not_found("customer", customer_id)
        return Response(status_code=204)

    return router
