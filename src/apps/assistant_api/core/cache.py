from __future__ import annotations

import time
from typing import Callable, Generic, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


class InMemoryCache(Generic[T]):
    def __init__(
        self,
        *,
        maxsize: int = 1024,
        default_ttl_seconds: int = 300,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._default_ttl = default_ttl_seconds
        self._cache: TTLCache[str, T] = TTLCache(
            maxsize=maxsize,
            ttl=default_ttl_seconds,
            timer=clock or time.time,
        )

    def get(self, key: str) -> T | None:
        return self._cache.get(key)

    def set(self, key: str, value: T, *, ttl_seconds: int | None = None) -> None:
        if ttl_seconds is None or ttl_seconds == self._default_ttl:
            self._cache[key] = value
            return
        cache: TTLCache[str, T] = TTLCache(
            maxsize=self._cache.maxsize,
            ttl=ttl_seconds,
            timer=self._cache.timer,
        )
        cache.update(self._cache)
        cache[key] = value
        self._cache = cache

    def clear(self) -> None:
        self._cache.clear()
