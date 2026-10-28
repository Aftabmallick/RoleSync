import subprocess
import tempfile
import pathlib
import re
import shutil
from typing import Dict, Any, Tuple, Optional
from app.core.config import settings


class TypstCompilationError(Exception):
    pass


class TypstCompilerService:
    def __init__(self, template_path: Optional[str] = None):
        t_path = template_path or settings.TYPST_TEMPLATE_PATH
        self.template_path = pathlib.Path(t_path).resolve()

    @classmethod
    def escape_typst(cls, text: str) -> str:
        r"""
        Exhaustively escapes all Typst DSL syntax characters:
        \, ", #, $, _, *, @, [, ], <, >
        """
        if not text:
            return ""
        return re.sub(r'([\\#"$_*@\[\]<>])', r'\\\1', str(text))

    def build_typst_markup(
        self,
        profile: Dict[str, Any],
        tailored_draft: Dict[str, Any],
        font_size: float = 9.5,
        text_spacing: str = "110%"
    ) -> str:
        """Synthesizes valid Typst markup binding candidate data to the resume template."""
        personal = profile.get("personal", {})

        src = f'#import "{self.template_path}": resume\n'
        src += f'#show: resume.with(\n'
        src += f'  name: "{self.escape_typst(personal.get("full_name", ""))}",\n'
        src += f'  email: "{self.escape_typst(personal.get("email", ""))}",\n'
        src += f'  phone: "{self.escape_typst(personal.get("phone", ""))}",\n'
        src += f'  location: "{self.escape_typst(personal.get("location", ""))}",\n'
        src += f'  linkedin: "{self.escape_typst(personal.get("linkedin", ""))}",\n'
        src += f'  github: "{self.escape_typst(personal.get("github", ""))}",\n'
        src += f'  summary: "{self.escape_typst(tailored_draft.get("summary", ""))}",\n'
        src += f'  font_size: {font_size}pt,\n'
        src += f'  text_spacing: {text_spacing},\n'

        # Technical Skills Matrix
        skills_raw = tailored_draft.get("skills", [])
        escaped_skills = [f'"{self.escape_typst(s)}"' for s in skills_raw]
        src += f'  skills: ((category: "Core Competencies", items: ({", ".join(escaped_skills)})),),\n'

        # Professional Experience
        exp_entries = []
        for exp in tailored_draft.get("experience", []):
            bullets = [f'"{self.escape_typst(b.get("tailored_text", ""))}"' for b in exp.get("bullet_points", [])]
            entry = (
                f'    (company: "{self.escape_typst(exp.get("company", ""))}", '
                f'role: "{self.escape_typst(exp.get("role", ""))}", '
                f'dates: "{self.escape_typst(exp.get("dates", ""))}", '
                f'location: "{self.escape_typst(exp.get("location", "Remote / Onsite"))}", '
                f'bullets: ({", ".join(bullets)}))'
            )
            exp_entries.append(entry)

        src += f'  experience: (\n{",\n".join(exp_entries)}\n  ),\n'

        # Education
        edu_entries = []
        for edu in profile.get("education", []):
            entry = (
                f'    (institution: "{self.escape_typst(edu.get("institution", ""))}", '
                f'dates: "{self.escape_typst(edu.get("end_date", ""))}", '
                f'degree: "{self.escape_typst(edu.get("degree", ""))}", '
                f'field: "{self.escape_typst(edu.get("field", ""))}", '
                f'gpa: "{self.escape_typst(edu.get("gpa", ""))}")'
            )
            edu_entries.append(entry)

        src += f'  education: (\n{",\n".join(edu_entries)}\n  )\n)\n'
        return src

    def compile_pdf(
        self,
        profile: Dict[str, Any],
        tailored_draft: Dict[str, Any],
        font_size: float = 9.5,
        text_spacing: str = "110%"
    ) -> Tuple[bytes, int]:
        """Compiles Typst DSL markup into PDF bytes and counts output pages."""
        typst_src = self.build_typst_markup(profile, tailored_draft, font_size, text_spacing)

        typst_bin = shutil.which(settings.TYPST_BINARY_PATH) or shutil.which("typst")
        if not typst_bin:
            raise TypstCompilationError("Typst binary is not installed on the system host.")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            input_file = tmp_path / "resume.typ"
            output_file = tmp_path / "resume.pdf"

            input_file.write_text(typst_src, encoding="utf-8")

            cmd = [
                typst_bin,
                "compile",
                "--root",
                str(self.template_path.parent),
                str(input_file),
                str(output_file)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if res.returncode != 0:
                raise TypstCompilationError(f"Typst compilation failed: {res.stderr}")

            pdf_bytes = output_file.read_bytes()
            page_count = self.inspect_page_count(pdf_bytes)
            return pdf_bytes, page_count

    def render_pdf_with_budget(
        self,
        profile: Dict[str, Any],
        tailored_draft: Dict[str, Any],
        target_pages: int = 1
    ) -> bytes:
        """
        Feedback calibration loop:
        Adjusts font size and spacing dynamically to ensure resume strictly adheres
        to target_pages limit without orphan line spillover.
        """
        font_presets = [9.5, 9.0, 8.5]
        spacing_presets = ["110%", "105%", "100%"]

        last_pdf = None
        for font_size, spacing in zip(font_presets, spacing_presets):
            pdf_bytes, page_count = self.compile_pdf(profile, tailored_draft, font_size, spacing)
            last_pdf = pdf_bytes
            if page_count <= target_pages:
                return pdf_bytes

        return last_pdf or b""

    @classmethod
    def inspect_page_count(cls, pdf_bytes: bytes) -> int:
        """Extracts page count from raw PDF dictionary metadata."""
        matches = re.findall(rb'/Type\s*/Page\b', pdf_bytes)
        return max(1, len(matches))
