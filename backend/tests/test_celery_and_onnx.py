import unittest
from app.tasks.tailor_tasks import celery_app, run_tailoring_pipeline_task
from app.services.guardrails import (
    ONNXNLIEngine,
    RobustGuardrailVerifier,
    TailoredResumeDraft,
    TailoredExperienceEntry,
    TailoredBulletPoint
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
        # Fallback predict_nli
        scores = engine.predict_nli(
            premise="Architected distributed APIs with FastAPI.",
            hypothesis="Built scalable backend services using FastAPI."
        )
        self.assertIn("entailment", scores)
        self.assertIn("contradiction", scores)
        self.assertGreaterEqual(scores["entailment"], 0.88)
        self.assertLessEqual(scores["contradiction"], 0.15)

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


if __name__ == "__main__":
    unittest.main()

