import unittest
import base64
from fastapi.testclient import TestClient
from app.main import app
from app.core.jwt import create_access_token
from app.services.resume_parser import resume_parser, ResumeParserService


class TestResumeParserService(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.token = create_access_token({"sub": "user_parser_test"})
        self.auth_headers = {"Authorization": f"Bearer {self.token}"}

    def test_parse_prose_resume_extraction(self):
        sample_resume_text = """
        Marcus Vance
        marcus@vance.io
        +1 (415) 555-0192
        San Francisco, CA
        linkedin.com/in/marcus-vance
        github.com/marcusvance

        PROFESSIONAL SUMMARY
        Principal Infrastructure Architect with 8+ years experience scaling globally distributed payment infrastructure across AWS and Kubernetes.

        EXPERIENCE
        Stripe - Principal Infrastructure Engineer
        2020 - Present
        - Engineered distributed payment ledger processing $1.8B in annual transactional volume.
        - Reduced P99 query latency by 45% through PostgreSQL read replica sharding.
        - Spearheaded zero-downtime migration of 150+ microservices to Kubernetes on AWS.

        Vanguard Cloud - Senior Systems Engineer
        2017 - 2020
        - Scaled Cassandra cluster to handle 2.5M queries per second with 99.999% availability.
        - Saved $450,000 annually by refactoring Docker container auto-scaling heuristics.

        EDUCATION
        Stanford University
        B.S. in Computer Science
        2017
        GPA: 3.92

        TECHNICAL SKILLS
        Python, Go, Docker, Kubernetes, AWS, PostgreSQL, Redis, Cassandra, Terraform, CI/CD
        """

        result = resume_parser.parse_resume_text(sample_resume_text)

        # 1. Contact validation
        self.assertEqual(result["personal"]["full_name"], "Marcus Vance")
        self.assertEqual(result["personal"]["email"], "marcus@vance.io")
        self.assertEqual(result["personal"]["phone"], "+1 (415) 555-0192")
        self.assertIn("San Francisco", result["personal"]["location"])
        self.assertIn("marcus-vance", result["personal"]["linkedin"])
        self.assertIn("marcusvance", result["personal"]["github"])

        # 2. Canonical Skill Extraction
        skill_names = {s["name"].lower() for s in result["skills"]}
        self.assertIn("python", skill_names)
        self.assertIn("docker", skill_names)
        self.assertIn("kubernetes", skill_names)
        self.assertIn("postgresql", skill_names)
        self.assertIn("redis", skill_names)

        # 3. Work Experience & Metrics
        self.assertGreaterEqual(len(result["experience"]), 1)
        first_role = result["experience"][0]
        self.assertIn("Stripe", first_role["company"])
        self.assertGreaterEqual(len(first_role["bullets"]), 1)
        # Verify bullet point IDs are present for guardrail tracking
        for b in first_role["bullets"]:
            self.assertTrue(b["id"].startswith("b_"))
            self.assertTrue(len(b["text"]) > 10)

        # 4. Education
        self.assertGreaterEqual(len(result["education"]), 1)
        edu = result["education"][0]
        self.assertEqual(edu["degree"], "B.S.")
        self.assertIn("Computer Science", edu["field"])

    def test_parse_resume_api_endpoint(self):
        sample_text = """
        Elena Rostova
        elena.rostova@tech.io
        (206) 555-9876
        Seattle, WA
        EXPERIENCE
        Amazon Web Services - Senior Software Engineer
        2021 - Present
        - Refactored DynamoDB ingestion pipeline achieving 35% latency reduction.
        EDUCATION
        University of Washington, M.S. in Software Engineering, 2021
        SKILLS
        Python, FastAPI, Docker, Kubernetes, AWS, PostgreSQL
        """

        # Post to endpoint
        resp = self.client.post(
            "/api/v1/profile/parse-resume",
            headers=self.auth_headers,
            json={"raw_text": sample_text}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertGreaterEqual(data["detected_skills_count"], 4)
        self.assertGreaterEqual(data["detected_experience_count"], 1)

        profile = data["profile"]
        self.assertEqual(profile["personal"]["full_name"], "Elena Rostova")
        self.assertEqual(profile["personal"]["email"], "elena.rostova@tech.io")

    def test_empty_resume_raises_error(self):
        resp = self.client.post(
            "/api/v1/profile/parse-resume",
            headers=self.auth_headers,
            json={"raw_text": "   "}
        )
        self.assertEqual(resp.status_code, 422)

    def test_parse_docx_resume(self):
        import zipfile
        import io

        # Synthesize a valid in-memory .docx archive
        docx_buffer = io.BytesIO()
        with zipfile.ZipFile(docx_buffer, "w") as z:
            doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>David Miller</w:t></w:r></w:p>
                <w:p><w:r><w:t>david@miller.dev | San Francisco, CA</w:t></w:r></w:p>
                <w:p><w:r><w:t>Skills: Python, Go, Docker, Kubernetes, PostgreSQL</w:t></w:r></w:p>
                <w:p><w:r><w:t>Experience: Senior Engineer at Apex Systems, built microservices.</w:t></w:r></w:p>
              </w:body>
            </w:document>"""
            z.writestr("word/document.xml", doc_xml)

        docx_bytes = docx_buffer.getvalue()
        text = resume_parser.extract_text_from_docx(docx_bytes)
        self.assertIn("David Miller", text)
        self.assertIn("Python", text)

        parsed = resume_parser.parse_docx(docx_bytes)
        self.assertIn("personal", parsed)
        self.assertIn("skills", parsed)


if __name__ == "__main__":
    unittest.main()

