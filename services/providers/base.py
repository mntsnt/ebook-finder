from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class BookResult(BaseModel):
    id: str  # Unique identifier e.g., 'gutenberg:1342'
    title: str
    authors: List[str] = Field(default_factory=list)
    source: str
    formats: Dict[str, str] = Field(default_factory=dict)  # format_ext -> direct download URL
    cover_url: Optional[str] = None
    filesize_str: Optional[str] = None
    language: Optional[str] = None

    @property
    def author_display(self) -> str:
        return ", ".join(self.authors) if self.authors else "Unknown Author"

    @property
    def available_formats(self) -> List[str]:
        return list(self.formats.keys())

class BaseBookProvider(ABC):
    name: str = "BaseProvider"

    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> List[BookResult]:
        """Search for books matching the given query."""
        pass
