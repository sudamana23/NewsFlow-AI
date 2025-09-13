import asyncio
import httpx
import feedparser
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, source_type: str):
        self.source_type = source_type
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "NewsDigest/1.0 (Professional News Aggregator)"
            }
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    @abstractmethod
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape articles from source"""
        pass
    
    async def fetch_rss(self, url: str) -> List[Dict[str, Any]]:
        """Fetch and parse RSS feed"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            feed = feedparser.parse(response.content)
            articles = []
            
            for entry in feed.entries[:10]:  # Limit to recent articles
                article = {
                    "url": entry.link,
                    "title": entry.title,
                    "content": getattr(entry, "summary", ""),
                    "published_at": self._parse_date(getattr(entry, "published", None)),
                    "source": feed.feed.get("title", url),
                    "source_type": self.source_type
                }
                articles.append(article)
            
            return articles
        except Exception as e:
            logger.error(f"Error fetching RSS {url}: {e}")
            return []
    
    async def fetch_with_playwright(self, url: str) -> Optional[str]:
        """Fetch dynamic content with Playwright"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle")
                content = await page.content()
                await browser.close()
                return content
        except Exception as e:
            logger.error(f"Error with Playwright {url}: {e}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse various date formats and return timezone-naive datetime"""
        if not date_str:
            return None
        
        try:
            # Try common formats
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(date_str)
            # Convert to timezone-naive UTC
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            try:
                dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                # Convert to timezone-naive UTC
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt
            except Exception:
                logger.warning(f"Could not parse date: {date_str}")
                return None
    
    def extract_text_content(self, html: str, max_length: int = 500) -> str:
        """Extract clean text from HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "aside"]):
                script.decompose()
            
            # Get text and clean it
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:max_length] if len(text) > max_length else text
        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return ""
