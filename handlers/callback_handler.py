"""
Inline-keyboard callback handler.
Routes: dl_all, list, pick, cancel, page, confirm_pick
"""

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes

from utils.downloader import download_and_send_videos
from utils.url_parser import format_url_list

logger = logging.getLogger("bot.callbacks")

PAGE_SIZE = 8   # URLs shown per page in "pick" mode


async def _callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data: str = query.data or ""
    user_id = update.effective_user.id

    # ── Download All ──────────────────────────────────────────────────────
    if data.startswith("dl_all_"):
        uid = int(data.split("_")[-1])
        if uid != user_id:
            await query.answer("⛔ Not your session.", show_alert=True)
            return
        urls = context.bot_data.get(f"urls_{uid}", [])
        if not urls:
            await query.edit_message_text("⚠️ Session expired. Please re-upload the file.")
            return
        await query.edit_message_text(
            f"🚀 Starting download of *{len(urls)}* video(s)…\n"
            "I'll send each video as it finishes.",
            parse_mode="Markdown",
        )
        asyncio.create_task(
            download_and_send_videos(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                urls=urls,
                queue_manager=context.bot_data.get("queue_manager"),
            )
        )

    # ── List URLs Only ────────────────────────────────────────────────────
    elif data.startswith("list_"):
        uid = int(data.split("_")[-1])
        urls = context.bot_data.get(f"urls_{uid}", [])
        if not urls:
            await query.edit_message_text("⚠️ Session expired.")
            return
        text = format_url_list(urls)
        # Telegram message limit = 4096 chars
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        await query.edit_message_text(
            f"📋 *{len(urls)} Video URL(s):*\n\n" + chunks[0],
            parse_mode="Markdown",
        )
        for chunk in chunks[1:]:
            await update.effective_message.reply_text(chunk, parse_mode="Markdown")

    # ── Pick Numbers mode ─────────────────────────────────────────────────
    elif data.startswith("pick_"):
        uid = int(data.split("_")[-1])
        if uid != user_id:
            await query.answer("⛔ Not your session.", show_alert=True)
            return
        urls = context.bot_data.get(f"urls_{uid}", [])
        if not urls:
            await query.edit_message_text("⚠️ Session expired.")
            return
        await _show_pick_page(query, context, uid, urls, page=0, selected=set())

    # ── Paging ────────────────────────────────────────────────────────────
    elif data.startswith("page_"):
        _, uid_str, page_str = data.split("_")
        uid = int(uid_str)
        page = int(page_str)
        urls = context.bot_data.get(f"urls_{uid}", [])
        selected: set = context.bot_data.get(f"selected_{uid}", set())
        await _show_pick_page(query, context, uid, urls, page, selected)

    # ── Toggle selection ──────────────────────────────────────────────────
    elif data.startswith("toggle_"):
        parts = data.split("_")
        uid = int(parts[1])
        idx = int(parts[2])
        page = int(parts[3])
        urls = context.bot_data.get(f"urls_{uid}", [])
        selected: set = context.bot_data.get(f"selected_{uid}", set())
        selected ^= {idx}   # toggle
        context.bot_data[f"selected_{uid}"] = selected
        await _show_pick_page(query, context, uid, urls, page, selected)

    # ── Confirm picked selection ──────────────────────────────────────────
    elif data.startswith("confirm_"):
        uid = int(data.split("_")[-1])
        urls = context.bot_data.get(f"urls_{uid}", [])
        selected: set = context.bot_data.get(f"selected_{uid}", set())
        chosen = [urls[i] for i in sorted(selected) if i < len(urls)]
        if not chosen:
            await query.answer("Select at least one video first!", show_alert=True)
            return
        await query.edit_message_text(
            f"🚀 Downloading *{len(chosen)}* selected video(s)…",
            parse_mode="Markdown",
        )
        asyncio.create_task(
            download_and_send_videos(
                bot=context.bot,
                chat_id=update.effective_chat.id,
                urls=chosen,
                queue_manager=context.bot_data.get("queue_manager"),
            )
        )

    # ── Cancel ────────────────────────────────────────────────────────────
    elif data.startswith("cancel_"):
        uid = int(data.split("_")[-1])
        context.bot_data.pop(f"urls_{uid}", None)
        context.bot_data.pop(f"selected_{uid}", None)
        await query.edit_message_text("❌ Cancelled.")

    # ── Help / Status shortcuts ───────────────────────────────────────────
    elif data == "help":
        from handlers.command_handler import HELP_TEXT
        await query.edit_message_text(HELP_TEXT, parse_mode="Markdown")

    elif data == "status":
        qm = context.bot_data.get("queue_manager")
        stats = qm.get_stats(user_id) if qm else {}
        await query.edit_message_text(
            f"📊 Active: `{stats.get('global_active',0)}` | "
            f"Queued: `{stats.get('global_queued',0)}`",
            parse_mode="Markdown",
        )


async def _show_pick_page(query, context, uid, urls, page, selected):
    total = len(urls)
    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, total)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    rows = []
    for i in range(start, end):
        label = ("✅ " if i in selected else "") + f"{i+1}. {_short(urls[i], 35)}"
        rows.append([InlineKeyboardButton(label, callback_data=f"toggle_{uid}_{i}_{page}")])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("◀️ Prev", callback_data=f"page_{uid}_{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{uid}_{page+1}"))
    rows.append(nav_row)

    rows.append([
        InlineKeyboardButton(f"✅ Download ({len(selected)} selected)", callback_data=f"confirm_{uid}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{uid}"),
    ])

    await query.edit_message_text(
        f"🔢 *Select videos to download* (page {page+1}/{total_pages}):\n"
        f"Tap to toggle ✅",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


def _short(url: str, max_len: int) -> str:
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path
        name = path.split("/")[-1] or url
        return name[:max_len]
    except Exception:
        return url[:max_len]


# Exported handler object
handle_callback = CallbackQueryHandler(_callback_router)
