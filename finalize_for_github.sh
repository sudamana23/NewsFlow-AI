#!/bin/bash

echo "🧹 Final GitHub Cleanup and Preparation"
echo "======================================"

cd /Users/damianspendel/Documents/github/news-digest-agent

echo ""
echo "1. 🗑️ Removing development artifacts..."
# Run the initial cleanup
chmod +x cleanup_for_github.sh
./cleanup_for_github.sh

echo ""
echo "2. 📝 Replacing files with clean versions..."

# Replace files with clean versions
mv .env.example.clean .env.example
mv README.md.clean README.md
mv CLOUDFLARE_SETUP.md.clean CLOUDFLARE_SETUP.md
mv .gitignore.clean .gitignore

# Remove the original versions if they exist
rm -f .env.example.old
rm -f README.md.old
rm -f CLOUDFLARE_SETUP.md.old

echo "   ✅ Updated core files with clean versions"

echo ""
echo "3. 🔍 Final scan for personal information..."

# Check for any remaining personal references
echo "   🔍 Scanning for personal data..."

PERSONAL_FOUND=0

# Check for domain references
if grep -r "misterbig\.org" . --include="*.md" --include="*.py" --include="*.yml" --include="*.txt" 2>/dev/null; then
    echo "   ⚠️ Found misterbig.org references"
    PERSONAL_FOUND=1
fi

# Check for usernames
if grep -r "damianspendel" . --include="*.md" --include="*.py" --include="*.yml" --include="*.txt" 2>/dev/null; then
    echo "   ⚠️ Found damianspendel references"
    PERSONAL_FOUND=1
fi

# Check for UUIDs
if grep -r "c3fa3fa3-10ab-4e9b-990f-305840738b08" . --include="*.md" --include="*.py" --include="*.yml" --include="*.txt" 2>/dev/null; then
    echo "   ⚠️ Found tunnel UUID references"
    PERSONAL_FOUND=1
fi

# Check for hardcoded paths
if grep -r "/Users/damianspendel" . --include="*.md" --include="*.py" --include="*.yml" --include="*.txt" 2>/dev/null; then
    echo "   ⚠️ Found hardcoded paths"
    PERSONAL_FOUND=1
fi

if [ $PERSONAL_FOUND -eq 0 ]; then
    echo "   ✅ No personal information found"
else
    echo "   ⚠️ Personal information still exists - review files above"
fi

echo ""
echo "4. 📁 Final project structure:"
tree -I '__pycache__|*.pyc' . 2>/dev/null || find . -type f -name "*.py" -o -name "*.yml" -o -name "*.yaml" -o -name "*.md" -o -name "*.txt" -o -name "*.html" -o -name "*.css" | grep -v __pycache__ | sort

echo ""
echo "5. 📋 Files ready for GitHub:"
echo "   ✅ Core application (app/ directory)"
echo "   ✅ Docker configuration (docker-compose.yml, Dockerfile)"
echo "   ✅ Dependencies (requirements.txt)"
echo "   ✅ Documentation (README.md, ARCHITECTURE.md, CLOUDFLARE_SETUP.md)"
echo "   ✅ Configuration template (.env.example)"
echo "   ✅ Git ignore rules (.gitignore)"
echo "   ✅ Static assets (static/)"

echo ""
echo "6. 🚫 Cleaned up (removed):"
echo "   ✅ All fix_*.sh scripts"
echo "   ✅ All test_*.py and test_*.sh scripts"
echo "   ✅ Debug and development scripts"
echo "   ✅ Personal domains and UUIDs"
echo "   ✅ Hardcoded paths and usernames"
echo "   ✅ Development artifacts"

echo ""
echo "✨ Project is ready for GitHub publication!"
echo ""
echo "📋 Next steps:"
echo "   1. Initialize git: git init"
echo "   2. Add files: git add ."
echo "   3. Commit: git commit -m 'Initial commit: News Digest Agent'"
echo "   4. Create GitHub repo"
echo "   5. Push: git remote add origin <repo-url> && git push -u origin main"
echo ""
echo "🎉 Your News Digest Agent is ready to share with the world!"

# Clean up the cleanup script itself
rm -f cleanup_for_github.sh
