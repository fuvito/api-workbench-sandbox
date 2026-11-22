"""The `conform-fail` API: request, probe, run and behavior failures."""

from fastapi import APIRouter

from app.conform_fail import disagree, drift, lenient, requests, rules, timing
from app.store import Store


def build_conform_fail_router(store: Store) -> APIRouter:
    router = APIRouter(prefix="/conform-fail")
    router.include_router(lenient.build_router())
    router.include_router(disagree.build_router())
    router.include_router(requests.build_router())
    router.include_router(timing.build_router(store))
    router.include_router(drift.build_router())
    router.include_router(rules.build_router(store))
    return router
