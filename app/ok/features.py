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
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import Field

from app.ok.common import ApiError, StrictModel
from app.ok.security import require_bearer
from app.store import Store

# A 1x1 transparent PNG.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
CSV = "id,name\n1,Widget\n2,Gadget\n"
EVENTS = [{"seq": 1, "event": "created"}, {"seq": 2, "event": "updated"}, {"seq": 3, "event": "closed"}]
INT_LIST = re.compile(r"^-?\d+$")


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

    @router.post("/oauth2/token")
    async def oauth2_token(request: Request) -> JSONResponse:
        """Client-credentials grant with the documented fake client; returns the fixed test token."""
        form = parse_qs((await request.body()).decode("utf-8", "replace"))  # no multipart library: urlencoded only
        if form.get("grant_type") != ["client_credentials"]:
            raise ApiError(400, "invalid_request", "grant_type must be client_credentials")
        return JSONResponse({"access_token": "test-token", "token_type": "Bearer", "expires_in": 3600})

    return router
