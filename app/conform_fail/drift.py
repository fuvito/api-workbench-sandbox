"""Baseline drift: one operation that is correct at drift 0 and breaks at drift 1 or higher.

The drift level is set at startup (the DRIFT environment variable or `--drift=<n>`) and never
changes while the server runs: there is no mode-switching endpoint. On Cloud Run the only way to
change it is a new revision. It lets a baseline be recorded at drift 0 and a later run at drift 1
show exactly one NEW violation (`clrsig conform --baseline`, CS-RUN-006).
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/drift/report")
    async def drift_report(request: Request) -> JSONResponse:
        level = request.app.state.settings.drift
        total: int | str = 3
        if level >= 1:
            total = "3"  # drift 1: the integer total becomes a string (a wrong type, CS-RESP-006)
        return JSONResponse({"total": total, "items": ["a", "b", "c"]})

    return router
