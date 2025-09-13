from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/newsdigest"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # LM Studio
    lm_studio_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "local-model"
    
    # News Sources
    mainstream_sources: List[str] = [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.cnn.com/rss/edition.rss",
        "https://www.theguardian.com/world/rss",
        "https://www.ft.com/news-feed"
    ]
    
    tech_sources: List[str] = [
        "https://arstechnica.com/feed/",
        "https://www.theverge.com/rss/index.xml"
    ]
    
    swiss_sources: List[str] = [
        "https://www.nzz.ch/recent.rss",
        "https://www.tagesanzeiger.ch/rss.html"
    ]
    
    # Reddit
    reddit_subreddits: List[str] = [
        "worldnews", "technology", "artificial", "MachineLearning",
        "ukraine", "switzerland"
    ]
    
    # Schedule
    update_interval_minutes: int = 60
    quiet_hours_start: int = 23  # 11pm
    quiet_hours_end: int = 6     # 6am
    deep_read_hours: List[int] = [6, 22]  # 6am, 10pm
    
    # Content
    max_stories_per_digest: int = 20
    summary_max_length: int = 150
    
    class Config:
        env_file = ".env"

settings = Settings()
