from fastapi import (
    HTTPException, Request, Body,Query, UploadFile, File,FastAPI
)

import os,asyncio
import csv, io
import aiohttp
from fastapi.responses import FileResponse, JSONResponse,HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi_utils.tasks import repeat_every

from aiohttp import ClientTimeout
from datetime import datetime, timezone,timedelta
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from bson import ObjectId
from routes.auth import get_current_user, SessionInfo
from plugins.pms.services.pdf_service import generate_pdf
from plugins.pms.helpers import recalc_invoice,find_utility,serialize_doc
from plugins.pms.models.models import (
    Vendor,Expense,Task
)


def init_auto_sync(app: FastAPI):
    @app.on_event("startup")
    @repeat_every(seconds=3600)  # hourly
    async def sync_all_vendors() -> None:
        db = app.state.adb
        vendors = await db["vendors"].find({"external_api_url": {"$exists": True}}).to_list(None)
        for v in vendors:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(v["external_api_url"], headers={"Authorization": f"Bearer {v.get('api_key', '')}"}) as resp:
                        data = await resp.json()
                        for job in data.get("tasks", []):
                            await db["tasks"].update_one(
                                {"external_id": job["id"]},
                                {"$set": job},
                                upsert=True
                            )
                await db["vendors"].update_one(
                    {"_id": v["_id"]},
                    {"$set": {"last_sync_at": datetime.now(timezone.utc)}}
                )
            except Exception as e:
                print(f"⚠️ Failed to sync vendor {v.get('name')}: {e}")

async def _async_insert_tasks(reader, db):
    for row in reader:
        data = {
            "unit_id": row.get("unit_id"),
            "vendor_id": row.get("vendor_id"),
            "title": row.get("title"),
            "description": row.get("description", ""),
            "status": row.get("status", "open"),
            "created_at": datetime.now(timezone.utc)
        }
        await db["tasks"].insert_one(data)
        yield data

async def _async_insert_expenses(reader, db):
    for row in reader:
        data = {
            "task_id": row.get("task_id"),
            "unit_id": row.get("unit_id"),
            "property_id": row.get("property_id"),
            "label": row.get("label"),
            "amount": float(row.get("amount", 0)),
            "payer": row.get("payer", "tenant"),
            "created_at": datetime.now(timezone.utc)
        }
        await db["expenses"].insert_one(data)
        yield data

async def include_unbilled_expenses(db, tenant_id: str, unit_id: str, month: str):
    """Fetch unbilled tenant expenses and mark them billed."""
    unbilled = await db["expenses"].find({
        "unit_id": unit_id,
        "payer": "tenant",
        "added_to_invoice": False
    }).to_list(None)

    items = []
    for exp in unbilled:
        items.append({
            "label": f"Expense: {exp['label']}",
            "amount": exp["amount"]
        })
        await db["expenses"].update_one(
            {"_id": exp["_id"]},
            {"$set": {"added_to_invoice": True, "billed_month": month}}
        )
    return items

# previous_invoices = await db["invoices"].find({
#     "tenant_id": tenant["_id"],
#     "balance": {"$gt": 0}
# }).sort("created_at", -1).to_list(1)

# if previous_invoices:
#     prev_balance = previous_invoices[0]["balance"]
#     items.append({"label": "Previous Balance", "amount": prev_balance})


def add_routes(router):
    @router.post("/vendors", response_model=Vendor)
    async def create_vendor(request: Request, vendor: Vendor):
        db = request.app.state.adb
        await db["vendors"].insert_one(vendor.model_dump(by_alias=True))
        return vendor
    
    @router.get("/vendors")
    async def list_vendors(request: Request, category: Optional[str] = None):
        db = request.app.state.adb
        query = {"active": True}
        if category:
            query["category"] = category
        vendors = await db["vendors"].find(query).to_list(None)
        return vendors
    
    @router.post("/vendors/{vendor_id}/sync")
    async def sync_vendor_tasks(request: Request, vendor_id: str):
        db = request.app.state.adb
        vendor = await db["vendors"].find_one({"_id": vendor_id})
        if not vendor or not vendor.get("external_api_url"):
            raise HTTPException(404, "Vendor or API info missing")

        async with aiohttp.ClientSession() as session:
            async with session.get(vendor["external_api_url"], headers={"Authorization": f"Bearer {vendor['api_key']}"}) as resp:
                data = await resp.json()
                for job in data.get("tasks", []):
                    await db["tasks"].update_one(
                        {"external_id": job["id"]},
                        {"$set": {
                            "unit_id": job.get("unit_id"),
                            "vendor_id": vendor_id,
                            "title": job["title"],
                            "description": job.get("description"),
                            "status": job.get("status", "open"),
                            "updated_at": datetime.now(timezone.utc)
                        }},
                        upsert=True
                    )
        await db["vendors"].update_one(
            {"_id": vendor_id}, {"$set": {"last_sync_at": datetime.now(timezone.utc)}}
        )
        return {"message": "Tasks synced successfully"}
    
    @router.post("/vendors/{vendor_id}/sync-async")
    async def sync_vendor_tasks_async(request: Request, vendor_id: str):
        """
        Sync vendor work orders asynchronously from external API.
        """
        db = request.app.state.adb
        vendor = await db["vendors"].find_one({"_id": vendor_id})
        if not vendor or not vendor.get("external_api_url"):
            raise HTTPException(404, "Vendor not found or missing API configuration")

        timeout = ClientTimeout(total=15)
        headers = {"Authorization": f"Bearer {vendor.get('api_key', '')}"}
        url = vendor["external_api_url"]

        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        raise HTTPException(resp.status, f"Vendor API returned {resp.status}")
                    data = await resp.json()
            except aiohttp.ClientError as e:
                raise HTTPException(502, f"Vendor API error: {e}")

        # Insert or update tasks
        inserted, updated = 0, 0
        for job in data.get("tasks", []):
            result = await db["tasks"].update_one(
                {"external_id": job["id"]},
                {"$set": {
                    "unit_id": job.get("unit_id"),
                    "vendor_id": vendor_id,
                    "title": job.get("title"),
                    "description": job.get("description"),
                    "status": job.get("status", "open"),
                    "updated_at": datetime.now(timezone.utc)
                }},
                upsert=True
            )
            if result.upserted_id:
                inserted += 1
            elif result.modified_count:
                updated += 1

        await db["vendors"].update_one(
            {"_id": vendor_id},
            {"$set": {"last_sync_at": datetime.now(timezone.utc)}}
        )

        return {
            "message": f"✅ Sync completed for {vendor['name']}",
            "inserted": inserted,
            "updated": updated,
            "api_url": url
        }

    # ===============================================================
    # Work Order
    # ===============================================================

    @router.post("/tasks", response_model=Task)
    async def create_task(request: Request, data: Task):
        db = request.app.state.adb
        data.created_at = datetime.now(timezone.utc)
        await db["tasks"].insert_one(data.model_dump(by_alias=True))
        await db["vendors"].update_one(
            {"_id": data.vendor_id},
            {"$addToSet": {"assigned_tasks": str(data.id)}}
        )
        return data
    
    @router.get("/properties/{property_id}/tasks")
    async def list_tasks(request: Request, property_id: str, status: Optional[str] = None):
        db = request.app.state.adb
        query = {"property_id": property_id}
        if status:
            query["status"] = status
        tasks = await db["tasks"].find(query).sort("created_at", -1).to_list(None)
        return tasks
    @router.patch("/tasks/{task_id}")
    async def update_task(request: Request, task_id: str, payload: dict = Body(...)):
        db = request.app.state.adb
        payload["updated_at"] = datetime.now(timezone.utc)
        await db["tasks"].update_one({"_id": task_id}, {"$set": payload})
        return {"message": "Task updated"}
    
    @router.delete("/tasks/{task_id}")
    async def delete_task(request: Request, task_id: str):
        db = request.app.state.adb
        await db["tasks"].delete_one({"_id": task_id})
        return {"message": "Task deleted"}
    
    @router.post("/expenses", response_model=Expense)
    async def add_expense(request: Request, expense: Expense):
        db = request.app.state.adb
        expense.created_at = datetime.now(timezone.utc)
        await db["expenses"].insert_one(expense.model_dump(by_alias=True))

        # Link to task
        if expense.task_id:
            await db["tasks"].update_one(
                {"_id": expense.task_id},
                {"$addToSet": {"expenses": str(expense.id)}}
            )
        return expense
    
    @router.get("/expenses")
    async def list_expenses(
        request: Request,
        property_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        payer: Optional[str] = None,
        added_to_invoice: Optional[bool] = None
    ):
        db = request.app.state.adb
        query = {}
        if property_id: query["property_id"] = property_id
        if unit_id: query["unit_id"] = unit_id
        if payer: query["payer"] = payer
        if added_to_invoice is not None:
            query["added_to_invoice"] = added_to_invoice
        expenses = await db["expenses"].find(query).sort("created_at", -1).to_list(None)
        return expenses
    
    @router.post("/expenses/{expense_id}/assign")
    async def assign_expense_to_invoice(request: Request, expense_id: str, invoice_id: str = Body(...)):
        db = request.app.state.adb
        await db["expenses"].update_one(
            {"_id": expense_id},
            {"$set": {"added_to_invoice": True, "invoice_id": invoice_id}}
        )
        return {"message": "Expense added to invoice"}
    
    @router.get("/expenses/summary")
    async def expense_summary(request: Request, month: str = Query(...)):
        db = request.app.state.adb
        start = datetime.strptime(month + "-01", "%Y-%m-%d")
        end = (start + timedelta(days=31)).replace(day=1)

        pipeline = [
            {"$match": {"created_at": {"$gte": start, "$lt": end}}},
            {"$group": {
                "_id": "$payer",
                "total_amount": {"$sum": "$amount"},
                "count": {"$sum": 1}
            }}
        ]
        summary = await db["expenses"].aggregate(pipeline).to_list(None)
        return {"month": month, "summary": summary}
    
    @router.get("/properties/{property_id}/operations-summary")
    async def operations_summary(request: Request, property_id: str, month: str = Query(...)):
        db = request.app.state.adb
        start = datetime.strptime(month + "-01", "%Y-%m-%d")
        end = (start + timedelta(days=31)).replace(day=1)

        tasks = await db["tasks"].count_documents({"property_id": property_id})
        completed = await db["tasks"].count_documents({"property_id": property_id, "status": "completed"})

        tenant_expenses = await db["expenses"].aggregate([
            {"$match": {"property_id": property_id, "payer": "tenant", "created_at": {"$gte": start, "$lt": end}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1)

        landlord_expenses = await db["expenses"].aggregate([
            {"$match": {"property_id": property_id, "payer": "landlord", "created_at": {"$gte": start, "$lt": end}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1)

        return {
            "property_id": property_id,
            "month": month,
            "total_tasks": tasks,
            "completed_tasks": completed,
            "pending_tasks": tasks - completed,
            "tenant_expenses": tenant_expenses[0]["total"] if tenant_expenses else 0,
            "landlord_expenses": landlord_expenses[0]["total"] if landlord_expenses else 0
        }
        
    @router.get("/expenses/export")
    async def export_expenses(request: Request):
        db = request.app.state.adb
        expenses = await db["expenses"].find({}).to_list(None)
        csv_path = "/tmp/expenses_export.csv"
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["_id","property_id","unit_id","label","amount","payer","added_to_invoice"])
            writer.writeheader()
            for e in expenses:
                writer.writerow(e)
        return FileResponse(csv_path, filename="expenses_export.csv")
    
    @router.post("/tasks/import")
    async def import_tasks_csv(request: Request, file: UploadFile = File(...)):
        """
        Import multiple tasks from a CSV file.
        Expected columns:
        unit_id,vendor_id,title,description,status
        """
        db = request.app.state.adb
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))

        inserted = 0
        async for row in _async_insert_tasks(reader, db):
            inserted += 1

        return {"message": f"✅ Imported {inserted} tasks successfully"}
    @router.post("/expenses/import")
    async def import_expenses_csv(request: Request, file: UploadFile = File(...)):
        """
        Import expenses from a CSV file.
        Expected columns:
        task_id,unit_id,property_id,label,amount,payer
        """
        db = request.app.state.adb
        content = await file.read()
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))

        inserted = 0
        async for row in _async_insert_expenses(reader, db):
            inserted += 1

        return {"message": f"✅ Imported {inserted} expenses successfully"}
    
    @router.get("/tasks/export")
    async def export_tasks_csv(request: Request):
        """
        Export all tasks to CSV.
        """
        db = request.app.state.adb
        tasks = await db["tasks"].find({}).to_list(None)
        csv_path = "/tmp/tasks_export.csv"

        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "_id","unit_id","vendor_id","title","description","status","created_at"
            ])
            writer.writeheader()
            for t in tasks:
                writer.writerow({k: str(v) for k, v in t.items() if k in writer.fieldnames})

        return FileResponse(csv_path, filename="tasks_export.csv")
    
    return router













