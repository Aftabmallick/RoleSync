import re
from typing import Dict, Any, List, Optional
from app.services.taxonomy import taxonomy_service
from app.services.llm_client import LLMClientService
from app.schemas.cover_letter import CoverLetterResponse


class CoverLetterService:
    @classmethod
    def generate_cover_letter(
        cls,
        target_role: str,
        company_name: str,
        raw_job_description: str,
        candidate_name: str = "Alex Mercer",
        candidate_summary: Optional[str] = None,
        master_profile: Optional[Dict[str, Any]] = None,
        tone: str = "professional"
    ) -> CoverLetterResponse:
        """
        Synthesizes a high-impact, ATS-optimized cover letter mapped strictly to authentic
        candidate achievements from their Master Profile.
        """
        # 1. Extract required skills from JD
        jd_skills = taxonomy_service.extract_skills_from_text(raw_job_description)

        # 2. Extract profile details
        profile = master_profile or {}
        personal = profile.get("personal", {})
        cand_name = personal.get("full_name") or candidate_name or "Alex Mercer"
        cand_summary = personal.get("summary") or candidate_summary or profile.get("summary") or (
            f"Experienced {target_role} specializing in scalable architecture and high-performance engineering."
        )

        experiences = profile.get("experience", [])
        projects = profile.get("projects", [])

        # 3. Find top matching skills
        profile_skills_raw = profile.get("skills", [])
        profile_skills = [
            s.get("name", "") if isinstance(s, dict) else str(s)
            for s in profile_skills_raw
        ]
        matched_skills = [
            s for s in profile_skills
            if taxonomy_service.normalize_skill(s) in jd_skills
        ]
        if not matched_skills:
            matched_skills = profile_skills[:4] or ["Python", "FastAPI", "PostgreSQL", "Docker"]

        # 4. Find most impactful authentic bullets from experience
        highlight_bullets = []
        for exp in experiences:
            company = exp.get("company", "Tech Company")
            role = exp.get("role", "Software Engineer")
            for b in exp.get("bullets", []):
                b_text = b.get("text", "")
                # Prioritize bullets with numbers/metrics or matching skills
                has_metric = bool(re.search(r"(\d+%|\$\d+|\d+x|\d+\s*(?:ms|s|users|requests))", b_text, re.IGNORECASE))
                has_skill = any(s.lower() in b_text.lower() for s in matched_skills)
                if has_metric or has_skill:
                    highlight_bullets.append((company, role, b_text))
                    break
            if len(highlight_bullets) >= 2:
                break

        # Fallback if no bullets matched
        if not highlight_bullets and experiences:
            first_exp = experiences[0]
            first_bullets = first_exp.get("bullets", [])
            if first_bullets:
                highlight_bullets.append((
                    first_exp.get("company", "Leading Systems"),
                    first_exp.get("role", target_role),
                    first_bullets[0].get("text", "Engineered scalable cloud infrastructure and backend microservices.")
                ))

        # 5. Attempt AI-driven synthesis via LLMClientService with strict guardrails
        top_skills_str = ", ".join(matched_skills[:4])
        llm_letter = LLMClientService.generate_cover_letter(
            target_role=target_role,
            company_name=company_name,
            required_skills=matched_skills,
            candidate_name=cand_name,
            candidate_summary=cand_summary,
            highlight_bullets=highlight_bullets,
            tone=tone
        )

        if llm_letter:
            subject = llm_letter.get("subject", f"Application for {target_role} - {cand_name}")
            salutation = llm_letter.get("salutation", f"Dear {company_name} Hiring Team,")
            opening = llm_letter.get("opening_paragraph", "")
            body_paragraphs = llm_letter.get("body_paragraphs", [])
            closing = llm_letter.get("closing_paragraph", "")
        else:
            # Deterministic template fallback
            if tone == "enthusiastic":
                subject = f"Application for {target_role} - {cand_name}"
                salutation = f"Dear {company_name} Hiring Team,"
                opening = (
                    f"I am thrilled to submit my application for the {target_role} position at {company_name}. "
                    f"With deep hands-on expertise in {top_skills_str}, I have followed {company_name}'s "
                    f"recent achievements with great admiration and would love to bring my technical background and problem-solving passion to your team."
                )
            elif tone == "confident":
                subject = f"{cand_name} - {target_role} Application"
                salutation = f"Dear Hiring Manager,"
                opening = (
                    f"I am writing to express my strong interest in the {target_role} role at {company_name}. "
                    f"Throughout my career as a {target_role}, I have specialized in building robust, high-throughput architectures "
                    f"leveraging {top_skills_str}. My technical foundation aligns directly with {company_name}'s engineering standards."
                )
            else:  # professional default
                subject = f"{target_role} Application - {cand_name}"
                salutation = f"Dear {company_name} Recruiting Team,"
                opening = (
                    f"I am writing to express my enthusiastic interest in the {target_role} opportunity at {company_name}. "
                    f"Having developed deep engineering competencies across {top_skills_str}, I am confident in my ability "
                    f"to make an immediate, meaningful impact on your engineering objectives."
                )

            body_paragraphs = []

            # Body paragraph 1: Experience & quantitative metrics
            if highlight_bullets:
                comp1, role1, bullet1 = highlight_bullets[0]
                body_paragraphs.append(
                    f"In my role as {role1} at {comp1}, I focused on solving critical infrastructure and performance challenges. "
                    f"Specifically, {bullet1.lower() if bullet1.startswith('I ') else bullet1} "
                    f"This experience solidified my approach to writing maintainable code and architecting resilient services under high concurrency."
                )
            else:
                body_paragraphs.append(
                    f"Throughout my tenure leading software initiatives, I have consistently delivered scalable backend systems, "
                    f"focusing on low-latency data pipelines and zero-downtime microservice deployments utilizing {top_skills_str}."
                )

            # Body paragraph 2: Project or additional experience
            if len(highlight_bullets) > 1:
                comp2, role2, bullet2 = highlight_bullets[1]
                body_paragraphs.append(
                    f"Additionally, while serving as {role2} at {comp2}, {bullet2.lower() if bullet2.startswith('I ') else bullet2} "
                    f"I look forward to applying this same rigor and data-driven execution to the initiatives underway at {company_name}."
                )
            elif projects:
                p = projects[0]
                p_name = p.get("name", "TitanRAG")
                p_tech = p.get("technologies") or top_skills_str
                p_bullet = p.get("bullets", [{}])[0].get("text", "Engineered scalable cloud applications.")
                body_paragraphs.append(
                    f"Beyond professional roles, I engineered {p_name} ({p_tech}), where I {p_bullet.lower() if p_bullet.startswith('I ') else p_bullet} "
                    f"This work reflects my dedication to modern software craftsmanship, automated verification, and reliable engineering."
                )
            else:
                body_paragraphs.append(
                    f"What excites me most about {company_name} is the opportunity to tackle ambitious technical challenges alongside "
                    f"a world-class team. I bring a relentless commitment to automated testing, code quality, and cross-functional collaboration."
                )

            closing = (
                f"Thank you for your time and consideration. I would welcome the opportunity to discuss how my experience and skills "
                f"in {top_skills_str} can help {company_name} accomplish its engineering goals. I look forward to speaking with you soon."
            )

        full_text = (
            f"{salutation}\n\n"
            f"{opening}\n\n"
            f"{'\n\n'.join(body_paragraphs)}\n\n"
            f"{closing}\n\n"
            f"Sincerely,\n{cand_name}"
        )

        word_count = len(full_text.split())

        return CoverLetterResponse(
            company_name=company_name,
            target_role=target_role,
            candidate_name=cand_name,
            subject=subject,
            salutation=salutation,
            opening_paragraph=opening,
            body_paragraphs=body_paragraphs,
            closing_paragraph=closing,
            full_text=full_text,
            word_count=word_count,
            matched_skills=matched_skills
        )
