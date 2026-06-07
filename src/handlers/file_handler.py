"""
Handles incoming .txt document uploads.
Parses MP4/video URLs and presents a download menu to the user.
"""

import logging
import os
import asyncio
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from utils.url_parser import parse_video_urls
from utils.queue_manager import QueueManager, DownloadJob
from utils.file_utils import save_upload, cleanup_file

logger = logging.getLogger("bot.file_handler")

MAX_FILE_SIZE = 20 * 1024 * 1024   # 20 MB
MAX_URLS = 500


async def handle_txt_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Entry point – called when user sends a .txt file."""
    doc = update.message.document
    user = update.effective_user
    chat_id = update.effective_chat.id

    # ── Size guard ────────────────────────────────────────────────────────
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ File too large ({doc.file_size / 1e6:.1f} MB). "
            f"Maximum allowed size is {MAX_FILE_SIZE // (1024*1024)} MB."
        )
        return

    status_msg = await update.message.reply_text("⏳ Reading your file…")

    try:
        # ── Download the .txt from Telegram ──────────────────────────────
        tg_file = await context.bot.get_file(doc.file_id)
        upload_path = Path("uploads") / f"{user.id}_{doc.file_name}"
        await tg_file.download_to_drive(str(upload_path))

        # ── Parse URLs ───────────────────────────────────────────────────
        with open(upload_path, "r", encoding="utf-8", errors="ignore") as fh:
            raw_text = fh.read()

        cleanup_file(upload_path)  # remove upload immediately

        urls = parse_video_urls(raw_text)

        if not urls:
            await status_msg.edit_text(
                "🔍 No video URLs found in that file.\n\n"
                "Make sure the file contains direct `.mp4` or video links (one per line)."
            )
            return

        if len(urls) > MAX_URLS:
            await status_msg.edit_text(
                f"⚠️ Found {len(urls)} URLs but the limit is {MAX_URLS}. "
                f"Only the first {MAX_URLS} will be processed."
            )
            urls = urls[:MAX_URLS]

        # ── Store URL list in user context ────────────────────────────────
        key = f"urls_{user.id}"
        context.bot_data[key] = urls

        # ── Build summary & action keyboard ──────────────────────────────
        preview_lines = "\n".join(f"  `{i+1}.` {_truncate(u, 60)}" for i, u in enumerate(urls[:10]))
        more = f"\n  … and {len(urls)-10} more" if len(urls) > 10 else ""

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"⬇️ Download All ({len(urls)})", callback_data=f"dl_all_{user.id}"),
            ],
            [
                InlineKeyboardButton("📋 List URLs Only",  callback_data=f"list_{user.id}"),
                InlineKeyboardButton("🔢 Pick Numbers",   callback_data=f"pick_{user.id}"),
            ],
            [
                InlineKeyboardButton("❌ Cancel",         callback_data=f"cancel_{user.id}"),
            ],
        ])

        await status_msg.edit_text(
            f"✅ Found *{len(urls)} video URL(s)* in `{doc.file_name}`:\n\n"
            f"{preview_lines}{more}\n\n"
            "Choose an action:",
            parse_mode="Markdown",
            reply_markup=keyboard,
        )

    except Exception as exc:
        logger.exception("Error handling file from user %s: %s", user.id, exc)
        await status_msg.edit_text(f"❌ Error processing file: `{exc}`", parse_mode="Markdown")


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[:max_len - 3] + "…"
