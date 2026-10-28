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


if __name__ == "__main__":
    unittest.main()
