"""A tiny in-process cache for rarely-changing rows (settings, active sales and offers).

Each web worker keeps its own copy, so a change made in the admin is picked up everywhere within `ttl`
seconds, and immediately by the worker that saved it (it calls `clear`).
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

T = TypeVar("T")
_MISSING: Any = object()


class TtlCache(Generic[T]):
    def __init__(self, ttl: float):
        self.ttl = ttl
        self._value: Any = _MISSING
        self._at = 0.0

    def get(self) -> T | None:
        if self._value is not _MISSING and time.monotonic() - self._at < self.ttl:
            return self._value
        return None

    def set(self, value: T) -> T:
        self._value, self._at = value, time.monotonic()
        return value

    def clear(self) -> None:
        self._value = _MISSING

    async def get_or_load(self, loader: Callable[[], Awaitable[T]]) -> T:
        cached = self.get()
        if cached is not None:
            return cached
        return self.set(await loader())
