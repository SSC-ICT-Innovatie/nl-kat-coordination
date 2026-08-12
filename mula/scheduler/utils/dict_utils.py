import threading
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from typing import Any


def deep_get(d: Any | None, keys: list[str]) -> Any:
    if not keys or d is None:
        return d
    return deep_get(d.get(keys[0]), keys[1:])


class ExpiredError(Exception):
    pass


class ExpiringDict:
    """ExpiringDict enables us to create a Dict that expires after a certain
    time. It will clear the cache when the expiration time is reached and
    return an ExpiredError.
    """

    def __init__(self, lifetime: int = 300, start_time: datetime = datetime.now(timezone.utc)) -> None:
        self.lifetime: timedelta = timedelta(seconds=lifetime)
        self.start_time = start_time
        self.expiration_time: datetime = start_time + self.lifetime
        self.lock: threading.Lock = threading.Lock()
        self.cache: dict[str, Any] = {}
        self._expiration_enabled: bool = True

    def get(self, key: str, default: Any | None = None) -> Any:
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def is_empty(self) -> bool:
        with self.lock:
            return len(self.cache) == 0

    def reset(self) -> None:
        with self.lock:
            self.cache.clear()
            self.expiration_time = datetime.now(timezone.utc) + self.lifetime

    @property
    def expiration_enabled(self) -> bool:
        """Whether expiration is enabled or not."""
        return self._expiration_enabled

    @expiration_enabled.setter
    def expiration_enabled(self, value: bool) -> None:
        """Enable or disable expiration. If disabled, the cache will never
        expire.

        Args:
            value (bool): Whether to enable or disable expiration.
        """
        with self.lock:
            self._expiration_enabled = value

            # If we are enabling expiration, we need to reset the expiration
            if value is True:
                self.expiration_time = datetime.now(timezone.utc) + self.lifetime

    def _is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expiration_time

    def __getitem__(self, key: str) -> Any:
        with self.lock:
            if self._is_expired() and self.expiration_enabled:
                # Using this instead of reset(), else we would lock
                self.cache.clear()
                self.expiration_time = datetime.now(timezone.utc) + self.lifetime

                raise ExpiredError

            if key not in self.cache:
                raise KeyError(key)

            return self.cache[key]

    def __setitem__(self, key: str, value: Any) -> None:
        with self.lock:
            self.cache[key] = value

    def __delitem__(self, key: str) -> None:
        with self.lock:
            del self.cache[key]

    def __contains__(self, key: str) -> bool:
        with self.lock:
            return key in self.cache

    def __len__(self) -> int:
        with self.lock:
            return len(self.cache)

    def __iter__(self) -> Iterator[str]:
        with self.lock:
            return iter(self.cache)

    def setdefault(self, key: str, default: Any) -> Any:
        with self.lock:
            return self.cache.setdefault(key, default)
