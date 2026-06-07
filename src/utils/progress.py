"""
Utility for sending and editing a progress message.
"""

import logging
from typing import Optional

from telegram import InlineKeyboardMarkup, Message
from telegram.constants import ParseMode
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class ProgressMessage:
    """
    Wraps a Telegram message for easy send/edit cycles.
    Falls back to a new message if editing fails.
    """

    def __init__(self, original_message: Message):
        self._original = original_message
        self.msg: Optional[Message] = None

    async def send(self, text: str, reply_markup=None):
        """Send the initial progress message."""
        try:
            self.msg = await self._original.reply_text(
                text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
            )
        except TelegramError as e:
            logger.warning(f"Failed to send progress message: {e}")

    async def edit(
        self,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
    ):
        """Edit the progress message in place."""
        if self.msg:
            try:
                await self.msg.edit_text(
                    text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                )
                return
            except TelegramError as e:
                logger.warning(f"Edit failed ({e}), sending new message.")

        # Fallback: send a new message
        await self.send(text, reply_markup)
