"""
Handles .txt file uploads. Supports multiple files in one message.
"""

import logging
import os
import uuid
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.extractor import extract_from_file
from src.handlers.sender import send_urls_to_user
from src.utils.progress import ProgressMessage

logger = logging.getLogger(__name__)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: one or multiple .txt files uploaded."""
    config = context.bot_data["config"]
    message = update.effective_message
    user = update.effective_user

    logger.info(f"User {user.id} ({user.username}) uploaded a file.")

    doc = message.document

    # ── Guard: file size ──────────────────────────────────────────────────────
    if doc.file_size and doc.file_size > config.max_file_bytes:
        await message.reply_text(
            f"⚠️ File too large ({doc.file_size / 1024 / 1024:.1f} MB). "
            f"Maximum allowed: {config.MAX_FILE_SIZE_MB} MB."
        )
        return

    # ── Guard: file type ──────────────────────────────────────────────────────
    name = doc.file_name or "file.txt"
    if not name.lower().endswith(".txt"):
        await message.reply_text(
            "⚠️ Only `.txt` files are supported.\n"
            "Please upload a plain text file containing video URLs."
        )
        return

    progress = ProgressMessage(message)
    await progress.send(f"📂 Received `{name}` — downloading…")

    # ── Download ──────────────────────────────────────────────────────────────
    save_dir = Path(config.UPLOAD_DIR)
    save_path = save_dir / f"{user.id}_{uuid.uuid4().hex[:8]}_{name}"

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(str(save_path))
    except Exception as e:
        logger.error(f"Download failed: {e}")
        await progress.edit("❌ Failed to download the file. Please try again.")
        return

    # ── Extract ───────────────────────────────────────────────────────────────
    await progress.edit(f"🔍 Scanning `{name}` for MP4 links…")

    try:
        result = await extract_from_file(
            save_path,
            max_urls=config.MAX_URLS_PER_FILE,
            executor=context.bot_data.get("executor"),
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        await progress.edit(f"❌ Could not read `{name}`: {e}")
        return
    finally:
        # Clean up temp file
        try:
            os.remove(save_path)
        except Exception:
            pass

    # ── Nothing found ─────────────────────────────────────────────────────────
    if not result.urls:
        await progress.edit(
            f"😕 No MP4 / video URLs found in `{name}`.\n\n"
            f"• Lines scanned: `{result.total_lines:,}`\n"
            f"• URLs detected: `{result.total_urls_found}`\n\n"
            "Make sure the file contains direct `.mp4` links."
        )
        return

    # ── Confirm before sending (large batches) ────────────────────────────────
    if len(result.urls) > 20:
        job_id = uuid.uuid4().hex[:12]
        if "pending_jobs" not in context.user_data:
            context.user_data["pending_jobs"] = {}
        context.user_data["pending_jobs"][job_id] = result.urls

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"✅ Send all {len(result.urls)} links",
                        callback_data=f"confirm_send_{job_id}",
                    ),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{job_id}"),
                ]
            ]
        )

        await progress.edit(
            f"✅ Scan complete for `{name}`!\n\n"
            f"📊 **Stats:**\n"
            f"• Lines scanned: `{result.total_lines:,}`\n"
            f"• Video URLs found: `{result.total_urls_found}`\n"
            f"• Duplicates removed: `{result.duplicates_removed}`\n"
            f"• **Ready to send: `{len(result.urls)}`**\n\n"
            f"Confirm to receive all links:",
            reply_markup=keyboard,
        )
    else:
        await progress.edit(
            f"✅ Found `{len(result.urls)}` video link(s) in `{name}` — sending now…"
        )
        await send_urls_to_user(update, context, result.urls, progress.msg)
