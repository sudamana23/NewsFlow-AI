from sqlmodel import SQLModel, Field, create_engine
from datetime import datetime
from typing import Optional, List
from enum import Enum
import uuid

class SourceType(str, Enum):
    MAINSTREAM = "mainstream"
    TECH = "tech"
    SOCIAL = "social"
    SWISS = "swiss"

class StoryCategory(str, Enum):
    WORLD = "world"
    POLITICS = "politics"
    TECHNOLOGY = "technology"
    AI_DATA = "ai_data"
    UKRAINE = "ukraine"
    GAZA = "gaza"
    SWITZERLAND = "switzerland"
    FINANCE = "finance"

def utc_now() -> datetime:
    """Return timezone-naive UTC datetime"""
    return datetime.utcnow()

class Article(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None
    source: str
    source_type: SourceType
    category: Optional[StoryCategory] = None
    published_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=utc_now)
    engagement_score: Optional[float] = 0.0
    is_processed: bool = False

class Digest(SQLModel, table=True):
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    created_at: datetime = Field(default_factory=utc_now)
    digest_type: str = Field(default="hourly")  # hourly, morning, evening
    stories_count: int
    categories: str  # JSON string of categories included
    is_archived: bool = False

class DigestArticle(SQLModel, table=True):
    digest_id: str = Field(foreign_key="digest.id", primary_key=True)
    article_id: str = Field(foreign_key="article.id", primary_key=True)
    position: int
    category_group: Optional[str] = None
