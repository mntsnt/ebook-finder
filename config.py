import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# Z-Library settings (bipinkrish/Zlibrary-API & sertraline/zlibrary)
# Can authenticate via Email & Password OR via Session Token (remix_userkey / remix_userid)
ZLIB_EMAIL = os.getenv("ZLIB_EMAIL", "").strip()
ZLIB_PASSWORD = os.getenv("ZLIB_PASSWORD", "").strip()
REMIX_USERKEY = (
    os.getenv("REMIX_USERKEY") 
    or os.getenv("ZLIB_USER_KEY") 
    or os.getenv("ZLIB_TOKEN") 
    or ""
).strip()
REMIX_USERID = os.getenv("REMIX_USERID", "").strip()

# Calibre conversion tool path (optional)
CALIBRE_CONVERT_PATH = os.getenv("CALIBRE_CONVERT_PATH", "ebook-convert")

# HTTP Port for cloud health check (AletCloud, Koyeb, Render, Railway, etc.)
PORT = int(os.getenv("PORT", "8080"))

# Telegram max file upload limit (in bytes) - 50 MB standard limit
TELEGRAM_FILE_SIZE_LIMIT = 50 * 1024 * 1024
