import aiosqlite

_db: aiosqlite.Connection | None = None


async def init_db(db_path: str = "data/bot.db") -> None:
    global _db
    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row


async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
