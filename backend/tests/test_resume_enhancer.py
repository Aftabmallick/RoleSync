import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestResumeEnhancerEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.sample_resume = {
            "personal": {
                "full_name": "Jordan Lee",
                "email": "jordan@example.com",
                "phone": "+1 555-123-4567",
                "location": "New York, NY",
                "linkedin": "linkedin.com/in/jordanlee"
            },
            "skills": [
                {"name": "Python"},
                {"name": "PostgreSQL"},
                {"name": "Docker"}
            ],
            "experience": [
                {
                    "company": "Nexus Systems",
                    "role": "Backend Engineer",
                    "start_date": "2021",
                    "end_date": "Present",
                    "location": "New York, NY",
                    "bullets": [
                        {
                            "id": "b_nexus_1",
                            "text": "Engineered REST APIs handling 5,000 req/sec reducing latency by 40%."
                        }
                    ]
                }
            ],
            "education": [
                {
                    "institution": "Columbia University",
                    "degree": "B.S.",
                    "field": "Computer Science",
                    "end_date": "2020",
                    "gpa": "3.8"
                }
            ],
            "section_order": ["experience", "education", "skills"]
        }

    def test_match_and_suggest_additions(self):
        jd = """
        We are looking for a Senior Backend Engineer at Stripe proficient in Python, FastAPI, Docker, and Kubernetes.
        Candidate will scale distributed payment microservices and PostgreSQL pipelines on AWS.
        """
        payload = {
            "job_description": jd,
            "target_role": "Senior Backend Engineer",
            "company_name": "Stripe",
            "resume": self.sample_resume
        }
        res = self.client.post("/api/v1/resume/match-and-suggest", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Score checks
        self.assertIn("current_score", data)
        self.assertIn("potential_score", data)
        self.assertGreater(data["potential_score"], data["current_score"]["composite_score"])
        self.assertGreater(data["score_boost"], 0)

        # Missing skills suggestions
        self.assertTrue(len(data["missing_skills"]) > 0)
        missing_names = [s["name"].lower() for s in data["missing_skills"]]
        self.assertTrue(any("fastapi" in m or "kubernetes" in m for m in missing_names))

        # Bullet improvement suggestions
        self.assertTrue(len(data["bullet_suggestions"]) > 0)
        b_sug = data["bullet_suggestions"][0]
        self.assertEqual(b_sug["original_id"], "b_nexus_1")
        self.assertIn("b_nexus_1", b_sug["original_id"])
        self.assertGreater(len(b_sug["suggested_text"]), len(b_sug["original_text"]))

    def test_apply_enhancements_and_save_version(self):
        apply_payload = {
            "base_resume": self.sample_resume,
            "target_role": "Senior Backend Engineer",
            "company_name": "Stripe",
            "version_name": "v1 - Stripe Tailored",
            "accepted_skills": ["FastAPI", "Kubernetes"],
            "accepted_summary": "Senior Backend Engineer specializing in Python, FastAPI, and Kubernetes.",
            "accepted_bullet_updates": [
                {
                    "original_id": "b_nexus_1",
                    "suggested_text": "Engineered high-throughput REST APIs using FastAPI and Kubernetes, handling 5,000 req/sec and reducing latency by 40%."
                }
            ]
        }
        res = self.client.post("/api/v1/resume/apply-enhancements", json=apply_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertIn("id", data)
        self.assertEqual(data["name"], "v1 - Stripe Tailored")
        self.assertEqual(data["target_company"], "Stripe")
        self.assertIsNotNone(data["pdf_base64"])
        version_id = data["id"]

        # Check that the version is listed in /resume/versions
        list_res = self.client.get("/api/v1/resume/versions")
        self.assertEqual(list_res.status_code, 200)
        vers = list_res.json()["versions"]
        self.assertTrue(any(v["id"] == version_id for v in vers))

        # Check deletion
        del_res = self.client.delete(f"/api/v1/resume/versions/{version_id}")
        self.assertEqual(del_res.status_code, 204)


if __name__ == "__main__":
    unittest.main()
