import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from config.config import SENTIFY_CACHE_DIR


def _cache_file_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return SENTIFY_CACHE_DIR / namespace / f"{digest}.json"


def get_cached_json(namespace: str, key: str, ttl_seconds: int) -> Any | None:
    cache_file = _cache_file_path(namespace, key)

    try:
        payload = json.loads(cache_file.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    cached_at = payload.get("cached_at")
    if not isinstance(cached_at, int | float):
        return None

    if time.time() - cached_at > ttl_seconds:
        return None

    return payload.get("value")


def set_cached_json(namespace: str, key: str, value: Any) -> None:
    cache_file = _cache_file_path(namespace, key)
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        temp_file = cache_file.with_suffix(
            f".{os.getpid()}.{time.time_ns()}.tmp"
        )
        payload = {"cached_at": time.time(), "value": value}

        temp_file.write_text(json.dumps(payload))
        temp_file.replace(cache_file)
    except OSError:
        return
