"""Notifications: cursor pagination, a date-time filter, and a mark-as-read action.

The cursor is opaque to clients (base64url of the last id number seen). Because it is based on
the id and not on a position, adding or marking records between pages never repeats or skips
an item, unlike offset paging.
"""

import base64
import json
from typing import Literal

from fastapi import APIRouter, Query, Request, Response

from app.latency import MAX_DELAY_MS, deliberate_delay
from app.ok.common import ApiError, BoolText, as_bool, not_found, parse_date_time
from app.store import Store

COLLECTION = "notifications"
Kind = Literal["info", "warning"]


def encode_cursor(last_number: int) -> str:
    raw = json.dumps({"after": last_number}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> int:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        after = json.loads(base64.urlsafe_b64decode(padded.encode()))["after"]
        if isinstance(after, bool) or not isinstance(after, int) or after < 0:
            raise ValueError
        return after
    except (ValueError, KeyError, TypeError) as exc:  # includes bad base64 and bad JSON
        raise ApiError(400, "invalid_cursor", "the cursor is not valid") from exc


def number_of(notification: dict) -> int:
    return int(notification["id"].split("-")[1])


def build(store: Store) -> APIRouter:
    router = APIRouter()

    @router.get("/notifications")
    async def list_notifications(
        request: Request,
        cursor: str | None = Query(None, min_length=1, max_length=200),
        limit: int = Query(5, ge=1, le=50),
        unread: BoolText | None = None,
        since: str | None = Query(None, max_length=40),
        kind: Kind | None = None,
        delay: int = Query(0, ge=0, le=MAX_DELAY_MS),
    ) -> dict:
        await deliberate_delay(request, delay)
        after = decode_cursor(cursor) if cursor is not None else 0
        since_dt = parse_date_time(since, "since") if since is not None else None

        items = sorted(await store.list(COLLECTION), key=number_of)
        if as_bool(unread) is not None:
            items = [n for n in items if n["read"] != as_bool(unread)]
        if kind is not None:
            items = [n for n in items if n["kind"] == kind]
        if since_dt is not None:
            items = [n for n in items if parse_date_time(n["createdAt"], "createdAt") >= since_dt]
        items = [n for n in items if number_of(n) > after]

        page = items[:limit]
        more = len(items) > limit
        return {"items": page, "nextCursor": encode_cursor(number_of(page[-1])) if more else None}

    @router.get("/notifications/{notification_id}")
    async def get_notification(notification_id: str) -> dict:
        notification = await store.get(COLLECTION, notification_id)
        if notification is None:
            raise not_found("notification", notification_id)
        return notification

    @router.post("/notifications/{notification_id}/read")
    async def mark_read(notification_id: str, response: Response) -> dict:
        """Idempotent: marking an already-read notification is still 200."""
        async with store.tx() as tx:
            notification = tx.get(COLLECTION, notification_id)
            if notification is None:
                raise not_found("notification", notification_id)
            notification["read"] = True
            tx.put(COLLECTION, notification_id, notification)
            return notification

    return router
