#!/bin/bash
# Script to push code to GitHub
# Run this after creating your GitHub repository

echo "🚀 Pushing WhatsInDemand to GitHub..."
echo ""

# Get repository URL from user
read -p "Enter your GitHub repository URL (e.g., https://github.com/username/whatsindemand.git): " REPO_URL

if [ -z "$REPO_URL" ]; then
    echo "❌ Error: Repository URL is required"
    exit 1
fi

# Add remote
echo "📡 Adding GitHub remote..."
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"

# Set main branch
echo "🌿 Setting main branch..."
git branch -M main

# Push to GitHub
echo "⬆️  Pushing to GitHub..."
echo ""
echo "⚠️  You'll be asked for credentials:"
echo "   - Username: Your GitHub username"
echo "   - Password: Use a Personal Access Token (NOT your password)"
echo ""
echo "   To create a token:"
echo "   GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)"
echo "   → Generate new token → Select 'repo' scope"
echo ""

git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Success! Your code is now on GitHub!"
    echo "   View it at: $REPO_URL"
else
    echo ""
    echo "❌ Push failed. Common issues:"
    echo "   1. Repository doesn't exist on GitHub (create it first)"
    echo "   2. Authentication failed (use Personal Access Token, not password)"
    echo "   3. Wrong repository URL"
    echo ""
    echo "   See GITHUB_SETUP.md for detailed instructions"
fi

