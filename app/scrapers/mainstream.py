from typing import List, Dict, Any
from app.scrapers.base import BaseScraper
from app.config import get_mainstream_sources

class MainstreamScraper(BaseScraper):
    def __init__(self):
        super().__init__("mainstream")
    
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape mainstream news sources"""
        all_articles = []
        
        # Use the new configuration system
        mainstream_sources = get_mainstream_sources()
        
        for source_url in mainstream_sources:
            articles = await self.fetch_rss(source_url)
            for article in articles:
                # Enhance with full content if needed
                if "ft.com" in article["url"]:
                    # FT might need special handling
                    article["requires_subscription"] = True
                
                # DON'T categorize here - let LM Studio do it in the pipeline
                # article["category"] = self._categorize_article(article)
                all_articles.append(article)
        
        return all_articles
    
    def _categorize_article(self, article: Dict[str, Any]) -> str:
        """Categorize article based on title and content"""
        title_content = f"{article['title']} {article.get('content', '')}".lower()
        
        if any(term in title_content for term in ["ukraine", "russia", "putin", "zelensky"]):
            return "ukraine"
        elif any(term in title_content for term in ["gaza", "israel", "palestine", "hamas"]):
            return "gaza" 
        elif any(term in title_content for term in ["ai", "artificial intelligence", "machine learning", "data"]):
            return "ai"
        elif any(term in title_content for term in ["technology", "tech", "digital", "cyber"]):
            return "tech"
        elif any(term in title_content for term in ["politics", "election", "government", "policy"]):
            return "politics"
        elif any(term in title_content for term in ["market", "economy", "financial", "bank", "stock"]):
            return "finance"
        else:
            return "world"
