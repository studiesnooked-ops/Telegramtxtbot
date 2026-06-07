#!/usr/bin/env python3
"""
Telegram Video Extractor Bot
Extracts MP4 URLs from .txt files and processes them.
Optimized for Render.com web service deployment.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from handlers.file_handler import handle_txt_file
from handlers.command_handler import (
    start_command,
    help_command,
    status_command,
    cancel_command,
)
from handlers.callback_handler import handle_callback
from utils.logger import setup_logger
from utils.queue_manager import QueueManager
from utils.health_server import run_health_server

# ── Config ──────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")   # e.g. https://your-app.onrender.com
PORT = int(os.environ.get("PORT", 10000))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 4))

logger = setup_logger("bot", "logs/bot.log")


def validate_env():
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN environment variable not set!")
        sys.exit(1)
    if not WEBHOOK_URL:
        logger.warning(
            "WEBHOOK_URL not set – falling back to polling mode. "
            "Set WEBHOOK_URL on Render for production."
        )


async def post_init(application: Application) -> None:
    """Called once after the app is initialized."""
    application.bot_data["queue_manager"] = QueueManager(max_workers=MAX_WORKERS)
    logger.info("QueueManager initialized with %d workers", MAX_WORKERS)


async def post_shutdown(application: Application) -> None:
    qm: QueueManager = application.bot_data.get("queue_manager")
    if qm:
        await qm.shutdown()
    logger.info("Bot shut down cleanly.")


def build_application() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)           # handle multiple users in parallel
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start",  start_command))
    app.add_handler(CommandHandler("help",   help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # .txt file uploads
    app.add_handler(MessageHandler(filters.Document.TXT, handle_txt_file))

    # Inline-keyboard callbacks
    app.add_handler(handle_callback)

    return app


def main():
    validate_env()

    # Ensure directories exist
    for d in ("logs", "uploads", "downloads"):
        Path(d).mkdir(exist_ok=True)

    application = build_application()

    if WEBHOOK_URL:
        # ── Webhook mode (Render web service) ─────────────────────────────
        logger.info("Starting in WEBHOOK mode on port %d", PORT)
        logger.info("Webhook URL: %s/webhook", WEBHOOK_URL)

        # Start lightweight health-check HTTP server in background thread
        import threading
        threading.Thread(
            target=run_health_server,
            args=(PORT,),
            daemon=True,
        ).start()

        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"{WEBHOOK_URL}/webhook",
            url_path="/webhook",
            drop_pending_updates=True,
        )
    else:
        # ── Polling mode (local dev / free Render without custom domain) ──
        logger.info("Starting in POLLING mode")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )


if __name__ == "__main__":
    main()
