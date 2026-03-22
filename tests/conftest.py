import os
import pytest

# Set required env vars before any bot modules are imported
os.environ.setdefault("BOT_TOKEN", "test_token")
os.environ.setdefault("SUPER_ADMIN_ID", "0")

from bot.database.connection import get_db, init_db, close_db
from bot.database.models import create_tables

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture
async def db():
    """Use in-memory SQLite for tests."""
    await init_db(":memory:")
    db_conn = await get_db()
    await create_tables(db_conn)
    yield db_conn
    await close_db()
