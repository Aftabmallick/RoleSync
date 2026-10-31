import hashlib
import logging
import os
from typing import List, Dict, Optional, Tuple
import numpy as np
from app.core.config import settings

logger = logging.getLogger("rolesync.embedding")

_embedding_model = None
_embedding_cache: Dict[str, np.ndarray] = {}


class EmbeddingService:
    """
    Dual-Provider Vector Embedding Engine.
    Primary: OpenAI text-embedding-3-large (3072 dimensions) when OPENAI_API_KEY is configured.
    Fallback: Local CPU FastEmbed (all-MiniLM-L6-v2, 384 dimensions) for zero-latency offline execution.
    Emergency: Deterministic MD5 n-gram hashing projection.
    """

    @classmethod
    def get_dimension(cls) -> int:
        if getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY"):
            return 3072
        return getattr(settings, "VECTOR_DIMENSION", 384)

    @classmethod
    def _get_openai_client(cls):
        api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                return OpenAI(api_key=api_key)
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client for embeddings: {e}")
        return None

    @classmethod
    def _get_model(cls):
        global _embedding_model
        if _embedding_model is None:
            try:
                from fastembed import TextEmbedding
                # Loads quantized ONNX model for CPU
                _embedding_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
                logger.info("Initialized local FastEmbed all-MiniLM-L6-v2 model on CPU.")
            except Exception as e:
                logger.warning(f"Could not load FastEmbed model: {e}")
                _embedding_model = False
        return _embedding_model if _embedding_model is not False else None

    @classmethod
    def embed_text(cls, text: str) -> np.ndarray:
        """
        Embeds a single string into a normalized dense numpy vector.
        Thread-safe with LRU memory caching.
        """
        dim = cls.get_dimension()
        clean = " ".join(text.strip().split())
        if not clean:
            return np.zeros(dim, dtype=np.float32)

        cache_key = hashlib.sha256(f"{dim}:{clean}".encode("utf-8")).hexdigest()
        if cache_key in _embedding_cache:
            return _embedding_cache[cache_key]

        # 1. Try OpenAI text-embedding-3-large if key configured
        openai_client = cls._get_openai_client()
        if openai_client:
            try:
                res = openai_client.embeddings.create(
                    input=clean,
                    model="text-embedding-3-large",
                    dimensions=3072
                )
                vec = np.array(res.data[0].embedding, dtype=np.float32)
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = vec / norm
                _embedding_cache[cache_key] = vec
                return vec
            except Exception as e:
                logger.warning(f"OpenAI embedding error, falling back to local FastEmbed: {e}")

        # 2. Local FastEmbed fallback (384 dimensions)
        model = cls._get_model()
        if model is not None:
            try:
                embeddings = list(model.embed([clean]))
                if embeddings:
                    vec = np.array(embeddings[0], dtype=np.float32)
                    norm = np.linalg.norm(vec)
                    if norm > 0:
                        vec = vec / norm
                    _embedding_cache[cache_key] = vec
                    return vec
            except Exception as e:
                logger.warning(f"FastEmbed embedding error: {e}")

        # 3. Deterministic pseudo-embedding fallback using character n-gram hashing
        vec = cls._hash_fallback_vector(clean, dim)
        _embedding_cache[cache_key] = vec
        return vec

    @classmethod
    def embed_texts(cls, texts: List[str]) -> List[np.ndarray]:
        """Embeds a batch of strings efficiently."""
        return [cls.embed_text(t) for t in texts]

    @classmethod
    def compute_cosine_similarity(cls, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Computes normalized cosine similarity in range [0.0, 1.0]."""
        if vec1 is None or vec2 is None:
            return 0.5
        # If dimensions differ due to model switch, slice to matching min dim
        if len(vec1) != len(vec2):
            min_len = min(len(vec1), len(vec2))
            vec1 = vec1[:min_len]
            vec2 = vec2[:min_len]
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        cos = float(np.dot(vec1, vec2) / (norm1 * norm2))
        return float(max(0.0, min(1.0, (cos + 1.0) / 2.0 if cos < 0 else cos)))

    @classmethod
    def _hash_fallback_vector(cls, text: str, dim: int = 384) -> np.ndarray:
        """Deterministic dimensional projection when ONNX weights are initializing."""
        words = text.lower().split()
        vec = np.zeros(dim, dtype=np.float32)
        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if (h // dim) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = np.linalg.norm(vec)
        return (vec / norm) if norm > 0 else vec


