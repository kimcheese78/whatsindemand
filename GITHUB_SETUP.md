# GitHub Setup Guide

## Step 1: Create a GitHub Account (if you don't have one)

1. Go to [github.com](https://github.com)
2. Click "Sign up"
3. Create your account (it's free!)

## Step 2: Create a New Repository

1. After logging in, click the **"+"** icon in the top right
2. Select **"New repository"**
3. Fill in:
   - **Repository name**: `whatsindemand` (or whatever you want)
   - **Description**: "Job market intelligence platform"
   - **Visibility**: Choose **Private** (recommended) or **Public**
   - **DO NOT** check "Initialize with README" (we already have code)
   - **DO NOT** add .gitignore or license (we already have them)
4. Click **"Create repository"**

## Step 3: Copy Your Repository URL

After creating the repo, GitHub will show you a page with instructions. You'll see a URL like:
- `https://github.com/YOUR_USERNAME/whatsindemand.git`

**Copy this URL** - you'll need it in the next step!

## Step 4: Connect Your Local Code to GitHub

Run these commands in your terminal (I'll help you with this):

```bash
cd /Users/henry_c/Whatsindemand
git remote add origin https://github.com/YOUR_USERNAME/whatsindemand.git
git branch -M main
git push -u origin main
```

**Important**: Replace `YOUR_USERNAME` with your actual GitHub username!

## Step 5: Authentication

When you run `git push`, GitHub will ask for authentication. You have two options:

### Option A: Personal Access Token (Recommended)
1. Go to GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Name it: "WhatsInDemand Deployment"
4. Select scopes: Check **"repo"** (this gives full repository access)
5. Click "Generate token"
6. **COPY THE TOKEN** (you'll only see it once!)
7. When `git push` asks for password, paste the token instead

### Option B: GitHub CLI (Easier, but requires installation)
```bash
# Install GitHub CLI first
brew install gh

# Then authenticate
gh auth login

# Then push
git push -u origin main
```

## Troubleshooting

**"Repository not found" error:**
- Make sure you created the repo on GitHub first
- Check that the URL is correct (with your username)

**"Authentication failed" error:**
- Make sure you're using a Personal Access Token, not your password
- Tokens need "repo" scope

**"Permission denied" error:**
- Check that the repository name matches exactly
- Make sure you're logged into the correct GitHub account

## Next Steps

Once your code is on GitHub:
1. Go to [render.com](https://render.com)
2. Sign up/login
3. Click "New" → "Web Service"
4. Connect your GitHub account
5. Select your `whatsindemand` repository
6. Follow the deployment steps in `DEPLOYMENT.md`





