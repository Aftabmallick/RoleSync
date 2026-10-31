import unittest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.core.jwt import create_access_token
from app.tasks.tailor_tasks import run_tailoring_pipeline_task, orchestrator
from app.services.guardrails import (
    RobustGuardrailVerifier,
    GuardrailViolationException,
    TailoredResumeDraft,
    TailoredExperienceEntry,
    TailoredBulletPoint,
)
from app.services.llm_client import LLMClientService


class TestChallengerM1Verification(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.multi_exp_master_profile = {
            "personal": {
                "full_name": "Marcus Vance",
                "email": "marcus@vance.io",
                "phone": "+1 555-987-6543",
                "location": "San Francisco, CA"
            },
            "skills": [
                {"name": "Python"},
                {"name": "FastAPI"},
                {"name": "Docker"},
                {"name": "Kubernetes"},
                {"name": "PostgreSQL"},
                {"name": "Redis"},
                {"name": "Go"}
            ],
            "experience": [
                {
                    "company": "Alpha Networks",
                    "role": "Staff Infrastructure Engineer",
                    "bullets": [
                        {
                            "id": "exp1_b1",
                            "text": "Engineered distributed service mesh handling 50M requests per day with 99.99% uptime."
                        },
                        {
                            "id": "exp1_b2",
                            "text": "Optimized Redis caching layer reducing database query latency by 45% across all clusters."
                        }
                    ]
                },
                {
                    "company": "Beta Cloud",
                    "role": "Senior Backend Developer",
                    "bullets": [
                        {
                            "id": "exp2_b1",
                            "text": "Constructed asynchronous event pipeline using FastAPI and PostgreSQL for financial telemetry."
                        },
                        {
                            "id": "exp2_b2",
                            "text": "Automated Kubernetes canary deployments with GitOps, shortening release cycles by 4x."
                        }
                    ]
                }
            ]
        }

    # =========================================================================
    # CHALLENGE 1: Layer 1, 2, 4 Rejections vs Layer 3 NLI Degradation
    # =========================================================================

    def test_challenge_layer_1_schema_violation_is_rejected_not_degraded(self):
        """
        Verify that Layer 1 schema violations (e.g., summary > 600 chars or empty skills)
        are NOT degraded and cause the task to fail with status FAILED.
        """
        original_execute_layers = RobustGuardrailVerifier.execute_all_layers

        def mock_layer_1_violation(verifier_self, draft):
            raise GuardrailViolationException(
                "LAYER_1_SCHEMA",
                "Summary exceeds 600-character layout budget limit.",
                {"length": 750, "limit": 600}
            )

        task_id = "test_challenge_l1_fail"
        with patch.object(RobustGuardrailVerifier, "execute_all_layers", new=mock_layer_1_violation):
            celery_res = run_tailoring_pipeline_task.apply(
                kwargs={
                    "task_id": task_id,
                    "user_id": "usr_challenger_l1",
                    "master_profile": self.multi_exp_master_profile,
                    "raw_jd": "Senior Cloud Engineer requiring Python and Kubernetes.",
                    "target_role": "Staff Infrastructure Engineer",
                    "company_name": "Stripe",
                    "required_years": 5.0
                }
            )
            result = celery_res.get()

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("LAYER_1_SCHEMA", str(result["error"]))
        self.assertIsNone(result.get("tailored_draft"))

    def test_challenge_layer_2_hallucinated_company_is_rejected_not_degraded(self):
        """
        Verify that Layer 2 hallucination (company not present in master profile)
        is NOT degraded and causes the task to fail with status FAILED.
        """
        def mock_rewrite_with_fake_company(*args, **kwargs):
            return [{"id": "exp1_b1", "text": "Engineered service mesh."}]

        def mock_layer_2_violation(verifier_self, draft):
            # Simulate a draft that contains a hallucinated company
            raise GuardrailViolationException(
                "LAYER_2_SUBSET",
                "Hallucinated company detected: 'Google X Lab'",
                {"unauthorized_company": "Google X Lab"}
            )

        task_id = "test_challenge_l2_fail"
        with patch.object(RobustGuardrailVerifier, "execute_all_layers", new=mock_layer_2_violation):
            celery_res = run_tailoring_pipeline_task.apply(
                kwargs={
                    "task_id": task_id,
                    "user_id": "usr_challenger_l2",
                    "master_profile": self.multi_exp_master_profile,
                    "raw_jd": "Senior Cloud Engineer requiring Python.",
                    "target_role": "Staff Engineer",
                    "company_name": "Google",
                    "required_years": 5.0
                }
            )
            result = celery_res.get()

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("LAYER_2_SUBSET", str(result["error"]))
        self.assertIsNone(result.get("tailored_draft"))

    def test_challenge_layer_4_metric_fabrication_is_rejected_not_degraded(self):
        """
        Verify that Layer 4 metric fabrication (e.g. inflating $500k to $10M)
        is NOT degraded and causes the task to fail with status FAILED.
        """
        def mock_layer_4_violation(verifier_self, draft):
            raise GuardrailViolationException(
                "LAYER_4_METRIC",
                "Fabricated or altered quantitative metrics: {'$10000000'}",
                {"fabricated_metrics": ["$10000000"], "master_text": "Saved $500k"}
            )

        task_id = "test_challenge_l4_fail"
        with patch.object(RobustGuardrailVerifier, "execute_all_layers", new=mock_layer_4_violation):
            celery_res = run_tailoring_pipeline_task.apply(
                kwargs={
                    "task_id": task_id,
                    "user_id": "usr_challenger_l4",
                    "master_profile": self.multi_exp_master_profile,
                    "raw_jd": "Senior Cloud Engineer requiring Python.",
                    "target_role": "Staff Engineer",
                    "company_name": "Fintech Corp",
                    "required_years": 5.0
                }
            )
            result = celery_res.get()

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("LAYER_4_METRIC", str(result["error"]))
        self.assertIsNone(result.get("tailored_draft"))

    # =========================================================================
    # CHALLENGE 2: Multi-Bullet NLI Degradation Across Distinct Experiences
    # =========================================================================

    def test_challenge_multi_bullet_nli_failure_across_distinct_experiences(self):
        """
        Empirically verify that when multiple bullets across DIFFERENT job experiences
        fail Layer 3 NLI verification:
        1. All offending bullets revert to their authentic master bullets.
        2. All offending bullets receive the badge '🛡️ Original Bullet Preserved (factual entailment boundary)'.
        3. Non-offending bullets retain their tailored text and do NOT have the badge.
        4. The task completes with status 'COMPLETED'.
        """
        # Let exp1_b1 fail NLI and exp2_b1 fail NLI
        # While exp1_b2 and exp2_b2 pass NLI
        failing_bullet_ids = {"exp1_b1", "exp2_b1"}

        def mock_rewrite_failing(target_role, company_name, required_keywords, original_bullets):
            res = []
            for b in original_bullets:
                if b["id"] in failing_bullet_ids:
                    res.append({"id": b["id"], "text": b["text"] + " [REWRITTEN DRIFT]"})
                else:
                    res.append({"id": b["id"], "text": b["text"]})
            return res

        class MockNLIClient:
            def predict_nli(self, premise: str, hypothesis: str):
                if "[REWRITTEN DRIFT]" in hypothesis:
                    # Contradiction / low entailment
                    return {"entailment": 0.30, "contradiction": 0.65, "neutral": 0.05}
                else:
                    # Entailed / passing
                    return {"entailment": 0.95, "contradiction": 0.02, "neutral": 0.03}

        mock_nli = MockNLIClient()

        # Patch ONNXNLIEngine instantiation and rewrite_bullets
        with patch("app.services.llm_client.LLMClientService.rewrite_bullets", side_effect=mock_rewrite_failing), \
             patch("app.services.guardrails.ONNXNLIEngine", return_value=mock_nli):
            task_id = "test_challenge_multi_nli_degrade"
            celery_res = run_tailoring_pipeline_task.apply(
                kwargs={
                    "task_id": task_id,
                    "user_id": "usr_challenger_multi_nli",
                    "master_profile": self.multi_exp_master_profile,
                    "raw_jd": "We are seeking a Staff Engineer skilled in Python, FastAPI, Kubernetes, and Docker.",
                    "target_role": "Staff Infrastructure Engineer",
                    "company_name": "CloudScale",
                    "required_years": 5.0
                }
            )
            result = celery_res.get()

        self.assertEqual(result["status"], "COMPLETED")
        self.assertIsNone(result["error"])

        draft = result["tailored_draft"]
        self.assertIsNotNone(draft)
        self.assertEqual(len(draft["experience"]), 2)

        # Build bullet map by ID
        bullet_map = {}
        for exp in draft["experience"]:
            for b in exp["bullet_points"]:
                bullet_map[b["original_bullet_id"]] = b

        tag_badge = "🛡️ Original Bullet Preserved (factual entailment boundary)"

        # Check exp1_b1: should be degraded to master text and tagged
        exp1_b1_master = self.multi_exp_master_profile["experience"][0]["bullets"][0]["text"]
        self.assertEqual(bullet_map["exp1_b1"]["tailored_text"], exp1_b1_master)
        self.assertEqual(bullet_map["exp1_b1"]["tag"], tag_badge)
        self.assertEqual(bullet_map["exp1_b1"]["preservation_tag"], tag_badge)
        self.assertEqual(bullet_map["exp1_b1"]["keywords_emphasized"], [])

        # Check exp2_b1: should be degraded to master text and tagged
        exp2_b1_master = self.multi_exp_master_profile["experience"][1]["bullets"][0]["text"]
        self.assertEqual(bullet_map["exp2_b1"]["tailored_text"], exp2_b1_master)
        self.assertEqual(bullet_map["exp2_b1"]["tag"], tag_badge)
        self.assertEqual(bullet_map["exp2_b1"]["preservation_tag"], tag_badge)
        self.assertEqual(bullet_map["exp2_b1"]["keywords_emphasized"], [])

        # Check exp1_b2: passed NLI, so should NOT have degradation tag
        self.assertNotEqual(bullet_map["exp1_b2"]["tag"], tag_badge)

        # Check exp2_b2: passed NLI, so should NOT have degradation tag
        self.assertNotEqual(bullet_map["exp2_b2"]["tag"], tag_badge)

    def test_challenge_all_bullets_fail_nli_degrades_all(self):
        """
        Empirically verify that if ALL bullets across ALL experiences fail NLI,
        every single bullet is reverted to its authentic master bullet and tagged,
        and the task completes without crashing.
        """
        def mock_rewrite_all_bullets(target_role, company_name, required_keywords, original_bullets):
            return [{"id": b["id"], "text": b["text"] + " [ADAPTED REWRITE]"} for b in original_bullets]

        class MockAllFailNLIClient:
            def predict_nli(self, premise: str, hypothesis: str):
                if "[ADAPTED REWRITE]" in hypothesis:
                    return {"entailment": 0.10, "contradiction": 0.85, "neutral": 0.05}
                return {"entailment": 0.99, "contradiction": 0.01, "neutral": 0.0}

        mock_nli = MockAllFailNLIClient()
        tag_badge = "🛡️ Original Bullet Preserved (factual entailment boundary)"

        with patch("app.services.llm_client.LLMClientService.rewrite_bullets", side_effect=mock_rewrite_all_bullets), \
             patch("app.services.guardrails.ONNXNLIEngine", return_value=mock_nli):
            task_id = "test_challenge_all_fail_nli"
            celery_res = run_tailoring_pipeline_task.apply(
                kwargs={
                    "task_id": task_id,
                    "user_id": "usr_challenger_all_nli",
                    "master_profile": self.multi_exp_master_profile,
                    "raw_jd": "We are seeking a Staff Engineer skilled in Python and Docker.",
                    "target_role": "Staff Engineer",
                    "company_name": "CloudScale",
                    "required_years": 4.0
                }
            )
            result = celery_res.get()

        self.assertEqual(result["status"], "COMPLETED")
        draft = result["tailored_draft"]

        # Collect all master original bullet texts
        master_bullet_texts = {}
        for exp in self.multi_exp_master_profile["experience"]:
            for b in exp["bullets"]:
                master_bullet_texts[b["id"]] = b["text"]

        total_bullets_checked = 0
        for exp in draft["experience"]:
            for b in exp["bullet_points"]:
                b_id = b["original_bullet_id"]
                # Must be reverted to authentic master text
                self.assertEqual(b["tailored_text"], master_bullet_texts[b_id])
                # Must be tagged with factual entailment boundary badge
                self.assertEqual(b["tag"], tag_badge)
                self.assertEqual(b["preservation_tag"], tag_badge)
                total_bullets_checked += 1

        self.assertEqual(total_bullets_checked, 4)

    # =========================================================================
    # CHALLENGE 3: Candidate Profile Retrieval Edge Cases & Identity Enforcements
    # =========================================================================

    def test_challenge_candidate_profile_empty_dict_raises_400(self):
        resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Staff Engineer",
                "company_name": "Stripe",
                "raw_job_description": "Python developer needed.",
                "master_profile": {}
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "Master profile with candidate identity is required for tailoring")

    def test_challenge_candidate_profile_whitespace_name_raises_400(self):
        resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Staff Engineer",
                "company_name": "Stripe",
                "raw_job_description": "Python developer needed.",
                "master_profile": {
                    "personal": {"full_name": "   "},
                    "skills": [{"name": "Python"}],
                    "experience": [{"company": "Tech", "role": "Dev", "bullets": []}]
                }
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "Master profile with candidate identity is required for tailoring")

    def test_challenge_candidate_profile_empty_skills_raises_400(self):
        resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Staff Engineer",
                "company_name": "Stripe",
                "raw_job_description": "Python developer needed.",
                "master_profile": {
                    "personal": {"full_name": "Valid Candidate"},
                    "skills": [],
                    "experience": [{"company": "Tech", "role": "Dev", "bullets": []}]
                }
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "Master profile with candidate identity is required for tailoring")

    def test_challenge_candidate_profile_empty_experience_raises_400(self):
        resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Staff Engineer",
                "company_name": "Stripe",
                "raw_job_description": "Python developer needed.",
                "master_profile": {
                    "personal": {"full_name": "Valid Candidate"},
                    "skills": [{"name": "Python"}],
                    "experience": []
                }
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "Master profile with candidate identity is required for tailoring")

    def test_challenge_authenticated_user_without_saved_profile_raises_400(self):
        user_id = str(uuid.uuid4())
        token = create_access_token({"sub": user_id, "email": "noprofile@rolesync.dev", "tier": "PRO"})
        resp = self.client.post(
            "/api/v1/tailor",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "target_role": "Staff Engineer",
                "company_name": "Stripe",
                "raw_job_description": "Python developer needed."
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["detail"], "Master profile with candidate identity is required for tailoring")


if __name__ == "__main__":
    unittest.main()
