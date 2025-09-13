import httpx
import json
from typing import Dict, Any, List
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class LMStudioSummarizer:
    def __init__(self):
        self.base_url = settings.lm_studio_url
        self.model = settings.lm_studio_model
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def summarize_article(self, article: Dict[str, Any]) -> str:
        """Summarize a single article using local LLM"""
        try:
            prompt = self._create_summary_prompt(article)
            
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional news summarizer. Create concise, factual summaries in 1-2 sentences. Focus on key facts and avoid speculation."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 100,
                    "temperature": 0.3
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            summary = result["choices"][0]["message"]["content"].strip()
            return summary[:settings.summary_max_length]
            
        except Exception as e:
            logger.error(f"Error summarizing article: {e}")
            return self._fallback_summary(article)
    
    async def create_digest_summary(self, articles: List[Dict[str, Any]]) -> Dict[str, str]:
        """Create category-based digest summaries"""
        summaries = {}
        
        # Group articles by category
        categories = {}
        for article in articles:
            cat = article.get("category", "world")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(article)
        
        # Create summary for each category
        for category, cat_articles in categories.items():
            if len(cat_articles) <= 3:
                # Few articles - list individually
                summaries[category] = f"{len(cat_articles)} stories in {category.replace('_', ' ').title()}"
            else:
                # Many articles - create overview
                titles = [art["title"] for art in cat_articles[:5]]
                prompt = f"Create a brief overview of these {category.replace('_', ' ')} news stories:\n" + "\n".join(titles)
                
                try:
                    overview = await self._get_llm_response(prompt, max_tokens=80)
                    summaries[category] = overview
                except Exception:
                    summaries[category] = f"{len(cat_articles)} stories in {category.replace('_', ' ').title()}"
        
        return summaries
    
    def _create_summary_prompt(self, article: Dict[str, Any]) -> str:
        """Create prompt for article summarization"""
        content = article.get("content", "")[:1000]  # Limit content length
        title = article["title"]
        
        return f"""Summarize this news article in 1-2 clear, factual sentences:

Title: {title}
Content: {content}

Summary:"""
    
    async def _get_llm_response(self, prompt: str, max_tokens: int = 100) -> str:
        """Get response from local LLM"""
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": 0.3
            }
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
    
    def _fallback_summary(self, article: Dict[str, Any]) -> str:
        """Create fallback summary if LLM fails"""
        content = article.get("content", "")
        if content:
            # Take first sentence or first 150 chars
            sentences = content.split(". ")
            if sentences:
                return sentences[0] + "."
        
        return f"Article from {article.get('source', 'Unknown source')}"
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global instance
summarizer = LMStudioSummarizer()
