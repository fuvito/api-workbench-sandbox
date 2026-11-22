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

BEARER_TOKENS = {"test-token": ["read"], "admin-token": ["read", "admin"]}  # token -> scopes
BASIC_USER, BASIC_PASS = "test-user", "test-pass"
API_KEY = "test-api-key"


class Unauthorized(ApiError):
    def __init__(self, challenge: str) -> None:
        super().__init__(401, "unauthorized", "missing or invalid credentials")
        self.challenge = challenge


class Forbidden(ApiError):
    def __init__(self) -> None:
        super().__init__(403, "forbidden", "this token lacks the admin scope")


def _same(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


async def unauthorized_handler(_: Request, exc: Unauthorized) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"code": exc.code, "message": exc.message},
        headers={"WWW-Authenticate": exc.challenge},
    )


def bearer_scopes(request: Request) -> list[str]:
    """Scopes of the presented bearer token; 401 if the token is missing or unknown."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    scopes = None
    for known, known_scopes in BEARER_TOKENS.items():
        if _same(token, known):  # compare against every token: no early exit on a match
            scopes = known_scopes
    if scheme.lower() != "bearer" or scopes is None:
        raise Unauthorized('Bearer realm="ok"')
    return scopes


def require_bearer(request: Request) -> None:
    bearer_scopes(request)


def require_admin_scope(request: Request) -> None:
    """Authenticated but not allowed: a valid token without the admin scope is 403."""
    if "admin" not in bearer_scopes(request):
        raise Forbidden()


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

    @router.get("/me")
    async def get_me(request: Request) -> dict:
        return {"user": BASIC_USER, "scopes": bearer_scopes(request)}

    @router.get("/stats", dependencies=[Depends(require_admin_scope)])
    async def get_stats() -> dict:
        snapshot = await store.snapshot()
        counts = {name: len(items) for name, items in snapshot.items()}
        live_customers = [c for c in snapshot.get("customers", {}).values() if "deletedAt" not in c]
        return {
            "products": counts.get("products", 0),
            "orders": counts.get("orders", 0),
            "customers": len(live_customers),
            "projects": counts.get("projects", 0),
            "tasks": counts.get("tasks", 0),
            "payments": counts.get("payments", 0),
            "invoices": counts.get("invoices", 0),
        }

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
