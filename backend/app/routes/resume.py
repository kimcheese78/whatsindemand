from flask import Blueprint, request, jsonify, current_app
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from app.models import db, UserProfile, UserSkill, Skill
from app.utils.jwt_handler import token_required
from app.services.resume_parser import ResumeParser
from app.services.skill_extractor import SkillExtractor

bp = Blueprint('resume', __name__)

def allowed_file(filename):
    """Check if file extension is allowed"""
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/upload', methods=['POST'])
@token_required
def upload_resume():
    """
    Upload and parse user's resume
    
    Expects:
        - file: Resume file (PDF or DOCX)
        - role: Target role (optional)
        - seniority: Seniority level (optional)
        - location: Job location (optional)
    """
    # Check if file is present
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file type. Only PDF and DOCX are allowed'}), 400
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > current_app.config['MAX_FILE_SIZE']:
        return jsonify({'error': 'File too large. Maximum size is 5MB'}), 400
    
    try:
        # Save file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{request.user_id}_{timestamp}_{filename}"
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_folder, exist_ok=True)
        
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        
        # Extract text from resume
        parser = ResumeParser()
        resume_text = parser.extract_text(file_path)
        
        if not resume_text or len(resume_text) < 50:
            os.remove(file_path)  # Clean up
            return jsonify({'error': 'Could not extract text from resume. Please ensure it contains readable text'}), 400
        
        # Extract skills
        extractor = SkillExtractor()
        extracted_skills = extractor.extract_skills(resume_text)
        
        # Update user profile
        profile = UserProfile.query.filter_by(user_id=request.user_id).first()
        
        if not profile:
            profile = UserProfile(user_id=request.user_id)
            db.session.add(profile)
        
        profile.resume_file_path = file_path
        profile.resume_text = resume_text
        profile.resume_uploaded_at = datetime.utcnow()
        
        # Update profile fields if provided
        if 'role' in request.form:
            profile.target_role = request.form['role']
        if 'seniority' in request.form:
            profile.seniority_level = request.form['seniority']
        if 'location' in request.form:
            profile.location = request.form['location']
        
        db.session.commit()
        
        # Save extracted skills to database
        # First, delete existing skills for this user
        UserSkill.query.filter_by(user_id=request.user_id).delete()
        
        # Add new skills
        for skill_data in extracted_skills:
            user_skill = UserSkill(
                user_id=request.user_id,
                skill_id=skill_data['skill_id'],
                confidence_score=skill_data['confidence'],
                is_custom=False
            )
            db.session.add(user_skill)
        
        db.session.commit()
        
        # Categorize skills
        categorized = extractor.categorize_skills(extracted_skills)
        
        return jsonify({
            'message': 'Resume uploaded and analyzed successfully',
            'file_id': unique_filename,
            'skills_found': len(extracted_skills),
            'skills': {
                'technical': categorized['technical'],
                'soft': categorized['soft'],
                'domain': categorized['domain']
            }
        }), 200
        
    except Exception as e:
        # Clean up file if it was saved
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        return jsonify({'error': f'Failed to process resume: {str(e)}'}), 500

@bp.route('/skills', methods=['GET'])
@token_required
def get_user_skills():
    """Get all skills for authenticated user"""
    user_skills = UserSkill.query.filter_by(user_id=request.user_id).all()
    
    skills_data = [us.to_dict() for us in user_skills]
    
    return jsonify({
        'skills': skills_data,
        'total': len(skills_data)
    }), 200

@bp.route('/skills', methods=['POST'])
@token_required
def add_custom_skill():
    """Add a custom skill manually"""
    data = request.get_json()
    skill_name = data.get('skill_name', '').strip()
    category = data.get('category', 'technical')
    
    if not skill_name:
        return jsonify({'error': 'Skill name is required'}), 400
    
    if category not in ['technical', 'soft', 'domain']:
        category = 'technical'
    
    # Validate skill name
    if not SkillExtractor.is_valid_skill(skill_name):
        return jsonify({'error': 'Invalid skill name'}), 400
    
    # Normalize the skill name
    normalized_name = SkillExtractor.normalize_skill_name(skill_name)
    
    # Case-insensitive search in master skills table
    skill = Skill.query.filter(
        db.func.lower(Skill.name) == normalized_name.lower()
    ).first()
    
    if not skill:
        # Create as UNVERIFIED
        skill = Skill(
            name=normalized_name, 
            category=category,
            is_verified=False
        )
        db.session.add(skill)
        db.session.commit()
    
    # Check if user already has this skill
    existing = UserSkill.query.filter_by(
        user_id=request.user_id,
        skill_id=skill.id
    ).first()
    
    if existing:
        return jsonify({'error': 'Skill already added'}), 409
    
    # Add to user's skills
    user_skill = UserSkill(
        user_id=request.user_id,
        skill_id=skill.id,
        confidence_score=100,
        is_custom=True
    )
    db.session.add(user_skill)
    db.session.commit()
    
    # Return with skill_id explicitly
    return jsonify({
        'message': 'Skill added successfully',
        'skill': {
            'id': user_skill.id,
            'skill_id': skill.id,  # ← Add this
            'skill_name': skill.name,
            'skill_category': skill.category,
            'confidence_score': user_skill.confidence_score,
            'is_custom': user_skill.is_custom
        }
    }), 201

@bp.route('/skills/<int:skill_id>', methods=['DELETE'])
@token_required
def remove_skill(skill_id):
    """Remove a skill from user's profile"""
    user_skill = UserSkill.query.filter_by(
        user_id=request.user_id,
        skill_id=skill_id
    ).first()
    
    if not user_skill:
        return jsonify({'error': 'Skill not found'}), 404
    
    db.session.delete(user_skill)
    db.session.commit()
    
    return jsonify({'message': 'Skill removed successfully'}), 200

@bp.route('/test')
def test():
    return jsonify({'message': 'Resume route working'}), 200
