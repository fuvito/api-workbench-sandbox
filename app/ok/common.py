"""Shared pieces of the strict `ok` API: error shape, request models, list helpers."""

from typing import Any, Literal

from fastapi import Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, model_validator


class StrictModel(BaseModel):
    """No type coercion ("5" is not an integer) and no unknown fields."""

    model_config = ConfigDict(strict=True, extra="forbid")


class PatchModel(StrictModel):
    """Base for PATCH bodies: every field optional (but never null), at least one present."""

    @model_validator(mode="after")
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        return self

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def not_found(what: str, id_: str) -> ApiError:
    return ApiError(404, "not_found", f"{what} {id_!r} does not exist")


def unprocessable(message: str) -> ApiError:
    return ApiError(422, "unprocessable", message)


# Paths whose error responses are RFC 7807 problem+json (declared that way in the spec).
PROBLEM_PREFIXES = ("/ok/customers",)

_TITLES = {400: "Bad Request", 404: "Not Found", 409: "Conflict", 422: "Unprocessable Entity"}


def error_body(request: Request, status: int, code: str, message: str) -> JSONResponse:
    if request.url.path.startswith(PROBLEM_PREFIXES):
        body = {
            "type": "about:blank",
            "title": _TITLES.get(status, "Error"),
            "status": status,
            "detail": message,
        }
        return JSONResponse(status_code=status, content=body, media_type="application/problem+json")
    return JSONResponse(status_code=status, content={"code": code, "message": message})


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_body(request, exc.status, exc.code, exc.message)


async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Malformed input on /ok is 400 with the declared error shape.

    FastAPI's default is 422 with a different body, so it is kept for other families.
    """
    if not request.url.path.startswith("/ok/"):
        return await request_validation_exception_handler(request, exc)
    first = exc.errors()[0]
    where = ".".join(str(p) for p in first["loc"])
    return error_body(request, 400, "invalid_request", f"{where}: {first['msg']}")


# ---- list helpers: pagination and boolean query values ----

BoolText = Literal["true", "false"]


class Page:
    """`limit` / `offset` query parameters, validated as the spec declares them."""

    def __init__(
        self,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ) -> None:
        self.limit, self.offset = limit, offset


def as_bool(value: BoolText | None) -> bool | None:
    return None if value is None else value == "true"


def paged(items: list[dict], page: Page, response: Response) -> dict[str, Any]:
    """Slice one page; body `total` and X-Total-Count are the count before pagination."""
    total = len(items)
    response.headers["X-Total-Count"] = str(total)
    return {"items": items[page.offset : page.offset + page.limit], "total": total}
