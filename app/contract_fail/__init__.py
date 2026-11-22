"""The `contract-fail` API: responses that deliberately differ from the spec."""

from fastapi import APIRouter

from app.contract_fail import cases


def build_contract_fail_router() -> APIRouter:
    router = APIRouter(prefix="/contract-fail")
    router.include_router(cases.build_router())
    return router
