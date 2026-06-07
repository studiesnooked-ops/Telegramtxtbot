"""
Parses raw text and extracts video/MP4 URLs.
Handles a wide variety of URL patterns.
"""

import re
from urllib.parse import urlparse
from typing import List

# ── Patterns ──────────────────────────────────────────────────────────────────
_URL_RE = re.compile(
    r"https?://"                      # scheme
    r"[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"  # rest of URL
,
    re.IGNORECASE,
)

# Keywords that indicate a video URL even without .mp4 extension
_VIDEO_KEYWORDS = re.compile(
    r"\.(mp4|m4v|mov|avi|mkv|webm|flv|wmv|mpeg|mpg|ts|m3u8)(\?|$|#)",
    re.IGNORECASE,
)
_VIDEO_PATH_HINTS = re.compile(
    r"/(video|videos|media|stream|clip|play|content|vod|hls|dash)/",
    re.IGNORECASE,
)
_CDN_DOMAINS = re.compile(
    r"\.(cloudfront\.net|akamaihd\.net|fastly\.net|cdnvideo|fbcdn|twimg|"
    r"googlevideo|ytimg|vimeocdn|wistia|bunnycdn|b-cdn\.net)",
    re.IGNORECASE,
)


def is_video_url(url: str) -> bool:
    """Return True if url looks like a video resource."""
    lower = url.lower()
    parsed = urlparse(url)
    path = parsed.path.lower()

    if _VIDEO_KEYWORDS.search(path + "?" + (parsed.query or "")):
        return True
    if _VIDEO_PATH_HINTS.search(path):
        return True
    if _CDN_DOMAINS.search(parsed.netloc):
        return True
    return False


def parse_video_urls(text: str) -> List[str]:
    """
    Extract unique video URLs from arbitrary text.
    Lines starting with '#' are treated as comments.
    """
    seen: set = set()
    results: List[str] = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        for match in _URL_RE.findall(line):
            url = match.rstrip(".,;)'\"")   # strip common trailing punctuation
            if url in seen:
                continue
            if is_video_url(url):
                seen.add(url)
                results.append(url)

    return results


def format_url_list(urls: List[str]) -> str:
    """Format a list of URLs as a numbered Markdown list."""
    lines = []
    for i, url in enumerate(urls, start=1):
        try:
            parsed = urlparse(url)
            name = parsed.path.split("/")[-1] or url
        except Exception:
            name = url
        lines.append(f"`{i:>3}.` [{name}]({url})")
    return "\n".join(lines)
