import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.pipeline import download_and_publish
from bot.services.downloader import DownloadSlotManager


async def _make_get_setting(overrides=None):
    defaults = {"max_concurrent_downloads": "1", "max_file_size_mb": "2000", "max_resolution": "1080"}
    if overrides:
        defaults.update(overrides)
    async def _get_setting(db, key):
        return defaults.get(key)
    return _get_setting


@pytest.mark.asyncio
async def test_pipeline_rejects_when_no_slot():
    slot_mgr = DownloadSlotManager()
    await slot_mgr.try_acquire_slot(1)
    bot = AsyncMock()
    get_setting_fn = await _make_get_setting()
    with patch("bot.services.pipeline.get_db", new_callable=AsyncMock), \
         patch("bot.services.pipeline.get_setting", side_effect=get_setting_fn), \
         patch("bot.services.pipeline.check_disk_space", return_value=(True, 5000)):
        await download_and_publish(
            bot=bot, slot_manager=slot_mgr, user_chat_id=111, user_id=111,
            source_url="https://x.com/u/status/1", caption="test", channel_chat_id=-100123,
        )
    bot.send_message.assert_awaited_once()
    assert "busy" in str(bot.send_message.call_args).lower()


@pytest.mark.asyncio
async def test_pipeline_rejects_when_no_disk_space():
    slot_mgr = DownloadSlotManager()
    bot = AsyncMock()
    get_setting_fn = await _make_get_setting()
    with patch("bot.services.pipeline.get_db", new_callable=AsyncMock), \
         patch("bot.services.pipeline.get_setting", side_effect=get_setting_fn), \
         patch("bot.services.pipeline.check_disk_space", return_value=(False, 100)):
        await download_and_publish(
            bot=bot, slot_manager=slot_mgr, user_chat_id=111, user_id=111,
            source_url="https://x.com/u/status/1", caption="test", channel_chat_id=-100123,
        )
    assert "disk" in str(bot.send_message.call_args).lower()
    assert slot_mgr.active_count == 0


@pytest.mark.asyncio
async def test_pipeline_rejects_oversized_file():
    slot_mgr = DownloadSlotManager()
    bot = AsyncMock()
    get_setting_fn = await _make_get_setting({"max_file_size_mb": "50"})
    mock_result = {
        "file_path": "/tmp/test.mp4", "tmp_dir": "/tmp/testdir",
        "duration": 10, "width": 1920, "height": 1080, "file_size_mb": 100.0,
    }
    with patch("bot.services.pipeline.get_db", new_callable=AsyncMock), \
         patch("bot.services.pipeline.get_setting", side_effect=get_setting_fn), \
         patch("bot.services.pipeline.check_disk_space", return_value=(True, 5000)), \
         patch("bot.services.pipeline.create_post_log", new_callable=AsyncMock, return_value=1), \
         patch("bot.services.pipeline.update_post_log_status", new_callable=AsyncMock), \
         patch("bot.services.pipeline.download_video", new_callable=AsyncMock, return_value=mock_result), \
         patch("shutil.rmtree"):
        await download_and_publish(
            bot=bot, slot_manager=slot_mgr, user_chat_id=111, user_id=111,
            source_url="https://x.com/u/status/1", caption="test", channel_chat_id=-100123,
        )
    assert "too large" in str(bot.send_message.call_args).lower()


@pytest.mark.asyncio
async def test_pipeline_success_path():
    slot_mgr = DownloadSlotManager()
    bot = AsyncMock()
    get_setting_fn = await _make_get_setting()
    mock_result = {
        "file_path": "/tmp/test.mp4", "tmp_dir": "/tmp/testdir",
        "duration": 10, "width": 1920, "height": 1080, "file_size_mb": 25.0,
    }
    with patch("bot.services.pipeline.get_db", new_callable=AsyncMock), \
         patch("bot.services.pipeline.get_setting", side_effect=get_setting_fn), \
         patch("bot.services.pipeline.check_disk_space", return_value=(True, 5000)), \
         patch("bot.services.pipeline.create_post_log", new_callable=AsyncMock, return_value=1), \
         patch("bot.services.pipeline.update_post_log_status", new_callable=AsyncMock), \
         patch("bot.services.pipeline.download_video", new_callable=AsyncMock, return_value=mock_result), \
         patch("bot.services.pipeline.publish_video", new_callable=AsyncMock, return_value=999), \
         patch("shutil.rmtree"):
        await download_and_publish(
            bot=bot, slot_manager=slot_mgr, user_chat_id=111, user_id=111,
            source_url="https://x.com/u/status/1", caption="test", channel_chat_id=-100123,
        )
    assert "success" in str(bot.send_message.call_args).lower()
    assert slot_mgr.active_count == 0


@pytest.mark.asyncio
async def test_pipeline_download_failure():
    slot_mgr = DownloadSlotManager()
    bot = AsyncMock()
    get_setting_fn = await _make_get_setting()
    with patch("bot.services.pipeline.get_db", new_callable=AsyncMock), \
         patch("bot.services.pipeline.get_setting", side_effect=get_setting_fn), \
         patch("bot.services.pipeline.check_disk_space", return_value=(True, 5000)), \
         patch("bot.services.pipeline.create_post_log", new_callable=AsyncMock, return_value=1), \
         patch("bot.services.pipeline.update_post_log_status", new_callable=AsyncMock), \
         patch("bot.services.pipeline.download_video", new_callable=AsyncMock, side_effect=RuntimeError("yt-dlp error")):
        await download_and_publish(
            bot=bot, slot_manager=slot_mgr, user_chat_id=111, user_id=111,
            source_url="https://x.com/u/status/1", caption="test", channel_chat_id=-100123,
        )
    assert "failed" in str(bot.send_message.call_args).lower()
    assert slot_mgr.active_count == 0
