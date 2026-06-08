import json
import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, current_app, Response
import bcrypt
from app.models import db, User, UserProfile, UserSkill, AuthToken
from app.utils.jwt_handler import generate_token, token_required
from app.utils.validators import validate_email, validate_password
from app.services import auth_tokens
from app.services.email import send_email
from app.services import email_templates
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app import limiter

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)


def _send_verification_email(user: User) -> None:
    raw = auth_tokens.issue(
        user.id, auth_tokens.PURPOSE_EMAIL_VERIFY, timedelta(hours=24)
    )
    subject, html, text = email_templates.email_verify(user, raw)
    send_email(user.email, subject, html, text)

@bp.route('/signup', methods=['POST'])
@limiter.limit("5 per minute; 20 per hour")
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
    
    # Issue email verification token + send verification email (best effort).
    try:
        _send_verification_email(new_user)
    except Exception as e:
        logger.warning('Verification email failed for %s: %s', new_user.email, e)

    # Generate auth token
    token = generate_token(new_user.id, new_user.email)

    return jsonify({
        'message': 'Account created successfully',
        'token': token,
        'user': new_user.to_dict()
    }), 201

@bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute; 50 per hour")
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
@limiter.limit("10 per minute; 50 per hour")
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
            # Create new user — Google verifies emails, so trust it.
            user = User(
                email=email,
                full_name=full_name,
                auth_provider='google',
                oauth_provider_id=google_id,
                email_verified=True,
                email_verified_at=datetime.utcnow(),
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


# ============================================
# ACCOUNT SAFETY ENDPOINTS
# ============================================

@bp.route('/forgot-password', methods=['POST'])
@limiter.limit("3 per minute; 10 per hour")
def forgot_password():
    """Initiate password reset. Returns 404 if no account exists for the email."""
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email is required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'If an account exists for that email, a reset link has been sent.'}), 200

    if not user.password_hash:
        return jsonify({
            'error': 'This account uses Google sign-in. Sign in with Google instead.'
        }), 400

    try:
        raw = auth_tokens.issue(
            user.id, auth_tokens.PURPOSE_PASSWORD_RESET, timedelta(hours=1)
        )
        subject, html, text = email_templates.password_reset(user, raw)
        send_email(user.email, subject, html, text)
    except Exception as e:
        logger.exception('Forgot-password email failed: %s', e)
        return jsonify({'error': 'Failed to send reset email. Try again shortly.'}), 500

    return jsonify({'message': 'A reset link has been sent. Please check your inbox (and spam folder).'}), 200


@bp.route('/reset-password', methods=['POST'])
@limiter.limit("5 per minute; 10 per hour")
def reset_password():
    data = request.get_json(silent=True) or {}
    raw = data.get('token')
    new_password = data.get('new_password') or ''

    is_valid, message = validate_password(new_password)
    if not is_valid:
        return jsonify({'error': message}), 400

    record = auth_tokens.consume(raw, auth_tokens.PURPOSE_PASSWORD_RESET)
    if not record:
        return jsonify({'error': 'This link is invalid, expired, or already used.'}), 400

    user = User.query.get(record.user_id)
    if not user:
        return jsonify({'error': 'Account not found.'}), 404

    user.password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.token_version = (user.token_version or 0) + 1
    auth_tokens.invalidate_all(user.id, auth_tokens.PURPOSE_PASSWORD_RESET)
    db.session.commit()

    token = generate_token(user.id, user.email, user.token_version)
    return jsonify({
        'message': 'Password reset successful.',
        'token': token,
        'user': user.to_dict(),
    }), 200


@bp.route('/change-password', methods=['POST'])
@token_required
def change_password():
    data = request.get_json(silent=True) or {}
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''

    user = User.query.get(request.user_id)
    if not user or not user.password_hash:
        return jsonify({'error': 'Password change is not available for this account.'}), 400

    if not bcrypt.checkpw(current_password.encode('utf-8'), user.password_hash.encode('utf-8')):
        return jsonify({'error': 'Current password is incorrect.'}), 401

    is_valid, message = validate_password(new_password)
    if not is_valid:
        return jsonify({'error': message}), 400

    user.password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user.token_version = (user.token_version or 0) + 1
    db.session.commit()
    return jsonify({'message': 'Password updated.'}), 200


@bp.route('/me', methods=['PATCH'])
@token_required
def update_me():
    data = request.get_json(silent=True) or {}
    user = User.query.get(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if 'full_name' in data:
        full_name = (data.get('full_name') or '').strip()
        if not full_name:
            return jsonify({'error': 'Name cannot be empty.'}), 400
        if len(full_name) > 255:
            return jsonify({'error': 'Name is too long.'}), 400
        user.full_name = full_name

    db.session.commit()
    return jsonify({'user': user.to_dict()}), 200


@bp.route('/change-email', methods=['POST'])
@token_required
def change_email():
    data = request.get_json(silent=True) or {}
    new_email = (data.get('new_email') or '').strip().lower()
    current_password = data.get('current_password') or ''

    if not validate_email(new_email):
        return jsonify({'error': 'Invalid email format.'}), 400

    user = User.query.get(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.password_hash:
        if not bcrypt.checkpw(current_password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return jsonify({'error': 'Current password is incorrect.'}), 401

    if new_email == (user.email or '').lower():
        return jsonify({'error': 'That is already your email.'}), 400

    if User.query.filter_by(email=new_email).first():
        return jsonify({'error': 'That email is already in use.'}), 409

    user.pending_email = new_email
    db.session.commit()

    raw = auth_tokens.issue(
        user.id,
        auth_tokens.PURPOSE_EMAIL_CHANGE,
        timedelta(hours=24),
        payload={'new_email': new_email},
    )
    subject, html, text = email_templates.email_change(user, raw, new_email)
    send_email(new_email, subject, html, text)

    return jsonify({'message': 'Confirmation link sent to your new email.'}), 200


@bp.route('/verify-email', methods=['POST'])
def verify_email():
    data = request.get_json(silent=True) or {}
    raw = data.get('token')
    if not raw:
        return jsonify({'error': 'Token required.'}), 400

    # Try email_verify first, then email_change.
    record = auth_tokens.consume(raw, auth_tokens.PURPOSE_EMAIL_VERIFY)
    if not record:
        record = auth_tokens.consume(raw, auth_tokens.PURPOSE_EMAIL_CHANGE)

    if not record:
        return jsonify({'error': 'This link is invalid, expired, or already used.'}), 400

    user = User.query.get(record.user_id)
    if not user:
        return jsonify({'error': 'Account not found.'}), 404

    if record.purpose == auth_tokens.PURPOSE_EMAIL_CHANGE:
        new_email = (record.payload or {}).get('new_email')
        if not new_email:
            return jsonify({'error': 'Token missing payload.'}), 400
        if User.query.filter(User.email == new_email, User.id != user.id).first():
            return jsonify({'error': 'That email is now in use by another account.'}), 409
        user.email = new_email
        user.pending_email = None

    user.email_verified = True
    user.email_verified_at = datetime.utcnow()
    db.session.commit()

    token = generate_token(user.id, user.email)
    return jsonify({
        'message': 'Email verified.',
        'token': token,
        'user': user.to_dict(),
    }), 200


@bp.route('/resend-verification', methods=['POST'])
@limiter.limit("2 per minute; 5 per hour")
@token_required
def resend_verification():
    user = User.query.get(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.email_verified:
        return jsonify({'message': 'Email already verified.'}), 200

    # Crude rate limit: only allow if no unconsumed token issued in last 5 min.
    recent = AuthToken.query.filter(
        AuthToken.user_id == user.id,
        AuthToken.purpose == auth_tokens.PURPOSE_EMAIL_VERIFY,
        AuthToken.consumed_at.is_(None),
        AuthToken.created_at > datetime.utcnow() - timedelta(minutes=5),
    ).first()
    if recent:
        return jsonify({'error': 'Please wait a few minutes before requesting another email.'}), 429

    _send_verification_email(user)
    return jsonify({'message': 'Verification email sent.'}), 200


@bp.route('/delete-account', methods=['POST'])
@token_required
def delete_account():
    data = request.get_json(silent=True) or {}
    user = User.query.get(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    if user.password_hash:
        password = data.get('password') or ''
        if not bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return jsonify({'error': 'Password is incorrect.'}), 401
    else:
        confirm = data.get('confirm') or ''
        if confirm != 'DELETE':
            return jsonify({'error': 'Please type DELETE to confirm.'}), 400

    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'Account deleted.'}), 200


@bp.route('/export-data', methods=['GET'])
@token_required
def export_data():
    user = User.query.get(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    profile = user.profile.to_dict() if user.profile else None
    skills = [
        {
            'skill_id': us.skill_id,
            'skill_name': us.skill.name if us.skill else None,
            'created_at': us.created_at.isoformat() if getattr(us, 'created_at', None) else None,
        }
        for us in (user.skills or [])
    ]

    payload = {
        'exported_at': datetime.utcnow().isoformat(),
        'user': user.to_dict(),
        'profile': profile,
        'skills': skills,
    }
    body = json.dumps(payload, indent=2, default=str)
    filename = f"whatsindemand-export-{user.id}-{datetime.utcnow().strftime('%Y%m%d')}.json"
    return Response(
        body,
        mimetype='application/json',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
