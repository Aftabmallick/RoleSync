import unittest
from app.services.typst_compiler import TypstCompilerService


class TestTypstEngine(unittest.TestCase):
    def setUp(self):
        self.compiler = TypstCompilerService()

    def test_typst_escaping_all_special_characters(self):
        # Text with all sensitive Typst DSL markers
        raw_text = 'Senior Engineer #1 at "Acme Corp" ($150k budget) with [React] & C++ *Fast* <tag> @user'
        escaped = TypstCompilerService.escape_typst(raw_text)

        self.assertIn(r'\#', escaped)
        self.assertIn(r'\"Acme Corp\"', escaped)
        self.assertIn(r'\$150k', escaped)
        self.assertIn(r'\[React\]', escaped)
        self.assertIn(r'\*Fast\*', escaped)
        self.assertIn(r'\<tag\>', escaped)
        self.assertIn(r'\@user', escaped)

    def test_build_typst_markup_synthesis(self):
        profile = {
            "personal": {
                "full_name": "Sarah Connor",
                "email": "sarah@cyberdyne.io",
                "phone": "+1 (555) 019-2834",
                "location": "Los Angeles, CA",
                "linkedin": "linkedin.com/in/sarah-connor"
            },
            "education": [
                {
                    "institution": "Stanford University",
                    "degree": "B.S.",
                    "field": "Computer Science",
                    "end_date": "2020",
                    "gpa": "3.9"
                }
            ]
        }
        draft = {
            "summary": "Specialized in distributed systems and cloud security #resilience.",
            "skills": ["Rust", "Python", "Kubernetes", "AWS"],
            "experience": [
                {
                    "company": "Tech Corp",
                    "role": "Lead Architect",
                    "dates": "2021 - Present",
                    "location": "San Francisco, CA",
                    "bullet_points": [
                        {"tailored_text": "Scaled throughput by 400% with zero downtime [$2M savings]."}
                    ]
                }
            ]
        }

        markup = self.compiler.build_typst_markup(profile, draft, font_size=9.0, text_spacing="105%")

        self.assertIn("Sarah Connor", markup)
        self.assertIn(r"sarah\@cyberdyne.io", markup)
        self.assertIn(r"\#resilience", markup)
        self.assertIn(r"\[\$2M savings\]", markup)
        self.assertIn("font_size: 9.0pt", markup)
        self.assertIn('text_spacing: 105%', markup)

    def test_page_count_inspection(self):
        # Synthetic mock PDF bytes with 2 page markers
        mock_pdf = b"""
        %PDF-1.4
        1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
        2 0 obj << /Type /Pages /Count 2 /Kids [ 3 0 R 4 0 R ] >> endobj
        3 0 obj << /Type /Page /Parent 2 0 R >> endobj
        4 0 obj << /Type /Page /Parent 2 0 R >> endobj
        %%EOF
        """
        count = TypstCompilerService.inspect_page_count(mock_pdf)
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
