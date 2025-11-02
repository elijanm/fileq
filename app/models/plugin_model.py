from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Plugin(BaseModel):
    name: str
    display_name: str
    version: str
    author: str
    description: Optional[str]
    enabled: bool = True
    verified: bool = False
    source: Optional[str] = None  # registry/github/local
    repo_url: Optional[str] = None
    checksum: Optional[str] = None
    permissions: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
