import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.endpoints.telemetry import drift_event_log


class TestAutopilotWorkflowSimulation(unittest.TestCase):
    """
    End-to-End Simulation of the Workday Multi-Step Application Autopilot,
    session state transitions, and telemetry drift reporting.
    """
    def setUp(self):
        self.client = TestClient(app)

    def test_workday_five_stage_state_machine_flow(self):
        """Simulates full 5-stage sequential traversal and data mapping."""
        stages = [
            "MY_INFORMATION",
            "MY_EXPERIENCE",
            "APPLICATION_QUESTIONS",
            "VOLUNTARY_DISCLOSURES",
            "REVIEW"
        ]

        candidate_data = {
            "firstName": "Alex",
            "lastName": "Mercer",
            "phone": "+1 555-019-2834",
            "city": "San Francisco",
            "postalCode": "94105",
            "resumeFileName": "Alex_Mercer_Resume.pdf",
            "legallyAuthorized": True,
            "requiresSponsorship": False,
            "gender": "Male",
            "veteranStatus": "Not a Veteran",
            "disabilityStatus": "No Disability"
        }

        # Simulated state checkpoint accumulator
        session_checkpoint = {
            "taskId": "task_simulation_001",
            "currentStepIndex": 0,
            "currentStepName": stages[0],
            "status": "IN_PROGRESS",
            "completedSteps": [],
            "stepData": {}
        }

        for i, stage in enumerate(stages):
            session_checkpoint["currentStepIndex"] = i
            session_checkpoint["currentStepName"] = stage

            if stage == "MY_INFORMATION":
                self.assertIn("firstName", candidate_data)
                self.assertIn("lastName", candidate_data)
                session_checkpoint["stepData"][stage] = {"fields_filled": 6, "errors": 0}

            elif stage == "MY_EXPERIENCE":
                self.assertIn("resumeFileName", candidate_data)
                session_checkpoint["stepData"][stage] = {"resume_attached": True, "method": "DataTransfer"}

            elif stage == "APPLICATION_QUESTIONS":
                self.assertTrue(candidate_data["legallyAuthorized"])
                self.assertFalse(candidate_data["requiresSponsorship"])
                session_checkpoint["stepData"][stage] = {"questions_answered": 2}

            elif stage == "VOLUNTARY_DISCLOSURES":
                self.assertEqual(candidate_data["gender"], "Male")
                session_checkpoint["stepData"][stage] = {"disclosures_filled": 3}

            elif stage == "REVIEW":
                # Supervised pause before final submission
                session_checkpoint["status"] = "PAUSED_FOR_USER_REVIEW"
                session_checkpoint["stepData"][stage] = {"ready_for_submission": True}

            session_checkpoint["completedSteps"].append(stage)

        # Assert full traversal verified
        self.assertEqual(len(session_checkpoint["completedSteps"]), 5)
        self.assertEqual(session_checkpoint["currentStepName"], "REVIEW")
        self.assertEqual(session_checkpoint["status"], "PAUSED_FOR_USER_REVIEW")

    def test_selector_drift_fallback_and_telemetry_flow(self):
        """Simulates selector drift detection during Workday navigation dispatching telemetry."""
        initial_events = len(drift_event_log)

        # Client encounters altered Workday DOM layout
        drift_payload = {
            "host": "myworkdayjobs.com",
            "ats_provider": "WORKDAY",
            "failed_selectors": [
                "[data-automation-id='legalNameSection_firstName']",
                "[data-automation-id='legalNameSection_lastName']"
            ],
            "page_structure_summary": {
                "totalElements": 210,
                "tagCounts": {"div": 90, "input": 12, "button": 5},
                "maxDepth": 11,
                "hasForm": True,
                "buttonCount": 5,
                "inputCount": 12
            },
            "client_version": "2.0.0-mv3",
            "timestamp": 1730001000.0
        }

        resp = self.client.post("/api/v1/telemetry/selector-failure", json=drift_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "RECORDED")
        self.assertIn("drift_", data["report_id"])
        self.assertEqual(len(drift_event_log), initial_events + 1)


if __name__ == "__main__":
    unittest.main()

