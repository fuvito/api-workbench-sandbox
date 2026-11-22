"""The `ok` API: strict, correct baseline. Handlers mirror specs/ok.yaml."""

from fastapi import APIRouter

from app.ok import orders, products, projects
from app.store import Store


def build_ok_router(store: Store) -> APIRouter:
    router = APIRouter(prefix="/ok")
    router.include_router(products.build(store))
    router.include_router(orders.build(store))
    router.include_router(projects.build(store))
    return router
