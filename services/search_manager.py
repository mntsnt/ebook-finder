import asyncio
import logging
from pathlib import Path
from typing import List, Optional

import aiohttp

from .providers.base import BookResult
from .providers.gutenberg import GutenbergProvider
from .providers.libgen import LibgenProvider
from .providers.openlibrary import OpenLibraryProvider
from .providers.standardebooks import StandardEbooksProvider
import config

logger = logging.getLogger(__name__)


class SearchManager:
    def __init__(self):
        self.providers = [
            GutenbergProvider(),
            OpenLibraryProvider(),
            StandardEbooksProvider(),
            LibgenProvider()
        ]

    async def search_all(self, query: str, limit_per_source: int = 4) -> List[BookResult]:
        """Queries all providers concurrently and merges results."""
        tasks = [p.search(query, limit=limit_per_source) for p in self.providers]
        gathered = await asyncio.gather(*tasks, return_exceptions=True)

        combined: List[BookResult] = []
        for res in gathered:
            if isinstance(res, list):
                combined.extend(res)

        return combined

    async def download_file(self, raw_url_or_ref: str, filename_hint: str) -> Optional[Path]:
        """Downloads a book file from direct URL or resolves mirror gateways."""
        target_path = config.DOWNLOAD_DIR / filename_hint

        # 1. Libgen gateway mirror (library.lol)
        direct_url = raw_url_or_ref
        if "library.lol" in raw_url_or_ref or "libgen" in raw_url_or_ref:
            resolved = await LibgenProvider.resolve_direct_download(raw_url_or_ref)
            if resolved:
                direct_url = resolved

        # 2. Stream download from resolved URL
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(
                    direct_url, 
                    allow_redirects=True, 
                    timeout=aiohttp.ClientTimeout(total=70)
                ) as resp:
                    if resp.status == 200:
                        content_type = resp.headers.get("Content-Type", "").lower()
                        # If mirror returns an HTML error/blocked page instead of an ebook
                        if "text/html" in content_type and not filename_hint.endswith(".html"):
                            logger.warning(f"[SearchManager] Server returned HTML content for {direct_url}, expected ebook file.")
                            return None

                        with open(target_path, "wb") as f:
                            while chunk := await resp.content.read(1024 * 64):
                                f.write(chunk)

                        if target_path.exists() and target_path.stat().st_size > 0:
                            return target_path
                    else:
                        logger.warning(f"[SearchManager] Download HTTP {resp.status} for {direct_url}")
        except Exception as e:
            logger.error(f"[SearchManager] Download error for {direct_url}: {e}")

        # Cleanup failed or empty target file
        try:
            if target_path.exists():
                target_path.unlink()
        except Exception:
            pass

        return None
