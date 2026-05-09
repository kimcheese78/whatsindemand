# backend/app/services/skill_gap_analyzer.py

from app.models import db, Job, JobSkill, Skill, Role, UserSkill, RoleTitleVariation
from sqlalchemy import func
from typing import List, Dict, Optional


class SkillGapAnalyzer:
    """Analyze skill gaps between user skills and role requirements"""
    
    def __init__(self):
        self.min_jobs_threshold = 1
    
    def analyze_gap(
        self, 
        target_role: str, 
        user_skill_ids: List[int],
        seniority_filter: Optional[str] = None,
        location_filter: Optional[str] = None
    ) -> Dict:
        """
        Analyze the gap between user's skills and target role requirements
        """
        role = self._find_role(target_role)
        if not role:
            return {
                'success': False,
                'error': f'Role "{target_role}" not found',
                'suggestions': self._suggest_similar_roles(target_role)
            }

        # Build job query with filters
        jobs_query = Job.query.filter(
            Job.role_id == role.id,
            Job.is_active == True
        )

        # Track which filters were actually applied and ignored
        filters_applied = {
            'seniority': None,
            'location': None
        }
        filters_ignored = []

        # Apply seniority filter
        if seniority_filter and seniority_filter != 'all':
            seniority_map = {
                'entry': ['entry', 'junior', 'associate', 'i', 'I', '1', 'intern'],
                'mid': ['mid', 'middle', 'ii', 'II', '2', 'intermediate'],
                'senior': ['senior', 'sr', 'iii', 'III', '3'],
                'lead': ['lead', 'principal', 'staff', 'director', 'head', 'iv', 'IV', '4', '5', 'senior-staff']
            }
            seniority_values = seniority_map.get(seniority_filter, [seniority_filter])
            seniority_conditions = [
                func.lower(Job.seniority_level) == val.lower() 
                for val in seniority_values
            ]
            jobs_query_seniority = jobs_query.filter(db.or_(*seniority_conditions))
            filtered_count = jobs_query_seniority.count()

            if filtered_count >= self.min_jobs_threshold:
                jobs_query = jobs_query_seniority
                filters_applied['seniority'] = seniority_filter
            else:
                filters_ignored.append({
                    'filter': 'seniority',
                    'value': seniority_filter,
                    'reason': f'Only {filtered_count} jobs found, need at least {self.min_jobs_threshold}'
                })
        
        # Apply location filter
        if location_filter and location_filter not in ['United States', 'Remote', 'Global']:
            jobs_query_location = jobs_query.filter(
                db.or_(
                    Job.location_city.ilike(f'%{location_filter}%'),
                    Job.location_state.ilike(f'%{location_filter}%'),
                    Job.location_raw.ilike(f'%{location_filter}%'),
                    Job.location_is_remote == True
                )
            )
            filtered_count = jobs_query_location.count()

            if filtered_count >= self.min_jobs_threshold:
                jobs_query = jobs_query_location
                filters_applied['location'] = location_filter
            else:
                filters_ignored.append({
                    'filter': 'location',
                    'value': location_filter,
                    'reason': f'Only {filtered_count} jobs found, need at least {self.min_jobs_threshold}'
                })

        # Get final job IDs
        job_ids = [j for (j,) in jobs_query.with_entities(Job.id).all()]

        # If filters were ignored, return error (don't show misleading data)
        if filters_ignored:
            ignored_values = ' and '.join([f"{f['value']} level" if f['filter'] == 'seniority' else f['value'] for f in filters_ignored])
            return {
                'success': False,
                'error': f'No {target_role} jobs found for {ignored_values}. Try a different seniority level.',
                'jobs_found': 0,
                'filters_ignored': filters_ignored,
                'suggestions': self._suggest_similar_roles(target_role)
            }

        # Check if we have enough jobs
        if len(job_ids) < self.min_jobs_threshold:
            return {
                'success': False,
                'error': f'Not enough job data for "{target_role}" (found {len(job_ids)} jobs)',
                'jobs_found': len(job_ids),
                'min_required': self.min_jobs_threshold,
                'suggestions': self._suggest_similar_roles(target_role)
            }
        
        # Get skill requirements
        role_skills = self._get_role_skill_requirements(job_ids)
        
        # Separate into matched and gaps
        user_skill_set = set(user_skill_ids)
        matched_skills = []
        gap_skills = []
        
        for skill_data in role_skills:
            skill_info = {
                'skill_id': skill_data['skill_id'],
                'name': skill_data['skill_name'],
                'category': skill_data['category'],
                'demand': skill_data['percentage'],
                'job_count': skill_data['job_count'],
                'priority': self._calculate_priority(skill_data['percentage']),
                'status': 'have' if skill_data['skill_id'] in user_skill_set else 'missing'
            }
            
            if skill_data['skill_id'] in user_skill_set:
                matched_skills.append(skill_info)
            else:
                gap_skills.append(skill_info)
        
        match_score = self._calculate_match_score(role_skills, user_skill_set)
        
        return {
            'success': True,
            'role': {
                'id': role.id,
                'title': role.normalized_title,
                'category': role.category,
                'job_family': role.job_family
            },
            'analysis': {
                'total_jobs_analyzed': len(job_ids),
                'match_score': round(match_score, 1),
                'match_rate': round(match_score, 1),
                'skills_matched': len(matched_skills),
                'skills_to_learn': len([s for s in gap_skills if s['priority'] in ['high', 'medium']]),
                'filters_requested': {
                    'seniority': seniority_filter,
                    'location': location_filter
                },
                'filters_applied': filters_applied,
                'filters_ignored': filters_ignored,
            },
            'skills_you_have': sorted(matched_skills, key=lambda x: x['demand'], reverse=True),
            'skills_missing': sorted(gap_skills, key=lambda x: x['demand'], reverse=True),
            'has_skills': sorted(matched_skills, key=lambda x: x['demand'], reverse=True),
            'missing_skills': sorted(gap_skills, key=lambda x: x['demand'], reverse=True),
        }
    
    def _find_role(self, role_name: str):
        role = Role.query.filter(
            func.lower(Role.normalized_title) == func.lower(role_name)
        ).first()
        if role:
            return role
        variation = RoleTitleVariation.query.filter(
            func.lower(RoleTitleVariation.original_title) == func.lower(role_name)
        ).first()
        if variation:
            return Role.query.get(variation.role_id)
        return Role.query.filter(
            Role.normalized_title.ilike(f'%{role_name}%')
        ).first()

    def _get_role_skill_requirements(self, job_ids: List[int]) -> List[Dict]:
        """Get skill frequency for a set of jobs"""
        if not job_ids:
            return []
            
        total_jobs = len(job_ids)
        
        skill_counts = db.session.query(
            Skill.id,
            Skill.name,
            Skill.category,
            func.count(JobSkill.id).label('job_count')
        ).join(JobSkill).filter(
            JobSkill.job_id.in_(job_ids)
        ).group_by(Skill.id).order_by(
            func.count(JobSkill.id).desc()
        ).all()
        
        return [
            {
                'skill_id': skill_id,
                'skill_name': skill_name,
                'category': category,
                'job_count': job_count,
                'percentage': round(job_count / total_jobs * 100, 1)
            }
            for skill_id, skill_name, category, job_count in skill_counts
        ]
    
    def _calculate_match_score(self, role_skills: List[Dict], user_skill_ids: set) -> float:
        """Calculate weighted match score"""
        if not role_skills:
            return 0.0
        
        total_weight = 0
        matched_weight = 0
        
        for skill in role_skills[:15]:
            weight = skill['percentage']
            total_weight += weight
            if skill['skill_id'] in user_skill_ids:
                matched_weight += weight
        
        return (matched_weight / total_weight * 100) if total_weight > 0 else 0.0
    
    def _calculate_priority(self, percentage: float) -> str:
        """Determine skill priority based on demand"""
        if percentage >= 40:
            return 'high'
        elif percentage >= 20:
            return 'medium'
        return 'low'
    
    def _suggest_similar_roles(self, query: str) -> List[Dict]:
        """Suggest similar role titles"""
        roles = Role.query.filter(
            Role.normalized_title.ilike(f'%{query}%')
        ).limit(5).all()
        
        if not roles:
            roles = db.session.query(Role).join(Job).group_by(Role.id).order_by(
                func.count(Job.id).desc()
            ).limit(10).all()
        
        return [{'id': r.id, 'title': r.normalized_title, 'category': r.category} for r in roles]
    
    def get_available_roles(self, min_jobs: int = None) -> List[Dict]:
        """Get all roles with job counts and curated search aliases."""
        threshold = min_jobs if min_jobs is not None else self.min_jobs_threshold

        roles = db.session.query(
            Role.id,
            Role.normalized_title,
            Role.category,
            Role.job_family,
            Role.search_aliases,
            func.count(Job.id).label('job_count')
        ).join(Job).filter(
            Job.is_active == True
        ).group_by(Role.id).having(
            func.count(Job.id) >= threshold
        ).order_by(
            func.count(Job.id).desc()
        ).all()

        return [
            {
                'id': role_id,
                'title': title,
                'category': category,
                'job_family': job_family,
                'job_count': job_count,
                'aliases': search_aliases or [],
            }
            for role_id, title, category, job_family, search_aliases, job_count in roles
        ]
    
    def get_skills_for_selection(self) -> Dict[str, List[Dict]]:
        """Get all skills organized by category"""
        skills = Skill.query.order_by(Skill.category, Skill.name).all()
        
        categorized = {'technical': [], 'soft': [], 'domain': [], 'hard': []}
        
        for skill in skills:
            skill_data = {'id': skill.id, 'name': skill.name, 'category': skill.category}
            category = skill.category or 'technical'
            if category in categorized:
                categorized[category].append(skill_data)
            if category in ['technical', 'domain']:
                categorized['hard'].append(skill_data)
        
        return categorized