"""The shared dependency for list operations: paging plus the optional `delay` parameter."""

from fastapi import Query, Request

from app.latency import MAX_DELAY_MS, deliberate_delay
from app.ok.common import Page


async def get_page(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    delay: int = Query(0, ge=0, le=MAX_DELAY_MS),
) -> Page:
    """limit/offset as declared in the spec. `?delay=<ms>` slows the list on purpose
    (capped, scaled by LATENCY_SCALE); absent means no delay."""
    await deliberate_delay(request, delay)
    return Page(limit, offset)
