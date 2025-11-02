from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests, os

KETO_WRITE_URL = os.getenv("KETO_WRITE_URL", "http://keto:4467")
KETO_READ_URL = os.getenv("KETO_READ_URL", "http://keto:4466")

router = APIRouter(prefix="/user-roles", tags=["user-roles"])

# --------------------------
# Schemas
# --------------------------
class AssignRole(BaseModel):
    tenant: str
    user_id: str
    role: str  # owner, admin, member, guest


class CheckRole(BaseModel):
    tenant: str
    user_id: str
    role: str


# --------------------------
# Helpers
# --------------------------
def keto_write(tuple_: dict):
    r = requests.put(f"{KETO_WRITE_URL}/relation-tuples", json=tuple_)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()

def keto_check(payload: dict):
    r = requests.post(f"{KETO_READ_URL}/check", json=payload)
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.json())
    return r.json()

# --------------------------
# Endpoints
# --------------------------
@router.post("/assign")
def assign_role(body: AssignRole):
    """
    Assign a role to a user within a tenant.
    """
    tuple_ = {
        "namespace": "tenant",
        "object": body.tenant,
        "relation": f"role:{body.role}",
        "subject_id": f"user:{body.user_id}"
    }
    return keto_write(tuple_)

@router.post("/check")
def check_role(body: CheckRole):
    """
    Check if user has a specific role in a tenant.
    """
    payload = {
        "namespace": "tenant",
        "object": body.tenant,
        "relation": f"role:{body.role}",
        "subject_id": f"user:{body.user_id}"
    }
    return keto_check(payload)
