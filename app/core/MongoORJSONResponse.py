import orjson
from fastapi.responses import ORJSONResponse
from bson import ObjectId
from datetime import datetime, date

def normalize_bson(obj):
    """Recursively convert ObjectId, datetime, and date to JSON-safe types."""
    if isinstance(obj, list):
        return [normalize_bson(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: normalize_bson(v) for k, v in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

def bson_default(obj):
    """Recursively handle BSON, datetime, and common Python types for safe ORJSON serialization."""
    # --- BSON ObjectId ---
    if isinstance(obj, ObjectId):
        return str(obj)

    # --- Dates / Datetimes ---
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()

    # --- Lists / Tuples / Sets ---
    if isinstance(obj, (list, tuple, set)):
        return [bson_default(item) for item in obj]

    # --- Dicts ---
    if isinstance(obj, dict):
        return {k: bson_default(v) for k, v in obj.items()}

    # --- Optionally handle Decimal / UUID ---
    # from decimal import Decimal
    # from uuid import UUID
    # if isinstance(obj, Decimal):
    #     return float(obj)
    # if isinstance(obj, UUID):
    #     return str(obj)

    # --- Fallback: Try to serialize model-like objects ---
    if hasattr(obj, "model_dump"):
        return bson_default(obj.model_dump())
    if hasattr(obj, "__dict__"):
        return bson_default(vars(obj))

    # --- Unknown types ---
    return str(obj)

class MongoORJSONResponse(ORJSONResponse):
    def render(self, content) -> bytes:
        return orjson.dumps(content, default=bson_default)

