# Deployment Guide

## Stack

- **Backend**: Railway (auto-deploys on push to `main`)
- **Frontend**: Vercel (auto-deploys on push to `main`)
- **Database**: Supabase (PostgreSQL)

---

## Backend (Railway)

Railway auto-deploys when you push to `main`. No manual steps needed for code changes.

**Environment variables** (set in Railway dashboard → Variables):
```
FLASK_ENV=production
SECRET_KEY=<random string>
JWT_SECRET_KEY=<random string>
DATABASE_URL=<supabase connection string>
FRONTEND_URL=https://whatsindemand.com
BACKEND_URL=https://<your-service>.railway.app
RESEND_API_KEY=<resend api key>
EMAIL_FROM=noreply@whatsindemand.com
WEB_URL=https://whatsindemand.com
```

**Start command**: `gunicorn run:app --bind 0.0.0.0:$PORT`

**Root directory**: `backend`

---

## Frontend (Vercel)

Vercel auto-deploys when you push to `main`.

**Environment variable** (set in Vercel dashboard → Settings → Environment Variables):
```
REACT_APP_API_URL=https://<your-service>.railway.app
```

---

## Database Migrations

After deploying backend changes that include schema changes, run via Railway shell:

```bash
flask db upgrade
```

---

## Post-Deployment Checklist

- [ ] Railway deploy succeeded (check dashboard)
- [ ] Vercel deploy succeeded (check dashboard)
- [ ] DB migration run if schema changed
- [ ] Environment variables set (especially RESEND_API_KEY, WEB_URL)
- [ ] Test auth flows end-to-end

---

## Troubleshooting

**Backend won't start:**
- Check Railway deploy logs
- Verify all environment variables are set
- Ensure `gunicorn` is in requirements.txt

**CORS errors:**
- Verify `FRONTEND_URL` in Railway matches your Vercel domain exactly

**Database connection fails:**
- Verify `DATABASE_URL` format (Supabase connection string)
- Check Supabase is accessible from Railway IPs

**Emails not sending:**
- Verify `RESEND_API_KEY` is set in Railway
- Check Railway logs — missing key logs a warning and skips silently
