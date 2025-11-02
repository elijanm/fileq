
async def run(db):
    print("🚀 Initializing ticketing plugin schema...")
    # Example setup: create collection or table
    if hasattr(db, 'app'):
        await db.app.create_collection("ticketing")
    print("✅ ticketing plugin migration complete.")
