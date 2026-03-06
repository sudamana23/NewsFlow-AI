import asyncio
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import json
import logging
import pytz
import httpx
from bs4 import BeautifulSoup

from app.database import get_async_session, create_db_and_tables, AsyncSessionLocal
from app.models import Article, Digest, DigestArticle, StoryCategory
from app.pipeline.streams import news_stream
from app.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="News Digest Agent", version="1.0.0")

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Timezone setup
CET = pytz.timezone('Europe/Zurich')  # CET/CEST timezone

def convert_to_cet(dt):
    """Convert UTC datetime to CET"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(CET)

_STOPWORDS = {
    # Articles, prepositions, conjunctions
    "the","a","an","in","on","of","to","for","and","or","is","are","was","were",
    "be","been","being","have","has","had","do","does","did","will","would",
    "could","should","may","might","can","with","at","by","from","as","it",
    "its","this","that","these","those","not","but","if","than","then","so",
    "up","out","new","over","into","about","after","before","between","more",
    # Common headline words
    "us","uk","eu","says","say","said","report","reports","how","why","what",
    "who","when","where","amid","since","per","via","just","gets","want","make",
    "here","your","their","they","them","some","much","very","well","will",
    "first","last","also","still","back","over","after","says","come","goes",
    # Reddit-specific noise
    "thread","threads","part","time","year","years","week","month","daily",
    "worldnews","subreddit","reddit","comments","upvotes","post","posts",
    "news","world","today","days","hours","breaking","update","updates",
    "watch","start","stop","look","like","need","take","know","tell","show",
    "call","plan","plan","deal","move","rise","fall","hold","keep","push",
}

def _compute_trending_topics(titles: list, top_n: int = 20, min_count: int = 2) -> list:
    """Compute top keywords from a list of article titles."""
    from collections import Counter
    import re
    counts: Counter = Counter()
    for title in titles:
        words = re.findall(r"[a-zA-Z]{4,}", title.lower())
        for w in words:
            if w not in _STOPWORDS:
                counts[w] += 1
    return [{"word": w.title(), "count": c} for w, c in counts.most_common(top_n) if c >= min_count]

# ── SEP cache ─────────────────────────────────────────────────────────────────
_sep_cache: dict = {}          # keys: "entry", "fetched_at"
_SEP_CACHE_TTL = timedelta(hours=2)

async def fetch_sep_entry() -> dict | None:
    """Fetch a random Stanford Encyclopedia of Philosophy entry (cached 2 h)."""
    global _sep_cache
    # Return cached entry if still fresh
    if _sep_cache.get("entry") and _sep_cache.get("fetched_at"):
        if datetime.utcnow() - _sep_cache["fetched_at"] < _SEP_CACHE_TTL:
            return _sep_cache["entry"]

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": "NewsFlow-AI/1.0 (educational digest reader)"},
        ) as client:
            resp = await client.get("https://plato.stanford.edu/cgi-bin/encyclopedia/random")
            if resp.status_code != 200:
                return _sep_cache.get("entry")   # serve stale on failure

            soup = BeautifulSoup(resp.text, "html.parser")

            # Title — SEP uses <h1> with the entry name
            title_el = (
                soup.find("h1", id="entry-title")
                or soup.find("h1")
            )
            title = title_el.get_text(strip=True) if title_el else "Philosophy"

            # Preamble — the paragraph(s) before the Table of Contents
            excerpt = ""
            preamble = (
                soup.find("div", id="preamble")
                or soup.find("section", id="preamble")
            )
            if preamble:
                first_p = preamble.find("p")
                excerpt = first_p.get_text(strip=True) if first_p else ""
            if not excerpt:
                # Fallback: first <p> inside #main-text or #content
                container = soup.find("div", id="main-text") or soup.find("div", id="content")
                if container:
                    first_p = container.find("p")
                    excerpt = first_p.get_text(strip=True) if first_p else ""

            # Keep excerpt to ~280 chars, cutting at a word boundary
            if len(excerpt) > 280:
                excerpt = excerpt[:280].rsplit(" ", 1)[0].rstrip(".,;:") + "…"

            entry = {
                "title": title,
                "excerpt": excerpt,
                "url": str(resp.url),
            }
            _sep_cache = {"entry": entry, "fetched_at": datetime.utcnow()}
            logger.info(f"📚 SEP entry fetched: {title}")
            return entry

    except Exception as e:
        logger.warning(f"⚠️ SEP fetch failed: {e}")
        return _sep_cache.get("entry")   # serve stale on failure


async def run_enum_migrations():
    """Add new StoryCategory enum values - must run outside a transaction."""
    import asyncpg
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    # SQLAlchemy/SQLModel stores enums by Python attribute name (uppercase), not value
    new_values = ["HEALTH", "SCIENCE", "CLIMATE", "GEOPOLITICS", "CRYPTO", "EUROPE", "SPORTS", "PHILOSOPHY", "NEUROSCIENCE"]
    try:
        conn = await asyncpg.connect(db_url)
        for value in new_values:
            try:
                await conn.execute(f"ALTER TYPE storycategory ADD VALUE IF NOT EXISTS '{value}'")
            except Exception:
                pass
        await conn.close()
        logger.info("✅ DB enum migrations complete")
    except Exception as e:
        logger.warning(f"⚠️ DB enum migration skipped (non-critical): {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize app on startup"""
    try:
        logger.info("🚀 Starting News Digest Agent...")

        # Initialize database (critical)
        await create_db_and_tables()
        logger.info("✅ Database tables created")

        # Run enum migrations to add new category values
        await run_enum_migrations()

        # Initialize Redis streams (non-critical)
        try:
            await news_stream.initialize()
            logger.info("✅ Redis streams initialized")
        except Exception as e:
            logger.warning(f"⚠️ Redis initialization failed (non-critical): {e}")

        # Initialize scheduler (non-critical)
        try:
            from app.scheduler.tasks import scheduler
            scheduler.start()
            logger.info("✅ Scheduler started")
        except Exception as e:
            logger.warning(f"⚠️ Scheduler initialization failed (non-critical): {e}")

        logger.info("🎉 App initialized successfully!")

    except Exception as e:
        logger.error(f"❌ Critical startup error: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        from app.scheduler.tasks import scheduler
        scheduler.shutdown()
    except:
        pass
    
    try:
        await news_stream.close()
    except:
        pass
    
    logger.info("🛑 App shutdown complete")

@app.get("/", response_class=HTMLResponse)
async def read_digest(
    request: Request,
    digest_type: str = "current",
    db: AsyncSession = Depends(get_async_session)
):
    """Main digest page"""

    try:
        # 1. Get the latest digest (or none)
        if digest_type == "current":
            result = await db.execute(
                select(Digest).order_by(desc(Digest.created_at)).limit(1)
            )
            digest = result.scalar_one_or_none()
        else:
            digest = None

        if not digest:
            sep_entry = await fetch_sep_entry()
            return templates.TemplateResponse(
                "digest.html",
                {
                    "request": request,
                    "digest": None,
                    "categories": {},
                    "hero_articles": [],
                    "social_articles": [],
                    "geopolitics_articles": [],
                    "trending_topics": [],
                    "sep_entry": sep_entry,
                    "message": "🚀 News Digest Agent is online! No digest yet. Check back soon.",
                    "is_deep_read": False
                }
            )

        digest_cet = convert_to_cet(digest.created_at)

        # 2. Load the articles for this digest
        result = await db.execute(
            select(Article, DigestArticle)
            .join(DigestArticle, Article.id == DigestArticle.article_id)
            .where(DigestArticle.digest_id == digest.id)
            .order_by(DigestArticle.position)
        )

        rows = result.all()

        # 3. Wrap each into the shape your template expects
        categories = {}
        for article, digest_article in rows:
            published_cet = convert_to_cet(article.published_at) if article.published_at else None
            item = {
                "article": article,
                "published_cet": published_cet,
                "position": digest_article.position,
                "category_group": digest_article.category_group,
            }
            cat = article.category or "world"
            categories.setdefault(cat, []).append(item)

        # 4. Hero articles — top 5 by engagement from last 24h
        since_24h = datetime.utcnow() - timedelta(hours=24)
        hero_result = await db.execute(
            select(Article)
            .where(Article.scraped_at >= since_24h)
            .where(Article.is_processed == True)
            .order_by(Article.engagement_score.desc(), Article.scraped_at.desc())
            .limit(5)
        )
        hero_articles = [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "summary": a.summary,
                "category": a.category or "world",
                "published_cet": convert_to_cet(a.published_at) if a.published_at else None,
            }
            for a in hero_result.scalars().all()
        ]

        # 5. Social articles — Reddit posts from last 24h
        social_result = await db.execute(
            select(Article)
            .where(Article.source.like("r/%"))
            .where(Article.scraped_at >= since_24h)
            .order_by(Article.scraped_at.desc())
            .limit(8)
        )
        social_articles = [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "published_cet": convert_to_cet(a.published_at) if a.published_at else None,
            }
            for a in social_result.scalars().all()
        ]

        # 6. Geopolitics articles — analysis/conflicts card
        geo_result = await db.execute(
            select(Article)
            .where(Article.category == "geopolitics")
            .where(Article.scraped_at >= since_24h)
            .order_by(Article.scraped_at.desc())
            .limit(6)
        )
        geopolitics_articles = [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "summary": a.summary,
                "published_cet": convert_to_cet(a.published_at) if a.published_at else None,
            }
            for a in geo_result.scalars().all()
        ]

        # 7. Trending topics — word frequency from Reddit article titles
        #    Use a 48-hour window and a low min-count so we get useful chips
        #    even when reddit article volume is low.
        since_48h = datetime.utcnow() - timedelta(hours=48)
        reddit_titles_result = await db.execute(
            select(Article.title)
            .where(Article.source.like("r/%"))
            .where(Article.scraped_at >= since_48h)
            .limit(200)
        )
        reddit_titles = [row[0] for row in reddit_titles_result.all()]

        # If we have too few Reddit titles, fall back to all sources
        if len(reddit_titles) < 10:
            all_titles_result = await db.execute(
                select(Article.title)
                .where(Article.scraped_at >= since_48h)
                .limit(300)
            )
            trending_topics = _compute_trending_topics(
                [row[0] for row in all_titles_result.all()], min_count=2
            )
        else:
            trending_topics = _compute_trending_topics(reddit_titles, min_count=1)

        # 8. SEP random philosophy entry
        sep_entry = await fetch_sep_entry()

        logger.info(
            f"📰 Serving digest: {len(rows)} articles, {len(hero_articles)} hero, "
            f"{len(social_articles)} social, {len(geopolitics_articles)} geo, "
            f"{len(trending_topics)} trending, SEP={'yes' if sep_entry else 'no'}"
        )

        return templates.TemplateResponse(
            "digest.html",
            {
                "request": request,
                "digest": digest,
                "digest_cet": digest_cet,
                "categories": categories,
                "hero_articles": hero_articles,
                "social_articles": social_articles,
                "geopolitics_articles": geopolitics_articles,
                "trending_topics": trending_topics,
                "sep_entry": sep_entry,
                "is_deep_read": digest.digest_type in ["morning", "evening"],
            }
        )

    except Exception as e:
        logger.error(f"❌ Error in main route: {e}")
        return templates.TemplateResponse(
            "digest.html",
            {
                "request": request,
                "digest": None,
                "articles": [],
                "categories": {},
                "hero_articles": [],
                "social_articles": [],
                "geopolitics_articles": [],
                "trending_topics": [],
                "sep_entry": _sep_cache.get("entry"),
                "message": "System is starting up. Please refresh in a moment.",
                "is_deep_read": False
            }
        )

@app.get("/api/digest/latest")
async def get_latest_digest(db: AsyncSession = Depends(get_async_session)):
    """API endpoint for latest digest data"""
    
    try:
        result = await db.execute(
            select(Digest)
            .order_by(desc(Digest.created_at))
            .limit(1)
        )
        digest = result.scalar_one_or_none()
        
        if not digest:
            return {"status": "no_digest"}
        
        # Get articles
        result = await db.execute(
            select(Article, DigestArticle)
            .join(DigestArticle, Article.id == DigestArticle.article_id)
            .where(DigestArticle.digest_id == digest.id)
            .order_by(DigestArticle.position)
        )
        
        articles_data = result.all()
        articles = []
        
        for article, digest_article in articles_data:
            # Convert times to CET for API
            published_cet = convert_to_cet(article.published_at) if article.published_at else None
            
            articles.append({
                "id": article.id,
                "title": article.title,
                "summary": article.summary,
                "url": article.url,
                "source": article.source,
                "category": article.category,
                "published_at": published_cet.isoformat() if published_cet else None,
                "engagement_score": article.engagement_score
            })
        
        digest_cet = convert_to_cet(digest.created_at)
        
        return {
            "status": "success",
            "digest": {
                "id": digest.id,
                "created_at": digest_cet.isoformat(),
                "digest_type": digest.digest_type,
                "stories_count": digest.stories_count
            },
            "articles": articles
        }
    except Exception as e:
        logger.error(f"❌ Error in API route: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/archive")
async def view_archive(
    request: Request,
    days: int = 7,
    db: AsyncSession = Depends(get_async_session)
):
    """View digest archive"""
    
    try:
        since_date = datetime.utcnow() - timedelta(days=days)
        
        result = await db.execute(
            select(Digest)
            .where(Digest.created_at >= since_date)
            .order_by(desc(Digest.created_at))
        )
        
        digests = result.scalars().all()
        
        # Convert digest times to CET
        digests_with_cet = []
        for digest in digests:
            digest_cet = convert_to_cet(digest.created_at)
            digests_with_cet.append({
                "digest": digest,
                "created_at_cet": digest_cet
            })
        
        return templates.TemplateResponse(
            "archive.html",
            {
                "request": request,
                "digests": digests_with_cet,
                "days": days
            }
        )
    except Exception as e:
        logger.error(f"❌ Error in archive route: {e}")
        return templates.TemplateResponse(
            "archive.html",
            {
                "request": request,
                "digests": [],
                "days": days
            }
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        async with AsyncSessionLocal() as db:
            await db.execute(select(1))
        
        # Test Redis connection
        redis_status = "connected" if news_stream.redis else "disconnected"
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "database": "connected",
            "redis": redis_status
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.post("/api/refresh")
async def trigger_refresh():
    """Manually trigger news refresh and redirect to main page"""
    try:
        logger.info("🔄 Manual refresh triggered - starting collection...")
        
        # Reload sources configuration first
        from app.config import reload_all_sources
        reload_all_sources()
        logger.info("✅ Sources configuration reloaded")
        
        # Import here to avoid circular imports
        from app.scheduler.tasks import NewsScheduler
        scheduler = NewsScheduler()
        
        # Run collection and processing
        await scheduler.collect_news()
        logger.info("✅ News collection completed")
        
        # Process any articles in the stream
        await scheduler.process_article_stream()
        logger.info("✅ Stream processing completed")
        
        # Create a new digest
        await scheduler.create_digest("manual")
        logger.info("✅ Manual digest created")
        
        # Return success response that will redirect
        return {"status": "success", "message": "News refreshed successfully!", "redirect": "/"}
        
        
    except Exception as e:
        logger.error(f"❌ Error in manual refresh: {e}")
        return {"status": "error", "message": f"Refresh failed: {str(e)}"}

@app.get("/refresh")
async def refresh_page():
    """Simple refresh endpoint that redirects back to main page"""
    try:
        logger.info("🔄 Page refresh via GET - starting collection...")
        
        # Reload sources configuration first
        from app.config import reload_all_sources
        reload_all_sources()
        logger.info("✅ Sources configuration reloaded")
        
        # Import here to avoid circular imports  
        from app.scheduler.tasks import NewsScheduler
        scheduler = NewsScheduler()
        
        # Run collection and processing
        await scheduler.collect_news()
        await scheduler.process_article_stream()
        await scheduler.create_digest("manual")
        
        logger.info("✅ Manual refresh completed, redirecting...")
        
        # Redirect back to main page
        return RedirectResponse(url="/", status_code=302)
        
    except Exception as e:
        logger.error(f"❌ Error in page refresh: {e}")
        # Still redirect even if there's an error
        return RedirectResponse(url="/", status_code=302)

@app.get("/debug/pipeline-test")
async def pipeline_test():
    """Test the full pipeline from collection to database"""
    try:
        from app.scrapers.mainstream import MainstreamScraper
        from app.config import get_mainstream_sources
        from app.pipeline.streams import news_stream
        from app.pipeline.summarizer import summarizer
        from app.database import AsyncSessionLocal
        from app.models import Article
        
        results = {"steps": []}
        
        # Step 1: Collection
        results["steps"].append("1. Testing article collection...")
        sources = get_mainstream_sources()
        scraper = MainstreamScraper()
        
        async with scraper:
            articles = await scraper.fetch_rss(sources[0])
            if articles:
                test_article = articles[0]  # Take first article
                results["steps"].append(f"✅ Collected article: {test_article['title'][:60]}...")
            else:
                results["steps"].append("❌ No articles collected")
                return results
        
        # Step 2: Redis stream
        results["steps"].append("2. Testing Redis stream...")
        try:
            if news_stream.redis:
                message_id = await news_stream.add_article(test_article)
                if message_id:
                    results["steps"].append(f"✅ Added to Redis: {message_id}")
                else:
                    results["steps"].append("❌ Failed to add to Redis")
            else:
                results["steps"].append("❌ Redis not connected")
        except Exception as e:
            results["steps"].append(f"❌ Redis error: {str(e)}")
        
        # Step 3: Stream processing
        results["steps"].append("3. Testing stream processing...")
        try:
            stream_articles = await news_stream.read_articles(count=1)
            if stream_articles:
                stream_article = stream_articles[0]
                results["steps"].append(f"✅ Read from stream: {stream_article.get('title', 'No title')[:60]}...")
                
                # Step 4: Categorization
                results["steps"].append("4. Testing categorization...")
                category, summary = await summarizer.categorize_and_summarize(stream_article)
                results["steps"].append(f"✅ Categorized as: {category}")
                results["steps"].append(f"✅ Summary: {summary[:60]}...")
                
                # Step 5: Database save
                results["steps"].append("5. Testing database save...")
                async with AsyncSessionLocal() as db:
                    article = Article(
                        url=stream_article["url"],
                        title=stream_article["title"],
                        content=stream_article.get("content", ""),
                        summary=summary,
                        source=stream_article["source"],
                        source_type="test",
                        category=category,
                        is_processed=True
                    )
                    db.add(article)
                    await db.commit()
                    results["steps"].append(f"✅ Saved to database: ID {article.id}")
                    
                    # Clean up the test article
                    await news_stream.acknowledge_article(stream_article["stream_id"])
                    results["steps"].append("✅ Acknowledged stream message")
            else:
                results["steps"].append("❌ No articles in stream")
        except Exception as e:
            results["steps"].append(f"❌ Processing error: {str(e)}")
        
        return {"status": "ok", "pipeline_test": results}
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/debug/simple-collection")
async def simple_collection():
    """Test simple collection without Redis/DB complexity"""
    try:
        from app.scrapers.mainstream import MainstreamScraper
        from app.config import get_mainstream_sources
        
        # Get sources
        sources = get_mainstream_sources()
        
        if not sources:
            return {"status": "error", "message": "No mainstream sources configured"}
        
        # Test first source only
        scraper = MainstreamScraper()
        async with scraper:
            # Try to scrape just the first source
            test_source = sources[0]
            articles = await scraper.fetch_rss(test_source)
            
            return {
                "status": "ok",
                "test_source": test_source,
                "articles_scraped": len(articles),
                "sample_articles": [
                    {
                        "title": article.get("title", "No title")[:80],
                        "source": article.get("source", "No source"),
                        "url": article.get("url", "No URL")[:60] + "..."
                    } for article in articles[:3]
                ],
                "total_sources_configured": len(sources)
            }
    except Exception as e:
        import traceback
        return {
            "status": "error", 
            "message": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/debug/collection")
async def debug_collection():
    """Debug news collection process"""
    try:
        from app.scheduler.tasks import NewsScheduler
        from app.config import get_mainstream_sources, get_tech_sources, get_swiss_sources, get_reddit_subreddits
        
        # Check sources configuration
        mainstream_sources = get_mainstream_sources()
        tech_sources = get_tech_sources()
        swiss_sources = get_swiss_sources()
        reddit_sources = get_reddit_subreddits()
        
        # Test a single scraper
        from app.scrapers.mainstream import MainstreamScraper
        
        test_results = {
            "sources_config": {
                "mainstream_count": len(mainstream_sources),
                "tech_count": len(tech_sources),
                "swiss_count": len(swiss_sources),
                "reddit_count": len(reddit_sources),
                "sample_mainstream": mainstream_sources[:3] if mainstream_sources else [],
            },
            "scraper_test": None,
            "collection_test": None
        }
        
        # Test mainstream scraper
        try:
            scraper = MainstreamScraper()
            async with scraper:
                # Try to scrape just one source
                if mainstream_sources:
                    articles = await scraper.fetch_rss(mainstream_sources[0])
                    test_results["scraper_test"] = {
                        "source": mainstream_sources[0],
                        "articles_found": len(articles),
                        "sample_titles": [article.get("title", "No title")[:60] for article in articles[:3]]
                    }
        except Exception as e:
            test_results["scraper_test"] = {"error": str(e)}
        
        # Test full collection process
        try:
            scheduler = NewsScheduler()
            # Don't actually run collection, just check if it would work
            test_results["collection_test"] = "Collection process accessible"
        except Exception as e:
            test_results["collection_test"] = {"error": str(e)}
        
        return {
            "status": "ok",
            "debug_info": test_results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/debug/test-categorization")
async def test_categorization():
    """Test categorization on sample articles"""
    try:
        from app.pipeline.summarizer import summarizer
        
        # Test articles with obvious categories
        test_articles = [
            {
                "title": "Ukraine receives new military aid from NATO allies",
                "content": "Ukraine will receive additional military support from NATO member countries as the conflict with Russia continues.",
                "url": "https://test.com/ukraine",
                "source": "Test Source"
            },
            {
                "title": "OpenAI announces GPT-5 with improved capabilities",
                "content": "OpenAI has revealed details about GPT-5, featuring enhanced artificial intelligence and machine learning capabilities.",
                "url": "https://test.com/ai",
                "source": "Test Source"
            },
            {
                "title": "Manchester United defeats Arsenal in Premier League match",
                "content": "Manchester United secured a 2-1 victory over Arsenal in yesterday's Premier League fixture at Old Trafford.",
                "url": "https://test.com/football",
                "source": "Test Source"
            }
        ]
        
        results = []
        for article in test_articles:
            try:
                category, summary = await summarizer.categorize_and_summarize(article)
                results.append({
                    "title": article["title"],
                    "detected_category": category,
                    "summary": summary[:100] + "..." if len(summary) > 100 else summary
                })
            except Exception as e:
                results.append({
                    "title": article["title"],
                    "error": str(e)
                })
        
        return {
            "status": "ok",
            "test_results": results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/debug/articles")
async def debug_articles(db: AsyncSession = Depends(get_async_session)):
    """Debug what articles exist and their categories"""
    try:
        # Get all recent articles
        result = await db.execute(
            select(Article.id, Article.title, Article.category, Article.source, Article.scraped_at, Article.is_processed)
            .order_by(desc(Article.scraped_at))
            .limit(20)
        )
        
        articles = result.all()
        
        # Get latest digest info
        digest_result = await db.execute(
            select(Digest.id, Digest.created_at, Digest.digest_type, Digest.stories_count)
            .order_by(desc(Digest.created_at))
            .limit(1)
        )
        
        latest_digest = digest_result.first()
        
        # If digest exists, get its articles
        digest_articles = []
        if latest_digest:
            digest_articles_result = await db.execute(
                select(Article.title, Article.category, DigestArticle.position)
                .join(DigestArticle, Article.id == DigestArticle.article_id)
                .where(DigestArticle.digest_id == latest_digest.id)
                .order_by(DigestArticle.position)
            )
            digest_articles = digest_articles_result.all()
        
        return {
            "status": "ok",
            "recent_articles": [
                {
                    "id": article.id,
                    "title": article.title[:80],
                    "category": article.category,
                    "source": article.source,
                    "scraped_at": article.scraped_at.isoformat() if article.scraped_at else None,
                    "is_processed": article.is_processed
                } for article in articles
            ],
            "latest_digest": {
                "id": latest_digest.id if latest_digest else None,
                "created_at": latest_digest.created_at.isoformat() if latest_digest else None,
                "type": latest_digest.digest_type if latest_digest else None,
                "stories_count": latest_digest.stories_count if latest_digest else 0
            } if latest_digest else None,
            "digest_articles": [
                {
                    "title": article[0][:80],
                    "category": article[1],
                    "position": article[2]
                } for article in digest_articles
            ]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/debug/categories")
async def debug_categories(db: AsyncSession = Depends(get_async_session)):
    """Debug category distribution"""
    try:
        # Get recent articles and their categories
        result = await db.execute(
            select(Article.category, Article.title, Article.source)
            .order_by(desc(Article.scraped_at))
            .limit(50)
        )
        
        articles = result.all()
        
        # Count by category
        category_counts = {}
        category_examples = {}
        
        for category, title, source in articles:
            if category not in category_counts:
                category_counts[category] = 0
                category_examples[category] = []
            
            category_counts[category] += 1
            if len(category_examples[category]) < 3:
                category_examples[category].append({"title": title, "source": source})
        
        return {
            "status": "ok",
            "total_recent_articles": len(articles),
            "category_counts": category_counts,
            "category_examples": category_examples,
            "expected_categories": ["ukraine", "gaza", "swiss", "europe", "ai", "tech", "crypto", "finance", "science", "health", "politics", "world", "premier_league"]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/debug/status")
async def debug_status():
    """Debug system status"""
    try:
        # Test database
        async with AsyncSessionLocal() as db:
            article_count = await db.execute(select(Article))
            articles = len(article_count.scalars().all())
            
            digest_count = await db.execute(select(Digest))
            digests = len(digest_count.scalars().all())
        
        # Get Redis info
        redis_info = await news_stream.get_stream_info() if news_stream.redis else {"error": "not connected"}
        
        # Get LM Studio model info
        from app.pipeline.summarizer import summarizer
        model_info = await summarizer.get_model_status()
        
        # Get sources info
        from app.config import source_manager, get_mainstream_sources, get_tech_sources
        mainstream_count = len(get_mainstream_sources())
        tech_count = len(get_tech_sources())
        
        return {
            "status": "ok",
            "database": {
                "connected": True,
                "articles": articles,
                "digests": digests
            },
            "redis": {
                "connected": news_stream.redis is not None,
                "stream_info": redis_info
            },
            "lm_studio": model_info,
            "sources": {
                "mainstream_sources": mainstream_count,
                "tech_sources": tech_count,
                "total_enabled": len(source_manager.get_enabled_sources())
            },
            "components": {
                "database": "✅ Working",
                "redis": "✅ Working" if news_stream.redis else "⚠️ Disconnected",
                "lm_studio": "✅ Working" if model_info.get("is_available") else "⚠️ Disconnected",
                "scheduler": "✅ Working",
                "web_interface": "✅ Working",
                "sources": f"✅ {len(source_manager.get_enabled_sources())} sources loaded"
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
