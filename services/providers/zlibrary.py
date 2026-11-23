import aiohttp
import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict

from .base import BaseBookProvider, BookResult
import config

logger = logging.getLogger(__name__)

# Registry for active search results mapping to book details
zlib_books_registry: Dict[str, dict] = {}

class ZLibraryProvider(BaseBookProvider):
    name = "Z-Library"

    # Known Z-Library EAPI mirror endpoints
    BASE_DOMAINS = [
        "https://singlelogin.re",
        "https://z-library.sk",
        "https://1lib.sk",
        "https://zlibrary-global.se"
    ]

    def __init__(self):
        self.active_domain = self.BASE_DOMAINS[0]
        self.remix_userid = config.REMIX_USERID
        self.remix_userkey = config.REMIX_USERKEY
        self.is_authenticated = bool(self.remix_userkey)
        self._login_lock = asyncio.Lock()

    def get_cookies(self) -> Dict[str, str]:
        cookies = {}
        if self.remix_userkey:
            cookies["remix_userkey"] = self.remix_userkey
        if self.remix_userid:
            cookies["remix_userid"] = self.remix_userid
        return cookies

    async def _ensure_auth(self) -> bool:
        """
        Authenticates with Z-Library using either:
        1. Token/Cookie (remix_userkey / remix_userid)
        2. Email & Password via /eapi/user/login
        """
        if self.is_authenticated:
            return True

        has_creds = bool(config.ZLIB_EMAIL and config.ZLIB_PASSWORD)
        has_token = bool(config.REMIX_USERKEY)

        if not has_creds and not has_token:
            return False

        async with self._login_lock:
            if self.is_authenticated:
                return True

            if has_token:
                self.remix_userkey = config.REMIX_USERKEY
                self.remix_userid = config.REMIX_USERID
                self.is_authenticated = True
                logger.info("[ZLibraryProvider] Authenticated using REMIX_USERKEY token.")
                return True

            # Attempt EAPI login with credentials across domains
            for domain in self.BASE_DOMAINS:
                url = f"{domain}/eapi/user/login"
                data = {"email": config.ZLIB_EMAIL, "password": config.ZLIB_PASSWORD}
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, data=data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status == 200:
                                res_json = await resp.json()
                                if res_json.get("success"):
                                    user_data = res_json.get("user", {})
                                    self.remix_userkey = user_data.get("remix_userkey")
                                    self.remix_userid = str(user_data.get("id", ""))
                                    self.active_domain = domain
                                    self.is_authenticated = True
                                    logger.info(f"[ZLibraryProvider] Successfully logged into {domain}")
                                    return True
                except Exception as e:
                    logger.debug(f"[ZLibraryProvider] Login attempt on {domain} failed: {e}")
                    continue

        return False

    async def search(self, query: str, limit: int = 5) -> List[BookResult]:
        """Queries Z-Library EAPI book search."""
        if not await self._ensure_auth():
            return []

        results: List[BookResult] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        for domain in self.BASE_DOMAINS:
            url = f"{domain}/eapi/book/search"
            payload = {"message": query, "limit": limit}
            try:
                async with aiohttp.ClientSession(headers=headers, cookies=self.get_cookies()) as session:
                    async with session.post(url, data=payload, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json()
                        books = data.get("books", [])

                        for item in books[:limit]:
                            book_id = f"zlib:{item.get('id')}"
                            hash_val = item.get("hash", "")
                            title = item.get("title", "Untitled")
                            author = item.get("author", "Unknown")
                            ext = str(item.get("extension", "epub")).lower()
                            size_str = item.get("filesizeString", "")
                            cover_url = item.get("cover")

                            reg_key = f"{item.get('id')}_{hash_val}"
                            zlib_books_registry[reg_key] = {
                                "id": item.get("id"),
                                "hash": hash_val,
                                "domain": domain,
                                "extension": ext,
                                "title": title
                            }

                            formats = {ext: f"zlib_token:{reg_key}"}

                            results.append(
                                BookResult(
                                    id=book_id,
                                    title=title,
                                    authors=[author] if author else [],
                                    source=self.name,
                                    formats=formats,
                                    cover_url=cover_url,
                                    filesize_str=size_str,
                                    language=item.get("language", "English")
                                )
                            )

                        if results:
                            self.active_domain = domain
                            break
            except Exception as e:
                logger.debug(f"[ZLibraryProvider] Search on {domain} error: {e}")
                continue

        return results

    @classmethod
    async def download_book(cls, reg_key: str, target_path: Path) -> Optional[Path]:
        """Downloads the requested book directly via Z-Library EAPI."""
        book_info = zlib_books_registry.get(reg_key)
        if not book_info:
            return None

        book_id = book_info["id"]
        book_hash = book_info["hash"]
        domain = book_info.get("domain", "https://singlelogin.re")

        url = f"{domain}/eapi/book/{book_id}/{book_hash}/file"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        cookies = {}
        if config.REMIX_USERKEY:
            cookies["remix_userkey"] = config.REMIX_USERKEY
        if config.REMIX_USERID:
            cookies["remix_userid"] = config.REMIX_USERID

        try:
            async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
                async with session.get(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=90)) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "")
                        if "application/json" in content_type:
                            data = await resp.json()
                            dl_url = data.get("file", {}).get("downloadLink")
                            if dl_url:
                                async with session.get(dl_url, timeout=aiohttp.ClientTimeout(total=90)) as dl_resp:
                                    if dl_resp.status == 200:
                                        with open(target_path, "wb") as f:
                                            while chunk := await dl_resp.content.read(64 * 1024):
                                                f.write(chunk)
                                        return target_path
                        else:
                            with open(target_path, "wb") as f:
                                while chunk := await resp.content.read(64 * 1024):
                                    f.write(chunk)
                            return target_path
        except Exception as e:
            logger.error(f"[ZLibraryProvider] Download error: {e}")

        return None
