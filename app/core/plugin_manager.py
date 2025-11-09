import json, shutil, requests, importlib.util
from pathlib import Path
import importlib
from fastapi import FastAPI
from core.config import settings
from core.database import get_database
from core.security import verify_signature
from rich.console import Console

console = Console()
PLUGIN_DIR = Path(__file__).resolve().parent.parent / "plugins"
BACKUP_DIR = Path(__file__).resolve().parent.parent / ".plugin_backups"
BACKUP_DIR.mkdir(exist_ok=True)


async def reload_user_plugins(user_id: str):
    """Reload plugins for a given user without restarting the app."""
    from core.database import get_database
    db = await anext(get_database())
    user_plugins = await db["user_plugins"].find({"user_id": user_id, "enabled": True}).to_list(None)

    app: FastAPI = FastAPI._get_current_object() if hasattr(FastAPI, "_get_current_object") else None
    if not app:
        console.print("[red]App context not found for plugin reload[/red]")
        return

    for up in user_plugins:
        
        req = up.get("minimum_subscription", {"required": False})
        if req.get("required") and not up["billing"].get("verified"):
            print(f"🔒 Skipping {up['plugin_name']} — subscription inactive")
            continue 
        
        plugin_name = up["plugin_name"]
        try:
            mod = importlib.import_module(f"plugins.{plugin_name}.plugin")
            init_func = getattr(mod, "init_plugin", None)
            if init_func:
                router = init_func().get("router")
                prefix = f"/u/{user_id}/plugins/{plugin_name}"
                app.include_router(router, prefix=prefix, tags=[plugin_name])
                console.print(f"[green]✅ Reloaded plugin {plugin_name} for user {user_id}[/green]")
        except Exception as e:
            console.print(f"[red]❌ Error loading {plugin_name}: {e}[/red]")
            
async def discover_plugins():
    """Scan local plugins, insert into DB if missing"""
    db_gen = get_database()
    db = await anext(db_gen)
    col = db.plugins
    
    seen = set()
    deleted = 0
    
    cursor =  col.find({})
    async for c in cursor:
        name= c.get("name")
        if not name:
            continue

        if name in seen:
            await col.delete_one({"_id": c.get("_id")})
            deleted += 1
        else:
            seen.add(name)
            
    if deleted>0:
         print(f"✅ Deleted {deleted} duplicate documents.")
    
    for module in PLUGIN_DIR.iterdir():
        if not module.is_dir():
            continue
        manifest_file = module / "plugin.json"
        if not manifest_file.exists():
            continue
        data = json.loads(manifest_file.read_text())
        existing = await col.find_one({"name": data["name"]})
        if not existing:
            print(f"🆕 Discovered new plugin: {data['name']}")
            await col.insert_one(data)
    await db_gen.aclose()
    print("🔍 Local discovery complete.")

async def verify_and_install_from_registry(name: str):
    """Fetch plugin from internal registry, verify, and install."""
    db_gen = get_database()
    db = await anext(db_gen)
    
    url = f"{settings.REGISTRY_URL}/plugins/{name}/latest"
    res = requests.get(url)
    plugin_data = res.json()
    archive_url = plugin_data["download_url"]
    signature = bytes.fromhex(plugin_data["signature"])
    zip_data = requests.get(archive_url).content

    if not verify_signature(zip_data, signature):
        raise ValueError("Plugin verification failed.")

    # Save plugin zip
    zip_path = BACKUP_DIR / f"{name}.zip"
    zip_path.write_bytes(zip_data)
    shutil.unpack_archive(zip_path, PLUGIN_DIR)

    await db.plugins.update_one(
        {"name": name},
        {"$set": {
            "verified": True,
            "version": plugin_data["version"],
            "source": "registry",
            "checksum": plugin_data["checksum"]
        }},
        upsert=True
    )
    await db_gen.aclose()
    print(f"✅ Plugin {name} installed and verified.")
