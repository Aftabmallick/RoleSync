import unittest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.tasks.tailor_tasks import orchestrator
from app.services.resume_parser import resume_parser
from app.services.cover_letter_service import CoverLetterService
from app.api.v1.endpoints.profile import encrypted_profiles_db
from app.core.jwt import create_access_token


class TestM2MockPurgeAndRFC7807Gating(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        encrypted_profiles_db.clear()

    def test_tailor_uninitialized_profile_returns_rfc7807_problem_details(self):
        """Verifies RFC 7807 Problem Details on uninitialized profile tailoring request."""
        resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Platform Engineer",
                "company_name": "Datadog",
                "raw_job_description": "We need a Platform Engineer with Kubernetes and Go experience.",
                "required_years": 3.0
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("application/problem+json", resp.headers.get("content-type", ""))
        body = resp.json()

        # Strict RFC 7807 fields
        self.assertEqual(body.get("title"), "PROFILE_UNINITIALIZED")
        self.assertEqual(body.get("type"), "https://rolesync.ai/errors/profile-uninitialized")
        self.assertEqual(body.get("status"), 400)
        self.assertEqual(body.get("detail"), "Master profile with candidate identity is required for tailoring")
        self.assertIn("instance", body)
        self.assertTrue(body["instance"].startswith("/api/v1/tailor"))

    def test_tailor_empty_dict_profile_returns_rfc7807_problem_details(self):
        """Verifies RFC 7807 gating when master_profile is an empty dictionary."""
        resp = self.client.post(
            "/api/v1/tailor",
            json={
                "target_role": "Backend Engineer",
                "company_name": "Stripe",
                "raw_job_description": "Looking for Python and FastAPI developers.",
                "master_profile": {}
            }
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("application/problem+json", resp.headers.get("content-type", ""))
        body = resp.json()
        self.assertEqual(body.get("title"), "PROFILE_UNINITIALIZED")
        self.assertEqual(body.get("status"), 400)

    def test_profile_uninitialized_get_returns_rfc7807(self):
        """Verifies GET /api/v1/profile raises ProfileUninitializedException when uninitialized."""
        resp = self.client.get("/api/v1/profile")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("application/problem+json", resp.headers.get("content-type", ""))
        body = resp.json()
        self.assertEqual(body.get("title"), "PROFILE_UNINITIALIZED")
        self.assertEqual(body.get("status"), 400)
        # Ensure Alex Mercer is nowhere in the error payload
        self.assertNotIn("Alex Mercer", str(body))
        self.assertNotIn("Apex Systems", str(body))

    def test_tailor_pipeline_orchestrator_rejects_missing_experience_without_synthetic_fallback(self):
        """Ensures tailor_tasks pipeline halts on empty experience and never injects Apex Systems."""
        empty_exp_profile = {
            "personal": {"full_name": "Authentic Candidate", "email": "candidate@real.tech"},
            "skills": [{"name": "Python"}, {"name": "Docker"}],
            "experience": []
        }
        result = orchestrator.execute_tailoring_pipeline(
            task_id=f"test_purge_{uuid.uuid4().hex[:8]}",
            user_id="usr_purge_test",
            master_profile=empty_exp_profile,
            raw_jd="Seeking Python engineer.",
            target_role="Software Engineer",
            company_name="TechCorp"
        )
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("Candidate master profile contains no experience records", result["error"])
        # Ensure Apex Systems was never injected into profile
        self.assertEqual(len(empty_exp_profile["experience"]), 0)

    def test_resume_parser_empty_dates_does_not_inject_apex_systems(self):
        """Ensures resume parser does not inject fake Apex Systems experience on unstructured text."""
        raw_text_no_dates = """
        John Doe
        john@doe.dev
        (555) 123-4567
        SKILLS
        Python, FastAPI, Docker
        EXPERIENCE
        Worked on various engineering tasks and systems without clear date formats.
        """
        parsed = resume_parser.parse_resume_text(raw_text_no_dates)
        self.assertIsInstance(parsed["experience"], list)
        # Verify Apex Systems and Alex Mercer are not present
        exp_companies = [e.get("company", "") for e in parsed["experience"]]
        self.assertNotIn("Apex Systems", exp_companies)
        for e in parsed["experience"]:
            for b in e.get("bullets", []):
                self.assertNotIn("saving $1,500,000", b.get("text", ""))

    def test_cover_letter_service_does_not_default_to_alex_mercer(self):
        """Ensures cover letter generator does not default to Alex Mercer or TitanRAG."""
        res = CoverLetterService.generate_cover_letter(
            target_role="Software Architect",
            company_name="Acme Corp",
            raw_job_description="Seeking a Software Architect with Python and Kubernetes skills.",
            candidate_name=None,
            master_profile={
                "personal": {},
                "skills": [{"name": "Python"}, {"name": "Kubernetes"}],
                "experience": []
            }
        )
        self.assertNotIn("Alex Mercer", res.full_text)
        self.assertNotIn("Alex Mercer", res.candidate_name)
        self.assertNotIn("TitanRAG", res.full_text)


if __name__ == "__main__":
    unittest.main()
