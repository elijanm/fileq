from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from bson import ObjectId
import random, string


def generate_reference(prefix: str = "TCK") -> str:
    """Generate a memorable alphanumeric reference like TCK-20251009-AB3F."""
    date_part = datetime.utcnow().strftime("%Y%m%d")
    rand_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}-{date_part}-{rand_part}"

class PyObjectId(ObjectId):
    """For serializing Mongo ObjectIds to strings."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    @classmethod
    def validate(cls, v):
        return str(v) if isinstance(v, ObjectId) else v
class Comment(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    author: str = Field(..., example="elijah@nexidra.com")
    message: str = Field(..., example="Investigating the issue now.")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    internal: bool = Field(default=False, description="Visible only to staff if True")

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
        
class TicketCreate(BaseModel):
    title: str = Field(..., example="Database latency issue")
    description: str = Field(..., example="Queries are timing out after 5s under load.")
    status: Literal["open", "in_progress", "resolved", "closed","reopened"] = Field("open", example="open")
    priority: Literal["low", "medium", "high", "urgent"] = Field("medium", example="high")
    category: Optional[str] = Field(None, example="Backend")
    
class Ticket(TicketCreate):
    id: Optional[str] = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    reference: str = Field(default_factory=generate_reference, example="TCK-20251009-AB3F")
    
    assigned_to: Optional[str] = None  # could be a user ID
    created_by: str
    comments: List[Comment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {ObjectId: str}
        populate_by_name = True
        
