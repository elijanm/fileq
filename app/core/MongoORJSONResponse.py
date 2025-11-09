import orjson
from fastapi.responses import ORJSONResponse
from bson import ObjectId
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Any
from bson import ObjectId
from pydantic_core import core_schema
import logging 

logger = logging.getLogger("bson_debug")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s")
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)
    

class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        return core_schema.no_info_after_validator_function(
            cls.validate,
            core_schema.union_schema([
                core_schema.str_schema(),
                core_schema.is_instance_schema(ObjectId)
            ])
        )

    @classmethod
    def validate(cls, v: Any, info: Any = None) -> ObjectId:
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {"type": "string"}
class MongoModel(BaseModel):
    # model_config = ConfigDict(
    #     populate_by_name=True,
    #     arbitrary_types_allowed=True,
    #     extra="ignore",
    #     ser_json_timedelta="iso8601",
    # )
    model_config = {
        "populate_by_name":True,
        "json_encoders": {
            ObjectId: str,
            PyObjectId: str,
        }
    }

    @field_serializer("*", when_used="json", check_fields=False)
    def serialize_objectid(cls, value):
        if isinstance(value, ObjectId):
            return str(value)
        return value

def normalize_bson(obj):
    """Recursively convert ObjectId, datetime, and date to JSON-safe types."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(by_alias=True)
    if isinstance(obj, list):
        return [normalize_bson(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: normalize_bson(v) for k, v in obj.items()}
    elif isinstance(obj, (ObjectId,PyObjectId)):
        return str(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

def bson_default(obj: Any) -> Any:
    """
    Recursively converts BSON / non-JSON types into serializable ones.
    Logs every conversion step for debugging.
    """
    t = type(obj)
    # --- Mongo ObjectId ---
    if isinstance(obj, ObjectId):
        logger.debug(f"Converting ObjectId → str: {obj}")
        return str(obj)

    # --- Datetime / Date ---
    if isinstance(obj, (datetime, date)):
        logger.debug(f"Converting datetime/date → ISO string: {obj}")
        return obj.isoformat()

    # --- Collections ---
    if isinstance(obj, (list, tuple, set)):
        logger.debug(f"Normalizing {t.__name__} with {len(obj)} elements")
        return [bson_default(i) for i in obj]

    # --- Dicts ---
    if isinstance(obj, dict):
        logger.debug(f"Normalizing dict with keys: {list(obj.keys())[:5]}")
        return {str(k): bson_default(v) for k, v in obj.items()}

    # --- Pydantic models ---
    if hasattr(obj, "model_dump"):
        logger.debug(f"Dumping Pydantic model: {obj.__class__.__name__}")
        try:
            return bson_default(obj.model_dump(by_alias=True))
        except Exception as e:
            logger.warning(f"model_dump() failed on {obj}: {e}")
            return bson_default(vars(obj))

    # --- Dataclasses / Generic objects ---
    if hasattr(obj, "__dataclass_fields__") or hasattr(obj, "__dict__"):
        logger.debug(f"Serializing object of type {t.__name__} via __dict__")
        return bson_default(vars(obj))

    # --- Iterators (e.g., Motor cursor) ---
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes, dict)):
        try:
            iterable_list = list(obj)
            logger.debug(f"Serializing iterable {t.__name__} of size {len(iterable_list)}")
            return [bson_default(i) for i in iterable_list]
        except Exception as e:
            logger.warning(f"Failed to iterate over {t.__name__}: {e}")

    # --- Fallback ---
    logger.debug(f"Falling back to str() for {t.__name__}: {obj}")
    return str(obj)
# -------------------------------------------------------------------
# ✅ Universal ORJSONResponse for FastAPI that supports MongoDB data
# -------------------------------------------------------------------
class MongoORJSONResponse(ORJSONResponse):
    """
    Global ORJSONResponse with detailed logging for BSON and nested structures.
    """
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        logger.info("🔹 Starting MongoORJSONResponse.render()")
        try:
            normalized = bson_default(content)
            logger.info("✅ Normalization complete, serializing with ORJSON")
            return orjson.dumps(normalized)
        except Exception as e:
            logger.error(f"❌ Normalization failed: {e}")
            logger.debug(f"Raw content type: {type(content)} → value: {repr(content)}")
            return orjson.dumps(content, default=bson_default)
# class MongoORJSONResponse(ORJSONResponse):
#     """
#     Global response class that serializes ObjectId, datetime, and other non-JSON-safe types.
#     You can set this as FastAPI’s default response class.
#     """
#     media_type = "application/json"

#     def render(self, content: Any) -> bytes:
#         # Normalize any lazy iterables like Motor cursors
#         if hasattr(content, "__aiter__") or hasattr(content, "__iter__") and not isinstance(content, (dict, list, str)):
#             try:
#                 content = list(content)
#             except Exception:
#                 pass
#         return orjson.dumps(content, default=bson_default)

