"""Time sources, in one place so tests can replace them.

Expiry and timestamps use `utcnow()`; rate-limit windows use `monotonic()`. Nothing here runs
in the background: all time-dependent behavior is computed when a request arrives.
"""

import asyncio
import time
from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def monotonic() -> float:
    return time.monotonic()


async def sleep(seconds: float) -> None:
    """The one place deliberate delays wait; always non-blocking."""
    await asyncio.sleep(seconds)
