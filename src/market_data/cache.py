import hashlib
import json
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Callable


class DataCache:
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)

    def _make_key(self, *args: Any, **kwargs: Any) -> str:
        raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Any | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            cached_at = datetime.fromisoformat(data["cached_at"])
            if datetime.now() - cached_at > self.ttl:
                return None
            return data["value"]
        except (json.JSONDecodeError, KeyError, ValueError):
            return None

    def set(self, key: str, value: Any) -> None:
        path = self._cache_path(key)
        path.write_text(
            json.dumps(
                {"cached_at": datetime.now().isoformat(), "value": value},
                ensure_ascii=False,
                default=str,
            )
        )

    def memoize(self, func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = f"{func.__name__}_{self._make_key(*args, **kwargs)}"
            cached = self.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            if result is not None:
                self.set(key, result)
            return result

        return wrapper
