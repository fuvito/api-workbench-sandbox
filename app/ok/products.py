from fastapi import APIRouter, Response
from pydantic import Field

from app.ok.common import StrictModel, not_found
from app.store import Store

COLLECTION = "products"


class ProductInput(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(ge=0)
    stock: int = Field(ge=0)


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/products")
    async def list_products() -> dict:
        items = await store.list(COLLECTION)
        return {"items": items, "total": len(items)}

    @router.post("/products", status_code=201)
    async def create_product(body: ProductInput) -> dict:
        return await store.create_auto(COLLECTION, "p", body.model_dump())

    @router.get("/products/{product_id}")
    async def get_product(product_id: str) -> dict:
        product = await store.get(COLLECTION, product_id)
        if product is None:
            raise not_found("product", product_id)
        return product

    @router.put("/products/{product_id}")
    async def replace_product(product_id: str, body: ProductInput) -> dict:
        record = {"id": product_id, **body.model_dump()}
        if not await store.update(COLLECTION, product_id, record):
            raise not_found("product", product_id)
        return record

    @router.delete("/products/{product_id}", status_code=204)
    async def delete_product(product_id: str) -> Response:
        if not await store.delete(COLLECTION, product_id):
            raise not_found("product", product_id)
        return Response(status_code=204)

    return router
