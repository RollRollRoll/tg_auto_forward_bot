import pytest
from unittest.mock import AsyncMock, MagicMock
from bot.services.publisher import publish_video

@pytest.mark.asyncio
async def test_publish_video_success():
    bot = AsyncMock()
    bot.send_video.return_value = MagicMock(message_id=42)
    result = await publish_video(
        bot, channel_chat_id=-100123, file_path="/tmp/test.mp4",
        caption="hello", duration=10, width=1920, height=1080,
    )
    assert result == 42
    bot.send_video.assert_awaited_once()
    assert bot.send_video.call_args.kwargs["supports_streaming"] is True

@pytest.mark.asyncio
async def test_publish_video_falls_back_to_document():
    bot = AsyncMock()
    bot.send_video.side_effect = Exception("codec error")
    bot.send_document.return_value = MagicMock(message_id=99)
    result = await publish_video(
        bot, channel_chat_id=-100123, file_path="/tmp/test.mp4", caption="hello",
    )
    assert result == 99
    bot.send_document.assert_awaited_once()

@pytest.mark.asyncio
async def test_publish_video_both_fail():
    bot = AsyncMock()
    bot.send_video.side_effect = Exception("video error")
    bot.send_document.side_effect = Exception("doc error")
    result = await publish_video(
        bot, channel_chat_id=-100123, file_path="/tmp/test.mp4", caption="hello",
    )
    assert result is None

@pytest.mark.asyncio
async def test_publish_video_fallback_truncates_long_caption():
    bot = AsyncMock()
    bot.send_video.side_effect = Exception("codec error")
    bot.send_document.return_value = MagicMock(message_id=99)
    long_caption = "a" * 1024
    await publish_video(
        bot, channel_chat_id=-100123, file_path="/tmp/test.mp4", caption=long_caption,
    )
    call_kwargs = bot.send_document.call_args.kwargs
    assert len(call_kwargs["caption"]) <= 1024
