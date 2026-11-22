"""Shared pieces of the strict `ok` API: error shape and request-model base."""

from fastapi import Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """No type coercion ("5" is not an integer) and no unknown fields."""

    model_config = ConfigDict(strict=True, extra="forbid")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def not_found(what: str, id_: str) -> ApiError:
    return ApiError(404, "not_found", f"{what} {id_!r} does not exist")


def unprocessable(message: str) -> ApiError:
    return ApiError(422, "unprocessable", message)


def error_body(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return error_body(exc.status, exc.code, exc.message)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Malformed input on /ok is 400 with the declared Error shape.

    FastAPI's default is 422 with a different body, so it is kept for other families.
    """
    if not request.url.path.startswith("/ok/"):
        return await request_validation_exception_handler(request, exc)
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    return error_body(400, "invalid_request", f"{where}: {first['msg']}")
