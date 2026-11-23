# EBook Finder Telegram Bot

An asynchronous Telegram bot that searches multiple global digital libraries (Open Library, Project Gutenberg, Standard Ebooks, Libgen, and Z-Library) and delivers books directly to your Telegram chat in various formats (EPUB, PDF, MOBI, TXT), with optional Calibre conversion capabilities.

---

## Features

- Multi-Source Search: Concurrent searching across Open Library / Internet Archive, Project Gutenberg, Standard Ebooks, Libgen, and Z-Library.
- Clean Professional UI: Text-based interface without emojis or symbols.
- Robust HTML Formatting: Safe against special characters, brackets, or underscores in book titles.
- Memory Bounded: In-memory cache protects against memory leaks during 24/7 cloud deployment.
- Multiple Formats: Direct downloads for EPUB, PDF, MOBI, TXT.
- On-The-Fly Conversion: Integrates with Calibre CLI (ebook-convert) when available.
- Asynchronous & Fast: Built with aiogram 3 and aiohttp.
- Automatic Cleanup: Deletes temporary downloaded cache files after sending.

---

## Quick Setup Guide

### 1. Open Terminal in this Folder
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

### 4. Configure Environment Variables
Create your `.env` file by copying `.env.example`:
```powershell
Copy-Item .env.example .env
```
Open `.env` in any text editor and paste your Telegram bot token:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_example
```

(Optional) For Z-Library, set either:
```env
REMIX_USERKEY=your_cookie_token
REMIX_USERID=your_cookie_id
```
or:
```env
ZLIB_EMAIL=your_email@example.com
ZLIB_PASSWORD=your_password
```

---

## Running the Bot

Run:
```powershell
python bot.py
```

---

## Docker & Cloud Deployment

This project includes a production-ready `Dockerfile` and `Procfile`.
Deploy directly to AletCloud, Koyeb, Render, Railway, or any Docker container host by setting `TELEGRAM_BOT_TOKEN` in your service's environment variables.
