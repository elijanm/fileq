from pydantic import BaseModel
from enum import Enum
from typing import Literal

class TasksModel(BaseModel):
    id: str
    created_at: str
    data: dict
    
class Provider(str, Enum):
    telenyx = "telenyx"
    twilio = "twilio"
    telnyx = "telnyx"
    nexmo = "nexmo"

ValidStatus = Literal["success", "queue", "failed"]