"""Timing and instability: slow, flaky, throttled, unavailable and otherwise unstable behavior.

Rules (CLAUDE.md): every wait is `await` on a bounded, LATENCY_SCALE-scaled delay and never holds
the store lock; every state-dependent behavior is a counter in this family's store, restored by
`POST /conform-fail/__admin/reset`; nothing runs in the background (progress is computed when a
request arrives); nothing contacts another host (the redirect loop only ever redirects to itself).

Each behavior is correct except for the one thing it is named for, and the one thing is not
declared in the spec, so ClearSignal's reaction is the point of the case.
"""

import hashlib
import json
import random
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from app import transport
from app.latency import deliberate_delay
from app.store import Store

# ---- constants: every number a case depends on lives here and in specs/conform-fail.yaml ----
SLOW_MS = 15_000  # longer than ClearSignal's default 10 s timeout (times LATENCY_SCALE)
HANG_MS = 30_000  # "never answers": bounded at the 30 s ceiling, then gives up with a normal answer
SLOW_HEADERS_MS = 4_000
SLOW_BODY_BYTES, SLOW_BODY_INTERVAL_MS = 50, 200  # headers at once, then 50 bytes at 5 per second (10 s)
TRUNCATED_DECLARED, TRUNCATED_SENT = 1000, 100
AFTER_WRITE_MS = 15_000
FLAKY_EVERY = 3  # every 3rd call fails
RATE_LIMIT_CALLS = 3  # the 4th call and later get 429
UNAVAILABLE_CALLS = 2  # the first 2 calls after reset get 503
DEGRADE_BASE_MS, DEGRADE_STEP_MS, DEGRADE_CAP_MS = 100, 300, 5_000
LATENCY_MAX_MS = 30_000
JITTER_SEED = "clrsig-jitter-v1"
LARGE_MAX_MB = 60  # hard cap on /large, above ClearSignal's 50 MB read cap
MAX_RECORDS = 1_000  # bound on the records the write cases keep
CHUNK = 64 * 1024


class TruncatedResponse(Response):
    """Declares `Content-Length: 1000`, sends 100 bytes and ends: the connection is closed short."""

    async def __call__(self, scope, receive, send) -> None:
        headers = [(b"content-type", b"application/json"), (b"content-length", str(TRUNCATED_DECLARED).encode())]
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": b"x" * TRUNCATED_SENT, "more_body": False})


def error(status: int, code: str, message: str, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, "message": message}, headers=headers)


def jitter_delay(call: int, low: int, high: int) -> int:
    """The `call`-th delay of a fixed pseudo-random sequence: same call number, same delay."""
    return low + random.Random(f"{JITTER_SEED}:{call}").randint(0, high - low)


def degrading_delay(call: int) -> int:
    return min(DEGRADE_BASE_MS + DEGRADE_STEP_MS * (call - 1), DEGRADE_CAP_MS)


def build_router(store: Store) -> APIRouter:
    router = APIRouter()

    async def next_call(name: str) -> int:
        """Count a call to `name` atomically; the counters are part of the store, so reset clears them."""
        async with store.tx() as tx:
            counter = tx.get("counters", name) or {"id": name, "n": 0}
            counter["n"] += 1
            tx.put("counters", name, counter)
            return counter["n"]

    # ---- delays ----

    @router.get("/slow")
    async def slow(request: Request) -> JSONResponse:
        await deliberate_delay(request, SLOW_MS)
        return JSONResponse({"ok": True, "delayMs": SLOW_MS})

    @router.get("/latency/jitter")  # before /latency/{ms}, or "jitter" would be read as ms
    async def latency_jitter(
        request: Request,
        low: int = Query(100, alias="min", ge=0, le=LATENCY_MAX_MS),
        high: int = Query(1000, alias="max", ge=0, le=LATENCY_MAX_MS),
    ) -> JSONResponse:
        if low > high:
            return error(400, "invalid_request", "min must not exceed max")
        call = await next_call("jitter")
        delay = jitter_delay(call, low, high)
        await deliberate_delay(request, delay)
        return JSONResponse({"ok": True, "call": call, "delayMs": delay})

    @router.get("/latency/degrading")
    async def latency_degrading(request: Request) -> JSONResponse:
        call = await next_call("degrading")
        delay = degrading_delay(call)
        await deliberate_delay(request, delay)
        return JSONResponse({"ok": True, "call": call, "delayMs": delay})

    @router.get("/latency/{ms}")
    async def latency_fixed(request: Request, ms: int) -> JSONResponse:
        if not 0 <= ms <= LATENCY_MAX_MS:
            return error(400, "invalid_request", f"ms must be between 0 and {LATENCY_MAX_MS}")
        await deliberate_delay(request, ms)
        return JSONResponse({"ok": True, "delayMs": ms})

    # ---- counted failures ----

    @router.get("/flaky")
    async def flaky() -> JSONResponse:
        call = await next_call("flaky")
        if call % FLAKY_EVERY == 0:
            return error(500, "flaky", f"call {call} fails on purpose")
        return JSONResponse({"ok": True, "call": call})

    @router.get("/rate-limited")
    async def rate_limited() -> JSONResponse:
        call = await next_call("rate-limited")
        if call > RATE_LIMIT_CALLS:
            return error(429, "rate_limited", "too many calls", {"Retry-After": "60"})
        return JSONResponse({"ok": True, "call": call})

    @router.get("/unavailable")
    async def unavailable() -> JSONResponse:
        return error(503, "unavailable", "try again later", {"Retry-After": "1"})

    @router.get("/unavailable-then-ok")
    async def unavailable_then_ok() -> JSONResponse:
        call = await next_call("unavailable-then-ok")
        if call <= UNAVAILABLE_CALLS:
            return error(503, "unavailable", f"call {call} is refused on purpose", {"Retry-After": "1"})
        return JSONResponse({"ok": True, "call": call})

    # ---- redirect loop: only ever to itself ----

    @router.get("/redirect-loop")
    async def redirect_loop(request: Request) -> RedirectResponse:
        return RedirectResponse(url=request.url.path, status_code=302)

    # ---- large body ----

    @router.get("/large")
    async def large(mb: int = Query(ge=0, le=LARGE_MAX_MB)) -> Response:
        total = mb * 1024 * 1024
        block = b"x" * CHUNK

        async def body() -> AsyncIterator[bytes]:
            sent = 0
            while sent < total:
                size = min(CHUNK, total - sent)
                yield block[:size]
                sent += size

        return StreamingResponse(
            body(), media_type="application/octet-stream", headers={"Content-Length": str(total)}
        )

    @router.get("/large/json")
    async def large_json(mb: int = Query(ge=0, le=LARGE_MAX_MB)) -> Response:
        """A valid JSON object `{"data": "xxx..."}` whose string is `mb` megabytes long."""
        head, tail = b'{"data":"', b'"}'
        total = mb * 1024 * 1024
        block = b"x" * CHUNK

        async def body() -> AsyncIterator[bytes]:
            yield head
            sent = 0
            while sent < total:
                size = min(CHUNK, total - sent)
                yield block[:size]
                sent += size
            yield tail

        length = len(head) + total + len(tail)
        return StreamingResponse(body(), media_type="application/json", headers={"Content-Length": str(length)})

    # ---- transport-level cases (local only until verified on Cloud Run) ----

    @router.get("/timeout/hang")
    async def timeout_hang(request: Request) -> JSONResponse:
        """Accepts the request and does not answer for 30 s (times LATENCY_SCALE), then gives up."""
        await deliberate_delay(request, HANG_MS)
        return JSONResponse({"ok": True, "delayMs": HANG_MS})

    @router.get("/timeout/slow-headers")
    async def timeout_slow_headers(request: Request) -> JSONResponse:
        await deliberate_delay(request, SLOW_HEADERS_MS)  # nothing is sent before the wait ends
        return JSONResponse({"ok": True, "delayMs": SLOW_HEADERS_MS})

    @router.get("/timeout/slow-body")
    async def timeout_slow_body(request: Request) -> Response:
        """Headers at once (with the real Content-Length), then the body 5 bytes per second."""
        pad = "x" * (SLOW_BODY_BYTES - len(json.dumps({"ok": True, "pad": ""}, separators=(",", ":"))))
        payload = json.dumps({"ok": True, "pad": pad}, separators=(",", ":")).encode()

        async def trickle() -> AsyncIterator[bytes]:
            for i in range(len(payload)):
                if i:
                    await deliberate_delay(request, SLOW_BODY_INTERVAL_MS)
                yield payload[i : i + 1]

        return StreamingResponse(trickle(), media_type="application/json", headers={"Content-Length": str(len(payload))})

    @router.get("/timeout/truncated-body")
    async def timeout_truncated_body() -> Response:
        return TruncatedResponse()

    @router.get("/timeout/connection-reset")
    async def timeout_connection_reset(request: Request) -> Response:
        """Closes the connection with a TCP reset and no answer at all."""
        transport.abort_connection(request.scope.get("client"))
        return Response(status_code=204)  # only reached when there is no real server to abort

    # ---- a write that takes effect before the timeout ----

    @router.post("/timeout/after-write", status_code=201)
    async def after_write(request: Request) -> JSONResponse:
        async with store.tx() as tx:
            records = tx.list("writes")
            if len(records) >= MAX_RECORDS:
                return error(422, "limit", "record limit reached; reset the family")
            record_id = tx.next_id("writes", "w")
            tx.put("writes", record_id, {"id": record_id})
        await deliberate_delay(request, AFTER_WRITE_MS)  # the write is already done
        return JSONResponse(status_code=201, content={"id": 1})

    @router.get("/timeout/after-write/records")
    async def after_write_records() -> JSONResponse:
        items = await store.list("writes")
        return JSONResponse({"total": len(items), "items": items})

    # ---- idempotency that is not ----

    @router.post("/idempotent", status_code=201)
    async def idempotent(idempotency_key: str | None = Header(default=None, min_length=1, max_length=64)) -> JSONResponse:
        async with store.tx() as tx:
            if len(tx.list("idempotent")) >= MAX_RECORDS:
                return error(422, "limit", "record limit reached; reset the family")
            record_id = tx.next_id("idempotent", "i")
            tx.put("idempotent", record_id, {"id": record_id, "key": idempotency_key})  # the key is ignored
        return JSONResponse(status_code=201, content={"id": 1})

    @router.get("/idempotent/records")
    async def idempotent_records() -> JSONResponse:
        items = await store.list("idempotent")
        return JSONResponse({"total": len(items), "items": items})

    # ---- lost update: If-Match is ignored ----

    def etag(record: dict) -> str:
        return '"' + hashlib.sha256(f"{record['version']}".encode()).hexdigest()[:12] + '"'

    @router.get("/lost-update")
    async def lost_update_get() -> JSONResponse:
        record = await store.get("lost_update", "main")
        return JSONResponse({"value": record["value"], "version": record["version"]}, headers={"ETag": etag(record)})

    @router.put("/lost-update")
    async def lost_update_put(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            body = None
        value = body.get("value") if isinstance(body, dict) else None
        if not isinstance(value, str) or not value:
            return error(400, "invalid_request", "value must be a non-empty string")
        async with store.tx() as tx:  # If-Match is read by nobody: that is the bug
            record = tx.get("lost_update", "main")
            record = {"id": "main", "value": value, "version": record["version"] + 1}
            tx.put("lost_update", "main", record)
        return JSONResponse({"value": record["value"], "version": record["version"]}, headers={"ETag": etag(record)})

    return router
