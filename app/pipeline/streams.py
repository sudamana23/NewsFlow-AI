import redis.asyncio as aioredis
import redis
import json
from typing import Dict, Any, List
from datetime import datetime
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class NewsStream:
    def __init__(self):
        self.redis = None
        self.stream_name = "news:articles"
        self.consumer_group = "processors"
        self.consumer_name = "processor-1"
    
    async def initialize(self):
        """Create Redis connection and consumer group"""
        try:
            # Create async Redis connection
            self.redis = aioredis.from_url(
                settings.redis_url, 
                encoding="utf-8", 
                decode_responses=True
            )
            
            # Test connection
            await self.redis.ping()
            logger.info("✅ Redis connection established")
            
            # Create consumer group
            try:
                await self.redis.xgroup_create(
                    self.stream_name, 
                    self.consumer_group, 
                    id="0", 
                    mkstream=True
                )
                logger.info(f"✅ Created Redis consumer group: {self.consumer_group}")
            except Exception as e:
                if "BUSYGROUP" in str(e):
                    logger.info(f"✅ Redis consumer group {self.consumer_group} already exists")
                else:
                    logger.warning(f"⚠️ Consumer group issue (non-critical): {e}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Redis: {e}")
            # Don't fail startup - just log the error
            self.redis = None
    
    def _serialize_article(self, article_data: Dict[str, Any]) -> Dict[str, str]:
        """Convert article data to Redis-compatible format (all strings)"""
        serialized = {}
        
        for key, value in article_data.items():
            if value is None:
                serialized[key] = ""
            elif isinstance(value, datetime):
                # Convert datetime to ISO string
                serialized[key] = value.isoformat()
            elif isinstance(value, (int, float, bool)):
                # Convert numbers/booleans to strings
                serialized[key] = str(value)
            elif isinstance(value, str):
                # Keep strings as-is
                serialized[key] = value
            else:
                # Convert any other type to JSON string
                serialized[key] = json.dumps(value)
        
        return serialized
    
    def _deserialize_article(self, fields: Dict[str, str]) -> Dict[str, Any]:
        """Convert Redis fields back to proper Python types"""
        article = {}
        
        for key, value in fields.items():
            if key == "stream_id":
                # Keep stream_id as string
                article[key] = value
            elif key in ["published_at", "scraped_at"]:
                # Convert ISO strings back to datetime
                if value and value != "":
                    try:
                        article[key] = datetime.fromisoformat(value)
                    except ValueError:
                        article[key] = None
                else:
                    article[key] = None
            elif key == "engagement_score":
                # Convert back to float
                try:
                    article[key] = float(value) if value else 0.0
                except ValueError:
                    article[key] = 0.0
            elif key == "is_processed":
                # Convert back to boolean
                article[key] = value.lower() in ("true", "1", "yes")
            elif value == "":
                # Empty strings become None
                article[key] = None
            else:
                # Keep as string or try to parse JSON
                try:
                    # Try to parse as JSON first
                    article[key] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # Keep as string if not valid JSON
                    article[key] = value
        
        return article
    
    async def add_article(self, article_data: Dict[str, Any]):
        """Add article to the stream"""
        if not self.redis:
            logger.warning("Redis not available, skipping article add")
            return None
            
        try:
            # Serialize the article data for Redis
            serialized_data = self._serialize_article(article_data)
            
            message_id = await self.redis.xadd(
                self.stream_name,
                serialized_data
            )
            logger.info(f"Added article to stream: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Error adding article to stream: {e}")
            return None
    
    async def read_articles(self, count: int = 10) -> List[Dict[str, Any]]:
        """Read unprocessed articles from stream"""
        if not self.redis:
            return []
            
        try:
            messages = await self.redis.xreadgroup(
                self.consumer_group,
                self.consumer_name,
                {self.stream_name: ">"},
                count=count,
                block=1000  # 1 second timeout
            )
            
            articles = []
            for stream, msgs in messages:
                for msg_id, fields in msgs:
                    # Deserialize the article data
                    article = self._deserialize_article(fields)
                    article["stream_id"] = msg_id
                    articles.append(article)
            
            return articles
        except Exception as e:
            logger.error(f"Error reading from stream: {e}")
            return []
    
    async def acknowledge_article(self, message_id: str):
        """Acknowledge processed article"""
        if not self.redis:
            return
            
        try:
            await self.redis.xack(
                self.stream_name,
                self.consumer_group,
                message_id
            )
        except Exception as e:
            logger.error(f"Error acknowledging message: {e}")
    
    async def get_pending_count(self) -> int:
        """Get count of pending messages"""
        if not self.redis:
            return 0
            
        try:
            info = await self.redis.xpending(self.stream_name, self.consumer_group)
            return info["pending"]
        except Exception as e:
            logger.error(f"Error getting pending count: {e}")
            return 0
    
    async def get_stream_info(self) -> Dict[str, Any]:
        """Get detailed stream information for debugging"""
        if not self.redis:
            return {"error": "Redis not connected"}
        
        try:
            info = {}
            
            # Stream length
            info["length"] = await self.redis.xlen(self.stream_name)
            
            # Latest entries
            latest = await self.redis.xrevrange(self.stream_name, count=5)
            info["latest_entries"] = len(latest)
            
            # Consumer group info
            try:
                groups = await self.redis.xinfo_groups(self.stream_name)
                info["consumer_groups"] = len(groups)
                if groups:
                    info["pending_messages"] = groups[0].get("pending", 0)
            except:
                info["consumer_groups"] = 0
                info["pending_messages"] = 0
            
            return info
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

# Global instance
news_stream = NewsStream()
