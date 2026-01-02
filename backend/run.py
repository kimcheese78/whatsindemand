# backend/run.py

from app import create_app
from app.models import db

# Create Flask app
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )