# Fix for Render Deployment Error

## Problem
```
ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'
```

## Solution

Render is looking for `requirements.txt` in the root directory, but your backend code is in the `backend/` folder.

### Fix in Render Dashboard:

1. Go to your Render service dashboard
2. Click on **Settings** (in the left sidebar)
3. Scroll down to **"Root Directory"**
4. Set it to: `backend`
5. Click **Save Changes**
6. Go back to **Events** and click **Manual Deploy** → **Deploy latest commit**

### Alternative: Update Build Command

If you can't find "Root Directory" setting, update the Build Command instead:

**Old:**
```
pip install -r requirements.txt
```

**New:**
```
cd backend && pip install -r requirements.txt
```

And update Start Command:

**Old:**
```
gunicorn run:app --bind 0.0.0.0:$PORT
```

**New:**
```
cd backend && gunicorn run:app --bind 0.0.0.0:$PORT
```

## Recommended Settings for Render

- **Root Directory**: `backend` ✅ (This is the best solution)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn run:app --bind 0.0.0.0:$PORT`

After setting Root Directory to `backend`, Render will automatically look for files in that folder, so your commands can be simpler.


