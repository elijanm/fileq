import importlib
from pathlib import Path
from core.migration_tracker import MigrationTracker

async def run_plugin_migrations(plugin_name: str, db):
    """Run all pending migrations for a plugin."""
    tracker = MigrationTracker(db)
    plugin_dir = Path("app/plugins") / plugin_name / "migrations"
    applied = {m["file"] for m in await tracker.get_applied(plugin_name)} if await tracker.get_applied(plugin_name) else set()

    for mig_file in sorted(plugin_dir.glob("*.py")):
        if mig_file.name in applied:
            continue  # skip already applied
        module_name = f"app.plugins.{plugin_name}.migrations.{mig_file.stem}"
        module = importlib.import_module(module_name)
        if hasattr(module, "run"):
            print(f"🚀 Applying {plugin_name}:{mig_file.name}")
            await module.run(db)
            await tracker.record_migration(plugin_name, mig_file.stem.split("_")[0], mig_file.name)
    print(f"✅ All migrations up to date for {plugin_name}.")


async def rollback_last_migration(plugin_name: str, db):
    """Rollback the most recent migration for a plugin."""
    tracker = MigrationTracker(db)
    last = await tracker.get_last_applied(plugin_name)
    if not last:
        print(f"⚠️ No migrations to rollback for {plugin_name}.")
        return

    file_name = last["file"]
    module_name = f"app.plugins.{plugin_name}.migrations.{Path(file_name).stem}"
    module = importlib.import_module(module_name)
    if hasattr(module, "rollback"):
        print(f"↩️ Rolling back {plugin_name}:{file_name}")
        await module.rollback(db)
        await tracker.mark_rollback(plugin_name, last["version"])
        print(f"✅ Rolled back {file_name}")
    else:
        print(f"⚠️ Migration {file_name} has no rollback defined.")
