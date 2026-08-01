"""add B2B org models (organizations, memberships, cohorts, clients)

Revision ID: f2a9c8d41e63
Revises: e8b13f5c2a71
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'f2a9c8d41e63'
down_revision = 'e8b13f5c2a71'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('org_type', sa.String(length=30), nullable=True),
        sa.Column('plan', sa.String(length=30), nullable=False, server_default='trial'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'org_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='coach'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'user_id', name='uq_org_membership'),
    )
    op.create_index('ix_org_memberships_org_id', 'org_memberships', ['org_id'])
    op.create_index('ix_org_memberships_user_id', 'org_memberships', ['user_id'])
    op.create_table(
        'cohorts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('target_role', sa.String(length=255), nullable=True),
        sa.Column('curriculum_skill_ids', postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cohorts_org_id', 'cohorts', ['org_id'])
    op.create_table(
        'org_clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('cohort_id', sa.Integer(), nullable=True),
        sa.Column('coach_user_id', sa.Integer(), nullable=True),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('target_role', sa.String(length=255), nullable=True),
        sa.Column('seniority', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cohort_id'], ['cohorts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['coach_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_org_clients_org_id', 'org_clients', ['org_id'])
    op.create_index('ix_org_clients_cohort_id', 'org_clients', ['cohort_id'])

    # user_skills / user_week_snapshots: person can be a user OR a managed client
    op.alter_column('user_skills', 'user_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('user_skills', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_user_skills_client', 'user_skills', 'org_clients',
                          ['client_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_user_skills_client_id', 'user_skills', ['client_id'])
    op.create_check_constraint('ck_user_skills_owner', 'user_skills',
                               'user_id IS NOT NULL OR client_id IS NOT NULL')

    op.alter_column('user_week_snapshots', 'user_id', existing_type=sa.Integer(), nullable=True)
    op.add_column('user_week_snapshots', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_user_week_snapshots_client', 'user_week_snapshots',
                          'org_clients', ['client_id'], ['id'], ondelete='CASCADE')
    op.create_index('ix_user_week_snapshots_client_id', 'user_week_snapshots', ['client_id'])
    op.execute("CREATE UNIQUE INDEX uq_client_week_snapshot ON user_week_snapshots "
               "(client_id, week_start) WHERE client_id IS NOT NULL")
    op.create_check_constraint('ck_user_week_snapshots_owner', 'user_week_snapshots',
                               'user_id IS NOT NULL OR client_id IS NOT NULL')


def downgrade():
    op.drop_constraint('ck_user_week_snapshots_owner', 'user_week_snapshots', type_='check')
    op.execute('DROP INDEX IF EXISTS uq_client_week_snapshot')
    op.drop_index('ix_user_week_snapshots_client_id', table_name='user_week_snapshots')
    op.drop_constraint('fk_user_week_snapshots_client', 'user_week_snapshots', type_='foreignkey')
    op.drop_column('user_week_snapshots', 'client_id')
    op.alter_column('user_week_snapshots', 'user_id', existing_type=sa.Integer(), nullable=False)

    op.drop_constraint('ck_user_skills_owner', 'user_skills', type_='check')
    op.drop_index('ix_user_skills_client_id', table_name='user_skills')
    op.drop_constraint('fk_user_skills_client', 'user_skills', type_='foreignkey')
    op.drop_column('user_skills', 'client_id')
    op.alter_column('user_skills', 'user_id', existing_type=sa.Integer(), nullable=False)

    op.drop_index('ix_org_clients_cohort_id', table_name='org_clients')
    op.drop_index('ix_org_clients_org_id', table_name='org_clients')
    op.drop_table('org_clients')
    op.drop_index('ix_cohorts_org_id', table_name='cohorts')
    op.drop_table('cohorts')
    op.drop_index('ix_org_memberships_user_id', table_name='org_memberships')
    op.drop_index('ix_org_memberships_org_id', table_name='org_memberships')
    op.drop_table('org_memberships')
    op.drop_table('organizations')
