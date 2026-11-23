import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from .base import BaseBookProvider, BookResult
import config

logger = logging.getLogger(__name__)

# Registry for active Z-Library book items
zlib_books_registry = {}

class ZLibraryProvider(BaseBookProvider):
    name = "Z-Library"

    def __init__(self):
        self.client = None
        self._is_logged_in = False
        self._login_lock = asyncio.Lock()

    async def _ensure_login(self) -> bool:
        """
        Authenticates with Z-Library using bipinkrish/Zlibrary-API / sertraline/zlibrary.
        Supports both:
          1. Direct Token/Cookie auth (REMIX_USERKEY / REMIX_USERID)
          2. Standard Email & Password login
        """
        if self._is_logged_in and self.client:
            return True

        has_credentials = bool(config.ZLIB_EMAIL and config.ZLIB_PASSWORD)
        has_token = bool(config.REMIX_USERKEY)

        if not has_credentials and not has_token:
            return False

        async with self._login_lock:
            if self._is_logged_in and self.client:
                return True

            try:
                import zlibrary
                self.client = zlibrary.AsyncZlib()

                # If token (remix_userkey / remix_userid) is provided
                if has_token:
                    logger.info("[ZLibraryProvider] Authenticating via token (remix_userkey)...")
                    # Set token attributes / cookies if supported by client
                    if hasattr(self.client, "remix_userkey"):
                        self.client.remix_userkey = config.REMIX_USERKEY
                    if config.REMIX_USERID and hasattr(self.client, "remix_userid"):
                        self.client.remix_userid = config.REMIX_USERID

                    # If client has session/cookies dict
                    if hasattr(self.client, "cookies") and isinstance(self.client.cookies, dict):
                        self.client.cookies["remix_userkey"] = config.REMIX_USERKEY
                        if config.REMIX_USERID:
                            self.client.cookies["remix_userid"] = config.REMIX_USERID

                    self._is_logged_in = True
                    return True

                # If credentials (email/password) are provided
                if has_credentials:
                    logger.info("[ZLibraryProvider] Logging in with email/password...")
                    await self.client.login(config.ZLIB_EMAIL, config.ZLIB_PASSWORD)
                    self._is_logged_in = True
                    logger.info("[ZLibraryProvider] Logged in successfully.")
                    return True

            except Exception as e:
                logger.warning(
                    f"[ZLibraryProvider] Could not authenticate with Z-Library API: {e}. "
                    "Please verify your credentials or REMIX_USERKEY."
                )
                self.client = None
                self._is_logged_in = False
                return False

        return False

    async def search(self, query: str, limit: int = 5) -> List[BookResult]:
        """Searches Z-Library."""
        if not await self._ensure_login():
            return []

        results: List[BookResult] = []
        try:
            paginator = await self.client.search(q=query, count=limit)
            items = await paginator.next()

            if not items and hasattr(paginator, "result") and paginator.result:
                items = paginator.result

            for idx, item in enumerate(items[:limit]):
                if isinstance(item, dict):
                    title = item.get("name") or item.get("title", "Untitled")
                    authors_val = item.get("author") or item.get("authors") or []
                    ext = str(item.get("extension", "epub")).lower()
                    size_str = str(item.get("size") or item.get("filesizeString", ""))
                    cover_url = item.get("cover")
                    book_id = f"zlib:{item.get('id', idx)}"
                else:
                    title = getattr(item, "name", None) or getattr(item, "title", "Untitled")
                    authors_val = getattr(item, "author", None) or getattr(item, "authors", [])
                    ext = str(getattr(item, "extension", "epub")).lower()
                    size_str = str(getattr(item, "size", ""))
                    cover_url = getattr(item, "cover", None)
                    book_id = f"zlib:{getattr(item, 'id', idx)}"

                if isinstance(authors_val, str):
                    authors = [a.strip() for a in authors_val.split(",") if a.strip()]
                elif isinstance(authors_val, list):
                    authors = [
                        a.get("author") if isinstance(a, dict) and "author" in a else str(a)
                        for a in authors_val
                    ]
                else:
                    authors = []

                reg_key = f"{book_id}:{ext}"
                zlib_books_registry[reg_key] = item

                formats = {ext: f"zlib_token:{reg_key}"}

                results.append(
                    BookResult(
                        id=book_id,
                        title=title,
                        authors=authors,
                        source=self.name,
                        formats=formats,
                        cover_url=cover_url,
                        filesize_str=size_str
                    )
                )
        except Exception as e:
            logger.error(f"[ZLibraryProvider] Search error: {e}")

        return results

    @classmethod
    async def download_book(cls, reg_key: str, target_path: Path) -> Optional[Path]:
        """Downloads the book using Z-Library client."""
        item = zlib_books_registry.get(reg_key)
        if not item:
            return None

        try:
            target_obj = item
            if hasattr(item, "fetch"):
                target_obj = await item.fetch()

            file_bytes = None
            if hasattr(target_obj, "download"):
                file_bytes = await target_obj.download()

            if file_bytes and isinstance(file_bytes, (bytes, bytearray)):
                with open(target_path, "wb") as f:
                    f.write(file_bytes)
                return target_path
        except Exception as e:
            logger.error(f"[ZLibraryProvider] Download error for {reg_key}: {e}")

        return None
