import unittest
from fastapi.testclient import TestClient
from app.main import app


class TestApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "RoleSync Platform API")

    def test_google_auth_and_token_refresh_flow(self):
        # 1. Login with Google ID token
        auth_resp = self.client.post(
            "/api/v1/auth/google",
            json={
                "id_token": "mock_google_id_token_xyz123",
                "device_fingerprint": "macbook_pro_m2_chrome_ext"
            }
        )
        self.assertEqual(auth_resp.status_code, 200)
        auth_data = auth_resp.json()
        self.assertIn("access_token", auth_data)
        self.assertIn("refresh_token", auth_data)
        self.assertEqual(auth_data["token_type"], "bearer")

        access_token = auth_data["access_token"]
        refresh_token = auth_data["refresh_token"]

        # 2. Rotate Refresh Token
        refresh_resp = self.client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": refresh_token,
                "device_fingerprint": "macbook_pro_m2_chrome_ext",
                "email": "candidate@example.com",
                "tier": "FREE"
            }
        )
        self.assertEqual(refresh_resp.status_code, 200)
        new_data = refresh_resp.json()
        self.assertIn("access_token", new_data)
        self.assertIn("refresh_token", new_data)
        self.assertNotEqual(refresh_token, new_data["refresh_token"])

        # 3. Attacker replays consumed old refresh token -> 401 Unauthorized
        replay_resp = self.client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": refresh_token,
                "device_fingerprint": "macbook_pro_m2_chrome_ext",
                "email": "candidate@example.com",
                "tier": "FREE"
            }
        )
        self.assertEqual(replay_resp.status_code, 401)
        self.assertIn("reuse detected", replay_resp.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()

