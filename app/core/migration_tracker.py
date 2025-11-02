import datetime

class MigrationTracker:
    """Tracks applied migrations in MongoDB (_migrations collection)."""

    def __init__(self, db):
        self.db = db
        self.collection = db["_migrations"]

    async def record_migration(self, plugin, version, file_name):
        await self.collection.insert_one({
            "plugin": plugin,
            "version": version,
            "file": file_name,
            "applied_at": datetime.datetime.utcnow(),
        })

    async def mark_rollback(self, plugin, version):
        await self.collection.update_one(
            {"plugin": plugin, "version": version},
            {"$set": {"rolled_back": True, "rolled_back_at": datetime.datetime.utcnow()}}
        )

    async def get_applied(self, plugin):
        return await self.collection.find({"plugin": plugin, "rolled_back": {"$ne": True}}).sort("applied_at", 1).to_list(None)

    async def get_last_applied(self, plugin):
        result = await self.collection.find({"plugin": plugin, "rolled_back": {"$ne": True}}).sort("applied_at", -1).limit(1).to_list(1)
        return result[0] if result else None
