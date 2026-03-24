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

# Path to cookies.txt for yt-dlp authentication (e.g. Twitter/X)
COOKIES_FILE: str = os.environ.get("COOKIES_FILE", "/app/data/cookies.txt")
