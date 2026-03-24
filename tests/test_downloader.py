import pytest
from bot.services.downloader import DownloadSlotManager

@pytest.mark.asyncio
async def test_acquire_and_release_slot():
    mgr = DownloadSlotManager()
    t1 = await mgr.try_acquire_slot(2)
    assert t1 is not None
    assert mgr.active_count == 1
    t2 = await mgr.try_acquire_slot(2)
    assert t2 is not None
    assert mgr.active_count == 2
    assert await mgr.try_acquire_slot(2) is None
    await mgr.release_slot(t1)
    assert mgr.active_count == 1
    assert await mgr.try_acquire_slot(2) is not None

@pytest.mark.asyncio
async def test_acquire_slot_max_one():
    mgr = DownloadSlotManager()
    assert await mgr.try_acquire_slot(1) is not None
    assert await mgr.try_acquire_slot(1) is None

@pytest.mark.asyncio
async def test_release_does_not_go_negative():
    mgr = DownloadSlotManager()
    await mgr.release_slot()
    assert mgr.active_count == 0
