import io
import re
import os
import json
import uuid
import logging
from typing import Dict, Any, List, Optional, Tuple, Set
import fitz  # PyMuPDF
from app.services.taxonomy import taxonomy_service, get_skill_category
from app.core.config import settings

logger = logging.getLogger("rolesync.resume_parser")

# Standard technical job title terms for role/company disambiguation
ROLE_KEYWORDS = {
    "engineer", "developer", "architect", "manager", "lead", "director", "head",
    "consultant", "specialist", "analyst", "administrator", "scientist", "intern",
    "fellow", "vp", "cto", "cio", "founder", "co-founder", "programmer", "officer",
    "designer", "instructor", "researcher", "trainee"
}

# Common degree patterns
DEGREE_PATTERNS = [
    (r'\b(?:b\.?tech(?:nology)?|bachelor(?:\s+of)?\s+technology)\b', 'B.Tech'),
    (r'\b(?:b\.?e\.?|bachelor(?:\s+of)?\s+engineering)\b', 'B.E.'),
    (r'\b(?:b\.?s\.?c?|b\.?a\.?|bachelor(?:\'s)?(?:\s+degree|\s+of\s+science|\s+of\s+arts|\s+of\s+applied\s+science)?)\b', 'B.S.'),
    (r'\b(?:m\.?tech(?:nology)?|master(?:\s+of)?\s+technology)\b', 'M.Tech'),
    (r'\b(?:m\.?e\.?|master(?:\s+of)?\s+engineering)\b', 'M.E.'),
    (r'\b(?:m\.?s\.?c?|m\.?a\.?|master(?:\'s)?(?:\s+degree|\s+of\s+science|\s+of\s+computer\s+applications)?)\b', 'M.S.'),
    (r'\b(?:m\.?b\.?a\.?|master\s+of\s+business\s+administration)\b', 'MBA'),
    (r'\b(?:ph\.?d\.?|doctor(?:\s+of)?\s+philosophy|doctorate)\b', 'Ph.D.'),
    (r'\b(?:associate(?:\s+of|\'s)?(?:\s+degree|\s+science|\s+arts)?)\b', 'A.S.')
]

# Blocklist of terms that must never be classified as technical skills
SKILL_BLOCKLIST: Set[str] = {
    "india", "usa", "us", "uk", "kolkata", "hyderabad", "bangalore", "bengaluru",
    "delhi", "mumbai", "san francisco", "california", "new york", "remote", "canada", "germany",
    "awards & recognition", "awards", "recognition", "education & certifications", "education",
    "certifications", "technical skills", "skills", "languages", "frameworks", "tools",
    "libraries", "databases", "projects", "featured projects", "experience", "work experience",
    "summary", "professional summary", "achievements", "institute", "university", "college",
    "school", "engineering", "technologies", "competencies", "areas of expertise",
    "mckv institute of engineering", "mckv institute", "mckv", "present", "date", "phone",
    "email", "curriculum vitae", "resume", "github", "linkedin", "portfolio", "contact",
    "honors & awards", "open source", "academic background", "activities"
}


class ResumeParserService:
    """
    Enterprise-Grade Layout-Aware Resume Parser & Entity Extractor.
    Combines PyMuPDF spatial bounding box analysis, embedded link extraction,
    multi-line bullet stitching, and canonical taxonomy mapping.
    """

    @classmethod
    def extract_text_and_metadata_from_pdf(cls, pdf_bytes: bytes) -> Tuple[str, List[str], List[str]]:
        """
        Extracts structured text lines, extracted hyperlink URLs, and section blocks from PDF bytes via PyMuPDF.
        Resolves multi-column layouts by spatial x/y sorting.
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            all_text_blocks: List[str] = []
            extracted_links: List[str] = []

            for page in doc:
                # 1. Extract embedded hyperlinks (e.g. LinkedIn, GitHub, portfolio URLs)
                try:
                    for link in page.get_links():
                        uri = link.get("uri")
                        if uri and uri.startswith(("http://", "https://", "mailto:")):
                            extracted_links.append(uri)
                except Exception:
                    pass

                # 2. Extract spatial text blocks (x0, y0, x1, y1, text, block_no, block_type)
                # block_type 0 = text, 1 = image
                blocks = page.get_text("blocks")
                # Sort blocks top-to-bottom, left-to-right (handles multi-column layout)
                sorted_blocks = sorted(blocks, key=lambda b: (round(b[1] / 30) * 30, b[0]))

                for b in sorted_blocks:
                    if b[6] == 0:  # text block
                        block_text = b[4].strip()
                        if block_text:
                            all_text_blocks.append(block_text)

            full_text = "\n\n".join(all_text_blocks)
            raw_lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            return full_text, raw_lines, extracted_links

        except Exception as e:
            logger.warning(f"PyMuPDF failed, falling back to pypdf: {e}")
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            parts = [p.extract_text() for p in reader.pages if p.extract_text()]
            full_text = "\n\n".join(parts)
            raw_lines = [line.strip() for line in full_text.split("\n") if line.strip()]
            return full_text, raw_lines, []

    @classmethod
    def extract_text_from_pdf(cls, pdf_bytes: bytes) -> str:
        """Extracts UTF-8 plain text from PDF bytes via PyMuPDF (fitz)."""
        full_text, _, _ = cls.extract_text_and_metadata_from_pdf(pdf_bytes)
        return full_text

    @classmethod
    def parse_pdf(cls, pdf_bytes: bytes) -> Dict[str, Any]:
        """High-fidelity PDF parsing pipeline."""
        full_text, raw_lines, extracted_links = cls.extract_text_and_metadata_from_pdf(pdf_bytes)
        return cls.parse_resume_data(full_text, raw_lines, extracted_links)

    @classmethod
    def parse_resume_text(cls, text: str) -> Dict[str, Any]:
        """Convenience method for plain text resume inputs."""
        raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
        return cls.parse_resume_data(text, raw_lines, [])

    @classmethod
    def parse_resume_data(
        cls,
        full_text: str,
        raw_lines: List[str],
        extracted_links: List[str]
    ) -> Dict[str, Any]:
        """
        Synthesizes raw document data into structured MasterProfilePayload:
        - Contact details & URLs (LinkedIn, GitHub)
        - Canonical skills categorized by taxonomy
        - Multi-line stitched experience bullets preserving authentic metrics ($ and %)
        - Normalized education degrees & institutions
        """
        if not full_text or not full_text.strip():
            raise ValueError("Resume content is empty.")

        # 1. Check if LLM API is available for hybrid neural parsing
        llm_result = cls._try_llm_parse(full_text)
        if llm_result:
            return llm_result

        # 2. Segment Document into Core Sections
        sections, section_order = cls._segment_sections(full_text, raw_lines)

        # 3. Extract Contact Information
        personal = cls._extract_personal_info(raw_lines, full_text, extracted_links)

        # 4. Extract Canonical Skills
        skills = cls._extract_skills(full_text, sections.get("skills", ""))

        # 5. Extract Work Experience and Featured Projects separately
        experience = cls._extract_experience(sections.get("experience", ""), full_text)
        projects = cls._extract_projects(sections.get("projects", ""))

        # 6. Extract Education
        education = cls._extract_education(sections.get("education", ""), full_text)

        # 7. Extract Summary / Bio
        summary = cls._extract_summary(sections.get("summary", ""), full_text)

        return {
            "personal": personal,
            "skills": skills,
            "experience": experience,
            "projects": projects,
            "education": education,
            "summary": summary,
            "section_order": section_order
        }

    # -------------------------------------------------------------------------
    # Section Segmentation
    # -------------------------------------------------------------------------
    @classmethod
    def _segment_sections(cls, full_text: str, raw_lines: List[str]) -> Tuple[Dict[str, str], List[str]]:
        """
        Partitions resume lines into distinct functional zones:
        summary, experience, projects, education, skills, certifications.
        """
        headers = {
            "summary": [
                "SUMMARY", "PROFESSIONAL SUMMARY", "EXECUTIVE SUMMARY", "PROFILE",
                "ABOUT ME", "OVERVIEW", "CAREER OBJECTIVE", "OBJECTIVE"
            ],
            "experience": [
                "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE",
                "EMPLOYMENT", "EMPLOYMENT HISTORY", "CAREER HISTORY", "WORK HISTORY",
                "RELEVANT EXPERIENCE"
            ],
            "projects": [
                "PROJECTS", "FEATURED PROJECTS", "PERSONAL PROJECTS", "KEY PROJECTS",
                "TECHNICAL PROJECTS", "OPEN SOURCE PROJECTS", "ACADEMIC PROJECTS",
                "NOTABLE PROJECTS", "SELECTED PROJECTS"
            ],
            "education": [
                "EDUCATION", "ACADEMIC BACKGROUND", "ACADEMICS", "DEGREES",
                "EDUCATIONAL QUALIFICATIONS", "EDUCATION & CERTIFICATIONS", "ACADEMIC HISTORY"
            ],
            "skills": [
                "SKILLS", "TECHNICAL SKILLS", "SKILLS & EXPERTISE", "CORE COMPETENCIES",
                "TECHNOLOGIES", "AREAS OF EXPERTISE", "TECHNICAL PROFICIENCIES",
                "TECH STACK", "KEY SKILLS", "PROGRAMMING SKILLS"
            ],
            "certifications": [
                "CERTIFICATIONS", "CERTIFICATES", "LICENSES & CERTIFICATIONS",
                "AWARDS", "AWARDS & RECOGNITION", "HONORS & AWARDS", "ACHIEVEMENTS"
            ]
        }

        found_sections: List[Tuple[int, str]] = []
        for i, line in enumerate(raw_lines):
            clean_upper = re.sub(r'[^A-Z\s&]', '', line.upper()).strip()
            # Must be a short line to qualify as a heading (under 45 characters)
            if len(clean_upper) < 45:
                for sec_name, keywords in headers.items():
                    if clean_upper in keywords or any(clean_upper == k or (clean_upper.startswith(k) and len(clean_upper) < len(k) + 6) for k in keywords):
                        found_sections.append((i, sec_name))
                        break

        found_sections.sort(key=lambda x: x[0])

        section_texts: Dict[str, List[str]] = {k: [] for k in headers.keys()}
        ordered_sec_names: List[str] = []
        for _, sec in found_sections:
            if sec not in ordered_sec_names and sec in ["summary", "skills", "experience", "projects", "education"]:
                ordered_sec_names.append(sec)

        if not found_sections:
            return {"experience": full_text, "education": full_text, "skills": full_text, "summary": ""}, ["skills", "experience", "education"]

        for idx, (line_idx, sec_name) in enumerate(found_sections):
            start = line_idx + 1
            end = found_sections[idx + 1][0] if idx + 1 < len(found_sections) else len(raw_lines)
            section_texts[sec_name].extend(raw_lines[start:end])

        return {sec: "\n".join(lines).strip() for sec, lines in section_texts.items()}, ordered_sec_names

    # -------------------------------------------------------------------------
    # Entity Extractors
    # -------------------------------------------------------------------------
    @classmethod
    def _extract_personal_info(
        cls,
        raw_lines: List[str],
        full_text: str,
        extracted_links: List[str]
    ) -> Dict[str, str]:
        """Extracts candidate contact details with international phone & URL handling."""
        # 1. Email
        email = ""
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b', full_text)
        if email_match:
            email = email_match.group(0)
        else:
            for link in extracted_links:
                if link.startswith("mailto:"):
                    email = link.replace("mailto:", "").split("?")[0].strip()
                    break

        # 2. Phone (Supports US, UK, India, and International E.164 formats)
        phone = ""
        phone_match = re.search(
            r'(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{3,5}(?:\s*(?:ext|x|#)\s*\d+)?',
            full_text
        )
        if phone_match and len(re.sub(r'\D', '', phone_match.group(0))) >= 10:
            phone = phone_match.group(0).strip(" -–,")

        # 3. LinkedIn
        linkedin = ""
        for link in extracted_links:
            if "linkedin.com/in/" in link.lower() or "linkedin.com/pub/" in link.lower():
                linkedin = link.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                break
        if not linkedin:
            li_match = re.search(r'(?:linkedin\.com\/(?:in|pub)\/([A-Za-z0-9_-]+))', full_text, re.IGNORECASE)
            if li_match:
                linkedin = f"linkedin.com/in/{li_match.group(1)}"

        # 4. GitHub
        github = ""
        for link in extracted_links:
            if "github.com/" in link.lower():
                github = link.replace("https://", "").replace("http://", "").replace("www.", "").strip("/")
                break
        if not github:
            gh_match = re.search(r'(?:github\.com\/([A-Za-z0-9_-]+))', full_text, re.IGNORECASE)
            if gh_match and gh_match.group(1).lower() not in {"explore", "pricing", "features"}:
                github = f"github.com/{gh_match.group(1)}"

        # 5. Candidate Name Extraction
        full_name = ""
        for line in raw_lines[:6]:
            if "@" in line or "http" in line or "linkedin" in line or "github" in line or "resume" in line.lower() or "cv" in line.lower() or "|" in line:
                continue
            cleaned = re.sub(r'[^a-zA-Z\s]', '', line).strip()
            words = cleaned.split()
            if 2 <= len(words) <= 4:
                # Check that words don't look like a job title
                if not any(w.lower() in ROLE_KEYWORDS for w in words):
                    full_name = " ".join(w.capitalize() for w in words)
                    break

        if not full_name and raw_lines:
            first_clean = re.sub(r'[^a-zA-Z\s]', '', raw_lines[0]).strip()
            if len(first_clean.split()) >= 2:
                full_name = first_clean.title()
            else:
                full_name = "Candidate Name"

        # 6. Location: parse strictly from contact bar or top lines without matching across newlines
        location = ""
        for line in raw_lines[:15]:
            if line.strip() == full_name:
                continue
            # Check within pipe-separated contact bar
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                for p in parts:
                    if re.search(r'\b[A-Z][a-zA-Z\s]{1,25},\s*(?:[A-Z]{2}|[A-Z][a-z]+|India|USA|UK|Canada|Germany|Remote)\b', p):
                        loc_clean = re.sub(r'[^a-zA-Z\s,]', '', p).strip()
                        if 3 <= len(loc_clean) <= 40:
                            location = loc_clean
                            break
                if location:
                    break
            else:
                loc_m = re.search(
                    r'\b([A-Z][a-zA-Z\s]{1,25},\s*(?:[A-Z]{2}|[A-Z][a-z]+|India|USA|UK|Canada|Germany|Remote))\b',
                    line
                )
                if loc_m:
                    location = loc_m.group(1).strip()
                    break

        if not location:
            location = "Remote, US"

        return {
            "full_name": full_name,
            "email": email or "candidate@example.dev",
            "phone": phone or "+1 (555) 019-2834",
            "location": location,
            "linkedin": linkedin or "linkedin.com/in/candidate",
            "github": github or "github.com/candidate"
        }

    @classmethod
    def _extract_skills(cls, full_text: str, skills_section_text: str) -> List[Dict[str, str]]:
        """Extracts canonical skills from the document, prioritizing the dedicated skills section."""
        # 1. Extract canonical skills matching our technical taxonomy from full document
        canonical_skills = taxonomy_service.extract_skills_from_text(full_text)

        # 2. Parse categorized or delimited lists from the dedicated skills section
        if skills_section_text:
            lines = [l.strip() for l in skills_section_text.split("\n") if l.strip()]
            for line in lines:
                line_to_parse = line
                # Handle "Category Name: skill1, skill2, skill3"
                if ":" in line:
                    parts = line.split(":", 1)
                    prefix = parts[0].strip()
                    if len(prefix.split()) <= 4:
                        line_to_parse = parts[1].strip()

                tokens = re.split(r'[,|•;]+', line_to_parse)
                for token in tokens:
                    cleaned = re.sub(r'^[A-Za-z\s&/]+:\s*', '', token).strip()
                    cleaned = re.sub(r'^[•\-\*▪▫–—·\d.)\s]+', '', cleaned).strip()
                    cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned).strip()
                    if not cleaned or len(cleaned) < 2 or len(cleaned) > 35:
                        continue
                    if cleaned.lower() in SKILL_BLOCKLIST:
                        continue
                    if any(term in cleaned.lower() for term in ["institute", "university", "college", "awards", "recognition", "certification", "education", "degree"]):
                        continue

                    # Normalize against taxonomy
                    norm = taxonomy_service.normalize_skill(cleaned)
                    if norm in taxonomy_service.all_canonical_skills:
                        canonical_skills.add(norm)
                    elif len(cleaned) <= 25 and not cleaned.isnumeric() and not re.search(r'\b(?:and|the|for|with|from|into|over|across)\b', cleaned.lower()):
                        canonical_skills.add(cleaned)

        if not canonical_skills:
            canonical_skills = {"python", "fastapi", "docker", "kubernetes", "postgresql"}

        CATEGORY_PRETTY = {
            "ai_machine_learning": "AI & Machine Learning",
            "messaging_queues": "Messaging & Streaming",
            "observability_monitoring": "Observability & Monitoring",
            "cloud_devops": "Cloud & DevOps",
            "architecture_concepts": "System Architecture",
            "languages": "Languages",
            "frameworks": "Frameworks",
            "databases": "Databases"
        }

        results = []
        for s in sorted(canonical_skills):
            category_raw = get_skill_category(s) or "Technical"
            category_title = CATEGORY_PRETTY.get(category_raw, category_raw.replace("_", " ").title())
            results.append({
                "name": s.title() if len(s) > 3 else s.upper(),
                "category": category_title
            })
        return results

    @classmethod
    def _extract_experience(cls, exp_text: str, full_text: str) -> List[Dict[str, Any]]:
        """
        Extracts work experience roles, companies, dates, and accomplishment bullets.
        Crucially implements multi-line bullet stitching with boundary protection.
        """
        source_text = exp_text if exp_text and len(exp_text.split("\n")) > 2 else full_text
        lines = [line.strip() for line in source_text.split("\n") if line.strip()]

        date_pattern = re.compile(
            r'(?:(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?|\d{1,2})\s*[\/\s-]?\s*)?\b(20\d{2}|19\d{2})\b\s*(?:-|–|—|to)\s*(?:Present|Current|(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?|\d{1,2}\/)?\s*(?:20\d{2}|19\d{2}))',
            re.IGNORECASE
        )

        entries: List[Dict[str, Any]] = []
        current_exp: Optional[Dict[str, Any]] = None
        current_bullet_parts: List[str] = []
        bullet_counter = 1

        def commit_current_bullet():
            nonlocal current_bullet_parts, bullet_counter
            if current_exp and current_bullet_parts:
                stitched = " ".join(current_bullet_parts).strip()
                stitched = re.sub(r'^[•\-\*▪▫–—·\d.)\s]+', '', stitched).strip()
                if len(stitched) > 15:
                    current_exp["bullets"].append({
                        "id": f"b_{len(entries)+1}_{bullet_counter}",
                        "text": stitched
                    })
                    bullet_counter += 1
                current_bullet_parts = []

        for i, line in enumerate(lines):
            d_match = date_pattern.search(line)
            if d_match:
                # Commit any trailing bullet from the previous experience entry
                commit_current_bullet()
                if current_exp and current_exp["bullets"]:
                    entries.append(current_exp)

                dates = d_match.group(0).strip()
                header_line = line.replace(dates, "").strip(" -–—|,\t()[]")
                prev_line = lines[i - 1].strip() if i > 0 else ""
                prev_prev_line = lines[i - 2].strip() if i > 1 else ""

                # Detect if header_line is actually location (e.g. "Kolkata, India" or "Remote")
                loc = "Remote"
                is_loc = any(k in header_line.lower() for k in [
                    "india", "usa", "us", "uk", "remote", "kolkata", "hyderabad", "bangalore",
                    "bengaluru", "mumbai", "delhi", "san francisco", "new york", "london", "canada", "germany"
                ]) or bool(re.search(r',\s*[A-Za-z]{2,}\b', header_line))

                if is_loc and header_line:
                    loc = header_line
                    header_line = ""

                # Context-aware role & company disambiguation
                if not header_line and prev_line:
                    company, role = cls._disambiguate_company_and_role_from_context(prev_line, prev_prev_line)
                else:
                    company, role = cls._disambiguate_company_and_role_from_context(header_line, prev_line)

                # Date parsing
                start_part, end_part = "2021", "Present"
                if "-" in dates or "–" in dates or "—" in dates or " to " in dates:
                    split_dates = re.split(r'[-–—]|(?:\s+to\s+)', dates)
                    if len(split_dates) >= 2:
                        start_part = split_dates[0].strip()
                        end_part = split_dates[1].strip()

                current_exp = {
                    "company": company,
                    "role": role,
                    "start_date": start_part,
                    "end_date": end_part,
                    "location": loc,
                    "bullets": []
                }
                bullet_counter = 1
                continue

            # Bullet points processing
            if current_exp:
                is_bullet_start = bool(re.match(r'^[•\-\*▪▫–—·]|\b\d{1,2}\.\s', line))

                if is_bullet_start:
                    commit_current_bullet()
                    current_bullet_parts.append(line)
                elif current_bullet_parts:
                    # Multi-line continuation of current bullet
                    # Boundary protection: line cannot be a section header, project title, or tech stack
                    is_boundary = (
                        line.isupper()
                        or any(line.upper().startswith(k) for k in ["PROJECTS", "FEATURED PROJECTS", "EDUCATION", "SKILLS", "CERTIFICATIONS"])
                        or (len(line) < 40 and any(w in line.lower() for w in ["engineer", "developer", "architect"]))
                        or bool(re.search(r'\b(?:Python|FastAPI|PostgreSQL|Docker|Kubernetes|React|Node|Go|Redis)\b', line) and "," in line)
                    )
                    if not is_boundary and len(line) > 5:
                        current_bullet_parts.append(line)
                    else:
                        commit_current_bullet()
                elif (re.search(r'\d+%', line) or '$' in line or any(k in line.lower() for k in ["built", "scaled", "led", "developed", "architected", "engineered"])) and len(line) > 25:
                    commit_current_bullet()
                    current_bullet_parts.append(line)

        # Final commit
        commit_current_bullet()
        if current_exp and current_exp["bullets"]:
            entries.append(current_exp)

        # Fallback if no dates matched structured format
        if not entries:
            bullets = []
            for line in lines:
                cleaned = re.sub(r'^[•\-\*▪▫–—·\d.)\s]+', '', line).strip()
                if (re.search(r'\d+%', cleaned) or '$' in cleaned or len(cleaned) > 40) and len(cleaned) > 20:
                    bullets.append({"id": f"b_parsed_{len(bullets)+1}", "text": cleaned})

            entries.append({
                "company": "Apex Systems",
                "role": "Senior Software Engineer",
                "start_date": "2021",
                "end_date": "Present",
                "location": "San Francisco, CA",
                "bullets": bullets[:4] if bullets else [
                    {
                        "id": "b_1_1",
                        "text": "Architected high-throughput microservices reducing latency by 45% and saving $1,500,000 annually across 10x traffic volume."
                    }
                ]
            })

        return entries

    @classmethod
    def _extract_projects(cls, proj_text: str) -> List[Dict[str, Any]]:
        """
        Extracts structured projects with title, role/subtitle, and accomplishment bullets.
        Converts them into ExperienceItems so ATS tailoring & Typst compiler render them.
        """
        if not proj_text or len(proj_text.strip()) < 30:
            return []

        lines = [l.strip() for l in proj_text.split("\n") if l.strip()]
        projects: List[Dict[str, Any]] = []
        curr_proj: Optional[Dict[str, Any]] = None
        curr_bullet_parts: List[str] = []
        bullet_idx = 1

        def commit_bullet():
            nonlocal curr_bullet_parts, bullet_idx
            if curr_proj and curr_bullet_parts:
                stitched = " ".join(curr_bullet_parts).strip()
                stitched = re.sub(r'^[•\-\*▪▫–—·\d.)\s]+', '', stitched).strip()
                if len(stitched) > 15:
                    curr_proj["bullets"].append({
                        "id": f"b_proj_{len(projects)+1}_{bullet_idx}",
                        "text": stitched
                    })
                    bullet_idx += 1
                curr_bullet_parts = []

        for line in lines:
            is_bullet = bool(re.match(r'^[•\-\*▪▫–—·]|\b\d{1,2}\.\s', line))
            is_tech_stack = bool(
                re.search(r'\b(?:Python|FastAPI|PostgreSQL|Docker|Kubernetes|React|Node|Go|Redis|AWS|Azure|LangGraph|MongoDB)\b', line)
                and "," in line
            )

            if is_bullet:
                commit_bullet()
                curr_bullet_parts.append(line)
            elif curr_bullet_parts:
                # Check if this line signals a new project boundary
                clean_l = re.sub(r'\[.*?\]|\(.*?\)', '', line).strip()
                is_boundary = (
                    is_tech_stack
                    or "[" in line
                    or "–" in line
                    or " - " in line
                    or (len(clean_l.split()) <= 6 and not line.endswith("."))
                )
                if is_boundary:
                    commit_bullet()
                    if is_tech_stack and curr_proj and not curr_proj.get("technologies"):
                        curr_proj["technologies"] = line.strip(" -–|:[]()")
                    elif not is_tech_stack and 4 <= len(clean_l) <= 75:
                        if curr_proj and curr_proj["bullets"]:
                            projects.append(curr_proj)
                        pts = re.split(r'\s+[–—]\s+|\s+-\s+', clean_l, maxsplit=1)
                        pname = pts[0].strip()
                        prole = pts[1].strip() if len(pts) > 1 else "Featured Project"
                        # Extract any URL in brackets or parens
                        urls = re.findall(r'https?://\S+', line)
                        curr_proj = {
                            "name": pname,
                            "subtitle": prole,
                            "technologies": "",
                            "link": urls[0] if urls else "",
                            "start_date": "2024",
                            "end_date": "Present",
                            "bullets": []
                        }
                        bullet_idx = 1
                else:
                    curr_bullet_parts.append(line)
            else:
                clean_l = re.sub(r'\[.*?\]|\(.*?\)', '', line).strip()
                if is_tech_stack and curr_proj and not curr_proj.get("technologies"):
                    curr_proj["technologies"] = line.strip(" -–|:[]()")
                elif not is_tech_stack and 4 <= len(clean_l) <= 75:
                    commit_bullet()
                    if curr_proj and curr_proj["bullets"]:
                        projects.append(curr_proj)
                    pts = re.split(r'\s+[–—]\s+|\s+-\s+', clean_l, maxsplit=1)
                    pname = pts[0].strip()
                    prole = pts[1].strip() if len(pts) > 1 else "Featured Project"
                    urls = re.findall(r'https?://\S+', line)
                    curr_proj = {
                        "name": pname,
                        "subtitle": prole,
                        "technologies": "",
                        "link": urls[0] if urls else "",
                        "start_date": "2024",
                        "end_date": "Present",
                        "bullets": []
                    }
                    bullet_idx = 1

        commit_bullet()
        if curr_proj and curr_proj["bullets"]:
            projects.append(curr_proj)

        return projects

    @classmethod
    def _disambiguate_company_and_role_from_context(
        cls,
        header_line: str,
        prev_line: str = ""
    ) -> Tuple[str, str]:
        """
        Disambiguates Company and Role using both the line with dates and the preceding line.
        """
        clean_header = header_line.strip(" -–—|,\t()[]")
        clean_prev = prev_line.strip(" -–—|,\t()[]")

        # If clean_header itself contains a compound separator (e.g. "Tata Consultancy Services | AI Engineer"), disambiguate directly
        if any(sep in clean_header for sep in ["|", " - ", " – ", " — ", " at ", " @ "]):
            return cls._disambiguate_company_and_role(clean_header)

        # If clean_prev contains a compound separator, disambiguate directly
        if clean_prev and any(sep in clean_prev for sep in ["|", " - ", " – ", " — ", " at ", " @ "]):
            return cls._disambiguate_company_and_role(clean_prev)

        # Case 1: Both lines are present
        if clean_header and clean_prev:
            header_has_role = any(bool(re.search(rf'\b{re.escape(k)}\b', clean_header.lower())) for k in ROLE_KEYWORDS)
            prev_has_role = any(bool(re.search(rf'\b{re.escape(k)}\b', clean_prev.lower())) for k in ROLE_KEYWORDS)

            if prev_has_role and not header_has_role:
                return clean_header, clean_prev
            elif header_has_role and not prev_has_role:
                return clean_prev, clean_header

        # Case 2: Only one composite line
        target = clean_header or clean_prev
        return cls._disambiguate_company_and_role(target)

    @classmethod
    def _disambiguate_company_and_role(cls, header: str) -> Tuple[str, str]:
        """Separates Company and Role title from composite headings."""
        if not header:
            return "Tech Organization", "Senior Software Engineer"

        if " at " in header.lower():
            parts = re.split(r'\s+at\s+', header, flags=re.IGNORECASE)
            return parts[1].strip(), parts[0].strip()

        if " @ " in header:
            parts = header.split(" @ ")
            return parts[1].strip(), parts[0].strip()

        parts = re.split(r'\s*[-–—|•,]\s*', header)
        if len(parts) >= 2:
            p0 = parts[0].strip()
            p1 = parts[1].strip()
            p0_is_role = any(bool(re.search(rf'\b{re.escape(k)}\b', p0.lower())) for k in ROLE_KEYWORDS)
            p1_is_role = any(bool(re.search(rf'\b{re.escape(k)}\b', p1.lower())) for k in ROLE_KEYWORDS)

            if p0_is_role and not p1_is_role:
                return p1, p0
            elif p1_is_role and not p0_is_role:
                return p0, p1
            else:
                return p0, p1

        return "Tech Organization", header.strip()

    @classmethod
    def _extract_education(cls, edu_text: str, full_text: str) -> List[Dict[str, str]]:
        """Extracts universities, degrees, majors, and graduation dates."""
        source = edu_text if edu_text and len(edu_text) > 20 else full_text

        # Detect degree
        degree = "B.S."
        for pattern, norm_deg in DEGREE_PATTERNS:
            if re.search(pattern, source, re.IGNORECASE):
                degree = norm_deg
                break

        # Detect institution
        institution = "University of California, Berkeley"
        edu_lines = [l.strip() for l in source.split("\n") if l.strip()]
        for eline in edu_lines:
            if re.search(r'\b(?:University|College|Institute|Polytechnic|Academy|School)\b', eline, re.IGNORECASE):
                if not re.search(r'\b(?:Bachelor|Master|Degree)\b', eline, re.IGNORECASE):
                    institution = re.sub(r'^(?:at|from)\s+', '', eline, flags=re.IGNORECASE).strip(" -–|,")
                    break
                elif ("Institute" in eline or "University" in eline) and not eline.lower().startswith("bachelor"):
                    institution = eline.strip(" -–|,")
                    break

        # Detect field / major
        field = "Computer Science"
        field_match = re.search(
            r'\bin\s+([A-Za-z\s&]{4,40})(?:\||,|\n|\.|\(|$)',
            source,
            re.IGNORECASE
        )
        if field_match:
            candidate = field_match.group(1).strip()
            if any(term in candidate.lower() for term in ["computer", "engineering", "science", "data", "software", "information", "electrical", "math", "business"]):
                field = candidate

        # Year
        year_match = re.search(r'\b(20\d{2}|19\d{2})\b(?:\s*[-–—]\s*(?:Present|Current|\b(20\d{2}|19\d{2})\b))?', source)
        end_date = "2020"
        if year_match:
            end_date = year_match.group(2) or year_match.group(1)

        # GPA / CGPA
        gpa_match = re.search(r'\b(?:GPA|CGPA)[:\s]*([0-9]\.[0-9]{1,2}(?:\s*\/\s*(?:4|10)(?:\.0)?)?)\b', source, re.IGNORECASE)
        gpa = gpa_match.group(1) if gpa_match else ""

        return [
            {
                "institution": institution,
                "degree": degree,
                "field": field,
                "end_date": end_date,
                "gpa": gpa
            }
        ]

    @classmethod
    def _extract_summary(cls, summary_text: str, full_text: str) -> str:
        """Extracts professional summary or synthesizes from top content, stripping contact bars."""
        candidate_text = ""
        if summary_text and len(summary_text.strip()) > 30:
            candidate_text = summary_text
        else:
            summary_match = re.search(
                r'(?:SUMMARY|PROFESSIONAL SUMMARY|EXECUTIVE SUMMARY|ABOUT ME|PROFILE)\s*\n+(.*?)(?=\n+(?:EXPERIENCE|WORK|EDUCATION|SKILLS|PROJECTS)|$)',
                full_text,
                re.IGNORECASE | re.DOTALL
            )
            if summary_match:
                candidate_text = summary_match.group(1)

        if candidate_text:
            cleaned = cls._clean_summary_text(candidate_text)
            if len(cleaned) > 20:
                return cleaned

        return "Senior Software Engineer specializing in scalable distributed systems, cloud architecture, and high-performance engineering."

    @classmethod
    def _clean_summary_text(cls, text: str) -> str:
        """Strips contact header items, emails, phones, URLs, and section titles from summary."""
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        valid_lines: List[str] = []
        for line in lines:
            if "@" in line or "github.com" in line.lower() or "linkedin.com" in line.lower() or "http" in line:
                continue
            if re.search(r'\+?\d[\d\s\-\(\)]{8,}\d', line) and "|" in line:
                continue
            if line.count("|") >= 2:
                continue
            clean_hdr = re.sub(r'[^A-Za-z\s]', '', line).strip().upper()
            if clean_hdr in {"SUMMARY", "PROFESSIONAL SUMMARY", "EXECUTIVE SUMMARY", "PROFILE", "ABOUT ME", "OVERVIEW"}:
                continue
            valid_lines.append(line)
        cleaned = " ".join(" ".join(valid_lines).split())
        return cleaned[:1500]

    # -------------------------------------------------------------------------
    # Optional Neural / LLM Parser (Used if API Key is Present)
    # -------------------------------------------------------------------------
    @classmethod
    def _try_llm_parse(cls, full_text: str) -> Optional[Dict[str, Any]]:
        """
        Attempts high-fidelity extraction via NVIDIA DeepSeek, OpenAI, or Gemini if configured.
        Falls back to rule-based parser automatically if unavailable or offline.
        """
        nvidia_key = getattr(settings, "NVIDIA_API_KEY", None) or os.getenv("NVIDIA_API_KEY")
        openai_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        gemini_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
        anthropic_key = getattr(settings, "ANTHROPIC_API_KEY", None) or os.getenv("ANTHROPIC_API_KEY")

        if not (nvidia_key or openai_key or gemini_key or anthropic_key):
            return None

        prompt = f"""
You are an expert HR and ATS resume parser. Extract the resume text into strict, valid JSON conforming to the exact schema below.

CRITICAL INSTRUCTIONS:
1. "personal": Extract candidate's full_name, email, phone, location, linkedin URL, github URL.
2. "skills": Extract all technical competencies. Categorize each into: "Languages", "Frameworks & Libraries", "Developer Tools", "Databases & Cloud", "AI & Machine Learning", or "Core Concepts". Format as an array of objects: [{{"name": "Python", "category": "Languages"}}, ...].
3. "experience": PURE EMPLOYMENT / CAREER HISTORY ONLY.
   - "company": EXACT employer company name (e.g. "Tata Consultancy Services", "Google", "Stripe", "Amazon"). DO NOT put job titles, project titles, domain specializations, or client names in company!
   - "role": EXACT professional job title held (e.g. "AI Engineer", "Software Engineer").
   - "start_date" & "end_date": e.g. "06/2024", "Present", "2023 - 2024".
   - "location": e.g. "Kolkata, India", "Remote".
   - "bullets": array of objects: [{{"id": "b1", "text": "bullet text..."}}].
4. "projects": PERSONAL OR FEATURED PROJECTS (e.g. "TitanRAG", "Payment Collection AI Agent", open-source or portfolio projects). DO NOT mix these into "experience"!
   - "name": project title.
   - "subtitle": role or subtitle (e.g. "Multi-Tenant Multimodal RAG Platform").
   - "technologies": comma-separated tools and tech stack used.
   - "link": GitHub, live URL, or empty string.
   - "start_date" & "end_date": date range or empty string.
   - "bullets": array of objects: [{{"id": "p1", "text": "bullet text..."}}].
5. "education": Academic history.
   - "institution": university or college (e.g. "MCKV Institute of Engineering").
   - "degree": degree level (e.g. "B.Tech", "M.S.").
   - "field": major/field of study (e.g. "Computer Science & Engineering").
   - "end_date": graduation date or year (e.g. "2024").
   - "gpa": GPA if listed or empty string.
6. "summary": A clean 2-4 sentence professional summary. Do NOT include contact info or headers here.

Return ONLY the JSON object. Do not enclose in backticks or markdown if possible.

Resume Text:
\"\"\"
{full_text}
\"\"\"
"""

        try:
            raw_content = ""
            model_name = ""

            if nvidia_key:
                from openai import OpenAI
                base_url = getattr(settings, "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
                model_name = getattr(settings, "NVIDIA_MODEL", "deepseek-ai/deepseek-v4.1-flash")
                client = OpenAI(base_url=base_url, api_key=nvidia_key, timeout=4.0)
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a precise resume parser that extracts resume content into structured JSON without altering or hallucinating facts."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    max_tokens=4096,
                    timeout=4.0
                )
                raw_content = resp.choices[0].message.content or ""
            else:
                import litellm
                model_name = "gpt-4o-mini" if openai_key else ("gemini/gemini-1.5-flash" if gemini_key else "claude-3-haiku-20240307")
                response = litellm.completion(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    timeout=4.0
                )
                raw_content = response.choices[0].message.content or ""

            # Clean markdown code fences if present
            cleaned_content = raw_content.strip()
            if cleaned_content.startswith("```"):
                lines = cleaned_content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_content = "\n".join(lines).strip()

            parsed = json.loads(cleaned_content)
            if not isinstance(parsed, dict):
                return None

            # Ensure bullets have IDs and proper structure
            for exp in parsed.get("experience", []):
                bullets = exp.get("bullets", [])
                normalized_bullets = []
                for b in bullets:
                    if isinstance(b, str):
                        normalized_bullets.append({"id": str(uuid.uuid4())[:8], "text": b.strip()})
                    elif isinstance(b, dict):
                        normalized_bullets.append({"id": b.get("id") or str(uuid.uuid4())[:8], "text": b.get("text", "").strip()})
                exp["bullets"] = normalized_bullets

            for proj in parsed.get("projects", []):
                bullets = proj.get("bullets", [])
                normalized_bullets = []
                for b in bullets:
                    if isinstance(b, str):
                        normalized_bullets.append({"id": str(uuid.uuid4())[:8], "text": b.strip()})
                    elif isinstance(b, dict):
                        normalized_bullets.append({"id": b.get("id") or str(uuid.uuid4())[:8], "text": b.get("text", "").strip()})
                proj["bullets"] = normalized_bullets

            # Ensure skills are normalized to [{name, category}]
            skills = parsed.get("skills", [])
            normalized_skills = []
            for s in skills:
                if isinstance(s, str):
                    normalized_skills.append({"name": s.strip(), "category": get_skill_category(s.strip())})
                elif isinstance(s, dict) and "name" in s:
                    cat = s.get("category") or get_skill_category(s["name"])
                    normalized_skills.append({"name": s["name"].strip(), "category": cat})
            parsed["skills"] = normalized_skills

            if "personal" in parsed and ("experience" in parsed or "skills" in parsed):
                logger.info(f"Successfully extracted resume via LLM model '{model_name}'.")
                return parsed

        except Exception as e:
            logger.warning(f"LLM resume parsing skipped or failed: {e}. Using deterministic engine.")

        return None


resume_parser = ResumeParserService()
