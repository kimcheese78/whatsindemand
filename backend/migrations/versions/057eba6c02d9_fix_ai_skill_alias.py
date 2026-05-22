"""fix_ai_skill_alias

Revision ID: 057eba6c02d9
Revises: eebdef0daefa
Create Date: 2026-05-23 08:35:01.950456

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '057eba6c02d9'
down_revision = 'eebdef0daefa'
branch_labels = None
depends_on = None


def upgrade():
    # Add 'AI' alias to Artificial Intelligence skill so it matches
    # resumes and JDs that use the abbreviation rather than the full name.
    op.execute("""
        UPDATE skills
        SET aliases = ARRAY['AI']
        WHERE name = 'Artificial Intelligence'
          AND (aliases IS NULL OR NOT ('AI' = ANY(aliases)))
    """)


def downgrade():
    op.execute("""
        UPDATE skills
        SET aliases = array_remove(aliases, 'AI')
        WHERE name = 'Artificial Intelligence'
    """)
