import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Telegram Bot Token (supports all common environment variable names)
TELEGRAM_BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("TELEGRAM_TOKEN")
    or os.getenv("TOKEN")
    or ""
).strip()

# Calibre conversion tool path (optional)
CALIBRE_CONVERT_PATH = os.getenv("CALIBRE_CONVERT_PATH", "ebook-convert")

# HTTP Port for cloud health check (AletCloud, Koyeb, Render, Railway, etc.)
PORT = int(os.getenv("PORT", "8080"))

# Telegram max file upload limit (in bytes) - 50 MB standard limit
TELEGRAM_FILE_SIZE_LIMIT = 50 * 1024 * 1024
