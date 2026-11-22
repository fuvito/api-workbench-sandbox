from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import Field

from app.ok.common import BoolText, Page, PatchModel, StrictModel, as_bool, not_found, paged
from app.ok.listing import get_page
from app.store import Store

COLLECTION = "products"
SORTS = {
    "name": ("name", False),
    "-name": ("name", True),
    "price": ("price", False),
    "-price": ("price", True),
}


class ProductInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0)
    stock: int = Field(ge=0)


class ProductPatch(PatchModel):
    # Optional but never null: the type is str, the default only applies when absent.
    name: str = Field(default=None, min_length=1, max_length=100)
    price: float = Field(default=None, ge=0)
    stock: int = Field(default=None, ge=0)


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/products")
    async def list_products(
        response: Response,
        page: Page = Depends(get_page),
        q: str | None = Query(None, min_length=1, max_length=100),
        min_price: float | None = Query(None, alias="minPrice", ge=0, allow_inf_nan=False),
        max_price: float | None = Query(None, alias="maxPrice", ge=0, allow_inf_nan=False),
        in_stock: BoolText | None = Query(None, alias="inStock"),
        sort: Literal["name", "-name", "price", "-price"] | None = None,
    ) -> dict:
        items = await store.list(COLLECTION)
        if q is not None:
            items = [p for p in items if q.lower() in p["name"].lower()]
        if min_price is not None:
            items = [p for p in items if p["price"] >= min_price]
        if max_price is not None:
            items = [p for p in items if p["price"] <= max_price]
        if as_bool(in_stock) is not None:
            items = [p for p in items if (p["stock"] > 0) == as_bool(in_stock)]
        if sort is not None:
            key, reverse = SORTS[sort]
            items.sort(key=lambda p: p[key], reverse=reverse)
        return paged(items, page, response)

    @router.head("/products")
    async def head_products() -> Response:
        total = len(await store.list(COLLECTION))
        return Response(status_code=200, headers={"X-Total-Count": str(total)})

    @router.options("/products", status_code=204)
    async def options_products() -> Response:
        return Response(status_code=204, headers={"Allow": "GET, HEAD, POST, OPTIONS"})

    @router.post("/products", status_code=201)
    async def create_product(body: ProductInput) -> dict:
        return await store.create_auto(COLLECTION, "p", body.model_dump())

    @router.get("/products/{product_id}")
    async def get_product(product_id: str) -> dict:
        product = await store.get(COLLECTION, product_id)
        if product is None:
            raise not_found("product", product_id)
        return product

    @router.head("/products/{product_id}")
    async def head_product(product_id: str) -> Response:
        # Bare 404: a HEAD response carries no body.
        found = await store.get(COLLECTION, product_id) is not None
        return Response(status_code=200 if found else 404)

    @router.options("/products/{product_id}", status_code=204)
    async def options_product(product_id: str) -> Response:
        allow = "GET, HEAD, PUT, PATCH, DELETE, OPTIONS"
        return Response(status_code=204, headers={"Allow": allow})

    @router.put("/products/{product_id}")
    async def replace_product(product_id: str, body: ProductInput) -> dict:
        record = {"id": product_id, **body.model_dump()}
        if not await store.update(COLLECTION, product_id, record):
            raise not_found("product", product_id)
        return record

    @router.patch("/products/{product_id}")
    async def update_product(product_id: str, body: ProductPatch) -> dict:
        product = await store.get(COLLECTION, product_id)
        if product is None:
            raise not_found("product", product_id)
        product.update(body.changes())
        await store.update(COLLECTION, product_id, product)
        return product

    @router.delete("/products/{product_id}", status_code=204)
    async def delete_product(product_id: str) -> Response:
        if not await store.delete(COLLECTION, product_id):
            raise not_found("product", product_id)
        return Response(status_code=204)

    return router
