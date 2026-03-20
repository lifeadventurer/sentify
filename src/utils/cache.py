import hashlib
import json
import os
import shutil
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from config.config import SENTIFY_CACHE_DIR


def _cache_file_path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return SENTIFY_CACHE_DIR / namespace / f"{digest}.json"


def _read_cache_payload(cache_file: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(cache_file.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def get_cached_json(
    namespace: str,
    key: str,
    ttl_seconds: int,
    allow_stale: bool = False,
) -> Any | None:
    cache_file = _cache_file_path(namespace, key)
    payload = _read_cache_payload(cache_file)
    if payload is None:
        return None

    cached_at = payload.get("cached_at")
    if not isinstance(cached_at, int | float):
        return None

    if not allow_stale and time.time() - cached_at > ttl_seconds:
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


def cleanup_expired_json(ttl_by_namespace: dict[str, int]) -> None:
    now = time.time()

    for namespace, ttl_seconds in ttl_by_namespace.items():
        namespace_dir = SENTIFY_CACHE_DIR / namespace
        try:
            cache_files = namespace_dir.iterdir()
        except OSError:
            continue

        for cache_file in cache_files:
            if not cache_file.is_file():
                continue

            payload = _read_cache_payload(cache_file)
            if payload is None:
                try:
                    cache_file.unlink()
                except OSError:
                    pass
                continue

            cached_at = payload.get("cached_at")
            if not isinstance(cached_at, int | float):
                try:
                    cache_file.unlink()
                except OSError:
                    pass
                continue

            if now - cached_at <= ttl_seconds:
                continue

            try:
                cache_file.unlink()
            except OSError:
                pass


def clear_cache_namespaces(namespaces: Iterable[str]) -> bool:
    try:
        SENTIFY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    for namespace in dict.fromkeys(namespaces):
        cache_entry = SENTIFY_CACHE_DIR / namespace
        try:
            if cache_entry.is_dir() and not cache_entry.is_symlink():
                shutil.rmtree(cache_entry)
            elif cache_entry.exists():
                cache_entry.unlink()
        except OSError:
            return False

    return True
