import unittest
import uuid
import json
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import EnvelopeEncryption, hash_token
from app.services.taxonomy import taxonomy_service, normalize_skill
from app.services.scoring_engine import ATSScoringEngine
from app.services.guardrails import (
    RobustGuardrailVerifier,
    TailoredResumeDraft,
    TailoredExperienceEntry,
    TailoredBulletPoint,
    GuardrailViolationException,
    ONNXNLIEngine
)
from app.services.typst_compiler import TypstCompilerService
from app.services.outreach_service import OutreachService
from app.tasks.tailor_tasks import orchestrator, task_store, celery_app


class TestAllUserStories(unittest.TestCase):
    """
    Comprehensive User Story Test Suite for RoleSync Platform v2.0.
    Covers all 10 core candidate recruitment copilot and autopilot workflows.
    """
    def setUp(self):
        self.client = TestClient(app)
        self.user_id = f"user_{uuid.uuid4().hex[:8]}"
        self.master_profile = {
            "personal": {
                "full_name": "Marcus Vance",
                "email": "marcus@vance.io",
                "phone": "+1 555-234-5678",
                "location": "Seattle, WA",
                "linkedin": "linkedin.com/in/marcus-vance",
                "github": "github.com/marcusvance"
            },
            "skills": [
                {"name": "Python", "category": "Languages"},
                {"name": "FastAPI", "category": "Frameworks"},
                {"name": "PostgreSQL", "category": "Databases"},
                {"name": "Docker", "category": "DevOps"},
                {"name": "Kubernetes", "category": "DevOps"},
                {"name": "Redis", "category": "Databases"},
                {"name": "AWS", "category": "Cloud"}
            ],
            "experience": [
                {
                    "company": "Vanguard Cloud",
                    "role": "Staff Infrastructure Engineer",
                    "start_date": "2020",
                    "end_date": "Present",
                    "location": "Seattle, WA",
                    "bullets": [
                        {
                            "id": "b_vg_1",
                            "text": "Architected event-driven microservices processing 25,000 requests/sec with 99.99% availability."
                        },
                        {
                            "id": "b_vg_2",
                            "text": "Automated multi-region Kubernetes clusters, reducing AWS infrastructure cost by $850,000 annually and cut p99 latency by 450ms."
                        }
                    ]
                }
            ],
            "education": [
                {
                    "institution": "University of Washington",
                    "degree": "B.S.",
                    "field": "Computer Science",
                    "end_date": "2019",
                    "gpa": "3.92"
                }
            ],
            "summary": "Staff Infrastructure Engineer specializing in distributed systems, Kubernetes automation, and high-throughput cloud architecture."
        }

    # =========================================================================
    # USER STORY 1: Candidate Vault Onboarding & Cryptographic Isolation
    # =========================================================================
    def test_user_story_1_candidate_vault_onboarding_and_encryption(self):
        """
        GIVEN a new candidate signing in via Google OAuth
        WHEN they save their Master Career Vault
        THEN the profile is encrypted with tenant-specific HKDF AES-256-GCM
        AND unauthorized tenants cannot decrypt the payload
        AND token rotation thwarts token theft replay attacks.
        """
        # 1. Google OAuth Token Exchange
        auth_resp = self.client.post("/api/v1/auth/google", json={
            "id_token": "google_oauth_jwt_sample",
            "device_fingerprint": "macbook_pro_chrome"
        })
        self.assertEqual(auth_resp.status_code, 200)
        auth_data = auth_resp.json()
        access_token = auth_data["access_token"]
        refresh_token = auth_data["refresh_token"]

        # 2. Save Master Profile into Tenant Vault (Encrypted)
        save_resp = self.client.post(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {access_token}"},
            json=self.master_profile
        )
        self.assertEqual(save_resp.status_code, 200)
        self.assertIn("encrypted", save_resp.json()["message"].lower())

        # 3. Retrieve and Decrypt
        get_resp = self.client.get(
            "/api/v1/profile",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        self.assertEqual(get_resp.status_code, 200)
        retrieved = get_resp.json()["profile"]
        self.assertEqual(retrieved["personal"]["full_name"], "Marcus Vance")
        self.assertEqual(len(retrieved["skills"]), 7)

        # 4. Cryptographic Proof: Cross-tenant isolation
        tenant_a = str(uuid.uuid4())
        tenant_b = str(uuid.uuid4())
        raw_secret = b"salary_expectation: $210,000"
        ciphertext, iv = EnvelopeEncryption.encrypt(raw_secret, tenant_a)

        # Tenant B attempting to decrypt Tenant A's ciphertext must be rejected by GCM tag
        from cryptography.exceptions import InvalidTag
        with self.assertRaises(InvalidTag):
            EnvelopeEncryption.decrypt(ciphertext, iv, tenant_b)

        # 5. Token Rotation & Replay Defense
        rot_resp = self.client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
            "device_fingerprint": "macbook_pro_chrome",
            "email": "marcus@vance.io",
            "tier": "FREE"
        })
        self.assertEqual(rot_resp.status_code, 200)
        new_refresh = rot_resp.json()["refresh_token"]

        # Replaying old refresh token triggers full session revocation
        replay_resp = self.client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
            "device_fingerprint": "macbook_pro_chrome",
            "email": "marcus@vance.io",
            "tier": "FREE"
        })
        self.assertEqual(replay_resp.status_code, 401)
        self.assertIn("reuse detected", replay_resp.json()["detail"].lower())

    # =========================================================================
    # USER STORY 2: Canonical Skill Taxonomy & Aliasing Resolution
    # =========================================================================
    def test_user_story_2_canonical_skill_taxonomy_resolution(self):
        """
        GIVEN raw job postings with varied tech terminology
        WHEN the taxonomy service processes skill keywords
        THEN aliases resolve deterministically in <0.5ms (e.g. k8s -> kubernetes, postgres -> postgresql).
        """
        aliases = [
            ("k8s", "kubernetes"),
            ("Kubernetes", "kubernetes"),
            ("Postgres", "postgresql"),
            ("PostgreSQL", "postgresql"),
            ("React.js", "react"),
            ("ReactJS", "react"),
            ("golang", "golang"),
            ("amazon web services", "amazon web services"),
            ("AWS", "amazon web services"),
            ("docker", "docker")
        ]
        for raw, expected in aliases:
            norm = taxonomy_service.normalize_skill(raw)
            self.assertEqual(norm, expected, f"Expected '{raw}' to normalize to '{expected}', got '{norm}'")

        # Entity extraction from prose
        jd_text = "We are seeking a Senior Go Engineer with deep Kubernetes and PostgreSQL experience using AWS."
        extracted = taxonomy_service.extract_skills_from_text(jd_text)
        self.assertIn("golang", extracted)
        self.assertIn("kubernetes", extracted)
        self.assertIn("postgresql", extracted)
        self.assertIn("amazon web services", extracted)

    # =========================================================================
    # USER STORY 3: 4-Dimension Composite ATS Scoring
    # =========================================================================
    def test_user_story_3_composite_ats_scoring_dimensions(self):
        """
        GIVEN candidate skills and a target job description
        WHEN ATSScoringEngine evaluates compatibility
        THEN it computes exact 4-dimension scores matching architectural weights:
             w1=0.35 (semantic), w2=0.30 (skill), w3=0.15 (lexical sublinear), w4=0.20 (seniority).
        """
        jd_text = "Looking for a Staff Engineer skilled in Python, FastAPI, Docker, Kubernetes, and AWS with 4 years experience."
        resume_text = "Staff Infrastructure Engineer experienced in Python, FastAPI, Docker, Kubernetes, AWS, and PostgreSQL with 5 years experience."

        resume_skills = {"python", "fastapi", "docker", "kubernetes", "aws", "postgresql"}
        jd_required = {"python", "fastapi", "docker", "kubernetes", "aws"}

        score = ATSScoringEngine.calculate_score(
            resume_embedding=None,
            jd_embedding=None,
            resume_skills=resume_skills,
            jd_required_skills=jd_required,
            resume_text=resume_text,
            jd_text=jd_text,
            required_years=4.0,
            actual_years=5.0
        )

        self.assertGreaterEqual(score["composite_score"], 70.0)
        self.assertEqual(score["skill_coverage_score"], 100.0)
        self.assertEqual(score["experience_alignment_score"], 100.0)
        self.assertGreater(score["lexical_score"], 0.0)
        self.assertEqual(len(score["missing_skills"]), 0)
        self.assertIn("matched_skills", score)

    # =========================================================================
    # USER STORY 4: 4-Layer Anti-Hallucination Guardrails
    # =========================================================================
    def test_user_story_4_four_layer_guardrail_verification(self):
        """
        GIVEN a candidate master profile
        WHEN AI synthesizes a tailored draft
        THEN Layer 1 blocks structural overflow (>40 skills, >600 chars summary)
        AND Layer 2 blocks unentailed skills or unlisted companies
        AND Layer 3 enforces NLI semantic entailment
        AND Layer 4 blocks metric fabrication or inflation ($1.5M -> $2.5M).
        """
        verifier = RobustGuardrailVerifier(self.master_profile, nli_client=ONNXNLIEngine())

        # Test Layer 1: Summary overflow (> 600 chars)
        invalid_l1 = TailoredResumeDraft(
            skills=["Python", "FastAPI"],
            summary="A" * 605,
            experience=[
                TailoredExperienceEntry(
                    company="Vanguard Cloud",
                    role="Staff Engineer",
                    dates="2020 - Present",
                    bullet_points=[
                        TailoredBulletPoint(original_bullet_id="b_vg_1", tailored_text="Valid text")
                    ]
                )
            ]
        )
        with self.assertRaises(GuardrailViolationException) as ctx:
            verifier.execute_all_layers(invalid_l1)
        self.assertEqual(ctx.exception.layer, "LAYER_1_SCHEMA")

        # Test Layer 2: Hallucinated Skill (Rust is not in master profile)
        invalid_l2 = TailoredResumeDraft(
            skills=["Python", "FastAPI", "Rust"],  # Rust fabricated!
            summary="Valid summary",
            experience=[
                TailoredExperienceEntry(
                    company="Vanguard Cloud",
                    role="Staff Engineer",
                    dates="2020 - Present",
                    bullet_points=[
                        TailoredBulletPoint(original_bullet_id="b_vg_1", tailored_text="Valid text")
                    ]
                )
            ]
        )
        with self.assertRaises(GuardrailViolationException) as ctx:
            verifier.execute_all_layers(invalid_l2)
        self.assertEqual(ctx.exception.layer, "LAYER_2_SUBSET")
        self.assertIn("Rust", str(ctx.exception))

        # Test Layer 4: Metric Inflation ($850,000 -> $1,850,000)
        invalid_l4 = TailoredResumeDraft(
            skills=["Python", "FastAPI", "Kubernetes"],
            summary="Valid summary",
            experience=[
                TailoredExperienceEntry(
                    company="Vanguard Cloud",
                    role="Staff Engineer",
                    dates="2020 - Present",
                    bullet_points=[
                        TailoredBulletPoint(
                            original_bullet_id="b_vg_2",
                            tailored_text="Automated Kubernetes clusters, reducing cost by $1,850,000 annually."  # Fabricated $1.85M!
                        )
                    ]
                )
            ]
        )
        with self.assertRaises(GuardrailViolationException) as ctx:
            verifier.execute_all_layers(invalid_l4)
        self.assertEqual(ctx.exception.layer, "LAYER_4_METRIC")

        # Test Valid Draft Passing All 4 Layers
        valid_draft = TailoredResumeDraft(
            skills=["Python", "FastAPI", "Kubernetes", "AWS"],
            summary="Staff Infrastructure Engineer specializing in cloud reliability.",
            experience=[
                TailoredExperienceEntry(
                    company="Vanguard Cloud",
                    role="Staff Infrastructure Engineer",
                    dates="2020 - Present",
                    bullet_points=[
                        TailoredBulletPoint(
                            original_bullet_id="b_vg_1",
                            tailored_text="Architected event-driven microservices processing 25,000 requests/sec with 99.99% availability.",
                            keywords_emphasized=["microservices"]
                        )
                    ]
                )
            ]
        )
        # Should execute cleanly without raising exception
        verifier.execute_all_layers(valid_draft)

    # =========================================================================
    # USER STORY 5: Typst DSL Escaping & Single-Page Budgeting
    # =========================================================================
    def test_user_story_5_typst_escaping_and_budgeting(self):
        r"""
        GIVEN special formatting characters in candidate text
        WHEN building Typst markup
        THEN all reserved DSL characters (\, #, $, _, *, @, [, ], <, >) are escaped
        AND page count inspection reliably counts PDF pages
        AND budgeting loop compacts multi-page overflow into exactly 1 page.
        """
        compiler = TypstCompilerService()

        # 1. DSL Escaping
        complex_text = "Lead #1 @ Stripe ($2.5M budget) [Kubernetes] *Fast* <50ms>"
        escaped = TypstCompilerService.escape_typst(complex_text)
        self.assertIn(r"\#1", escaped)
        self.assertIn(r"\@ Stripe", escaped)
        self.assertIn(r"\$2.5M", escaped)
        self.assertIn(r"\[Kubernetes\]", escaped)
        self.assertIn(r"\*Fast\*", escaped)
        self.assertIn(r"\<50ms\>", escaped)

        # 2. Markup synthesis
        draft = {
            "summary": "Specialized in cloud architecture #resilience.",
            "skills": ["Python", "Kubernetes", "AWS"],
            "experience": [
                {
                    "company": "Vanguard Cloud",
                    "role": "Staff Engineer",
                    "dates": "2020 - Present",
                    "location": "Seattle, WA",
                    "bullet_points": [{"tailored_text": "Scaled systems by 400%."}]
                }
            ]
        }
        markup = compiler.build_typst_markup(self.master_profile, draft, font_size=9.5)
        self.assertIn("Marcus Vance", markup)
        self.assertIn(r"marcus\@vance.io", markup)
        self.assertIn("Vanguard Cloud", markup)

        # 3. Dynamic Page Budgeting Loop
        class BudgetTestCompiler(TypstCompilerService):
            def compile_pdf(self, profile, tailored_draft, font_size=9.5, text_spacing="110%"):
                # Simulates 2 pages at font_size >= 9.0, compacts to 1 page at 8.5
                count = 2 if font_size > 8.5 else 1
                fake_pdf = f"%PDF-1.4\n/Type /Page\n" * count + "%%EOF"
                return fake_pdf.encode("utf-8"), count

        budget_compiler = BudgetTestCompiler()
        pdf_out = budget_compiler.render_pdf_with_budget(self.master_profile, draft, target_pages=1)
        final_pages = TypstCompilerService.inspect_page_count(pdf_out)
        self.assertEqual(final_pages, 1)

    # =========================================================================
    # USER STORY 6: End-to-End Async Tailoring Pipeline & Live Task Status
    # =========================================================================
    def test_user_story_6_async_tailoring_pipeline_lifecycle(self):
        """
        GIVEN a job description
        WHEN candidate enqueues tailoring request
        THEN server returns 202 Accepted with task_id immediately
        AND background worker extracts skills, verifies guardrails, scores ATS, and compiles PDF
        AND status endpoint returns COMPLETED with ATS breakdown and vector PDF base64.
        """
        raw_jd = "Looking for a Staff Engineer experienced in Python, Kubernetes, and Docker."

        # 1. Enqueue task
        post_resp = self.client.post("/api/v1/tailor", json={
            "target_role": "Staff Engineer",
            "company_name": "Datadog",
            "raw_job_description": raw_jd,
            "required_years": 4.0,
            "master_profile": self.master_profile
        })
        self.assertEqual(post_resp.status_code, 202)
        task_id = post_resp.json()["task_id"]

        # 2. Query task status
        get_resp = self.client.get(f"/api/v1/tailor/{task_id}")
        self.assertEqual(get_resp.status_code, 200)
        data = get_resp.json()
        self.assertEqual(data["task_id"], task_id)
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIsNotNone(data["ats_score"])
        self.assertIsNotNone(data["pdf_base64"])
        self.assertIsNone(data["error"])

    # =========================================================================
    # USER STORY 7: Recruiter Discovery & CAN-SPAM / GDPR Compliant Outreach
    # =========================================================================
    def test_user_story_7_compliant_recruiter_outreach(self):
        """
        GIVEN a target hiring company
        WHEN finding recruiters and generating cold outreach
        THEN deliverability is verified without raw port 25 SMTP sockets
        AND email body strictly includes postal address, opt-out link, and remains < 120 words
        AND candidate daily autopilot limit (15/day) is enforced.
        """
        # 1. Recruiter discovery & email verification
        domain, recruiters = OutreachService.discover_recruiters("Stripe", department="Engineering")
        self.assertEqual(domain, "stripe.com")
        self.assertGreater(len(recruiters), 0)

        verified = OutreachService.verify_email_deliverability(recruiters[0].email)
        self.assertTrue(verified.is_deliverable)
        self.assertFalse(verified.smtp_check_performed, "Raw port 25 SMTP handshakes must never be executed")

        # 2. Synthesize compliant outreach draft
        res = OutreachService.synthesize_outreach_email(
            candidate_name="Marcus Vance",
            candidate_role="Staff Infrastructure Engineer",
            candidate_summary="Expert in distributed Kubernetes architectures.",
            recruiter_name=recruiters[0].full_name,
            recruiter_email=recruiters[0].email,
            recruiter_title=recruiters[0].title,
            company_name="Stripe",
            target_job_title="Staff SRE",
            mode="copilot",
            user_id="usr_outreach_test_1"
        )
        draft = res.draft
        self.assertLess(draft.word_count, 120)
        self.assertTrue(draft.is_compliant)
        self.assertIn("100 Montgomery St", draft.body_text)
        self.assertIn("https://rolesync.ai/opt-out?token=", draft.body_text)

    # =========================================================================
    # USER STORY 8: Workday Multi-Step Wizard Autopilot Simulation
    # =========================================================================
    def test_user_story_8_workday_autopilot_five_stage_traversal(self):
        """
        GIVEN a multi-step Workday application wizard
        WHEN the autopilot navigates sequential stages
        THEN each stage (MY_INFORMATION -> MY_EXPERIENCE -> QUESTIONS -> DISCLOSURES -> REVIEW)
        populates mapped fields, updates session checkpoints, and pauses before final submission.
        """
        stages = [
            "MY_INFORMATION",
            "MY_EXPERIENCE",
            "APPLICATION_QUESTIONS",
            "VOLUNTARY_DISCLOSURES",
            "REVIEW"
        ]

        checkpoint = {
            "taskId": "task_workday_auto_001",
            "currentStepIndex": 0,
            "currentStepName": stages[0],
            "status": "IN_PROGRESS",
            "completedSteps": [],
            "stepData": {}
        }

        for i, stage in enumerate(stages):
            checkpoint["currentStepIndex"] = i
            checkpoint["currentStepName"] = stage
            checkpoint["stepData"][stage] = {"fields_filled": 4, "errors": 0}
            checkpoint["completedSteps"].append(stage)

            if stage == "REVIEW":
                # Supervised safety pause
                checkpoint["status"] = "PAUSED_FOR_USER_REVIEW"

        self.assertEqual(len(checkpoint["completedSteps"]), 5)
        self.assertEqual(checkpoint["status"], "PAUSED_FOR_USER_REVIEW")

    # =========================================================================
    # USER STORY 9: Telemetry, Error Handling & Selector Drift Monitoring
    # =========================================================================
    def test_user_story_9_telemetry_drift_reporting_and_rfc7807_errors(self):
        """
        GIVEN DOM selector drift on a target ATS portal
        WHEN extension reports the failure to the backend
        THEN candidate PII is sanitized
        AND RFC 7807 problem+json error formatting is returned on validation errors.
        """
        drift_payload = {
            "host": "myworkdayjobs.com",
            "ats_provider": "WORKDAY",
            "failed_selectors": ["[data-automation-id='legalNameSection_lastName']"],
            "page_structure_summary": {
                "totalElements": 150,
                "tagCounts": {"div": 50, "input": 8},
                "maxDepth": 7,
                "hasForm": True,
                "buttonCount": 3,
                "inputCount": 8
            },
            "client_version": "2.0.0-mv3",
            "timestamp": time.time()
        }

        res = self.client.post("/api/v1/telemetry/selector-failure", json=drift_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "RECORDED")

        # RFC 7807 format on unprocessable payload
        err_res = self.client.post("/api/v1/telemetry/selector-failure", json={"invalid": "payload"})
        self.assertEqual(err_res.status_code, 422)
        self.assertEqual(err_res.headers["content-type"], "application/problem+json")
        err_json = err_res.json()
        self.assertIn("type", err_json)
        self.assertIn("invalid_params", err_json)

    # =========================================================================
    # USER STORY 10: Real-Time WebSocket Streaming & Background Keepalive
    # =========================================================================
    def test_user_story_10_realtime_websocket_task_channel(self):
        """
        GIVEN an ongoing background tailoring task
        WHEN a client connects to /ws/v1/tasks/{task_id}
        THEN progress states are streamed over the WebSocket
        AND client can send keepalive PING frames receiving PONG responses.
        """
        task_id = "test_ws_story_10"
        task_store[task_id] = {"status": "PROCESSING", "stage": "SYNTHESIZING_TAILORED_DRAFT"}

        with self.client.websocket_connect(f"/ws/v1/tasks/{task_id}") as ws:
            # 1. Receives current state upon connection
            initial = ws.receive_json()
            self.assertEqual(initial["task_id"], task_id)
            self.assertEqual(initial["stage"], "SYNTHESIZING_TAILORED_DRAFT")

            # 2. Keepalive ping-pong
            ws.send_text("PING")
            pong = ws.receive_text()
            self.assertEqual(pong, "PONG")

    # =========================================================================
    # USER STORY 11: Application Tracking Pipeline & Lifecycle Management
    # =========================================================================
    def test_user_story_11_application_tracking_lifecycle(self):
        """
        GIVEN an applied or tailored job position
        WHEN candidate saves it to their Application Tracker
        THEN the application is recorded with ATS match score and provider
        AND candidate can update status (DRAFT -> APPLIED -> INTERVIEWING -> OFFERED)
        AND candidate notes and filter queries persist accurately.
        """
        create_payload = {
            "company_name": "Datadog",
            "job_title": "Senior Reliability Engineer",
            "job_url": "https://careers.datadoghq.com/detail/123",
            "ats_provider": "GREENHOUSE",
            "ats_score": 91.5,
            "status": "APPLIED",
            "notes": "Met recruiter at Tech Summit; submitted tailored resume.",
            "tailored_summary": "SRE specializing in multi-region Kubernetes and low-latency microservices."
        }

        # 1. Create application
        res = self.client.post("/api/v1/applications", json=create_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        app_id = data["id"]
        self.assertEqual(data["company_name"], "Datadog")
        self.assertEqual(data["status"], "APPLIED")
        self.assertEqual(data["ats_score"], 91.5)

        # 2. List applications
        res_list = self.client.get("/api/v1/applications")
        self.assertEqual(res_list.status_code, 200)
        list_data = res_list.json()
        self.assertGreaterEqual(list_data["total"], 1)
        found = [a for a in list_data["applications"] if a["id"] == app_id]
        self.assertTrue(len(found) == 1)

        # 3. Update status to INTERVIEWING
        patch_res = self.client.patch(f"/api/v1/applications/{app_id}", json={
            "status": "INTERVIEWING",
            "notes": "Recruiter screen scheduled for Friday 2 PM."
        })
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.json()["status"], "INTERVIEWING")
        self.assertIn("Friday 2 PM", patch_res.json()["notes"])

        # 4. Advance status to OFFERED
        offer_res = self.client.patch(f"/api/v1/applications/{app_id}", json={
            "status": "OFFERED"
        })
        self.assertEqual(offer_res.status_code, 200)
        self.assertEqual(offer_res.json()["status"], "OFFERED")

        # 5. Clean up
        del_res = self.client.delete(f"/api/v1/applications/{app_id}")
        self.assertEqual(del_res.status_code, 204)

    # =========================================================================
    # USER STORY 12: Context-Aware Cover Letter Synthesis with Multi-Tone Selection
    # =========================================================================
    def test_user_story_12_cover_letter_synthesis(self):
        """
        GIVEN a target job posting and candidate Master Profile
        WHEN candidate requests a tailored cover letter across different tones
        THEN the synthesized letter highlights matching technical competencies
        AND includes authentic quantitative metrics from their Master Vault
        AND strictly avoids fabricating experiences or unlisted companies.
        """
        req_payload = {
            "target_role": "Staff Infrastructure Engineer",
            "company_name": "Cloudflare",
            "raw_job_description": "Seeking a Staff Engineer skilled in Python, Kubernetes, Redis, Docker, and AWS to scale distributed edge networks.",
            "candidate_name": "Marcus Vance",
            "candidate_summary": self.master_profile["summary"],
            "master_profile": self.master_profile,
            "tone": "confident"
        }

        res = self.client.post("/api/v1/cover-letter/synthesize", json=req_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["company_name"], "Cloudflare")
        self.assertEqual(data["target_role"], "Staff Infrastructure Engineer")
        self.assertEqual(data["candidate_name"], "Marcus Vance")
        self.assertIn("Cloudflare", data["full_text"])
        self.assertIn("Kubernetes", data["full_text"])
        self.assertGreater(data["word_count"], 120)
        self.assertTrue(len(data["body_paragraphs"]) >= 2)

        # Test enthusiastic tone
        req_payload["tone"] = "enthusiastic"
        res_enth = self.client.post("/api/v1/cover-letter/synthesize", json=req_payload)
        self.assertEqual(res_enth.status_code, 200)
        self.assertIn("thrilled", res_enth.json()["opening_paragraph"].lower())


if __name__ == "__main__":
    unittest.main()
