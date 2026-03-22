import pytest
import aiosqlite

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
