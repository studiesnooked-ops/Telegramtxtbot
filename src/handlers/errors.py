"""
Global error handler for the PTB Application.
"""

import logging
import traceback

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log all unhandled exceptions and notify the user."""
    logger.error(
        "Unhandled exception while handling an update:",
        exc_info=context.error,
    )

    tb = "".join(traceback.format_exception(type(context.error), context.error, context.error.__traceback__))
    logger.debug(f"Traceback:\n{tb}")

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Please try again.\n"
                "If the problem persists, contact the bot admin."
            )
        except Exception:
            pass
