import pytest
import aiosqlite
from bot.database.crud import (
    add_admin, remove_admin, list_admins, is_admin,
    add_channel, remove_channel, list_channels,
    get_setting, set_setting, get_all_settings,
    create_post_log, update_post_log_status,
)

@pytest.mark.asyncio
async def test_tables_created(db):
    """All four tables should exist after create_tables."""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in await cursor.fetchall()]
    assert "admins" in tables
    assert "channels" in tables
    assert "post_logs" in tables
    assert "settings" in tables

@pytest.mark.asyncio
async def test_default_settings_inserted(db):
    """Default settings should be pre-populated."""
    cursor = await db.execute("SELECT key, value FROM settings ORDER BY key")
    rows = {row[0]: row[1] for row in await cursor.fetchall()}
    assert rows["max_resolution"] == "1080"
    assert rows["max_file_size_mb"] == "2000"
    assert rows["max_concurrent_downloads"] == "2"

@pytest.mark.asyncio
async def test_admins_table_unique_constraint(db):
    """Inserting duplicate user_id should fail."""
    await db.execute(
        "INSERT INTO admins (user_id, username) VALUES (?, ?)", (123, "alice")
    )
    await db.commit()
    with pytest.raises(aiosqlite.IntegrityError):
        await db.execute(
            "INSERT INTO admins (user_id, username) VALUES (?, ?)", (123, "alice2")
        )
        await db.commit()

@pytest.mark.asyncio
async def test_channels_table_unique_constraint(db):
    """Inserting duplicate chat_id should fail."""
    await db.execute(
        "INSERT INTO channels (chat_id, title) VALUES (?, ?)", (-1001234, "Test")
    )
    await db.commit()
    with pytest.raises(aiosqlite.IntegrityError):
        await db.execute(
            "INSERT INTO channels (chat_id, title) VALUES (?, ?)", (-1001234, "Dupe")
        )
        await db.commit()

# --- Admin CRUD ---

@pytest.mark.asyncio
async def test_add_and_list_admins(db):
    await add_admin(db, user_id=111, username="alice")
    await add_admin(db, user_id=222, username="bob")
    admins = await list_admins(db)
    assert len(admins) == 2
    assert admins[0]["user_id"] == 111

@pytest.mark.asyncio
async def test_remove_admin(db):
    await add_admin(db, user_id=111, username="alice")
    removed = await remove_admin(db, user_id=111)
    assert removed is True
    admins = await list_admins(db)
    assert len(admins) == 0

@pytest.mark.asyncio
async def test_remove_nonexistent_admin(db):
    removed = await remove_admin(db, user_id=999)
    assert removed is False

@pytest.mark.asyncio
async def test_is_admin(db):
    assert await is_admin(db, user_id=111) is False
    await add_admin(db, user_id=111, username="alice")
    assert await is_admin(db, user_id=111) is True

# --- Channel CRUD ---

@pytest.mark.asyncio
async def test_add_and_list_channels(db):
    await add_channel(db, chat_id=-1001111, title="Channel A")
    await add_channel(db, chat_id=-1002222, title="Channel B")
    channels = await list_channels(db)
    assert len(channels) == 2

@pytest.mark.asyncio
async def test_remove_channel(db):
    await add_channel(db, chat_id=-1001111, title="Channel A")
    removed = await remove_channel(db, chat_id=-1001111)
    assert removed is True
    assert len(await list_channels(db)) == 0

# --- Settings ---

@pytest.mark.asyncio
async def test_get_setting_default(db):
    val = await get_setting(db, "max_resolution")
    assert val == "1080"

@pytest.mark.asyncio
async def test_set_setting_valid(db):
    await set_setting(db, "max_resolution", "720")
    val = await get_setting(db, "max_resolution")
    assert val == "720"

@pytest.mark.asyncio
async def test_set_setting_invalid_key(db):
    with pytest.raises(ValueError, match="Unknown setting"):
        await set_setting(db, "nonexistent_key", "value")

@pytest.mark.asyncio
async def test_set_setting_invalid_value(db):
    with pytest.raises(ValueError, match="must be one of"):
        await set_setting(db, "max_resolution", "999")

@pytest.mark.asyncio
async def test_set_max_file_size_invalid(db):
    with pytest.raises(ValueError):
        await set_setting(db, "max_file_size_mb", "3000")

@pytest.mark.asyncio
async def test_set_max_concurrent_downloads_invalid(db):
    with pytest.raises(ValueError):
        await set_setting(db, "max_concurrent_downloads", "10")

@pytest.mark.asyncio
async def test_get_all_settings(db):
    settings = await get_all_settings(db)
    assert "max_resolution" in settings
    assert "max_file_size_mb" in settings
    assert "max_concurrent_downloads" in settings

# --- Post Logs ---

@pytest.mark.asyncio
async def test_create_and_update_post_log(db):
    log_id = await create_post_log(
        db, admin_user_id=111, source_url="https://x.com/user/status/123",
        channel_chat_id=-1001111, caption="test caption",
    )
    assert log_id > 0
    await update_post_log_status(db, log_id, status="done", message_id=456)
    cursor = await db.execute("SELECT * FROM post_logs WHERE id = ?", (log_id,))
    row = await cursor.fetchone()
    assert row["status"] == "done"
    assert row["message_id"] == 456

@pytest.mark.asyncio
async def test_update_post_log_failed(db):
    log_id = await create_post_log(
        db, admin_user_id=111, source_url="https://x.com/user/status/123",
        channel_chat_id=-1001111, caption="test",
    )
    await update_post_log_status(db, log_id, status="failed", error_message="Download timeout")
    cursor = await db.execute("SELECT * FROM post_logs WHERE id = ?", (log_id,))
    row = await cursor.fetchone()
    assert row["status"] == "failed"
    assert row["error_message"] == "Download timeout"
