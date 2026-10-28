"""Initial schema and PostgreSQL Row-Level Security (RLS) policies

Revision ID: 001_initial_schema_and_rls
Revises: 
Create Date: 2026-10-28 23:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema_and_rls'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Users Table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('full_name', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('google_id', sa.String(255), nullable=True, unique=True),
        sa.Column('plan_tier', sa.String(50), nullable=False, server_default='FREE'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_users_email', 'users', ['email'])
    op.create_index('ix_users_google_id', 'users', ['google_id'])

    # 2. Create Master Profiles Table
    op.create_table(
        'master_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('encrypted_profile_data', sa.LargeBinary(), nullable=False),
        sa.Column('encryption_iv', sa.LargeBinary(), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_master_profiles_user_id', 'master_profiles', ['user_id'])

    # 3. Create Jobs Table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('url', sa.String(1024), nullable=False),
        sa.Column('ats_platform', sa.String(50), nullable=False, server_default='GENERIC'),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('company', sa.String(255), nullable=False),
        sa.Column('raw_content', sa.Text(), nullable=False),
        sa.Column('extracted_skills', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_jobs_user_id', 'jobs', ['user_id'])

    # 4. Create Applications Table
    op.create_table(
        'applications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('ats_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tailored_resume_data', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('pdf_s3_key', sa.String(512), nullable=True),
        sa.Column('applied_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_applications_user_id', 'applications', ['user_id'])
    op.create_index('ix_applications_status', 'applications', ['status'])

    # 5. Create Application History Table
    op.create_table(
        'application_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('from_status', sa.String(50), nullable=False),
        sa.Column('to_status', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('transitioned_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_application_history_application_id', 'application_history', ['application_id'])

    # 6. Create Outreach Emails Table
    op.create_table(
        'outreach_emails',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('application_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('recipient_email', sa.String(255), nullable=False),
        sa.Column('recipient_name', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(512), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='DRAFT'),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_outreach_emails_user_id', 'outreach_emails', ['user_id'])

    # 7. Create Refresh Tokens Table
    op.create_table(
        'refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('device_fingerprint', sa.String(128), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'])

    # 8. Create Usage Tracking Table
    op.create_table(
        'usage_tracking',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_usage_tracking_user_id', 'usage_tracking', ['user_id'])
    op.create_index('ix_usage_tracking_action_type', 'usage_tracking', ['action_type'])

    # =========================================================================
    # ROW-LEVEL SECURITY (RLS) POLICIES
    # =========================================================================
    # Enable RLS on multi-tenant core tables
    op.execute("ALTER TABLE master_profiles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE applications ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE outreach_emails ENABLE ROW LEVEL SECURITY;")

    # Master Profiles Tenant Isolation Policy
    op.execute("""
        CREATE POLICY tenant_isolation_master_profiles ON master_profiles
            FOR ALL
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);
    """)

    # Applications Tenant Isolation Policy
    op.execute("""
        CREATE POLICY tenant_isolation_applications ON applications
            FOR ALL
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);
    """)

    # Outreach Emails Tenant Isolation Policy
    op.execute("""
        CREATE POLICY tenant_isolation_outreach_emails ON outreach_emails
            FOR ALL
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID)
            WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);
    """)


def downgrade() -> None:
    # Drop RLS Policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_outreach_emails ON outreach_emails;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_applications ON applications;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_master_profiles ON master_profiles;")

    # Disable RLS
    op.execute("ALTER TABLE outreach_emails DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE applications DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE master_profiles DISABLE ROW LEVEL SECURITY;")

    # Drop Tables
    op.drop_table('usage_tracking')
    op.drop_table('refresh_tokens')
    op.drop_table('outreach_emails')
    op.drop_table('application_history')
    op.drop_table('applications')
    op.drop_table('jobs')
    op.drop_table('master_profiles')
    op.drop_table('users')

