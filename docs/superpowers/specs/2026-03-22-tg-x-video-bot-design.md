# Telegram X Video Forward Bot - Design Spec

## Overview

A Telegram Bot that receives Twitter (X) video links from authorized users via private chat, downloads the video using yt-dlp, and publishes it with user-provided rich text caption to a designated Telegram Channel. Uses a Local Bot API Server to support uploads up to 2000MB.

## Tech Stack

| Component | Choice |
|-----------|--------|
| Language | Python 3.11+ |
| Bot Framework | python-telegram-bot v20+ (async) |
| Video Download | yt-dlp (Python API) |
| Database | SQLite via aiosqlite |
| Bot API | Telegram Local Bot API Server (2000MB upload limit) |
| Deployment | Docker Compose / Direct run |

## Architecture

```
User (Private Chat)
    │
    ▼
┌─────────────────────────┐
│   Telegram Bot           │
│  (python-telegram-bot)   │
│                          │
│  ConversationHandler     │
│  链接 → 文案 → Channel   │
│         │                │
│    Downloader (yt-dlp)   │
│         │                │
│    Publisher (send_video) │
│         │                │
│    Database (SQLite)     │
└─────────────────────────┘
          │
          ▼
┌─────────────────────────┐
│ Local Bot API Server     │
│ (telegram-bot-api)       │
│ Upload limit: 2000MB     │
└─────────────────────────┘
          │
          ▼
    Telegram Channel(s)
```

### Core Modules

| Module | Responsibility |
|--------|---------------|
| **Bot Handler** | User interaction, conversation state management (link → caption → channel selection → download → publish) |
| **Downloader** | yt-dlp video download with quality control |
| **Publisher** | Send video + caption to target Channel |
| **Database** | Store config (admin whitelist, channel list, video quality settings, post logs) |
| **Admin Commands** | Bot commands for runtime config management |

## Interaction Flow

```
User:  sends X video link
Bot:   "Parsing link..." → validates link
Bot:   "Please enter the caption (HTML format supported)"
User:  sends caption
Bot:   [multiple channels] → Inline Keyboard to select target Channel
       [single channel] → skip selection
Bot:   "Downloading video..."
Bot:   [file too large] "Video too large (XXX MB), cannot send"
Bot:   [success] "Published to [Channel Name]" + message link
```

### ConversationHandler States

```python
# State constants
WAITING_CAPTION = 0     # Link received, waiting for caption
WAITING_CHANNEL = 1     # Caption received, waiting for channel selection (multi-channel only)

# entry_points: MessageHandler with URL regex filter (admin-only)
# states:
#   WAITING_CAPTION: MessageHandler for text input
#   WAITING_CHANNEL: CallbackQueryHandler for inline keyboard selection
# fallbacks: CommandHandler for /cancel
```

The conversation auto-advances past WAITING_CHANNEL when only one channel is configured. After channel is determined (either by auto-select or user pick), download and publish happen automatically — no extra confirmation step.

## Database Design

### admins

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK | Auto-increment |
| user_id | BIGINT UNIQUE | Telegram User ID |
| username | TEXT | Username for display |
| created_at | TIMESTAMP | Time added |

### channels

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK | Auto-increment |
| chat_id | BIGINT UNIQUE | Channel Chat ID |
| title | TEXT | Channel display name (for button labels) |
| created_at | TIMESTAMP | Time added |

### settings

| Field | Type | Description |
|-------|------|-------------|
| key | TEXT PK | Config key |
| value | TEXT | Config value (JSON serialized) |

Default settings:
- `max_resolution`: `"1080"` — max video resolution
- `max_file_size_mb`: `"2000"` — max file size in MB

Allowed settings keys and valid ranges:
- `max_resolution`: one of `"360"`, `"480"`, `"720"`, `"1080"`, `"1440"`, `"2160"`
- `max_file_size_mb`: integer between `1` and `2000`

The `/set` command validates keys against this whitelist and values against their allowed ranges.

### post_logs

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER PK | Auto-increment |
| admin_user_id | BIGINT | Operator |
| source_url | TEXT | Original X link |
| channel_chat_id | BIGINT | Target Channel |
| message_id | INTEGER | Published message ID (null until published) |
| caption | TEXT | Sent caption |
| status | TEXT | `downloading` / `publishing` / `done` / `failed` |
| error_message | TEXT | Error details if status is `failed` (nullable) |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last status update time |

## Bot Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and usage instructions |
| `/help` | Help information |
| `/cancel` | Cancel current operation |

### Admin Commands

| Command | Description |
|---------|-------------|
| `/add_admin <user_id>` | Add admin (super admin only) |
| `/remove_admin <user_id>` | Remove admin (super admin only) |
| `/list_admins` | List all admins |
| `/add_channel <chat_id> <title>` | Add target Channel |
| `/remove_channel <chat_id>` | Remove Channel |
| `/list_channels` | List all Channels |
| `/set <key> <value>` | Update config |
| `/get <key>` | View config value |
| `/settings` | View all settings |

### Permission Levels

- **Super Admin** (`SUPER_ADMIN_ID` env var): Can manage other admins + all admin functions
- **Admin**: Can post videos, manage Channels and settings, but cannot add/remove admins

## Video Download Logic

### Link Validation

Supported URL patterns:
- `twitter.com/*/status/*`
- `x.com/*/status/*`
- `t.co/*` short links — Bot resolves via HTTP HEAD redirect before passing to yt-dlp

Regex match first, then yt-dlp `extract_info` to verify the link contains downloadable video.

### Download Parameters

```python
ydl_opts = {
    'format': f'best[height<={max_resolution}]'
              f'/bestvideo[height<={max_resolution}]+bestaudio'
              f'/best',
    'outtmpl': os.path.join(tmp_dir, '%(id)s.%(ext)s'),
    'merge_output_format': 'mp4',
}
```

**Note:** The `filesize` filter is intentionally omitted from the format string because most X/Twitter CDNs do not return `Content-Length` metadata, causing the filter to skip all formats. Instead, file size is checked **after download** (step 4 in Download Flow). The format string only controls resolution.

### Download Flow

1. Call yt-dlp Python API (not subprocess)
2. Build format selection from `max_resolution` and `max_file_size_mb` in settings
3. Download to temp directory (`tempfile.mkdtemp()`)
4. Check file size after download; notify user if over limit
5. Clean up temp files on both success and failure

## Publishing Logic

1. Use `bot.send_video()` to send to target Channel
2. Pass `caption` with user text, `parse_mode='HTML'` for rich text
3. Pass video metadata from yt-dlp `extract_info`: `duration`, `width`, `height`, and `thumbnail` (download thumbnail to temp file) so Telegram renders an inline video player instead of a generic file
4. On success, get `message_id` and log to `post_logs`
5. Reply to user with success message + Channel message link

### Rich Text Format

HTML format (more reliable than Markdown in Telegram):
- Supported tags: `<b>`, `<i>`, `<u>`, `<s>`, `<a href="...">`, `<code>`, `<pre>`
- User-provided caption is sanitized: unsupported HTML tags are stripped before sending to avoid Telegram API errors
- Documented in `/start` help message

## Error Handling

| Scenario | Response |
|----------|----------|
| Invalid / non-X link | "Please send a valid X video link" |
| yt-dlp download failure | "Download failed, please check if the link contains a video" |
| File exceeds size limit | "Video too large (XXX MB), exceeds limit (YYY MB)" |
| Channel send failure | "Send failed, please check if Bot is a Channel admin" |
| Network timeout | "Network timeout, please try again later" |
| Unsupported HTML tags in caption | Strip unsupported tags silently, send with clean HTML |

### Concurrency

Downloads are processed sequentially per user (ConversationHandler enforces one active session per user). If multiple admins submit links concurrently, downloads happen in parallel. No global concurrency limit is imposed — for a small admin team this is acceptable. If disk usage becomes a concern, it can be addressed later with a download queue.

## Project Structure

```
tg_auto_forward_bot/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point, init Bot and start
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py          # /start, /help, /cancel
│   │   ├── conversation.py   # Core two-step conversation flow
│   │   └── admin.py          # Admin command handlers
│   ├── services/
│   │   ├── __init__.py
│   │   ├── downloader.py     # yt-dlp download logic
│   │   └── publisher.py      # Send video to Channel
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py     # Database connection management
│   │   ├── models.py         # Table definitions and init
│   │   └── crud.py           # CRUD operations
│   ├── utils/
│   │   ├── __init__.py
│   │   └── validators.py     # URL validation utilities
│   └── config.py             # Environment variable loading
├── .env.example              # Environment variable template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml        # Bot + Local Bot API Server
├── .gitignore
└── README.md
```

## Deployment

### Environment Variables

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram Bot Token |
| `API_BASE_URL` | Local Bot API Server URL (e.g., `http://localhost:8081`) |
| `SUPER_ADMIN_ID` | Super admin Telegram User ID |
| `API_ID` | Telegram API ID (for Local Bot API Server) |
| `API_HASH` | Telegram API Hash (for Local Bot API Server) |

### Docker Compose

```yaml
services:
  telegram-bot-api:
    image: aiogram/telegram-bot-api
    environment:
      TELEGRAM_API_ID: ${API_ID}
      TELEGRAM_API_HASH: ${API_HASH}
      TELEGRAM_LOCAL: "true"          # Enable local mode for 2000MB upload limit
    ports:
      - "8081:8081"
    volumes:
      - shared-data:/var/lib/telegram-bot-api

  bot:
    build: .
    environment:
      BOT_TOKEN: ${BOT_TOKEN}
      API_BASE_URL: http://telegram-bot-api:8081
      SUPER_ADMIN_ID: ${SUPER_ADMIN_ID}
    volumes:
      - bot-data:/app/data
      - shared-data:/var/lib/telegram-bot-api  # Shared volume for local file path uploads
    depends_on:
      - telegram-bot-api

volumes:
  shared-data:    # Shared between bot and API server for local file path passing
  bot-data:       # SQLite database persistence
```

**Local file path uploads:** In local mode, `send_video` can accept a local file path instead of uploading via HTTP. The `shared-data` volume is mounted in both containers so the bot can download files to a path accessible by the API server. The bot downloads to `/var/lib/telegram-bot-api/downloads/` and passes the path directly. This avoids re-uploading large files over HTTP between containers.

### Direct Run

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
# Ensure Local Bot API Server is running separately
python -m bot.main
```

### Dependencies

```
python-telegram-bot[ext]>=20.0
yt-dlp
aiosqlite
python-dotenv
```
