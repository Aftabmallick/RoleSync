import unittest
import uuid
import os
from cryptography.exceptions import InvalidTag
from app.core.security import EnvelopeEncryption, hash_token, verify_password, get_password_hash


class TestSecurityAndEncryption(unittest.TestCase):
    def test_hkdf_tenant_key_derivation(self):
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())

        dek_a1 = EnvelopeEncryption.derive_tenant_dek(user_a)
        dek_a2 = EnvelopeEncryption.derive_tenant_dek(user_a)
        dek_b = EnvelopeEncryption.derive_tenant_dek(user_b)

        # Deterministic for the same user
        self.assertEqual(dek_a1, dek_a2)
        self.assertEqual(len(dek_a1), 32)  # 256 bits

        # Completely different keys across different tenants
        self.assertNotEqual(dek_a1, dek_b)

    def test_envelope_encryption_roundtrip(self):
        user_id = str(uuid.uuid4())
        secret_profile = b'{"full_name": "Alice Dev", "skills": ["Python", "Typst", "FastAPI"]}'

        ciphertext, iv = EnvelopeEncryption.encrypt(secret_profile, user_id)
        self.assertNotEqual(ciphertext, secret_profile)
        self.assertEqual(len(iv), 12)

        decrypted = EnvelopeEncryption.decrypt(ciphertext, iv, user_id)
        self.assertEqual(decrypted, secret_profile)

    def test_cross_tenant_decryption_tamper_proofing(self):
        user_a = str(uuid.uuid4())
        user_b = str(uuid.uuid4())
        secret_profile = b'{"salary_expectation": 185000}'

        ciphertext_a, iv_a = EnvelopeEncryption.encrypt(secret_profile, user_a)

        # Attempting to decrypt Tenant A's ciphertext using Tenant B's credentials must fail
        with self.assertRaises(InvalidTag):
            EnvelopeEncryption.decrypt(ciphertext_a, iv_a, user_b)

    def test_ciphertext_tampering_raises(self):
        user_id = str(uuid.uuid4())
        data = b"sensitive resume data"
        ciphertext, iv = EnvelopeEncryption.encrypt(data, user_id)

        # Tamper with one byte of ciphertext
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF

        with self.assertRaises(InvalidTag):
            EnvelopeEncryption.decrypt(bytes(tampered), iv, user_id)

    def test_token_and_password_hashing(self):
        raw_token = "refresh_token_sample_12345"
        h1 = hash_token(raw_token)
        h2 = hash_token(raw_token)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex digest

        pwd = "StrongSecurePassword!123"
        hashed = get_password_hash(pwd)
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))


if __name__ == "__main__":
    unittest.main()
