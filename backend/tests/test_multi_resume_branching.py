import io
import unittest
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.core.database import Base
from app.models.user import User
from app.models.resume_variant import ResumeVariant, MasterBullet, ResumeVariantBullet
from app.models import (
    ResumeVariant as ExportedResumeVariant,
    MasterBullet as ExportedMasterBullet,
    ResumeVariantBullet as ExportedResumeVariantBullet,
)
import alembic.config
import alembic.command


class TestMultiResumeBranchingModels(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create an in-memory SQLite database for isolated model verification
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    def test_model_exports_and_aliases(self):
        """Verify models are properly exported and helper aliases function correctly."""
        self.assertIs(ResumeVariant, ExportedResumeVariant)
        self.assertIs(MasterBullet, ExportedMasterBullet)
        self.assertIs(ResumeVariantBullet, ExportedResumeVariantBullet)

        # ResumeVariant aliases
        variant = ResumeVariant(name="Backend Lead", target_role="Tech Lead")
        self.assertEqual(variant.branch_name, "Backend Lead")
        variant.branch_name = "Cloud Platform Lead"
        self.assertEqual(variant.name, "Cloud Platform Lead")

        # MasterBullet aliases
        bullet = MasterBullet(section="Experience", bullet_text="Built microservices")
        self.assertEqual(bullet.raw_text, "Built microservices")
        bullet.raw_text = "Architected high-throughput microservices"
        self.assertEqual(bullet.bullet_text, "Architected high-throughput microservices")

        # ResumeVariantBullet aliases
        rvb = ResumeVariantBullet(position=3)
        self.assertEqual(rvb.position_order, 3)
        rvb.position_order = 5
        self.assertEqual(rvb.position, 5)

    async def test_crud_and_relational_hierarchy(self):
        """Verify full lifecycle: User -> MasterBullet + ResumeVariant -> ResumeVariantBullet."""
        async with self.session_factory() as session:
            # 1. Create User
            user = User(
                email=f"candidate_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Alex Mercer",
                plan_tier="PRO",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            self.assertIsNotNone(user.id)

            # 2. Create Master Bullets
            bullet1 = MasterBullet(
                user_id=user.id,
                section="Backend Engineering",
                bullet_text="Scaled Kafka cluster to process 50,000 events/sec with zero loss.",
                metrics={"tps": 50000, "latency_reduction_pct": 35},
            )
            bullet2 = MasterBullet(
                user_id=user.id,
                section="Cloud Infrastructure",
                bullet_text="Provisioned multi-region Kubernetes clusters using Terraform and ArgoCD.",
                metrics={"regions": 3, "uptime": 99.99},
            )
            session.add_all([bullet1, bullet2])
            await session.commit()
            await session.refresh(bullet1)
            await session.refresh(bullet2)

            # 3. Create Resume Variant
            variant = ResumeVariant(
                user_id=user.id,
                name="Principal Distributed Systems",
                target_role="Distributed Systems Staff Engineer",
                target_company="Stripe",
            )
            session.add(variant)
            await session.commit()
            await session.refresh(variant)

            # 4. Link via Junction Table
            link1 = ResumeVariantBullet(
                variant_id=variant.id,
                bullet_id=bullet1.id,
                position=0,
                is_tailored=False,
            )
            link2 = ResumeVariantBullet(
                variant_id=variant.id,
                bullet_id=bullet2.id,
                position=1,
                is_tailored=True,
                tailored_text="Architected and provisioned multi-region Kubernetes clusters for high availability.",
            )
            session.add_all([link1, link2])
            await session.commit()

            # 5. Query Variant with joined bullets and assert ordering
            stmt = (
                select(ResumeVariant)
                .where(ResumeVariant.id == variant.id)
                .options(
                    selectinload(ResumeVariant.variant_bullets).selectinload(ResumeVariantBullet.bullet)
                )
            )
            result = await session.execute(stmt)
            loaded_variant = result.scalar_one()

            self.assertEqual(len(loaded_variant.variant_bullets), 2)
            self.assertEqual(loaded_variant.variant_bullets[0].position, 0)
            self.assertEqual(loaded_variant.variant_bullets[1].position, 1)
            self.assertFalse(loaded_variant.variant_bullets[0].is_tailored)
            self.assertTrue(loaded_variant.variant_bullets[1].is_tailored)
            self.assertEqual(
                loaded_variant.variant_bullets[0].bullet.bullet_text,
                bullet1.bullet_text,
            )
            self.assertEqual(
                loaded_variant.variant_bullets[1].tailored_text,
                "Architected and provisioned multi-region Kubernetes clusters for high availability.",
            )

    async def test_cascade_delete_variant_leaves_master_bullet_intact(self):
        """Deleting a resume variant must clean up junction bullets without deleting master bullets."""
        async with self.session_factory() as session:
            user = User(
                email=f"candidate_{uuid.uuid4().hex[:6]}@example.com",
                full_name="Jane Doe",
            )
            session.add(user)
            await session.commit()

            bullet = MasterBullet(
                user_id=user.id,
                section="Core",
                bullet_text="Built low-latency trading gateway in Rust.",
            )
            session.add(bullet)
            await session.commit()

            variant = ResumeVariant(user_id=user.id, name="Quant Variant")
            session.add(variant)
            await session.commit()

            link = ResumeVariantBullet(variant_id=variant.id, bullet_id=bullet.id, position=0)
            session.add(link)
            await session.commit()

            # Delete the variant
            await session.delete(variant)
            await session.commit()

            # Verify link is deleted (cascaded)
            link_check = await session.execute(
                select(ResumeVariantBullet).where(ResumeVariantBullet.variant_id == variant.id)
            )
            self.assertEqual(len(link_check.scalars().all()), 0)

            # Verify master bullet remains intact
            bullet_check = await session.execute(
                select(MasterBullet).where(MasterBullet.id == bullet.id)
            )
            self.assertIsNotNone(bullet_check.scalar_one_or_none())


class TestAlembicMigration003(unittest.TestCase):
    def _get_alembic_config(self):
        import os
        alembic_cfg_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        )
        script_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "alembic")
        )
        cfg = alembic.config.Config(alembic_cfg_path)
        cfg.set_main_option("script_location", script_dir)
        return cfg

    def test_migration_chain_and_revision_graph(self):
        """Verify migration revision metadata and lineage in the Alembic script directory."""
        from alembic.script import ScriptDirectory

        cfg = self._get_alembic_config()
        script = ScriptDirectory.from_config(cfg)

        head_rev = script.get_current_head()
        self.assertEqual(head_rev, "003")

        rev_003 = script.get_revision("003")
        self.assertIsNotNone(rev_003)
        self.assertEqual(rev_003.down_revision, "002_add_resume_versions")

        rev_002 = script.get_revision("002_add_resume_versions")
        self.assertIsNotNone(rev_002)
        self.assertEqual(rev_002.down_revision, "001_initial_schema_and_rls")

    def test_alembic_upgrade_sql_contains_tables_and_rls(self):
        """Verify generated SQL for migration 003 contains all required tables, indexes, and RLS policies."""
        import contextlib
        cfg = self._get_alembic_config()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            alembic.command.upgrade(cfg, "002_add_resume_versions:003", sql=True)
        sql = buf.getvalue()

        # Tables
        self.assertIn("CREATE TABLE resume_variants", sql)
        self.assertIn("CREATE TABLE master_bullets", sql)
        self.assertIn("CREATE TABLE resume_variant_bullets", sql)

        # Indexes
        self.assertIn("CREATE INDEX ix_resume_variants_user_id ON resume_variants (user_id)", sql)
        self.assertIn("CREATE INDEX ix_resume_variants_user_target_role ON resume_variants (user_id, target_role)", sql)
        self.assertIn("CREATE INDEX ix_master_bullets_user_id ON master_bullets (user_id)", sql)
        self.assertIn("CREATE INDEX ix_resume_variant_bullets_variant_id ON resume_variant_bullets (variant_id)", sql)
        self.assertIn("CREATE INDEX ix_resume_variant_bullets_bullet_id ON resume_variant_bullets (bullet_id)", sql)
        self.assertIn("CREATE INDEX ix_resume_variant_bullets_variant_bullet ON resume_variant_bullets (variant_id, bullet_id)", sql)

        # RLS Policies
        self.assertIn("ALTER TABLE resume_variants ENABLE ROW LEVEL SECURITY;", sql)
        self.assertIn("ALTER TABLE master_bullets ENABLE ROW LEVEL SECURITY;", sql)
        self.assertIn("ALTER TABLE resume_variant_bullets ENABLE ROW LEVEL SECURITY;", sql)
        self.assertIn("CREATE POLICY resume_variants_tenant_isolation ON resume_variants", sql)
        self.assertIn("CREATE POLICY master_bullets_tenant_isolation ON master_bullets", sql)
        self.assertIn("CREATE POLICY resume_variant_bullets_tenant_isolation ON resume_variant_bullets", sql)
        self.assertIn("NULLIF(current_setting('app.current_user_id', true), '')::UUID", sql)

    def test_alembic_downgrade_sql_contains_drops(self):
        """Verify generated downgrade SQL drops RLS policies and tables cleanly."""
        import contextlib
        cfg = self._get_alembic_config()

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            alembic.command.downgrade(cfg, "003:002_add_resume_versions", sql=True)
        sql = buf.getvalue()

        self.assertIn("DROP POLICY IF EXISTS resume_variants_tenant_isolation ON resume_variants", sql)
        self.assertIn("DROP POLICY IF EXISTS master_bullets_tenant_isolation ON master_bullets", sql)
        self.assertIn("DROP POLICY IF EXISTS resume_variant_bullets_tenant_isolation ON resume_variant_bullets", sql)
        self.assertIn("DROP TABLE resume_variant_bullets", sql)
        self.assertIn("DROP TABLE master_bullets", sql)
        self.assertIn("DROP TABLE resume_variants", sql)




if __name__ == "__main__":
    unittest.main()
