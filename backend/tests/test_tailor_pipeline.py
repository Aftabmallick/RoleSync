import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.tasks.tailor_tasks import orchestrator, task_store


class TestTailorPipeline(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.sample_master_profile = {
            "personal": {
                "full_name": "Elena Rostova",
                "email": "elena@rostova.tech",
                "phone": "+1 555-432-8765",
                "location": "Seattle, WA"
            },
            "skills": [
                {"name": "Python"},
                {"name": "FastAPI"},
                {"name": "Docker"},
                {"name": "PostgreSQL"},
                {"name": "Kubernetes"}
            ],
            "experience": [
                {
                    "company": "Cloud Corp",
                    "role": "Backend Engineer",
                    "bullets": [
                        {
                            "id": "b_cloud_1",
                            "text": "Engineered distributed APIs with FastAPI and PostgreSQL, serving 10M requests daily."
                        }
                    ]
                }
            ]
        }

    def test_orchestrator_direct_execution(self):
        task_id = "test_direct_task_123"
        raw_jd = """
        Looking for a Backend Developer with strong skills in Python and FastAPI.
        Knowledge of PostgreSQL, Docker, and Kubernetes is required.
        """

        result = orchestrator.execute_tailoring_pipeline(
            task_id=task_id,
            user_id="usr_test_1",
            master_profile=self.sample_master_profile,
            raw_jd=raw_jd,
            target_role="Backend Developer",
            company_name="InnovateTech",
            required_years=3.0
        )

        self.assertEqual(result["status"], "COMPLETED")
        self.assertIsNotNone(result["ats_score"])
        self.assertGreater(result["ats_score"]["composite_score"], 65.0)
        self.assertIsNotNone(result["pdf_base64"])
        self.assertIsNone(result["error"])

    def test_async_endpoint_enqueue_and_poll(self):
        # 1. Post to /api/v1/tailor -> expect 202 Accepted
        post_resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Senior Cloud Engineer",
                "company_name": "Stripe",
                "raw_job_description": "We need a Senior Cloud Engineer experienced in Python, Docker, and Kubernetes.",
                "required_years": 4.0,
                "master_profile": self.sample_master_profile
            }
        )

        self.assertEqual(post_resp.status_code, 202)
        post_data = post_resp.json()
        self.assertIn("task_id", post_data)
        task_id = post_data["task_id"]

        # 2. Poll /api/v1/tailor/{task_id} -> background task executed in TestClient
        get_resp = self.client.get(f"/api/v1/tailor/{task_id}")
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.json()

        self.assertEqual(get_data["task_id"], task_id)
        self.assertEqual(get_data["status"], "COMPLETED")
        self.assertIsNotNone(get_data["ats_score"])
        self.assertIsNotNone(get_data["pdf_base64"])

    def test_tailor_missing_profile_raises_400(self):
        post_resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Senior Cloud Engineer",
                "company_name": "Stripe",
                "raw_job_description": "We need a Senior Cloud Engineer experienced in Python, Docker, and Kubernetes.",
                "required_years": 4.0
            }
        )
        self.assertEqual(post_resp.status_code, 400)
        self.assertEqual(
            post_resp.json().get("detail"),
            "Master profile with candidate identity is required for tailoring"
        )

    def test_tailor_incomplete_identity_raises_400(self):
        incomplete_profile = {
            "personal": {
                # missing full_name
                "email": "candidate@example.dev"
            },
            "skills": [{"name": "Python"}],
            "experience": [
                {
                    "company": "Tech Corp",
                    "role": "Software Engineer",
                    "bullets": [{"id": "b1", "text": "Built services with Python."}]
                }
            ]
        }
        post_resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Software Engineer",
                "company_name": "Stripe",
                "raw_job_description": "Looking for a Python Software Engineer.",
                "master_profile": incomplete_profile
            }
        )
        self.assertEqual(post_resp.status_code, 400)
        self.assertEqual(
            post_resp.json().get("detail"),
            "Master profile with candidate identity is required for tailoring"
        )

    def test_tailor_authenticated_user_db_profile_resolution(self):
        import uuid
        from app.core.jwt import create_access_token

        user_id = str(uuid.uuid4())
        token = create_access_token({"sub": user_id, "email": "testuser@rolesync.dev", "tier": "PRO"})
        headers = {"Authorization": f"Bearer {token}"}

        # Save profile first
        save_resp = self.client.post(
            "/api/v1/profile",
            headers=headers,
            json=self.sample_master_profile
        )
        self.assertEqual(save_resp.status_code, 200)

        # Call tailor without master_profile in body, relying on DB profile resolution
        tailor_resp = self.client.post(
            "/api/v1/tailor",
            headers=headers,
            json={
                "target_role": "Backend Engineer",
                "company_name": "InnovateTech",
                "raw_job_description": "Looking for a Backend Developer with skills in Python and FastAPI.",
                "required_years": 3.0
            }
        )
        self.assertEqual(tailor_resp.status_code, 202)
        task_id = tailor_resp.json()["task_id"]
        self.assertIsNotNone(task_id)

    def test_nli_guardrail_violation_degradation(self):
        from unittest.mock import patch
        from app.tasks.tailor_tasks import run_tailoring_pipeline_task
        from app.services.guardrails import GuardrailViolationException, RobustGuardrailVerifier

        original_layer_3 = RobustGuardrailVerifier._layer_3_nli_entailment_check

        def mock_layer_3_with_violation(verifier_self, draft):
            # If the bullet has not been degraded/preserved yet, simulate an NLI entailment failure
            for exp in draft.experience:
                for bullet in exp.bullet_points:
                    if not bullet.tag:
                        master_orig = verifier_self.master_bullets_index.get(bullet.original_bullet_id, {}).get("text", "")
                        raise GuardrailViolationException(
                            "LAYER_3_NLI",
                            f"Factual contradiction detected in tailored bullet: {bullet.tailored_text}",
                            {
                                "contradiction_score": 0.95,
                                "premise": master_orig,
                                "bullet_id": bullet.original_bullet_id
                            }
                        )
            return original_layer_3(verifier_self, draft)

        task_id = "test_nli_degrade_task"
        with patch.object(RobustGuardrailVerifier, "_layer_3_nli_entailment_check", new=mock_layer_3_with_violation):
            celery_res = run_tailoring_pipeline_task.apply(
                kwargs={
                    "task_id": task_id,
                    "user_id": "usr_test_degrade",
                    "master_profile": self.sample_master_profile,
                    "raw_jd": "Looking for a Python and FastAPI Backend Developer.",
                    "target_role": "Backend Developer",
                    "company_name": "InnovateTech",
                    "required_years": 3.0
                }
            )
            result = celery_res.get()

        self.assertEqual(result["status"], "COMPLETED")
        self.assertIsNone(result["error"])

        # Verify degraded bullet
        draft = result["tailored_draft"]
        self.assertIsNotNone(draft)
        bullet = draft["experience"][0]["bullet_points"][0]

        # Offending bullet was reverted to master original text and properly tagged
        expected_master_text = self.sample_master_profile["experience"][0]["bullets"][0]["text"]
        self.assertEqual(bullet["tailored_text"], expected_master_text)
        self.assertEqual(bullet["tag"], "🛡️ Original Bullet Preserved (factual entailment boundary)")
        self.assertEqual(bullet["preservation_tag"], "🛡️ Original Bullet Preserved (factual entailment boundary)")


if __name__ == "__main__":
    unittest.main()
