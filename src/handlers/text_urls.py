"""
Handles plain text messages containing URLs pasted directly.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.extractor import extract_mp4_urls
from src.handlers.sender import send_urls_to_user
from src.utils.progress import ProgressMessage

logger = logging.getLogger(__name__)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extract video URLs from a pasted block of text."""
    config = context.bot_data["config"]
    message = update.effective_message
    text = message.text or ""

    # Ignore very short messages (greetings, etc.)
    if len(text) < 20:
        await message.reply_text(
            "👋 Hello! Send me a `.txt` file or paste text containing MP4 URLs "
            "and I'll extract them for you.\n\nType /help for instructions."
        )
        return

    progress = ProgressMessage(message)
    await progress.send("🔍 Scanning your text for video URLs…")

    result = await extract_mp4_urls(
        text,
        source_name="pasted_text",
        max_urls=config.MAX_URLS_PER_FILE,
        executor=context.bot_data.get("executor"),
    )

    if not result.urls:
        await progress.edit(
            "😕 No MP4 / video URLs found in your message.\n\n"
            "Try uploading a `.txt` file instead, or check that your links are valid."
        )
        return

    await progress.edit(
        f"✅ Found `{len(result.urls)}` video link(s) — sending now…"
    )
    await send_urls_to_user(update, context, result.urls, progress.msg)
