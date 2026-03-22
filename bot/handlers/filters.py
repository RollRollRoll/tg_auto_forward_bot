from __future__ import annotations
import functools
from typing import Callable, Any

from telegram import Update
from telegram.constants import ChatType

from bot.config import SUPER_ADMIN_ID
from bot.database.connection import get_db
from bot.database.crud import is_admin


def private_chat_only(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(update: Update, context: Any, *args, **kwargs):
        if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper


def admin_only(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(update: Update, context: Any, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id == SUPER_ADMIN_ID:
            return await func(update, context, *args, **kwargs)
        db = await get_db()
        if await is_admin(db, user_id=user_id):
            return await func(update, context, *args, **kwargs)
        return None
    return wrapper


def super_admin_only(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(update: Update, context: Any, *args, **kwargs):
        if update.effective_user.id != SUPER_ADMIN_ID:
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper
