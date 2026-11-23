import urllib.parse
import aiohttp
from typing import List
from .base import BaseBookProvider, BookResult

class OpenLibraryProvider(BaseBookProvider):
    name = "Open Library"
    SEARCH_URL = "https://openlibrary.org/search.json"

    async def search(self, query: str, limit: int = 4) -> List[BookResult]:
        encoded = urllib.parse.quote(query)
        url = f"{self.SEARCH_URL}?q={encoded}&limit={limit}"
        results: List[BookResult] = []

        headers = {
            "User-Agent": "EbookFinderBot/1.0 (https://github.com/mntsnt/ebook-finder)"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                    if resp.status != 200:
                        return results
                    data = await resp.json()

            docs = data.get("docs", [])
            for doc in docs[:limit]:
                # Check for public/downloadable Internet Archive items
                ia_ids = doc.get("ia", [])
                if not ia_ids:
                    continue

                ia_id = ia_ids[0]
                book_id = f"openlibrary:{ia_id}"
                title = doc.get("title", "Untitled")
                authors = doc.get("author_name", [])
                cover_i = doc.get("cover_i")
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg" if cover_i else None

                # Construct direct Internet Archive download links
                formats = {
                    "pdf": f"https://archive.org/download/{ia_id}/{ia_id}.pdf",
                    "epub": f"https://archive.org/download/{ia_id}/{ia_id}.epub"
                }

                languages = doc.get("language", ["eng"])
                lang = languages[0].upper() if languages else "EN"

                results.append(
                    BookResult(
                        id=book_id,
                        title=title,
                        authors=authors[:3],
                        source=self.name,
                        formats=formats,
                        cover_url=cover_url,
                        language=lang
                    )
                )
        except Exception as e:
            print(f"[OpenLibraryProvider] Search error: {e}")

        return results
