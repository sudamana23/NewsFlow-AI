from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.config import settings

class SwissScraper(BaseScraper):
    def __init__(self):
        super().__init__("swiss")
    
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape Swiss news sources"""
        all_articles = []
        
        for source_url in settings.swiss_sources:
            articles = await self.fetch_rss(source_url)
            for article in articles:
                # Categorize Swiss articles
                article["category"] = self._categorize_swiss_article(article)
                all_articles.append(article)
        
        return all_articles
    
    def _categorize_swiss_article(self, article: Dict[str, Any]) -> str:
        """Categorize Swiss article based on content"""
        title_content = f"{article['title']} {article.get('content', '')}".lower()
        
        # Check for international topics first
        if any(term in title_content for term in ["ukraine", "russia", "putin", "zelensky"]):
            return "ukraine"
        elif any(term in title_content for term in ["gaza", "israel", "palestine", "hamas"]):
            return "gaza"
        elif any(term in title_content for term in ["ai", "artificial intelligence", "machine learning", "data"]):
            return "ai_data"
        elif any(term in title_content for term in ["technology", "tech", "digital", "cyber"]):
            return "technology"
        elif any(term in title_content for term in ["politik", "politics", "bundesrat", "parliament", "wahlen"]):
            return "politics"
        elif any(term in title_content for term in ["wirtschaft", "economy", "bank", "börse", "franken"]):
            return "finance"
        else:
            # Default to Switzerland category for local news
            return "switzerland"
