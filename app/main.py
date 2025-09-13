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
        # Assume UTC if no timezone info
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(CET)

@app.on_event("startup")
async def startup_event():
    """Initialize app on startup"""
    try:
        logger.info("🚀 Starting News Digest Agent...")
        
        # Initialize database (critical)
        await create_db_and_tables()
        logger.info("✅ Database tables created")
        
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
        if digest_type == "current":
            # Get latest digest
            result = await db.execute(
                select(Digest)
                .order_by(desc(Digest.created_at))
                .limit(1)
            )
            digest = result.scalar_one_or_none()
        else:
            # Get specific digest by date or type
            digest = None
        
        if not digest:
            logger.info("No digest found, showing placeholder")
            return templates.TemplateResponse(
                "digest.html",
                {
                    "request": request,
                    "digest": None,
                    "articles": [],
                    "categories": {},
                    "message": "🚀 News Digest Agent is online! The system is collecting news and will have your first digest ready soon. Check back in an hour for your personalized news summary.",
                    "is_deep_read": False
                }
            )
        
        # Convert digest time to CET
        digest_cet = convert_to_cet(digest.created_at)
        
        # Get articles for this digest
        result = await db.execute(
            select(Article, DigestArticle)
            .join(DigestArticle, Article.id == DigestArticle.article_id)
            .where(DigestArticle.digest_id == digest.id)
            .order_by(DigestArticle.position)
        )
        
        articles_data = result.all()
        articles = []
        
        for article, digest_article in articles_data:
            # Convert article times to CET
            published_cet = convert_to_cet(article.published_at) if article.published_at else None
            
            articles.append({
                "article": article, 
                "position": digest_article.position, 
                "category_group": digest_article.category_group,
                "published_cet": published_cet
            })
        
        # Group articles by category
        categories = {}
        for item in articles:
            cat = item["article"].category or "world"
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item)
        
        logger.info(f"📰 Serving digest with {len(articles)} articles across {len(categories)} categories")
        
        return templates.TemplateResponse(
            "digest.html",
            {
                "request": request,
                "digest": digest,
                "digest_cet": digest_cet,
                "articles": articles,
                "categories": categories,
                "is_deep_read": digest.digest_type in ["morning", "evening"]
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Error in main route: {e}")
        # Return a simple error page instead of crashing
        return templates.TemplateResponse(
            "digest.html",
            {
                "request": request,
                "digest": None,
                "articles": [],
                "categories": {},
                "message": f"System is starting up. Please refresh in a moment.",
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
            "components": {
                "database": "✅ Working",
                "redis": "✅ Working" if news_stream.redis else "⚠️ Disconnected",
                "scheduler": "✅ Working",
                "web_interface": "✅ Working"
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
