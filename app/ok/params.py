"""Parameter-type examples: headers, a required cookie, arrays, date, date-time, number, enum."""

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Cookie, Header, Query, Response

from app.ok.common import ApiError, parse_date_time
from app.store import Store

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Mode = Literal["strict", "lenient"]


def parse_int_list(csv: str) -> list[int]:
    """`ids=1,2,3` (form style, explode=false). Strict: no blanks, no non-integers."""
    parts = csv.split(",")
    if not (1 <= len(parts) <= 20) or any(not p.lstrip("-").isdigit() or p != p.strip() for p in parts):
        raise ApiError(400, "invalid_request", "ids must be 1 to 20 comma-separated integers")
    return [int(p) for p in parts]


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/request-info")
    async def request_info(
        response: Response,
        x_request_id: str | None = Header(default=None, pattern=UUID_PATTERN),
        accept_language: str | None = Header(default=None, min_length=1, max_length=100),
    ) -> dict:
        """Echoes the client's X-Request-Id, or makes one up; always sets the response header."""
        request_id = x_request_id or str(uuid.uuid4())
        response.headers["X-Request-Id"] = request_id
        language = (accept_language or "en").split(",")[0].split(";")[0].strip()
        return {"requestId": request_id, "language": language}

    @router.get("/preferences")
    async def preferences(theme: Literal["light", "dark"] = Cookie()) -> dict:
        """The `theme` cookie is required: missing or not light/dark is 400."""
        return {"theme": theme}

    @router.get("/lookup")
    async def lookup(
        ids: str = Query(max_length=200),
        since: str | None = Query(None, max_length=40),
        on: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        ratio: float | None = Query(None, ge=0, le=1, allow_inf_nan=False),
        mode: Mode | None = None,
        tags: list[str] | None = Query(None, max_length=10),
    ) -> dict:
        """Echoes what it parsed, so clients can check each parameter type end to end."""
        result: dict = {"ids": parse_int_list(ids)}
        if since is not None:
            result["since"] = parse_date_time(since, "since").isoformat().replace("+00:00", "Z")
        if on is not None:
            try:
                result["on"] = date.fromisoformat(on).isoformat()
            except ValueError as exc:
                raise ApiError(400, "invalid_request", "on is not a real date") from exc
        if ratio is not None:
            result["ratio"] = ratio
        if mode is not None:
            result["mode"] = mode
        if tags is not None:
            if len(set(tags)) != len(tags) or any(not t for t in tags):
                raise ApiError(400, "invalid_request", "tags must be unique and non-empty")
            result["tags"] = tags
        return result

    return router
