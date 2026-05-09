# Environment Variables Guide

This guide helps you set up all the environment variables needed for deployment.

## 🔐 Step 1: Generate Secret Keys

Run these commands:

```bash
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

## 📋 Step 2: Environment Variables for Railway (Backend)

Go to your Railway dashboard → Your service → Variables tab

Add these variables:

### Required:

1. **FLASK_ENV** — `production`

2. **SECRET_KEY** — generated above

3. **JWT_SECRET_KEY** — generated above

4. **DATABASE_URL**
   ```
   [Your Supabase connection string]
   ```
   Format: `postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres`
   
   Find it in: Supabase dashboard → Settings → Database → Connection string → URI

5. **FRONTEND_URL** — `https://whatsindemand.com`

6. **BACKEND_URL** — your Railway service URL (found in Railway dashboard after first deploy)

7. **RESEND_API_KEY** — from resend.com (required for password reset / email verification)

8. **EMAIL_FROM** — `noreply@whatsindemand.com`

9. **WEB_URL** — `https://whatsindemand.com`

### Optional:

- **GOOGLE_CLIENT_ID** — for Google OAuth
- **STRIPE_SECRET_KEY** — for payments

## 📋 Step 3: Environment Variables for Vercel (Frontend)

Go to Vercel dashboard → Your project → Settings → Environment Variables

1. **REACT_APP_API_URL** — your Railway backend URL

## ✅ Quick Checklist

- [ ] Generated SECRET_KEY and JWT_SECRET_KEY
- [ ] Got DATABASE_URL from Supabase
- [ ] Added all variables to Railway
- [ ] Added REACT_APP_API_URL to Vercel
- [ ] Set RESEND_API_KEY for email flows

## 🆘 Troubleshooting

**"Database connection failed":**
- Check DATABASE_URL format (should start with `postgresql://`)
- Check Supabase allows connections from Railway IPs

**"CORS error":**
- Make sure FRONTEND_URL in Railway matches your domain exactly
- No trailing slashes, include `https://`

**Emails not sending:**
- Verify RESEND_API_KEY is set in Railway
- Check Railway logs — missing key logs a warning and skips silently

**"Environment variable not found":**
- Variable names are case-sensitive
- Redeploy after adding variables
