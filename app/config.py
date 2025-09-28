from pydantic_settings import BaseSettings
from typing import List, Dict, Any, Optional
import yaml
import os
from pathlib import Path

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/newsdigest"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # LM Studio - Auto-detect model, fallback if needed
    lm_studio_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "auto"  # "auto" = auto-detect, or specify model name
    lm_studio_fallback_model: str = "local-model"  # Used if auto-detection fails
    
    # Security Settings
    enable_auth: bool = False
    auth_username: str = "admin"
    auth_password: str = ""  # Set via environment variable
    session_secret: str = "change-me-in-production"
    
    # Schedule
    update_interval_minutes: int = 60
    quiet_hours_start: int = 23  # 11pm
    quiet_hours_end: int = 6     # 6am
    deep_read_hours: List[int] = [6, 22]  # 6am, 10pm
    
    # Content
    max_stories_per_digest: int = 20
    summary_max_length: int = 150
    
    # Source configuration file path
    sources_config_path: str = "config/sources.yaml"
    
    class Config:
        env_file = ".env"

class NewsSourceManager:
    """Manages news sources from YAML configuration"""
    
    def __init__(self, config_path: str = "config/sources.yaml"):
        self.config_path = Path(config_path)
        self._sources_config = None
        self.load_sources()
    
    def load_sources(self):
        """Load sources from YAML file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._sources_config = yaml.safe_load(f)
            else:
                # Create default config if doesn't exist
                self._create_default_config()
        except Exception as e:
            print(f"⚠️ Error loading sources config: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """Create default sources configuration"""
        default_config = {
            "mainstream_sources": [
                {
                    "name": "BBC World",
                    "url": "https://feeds.bbci.co.uk/news/world/rss.xml",
                    "category": "world",
                    "enabled": True
                },
                {
                    "name": "CNN International", 
                    "url": "https://rss.cnn.com/rss/edition.rss",
                    "category": "world",
                    "enabled": True
                }
            ],
            "tech_sources": [
                {
                    "name": "Ars Technica",
                    "url": "https://arstechnica.com/feed/",
                    "category": "tech", 
                    "enabled": True
                }
            ],
            "reddit_sources": [
                {
                    "name": "r/worldnews",
                    "subreddit": "worldnews",
                    "category": "world",
                    "enabled": True
                }
            ],
            "settings": {
                "max_articles_per_source": 10,
                "update_frequency_minutes": 60,
                "respect_robots_txt": True,
                "user_agent": "NewsDigestAgent/1.0"
            }
        }
        self._sources_config = default_config
    
    def get_enabled_sources(self, source_type: str = None) -> List[Dict[str, Any]]:
        """Get list of enabled sources, optionally filtered by type"""
        if not self._sources_config:
            return []
        
        enabled_sources = []
        
        source_types = [source_type] if source_type else self._sources_config.keys()
        
        for stype in source_types:
            if stype == "settings":
                continue
                
            sources = self._sources_config.get(stype, [])
            for source in sources:
                if source.get("enabled", True):
                    source["source_type"] = stype
                    enabled_sources.append(source)
        
        return enabled_sources
    
    def get_rss_feeds(self) -> List[str]:
        """Get all enabled RSS feed URLs"""
        feeds = []
        for source in self.get_enabled_sources():
            if "url" in source:
                feeds.append(source["url"])
        return feeds
    
    def get_reddit_subreddits(self) -> List[str]:
        """Get all enabled Reddit subreddits"""
        subreddits = []
        reddit_sources = self.get_enabled_sources("reddit_sources")
        for source in reddit_sources:
            if "subreddit" in source:
                subreddits.append(source["subreddit"])
        return subreddits
    
    def get_sources_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all enabled sources for a specific category"""
        return [s for s in self.get_enabled_sources() if s.get("category") == category]
    
    def get_source_settings(self) -> Dict[str, Any]:
        """Get source-related settings"""
        return self._sources_config.get("settings", {})
    
    def reload_sources(self):
        """Reload sources from file (useful for runtime updates)"""
        self.load_sources()

# Create global instances
settings = Settings()
source_manager = NewsSourceManager(settings.sources_config_path)

# Backward compatibility: expose sources as before
def get_mainstream_sources() -> List[str]:
    """Get mainstream news sources including finance, science, government, and sports"""
    urls = []
    # Include multiple categories in mainstream scraper
    for category in ["mainstream_sources", "finance_sources", "science_sources", "government_sources", "sports_sources"]:
        sources = source_manager.get_enabled_sources(category)
        urls.extend([s["url"] for s in sources if "url" in s])
    return urls

def get_tech_sources() -> List[str]:
    """Get tech sources including AI sources"""
    urls = []
    # Include both tech and AI categories
    for category in ["tech_sources", "ai_sources"]:
        sources = source_manager.get_enabled_sources(category)
        urls.extend([s["url"] for s in sources if "url" in s])
    return urls

def get_swiss_sources() -> List[str]:
    return [s["url"] for s in source_manager.get_enabled_sources("swiss_sources") if "url" in s]

def get_reddit_subreddits() -> List[str]:
    return source_manager.get_reddit_subreddits()

# New helper functions
def get_all_rss_sources() -> List[str]:
    """Get all RSS feed URLs from all categories"""
    return source_manager.get_rss_feeds()

def reload_all_sources():
    """Reload sources configuration from file"""
    source_manager.reload_sources()
