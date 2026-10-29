import unittest
from app.services.taxonomy import taxonomy_service, normalize_skill, get_skill_category


class TestSkillTaxonomy(unittest.TestCase):
    def test_canonical_normalization(self):
        cases = [
            ("k8s", "kubernetes"),
            ("Kubernetes", "kubernetes"),
            ("Kube", "kubernetes"),
            ("Postgres", "postgresql"),
            ("PostgreSQL", "postgresql"),
            ("PSQL", "postgresql"),
            ("React.js", "react"),
            ("REACTJS", "react"),
            ("react", "react"),
            ("Node.js", "node.js"),
            ("NodeJS", "node.js"),
            ("AWS", "amazon web services"),
            ("Amazon Web Services", "amazon web services"),
            ("GCP", "google cloud platform"),
            ("Google Cloud", "google cloud platform"),
            ("TS", "typescript"),
            ("TypeScript", "typescript"),
            ("Py", "python"),
            ("Python3", "python"),
            ("FastAPI", "fastapi"),
            ("Fast API", "fastapi"),
            ("CI/CD", "ci/cd"),
            ("cicd", "ci/cd"),
            ("Continuous Integration", "ci/cd")
        ]

        for raw_input, expected in cases:
            with self.subTest(raw_input=raw_input):
                actual = normalize_skill(raw_input)
                self.assertEqual(actual, expected)

    def test_skill_equivalence(self):
        self.assertTrue(taxonomy_service.is_equivalent("k8s", "Kubernetes"))
        self.assertTrue(taxonomy_service.is_equivalent("Postgres", "psql"))
        self.assertTrue(taxonomy_service.is_equivalent("React.js", "reactjs"))
        self.assertFalse(taxonomy_service.is_equivalent("Python", "Rust"))

    def test_skill_categories(self):
        self.assertEqual(get_skill_category("Python"), "languages")
        self.assertEqual(get_skill_category("PostgreSQL"), "databases")
        self.assertEqual(get_skill_category("Kubernetes"), "cloud_devops")
        self.assertEqual(get_skill_category("React"), "frameworks")
        self.assertEqual(get_skill_category("Microservices"), "architecture_concepts")
        self.assertIsNone(get_skill_category("UnregisteredRandomSkillXYZ"))

    def test_skill_extraction_from_jd_text(self):
        jd_text = """
        We are seeking a Senior Backend Engineer proficient in Python or Golang with hands-on experience in
        FastAPI and microservices architecture. Strong knowledge of PostgreSQL, Redis, and containerization
        using Docker and k8s on AWS is required. Experience with CI/CD pipelines (GitHub Actions) is a plus.
        """

        extracted = taxonomy_service.extract_skills_from_text(jd_text)

        expected_skills = {
            "python",
            "golang",
            "fastapi",
            "microservices",
            "postgresql",
            "redis",
            "docker",
            "kubernetes",
            "amazon web services",
            "ci/cd",
            "github actions"
        }

        for skill in expected_skills:
            self.assertIn(skill, extracted, f"Expected {skill} to be extracted from JD")

    def test_unknown_skill_fallback(self):
        unknown = "Hyperdimensional Vector Optimization"
        normalized = normalize_skill(unknown)
        self.assertEqual(normalized, unknown.lower())


if __name__ == "__main__":
    unittest.main()
