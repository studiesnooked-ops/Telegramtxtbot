"""
Basic command handlers.
"""

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

_HELP_TEXT = """
🎬 *Video URL Extractor Bot*

*What I do:*
I scan `.txt` files (or pasted text) and extract all MP4 / video URLs found inside.

*How to use:*
1️⃣ Send me any `.txt` file — I'll find every video link automatically.
2️⃣ Or paste text directly containing video URLs.

*Supported URL types:*
• Direct `.mp4` links
• CDN-hosted video files (AWS S3, Cloudfront, Bunny, etc.)
• URLs with video in query parameters
• URL-encoded video links

*Commands:*
/start — Welcome message
/help — This help text
/cancel — Cancel current operation
/stats — Bot statistics _(admin only)_

*Tips:*
• Files up to 20 MB are supported
• Up to 500 URLs extracted per file
• Large results (50+) are sent as a bundled `.txt` file
• You can upload multiple files one after another
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Hello, *{user.first_name}*!\n\n"
        "I extract MP4 and video URLs from `.txt` files.\n\n"
        "Just send me a text file and I'll do the rest! 🚀\n\n"
        "Type /help for full instructions.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        _HELP_TEXT,
        parse_mode=ParseMode.MARKDOWN,
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Any pending operations have been cancelled.\n"
        "Send me a `.txt` file whenever you're ready!"
    )
