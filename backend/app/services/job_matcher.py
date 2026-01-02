from app.models import Job, UserSkill, JobSkill, Company
from sqlalchemy import and_, func

class JobMatcher:
    """Match users with relevant jobs based on skills"""
    
    def find_matching_jobs(self, user_id: int, filters: dict = None):
        """
        Find jobs matching user's skills
        
        Args:
            user_id: User ID
            filters: Optional filters (role, location, seniority)
            
        Returns:
            List of jobs with match scores
        """
        # Get user's skills
        user_skills = UserSkill.query.filter_by(user_id=user_id).all()
        user_skill_ids = [us.skill_id for us in user_skills]
        
        if not user_skill_ids:
            return []
        
        # Build query
        query = Job.query.filter(Job.is_active == True)
        
        # Apply filters
        if filters:
            if filters.get('role'):
                query = query.filter(Job.title.ilike(f"%{filters['role']}%"))
            
            if filters.get('location'):
                location = filters['location']
                query = query.filter(
                    (Job.location_city.ilike(f"%{location}%")) |
                    (Job.location_state.ilike(f"%{location}%")) |
                    (Job.location_country.ilike(f"%{location}%")) |
                    (Job.location_is_remote == True)
                )
            
            if filters.get('seniority'):
                query = query.filter(Job.seniority_level == filters['seniority'])
        
        # Get all matching jobs
        jobs = query.all()
        
        # Calculate match scores
        matched_jobs = []
        for job in jobs:
            match_data = self._calculate_match(job, user_skill_ids)
            if match_data['match_score'] > 0:
                matched_jobs.append({
                    'job': job.to_dict(),
                    'match_score': match_data['match_score'],
                    'matched_skills': match_data['matched_skills'],
                    'missing_skills': match_data['missing_skills'],
                    'total_required_skills': match_data['total_skills']
                })
        
        # Sort by match score
        matched_jobs.sort(key=lambda x: x['match_score'], reverse=True)
        
        return matched_jobs
    
    def _calculate_match(self, job: Job, user_skill_ids: list) -> dict:
        """Calculate match score between job and user skills"""
        # Get job's required skills
        job_skills = JobSkill.query.filter_by(job_id=job.id).all()
        job_skill_ids = [js.skill_id for js in job_skills]
        
        if not job_skill_ids:
            return {
                'match_score': 0,
                'matched_skills': [],
                'missing_skills': [],
                'total_skills': 0
            }
        
        # Find matched and missing skills
        matched_skill_ids = set(user_skill_ids) & set(job_skill_ids)
        missing_skill_ids = set(job_skill_ids) - set(user_skill_ids)
        
        # Get skill names
        from app.models import Skill
        matched_skills = [
            Skill.query.get(sid).name 
            for sid in matched_skill_ids
        ]
        missing_skills = [
            Skill.query.get(sid).name 
            for sid in missing_skill_ids
        ]
        
        # Calculate match score (percentage)
        match_score = int((len(matched_skill_ids) / len(job_skill_ids)) * 100)
        
        return {
            'match_score': match_score,
            'matched_skills': matched_skills,
            'missing_skills': missing_skills,
            'total_skills': len(job_skill_ids)
        }
    
    def get_skill_demand(self, skill_id: int, filters: dict = None) -> dict:
        """
        Get demand statistics for a skill
        
        Args:
            skill_id: Skill ID
            filters: Optional filters (location, seniority)
            
        Returns:
            Demand stats (job count, percentage)
        """
        # Build base query
        query = JobSkill.query.join(Job).filter(
            and_(
                JobSkill.skill_id == skill_id,
                Job.is_active == True
            )
        )
        
        # Apply filters
        if filters:
            if filters.get('location'):
                location = filters['location']
                query = query.filter(
                    (Job.location_city.ilike(f"%{location}%")) |
                    (Job.location_state.ilike(f"%{location}%"))
                )
            
            if filters.get('seniority'):
                query = query.filter(Job.seniority_level == filters['seniority'])
        
        job_count = query.count()
        
        # Get total jobs (with same filters)
        total_query = Job.query.filter(Job.is_active == True)
        if filters:
            if filters.get('location'):
                location = filters['location']
                total_query = total_query.filter(
                    (Job.location_city.ilike(f"%{location}%")) |
                    (Job.location_state.ilike(f"%{location}%"))
                )
            if filters.get('seniority'):
                total_query = total_query.filter(Job.seniority_level == filters['seniority'])
        
        total_jobs = total_query.count()
        
        demand_percentage = int((job_count / total_jobs * 100)) if total_jobs > 0 else 0
        
        return {
            'job_count': job_count,
            'total_jobs': total_jobs,
            'demand_percentage': demand_percentage
        }
