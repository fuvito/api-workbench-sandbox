"""OpenAPI feature examples (specs/ok-features.yaml): one small operation per feature.

Parameter styles (deepObject, pipeDelimited, spaceDelimited, label, matrix), allowEmptyValue and
allowReserved, number constraints and formats, `not`, a deprecated operation, a response link,
TRACE, CSV / PNG / NDJSON bodies, a `requestBodies` component, and oauth2 / openIdConnect security.
Every handler is strict, like the rest of `ok`: bad input is a declared 400.
"""

import base64
import binascii
import json
import re
import secrets
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs

from fastapi import APIRouter, Cookie, Depends, Path, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import Field

from app.ok.common import ApiError, StrictModel
from app.ok.security import Forbidden, Unauthorized, require_bearer
from app.store import Store

# A 1x1 transparent PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
CSV = "id,name\n1,Widget\n2,Gadget\n"
EVENTS = [{"seq": 1, "event": "created"}, {"seq": 2, "event": "updated"}, {"seq": 3, "event": "closed"}]
INT_LIST = re.compile(r"^-?\d+$")


# Credentials a bearer-protected operation can meet (documented fake test values, like the others):
# an unknown token, a token that has expired, a token without the needed scope, and one with it.
CRED_TOKENS = {"test-token": ["read"], "writer-token": ["read", "write"]}
EXPIRED_TOKEN = "expired-token"
SESSION_USER, SESSION_PASSWORD = "test-user", "test-pass"
SESSION_COOKIE = "session"
ITEMS = 10  # items behind the Link-header pagination
PER_PAGE_DEFAULT, PER_PAGE_MAX = 3, 5


def credential_scopes(request: Request) -> list[str]:
    """Scopes of the presented token. Missing or unknown is 401; an expired token is 401 with the reason."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and secrets.compare_digest(token.encode(), EXPIRED_TOKEN.encode()):
        raise Unauthorized('Bearer realm="ok", error="invalid_token", error_description="the access token expired"')
    scopes = None
    for known, known_scopes in CRED_TOKENS.items():
        if secrets.compare_digest(token.encode(), known.encode()):  # no early exit on a match
            scopes = known_scopes
    if scheme.lower() != "bearer" or scopes is None:
        raise Unauthorized('Bearer realm="ok"')
    return scopes


def require_write(request: Request) -> None:
    if "write" not in credential_scopes(request):
        raise Forbidden()


def int_list(parts: list[str], what: str) -> list[int]:
    if not (1 <= len(parts) <= 20) or any(not INT_LIST.match(p) for p in parts):
        raise ApiError(400, "invalid_request", f"{what} must be 1 to 20 integers")
    return [int(p) for p in parts]


class NumbersBody(StrictModel):
    count: int = Field(gt=0, le=1_000_000, multiple_of=5)
    ratio: float = Field(gt=0, lt=1, allow_inf_nan=False)
    secret: str = Field(min_length=8, max_length=100)
    blob: str = Field(max_length=1000)


class NameBody(StrictModel):
    name: str = Field(min_length=1, max_length=20)


class NoteBody(StrictModel):
    text: str = Field(min_length=1, max_length=200)


class ItemBody(StrictModel):
    title: str = Field(min_length=1, max_length=40)


def build(store: Store) -> APIRouter:
    router = APIRouter(prefix="/features")

    @router.get("/deep-object")
    async def deep_object(request: Request) -> dict:
        """`filter[status]=open&filter[min]=2` (style deepObject, explode true)."""
        result: dict = {}
        for key, value in request.query_params.multi_items():
            if not key.startswith("filter["):
                continue
            field = key[len("filter[") :].removesuffix("]")
            if field == "status" and value in ("open", "closed") and "status" not in result:
                result["status"] = value
            elif field == "min" and INT_LIST.match(value) and "min" not in result:
                result["min"] = int(value)
            else:
                raise ApiError(400, "invalid_request", f"filter[{field}] is not a valid filter")
        return result

    @router.get("/pipe-delimited")
    async def pipe_delimited(ids: str) -> dict:
        """`ids=1|2|3` (style pipeDelimited, explode false)."""
        return {"ids": int_list(ids.split("|"), "ids")}

    @router.get("/space-delimited")
    async def space_delimited(ids: str) -> dict:
        """`ids=1%202%203` (style spaceDelimited, explode false)."""
        return {"ids": int_list(ids.split(" "), "ids")}

    @router.get("/label/{ids}")
    async def label(ids: str = Path(max_length=200)) -> dict:
        """`/label/.1,2,3` (path style label, explode false: a dot, then comma-separated values)."""
        if not ids.startswith("."):
            raise ApiError(400, "invalid_request", "ids must use the label style: .1,2,3")
        return {"ids": int_list(ids[1:].split(","), "ids")}

    @router.get("/matrix/{ids}")
    async def matrix(ids: str = Path(max_length=200)) -> dict:
        """`/matrix/;matrixIds=1,2,3` (path style matrix, explode false: `;<parameter name>=values`)."""
        prefix = ";matrixIds="
        if not ids.startswith(prefix):
            raise ApiError(400, "invalid_request", "ids must use the matrix style: ;matrixIds=1,2,3")
        return {"ids": int_list(ids[len(prefix) :].split(","), "ids")}

    @router.get("/flags")
    async def flags(request: Request) -> dict:
        """`flag` allows an empty value (`?flag=`); `path` allows reserved characters (`a/b:c`)."""
        flag, path = request.query_params.get("flag"), request.query_params.get("path")
        if flag is not None and len(flag) > 40 or path is not None and len(path) > 100:
            raise ApiError(400, "invalid_request", "flag or path is too long")
        return {"flag": flag, "path": path}

    @router.post("/numbers")
    async def numbers(body: NumbersBody) -> dict:
        """int64 + multipleOf + exclusive bounds, double, a password and a base64 (byte) string."""
        try:
            raw = base64.b64decode(body.blob, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ApiError(400, "invalid_request", "blob must be base64") from exc
        return {"count": body.count, "ratio": body.ratio, "secretLength": len(body.secret), "blobBytes": len(raw)}

    @router.post("/names")
    async def names(body: NameBody) -> dict:
        """`name` is any string except the reserved words (schema `not: {enum: [admin, root]}`)."""
        if body.name in ("admin", "root"):
            raise ApiError(400, "invalid_request", "name is reserved")
        return {"name": body.name}

    @router.get("/greeting", deprecated=True)
    async def greeting() -> dict:
        return {"message": "hello"}

    @router.post("/items", status_code=201)
    async def create_item(body: ItemBody, response: Response) -> dict:
        item = await store.create_auto("feature_items", "item", {"title": body.title})
        response.headers["Location"] = f"/ok/features/items/{item['id']}"
        return item

    @router.get("/items/{itemId}")
    async def get_item(item_id: str = Path(alias="itemId", max_length=40)) -> dict:
        item = await store.get("feature_items", item_id)
        if item is None:
            raise ApiError(404, "not_found", "item not found")
        return item

    @router.api_route("/trace", methods=["TRACE"], response_class=PlainTextResponse)
    async def trace() -> str:
        return "trace ok"

    @router.get("/report.csv", response_class=PlainTextResponse)
    async def report_csv() -> Response:
        return Response(content=CSV, media_type="text/csv")

    @router.get("/logo.png")
    async def logo_png() -> Response:
        return Response(content=PNG, media_type="image/png")

    @router.get("/events.ndjson")
    async def events_ndjson() -> Response:
        body = "".join(json.dumps(e) + "\n" for e in EVENTS)
        return Response(content=body, media_type="application/x-ndjson")

    @router.post("/notes")
    async def notes(body: NoteBody) -> dict:
        """The request body is a `components.requestBodies` reference in the spec."""
        return {"text": body.text, "length": len(body.text)}

    @router.post("/xml-note")
    async def xml_note(request: Request) -> dict:
        """An XML request body: `<note><text>hello</text></note>`. No DOCTYPE or entities (no expansion attacks)."""
        raw = await request.body()
        if not raw.strip():
            raise ApiError(400, "invalid_request", "an XML body is required")
        if len(raw) > 10_000 or b"<!" in raw:
            raise ApiError(400, "invalid_request", "the XML body is too large or has a DOCTYPE or entity")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ApiError(400, "invalid_request", "the body is not well-formed XML") from exc
        text = root.findtext("text") if root.tag == "note" else None
        if not text or len(text) > 200:
            raise ApiError(400, "invalid_request", "expected <note><text>...</text></note>")
        return {"text": text, "length": len(text)}

    @router.get("/oauth2-profile", dependencies=[Depends(require_bearer)])
    async def oauth2_profile() -> dict:
        """oauth2 (clientCredentials): the access token from the token endpoint is the fixed test token."""
        return {"user": "test-user", "via": "oauth2"}

    @router.get("/openid-profile", dependencies=[Depends(require_bearer)])
    async def openid_profile() -> dict:
        return {"user": "test-user", "via": "openIdConnect"}

    @router.get("/.well-known/openid-configuration", include_in_schema=False)
    async def openid_configuration(request: Request) -> dict:
        """The discovery document the `openIdConnect` scheme points to (not an operation of the spec)."""
        base = f"{str(request.base_url).rstrip('/')}/ok/features"
        return {"issuer": base, "token_endpoint": f"{base}/oauth2/token", "grant_types_supported": ["client_credentials"]}

    # ---- credentials: expired, under-privileged, and good ----

    @router.get("/credentials/profile")
    async def credentials_profile(request: Request) -> dict:
        """Any valid token: 200. Missing or unknown token: 401. The expired token: 401 with the reason."""
        return {"user": "test-user", "scopes": credential_scopes(request)}

    @router.get("/credentials/write-area", dependencies=[Depends(require_write)])
    async def credentials_write_area() -> dict:
        """Needs the write scope: `test-token` (read only) is 403, `writer-token` is 200, `expired-token` is 401."""
        return {"area": "write", "ok": True}

    # ---- a session in a cookie ----

    class LoginBody(StrictModel):
        user: str = Field(min_length=1, max_length=40)
        password: str = Field(min_length=1, max_length=100)

    @router.post("/session/login", status_code=204)
    async def session_login(body: LoginBody) -> Response:
        """Right credentials: 204 and `Set-Cookie: session=...`. Wrong: 401."""
        ok = secrets.compare_digest(body.user.encode(), SESSION_USER.encode()) & secrets.compare_digest(
            body.password.encode(), SESSION_PASSWORD.encode()
        )
        if not ok:
            raise Unauthorized('Cookie realm="ok"')
        session = await store.create_auto("feature_sessions", "sess", {"user": body.user})
        response = Response(status_code=204)
        response.set_cookie(SESSION_COOKIE, session["id"], path="/ok/features", httponly=True, samesite="lax")
        return response

    @router.get("/session/me")
    async def session_me(session: str | None = Cookie(default=None, max_length=100)) -> dict:
        """The cookie is the credential: missing, unknown or logged-out is 401."""
        record = await store.get("feature_sessions", session) if session else None
        if record is None:
            raise Unauthorized('Cookie realm="ok"')
        return {"user": record["user"], "session": session}

    @router.post("/session/logout", status_code=204)
    async def session_logout(session: str | None = Cookie(default=None, max_length=100)) -> Response:
        """Ends the session (if any) and clears the cookie. Always 204."""
        if session:
            await store.delete("feature_sessions", session)
        response = Response(status_code=204)
        response.delete_cookie(SESSION_COOKIE, path="/ok/features")
        return response

    # ---- pagination with Link headers ----

    @router.get("/links/items")
    async def link_items(
        request: Request,
        response: Response,
        page: int = Query(1, ge=1, le=1000),
        per_page: int = Query(PER_PAGE_DEFAULT, ge=1, le=PER_PAGE_MAX),
    ) -> list:
        """10 numbered items. The `Link` header (RFC 8288) carries first, prev, next and last."""
        last = max(1, -(-ITEMS // per_page))
        if page > last:
            raise ApiError(400, "invalid_request", f"page must be at most {last}")
        start = (page - 1) * per_page
        base = str(request.url.replace(query=""))

        def link(target: int, rel: str) -> str:
            return f'<{base}?page={target}&per_page={per_page}>; rel="{rel}"'

        links = [link(1, "first"), link(last, "last")]
        if page > 1:
            links.append(link(page - 1, "prev"))
        if page < last:
            links.append(link(page + 1, "next"))
        response.headers["Link"] = ", ".join(links)
        response.headers["X-Total-Count"] = str(ITEMS)
        return [{"n": n, "name": f"item {n}"} for n in range(start + 1, min(start + per_page, ITEMS) + 1)]

    @router.post("/oauth2/token")
    async def oauth2_token(request: Request) -> JSONResponse:
        """Client-credentials grant with the documented fake client; returns the fixed test token."""
        form = parse_qs((await request.body()).decode("utf-8", "replace"))  # no multipart library: urlencoded only
        if form.get("grant_type") != ["client_credentials"]:
            raise ApiError(400, "invalid_request", "grant_type must be client_credentials")
        return JSONResponse({"access_token": "test-token", "token_type": "Bearer", "expires_in": 3600})

    return router
