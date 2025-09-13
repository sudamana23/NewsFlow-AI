from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.config import settings

class TechScraper(BaseScraper):
    def __init__(self):
        super().__init__("tech")
    
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape tech news sources"""
        all_articles = []
        
        for source_url in settings.tech_sources:
            articles = await self.fetch_rss(source_url)
            for article in articles:
                # All tech articles get technology category by default
                article["category"] = self._categorize_tech_article(article)
                all_articles.append(article)
        
        return all_articles
    
    def _categorize_tech_article(self, article: Dict[str, Any]) -> str:
        """Categorize tech article based on content"""
        title_content = f"{article['title']} {article.get('content', '')}".lower()
        
        # Check for AI/ML specific content first
        if any(term in title_content for term in ["ai", "artificial intelligence", "machine learning", "llm", "gpt", "neural", "deep learning"]):
            return "ai_data"
        else:
            return "technology"
