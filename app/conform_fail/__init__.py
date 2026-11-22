"""The `conform-fail` API: request, probe, run and behavior failures."""

from fastapi import APIRouter

from app.conform_fail import lenient


def build_conform_fail_router() -> APIRouter:
    router = APIRouter(prefix="/conform-fail")
    router.include_router(lenient.build_router())
    return router
