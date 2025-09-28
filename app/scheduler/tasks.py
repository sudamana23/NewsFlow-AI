import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_
from typing import List, Dict, Any
import logging

from app.database import AsyncSessionLocal
from app.models import Article, Digest, DigestArticle, StoryCategory
from app.scrapers.mainstream import MainstreamScraper
from app.scrapers.social import SocialScraper
from app.scrapers.tech import TechScraper
from app.scrapers.swiss import SwissScraper
from app.pipeline.streams import news_stream
from app.pipeline.summarizer import summarizer
from app.config import settings

logger = logging.getLogger(__name__)

class NewsScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Setup all scheduled jobs"""
        
        # Hourly news collection (except quiet hours)
        self.scheduler.add_job(
            self.collect_news,
            CronTrigger(minute=0),  # Every hour at minute 0
            id="hourly_collection",
            max_instances=1
        )
        
        # Hourly digest creation (except quiet hours)
        self.scheduler.add_job(
            self.create_digest,
            CronTrigger(minute=15),  # 15 minutes after collection
            id="hourly_digest",
            max_instances=1,
            kwargs={"digest_type": "hourly"}
        )
        
        # Morning deep read digest
        self.scheduler.add_job(
            self.create_digest,
            CronTrigger(hour=6, minute=0),
            id="morning_digest",
            max_instances=1,
            kwargs={"digest_type": "morning"}
        )
        
        # Evening deep read digest
        self.scheduler.add_job(
            self.create_digest,
            CronTrigger(hour=22, minute=0),
            id="evening_digest",
            max_instances=1,
            kwargs={"digest_type": "evening"}
        )
        
        # Daily cleanup and archiving
        self.scheduler.add_job(
            self.cleanup_old_data,
            CronTrigger(hour=2, minute=0),  # 2 AM daily
            id="daily_cleanup",
            max_instances=1
        )
        
        # Stream processing (continuous)
        self.scheduler.add_job(
            self.process_article_stream,
            "interval",
            seconds=30,
            id="stream_processor",
            max_instances=1
        )
    
    async def collect_news(self):
        """Collect news from all sources and add to Redis streams"""
        current_hour = datetime.now().hour
        
        # Skip during quiet hours
        if settings.quiet_hours_start <= current_hour or current_hour < settings.quiet_hours_end:
            logger.info(f"Skipping collection during quiet hours: {current_hour}")
            return
        
        logger.info("Starting news collection...")
        
        try:
            all_articles = []
            
            # Collect from all scrapers
            scrapers = [
                MainstreamScraper(),
                TechScraper(),
                SocialScraper(),
                SwissScraper()
            ]
            
            for scraper in scrapers:
                async with scraper:
                    articles = await scraper.scrape()
                    all_articles.extend(articles)
                    logger.info(f"Collected {len(articles)} articles from {scraper.__class__.__name__}")
            
            # Add articles to Redis streams for processing
            added_count = 0
            for article in all_articles:
                try:
                    message_id = await news_stream.add_article(article)
                    if message_id:
                        added_count += 1
                except Exception as e:
                    logger.error(f"Failed to add article to stream: {e}")
            
            logger.info(f"Added {added_count} articles to Redis streams for processing")
            
        except Exception as e:
            logger.error(f"Error in news collection: {e}")
    
    async def process_article_stream(self):
        """Process articles from Redis stream"""
        try:
            articles = await news_stream.read_articles(count=5)
            
            if not articles:
                return
            
            logger.info(f"Processing {len(articles)} articles from Redis stream")
            
            for article_data in articles:
                try:
                    # Start fresh database session for each article
                    async with AsyncSessionLocal() as db:
                        # Check if article already exists
                        existing = await db.execute(
                            select(Article).where(Article.url == article_data["url"])
                        )
                        
                        if existing.scalar_one_or_none():
                            logger.info(f"Article already exists: {article_data['url']}")
                            await news_stream.acknowledge_article(article_data["stream_id"])
                            continue
                        
                        # Summarize and categorize article content with LM Studio
                        category, summary = await summarizer.categorize_and_summarize(article_data)
                        
                        # Ensure published_at is timezone-naive if it exists
                        published_at = article_data.get("published_at")
                        if published_at and hasattr(published_at, 'tzinfo') and published_at.tzinfo:
                            published_at = published_at.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                        
                        # Create article record
                        article = Article(
                            url=article_data["url"],
                            title=article_data["title"],
                            content=article_data.get("content", ""),
                            summary=summary,
                            source=article_data["source"],
                            source_type=article_data["source_type"],
                            category=category,  # Use AI-determined category
                            published_at=published_at,
                            engagement_score=article_data.get("engagement_score", 0.0),
                            is_processed=True
                        )
                        
                        db.add(article)
                        await db.commit()
                        
                        # Acknowledge processing
                        await news_stream.acknowledge_article(article_data["stream_id"])
                        
                        logger.info(f"Processed article: {article.title[:50]}...")
                        
                except Exception as e:
                    logger.error(f"Error processing article: {e}")
                    # Don't acknowledge failed articles so they can be retried
                        
        except Exception as e:
            logger.error(f"Error in stream processing: {e}")
    
    async def create_digest(self, digest_type: str = "hourly"):
        """Create digest from processed articles"""
        current_hour = datetime.now().hour
        
        # Skip hourly digests during quiet hours
        if digest_type == "hourly" and (settings.quiet_hours_start <= current_hour or current_hour < settings.quiet_hours_end):
            return
        
        logger.info(f"Creating {digest_type} digest...")
        
        try:
            async with AsyncSessionLocal() as db:
                # Get time window for articles
                if digest_type == "hourly":
                    since = datetime.utcnow() - timedelta(hours=1)
                elif digest_type in ["morning", "evening"]:
                    since = datetime.utcnow() - timedelta(hours=12)
                else:
                    since = datetime.utcnow() - timedelta(hours=1)
                
                # Get recent processed articles
                result = await db.execute(
                    select(Article)
                    .where(and_(
                        Article.scraped_at >= since,
                        Article.is_processed == True
                    ))
                    .order_by(Article.engagement_score.desc(), Article.scraped_at.desc())
                    .limit(settings.max_stories_per_digest * 2)  # Get more for filtering
                )
                
                articles = result.scalars().all()
                
                if not articles:
                    logger.info("No articles available for digest")
                    return
                
                # Smart article selection
                selected_articles = await self._select_articles_for_digest(articles, digest_type)
                
                if not selected_articles:
                    logger.info("No articles selected for digest")
                    return
                
                # Create digest record
                digest = Digest(
                    digest_type=digest_type,
                    stories_count=len(selected_articles),
                    categories=",".join(set(a.category or "world" for a in selected_articles))
                )
                
                db.add(digest)
                await db.flush()  # Get digest ID
                
                # Add articles to digest
                for i, article in enumerate(selected_articles):
                    digest_article = DigestArticle(
                        digest_id=digest.id,
                        article_id=article.id,
                        position=i,
                        category_group=article.category
                    )
                    db.add(digest_article)
                
                await db.commit()
                
                logger.info(f"Created {digest_type} digest with {len(selected_articles)} articles")
                
        except Exception as e:
            logger.error(f"Error creating digest: {e}")
    
    async def _select_articles_for_digest(self, articles: List[Article], digest_type: str) -> List[Article]:
        """Smart article selection for digest"""
        
        # Group by category
        categories = {}
        for article in articles:
            cat = article.category or "world"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(article)
        
        selected = []
        max_per_category = 5 if digest_type in ["morning", "evening"] else 3
        
        # Priority categories (updated to match new categorization)
        priority_cats = ["ukraine", "gaza", "ai", "tech", "finance", "politics", "premier_league", "swiss", "world"]
        
        for cat in priority_cats:
            if cat in categories:
                # Select top articles from this category
                cat_articles = sorted(
                    categories[cat], 
                    key=lambda x: (x.engagement_score or 0, x.scraped_at), 
                    reverse=True
                )
                selected.extend(cat_articles[:max_per_category])
        
        # Add remaining categories
        for cat, cat_articles in categories.items():
            if cat not in priority_cats:
                selected.extend(cat_articles[:2])
        
        # Final selection and deduplication
        seen_urls = set()
        final_articles = []
        
        for article in selected:
            if article.url not in seen_urls and len(final_articles) < settings.max_stories_per_digest:
                seen_urls.add(article.url)
                final_articles.append(article)
        
        return final_articles
    
    async def cleanup_old_data(self):
        """Clean up old articles and implement archiving strategy"""
        logger.info("Starting daily cleanup...")
        
        try:
            async with AsyncSessionLocal() as db:
                now = datetime.utcnow()
                
                # Delete articles older than 7 days (keep digests)
                week_ago = now - timedelta(days=7)
                await db.execute(
                    delete(Article).where(Article.scraped_at < week_ago)
                )
                
                # Archive digests older than 7 days but keep monthly samples
                # This is a simplified version - you'd implement more sophisticated archiving
                old_digests = await db.execute(
                    select(Digest).where(Digest.created_at < week_ago)
                )
                
                for digest in old_digests.scalars():
                    # Keep one digest per day, then one per month
                    # Implementation depends on your archiving strategy
                    pass
                
                await db.commit()
                logger.info("Cleanup completed")
                
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
    
    def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        logger.info("News scheduler started")
    
    def shutdown(self):
        """Shutdown the scheduler"""
        self.scheduler.shutdown()
        logger.info("News scheduler stopped")

# Global scheduler instance
scheduler = NewsScheduler()
