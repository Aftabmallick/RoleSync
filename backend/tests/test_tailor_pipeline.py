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
                "required_years": 4.0
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


if __name__ == "__main__":
    unittest.main()
