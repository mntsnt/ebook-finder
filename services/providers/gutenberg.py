import urllib.parse
import aiohttp
from typing import List
from .base import BaseBookProvider, BookResult

class GutenbergProvider(BaseBookProvider):
    name = "Project Gutenberg"
    BASE_URL = "https://gutendex.com/books/"

    async def search(self, query: str, limit: int = 5) -> List[BookResult]:
        encoded_query = urllib.parse.quote(query)
        url = f"{self.BASE_URL}?search={encoded_query}"
        results: List[BookResult] = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return results
                    data = await resp.json()

            for item in data.get("results", [])[:limit]:
                book_id = f"gutenberg:{item.get('id')}"
                title = item.get("title", "Untitled")
                authors = [a.get("name", "Unknown") for a in item.get("authors", [])]
                formats_raw = item.get("formats", {})

                # Extract useful ebook formats
                formats = {}
                cover_url = None

                for mime, link in formats_raw.items():
                    if "application/epub+zip" in mime:
                        formats["epub"] = link
                    elif "x-mobipocket-ebook" in mime:
                        formats["mobi"] = link
                    elif "application/pdf" in mime:
                        formats["pdf"] = link
                    elif "text/plain" in mime and "txt" not in formats:
                        formats["txt"] = link
                    elif "image/jpeg" in mime and not cover_url:
                        cover_url = link

                languages = item.get("languages", [])
                lang_str = languages[0].upper() if languages else "EN"

                results.append(
                    BookResult(
                        id=book_id,
                        title=title,
                        authors=authors,
                        source=self.name,
                        formats=formats,
                        cover_url=cover_url,
                        language=lang_str,
                    )
                )
        except Exception as e:
            print(f"[GutenbergProvider] Error searching: {e}")

        return results
