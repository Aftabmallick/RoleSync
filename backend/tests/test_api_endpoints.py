import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.api.v1.endpoints.profile import encrypted_profiles_db


class TestApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        encrypted_profiles_db.clear()

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

    def test_master_profile_encryption_api(self):
        # 1. GET default initial profile
        get_res = self.client.get("/api/v1/profile")
        self.assertEqual(get_res.status_code, 200)
        data = get_res.json()
        self.assertIn("profile", data)
        self.assertEqual(data["profile"]["personal"]["full_name"], "Alex Mercer")

        # 2. POST custom profile (AES-256 HKDF encrypted)
        custom_payload = {
            "personal": {
                "full_name": "Jordan Bell",
                "email": "jordan@bell.io",
                "phone": "+1 555-888-9999",
                "location": "Austin, TX",
                "linkedin": "linkedin.com/in/jordanbell",
                "github": "github.com/jordanbell"
            },
            "skills": [
                {"name": "Rust", "category": "Languages"},
                {"name": "Kubernetes", "category": "DevOps"}
            ],
            "experience": [],
            "education": [],
            "summary": "Rust Systems Architect"
        }
        post_res = self.client.post("/api/v1/profile", json=custom_payload)
        self.assertEqual(post_res.status_code, 200)
        post_data = post_res.json()
        self.assertEqual(post_data["profile"]["personal"]["full_name"], "Jordan Bell")
        self.assertIn("encrypted", post_data["message"].lower())

        # 3. GET profile back decrypted
        verify_res = self.client.get("/api/v1/profile")
        self.assertEqual(verify_res.status_code, 200)
        verify_data = verify_res.json()
        self.assertEqual(verify_data["profile"]["personal"]["full_name"], "Jordan Bell")
        self.assertEqual(verify_data["profile"]["skills"][0]["name"], "Rust")


if __name__ == "__main__":
    unittest.main()

