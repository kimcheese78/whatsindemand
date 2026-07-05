"""add weekly_digest to user_profiles

Revision ID: b7e2a90c4f11
Revises: 1f31b1a3b270
Create Date: 2026-07-05

"""
from alembic import op
import sqlalchemy as sa


revision = 'b7e2a90c4f11'
down_revision = '1f31b1a3b270'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('weekly_digest', sa.Boolean(),
                                      nullable=False, server_default='true'))


def downgrade():
    with op.batch_alter_table('user_profiles', schema=None) as batch_op:
        batch_op.drop_column('weekly_digest')
