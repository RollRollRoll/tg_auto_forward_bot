from __future__ import annotations
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters,
)

from bot.database.connection import get_db
from bot.database.crud import list_channels
from bot.handlers.filters import admin_only, private_chat_only
from bot.services.pipeline import download_and_publish
from bot.utils.validators import extract_url, resolve_t_co, sanitize_caption

logger = logging.getLogger(__name__)

WAITING_CAPTION = 0
WAITING_CHANNEL = 1


@private_chat_only
@admin_only
async def entry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = extract_url(update.message.text)
    if not url:
        return ConversationHandler.END

    if "t.co/" in url:
        try:
            url = await resolve_t_co(url)
        except Exception:
            await update.message.reply_text("Failed to resolve short link. Please send the full URL.")
            return ConversationHandler.END

    context.user_data["source_url"] = url
    await update.message.reply_text("Link received. Please enter the caption (HTML format supported, max 1024 chars):")
    return WAITING_CAPTION


async def caption_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw_caption = update.message.text
    sanitized, error = sanitize_caption(raw_caption)
    if error:
        await update.message.reply_text(error)
        return WAITING_CAPTION

    context.user_data["caption"] = sanitized
    db = await get_db()
    channels = await list_channels(db)

    if not channels:
        await update.message.reply_text("No channels configured. Use /add_channel first.")
        return ConversationHandler.END

    if len(channels) == 1:
        context.user_data["channel_chat_id"] = channels[0]["chat_id"]
        return await _start_download(update, context)

    keyboard = [
        [InlineKeyboardButton(ch["title"], callback_data=str(ch["chat_id"]))]
        for ch in channels
    ]
    await update.message.reply_text("Select target channel:", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_CHANNEL


async def channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["channel_chat_id"] = int(query.data)
    return await _start_download(update, context)


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def _start_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    source_url = context.user_data["source_url"]
    caption = context.user_data["caption"]
    channel_chat_id = context.user_data["channel_chat_id"]
    user_id = update.effective_user.id
    user_chat_id = update.effective_chat.id

    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text("Task accepted. Downloading video...")

    slot_manager = context.bot_data["slot_manager"]

    context.application.create_task(
        download_and_publish(
            bot=context.bot, slot_manager=slot_manager,
            user_chat_id=user_chat_id, user_id=user_id,
            source_url=source_url, caption=caption, channel_chat_id=channel_chat_id,
        ),
        update=update,
    )

    context.user_data.clear()
    return ConversationHandler.END


def build_conversation_handler() -> ConversationHandler:
    url_filter = filters.TEXT & filters.Regex(
        r"https?://(?:(?:twitter|x)\.com/\w+/status/\d+|t\.co/\w+)"
    )
    return ConversationHandler(
        entry_points=[MessageHandler(url_filter, entry_handler)],
        states={
            WAITING_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, caption_handler)],
            WAITING_CHANNEL: [CallbackQueryHandler(channel_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        per_user=True,
        per_chat=True,
    )
