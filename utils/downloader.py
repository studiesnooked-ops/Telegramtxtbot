"""
Async video downloader with progress reporting.
Downloads video files and forwards them to the Telegram chat.
Files >50 MB: sends a direct link instead of uploading.
"""

import asyncio
import logging
import os
import re
import time
import aiohttp
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse, unquote

from telegram import Bot
from telegram.constants import FileSizeLimit

from utils.queue_manager import QueueManager

logger = logging.getLogger("bot.downloader")

DOWNLOAD_DIR = Path("downloads")
CHUNK_SIZE = 512 * 1024   # 512 KB
SEND_SIZE_LIMIT = 50 * 1024 * 1024   # 50 MB – Telegram bot limit
CONNECT_TIMEOUT = 15
READ_TIMEOUT = 120
MAX_RETRIES = 3
RETRY_DELAY = 3   # seconds

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def _guess_filename(url: str, content_type: str = "") -> str:
    """Derive a sensible filename from a URL or content-type."""
    path = unquote(urlparse(url).path)
    name = path.split("/")[-1]

    # Strip query params that might be embedded
    name = re.sub(r"\?.*", "", name)

    if not name or "." not in name:
        ext = "mp4"
        if "webm" in content_type:
            ext = "webm"
        elif "ogg" in content_type or "ogv" in content_type:
            ext = "ogv"
        name = f"video_{int(time.time())}.{ext}"

    # Sanitize
    name = re.sub(r"[^\w.\-]", "_", name)
    return name


async def _download_one(
    session: aiohttp.ClientSession,
    url: str,
    dest_path: Path,
    progress_cb=None,
) -> bool:
    """Download a single URL to dest_path. Returns True on success."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(
                url,
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(connect=CONNECT_TIMEOUT, total=READ_TIMEOUT * 10),
                allow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0

                with open(dest_path, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total:
                            await progress_cb(downloaded, total)

            return True

        except aiohttp.ClientResponseError as exc:
            logger.warning("HTTP %s for %s (attempt %d)", exc.status, url, attempt)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Network error %s for %s (attempt %d)", exc, url, attempt)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(RETRY_DELAY * attempt)

    return False


async def download_and_send_videos(
    bot: Bot,
    chat_id: int,
    urls: List[str],
    queue_manager: Optional[QueueManager] = None,
) -> None:
    """Download each URL and send the result to chat_id."""
    DOWNLOAD_DIR.mkdir(exist_ok=True)

    connector = aiohttp.TCPConnector(limit=8, ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:

        # Process up to 3 videos concurrently per call
        sem = asyncio.Semaphore(3)

        async def process(idx: int, url: str):
            async with sem:
                await _process_single(bot, chat_id, session, idx, url, len(urls))

        tasks = [asyncio.create_task(process(i, u)) for i, u in enumerate(urls, start=1)]
        await asyncio.gather(*tasks, return_exceptions=True)

    await bot.send_message(
        chat_id,
        f"✅ All done! Processed *{len(urls)}* video(s).",
        parse_mode="Markdown",
    )


async def _process_single(
    bot: Bot,
    chat_id: int,
    session: aiohttp.ClientSession,
    idx: int,
    url: str,
    total: int,
) -> None:
    """Handle downloading and sending one video."""
    status = await bot.send_message(
        chat_id,
        f"⬇️ *{idx}/{total}* Downloading…\n`{url[:80]}`",
        parse_mode="Markdown",
    )

    filename = _guess_filename(url)
    dest = DOWNLOAD_DIR / filename

    # Progress callback (throttled to avoid Telegram flood limits)
    last_edit: list = [0.0]

    async def progress(done, total_bytes):
        now = time.time()
        if now - last_edit[0] < 3:
            return
        last_edit[0] = now
        pct = done / total_bytes * 100
        bar_len = 16
        filled = int(bar_len * done / total_bytes)
        bar = "█" * filled + "░" * (bar_len - filled)
        try:
            await status.edit_text(
                f"⬇️ *{idx}/{total}* `{bar}` {pct:.0f}%\n"
                f"`{_fmt_size(done)}` / `{_fmt_size(total_bytes)}`\n"
                f"`{filename}`",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    success = await _download_one(session, url, dest, progress_cb=progress)

    if not success:
        await status.edit_text(
            f"❌ *{idx}/{total}* Failed after {MAX_RETRIES} retries.\n`{url[:80]}`",
            parse_mode="Markdown",
        )
        return

    file_size = dest.stat().st_size

    if file_size <= SEND_SIZE_LIMIT:
        try:
            await status.edit_text(
                f"📤 *{idx}/{total}* Sending `{filename}` ({_fmt_size(file_size)})…",
                parse_mode="Markdown",
            )
            with open(dest, "rb") as fh:
                await bot.send_video(
                    chat_id,
                    video=fh,
                    filename=filename,
                    caption=f"🎬 `{filename}`\n📦 {_fmt_size(file_size)}",
                    parse_mode="Markdown",
                    supports_streaming=True,
                )
            await status.delete()
        except Exception as exc:
            logger.exception("Failed to send %s: %s", filename, exc)
            await status.edit_text(
                f"⚠️ *{idx}/{total}* Downloaded but failed to send: `{exc}`",
                parse_mode="Markdown",
            )
    else:
        # File too big to send via bot API – give them the direct link
        await status.edit_text(
            f"📦 *{idx}/{total}* `{filename}` is {_fmt_size(file_size)} "
            f"(over Telegram's 50 MB limit).\n\n"
            f"🔗 Direct link:\n`{url}`",
            parse_mode="Markdown",
        )

    # Cleanup downloaded file
    try:
        dest.unlink(missing_ok=True)
    except Exception:
        pass


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
