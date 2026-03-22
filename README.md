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
