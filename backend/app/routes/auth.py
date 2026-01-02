from flask import Blueprint, request, jsonify, current_app
import bcrypt
from app.models import db, User, UserProfile
from app.utils.jwt_handler import generate_token, token_required
from app.utils.validators import validate_email, validate_password
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

bp = Blueprint('auth', __name__)

@bp.route('/signup', methods=['POST'])
def signup():
    """User signup with email/password"""
    data = request.get_json()
    
    # Validate input
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    if not validate_email(email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    is_valid, message = validate_password(password)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    # Check if user already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'error': 'Email already registered'}), 409
    
    # Hash password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    # Create user
    new_user = User(
        email=email,
        password_hash=password_hash.decode('utf-8'),
        full_name=full_name,
        auth_provider='email'
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    # Create empty profile
    profile = UserProfile(
        user_id=new_user.id,
        target_role=data.get('target_role'),
        seniority_level=data.get('seniority_level'),
        location=data.get('location')
    )
    db.session.add(profile)
    db.session.commit()
    
    # Generate token
    token = generate_token(new_user.id, new_user.email)
    
    return jsonify({
        'message': 'Account created successfully',
        'token': token,
        'user': new_user.to_dict()
    }), 201

@bp.route('/login', methods=['POST'])
def login():
    """User login with email/password"""
    data = request.get_json()
    
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    # Find user
    user = User.query.filter_by(email=email).first()
    
    if not user or not user.password_hash:
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Check password
    if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    # Generate token
    token = generate_token(user.id, user.email)
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict()
    }), 200

@bp.route('/google', methods=['POST'])
def google_auth():
    """Google OAuth authentication"""
    data = request.get_json()
    token = data.get('credential')
    
    if not token:
        return jsonify({'error': 'Google credential is required'}), 400
    
    try:
        # Verify Google token
        idinfo = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            current_app.config['GOOGLE_CLIENT_ID']
        )
        
        # Get user info from Google
        email = idinfo['email']
        full_name = idinfo.get('name', '')
        google_id = idinfo['sub']
        
        # Check if user exists
        user = User.query.filter_by(email=email).first()
        
        if not user:
            # Create new user
            user = User(
                email=email,
                full_name=full_name,
                auth_provider='google',
                oauth_provider_id=google_id
            )
            db.session.add(user)
            db.session.commit()
            
            # Create empty profile
            profile = UserProfile(user_id=user.id)
            db.session.add(profile)
            db.session.commit()
        
        # Generate token
        token = generate_token(user.id, user.email)
        
        return jsonify({
            'message': 'Authentication successful',
            'token': token,
            'user': user.to_dict()
        }), 200
        
    except ValueError as e:
        return jsonify({'error': 'Invalid Google token'}), 401

@bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    """Get current authenticated user"""
    user = User.query.get(request.user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Include profile data
    profile = user.profile.to_dict() if user.profile else None
    
    return jsonify({
        'user': user.to_dict(),
        'profile': profile
    }), 200

@bp.route('/check-pro', methods=['GET'])
@token_required
def check_pro_access():
    """Check if user has pro access"""
    user = User.query.get(request.user_id)
    
    return jsonify({
        'has_pro_access': user.has_pro_access if user else False
    }), 200

@bp.route('/test')
def test():
    """Test endpoint"""
    return jsonify({'message': 'Auth route working'}), 200
