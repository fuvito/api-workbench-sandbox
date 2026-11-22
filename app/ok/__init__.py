"""The `ok` API: strict, correct baseline. Handlers mirror specs/ok.yaml."""

from fastapi import APIRouter

from app.ok import customers, discounts, features, invoices, misc, notifications, orders, params, payments, products, projects, ratelimit, reports, security
from app.store import Store


def build_ok_router(store: Store) -> APIRouter:
    router = APIRouter(prefix="/ok")
    router.include_router(products.build(store))
    router.include_router(orders.build(store))
    router.include_router(invoices.build(store))
    router.include_router(discounts.build(store))
    router.include_router(reports.build(store))
    router.include_router(ratelimit.build(store))
    router.include_router(notifications.build(store))
    router.include_router(params.build(store))
    router.include_router(projects.build(store))
    router.include_router(customers.build(store))
    router.include_router(payments.build(store))
    router.include_router(security.build(store))
    router.include_router(misc.build(store))
    router.include_router(features.build(store))
    return router
