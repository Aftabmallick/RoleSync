import unittest
from app.tasks.tailor_tasks import celery_app
from app.services.guardrails import (
    ONNXNLIEngine,
    RobustGuardrailVerifier,
    TailoredResumeDraft,
    TailoredExperienceEntry,
    TailoredBulletPoint,
    GuardrailViolationException
)


class TestCeleryAndONNX(unittest.TestCase):
    def test_celery_app_configuration(self):
        # Verify Celery app exists, has correct name and task registration
        self.assertEqual(celery_app.main, "rolesync")
        self.assertIn("rolesync.tailor_pipeline", celery_app.tasks)
        self.assertEqual(celery_app.conf.timezone, "UTC")
        self.assertTrue(celery_app.conf.enable_utc)

    def test_onnx_nli_engine_fallback_and_inference(self):
        engine = ONNXNLIEngine()
        # Fallback predict_nli: when weights are missing or session uninitialized,
        # verify strict deterministic fail-safe invariant: P(contradiction) = 1.0, P(entailment) = 0.0
        scores = engine.predict_nli(
            premise="Architected distributed APIs with FastAPI.",
            hypothesis="Built scalable backend services using FastAPI."
        )
        self.assertIn("entailment", scores)
        self.assertIn("contradiction", scores)
        self.assertEqual(scores["contradiction"], 1.0)
        self.assertEqual(scores["entailment"], 0.0)
        self.assertEqual(scores.get("neutral", 0.0), 0.0)

        # Identity entailment invariant: identical strings entail with P(entailment) = 1.0
        id_scores = engine.predict_nli(
            premise="Architected distributed APIs with FastAPI.",
            hypothesis="Architected distributed APIs with FastAPI."
        )
        self.assertEqual(id_scores["entailment"], 1.0)
        self.assertEqual(id_scores["contradiction"], 0.0)
        self.assertEqual(id_scores.get("neutral", 0.0), 0.0)


    def test_robust_guardrails_with_onnx_engine(self):
        master_profile = {
            "personal": {"full_name": "Dev Candidate"},
            "skills": [{"name": "Python"}, {"name": "FastAPI"}],
            "experience": [
                {
                    "company": "Tech Corp",
                    "role": "Engineer",
                    "bullets": [
                        {"id": "b1", "text": "Built data pipelines in Python and FastAPI."}
                    ]
                }
            ]
        }
        verifier = RobustGuardrailVerifier(master_profile, nli_client=ONNXNLIEngine())
        draft = TailoredResumeDraft(
            skills=["Python", "FastAPI"],
            summary="Experienced software engineer.",
            experience=[
                TailoredExperienceEntry(
                    company="Tech Corp",
                    role="Engineer",
                    dates="2021-Present",
                    bullet_points=[
                        TailoredBulletPoint(
                            original_bullet_id="b1",
                            tailored_text="Built data pipelines in Python and FastAPI."
                        )
                    ]
                )
            ]
        )
        # Must pass all 4 layers
        verifier.execute_all_layers(draft)

    def test_failsafe_blocks_unentailed_bullet_without_model(self):
        master_profile = {
            "personal": {"full_name": "Dev Candidate"},
            "skills": [{"name": "Python"}, {"name": "FastAPI"}],
            "experience": [
                {
                    "company": "Tech Corp",
                    "role": "Engineer",
                    "bullets": [
                        {"id": "b1", "text": "Built data pipelines in Python and FastAPI."}
                    ]
                }
            ]
        }
        verifier = RobustGuardrailVerifier(master_profile, nli_client=ONNXNLIEngine())
        draft = TailoredResumeDraft(
            skills=["Python", "FastAPI"],
            summary="Experienced software engineer.",
            experience=[
                TailoredExperienceEntry(
                    company="Tech Corp",
                    role="Engineer",
                    dates="2021-Present",
                    bullet_points=[
                        TailoredBulletPoint(
                            original_bullet_id="b1",
                            tailored_text="Engineered distributed real-time pipelines using Python and FastAPI."
                        )
                    ]
                )
            ]
        )
        with self.assertRaises(GuardrailViolationException) as ctx:
            verifier.execute_all_layers(draft)
        self.assertEqual(ctx.exception.layer, "LAYER_3_NLI")
        self.assertEqual(ctx.exception.details.get("contradiction_score"), 1.0)

    def test_verify_bullet_factuality_interface_contract(self):
        engine = ONNXNLIEngine()
        # Identity entailment contract
        res_ident = engine.verify_bullet_factuality("Deployed K8s clusters.", "Deployed K8s clusters.")
        self.assertEqual(res_ident["entailment"], 1.0)
        self.assertEqual(res_ident["contradiction"], 0.0)

        # Fail-safe fallback contract
        res_diff = engine.verify_bullet_factuality("Deployed K8s clusters.", "Never managed K8s clusters.")
        self.assertEqual(res_diff["contradiction"], 1.0)
        self.assertEqual(res_diff["entailment"], 0.0)


if __name__ == "__main__":
    unittest.main()


