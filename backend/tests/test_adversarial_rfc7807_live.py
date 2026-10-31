"""
Adversarial RFC 7807 Problem Details Verification Harness for RoleSync Live Endpoints.

Executed by Empirical Challenger 1 (Milestone 1 Iteration 2).
Tests:
1. Malformed payloads to /api/v1/auth/register, /api/v1/tailor, /api/v1/profile
2. Auth errors, missing auth, invalid tokens, and token replay on /api/v1/auth/refresh
3. Non-existent IDs on /api/v1/applications/{app_id}, /api/v1/resume/versions/{version_id}, /api/v1/tailor/{task_id}
4. Strict validation of 100% of error responses:
   - Header Content-Type contains application/problem+json
   - All 5 required keys: type, title, status, detail, instance
   - Status code alignment
   - Non-empty string types
"""

import json
import sqlite3
import sys
import uuid
from typing import Any, Dict, List, Optional
import psycopg2
import requests

BASE_URL = "http://127.0.0.1:8000"
REQUIRED_RFC7807_KEYS = {"type", "title", "status", "detail", "instance"}


class AdversarialTestRunner:
    def __init__(self):
        self.session = requests.Session()
        self.test_id = uuid.uuid4().hex[:8]
        self.test_email = f"challenger_test_{self.test_id}@rolesync.io"
        self.test_password = f"P@ssw0rdSecure_{self.test_id}!"
        self.test_full_name = f"Challenger User {self.test_id}"
        self.auth_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.failures: List[Dict[str, Any]] = []

    def validate_rfc7807(self, response: requests.Response, expected_status: Optional[int] = None, context: str = "") -> bool:
        """Validates that a response strictly complies with RFC 7807 Problem Details."""
        self.total_tests += 1
        test_desc = f"RFC7807 Validation [{response.request.method} {response.url}] ({context})"
        
        # Check HTTP Status Code
        if expected_status and response.status_code != expected_status:
            msg = f"Expected status {expected_status}, got {response.status_code}"
            self.failures.append({"test": test_desc, "error": msg, "body": response.text[:300]})
            print(f"  [FAIL] {test_desc}: {msg}")
            self.failed_tests += 1
            return False

        # Check Content-Type header
        ct = response.headers.get("content-type", "")
        if "application/problem+json" not in ct:
            msg = f"Expected 'application/problem+json' in Content-Type, got '{ct}'"
            self.failures.append({"test": test_desc, "error": msg, "body": response.text[:300]})
            print(f"  [FAIL] {test_desc}: {msg}")
            self.failed_tests += 1
            return False

        # Parse JSON
        try:
            body = response.json()
        except Exception as e:
            msg = f"Response body is not valid JSON: {e}"
            self.failures.append({"test": test_desc, "error": msg, "body": response.text[:300]})
            print(f"  [FAIL] {test_desc}: {msg}")
            self.failed_tests += 1
            return False

        # Check 5 Required Keys
        missing = REQUIRED_RFC7807_KEYS - set(body.keys())
        if missing:
            msg = f"Missing required RFC 7807 keys: {missing}. Present keys: {list(body.keys())}"
            self.failures.append({"test": test_desc, "error": msg, "body": body})
            print(f"  [FAIL] {test_desc}: {msg}")
            self.failed_tests += 1
            return False

        # Validate types and values
        for key in ["type", "title", "detail", "instance"]:
            val = body.get(key)
            if not isinstance(val, str) or not val.strip():
                msg = f"Field '{key}' must be non-empty string, got {type(val)}: {repr(val)}"
                self.failures.append({"test": test_desc, "error": msg, "body": body})
                print(f"  [FAIL] {test_desc}: {msg}")
                self.failed_tests += 1
                return False

        status_val = body.get("status")
        if not isinstance(status_val, int) or status_val != response.status_code:
            msg = f"Field 'status' ({status_val}) does not match HTTP status code ({response.status_code})"
            self.failures.append({"test": test_desc, "error": msg, "body": body})
            print(f"  [FAIL] {test_desc}: {msg}")
            self.failed_tests += 1
            return False

        print(f"  [PASS] {test_desc} -> {response.status_code} application/problem+json [all 5 keys valid]")
        self.passed_tests += 1
        return True

    def setup_authenticated_user(self):
        """Creates a temporary user to get valid auth headers for testing authenticated endpoints."""
        print("\n--- Setup: Register Ephemeral Candidate for Authenticated Stress Tests ---")
        payload = {
            "email": self.test_email,
            "password": self.test_password,
            "full_name": self.test_full_name,
        }
        res = self.session.post(f"{BASE_URL}/api/v1/auth/register", json=payload, timeout=10)
        if res.status_code == 201:
            data = res.json()
            self.auth_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self.user_id = data.get("user", {}).get("id")
            print(f"  [SETUP OK] Registered user {self.test_email} (id={self.user_id})")
        else:
            raise RuntimeError(f"Failed to register test candidate: {res.status_code} - {res.text}")

    # =========================================================================
    # Test Suite 1: Malformed payloads to /register, /tailor, /profile
    # =========================================================================
    def test_malformed_auth_register(self):
        print("\n--- Suite 1.1: Malformed Payloads to /api/v1/auth/register ---")
        url = f"{BASE_URL}/api/v1/auth/register"

        # 1. Empty dict -> 422
        r = self.session.post(url, json={}, timeout=10)
        self.validate_rfc7807(r, 422, "Empty JSON payload")

        # 2. Missing email -> 422
        r = self.session.post(url, json={"password": self.test_password, "full_name": "Test"}, timeout=10)
        self.validate_rfc7807(r, 422, "Missing email field")

        # 3. Missing password -> 422
        r = self.session.post(url, json={"email": "valid@email.com", "full_name": "Test"}, timeout=10)
        self.validate_rfc7807(r, 422, "Missing password field")

        # 4. Invalid email format -> 422
        r = self.session.post(url, json={"email": "not-an-email", "password": self.test_password, "full_name": "Test"}, timeout=10)
        self.validate_rfc7807(r, 422, "Malformed email format")

        # 5. Type mismatch (email is integer) -> 422
        r = self.session.post(url, json={"email": 123456, "password": self.test_password, "full_name": "Test"}, timeout=10)
        self.validate_rfc7807(r, 422, "Email field type mismatch (integer)")

        # 6. Raw malformed JSON string -> 422
        r = self.session.post(url, data='{"email": "broken_json', headers={"Content-Type": "application/json"}, timeout=10)
        self.validate_rfc7807(r, 422, "Malformed JSON syntax")

        # 7. Duplicate registration (business logic 400)
        r = self.session.post(url, json={"email": self.test_email, "password": self.test_password, "full_name": "Dup"}, timeout=10)
        self.validate_rfc7807(r, 400, "Duplicate email registration")

    def test_malformed_tailor(self):
        print("\n--- Suite 1.2: Malformed Payloads to /api/v1/tailor ---")
        url = f"{BASE_URL}/api/v1/tailor"

        auth_hdr = {"Authorization": f"Bearer {self.auth_token}"}

        # 1. Empty JSON payload -> 422
        r = self.session.post(url, json={}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "Empty JSON payload")

        # 2. Missing raw_job_description -> 422
        r = self.session.post(url, json={"target_role": "Engineer", "company_name": "Acme"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "Missing raw_job_description")

        # 3. Missing target_role -> 422
        r = self.session.post(url, json={"raw_job_description": "We need an engineer", "company_name": "Acme"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "Missing target_role")

        # 4. Missing company_name -> 422
        r = self.session.post(url, json={"raw_job_description": "We need an engineer", "target_role": "Engineer"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "Missing company_name")

        # 5. Type mismatch (raw_job_description is integer) -> 422
        r = self.session.post(url, json={"target_role": "Engineer", "company_name": "Acme", "raw_job_description": 98765}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "raw_job_description type mismatch")

        # 6. Malformed JSON syntax -> 422
        r = self.session.post(url, data='{"target_role":', headers={**auth_hdr, "Content-Type": "application/json"}, timeout=10)
        self.validate_rfc7807(r, 422, "Malformed JSON syntax")

        # 7. Unauthenticated request without master profile -> 400 (Identity required)
        r = self.session.post(
            url,
            json={
                "target_role": "Engineer",
                "company_name": "Acme",
                "raw_job_description": "Looking for a backend Python developer.",
            },
            timeout=10
        )
        self.validate_rfc7807(r, 400, "Unauthenticated request without master profile")

        # 8. Invalid auth token without master profile -> 400 (Invalid token treated as unauthenticated, identity required)
        r = self.session.post(
            url,
            json={
                "target_role": "Engineer",
                "company_name": "Acme",
                "raw_job_description": "Looking for a backend Python developer.",
            },
            headers={"Authorization": "Bearer invalid_token_123"},
            timeout=10
        )
        self.validate_rfc7807(r, 400, "Invalid Bearer token without master profile")

    def test_malformed_profile(self):
        print("\n--- Suite 1.3: Malformed Payloads to /api/v1/profile ---")
        url = f"{BASE_URL}/api/v1/profile"

        # 1. Missing Authorization header -> 401
        r = self.session.post(url, json={"personal": {}}, timeout=10)
        self.validate_rfc7807(r, 401, "Missing Authorization header")

        # 2. Invalid Authorization header -> 401
        r = self.session.post(url, json={"personal": {}}, headers={"Authorization": "Bearer bad_tok"}, timeout=10)
        self.validate_rfc7807(r, 401, "Invalid Bearer token")

        auth_hdr = {"Authorization": f"Bearer {self.auth_token}"}

        # 3. Empty JSON payload -> 422
        r = self.session.post(url, json={}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "Empty JSON payload")

        # 4. Type mismatch: personal is a string instead of dict -> 422
        r = self.session.post(url, json={"personal": "Not a dict"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "Field personal as string")

        # 5. Type mismatch: skills is a string instead of list -> 422
        r = self.session.post(url, json={"personal": {"full_name": "Test"}, "skills": "Not a list"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 422, "Field skills as string")

        # 6. Malformed JSON syntax -> 422
        r = self.session.post(url, data='{"personal": {', headers={**auth_hdr, "Content-Type": "application/json"}, timeout=10)
        self.validate_rfc7807(r, 422, "Malformed JSON syntax")

    # =========================================================================
    # Test Suite 2: Auth errors, missing auth, invalid tokens, token replay on /auth/refresh
    # =========================================================================
    def test_auth_refresh_errors(self):
        print("\n--- Suite 2: Auth Errors, Invalid Tokens, and Token Replay on /api/v1/auth/refresh ---")
        url = f"{BASE_URL}/api/v1/auth/refresh"

        # 1. Empty JSON payload -> 422
        r = self.session.post(url, json={}, timeout=10)
        self.validate_rfc7807(r, 422, "Empty JSON payload")

        # 2. Missing refresh_token field -> 422
        r = self.session.post(url, json={"device_fingerprint": "browser_fp"}, timeout=10)
        self.validate_rfc7807(r, 422, "Missing refresh_token field")

        # 3. Missing device_fingerprint field -> 422
        r = self.session.post(url, json={"refresh_token": "some_token"}, timeout=10)
        self.validate_rfc7807(r, 422, "Missing device_fingerprint field")

        # 4. Malformed JSON syntax -> 422
        r = self.session.post(url, data='{"refresh_token":', headers={"Content-Type": "application/json"}, timeout=10)
        self.validate_rfc7807(r, 422, "Malformed JSON syntax")

        # 5. Invalid token string with valid device_fingerprint -> 401
        r = self.session.post(url, json={"refresh_token": "totally_invalid_token_xyz", "device_fingerprint": "browser_fp"}, timeout=10)
        self.validate_rfc7807(r, 401, "Arbitrary invalid refresh token")

        # 6. Empty refresh_token string with valid device_fingerprint -> 401
        r = self.session.post(url, json={"refresh_token": "", "device_fingerprint": "browser_fp"}, timeout=10)
        self.validate_rfc7807(r, 401, "Empty refresh_token string")

        # 7. Valid refresh token rotation followed by Token Replay -> 401
        print("  [STEP] Performing legitimate refresh token rotation...")
        r_valid = self.session.post(
            url,
            json={
                "refresh_token": self.refresh_token,
                "device_fingerprint": "browser_client",
                "email": self.test_email
            },
            timeout=10
        )
        if r_valid.status_code != 200:
            raise RuntimeError(f"Valid refresh failed unexpectedly: {r_valid.status_code} - {r_valid.text}")
        new_tokens = r_valid.json()
        new_refresh = new_tokens.get("refresh_token")
        old_refresh = self.refresh_token
        # Update current active token
        self.refresh_token = new_refresh
        self.auth_token = new_tokens.get("access_token")
        print("  [STEP] Legitimate refresh succeeded. Now attempting token replay with revoked token...")

        # Token Replay with old revoked refresh_token -> 401
        r_replay = self.session.post(
            url,
            json={
                "refresh_token": old_refresh,
                "device_fingerprint": "browser_client",
                "email": self.test_email
            },
            timeout=10
        )
        self.validate_rfc7807(r_replay, 401, "Token replay with rotated/revoked refresh token")

    # =========================================================================
    # Test Suite 3: Non-existent IDs
    # =========================================================================
    def test_nonexistent_ids(self):
        print("\n--- Suite 3: Non-existent IDs on /applications, /resume/versions, /tailor ---")
        auth_hdr = {"Authorization": f"Bearer {self.auth_token}"}
        nil_uuid = "00000000-0000-0000-0000-000000000000"
        rand_uuid = str(uuid.uuid4())
        rand_str = f"nonexistent_{uuid.uuid4().hex[:10]}"

        # --- 3.1 /api/v1/applications/{app_id} ---
        app_url_nil = f"{BASE_URL}/api/v1/applications/{nil_uuid}"
        app_url_rand = f"{BASE_URL}/api/v1/applications/{rand_uuid}"
        app_url_str = f"{BASE_URL}/api/v1/applications/{rand_str}"

        # Unauthenticated calls
        r = self.session.patch(app_url_nil, json={"status": "APPLIED"}, timeout=10)
        self.validate_rfc7807(r, 401, "PATCH application without auth")

        r = self.session.delete(app_url_nil, timeout=10)
        self.validate_rfc7807(r, 401, "DELETE application without auth")

        # Authenticated PATCH non-existent nil UUID -> 404
        r = self.session.patch(app_url_nil, json={"status": "INTERVIEWING"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "PATCH application non-existent nil UUID")

        # Authenticated PATCH non-existent random UUID -> 404
        r = self.session.patch(app_url_rand, json={"status": "INTERVIEWING"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "PATCH application non-existent random UUID")

        # Authenticated PATCH non-existent string ID -> 404
        r = self.session.patch(app_url_str, json={"status": "INTERVIEWING"}, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "PATCH application non-existent string ID")

        # Authenticated DELETE non-existent nil UUID -> 404
        r = self.session.delete(app_url_nil, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "DELETE application non-existent nil UUID")

        # Authenticated DELETE non-existent random UUID -> 404
        r = self.session.delete(app_url_rand, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "DELETE application non-existent random UUID")

        # Authenticated DELETE non-existent string ID -> 404
        r = self.session.delete(app_url_str, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "DELETE application non-existent string ID")

        # --- 3.2 /api/v1/resume/versions/{version_id} ---
        ver_url_nil = f"{BASE_URL}/api/v1/resume/versions/{nil_uuid}"
        ver_url_str = f"{BASE_URL}/api/v1/resume/versions/{rand_str}"

        # Unauthenticated DELETE -> 401
        r = self.session.delete(ver_url_nil, timeout=10)
        self.validate_rfc7807(r, 401, "DELETE resume version without auth")

        # Authenticated DELETE non-existent nil UUID -> 404
        r = self.session.delete(ver_url_nil, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "DELETE resume version non-existent nil UUID")

        # Authenticated DELETE non-existent string ID -> 404
        r = self.session.delete(ver_url_str, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "DELETE resume version non-existent string ID")

        # --- 3.3 /api/v1/tailor/{task_id} ---
        tail_url_nil = f"{BASE_URL}/api/v1/tailor/{nil_uuid}"
        tail_url_str = f"{BASE_URL}/api/v1/tailor/{rand_str}"

        # Unauthenticated GET non-existent task ID -> 404
        r = self.session.get(tail_url_nil, timeout=10)
        self.validate_rfc7807(r, 404, "GET tailor task without auth (non-existent task ID)")

        # Authenticated GET non-existent nil UUID -> 404
        r = self.session.get(tail_url_nil, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "GET tailor task non-existent nil UUID")

        # Authenticated GET non-existent string task ID -> 404
        r = self.session.get(tail_url_str, headers=auth_hdr, timeout=10)
        self.validate_rfc7807(r, 404, "GET tailor task non-existent string ID")

    # =========================================================================
    # Teardown: Comprehensive Dual-Datastore Cleanup
    # =========================================================================
    def teardown(self):
        print("\n--- Teardown: Purging Challenger Ephemeral Records Across All Datastores ---")
        # 1. PostgreSQL Purge
        try:
            conn = psycopg2.connect("postgresql://rolesync_admin:rolesync_secure_password@localhost:5432/rolesync_db")
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email LIKE 'challenger_test_%'")
            user_ids = [r[0] for r in cur.fetchall()]
            for uid in user_ids:
                cur.execute("DELETE FROM application_history WHERE application_id IN (SELECT id FROM applications WHERE user_id = %s)", (uid,))
                cur.execute("DELETE FROM applications WHERE user_id = %s", (uid,))
                cur.execute("DELETE FROM master_profiles WHERE user_id = %s", (uid,))
                cur.execute("DELETE FROM resume_versions WHERE user_id = %s", (uid,))
                cur.execute("DELETE FROM refresh_tokens WHERE user_id = %s", (uid,))
                cur.execute("DELETE FROM users WHERE id = %s", (uid,))
            conn.commit()

            cur.execute("SELECT count(*) FROM users WHERE email LIKE 'challenger_test_%'")
            rem_users = cur.fetchone()[0]
            conn.close()
            print(f"  [TEARDOWN] PostgreSQL purge complete. Residual challenger users: {rem_users}")
            assert rem_users == 0, f"Residual challenger users in PostgreSQL: {rem_users}"
        except Exception as e:
            print(f"  [TEARDOWN WARNING] PostgreSQL purge error: {e}")

        # 2. SQLite Purge
        for db_path in ["RoleSync/backend/rolesync_dev.db", "RoleSync/rolesync_dev.db"]:
            try:
                sconn = sqlite3.connect(db_path)
                scur = sconn.cursor()
                scur.execute("SELECT id FROM users WHERE email LIKE 'challenger_test_%'")
                uids = [r[0] for r in scur.fetchall()]
                for uid in uids:
                    scur.execute("DELETE FROM applications WHERE user_id = ?", (uid,))
                    scur.execute("DELETE FROM master_profiles WHERE user_id = ?", (uid,))
                    scur.execute("DELETE FROM users WHERE id = ?", (uid,))
                sconn.commit()
                scur.execute("SELECT count(*) FROM users WHERE email LIKE 'challenger_test_%'")
                rem = scur.fetchone()[0]
                sconn.close()
                print(f"  [TEARDOWN] SQLite ({db_path}) purge complete. Residual challenger users: {rem}")
                assert rem == 0, f"Residual challenger users in SQLite {db_path}: {rem}"
            except Exception as e:
                print(f"  [TEARDOWN WARNING] SQLite purge error on {db_path}: {e}")

    def run_all(self) -> int:
        print("================================================================================")
        print("   ADVERSARIAL RFC 7807 ERROR SPECIFICATION & STRESS TEST HARNESS               ")
        print("================================================================================")

        try:
            self.setup_authenticated_user()
            self.test_malformed_auth_register()
            self.test_malformed_tailor()
            self.test_malformed_profile()
            self.test_auth_refresh_errors()
            self.test_nonexistent_ids()
        finally:
            self.teardown()

        print("\n================================================================================")
        print(f"   ADVERSARIAL STRESS TEST SUMMARY: Total={self.total_tests} | Passed={self.passed_tests} | Failed={self.failed_tests}")
        print("================================================================================")
        if self.failures:
            print("\nFAILURES ENCOUNTERED:")
            for f in self.failures:
                print(f" - {f['test']}: {f['error']}")
            return 1
        else:
            print("100% of tested error responses strictly emitted 'application/problem+json'")
            print("and all 5 required RFC 7807 keys: type, title, status, detail, instance.")
            return 0


if __name__ == "__main__":
    runner = AdversarialTestRunner()
    sys.exit(runner.run_all())
