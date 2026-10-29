import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.services.outreach_service import OutreachService, OutreachComplianceError


class TestOutreachEngine(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_domain_normalization(self):
        d1 = OutreachService.normalize_company_domain("Stripe")
        self.assertEqual(d1, "stripe.com")

        d2 = OutreachService.normalize_company_domain("Google Cloud", "cloud.google.com")
        self.assertEqual(d2, "cloud.google.com")

        d3 = OutreachService.normalize_company_domain("Airbnb, Inc.")
        self.assertEqual(d3, "airbnbinc.com")

    def test_recruiter_discovery(self):
        domain, recruiters = OutreachService.discover_recruiters(
            company_name="Netflix",
            domain="netflix.com",
            role_title="Senior Platform Engineer",
            department="Cloud Infrastructure"
        )
        self.assertEqual(domain, "netflix.com")
        self.assertGreaterEqual(len(recruiters), 2)
        for r in recruiters:
            self.assertIn("@netflix.com", r.email)
            self.assertGreaterEqual(r.confidence_score, 80.0)
            self.assertEqual(r.verification_status, "valid")

    def test_deliverability_verification_no_port_25(self):
        # Valid corporate email
        v1 = OutreachService.verify_email_deliverability("sarah.chen@stripe.com")
        self.assertTrue(v1.is_deliverable)
        self.assertFalse(v1.smtp_check_performed, "Raw port 25 SMTP handshakes must never be executed")
        self.assertGreaterEqual(v1.confidence_score, 80.0)

        # Disposable email
        v2 = OutreachService.verify_email_deliverability("test@mailinator.com")
        self.assertFalse(v2.is_deliverable)
        self.assertEqual(v2.status, "invalid")

        # Invalid syntax
        v3 = OutreachService.verify_email_deliverability("not-an-email")
        self.assertFalse(v3.is_deliverable)
        self.assertEqual(v3.confidence_score, 0.0)

    def test_compliance_synthesis_can_spam_and_gdpr(self):
        response = OutreachService.synthesize_outreach_email(
            candidate_name="Alex Mercer",
            candidate_role="Senior Distributed Systems Engineer",
            candidate_summary="7+ years architecting high-throughput event-driven microservices in Go, Rust, and Python.",
            recruiter_name="Sarah Chen",
            recruiter_email="sarah.chen@stripe.com",
            recruiter_title="Head of Technical Recruiting",
            company_name="Stripe",
            target_job_title="Senior Infrastructure Engineer",
            mode="copilot",
            user_id="test_candidate_42"
        )

        draft = response.draft
        # 1. Word count constraint (< 120 words)
        self.assertLess(draft.word_count, 120)

        # 2. CAN-SPAM physical address present
        self.assertIn("100 Montgomery St", draft.body_text)
        self.assertIn(draft.physical_address, draft.body_text)

        # 3. 1-click opt-out / unsubscribe link present
        self.assertIn("https://rolesync.ai/opt-out?token=", draft.body_text)
        self.assertTrue(draft.is_compliant)
        self.assertEqual(len(draft.validation_errors), 0)

    def test_autopilot_daily_limit_enforcement(self):
        user_id = "test_autopilot_limit_user"
        # Reset counter for test user
        import time
        today = time.strftime("%Y-%m-%d")
        if today not in OutreachService._daily_send_counts:
            OutreachService._daily_send_counts[today] = {}
        OutreachService._daily_send_counts[today][user_id] = 14


        # 15th email should succeed
        resp = OutreachService.synthesize_outreach_email(
            candidate_name="Alex Mercer",
            candidate_role="Senior Platform Engineer",
            candidate_summary="Expert in Kubernetes and cloud reliability.",
            recruiter_name="Sarah Chen",
            recruiter_email="sarah.chen@stripe.com",
            recruiter_title="Head of Recruiting",
            company_name="Stripe",
            target_job_title="Staff SRE",
            mode="autopilot",
            user_id=user_id
        )
        self.assertEqual(resp.daily_quota_remaining, 0)

        # 16th email in autopilot mode should be rejected to protect domain reputation
        with self.assertRaises(OutreachComplianceError) as ctx:
            OutreachService.synthesize_outreach_email(
                candidate_name="Alex Mercer",
                candidate_role="Senior Platform Engineer",
                candidate_summary="Expert in Kubernetes and cloud reliability.",
                recruiter_name="Sarah Chen",
                recruiter_email="sarah.chen@stripe.com",
                recruiter_title="Head of Recruiting",
                company_name="Stripe",
                target_job_title="Staff SRE",
                mode="autopilot",
                user_id=user_id
            )
        self.assertIn("Daily autopilot outreach limit of 15 emails reached", str(ctx.exception))

    def test_deliverability_failure_blocks_outreach(self):
        with self.assertRaises(OutreachComplianceError) as ctx:
            OutreachService.synthesize_outreach_email(
                candidate_name="Alex Mercer",
                candidate_role="Senior Engineer",
                candidate_summary="Python and Go specialist.",
                recruiter_name="Bad Recruiter",
                recruiter_email="invalid_address@throwaway.com",
                recruiter_title="Recruiter",
                company_name="Acme",
                target_job_title="Engineer",
                mode="copilot"
            )
        self.assertIn("deliverability failed", str(ctx.exception))

    def test_outreach_api_endpoints(self):
        # 1. Discover
        disc_resp = self.client.post(
            "/api/v1/outreach/discover",
            json={
                "company_name": "Datadog",
                "domain": "datadoghq.com",
                "role_title": "Site Reliability Engineer"
            }
        )
        self.assertEqual(disc_resp.status_code, 200)
        disc_data = disc_resp.json()
        self.assertEqual(disc_data["domain"], "datadoghq.com")
        self.assertGreaterEqual(len(disc_data["recruiters"]), 1)

        # 2. Verify
        ver_resp = self.client.post(
            "/api/v1/outreach/verify",
            json={"email": "recruiter@datadoghq.com"}
        )
        self.assertEqual(ver_resp.status_code, 200)
        ver_data = ver_resp.json()
        self.assertTrue(ver_data["is_deliverable"])
        self.assertFalse(ver_data["smtp_check_performed"])

        # 3. Synthesize
        synth_resp = self.client.post(
            "/api/v1/outreach/synthesize",
            json={
                "candidate_name": "Alex Mercer",
                "candidate_role": "Backend Architect",
                "candidate_summary": "Architected low-latency distributed databases.",
                "recruiter_name": "Alex Vargas",
                "recruiter_email": "alex.vargas@datadoghq.com",
                "recruiter_title": "Engineering Manager",
                "company_name": "Datadog",
                "target_job_title": "Staff Backend Engineer",
                "mode": "copilot"
            }
        )
        self.assertEqual(synth_resp.status_code, 200)
        synth_data = synth_resp.json()
        self.assertEqual(synth_data["mode"], "copilot")
        self.assertTrue(synth_data["draft"]["is_compliant"])
        self.assertLess(synth_data["draft"]["word_count"], 120)


if __name__ == "__main__":
    unittest.main()
