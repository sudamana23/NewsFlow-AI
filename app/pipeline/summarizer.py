import httpx
import json
import re
import asyncio
from typing import Dict, Any, List, Tuple
from app.config import settings
from app.lmstudio import lm_studio_manager
import logging

logger = logging.getLogger(__name__)

class LMStudioSummarizer:
    def __init__(self):
        self.base_url = settings.lm_studio_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Category keywords for intelligent classification
        self.category_keywords = {
            "ukraine": ["ukraine", "ukrainian", "russia", "russian", "putin", "zelensky", "kyiv", "moscow", "war", "invasion", "nato", "military aid"],
            "gaza": ["gaza", "israel", "israeli", "palestinian", "palestine", "hamas", "west bank", "jerusalem", "netanyahu", "middle east"],
            "ai": ["artificial intelligence", "ai", "machine learning", "ml", "chatgpt", "openai", "llm", "neural", "deep learning", "algorithm", "automation", "robot"],
            "tech": ["technology", "software", "hardware", "startup", "silicon valley", "app", "platform", "digital", "cyber", "internet", "meta", "google", "apple", "microsoft"],
            "finance": ["stock", "market", "economy", "economic", "inflation", "fed", "federal reserve", "wall street", "nasdaq", "dow", "s&p", "crypto", "bitcoin"],
            "politics": ["election", "congress", "senate", "president", "government", "policy", "vote", "campaign", "republican", "democrat", "political"],
            "health": ["health", "medical", "hospital", "doctor", "disease", "vaccine", "pandemic", "covid", "medicine", "healthcare"],
            "climate": ["climate", "global warming", "carbon", "renewable", "solar", "wind", "environment", "pollution", "emissions", "sustainability"],
            "sports": ["sport", "football", "soccer", "basketball", "baseball", "olympics", "championship", "league", "team", "player"],
            "business": ["business", "company", "corporate", "ceo", "merger", "acquisition", "revenue", "profit", "earnings", "enterprise"]
        }
    
    async def get_current_model(self) -> str:
        """Get the currently active model from LM Studio"""
        if settings.lm_studio_model == "auto":
            return await lm_studio_manager.get_current_model()
        else:
            return settings.lm_studio_model
    
    async def summarize_article(self, article: Dict[str, Any]) -> str:
        """Summarize a single article using local LLM"""
        try:
            # Get current model (auto-detected or configured)
            current_model = await self.get_current_model()
            
            prompt = self._create_summary_prompt(article)
            
            response = await asyncio.wait_for(
                self.client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": current_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a news summarizer. Respond ONLY with a factual 1-2 sentence summary. Do not include any prefixes, explanations, or meta-commentary."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "max_tokens": 80,
                        "temperature": 0.2
                    }
                ),
                timeout=20.0  # 20 second timeout for summarization
            )
            
            response.raise_for_status()
            result = response.json()
            
            raw_summary = result["choices"][0]["message"]["content"].strip()
            
            # Clean up the response - remove common unwanted prefixes
            summary = self._clean_summary(raw_summary)
            
            # Log successful use of detected model (occasionally)
            import random
            if random.random() < 0.1:  # Log 10% of the time to avoid spam
                logger.info(f"✅ Successfully used model '{current_model}' for summarization")
            
            return summary[:settings.summary_max_length]
            
        except asyncio.TimeoutError:
            logger.warning(f"LLM summarization timeout for: {article['title'][:50]}...")
            return self._fallback_summary(article)
        except Exception as e:
            logger.error(f"Error summarizing article with model '{current_model}': {e}")
            return self._fallback_summary(article)
    
    async def categorize_and_summarize(self, article: Dict[str, Any]) -> Tuple[str, str]:
        """Both categorize and summarize an article using enhanced LM Studio"""
        try:
            # Get intelligent category using LM Studio
            category = await self._llm_categorize_article(article)
            
            # Get clean summary
            summary = await self.summarize_article(article)
            
            return category, summary
            
        except Exception as e:
            logger.error(f"Error categorizing and summarizing: {e}")
            # Fallback to keyword-based categorization
            fallback_category = self._keyword_categorize_article(article)
            return fallback_category, self._fallback_summary(article)
    
    async def _llm_categorize_article(self, article: Dict[str, Any]) -> str:
        """Use LM Studio for intelligent article categorization with timeout handling"""
        try:
            current_model = await self.get_current_model()
            
            # Create enhanced categorization prompt
            prompt = self._create_categorization_prompt(article)
            
            # Add shorter timeout for categorization
            response = await asyncio.wait_for(
                self.client.post(
                    f"{self.base_url}/chat/completions",
                    json={
                        "model": current_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a news categorization expert. Respond ONLY with the category name, nothing else. Choose the most specific and contextually appropriate category based on the priority rules given."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "max_tokens": 10,
                        "temperature": 0.1
                    }
                ),
                timeout=15.0  # 15 second timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            category = result["choices"][0]["message"]["content"].strip().lower()
            
            # Validate category is one of our accepted categories
            valid_categories = ["ukraine", "gaza", "swiss", "europe", "ai", "tech", "crypto", "finance", "science", "health", "politics", "world", "premier_league"]
            
            if category in valid_categories:
                logger.info(f"LLM categorized as '{category}': {article['title'][:50]}...")
                return category
            else:
                # Fallback to keyword method if LLM gives invalid category
                logger.warning(f"LLM gave invalid category '{category}', using fallback")
                return self._keyword_categorize_article(article)
            
        except asyncio.TimeoutError:
            logger.warning(f"LLM categorization timeout for: {article['title'][:50]}...")
            return self._keyword_categorize_article(article)
        except Exception as e:
            logger.error(f"Error in LLM categorization: {e}")
            return self._keyword_categorize_article(article)
    
    def _create_categorization_prompt(self, article: Dict[str, Any]) -> str:
        """Create enhanced categorization prompt with hierarchy"""
        title = article["title"]
        content = article.get("content", "")[:400]  # Reduced content length
        source = article.get("source", "")
        
        prompt = f"""Categorize this news article. Choose ONE category from this list:

ukraine, gaza, swiss, europe, ai, tech, crypto, finance, science, health, politics, world, premier_league

Rules:
- If about Ukraine/Russia war → ukraine
- If about Gaza/Israel/Palestine → gaza  
- If about Switzerland → swiss
- If about AI/Machine Learning → ai
- If about other technology → tech
- If about crypto/Bitcoin → crypto
- If about finance/markets → finance
- If about scientific research → science
- If about health/medicine → health
- If about politics/elections → politics
- If about Premier League football → premier_league
- Everything else → world

Title: {title}
Source: {source}
Content: {content}

Category:"""
        
        return prompt
    
    def _keyword_categorize_article(self, article: Dict[str, Any]) -> str:
        """Fallback keyword-based categorization (enhanced)"""
        text_to_analyze = (
            article["title"] + " " + 
            article.get("content", "")[:500]
        ).lower()
        
        # Enhanced keyword mapping with better priority
        priority_keywords = {
            # Highest priority - conflicts
            "ukraine": ["ukraine", "ukrainian", "russia", "russian", "putin", "zelensky", "kyiv", "moscow", "war in ukraine", "invasion", "nato aid"],
            "gaza": ["gaza", "israel", "israeli", "palestinian", "palestine", "hamas", "west bank", "jerusalem", "netanyahu", "israel-palestine", "idf", "middle east conflict"],
            
            # Geographic
            "swiss": ["switzerland", "swiss", "zurich", "geneva", "bern", "basel", "swiss franc", "swiss bank"],
            "europe": ["european union", "eu ", "brexit", "european commission", "eurozone", "european parliament"],
            
            # Technical
            "ai": ["artificial intelligence", "ai ", "machine learning", "chatgpt", "openai", "llm", "neural network", "deep learning", "gpt", "claude", "anthropic"],
            "crypto": ["bitcoin", "cryptocurrency", "blockchain", "ethereum", "defi", "nft", "crypto "],
            "tech": ["technology", "software", "hardware", "startup", "silicon valley", "app store", "cyber", "programming", "developer"],
            "finance": ["stock market", "wall street", "nasdaq", "dow jones", "federal reserve", "inflation", "economy"],
            
            # Science & Health
            "science": ["research", "study finds", "scientists", "discovery", "space", "nasa", "climate change"],
            "health": ["health", "medical", "hospital", "doctor", "disease", "vaccine", "pandemic", "covid"],
            
            # Sports
            "premier_league": ["premier league", "manchester united", "manchester city", "liverpool", "chelsea", "arsenal", "tottenham", "football", "premier league", "epl", "english football"]
        }
        
        # Score categories with priority weighting
        category_scores = {}
        for category, keywords in priority_keywords.items():
            score = 0
            for keyword in keywords:
                title_matches = article["title"].lower().count(keyword) * 5  # Title gets higher weight
                content_matches = text_to_analyze.count(keyword) * 2
                score += title_matches + content_matches
            
            if score > 0:
                # Apply priority multipliers
                if category in ["ukraine", "gaza"]:
                    score *= 3  # Conflicts get highest priority
                elif category == "swiss":
                    score *= 2  # Local news gets priority
                
                category_scores[category] = score
        
        if category_scores:
            best_category = max(category_scores, key=category_scores.get)
            logger.info(f"Keyword categorized as '{best_category}' with score {category_scores[best_category]}: {article['title'][:50]}...")
            return best_category
        
        # Ultimate fallback based on source
        return self._categorize_by_source(article)
    
    def _categorize_by_source(self, article: Dict[str, Any]) -> str:
        """Categorize based on news source as final fallback"""
        source_lower = article.get("source", "").lower()
        
        if any(tech_source in source_lower for tech_source in ["ars technica", "verge", "techcrunch", "hacker news", "wired", "engadget"]):
            return "tech"
        elif any(ai_source in source_lower for ai_source in ["ai news", "venturebeat", "mit technology"]):
            return "ai" 
        elif any(fin_source in source_lower for fin_source in ["financial times", "bloomberg", "reuters", "marketwatch", "yahoo finance"]):
            return "finance"
        elif any(swiss_source in source_lower for swiss_source in ["nzz", "tages-anzeiger", "swissinfo", "local switzerland"]):
            return "swiss"
        elif "reddit" in source_lower:
            # Try to map subreddit to category
            if "technology" in source_lower or "artificial" in source_lower:
                return "tech"
            elif "worldnews" in source_lower:
                return "world"
            elif "switzerland" in source_lower:
                return "swiss"
        
        return "world"  # Final fallback
    
    def _create_summary_prompt(self, article: Dict[str, Any]) -> str:
        """Create a direct prompt for article summarization"""
        content = article.get("content", "")[:800]  # Limit content length
        title = article["title"]
        
        # More direct prompt that should produce cleaner output
        return f"Title: {title}\n\nText: {content}\n\nWrite a factual 1-2 sentence news summary:"
    
    def _clean_summary(self, raw_summary: str) -> str:
        """Clean unwanted prefixes and formatting from summary"""
        summary = raw_summary.strip()
        
        # Remove common unwanted prefixes
        unwanted_prefixes = [
            "Here is a summary of the news article in 1-2 clear, factual sentences:",
            "Here is a summary of the article in 1-2 sentences:",
            "Here is a 1-2 sentence summary:",
            "Here's a summary:",
            "Summary:",
            "In summary:",
            "The article reports that",
            "According to the article,",
            "This article discusses",
            "The news article states that",
        ]
        
        for prefix in unwanted_prefixes:
            if summary.lower().startswith(prefix.lower()):
                summary = summary[len(prefix):].strip()
                break
        
        # Remove quotation marks if the entire summary is wrapped
        if summary.startswith('"') and summary.endswith('"'):
            summary = summary[1:-1]
        
        # Ensure first letter is capitalized
        if summary and summary[0].islower():
            summary = summary[0].upper() + summary[1:]
        
        # Remove any remaining leading colons or dashes
        summary = re.sub(r'^[:\-\s]+', '', summary).strip()
        
        return summary
    
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
            category_display = self._get_category_display_name(category)
            
            if len(cat_articles) <= 3:
                # Few articles - simple count
                summaries[category] = f"{len(cat_articles)} stories in {category_display}"
            else:
                # Many articles - create brief overview
                summaries[category] = f"{len(cat_articles)} stories covering {category_display} developments"
        
        return summaries
    
    def _get_category_display_name(self, category: str) -> str:
        """Get human-readable category name"""
        display_names = {
            "ukraine": "Ukraine War",
            "gaza": "Israel-Gaza Conflict", 
            "ai": "AI & Technology",
            "tech": "Technology",
            "finance": "Financial Markets",
            "politics": "Politics",
            "health": "Health & Medicine",
            "climate": "Climate & Environment",
            "sports": "Sports",
            "business": "Business",
            "world": "World News",
            "swiss": "Swiss News"
        }
        return display_names.get(category, category.replace("_", " ").title())
    
    async def _get_llm_response(self, prompt: str, max_tokens: int = 100) -> str:
        """Get response from local LLM using current model"""
        current_model = await self.get_current_model()
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": current_model,
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
            # Take first sentence or first 120 chars
            sentences = content.split(". ")
            if sentences and len(sentences[0]) > 20:
                return sentences[0] + "."
            elif len(content) > 120:
                return content[:120].rsplit(" ", 1)[0] + "..."
        
        return f"News from {article.get('source', 'Unknown source')}"
    
    async def get_model_status(self) -> Dict[str, Any]:
        """Get current model status and info"""
        return await lm_studio_manager.get_model_info()
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global instance
summarizer = LMStudioSummarizer()
