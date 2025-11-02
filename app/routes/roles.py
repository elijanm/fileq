from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import requests, os

KETO_READ_URL = os.getenv("KETO_READ_URL", "http://keto:4466")
KETO_WRITE_URL = os.getenv("KETO_WRITE_URL", "http://keto:4467")

router = APIRouter(prefix="/roles", tags=["roles"])

# --------------------------
# Schemas
# --------------------------
class RoleCreate(BaseModel):
    tenant: str
    role: str
    permissions: list[str]  # e.g., ["upload:file", "delete:file"]


class AssignRole(BaseModel):
    tenant: str
    role: str
    user_id: str


class PermissionCheck(BaseModel):
    user_id: str
    action: str
    object_id: str
    namespace: str = "fileq"


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

@router.post("")
def create_role(body: RoleCreate):
    """
    Define a new role in a tenant by mapping it to permissions.
    This stores relation-tuples in Keto like:
    role:admin has relation upload:file on tenant:xyz
    """
    results = []
    for perm in body.permissions:
        tuple_ = {
            "namespace": "tenant",
            "object": body.tenant,
            "relation": f"role:{body.role}",
            "subject_id": f"perm:{perm}"
        }
        results.append(keto_write(tuple_))
    return {"msg": "Role created", "role": body.role, "results": results}


@router.post("/assign")
def assign_role(body: AssignRole):
    """
    Assign role to a user in a tenant.
    Stores tuple: user:X has relation role:admin on tenant:Y
    """
    tuple_ = {
        "namespace": "tenant",
        "object": body.tenant,
        "relation": f"role:{body.role}",
        "subject_id": f"user:{body.user_id}"
    }
    return keto_write(tuple_)


@router.post("/check")
def check_permission(body: PermissionCheck):
    """
    Check if a user has a permission on an object.
    """
    payload = {
        "namespace": body.namespace,
        "object": body.object_id,
        "relation": body.action,
        "subject_id": f"user:{body.user_id}"
    }
    result = keto_check(payload)
    return {"allowed": result.get("allowed", False)}
