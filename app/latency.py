"""Deliberate, bounded, non-blocking delays.

Rules (CLAUDE.md): sleep with `await asyncio.sleep`, never hold a store lock while sleeping,
apply LATENCY_SCALE to every deliberate delay, and bound everything:

- a requested delay is at most MAX_DELAY_MS (callers validate and answer 400 above it),
- the scaled sleep is at most MAX_SLEEP_SECONDS,
- at most MAX_CONCURRENT_SLOW requests may be sleeping at once; more get 503.
"""

import asyncio

from fastapi import Request

from app import clock

MAX_DELAY_MS = 10_000
MAX_SLEEP_SECONDS = 30.0
MAX_CONCURRENT_SLOW = 20


class TooManySlowRequests(Exception):
    """Raised when MAX_CONCURRENT_SLOW requests are already sleeping."""


def new_slow_slots() -> asyncio.Semaphore:
    return asyncio.Semaphore(MAX_CONCURRENT_SLOW)


def scaled_seconds(ms: int, scale: float) -> float:
    return min(ms / 1000 * scale, MAX_SLEEP_SECONDS)


async def deliberate_delay(request: Request, ms: int) -> None:
    """Wait `ms` milliseconds (times LATENCY_SCALE) without blocking the event loop."""
    if ms <= 0:
        return
    seconds = scaled_seconds(ms, request.app.state.settings.latency_scale)
    slots: asyncio.Semaphore = request.app.state.slow_slots
    if slots.locked():  # no await between this check and the acquire below
        raise TooManySlowRequests()
    async with slots:
        await clock.sleep(seconds)
