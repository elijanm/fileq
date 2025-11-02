from pydantic import BaseModel
from typing import Optional, List

class RegistryPlugin(BaseModel):
    name: str
    version: str
    author: str
    description: Optional[str]
    verified: bool
    checksum: str
    signature: str
    download_url: str
