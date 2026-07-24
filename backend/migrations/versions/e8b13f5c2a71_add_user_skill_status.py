"""add status + status_changed_at to user_skills (Learning Tracker)

Revision ID: e8b13f5c2a71
Revises: c4d21e9a7b30
Create Date: 2026-07-25

"""
from alembic import op
import sqlalchemy as sa


revision = 'e8b13f5c2a71'
down_revision = 'c4d21e9a7b30'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_skills', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20),
                                      nullable=False, server_default='have'))
        batch_op.add_column(sa.Column('status_changed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('user_skills', schema=None) as batch_op:
        batch_op.drop_column('status_changed_at')
        batch_op.drop_column('status')
