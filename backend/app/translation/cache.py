import hashlib
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from backend.app.translation.config import LLM_MODEL, TRANSLATION_CACHE_DIR

logger = logging.getLogger("translation.cache")

CACHE_VERSION = 1


def ensure_translation_cache_dir() -> Path:
    """Ensure the on-disk translation cache directory exists."""
    cache_dir = Path(TRANSLATION_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def compute_translation_cache_key(
    transcript_content: str,
    transcript_segments: list | None,
    source_language: str,
    target_language: str,
) -> str:
    """Build a deterministic cache key for a translation request."""
    payload = {
        "cache_version": CACHE_VERSION,
        "content": transcript_content,
        "model": LLM_MODEL,
        "segments": transcript_segments or [],
        "source_language": source_language,
        "target_language": target_language,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_translation_cache_path(cache_key: str) -> Path:
    """Resolve the cache file path for a given cache key."""
    return ensure_translation_cache_dir() / f"{cache_key}.json"


def read_cached_translation(cache_key: str) -> dict[str, Any] | None:
    """Read a cached translation payload from disk if it exists."""
    cache_path = get_translation_cache_path(cache_key)
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r", encoding="utf-8") as handle:
            cached_payload = json.load(handle)

        if cached_payload.get("cache_version") != CACHE_VERSION:
            logger.warning(
                "Ignoring translation cache entry %s due to version mismatch",
                cache_path.name,
            )
            return None

        return cached_payload
    except Exception as error:
        logger.warning(
            "Failed to read translation cache entry %s: %s",
            cache_path,
            error,
        )
        return None


def write_cached_translation(
    cache_key: str,
    *,
    content: str,
    segments: list | None,
    source_language: str,
    target_language: str,
    strategy: str,
) -> Path:
    """Persist a translation payload to disk for future reuse."""
    cache_path = get_translation_cache_path(cache_key)
    payload = {
        "cache_version": CACHE_VERSION,
        "cached_at": time.time(),
        "content": content,
        "model": LLM_MODEL,
        "segments": segments,
        "source_language": source_language,
        "strategy": strategy,
        "target_language": target_language,
    }

    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=cache_path.parent,
        encoding="utf-8",
        suffix=".tmp",
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        temp_path = Path(handle.name)

    temp_path.replace(cache_path)
    return cache_path
