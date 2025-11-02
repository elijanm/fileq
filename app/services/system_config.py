from pymongo import MongoClient
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional
from pymongo.database import Database


class SystemConfigService:
    _instance: Optional["SystemConfigService"] = None
    _lock = Lock()

    def __init__(self, db: Database):
       
        self.db = db
        self.collection = self.db["system_config"]
        self._cache: Dict[str, Any] = {}
        self._last_loaded: Optional[datetime] = None
        self.reload()

    # ---- Singleton Setup ----
    @classmethod
    def setup(cls,  db: Database):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db)
        return cls._instance

    @classmethod
    def instance(cls) -> "SystemConfigService":
        if cls._instance is None:
            raise RuntimeError("SystemConfigService not initialized. Call setup() first.")
        return cls._instance

    # ---- API Methods ----
    def reload(self):
        """Reload all configs from DB into memory."""
        configs = self.collection.find({})
        self._cache = {c["key"]: c["value"] for c in configs}
        self._last_loaded = datetime.utcnow()

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value from cache."""
        return self._cache.get(key, default)

    def set(self, key: str, value: Any, updated_by: str = "system"):
        """Update a config in DB and cache."""
        now = datetime.utcnow()
        self.collection.update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": now, "updated_by": updated_by}},
            upsert=True,
        )
        self._cache[key] = value

    def all(self) -> Dict[str, Any]:
        """Return all configs from cache."""
        return self._cache

    def last_loaded(self) -> Optional[datetime]:
        return self._last_loaded
