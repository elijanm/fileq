from datetime import datetime, timedelta,timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException

class PropertySnapshotService:
    """
    Maintains cached structural data (properties + units) per owner.
    Snapshot type: 'properties'
    Cache key: owner_id
    """

    def __init__(self, db, ttl_hours: int = 24):
        self.db = db
        self.snapshots = db.system_snapshots
        self.properties = db.properties
        self.units = db.units
        self.ttl = timedelta(hours=ttl_hours)
        self.snapshot_type = "properties"

    async def _get_cached(self, owner_id: str):
        """Fetch existing properties snapshot if valid."""
        now = datetime.now(timezone.utc)
        return await self.snapshots.find_one({
            "type": self.snapshot_type,
            "period_key": owner_id,
            "created_at": {"$gte": now - self.ttl}
        })

    async def _save_snapshot(self, owner_id: str, properties: list):
        """Save refreshed property snapshot."""
        doc = {
            "type": self.snapshot_type,
            "period_key": owner_id,
            "created_at": datetime.now(timezone.utc),
            "data": {
                "properties": properties,
                "meta": {"generated_at": datetime.now(timezone.utc).isoformat()}
            }
        }
        await self.snapshots.insert_one(doc)
        print(f"💾 Property snapshot cached for owner {owner_id}")
        return doc

    async def _build_property_snapshot(self, owner_id: str) -> list:
        """Fetch property and unit structure."""
        props = [p async for p in self.properties.find({"owner_id": owner_id})]
        if not props:
            raise HTTPException(status_code=404, detail="No properties found")

        prop_ids = [p["_id"] for p in props]
        units = [u async for u in self.units.find({"property_id": {"$in": prop_ids}})]

        units_by_prop = {}
        for u in units:
            pid = u["property_id"]
            units_by_prop.setdefault(pid, []).append({
                "_id": str(u["_id"]),
                "unit_number":u.get("unitNumber"),
                "unit_name": u.get("unitName"),
                "status": u.get("status"),
                "rent": u.get("rentAmount")
            })

        for p in props:
            p["_id"] = str(p["_id"])
            p["units"] = units_by_prop.get(p["_id"], [])
            p.pop("owner_id", None)  # don't expose internal field

        return props
    def prepare_data(self,doc,summarize=True):
        if summarize:
            snapshot=doc["data"]
            return [{
                "id":u.get("_id"),
                "name":u.get("name"),
                "type":u.get("propertyType"),
                "location":u.get("location"),
                "total_units":u.get("unitsTotal"),
                "units_occupied":u.get("unitsOccupied"),
                "units":u.get("units")
            }for u in snapshot.get("properties")]
        return doc["data"]
        
    async def get_or_refresh_snapshot(self, owner_id: str,summarize=True) -> dict:
        """Return cached or fresh property snapshot for a user."""
        cached = await self._get_cached(owner_id)
        if cached:
            print(f"✅ Property cache hit for {owner_id}")
            return self.prepare_data(cached,summarize)

        props = await self._build_property_snapshot(owner_id)
        doc = await self._save_snapshot(owner_id, props)
        return self.prepare_data(cached,summarize)

    async def invalidate_snapshot(self, owner_id: str):
        """Delete cached snapshot if property/unit structure changes."""
        res = await self.snapshots.delete_many({
            "type": self.snapshot_type,
            "period_key": owner_id
        })
        print(f"🧹 Deleted {res.deleted_count} cached property snapshot(s) for {owner_id}")
