from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from pathlib import Path

PRIVATE_KEY_PATH = Path("../secrets/private_key.pem")

def sign_data(data: bytes) -> bytes:
  
    private_key = serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    return private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
