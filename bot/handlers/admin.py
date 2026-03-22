from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.filters import private_chat_only, admin_only, super_admin_only
from bot.database.connection import get_db
from bot.database.crud import (
    add_admin, remove_admin, list_admins,
    add_channel, remove_channel, list_channels,
    get_setting, set_setting, get_all_settings,
)

@private_chat_only
@super_admin_only
async def add_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /add_admin <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id must be an integer.")
        return
    db = await get_db()
    try:
        await add_admin(db, user_id=user_id)
        await update.message.reply_text(f"Admin {user_id} added.")
    except Exception:
        await update.message.reply_text(f"Admin {user_id} already exists.")

@private_chat_only
@super_admin_only
async def remove_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /remove_admin <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id must be an integer.")
        return
    db = await get_db()
    if await remove_admin(db, user_id=user_id):
        await update.message.reply_text(f"Admin {user_id} removed.")
    else:
        await update.message.reply_text(f"Admin {user_id} not found.")

@private_chat_only
@super_admin_only
async def list_admins_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = await get_db()
    admins = await list_admins(db)
    if not admins:
        await update.message.reply_text("No admins configured.")
        return
    lines = [f"<b>Admins ({len(admins)}):</b>"]
    for a in admins:
        lines.append(f"  {a['user_id']} — {a['username'] or 'N/A'}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

@private_chat_only
@admin_only
async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /add_channel <chat_id>")
        return
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("chat_id must be an integer.")
        return
    bot = context.bot
    try:
        chat = await bot.get_chat(chat_id)
    except Exception:
        await update.message.reply_text("Invalid chat_id or bot has no access to this channel.")
        return
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        if not getattr(member, "can_post_messages", False):
            await update.message.reply_text("Bot is not an admin of this channel with posting permissions. Please add the bot as a channel admin first.")
            return
    except Exception:
        await update.message.reply_text("Bot is not a member of this channel. Please add the bot as a channel admin first.")
        return
    db = await get_db()
    try:
        await add_channel(db, chat_id=chat_id, title=chat.title or str(chat_id))
        await update.message.reply_text(f"Channel added: <b>{chat.title}</b> ({chat_id})", parse_mode="HTML")
    except Exception:
        await update.message.reply_text(f"Channel {chat_id} already exists.")

@private_chat_only
@admin_only
async def remove_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /remove_channel <chat_id>")
        return
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("chat_id must be an integer.")
        return
    db = await get_db()
    if await remove_channel(db, chat_id=chat_id):
        await update.message.reply_text(f"Channel {chat_id} removed.")
    else:
        await update.message.reply_text(f"Channel {chat_id} not found.")

@private_chat_only
@admin_only
async def list_channels_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = await get_db()
    channels = await list_channels(db)
    if not channels:
        await update.message.reply_text("No channels configured.")
        return
    lines = [f"<b>Channels ({len(channels)}):</b>"]
    for ch in channels:
        lines.append(f"  {ch['title']} ({ch['chat_id']})")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

@private_chat_only
@admin_only
async def set_setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("Usage: /set <key> <value>")
        return
    key, value = context.args[0], context.args[1]
    db = await get_db()
    try:
        await set_setting(db, key, value)
        await update.message.reply_text(f"Setting <code>{key}</code> = <code>{value}</code>", parse_mode="HTML")
    except ValueError as e:
        await update.message.reply_text(str(e))

@private_chat_only
@admin_only
async def get_setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /get <key>")
        return
    db = await get_db()
    val = await get_setting(db, context.args[0])
    if val is None:
        await update.message.reply_text(f"Unknown setting: {context.args[0]}")
    else:
        await update.message.reply_text(f"<code>{context.args[0]}</code> = <code>{val}</code>", parse_mode="HTML")

@private_chat_only
@admin_only
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = await get_db()
    settings = await get_all_settings(db)
    lines = ["<b>Settings:</b>"]
    for k, v in sorted(settings.items()):
        lines.append(f"  <code>{k}</code> = <code>{v}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
