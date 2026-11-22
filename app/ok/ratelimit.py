"""Rate limit: K calls per fixed window per client, then 429 with Retry-After.

Only GET /ok/rate-limited is limited; the rest of the API never throttles. The client is the
`X-Client-Id` header when sent, else the caller's address. State lives in the store, so
`__admin/reset` clears every counter. The number of tracked clients is bounded.
"""

import math

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import JSONResponse

from app import clock
from app.ok.common import ApiError
from app.store import Store

COLLECTION = "rate_limits"
LIMIT = 5  # calls per window
WINDOW_SECONDS = 60.0
MAX_CLIENTS = 1000


class RateLimited(ApiError):
    def __init__(self, retry_after: int) -> None:
        super().__init__(429, "rate_limited", f"limit of {LIMIT} calls per window reached")
        self.retry_after = retry_after


async def rate_limited_handler(_: Request, exc: RateLimited) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"code": exc.code, "message": exc.message},
        headers={
            "Retry-After": str(exc.retry_after),
            "X-RateLimit-Limit": str(LIMIT),
            "X-RateLimit-Remaining": "0",
        },
    )


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/rate-limited")
    async def rate_limited(
        request: Request,
        response: Response,
        x_client_id: str | None = Header(default=None, min_length=1, max_length=64),
    ) -> dict:
        client = x_client_id or (request.client.host if request.client else "unknown")
        now = clock.monotonic()
        async with store.tx() as tx:
            window = tx.get(COLLECTION, client)
            if window is None or now - window["start"] >= WINDOW_SECONDS:
                if len(tx.list(COLLECTION)) >= MAX_CLIENTS:  # drop expired windows first
                    for old in tx.list(COLLECTION):
                        if now - old["start"] >= WINDOW_SECONDS:
                            tx.delete(COLLECTION, old["id"])
                window = {"id": client, "start": now, "count": 0}
            if window["count"] >= LIMIT:
                retry = max(1, math.ceil(WINDOW_SECONDS - (now - window["start"])))
                raise RateLimited(retry)
            window["count"] += 1
            tx.put(COLLECTION, client, window)
        remaining = LIMIT - window["count"]
        response.headers["X-RateLimit-Limit"] = str(LIMIT)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return {"status": "ok", "remaining": remaining}

    return router
