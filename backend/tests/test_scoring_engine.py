import unittest
import numpy as np
from app.services.scoring_engine import ATSScoringEngine


class TestATSScoringEngine(unittest.TestCase):
    def test_identical_profile_and_jd(self):
        vec = np.array([0.5, 0.5, 0.5, 0.5])
        skills = {"Python", "FastAPI", "PostgreSQL", "Docker"}
        text = "Senior Python engineer building microservices with FastAPI and PostgreSQL on Docker."

        res = ATSScoringEngine.calculate_score(
            resume_embedding=vec,
            jd_embedding=vec,
            resume_skills=skills,
            jd_required_skills=skills,
            resume_text=text,
            jd_text=text,
            required_years=5.0,
            actual_years=5.0
        )

        self.assertGreaterEqual(res["composite_score"], 98.0)
        self.assertEqual(res["skill_coverage_score"], 100.0)
        self.assertEqual(res["experience_alignment_score"], 100.0)
        self.assertEqual(len(res["missing_skills"]), 0)

    def test_disjoint_skills_and_embeddings(self):
        vec_res = np.array([1.0, 0.0, 0.0, 0.0])
        vec_jd = np.array([0.0, 1.0, 0.0, 0.0])  # Orthogonal vectors

        res_skills = {"HTML", "CSS"}
        jd_skills = {"Rust", "Solidity", "Kubernetes", "C++"}

        res_text = "Junior web designer formatting HTML and CSS layouts."
        jd_text = "Core blockchain developer writing high-frequency Rust and C++ systems on Kubernetes."

        res = ATSScoringEngine.calculate_score(
            resume_embedding=vec_res,
            jd_embedding=vec_jd,
            resume_skills=res_skills,
            jd_required_skills=jd_skills,
            resume_text=res_text,
            jd_text=jd_text,
            required_years=7.0,
            actual_years=1.0
        )

        self.assertLessEqual(res["composite_score"], 35.0)
        self.assertEqual(res["skill_coverage_score"], 0.0)
        self.assertIn("LOW_MATCH", res["recommendation"])

    def test_canonical_skill_alias_matching(self):
        # Candidate has aliases, JD has canonical names
        candidate_skills = {"Postgres", "k8s", "React.js", "AWS"}
        jd_required = {"PostgreSQL", "Kubernetes", "React", "Amazon Web Services"}

        res = ATSScoringEngine.calculate_score(
            resume_embedding=None,
            jd_embedding=None,
            resume_skills=candidate_skills,
            jd_required_skills=jd_required,
            resume_text="Cloud software engineer",
            jd_text="Senior Cloud engineer",
            required_years=4.0,
            actual_years=4.0
        )

        # Through the canonical taxonomy, all 4 skills must be recognized as 100% matched!
        self.assertEqual(res["skill_coverage_score"], 100.0)
        self.assertEqual(len(res["missing_skills"]), 0)

    def test_experience_alignment_curve(self):
        # 1. Exact match
        score_exact = ATSScoringEngine._calculate_experience_alignment(5.0, 5.0)
        self.assertEqual(score_exact, 1.0)

        # 2. Within grace buffer (5 + 3 = 8 years)
        score_grace = ATSScoringEngine._calculate_experience_alignment(5.0, 8.0)
        self.assertEqual(score_grace, 1.0)

        # 3. Under-qualified (2.5 out of 5 years)
        score_under = ATSScoringEngine._calculate_experience_alignment(5.0, 2.5)
        self.assertEqual(score_under, 0.5)

        # 4. Over-qualified (12 years for 5-year role)
        # buffer = 9 years. over_diff = 3. score = 1.0 - 0.15 = 0.85
        score_over = ATSScoringEngine._calculate_experience_alignment(5.0, 12.0)
        self.assertEqual(score_over, 0.85)

        # 5. Heavy over-qualification clamped to floor (0.70)
        score_heavy = ATSScoringEngine._calculate_experience_alignment(5.0, 30.0)
        self.assertEqual(score_heavy, 0.70)

    def test_sublinear_tf_lexical_scoring(self):
        jd = "python fastapi postgresql docker kubernetes aws microservices"
        # Spammed resume repeating python 100 times
        resume_spammed = "python " * 100

        score = ATSScoringEngine._calculate_sublinear_lexical_score(resume_spammed, jd)
        # Sublinear TF should NOT allow single-word spam to game the lexical match
        self.assertLess(score, 0.40)

    def test_zero_boundary_handling(self):
        # 0 required years and empty required skills
        res = ATSScoringEngine.calculate_score(
            resume_embedding=None,
            jd_embedding=None,
            resume_skills=set(),
            jd_required_skills=set(),
            resume_text="",
            jd_text="",
            required_years=0.0,
            actual_years=2.0
        )

        self.assertIsNotNone(res["composite_score"])
        self.assertEqual(res["skill_coverage_score"], 100.0)
        self.assertEqual(res["experience_alignment_score"], 100.0)


if __name__ == "__main__":
    unittest.main()
