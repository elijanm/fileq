from __future__ import annotations
import os, re, json, hashlib
from typing import Dict, List, Any
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, field_validator

# ----------------------------------------------------------------------------
# 🔐 Encryption
# ----------------------------------------------------------------------------
SECRET_KEY = os.getenv("ENCRYPTION_KEY") or Fernet.generate_key().decode()
fernet = Fernet(SECRET_KEY.encode() if isinstance(SECRET_KEY, str) else SECRET_KEY)

def encrypt_value(v: str | None) -> str | None:
    if not v or not isinstance(v, str):
        return v
    return fernet.encrypt(v.encode()).decode()

def decrypt_value(v: str | None) -> str | None:
    if not v or not isinstance(v, str):
        return v
    try:
        return fernet.decrypt(v.encode()).decode()
    except Exception:
        return v  # already plaintext or invalid ciphertext

# ----------------------------------------------------------------------------
# 😎 Masking for logs
# ----------------------------------------------------------------------------
def mask_value(v: str) -> str:
    if not isinstance(v, str):
        return v
    if "@" in v:
        user, _, domain = v.partition("@")
        return user[:2] + "***@" + domain
    if v.isdigit() and len(v) >= 8:
        return "*" * (len(v) - 4) + v[-4:]
    return v[:2] + "***" if len(v) > 3 else "***"

# ----------------------------------------------------------------------------
# 🔎 PII patterns
# ----------------------------------------------------------------------------
PII_KEYWORDS = [
    "name", "email", "phone", "mobile", "ssn", "dob", "address",
    "card", "account", "iban", "passport", "license", "secret", "token", "pmi"
]
PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{2,3}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{4}\b",
    "ssn":   r"\b\d{3}-\d{2}-\d{4}\b",
    "card":  r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
}

# ----------------------------------------------------------------------------
# ⚙️ Hash helpers
# ----------------------------------------------------------------------------
HASH_SALT = os.getenv("HASH_SALT", "nexidra_salt").encode()

def search_hash(v: str) -> str:
    """Deterministic hash for exact lookup"""
    return hashlib.sha256(HASH_SALT + v.lower().encode()).hexdigest()

def tokenize_for_search(text: str, n: int = 3) -> list[str]:
    """Generate n-gram hashes for partial lookup."""
    text = text.lower()
    ngrams = {text[i:i+n] for i in range(len(text) - n + 1)} if len(text) >= n else {text}
    return [hashlib.sha256(HASH_SALT + ng.encode()).hexdigest() for ng in ngrams]

# ----------------------------------------------------------------------------
# 🧠 Base Model
# ----------------------------------------------------------------------------
class SecurePIIModel(BaseModel):
    """
    - Auto-encrypt/decrypt PII
    - Auto-generate _hash and _search tokens for DB lookups
    - Masked dump for safe logs
    """
    model_config = {"ser_json_tuples": True}

    # --- auto-decrypt on load -----------------------------------------------
    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def _auto_decrypt(cls, v, info):
        if isinstance(v, str) and any(k in info.field_name.lower() for k in PII_KEYWORDS):
            return decrypt_value(v)
        return v

    # --- identify PII -------------------------------------------------------
    def identify_pii(self) -> Dict[str, List[str]]:
        found: Dict[str, List[str]] = {}
        for field, value in self.model_dump().items():
            hits = []
            lf = field.lower()
            for k in PII_KEYWORDS:
                if k in lf:
                    hits.append(f"keyword:{k}")
            if isinstance(value, str):
                for label, pattern in PII_PATTERNS.items():
                    if re.search(pattern, value):
                        hits.append(f"pattern:{label}")
            if hits:
                found[field] = hits
        return found

    # --- masked for logs ----------------------------------------------------
    def masked_dump(self) -> Dict[str, Any]:
        data = self.model_dump()
        for f, v in data.items():
            if isinstance(v, str) and any(k in f.lower() for k in PII_KEYWORDS):
                data[f] = mask_value(v)
        return data

    # --- secure encrypted storage ------------------------------------------
    def secure_dict(self) -> Dict[str, Any]:
        """Return dict ready for DB storage (encrypted)."""
        data = self.model_dump()
        for f, v in data.items():
            if isinstance(v, str) and any(k in f.lower() for k in PII_KEYWORDS):
                data[f] = encrypt_value(v)
        return data

    def secure_json(self) -> str:
        return json.dumps(self.secure_dict(), ensure_ascii=False)

    # --- deterministic hashes for exact search -----------------------------
    def hash_fields(self) -> Dict[str, str]:
        data = {}
        for f, v in self.model_dump().items():
            if isinstance(v, str) and any(k in f.lower() for k in PII_KEYWORDS):
                data[f + "_hash"] = search_hash(v)
        return data

    # --- hashed n-grams for partial search ---------------------------------
    def searchable_index(self, n: int = 3) -> Dict[str, List[str]]:
        data = {}
        for f, v in self.model_dump().items():
            if isinstance(v, str) and any(k in f.lower() for k in PII_KEYWORDS):
                data[f + "_search"] = tokenize_for_search(v, n)
        return data

    # --- convenience combined for DB insert --------------------------------
    def db_record(self) -> Dict[str, Any]:
        """
        Return a full record for DB:
        - encrypted PII fields
        - _hash fields for exact lookup
        - _search tokens for partial lookup
        """
        rec = self.secure_dict()
        rec.update(self.hash_fields())
        rec.update(self.searchable_index())
        return rec

# ----------------------------------------------------------------------------
# 🧾 Example
# ----------------------------------------------------------------------------
class CustomerRecord(SecurePIIModel):
    customer_id: str
    full_name: str
    email: str
    phone_number: str
    address: str
    notes: str | None = Field(None)


if __name__ == "__main__":
    customer = CustomerRecord(
        customer_id="CUST123",
        full_name="Alice Johnson",
        email="alice@example.com",
        phone_number="+1 425 555 0199",
        address="123 Market Street, Seattle, WA",
        notes="VIP client"
    )

    print("\n🟢 Plain memory:")
    print(customer.model_dump())

    print("\n🔒 Ready for DB:")
    print(json.dumps(customer.db_record(), indent=2)[:500], "...\n")

    print("🔍 Example hash query:")
    print(" email_hash =", search_hash("alice@example.com"))

    print("\n🔍 Example partial search tokens (3-gram):")
    print(tokenize_for_search("alice", 3))
