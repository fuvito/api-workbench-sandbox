"""Cases for the `contract-fail` family: one function per case, each breaking exactly one thing.

A case is a plain GET under /contract-fail/cases/<slug>. The spec (specs/contract-fail.yaml)
declares the correct behavior; the handler here deviates in the single documented way. Every
other part of the response stays correct so ClearSignal reports only the intended check.

The expected check for each case is recorded in expectations/contract-fail.yaml.
"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Request, Response

from app.latency import deliberate_delay

# slug -> handler; filled by @case. The spec must describe exactly these (see tests).
CASES: dict[str, Callable[..., Awaitable[Response]]] = {}
# Routes the server has but the spec deliberately does not describe.
UNDOCUMENTED: dict[str, Callable[..., Awaitable[Response]]] = {}


def case(slug: str):
    def register(fn):
        CASES[slug] = fn
        return fn

    return register


def undocumented(slug: str):
    """A route the server has and the spec deliberately does not describe."""

    def register(fn):
        UNDOCUMENTED[slug] = fn
        return fn

    return register


# ---- building blocks: a correct response, then one deliberate change ----

WIDGET: dict[str, Any] = {"id": 1, "name": "Alpha", "price": 9.99}


def json_response(
    body: Any,
    status: int = 200,
    headers: dict[str, str] | None = None,
    media_type: str | None = "application/json",
) -> Response:
    """Serialize `body` ourselves so the bytes on the wire are exactly what the case intends."""
    return Response(
        content=json.dumps(body).encode(),
        status_code=status,
        headers=headers,
        media_type=media_type,
    )


def counted(body: Any, total: str | None = "1", **kwargs: Any) -> Response:
    """A correct response that carries the declared X-Total-Count header (or not, if None)."""
    headers = {"X-Total-Count": total} if total is not None else {}
    return json_response(body, headers=headers, **kwargs)


# ---- controls: must pass ----


@case("control-ok")
async def control_ok() -> Response:
    return json_response(WIDGET)


@case("resp-001b-default-response-ok")
async def resp_001b() -> Response:
    # 503 is not listed, but the spec has a `default` response, which counts as declared.
    return json_response({"code": "unavailable", "message": "try later"}, status=503)


# ---- CS-RESP-001 .. CS-RESP-006 ----


@case("resp-001-undeclared-status")
async def resp_001() -> Response:
    return json_response({"code": "boom", "message": "internal error"}, status=500)


@case("resp-002-wrong-content-type")
async def resp_002() -> Response:
    return json_response(WIDGET, media_type="text/plain")  # valid JSON, wrong type


@case("resp-003-missing-required-header")
async def resp_003() -> Response:
    return counted(WIDGET, total=None)  # X-Total-Count omitted


@case("resp-004-wrong-header-type")
async def resp_004() -> Response:
    return counted(WIDGET, total="many")  # integer expected


@case("resp-005-missing-required-field")
async def resp_005() -> Response:
    return json_response({"name": "Alpha", "price": 9.99})  # id omitted


@case("resp-006-wrong-field-type")
async def resp_006() -> Response:
    return json_response({"id": 1, "name": "Alpha", "price": "9.99"})  # number expected


@case("resp-006b-array-for-object")
async def resp_006b() -> Response:
    return json_response([WIDGET])  # object expected


@case("resp-nested-wrong-type")
async def resp_nested() -> Response:
    return json_response(
        {
            "id": 7,
            "customer": {"name": "Ada", "address": {"city": "London"}},
            "lines": [{"sku": "A-1", "qty": "two"}, {"sku": "B-2", "qty": 1}],  # lines[0].qty
        }
    )


# ---- CS-RESP-007: values outside the declared constraints ----


@case("resp-007-enum")
async def resp_007() -> Response:
    return json_response({"status": "archived"})  # enum: active, inactive


@case("resp-007b-minimum")
async def resp_007b() -> Response:
    return json_response({"quantity": -1})  # minimum 0


@case("resp-007f-maximum")
async def resp_007f() -> Response:
    return json_response({"percent": 101})  # maximum 100


@case("resp-007c-pattern")
async def resp_007c_pattern() -> Response:
    return json_response({"code": "abc-1"})  # ^[A-Z]{3}-[0-9]{3}$


@case("resp-007c-minlength")
async def resp_007c_minlength() -> Response:
    return json_response({"name": "ab"})  # minLength 3


@case("resp-007c-maxlength")
async def resp_007c_maxlength() -> Response:
    return json_response({"name": "toolong"})  # maxLength 5


@case("resp-007c-minitems")
async def resp_007c_minitems() -> Response:
    return json_response({"tags": []})  # minItems 1


@case("resp-007c-uniqueitems")
async def resp_007c_uniqueitems() -> Response:
    return json_response({"tags": ["a", "a"]})  # uniqueItems


@case("resp-007d-null-not-nullable")
async def resp_007d() -> Response:
    return json_response({"id": 1, "name": None})  # name is not nullable


@case("resp-007e-bad-datetime")
async def resp_007e() -> Response:
    return json_response({"createdAt": "yesterday"})  # format: date-time


# ---- CS-RESP-008: not JSON / empty ----


@case("resp-008-invalid-json")
async def resp_008() -> Response:
    return Response(content=b"{not json", media_type="application/json")


@case("resp-008b-empty-body")
async def resp_008b() -> Response:
    return Response(content=b"", status_code=200, media_type="application/json")


# ---- CS-RESP-009: oneOf / discriminator ----


@case("resp-009-oneof-no-match")
async def resp_009() -> Response:
    return json_response({"c": 1})  # needs {a} or {b}


@case("resp-poly-discriminator-wrong")
async def resp_poly() -> Response:
    return json_response({"type": "cat", "barks": True})  # a cat must meow; this is a dog's shape


# ---- CS-RESP-010: extra property ----


@case("resp-010-extra-property-closed")
async def resp_010() -> Response:
    return json_response({"id": 1, "extra": True})  # additionalProperties: false


@case("resp-010b-extra-property-open")
async def resp_010b() -> Response:
    return json_response({**WIDGET, "extra": True})  # open schema: allowed, must pass


# ---- CS-RESP-011: writeOnly leak ----


@case("resp-011-writeonly-leak")
async def resp_011() -> Response:
    return json_response({"id": 1, "name": "Ada", "password": "hunter2"})


# ---- XML (no decoder in ClearSignal: not checked, CS-NC-009) ----


@case("resp-012-xml-valid")
async def resp_012() -> Response:
    xml = b"<widget><id>1</id><name>Alpha</name><price>9.99</price></widget>"
    return Response(content=xml, media_type="application/xml")


# ---- formats ClearSignal checks since 0.9.0 (email, uuid, ipv4, ipv6) ----


@case("resp-007g-format-email-uuid")
async def resp_007g() -> Response:
    return json_response({"mail": "nope", "ref": "not-a-uuid"})


# ---- two problems at once: ClearSignal reports the header first (CS-GAP-011) ----


@case("resp-multi-problem")
async def resp_multi() -> Response:
    return counted({"name": "Alpha", "price": 9.99}, total=None)  # no header AND no id


# ---- known gaps: wrong, but ClearSignal does not catch it today ----


@case("gap-format-uri")
async def gap_format_uri() -> Response:
    return json_response({"link": "not a uri"})


@case("gap-undeclared-header")
async def gap_header() -> Response:
    return json_response(WIDGET, headers={"X-Debug": "1"})


@case("gap-slow-response")
async def gap_slow(request: Request) -> Response:
    await deliberate_delay(request, 5000)  # bounded, scaled by LATENCY_SCALE, never blocks
    return json_response(WIDGET)


# ---- not checked: nothing to compare, must not fail ----


@case("nc-002-no-content-declared")
async def nc_002() -> Response:
    return json_response(WIDGET)  # the spec declares 200 with no content at all


@case("nc-octet-stream")
async def nc_octet() -> Response:
    return Response(content=bytes([0, 1, 2, 3]), media_type="application/octet-stream")


@case("nc-no-content-type")
async def nc_no_content_type() -> Response:
    return json_response(WIDGET, media_type=None)  # a JSON body with no Content-Type header


@undocumented("nc-undocumented-path")
async def nc_undocumented() -> Response:
    return json_response(WIDGET)  # exists on the server, not in the spec (scenario step only)


def build_router() -> APIRouter:
    """GET /cases/<slug> for every registered case."""
    router = APIRouter(prefix="/cases")
    for slug, handler in {**CASES, **UNDOCUMENTED}.items():
        router.add_api_route(f"/{slug}", handler, methods=["GET"], include_in_schema=False)
    return router
