import os
import pkgutil
import importlib
import json
from pathlib import Path
from fastapi import FastAPI
from core.database import get_database
from models.plugin_model import Plugin
from core.permissions import register_permissions
from loguru import logger
from pymongo import DESCENDING
from fastapi.staticfiles import StaticFiles


async def discover_and_register_plugins(app: FastAPI):
    """
    Discover, register, and load plugins dynamically into the FastAPI app.

    Modes:
    - DEV: load only the latest version of each plugin from /plugins directory.
    - PROD: load only the versions installed by users (from user_plugins collection).
    """

    env = os.getenv("APP_ENV", "development").lower()
    logger.info(f"🔍 Starting plugin discovery in {env.upper()} mode...")

    plugins_path = Path(__file__).resolve().parent.parent / "plugins"
    db_gen = get_database()
    db = await anext(db_gen)
    plugin_collection = db["plugins"]
    user_plugins = db["user_plugins"]  # stores user-installed versions

    loaded_plugins = set()
    discovered = 0

    if not plugins_path.exists():
        logger.warning(f"⚠️ Plugins directory not found: {plugins_path}")
        await db_gen.aclose()
        return list(loaded_plugins)

    # -------------------------------------------------
    # 🧪 DEV MODE: load only the latest version of each plugin
    # -------------------------------------------------
    if env in ("dev", "development"):
        for module in pkgutil.iter_modules([str(plugins_path)]):
            if not module.ispkg:
                continue

            plugin_dir = plugins_path / module.name
            manifest_file = plugin_dir / "plugin.json"
            perms_file = plugin_dir / "permissions.json"

            if not manifest_file.exists():
                logger.warning(f"⚠️ Missing manifest for plugin: {module.name}")
                continue

            try:
                manifest = json.loads(manifest_file.read_text())
            except Exception as e:
                logger.error(f"❌ Failed to parse manifest for {module.name}: {e}")
                continue

            permissions = []
            if perms_file.exists():
                try:
                    permissions = json.loads(perms_file.read_text())
                except Exception as e:
                    logger.warning(f"⚠️ Failed to parse permissions.json for {module.name}: {e}")

            existing = await plugin_collection.find_one({"name": manifest["name"]})
            if not existing:
                logger.info(f"🆕 Registering new plugin: {manifest['name']}")
                manifest["permissions"] = permissions
                await plugin_collection.insert_one(Plugin(**manifest).model_dump())
            else:
                logger.debug(f"✅ Plugin already registered: {manifest['name']}")
            discovered += 1

        # Load only the latest version of each enabled plugin
        plugin_names = await plugin_collection.distinct("name", {"enabled": True})
        for plugin_name in plugin_names:
            plugin = await plugin_collection.find_one(
                {"name": plugin_name, "enabled": True},
                sort=[("published_at", DESCENDING)],
            )
            if not plugin:
                continue

            try:
                module_path = f"plugins.{plugin_name}.plugin"
                plugin_module = importlib.import_module(module_path)

                if not hasattr(plugin_module, "init_plugin"):
                    logger.warning(f"⚠️ Plugin {plugin_name} missing init_plugin()")
                    continue
                
                # ✅ Register static directory at app level
                base_dir = Path(__file__).resolve().parent.parent  # points to your app/ folder
                plugin_static_path = base_dir / f"plugins/{plugin_name}/static"
                if plugin_static_path.exists():
                    static_mount = f"/{plugin_name}/static"
                    app.mount(
                        static_mount,
                        StaticFiles(directory=str(plugin_static_path)),
                        name=f"plugin_{plugin_name}_static"
                    )
                    logger.info(f"✅ Mounted static for {plugin_name} at {static_mount}")
                else:
                    print("dne")

                plugin_instance = plugin_module.init_plugin(app)
                router = plugin_instance.get("router")

                if router:
                    app.include_router(
                        router,
                        prefix=f"/{plugin_name}",
                        tags=[plugin_name],
                    )

                register_permissions(plugin_name, plugin.get("permissions", []))
                loaded_plugins.add(plugin_name)
                logger.info(f"🧩 Loaded plugin (DEV latest): {plugin_name} ({plugin['version']})")

            except Exception as e:
                logger.exception(f"❌ Failed to load plugin {plugin_name}: {e}")

    # -------------------------------------------------
    # 🚀 PROD MODE: load only user-installed versions
    # -------------------------------------------------
    else:
        # Each user may have different plugin versions installed
        user_plugin_records = (
            await user_plugins.find({"active": True}).to_list(None)
        )

        # Map of {plugin_name: installed_version}
        user_plugin_map = {
            rec["plugin_name"]: rec["installed_version"]
            for rec in user_plugin_records
        }

        for plugin_name, version in user_plugin_map.items():
            plugin = await plugin_collection.find_one(
                {"name": plugin_name, "version": version, "verified": True}
            )
            if not plugin:
                logger.warning(f"⚠️ No verified plugin {plugin_name}@{version} found.")
                continue

            try:
                module_path = f"plugins.{plugin_name}.plugin"
                plugin_module = importlib.import_module(module_path)

                if not hasattr(plugin_module, "init_plugin"):
                    logger.warning(f"⚠️ Plugin {plugin_name} missing init_plugin()")
                    continue

                plugin_instance = plugin_module.init_plugin(app)
                router = plugin_instance.get("router")

                if router:
                    app.include_router(
                        router,
                        prefix=f"/{plugin_name}",
                        tags=[plugin_name],
                    )

                register_permissions(plugin_name, plugin.get("permissions", []))
                loaded_plugins.add(f"{plugin_name}@{version}")
                logger.info(f"🧩 Loaded plugin (PROD user-installed): {plugin_name}@{version}")

            except Exception as e:
                logger.exception(f"❌ Failed to load plugin {plugin_name}@{version}: {e}")

    # -------------------------------------------------
    # ✅ Cleanup
    # -------------------------------------------------
    await db_gen.aclose()
    logger.info(f"✅ Plugin discovery complete — {len(loaded_plugins)} loaded, {discovered} discovered.")
    return list(loaded_plugins)
