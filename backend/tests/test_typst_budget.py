import unittest
from app.services.typst_compiler import TypstCompilerService


class MockTypstCompilerWithOverflow(TypstCompilerService):
    def __init__(self):
        super().__init__()
        self.compile_attempts = []

    def compile_pdf(self, profile, tailored_draft, font_size=9.5, text_spacing="110%"):
        self.compile_attempts.append({"font_size": font_size, "text_spacing": text_spacing})
        # Simulate: at font_size=9.5 page_count=2, at 9.0 page_count=2, at 8.5 page_count=1
        if font_size > 8.5:
            fake_pdf = b"""
            %PDF-1.4
            1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
            2 0 obj << /Type /Pages /Count 2 /Kids [ 3 0 R 4 0 R ] >> endobj
            3 0 obj << /Type /Page /Parent 2 0 R >> endobj
            4 0 obj << /Type /Page /Parent 2 0 R >> endobj
            %%EOF
            """
            return fake_pdf, 2
        else:
            fake_pdf = b"""
            %PDF-1.4
            1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
            2 0 obj << /Type /Pages /Count 1 /Kids [ 3 0 R ] >> endobj
            3 0 obj << /Type /Page /Parent 2 0 R >> endobj
            %%EOF
            """
            return fake_pdf, 1


class TestTypstPageBudget(unittest.TestCase):
    def test_feedback_budget_loop_compacts_overflow(self):
        compiler = MockTypstCompilerWithOverflow()
        profile = {"personal": {"full_name": "Test User"}}
        draft = {"skills": ["Python"], "experience": [], "summary": "Sample summary"}

        pdf_bytes = compiler.render_pdf_with_budget(profile, draft, target_pages=1)
        self.assertIsNotNone(pdf_bytes)

        # Must have iterated through presets until reaching font_size=8.5 (attempt 3)
        self.assertEqual(len(compiler.compile_attempts), 3)
        self.assertEqual(compiler.compile_attempts[0]["font_size"], 9.5)
        self.assertEqual(compiler.compile_attempts[1]["font_size"], 9.0)
        self.assertEqual(compiler.compile_attempts[2]["font_size"], 8.5)

        # Inspect resulting PDF page count -> must strictly equal 1
        final_page_count = TypstCompilerService.inspect_page_count(pdf_bytes)
        self.assertEqual(final_page_count, 1)


if __name__ == "__main__":
    unittest.main()
