import asyncio
import logging
import uuid
from pathlib import Path
from typing import Dict

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

import config
from services.search_manager import SearchManager
from services.converter import EbookConverter
from services.providers.base import BookResult

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# In-memory cache for book results (to keep Telegram callback_data under 64 bytes)
results_cache: Dict[str, BookResult] = {}

search_manager = SearchManager()

# Initialize bot and dispatcher
if not config.TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN is not set! Please set it in .env before running.")

bot = Bot(token=config.TELEGRAM_BOT_TOKEN or "DUMMY_TOKEN")
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = (
        "📚 *Welcome to EBook Finder Bot!*\n\n"
        "I can search multiple global libraries for books and deliver them directly to your chat in various formats (EPUB, PDF, MOBI, etc.).\n\n"
        "🔍 *How to search:*\n"
        "Simply send me any book title or author, e.g.:\n"
        "• `Dune`\n"
        "• `Frankenstein`\n"
        "• `Clean Code Robert Martin`\n\n"
        "Or use: `/search <query>`\n\n"
        "⚡ *Supported Sources:*\n"
        "• Project Gutenberg (Classic literature)\n"
        "• Libgen (Non-fiction & fiction)\n"
        "• Z-Library (if configured in .env)\n"
    )
    await message.answer(welcome_text, parse_mode="Markdown")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "📖 *Help & Usage:*\n\n"
        "1. Type any book title to search.\n"
        "2. Click on the available format buttons (EPUB, PDF, MOBI, etc.) under the book.\n"
        "3. If your desired format isn't directly available, click *Convert* to transform it using Calibre.\n"
        "4. Telegram has a 50MB limit for direct file transfers. Larger files will provide a direct download link.\n"
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message(F.text)
async def handle_search(message: Message):
    query = message.text.strip()
    if query.startswith("/search"):
        query = query.replace("/search", "", 1).strip()

    if not query:
        await message.answer("Please provide a book name to search. Example: `/search Dracula`", parse_mode="Markdown")
        return

    status_msg = await message.answer(f"🔍 Searching for *{query}* across libraries...", parse_mode="Markdown")

    try:
        results = await search_manager.search_all(query, limit_per_source=4)
        if not results:
            await status_msg.edit_text(f"❌ No books found matching *{query}*. Try another search phrase.", parse_mode="Markdown")
            return

        await status_msg.delete()

        # Present the top 5 results
        for book in results[:5]:
            cache_id = str(uuid.uuid4())[:8]
            results_cache[cache_id] = book

            # Format info card
            authors_str = book.author_display
            size_str = f" • {book.filesize_str}" if book.filesize_str else ""
            lang_str = f" [{book.language}]" if book.language else ""

            caption = (
                f"📖 *{book.title}*\n"
                f"✍️ {authors_str}{lang_str}\n"
                f"🏛 Source: _{book.source}_{size_str}\n"
            )

            # Build inline buttons for available formats
            keyboard_rows = []
            format_buttons = []
            for fmt in book.available_formats:
                format_buttons.append(
                    InlineKeyboardButton(
                        text=f"📥 {fmt.upper()}",
                        callback_data=f"dl:{cache_id}:{fmt}"
                    )
                )
            if format_buttons:
                keyboard_rows.append(format_buttons)

            # Conversion options if Calibre is available
            conv_buttons = [
                InlineKeyboardButton(text="⚡ To MOBI", callback_data=f"cv:{cache_id}:mobi"),
                InlineKeyboardButton(text="⚡ To PDF", callback_data=f"cv:{cache_id}:pdf"),
                InlineKeyboardButton(text="⚡ To EPUB", callback_data=f"cv:{cache_id}:epub")
            ]
            keyboard_rows.append(conv_buttons)

            markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
            await message.answer(caption, reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        await status_msg.edit_text("⚠️ An error occurred while searching. Please try again.")


@dp.callback_query(F.data.startswith("dl:"))
async def handle_direct_download(callback: CallbackQuery):
    _, cache_id, requested_fmt = callback.data.split(":")
    book = results_cache.get(cache_id)

    if not book:
        await callback.answer("⚠️ Search session expired. Please search again.", show_alert=True)
        return

    raw_url = book.formats.get(requested_fmt)
    if not raw_url:
        await callback.answer(f"Format {requested_fmt.upper()} not found for this book.", show_alert=True)
        return

    await callback.answer()
    progress = await callback.message.reply(f"⏳ Downloading *{book.title}* ({requested_fmt.upper()})...", parse_mode="Markdown")

    safe_title = "".join(c for c in book.title if c.isalnum() or c in (" ", "_", "-")).rstrip()[:40]
    filename_hint = f"{safe_title}_{cache_id}.{requested_fmt}"

    file_path = await search_manager.download_file(raw_url, filename_hint)

    if not file_path or not file_path.exists():
        await progress.edit_text("❌ Failed to download file from the mirror. It may be currently offline.")
        return

    # Check file size (Telegram 50MB limit)
    file_size = file_path.stat().st_size
    if file_size > config.TELEGRAM_FILE_SIZE_LIMIT:
        await progress.edit_text(
            f"⚠️ File is too large for Telegram upload ({file_size // (1024*1024)} MB > 50 MB limit).\n"
            f"Direct download link: [Click here to download]({raw_url})",
            parse_mode="Markdown"
        )
        try:
            file_path.unlink()
        except Exception:
            pass
        return

    # Send document
    try:
        await progress.edit_text("📤 Uploading book to Telegram...")
        doc = FSInputFile(file_path, filename=f"{safe_title}.{requested_fmt}")
        await callback.message.reply_document(
            document=doc,
            caption=f"📘 *{book.title}*\n✍️ {book.author_display}\n🏛 {book.source}",
            parse_mode="Markdown"
        )
        await progress.delete()
    except Exception as e:
        logger.error(f"Telegram upload error: {e}")
        await progress.edit_text(f"⚠️ Could not send document: {e}")
    finally:
        # Cleanup temporary file
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass


@dp.callback_query(F.data.startswith("cv:"))
async def handle_convert_download(callback: CallbackQuery):
    _, cache_id, target_ext = callback.data.split(":")
    book = results_cache.get(cache_id)

    if not book:
        await callback.answer("⚠️ Search session expired. Please search again.", show_alert=True)
        return

    if not EbookConverter.is_calibre_available():
        await callback.answer(
            "⚠️ Calibre (ebook-convert) is not installed on the server. Please install Calibre to enable format conversion.",
            show_alert=True
        )
        return

    # Find the best source format (prefer epub, then mobi, then pdf)
    source_fmt = None
    for preferred in ["epub", "mobi", "pdf", "txt"]:
        if preferred in book.formats:
            source_fmt = preferred
            break

    if not source_fmt:
        source_fmt = list(book.formats.keys())[0] if book.formats else None

    if not source_fmt:
        await callback.answer("No source file available to convert.", show_alert=True)
        return

    await callback.answer()
    progress = await callback.message.reply(
        f"⏳ Fetching source ({source_fmt.upper()}) and converting to *{target_ext.upper()}*...",
        parse_mode="Markdown"
    )

    safe_title = "".join(c for c in book.title if c.isalnum() or c in (" ", "_", "-")).rstrip()[:40]
    source_filename = f"{safe_title}_{cache_id}.{source_fmt}"
    raw_url = book.formats[source_fmt]

    source_path = await search_manager.download_file(raw_url, source_filename)
    if not source_path or not source_path.exists():
        await progress.edit_text("❌ Failed to download original source file for conversion.")
        return

    # Convert using Calibre
    await progress.edit_text(f"⚙️ Converting to {target_ext.upper()} via Calibre...")
    converted_path = await EbookConverter.convert(source_path, target_ext)

    if not converted_path or not converted_path.exists():
        await progress.edit_text("❌ Conversion failed. The file structure may be unsupported.")
        try:
            source_path.unlink()
        except Exception:
            pass
        return

    # Upload converted file
    try:
        await progress.edit_text(f"📤 Uploading converted {target_ext.upper()} to Telegram...")
        doc = FSInputFile(converted_path, filename=f"{safe_title}.{target_ext}")
        await callback.message.reply_document(
            document=doc,
            caption=f"📘 *{book.title}* ({target_ext.upper()})\n✍️ {book.author_display}\n⚡ Converted from {source_fmt.upper()}",
            parse_mode="Markdown"
        )
        await progress.delete()
    except Exception as e:
        logger.error(f"Telegram upload error: {e}")
        await progress.edit_text(f"⚠️ Could not send converted document: {e}")
    finally:
        # Cleanup temporary files
        for p in [source_path, converted_path]:
            try:
                if p and p.exists():
                    p.unlink()
            except Exception:
                pass


async def main():
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n" + "=" * 60)
        print("ERROR: Please set your TELEGRAM_BOT_TOKEN in .env before running!")
        print("=" * 60 + "\n")
        return

    print("🚀 Starting EBook Finder Bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
