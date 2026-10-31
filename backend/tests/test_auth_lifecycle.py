import unittest
import uuid
from app.core.jwt import create_access_token, verify_access_token
from app.services.auth_service import (
    TokenManager,
    InvalidRefreshTokenException,
    RefreshTokenRevokedException,
)


class TestAuthLifecycle(unittest.TestCase):
    def setUp(self):
        self.manager = TokenManager()
        self.user_id = str(uuid.uuid4())
        self.email = "candidate@example.com"
        self.tier = "PRO"
        self.device_fingerprint = "fp_macos_chrome_ext_991823"

    def test_access_token_creation_and_verification(self):
        token = create_access_token({
            "sub": self.user_id,
            "email": self.email,
            "tier": self.tier
        })
        payload = verify_access_token(token)

        self.assertEqual(payload["sub"], self.user_id)
        self.assertEqual(payload["email"], self.email)
        self.assertEqual(payload["tier"], self.tier)
        self.assertEqual(payload["iss"], "https://api.rolesync.io")
        self.assertEqual(payload["aud"], "https://app.rolesync.io")

    def test_refresh_token_rotation_success(self):
        tokens1 = self.manager.issue_token_pair(
            self.user_id, self.email, self.tier, self.device_fingerprint
        )
        refresh1 = tokens1["refresh_token"]

        # Rotate refresh token
        tokens2 = self.manager.rotate_refresh_token(
            refresh1, self.device_fingerprint, self.email, self.tier
        )
        refresh2 = tokens2["refresh_token"]

        self.assertNotEqual(refresh1, refresh2)
        self.assertIsNotNone(tokens2["access_token"])

    def test_reuse_anomaly_triggers_global_revocation(self):
        tokens1 = self.manager.issue_token_pair(
            self.user_id, self.email, self.tier, self.device_fingerprint
        )
        refresh1 = tokens1["refresh_token"]

        # Legitimate rotation
        tokens2 = self.manager.rotate_refresh_token(
            refresh1, self.device_fingerprint, self.email, self.tier
        )
        refresh2 = tokens2["refresh_token"]

        # Attacker replays consumed token refresh1!
        with self.assertRaises(RefreshTokenRevokedException):
            self.manager.rotate_refresh_token(
                refresh1, self.device_fingerprint, self.email, self.tier
            )

        # Attacker's replay must have caused refresh2 to be revoked as well!
        with self.assertRaises((InvalidRefreshTokenException, RefreshTokenRevokedException)):
            self.manager.rotate_refresh_token(
                refresh2, self.device_fingerprint, self.email, self.tier
            )

    def test_device_fingerprint_mismatch_rejected(self):
        tokens = self.manager.issue_token_pair(
            self.user_id, self.email, self.tier, self.device_fingerprint
        )
        with self.assertRaises(InvalidRefreshTokenException):
            self.manager.rotate_refresh_token(
                tokens["refresh_token"], "attacker_fingerprint_xyz", self.email, self.tier
            )

    def test_register_login_and_me_api_lifecycle(self):
        from fastapi.testclient import TestClient
        from app.main import app
        client = TestClient(app)

        test_email = f"test_cand_{uuid.uuid4().hex[:6]}@example.com"
        test_pwd = "StrongPassword123!"

        # 1. Register candidate
        reg_resp = client.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": test_pwd,
            "full_name": "Test Candidate Dev"
        })
        self.assertEqual(reg_resp.status_code, 201)
        data = reg_resp.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["email"], test_email)
        self.assertEqual(data["user"]["full_name"], "Test Candidate Dev")
        token = data["access_token"]

        # 2. Duplicate registration rejected
        dup_resp = client.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": test_pwd,
            "full_name": "Duplicate Candidate"
        })
        self.assertEqual(dup_resp.status_code, 400)

        # 3. Login with correct password
        login_resp = client.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": test_pwd
        })
        self.assertEqual(login_resp.status_code, 200)
        login_data = login_resp.json()
        self.assertIn("access_token", login_data)

        # 4. Login with incorrect password rejected
        bad_login = client.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "WrongPassword!"
        })
        self.assertEqual(bad_login.status_code, 401)

        # 5. Access /auth/me with Bearer token
        me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.json()
        self.assertEqual(me_data["email"], test_email)


if __name__ == "__main__":
    unittest.main()
