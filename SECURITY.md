# 🔒 Security & Configuration Guide

## 🎯 **Quick Security Setup**

### 1. **Run the Security Setup Script**
```bash
chmod +x setup_security.sh
./setup_security.sh
```

This script will:
- ✅ Enable password protection
- ✅ Generate secure credentials  
- ✅ Configure session security
- ✅ Set up news sources
- ✅ Provide security recommendations

### 2. **Manual Configuration (Alternative)**

If you prefer manual setup, edit your `.env` file:

```bash
# Copy example configuration
cp .env.example .env

# Edit the security settings
nano .env
```

Add these security settings:
```bash
# Enable password protection
ENABLE_AUTH=true
AUTH_USERNAME=admin
AUTH_PASSWORD=your-secure-password-here
SESSION_SECRET=your-long-random-secret-key-here
```

---

## 🔐 **Authentication & Password Protection**

### **Features:**
- 🔒 **Session-based authentication** with secure cookies
- 🛡️ **Bcrypt password hashing** for production security
- ⏰ **24-hour session expiration** with auto-refresh
- 🚫 **Automatic logout** on session timeout
- 📱 **Mobile-responsive login page**

### **Enable Authentication:**
1. Set `ENABLE_AUTH=true` in `.env`
2. Configure `AUTH_USERNAME` and `AUTH_PASSWORD`
3. Set a secure `SESSION_SECRET` (64+ character random string)
4. Restart: `docker-compose restart app`

### **Access Control:**
- All routes protected except `/login`, `/logout`, `/health`
- Redirects unauthenticated users to login page
- Secure session cookies with HttpOnly flag
- Protection against CSRF and session hijacking

---

## 🌐 **HTTPS & SSL Security**

### **Automatic HTTPS via Cloudflare:**
Your tunnel already provides enterprise-grade security:

- ✅ **Automatic SSL certificates**
- ✅ **TLS 1.3 encryption** 
- ✅ **DDoS protection**
- ✅ **Bot mitigation**
- ✅ **Global CDN** with edge security

### **Production HTTPS Setup:**
If deploying elsewhere, update `app/auth.py`:
```python
response.set_cookie(
    key="session_token", 
    value=token, 
    httponly=True, 
    secure=True,      # Enable for HTTPS
    samesite="strict" # Stricter CSRF protection
)
```

---

## 📰 **Configurable News Sources**

### **YAML Configuration System:**
Sources are now managed in `config/sources.yaml`:

```yaml
mainstream_sources:
  - name: "BBC World"
    url: "https://feeds.bbci.co.uk/news/world/rss.xml"
    category: "world"
    enabled: true

tech_sources:
  - name: "Ars Technica"
    url: "https://arstechnica.com/feed/"
    category: "tech"
    enabled: true

custom_sources:
  - name: "Your Custom Feed"
    url: "https://example.com/feed.rss"
    category: "custom"
    enabled: true
```

### **Adding New Sources:**
1. Edit `config/sources.yaml`
2. Add your RSS feed or Reddit subreddit
3. Set `enabled: true`
4. Restart: `docker-compose restart app`
5. Sources reload automatically

### **Source Categories:**
- `mainstream_sources` - Major news outlets
- `tech_sources` - Technology publications
- `swiss_sources` - Swiss/local news
- `ai_sources` - AI and data science news
- `reddit_sources` - Reddit communities
- `custom_sources` - Your personal feeds

---

## 🛡️ **Container Security**

### **Non-Root Execution:**
The application now runs as user `newsapp` (UID 1000):

```dockerfile
# Creates restricted user
RUN groupadd -r newsapp && useradd -r -g newsapp -u 1000 newsapp
USER newsapp

# Installs packages to user directory
RUN pip install --user --no-cache-dir -r requirements.txt
```

### **Security Benefits:**
- ✅ **No root privileges** inside container
- ✅ **Limited file system access**
- ✅ **Reduced attack surface**
- ✅ **Process isolation**
- ✅ **Resource limitations**

### **File Permissions:**
```bash
# All app files owned by newsapp user
COPY --chown=newsapp:newsapp . .

# Directories created with proper permissions
RUN mkdir -p static config
```

---

## 🔧 **Advanced Security Configuration**

### **Database Security:**
Update `docker-compose.yml` with secure credentials:
```yaml
environment:
  POSTGRES_USER: your_secure_user
  POSTGRES_PASSWORD: your_secure_password_here
  POSTGRES_DB: newsdigest
```

### **Redis Security:**
For production, enable Redis authentication:
```yaml
redis:
  image: redis:7-alpine
  command: redis-server --requirepass your_redis_password
```

### **Network Security:**
Limit exposed ports in production:
```yaml
services:
  app:
    ports:
      - "127.0.0.1:8000:8000"  # Only localhost access
```

### **Environment Variables:**
Never commit sensitive data:
```bash
# Use strong, unique passwords
AUTH_PASSWORD=$(openssl rand -base64 32)
SESSION_SECRET=$(openssl rand -base64 64)
DB_PASSWORD=$(openssl rand -base64 16)
```

---

## 🚨 **Security Monitoring**

### **Access Logs:**
Monitor authentication attempts:
```bash
# View login attempts
docker-compose logs app | grep "login\|auth"

# Failed authentication attempts
docker-compose logs app | grep "Failed login"

# Session activity
docker-compose logs app | grep "session"
```

### **Health Monitoring:**
```bash
# System health
curl http://localhost:8000/health

# Debug information (authenticated users only)
curl http://localhost:8000/debug/status
```

### **Security Headers:**
The application includes security headers:
- `HttpOnly` cookies prevent XSS
- `SameSite` cookies prevent CSRF
- Session validation on every request
- Automatic session cleanup

---

## ✅ **Security Checklist**

### **Basic Security:**
- [ ] Password protection enabled
- [ ] Strong, unique passwords set
- [ ] Session secret configured  
- [ ] Non-root container user
- [ ] HTTPS via Cloudflare tunnel

### **Production Security:**
- [ ] Database credentials changed
- [ ] Redis authentication enabled
- [ ] Regular security updates scheduled
- [ ] Access logs monitored
- [ ] Backup strategy implemented

### **Advanced Security:**
- [ ] Fail2ban for brute force protection
- [ ] IP allowlisting in Cloudflare
- [ ] WAF rules configured
- [ ] Rate limiting enabled
- [ ] Security headers validated

---

## 🆘 **Security Troubleshooting**

### **Can't Login:**
```bash
# Check auth settings
grep -E "ENABLE_AUTH|AUTH_" .env

# Verify password format
echo "Plain text passwords should not start with $2b$"

# Reset session storage
docker-compose restart app
```

### **Session Issues:**
```bash
# Clear browser cookies
# Or restart the app to clear server sessions
docker-compose restart app
```

### **HTTPS Problems:**
- Cloudflare tunnel provides automatic HTTPS
- Verify tunnel is running: `cloudflared tunnel list`
- Check DNS: `dig news.yourdomain.com`

---

## 🎉 **You're Secure!**

With these configurations, your News Digest Agent has:

- 🔒 **Enterprise-grade authentication**
- 🛡️ **Container-level isolation** 
- 🌐 **Automatic HTTPS encryption**
- 📰 **Flexible source management**
- 📊 **Comprehensive monitoring**

Your personal news intelligence system is now secure and ready for global access! 🚀

