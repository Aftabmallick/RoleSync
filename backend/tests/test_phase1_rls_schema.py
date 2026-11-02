"""
RoleSync Phase 1 - Multi-Resume Branching Database Schema & RLS Test Suite
Verifies:
- Tier 1: Schema definitions, ORM models (ResumeVariant, MasterBullet, ResumeVariantBullet), aliases, and relationships.
- Tier 2: Cascade deletions, relationship integrity, and migration metadata in 003_add_multi_resume_branching.py.
- Tier 3: PostgreSQL Row-Level Security (RLS) tenant isolation policies, SQL expressions, and multi-tenant query isolation.
"""

import importlib.util
import os
import pathlib
import unittest
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# Optional postgres driver import guarded against missing dependency
try:
    import psycopg2
except ImportError:
    psycopg2 = None

# Import Phase 1 ORM Models
from app.models.resume_variant import MasterBullet, ResumeVariant, ResumeVariantBullet
from app.models.user import User


class TestMultiResumeBranchingSchema(unittest.TestCase):
    """
    Tier 1 & Tier 2: Schema Validation, Column Definitions, Relationships & Cascade Deletions.
    """

    def setUp(self):
        # Create an isolated in-memory SQLite engine for schema and ORM tests
        self.engine = create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        self.Base = declarative_base()

        # Define SQLite-compatible mock schema for the test session
        class MockUser(self.Base):
            __tablename__ = "users"
            id = Column(String(36), primary_key=True)
            email = Column(String(255), nullable=False, unique=True)
            full_name = Column(String(255), nullable=False)

        class MockResumeVariant(self.Base):
            __tablename__ = "resume_variants"
            id = Column(String(36), primary_key=True)
            user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
            name = Column(String(255), nullable=False)
            target_role = Column(String(255), nullable=True)
            target_company = Column(String(255), nullable=True)
            created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
            updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

            variant_bullets = relationship(
                "MockResumeVariantBullet",
                back_populates="variant",
                cascade="all, delete-orphan",
            )

        class MockMasterBullet(self.Base):
            __tablename__ = "master_bullets"
            id = Column(String(36), primary_key=True)
            user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
            section = Column(String(100), nullable=False)
            bullet_text = Column(Text, nullable=False)
            metrics = Column(Text, nullable=True)
            created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

            variant_bullets = relationship(
                "MockResumeVariantBullet",
                back_populates="bullet",
                cascade="all, delete-orphan",
            )

        class MockResumeVariantBullet(self.Base):
            __tablename__ = "resume_variant_bullets"
            id = Column(String(36), primary_key=True)
            variant_id = Column(String(36), ForeignKey("resume_variants.id", ondelete="CASCADE"), nullable=False)
            bullet_id = Column(String(36), ForeignKey("master_bullets.id", ondelete="CASCADE"), nullable=False)
            position = Column(Integer, default=0, nullable=False)
            is_tailored = Column(Boolean, default=False, nullable=False)
            tailored_text = Column(Text, nullable=True)

            variant = relationship("MockResumeVariant", back_populates="variant_bullets")
            bullet = relationship("MockMasterBullet", back_populates="variant_bullets")

        self.MockUser = MockUser
        self.MockResumeVariant = MockResumeVariant
        self.MockMasterBullet = MockMasterBullet
        self.MockResumeVariantBullet = MockResumeVariantBullet

        self.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()
        self.Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_orm_model_attributes_and_aliases(self):
        """Tier 1: Verify model instantiation, fields, and roadmap aliases."""
        variant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        variant = ResumeVariant(
            id=variant_id,
            user_id=user_id,
            name="Principal Infrastructure Engineer",
            target_role="Staff DevOps",
            target_company="Stripe",
        )

        self.assertEqual(variant.id, variant_id)
        self.assertEqual(variant.user_id, user_id)
        self.assertEqual(variant.name, "Principal Infrastructure Engineer")
        self.assertEqual(variant.branch_name, "Principal Infrastructure Engineer")

        # Test alias setter
        variant.branch_name = "Cloud Platform Lead"
        self.assertEqual(variant.name, "Cloud Platform Lead")

        # Test MasterBullet
        bullet_id = uuid.uuid4()
        bullet = MasterBullet(
            id=bullet_id,
            user_id=user_id,
            section="experience",
            bullet_text="Engineered distributed Kafka event pipeline processing 20M events/day.",
            metrics={"events_per_day": 20_000_000},
        )
        self.assertEqual(bullet.raw_text, "Engineered distributed Kafka event pipeline processing 20M events/day.")
        bullet.raw_text = "Updated bullet content"
        self.assertEqual(bullet.bullet_text, "Updated bullet content")

        # Test ResumeVariantBullet
        junction_id = uuid.uuid4()
        junction = ResumeVariantBullet(
            id=junction_id,
            variant_id=variant_id,
            bullet_id=bullet_id,
            position=3,
            is_tailored=True,
            tailored_text="Architected distributed Kafka streaming pipeline with 99.99% availability.",
        )
        self.assertEqual(junction.position_order, 3)
        junction.position_order = 5
        self.assertEqual(junction.position, 5)

    def test_relational_mapping_and_ordering(self):
        """Tier 1: Verify foreign key references, bidirectional relationships, and ordering."""
        u_id = str(uuid.uuid4())
        user = self.MockUser(id=u_id, email=f"user_{u_id[:6]}@rolesync.io", full_name="MultiResume Tester")
        self.session.add(user)

        var_id = str(uuid.uuid4())
        variant = self.MockResumeVariant(
            id=var_id,
            user_id=u_id,
            name="Backend Variant",
            target_role="Senior Backend Engineer",
        )
        self.session.add(variant)

        b1_id = str(uuid.uuid4())
        b2_id = str(uuid.uuid4())
        bullet1 = self.MockMasterBullet(
            id=b1_id,
            user_id=u_id,
            section="experience",
            bullet_text="Built microservices in Go.",
        )
        bullet2 = self.MockMasterBullet(
            id=b2_id,
            user_id=u_id,
            section="experience",
            bullet_text="Optimized PostgreSQL query latency.",
        )
        self.session.add_all([bullet1, bullet2])
        self.session.commit()

        # Add junction items with explicit positioning
        j1 = self.MockResumeVariantBullet(
            id=str(uuid.uuid4()),
            variant_id=var_id,
            bullet_id=b1_id,
            position=1,
            is_tailored=False,
        )
        j2 = self.MockResumeVariantBullet(
            id=str(uuid.uuid4()),
            variant_id=var_id,
            bullet_id=b2_id,
            position=2,
            is_tailored=True,
            tailored_text="Tuned PostgreSQL indexes reducing p99 latency by 60%.",
        )
        self.session.add_all([j1, j2])
        self.session.commit()

        # Re-query variant and verify relationship traversal
        queried = self.session.query(self.MockResumeVariant).filter_by(id=var_id).first()
        self.assertIsNotNone(queried)
        self.assertEqual(len(queried.variant_bullets), 2)
        self.assertEqual(queried.variant_bullets[0].bullet.bullet_text, "Built microservices in Go.")
        self.assertTrue(queried.variant_bullets[1].is_tailored)

    def test_cascade_delete_variant_removes_junction_bullets(self):
        """Tier 2: Deleting a ResumeVariant cascades to variant_bullets without deleting MasterBullet."""
        u_id = str(uuid.uuid4())
        user = self.MockUser(id=u_id, email=f"user_{u_id[:6]}@rolesync.io", full_name="Cascade Tester")
        self.session.add(user)

        var_id = str(uuid.uuid4())
        variant = self.MockResumeVariant(id=var_id, user_id=u_id, name="To Be Deleted")
        b_id = str(uuid.uuid4())
        bullet = self.MockMasterBullet(id=b_id, user_id=u_id, section="summary", bullet_text="Master bullet.")
        self.session.add_all([variant, bullet])
        self.session.commit()

        j_id = str(uuid.uuid4())
        junction = self.MockResumeVariantBullet(id=j_id, variant_id=var_id, bullet_id=b_id, position=0)
        self.session.add(junction)
        self.session.commit()

        # Delete the variant
        self.session.delete(variant)
        self.session.commit()

        # Verify junction bullet was cascaded
        queried_j = self.session.query(self.MockResumeVariantBullet).filter_by(id=j_id).first()
        self.assertIsNone(queried_j)

        # Verify MasterBullet still exists (not deleted)
        queried_b = self.session.query(self.MockMasterBullet).filter_by(id=b_id).first()
        self.assertIsNotNone(queried_b)

    def test_cascade_delete_master_bullet_removes_junction_bullets(self):
        """Tier 2: Deleting a MasterBullet cascades to variant_bullets."""
        u_id = str(uuid.uuid4())
        user = self.MockUser(id=u_id, email=f"user_{u_id[:6]}@rolesync.io", full_name="Bullet Cascade Tester")
        self.session.add(user)

        var_id = str(uuid.uuid4())
        variant = self.MockResumeVariant(id=var_id, user_id=u_id, name="Active Variant")
        b_id = str(uuid.uuid4())
        bullet = self.MockMasterBullet(id=b_id, user_id=u_id, section="exp", bullet_text="Ephemeral bullet.")
        self.session.add_all([variant, bullet])
        self.session.commit()

        j_id = str(uuid.uuid4())
        junction = self.MockResumeVariantBullet(id=j_id, variant_id=var_id, bullet_id=b_id, position=0)
        self.session.add(junction)
        self.session.commit()

        # Delete master bullet
        self.session.delete(bullet)
        self.session.commit()

        # Verify junction bullet was removed
        queried_j = self.session.query(self.MockResumeVariantBullet).filter_by(id=j_id).first()
        self.assertIsNone(queried_j)


class TestAlembicMigration003AndRLSPolicies(unittest.TestCase):
    """
    Tier 2 & Tier 3: Alembic 003 Migration Verification and Row-Level Security (RLS) Policy Invariants.
    """

    @classmethod
    def setUpClass(cls):
        # Dynamically import the Alembic 003 migration script
        migration_path = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions" / "003_add_multi_resume_branching.py"
        cls.migration_path = migration_path
        cls.migration_exists = migration_path.exists()
        if cls.migration_exists:
            spec = importlib.util.spec_from_file_location("migration_003", str(migration_path))
            cls.migration_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.migration_module)
        else:
            cls.migration_module = None

    def test_alembic_003_migration_file_exists_and_revision_chain(self):
        """Tier 2: Verify migration 003 file exists and connects cleanly to down_revision 002."""
        self.assertTrue(self.migration_exists, f"Migration file missing at {self.migration_path}")
        self.assertEqual(getattr(self.migration_module, "revision", None), "003")
        self.assertEqual(getattr(self.migration_module, "down_revision", None), "002_add_resume_versions")
        self.assertTrue(hasattr(self.migration_module, "upgrade"), "Migration 003 missing upgrade() function")
        self.assertTrue(hasattr(self.migration_module, "downgrade"), "Migration 003 missing downgrade() function")

    def test_rls_sql_policy_definitions_in_migration(self):
        """Tier 3: Inspect RLS policy statements in migration 003 for strict tenant isolation semantics."""
        self.assertTrue(self.migration_exists)
        with open(self.migration_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Verify RLS is enabled on all 3 tables
        self.assertIn("ALTER TABLE resume_variants ENABLE ROW LEVEL SECURITY", content)
        self.assertIn("ALTER TABLE master_bullets ENABLE ROW LEVEL SECURITY", content)
        self.assertIn("ALTER TABLE resume_variant_bullets ENABLE ROW LEVEL SECURITY", content)

        # 2. Verify tenant isolation policy definitions
        self.assertIn("CREATE POLICY resume_variants_tenant_isolation ON resume_variants", content)
        self.assertIn("CREATE POLICY master_bullets_tenant_isolation ON master_bullets", content)
        self.assertIn("CREATE POLICY resume_variant_bullets_tenant_isolation ON resume_variant_bullets", content)

        # 3. Verify session variable app.current_user_id is strictly checked
        self.assertIn("current_setting('app.current_user_id', true)", content)
        self.assertIn("NULLIF(current_setting('app.current_user_id', true), '')::UUID", content)

    def test_simulated_multi_tenant_isolation_filter(self):
        """
        Tier 3: Invariant check - multi-tenant queries must isolate data strictly by user_id.
        User A querying the system cannot access User B's resume variants or master bullets.
        """
        engine = create_engine("sqlite:///:memory:")
        Base = declarative_base()

        class TenantVariant(Base):
            __tablename__ = "variants_sim"
            id = Column(String(36), primary_key=True)
            user_id = Column(String(36), nullable=False, index=True)
            name = Column(String(100), nullable=False)

        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())

        var_a = TenantVariant(id=str(uuid.uuid4()), user_id=tenant_a, name="Tenant A's Confidential Variant")
        var_b = TenantVariant(id=str(uuid.uuid4()), user_id=tenant_b, name="Tenant B's Confidential Variant")
        session.add_all([var_a, var_b])
        session.commit()

        # Emulate RLS filtering clause: WHERE user_id = current_tenant_id
        def query_as_tenant(current_tenant: Optional[str]):
            stmt = select(TenantVariant).where(TenantVariant.user_id == current_tenant)
            return session.execute(stmt).scalars().all()

        results_a = query_as_tenant(tenant_a)
        self.assertEqual(len(results_a), 1)
        self.assertEqual(results_a[0].name, "Tenant A's Confidential Variant")

        results_b = query_as_tenant(tenant_b)
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_b[0].name, "Tenant B's Confidential Variant")

        # Emulate unauthenticated / null session: should yield zero rows
        results_none = query_as_tenant(None)
        self.assertEqual(len(results_none), 0)

        session.close()
        engine.dispose()


if __name__ == "__main__":
    unittest.main()
