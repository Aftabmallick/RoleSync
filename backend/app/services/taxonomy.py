import json
import pathlib
import re
from typing import Dict, Set, Optional, Tuple, List


class SkillTaxonomy:
    """
    Deterministic skill taxonomy and alias normalizer.
    Maps non-standard variations (e.g. 'k8s', 'postgres', 'react.js')
    to canonical technical entities in sub-millisecond time.
    """
    def __init__(self, data_path: Optional[str] = None):
        self.data_path = data_path or str(
            pathlib.Path(__file__).parent.parent / "data" / "canonical_skills.json"
        )
        self.alias_to_canonical: Dict[str, str] = {}
        self.canonical_to_category: Dict[str, str] = {}
        self.all_canonical_skills: Set[str] = set()
        self._compiled_regex_patterns: List[Tuple[re.Pattern, str]] = []
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        try:
            path = pathlib.Path(self.data_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = self._get_fallback_data()
        except Exception:
            data = self._get_fallback_data()

        for category, skill_map in data.items():
            for canonical, aliases in skill_map.items():
                canonical_clean = canonical.lower().strip()
                self.all_canonical_skills.add(canonical_clean)
                self.canonical_to_category[canonical_clean] = category

                # Ensure canonical key maps to itself
                self.alias_to_canonical[canonical_clean] = canonical_clean

                # Map all aliases
                for alias in aliases:
                    alias_clean = alias.lower().strip()
                    self.alias_to_canonical[alias_clean] = canonical_clean

        # Build regex patterns for entity extraction from raw text
        # Sort by length descending to match longest phrases first (e.g., 'amazon web services' before 'aws')
        sorted_aliases = sorted(self.alias_to_canonical.keys(), key=lambda x: len(x), reverse=True)
        for alias in sorted_aliases:
            # Special case short/common words to avoid false positive triggers in prose
            if alias in {"c", "r", "go", "next"}:
                pattern = re.compile(rf'(?i)(?:\b{re.escape(alias)}\b\s+(?:programming|language|developer|runtime|framework|stack))|(?:\b(?:using|in|with)\s+{re.escape(alias)}\b)')
            else:
                pattern = re.compile(rf'(?i)\b{re.escape(alias)}\b')
            self._compiled_regex_patterns.append((pattern, self.alias_to_canonical[alias]))

    def normalize_skill(self, raw_skill: str) -> str:
        """
        Normalizes a skill string to its canonical identifier.
        Example:
            'PostgreSQL' -> 'postgresql'
            'k8s' -> 'kubernetes'
            'React.js' -> 'react'
        If unmapped, returns the cleaned, lowercase string.
        """
        if not raw_skill:
            return ""
        cleaned = raw_skill.lower().strip()
        # Direct dictionary lookup
        if cleaned in self.alias_to_canonical:
            return self.alias_to_canonical[cleaned]

        # Punctuation normalization: e.g. 'react-js' -> 'react js'
        simplified = re.sub(r'[\-_.]', ' ', cleaned).strip()
        if simplified in self.alias_to_canonical:
            return self.alias_to_canonical[simplified]

        return cleaned

    def get_skill_category(self, raw_skill: str) -> Optional[str]:
        """Returns the high-level category of the skill (e.g., 'languages', 'databases')."""
        canonical = self.normalize_skill(raw_skill)
        return self.canonical_to_category.get(canonical)

    def extract_skills_from_text(self, text: str) -> Set[str]:
        """
        Extracts all canonical technical skills mentioned in arbitrary text
        (e.g., Job Descriptions or resume summaries).
        """
        if not text:
            return set()

        extracted: Set[str] = set()
        for pattern, canonical in self._compiled_regex_patterns:
            if pattern.search(text):
                extracted.add(canonical)

        return extracted

    def is_equivalent(self, skill_a: str, skill_b: str) -> bool:
        """Checks if two skill strings resolve to the exact same canonical entity."""
        return self.normalize_skill(skill_a) == self.normalize_skill(skill_b)

    @staticmethod
    def _get_fallback_data() -> Dict[str, Dict[str, List[str]]]:
        """Embedded fallback in case external JSON is missing."""
        return {
            "languages": {
                "python": ["python", "python3", "py"],
                "javascript": ["javascript", "js"],
                "typescript": ["typescript", "ts"],
                "golang": ["golang", "go"],
                "rust": ["rust"]
            },
            "frameworks": {
                "react": ["react", "react.js", "reactjs"],
                "fastapi": ["fastapi"],
                "django": ["django"]
            },
            "databases": {
                "postgresql": ["postgresql", "postgres", "psql"],
                "redis": ["redis"],
                "qdrant": ["qdrant"]
            },
            "cloud_devops": {
                "kubernetes": ["kubernetes", "k8s"],
                "docker": ["docker"],
                "amazon web services": ["aws", "amazon web services"]
            }
        }


taxonomy_service = SkillTaxonomy()
normalize_skill = taxonomy_service.normalize_skill
get_skill_category = taxonomy_service.get_skill_category
