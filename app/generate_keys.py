#!/usr/bin/env python3
"""
Generate RSA key pair for Nexidra Registry Plugin Signing
----------------------------------------------------------
Creates:
  secrets/private_key.pem
  secrets/public_key.pem
"""

from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

SECRET_DIR = Path("secrets")
SECRET_DIR.mkdir(parents=True, exist_ok=True)

# Generate private key (4096-bit RSA)
private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

# Write private key
private_path = SECRET_DIR / "private_key.pem"
private_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
)
private_path.write_bytes(private_bytes)
print(f"🔑 Generated private key → {private_path}")

# Write public key
public_path = SECRET_DIR / "public_key.pem"
public_bytes = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)
public_path.write_bytes(public_bytes)
print(f"🔓 Generated public key → {public_path}")
