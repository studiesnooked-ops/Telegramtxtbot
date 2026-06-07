"""
Admin-only command handlers.
"""

import logging
import time

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Simple in-process stats counter
_stats = {
    "files_processed": 0,
    "urls_extracted": 0,
    "users": set(),
    "start_time": time.time(),
}


def record_extraction(user_id: int, url_count: int):
    """Call this after each successful extraction."""
    _stats["files_processed"] += 1
    _stats["urls_extracted"] += url_count
    _stats["users"].add(user_id)


def _is_admin(user_id: int, config) -> bool:
    return not config.ADMIN_IDS or user_id in config.ADMIN_IDS


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = context.bot_data["config"]
    user = update.effective_user

    if not _is_admin(user.id, config):
        await update.message.reply_text("⛔ Admin only.")
        return

    uptime_s = int(time.time() - _stats["start_time"])
    h, rem = divmod(uptime_s, 3600)
    m, s = divmod(rem, 60)

    await update.message.reply_text(
        f"📊 *Bot Statistics*\n\n"
        f"• Uptime: `{h}h {m}m {s}s`\n"
        f"• Files processed: `{_stats['files_processed']}`\n"
        f"• URLs extracted: `{_stats['urls_extracted']}`\n"
        f"• Unique users: `{len(_stats['users'])}`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = context.bot_data["config"]
    user = update.effective_user

    if not _is_admin(user.id, config):
        await update.message.reply_text("⛔ Admin only.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    text = " ".join(context.args)
    sent = 0
    for uid in list(_stats["users"]):
        try:
            await context.bot.send_message(uid, f"📢 {text}")
            sent += 1
        except Exception:
            pass

    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")
