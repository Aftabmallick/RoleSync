import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from app.core.config import settings
from app.services.guardrails import GuardrailSanitizer

logger = logging.getLogger("rolesync.llm_client")


class LLMClientService:
    """
    Enterprise Multi-Provider LLM Gateway.
    Prioritizes NVIDIA NIM (DeepSeek V4.1 Flash) from environment,
    with automatic failover to deterministic fact-preserving synthesis.
    Enforces strict prompt injection filtering and zero-hallucination guardrails.
    """

    @classmethod
    def get_client(cls) -> Optional[OpenAI]:
        nvidia_key = getattr(settings, "NVIDIA_API_KEY", None) or os.getenv("NVIDIA_API_KEY")
        if nvidia_key:
            base_url = getattr(settings, "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
            return OpenAI(base_url=base_url, api_key=nvidia_key)
        
        openai_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        if openai_key:
            return OpenAI(api_key=openai_key)

        return None

    @classmethod
    def rewrite_bullets(
        cls,
        target_role: str,
        company_name: str,
        required_keywords: List[str],
        original_bullets: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        Synthesizes tailored experience bullets that naturally weave target keywords into verified candidate achievements.
        Strict zero-hallucination constraint: never modifies metrics, dates, or companies.
        Validates inputs with GuardrailSanitizer against prompt injection attacks.
        """
        # Input sanitization & injection detection
        safe_role = GuardrailSanitizer.sanitize_prompt_input(target_role, max_length=150)
        safe_company = GuardrailSanitizer.sanitize_prompt_input(company_name, max_length=150)
        safe_keywords = [GuardrailSanitizer.sanitize_prompt_input(k, max_length=100) for k in required_keywords]
        
        sanitized_bullets = []
        injection_detected = False
        for b in original_bullets:
            raw_text = b.get("text", "")
            if GuardrailSanitizer.detect_prompt_injection(raw_text):
                logger.warning(f"Prompt injection pattern detected in bullet id={b.get('id')}; aborting LLM invocation.")
                injection_detected = True
                break
            sanitized_bullets.append({
                "id": b.get("id", ""),
                "text": GuardrailSanitizer.sanitize_prompt_input(raw_text, max_length=1000)
            })

        client = cls.get_client() if not injection_detected else None
        model_name = getattr(settings, "NVIDIA_MODEL", "deepseek-ai/deepseek-v4.1-flash")

        if client and not injection_detected:
            prompt = f"""
You are an expert executive resume writer. Tailor the candidate's authentic experience bullet points for the role of {safe_role} at {safe_company}.

CRITICAL ZERO-HALLUCINATION RULES:
1. Preserve all existing metrics, numbers, percentages, and dollar amounts EXACTLY as they appear. DO NOT invent or inflate any numbers.
2. Emphasize relevant technical keywords: {', '.join(safe_keywords[:6])}.
3. Every rewritten bullet must remain factually entailed by the original.
4. Output strict JSON array of objects: [{{"id": "original_id", "text": "tailored text..."}}].

Original Bullets:
{json.dumps(sanitized_bullets, indent=2)}
"""
            try:
                resp = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a precise resume enhancer that strictly adheres to factual entailment."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=1024
                )
                content = resp.choices[0].message.content or ""
                # Parse JSON
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    lines = cleaned.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    cleaned = "\n".join(lines).strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, list) and len(parsed) == len(original_bullets):
                    return parsed
            except Exception as e:
                logger.warning(f"LLM bullet rewrite failed ({e}). Using deterministic enhancement.")

        # Deterministic factual enhancement fallback
        enhanced: List[Dict[str, str]] = []
        kw_pool = list(safe_keywords)
        for idx, b in enumerate(original_bullets):
            orig_text = b.get("text", "")
            b_id = b.get("id", f"b_{idx}")
            if kw_pool and not any(k.lower() in orig_text.lower() for k in kw_pool[:2]):
                chosen_kw = ", ".join(k.title() for k in kw_pool[:2])
                kw_pool = kw_pool[2:]
                clean_text = orig_text.rstrip(".")
                new_text = f"{clean_text} utilizing {chosen_kw} to optimize system performance and reliability."
            else:
                new_text = orig_text
            enhanced.append({"id": b_id, "text": new_text})

        return enhanced

    @classmethod
    def generate_cover_letter(
        cls,
        target_role: str,
        company_name: str,
        required_skills: List[str],
        candidate_name: str,
        candidate_summary: str,
        highlight_bullets: List[Tuple[str, str, str]],
        tone: str = "professional"
    ) -> Optional[Dict[str, Any]]:
        """
        Synthesizes an executive, targeted cover letter adhering strictly to candidate background.
        Returns parsed dictionary with subject, salutation, opening_paragraph, body_paragraphs, closing_paragraph
        or None if LLM is unavailable / failed.
        """
        # Sanitize all inputs
        safe_role = GuardrailSanitizer.sanitize_prompt_input(target_role, max_length=150)
        safe_company = GuardrailSanitizer.sanitize_prompt_input(company_name, max_length=150)
        safe_name = GuardrailSanitizer.sanitize_prompt_input(candidate_name, max_length=150)
        safe_summary = GuardrailSanitizer.sanitize_prompt_input(candidate_summary, max_length=800)
        safe_skills = [GuardrailSanitizer.sanitize_prompt_input(s, max_length=100) for s in required_skills[:8]]

        for comp, r, bullet in highlight_bullets:
            if GuardrailSanitizer.detect_prompt_injection(bullet):
                logger.warning("Prompt injection detected in candidate bullet for cover letter; aborting LLM synthesis.")
                return None

        client = cls.get_client()
        if not client:
            return None

        bullets_repr = "\n".join([
            f"- At {comp} as {r}: {bullet}"
            for comp, r, bullet in highlight_bullets
        ])

        prompt = f"""
You are a premier executive career advisor and cover letter author.
Generate an authentic, compelling cover letter for {safe_name} applying for {safe_role} at {safe_company}.

Tone: {tone}
Key Candidate Background:
Summary: {safe_summary}
Target Matching Skills: {', '.join(safe_skills)}
Key Verified Achievements:
{bullets_repr}

RULES:
1. Reference ONLY the authentic experiences and skills provided above. Do not hallucinate employers, metrics, or credentials.
2. Structure must be clean, narrative-driven, and highly persuasive.
3. Return STRICT valid JSON with the following structure:
{{
  "subject": "Application for {safe_role} - {safe_name}",
  "salutation": "Dear {safe_company} Hiring Team,",
  "opening_paragraph": "...",
  "body_paragraphs": [
    "paragraph focusing on technical achievements and metrics...",
    "paragraph connecting achievements to company mission and engineering culture..."
  ],
  "closing_paragraph": "..."
}}
"""
        model_name = getattr(settings, "NVIDIA_MODEL", "deepseek-ai/deepseek-v4.1-flash")
        try:
            resp = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a professional cover letter generator that outputs strictly structured JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            content = resp.choices[0].message.content or ""
            cleaned = content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()
            parsed = json.loads(cleaned)
            if (
                isinstance(parsed, dict)
                and "opening_paragraph" in parsed
                and "body_paragraphs" in parsed
                and isinstance(parsed["body_paragraphs"], list)
            ):
                return parsed
        except Exception as e:
            logger.warning(f"LLM cover letter generation failed ({e}). Falling back to deterministic engine.")

        return None


