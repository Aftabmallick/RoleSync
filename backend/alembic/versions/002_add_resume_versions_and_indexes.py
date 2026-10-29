"""Add resume_versions table and tenant isolation indexes

Revision ID: 002_add_resume_versions
Revises: 001_initial_schema_and_rls
Create Date: 2026-10-29 21:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_resume_versions'
down_revision: Union[str, None] = '001_initial_schema_and_rls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create resume_versions table
    op.create_table(
        'resume_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_name', sa.String(255), nullable=False),
        sa.Column('target_company', sa.String(255), nullable=False),
        sa.Column('target_role', sa.String(255), nullable=False),
        sa.Column('ats_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('profile_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('pdf_base64', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_resume_versions_user_id', 'resume_versions', ['user_id'])
    op.create_index('ix_resume_versions_target_company', 'resume_versions', ['target_company'])

    # 2. Enable Row-Level Security (RLS) on resume_versions
    op.execute("ALTER TABLE resume_versions ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY resume_versions_tenant_isolation ON resume_versions
        FOR ALL
        USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid);
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS resume_versions_tenant_isolation ON resume_versions;")
    op.drop_table('resume_versions')
