#!/bin/bash

echo "🔧 Final Fix - News Digest Agent"
echo "Applying all Redis and startup fixes..."

cd /Users/damianspendel/Documents/github/news-digest-agent

echo ""
echo "1. 🛑 Stopping all services..."
docker-compose down

echo ""
echo "2. 🧹 Cleaning up Redis data..."
docker-compose up -d redis
sleep 5
docker-compose exec redis redis-cli FLUSHALL
docker-compose stop redis

echo ""
echo "3. 🔨 Rebuilding app with fixes..."
docker-compose build app

echo ""
echo "4. 🚀 Starting all services..."
docker-compose up -d

echo ""
echo "5. ⏳ Waiting for complete startup (45 seconds)..."
sleep 45

echo ""
echo "6. 🧪 Testing all endpoints..."

echo "   📊 Health Check:"
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q "healthy\|degraded"; then
    echo "   ✅ Health endpoint working"
    echo "      Response: $HEALTH"
else
    echo "   ❌ Health endpoint failed"
fi

echo ""
echo "   🏠 Main Dashboard:"
MAIN=$(curl -s -w "%{http_code}" http://localhost:8000 -o /dev/null)
if [ "$MAIN" = "200" ]; then
    echo "   ✅ Main dashboard working (HTTP $MAIN)"
else
    echo "   ❌ Main dashboard failed (HTTP $MAIN)"
fi

echo ""
echo "   📚 Archive Page:"
ARCHIVE=$(curl -s -w "%{http_code}" http://localhost:8000/archive -o /dev/null)
if [ "$ARCHIVE" = "200" ]; then
    echo "   ✅ Archive page working (HTTP $ARCHIVE)"
else
    echo "   ❌ Archive page failed (HTTP $ARCHIVE)"
fi

echo ""
echo "   🔍 Debug Status:"
DEBUG=$(curl -s http://localhost:8000/debug/status)
if echo "$DEBUG" | grep -q "database"; then
    echo "   ✅ Debug endpoint working"
    echo "      $DEBUG"
else
    echo "   ❌ Debug endpoint failed"
fi

echo ""
echo "7. 📋 Container Status:"
docker-compose ps

echo ""
echo "8. 📝 Recent App Logs:"
docker-compose logs --tail=10 app

echo ""
echo "🎉 Results:"
if [ "$MAIN" = "200" ] && [ "$ARCHIVE" = "200" ]; then
    echo "✅ SUCCESS! All pages are working"
    echo ""
    echo "🌐 Your News Digest Agent is ready at:"
    echo "   • Main Dashboard: http://localhost:8000"
    echo "   • Archive: http://localhost:8000/archive"
    echo "   • API Docs: http://localhost:8000/docs"
    echo "   • Debug Status: http://localhost:8000/debug/status"
    echo ""
    echo "📰 The system will start collecting news automatically and create"
    echo "    your first digest within the hour!"
else
    echo "❌ Some issues remain. Check the logs above."
    echo ""
    echo "🔍 For detailed debugging:"
    echo "   docker-compose logs app"
    echo "   docker-compose logs db"
    echo "   docker-compose logs redis"
fi

echo ""
echo "✨ Fix script complete!"
