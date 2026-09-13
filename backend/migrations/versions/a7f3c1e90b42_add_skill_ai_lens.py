"""add ai_lens to skills (control-AI skill grouping)

Revision ID: a7f3c1e90b42
Revises: e4c1a7f9b21d
Create Date: 2026-09-13

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7f3c1e90b42'
down_revision = 'e4c1a7f9b21d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ai_lens', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.drop_column('ai_lens')
