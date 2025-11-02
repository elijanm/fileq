from fastapi import FastAPI, UploadFile, Form, HTTPException,Depends
from pathlib import Path
import hashlib, json, base64
from core.security import sign_data
from models.registry_model import RegistryPlugin
from core.database import get_database
from utils.helper import serialize_doc
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

app = FastAPI(title="Nexidra Plugin Registry")
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@app.post("/api/publish")
async def publish_plugin(
    file: UploadFile,
    manifest: str = Form(...),
    db:AsyncIOMotorDatabase=Depends(get_database)
):
    """GitHub Actions calls this after a release"""
    manifest_data = json.loads(manifest)
    path = UPLOAD_DIR / f"{manifest_data['name']}_{manifest_data['version']}.zip"
    content = await file.read()
    path.write_bytes(content)

    checksum = hashlib.sha256(content).hexdigest()
    signature = sign_data(content).hex()

    
    await db.plugins.insert_one({
        **manifest_data,
        "checksum": checksum,
        "signature": signature,
        "verified": True
    })
    return {"status": "published", "checksum": checksum, "signature": signature}


@app.get("/api/plugins/{name}/latest")
async def get_latest_plugin(
    name: str, db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Returns the latest version of a specific verified plugin,
    including all previous versions for rollback/upgrade view.
    """
    pipeline = [
        {"$match": {"verified": True, "name": name}},
        {"$sort": {"published_at": -1}},
        {
            "$group": {
                "_id": "$name",
                "latest": {"$first": "$$ROOT"},
                "versions": {
                    "$push": {
                        "version": "$version",
                        "published_at": "$published_at",
                        "checksum": "$checksum",
                    }
                },
            }
        },
        {
            "$replaceRoot": {
                "newRoot": {
                    "$mergeObjects": [
                        "$latest",
                        {"versions": "$versions"},
                    ]
                }
            }
        },
    ]

    result = await db.plugins.aggregate(pipeline).to_list(1)
    if not result:
        return {"error": f"Plugin '{name}' not found or not verified."}
    
    return serialize_doc(result[0])

@app.get("/api/plugins/{name}/versions")
async def list_plugin_versions(name: str, db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Return all versions of a given plugin, sorted newest-first.
    """
    versions = (
        await db.plugins.find({"name": name, "verified": True})
        .sort("published_at", -1)
        .to_list(50)
    )
    return versions



@app.get("/api/plugins")
async def list_plugins(db: AsyncIOMotorDatabase = Depends(get_database)):
    """
    Public marketplace endpoint:
    Returns only the latest version of each verified plugin,
    and includes prior version numbers in a nested 'versions' field.
    """
    pipeline = [
        {"$match": {"verified": True}},
        {"$sort": {"name": 1, "published_at": -1}},
        {
            "$group": {
                "_id": "$name",
                "latest": {"$first": "$$ROOT"},
                "versions": {
                    "$push": {
                        "version": "$version",
                        "published_at": "$published_at"
                    }
                },
            }
        },
        {
            "$replaceRoot": {
                "newRoot": {
                    "$mergeObjects": [
                        "$latest",
                        {"versions": "$versions"},
                    ]
                }
            }
        },
        {"$sort": {"name": 1}},
    ]

    results = await db.plugins.aggregate(pipeline).to_list(None)
    return [serialize_doc(r) for r in results]
