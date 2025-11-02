"""
core/registry_client.py
-----------------------
Handles interaction with the Nexidra Plugin Registry:
 - list / get / download
 - verify signatures & checksums
 - publish new plugin versions (with API key auth)
"""

import httpx
import hashlib
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from core.config import settings
from core.security import sign_data, verify_signature
from rich.console import Console
from semver import VersionInfo
import os
console = Console()

class RegistryClient:
    """Async client for the Nexidra internal plugin registry."""

    def __init__(self, registry_url: Optional[str] = None, api_key: Optional[str] = None):
        self.registry_url = registry_url or settings.REGISTRY_URL.rstrip("/")
        self.api_key = api_key or settings.REGISTRY_URL
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self.session = httpx.AsyncClient(timeout=20.0, headers=headers)

    # ----------------------------------------------------------------
    #  Plugin Fetching / Sync
    # ----------------------------------------------------------------
    async def list_plugins(self) -> list:
        """Fetch all available plugins from registry."""
        try:
            res = await self.session.get(f"{self.registry_url}/plugins")
            res.raise_for_status()
            return res.json()
        except Exception as e:
            console.print(f"[red]⚠️ Failed to fetch plugin list: {e}[/red]")
            return []

    async def get_plugin_manifest(self, name: str) -> Optional[dict]:
        """Fetch plugin manifest (metadata only)."""
        try:
            res = await self.session.get(f"{self.registry_url}/plugins/{name}/manifest")
            res.raise_for_status()
            return res.json()
        except Exception as e:
            console.print(f"[red]⚠️ Failed to fetch manifest for {name}: {e}[/red]")
            return None

    async def download_plugin_zip(self, name: str, version: Optional[str] = None) -> Optional[Path]:
        """Download plugin zip archive from registry."""
        try:
            url = f"{self.registry_url}/plugins/{name}/download"
            if version:
                url += f"?version={version}"
            res = await self.session.get(url)
            res.raise_for_status()

            zip_path = Path(f".plugin_backups/{name}_{version or 'latest'}.zip")
            zip_path.parent.mkdir(exist_ok=True, parents=True)
            zip_path.write_bytes(res.content)

            console.print(f"[green]📦 Downloaded {name}@{version or 'latest'} to {zip_path}[/green]")
            return zip_path
        except Exception as e:
            console.print(f"[red]⚠️ Failed to download plugin {name}: {e}[/red]")
            return None

    # ----------------------------------------------------------------
    #  Verification
    # ----------------------------------------------------------------
    async def verify_plugin(self, zip_path: Path, manifest: dict) -> bool:
        """Verify plugin integrity and optional signature."""
        try:
            if not zip_path.exists():
                console.print(f"[red]Missing file: {zip_path}[/red]")
                return False

            data = zip_path.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            expected_checksum = manifest.get("checksum")

            if expected_checksum and checksum != expected_checksum:
                console.print(f"[red]❌ Checksum mismatch for {manifest['name']}[/red]")
                return False

            if "signature" in manifest:
                signature_valid = verify_signature(data, bytes.fromhex(manifest["signature"]))
                if not signature_valid:
                    console.print(f"[red]🔒 Signature verification failed for {manifest['name']}[/red]")
                    return False

            console.print(f"[green]✅ Verified {manifest['name']} integrity and signature[/green]")
            return True
        except Exception as e:
            console.print(f"[red]⚠️ Verification error: {e}[/red]")
            return False

    # ----------------------------------------------------------------
    #  Publishing
    # ----------------------------------------------------------------
    async def publish_plugin(self, name: str, zip_path: Path, manifest_path: Path) -> bool:
        """
        Upload and register a plugin zip + manifest to the registry.
        """
        if not self.api_key:
            console.print("[red]❌ Missing REGISTRY_API_KEY[/red]")
            return False

        if not zip_path.exists() or not manifest_path.exists():
            console.print(f"[red]❌ Missing files for {name}[/red]")
            return False

        files = {
        "file": (zip_path.name, open(zip_path, "rb"), "application/zip"),
        }
        manifest_dict = json.loads(manifest_path.read_text())
        manifest_data = json.dumps(manifest_dict)
        
        
        data = {
            "manifest": manifest_data,
        }
     
        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            
            res = await self.session.post(
                f"{self.registry_url}/api/publish",
                files=files,
                data=data,
                headers=headers,
            )
            if res.status_code in [201,200]:
                console.print(f"[green]✅ Plugin '{name}' successfully published to registry[/green]")
               
                return True
            else:
                console.print(f"[red]⚠️ Registry rejected publish ({res.status_code}): {res.text}[/red]")
                return False
        except Exception as e:
            console.print(f"[red]❌ Error publishing {name}: {e}[/red]")
            return False

    async def close(self):
        await self.session.aclose()
    async def publish_plugin_old(name: str):
        """Safely publish a plugin to the internal registry."""
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

        # Verify credentials first
        registry_key = os.getenv("REGISTRY_API_KEY")
        registry_url = os.getenv("REGISTRY_URL")
        if not registry_key or not registry_url:
            console.print("[red]❌ Missing REGISTRY_API_KEY or REGISTRY_URL for publishing.[/red]")
            console.print("💡 Set them in your .env or environment before publishing.")
            return

        # Prepare archive (without touching manifest)
        
        version_tag = current_version
        zip_name = f"{name}_{version_tag}.zip"
        zip_path = BACKUP_DIR / zip_name
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.make_archive(str(zip_path).replace(".zip", ""), "zip", plugin_dir)
        console.print(f"[cyan]📦 Packaging {name}@{version_tag}...[/cyan]")

        # Attempt publish
        client = RegistryClient()
        success = await client.publish_plugin(name, zip_path, manifest_path)
        await client.close()

        if success:
            # ✅ Only bump after success
            
            manifest_path.write_text(json.dumps(manifest, indent=4))
            console.print(f"[blue]🔼 Bumped version {current_version} → {new_version} after successful publish[/blue]")
            console.print(f"[green]✅ Published {name}@{new_version} successfully![/green]")
        else:
            console.print(f"[red]❌ Failed to publish {name}@{current_version}[/red]")

    async def publish_plugin_old(self, plugin_name: str, zip_path: Path, manifest_path: Path):
        """Publish or update a plugin in the registry."""
        if not self.api_key:
            console.print("[red]❌ Missing REGISTRY_API_KEY for publishing.[/red]")
            return False

        if not zip_path.exists() or not manifest_path.exists():
            console.print(f"[red]❌ Missing zip or manifest for {plugin_name}[/red]")
            return False

        # Load manifest
        manifest = json.loads(manifest_path.read_text())
        data = zip_path.read_bytes()

        # Compute checksum and signature
        checksum = hashlib.sha256(data).hexdigest()
        signature = sign_data(data).hex()

        manifest.update({
            "checksum": checksum,
            "signature": signature,
            "published_at": datetime.utcnow().isoformat(),
        })

        # Prepare upload
        files = {"file": zip_path.open("rb")}
        data = {"manifest": json.dumps(manifest)}

        try:
            res = await self.session.post(f"{self.registry_url}/plugins/publish", files=files, data=data)
            res.raise_for_status()
            console.print(f"[green]🚀 Published {plugin_name}@{manifest['version']} successfully![/green]")
            return True
        except httpx.HTTPStatusError as e:
            console.print(f"[red]❌ Registry returned {e.response.status_code}: {e.response.text}[/red]")
        except Exception as e:
            console.print(f"[red]⚠️ Error publishing {plugin_name}: {e}[/red]")
        return False

    # ----------------------------------------------------------------
    #  Cleanup
    # ----------------------------------------------------------------
    async def close(self):
        await self.session.aclose()


# from core.registry_client import RegistryClient
# import asyncio

# async def publish_sms():
#     client = RegistryClient()
#     await client.publish_plugin(
#         "sms",
#         Path("plugins/sms.zip"),
#         Path("plugins/sms/plugin.json")
#     )
#     await client.close()

# asyncio.run(publish_sms())
