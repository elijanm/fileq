
async def run(db):
    print("🚀 Initializing tasks plugin schema...")
    # Example setup: create collection or table
    if hasattr(db, 'app'):
        await db.app.create_collection("tasks")
    print("✅ tasks plugin migration complete.")
