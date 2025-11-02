
async def run(db):
    print("🚀 Initializing heatmap plugin schema...")
    await db.create_collection("heatmap_events")
    print("✅ heatmap_events collection created.")
