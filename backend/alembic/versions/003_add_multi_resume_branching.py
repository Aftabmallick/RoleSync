"""Add multi-resume branching database schema and Row-Level Security (RLS) policies

Revision ID: 003
Revises: 002_add_resume_versions
Create Date: 2026-11-02 07:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002_add_resume_versions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create resume_variants table
    op.create_table(
        'resume_variants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('target_role', sa.String(255), nullable=True),
        sa.Column('target_company', sa.String(255), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_resume_variants_user_id', 'resume_variants', ['user_id'])
    op.create_index('ix_resume_variants_user_target_role', 'resume_variants', ['user_id', 'target_role'])

    # 2. Create master_bullets table
    op.create_table(
        'master_bullets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('section', sa.String(100), nullable=False),
        sa.Column('bullet_text', sa.Text(), nullable=False),
        sa.Column('metrics', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_master_bullets_user_id', 'master_bullets', ['user_id'])

    # 3. Create resume_variant_bullets junction table
    op.create_table(
        'resume_variant_bullets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('variant_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('resume_variants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('bullet_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('master_bullets.id', ondelete='CASCADE'), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('is_tailored', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('tailored_text', sa.Text(), nullable=True),
    )
    op.create_index('ix_resume_variant_bullets_variant_id', 'resume_variant_bullets', ['variant_id'])
    op.create_index('ix_resume_variant_bullets_bullet_id', 'resume_variant_bullets', ['bullet_id'])
    op.create_index('ix_resume_variant_bullets_variant_bullet', 'resume_variant_bullets', ['variant_id', 'bullet_id'])

    # 4. PostgreSQL Row-Level Security (RLS) Policies
    bind = op.get_bind()
    is_postgres = bind is None or bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("ALTER TABLE resume_variants ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE master_bullets ENABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE resume_variant_bullets ENABLE ROW LEVEL SECURITY;")

        op.execute("""
            CREATE POLICY resume_variants_tenant_isolation ON resume_variants
            FOR ALL
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);
        """)

        op.execute("""
            CREATE POLICY master_bullets_tenant_isolation ON master_bullets
            FOR ALL
            USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID);
        """)

        op.execute("""
            CREATE POLICY resume_variant_bullets_tenant_isolation ON resume_variant_bullets
            FOR ALL
            USING (EXISTS (
                SELECT 1 FROM resume_variants v
                WHERE v.id = resume_variant_bullets.variant_id
                AND v.user_id = NULLIF(current_setting('app.current_user_id', true), '')::UUID
            ));
        """)


def downgrade() -> None:
    # 1. Drop RLS Policies and Disable RLS
    bind = op.get_bind()
    is_postgres = bind is None or bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("DROP POLICY IF EXISTS resume_variant_bullets_tenant_isolation ON resume_variant_bullets;")
        op.execute("DROP POLICY IF EXISTS master_bullets_tenant_isolation ON master_bullets;")
        op.execute("DROP POLICY IF EXISTS resume_variants_tenant_isolation ON resume_variants;")

        op.execute("ALTER TABLE resume_variant_bullets DISABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE master_bullets DISABLE ROW LEVEL SECURITY;")
        op.execute("ALTER TABLE resume_variants DISABLE ROW LEVEL SECURITY;")

    # 2. Drop Tables
    op.drop_index('ix_resume_variant_bullets_variant_bullet', table_name='resume_variant_bullets')
    op.drop_index('ix_resume_variant_bullets_bullet_id', table_name='resume_variant_bullets')
    op.drop_index('ix_resume_variant_bullets_variant_id', table_name='resume_variant_bullets')
    op.drop_table('resume_variant_bullets')

    op.drop_index('ix_master_bullets_user_id', table_name='master_bullets')
    op.drop_table('master_bullets')

    op.drop_index('ix_resume_variants_user_target_role', table_name='resume_variants')
    op.drop_index('ix_resume_variants_user_id', table_name='resume_variants')
    op.drop_table('resume_variants')
