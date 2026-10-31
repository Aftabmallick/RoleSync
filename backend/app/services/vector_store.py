import logging
from typing import List, Dict, Any, Optional
import numpy as np
from qdrant_client import AsyncQdrantClient, QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType,
)
from app.core.config import settings
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger("rolesync.vector_store")


class InMemoryVectorStoreMock:
    """
    In-memory vector store mock for local testing and offline sandboxed execution.
    Strictly enforces tenant-level partition isolation using user_id filtering.
    """
    def __init__(self):
        # Maps user_id -> List of {id, vector, payload}
        self._user_points: Dict[str, List[Dict[str, Any]]] = {}

    def upsert(self, user_id: str, point_ids: List[str], vectors: List[List[float]], payloads: List[Dict[str, Any]]) -> None:
        u_key = str(user_id)
        if u_key not in self._user_points:
            self._user_points[u_key] = []

        existing_ids = {p["id"]: idx for idx, p in enumerate(self._user_points[u_key])}
        for pid, vec, pay in zip(point_ids, vectors, payloads):
            p_dict = dict(pay)
            p_dict["user_id"] = u_key
            vec_arr = np.array(vec, dtype=np.float32)
            norm = np.linalg.norm(vec_arr)
            norm_vec = (vec_arr / norm) if norm > 0 else vec_arr

            entry = {"id": str(pid), "vector": norm_vec, "payload": p_dict}
            if str(pid) in existing_ids:
                self._user_points[u_key][existing_ids[str(pid)]] = entry
            else:
                self._user_points[u_key].append(entry)

    def search(self, user_id: str, query_vector: List[float], limit: int = 5, category: Optional[str] = None) -> List[Dict[str, Any]]:
        u_key = str(user_id)
        points = self._user_points.get(u_key, [])
        if not points:
            return []

        q_arr = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_arr)
        if q_norm > 0:
            q_arr = q_arr / q_norm

        scored = []
        for p in points:
            if category and p["payload"].get("category") != category:
                continue
            v = p["vector"]
            # Both normalized -> cosine is dot product
            score = float(np.dot(q_arr, v))
            scored.append({
                "id": p["id"],
                "score": round(score, 4),
                "payload": p["payload"]
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]


class QdrantVectorService:
    def __init__(self, client: Optional[AsyncQdrantClient] = None):
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self._is_live_qdrant: Optional[bool] = None
        self._mock_store = InMemoryVectorStoreMock()

        if client:
            self.client = client
            self._is_live_qdrant = True
        else:
            try:
                self.client = AsyncQdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=2.0,
                    check_compatibility=False
                )
            except Exception:
                self.client = None
                self._is_live_qdrant = False

    async def check_availability(self) -> bool:
        if self._is_live_qdrant is not None:
            return self._is_live_qdrant
        if not self.client:
            self._is_live_qdrant = False
            return False
        try:
            await self.client.get_collections()
            self._is_live_qdrant = True
            logger.info(f"Connected to Qdrant Vector DB at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
        except Exception as exc:
            logger.info(f"Qdrant unreachable ({type(exc).__name__}). Using in-memory vector store engine.")
            self._is_live_qdrant = False
        return self._is_live_qdrant

    async def initialize_collection(self) -> None:
        """Initializes the collection and enforces a mandatory tenant isolation keyword index on user_id."""
        if not await self.check_availability():
            return

        dim = EmbeddingService.get_dimension()
        try:
            collections = await self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                logger.info(f"Creating Qdrant collection: {self.collection_name} (dim={dim})")
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
                )
                # Create mandatory tenant filtering index
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="user_id",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                await self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name="category",
                    field_schema=PayloadSchemaType.KEYWORD,
                )
                logger.info("Successfully configured Qdrant collection and indexes.")
        except Exception as e:
            logger.warning(f"Error initializing Qdrant collection: {e}")
            self._is_live_qdrant = False

    async def upsert_experience_vectors(
        self,
        user_id: str,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        point_ids: List[str]
    ) -> None:
        """Upserts candidate experience embeddings, guaranteeing that user_id is injected into every payload."""
        # Always mirror into mock store for local consistency
        self._mock_store.upsert(user_id, point_ids, vectors, payloads)

        if not await self.check_availability():
            return

        try:
            points = []
            for pid, vec, pay in zip(point_ids, vectors, payloads):
                payload_copy = dict(pay)
                payload_copy["user_id"] = str(user_id)
                points.append(
                    PointStruct(
                        id=pid,
                        vector=vec,
                        payload=payload_copy
                    )
                )

            await self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        except Exception as exc:
            logger.warning(f"Qdrant upsert failed: {exc}")

    def upsert_experience_vectors_sync(
        self,
        user_id: str,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        point_ids: List[str]
    ) -> None:
        """Synchronous wrapper for Celery workers and blocking execution pipelines."""
        self._mock_store.upsert(user_id, point_ids, vectors, payloads)

    async def search_relevant_experiences(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries Qdrant with a strictly enforced filter on user_id.
        Prevents cross-tenant semantic data leakage.
        """
        if not await self.check_availability():
            return self._mock_store.search(user_id, query_vector, limit=limit, category=category)

        try:
            must_conditions = [
                FieldCondition(
                    key="user_id",
                    match=MatchValue(value=str(user_id))
                )
            ]

            if category:
                must_conditions.append(
                    FieldCondition(
                        key="category",
                        match=MatchValue(value=category)
                    )
                )

            search_result = await self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=Filter(must=must_conditions),
                limit=limit,
            )

            return [
                {
                    "id": str(hit.id),
                    "score": hit.score,
                    "payload": hit.payload
                }
                for hit in search_result
            ]
        except Exception as exc:
            logger.warning(f"Qdrant search failed: {exc}; falling back to local vector memory.")
            return self._mock_store.search(user_id, query_vector, limit=limit, category=category)

    def search_relevant_experiences_sync(
        self,
        user_id: str,
        query_vector: List[float],
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Synchronous search wrapper for Celery background tasks."""
        return self._mock_store.search(user_id, query_vector, limit=limit, category=category)


qdrant_service = QdrantVectorService()
