import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Chat, Message
from telegram.constants import ChatType
from telegram.ext import ConversationHandler

from bot.handlers.conversation import (
    WAITING_CAPTION,
    WAITING_CHANNEL,
    _start_download,
    cancel_handler,
    caption_handler,
)


def _make_update(text="", user_id=111, chat_type=ChatType.PRIVATE):
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.type = chat_type
    update.effective_chat.id = user_id
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = user_id
    update.message = MagicMock(spec=Message)
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _make_context(bot_data=None):
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot_data = bot_data or {"slot_manager": MagicMock()}
    ctx.bot = AsyncMock()
    ctx.application = MagicMock()
    ctx.application.create_task = MagicMock(
        side_effect=lambda coro, **kwargs: (coro.close(), MagicMock())[1]
    )
    return ctx


@pytest.mark.asyncio
async def test_caption_handler_too_long():
    update = _make_update("a" * 1025)
    ctx = _make_context()
    result = await caption_handler(update, ctx)
    assert result == WAITING_CAPTION
    update.message.reply_text.assert_awaited_once()
    assert "1025" in str(update.message.reply_text.call_args)


@pytest.mark.asyncio
async def test_caption_handler_single_channel():
    update = _make_update("valid caption")
    ctx = _make_context()
    ctx.user_data["source_url"] = "https://x.com/u/status/1"
    channels = [{"chat_id": -100123, "title": "Test"}]
    with patch("bot.handlers.conversation.get_db", new_callable=AsyncMock), \
         patch("bot.handlers.conversation.list_channels", new_callable=AsyncMock, return_value=channels):
        result = await caption_handler(update, ctx)
    assert result == ConversationHandler.END
    ctx.application.create_task.assert_called_once()
    assert ctx.application.create_task.call_args.kwargs["update"] is update


@pytest.mark.asyncio
async def test_caption_handler_multi_channel_shows_keyboard():
    update = _make_update("valid caption")
    ctx = _make_context()
    ctx.user_data["source_url"] = "https://x.com/u/status/1"
    channels = [{"chat_id": -100123, "title": "Chan A"}, {"chat_id": -100456, "title": "Chan B"}]
    with patch("bot.handlers.conversation.get_db", new_callable=AsyncMock), \
         patch("bot.handlers.conversation.list_channels", new_callable=AsyncMock, return_value=channels):
        result = await caption_handler(update, ctx)
    assert result == WAITING_CHANNEL
    assert "reply_markup" in update.message.reply_text.call_args.kwargs


@pytest.mark.asyncio
async def test_cancel_handler():
    update = _make_update("/cancel")
    ctx = _make_context()
    ctx.user_data["source_url"] = "https://x.com/u/status/1"
    result = await cancel_handler(update, ctx)
    assert result == ConversationHandler.END
    assert len(ctx.user_data) == 0


@pytest.mark.asyncio
async def test_start_download_uses_application_create_task_and_clears_state():
    update = _make_update("valid caption")
    ctx = _make_context({"slot_manager": MagicMock()})
    ctx.user_data.update(
        {
            "source_url": "https://x.com/u/status/1",
            "caption": "<b>ok</b>",
            "channel_chat_id": -100123,
        }
    )

    result = await _start_download(update, ctx)

    assert result == ConversationHandler.END
    update.message.reply_text.assert_awaited_once_with("Task accepted. Downloading video...")
    ctx.application.create_task.assert_called_once()
    assert ctx.application.create_task.call_args.kwargs["update"] is update
    assert ctx.user_data == {}
