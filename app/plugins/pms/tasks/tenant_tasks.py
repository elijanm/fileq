import asyncio
import dramatiq
from bson import ObjectId
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from plugins.pms.utils.advanced_rent_analytics import AdvancedRentAnalytics
from workers.tasks import MONGO_URI
from core.scheduler_decorators import run_every_day,run_every_hour,run_every_minute

@run_every_hour
@dramatiq.actor
def test_hourly():
    """Entry point for Dramatiq (sync context)."""
    print(f"Called at {datetime.now(timezone.utc)}")
    
@run_every_minute
@dramatiq.actor
def daily_enrich_active_tenants():
    """Entry point for Dramatiq (sync context)."""
    asyncio.run(_async_daily_enrich_active_tenants())

@dramatiq.actor
def generate_custom_messaging(tenant_data):
    print(f"{tenant_data.get('tenant_name')} About to be customized")
    
async def _async_daily_enrich_active_tenants():
    """Runs inside its own event loop."""
    # ---- DB setup ----
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["fq_db"]
    analytics = AdvancedRentAnalytics(db)

    today = datetime.now(timezone.utc)

    # ---- MongoDB query (async) ----
    cursor = db.property_leases.find(
        {
            "status": "signed",
            "lease_terms.start_date": {"$lte": today},
            "lease_terms.end_date": {"$gte": today},
        },
        {"tenant_id": 1},
    )
    active_leases = await cursor.to_list(length=None)
    import threading,os
    # print(f"📅 Enriching {len(active_leases)} tenants with active leases...")
    print(f"📅 Enriching {len(active_leases)} tenants with active leases... "
      f"[pid={os.getpid()}, thread={threading.current_thread().name}]")

    # ---- iterate async results ----
    for lease in active_leases:
        tenant_id = ObjectId(lease["tenant_id"])
        

        results = await analytics.get_tenant_risk_score(tenant_id,print_=False)
        tenant_name=results.get("tenant_name")
        # Prepare meta payload
        meta_payload = {
            "risk_score": results.get("risk_score"),
            "risk_components": results.get("risk_components"),
            "finance_metrics": results.get("metrics"),
            "recommendations": results.get("recommendations"),
            "last_enriched": datetime.now(timezone.utc),
        }

        update_result = await db.property_tenants.update_one(
                {"_id": tenant_id},
                {
                    "$set": {
                        "meta.risk_score": results.get("risk_score"),
                        "meta.risk_components": results.get("risk_components"),
                        "meta.finance_metrics": results.get("metrics"),
                        "meta.recommendations": results.get("recommendations"),
                        "meta.last_enriched": datetime.now(timezone.utc),
                    }
                },
            )
        if update_result.matched_count or update_result.upserted_id:
            print(f"✅ Updated meta for tenant {tenant_name}")
        else:
            print(f"⚠️ Tenant not found: {tenant_name}")
        generate_custom_messaging.send(results)

    client.close()
    print("✅  Finished enrichment")
