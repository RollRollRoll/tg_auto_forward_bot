# Telegram X Video Forward Bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram Bot that receives X (Twitter) video links from authorized admins in private chat, downloads videos with yt-dlp, and publishes them with user-provided HTML captions to configurable Telegram Channels via a Local Bot API Server.

**Architecture:** Two-phase execution model — Phase 1: ConversationHandler collects link, caption, channel selection then returns END immediately. Phase 2: background `asyncio.Task` handles download, post-processing, and publishing concurrently. SQLite via aiosqlite stores admin whitelist, channels, settings, and post logs. `DownloadSlotManager` (counter + asyncio.Lock) caps concurrent downloads.

**Tech Stack:** Python 3.11+, python-telegram-bot v20+, yt-dlp (Python API), aiosqlite, python-dotenv, ffmpeg (system), Telegram Local Bot API Server (Docker)

**Spec:** `docs/superpowers/specs/2026-03-22-tg-x-video-bot-design.md`

---

## File Map

| File | Responsibility |
|------|---------------|
| `bot/__init__.py` | Package marker |
| `bot/main.py` | Entry point: load config, init DB, build Application with local_mode, register handlers, startup checks (getMe), stale file cleanup, run polling |
| `bot/config.py` | Load env vars (BOT_TOKEN, API_BASE_URL, SUPER_ADMIN_ID), expose as module-level constants |
| `bot/database/__init__.py` | Package marker |
| `bot/database/connection.py` | Singleton aiosqlite connection manager (init, get, close) |
| `bot/database/models.py` | CREATE TABLE statements for admins, channels, settings, post_logs; init_db() function with default settings |
| `bot/database/crud.py` | All DB queries: admin CRUD, channel CRUD, settings get/set with validation, post_log insert/update |
| `bot/handlers/__init__.py` | Package marker |
| `bot/handlers/filters.py` | Shared filters: private_chat_only, admin_only, super_admin_only |
| `bot/handlers/start.py` | /start, /help, /cancel command handlers |
| `bot/handlers/admin.py` | Admin command handlers: add/remove/list admins, add/remove/list channels, set/get/settings |
| `bot/handlers/conversation.py` | ConversationHandler: entry (URL detection), WAITING_CAPTION, WAITING_CHANNEL states; spawns background task on completion |
| `bot/services/__init__.py` | Package marker |
| `bot/services/downloader.py` | DownloadSlotManager class; download_video() with yt-dlp, disk check, codec-preferring format string, faststart post-processing |
| `bot/services/publisher.py` | publish_video(): send_video with supports_streaming, fallback to send_document; post_log updates |
| `bot/services/pipeline.py` | download_and_publish() orchestrator: slot acquire, download, post-process, publish, notify user, cleanup in finally |
| `bot/utils/__init__.py` | Package marker |
| `bot/utils/validators.py` | URL regex validation, t.co resolver (HTTP HEAD), caption HTML sanitization + length check |
| `tests/__init__.py` | Package marker |
| `tests/conftest.py` | Shared fixtures (db fixture, pytest-asyncio config) |
| `tests/test_validators.py` | Tests for URL validation, t.co resolution, caption sanitization |
| `tests/test_database.py` | Tests for all CRUD operations, settings validation, default init |
| `tests/test_downloader.py` | Tests for DownloadSlotManager, disk check logic |
| `tests/test_filters.py` | Tests for private_chat_only, admin_only, super_admin_only filters |
| `tests/test_publisher.py` | Tests for publish_video with send_video/send_document fallback |
| `tests/test_conversation.py` | Tests for ConversationHandler states and transitions |
| `tests/test_pipeline.py` | Integration tests for download_and_publish orchestrator (5 scenarios) |
| `.env.example` | Template with all env vars |
| `requirements.txt` | Python dependencies |
| `requirements-dev.txt` | Dev dependencies (pytest, pytest-asyncio) |
| `Dockerfile` | Bot container image |
| `docker-compose.yml` | Bot + Local Bot API Server orchestration |

---

## Task 1: Project Scaffolding and Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `bot/__init__.py`
- Create: `bot/config.py`
- Create: `tests/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: Update .gitignore for Python project**

Replace the current AL-template .gitignore with Python-appropriate entries:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/

# Virtual environment
venv/
.venv/

# Environment
.env

# IDE
.vscode/
.idea/

# Testing
.pytest_cache/
htmlcov/
.coverage

# Database
*.db

# Downloads temp
downloads/

# OS
.DS_Store

# Serena
.serena/
```

- [ ] **Step 2: Create requirements.txt**

```
python-telegram-bot[ext]>=20.0
yt-dlp
aiosqlite
python-dotenv
httpx
```

- [ ] **Step 3: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=7.0
pytest-asyncio>=0.21
```

- [ ] **Step 4: Create .env.example**

```bash
# Telegram Bot Token (from @BotFather)
BOT_TOKEN=

# Local Bot API Server URL
API_BASE_URL=http://localhost:8081

# Super admin Telegram User ID
SUPER_ADMIN_ID=

# Telegram API credentials (for Local Bot API Server)
API_ID=
API_HASH=
```

- [ ] **Step 5: Create bot/__init__.py**

```python
```

(Empty file — package marker only)

- [ ] **Step 6: Create bot/config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
API_BASE_URL: str = os.environ.get("API_BASE_URL", "http://localhost:8081")
SUPER_ADMIN_ID: int = int(os.environ["SUPER_ADMIN_ID"])

# Download directory — must be on the shared volume with Local Bot API Server
# In Docker: /var/lib/telegram-bot-api/downloads/
# In direct run: configurable, defaults to ./downloads/
DOWNLOAD_DIR: str = os.environ.get(
    "DOWNLOAD_DIR", "/var/lib/telegram-bot-api/downloads"
)
```

- [ ] **Step 7: Create tests/__init__.py**

```python
```

- [ ] **Step 8: Install dependencies and verify**

Run: `cd /Users/chenjinfan/Project/tg_auto_forward_bot && python3 -m venv venv && source venv/bin/activate && pip install -r requirements-dev.txt`
Expected: All packages install successfully.

- [ ] **Step 9: Commit**

```bash
git add .gitignore requirements.txt requirements-dev.txt .env.example bot/__init__.py bot/config.py tests/__init__.py
git commit -m "feat: project scaffolding with dependencies and config"
```

---

## Task 2: Database Layer — Connection and Models

**Files:**
- Create: `bot/database/__init__.py`
- Create: `bot/database/connection.py`
- Create: `bot/database/models.py`
- Create: `tests/test_database.py`

- [ ] **Step 1: Create bot/database/__init__.py**

```python
```

- [ ] **Step 2: Create tests/conftest.py with shared fixtures**

Create `tests/conftest.py`:

```python
import pytest
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
```

- [ ] **Step 3: Write failing tests for database init and schema**

Create `tests/test_database.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /Users/chenjinfan/Project/tg_auto_forward_bot && python -m pytest tests/test_database.py -v`
Expected: FAIL — modules not found.

- [ ] **Step 5: Implement bot/database/connection.py**

```python
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
```

- [ ] **Step 6: Implement bot/database/models.py**

```python
import aiosqlite

_DEFAULT_SETTINGS = {
    "max_resolution": "1080",
    "max_file_size_mb": "2000",
    "max_concurrent_downloads": "2",
}


async def create_tables(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id BIGINT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS post_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_user_id BIGINT NOT NULL,
            source_url TEXT NOT NULL,
            channel_chat_id BIGINT NOT NULL,
            message_id INTEGER,
            caption TEXT,
            status TEXT NOT NULL DEFAULT 'downloading',
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Insert default settings (skip if already exist)
    for key, value in _DEFAULT_SETTINGS.items():
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
    await db.commit()
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_database.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add bot/database/ tests/conftest.py tests/test_database.py
git commit -m "feat: database connection manager and schema with defaults"
```

---

## Task 3: Database Layer — CRUD Operations

**Files:**
- Create: `bot/database/crud.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Write failing tests for CRUD operations**

Append to `tests/test_database.py`:

```python
from bot.database.crud import (
    add_admin, remove_admin, list_admins, is_admin,
    add_channel, remove_channel, list_channels,
    get_setting, set_setting, get_all_settings,
    create_post_log, update_post_log_status,
)

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
        db,
        admin_user_id=111,
        source_url="https://x.com/user/status/123",
        channel_chat_id=-1001111,
        caption="test caption",
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
        db, admin_user_id=111,
        source_url="https://x.com/user/status/123",
        channel_chat_id=-1001111, caption="test",
    )
    await update_post_log_status(
        db, log_id, status="failed", error_message="Download timeout"
    )
    cursor = await db.execute("SELECT * FROM post_logs WHERE id = ?", (log_id,))
    row = await cursor.fetchone()
    assert row["status"] == "failed"
    assert row["error_message"] == "Download timeout"
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `python -m pytest tests/test_database.py -v`
Expected: New tests FAIL — crud module not found.

- [ ] **Step 3: Implement bot/database/crud.py**

```python
from __future__ import annotations
import aiosqlite

# --- Settings validation ---

_SETTINGS_VALIDATORS = {
    "max_resolution": {
        "type": "enum",
        "values": ["360", "480", "720", "1080", "1440", "2160"],
    },
    "max_file_size_mb": {"type": "int_range", "min": 1, "max": 2000},
    "max_concurrent_downloads": {"type": "int_range", "min": 1, "max": 5},
}


def _validate_setting(key: str, value: str) -> None:
    if key not in _SETTINGS_VALIDATORS:
        raise ValueError(f"Unknown setting: '{key}'")
    spec = _SETTINGS_VALIDATORS[key]
    if spec["type"] == "enum":
        if value not in spec["values"]:
            raise ValueError(
                f"'{key}' must be one of: {', '.join(spec['values'])}"
            )
    elif spec["type"] == "int_range":
        try:
            v = int(value)
        except ValueError:
            raise ValueError(f"'{key}' must be an integer") from None
        if not (spec["min"] <= v <= spec["max"]):
            raise ValueError(
                f"'{key}' must be between {spec['min']} and {spec['max']}"
            )


# --- Admin CRUD ---

async def add_admin(
    db: aiosqlite.Connection, *, user_id: int, username: str | None = None
) -> None:
    await db.execute(
        "INSERT INTO admins (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )
    await db.commit()


async def remove_admin(db: aiosqlite.Connection, *, user_id: int) -> bool:
    cursor = await db.execute(
        "DELETE FROM admins WHERE user_id = ?", (user_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def list_admins(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        "SELECT user_id, username, created_at FROM admins ORDER BY created_at"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def is_admin(db: aiosqlite.Connection, *, user_id: int) -> bool:
    cursor = await db.execute(
        "SELECT 1 FROM admins WHERE user_id = ?", (user_id,)
    )
    return await cursor.fetchone() is not None


# --- Channel CRUD ---

async def add_channel(
    db: aiosqlite.Connection, *, chat_id: int, title: str
) -> None:
    await db.execute(
        "INSERT INTO channels (chat_id, title) VALUES (?, ?)",
        (chat_id, title),
    )
    await db.commit()


async def remove_channel(db: aiosqlite.Connection, *, chat_id: int) -> bool:
    cursor = await db.execute(
        "DELETE FROM channels WHERE chat_id = ?", (chat_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def list_channels(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        "SELECT chat_id, title, created_at FROM channels ORDER BY created_at"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# --- Settings ---

async def get_setting(db: aiosqlite.Connection, key: str) -> str | None:
    cursor = await db.execute(
        "SELECT value FROM settings WHERE key = ?", (key,)
    )
    row = await cursor.fetchone()
    return row["value"] if row else None


async def set_setting(
    db: aiosqlite.Connection, key: str, value: str
) -> None:
    _validate_setting(key, value)
    await db.execute(
        "UPDATE settings SET value = ? WHERE key = ?", (value, key)
    )
    await db.commit()


async def get_all_settings(db: aiosqlite.Connection) -> dict[str, str]:
    cursor = await db.execute("SELECT key, value FROM settings")
    rows = await cursor.fetchall()
    return {row["key"]: row["value"] for row in rows}


# --- Post Logs ---

async def create_post_log(
    db: aiosqlite.Connection,
    *,
    admin_user_id: int,
    source_url: str,
    channel_chat_id: int,
    caption: str,
) -> int:
    cursor = await db.execute(
        """INSERT INTO post_logs
           (admin_user_id, source_url, channel_chat_id, caption, status)
           VALUES (?, ?, ?, ?, 'downloading')""",
        (admin_user_id, source_url, channel_chat_id, caption),
    )
    await db.commit()
    return cursor.lastrowid


async def update_post_log_status(
    db: aiosqlite.Connection,
    log_id: int,
    *,
    status: str,
    message_id: int | None = None,
    error_message: str | None = None,
) -> None:
    await db.execute(
        """UPDATE post_logs
           SET status = ?, message_id = ?, error_message = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (status, message_id, error_message, log_id),
    )
    await db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_database.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/database/crud.py tests/test_database.py
git commit -m "feat: CRUD operations with settings validation"
```

---

## Task 4: URL Validation and Caption Sanitization

**Files:**
- Create: `bot/utils/__init__.py`
- Create: `bot/utils/validators.py`
- Create: `tests/test_validators.py`

- [ ] **Step 1: Create bot/utils/__init__.py**

```python
```

- [ ] **Step 2: Write failing tests for URL validation**

Create `tests/test_validators.py`:

```python
import pytest
from bot.utils.validators import is_x_video_url, sanitize_caption

# --- URL validation ---

class TestIsXVideoUrl:
    def test_x_com_status_url(self):
        assert is_x_video_url("https://x.com/user/status/1234567890") is True

    def test_twitter_com_status_url(self):
        assert is_x_video_url("https://twitter.com/user/status/1234567890") is True

    def test_x_com_with_query_params(self):
        assert is_x_video_url("https://x.com/user/status/123?s=20") is True

    def test_t_co_short_link(self):
        assert is_x_video_url("https://t.co/abc123") is True

    def test_invalid_url(self):
        assert is_x_video_url("https://youtube.com/watch?v=abc") is False

    def test_plain_text(self):
        assert is_x_video_url("hello world") is False

    def test_empty_string(self):
        assert is_x_video_url("") is False

    def test_x_com_without_status(self):
        assert is_x_video_url("https://x.com/user") is False

# --- Caption sanitization ---

class TestSanitizeCaption:
    def test_allowed_tags_preserved(self):
        html = "<b>bold</b> <i>italic</i> <u>underline</u>"
        result, error = sanitize_caption(html)
        assert "<b>bold</b>" in result
        assert "<i>italic</i>" in result
        assert error is None

    def test_disallowed_tags_stripped(self):
        html = "<div>text</div><script>alert(1)</script>"
        result, error = sanitize_caption(html)
        assert "<div>" not in result
        assert "<script>" not in result
        assert "text" in result
        assert error is None

    def test_bare_ampersand_escaped(self):
        html = "A & B"
        result, error = sanitize_caption(html)
        assert "&amp;" in result
        assert error is None

    def test_bare_angle_brackets_escaped(self):
        html = "1 < 2 > 0"
        result, error = sanitize_caption(html)
        assert "&lt;" in result
        assert "&gt;" in result
        assert error is None

    def test_a_tag_with_href_preserved(self):
        html = '<a href="https://example.com">link</a>'
        result, error = sanitize_caption(html)
        assert 'href="https://example.com"' in result
        assert error is None

    def test_caption_at_limit(self):
        text = "a" * 1024
        result, error = sanitize_caption(text)
        assert error is None

    def test_caption_over_limit(self):
        text = "a" * 1025
        result, error = sanitize_caption(text)
        assert error is not None
        assert "1025" in error
        assert "1024" in error

    def test_tags_not_counted_in_length(self):
        # 10 chars of text + tags should be fine
        html = "<b>" + "a" * 1024 + "</b>"
        result, error = sanitize_caption(html)
        assert error is None

    def test_code_and_pre_preserved(self):
        html = "<code>x=1</code> <pre>block</pre>"
        result, error = sanitize_caption(html)
        assert "<code>x=1</code>" in result
        assert "<pre>block</pre>" in result
        assert error is None

    def test_s_tag_preserved(self):
        html = "<s>strikethrough</s>"
        result, error = sanitize_caption(html)
        assert "<s>strikethrough</s>" in result
        assert error is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_validators.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement bot/utils/validators.py**

```python
from __future__ import annotations
import re
from html.parser import HTMLParser
from io import StringIO

# --- URL validation ---

_X_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/\w+/status/\d+",
    re.IGNORECASE,
)
_TCO_PATTERN = re.compile(r"https?://t\.co/\w+", re.IGNORECASE)


def is_x_video_url(text: str) -> bool:
    if not text:
        return False
    return bool(_X_URL_PATTERN.search(text) or _TCO_PATTERN.search(text))


def extract_url(text: str) -> str | None:
    m = _X_URL_PATTERN.search(text) or _TCO_PATTERN.search(text)
    return m.group(0) if m else None


async def resolve_t_co(url: str) -> str:
    """Resolve t.co short link to full URL via HTTP HEAD redirect."""
    import httpx

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.head(url)
        return str(resp.url)


# --- Caption sanitization ---

_ALLOWED_TAGS = {"b", "i", "u", "s", "a", "code", "pre"}
_ALLOWED_ATTRS = {"a": {"href"}}

# Matches < that is NOT part of a valid HTML tag opening/closing
# (i.e., < not followed by a known tag name or /)
_BARE_LT = re.compile(
    r"<(?!/?\s*(?:" + "|".join(_ALLOWED_TAGS) + r")[\s>/])",
    re.IGNORECASE,
)


def _pre_escape_bare_angles(text: str) -> str:
    """Escape < and > that are NOT part of allowed HTML tags.

    This prevents HTMLParser from misinterpreting bare angle brackets
    like '1 < 2 > 0' as malformed tags.
    """
    # First, escape bare < that don't start a known tag
    result = _BARE_LT.sub("&lt;", text)
    # Then escape orphan > that aren't closing a known tag
    # (simple heuristic: > not preceded by a tag name or closing quote)
    result = re.sub(r"(?<![\"'\w/])>", "&gt;", result)
    return result


class _HTMLSanitizer(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = StringIO()
        self.plain_text = StringIO()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag in _ALLOWED_TAGS:
            allowed = _ALLOWED_ATTRS.get(tag, set())
            attr_str = ""
            for name, value in attrs:
                if name in allowed and value is not None:
                    safe_val = value.replace('"', "&quot;")
                    attr_str += f' {name}="{safe_val}"'
            self.result.write(f"<{tag}{attr_str}>")

    def handle_endtag(self, tag: str):
        if tag in _ALLOWED_TAGS:
            self.result.write(f"</{tag}>")

    def handle_data(self, data: str):
        escaped = (
            data.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        self.result.write(escaped)
        self.plain_text.write(data)

    def handle_entityref(self, name: str):
        self.result.write(f"&{name};")
        self.plain_text.write(f"&{name};")  # count as 1 visual char would be better, but safe to overcount

    def handle_charref(self, name: str):
        self.result.write(f"&#{name};")


def sanitize_caption(html: str) -> tuple[str, str | None]:
    """Sanitize HTML caption for Telegram.

    Returns:
        (sanitized_html, error_message)
        error_message is None if valid, otherwise a user-facing error string.
    """
    # Pre-escape bare angle brackets before parsing
    preprocessed = _pre_escape_bare_angles(html)
    sanitizer = _HTMLSanitizer()
    sanitizer.feed(preprocessed)
    result = sanitizer.result.getvalue()
    plain_len = len(sanitizer.plain_text.getvalue())

    if plain_len > 1024:
        return result, f"Caption too long ({plain_len}/1024 chars). Please shorten and resend."

    return result, None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_validators.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bot/utils/ tests/test_validators.py
git commit -m "feat: URL validation and caption HTML sanitization"
```

---

## Task 5: Handler Filters (Private Chat, Admin, Super Admin)

**Files:**
- Create: `bot/handlers/__init__.py`
- Create: `bot/handlers/filters.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Create bot/handlers/__init__.py**

```python
```

- [ ] **Step 2: Write failing tests for filters**

Create `tests/test_filters.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Chat, Message
from telegram.constants import ChatType

from bot.handlers.filters import private_chat_only, admin_only, super_admin_only


def _make_update(chat_type: str = ChatType.PRIVATE, user_id: int = 111) -> Update:
    """Create a minimal mock Update."""
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
    update = _make_update(chat_type=ChatType.PRIVATE)
    context = MagicMock()
    result = await wrapped(update, context)
    assert result == "ok"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_private_chat_only_blocks_group():
    handler = AsyncMock(return_value="ok")
    wrapped = private_chat_only(handler)
    update = _make_update(chat_type=ChatType.GROUP)
    context = MagicMock()
    result = await wrapped(update, context)
    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_only_allows_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = admin_only(handler)
    update = _make_update(user_id=111)
    context = MagicMock()

    with patch("bot.handlers.filters.is_admin", return_value=True) as mock_is_admin, \
         patch("bot.handlers.filters.get_db") as mock_get_db:
        mock_get_db.return_value = MagicMock()
        result = await wrapped(update, context)

    assert result == "ok"


@pytest.mark.asyncio
async def test_admin_only_blocks_non_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = admin_only(handler)
    update = _make_update(user_id=999)
    context = MagicMock()

    with patch("bot.handlers.filters.is_admin", return_value=False) as mock_is_admin, \
         patch("bot.handlers.filters.get_db") as mock_get_db, \
         patch("bot.handlers.filters.SUPER_ADMIN_ID", 0):
        mock_get_db.return_value = MagicMock()
        result = await wrapped(update, context)

    assert result is None


@pytest.mark.asyncio
async def test_admin_only_allows_super_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = admin_only(handler)
    update = _make_update(user_id=42)
    context = MagicMock()

    with patch("bot.handlers.filters.is_admin", return_value=False), \
         patch("bot.handlers.filters.get_db") as mock_get_db, \
         patch("bot.handlers.filters.SUPER_ADMIN_ID", 42):
        mock_get_db.return_value = MagicMock()
        result = await wrapped(update, context)

    assert result == "ok"


@pytest.mark.asyncio
async def test_super_admin_only_allows_super_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = super_admin_only(handler)
    update = _make_update(user_id=42)
    context = MagicMock()

    with patch("bot.handlers.filters.SUPER_ADMIN_ID", 42):
        result = await wrapped(update, context)

    assert result == "ok"


@pytest.mark.asyncio
async def test_super_admin_only_blocks_regular_admin():
    handler = AsyncMock(return_value="ok")
    wrapped = super_admin_only(handler)
    update = _make_update(user_id=111)
    context = MagicMock()

    with patch("bot.handlers.filters.SUPER_ADMIN_ID", 42):
        result = await wrapped(update, context)

    assert result is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_filters.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement bot/handlers/filters.py**

```python
from __future__ import annotations
import functools
from typing import Callable, Any

from telegram import Update
from telegram.constants import ChatType

from bot.config import SUPER_ADMIN_ID
from bot.database.connection import get_db
from bot.database.crud import is_admin


def private_chat_only(func: Callable) -> Callable:
    """Decorator: silently ignore non-private-chat messages."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: Any, *args, **kwargs):
        if update.effective_chat and update.effective_chat.type != ChatType.PRIVATE:
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper


def admin_only(func: Callable) -> Callable:
    """Decorator: only allow admins and super admin."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: Any, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id == SUPER_ADMIN_ID:
            return await func(update, context, *args, **kwargs)
        db = await get_db()
        if await is_admin(db, user_id=user_id):
            return await func(update, context, *args, **kwargs)
        return None
    return wrapper


def super_admin_only(func: Callable) -> Callable:
    """Decorator: only allow super admin."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: Any, *args, **kwargs):
        if update.effective_user.id != SUPER_ADMIN_ID:
            return None
        return await func(update, context, *args, **kwargs)
    return wrapper
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_filters.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bot/handlers/__init__.py bot/handlers/filters.py tests/test_filters.py
git commit -m "feat: private_chat_only, admin_only, super_admin_only filters"
```

---

## Task 6: Download Slot Manager and Disk Check

**Files:**
- Create: `bot/services/__init__.py`
- Create: `bot/services/downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: Create bot/services/__init__.py**

```python
```

- [ ] **Step 2: Write failing tests for DownloadSlotManager**

Create `tests/test_downloader.py`:

```python
import pytest
from bot.services.downloader import DownloadSlotManager

@pytest.mark.asyncio
async def test_acquire_and_release_slot():
    mgr = DownloadSlotManager()
    assert await mgr.try_acquire_slot(2) is True
    assert mgr.active_count == 1
    assert await mgr.try_acquire_slot(2) is True
    assert mgr.active_count == 2
    assert await mgr.try_acquire_slot(2) is False  # full
    await mgr.release_slot()
    assert mgr.active_count == 1
    assert await mgr.try_acquire_slot(2) is True  # slot freed

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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_downloader.py -v`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement DownloadSlotManager in bot/services/downloader.py**

```python
from __future__ import annotations
import asyncio
import os
import shutil
import tempfile
import time
from pathlib import Path

import yt_dlp

from bot.config import DOWNLOAD_DIR


class DownloadSlotManager:
    def __init__(self):
        self._active_downloads: int = 0
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return self._active_downloads

    async def try_acquire_slot(self, max_slots: int) -> bool:
        async with self._lock:
            if self._active_downloads >= max_slots:
                return False
            self._active_downloads += 1
            return True

    async def release_slot(self) -> None:
        async with self._lock:
            self._active_downloads = max(0, self._active_downloads - 1)


def check_disk_space(
    max_concurrent: int, max_file_size_mb: int
) -> tuple[bool, int]:
    """Check if enough disk space is available.

    Returns:
        (has_space, free_mb)
    """
    usage = shutil.disk_usage(DOWNLOAD_DIR)
    free_mb = usage.free // (1024 * 1024)
    required_mb = max_concurrent * max_file_size_mb * 2
    return free_mb >= required_mb, free_mb


def cleanup_stale_files(max_age_seconds: int = 3600) -> int:
    """Remove stale files and temp directories from DOWNLOAD_DIR.

    Returns: number of items removed.
    """
    download_path = Path(DOWNLOAD_DIR)
    if not download_path.exists():
        return 0
    removed = 0
    now = time.time()
    for item in download_path.iterdir():
        if (now - item.stat().st_mtime) > max_age_seconds:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            removed += 1
    return removed


async def download_video(
    url: str, *, max_resolution: int = 1080
) -> dict:
    """Download video from X/Twitter URL using yt-dlp.

    Returns dict with keys: file_path, duration, width, height, title
    Raises RuntimeError on failure.
    """
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(dir=DOWNLOAD_DIR)

    ydl_opts = {
        "format": (
            f"best[vcodec^=avc][acodec^=mp4a][height<={max_resolution}]"
            f"/bestvideo[vcodec^=avc][height<={max_resolution}]+bestaudio[acodec^=mp4a]"
            f"/bestvideo[vcodec^=avc][height<={max_resolution}]+bestaudio"
            f"/best[height<={max_resolution}]"
            f"/bestvideo[height<={max_resolution}]+bestaudio"
            f"/best"
        ),
        "outtmpl": os.path.join(tmp_dir, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}
        ],
        "postprocessor_args": {
            "ffmpeg": ["-movflags", "+faststart"],
        },
        "quiet": True,
        "no_warnings": True,
    }

    loop = asyncio.get_running_loop()
    try:
        info = await loop.run_in_executor(None, _do_download, ydl_opts, url)
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Download failed: {e}") from e

    # Find the downloaded file
    files = list(Path(tmp_dir).glob("*"))
    if not files:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError("Download produced no files")

    file_path = files[0]
    return {
        "file_path": str(file_path),
        "tmp_dir": tmp_dir,
        "duration": info.get("duration"),
        "width": info.get("width"),
        "height": info.get("height"),
        "title": info.get("title", ""),
        "file_size_mb": file_path.stat().st_size / (1024 * 1024),
    }


def _do_download(ydl_opts: dict, url: str) -> dict:
    """Synchronous download — runs in executor."""
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info or {}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_downloader.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add bot/services/__init__.py bot/services/downloader.py tests/test_downloader.py
git commit -m "feat: DownloadSlotManager and yt-dlp download service"
```

---

## Task 7: Publisher Service

**Files:**
- Create: `bot/services/publisher.py`
- Create: `tests/test_publisher.py`

- [ ] **Step 1: Write failing tests for publisher**

Create `tests/test_publisher.py`:

```python
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
    call_kwargs = bot.send_video.call_args.kwargs
    assert call_kwargs["supports_streaming"] is True


@pytest.mark.asyncio
async def test_publish_video_falls_back_to_document():
    bot = AsyncMock()
    bot.send_video.side_effect = Exception("codec error")
    bot.send_document.return_value = MagicMock(message_id=99)

    result = await publish_video(
        bot, channel_chat_id=-100123, file_path="/tmp/test.mp4",
        caption="hello",
    )
    assert result == 99
    bot.send_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_video_both_fail():
    bot = AsyncMock()
    bot.send_video.side_effect = Exception("video error")
    bot.send_document.side_effect = Exception("doc error")

    result = await publish_video(
        bot, channel_chat_id=-100123, file_path="/tmp/test.mp4",
        caption="hello",
    )
    assert result is None


@pytest.mark.asyncio
async def test_publish_video_fallback_truncates_long_caption():
    """Fallback caption suffix must not exceed 1024 chars total."""
    bot = AsyncMock()
    bot.send_video.side_effect = Exception("codec error")
    bot.send_document.return_value = MagicMock(message_id=99)

    long_caption = "a" * 1024
    await publish_video(
        bot, channel_chat_id=-100123, file_path="/tmp/test.mp4",
        caption=long_caption,
    )
    call_kwargs = bot.send_document.call_args.kwargs
    # Caption should be truncated to fit within 1024
    assert len(call_kwargs["caption"]) <= 1024
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_publisher.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement bot/services/publisher.py**

```python
from __future__ import annotations
import logging
from pathlib import Path

from telegram import Bot

logger = logging.getLogger(__name__)

_FALLBACK_SUFFIX = "\n\n<i>(Sent as file — non-streamable format)</i>"


async def publish_video(
    bot: Bot,
    *,
    channel_chat_id: int,
    file_path: str,
    caption: str,
    duration: int | None = None,
    width: int | None = None,
    height: int | None = None,
) -> int | None:
    """Send video to channel. Returns message_id on success.

    Falls back to send_document if send_video fails.
    Returns None if both fail (caller handles error).
    """
    video_path = Path(file_path)

    try:
        msg = await bot.send_video(
            chat_id=channel_chat_id,
            video=video_path,
            caption=caption,
            parse_mode="HTML",
            supports_streaming=True,
            duration=duration,
            width=width,
            height=height,
        )
        return msg.message_id
    except Exception as e:
        logger.warning("send_video failed, falling back to send_document: %s", e)

    # Fallback: send as document
    # Truncate caption if adding suffix would exceed 1024 chars
    max_caption_len = 1024 - len(_FALLBACK_SUFFIX)
    fallback_caption = caption[:max_caption_len] + _FALLBACK_SUFFIX

    try:
        msg = await bot.send_document(
            chat_id=channel_chat_id,
            document=video_path,
            caption=fallback_caption,
            parse_mode="HTML",
        )
        return msg.message_id
    except Exception as e:
        logger.error("send_document also failed: %s", e)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_publisher.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/services/publisher.py tests/test_publisher.py
git commit -m "feat: publisher service with send_video/send_document fallback and tests"
```

---

## Task 8: Download-and-Publish Pipeline (Background Task Orchestrator)

**Files:**
- Create: `bot/services/pipeline.py`
- Create: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing test for pipeline**

Create `tests/test_pipeline.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.pipeline import download_and_publish
from bot.services.downloader import DownloadSlotManager


async def _make_get_setting(overrides=None):
    """Helper to create a mock get_setting that returns defaults."""
    defaults = {"max_concurrent_downloads": "1", "max_file_size_mb": "2000", "max_resolution": "1080"}
    if overrides:
        defaults.update(overrides)
    async def _get_setting(db, key):
        return defaults.get(key)
    return _get_setting


@pytest.mark.asyncio
async def test_pipeline_rejects_when_no_slot():
    """When all slots are full, pipeline should send busy message."""
    slot_mgr = DownloadSlotManager()
    await slot_mgr.try_acquire_slot(1)  # fill the only slot

    bot = AsyncMock()
    get_setting_fn = await _make_get_setting()

    with patch("bot.services.pipeline.get_db", new_callable=AsyncMock), \
         patch("bot.services.pipeline.get_setting", side_effect=get_setting_fn):
        await download_and_publish(
            bot=bot, slot_manager=slot_mgr, user_chat_id=111, user_id=111,
            source_url="https://x.com/u/status/1", caption="test", channel_chat_id=-100123,
        )

    bot.send_message.assert_awaited_once()
    assert "busy" in str(bot.send_message.call_args).lower()


@pytest.mark.asyncio
async def test_pipeline_rejects_when_no_disk_space():
    """When disk space is insufficient, pipeline should notify user."""
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
    assert slot_mgr.active_count == 0  # slot released in finally


@pytest.mark.asyncio
async def test_pipeline_rejects_oversized_file():
    """When downloaded file exceeds size limit, pipeline should notify."""
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
    """Happy path: download + publish succeeds."""
    slot_mgr = DownloadSlotManager()
    bot = AsyncMock()
    bot.send_video = AsyncMock()
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
    """When download raises, pipeline should notify user and release slot."""
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement bot/services/pipeline.py**

```python
from __future__ import annotations
import logging
import shutil

from telegram import Bot

from bot.database.connection import get_db
from bot.database.crud import (
    create_post_log,
    get_setting,
    update_post_log_status,
)
from bot.services.downloader import (
    DownloadSlotManager,
    check_disk_space,
    download_video,
)
from bot.services.publisher import publish_video

logger = logging.getLogger(__name__)


async def download_and_publish(
    *,
    bot: Bot,
    slot_manager: DownloadSlotManager,
    user_chat_id: int,
    user_id: int,
    source_url: str,
    caption: str,
    channel_chat_id: int,
) -> None:
    """Background task: download video and publish to channel.

    This runs as an asyncio.Task, NOT inside a handler.
    All user communication is via bot.send_message().
    """
    db = await get_db()
    max_concurrent = int(await get_setting(db, "max_concurrent_downloads") or "2")
    max_file_size = int(await get_setting(db, "max_file_size_mb") or "2000")
    max_resolution = int(await get_setting(db, "max_resolution") or "1080")

    # Try to acquire download slot
    if not await slot_manager.try_acquire_slot(max_concurrent):
        active = slot_manager.active_count
        await bot.send_message(
            chat_id=user_chat_id,
            text=f"Server busy ({active}/{max_concurrent} download slots in use). "
                 f"Please resend your link to try again.",
        )
        return

    log_id = None
    tmp_dir = None
    try:
        # Check disk space
        has_space, free_mb = check_disk_space(max_concurrent, max_file_size)
        if not has_space:
            await bot.send_message(
                chat_id=user_chat_id,
                text="Insufficient disk space, please try again later.",
            )
            return

        # Create post log
        log_id = await create_post_log(
            db,
            admin_user_id=user_id,
            source_url=source_url,
            channel_chat_id=channel_chat_id,
            caption=caption,
        )

        # Download
        result = await download_video(source_url, max_resolution=max_resolution)
        tmp_dir = result["tmp_dir"]

        # Check file size
        if result["file_size_mb"] > max_file_size:
            await update_post_log_status(
                db, log_id, status="failed",
                error_message=f"File too large: {result['file_size_mb']:.1f} MB",
            )
            await bot.send_message(
                chat_id=user_chat_id,
                text=f"Video too large ({result['file_size_mb']:.1f} MB), "
                     f"exceeds limit ({max_file_size} MB).",
            )
            return

        # Publish
        await update_post_log_status(db, log_id, status="publishing")
        message_id = await publish_video(
            bot,
            channel_chat_id=channel_chat_id,
            file_path=result["file_path"],
            caption=caption,
            duration=result.get("duration"),
            width=result.get("width"),
            height=result.get("height"),
        )

        if message_id:
            await update_post_log_status(
                db, log_id, status="done", message_id=message_id
            )
            await bot.send_message(
                chat_id=user_chat_id,
                text=f"Published successfully! (message #{message_id})",
            )
        else:
            await update_post_log_status(
                db, log_id, status="failed",
                error_message="Failed to send to channel",
            )
            await bot.send_message(
                chat_id=user_chat_id,
                text="Send failed, please check Bot permissions.",
            )

    except Exception as e:
        logger.exception("Pipeline error for %s", source_url)
        if log_id:
            await update_post_log_status(
                db, log_id, status="failed", error_message=str(e)
            )
        await bot.send_message(
            chat_id=user_chat_id,
            text=f"Download failed: {e}",
        )
    finally:
        await slot_manager.release_slot()
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add bot/services/pipeline.py tests/test_pipeline.py
git commit -m "feat: download-and-publish pipeline orchestrator"
```

---

## Task 9: /start, /help, /cancel Handlers

**Files:**
- Create: `bot/handlers/start.py`

- [ ] **Step 1: Implement bot/handlers/start.py**

```python
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.filters import private_chat_only

_HELP_TEXT = """<b>X Video Forward Bot</b>

Send me a Twitter/X video link and I'll publish it to a Telegram channel.

<b>How to use:</b>
1. Send an X video link (x.com or twitter.com)
2. I'll ask you for a caption
3. Choose the target channel (if multiple)
4. I'll download and publish!

<b>Caption format (HTML):</b>
Supported tags: <code>&lt;b&gt;</code> <code>&lt;i&gt;</code> <code>&lt;u&gt;</code> <code>&lt;s&gt;</code> <code>&lt;a href="..."&gt;</code> <code>&lt;code&gt;</code> <code>&lt;pre&gt;</code>
Max length: 1024 characters (text only, tags don't count)

<b>Admin commands:</b>
/add_channel &lt;chat_id&gt; — Add channel
/remove_channel &lt;chat_id&gt; — Remove channel
/list_channels — List channels
/set &lt;key&gt; &lt;value&gt; — Update setting
/settings — View all settings

<b>Super admin commands:</b>
/add_admin &lt;user_id&gt; — Add admin
/remove_admin &lt;user_id&gt; — Remove admin
/list_admins — List admins"""


@private_chat_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(_HELP_TEXT, parse_mode="HTML")


@private_chat_only
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(_HELP_TEXT, parse_mode="HTML")
```

- [ ] **Step 2: Commit**

```bash
git add bot/handlers/start.py
git commit -m "feat: /start and /help command handlers"
```

---

## Task 10: Admin Command Handlers

**Files:**
- Create: `bot/handlers/admin.py`

- [ ] **Step 1: Implement bot/handlers/admin.py**

```python
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.filters import private_chat_only, admin_only, super_admin_only
from bot.database.connection import get_db
from bot.database.crud import (
    add_admin,
    remove_admin,
    list_admins,
    add_channel,
    remove_channel,
    list_channels,
    get_setting,
    set_setting,
    get_all_settings,
)


# --- Admin management (super admin only) ---

@private_chat_only
@super_admin_only
async def add_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /add_admin <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id must be an integer.")
        return
    db = await get_db()
    try:
        await add_admin(db, user_id=user_id)
        await update.message.reply_text(f"Admin {user_id} added.")
    except Exception:
        await update.message.reply_text(f"Admin {user_id} already exists.")


@private_chat_only
@super_admin_only
async def remove_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /remove_admin <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("user_id must be an integer.")
        return
    db = await get_db()
    if await remove_admin(db, user_id=user_id):
        await update.message.reply_text(f"Admin {user_id} removed.")
    else:
        await update.message.reply_text(f"Admin {user_id} not found.")


@private_chat_only
@super_admin_only
async def list_admins_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = await get_db()
    admins = await list_admins(db)
    if not admins:
        await update.message.reply_text("No admins configured.")
        return
    lines = [f"<b>Admins ({len(admins)}):</b>"]
    for a in admins:
        lines.append(f"  {a['user_id']} — {a['username'] or 'N/A'}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# --- Channel management ---

@private_chat_only
@admin_only
async def add_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /add_channel <chat_id>")
        return
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("chat_id must be an integer.")
        return

    bot = context.bot
    # Validate: get_chat
    try:
        chat = await bot.get_chat(chat_id)
    except Exception:
        await update.message.reply_text(
            "Invalid chat_id or bot has no access to this channel."
        )
        return

    # Validate: bot is admin with can_post_messages
    try:
        member = await bot.get_chat_member(chat_id, bot.id)
        if not getattr(member, "can_post_messages", False):
            await update.message.reply_text(
                "Bot is not an admin of this channel with posting permissions. "
                "Please add the bot as a channel admin first."
            )
            return
    except Exception:
        await update.message.reply_text(
            "Bot is not a member of this channel. "
            "Please add the bot as a channel admin first."
        )
        return

    db = await get_db()
    try:
        await add_channel(db, chat_id=chat_id, title=chat.title or str(chat_id))
        await update.message.reply_text(
            f"Channel added: <b>{chat.title}</b> ({chat_id})", parse_mode="HTML"
        )
    except Exception:
        await update.message.reply_text(f"Channel {chat_id} already exists.")


@private_chat_only
@admin_only
async def remove_channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /remove_channel <chat_id>")
        return
    try:
        chat_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("chat_id must be an integer.")
        return
    db = await get_db()
    if await remove_channel(db, chat_id=chat_id):
        await update.message.reply_text(f"Channel {chat_id} removed.")
    else:
        await update.message.reply_text(f"Channel {chat_id} not found.")


@private_chat_only
@admin_only
async def list_channels_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = await get_db()
    channels = await list_channels(db)
    if not channels:
        await update.message.reply_text("No channels configured.")
        return
    lines = [f"<b>Channels ({len(channels)}):</b>"]
    for ch in channels:
        lines.append(f"  {ch['title']} ({ch['chat_id']})")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# --- Settings management ---

@private_chat_only
@admin_only
async def set_setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 2:
        await update.message.reply_text("Usage: /set <key> <value>")
        return
    key, value = context.args[0], context.args[1]
    db = await get_db()
    try:
        await set_setting(db, key, value)
        await update.message.reply_text(f"Setting <code>{key}</code> = <code>{value}</code>", parse_mode="HTML")
    except ValueError as e:
        await update.message.reply_text(str(e))


@private_chat_only
@admin_only
async def get_setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /get <key>")
        return
    key = context.args[0]
    db = await get_db()
    val = await get_setting(db, key)
    if val is None:
        await update.message.reply_text(f"Unknown setting: {key}")
    else:
        await update.message.reply_text(
            f"<code>{key}</code> = <code>{val}</code>", parse_mode="HTML"
        )


@private_chat_only
@admin_only
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = await get_db()
    settings = await get_all_settings(db)
    lines = ["<b>Settings:</b>"]
    for k, v in sorted(settings.items()):
        lines.append(f"  <code>{k}</code> = <code>{v}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")
```

- [ ] **Step 2: Commit**

```bash
git add bot/handlers/admin.py
git commit -m "feat: admin command handlers with channel validation"
```

---

## Task 11: Conversation Handler (Core Two-Phase Flow)

**Files:**
- Create: `bot/handlers/conversation.py`

- [ ] **Step 1: Implement bot/handlers/conversation.py**

```python
from __future__ import annotations
import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.database.connection import get_db
from bot.database.crud import list_channels
from bot.handlers.filters import admin_only, private_chat_only
from bot.services.pipeline import download_and_publish
from bot.utils.validators import extract_url, is_x_video_url, resolve_t_co, sanitize_caption

logger = logging.getLogger(__name__)

# States
WAITING_CAPTION = 0
WAITING_CHANNEL = 1


@private_chat_only
@admin_only
async def entry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry: user sends an X video link."""
    url = extract_url(update.message.text)
    if not url:
        return ConversationHandler.END

    # Resolve t.co short links before storing
    if "t.co/" in url:
        try:
            url = await resolve_t_co(url)
        except Exception:
            await update.message.reply_text("Failed to resolve short link. Please send the full URL.")
            return ConversationHandler.END

    context.user_data["source_url"] = url
    await update.message.reply_text(
        "Link received. Please enter the caption (HTML format supported, max 1024 chars):"
    )
    return WAITING_CAPTION


async def caption_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """WAITING_CAPTION: user sends caption text."""
    raw_caption = update.message.text
    sanitized, error = sanitize_caption(raw_caption)

    if error:
        await update.message.reply_text(error)
        return WAITING_CAPTION  # stay in state, let user retry

    context.user_data["caption"] = sanitized

    # Check channels
    db = await get_db()
    channels = await list_channels(db)

    if not channels:
        await update.message.reply_text("No channels configured. Use /add_channel first.")
        return ConversationHandler.END

    if len(channels) == 1:
        # Single channel — skip selection, go directly to download
        context.user_data["channel_chat_id"] = channels[0]["chat_id"]
        return await _start_download(update, context)

    # Multiple channels — show inline keyboard
    keyboard = [
        [InlineKeyboardButton(ch["title"], callback_data=str(ch["chat_id"]))]
        for ch in channels
    ]
    await update.message.reply_text(
        "Select target channel:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_CHANNEL


async def channel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """WAITING_CHANNEL: user selects channel via inline keyboard."""
    query = update.callback_query
    await query.answer()

    context.user_data["channel_chat_id"] = int(query.data)
    return await _start_download(update, context)


async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    context.user_data.clear()
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


async def _start_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End conversation and spawn background download task."""
    source_url = context.user_data["source_url"]
    caption = context.user_data["caption"]
    channel_chat_id = context.user_data["channel_chat_id"]
    user_id = update.effective_user.id
    user_chat_id = update.effective_chat.id

    # Get the message to reply to
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text("Task accepted. Downloading video...")

    # Get slot manager from bot_data (set in main.py)
    slot_manager = context.bot_data["slot_manager"]

    # Spawn background task (store ref to avoid "exception never retrieved" warning)
    task = asyncio.create_task(
        download_and_publish(
            bot=context.bot,
            slot_manager=slot_manager,
            user_chat_id=user_chat_id,
            user_id=user_id,
            source_url=source_url,
            caption=caption,
            channel_chat_id=channel_chat_id,
        )
    )
    task.add_done_callback(lambda t: t.exception() if not t.cancelled() and t.exception() else None)

    context.user_data.clear()
    return ConversationHandler.END


def build_conversation_handler() -> ConversationHandler:
    """Build and return the ConversationHandler."""
    url_filter = filters.TEXT & filters.Regex(
        r"https?://(?:(?:twitter|x)\.com/\w+/status/\d+|t\.co/\w+)"
    )

    return ConversationHandler(
        entry_points=[MessageHandler(url_filter, entry_handler)],
        states={
            WAITING_CAPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, caption_handler)],
            WAITING_CHANNEL: [CallbackQueryHandler(channel_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        per_user=True,
        per_chat=True,
    )
```

- [ ] **Step 2: Write tests for conversation handler**

Create `tests/test_conversation.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Chat, Message, CallbackQuery
from telegram.constants import ChatType
from telegram.ext import ConversationHandler

from bot.handlers.conversation import (
    entry_handler, caption_handler, channel_handler, cancel_handler,
    WAITING_CAPTION, WAITING_CHANNEL,
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


def _make_context(channels=None, bot_data=None):
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot_data = bot_data or {"slot_manager": MagicMock()}
    ctx.bot = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_entry_handler_valid_url():
    update = _make_update("https://x.com/user/status/123")
    ctx = _make_context()

    with patch("bot.handlers.conversation.admin_only", lambda f: f), \
         patch("bot.handlers.conversation.private_chat_only", lambda f: f):
        # Need to call the unwrapped function since decorators are applied at definition
        from bot.handlers.conversation import entry_handler
        # Patch the decorators at module level
        with patch("bot.handlers.filters.is_admin", return_value=True), \
             patch("bot.handlers.filters.get_db", new_callable=AsyncMock), \
             patch("bot.handlers.filters.SUPER_ADMIN_ID", 111):
            result = await entry_handler.__wrapped__.__wrapped__(update, ctx)

    assert result == WAITING_CAPTION
    assert ctx.user_data["source_url"] == "https://x.com/user/status/123"


@pytest.mark.asyncio
async def test_caption_handler_too_long():
    update = _make_update("a" * 1025)
    ctx = _make_context()

    result = await caption_handler(update, ctx)

    assert result == WAITING_CAPTION  # stays in state
    update.message.reply_text.assert_awaited_once()
    assert "1025" in str(update.message.reply_text.call_args)


@pytest.mark.asyncio
async def test_caption_handler_single_channel():
    update = _make_update("valid caption")
    ctx = _make_context()
    ctx.user_data["source_url"] = "https://x.com/u/status/1"

    channels = [{"chat_id": -100123, "title": "Test"}]

    with patch("bot.handlers.conversation.get_db", new_callable=AsyncMock), \
         patch("bot.handlers.conversation.list_channels", new_callable=AsyncMock, return_value=channels), \
         patch("bot.handlers.conversation.download_and_publish", new_callable=AsyncMock):
        result = await caption_handler(update, ctx)

    assert result == ConversationHandler.END


@pytest.mark.asyncio
async def test_caption_handler_multi_channel_shows_keyboard():
    update = _make_update("valid caption")
    ctx = _make_context()
    ctx.user_data["source_url"] = "https://x.com/u/status/1"

    channels = [
        {"chat_id": -100123, "title": "Chan A"},
        {"chat_id": -100456, "title": "Chan B"},
    ]

    with patch("bot.handlers.conversation.get_db", new_callable=AsyncMock), \
         patch("bot.handlers.conversation.list_channels", new_callable=AsyncMock, return_value=channels):
        result = await caption_handler(update, ctx)

    assert result == WAITING_CHANNEL
    # Verify inline keyboard was sent
    call_kwargs = update.message.reply_text.call_args.kwargs
    assert "reply_markup" in call_kwargs


@pytest.mark.asyncio
async def test_cancel_handler():
    update = _make_update("/cancel")
    ctx = _make_context()
    ctx.user_data["source_url"] = "https://x.com/u/status/1"

    result = await cancel_handler(update, ctx)
    assert result == ConversationHandler.END
    assert len(ctx.user_data) == 0
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_conversation.py -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/conversation.py tests/test_conversation.py
git commit -m "feat: conversation handler with two-phase execution model and tests"
```

---

## Task 12: Main Entry Point

**Files:**
- Create: `bot/main.py`

- [ ] **Step 1: Implement bot/main.py**

```python
import asyncio
import logging
import os

from telegram.ext import ApplicationBuilder, CommandHandler

from bot.config import API_BASE_URL, BOT_TOKEN, DOWNLOAD_DIR, SUPER_ADMIN_ID
from bot.database.connection import close_db, init_db
from bot.database.crud import add_admin, is_admin
from bot.database.models import create_tables
from bot.handlers.admin import (
    add_admin_handler,
    add_channel_handler,
    get_setting_handler,
    list_admins_handler,
    list_channels_handler,
    remove_admin_handler,
    remove_channel_handler,
    set_setting_handler,
    settings_handler,
)
from bot.handlers.conversation import build_conversation_handler
from bot.handlers.start import help_handler, start_handler
from bot.services.downloader import DownloadSlotManager, cleanup_stale_files

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application) -> None:
    """Run after Application.initialize() — DB setup, startup checks."""
    from bot.database.connection import get_db

    # Init database
    db_path = os.path.join("data", "bot.db")
    os.makedirs("data", exist_ok=True)
    await init_db(db_path)
    db = await get_db()
    await create_tables(db)

    # Ensure super admin is in admins table
    if not await is_admin(db, user_id=SUPER_ADMIN_ID):
        await add_admin(db, user_id=SUPER_ADMIN_ID, username="super_admin")
        logger.info("Super admin %d added to database", SUPER_ADMIN_ID)

    # Ensure download directory exists
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Cleanup stale download files
    removed = cleanup_stale_files()
    if removed:
        logger.info("Cleaned up %d stale download files", removed)

    # Verify connectivity to Bot API
    me = await application.bot.get_me()
    logger.info("Bot started: @%s (id=%d)", me.username, me.id)


async def post_shutdown(application) -> None:
    """Cleanup on shutdown."""
    await close_db()


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .base_url(f"{API_BASE_URL}/bot")
        .base_file_url(f"{API_BASE_URL}/file/bot")
        .local_mode(True)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Store slot manager in bot_data for access from handlers
    app.bot_data["slot_manager"] = DownloadSlotManager()

    # Register handlers
    # Conversation handler first (highest priority for URL messages)
    app.add_handler(build_conversation_handler())

    # User commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))

    # Admin commands
    app.add_handler(CommandHandler("add_admin", add_admin_handler))
    app.add_handler(CommandHandler("remove_admin", remove_admin_handler))
    app.add_handler(CommandHandler("list_admins", list_admins_handler))
    app.add_handler(CommandHandler("add_channel", add_channel_handler))
    app.add_handler(CommandHandler("remove_channel", remove_channel_handler))
    app.add_handler(CommandHandler("list_channels", list_channels_handler))
    app.add_handler(CommandHandler("set", set_setting_handler))
    app.add_handler(CommandHandler("get", get_setting_handler))
    app.add_handler(CommandHandler("settings", settings_handler))

    logger.info("Starting bot polling...")
    app.run_polling()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add bot/main.py
git commit -m "feat: main entry point with Application setup and handler registration"
```

---

## Task 13: Docker and Deployment Files

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ bot/

CMD ["python", "-m", "bot.main"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  telegram-bot-api:
    image: aiogram/telegram-bot-api
    environment:
      TELEGRAM_API_ID: ${API_ID}
      TELEGRAM_API_HASH: ${API_HASH}
      TELEGRAM_LOCAL: "true"
    ports:
      - "8081:8081"
    volumes:
      - shared-data:/var/lib/telegram-bot-api
    restart: unless-stopped

  bot:
    build: .
    environment:
      BOT_TOKEN: ${BOT_TOKEN}
      API_BASE_URL: http://telegram-bot-api:8081
      SUPER_ADMIN_ID: ${SUPER_ADMIN_ID}
      DOWNLOAD_DIR: /var/lib/telegram-bot-api/downloads
    volumes:
      - bot-data:/app/data
      - shared-data:/var/lib/telegram-bot-api
    depends_on:
      - telegram-bot-api
    restart: unless-stopped

volumes:
  shared-data:
  bot-data:
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: Dockerfile and docker-compose with Local Bot API Server"
```

---

## Task 14: Update .gitignore, README, and Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README.md with setup instructions**

```markdown
# Telegram X Video Forward Bot

A Telegram Bot that receives X (Twitter) video links, downloads videos with yt-dlp, and publishes them to Telegram Channels with custom captions.

## Features

- Private chat interaction with authorized admins
- HTML-formatted captions (bold, italic, links, code)
- Multi-channel support with inline keyboard selection
- Configurable video quality and concurrent download limits
- Local Bot API Server for uploads up to 2000 MB
- SQLite database for configuration

## Quick Start (Docker)

1. Get a bot token from [@BotFather](https://t.me/BotFather)
2. Get API credentials from [my.telegram.org](https://my.telegram.org)
3. **Important:** Log out from official API first:
   ```bash
   curl https://api.telegram.org/bot<YOUR_TOKEN>/logOut
   ```
   Wait 10 minutes before proceeding.
4. Configure:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```
5. Run:
   ```bash
   docker compose up -d
   ```

## Quick Start (Direct)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — ensure Local Bot API Server is running separately
python -m bot.main
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome and help |
| `/help` | Show help |
| `/add_channel <chat_id>` | Add target channel |
| `/list_channels` | List channels |
| `/settings` | View all settings |
| `/set <key> <value>` | Update setting |

See `/help` in the bot for full command list.
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with setup instructions"
```

- [ ] **Step 4: Final verification — lint and structure check**

Run: `find bot/ -name "*.py" | head -20 && python -c "from bot.config import BOT_TOKEN" 2>&1 || echo "Config requires .env (expected)"`
Expected: All files exist. Config import fails because .env isn't set (expected in dev).
