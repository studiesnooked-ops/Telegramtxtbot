"""
Core MP4 URL extractor.
Supports multiple input formats:
  - Direct .mp4 URLs
  - URLs containing video parameters
  - Playlist files (M3U/M3U8 references)
  - Encoded / obfuscated URLs
  - Mixed-content text files
"""

import asyncio
import hashlib
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────

# Primary: direct .mp4 in URL path or query string
_RE_MP4_DIRECT = re.compile(
    r'https?://[^\s\'"<>\[\]{}|\\^`\x00-\x1f]+'
    r'(?:\.mp4|\.MP4)(?:[?#][^\s\'"<>\[\]{}|\\^`\x00-\x1f]*)?',
    re.IGNORECASE,
)

# Secondary: generic video URL (mp4 in query param, CDN patterns)
_RE_VIDEO_GENERIC = re.compile(
    r'https?://[^\s\'"<>\[\]{}|\\^`\x00-\x1f]+'
    r'(?:\?[^\s]*(?:mp4|video|vid|media|stream)[^\s]*)',
    re.IGNORECASE,
)

# Encoded: URL-encoded mp4 links
_RE_ENCODED = re.compile(
    r'https?%3A%2F%2F[^\s\'"<>\[\]{}|\\^`\x00-\x1f]+',
    re.IGNORECASE,
)

# CDN-style patterns without extension
_CDN_PATTERNS = re.compile(
    r'https?://(?:'
    r'[a-z0-9\-]+\.(?:cdn|cloudfront|akamai|fastly|bunny)'
    r'|storage\.googleapis\.com'
    r'|s3(?:\.[a-z0-9\-]+)?\.amazonaws\.com'
    r'|blob\.core\.windows\.net'
    r'|r2\.cloudflarestorage\.com'
    r')[^\s\'"<>\[\]{}|\\^`\x00-\x1f]*',
    re.IGNORECASE,
)

# All URL pattern (fallback — grabs every URL, filtered later)
_RE_ANY_URL = re.compile(
    r'https?://[^\s\'"<>\[\]{}|\\^`\x00-\x1f]+',
    re.IGNORECASE,
)

# Video-related file extensions
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ts", ".flv"}

# Video-related keywords for CDN links
_VIDEO_KEYWORDS = {
    "video", "vid", "media", "stream", "mp4", "movie",
    "clip", "play", "watch", "content", "file",
}


@dataclass
class ExtractionResult:
    urls: list[str]
    total_lines: int
    total_urls_found: int
    duplicates_removed: int
    source_name: str
    checksum: str


def _is_video_url(url: str) -> bool:
    """Heuristic: does this URL likely point to a video?"""
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()
        query = parsed.query.lower()

        # Check path extension
        ext = Path(path).suffix.lower()
        if ext in _VIDEO_EXTS:
            return True

        # Check query string for video hints
        if any(kw in query for kw in _VIDEO_KEYWORDS):
            return True

        # Check CDN domains with no extension
        if _CDN_PATTERNS.match(url):
            return True

        return False
    except Exception:
        return False


def _extract_from_text(text: str) -> list[str]:
    """Pure CPU work — runs in a subprocess via ProcessPoolExecutor."""
    found: set[str] = set()

    # 1. Direct .mp4 URLs
    for m in _RE_MP4_DIRECT.finditer(text):
        found.add(m.group(0).rstrip(".,;\"'"))

    # 2. Percent-encoded URLs → decode then check
    for m in _RE_ENCODED.finditer(text):
        decoded = unquote(m.group(0))
        if _is_video_url(decoded):
            found.add(decoded.rstrip(".,;\"'"))

    # 3. Generic video query-string URLs
    for m in _RE_VIDEO_GENERIC.finditer(text):
        found.add(m.group(0).rstrip(".,;\"'"))

    # 4. Any URL that passes the video heuristic
    for m in _RE_ANY_URL.finditer(text):
        url = m.group(0).rstrip(".,;\"'")
        if _is_video_url(url):
            found.add(url)

    return sorted(found)


async def extract_mp4_urls(
    text: str,
    source_name: str = "input",
    max_urls: int = 500,
    executor: Optional[ProcessPoolExecutor] = None,
) -> ExtractionResult:
    """
    Async wrapper around the CPU-intensive extractor.
    Runs extraction in a ProcessPoolExecutor to avoid blocking the event loop.
    """
    lines = text.splitlines()
    total_lines = len(lines)

    loop = asyncio.get_event_loop()

    try:
        if executor:
            raw_urls = await loop.run_in_executor(executor, _extract_from_text, text)
        else:
            raw_urls = _extract_from_text(text)
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        raw_urls = []

    total_found = len(raw_urls)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for url in raw_urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)

    duplicates = total_found - len(unique)

    # Cap at max_urls
    unique = unique[:max_urls]

    # Stable checksum for this result set
    checksum = hashlib.md5("\n".join(unique).encode()).hexdigest()[:8]

    logger.info(
        f"[{source_name}] lines={total_lines} found={total_found} "
        f"unique={len(unique)} dupes={duplicates}"
    )

    return ExtractionResult(
        urls=unique,
        total_lines=total_lines,
        total_urls_found=total_found,
        duplicates_removed=duplicates,
        source_name=source_name,
        checksum=checksum,
    )


async def extract_from_file(
    file_path: str | Path,
    max_urls: int = 500,
    executor: Optional[ProcessPoolExecutor] = None,
) -> ExtractionResult:
    """Read a file and extract MP4 URLs from it."""
    path = Path(file_path)

    # Try common encodings
    text = None
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text = path.read_text(encoding=enc)
            break
        except (UnicodeDecodeError, Exception):
            continue

    if text is None:
        raise ValueError(f"Could not decode file: {path.name}")

    return await extract_mp4_urls(
        text,
        source_name=path.name,
        max_urls=max_urls,
        executor=executor,
    )
