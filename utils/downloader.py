"""
Async video downloader with FFmpeg speed optimization.
Downloads videos, processes them (FFmpeg), and sends to Telegram.
Render-optimized version.
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

from utils.queue_manager import QueueManager
from utils.ffmpeg import get_ffmpeg_cmd, run_ffmpeg

logger = logging.getLogger("bot.downloader")

DOWNLOAD_DIR = Path("downloads")

CHUNK_SIZE = 512 * 1024
SEND_SIZE_LIMIT = 50 * 1024 * 1024

CONNECT_TIMEOUT = 15
READ_TIMEOUT = 120

MAX_RETRIES = 3
RETRY_DELAY = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


# ───────────────────────── FILE NAME ─────────────────────────

def _guess_filename(url: str, content_type: str = "") -> str:
    path = unquote(urlparse(url).path)
    name = path.split("/")[-1]
    name = re.sub(r"\?.*", "", name)

    if not name or "." not in name:
        name = f"video_{int(time.time())}.mp4"

    return re.sub(r"[^\w.\-]", "_", name)


# ───────────────────────── DOWNLOAD ─────────────────────────

async def _download_one(session, url, dest_path, progress_cb=None):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with session.get(url, headers=HEADERS) as resp:
                resp.raise_for_status()

                total = int(resp.headers.get("Content-Length", 0))
                done = 0

                with open(dest_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(CHUNK_SIZE):
                        f.write(chunk)
                        done += len(chunk)

                        if progress_cb and total:
                            await progress_cb(done, total)

            return True

        except Exception as e:
            logger.warning("Download error %s (attempt %d)", e, attempt)

        await asyncio.sleep(RETRY_DELAY * attempt)

    return False


# ───────────────────────── MAIN PIPELINE ─────────────────────────

async def download_and_send_videos(
    bot: Bot,
    chat_id: int,
    urls: List[str],
    queue_manager: Optional[QueueManager] = None,
) -> None:

    DOWNLOAD_DIR.mkdir(exist_ok=True)

    connector = aiohttp.TCPConnector(limit=6, ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:

        sem = asyncio.Semaphore(2)  # Render-safe limit

        async def worker(i, url):
            async with sem:
                await _process(bot, chat_id, session, i, url, len(urls))

        tasks = [
            asyncio.create_task(worker(i, u))
            for i, u in enumerate(urls, 1)
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    await bot.send_message(chat_id, "✅ All videos processed successfully.")


# ───────────────────────── PROCESS SINGLE ─────────────────────────

async def _process(bot, chat_id, session, idx, url, total):

    msg = await bot.send_message(
        chat_id,
        f"⬇️ {idx}/{total} Downloading..."
    )

    filename = _guess_filename(url)
    raw_file = DOWNLOAD_DIR / f"raw_{filename}"
    final_file = DOWNLOAD_DIR / f"final_{filename}"

    last_update = [0]

    async def progress(done, total_bytes):
        now = time.time()
        if now - last_update[0] < 2:
            return
        last_update[0] = now

        pct = (done / total_bytes) * 100 if total_bytes else 0
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))

        try:
            await msg.edit_text(
                f"⬇️ {idx}/{total}\n{bar} {pct:.0f}%"
            )
        except:
            pass

    success = await _download_one(session, url, raw_file, progress)

    if not success:
        await msg.edit_text(f"❌ Failed {idx}/{total}")
        return

    # ── FFmpeg SPEED OPTIMIZATION STEP ──
    try:
        cmd = get_ffmpeg_cmd(
            str(raw_file),
            str(final_file),
            fast_mode=True
        )

        await run_ffmpeg(cmd)

    except Exception as e:
        await msg.edit_text(f"⚠️ FFmpeg error: {e}")
        return

    size = final_file.stat().st_size

    # ── SEND VIDEO ──
    if size <= SEND_SIZE_LIMIT:
        try:
            with open(final_file, "rb") as f:
                await bot.send_video(
                    chat_id,
                    video=f,
                    caption=f"🎬 {filename}"
                )
            await msg.delete()
        except Exception as e:
            await msg.edit_text(f"⚠️ Send error: {e}")
    else:
        await msg.edit_text("📦 File too large for Telegram")

    # cleanup
    try:
        raw_file.unlink(missing_ok=True)
        final_file.unlink(missing_ok=True)
    except:
        pass
