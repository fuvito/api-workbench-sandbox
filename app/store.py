"""Generic in-memory store with a lock and deterministic seed/reset.

Records are plain dicts grouped by collection name. The lock is only held for
the dict operation itself; never await anything slow while holding it.
"""

import asyncio
import copy
from collections.abc import Callable
from typing import Any

Record = dict[str, Any]
SeedData = dict[str, dict[str, Record]]


class Store:
    def __init__(self, seed_factory: Callable[[], SeedData]) -> None:
        self._seed_factory = seed_factory
        self._lock = asyncio.Lock()
        self._load_seed()

    def _load_seed(self) -> None:
        self._data: SeedData = self._seed_factory()
        # Next sequential id number per collection; reset together with the data.
        self._counters: dict[str, int] = {c: len(items) for c, items in self._data.items()}

    async def reset(self) -> None:
        async with self._lock:
            self._load_seed()

    async def create_auto(self, collection: str, prefix: str, record: Record) -> Record:
        """Store a record under a new sequential id (`<prefix>-<n>`, never reused)."""
        async with self._lock:
            n = self._counters.get(collection, 0) + 1
            self._counters[collection] = n
            stored = {"id": f"{prefix}-{n}", **{k: v for k, v in record.items() if k != "id"}}
            self._data.setdefault(collection, {})[stored["id"]] = copy.deepcopy(stored)
            return stored

    async def snapshot(self) -> SeedData:
        async with self._lock:
            return copy.deepcopy(self._data)

    async def list(self, collection: str) -> list[Record]:
        async with self._lock:
            return [copy.deepcopy(r) for r in self._data.get(collection, {}).values()]

    async def get(self, collection: str, id_: str) -> Record | None:
        async with self._lock:
            record = self._data.get(collection, {}).get(id_)
            return copy.deepcopy(record) if record is not None else None

    async def create(self, collection: str, id_: str, record: Record) -> bool:
        """Return False if the id already exists."""
        async with self._lock:
            items = self._data.setdefault(collection, {})
            if id_ in items:
                return False
            items[id_] = copy.deepcopy(record)
            return True

    async def update(self, collection: str, id_: str, record: Record) -> bool:
        """Return False if the id does not exist."""
        async with self._lock:
            items = self._data.get(collection, {})
            if id_ not in items:
                return False
            items[id_] = copy.deepcopy(record)
            return True

    async def delete(self, collection: str, id_: str) -> bool:
        async with self._lock:
            return self._data.get(collection, {}).pop(id_, None) is not None
