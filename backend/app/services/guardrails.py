import re
import pathlib
import logging
import unicodedata
from typing import List, Dict, Any, Set, Optional
import numpy as np
from pydantic import BaseModel, Field
from app.services.taxonomy import normalize_skill
from app.core.config import settings

logger = logging.getLogger(__name__)


class TailoredBulletPoint(BaseModel):
    original_bullet_id: str
    tailored_text: str
    keywords_emphasized: List[str] = Field(default_factory=list)
    tag: Optional[str] = None
    preservation_tag: Optional[str] = None


class TailoredExperienceEntry(BaseModel):
    company: str
    role: str
    dates: str
    location: Optional[str] = "Remote / Onsite"
    bullet_points: List[TailoredBulletPoint]


class TailoredResumeDraft(BaseModel):
    skills: List[str]
    experience: List[TailoredExperienceEntry]
    summary: str
    projects: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    personal: Optional[Dict[str, Any]] = None
    section_order: Optional[List[str]] = None


class GuardrailViolationException(Exception):
    def __init__(self, layer: str, message: str, details: Dict[str, Any]):
        super().__init__(f"[{layer}] {message}")
        self.layer = layer
        self.message = message
        self.details = details


class SecurityException(Exception):
    """Raised when an adversarial prompt injection or security violation is detected."""
    def __init__(self, detail: str = "Prompt injection attempt detected in job description input"):
        super().__init__(detail)
        self.detail = detail


class GuardrailSanitizer:
    """
    Input Sanitization & Prompt Injection Protection Engine (Layer 1 Defense).
    Hardened against adversarial instruction overrides, role-playing jailbreaks,
    invisible zero-width unicode evasion, and modern LLM delimiters.
    """
    DELIMITER_PATTERNS = [
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"<\|start_header_id\|>",
        r"<\|end_header_id\|>",
        r"<\|eot_id\|>",
        r"<\|system\|>",
        r"<\|user\|>",
        r"<\|assistant\|>",
        r"\[INST\]",
        r"\[/INST\]",
        r"<<SYS>>",
        r"<</SYS>>",
        r"```\s*system",
    ]
    DELIMITER_REGEX = re.compile(r"(?i)(" + "|".join(DELIMITER_PATTERNS) + ")")

    INJECTION_PATTERNS = [
        # Intent hijacking & instruction override verbs
        re.compile(
            r"(?is)\b(ignore|disregard|neglect|override|bypass|forget|cancel)\b.*\b(instructions?|prompts?|rules?|system|constraints?|context|directives?|guidelines?)\b"
        ),
        # Role-play & persona injection
        re.compile(
            r"(?is)\b(you\s+are\s+now|pretend\s+(?:to\s+be|you\s+are)|act\s+as(?:\s+an?)?|system\s+prompt|new\s+system\s+role|developer\s+mode|jailbreak|unfiltered\s+mode|administrative\s+mode|bypass\s+restrictions)\b"
        ),
        # Modern LLM delimiters & instruction framing
        re.compile(
            r"(?i)(\[INST\]|\[/INST\]|<\|im_start\|>|<\|im_end\|>|<\|start_header_id\|>|<\|end_header_id\|>|<\|eot_id\|>|<\|system\|>|<\|user\|>|<\|assistant\|>|<<SYS>>|<\</SYS>>|```\s*system)"
        ),
    ]

    HOMOGLYPH_MAP = str.maketrans({
        # Cyrillic confusables
        '\u0430': 'a', '\u0410': 'A',
        '\u0441': 'c', '\u0421': 'C',
        '\u0435': 'e', '\u0415': 'E',
        '\u0456': 'i', '\u0406': 'I',
        '\u0458': 'j', '\u0408': 'J',
        '\u043e': 'o', '\u041e': 'O',
        '\u0440': 'p', '\u0420': 'P',
        '\u0455': 's', '\u0405': 'S',
        '\u0445': 'x', '\u0425': 'X',
        '\u0443': 'y', '\u0423': 'Y',
        '\u0501': 'd', '\u0432': 'b',
        '\u04bb': 'h', '\u043f': 'n',
        # Greek confusables
        '\u03bf': 'o', '\u039f': 'O',
        '\u03b1': 'a', '\u0391': 'A',
        '\u03b5': 'e', '\u0395': 'E',
        '\u03b9': 'i', '\u0399': 'I',
        '\u03c1': 'p', '\u03a1': 'P',
    })

    @classmethod
    def detect_prompt_injection(cls, text: str) -> bool:
        if not text or not isinstance(text, str):
            return False
        # 1. Unicode NFKC normalization and cross-script homoglyph translation
        normalized = unicodedata.normalize("NFKC", text).translate(cls.HOMOGLYPH_MAP)
        # 2. Strip zero-width and invisible control characters used for regex evasion
        cleaned = re.sub(r"[\u200B-\u200D\uFEFF\u00AD]", "", normalized)
        # 3. Match against adversarial injection patterns
        return any(pattern.search(cleaned) is not None for pattern in cls.INJECTION_PATTERNS)

    @classmethod
    def sanitize_prompt_input(cls, text: str, max_length: int = 1500) -> str:
        if not text or not isinstance(text, str):
            return ""
        # 1. Unicode NFKC normalization and cross-script homoglyph translation
        cleaned = unicodedata.normalize("NFKC", text).translate(cls.HOMOGLYPH_MAP)
        # 2. Strip zero-width and invisible characters
        cleaned = re.sub(r"[\u200B-\u200D\uFEFF\u00AD]", "", cleaned)
        # 3. Neutralize modern LLM delimiters (multi-pass to handle nested injection)
        for _ in range(3):
            prev = cleaned
            cleaned = cls.DELIMITER_REGEX.sub("", cleaned)
            if cleaned == prev:
                break
        # 4. Truncate length
        cleaned = cleaned[:max_length]
        # 5. Strip raw control characters while preserving valid whitespace
        cleaned = "".join(ch for ch in cleaned if ch.isprintable() or ch in "\n\r\t")
        return cleaned.strip()


class ONNXNLIEngine:
    """
    ONNX Runtime INT8 Natural Language Inference (NLI) Engine.
    Executes cross-encoder NLI (e.g. DeBERTa-v3-small quantized INT8) in <80ms on CPU.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or getattr(settings, "ONNX_NLI_MODEL_PATH", "models/onnx/nli_quantized.onnx")
        self.session = None
        self.tokenizer = None
        self._initialize_tokenizer()
        self._initialize_session()

    def _initialize_tokenizer(self) -> None:
        try:
            p = pathlib.Path(self.model_path)
            tok_dir = p.parent / "tokenizer"
            if tok_dir.exists():
                from transformers import AutoTokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(str(tok_dir), local_files_only=True)
                logger.info(f"Loaded local tokenizer from {tok_dir}")
            else:
                self.tokenizer = None
        except Exception:
            self.tokenizer = None

    def _initialize_session(self) -> None:
        if not self.model_path:
            return
        p = pathlib.Path(self.model_path)
        if not p.exists():
            return
        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.session = ort.InferenceSession(
                str(p),
                sess_options=opts,
                providers=["CPUExecutionProvider"]
            )
            logger.info(f"Loaded ONNX NLI model from {p}")
        except Exception as e:
            logger.warning(f"Could not load ONNX NLI session from {p}: {e}")

    def tokenize_premise_hypothesis(self, premise: str, hypothesis: str, max_length: int = 128) -> Dict[str, np.ndarray]:
        """Maps premise and hypothesis into token tensors for ONNX cross-encoders."""
        if self.tokenizer is not None:
            try:
                encoded = self.tokenizer(
                    premise,
                    hypothesis,
                    max_length=max_length,
                    padding="max_length",
                    truncation=True,
                    return_tensors="np"
                )
                return {
                    "input_ids": encoded["input_ids"].astype(np.int64),
                    "attention_mask": encoded["attention_mask"].astype(np.int64),
                }
            except Exception as e:
                logger.warning(f"Tokenizer encoding failed ({e}); falling back to standard encoding.")

        # Standard deterministic subword/token mapping
        text = f"{premise} [SEP] {hypothesis}"
        words = text.split()
        tokens = [101] + [abs(hash(w)) % 28000 + 1000 for w in words][:max_length - 2] + [102]
        pad_len = max(0, max_length - len(tokens))
        padded_tokens = tokens + [0] * pad_len
        att_mask = [1] * len(tokens) + [0] * pad_len

        return {
            "input_ids": np.array([padded_tokens], dtype=np.int64),
            "attention_mask": np.array([att_mask], dtype=np.int64),
        }

    def predict_nli(self, premise: str, hypothesis: str) -> Dict[str, float]:
        """
        Runs neural entailment evaluation between authentic premise and tailored hypothesis.
        Returns: {"entailment": float, "contradiction": float, "neutral": float}
        """
        p_clean = (premise or "").strip()
        h_clean = (hypothesis or "").strip()

        # Enforce identity entailment: identical strings are factually entailed
        if p_clean == h_clean:
            return {"entailment": 1.0, "contradiction": 0.0, "neutral": 0.0}

        if self.session:
            try:
                model_inputs = self.tokenize_premise_hypothesis(p_clean, h_clean)
                inputs = {inp.name: model_inputs.get(inp.name, np.ones((1, 128), dtype=np.int64)) for inp in self.session.get_inputs()}
                outputs = self.session.run(None, inputs)
                logits = outputs[0][0]
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / np.sum(exp_logits)
                return {
                    "contradiction": float(probs[0]),
                    "neutral": float(probs[1]) if len(probs) > 1 else 0.0,
                    "entailment": float(probs[-1])
                }
            except Exception as exc:
                logger.warning(f"ONNX inference failed: {exc}")

        # Strict Fail-Safe Default Invariant (M1.6 / M5):
        # Whenever ONNX model weights are missing or session initialization fails,
        # eradicate word-overlap fallback and return strict contradiction.
        return {"contradiction": 1.0, "entailment": 0.0, "neutral": 0.0}

    def verify_bullet_factuality(self, premise: str, hypothesis: str) -> Dict[str, float]:
        """Interface contract alias for predict_nli."""
        return self.predict_nli(premise, hypothesis)


class RobustGuardrailVerifier:
    def __init__(
        self,
        master_profile: Dict[str, Any],
        nli_client: Any = None,
        onnx_nli_path: Optional[str] = None
    ):
        self.master = master_profile
        if nli_client is not None:
            self.nli_client = nli_client
        elif onnx_nli_path is not None:
            self.nli_client = ONNXNLIEngine(model_path=onnx_nli_path)
        else:
            self.nli_client = None

        # 1. Build normalized canonical skill lookup
        self.master_skills: Set[str] = set()
        for s in master_profile.get("skills", []):
            if isinstance(s, dict):
                self.master_skills.add(normalize_skill(s.get("name", "")))
            elif isinstance(s, str):
                self.master_skills.add(normalize_skill(s))

        # 2. Build normalized company lookup
        self.master_companies: Set[str] = {
            exp.get("company", "").lower().strip()
            for exp in master_profile.get("experience", [])
            if exp.get("company")
        }

        # 3. Build bullet ID index (handling dict and str bullet shapes gracefully)
        self.master_bullets_index: Dict[str, Dict[str, Any]] = {}
        for idx_e, exp in enumerate(master_profile.get("experience", [])):
            for idx_b, b in enumerate(exp.get("bullets", [])):
                if isinstance(b, dict):
                    b_id = b.get("id") or f"b_{idx_e+1}_{idx_b+1}"
                    self.master_bullets_index[b_id] = b
                elif isinstance(b, str):
                    b_id = f"b_{idx_e+1}_{idx_b+1}"
                    self.master_bullets_index[b_id] = {"id": b_id, "text": b}
        for idx_p, proj in enumerate(master_profile.get("projects", [])):
            for idx_b, b in enumerate(proj.get("bullets", [])):
                if isinstance(b, dict):
                    b_id = b.get("id") or f"p_{idx_p+1}_{idx_b+1}"
                    self.master_bullets_index[b_id] = b
                elif isinstance(b, str):
                    b_id = f"p_{idx_p+1}_{idx_b+1}"
                    self.master_bullets_index[b_id] = {"id": b_id, "text": b}

    def execute_all_layers(self, draft: TailoredResumeDraft) -> None:
        """
        Executes the sequential 4-layer verification pipeline.
        Raises GuardrailViolationException upon detecting any hallucination or drift.
        """
        self._layer_1_schema_check(draft)
        self._layer_2_deterministic_subset_check(draft)
        self._layer_4_metric_integrity_check(draft)
        self._layer_3_nli_entailment_check(draft)

    def verify_bullet_factuality(self, premise: str, hypothesis: str) -> Dict[str, float]:
        """Evaluates factual entailment between premise and hypothesis using configured NLI engine."""
        if self.nli_client:
            return self.nli_client.predict_nli(premise, hypothesis)
        if (premise or "").strip() == (hypothesis or "").strip():
            return {"entailment": 1.0, "contradiction": 0.0, "neutral": 0.0}
        return {"contradiction": 1.0, "entailment": 0.0, "neutral": 0.0}

    def _layer_1_schema_check(self, draft: TailoredResumeDraft) -> None:
        """Layer 1: Structural boundaries, skill volume, and layout constraints."""
        if not draft.skills:
            raise GuardrailViolationException(
                "LAYER_1_SCHEMA",
                "Skill catalog cannot be empty.",
                {"field": "skills"}
            )
        if len(draft.skills) > 40:
            raise GuardrailViolationException(
                "LAYER_1_SCHEMA",
                "Skill count exceeds ATS single-page density budget (max 40).",
                {"count": len(draft.skills), "limit": 40}
            )
        if len(draft.summary) > 600:
            raise GuardrailViolationException(
                "LAYER_1_SCHEMA",
                "Summary exceeds 600-character layout budget limit.",
                {"length": len(draft.summary), "limit": 600}
            )
        if not draft.experience:
            raise GuardrailViolationException(
                "LAYER_1_SCHEMA",
                "Experience entries cannot be empty.",
                {"field": "experience"}
            )

    def _layer_2_deterministic_subset_check(self, draft: TailoredResumeDraft) -> None:
        """
        Layer 2: Strict mathematical subset validation against the Master Profile,
        leveraging the Canonical Skill Graph to prevent false rejections of valid aliases.
        """
        # 1. Validate skills
        for skill in draft.skills:
            canonical = normalize_skill(skill)
            if canonical not in self.master_skills:
                raise GuardrailViolationException(
                    "LAYER_2_SUBSET",
                    f"Hallucinated skill detected: '{skill}' (canonical: '{canonical}') is not present in candidate Master Profile.",
                    {"unauthorized_skill": skill, "canonical": canonical}
                )

        # 2. Validate companies and bullet links
        for exp in draft.experience:
            comp_clean = exp.company.lower().strip()
            if comp_clean not in self.master_companies:
                raise GuardrailViolationException(
                    "LAYER_2_SUBSET",
                    f"Hallucinated company detected: '{exp.company}'",
                    {"unauthorized_company": exp.company}
                )

            for bullet in exp.bullet_points:
                if bullet.original_bullet_id not in self.master_bullets_index:
                    raise GuardrailViolationException(
                        "LAYER_2_SUBSET",
                        f"Unlinked bullet ID '{bullet.original_bullet_id}' detected.",
                        {"invalid_bullet_id": bullet.original_bullet_id}
                    )

    def _layer_3_nli_entailment_check(self, draft: TailoredResumeDraft) -> None:
        """
        Layer 3: Semantic NLI Entailment verification using Natural Language Inference.
        Premise = Master original fact; Hypothesis = Tailored phrasing.
        """
        if not self.nli_client:
            return  # Skipped if NLI client is disabled in lightweight testing mode

        for exp in draft.experience:
            for bullet in exp.bullet_points:
                master_orig = self.master_bullets_index[bullet.original_bullet_id]["text"]
                scores = self.nli_client.predict_nli(premise=master_orig, hypothesis=bullet.tailored_text)

                entailment = scores.get("entailment", 1.0)
                contradiction = scores.get("contradiction", 0.0)

                if contradiction > 0.15:
                    raise GuardrailViolationException(
                        "LAYER_3_NLI",
                        f"Factual contradiction detected in tailored bullet: {bullet.tailored_text}",
                        {
                            "contradiction_score": contradiction,
                            "premise": master_orig,
                            "bullet_id": bullet.original_bullet_id
                        }
                    )
                if entailment < 0.88:
                    raise GuardrailViolationException(
                        "LAYER_3_NLI",
                        f"Tailored bullet lacks factual entailment (score: {entailment:.2f}): {bullet.tailored_text}",
                        {
                            "entailment_score": entailment,
                            "premise": master_orig,
                            "bullet_id": bullet.original_bullet_id
                        }
                    )

    def _layer_4_metric_integrity_check(self, draft: TailoredResumeDraft) -> None:
        """
        Layer 4: Prevents numerical inflation and metric fabrication.
        Extracts numbers, currency, percentages, and multipliers with magnitude normalization.
        """
        for exp in draft.experience:
            for bullet in exp.bullet_points:
                master_text = self.master_bullets_index[bullet.original_bullet_id]["text"]
                master_metrics = self.extract_normalized_metrics(master_text)
                tailored_metrics = self.extract_normalized_metrics(bullet.tailored_text)

                # Ensure every metric claimed in tailored bullet was present in master bullet
                fabricated = tailored_metrics - master_metrics
                if fabricated:
                    raise GuardrailViolationException(
                        "LAYER_4_METRIC",
                        f"Fabricated or altered quantitative metrics: {fabricated}",
                        {"fabricated_metrics": list(fabricated), "master_text": master_text}
                    )

    @classmethod
    def extract_normalized_metrics(cls, text: str) -> Set[str]:
        """
        Extracts and normalizes numbers, percentages, currency, and multipliers.
        Examples:
            '$1.5M' -> '$1500000'
            '$1,500,000' -> '$1500000'
            '1500ms' -> '1500ms'
            '1.5s' -> '1500ms'
            '20%' -> '20%'
            '10x' -> '10x'
        """
        text = text.lower()
        normalized_tokens: Set[str] = set()

        # 1. Currency with suffixes ($1.5M, $200k, $1,500,000)
        currency_matches = re.findall(r'\$\s*([\d,]+(?:\.\d+)?)\s*(k|m|b)?\b', text)
        for num_str, suffix in currency_matches:
            clean_num = num_str.replace(',', '')
            if not clean_num:
                continue
            val = float(clean_num)
            if suffix == 'm':
                val *= 1_000_000
            elif suffix == 'k':
                val *= 1_000
            elif suffix == 'b':
                val *= 1_000_000_000
            normalized_tokens.add(f"${int(val)}")

        # 2. Time/latency conversions (1.5s -> 1500ms, 250ms)
        latency_matches = re.findall(r'\b([\d,]+(?:\.\d+)?)\s*(ms|s)\b', text)
        for num_str, unit in latency_matches:
            val = float(num_str.replace(',', ''))
            if unit == 's':
                val *= 1000.0
            normalized_tokens.add(f"{int(val)}ms")

        # 3. Percentages (e.g. 25%, 99.9%)
        pct_matches = re.findall(r'\b([\d,]+(?:\.\d+)?)\s*%', text)
        for num_str in pct_matches:
            val = float(num_str.replace(',', ''))
            normalized_tokens.add(f"{val:.1f}%")

        # 4. Multipliers (e.g. 10x, 4x)
        mult_matches = re.findall(r'\b([\d,]+(?:\.\d+)?)\s*x\b', text)
        for num_str in mult_matches:
            val = float(num_str.replace(',', ''))
            normalized_tokens.add(f"{val:.1f}x")

        # 5. Plain integers/floats (excluding years 1900-2099 to avoid date conflicts)
        plain_matches = re.findall(r'\b([\d,]+(?:\.\d+)?)\b', text)
        for num_str in plain_matches:
            try:
                num = float(num_str.replace(',', ''))
                # Ignore calendar years
                if 1950 <= num <= 2050 and num == int(num):
                    continue
                normalized_tokens.add(f"num_{num:g}")
            except ValueError:
                pass

        return normalized_tokens


# Interface Contract Alias
GuardrailVerifier = RobustGuardrailVerifier
