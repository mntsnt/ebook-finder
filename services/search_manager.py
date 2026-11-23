import asyncio
import os
import aiohttp
from pathlib import Path
from typing import List, Optional, Tuple
from .providers.base import BookResult
from .providers.gutenberg import GutenbergProvider
from .providers.libgen import LibgenProvider
from .providers.zlibrary import ZLibraryProvider
import config

class SearchManager:
    def __init__(self):
        self.providers = [
            GutenbergProvider(),
            LibgenProvider(),
            ZLibraryProvider()
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
        """Downloads a book file from direct URL, Z-Library client, or resolves mirror gateways."""
        target_path = config.DOWNLOAD_DIR / filename_hint

        # 1. Check if it's a Z-Library item managed by sertraline/zlibrary
        if raw_url_or_ref.startswith("zlib_token:"):
            reg_key = raw_url_or_ref.replace("zlib_token:", "", 1)
            return await ZLibraryProvider.download_book(reg_key, target_path)

        # 2. Check if it's a Libgen gateway mirror (library.lol)
        direct_url = raw_url_or_ref
        if "library.lol" in raw_url_or_ref or "libgen" in raw_url_or_ref:
            resolved = await LibgenProvider.resolve_direct_download(raw_url_or_ref)
            if resolved:
                direct_url = resolved

        # 3. Download file stream
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(direct_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        with open(target_path, "wb") as f:
                            while chunk := await resp.content.read(1024 * 64):
                                f.write(chunk)
                        return target_path
        except Exception as e:
            print(f"[SearchManager] Download error for {direct_url}: {e}")

        return None
