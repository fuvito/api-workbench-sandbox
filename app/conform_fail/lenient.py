"""Lenient and strict operations for `clrsig conform --negative`.

ClearSignal's negative probes send four kinds of bad request and expect a 4xx: a body without a
required field (CS-PROBE-001), a field of the wrong type (CS-PROBE-002), a missing required query
parameter (CS-PROBE-003) and missing credentials (CS-PROBE-004).

Each LENIENT operation skips exactly one of those validations and enforces all the others, so it
fails exactly one probe kind. Three more lenient operations skip checks ClearSignal does not probe
today (wrong credentials, enum and boundary values, unknown fields): they pass, pinning the gaps.
Each STRICT operation enforces everything, as the control group.

Handlers read the body by hand: FastAPI/Pydantic validation would reject what these operations
must deliberately accept.
"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

TOKEN = "test-token"  # the documented fake credential, same as the ok API


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def created() -> JSONResponse:
    return JSONResponse(status_code=201, content={"id": 1})


async def read_object(request: Request) -> dict[str, Any] | None:
    """The JSON body if it is an object; None otherwise (every operation answers 400 then)."""
    try:
        data = await request.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def bearer_token(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" and token else None


def build_router() -> APIRouter:
    router = APIRouter()

    # ================================================================ lenient

    @router.post("/lenient/missing-field")
    async def lenient_missing_field(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or ("name" in body and not isinstance(body["name"], str)):
            return error(400, "invalid_request", "name must be a string")
        return created()  # deliberately accepts a body without name

    @router.post("/lenient/wrong-type")
    async def lenient_wrong_type(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or "quantity" not in body:
            return error(400, "invalid_request", "quantity is required")
        return created()  # deliberately accepts "lots"

    @router.get("/lenient/missing-query")
    async def lenient_missing_query(q: str | None = None) -> JSONResponse:
        return JSONResponse({"q": q or ""})  # deliberately answers without q

    @router.get("/lenient/no-auth")
    async def lenient_no_auth() -> JSONResponse:
        return JSONResponse({"secret": "s3cret"})  # deliberately never asks for credentials

    @router.get("/lenient/wrong-auth")
    async def lenient_wrong_auth(request: Request) -> JSONResponse:
        if bearer_token(request) is None:
            return error(401, "unauthorized", "a bearer token is required")
        return JSONResponse({"secret": "s3cret"})  # deliberately accepts any token

    @router.post("/lenient/enum-and-boundary")
    async def lenient_enum_and_boundary(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or not isinstance(body.get("level"), str) or not is_int(body.get("percent")):
            return error(400, "invalid_request", "level must be a string and percent an integer")
        return created()  # deliberately accepts level "extreme" and percent 5000

    @router.post("/lenient/unknown-fields")
    async def lenient_unknown_fields(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or not isinstance(body.get("name"), str) or not body["name"]:
            return error(400, "invalid_request", "name must be a non-empty string")
        return created()  # deliberately accepts extra fields

    # ================================================================= strict

    @router.post("/strict/missing-field")
    async def strict_missing_field(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or not isinstance(body.get("name"), str) or not body["name"]:
            return error(400, "invalid_request", "name is required and must be a non-empty string")
        return created()

    @router.post("/strict/wrong-type")
    async def strict_wrong_type(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or not is_int(body.get("quantity")) or body["quantity"] < 1:
            return error(400, "invalid_request", "quantity is required and must be an integer of at least 1")
        return created()

    @router.get("/strict/missing-query")
    async def strict_missing_query(q: str | None = None) -> JSONResponse:
        if not q:
            return error(400, "invalid_request", "q is required")
        return JSONResponse({"q": q})

    async def require_token(request: Request) -> JSONResponse | None:
        token = bearer_token(request)
        if token != TOKEN:
            return error(401, "unauthorized", "a valid bearer token is required")
        return None

    @router.get("/strict/no-auth")
    async def strict_no_auth(request: Request) -> JSONResponse:
        return await require_token(request) or JSONResponse({"secret": "s3cret"})

    @router.get("/strict/wrong-auth")
    async def strict_wrong_auth(request: Request) -> JSONResponse:
        return await require_token(request) or JSONResponse({"secret": "s3cret"})

    @router.post("/strict/enum-and-boundary")
    async def strict_enum_and_boundary(request: Request) -> JSONResponse:
        body = await read_object(request)
        percent = body.get("percent") if body else None
        if body is None or body.get("level") not in ("low", "high") or not is_int(percent) or not 0 <= percent <= 100:
            return error(400, "invalid_request", "level must be low or high and percent 0 to 100")
        return created()

    @router.post("/strict/unknown-fields")
    async def strict_unknown_fields(request: Request) -> JSONResponse:
        body = await read_object(request)
        if body is None or set(body) != {"name"} or not isinstance(body["name"], str) or not body["name"]:
            return error(400, "invalid_request", "only a non-empty string name is allowed")
        return created()

    return router
