"""auth account safety: email_verified columns + auth_tokens table

Revision ID: 32b5c4f29cf0
Revises: 4bfa7ebcd0ac
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '32b5c4f29cf0'
down_revision = '4bfa7ebcd0ac'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('pending_email', sa.String(length=255), nullable=True))

    # Drop the True server_default so future inserts use the model default (False).
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('email_verified', server_default=sa.false())

    op.create_table(
        'auth_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=128), nullable=False),
        sa.Column('purpose', sa.String(length=32), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('ix_auth_tokens_user_id', 'auth_tokens', ['user_id'])
    op.create_index('ix_auth_tokens_token_hash', 'auth_tokens', ['token_hash'])
    op.create_index('ix_auth_tokens_expires_at', 'auth_tokens', ['expires_at'])


def downgrade():
    op.drop_index('ix_auth_tokens_expires_at', table_name='auth_tokens')
    op.drop_index('ix_auth_tokens_token_hash', table_name='auth_tokens')
    op.drop_index('ix_auth_tokens_user_id', table_name='auth_tokens')
    op.drop_table('auth_tokens')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('pending_email')
        batch_op.drop_column('email_verified_at')
        batch_op.drop_column('email_verified')
