"""Security examples: bearer, basic, API key in a header and in the query string.

Credentials are documented fake fixtures, not secrets. Each secured operation lives on its
own small read-only endpoint so the rest of the API stays public.
"""

import base64
import secrets

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.ok.common import ApiError, Page, paged
from app.ok.listing import get_page
from app.store import Store

BEARER_TOKEN = "test-token"
BASIC_USER, BASIC_PASS = "test-user", "test-pass"
API_KEY = "test-api-key"


class Unauthorized(ApiError):
    def __init__(self, challenge: str) -> None:
        super().__init__(401, "unauthorized", "missing or invalid credentials")
        self.challenge = challenge


def _same(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


async def unauthorized_handler(_: Request, exc: Unauthorized) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"code": exc.code, "message": exc.message},
        headers={"WWW-Authenticate": exc.challenge},
    )


def require_bearer(request: Request) -> None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not _same(token, BEARER_TOKEN):
        raise Unauthorized('Bearer realm="ok"')


def require_basic(request: Request) -> None:
    scheme, _, encoded = request.headers.get("authorization", "").partition(" ")
    try:
        user, _, password = base64.b64decode(encoded, validate=True).decode().partition(":")
    except ValueError:
        user = password = ""
    # Evaluate both comparisons so timing does not reveal which part was wrong.
    ok = _same(user, BASIC_USER) & _same(password, BASIC_PASS)
    if scheme.lower() != "basic" or not ok:
        raise Unauthorized('Basic realm="ok"')


def require_key_header(request: Request) -> None:
    if not _same(request.headers.get("x-api-key", ""), API_KEY):
        raise Unauthorized('ApiKey realm="ok"')


def require_key_query(request: Request) -> None:
    if not _same(request.query_params.get("api_key", ""), API_KEY):
        raise Unauthorized('ApiKey realm="ok"')


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/me", dependencies=[Depends(require_bearer)])
    async def get_me() -> dict:
        return {"user": BASIC_USER, "scopes": ["read"]}

    @router.get("/audit-events", dependencies=[Depends(require_basic)])
    async def list_audit_events(response: Response, page: Page = Depends(get_page)) -> dict:
        return paged(await store.list("audit_events"), page, response)

    @router.get("/feature-flags", dependencies=[Depends(require_key_query)])
    async def get_feature_flags() -> dict:
        return (await store.get("feature_flags", "main"))["values"]

    @router.get("/partner-status", dependencies=[Depends(require_key_header)])
    async def get_partner_status() -> dict:
        return {"partner": "acme", "status": "active"}

    return router
