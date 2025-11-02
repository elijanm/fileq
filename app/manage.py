#!/usr/bin/env python3
"""
Nexidra Plugin Manager CLI
---------------------------------
Manage local, registry, and verified plugins for the Nexidra modular system.
Usage:
    python manage.py plugin list
    python manage.py plugin discover
    python manage.py plugin install sms
    python manage.py plugin upgrade sms
    python manage.py plugin rollback sms
    python manage.py plugin verify-all
    python manage.py marketplace sync
"""

import asyncio
import sys
import os
import json
from rich.console import Console
from rich.table import Table
from pathlib import Path
from inspect import iscoroutinefunction
from datetime import  datetime,timezone
import argparse
import textwrap
import shutil
from zipfile import ZipFile
from dotenv import load_dotenv

# Local imports
from core.plugin_manager import discover_plugins, verify_and_install_from_registry
from core.database import get_database,db_manager
from core.config import settings

COMMANDS = {}
def command(category: str, name: str, description: str=None):
    """
    Decorator to auto-register CLI commands.
    Example:
        @command("plugin", "list", "List all installed plugins")
        async def list_plugins(): ...
    """
    def decorator(func):
        doc = (func.__doc__ or "").strip().splitlines()[0] if not description else description
        COMMANDS.setdefault(category, {})[name] = {
            "func": func,
            "description": doc,
        }
        return func
    return decorator


console = Console()
PLUGIN_DIR = Path(__file__).resolve().parent / "plugins"
BACKUP_DIR = Path(__file__).resolve().parent / ".plugin_backups"

load_dotenv()

# ---------------------------
# HELP / COMMAND SUMMARY
# ---------------------------

def show_help_dynamic():
    from rich.panel import Panel
    from rich.markdown import Markdown
    console.print(Panel.fit("[bold cyan]🧠 Nexidra CLI — Auto-Generated Help[/bold cyan]\n"))

    for category, cmds in COMMANDS.items():
        table = Table(title=f"[bold]{category.capitalize()} Commands[/bold]", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="white")
        for name, meta in cmds.items():
            table.add_row(name, meta["description"])
        console.print(table)

    console.print("\n💡 Example:\n[green]python manage.py plugin list[/green]")
    console.print("[dim]Run 'python manage.py help' anytime to regenerate this list.[/dim]")
    (Path(__file__).parent / "CLI_COMMANDS.md").write_text(
        "\n".join(f"{cat}:{cmd} - {meta['description']}" for cat, cmds in COMMANDS.items() for cmd, meta in cmds.items())
    )
    
def show_help():
    from rich.panel import Panel
    from rich.markdown import Markdown

    help_text = """
    # Nexidra Plugin Manager CLI

    Manage plugins, marketplace sync, migrations, and publishing in your modular system.

    ## 🧩 Plugin Commands
    | Command | Description |
    |----------|-------------|
    | `python manage.py plugin list` | List all installed plugins |
    | `python manage.py plugin discover` | Discover and register local plugins |
    | `python manage.py plugin install <name>` | Install a plugin from registry |
    | `python manage.py plugin uninstall <name>` | Uninstall a plugin |
    | `python manage.py plugin upgrade <name>` | Upgrade to latest version |
    | `python manage.py plugin downgrade <name>` | Downgrade to previous version |
    | `python manage.py plugin verify-all` | Verify all plugin signatures |
    | `python manage.py plugin publish <name>` | Publish plugin to internal registry |
    | `python manage.py plugin new <name> [--db mongo|postgres] [--template basic|chat]` | Create a new plugin template |

    ## 🏪 Marketplace
    | Command | Description |
    |----------|-------------|
    | `python manage.py marketplace sync` | Sync plugin list from registry |

    ## 🧱 Migrations
    | Command | Description |
    |----------|-------------|
    | `python manage.py migration new <plugin> [description] [--bump patch|minor|major]` | Generate migration script |
    | `python manage.py migration run <plugin|all>` | Run migrations |
    | `python manage.py migration rollback <plugin>` | Rollback last migration |

    ## 🧰 Example Usage
    ```bash
    python manage.py plugin list
    python manage.py plugin install heatmap
    python manage.py plugin publish analytics
    python manage.py migration new heatmap "add metrics" --bump minor
    python manage.py marketplace sync
    Pro Tip: All commands are async-safe and work with both MongoDB and Postgres backends.
    """
    console.print(Panel(Markdown(help_text), title="🧠 Nexidra CLI Help", expand=False))

# ---------------------------
# Utility Functions
# ---------------------------
@command("plugin", "list", "List all installed plugins")
async def list_plugins():
    """List all plugins in the database"""
    db = await anext(get_database())
    plugins = db.plugins
    data = await plugins.find().to_list(100)
    table = Table(title="Installed Plugins")
    table.add_column("Name", style="bold cyan")
    table.add_column("Version", style="yellow")
    table.add_column("Enabled", justify="center")
    table.add_column("Verified", justify="center")
    table.add_column("Source", justify="center")
    for p in data:
        table.add_row(
            p["name"],
            p.get("version", "-"),
            "✅" if p.get("enabled") else "❌",
            "🔒" if p.get("verified") else "⚠️",
            p.get("source", "-"),
        )
    console.print(table)
    
@command("plugin", "publish")
async def publish_plugin(name: str):
    """Package and publish a plugin to the internal registry"""
    from core.registry_client import RegistryClient
    from semver import VersionInfo
    import shutil, os, datetime, json

    plugin_dir = PLUGIN_DIR / name
    manifest_path = plugin_dir / "plugin.json"
    if not plugin_dir.exists() or not manifest_path.exists():
        console.print(f"[red]❌ Plugin '{name}' not found or missing plugin.json[/red]")
        return

    # Load manifest but do NOT bump yet
    manifest = json.loads(manifest_path.read_text())
    current_version = manifest.get("version", "1.0.0")
    new_version = str(VersionInfo.parse(current_version).bump_patch())
    # Verify credentials first
    registry_key = os.getenv("REGISTRY_API_KEY")
    registry_url = os.getenv("REGISTRY_URL")
    if not registry_key or not registry_url:
        console.print("[red]❌ Missing REGISTRY_API_KEY or REGISTRY_URL for publishing.[/red]")
        console.print("💡 Set them in your .env or environment before publishing.")
        return

    # Prepare archive (without touching manifest)
    version_tag = new_version
    zip_name = f"{name}_{version_tag}.zip"
    zip_path = BACKUP_DIR / zip_name
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", plugin_dir)
    console.print(f"[cyan]📦 Packaging {name}@{version_tag}...[/cyan]")
    
    
    temp_manifest = manifest.copy()
    temp_manifest["version"] = new_version
    temp_manifest["published_at"] = datetime.datetime.now(timezone.utc).isoformat()
    # temp_manifest_data = json.dumps(temp_manifest, indent=4)
    import tempfile
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp_file:
        json.dump(temp_manifest, tmp_file, indent=4)
        tmp_file.flush()       # force write to disk
        os.fsync(tmp_file.fileno())  # ensure OS flushes the buffer
        tmp_manifest_path = Path(tmp_file.name)
       
        # Attempt publish
        client = RegistryClient()
        success = await client.publish_plugin(name, zip_path, tmp_manifest_path)
        await client.close()

        if success:
            # ✅ Only bump after success
            
            manifest_path.write_text(json.dumps(temp_manifest, indent=4))
            console.print(f"[blue]🔼 Bumped version {current_version} → {new_version} after successful publish[/blue]")
            console.print(f"[green]✅ Published {name}@{new_version} successfully![/green]")
        else:
            console.print(f"[red]❌ Failed to publish {name}@{current_version}[/red]")



async def publish_plugin_old(name: str):
    """Package and publish a plugin to the internal registry."""
    from core.registry_client import RegistryClient
    from semver import VersionInfo
    

    plugin_dir = PLUGIN_DIR / name
    if not plugin_dir.exists():
        console.print(f"[red]❌ Plugin '{name}' not found in {PLUGIN_DIR}[/red]")
        return

    manifest_path = plugin_dir / "plugin.json"
    if not manifest_path.exists():
        console.print(f"[red]❌ Missing plugin.json in {plugin_dir}[/red]")
        return

    manifest = json.loads(manifest_path.read_text())
   
    old_version = manifest.get("version", "1.0.0")
    new_version = str(VersionInfo.parse(old_version).bump_patch())
    manifest["version"] = new_version
    manifest["published_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=4))
    console.print(f"[blue]🔼 Bumped version {old_version} → {new_version} before publish[/blue]")
    version = new_version
    
    zip_name = f"{name}_{version}.zip"
    zip_path = BACKUP_DIR / zip_name
    zip_path.parent.mkdir(exist_ok=True, parents=True)

    # Package the plugin folder into a zip
    console.print(f"[cyan]📦 Packaging {name}@{version}...[/cyan]")
    shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", plugin_dir)

    # Upload to registry
    client = RegistryClient()
    success = await client.publish_plugin(name, zip_path, manifest_path)
    await client.close()

    if success:
        console.print(f"[green]✅ Published {name}@{version} successfully![/green]")
    else:
        console.print(f"[red]❌ Failed to publish {name}@{version}[/red]")
@command("plugin", "rollback", "Rollback plugin to prev sttate in registry")       
async def rollback_plugin(name: str):
    """Rollback to last backup zip"""
    backups = list(BACKUP_DIR.glob(f"{name}_*.zip"))
    if not backups:
        console.print(f"[red]No backups found for {name}[/red]")
        return
    latest_backup = sorted(backups)[-1]
    console.print(f"[yellow]Rolling back {name} using {latest_backup.name}...[/yellow]")
    import shutil
    shutil.unpack_archive(latest_backup, PLUGIN_DIR)
    console.print(f"[green]✅ Rolled back {name} successfully![/green]")

@command("plugin", "verify-all", "Reverify all installed plugins (signature check)")  
async def verify_all_plugins():
    """Reverify all installed plugins (signature check)"""
    from core.security import verify_signature
    import hashlib

    db  = await anext(get_database())
    plugins = db.plugins
    async for plugin in plugins.find():
        name = plugin["name"]
        zip_path = BACKUP_DIR / f"{name}.zip"
        if not zip_path.exists():
            continue
        data = zip_path.read_bytes()
        valid = verify_signature(data, bytes.fromhex(plugin.get("signature", "")))
        if valid:
            console.print(f"[green]✔ Verified {name}[/green]")
            await plugins.update_one({"name": name}, {"$set": {"verified": True}})
        else:
            console.print(f"[red]✖ Verification failed for {name}[/red]")
@command("marketplace", "sync", "Sync available plugins from registry")
async def sync_marketplace():
    from core.registry_client import RegistryClient

    rc = RegistryClient()
    plugins = await rc.list_plugins()
    await rc.close()

    table = Table(title="Available Plugins on Registry")
    table.add_column("Name", style="bold cyan")
    table.add_column("Version", style="yellow")
    table.add_column("Verified", justify="center")

    for p in plugins:
        table.add_row(
            p["name"], p.get("version", "-"), "🔒" if p.get("verified") else "⚠️"
        )

    console.print(table)
    
@command("plugin", "new", "Generate a new plugin folder template with standard structure and options")
async def create_plugin_template(name: str, db: str = "mongo", template: str = "basic", author: str = "Nexidra Technologies"):
    """Generate a new plugin folder template with standard structure and options"""
    base_dir = PLUGIN_DIR / name
    if base_dir.exists():
        console.print(f"[red]Plugin '{name}' already exists.[/red]")
        return

    console.print(f"[cyan]✨ Creating plugin '{name}' (db={db}, template={template})...[/cyan]")
    (base_dir / "migrations").mkdir(parents=True, exist_ok=True)
    (base_dir / "templates").mkdir(parents=True, exist_ok=True)

    # manifest (plugin.json)
    manifest = {
        "name": name,
        "display_name": name.capitalize(),
        "version": "1.0.0",
        "author": author,
        "description": f"{name.capitalize()} plugin for Nexidra modular system.",
        "enabled": True,
        "verified": False,
        "permissions": [f"{name}.*", f"{name}.create", f"{name}.view"],
        "database": db,
        "pricing": {
            "type": "subscription",           #// free | freemium | one_time | subscription
            "plan_id": "default",  #// Lago plan slug
            "trial_days": 7,
            "currency": "USD",
            "price": 9.99,
            "features": ["unlimited_events", "export_csv"]
        },
        "minimum_subscription": {
            "required":False,
            "plan_id": "core_pro", 
            "feature": "analytics"
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    (base_dir / "plugin.json").write_text(json.dumps(manifest, indent=4))

    # permissions.json
    permissions = [f"{name}.*", f"{name}.create", f"{name}.view"]
    (base_dir / "permissions.json").write_text(json.dumps(permissions, indent=4))

    # migrations/1.0.0_init.py
    migration_code = textwrap.dedent(f"""
    async def run(db):
        print("🚀 Initializing {name} plugin schema...")
        # Example setup: create collection or table
        if hasattr(db, 'app'):
            await db.app.create_collection("{name}")
        print("✅ {name} plugin migration complete.")
    """)
    (base_dir / "migrations" / "1.0.0_init.py").write_text(migration_code)

    # models.py (adjusted per DB)
    if db == "postgres":
        model_code = f"""from sqlalchemy import Column, Integer, String
from core.database import Base

class {name.capitalize()}(Base):
    __tablename__ = '{name}'
    id = Column(Integer, primary_key=True, index=True)
    data = Column(String)
"""
    else:
        model_code = f"""from pydantic import BaseModel

class {name.capitalize()}Model(BaseModel):
    id: str
    created_at: str
    data: dict
"""
    (base_dir / "models.py").write_text(model_code)

    # templates
    dashboard_html = f"""<html>
    <head><title>{name.capitalize()} Plugin</title></head>
    <body style='font-family:sans-serif;'>
        <h1>{name.capitalize()} Plugin Dashboard</h1>
        <p>Welcome to the {name} plugin!</p>
    </body>
</html>"""
    (base_dir / "templates" / "dashboard.html").write_text(dashboard_html)

    # plugin.py (routes differ by template)
    if template == "chat":
        plugin_code = f'''from fastapi import APIRouter, WebSocket
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from routes.auth import get_current_user,checker,Depends,SessionInfo

def init_plugin():
    router = APIRouter()
    templates = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(templates))

    @router.get("/")
    @checker.require_role("admin")
    async def chat_ui(user:SessionInfo=Depends(get_current_user)):
        tmpl = env.get_template("dashboard.html")
        return tmpl.render(title="{name.capitalize()} Chat")

    @router.websocket("/ws")
    async def chat_socket(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Connected to {name} chat plugin")
        try:
            while True:
                msg = await websocket.receive_text()
                await websocket.send_text(f"[Echo] {{msg}}")
        except Exception:
            await websocket.close()

    return {{"router": router}}
'''
    else:
        plugin_code = f'''from fastapi import APIRouter
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from routes.auth import get_current_user,checker,Depends,SessionInfo

def init_plugin():
    router = APIRouter()
    templates = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(templates))

    @router.get("/")
    @checker.require_role("admin")
    async def dashboard(user:SessionInfo=Depends(get_current_user)):
        tmpl = env.get_template("dashboard.html")
        return tmpl.render(title="{name.capitalize()} Plugin")

    @router.post("/create")
    @checker.require_role("admin")
    async def create_item(item: dict,user:SessionInfo=Depends(get_current_user)):
        return {{"status": "created", "plugin": "{name}", "item": item}}

    return {{"router": router}}
'''
    (base_dir / "plugin.py").write_text(plugin_code)

    console.print(f"[green]✅ Plugin '{name}' created successfully at {base_dir}[/green]")

    # Auto-register new plugin into DB
    await discover_plugins()
    console.print(f"[blue]📘 '{name}' auto-registered in plugin database.[/blue]")
import semver  # install with: pip install semver

@command("migration", "new", "Create a new migration script for a plugin")
async def create_plugin_migration(plugin_name: str, description: str = "update", bump: str = "patch"):
    """
    Generate a new migration file for a given plugin, automatically bumping the version.
    bump = 'major' | 'minor' | 'patch'
    """
    plugin_dir = PLUGIN_DIR / plugin_name / "migrations"
    manifest_path = PLUGIN_DIR / plugin_name / "plugin.json"

    if not plugin_dir.exists() or not manifest_path.exists():
        console.print(f"[red]Plugin '{plugin_name}' not found or missing migrations folder.[/red]")
        return

    # Load current version
    manifest = json.loads(manifest_path.read_text())
    current_version = manifest.get("version", "1.0.0")

    # Auto-increment version
    new_version = str(semver.VersionInfo.parse(current_version).bump_patch())
    if bump == "minor":
        new_version = str(semver.VersionInfo.parse(current_version).bump_minor())
    elif bump == "major":
        new_version = str(semver.VersionInfo.parse(current_version).bump_major())

    # Save new version to manifest
    manifest["version"] = new_version
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=4))

    # Sanitize filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"{new_version}_{description.replace(' ', '_')}.py"
    migration_path = plugin_dir / filename

    # Template content
    migration_code = f'''"""
Migration: {description}
Auto-generated for plugin: {plugin_name}
Version: {new_version}
Generated at: {datetime.now(timezone.utc).isoformat()}
"""

async def run(db):
    print("🚀 Running migration {new_version} for {plugin_name}...")
    # Example: await db["{plugin_name}_collection"].update_many({{}}, {{"$set": {{"migrated": True}}}})
    print("✅ Migration {new_version} complete.")


async def rollback(db):
    print("↩️ Rolling back migration {new_version} for {plugin_name}...")
    # Example: await db["{plugin_name}_collection"].delete_many({{"migrated": True}})
    print("✅ Rollback for {new_version} complete.")
'''

    migration_path.write_text(migration_code)
    console.print(f"[green]✅ Created migration {migration_path}[/green]")
    console.print(f"[blue]🔼 Bumped {plugin_name} version: {current_version} → {new_version}[/blue]")

@command("plugin", "discover")
async def idiscover_plugins():
    """Discover plugins and register them in the local database."""
    await discover_plugins()
    
@command("plugin", "install")
async def iverify_and_install_from_registry(name):
    """Fetch plugin from internal registry, verify, and install."""
    await verify_and_install_from_registry(name)
    
@command("plugin", "upgrade")
async def icheck_for_updates():
    """Fetch plugin updated internal registry."""
    from core.plugin_manager import check_for_updates
    await check_for_updates()
@command("plugin", "rollback")
async def irollback_plugin(name:str):
    """Fetch plugin from internal registry, verify, and install."""
    await rollback_plugin(name)
    
    
@command("migration", "run")
async def irun_plugin_migrations(plugin_name: str, db):
    """Run all pending migrations for a plugin."""
    from core.migration_runner import run_plugin_migrations
    return await run_plugin_migrations(plugin_name, db)

@command("migration", "rollback")
async def irollback_last_migration(plugin_name: str, db):
    """Rollback the most recent migration for a plugin."""
    from core.migration_runner import rollback_last_migration
    return await rollback_last_migration(plugin_name, db)

# @command("plugin", "rollback")
# async def ipublish_plugin(name:str):
#     """Fetch plugin from internal registry, verify, and install."""
#     await publish_plugin(name) 
    
# ---------------------------
# Command Routing
# ---------------------------

async def main():
    if len(sys.argv) < 2:
        console.print("[yellow]Usage: python manage.py [plugin|marketplace] <command>[/yellow]")
        sys.exit(1)

    category = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else None
    if len(sys.argv) < 2 or sys.argv[1] in ["help", "--help", "-h"]:
        show_help()
        sys.exit(0)

    if category == "plugin":
        if cmd=="test":
            try:
                db_gen = get_database()
                db = await anext(db_gen)
                await db_manager._client.server_info()
                await db_gen.aclose()
                console.print(f"[green]DB Connected: okay[/green]")
            except Exception as e:
                 console.print(f"[red]DB error {e}  <name>[/red]")
        elif cmd == "list":
            await list_plugins()
        elif cmd == "discover":
            await idiscover_plugins()
        elif cmd == "install":
            if len(sys.argv) < 4:
                console.print("[red]Usage: python manage.py plugin install <name>[/red]")
                return
            name = sys.argv[3]
            await iverify_and_install_from_registry(name)
        elif cmd == "upgrade":
            if len(sys.argv) < 4:
                console.print("[red]Usage: python manage.py plugin upgrade <name>[/red]")
                return
            from core.plugin_manager import check_for_updates
            await icheck_for_updates()
        elif cmd == "rollback":
            if len(sys.argv) < 4:
                console.print("[red]Usage: python manage.py plugin rollback <name>[/red]")
                return
            name = sys.argv[3]
            await irollback_plugin(name)
        elif cmd == "verify-all":
            await verify_all_plugins()
        elif cmd == "publish":
            if len(sys.argv) < 4:
                console.print("[red]Usage: python manage.py plugin publish <name>[/red]")
                return
            name = sys.argv[3]
            await publish_plugin(name)
        elif cmd == "new":
            parser = argparse.ArgumentParser(description="Create a new Nexidra plugin template")
            parser.add_argument("name", help="Plugin name")
            parser.add_argument("--db", default="mongo", choices=["mongo", "postgres"], help="Database backend")
            parser.add_argument("--template", default="basic", choices=["basic", "chat", "dashboard","none"], help="Plugin UI template type")
            parser.add_argument("--author", default="Nexidra Technologies", help="Author name")
            args = parser.parse_args(sys.argv[3:])

            await create_plugin_template(args.name, db=args.db, template=args.template, author=args.author)
        else:
            console.print("[red]Unknown plugin command[/red]")

    elif category == "marketplace":
        if cmd == "sync":
            await sync_marketplace()
        else:
            console.print("[red]Unknown marketplace command[/red]")
    elif cmd == "migration":
        action = sys.argv[2] if len(sys.argv) > 2 else None
        if action == "new":
            if len(sys.argv) < 4:
                console.print("[red]Usage: python manage.py migration new <plugin> [description] [--bump patch|minor|major][/red]")
            else:
                plugin_name = sys.argv[3]
                description = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else "update"

                parser = argparse.ArgumentParser(description="Create a plugin migration")
                parser.add_argument("--bump", default="patch", choices=["patch", "minor", "major"], help="Version bump type")
                args, _ = parser.parse_known_args(sys.argv[4:])

                await create_plugin_migration(plugin_name, description, bump=args.bump)
        elif action == "run":
            plugin = sys.argv[3] if len(sys.argv) > 3 else "all"
            
            db_gen = get_database()
            db = await anext(db_gen)
            if plugin == "all":
                for folder in Path("app/plugins").iterdir():
                    if (folder / "migrations").exists():
                        await irun_plugin_migrations(folder.name, db)
            else:
                await irun_plugin_migrations(plugin, db)
            await db_gen.aclose()
            
        elif action == "rollback":
            plugin = sys.argv[3]
            db_gen = get_database()
            db = await anext(db_gen)
            await irollback_last_migration(plugin, db)
            await db_gen.aclose()
       


        
   

    else:
        console.print("[red]Unknown category[/red]")
async def main_dynamic():
    if len(sys.argv) < 2 or sys.argv[1] in ["help", "--help", "-h"]:
        show_help_dynamic()
        return

    category = sys.argv[1]
    cmd = sys.argv[2] if len(sys.argv) > 2 else None

    if category not in COMMANDS:
        console.print(f"[red]❌ Unknown category '{category}'[/red]")
        show_help_dynamic()
        return

    if not cmd or cmd not in COMMANDS[category]:
        console.print(f"[yellow]⚠️ Unknown or missing command for category '{category}'[/yellow]")
        show_help()
        return

    func = COMMANDS[category][cmd]["func"]
    if iscoroutinefunction(func):
        await func(*sys.argv[3:])
    else:
        func(*sys.argv[3:])


if __name__ == "__main__":
    try:
        asyncio.run(main_dynamic())
    except KeyboardInterrupt:
        console.print("\n[red]Aborted by user.[/red]")
