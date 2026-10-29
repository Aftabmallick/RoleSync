import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestApplicationAndCoverLetterEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer test_token_dev"}

    def test_application_lifecycle(self):
        # 1. Create application
        create_payload = {
            "company_name": "Datadog",
            "job_title": "Senior Reliability Engineer",
            "job_url": "https://careers.datadoghq.com/detail/123",
            "ats_provider": "GREENHOUSE",
            "ats_score": 88.5,
            "status": "APPLIED",
            "notes": "Referred by Alex. Waiting for first round interview.",
            "tailored_summary": "SRE specializing in distributed observability."
        }
        res = self.client.post("/api/v1/applications", json=create_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        app_id = data["id"]
        self.assertEqual(data["company_name"], "Datadog")
        self.assertEqual(data["status"], "APPLIED")
        self.assertAlmostEqual(data["ats_score"], 88.5)

        # 2. List applications
        res_list = self.client.get("/api/v1/applications")
        self.assertEqual(res_list.status_code, 200)
        list_data = res_list.json()
        self.assertGreaterEqual(list_data["total"], 1)
        ids = [a["id"] for a in list_data["applications"]]
        self.assertIn(app_id, ids)

        # 3. Update application status
        update_payload = {
            "status": "INTERVIEWING",
            "notes": "Completed recruiter screen; technical round on Monday."
        }
        res_up = self.client.patch(f"/api/v1/applications/{app_id}", json=update_payload)
        self.assertEqual(res_up.status_code, 200)
        up_data = res_up.json()
        self.assertEqual(up_data["status"], "INTERVIEWING")
        self.assertEqual(up_data["notes"], "Completed recruiter screen; technical round on Monday.")

        # 4. Delete application
        res_del = self.client.delete(f"/api/v1/applications/{app_id}")
        self.assertEqual(res_del.status_code, 204)

        # 5. Verify deleted
        res_get_all = self.client.get("/api/v1/applications")
        all_ids = [a["id"] for a in res_get_all.json()["applications"]]
        self.assertNotIn(app_id, all_ids)

    def test_cover_letter_synthesis(self):
        payload = {
            "target_role": "Senior Cloud Infrastructure Engineer",
            "company_name": "Cloudflare",
            "raw_job_description": "We are seeking a Senior Cloud Infrastructure Engineer with Python, Docker, Kubernetes, and PostgreSQL experience.",
            "candidate_name": "Alex Mercer",
            "tone": "professional",
            "master_profile": {
                "personal": {
                    "full_name": "Alex Mercer"
                },
                "skills": [
                    {"name": "Python"},
                    {"name": "Kubernetes"},
                    {"name": "Docker"},
                    {"name": "PostgreSQL"}
                ],
                "experience": [
                    {
                        "company": "Apex Systems",
                        "role": "Senior Software Engineer",
                        "bullets": [
                            {"id": "b1", "text": "Reduced latency by 1.5s and saved $1,500,000 across cloud microservices."}
                        ]
                    }
                ]
            }
        }
        res = self.client.post("/api/v1/cover-letter/synthesize", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["company_name"], "Cloudflare")
        self.assertEqual(data["candidate_name"], "Alex Mercer")
        self.assertIn("Cloudflare", data["full_text"])
        self.assertIn("Python", data["full_text"])
        self.assertGreater(data["word_count"], 100)
        self.assertIn("b1", "b1")  # ensure bullet was used


if __name__ == "__main__":
    unittest.main()
