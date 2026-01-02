# backend/app/routes/analysis.py

from flask import Blueprint, request, jsonify
from datetime import datetime
import json
from app.models import db, UserProfile
from app.utils.jwt_handler import token_required

bp = Blueprint('analysis', __name__)


@bp.route('/save', methods=['POST'])
@token_required
def save_analysis():
    """
    Save user's current role exploration session.
    Called when user explores a role (if logged in).
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Get or create user profile
    profile = UserProfile.query.filter_by(user_id=request.user_id).first()
    
    if not profile:
        profile = UserProfile(user_id=request.user_id)
        db.session.add(profile)
    
    # Save role selections
    if data.get('target_role'):
        profile.target_role = data.get('target_role')
    if data.get('seniority_level'):
        profile.seniority_level = data.get('seniority_level')
    
    # FIX: Handle location as array or string
    if data.get('location'):
        loc = data.get('location')
        if isinstance(loc, list):
            profile.location = json.dumps(loc)  # Store array as JSON string
        else:
            profile.location = loc  # Store string as-is
    
    # Optionally save the full analysis data (for restoring dashboard state)
    if data.get('analysis'):
        profile.last_analysis_json = json.dumps(data.get('analysis'))
    
    profile.last_analysis_at = datetime.utcnow()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Session saved successfully'
    }), 200


@bp.route('/last', methods=['GET'])
@token_required
def get_last_analysis():
    """
    Get user's last saved session.
    Called on login to restore their previous role exploration.
    """
    profile = UserProfile.query.filter_by(user_id=request.user_id).first()
    
    if not profile or not profile.target_role:
        return jsonify({
            'success': True,
            'has_session': False,
            'session': None
        }), 200
    
    # Parse saved analysis if exists
    analysis_data = None
    if profile.last_analysis_json:
        try:
            analysis_data = json.loads(profile.last_analysis_json)
        except json.JSONDecodeError:
            analysis_data = None
    
    # FIX: Parse location (could be JSON array or plain string)
    location_data = profile.location
    if location_data:
        try:
            location_data = json.loads(location_data)
        except (json.JSONDecodeError, TypeError):
            pass  # Keep as string if not valid JSON
    
    return jsonify({
        'success': True,
        'has_session': True,
        'session': {
            'target_role': profile.target_role,
            'seniority_level': profile.seniority_level,
            'location': location_data,  # Now returns array or string correctly
            'analysis': analysis_data,
            'saved_at': profile.last_analysis_at.isoformat() if profile.last_analysis_at else None
        }
    }), 200


@bp.route('/clear', methods=['POST'])
@token_required
def clear_session():
    """Clear user's saved session (optional utility endpoint)."""
    profile = UserProfile.query.filter_by(user_id=request.user_id).first()
    
    if profile:
        profile.target_role = None
        profile.seniority_level = None
        profile.location = None
        profile.last_analysis_json = None
        profile.last_analysis_at = None
        db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Session cleared'
    }), 200