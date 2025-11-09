from __future__ import annotations
from typing import List, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from bson import ObjectId

# --- Utilities ---
class PyObjectId(ObjectId):
    """Enable ObjectId fields in Pydantic."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        try:
            return ObjectId(str(v))
        except Exception:
            raise ValueError("Invalid ObjectId")

# --- Submodels ---
class SharedAccess(BaseModel):
    entity_type: Literal["user", "branch", "organization"]
    entity_id: str
    role: Literal["viewer", "manager", "admin", "editor"] = "viewer"

class OwnerModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    type: Literal["organization", "user", "branch"]
    entity_id: str
    access: Literal["restricted", "organization", "open"] = "restricted"
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class XYZModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    owner_id: PyObjectId
    shared_with: List[SharedAccess] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=lambda: ["read"])
    created_at: datetime = Field(default_factory=datetime.utcnow)
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import HTTPException

class AccessService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.owners = db["owners"]

    # --- Create an Owner ---
    async def create_owner(self, owner: OwnerModel) -> dict:
        owner_dict = owner.model_dump(by_alias=True, exclude_none=True)
        res = await self.owners.insert_one(owner_dict)
        owner_dict["_id"] = res.inserted_id
        return owner_dict

    # --- Create a new document under ownership ---
    async def create_xyz(self, data: XYZModel) -> dict:
        exists = await self.owners.count_documents({"_id": data.owner_id})
        if not exists:
            raise HTTPException(status_code=400, detail="Invalid owner_id")

        doc = data.model_dump(by_alias=True, exclude_none=True)
        result = await self.db["xyz"].insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    # --- Authorization check ---
    async def can_access(self, user: dict, doc: dict) -> bool:
        owner = await self.owners.find_one({"_id": doc["owner_id"]})
        if not owner:
            return False

        access = owner.get("access", "restricted")
        org_id = user.get("org_id")
        user_id = user.get("id")
        branches = user.get("branches", [])

        # --- Open access ---
        if access == "open":
            return True

        # --- Org-wide access ---
        if access == "organization" and owner["entity_id"] == org_id:
            return True

        # --- Restricted: check shared_with ---
        if access == "restricted":
            for shared in doc.get("shared_with", []):
                if shared["entity_id"] in [user_id, *branches]:
                    return True

        return False

    # --- Fetch all accessible docs for a user ---
    async def get_accessible_xyz(self, user: dict) -> list[dict]:
        org_id = user.get("org_id")
        user_id = user.get("id")
        branches = user.get("branches", [])

        # Step 1: Get accessible owners
        owner_filter = {
            "$or": [
                {"entity_id": org_id, "access": {"$in": ["organization", "open"]}},
                {"access": "open"}
            ]
        }
        owner_ids = await self.owners.distinct("_id", owner_filter)

        # Step 2: Fetch docs
        cursor = self.db["xyz"].find({
            "$or": [
                {"owner_id": {"$in": owner_ids}},
                {"shared_with.entity_id": user_id},
                {"shared_with.entity_id": {"$in": branches}}
            ]
        })
        return [d async for d in cursor]
    
    
    
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

router = APIRouter()

@router.post("/owners")
async def create_owner(owner: OwnerModel, db: AsyncIOMotorDatabase = Depends(...)):
    service = AccessService(db)
    return await service.create_owner(owner)

@router.post("/xyz")
async def create_xyz(data: XYZModel, db: AsyncIOMotorDatabase = Depends(...)):
    service = AccessService(db)
    return await service.create_xyz(data)

@router.get("/xyz")
async def list_accessible_xyz(db: AsyncIOMotorDatabase = Depends(...), current_user: dict = Depends(...)):
    service = AccessService(db)
    docs = await service.get_accessible_xyz(current_user)
    return docs
