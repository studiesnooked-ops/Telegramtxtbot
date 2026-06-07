"""File system helpers."""

import logging
import os
from pathlib import Path

logger = logging.getLogger("bot.file_utils")


def save_upload(data: bytes, filename: str, directory: str = "uploads") -> Path:
    Path(directory).mkdir(parents=True, exist_ok=True)
    dest = Path(directory) / filename
    dest.write_bytes(data)
    return dest


def cleanup_file(path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Could not delete %s: %s", path, exc)


def cleanup_old_files(directory: str, max_age_seconds: int = 3600) -> int:
    """Remove files older than max_age_seconds. Returns count deleted."""
    import time
    count = 0
    cutoff = time.time() - max_age_seconds
    for p in Path(directory).iterdir():
        if p.is_file() and p.stat().st_mtime < cutoff:
            cleanup_file(p)
            count += 1
    return count
