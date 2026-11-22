"""The adversarial group, `GET /conform-fail/hostile/<case>`: odd and malformed response bodies.

Each endpoint answers 200 with `Content-Type: application/json` and a body built byte by byte, so a
case is exactly the one thing it is named for. The spec declares one shape for all of them (an
object with an integer `id`), so a body that is not that shape, or not JSON at all, is the point.

Two groups: bodies that are valid JSON and valid for the schema but unusual (deep, wide, unicode,
big numbers, gzip, duplicate headers, a very large header, chunked), which ClearSignal must accept;
and bodies that are malformed (invalid UTF-8, a raw newline in a string, NaN, trailing garbage, gzip
that is not gzip) or that no standard defines (a duplicate key, a BOM, a number beyond float64, a
lone surrogate). Nothing here is random and nothing reads the request.
"""

import gzip
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse

JSON = "application/json"
DEPTH = 200  # nesting levels of `deep-nesting`
WIDTH = 20_000  # keys of `wide-object`
BIG_HEADER = 60_000  # bytes of the `X-Big` header


def deep() -> bytes:
    return b'{"id":1,"nest":' + b"[" * DEPTH + b"1" + b"]" * DEPTH + b"}"


def wide() -> bytes:
    keys = ",".join(f'"k{i}":{i}' for i in range(WIDTH))
    return f'{{"id":1,{keys}}}'.encode()


# case name -> the exact response body
BODIES: dict[str, bytes] = {
    # valid and valid for the schema
    "deep-nesting": deep(),
    "wide-object": wide(),
    "unicode": '{"id":1,"text":"café שלום \U0001f600 \\ud83d\\ude00 \\u0000"}'.encode(),
    "integer-as-float": b'{"id":1.0}',
    "integer-exponent": b'{"id":1e2}',
    "big-integer": b'{"id":9223372036854775808}',
    "negative-zero": b'{"id":-0}',
    # malformed or undefined
    "bom": b'\xef\xbb\xbf{"id":1}',
    "invalid-utf8": b'{"id":1,"text":"bad \xff\xfe byte"}',
    "raw-newline-in-string": b'{"id":1,"text":"line one\nline two"}',
    "nan-literal": b'{"id":NaN}',
    "trailing-garbage": b'{"id":1} garbage',
    "duplicate-keys": b'{"id":1,"id":"two"}',
    "float-overflow": b'{"id":1,"ratio":1e400}',
    "lone-surrogate": b'{"id":1,"text":"\\ud800"}',
}


def build_router() -> APIRouter:
    router = APIRouter(prefix="/hostile")

    def body_route(name: str, payload: bytes) -> None:
        async def handler() -> Response:
            return Response(content=payload, media_type=JSON)

        router.add_api_route(f"/{name}", handler, methods=["GET"], name=f"hostile_{name}")

    for name, payload in BODIES.items():
        body_route(name, payload)

    @router.get("/gzip")
    async def gzipped() -> Response:
        """A valid gzip body with `Content-Encoding: gzip`."""
        return Response(content=gzip.compress(b'{"id":1}'), media_type=JSON, headers={"Content-Encoding": "gzip"})

    @router.get("/gzip-lie")
    async def gzip_lie() -> Response:
        """Says gzip but sends plain JSON."""
        return Response(content=b'{"id":1}', media_type=JSON, headers={"Content-Encoding": "gzip"})

    @router.get("/duplicate-headers")
    async def duplicate_headers() -> Response:
        """The same header twice and two cookies."""
        response = Response(content=b'{"id":1}', media_type=JSON)
        for name, value in ((b"x-dup", b"one"), (b"x-dup", b"two"), (b"set-cookie", b"a=1; Path=/"), (b"set-cookie", b"b=2; Path=/")):
            response.raw_headers.append((name, value))
        return response

    @router.get("/big-header")
    async def big_header() -> Response:
        return Response(content=b'{"id":1}', media_type=JSON, headers={"X-Big": "a" * BIG_HEADER})

    @router.get("/chunked-stream")
    async def chunked_stream() -> StreamingResponse:
        """No Content-Length: the body arrives in three chunks."""

        async def parts() -> AsyncIterator[bytes]:
            for part in (b'{"id":', b"1,", b'"text":"chunked"}'):
                yield part

        return StreamingResponse(parts(), media_type=JSON)

    return router
