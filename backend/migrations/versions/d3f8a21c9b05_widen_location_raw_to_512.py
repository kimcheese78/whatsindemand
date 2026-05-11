"""widen location_raw to 512

Revision ID: d3f8a21c9b05
Revises: 45e6ecc7a4e7
Create Date: 2026-05-10

"""
from alembic import op
import sqlalchemy as sa


revision = 'd3f8a21c9b05'
down_revision = '45e6ecc7a4e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('location_raw',
                              existing_type=sa.String(length=255),
                              type_=sa.String(length=512),
                              existing_nullable=True)


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('location_raw',
                              existing_type=sa.String(length=512),
                              type_=sa.String(length=255),
                              existing_nullable=True)
