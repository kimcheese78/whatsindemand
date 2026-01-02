# WhatsInDemand

A real-time job market intelligence platform that tracks skills demand, job trends, and helps professionals stay ahead of market changes.

## Tech Stack

- **Frontend**: React (Create React App) + Tailwind CSS
- **Backend**: Flask (Python) + SQLAlchemy
- **Database**: PostgreSQL
- **Deployment**: Vercel (Frontend) + Render (Backend) + Supabase (Database)

## Project Structure

```
Whatsindemand/
├── frontend/          # React frontend application
│   ├── src/          # Source code
│   └── public/       # Static assets
├── backend/          # Flask backend API
│   ├── app/          # Application code
│   │   ├── routes/   # API endpoints
│   │   ├── models/   # Database models
│   │   ├── services/ # Business logic
│   │   └── scrapers/ # Job scraping logic
│   ├── scripts/      # Utility scripts
│   └── migrations/   # Database migrations
└── README.md
```

## Local Development

### Prerequisites
- Python 3.13+
- Node.js 18+
- PostgreSQL (or use Supabase)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your database URL and secrets

# Run migrations
flask db upgrade

# Start server
python run.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm start
```

## Deployment

See `DEPLOYMENT.md` for detailed deployment instructions.

## Environment Variables

### Backend (.env)
- `SECRET_KEY` - Flask secret key
- `JWT_SECRET_KEY` - JWT signing key
- `DATABASE_URL` - PostgreSQL connection string
- `FRONTEND_URL` - Frontend URL for CORS
- `BACKEND_URL` - Backend URL
- `REDIS_URL` - Redis connection (optional)

### Frontend
- `REACT_APP_API_URL` - Backend API URL

## License

MIT

