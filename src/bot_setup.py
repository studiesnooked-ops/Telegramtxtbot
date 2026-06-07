"""
Creates the PTB Application and registers all handlers.
"""

import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from src.config import Config
from src.handlers.admin import admin_stats, broadcast
from src.handlers.commands import cancel, help_command, start
from src.handlers.document import handle_document
from src.handlers.text_urls import handle_text_message
from src.handlers.errors import error_handler

logger = logging.getLogger(__name__)


async def create_application(config: Config) -> Application:
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .concurrent_updates(True)          # Handle updates in parallel
        .build()
    )

    # Store config for handlers
    app.bot_data["config"] = config

    # ── Command handlers ──────────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # ── Document handler (.txt files) ─────────────────────────────────────────
    app.add_handler(
        MessageHandler(
            filters.Document.MimeType("text/plain")
            | filters.Document.FileExtension("txt"),
            handle_document,
        )
    )

    # ── Text message handler (pasted URLs) ───────────────────────────────────
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message)
    )

    # ── Callback query handler (inline buttons) ───────────────────────────────
    app.add_handler(CallbackQueryHandler(handle_callback))

    # ── Error handler ─────────────────────────────────────────────────────────
    app.add_error_handler(error_handler)

    logger.info("All handlers registered successfully.")
    return app


async def handle_callback(update, context):
    """Route inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data.startswith("cancel_"):
        await query.edit_message_text("❌ Operation cancelled.")
    elif data.startswith("confirm_send_"):
        # Trigger sending from stored context
        job_id = data.replace("confirm_send_", "")
        jobs = context.user_data.get("pending_jobs", {})
        if job_id in jobs:
            urls = jobs.pop(job_id)
            from src.handlers.sender import send_urls_to_user
            await query.edit_message_text(
                f"✅ Confirmed! Sending {len(urls)} video link(s)..."
            )
            await send_urls_to_user(update, context, urls, query.message)
        else:
            await query.edit_message_text("⚠️ Session expired. Please re-upload the file.")
