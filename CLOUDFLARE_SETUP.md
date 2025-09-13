# 🌐 Cloudflare Tunnel Setup Guide

## 📋 **Prerequisites**
- ✅ Cloudflare account with your domain
- ✅ News Digest Agent running on `localhost:8000`
- ✅ Server with stable internet connection

---

## 🔧 **Step-by-Step Setup**

### **1. Install Cloudflare Tunnel**
```bash
# Install via Homebrew (macOS)
brew install cloudflare/cloudflare/cloudflared

# Or install via package manager (Linux)
# curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
# sudo dpkg -i cloudflared-linux-amd64.deb

# Verify installation
cloudflared --version
```

### **2. Authenticate with Cloudflare**
```bash
# This opens your browser for login
cloudflared tunnel login
```
**What happens:** Browser opens → Login to Cloudflare → Select your domain → Authentication complete

### **3. Create Your Tunnel**
```bash
# Create the tunnel (replace 'news-digest' with any name you prefer)
cloudflared tunnel create news-digest
```
**Output:** You'll get a UUID like `abc123def-456g-789h-ijkl-mnop123qrstu`
**Important:** Copy this UUID - you'll need it!

### **4. Create Configuration File**
```bash
# Create the config directory if it doesn't exist
mkdir -p ~/.cloudflared

# Create the config file
nano ~/.cloudflared/config.yml
```

**Add this content** (replace placeholders with your actual values):
```yaml
tunnel: YOUR_TUNNEL_UUID_HERE
credentials-file: ~/.cloudflared/YOUR_TUNNEL_UUID.json

ingress:
  - hostname: news.yourdomain.com
    service: http://localhost:8000
  - service: http_status:404
```

### **5. Create DNS Record**
```bash
# Replace placeholders with your actual values
cloudflared tunnel route dns YOUR_TUNNEL_UUID news.yourdomain.com
```
**What this does:** Creates a CNAME record pointing `news.yourdomain.com` to your tunnel

### **6. Test the Tunnel**
```bash
# Replace YOUR_TUNNEL_UUID with your actual UUID  
cloudflared tunnel run YOUR_TUNNEL_UUID
```
**Expected output:**
```
2025-09-12T20:30:00Z INF Started tunnel
2025-09-12T20:30:00Z INF +----------------------------+
2025-09-12T20:30:00Z INF |  Your Quick Tunnel is ready!  |
2025-09-12T20:30:00Z INF +----------------------------+
```

**Test it:** Open `https://news.yourdomain.com` in your browser!

### **7. Install as Permanent Service**
```bash
# Install as system service (runs automatically)
sudo cloudflared service install

# Start the service  
sudo launchctl start com.cloudflare.cloudflared  # macOS
# sudo systemctl start cloudflared              # Linux

# Check if it's running
sudo launchctl list | grep cloudflare           # macOS
# sudo systemctl status cloudflared             # Linux
```

---

## ✅ **Verification Steps**

### **Check DNS Propagation**
```bash
# Should show your tunnel endpoint
dig news.yourdomain.com
```

### **Test HTTPS Access**
```bash
# Should return your news digest HTML
curl -s https://news.yourdomain.com | head -20
```

### **Monitor Tunnel Status**
```bash
# Check tunnel logs
sudo tail -f /var/log/cloudflared.log

# Or check service status
sudo launchctl list com.cloudflare.cloudflared  # macOS
# sudo systemctl status cloudflared             # Linux
```

---

## 🛠️ **Troubleshooting**

### **Tunnel Not Connecting**
```bash
# Check if your local service is running
curl http://localhost:8000/health

# Restart your news digest
docker-compose restart app
```

### **DNS Not Resolving**
- Wait 5-10 minutes for DNS propagation
- Check Cloudflare dashboard → DNS → Records
- Ensure CNAME record exists for your subdomain

### **502 Bad Gateway**
- Your tunnel is working but can't reach `localhost:8000`
- Check if Docker containers are running: `docker-compose ps`
- Verify your news digest responds: `curl http://localhost:8000`

---

## 🎉 **Success!**

Once complete, you'll have:
- ✅ **Global Access**: `https://news.yourdomain.com` works from anywhere
- ✅ **Automatic HTTPS**: Cloudflare provides SSL certificates
- ✅ **DDoS Protection**: Cloudflare protects your server
- ✅ **Always On**: Service runs automatically on system startup
- ✅ **Private**: Your server IP stays hidden

Your personal news intelligence is now globally accessible! 🌍📰🤖

---

## 🔗 **Multiple Services (Optional)**

You can route multiple subdomains through a single tunnel:

```yaml
tunnel: YOUR_TUNNEL_UUID_HERE
credentials-file: ~/.cloudflared/YOUR_TUNNEL_UUID.json

ingress:
  - hostname: news.yourdomain.com
    service: http://localhost:8000
  - hostname: ssh.yourdomain.com
    service: ssh://localhost:22
  - hostname: other.yourdomain.com
    service: http://localhost:3000
  - service: http_status:404
```

This allows you to expose multiple services (news digest, SSH, other apps) through one tunnel configuration.
