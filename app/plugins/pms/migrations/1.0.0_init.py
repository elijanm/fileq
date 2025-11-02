
async def run(db):
    print("🚀 Initializing pms plugin schema...")
    # Example setup: create collection or table
    if hasattr(db, 'app'):
        await db.app.create_collection("pms")
        await db["invoices"].create_index([("tenant_id", 1), ("month", 1)])
        await db["units"].create_index("property_id")
        await db["payments"].create_index("invoice_id")
        
    print("✅ pms plugin migration complete.")
