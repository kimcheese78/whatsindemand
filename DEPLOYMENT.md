# Deployment Guide

## Quick Deploy (Free Tier)

### 1. Database Setup (Supabase)

1. Go to [supabase.com](https://supabase.com) and create account
2. Create new project
3. Copy connection string from Settings → Database
4. Format: `postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres`

### 2. Backend Deployment (Render)

1. Push code to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect GitHub repo
4. Settings:
   - **Name**: `whatsindemand-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app --bind 0.0.0.0:$PORT`
5. Add Environment Variables:
   ```
   FLASK_ENV=production
   SECRET_KEY=<generate-random-string>
   JWT_SECRET_KEY=<generate-random-string>
   DATABASE_URL=<supabase-connection-string>
   FRONTEND_URL=https://your-app.vercel.app
   BACKEND_URL=https://your-backend.onrender.com
   PORT=10000
   ```
6. Deploy

### 3. Frontend Deployment (Vercel)

1. Go to [vercel.com](https://vercel.com) → New Project
2. Import from GitHub, select `frontend` folder
3. Add Environment Variable:
   ```
   REACT_APP_API_URL=https://your-backend.onrender.com
   ```
4. Deploy

### 4. Run Database Migrations

After backend is deployed:
1. Go to Render dashboard → Your service → Shell
2. Run: `flask db upgrade`

Or create tables manually:
```python
from app import create_app
from app.models import db

app = create_app()
with app.app_context():
    db.create_all()
```

## Required Files for Deployment

### Backend
- `Procfile` - Process file for Render
- `runtime.txt` - Python version
- `requirements.txt` - Python dependencies (must include `gunicorn`)

### Frontend
- `package.json` - Node dependencies
- `vercel.json` - Vercel configuration (optional)

## Post-Deployment Checklist

- [ ] Backend is accessible at Render URL
- [ ] Frontend is accessible at Vercel URL
- [ ] Database migrations completed
- [ ] CORS configured correctly
- [ ] Environment variables set
- [ ] Test API endpoints
- [ ] Test frontend → backend connection

## Troubleshooting

**Backend won't start:**
- Check Render logs
- Verify all environment variables are set
- Ensure `gunicorn` is in requirements.txt

**CORS errors:**
- Verify `FRONTEND_URL` matches your Vercel domain exactly
- Check backend CORS configuration

**Database connection fails:**
- Verify `DATABASE_URL` format
- Check Supabase connection settings
- Ensure database is accessible from Render IPs

**Frontend can't connect to backend:**
- Verify `REACT_APP_API_URL` is set correctly
- Check backend is running (Render services sleep after inactivity)
- Test backend URL directly in browser

