"""add user_week_snapshots (Position Score weekly tracking)

Revision ID: c4d21e9a7b30
Revises: b7e2a90c4f11
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d21e9a7b30'
down_revision = 'b7e2a90c4f11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_week_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('position_score', sa.Integer(), nullable=True),
        sa.Column('match_pct', sa.Float(), nullable=True),
        sa.Column('market_momentum', sa.Float(), nullable=True),
        sa.Column('ai_exposure', sa.Float(), nullable=True),
        sa.Column('matched_jobs_count', sa.Integer(), nullable=True),
        sa.Column('new_matched_jobs', sa.Integer(), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'week_start', name='uq_user_week_snapshot'),
    )
    op.create_index('ix_user_week_snapshots_user_id', 'user_week_snapshots',
                    ['user_id'], unique=False)


def downgrade():
    op.drop_index('ix_user_week_snapshots_user_id', table_name='user_week_snapshots')
    op.drop_table('user_week_snapshots')
