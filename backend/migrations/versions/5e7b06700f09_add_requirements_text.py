"""add_requirements_text

Revision ID: 5e7b06700f09
Revises: 057eba6c02d9
Create Date: 2026-05-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '5e7b06700f09'
down_revision = 'fad7f72df7d5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('jobs', sa.Column('requirements_text', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('jobs', 'requirements_text')
