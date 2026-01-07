# Environment Variables Guide

This guide helps you set up all the environment variables needed for deployment.

## 🔐 Step 1: Generate Secret Keys

I'll generate secure random keys for you. Run these commands:

```bash
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

Or use these pre-generated ones (copy them exactly):

```
SECRET_KEY=YOUR_SECRET_KEY_HERE
JWT_SECRET_KEY=YOUR_JWT_SECRET_KEY_HERE
```

## 📋 Step 2: Environment Variables for Render (Backend)

Go to your Render dashboard → Your service → Environment tab

Add these variables one by one:

### Required Variables:

1. **FLASK_ENV**
   ```
   production
   ```

2. **SECRET_KEY**
   ```
   [Paste the SECRET_KEY you generated above]
   ```
   Example: `xK9mP2qR7vT4wY8zA1bC3dE5fG6hI0jK2lM4nO6pQ8rS0tU2vW4xY6zA8bC0dE`

3. **JWT_SECRET_KEY**
   ```
   [Paste the JWT_SECRET_KEY you generated above]
   ```
   Example: `aB3cD5eF7gH9iJ1kL3mN5oP7qR9sT1uV3wX5yZ7aB9cD1eF3gH5iJ7kL9mN`

4. **DATABASE_URL**
   ```
   [Your Supabase connection string]
   ```
   Format: `postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres`
   
   **Where to find it:**
   - Go to Supabase dashboard
   - Settings → Database
   - Under "Connection string" → "URI"
   - Copy the entire string

5. **FRONTEND_URL**
   ```
   https://your-app.vercel.app
   ```
   ⚠️ **You'll update this AFTER deploying frontend to Vercel**
   - For now, use: `http://localhost:3000` (temporary)
   - After Vercel deployment, update to your actual Vercel URL

6. **BACKEND_URL**
   ```
   https://your-backend.onrender.com
   ```
   ⚠️ **You'll get this AFTER deploying to Render**
   - Render will give you a URL like: `https://whatsindemand-backend.onrender.com`
   - Update this value once you have your Render URL

7. **PORT**
   ```
   10000
   ```
   (Render sets this automatically, but good to have)

### Optional Variables (can skip for now):

- **REDIS_URL** - Only needed if using rate limiting (can skip)
- **STRIPE_SECRET_KEY** - Only needed for payments (can skip)
- **GOOGLE_CLIENT_ID** - Only needed for Google OAuth (can skip)

## 📋 Step 3: Environment Variables for Vercel (Frontend)

Go to Vercel dashboard → Your project → Settings → Environment Variables

Add this variable:

1. **REACT_APP_API_URL**
   ```
   https://your-backend.onrender.com
   ```
   ⚠️ **Update this AFTER deploying backend to Render**
   - Use your actual Render backend URL
   - Example: `https://whatsindemand-backend.onrender.com`

## 🔄 Step 4: Update After Deployment

After you deploy:

1. **Get your Render backend URL:**
   - Render dashboard → Your service
   - Copy the URL (e.g., `https://whatsindemand-backend-xxxx.onrender.com`)

2. **Update Render environment variable:**
   - Go to Render → Environment tab
   - Update `BACKEND_URL` to your actual Render URL

3. **Update Vercel environment variable:**
   - Go to Vercel → Environment Variables
   - Update `REACT_APP_API_URL` to your Render backend URL

4. **Get your Vercel frontend URL:**
   - Vercel dashboard → Your project
   - Copy the URL (e.g., `https://whatsindemand.vercel.app`)

5. **Update Render environment variable:**
   - Go to Render → Environment tab
   - Update `FRONTEND_URL` to your actual Vercel URL

6. **Redeploy both services** (they'll auto-redeploy when you update env vars)

## ✅ Quick Checklist

- [ ] Generated SECRET_KEY
- [ ] Generated JWT_SECRET_KEY
- [ ] Got DATABASE_URL from Supabase
- [ ] Added all variables to Render
- [ ] Added REACT_APP_API_URL to Vercel
- [ ] Updated URLs after deployment

## 🆘 Troubleshooting

**"Database connection failed":**
- Check DATABASE_URL format (should start with `postgresql://`)
- Make sure password is correct
- Check Supabase allows connections from Render IPs

**"CORS error":**
- Make sure FRONTEND_URL in Render matches your Vercel URL exactly
- No trailing slashes
- Include `https://`

**"Environment variable not found":**
- Make sure variable names are exact (case-sensitive)
- Redeploy after adding variables


