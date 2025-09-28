from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.config import get_tech_sources

class TechScraper(BaseScraper):
    def __init__(self):
        super().__init__("tech")
    
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape tech news sources"""
        all_articles = []
        
        # Use the new configuration system
        tech_sources = get_tech_sources()
        
        for source_url in tech_sources:
            articles = await self.fetch_rss(source_url)
            for article in articles:
                # DON'T categorize here - let LM Studio do it in the pipeline  
                # article["category"] = self._categorize_tech_article(article)
                all_articles.append(article)
        
        return all_articles
    
    def _categorize_tech_article(self, article: Dict[str, Any]) -> str:
        """Categorize tech article based on content"""
        title_content = f"{article['title']} {article.get('content', '')}".lower()
        
        # Check for AI/ML specific content first
        if any(term in title_content for term in ["ai", "artificial intelligence", "machine learning", "llm", "gpt", "neural", "deep learning"]):
            return "ai"
        else:
            return "tech"
