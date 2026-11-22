"""Shared pieces of the strict `ok` API: error shape, request models, list helpers."""

import hashlib
import json
from typing import Any, Literal

from fastapi import Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, model_validator

from app import clock
from app.latency import TooManySlowRequests


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


def utc_now() -> str:
    """Current UTC time as an RFC 3339 string with second precision (matches `date-time`)."""
    return clock.utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status, self.code, self.message = status, code, message


def etag_of(record: dict) -> str:
    """Strong ETag of a representation: a short hash of its canonical JSON."""
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"))
    return '"' + hashlib.sha256(raw.encode()).hexdigest()[:16] + '"'


def check_if_match(header: str | None, record: dict, *, required: bool) -> None:
    """Optimistic concurrency: 428 when required and absent, 412 when it does not match.

    `*` matches any existing record; several comma-separated tags are allowed; weak tags
    (W/"...") never match, as strong comparison requires.
    """
    if header is None:
        if required:
            raise ApiError(428, "precondition_required", "an If-Match header is required")
        return
    tags = [t.strip() for t in header.split(",")]
    if "*" not in tags and etag_of(record) not in tags:
        raise ApiError(412, "precondition_failed", "the resource changed; fetch it again")


def with_etag(response: Response, record: dict) -> dict:
    """Set the ETag header from the representation being returned, and return it."""
    response.headers["ETag"] = etag_of(record)
    return record


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


async def too_many_slow_handler(request: Request, _: TooManySlowRequests) -> JSONResponse:
    return error_body(request, 503, "too_many_slow_requests", "too many slow requests in progress; retry")


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
    """Validated `limit` / `offset`; built by `app.ok.listing.get_page`."""

    def __init__(self, limit: int, offset: int) -> None:
        self.limit, self.offset = limit, offset


def as_bool(value: BoolText | None) -> bool | None:
    return None if value is None else value == "true"


def paged(items: list[dict], page: Page, response: Response) -> dict[str, Any]:
    """Slice one page; body `total` and X-Total-Count are the count before pagination."""
    total = len(items)
    response.headers["X-Total-Count"] = str(total)
    return {"items": items[page.offset : page.offset + page.limit], "total": total}
