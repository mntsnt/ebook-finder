import asyncio
import html
import logging
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

import config
from aiohttp import web
from services.search_manager import SearchManager
from services.converter import EbookConverter
from services.providers.base import BookResult

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Memory-bounded cache for book results (max 500 items, prevents memory leaks)
class BoundedCache(OrderedDict):
    def __init__(self, maxsize: int = 500):
        super().__init__()
        self.maxsize = maxsize

    def __setitem__(self, key, value):
        if len(self) >= self.maxsize:
            self.popitem(last=False)
        super().__setitem__(key, value)


results_cache: Dict[str, BookResult] = BoundedCache(maxsize=500)
search_manager = SearchManager()

if not config.TELEGRAM_BOT_TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN is not configured in environment variables.")

bot = Bot(token=config.TELEGRAM_BOT_TOKEN or "DUMMY_TOKEN")
dp = Dispatcher()


def sanitize_filename(title: str, fallback_id: str) -> str:
    """Produces a clean filename safe for filesystems and Telegram uploads."""
    clean = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip()
    return (clean[:45] if clean else f"book_{fallback_id}")


@dp.message(CommandStart())
async def cmd_start(message: Message):
    welcome_text = (
        "<b>Welcome to EBook Finder Bot</b>\n\n"
        "Search global digital libraries and receive books directly in your chat in multiple formats (EPUB, PDF, MOBI, TXT).\n\n"
        "<b>How to search:</b>\n"
        "Send any book title or author directly, for example:\n"
        "• <code>Dune</code>\n"
        "• <code>Frankenstein</code>\n"
        "• <code>Clean Code Robert Martin</code>\n\n"
        "Or use the search command:\n"
        "<code>/search &lt;query&gt;</code>\n\n"
        "<b>Connected Sources:</b>\n"
        "• Open Library / Internet Archive\n"
        "• Project Gutenberg\n"
        "• Standard Ebooks\n"
        "• Libgen\n"
        "• Z-Library (if configured)"
    )
    await message.answer(welcome_text, parse_mode="HTML")


@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "<b>Usage Guide</b>\n\n"
        "1. Send a book title or author name to search.\n"
        "2. Click the format button (EPUB, PDF, MOBI, etc.) under any book result to download.\n"
        "3. Telegram allows direct file delivery up to 50 MB. Larger files will include a direct download link.\n"
        "4. Use /search &lt;title&gt; or send plain text at any time."
    )
    await message.answer(help_text, parse_mode="HTML")


@dp.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject):
    query = command.args.strip() if command.args else ""
    if not query:
        await message.answer(
            "Please provide a book name. Example: <code>/search Dracula</code>",
            parse_mode="HTML"
        )
        return
    await execute_search(message, query)


@dp.message(F.text & ~F.text.startswith("/"))
async def handle_text_search(message: Message):
    query = message.text.strip()
    if not query:
        return
    await execute_search(message, query)


@dp.message(F.text.startswith("/"))
async def handle_unknown_command(message: Message):
    await message.answer(
        "Unknown command. Send a book title to search or use /help to see usage instructions.",
        parse_mode="HTML"
    )


async def execute_search(message: Message, query: str):
    escaped_query = html.escape(query)
    status_msg = await message.answer(
        f"Searching for <b>{escaped_query}</b> across libraries...",
        parse_mode="HTML"
    )

    try:
        results = await search_manager.search_all(query, limit_per_source=4)
        if not results:
            await status_msg.edit_text(
                f"No books found matching <b>{escaped_query}</b>. Try another search phrase.",
                parse_mode="HTML"
            )
            return

        await status_msg.delete()

        calibre_ready = EbookConverter.is_calibre_available()

        # Present the top 5 results
        for book in results[:5]:
            cache_id = str(uuid.uuid4())[:8]
            results_cache[cache_id] = book

            title_safe = html.escape(book.title)
            authors_safe = html.escape(book.author_display)
            source_safe = html.escape(book.source)
            size_str = f" | {html.escape(book.filesize_str)}" if book.filesize_str else ""
            lang_str = f" [{html.escape(book.language)}]" if book.language else ""

            caption = (
                f"<b>Title:</b> {title_safe}\n"
                f"<b>Author:</b> {authors_safe}{lang_str}\n"
                f"<b>Source:</b> {source_safe}{size_str}"
            )

            # Build inline buttons for available formats
            keyboard_rows: List[List[InlineKeyboardButton]] = []
            format_buttons: List[InlineKeyboardButton] = []

            for fmt in book.available_formats:
                format_buttons.append(
                    InlineKeyboardButton(
                        text=f"Download {fmt.upper()}",
                        callback_data=f"dl:{cache_id}:{fmt}"
                    )
                )

            if format_buttons:
                keyboard_rows.append(format_buttons)

            # Only show conversion buttons if Calibre is installed and format isn't already present
            if calibre_ready:
                conv_buttons: List[InlineKeyboardButton] = []
                for target_ext in ["mobi", "pdf", "epub"]:
                    if target_ext not in book.formats:
                        conv_buttons.append(
                            InlineKeyboardButton(
                                text=f"Convert to {target_ext.upper()}",
                                callback_data=f"cv:{cache_id}:{target_ext}"
                            )
                        )
                if conv_buttons:
                    keyboard_rows.append(conv_buttons)

            markup = InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
            await message.answer(caption, reply_markup=markup, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}", exc_info=True)
        try:
            await status_msg.edit_text("An error occurred while searching. Please try again.")
        except Exception:
            pass


@dp.callback_query(F.data.startswith("dl:"))
async def handle_direct_download(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid request.", show_alert=True)
        return

    _, cache_id, requested_fmt = parts
    book = results_cache.get(cache_id)

    if not book:
        await callback.answer("Search session expired. Please search again.", show_alert=True)
        return

    raw_url = book.formats.get(requested_fmt)
    if not raw_url:
        await callback.answer(f"Format {requested_fmt.upper()} not found for this book.", show_alert=True)
        return

    await callback.answer()
    title_safe = html.escape(book.title)
    progress = await callback.message.reply(
        f"Downloading <b>{title_safe}</b> ({requested_fmt.upper()})...",
        parse_mode="HTML"
    )

    filename_base = sanitize_filename(book.title, cache_id)
    filename_hint = f"{filename_base}_{cache_id}.{requested_fmt}"

    file_path = await search_manager.download_file(raw_url, filename_hint)

    if not file_path or not file_path.exists():
        await progress.edit_text("Failed to download file from the mirror. It may be currently unreachable.")
        return

    # Check file size (Telegram 50MB limit)
    file_size = file_path.stat().st_size
    if file_size > config.TELEGRAM_FILE_SIZE_LIMIT:
        size_mb = file_size // (1024 * 1024)
        escaped_url = html.escape(raw_url)
        await progress.edit_text(
            f"File is too large for Telegram upload ({size_mb} MB exceeds the 50 MB limit).\n"
            f"<a href=\"{escaped_url}\">Click here to download directly</a>",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        try:
            file_path.unlink()
        except Exception:
            pass
        return

    # Upload document
    try:
        await progress.edit_text("Uploading book to Telegram...")
        doc = FSInputFile(file_path, filename=f"{filename_base}.{requested_fmt}")
        await callback.message.reply_document(
            document=doc,
            caption=(
                f"<b>Title:</b> {title_safe}\n"
                f"<b>Author:</b> {html.escape(book.author_display)}\n"
                f"<b>Source:</b> {html.escape(book.source)}"
            ),
            parse_mode="HTML"
        )
        await progress.delete()
    except Exception as e:
        logger.error(f"Telegram upload error: {e}")
        await progress.edit_text(f"Could not send document: {html.escape(str(e))}", parse_mode="HTML")
    finally:
        try:
            if file_path and file_path.exists():
                file_path.unlink()
        except Exception:
            pass


@dp.callback_query(F.data.startswith("cv:"))
async def handle_convert_download(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Invalid request.", show_alert=True)
        return

    _, cache_id, target_ext = parts
    book = results_cache.get(cache_id)

    if not book:
        await callback.answer("Search session expired. Please search again.", show_alert=True)
        return

    if not EbookConverter.is_calibre_available():
        await callback.answer(
            "Calibre (ebook-convert) is not installed on the server. Format conversion is currently unavailable.",
            show_alert=True
        )
        return

    # Find the best source format
    source_fmt = None
    for preferred in ["epub", "mobi", "pdf", "txt"]:
        if preferred in book.formats:
            source_fmt = preferred
            break

    if not source_fmt:
        source_fmt = list(book.formats.keys())[0] if book.formats else None

    if not source_fmt:
        await callback.answer("No source file available for conversion.", show_alert=True)
        return

    await callback.answer()
    title_safe = html.escape(book.title)
    progress = await callback.message.reply(
        f"Downloading source ({source_fmt.upper()}) and converting to {target_ext.upper()}...",
        parse_mode="HTML"
    )

    filename_base = sanitize_filename(book.title, cache_id)
    source_filename = f"{filename_base}_{cache_id}.{source_fmt}"
    raw_url = book.formats[source_fmt]

    source_path = await search_manager.download_file(raw_url, source_filename)
    if not source_path or not source_path.exists():
        await progress.edit_text("Failed to download original source file for conversion.")
        return

    await progress.edit_text(f"Converting to {target_ext.upper()} via Calibre...")
    converted_path = await EbookConverter.convert(source_path, target_ext)

    if not converted_path or not converted_path.exists():
        await progress.edit_text("Conversion failed. The file format or structure may not be convertible.")
        try:
            source_path.unlink()
        except Exception:
            pass
        return

    # Check converted file size
    conv_size = converted_path.stat().st_size
    if conv_size > config.TELEGRAM_FILE_SIZE_LIMIT:
        size_mb = conv_size // (1024 * 1024)
        await progress.edit_text(
            f"Converted file is too large for Telegram upload ({size_mb} MB exceeds the 50 MB limit)."
        )
        for p in [source_path, converted_path]:
            try:
                if p and p.exists():
                    p.unlink()
            except Exception:
                pass
        return

    # Upload converted file
    try:
        await progress.edit_text(f"Uploading converted {target_ext.upper()} to Telegram...")
        doc = FSInputFile(converted_path, filename=f"{filename_base}.{target_ext}")
        await callback.message.reply_document(
            document=doc,
            caption=(
                f"<b>Title:</b> {title_safe} ({target_ext.upper()})\n"
                f"<b>Author:</b> {html.escape(book.author_display)}\n"
                f"Converted from {source_fmt.upper()}"
            ),
            parse_mode="HTML"
        )
        await progress.delete()
    except Exception as e:
        logger.error(f"Telegram upload error: {e}")
        await progress.edit_text(f"Could not send converted document: {html.escape(str(e))}", parse_mode="HTML")
    finally:
        for p in [source_path, converted_path]:
            try:
                if p and p.exists():
                    p.unlink()
            except Exception:
                pass


async def handle_health(request):
    return web.Response(text="EBook Finder Bot is running.\n", status=200)


async def start_health_server():
    """Starts a lightweight HTTP server for cloud platforms (AletCloud, Koyeb, Render, Railway)."""
    app = web.Application()
    app.router.add_get("/", handle_health)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/healthz", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    logger.info(f"Health check HTTP server active on 0.0.0.0:{config.PORT}")


async def main():
    # Start HTTP server for cloud platform health checks
    try:
        await start_health_server()
    except Exception as e:
        logger.warning(f"Could not bind health check HTTP server on port {config.PORT}: {e}")

    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        logger.error("=" * 60)
        logger.error("CRITICAL: TELEGRAM_BOT_TOKEN is missing or not configured!")
        logger.error("Please add TELEGRAM_BOT_TOKEN to your platform's environment variables.")
        logger.error("=" * 60)
        # Keep process alive so the container passes health checks and logs remain visible
        while True:
            await asyncio.sleep(3600)

    logger.info("Starting Telegram polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
