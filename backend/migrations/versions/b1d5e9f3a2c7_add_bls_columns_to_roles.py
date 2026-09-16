"""add bls columns to roles

Revision ID: b1d5e9f3a2c7
Revises: a7f3c1e90b42
Create Date: 2026-09-17

Adds three nullable columns to the roles table for BLS Employment Projections,
populated by scripts/map_roles_to_bls.py. Purely additive; safe on prod.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b1d5e9f3a2c7'
down_revision = 'a7f3c1e90b42'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('roles', sa.Column('bls_soc_code', sa.String(length=10), nullable=True))
    op.add_column('roles', sa.Column('bls_projection_pct', sa.Float(), nullable=True))
    op.add_column('roles', sa.Column('bls_projection_period', sa.String(length=30), nullable=True))
    op.create_index('ix_roles_bls_soc_code', 'roles', ['bls_soc_code'])


def downgrade():
    op.drop_index('ix_roles_bls_soc_code', table_name='roles')
    op.drop_column('roles', 'bls_projection_period')
    op.drop_column('roles', 'bls_projection_pct')
    op.drop_column('roles', 'bls_soc_code')
