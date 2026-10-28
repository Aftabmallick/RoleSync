import logging
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
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

logger = logging.getLogger(__name__)


class QdrantVectorService:
    def __init__(self, client: Optional[AsyncQdrantClient] = None):
        if client:
            self.client = client
        else:
            self.client = AsyncQdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                api_key=settings.QDRANT_API_KEY,
            )
        self.collection_name = settings.QDRANT_COLLECTION_NAME

    async def initialize_collection(self) -> None:
        """Initializes the collection and enforces a mandatory tenant isolation keyword index on user_id."""
        try:
            collections = await self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name not in collection_names:
                logger.info(f"Creating Qdrant collection: {self.collection_name}")
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=3072, distance=Distance.COSINE),
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
            logger.error(f"Error initializing Qdrant collection: {e}")
            raise

    async def upsert_experience_vectors(
        self,
        user_id: str,
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
        point_ids: List[str]
    ) -> None:
        """Upserts candidate experience embeddings, guaranteeing that user_id is injected into every payload."""
        points = []
        for pid, vec, pay in zip(point_ids, vectors, payloads):
            # Invariant: user_id must be in payload for tenant filtering
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
