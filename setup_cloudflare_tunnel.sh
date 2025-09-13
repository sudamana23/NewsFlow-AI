#!/bin/bash

echo "🌐 Setting up Cloudflare Tunnel for news.misterbig.org"
echo "=================================================="

echo ""
echo "📋 Prerequisites:"
echo "   ✅ Cloudflare account with misterbig.org domain"
echo "   ✅ News Digest Agent running on localhost:8000"
echo "   ✅ Mac Mini with static local IP"

echo ""
echo "🔧 Step 1: Install Cloudflare Tunnel (cloudflared)"
echo "   Run this command:"
echo "   brew install cloudflare/cloudflare/cloudflared"

echo ""
echo "🔑 Step 2: Authenticate with Cloudflare"
echo "   Run this command and follow the browser login:"
echo "   cloudflared tunnel login"

echo ""
echo "🚇 Step 3: Create the tunnel"
echo "   cloudflared tunnel create news-digest"
echo "   # This creates a tunnel and gives you a UUID"

echo ""
echo "📍 Step 4: Create tunnel configuration"
echo "   Create file: ~/.cloudflared/config.yml"
echo ""
cat << 'EOF'
# Example config.yml content:
tunnel: YOUR_TUNNEL_UUID_HERE
credentials-file: /Users/YOUR_USERNAME/.cloudflared/YOUR_TUNNEL_UUID.json

ingress:
  - hostname: 
    service: http://localhost:8000
  - service: http_status:404
EOF

echo ""
echo "🌍 Step 5: Create DNS record"
echo "   cloudflared tunnel route dns YOUR_TUNNEL_UUID news.misterbig.org"

echo ""
echo "🚀 Step 6: Start the tunnel"
echo "   cloudflared tunnel run YOUR_TUNNEL_UUID"

echo ""
echo "🔄 Step 7: Run tunnel as service (persistent)"
echo "   sudo cloudflared service install"
echo "   sudo launchctl start com.cloudflare.cloudflared"

echo ""
echo "✅ Once complete, your news digest will be available at:"
echo "   https://

echo ""
echo "💡 Need help? Check Cloudflare Tunnel docs:"
echo "   https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/"
