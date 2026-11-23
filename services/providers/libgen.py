import re
import urllib.parse
import aiohttp
from bs4 import BeautifulSoup
from typing import List, Optional
from .base import BaseBookProvider, BookResult

class LibgenProvider(BaseBookProvider):
    name = "Libgen"
    MIRRORS = [
        "https://libgen.is",
        "https://libgen.rs",
        "https://libgen.st"
    ]

    async def search(self, query: str, limit: int = 5) -> List[BookResult]:
        encoded = urllib.parse.quote(query)
        results: List[BookResult] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }

        # Try active mirrors
        for mirror in self.MIRRORS:
            url = f"{mirror}/search.php?req={encoded}&res=25&column=def"
            try:
                async with aiohttp.ClientSession(headers=headers) as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status != 200:
                            continue
                        html = await resp.text()

                soup = BeautifulSoup(html, "html.parser")
                tables = soup.find_all("table")
                if len(tables) < 3:
                    continue

                table = tables[2]  # Results table
                rows = table.find_all("tr")[1:]  # Skip header

                for row in rows:
                    if len(results) >= limit:
                        break
                    cols = row.find_all("td")
                    if len(cols) < 10:
                        continue

                    # Column structure:
                    # 0: ID, 1: Authors, 2: Title, 3: Publisher, 4: Year, 5: Pages, 6: Lang, 7: Size, 8: Extension, 9: Mirror 1
                    book_id = f"libgen:{cols[0].get_text(strip=True)}"
                    authors = [a.strip() for a in cols[1].get_text(strip=True).split(",") if a.strip()]
                    title_elem = cols[2].find("a")
                    title = title_elem.get_text(strip=True) if title_elem else cols[2].get_text(strip=True)
                    
                    lang = cols[6].get_text(strip=True)
                    size_str = cols[7].get_text(strip=True)
                    extension = cols[8].get_text(strip=True).lower()
                    
                    # Mirror link to resolve direct download
                    mirror_elem = cols[9].find("a")
                    mirror_url = mirror_elem["href"] if mirror_elem and mirror_elem.has_attr("href") else None

                    if not mirror_url or not extension:
                        continue

                    formats = {extension: mirror_url}

                    results.append(
                        BookResult(
                            id=book_id,
                            title=title,
                            authors=authors,
                            source=self.name,
                            formats=formats,
                            filesize_str=size_str,
                            language=lang,
                        )
                    )

                if results:
                    break  # Got results from this mirror

            except Exception as e:
                # Mirror failed or timed out, try next mirror
                continue

        return results

    @staticmethod
    async def resolve_direct_download(mirror_url: str) -> Optional[str]:
        """Resolves the direct download URL from Libgen's download gateway (e.g. library.lol)."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(mirror_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        soup = BeautifulSoup(await resp.text(), "html.parser")
                        # Look for the GET link
                        download_link = soup.find("a", string=re.compile(r"GET", re.I))
                        if download_link and download_link.has_attr("href"):
                            return download_link["href"]
                        # Or IPFS / Cloudflare links
                        cloudflare_link = soup.find("a", string=re.compile(r"Cloudflare", re.I))
                        if cloudflare_link and cloudflare_link.has_attr("href"):
                            return cloudflare_link["href"]
        except Exception:
            pass
        return None
