"""Telegram command handlers: /start /help /status /cancel"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger("bot.commands")

WELCOME_TEXT = """
🎬 *Video Extractor Bot*

Hello, {name}! I can extract MP4 video links from `.txt` files and let you download them in bulk.

*How to use:*
1️⃣ Send me a `.txt` file containing video URLs (one per line)
2️⃣ I'll scan it for all MP4 / video links
3️⃣ Choose to download all, pick specific ones, or just get a clean list

*Supported URL formats:*
• Direct `.mp4` links
• URLs containing `video`, `media`, `stream`
• CDN URLs (e.g. cloudfront, akamai, etc.)

Type /help for more info.
"""

HELP_TEXT = """
📖 *Help & Commands*

`/start`  – Welcome message
`/help`   – This help text
`/status` – Show current queue status
`/cancel` – Cancel your active job

*File format tips:*
• One URL per line
• Lines starting with `#` are treated as comments
• Blank lines are ignored
• Supports HTTP and HTTPS links

*Limits:*
• Max file size: 20 MB
• Max URLs per file: 500
• Concurrent downloads per user: 3

*Output:*
• Bot sends each video file directly in chat (≤50 MB)
• Larger files: you get a direct download link message
"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Help", callback_data="help"),
         InlineKeyboardButton("📊 Status", callback_data="status")],
    ])
    await update.message.reply_text(
        WELCOME_TEXT.format(name=user.first_name),
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    qm = context.bot_data.get("queue_manager")
    if not qm:
        await update.message.reply_text("⚠️ Queue manager not ready yet.")
        return

    user_id = update.effective_user.id
    stats = qm.get_stats(user_id)
    text = (
        f"📊 *Queue Status*\n\n"
        f"🌐 Global:\n"
        f"  • Active jobs: `{stats['global_active']}`\n"
        f"  • Queued jobs: `{stats['global_queued']}`\n"
        f"  • Total workers: `{stats['max_workers']}`\n\n"
        f"👤 Your jobs:\n"
        f"  • Active: `{stats['user_active']}`\n"
        f"  • Queued: `{stats['user_queued']}`\n"
        f"  • Completed today: `{stats['user_completed']}`\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    qm = context.bot_data.get("queue_manager")
    user_id = update.effective_user.id
    if qm:
        cancelled = qm.cancel_user_jobs(user_id)
        await update.message.reply_text(
            f"🛑 Cancelled `{cancelled}` job(s).",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("Nothing to cancel.")
