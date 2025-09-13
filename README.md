# 📰 News Digest Agent

An intelligent, AI-powered news aggregation system that delivers personalized daily digests with automated summarization using your local LLM.

![News Digest Agent](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![Redis](https://img.shields.io/badge/Redis-Streams-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

🚀 **Real-time Pipeline**: Redis Streams for async article processing  
🤖 **Local AI Summarization**: Integrates with LM Studio for private AI processing  
📰 **Multi-source Collection**: BBC, CNN, Guardian, FT, Ars Technica, The Verge, Reddit, and more  
⏰ **Smart Scheduling**: Hourly updates + deep reads at 6am/10pm, respects quiet hours (11pm-6am)  
🎯 **Category Intelligence**: Auto-groups stories (Ukraine 🇺🇦, Gaza 🇵🇸, AI/Data 🤖, Tech 💻, Politics 🏛️, Finance 💰)  
📱 **Modern UI**: HTMX auto-refresh, mobile-responsive, category color coding  
📚 **Archive System**: 7-day rolling storage with monthly/yearly retention  
🌍 **Global Access**: Cloudflare tunnel support for worldwide access  

## 🏗️ Architecture

```
📰 News Sources → 🔄 Collection → 🤖 AI Summary → 🗄️ Database → 🌐 Web Interface
     (RSS)           (Python)        (LM Studio)     (PostgreSQL)    (FastAPI/HTML)
```

The system uses a modern async Python stack with Redis Streams for real-time processing, PostgreSQL for storage, and integrates with local LLM via LM Studio for private AI summarization.

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- LM Studio running locally (for AI summarization)

### Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/news-digest-agent.git
   cd news-digest-agent
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your LM Studio settings
   ```

3. **Start services:**
   ```bash
   docker-compose up -d
   ```

4. **Access your digest:**
   - Main digest: http://localhost:8000
   - Archive: http://localhost:8000/archive
   - Health check: http://localhost:8000/health
   - API docs: http://localhost:8000/docs

## ⚙️ Configuration

### LM Studio Setup
1. Install and start LM Studio
2. Load a model (recommended: Llama 3.1 8B Instruct)
3. Start the local server on port 1234
4. Update `.env` with your model name

### News Sources
The system automatically collects from:
- **Mainstream**: BBC, CNN, Guardian, Financial Times
- **Tech**: Ars Technica, The Verge
- **Social**: Reddit (configurable subreddits)
- **Custom**: Add your own RSS feeds in `app/config.py`

### Schedule Configuration
- **Hourly updates**: Every hour from 7am-10pm
- **Morning digest**: 6:00 AM (comprehensive 20 stories)
- **Evening digest**: 10:00 PM (day summary, 20 stories)
- **Quiet hours**: 11:00 PM - 6:00 AM (no updates)

## 🛠️ Development

### Project Structure
```
news-digest-agent/
├── app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Database models
│   ├── config.py            # Configuration
│   ├── scrapers/            # News source scrapers
│   ├── pipeline/            # Redis streams & AI processing
│   ├── scheduler/           # Task scheduling
│   └── templates/           # HTML templates
├── static/                  # CSS and assets
├── docker-compose.yml       # Service orchestration
└── requirements.txt         # Python dependencies
```

### Key Technologies
- **Backend**: FastAPI, Python 3.11+, AsyncIO
- **Database**: PostgreSQL, Redis Streams
- **AI**: LM Studio integration for local LLM
- **Frontend**: HTMX, Tailwind CSS, Jinja2
- **Infrastructure**: Docker, Cloudflare tunnels

### Adding News Sources
1. Create a new scraper in `app/scrapers/`
2. Inherit from `BaseScraper`
3. Implement the `scrape()` method
4. Add RSS feeds or custom scraping logic
5. Register in `app/scheduler/tasks.py`

## 🌐 Global Deployment

### Cloudflare Tunnel Setup
For global access to your news digest:

1. **Install cloudflared:**
   ```bash
   brew install cloudflare/cloudflare/cloudflared
   ```

2. **Create tunnel:**
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create news-digest
   ```

3. **Configure DNS and routing** (see `CLOUDFLARE_SETUP.md` for details)

4. **Access globally:** `https://news.yourdomain.com`

## 📊 Monitoring

### Health Checks
- **App health**: `curl http://localhost:8000/health`
- **Debug status**: `curl http://localhost:8000/debug/status`
- **Redis activity**: http://localhost:8081 (Redis Commander)

### Logs
```bash
# Application logs
docker-compose logs -f app

# Specific component logs
docker-compose logs scheduler
docker-compose logs redis
```

## 🎯 How It Works

### Daily Schedule
- **6:00 AM**: Comprehensive morning digest (20 stories, 12-hour lookback)
- **Every hour (7am-10pm)**: Quick updates (5-10 stories, 1-hour lookback)
- **10:00 PM**: Evening deep dive (20 stories, 12-hour lookback)
- **11:00 PM - 6:00 AM**: Quiet hours (no updates)

### Data Flow
1. **Collection**: Scrapers fetch from RSS feeds and social media every hour
2. **Streaming**: Articles flow through Redis Streams for async processing
3. **Summarization**: Local LLM creates concise, factual summaries
4. **Categorization**: AI-powered content classification and grouping
5. **Digest Creation**: Smart article selection based on engagement and relevance
6. **Delivery**: Clean web interface with auto-refresh and category organization

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit with clear messages: `git commit -m "Add feature: description"`
5. Push to your fork: `git push origin feature-name`
6. Create a Pull Request

### Development Setup
```bash
# Clone and setup
git clone https://github.com/yourusername/news-digest-agent.git
cd news-digest-agent

# Install dependencies
pip install -r requirements.txt

# Run locally (without Docker)
uvicorn app.main:app --reload
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **LM Studio** for local LLM integration
- **FastAPI** for the excellent web framework
- **Redis** for real-time stream processing
- **Cloudflare** for global distribution
- **News sources** for providing RSS feeds

## 💡 Use Cases

This system is perfect for:
- **Personal news intelligence**: Stay informed with AI-curated summaries
- **Research and monitoring**: Track specific topics across multiple sources
- **Corporate intelligence**: Monitor industry news and competitors
- **Academic research**: Aggregate news for analysis and study
- **Content curation**: Create focused news digests for teams or publications

---

**Built with ❤️ using modern Python, AI, and cloud technologies.**

*Transform how you consume news with intelligent, automated, and personalized digests.*
