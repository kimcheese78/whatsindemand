"""skill discovery pipeline: skill_candidates, skill_candidate_jobs, discovery_runs, jobs.skills_dirty

Revision ID: a1c9e3f82d47
Revises: 32b5c4f29cf0
Create Date: 2026-05-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'a1c9e3f82d47'
down_revision = '32b5c4f29cf0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'skill_candidates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True),
        sa.Column('job_count', sa.Integer(), server_default='0'),
        sa.Column('company_count', sa.Integer(), server_default='0'),
        sa.Column('first_seen', sa.Date()),
        sa.Column('last_seen', sa.Date()),
        sa.Column('methods', postgresql.ARRAY(sa.String())),
        sa.Column('example_contexts', postgresql.ARRAY(sa.String())),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('promoted_skill_id', sa.Integer(), sa.ForeignKey('skills.id'), nullable=True),
        sa.Column('promoted_at', sa.DateTime(), nullable=True),
        sa.Column('rejected_reason', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_skill_candidates_name', 'skill_candidates', ['name'])
    op.create_index('ix_skill_candidates_status', 'skill_candidates', ['status'])

    op.create_table(
        'skill_candidate_jobs',
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('skill_candidates.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id', ondelete='CASCADE'), primary_key=True),
    )

    op.create_table(
        'discovery_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime()),
        sa.Column('jobs_processed', sa.Integer(), server_default='0'),
        sa.Column('candidates_upserted', sa.Integer(), server_default='0'),
        sa.Column('candidates_promoted', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(20), server_default='running'),
        sa.Column('error', sa.Text()),
    )

    with op.batch_alter_table('jobs') as batch_op:
        batch_op.add_column(sa.Column('skills_dirty', sa.Boolean(), server_default=sa.false()))

    # Existing jobs are already extracted — mark clean.
    op.execute("UPDATE jobs SET skills_dirty = false")


def downgrade():
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.drop_column('skills_dirty')

    op.drop_table('skill_candidate_jobs')
    op.drop_table('skill_candidates')
    op.drop_table('discovery_runs')
