"""Correct operations whose outcome under ClearSignal depends on the environment file.

Nothing is wrong with these handlers or their spec. They exist so that the failures caused by
the environment ClearSignal is given (a value of the wrong type, a missing value) are isolated:
with the right environment each passes, and the only thing that changes between a pass and a
failure is the environment file.

    GET  /requests/param-type/{itemId}   integer path parameter
    POST /requests/body-value            number in the body, taken from the environment
"""

import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

INTEGER = re.compile(r"^-?[0-9]{1,18}$")


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/requests/param-type/{item_id}")
    async def param_type(item_id: str) -> JSONResponse:
        if not INTEGER.match(item_id):  # any integer the spec allows, negative ones included
            return error(400, "invalid_id", "itemId must be an integer")
        return JSONResponse({"id": int(item_id)})

    @router.post("/requests/body-value")
    async def body_value(request: Request) -> JSONResponse:
        try:
            body: Any = await request.json()
        except ValueError:
            body = None
        amount = body.get("amount") if isinstance(body, dict) else None
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
            return error(400, "invalid_request", "amount must be a non-negative number")
        return JSONResponse(status_code=201, content={"id": 1})

    return router
