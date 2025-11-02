from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from semver import VersionInfo
import json, importlib
from core.database import get_database
from core.plugin_loader import reload_user_plugins
from core.registry_client import RegistryClient
from core.auth import get_current_user  # your existing auth dependency

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

# -------------------------------
# Helper
# -------------------------------
async def get_registry_plugin(name: str):
    client = RegistryClient()
    manifest = await client.get_plugin_manifest(name)
    await client.close()
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found in registry.")
    return manifest

# -------------------------------
# 1️⃣ Install Plugin
# -------------------------------
@router.post("/install/{plugin_name}")
async def install_plugin(plugin_name: str, user=Depends(get_current_user)):
    db = await anext(get_database())
    registry_plugin = await get_registry_plugin(plugin_name)
    pricing = registry_plugin.get("pricing", {"type": "free"})
    minimum_subscription = registry_plugin.get("minimum_subscription", {"required": False})
    
    # 🔒 Step 1: Validate required subscription
    if minimum_subscription.get("required",False):
        # lago = LagoClient()
        # subs = await lago.list_customer_subscriptions(str(user.id))
        subs={}
        has_required = any(
            s["plan_code"] == minimum_subscription["plan_id"] for s in subs.get("subscriptions", [])
        )
        # await lago.close()
        if not has_required:
            raise HTTPException(
                status_code=402,
                detail=f"⚠️ You must have an active '{minimum_subscription['plan_id']}' subscription to install this plugin."
            )

    # 💳 Step 2: Handle billing for the plugin itself (if it’s paid)
    if pricing["type"] in ["subscription", "one_time"]:
        # lago = LagoClient()
        pass
        # customer_id = await lago.ensure_customer(user)
        if pricing["type"] == "subscription":
            # await lago.subscribe_customer(customer_id, pricing["plan_id"])
            pass
        else:
            # await lago.create_one_time_charge(customer_id, plugin_name, pricing)
            pass
        # await lago.close()

    # 🧱 Step 3: Register plugin to DB
    user_plugin = {
        "user_id": user.id,
        "plugin_name": plugin_name,
        "version": registry_plugin["version"],
        "installed_at": datetime.utcnow().isoformat(),
        "enabled": True,
        "billing": {
            "model": pricing["type"],
            "plan_id": pricing.get("plan_id"),
            "active": pricing["type"] == "free",
            "verified": pricing["type"] == "free",
        },
        "requires_subscription": requirement,
    }
    await db["user_plugins"].insert_one(user_plugin)
    await reload_user_plugins(user.id)
    return {
        "message": f"✅ Installed {plugin_name} ({pricing['type']}) for {user.email}",
        "requires_subscription": requirement
    }


# -------------------------------
# 2️⃣ Uninstall Plugin
# -------------------------------
@router.delete("/uninstall/{plugin_name}")
async def uninstall_plugin(plugin_name: str, user=Depends(get_current_user)):
    db = await anext(get_database())
    result = await db["user_plugins"].delete_one({"user_id": user.id, "plugin_name": plugin_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Plugin not installed.")
    await reload_user_plugins(user.id)
    return {"message": f"🗑️ Uninstalled plugin '{plugin_name}'"}

# -------------------------------
# 3️⃣ Upgrade Plugin
# -------------------------------
@router.post("/upgrade/{plugin_name}")
async def upgrade_plugin(plugin_name: str, user=Depends(get_current_user)):
    db = await anext(get_database())
    installed = await db["user_plugins"].find_one({"user_id": user.id, "plugin_name": plugin_name})
    if not installed:
        raise HTTPException(status_code=404, detail="Plugin not installed.")

    registry_plugin = await get_registry_plugin(plugin_name)
    current_version = VersionInfo.parse(installed["version"])
    new_version = VersionInfo.parse(registry_plugin["version"])

    if new_version <= current_version:
        raise HTTPException(status_code=400, detail="Already up to date or newer.")

    await db["user_plugins"].update_one(
        {"_id": installed["_id"]},
        {"$set": {"version": str(new_version), "updated_at": datetime.utcnow().isoformat()}}
    )
    await reload_user_plugins(user.id)
    return {"message": f"🔼 Upgraded {plugin_name} to {new_version}"}

# -------------------------------
# 4️⃣ Downgrade Plugin
# -------------------------------
@router.post("/downgrade/{plugin_name}")
async def downgrade_plugin(plugin_name: str, user=Depends(get_current_user)):
    db = await anext(get_database())
    installed = await db["user_plugins"].find_one({"user_id": user.id, "plugin_name": plugin_name})
    if not installed:
        raise HTTPException(status_code=404, detail="Plugin not installed.")

    # Check registry for available versions
    client = RegistryClient()
    available_versions = await client.list_versions(plugin_name)
    await client.close()

    current_version = VersionInfo.parse(installed["version"])
    prev_versions = [VersionInfo.parse(v) for v in available_versions if VersionInfo.parse(v) < current_version]
    if not prev_versions:
        raise HTTPException(status_code=400, detail="No previous version available.")

    prev_version = max(prev_versions)
    await db["user_plugins"].update_one(
        {"_id": installed["_id"]},
        {"$set": {"version": str(prev_version), "updated_at": datetime.utcnow().isoformat()}}
    )
    await reload_user_plugins(user.id)
    return {"message": f"⬇️ Downgraded {plugin_name} to {prev_version}"}

# -------------------------------
# 5️⃣ List My Plugins
# -------------------------------
@router.get("/my")
async def list_my_plugins(user=Depends(get_current_user)):
    db = await anext(get_database())
    plugins = await db["user_plugins"].find({"user_id": user.id}).to_list(None)
    return plugins
