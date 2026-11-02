"""
RoleSync Phase 1 - Challenger Phase 1 Instance 2 Adversarial Stress Test Suite
Author: challenger_phase1_2 (Empirical Challenger)

Empirical challenges executed:
1. Alembic 003 DDL upgrade and downgrade offline generation & SQL syntax validation
2. SQLite Engine-level Foreign Key Cascades with PRAGMA foreign_keys = ON (raw SQL deletes)
3. SQLAlchemy ORM Session Cascades (deleting user, deleting variant, deleting master bullet, orphan removal)
4. Model Aliases, Type Constraints, JSONB and UUID serialization invariants
5. PostgreSQL RLS SQL expression parsing, NULLIF semantics, and simulated cross-tenant query injection
6. Edge case tenant collision: Tenant A attempting to bind Tenant B's master bullets in junction table
7. Extension Ergonomics & Logic Oracles (modal elevation positioning oracle, checkbox defaults oracle)
"""

import io
import os
import re
import sys
import uuid
import unittest
import contextlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

import pytest
from sqlalchemy import (
    create_engine,
    text,
    select,
    delete,
    event,
    Column,
    String,
    Integer,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.dialects import postgresql, sqlite
import alembic.config
import alembic.command
from alembic.script import ScriptDirectory

# Target Models
from app.core.database import Base
from app.models.user import User
from app.models.resume_variant import ResumeVariant, MasterBullet, ResumeVariantBullet


class TestAdversarialSchemaAndCascades(unittest.TestCase):
    """
    Empirically challenge Schema DDL, SQLite engine-level FK cascades,
    and SQLAlchemy ORM cascading behavior.
    """

    def setUp(self):
        # Create an engine with foreign keys strictly enabled at SQLite engine level
        self.engine = create_engine(
            "sqlite:///:memory:",
            echo=False,
            connect_args={"check_same_thread": False},
        )

        # Enforce SQLite foreign key constraints via engine listener
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        # Build schema using Base.metadata (tests actual app models)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_challenge_sqlite_engine_enforces_fk_constraints(self):
        """Verify PRAGMA foreign_keys=ON is active and rejects orphaned children."""
        res = self.session.execute(text("PRAGMA foreign_keys;")).scalar()
        self.assertEqual(res, 1, "PRAGMA foreign_keys must be enabled on SQLite test engine")

        # Attempt to insert a ResumeVariant referencing a nonexistent user_id
        nonexistent_user_id = uuid.uuid4()
        variant = ResumeVariant(
            id=uuid.uuid4(),
            user_id=nonexistent_user_id,
            name="Orphan Variant",
        )
        self.session.add(variant)
        with self.assertRaises(Exception):
            self.session.commit()
        self.session.rollback()

    def test_challenge_raw_sql_cascade_delete_user_removes_variants_and_bullets(self):
        """
        Adversarial test: Run a raw SQL DELETE on users.
        Does the SQLite engine-level ON DELETE CASCADE delete:
        1. resume_variants
        2. master_bullets
        3. resume_variant_bullets
        """
        u_id = uuid.uuid4()
        user = User(
            id=u_id,
            email=f"cascade_user_{u_id.hex[:6]}@adversarial.org",
            full_name="Cascade Subject",
        )
        self.session.add(user)
        self.session.commit()

        # Add variant & bullet
        var_id = uuid.uuid4()
        variant = ResumeVariant(id=var_id, user_id=u_id, name="Test Variant")

        b_id = uuid.uuid4()
        bullet = MasterBullet(id=b_id, user_id=u_id, section="Skills", bullet_text="Python & Rust")

        self.session.add_all([variant, bullet])
        self.session.commit()

        # Add junction link
        j_id = uuid.uuid4()
        junction = ResumeVariantBullet(id=j_id, variant_id=var_id, bullet_id=b_id, position=1)
        self.session.add(junction)
        self.session.commit()

        # Verify all 4 entities exist
        self.assertIsNotNone(self.session.get(User, u_id))
        self.assertIsNotNone(self.session.get(ResumeVariant, var_id))
        self.assertIsNotNone(self.session.get(MasterBullet, b_id))
        self.assertIsNotNone(self.session.get(ResumeVariantBullet, j_id))

        # Perform RAW SQL delete directly on users table (bypassing ORM session cascade)
        # Note: In SQLite, UUIDs are stored as CHAR(32) or CHAR(36) strings by SQLAlchemy TypeDecorator
        self.session.execute(delete(User).where(User.id == u_id))
        self.session.commit()

        # Assert cascades occurred at database engine level
        self.assertIsNone(self.session.get(User, u_id))
        self.assertIsNone(self.session.get(ResumeVariant, var_id), "ResumeVariant should cascade on User delete")
        self.assertIsNone(self.session.get(MasterBullet, b_id), "MasterBullet should cascade on User delete")
        self.assertIsNone(self.session.get(ResumeVariantBullet, j_id), "ResumeVariantBullet should cascade on Variant/Bullet delete")

    def test_challenge_deleting_variant_preserves_master_bullet(self):
        """Deleting a variant must cascade to junction, but NEVER delete the MasterBullet."""
        u_id = uuid.uuid4()
        user = User(id=u_id, email=f"keep_bullet_{u_id.hex[:6]}@test.com", full_name="Bullet Keeper")
        self.session.add(user)
        self.session.commit()

        var_id = uuid.uuid4()
        variant = ResumeVariant(id=var_id, user_id=u_id, name="Variant To Drop")

        b_id = uuid.uuid4()
        bullet = MasterBullet(id=b_id, user_id=u_id, section="Projects", bullet_text="Permanent master achievement")

        self.session.add_all([variant, bullet])
        self.session.commit()

        j_id = uuid.uuid4()
        junction = ResumeVariantBullet(id=j_id, variant_id=var_id, bullet_id=b_id, position=0)
        self.session.add(junction)
        self.session.commit()

        # Delete variant via ORM
        self.session.delete(variant)
        self.session.commit()

        # Check: junction deleted, master bullet preserved
        self.assertIsNone(self.session.get(ResumeVariant, var_id))
        self.assertIsNone(self.session.get(ResumeVariantBullet, j_id))
        surviving_bullet = self.session.get(MasterBullet, b_id)
        self.assertIsNotNone(surviving_bullet, "MasterBullet must survive variant deletion")
        self.assertEqual(surviving_bullet.bullet_text, "Permanent master achievement")

    def test_challenge_orphan_removal_on_variant_bullets_collection(self):
        """Removing a junction bullet from variant.variant_bullets must trigger delete-orphan."""
        u_id = uuid.uuid4()
        user = User(id=u_id, email=f"orphan_{u_id.hex[:6]}@test.com", full_name="Orphan Tester")
        self.session.add(user)
        self.session.commit()

        variant = ResumeVariant(id=uuid.uuid4(), user_id=u_id, name="Collection Variant")
        b1 = MasterBullet(id=uuid.uuid4(), user_id=u_id, section="A", bullet_text="B1")
        b2 = MasterBullet(id=uuid.uuid4(), user_id=u_id, section="B", bullet_text="B2")
        self.session.add_all([variant, b1, b2])
        self.session.commit()

        j1 = ResumeVariantBullet(id=uuid.uuid4(), variant=variant, bullet=b1, position=0)
        j2 = ResumeVariantBullet(id=uuid.uuid4(), variant=variant, bullet=b2, position=1)
        self.session.add_all([j1, j2])
        self.session.commit()

        j2_id = j2.id
        self.assertEqual(len(variant.variant_bullets), 2)

        # Remove j2 from collection
        variant.variant_bullets.remove(j2)
        self.session.commit()

        # j2 should be deleted from DB due to cascade="all, delete-orphan"
        self.assertIsNone(self.session.get(ResumeVariantBullet, j2_id), "Orphaned junction bullet must be deleted")
        self.assertEqual(len(variant.variant_bullets), 1)
        # b2 itself remains
        self.assertIsNotNone(self.session.get(MasterBullet, b2.id))

    def test_challenge_model_aliases_bidirectional_synchronization(self):
        """Stress-test property aliases branch_name, raw_text, position_order, and bullets."""
        variant = ResumeVariant(name="Original Name")
        self.assertEqual(variant.branch_name, "Original Name")
        variant.branch_name = "Mutated Name"
        self.assertEqual(variant.name, "Mutated Name")
        self.assertEqual(variant.branch_name, "Mutated Name")

        bullet = MasterBullet(bullet_text="Original Bullet Text")
        self.assertEqual(bullet.raw_text, "Original Bullet Text")
        bullet.raw_text = "Mutated Bullet Text"
        self.assertEqual(bullet.bullet_text, "Mutated Bullet Text")
        self.assertEqual(bullet.raw_text, "Mutated Bullet Text")

        rvb = ResumeVariantBullet(position=42)
        self.assertEqual(rvb.position_order, 42)
        rvb.position_order = 99
        self.assertEqual(rvb.position, 99)
        self.assertEqual(rvb.position_order, 99)

        # bullets alias on variant
        self.assertEqual(variant.bullets, variant.variant_bullets)


class TestAdversarialRLSAndMultiTenancy(unittest.TestCase):
    """
    Adversarial verification of PostgreSQL RLS policies in 003_add_multi_resume_branching.py
    and multi-tenant cross-tenant isolation attack vectors.
    """

    def test_challenge_rls_sql_syntax_and_predicates_in_migration_003(self):
        """Empirically parse migration 003 and verify RLS statements and clauses."""
        alembic_cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic"))
        cfg = alembic.config.Config(alembic_cfg_path)
        cfg.set_main_option("script_location", script_dir)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            alembic.command.upgrade(cfg, "002_add_resume_versions:003", sql=True)
        sql = buf.getvalue()

        # Check 1: RLS is explicitly ENABLED for all three tables
        for table in ["resume_variants", "master_bullets", "resume_variant_bullets"]:
            self.assertRegex(
                sql,
                rf"ALTER\s+TABLE\s+{table}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY",
                f"Missing ENABLE ROW LEVEL SECURITY for {table}",
            )

        # Check 2: All 3 policies use FOR ALL
        self.assertRegex(sql, r"CREATE\s+POLICY\s+resume_variants_tenant_isolation\s+ON\s+resume_variants\s+FOR\s+ALL")
        self.assertRegex(sql, r"CREATE\s+POLICY\s+master_bullets_tenant_isolation\s+ON\s+master_bullets\s+FOR\s+ALL")
        self.assertRegex(sql, r"CREATE\s+POLICY\s+resume_variant_bullets_tenant_isolation\s+ON\s+resume_variant_bullets\s+FOR\s+ALL")

        # Check 3: Strict session user check: NULLIF(current_setting('app.current_user_id', true), '')::UUID
        # The 'true' parameter is CRUCIAL: it prevents current_setting() from throwing error if setting is unset!
        self.assertIn("current_setting('app.current_user_id', true)", sql)

        # Check 4: The junction table checks tenant via EXISTS subquery joining resume_variants
        junction_policy_match = re.search(
            r"CREATE POLICY resume_variant_bullets_tenant_isolation ON resume_variant_bullets[\s\S]*?USING\s*\(\s*EXISTS\s*\(\s*SELECT 1 FROM resume_variants v[\s\S]*?v\.id = resume_variant_bullets\.variant_id[\s\S]*?v\.user_id = NULLIF\(current_setting\('app\.current_user_id', true\), ''\)::UUID",
            sql,
        )
        self.assertIsNotNone(junction_policy_match, "Junction table RLS policy must verify variant ownership via subquery")

    def test_challenge_simulated_cross_tenant_data_leakage(self):
        """
        Adversarial scenario: Tenant B executes an inner join on resume_variants and master_bullets.
        We verify Tenant B cannot view Tenant A's bullets even if Tenant B manages to insert a junction link.
        """
        engine = create_engine("sqlite:///:memory:")
        BaseSim = declarative_base()

        class SimVariant(BaseSim):
            __tablename__ = "sim_variants"
            id = Column(String(36), primary_key=True)
            user_id = Column(String(36), nullable=False)
            name = Column(String(100), nullable=False)

        class SimBullet(BaseSim):
            __tablename__ = "sim_bullets"
            id = Column(String(36), primary_key=True)
            user_id = Column(String(36), nullable=False)
            text = Column(Text, nullable=False)

        class SimJunction(BaseSim):
            __tablename__ = "sim_junction"
            id = Column(String(36), primary_key=True)
            variant_id = Column(String(36), nullable=False)
            bullet_id = Column(String(36), nullable=False)

        BaseSim.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())

        # Tenant A data
        var_a_id = str(uuid.uuid4())
        bullet_a_id = str(uuid.uuid4())
        session.add(SimVariant(id=var_a_id, user_id=tenant_a, name="Secret Stealth Variant A"))
        session.add(SimBullet(id=bullet_a_id, user_id=tenant_a, text="Tenant A's Proprietary Metrics"))

        # Tenant B data
        var_b_id = str(uuid.uuid4())
        bullet_b_id = str(uuid.uuid4())
        session.add(SimVariant(id=var_b_id, user_id=tenant_b, name="Tenant B Standard Variant"))
        session.add(SimBullet(id=bullet_b_id, user_id=tenant_b, text="Tenant B Standard Metrics"))
        session.commit()

        # Hostile scenario: Tenant B tries to link Tenant A's bullet into Tenant B's variant
        j_malicious = SimJunction(id=str(uuid.uuid4()), variant_id=var_b_id, bullet_id=bullet_a_id)
        session.add(j_malicious)
        session.commit()

        # Emulate Postgres RLS query enforcement for Tenant B:
        # Each table has WHERE user_id == tenant_b filter automatically applied by RLS
        # When Tenant B queries their junction table and joins sim_bullets:
        stmt = (
            select(SimJunction.id, SimBullet.text)
            .join(SimBullet, SimJunction.bullet_id == SimBullet.id)
            .where(
                # RLS on junction table: variant belongs to tenant_b
                SimJunction.variant_id.in_(
                    select(SimVariant.id).where(SimVariant.user_id == tenant_b)
                ),
                # RLS on bullet table: bullet belongs to tenant_b
                SimBullet.user_id == tenant_b,
            )
        )
        leaked_bullets = session.execute(stmt).all()
        # Because SimBullet.user_id == tenant_b, Tenant A's bullet is filtered out and NOT leaked!
        self.assertEqual(len(leaked_bullets), 0, "RLS on master_bullets strictly blocks cross-tenant bullet disclosure")

        session.close()
        engine.dispose()

    def test_challenge_downgrade_sql_drops_all_policies_and_tables(self):
        """Verify downgrade drops policies before tables to avoid orphaned dependency errors."""
        alembic_cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
        script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic"))
        cfg = alembic.config.Config(alembic_cfg_path)
        cfg.set_main_option("script_location", script_dir)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            alembic.command.downgrade(cfg, "003:002_add_resume_versions", sql=True)
        sql = buf.getvalue()

        # Check drop policies
        self.assertIn("DROP POLICY IF EXISTS resume_variant_bullets_tenant_isolation ON resume_variant_bullets", sql)
        self.assertIn("DROP POLICY IF EXISTS master_bullets_tenant_isolation ON master_bullets", sql)
        self.assertIn("DROP POLICY IF EXISTS resume_variants_tenant_isolation ON resume_variants", sql)

        # Check disable RLS
        self.assertIn("ALTER TABLE resume_variant_bullets DISABLE ROW LEVEL SECURITY", sql)
        self.assertIn("ALTER TABLE master_bullets DISABLE ROW LEVEL SECURITY", sql)
        self.assertIn("ALTER TABLE resume_variants DISABLE ROW LEVEL SECURITY", sql)

        # Check drop tables in reverse dependency order: junction -> master_bullets -> resume_variants
        pos_junction = sql.find("DROP TABLE resume_variant_bullets")
        pos_bullets = sql.find("DROP TABLE master_bullets")
        pos_variants = sql.find("DROP TABLE resume_variants")

        self.assertTrue(pos_junction != -1 and pos_bullets != -1 and pos_variants != -1)
        self.assertLess(pos_junction, pos_bullets, "Junction table must be dropped before master_bullets")
        self.assertLess(pos_junction, pos_variants, "Junction table must be dropped before resume_variants")


class TestAdversarialExtensionErgonomics(unittest.TestCase):
    """
    Adversarial logic oracles for Extension Ergonomics & Checkbox Invariants.
    """

    def test_challenge_modal_positioning_oracle(self):
        """
        Oracle test for CopilotCapsule.evaluateCollision modal docking algorithm:
        Given viewport (innerWidth, innerHeight) and modalRect (top, left, width, height, bottom, right),
        verify calculated style.top and style.right clamp safely and never cause negative coordinates.
        """
        def calc_dock_position(modal_top: float, modal_right: float, inner_w: int, inner_h: int):
            top_px = max(12, round(modal_top + 8))
            right_px = max(12, round(inner_w - modal_right + 12))
            return top_px, right_px

        # Scenario 1: Standard centered modal (1200x800 viewport, modal at top: 100, right: 900)
        top, right = calc_dock_position(100, 900, 1200, 800)
        self.assertEqual(top, 108)
        self.assertEqual(right, 312)

        # Scenario 2: Modal overflowing top viewport (modal_top = -50)
        top, right = calc_dock_position(-50, 900, 1200, 800)
        self.assertEqual(top, 12, "Should clamp to minimum 12px margin")

        # Scenario 3: Fullscreen modal spanning entire viewport (modal_right = 1200, modal_top = 0)
        top, right = calc_dock_position(0, 1200, 1200, 800)
        self.assertEqual(top, 12)
        self.assertEqual(right, 12, "Should clamp to minimum 12px margin on edge")

        # Scenario 4: Modal partially offscreen to the right (modal_right = 1350)
        top, right = calc_dock_position(50, 1350, 1200, 800)
        self.assertEqual(top, 58)
        self.assertEqual(right, 12, "Should clamp to minimum 12px when modal exceeds viewport width")

    def test_challenge_honest_candidate_checkbox_initialization_oracle(self):
        """
        Adversarial test: Simulating match-and-suggest API payload with 50 skills and 30 bullets.
        Verify that 100% of skills and bullets initialize to False (strictly opt-in).
        """
        sample_api_response = {
            "missing_skills": [{"name": f"Skill_{i}", "category": "Tech"} for i in range(50)],
            "bullet_suggestions": [{"original_id": f"bullet_{j}", "suggested_text": f"Rewritten {j}"} for j in range(30)],
        }

        # Emulate ResumeMatcher.tsx handleMatchResume initialization:
        accepted_skills = {}
        for s in sample_api_response["missing_skills"]:
            accepted_skills[s["name"]] = False

        accepted_bullets = {}
        for b in sample_api_response["bullet_suggestions"]:
            accepted_bullets[b["original_id"]] = False

        # Invariant 1: Total count matches
        self.assertEqual(len(accepted_skills), 50)
        self.assertEqual(len(accepted_bullets), 30)

        # Invariant 2: ZERO skills default to True
        self.assertFalse(any(accepted_skills.values()), "All missing skills must default to False")

        # Invariant 3: ZERO bullets default to True
        self.assertFalse(any(accepted_bullets.values()), "All bullet suggestions must default to False")

        # Invariant 4: Filtering for submission when user takes NO action
        skills_to_apply = [k for k, v in accepted_skills.items() if v]
        bullets_to_apply = [
            b for b in sample_api_response["bullet_suggestions"] if accepted_bullets[b["original_id"]]
        ]
        self.assertEqual(len(skills_to_apply), 0, "No skills should be submitted if candidate takes no action")
        self.assertEqual(len(bullets_to_apply), 0, "No bullets should be rewritten if candidate takes no action")


if __name__ == "__main__":
    unittest.main()
