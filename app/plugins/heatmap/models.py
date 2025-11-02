from pydantic import BaseModel

class HeatmapModel(BaseModel):
    id: str
    created_at: str
    data: dict
