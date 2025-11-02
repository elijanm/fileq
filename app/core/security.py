from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from core.config import settings
from pathlib import Path

PRIVATE_KEY_PATH = Path("secrets/private_key.pem")
PUBLIC_KEY_PATH = Path("secrets/public_key.pem")

def sign_data(data: bytes) -> bytes:
    """Sign data using RSA private key."""
    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    return private_key.sign(data, padding.PKCS1v15(), hashes.SHA256())

def verify_signature(data: bytes, signature: bytes) -> bool:
    """Verify data signature with public key."""
    public_key = serialization.load_pem_public_key(PUBLIC_KEY_PATH.read_bytes())
    try:
        public_key.verify(signature, data, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False
    

