import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Chat, Message
from telegram.constants import ChatType
from bot.handlers.filters import private_chat_only, admin_only, super_admin_only

def _make_update(chat_type=ChatType.PRIVATE, user_id=111):
    update = MagicMock(spec=Update)
    update.effective_chat = MagicMock(spec=Chat)
    update.effective_chat.type = chat_type
    update.effective_user = MagicMock(spec=User)
    update.effective_user.id = user_id
    update.message = MagicMock(spec=Message)
    return update

@pytest.mark.asyncio
async def test_private_chat_only_allows_private():
    handler = AsyncMock(return_value="ok")
    wrapped = private_chat_only(handler)
    result = await wrapped(_make_update(ChatType.PRIVATE), MagicMock())
    assert result == "ok"
    handler.assert_awaited_once()

@pytest.mark.asyncio
async def test_private_chat_only_blocks_group():
    handler = AsyncMock(return_value="ok")
    wrapped = private_chat_only(handler)
    result = await wrapped(_make_update(ChatType.GROUP), MagicMock())
    assert result is None
    handler.assert_not_awaited()

@pytest.mark.asyncio
async def test_admin_only_allows_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = admin_only(handler)
    with patch("bot.handlers.filters.is_admin", return_value=True), \
         patch("bot.handlers.filters.get_db") as mock_get_db:
        mock_get_db.return_value = MagicMock()
        result = await wrapped(_make_update(user_id=111), MagicMock())
    assert result == "ok"

@pytest.mark.asyncio
async def test_admin_only_blocks_non_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = admin_only(handler)
    with patch("bot.handlers.filters.is_admin", return_value=False), \
         patch("bot.handlers.filters.get_db") as mock_get_db, \
         patch("bot.handlers.filters.SUPER_ADMIN_ID", 0):
        mock_get_db.return_value = MagicMock()
        result = await wrapped(_make_update(user_id=999), MagicMock())
    assert result is None

@pytest.mark.asyncio
async def test_admin_only_allows_super_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = admin_only(handler)
    with patch("bot.handlers.filters.is_admin", return_value=False), \
         patch("bot.handlers.filters.get_db") as mock_get_db, \
         patch("bot.handlers.filters.SUPER_ADMIN_ID", 42):
        mock_get_db.return_value = MagicMock()
        result = await wrapped(_make_update(user_id=42), MagicMock())
    assert result == "ok"

@pytest.mark.asyncio
async def test_super_admin_only_allows_super_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = super_admin_only(handler)
    with patch("bot.handlers.filters.SUPER_ADMIN_ID", 42):
        result = await wrapped(_make_update(user_id=42), MagicMock())
    assert result == "ok"

@pytest.mark.asyncio
async def test_super_admin_only_blocks_regular_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = super_admin_only(handler)
    with patch("bot.handlers.filters.SUPER_ADMIN_ID", 42):
        result = await wrapped(_make_update(user_id=111), MagicMock())
    assert result is None
