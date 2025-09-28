from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.config import get_swiss_sources

class SwissScraper(BaseScraper):
    def __init__(self):
        super().__init__("swiss")
    
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape Swiss news sources"""
        all_articles = []
        
        # Use the new configuration system
        swiss_sources = get_swiss_sources()
        
        for source_url in swiss_sources:
            articles = await self.fetch_rss(source_url)
            for article in articles:
                # DON'T categorize here - let LM Studio do it in the pipeline
                # article["category"] = self._categorize_swiss_article(article)
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
            return "ai"
        elif any(term in title_content for term in ["technology", "tech", "digital", "cyber"]):
            return "tech"
        elif any(term in title_content for term in ["politik", "politics", "bundesrat", "parliament", "wahlen"]):
            return "politics"
        elif any(term in title_content for term in ["wirtschaft", "economy", "bank", "börse", "franken"]):
            return "finance"
        else:
            # Default to Swiss category for local news
            return "swiss"
