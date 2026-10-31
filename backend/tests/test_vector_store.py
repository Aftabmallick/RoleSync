import unittest
import asyncio
import uuid
from app.services.vector_store import QdrantVectorService, InMemoryVectorStoreMock
from app.services.embedding_service import EmbeddingService


class TestVectorStoreTenantIsolation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.vector_service = QdrantVectorService()
        await self.vector_service.initialize_collection()

    async def test_tenant_isolation_cross_user_leakage_defense(self):
        user_alice = str(uuid.uuid4())
        user_bob = str(uuid.uuid4())

        # Alice's experience
        alice_text = "Architected distributed PostgreSQL database with 10M rows"
        alice_vec = EmbeddingService.embed_text(alice_text).tolist()
        await self.vector_service.upsert_experience_vectors(
            user_id=user_alice,
            vectors=[alice_vec],
            payloads=[{"bullet_id": "b_alice_1", "text": alice_text, "category": "experience"}],
            point_ids=["pt_alice_1"]
        )

        # Bob's experience
        bob_text = "Built iOS Swift mobile application with SwiftUI"
        bob_vec = EmbeddingService.embed_text(bob_text).tolist()
        await self.vector_service.upsert_experience_vectors(
            user_id=user_bob,
            vectors=[bob_vec],
            payloads=[{"bullet_id": "b_bob_1", "text": bob_text, "category": "experience"}],
            point_ids=["pt_bob_1"]
        )

        # Query using a PostgreSQL-related query
        query_vec = EmbeddingService.embed_text("Looking for PostgreSQL database experience").tolist()

        # Alice's search must find Alice's bullet
        alice_results = await self.vector_service.search_relevant_experiences(
            user_id=user_alice,
            query_vector=query_vec,
            limit=5
        )
        self.assertGreaterEqual(len(alice_results), 1)
        self.assertEqual(alice_results[0]["payload"]["bullet_id"], "b_alice_1")
        self.assertEqual(alice_results[0]["payload"]["user_id"], user_alice)

        # Bob's search with the same query must NOT return Alice's bullet
        bob_results = await self.vector_service.search_relevant_experiences(
            user_id=user_bob,
            query_vector=query_vec,
            limit=5
        )
        for hit in bob_results:
            self.assertNotEqual(hit["payload"].get("user_id"), user_alice)
            self.assertNotEqual(hit["payload"].get("bullet_id"), "b_alice_1")

    async def test_synchronous_wrapper_in_celery(self):
        user_id = str(uuid.uuid4())
        text = "Led Kubernetes orchestration across 5 clusters"
        vec = EmbeddingService.embed_text(text).tolist()

        self.vector_service.upsert_experience_vectors_sync(
            user_id=user_id,
            vectors=[vec],
            payloads=[{"bullet_id": "b_k8s_1", "text": text, "category": "experience"}],
            point_ids=["pt_k8s_1"]
        )

        results = self.vector_service.search_relevant_experiences_sync(
            user_id=user_id,
            query_vector=vec,
            limit=3
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["payload"]["bullet_id"], "b_k8s_1")


if __name__ == "__main__":
    unittest.main()

