# 📚 EBook Finder Telegram Bot

An asynchronous Telegram bot that searches multiple global digital libraries (Project Gutenberg, Libgen, and optional Z-Library) and delivers books directly to your Telegram chat in various formats (EPUB, PDF, MOBI, TXT, etc.), with automatic Calibre conversion capabilities.

---

## 🚀 Features

- **Multi-Source Search**: Concurrent searching across Project Gutenberg, Libgen mirrors, and Z-Library (supports [bipinkrish/Zlibrary-API](https://github.com/bipinkrish/Zlibrary-API) & [sertraline/zlibrary](https://github.com/sertraline/zlibrary)).
- **Flexible Authentication**: Supports both email/password and session cookie tokens (`remix_userkey` / `remix_userid`) perfect for cloud environment variables.
- **Multiple Formats**: Direct downloads for EPUB, PDF, MOBI, TXT.
- **On-The-Fly Conversion**: Integrates with Calibre CLI (`ebook-convert`) to convert books (e.g. EPUB to MOBI for Kindle, or EPUB to PDF).
- **Asynchronous & Fast**: Built with `aiogram 3` and `aiohttp`.
- **Automatic Cleanup**: Deletes downloaded cache files after sending to save disk space.

---

## 🛠️ Quick Setup Guide

### 1. Open Terminal in this Folder
Open PowerShell or Command Prompt:
```powershell
cd C:\Users\hp\Desktop\ebook-finder
```

### 2. Create and Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configure Your Bot Token
Create your `.env` file by copying `.env.example`:
```powershell
Copy-Item .env.example .env
```
Open `.env` in any text editor and paste your Telegram bot token:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_example
```

*(Optional)* If you want Z-Library support, add your Z-Library account details in `.env`:
```env
ZLIB_EMAIL=your_email@example.com
ZLIB_PASSWORD=your_password
```

---

## 🏃‍♂️ Running the Bot

Run:
```powershell
python bot.py
```

Now open Telegram, go to your bot, and send `/start` or any book title (e.g., `Dune`, `Sherlock Holmes`, `Clean Code`)!

---

## ⚡ (Optional) Format Conversion with Calibre

To enable the `[⚡ To MOBI]`, `[⚡ To PDF]`, and `[⚡ To EPUB]` conversion buttons:
1. Download and install [Calibre](https://calibre-ebook.com/download_windows).
2. Ensure Calibre's folder (typically `C:\Program Files\Calibre2`) is in your system **PATH**, or set `CALIBRE_CONVERT_PATH` in `.env`.
