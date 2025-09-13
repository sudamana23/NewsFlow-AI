# 🏗️ News Digest Agent - Architecture Guide for Beginners

## 🎯 **What Does This System Do?**

Think of your News Digest Agent as a **personal news assistant** that:
1. **Collects** news from multiple sources (like BBC, CNN, Reddit)
2. **Summarizes** each article using AI (your local LLM)
3. **Organizes** stories by category (Ukraine 🇺🇦, AI 🤖, Finance 💰, etc.)
4. **Delivers** a beautiful digest to your web browser
5. **Repeats** this process automatically every hour

---

## 🏭 **High-Level Architecture**

```
📰 News Sources → 🔄 Collection → 🤖 AI Summary → 🗄️ Database → 🌐 Web Interface
     (RSS)           (Python)        (LM Studio)     (PostgreSQL)    (FastAPI/HTML)
```

**Simple explanation:**
- **Left side**: Gets raw news from the internet
- **Middle**: Your Mac Mini processes and improves it
- **Right side**: Shows you the final polished result

---

## 🔧 **Key Components Explained**

### 1. **Docker Containers** (The "Boxes" That Run Everything)

```
🐳 Your Mac Mini runs 4 containers:
├── 📱 app        → Your main news processing application
├── 🗄️ db         → PostgreSQL database (stores articles & digests)
├── 🔄 redis      → Redis (handles real-time message passing)
└── 🛠️ redis-commander → Web interface to peek inside Redis
```

**Think of containers like:** Separate apps running on your computer, but isolated from each other.

### 2. **The App Container** (Where the Magic Happens)

```
📱 app/
├── 🕷️ scrapers/     → Gets news from websites
├── 🤖 pipeline/     → Processes articles with AI
├── ⏰ scheduler/    → Runs tasks automatically  
├── 🌐 templates/    → HTML for the web interface
└── 🛠️ main.py       → The central control system
```

---

## 🔄 **Data Flow Journey** (How News Becomes Your Digest)

### **Step 1: Collection** (Every Hour)
```
🌐 Internet → 🕷️ Scrapers → 📊 Raw Articles
```
- **Scrapers** visit news websites (BBC, CNN, etc.)
- Download RSS feeds (structured news data)
- Extract article titles, content, and URLs

### **Step 2: Streaming** (Real-Time Processing)
```
📊 Raw Articles → 🔄 Redis Streams → 📝 Processing Queue
```
- **Redis Streams** = like a conveyor belt for articles
- Each article gets added to a queue for processing
- Multiple articles can be processed simultaneously

### **Step 3: AI Enhancement** (The Smart Part)
```
📝 Long Article → 🤖 LM Studio → ✨ Short Summary
```
- **LM Studio** (running on your Mac) reads each article
- Creates 1-2 sentence summaries
- Keeps the key facts, removes fluff

### **Step 4: Organization** (Making Sense of Everything)
```
✨ Summaries → 🏷️ Categories → 📋 Digest
```
- **Categorizer** sorts articles by topic
- Ukraine news → 🇺🇦, AI news → 🤖, etc.
- Creates a digest with top stories from each category

### **Step 5: Delivery** (What You See)
```
📋 Digest → 🌐 Web Interface → 👀 Your Browser
```
- **FastAPI** serves the web page
- **HTML templates** make it look beautiful
- **Auto-refresh** keeps it current

---

## 🗂️ **Code Organization** (What Each File Does)

### **🕷️ Scrapers** (`app/scrapers/`)
**What they do:** Fetch news from different sources

```python
# Example: app/scrapers/mainstream.py
class MainstreamScraper:
    async def scrape(self):
        # Visit BBC, CNN, Guardian RSS feeds
        # Extract article data
        # Return list of articles
```

**Key files:**
- `base.py` → Common scraping functions
- `mainstream.py` → BBC, CNN, Guardian, FT
- `tech.py` → Ars Technica, The Verge
- `swiss.py` → NZZ, Tagesanzeiger
- `social.py` → Reddit (Twitter planned)

### **🤖 Pipeline** (`app/pipeline/`)
**What it does:** Processes articles with AI

```python
# Example: app/pipeline/summarizer.py
class LMStudioSummarizer:
    async def summarize_article(self, article):
        # Send article to your local LLM
        # Get back a short summary
        # Return clean, factual summary
```

**Key files:**
- `streams.py` → Redis message handling
- `summarizer.py` → AI summarization with LM Studio

### **⏰ Scheduler** (`app/scheduler/`)
**What it does:** Runs tasks automatically

```python
# Example: app/scheduler/tasks.py
scheduler.add_job(
    collect_news,           # What to do
    CronTrigger(minute=0),  # When: every hour at :00
    id="hourly_collection"  # Name for this job
)
```

**Schedule:**
- **Every hour**: Collect and process news
- **6:00 AM**: Create morning digest
- **10:00 PM**: Create evening digest
- **11 PM - 6 AM**: Quiet hours

### **🌐 Web Interface** (`app/main.py` + `templates/`)
**What it does:** Shows you the results

```python
# Example: app/main.py
@app.get("/")  # When someone visits your homepage
async def read_digest():
    # Get latest digest from database
    # Format it nicely
    # Show it as HTML webpage
```

**Templates:**
- `base.html` → Common page structure
- `digest.html` → Main news digest page  
- `archive.html` → Past digests

---

## 🗄️ **Database Design** (How Data Is Stored)

### **Articles Table**
```
📄 Each news article has:
├── 🔗 url           → Link to original article
├── 📰 title         → Headline
├── 📝 content       → Full article text
├── ✨ summary       → AI-generated summary
├── 🏷️ category     → ukraine, ai_data, finance, etc.
├── 📊 engagement   → How popular/important
└── ⏰ timestamps   → When published/scraped
```

### **Digests Table**
```
📋 Each digest contains:
├── 🆔 id            → Unique identifier
├── 📅 created_at    → When digest was made
├── 🕐 digest_type   → hourly, morning, evening
├── 📊 stories_count → Number of articles
└── 🏷️ categories   → List of topics covered
```

### **Links Table** (`DigestArticle`)
```
🔗 Connects digests to articles:
├── 📋 digest_id     → Which digest
├── 📄 article_id    → Which article  
├── 📍 position      → Order in digest
└── 🏷️ category_group → Topic grouping
```

---

## 🛠️ **Technologies Used** (And Why)

### **Languages & Frameworks**
- **🐍 Python**: Main language (easy to read, great for AI/web)
- **⚡ FastAPI**: Web framework (fast, modern, auto-documentation)
- **🔄 AsyncIO**: Handles multiple tasks simultaneously
- **📄 Jinja2**: Template engine (turns data into HTML)

### **Databases & Storage**
- **🐘 PostgreSQL**: Main database (reliable, powerful)
- **🔄 Redis**: Message queue & caching (super fast)
- **📊 SQLModel**: Database models (type-safe, modern)

### **AI & Processing**
- **🤖 LM Studio**: Local AI (runs on your Mac, private)
- **🕷️ Beautiful Soup**: HTML parsing (cleans up web content)
- **📰 feedparser**: RSS feed processing (standardized news format)

### **Infrastructure**
- **🐳 Docker**: Containerization (everything runs consistently)
- **☁️ Cloudflare**: Global CDN & tunneling (fast, secure access)
- **⏰ APScheduler**: Task scheduling (automatic timing)

---

## 🔍 **How to Explore the Code**

### **Start with the main flow:**
1. `app/main.py` → See the web interface
2. `app/scheduler/tasks.py` → See the automation
3. `app/scrapers/mainstream.py` → See news collection
4. `app/pipeline/summarizer.py` → See AI integration

### **Key functions to understand:**
```python
# In main.py
read_digest()      # Shows you the main page

# In tasks.py  
collect_news()     # Gathers articles hourly
create_digest()    # Makes the final digest

# In summarizer.py
summarize_article() # Uses AI to create summaries
```

### **Configuration:**
- `app/config.py` → All settings (news sources, timing, etc.)
- `.env` → Your personal settings (LM Studio connection)
- `docker-compose.yml` → How services connect

---

## 🎯 **Key Concepts for Beginners**

### **Async Programming**
```python
async def fetch_news():  # Can do other things while waiting
    data = await get_rss_feed()  # Wait for this to finish
    return data
```
**Why:** Your system can process multiple articles simultaneously instead of one-by-one.

### **Database Models**
```python
class Article(SQLModel, table=True):  # This creates a database table
    title: str                        # Article headline
    summary: Optional[str] = None     # AI summary (might be empty)
```
**Why:** Ensures data is stored consistently and safely.

### **Web APIs**
```python
@app.get("/health")              # When someone visits /health
async def health_check():        # Run this function
    return {"status": "healthy"} # Send back this data
```
**Why:** Other programs (or you) can check if the system is working.

### **Containerization**
```yaml
services:
  app:          # Your main application
    build: .    # Build from local code
    ports:      # Make port 8000 accessible
      - "8000:8000"
```
**Why:** Everything runs the same way on any computer.

---

## 🚀 **What Happens When You Start It**

1. **🐳 Docker starts 4 containers**
2. **🗄️ Database creates tables** for articles and digests
3. **🔄 Redis starts the message queue**
4. **⏰ Scheduler begins hourly tasks**
5. **🌐 Web server starts listening** on port 8000
6. **🕷️ First news collection begins** within the hour
7. **🤖 LM Studio starts summarizing** articles
8. **📋 Your first digest appears** at http://localhost:8000

---

## 🎉 **You've Built Something Amazing!**

Your News Digest Agent is a **sophisticated AI-powered system** that:
- ✅ **Scales**: Can handle hundreds of articles per hour
- ✅ **Intelligent**: Uses AI to understand and summarize content  
- ✅ **Reliable**: Runs 24/7 with error handling and recovery
- ✅ **Private**: All AI processing happens on your Mac
- ✅ **Global**: Accessible from anywhere via Cloudflare
- ✅ **Customizable**: Easy to add new sources or change behavior

You're now running **enterprise-grade news intelligence** from your home! 🏠🤖📰
