"""
Sends extracted URLs back to the user.
Strategies:
  - ≤ 10 URLs  → individual messages
  - 11-50 URLs → chunked messages (10 per message)
  - > 50 URLs  → .txt file attachment + summary message
"""

import asyncio
import logging
import uuid
from pathlib import Path

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 10          # URLs per message in medium mode
_LARGE_THRESHOLD = 50     # switch to file mode above this


async def send_urls_to_user(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    urls: list[str],
    reply_to: Message | None = None,
):
    """Dispatch to the right sending strategy based on URL count."""
    config = context.bot_data["config"]
    chat_id = update.effective_chat.id
    count = len(urls)

    try:
        if count <= 10:
            await _send_individual(context, chat_id, urls, config)
        elif count <= _LARGE_THRESHOLD:
            await _send_chunked(context, chat_id, urls, config)
        else:
            await _send_as_file(context, chat_id, urls, config, reply_to)
    except Exception as e:
        logger.error(f"Sender error: {e}")
        await context.bot.send_message(
            chat_id,
            f"❌ An error occurred while sending URLs: {e}",
        )


# ── Strategy 1: individual messages ──────────────────────────────────────────

async def _send_individual(context, chat_id, urls, config):
    for i, url in enumerate(urls, 1):
        label = f"`[{i}/{len(urls)}]`\n"
        await _safe_send(context, chat_id, label + url)
        if config.BATCH_SEND_DELAY > 0:
            await asyncio.sleep(config.BATCH_SEND_DELAY)

    await context.bot.send_message(
        chat_id,
        f"✅ Done! Sent {len(urls)} video link(s).",
    )


# ── Strategy 2: chunked messages ─────────────────────────────────────────────

async def _send_chunked(context, chat_id, urls, config):
    total = len(urls)
    for i in range(0, total, _CHUNK_SIZE):
        chunk = urls[i : i + _CHUNK_SIZE]
        start = i + 1
        end = min(i + _CHUNK_SIZE, total)
        header = f"🎬 Links {start}–{end} of {total}:\n\n"
        body = "\n".join(chunk)
        await _safe_send(context, chat_id, header + body)
        if config.BATCH_SEND_DELAY > 0:
            await asyncio.sleep(config.BATCH_SEND_DELAY)

    await context.bot.send_message(
        chat_id,
        f"✅ All {total} video links sent!",
    )


# ── Strategy 3: .txt file ────────────────────────────────────────────────────

async def _send_as_file(context, chat_id, urls, config, reply_to):
    total = len(urls)
    download_dir = Path(config.DOWNLOAD_DIR)
    out_path = download_dir / f"videos_{uuid.uuid4().hex[:8]}.txt"

    # Write the file
    content_lines = [
        f"# Video URLs extracted by @VideoExtractorBot",
        f"# Total: {total} links",
        "",
        *urls,
        "",
    ]
    out_path.write_text("\n".join(content_lines), encoding="utf-8")

    caption = (
        f"🎬 **{total} Video Links Extracted**\n\n"
        f"All MP4 URLs have been compiled into this file.\n"
        f"Open it in any text editor to access your links."
    )

    try:
        with open(out_path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=out_path.name,
                caption=caption,
                parse_mode=ParseMode.MARKDOWN,
            )

        # Also send first 5 as a preview
        preview = "\n".join(f"• {u}" for u in urls[:5])
        await context.bot.send_message(
            chat_id,
            f"**Preview (first 5 of {total}):**\n\n{preview}\n\n"
            f"… and {total - 5} more in the file above.",
            parse_mode=ParseMode.MARKDOWN,
        )
    finally:
        try:
            out_path.unlink()
        except Exception:
            pass


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _safe_send(context, chat_id, text, retries=3):
    """Send a message with retry on rate-limit errors."""
    for attempt in range(retries):
        try:
            await context.bot.send_message(
                chat_id,
                text,
                disable_web_page_preview=True,
            )
            return
        except RetryAfter as e:
            wait = e.retry_after + 1
            logger.warning(f"Rate limited. Waiting {wait}s…")
            await asyncio.sleep(wait)
        except TelegramError as e:
            if attempt == retries - 1:
                logger.error(f"Failed to send after {retries} attempts: {e}")
                raise
            await asyncio.sleep(2 ** attempt)
