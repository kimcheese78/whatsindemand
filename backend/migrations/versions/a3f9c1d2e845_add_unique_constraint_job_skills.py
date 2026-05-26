"""add_unique_constraint_job_skills

Revision ID: a3f9c1d2e845
Revises: 5e7b06700f09
Create Date: 2026-05-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3f9c1d2e845'
down_revision = '5e7b06700f09'
branch_labels = None
depends_on = None


def upgrade():
    # Remove duplicates before adding constraint
    op.execute("""
        DELETE FROM job_skills a
        USING job_skills b
        WHERE a.job_id = b.job_id
          AND a.skill_id = b.skill_id
          AND a.id > b.id
    """)
    op.create_unique_constraint('uq_job_skills_job_skill', 'job_skills', ['job_id', 'skill_id'])


def downgrade():
    op.drop_constraint('uq_job_skills_job_skill', 'job_skills', type_='unique')
