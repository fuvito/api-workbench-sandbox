"""Small public operations: a string-to-string settings map and a text/plain version."""

from fastapi import APIRouter, Body, Path, Request
from fastapi.responses import PlainTextResponse
from pydantic import TypeAdapter

from app.latency import MAX_DELAY_MS, deliberate_delay
from app.ok.common import ApiError
from app.store import Store

VERSION = "1.0.0"
# Strict map of short strings; the same limits as `Settings` in the spec.
_SETTINGS = TypeAdapter(dict[str, str])
MAX_SETTINGS = 20
MAX_VALUE_LEN = 200


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/settings")
    async def get_settings() -> dict:
        return (await store.get("settings", "main"))["values"]

    @router.put("/settings")
    async def replace_settings(body: dict = Body(...)) -> dict:
        try:
            values = _SETTINGS.validate_python(body, strict=True)
        except ValueError as exc:
            raise ApiError(400, "invalid_request", "settings must map strings to strings") from exc
        if len(values) > MAX_SETTINGS or any(len(v) > MAX_VALUE_LEN for v in values.values()):
            raise ApiError(400, "invalid_request", "too many settings or a value is too long")
        await store.update("settings", "main", {"id": "main", "values": values})
        return values

    @router.get("/ok-slow/{ms}")
    async def ok_slow(request: Request, ms: int = Path(ge=0, le=MAX_DELAY_MS)) -> dict:
        """Correct but slow: waits `ms` (cap 10000, times LATENCY_SCALE), then answers 200."""
        await deliberate_delay(request, ms)
        return {"requestedMs": ms}

    @router.get("/version", response_class=PlainTextResponse)
    async def get_version() -> str:
        return VERSION

    return router
