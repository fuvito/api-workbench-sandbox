"""Operations where the spec and the server disagree about what exists.

Each case is wrong in one way, the way real APIs drift from their specs:

- /ghost                  declared in the spec, no route on the server (404)
- /orphan                 the spec declares DELETE; the server only implements POST (405)
- /wrong-method           the spec declares PATCH; the server only implements PUT (405)
- /path-param/{id}        the spec says id is an integer; the server only accepts UUIDs (400)
- /requires-extra-header  the server needs an X-Tenant header the spec never mentions (400)
- /undocumented           the server has it, the spec does not (not exercised by conform)
- /form and /multipart    declared form bodies; ClearSignal generates no body for them (CS-GAP-006)
- /subscribe              declares a callback that ClearSignal does not exercise (CS-GAP-010)

The 404 and 405 answers come from the framework on purpose: they are what a real server without
that route or method says. Nothing here calls a URL it was given.
"""

import re
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

# Routes the server has that the spec deliberately does not describe, for tests and the runner:
# (method, path). /ghost is the opposite: described, not implemented.
UNDOCUMENTED_OPERATIONS = (
    ("PUT", "/wrong-method"),
    ("POST", "/orphan"),
    ("GET", "/undocumented"),
)


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message})


def build_router() -> APIRouter:
    router = APIRouter()

    # /ghost: intentionally NOT implemented. The framework's own 404 is the behavior.

    @router.post("/orphan")  # the spec describes DELETE /orphan; this method is not in the spec
    async def orphan_post() -> JSONResponse:
        return JSONResponse({"ok": True})

    @router.put("/wrong-method")  # the spec describes PATCH /wrong-method
    async def wrong_method_put() -> JSONResponse:
        return JSONResponse({"ok": True})

    @router.get("/path-param/{id}")
    async def path_param(id: str) -> JSONResponse:
        if not UUID.match(id):
            return error(400, "invalid_id", "id must be a UUID")
        return JSONResponse({"id": 1})

    @router.post("/requires-extra-header")
    async def requires_extra_header(x_tenant: str | None = Header(default=None)) -> JSONResponse:
        if not x_tenant:
            return error(400, "missing_header", "the X-Tenant header is required")
        return JSONResponse(status_code=201, content={"id": 1})

    @router.get("/undocumented")
    async def undocumented() -> JSONResponse:
        return JSONResponse({"id": 1})

    @router.post("/form")
    async def form(request: Request) -> JSONResponse:
        """Accepts a urlencoded form with a name; anything else (including no body) is 400."""
        if not request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
            return error(400, "invalid_request", "a form-encoded body is required")
        fields = parse_qs((await request.body()).decode(errors="replace"))
        if not fields.get("name", [""])[0]:
            return error(400, "invalid_request", "name is required")
        return JSONResponse(status_code=201, content={"id": 1})

    @router.post("/multipart")
    async def multipart(request: Request) -> JSONResponse:
        """Accepts a multipart body that has a `name` part; it does not parse the parts further."""
        body = await request.body()
        if not request.headers.get("content-type", "").startswith("multipart/form-data") or b'name="name"' not in body:
            return error(400, "invalid_request", "a multipart body with a name part is required")
        return JSONResponse(status_code=201, content={"id": 1})

    @router.post("/subscribe")
    async def subscribe(request: Request) -> JSONResponse:
        """Validates strictly. The callback URL is only checked for shape and never contacted."""
        try:
            body = await request.json()
        except ValueError:
            body = None
        url = body.get("callbackUrl") if isinstance(body, dict) else None
        if not isinstance(url, str) or not re.match(r"^https?://\S+$", url):
            return error(400, "invalid_request", "callbackUrl must be an http(s) URL")
        return JSONResponse(status_code=201, content={"id": 1})

    return router
