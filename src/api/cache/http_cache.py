from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import diskcache


class HttpCache:
    def __init__(self, directory: str | Path, ttl_seconds: int | None = None) -> None:
        Path(directory).mkdir(parents=True, exist_ok=True)
        self._cache = diskcache.Cache(str(directory))
        self._ttl = ttl_seconds

    @staticmethod
    def build_key(endpoint: str, params: dict[str, Any] | None = None) -> str:
        payload = json.dumps(params or {}, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{endpoint}|{payload}".encode()).hexdigest()
        return digest

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any | None:
        return self._cache.get(self.build_key(endpoint, params))

    def set(self, endpoint: str, params: dict[str, Any] | None, value: Any) -> None:
        self._cache.set(self.build_key(endpoint, params), value, expire=self._ttl)

    def close(self) -> None:
        self._cache.close()
