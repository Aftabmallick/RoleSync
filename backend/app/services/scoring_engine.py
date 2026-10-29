import re
import math
from typing import Set, Dict, Any, List, Optional
import numpy as np
from collections import Counter
from app.services.taxonomy import normalize_skill
from app.services.embedding_service import EmbeddingService


class ATSScoringEngine:
    WEIGHT_SEMANTIC = 0.35
    WEIGHT_SKILL = 0.30
    WEIGHT_LEXICAL = 0.15
    WEIGHT_EXPERIENCE = 0.20

    STOP_WORDS = {
        "the", "and", "or", "to", "in", "with", "a", "an", "of", "for", "on", "at", "by", "from",
        "as", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does",
        "did", "but", "if", "then", "else", "when", "up", "down", "out", "over", "under", "again",
        "further", "once", "here", "there", "all", "any", "both", "each", "few", "more", "most",
        "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
        "very", "can", "will", "just", "should", "now", "we", "our", "you", "your", "they", "their"
    }

    @classmethod
    def calculate_score(
        cls,
        resume_embedding: Optional[np.ndarray],
        jd_embedding: Optional[np.ndarray],
        resume_skills: Set[str],
        jd_required_skills: Set[str],
        resume_text: str,
        jd_text: str,
        required_years: float,
        actual_years: float
    ) -> Dict[str, Any]:
        """
        Calculates a composite 4-dimension ATS match score scaled from 0.0 to 100.0.
        Dimensions:
            1. Semantic Cosine Proximity (w1 = 0.35)
            2. Canonical Hard Skill Coverage Recall (w2 = 0.30)
            3. Sublinear TF Lexical Match (w3 = 0.15)
            4. Seniority & Experience Curve (w4 = 0.20)
        """
        # 1. Cosine Semantic Similarity via Dense Vector Embeddings
        if resume_embedding is None and resume_text:
            resume_embedding = EmbeddingService.embed_text(resume_text)
        if jd_embedding is None and jd_text:
            jd_embedding = EmbeddingService.embed_text(jd_text)

        if resume_embedding is not None and jd_embedding is not None:
            cos_sim_norm = EmbeddingService.compute_cosine_similarity(resume_embedding, jd_embedding)
        else:
            cos_sim_norm = cls._calculate_jaccard_fallback(resume_text, jd_text)

        # 2. Hard Skill Overlap (Normalized via Canonical Taxonomy)
        norm_resume_skills = {normalize_skill(s) for s in resume_skills if s}
        norm_jd_skills = {normalize_skill(s) for s in jd_required_skills if s}

        if not norm_jd_skills:
            skill_ratio = 1.0
            matched_skills = list(norm_resume_skills)
            missing_skills = []
        else:
            matched = norm_resume_skills.intersection(norm_jd_skills)
            skill_ratio = len(matched) / len(norm_jd_skills)
            matched_skills = sorted(list(matched))
            missing_skills = sorted(list(norm_jd_skills - norm_resume_skills))

        # 3. Sublinear TF Length-Normalized Lexical Score
        lexical_score = cls._calculate_sublinear_lexical_score(resume_text, jd_text)

        # 4. Seniority & Experience Alignment
        exp_score = cls._calculate_experience_alignment(required_years, actual_years)

        # Weighted Composite Formulation
        composite = (
            (cls.WEIGHT_SEMANTIC * cos_sim_norm) +
            (cls.WEIGHT_SKILL * skill_ratio) +
            (cls.WEIGHT_LEXICAL * lexical_score) +
            (cls.WEIGHT_EXPERIENCE * exp_score)
        ) * 100.0

        composite = round(min(100.0, max(0.0, composite)), 2)

        return {
            "composite_score": composite,
            "semantic_score": round(cos_sim_norm * 100, 2),
            "skill_coverage_score": round(skill_ratio * 100, 2),
            "lexical_score": round(lexical_score * 100, 2),
            "experience_alignment_score": round(exp_score * 100, 2),
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "recommendation": cls._get_recommendation(composite)
        }

    @classmethod
    def _calculate_sublinear_lexical_score(cls, resume_text: str, jd_text: str) -> float:
        """
        Sublinear TF Length-Normalized Lexical Matcher.
        Damps high frequency keyword repetition using (1 + ln(TF)).
        """
        if not jd_text or not resume_text:
            return 0.0

        jd_tokens = [w for w in re.findall(r'\b[a-z]{2,}\b', jd_text.lower()) if w not in cls.STOP_WORDS]
        res_tokens = [w for w in re.findall(r'\b[a-z]{2,}\b', resume_text.lower()) if w not in cls.STOP_WORDS]

        if not jd_tokens:
            return 1.0

        jd_counts = Counter(jd_tokens)
        res_counts = Counter(res_tokens)

        # Evaluate significant terms (top 50 frequent keywords in JD)
        top_terms = [t for t, _ in jd_counts.most_common(50)]

        numerator = 0.0
        denominator = 0.0

        for term in top_terms:
            jd_weight = 1.0 + math.log(jd_counts[term])
            denominator += jd_weight
            if term in res_counts:
                res_weight = 1.0 + math.log(res_counts[term])
                numerator += min(res_weight, jd_weight)

        if denominator <= 0:
            return 1.0

        return min(1.0, max(0.0, numerator / denominator))

    @staticmethod
    def _calculate_experience_alignment(req_years: float, actual_years: float) -> float:
        """
        Experience alignment curve:
        - Exact match or within +4 years: 1.0
        - Under-qualified: linear penalty (actual / req)
        - Over-qualified: gentle decay to avoid over-qualification rejection
        """
        if req_years <= 0:
            return 1.0
        if actual_years >= req_years and actual_years <= req_years + 4.0:
            return 1.0
        if actual_years < req_years:
            return max(0.0, actual_years / req_years)
        # Gentle overqualification decay
        over_diff = actual_years - (req_years + 4.0)
        return max(0.70, 1.0 - (0.05 * over_diff))

    @classmethod
    def _calculate_jaccard_fallback(cls, text_a: str, text_b: str) -> float:
        tokens_a = set(re.findall(r'\b[a-z]{2,}\b', text_a.lower())) - cls.STOP_WORDS
        tokens_b = set(re.findall(r'\b[a-z]{2,}\b', text_b.lower())) - cls.STOP_WORDS
        if not tokens_a or not tokens_b:
            return 0.5
        intersect = len(tokens_a.intersection(tokens_b))
        union = len(tokens_a.union(tokens_b))
        return intersect / max(1, union)

    @staticmethod
    def _get_recommendation(score: float) -> str:
        if score >= 85.0:
            return "STRONG_MATCH: High probability of ATS pass. Immediate dispatch recommended."
        if score >= 70.0:
            return "GOOD_MATCH: Rephrase bullet points to emphasize missing keywords."
        if score >= 50.0:
            return "MODERATE_MATCH: Critical technical skills missing from Master Profile."
        return "LOW_MATCH: Profile does not satisfy baseline requirements."
