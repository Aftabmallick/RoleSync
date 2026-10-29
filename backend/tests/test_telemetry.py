import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.endpoints.telemetry import sanitize_structural_metadata, drift_event_log


class TestTelemetryAndErrors(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_selector_failure_telemetry_reporting(self):
        initial_count = len(drift_event_log)
        payload = {
            "host": "boards.greenhouse.io",
            "ats_provider": "GREENHOUSE",
            "failed_selectors": [".app-title", "#content .job-post"],
            "page_structure_summary": {
                "totalElements": 154,
                "tagCounts": {"div": 45, "span": 30, "button": 4},
                "maxDepth": 8,
                "hasForm": True,
                "buttonCount": 4,
                "inputCount": 6,
            },
            "client_version": "2.0.0-mv3",
            "timestamp": 1730000000.0,
        }

        resp = self.client.post("/api/v1/telemetry/selector-failure", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "RECORDED")
        self.assertIn("drift_", data["report_id"])
        self.assertEqual(len(drift_event_log), initial_count + 1)

    def test_telemetry_metadata_pii_sanitization(self):
        dirty_metadata = {
            "element_title": "Job application for Alex Mercer",
            "contact_support": "reach out to recruiter@megacorp.com for inquiries",
            "support_phone": "Call 415-555-0199 for help",
            "nested": {
                "user_email": "candidate@example.org",
                "safe_tag": "div.container-fluid",
            },
            "safe_counter": 42,
        }

        cleaned = sanitize_structural_metadata(dirty_metadata)
        # Verify emails and phones are stripped
        self.assertEqual(cleaned["contact_support"], "[REDACTED_PII]")
        self.assertEqual(cleaned["support_phone"], "[REDACTED_PII]")
        self.assertEqual(cleaned["nested"]["user_email"], "[REDACTED_PII]")
        self.assertEqual(cleaned["nested"]["safe_tag"], "div.container-fluid")
        self.assertEqual(cleaned["safe_counter"], 42)

    def test_rfc7807_validation_error_format(self):
        # Sending invalid payload to trigger 422
        resp = self.client.post(
            "/api/v1/telemetry/selector-failure",
            json={"host": "incomplete_payload"}  # missing ats_provider, failed_selectors, etc.
        )
        self.assertEqual(resp.status_code, 422)
        self.assertEqual(resp.headers.get("content-type"), "application/problem+json")

        data = resp.json()
        # Verify RFC 7807 fields
        self.assertIn("type", data)
        self.assertEqual(data["type"], "https://rolesync.ai/errors/validation-error")
        self.assertEqual(data["title"], "Unprocessable Request Payload")
        self.assertEqual(data["status"], 422)
        self.assertIn("instance", data)
        self.assertIn("invalid_params", data)
        self.assertIsInstance(data["invalid_params"], list)
        self.assertGreater(len(data["invalid_params"]), 0)


if __name__ == "__main__":
    unittest.main()

