import pytest
from bot.services.downloader import DownloadSlotManager

@pytest.mark.asyncio
async def test_acquire_and_release_slot():
    mgr = DownloadSlotManager()
    assert await mgr.try_acquire_slot(2) is True
    assert mgr.active_count == 1
    assert await mgr.try_acquire_slot(2) is True
    assert mgr.active_count == 2
    assert await mgr.try_acquire_slot(2) is False
    await mgr.release_slot()
    assert mgr.active_count == 1
    assert await mgr.try_acquire_slot(2) is True

@pytest.mark.asyncio
async def test_acquire_slot_max_one():
    mgr = DownloadSlotManager()
    assert await mgr.try_acquire_slot(1) is True
    assert await mgr.try_acquire_slot(1) is False

@pytest.mark.asyncio
async def test_release_does_not_go_negative():
    mgr = DownloadSlotManager()
    await mgr.release_slot()
    assert mgr.active_count == 0
