#!/usr/bin/env python3
"""
Telegram Video Extractor Bot (Polling + Render Web Service compatible)
"""

import os
import sys
import logging
import threading
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

# ── Your handlers ─────────────────────────────────────────────
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

# 🔥 ADD HEALTH SERVER IMPORT
from utils.health_server import run_health_server


# ── Config ────────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", 4))

logger = setup_logger("bot", "logs/bot.log")


# ── ENV CHECK ────────────────────────────────────────────────
def validate_env():
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is missing!")
        sys.exit(1)


# ── Lifecycle hooks ───────────────────────────────────────────
async def post_init(application: Application):
    application.bot_data["queue_manager"] = QueueManager(max_workers=MAX_WORKERS)
    logger.info("QueueManager started with %d workers", MAX_WORKERS)


async def post_shutdown(application: Application):
    qm = application.bot_data.get("queue_manager")
    if qm:
        await qm.shutdown()
    logger.info("Bot shutdown complete")


# ── BUILD BOT ────────────────────────────────────────────────
def build_application() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # File uploads
    app.add_handler(MessageHandler(filters.Document.TXT, handle_txt_file))

    # Callback queries
    app.add_handler(handle_callback)

    return app


# ── MAIN ──────────────────────────────────────────────────────
def main():
    validate_env()

    # Create folders
    for folder in ("logs", "uploads", "downloads"):
        Path(folder).mkdir(exist_ok=True)

    application = build_application()

    logger.info("Starting WEB SERVICE MODE (Polling + Health server)")

    # 🔥 START HEALTH SERVER (REQUIRED FOR RENDER WEB SERVICE)
    threading.Thread(
        target=run_health_server,
        daemon=True
    ).start()

    # Start Telegram bot
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
