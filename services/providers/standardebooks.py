import urllib.parse
import aiohttp
from bs4 import BeautifulSoup
from typing import List
from .base import BaseBookProvider, BookResult

class StandardEbooksProvider(BaseBookProvider):
    name = "Standard Ebooks"
    SEARCH_URL = "https://standardebooks.org/opds/search"

    async def search(self, query: str, limit: int = 3) -> List[BookResult]:
        encoded = urllib.parse.quote(query)
        url = f"{self.SEARCH_URL}?query={encoded}"
        results: List[BookResult] = []

        headers = {
            "User-Agent": "EbookFinderBot/1.0"
        }

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return results
                    xml_data = await resp.text()

            try:
                soup = BeautifulSoup(xml_data, "xml")
            except Exception:
                soup = BeautifulSoup(xml_data, "html.parser")
            entries = soup.find_all("entry")

            for entry in entries[:limit]:
                title_elem = entry.find("title")
                title = title_elem.get_text(strip=True) if title_elem else "Untitled"
                
                authors = [a.get_text(strip=True) for a in entry.find_all("name")]
                
                formats = {}
                cover_url = None

                for link in entry.find_all("link"):
                    href = link.get("href", "")
                    if href.startswith("/"):
                        href = f"https://standardebooks.org{href}"
                    
                    link_type = link.get("type", "")
                    rel = link.get("rel", "")

                    if "application/epub+zip" in link_type:
                        formats["epub"] = href
                    elif "x-mobipocket-ebook" in link_type or "mobi" in href:
                        formats["mobi"] = href
                    elif "kepub" in href:
                        formats["kepub"] = href
                    elif "image" in link_type or "cover" in rel:
                        if not cover_url:
                            cover_url = href

                if formats:
                    safe_id = "".join(c for c in title if c.isalnum()).lower()[:20]
                    results.append(
                        BookResult(
                            id=f"standardebooks:{safe_id}",
                            title=title,
                            authors=authors,
                            source=self.name,
                            formats=formats,
                            cover_url=cover_url,
                            language="EN"
                        )
                    )
        except Exception as e:
            print(f"[StandardEbooksProvider] Search error: {e}")

        return results
