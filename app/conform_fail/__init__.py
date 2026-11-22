"""The `conform-fail` API: request, probe, run and behavior failures."""

from fastapi import APIRouter

from app.conform_fail import disagree, lenient, requests


def build_conform_fail_router() -> APIRouter:
    router = APIRouter(prefix="/conform-fail")
    router.include_router(lenient.build_router())
    router.include_router(disagree.build_router())
    router.include_router(requests.build_router())
    return router
