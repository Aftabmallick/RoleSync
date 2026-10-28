import os
import hmac
import hashlib
from typing import Tuple
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.core.config import settings


class EnvelopeEncryption:
    INFO_CONTEXT = b"RoleSync-UserData"

    @classmethod
    def get_master_kek(cls) -> bytes:
        """Returns the 256-bit (32-byte) Master Key Encryption Key."""
        return bytes.fromhex(settings.MASTER_ENCRYPTION_KEY_HEX)

    @classmethod
    def derive_tenant_dek(cls, user_id: str) -> bytes:
        """
        Derives a Data Encryption Key (DEK) uniquely for a given tenant using HKDF-SHA256.
        DEK = HKDF-SHA256(MasterKEK, Salt=user_id, Info="RoleSync-UserData")
        """
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=user_id.encode("utf-8"),
            info=cls.INFO_CONTEXT,
        )
        return hkdf.derive(cls.get_master_kek())

    @classmethod
    def encrypt(cls, plaintext: bytes, user_id: str) -> Tuple[bytes, bytes]:
        """
        Encrypts plaintext bytes with AES-256-GCM using the tenant-derived DEK.
        Returns: (ciphertext_with_tag, 96_bit_iv)
        """
        dek = cls.derive_tenant_dek(user_id)
        aesgcm = AESGCM(dek)
        iv = os.urandom(12)  # 96-bit recommended IV for GCM
        # aesgcm.encrypt returns ciphertext + 128-bit authentication tag
        ciphertext = aesgcm.encrypt(iv, plaintext, associated_data=user_id.encode("utf-8"))
        return ciphertext, iv

    @classmethod
    def decrypt(cls, ciphertext: bytes, iv: bytes, user_id: str) -> bytes:
        """
        Decrypts ciphertext bytes with AES-256-GCM using the tenant-derived DEK.
        Verifies GCM authentication tag against associated_data=user_id.
        """
        dek = cls.derive_tenant_dek(user_id)
        aesgcm = AESGCM(dek)
        return aesgcm.decrypt(iv, ciphertext, associated_data=user_id.encode("utf-8"))


def hash_token(raw_token: str) -> str:
    """Returns SHA-256 hex digest for storage in Redis or PostgreSQL."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a password against a PBKDF2-HMAC-SHA256 salted hash using constant-time comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        _, iterations_str, salt_hex, hash_hex = parts
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt,
            int(iterations_str)
        )
        return hmac.compare_digest(derived, expected_hash)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generates a secure PBKDF2-HMAC-SHA256 salted hash with 100,000 iterations."""
    salt = os.urandom(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations
    )
    return f"pbkdf2_sha256${iterations}${salt.hex()}${derived.hex()}"
