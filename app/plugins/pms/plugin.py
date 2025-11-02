from fastapi import (
    APIRouter, HTTPException, Request, Body, Depends,
    BackgroundTasks, Query, FastAPI
)
import os,asyncio
from fastapi.responses import FileResponse, JSONResponse,HTMLResponse
from fastapi.templating import Jinja2Templates
from bson import Regex
from datetime import datetime, timezone,timedelta,date
from typing import List, Optional, Dict,Any
from pydantic import BaseModel, Field
from bson import ObjectId
from routes.auth import get_current_user, SessionInfo
from plugins.pms.services.pdf_service import generate_pdf
from plugins.pms.helpers import recalc_invoice,find_utility,serialize_doc
from plugins.pms.models import (
    PropertyInDB,PropertyResponse,LeaseCreate,LeaseInDB, Tenant, Unit,
    Payment,PaymentCreate,ContractSignRequest,UnitListItem, Contract,Utility, WaterUsage,PropertyListResponse, MeterUpdate,PropertyCreate,UnitCreate,DepositTransaction,ContractCreate,Clause
)
from plugins.pms.utils.ledger import Ledger,LedgerEntry,Invoice,LineItem,compute_financial_metrics,compute_forecast_metrics
from plugins.pms.utils.lease import prepare_contract_data,capture_signature_metadata
from plugins.pms.vendor import add_routes
from utils.media_tools import upload_image
from plugins.pms.unit_helper import auto_generate_units,batch_insert_units,ensureRoomAssigned
from plugins.pms.models import (
   
PropertyDetailResponse,UnitUpdate,UnitResponse,PropertyUpdate
)
from plugins.pms.utils.tenant_snapshot import TenantSnapshotManager
from statistics import mean
from math import ceil
from plugins.pms.utils.prorate import prorated_rent_charges
from plugins.pms.property_helper import get_property_detail


templates = Jinja2Templates(directory="plugins/pms/templates")
router = APIRouter(prefix="/property", tags=["Property Management"])


UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ===============================================================
# UTILITIES
# ===============================================================

async def authorize_property(db, property_id: str, owner_id: str):
    prop = await db["properties"].find_one({"_id": property_id, "owner_id": owner_id})
    if not prop:
        raise HTTPException(403, "Unauthorized or property not found")
    return prop


# ===============================================================
# ROUTES
# ===============================================================

@router.get("/tenants/search/{id_number}")
async def search_tenant(
    request: Request,
    id_number: str,
    user: SessionInfo = Depends(get_current_user)
):
    """
    Search for a tenant by ID number.
    Returns tenant information and whether they have an active lease.
    """
    db = request.app.state.adb
    
    # Search for tenant by ID number across properties owned by this user
    tenant = await db["property_tenants"].find_one({
        "id_number": id_number,
        # "owner_id": user.user_id
    })
    
    if not tenant:
        return {
            "found": False,
            "tenant": None
        }
    
    # Check if tenant has an active lease
    active_lease = await db["property_leases"].find_one({
        "tenant_id": str(tenant["_id"]),
        "status": "signed"
    })
    
    return {
        "found": True,
        "tenant": {
            "_id": str(tenant["_id"]),
            "fullName": tenant.get("fullName") or tenant.get("full_name"),
            "email": tenant.get("email"),
            "phone": tenant.get("phone"),
            "idNumber": tenant.get("idNumber") or tenant.get("id_number"),
            "hasActiveLease": active_lease is not None
        }
    }
    
@router.post("/contracts/create")
async def create_contract(request: Request, contract: LeaseCreate):
    """Create a new rental contract draft and reuse or request landlord signature."""
    db = request.app.state.adb

    # --- Step 1: Check or create tenant ---
    tenant_data = contract.tenant_details.model_dump()
    existing_tenant = await db["property_tenants"].find_one({
        "$or": [
            {"email": tenant_data.get("email")},
            {"phone": tenant_data.get("phone")},
            {"idNumber": tenant_data.get("idNumber")},
            
        ]
    })

    if existing_tenant:
        tenant_id = existing_tenant["_id"]
    else:
        tenant = Tenant(
            full_name=tenant_data["full_name"],
            email=tenant_data.get("email"),
            phone=tenant_data.get("phone"),
            property_id=contract.property_id,
            unit_ids=contract.units_id,
            active=False,
            joined_at=datetime.now(timezone.utc),
            created_at =datetime.now(timezone.utc),
            updated_at =datetime.now(timezone.utc)
        )
        await db["property_tenants"].insert_one(tenant.model_dump(by_alias=True))
        tenant_id = tenant.id

    # --- Step 2: Check property for landlord signature ---
    property_doc = await db["properties"].find_one({"_id": contract.property_id})
    if not property_doc:
        raise HTTPException(404, "Property not found")
    # await db["properties"].update_one(
    #         {"_id": contract["property_id"]},
    #         {"$set": {"landlord_signature": signature,"landlord_signature_metadata":signature_metadata}}
    #     )
    landlord_signature = property_doc.get("landlord_signature")
    landlord_signature_metadata=property_doc.get("landlord_signature_metadata")
    landlord_sign_url = None
    contract_id = ObjectId()
    if not landlord_signature:
        # Landlord has not signed yet → create sign URL
        landlord_sign_url = str(request.url_for("contract_sign_page", contract_id=str(contract_id), role="landlord"))
        
    tenant_sign_url = str(request.url_for("contract_sign_page", contract_id=str(contract_id),role="tenant"))
    # --- Step 3: Create contract document ---
    # clauses = [c.model_dump() if isinstance(c, Clause) else c for c in contract.clauses]
    contract_doc=contract.model_dump()
    signed_date = datetime.now(timezone.utc)
    # update_fields["landlord_signed_date"] = signed_date
    contract_doc.update({
        "_id": contract_id,
        "tenant_id":tenant_id,
        "status": "pending",
        "tenant_signature": None,
        "landlord_signature": landlord_signature,
        "landlord_signature_metadata":landlord_signature_metadata,
        "landlord_signed_date":signed_date if landlord_signature else None,
        "created_at": signed_date,
        "updated_at": signed_date,
    })
    # contract_doc = {
    #     "_id": contract_id,
    #     "tenant_id": tenant_id,
    #     "property_id": contract.property_id,
    #     "units_id": contract.units_id,
    #     "start_date": contract.start_date,
    #     "end_date": contract.end_date,
    #     "rent_amount": contract.rent_amount,
    #     "deposit_amount": contract.deposit_amount,
    #     "clauses": clauses,
    #     "status": "pending",
    #     "tenant_signature": None,
    #     "landlord_signature": landlord_signature,  # <-- Reused if exists
    #     "created_at": datetime.now(timezone.utc)
    # }

    await db["property_leases"].insert_one(contract_doc)

    response = {
        "message": "Contract created successfully",
        "contract_id": str(contract_doc["_id"]),
        "tenant_id": str(tenant_id),
        "status": "pending",
        "tenant_sign_url":tenant_sign_url
    }

    if landlord_signature:
        response["landlord_signature_status"] = "reused"
    else:
        response["landlord_signature_status"] = "missing"
        response["landlord_sign_url"] = landlord_sign_url

    return response
@router.get("/contracts")
async def list_contracts(
    request: Request,
    user: SessionInfo = Depends(get_current_user),
    property_id: str | None = Query(None),
    status: str | None = Query(None)
):
    """
    List all contracts for the current landlord or filter by property/status.
    Returns enriched data including tenant, property, and unit info.
    """
    db = request.app.state.adb

    # --- Base query ---
    # query = {"owner_id": user.user_id}
    query = {}
    if property_id:
        query["property_id"] = property_id
    if status:
        query["status"] = status

    # --- Find all contracts owned by landlord ---
    contracts = await db["property_leases"].find(query).to_list(None)
    if not contracts:
        return {"total": 0, "property_leases": []}

    results = []
    # print(contracts)
    for c in contracts:
        # tenant = await db["property_tenants"].find_one(
        #     {"_id": ObjectId(c["tenant_id"])}, {"full_name": 1, "email": 1, "phone": 1}
        # )
        tenant=c["tenant_details"]
        prop = await db["properties"].find_one(
            {"_id": c["property_id"]}, {"name": 1, "location": 1}
        )
        unit_ids = [ObjectId(uid) for uid in c.get("units_id", []) if uid]
        units = await db["units"].find(
            {"_id": {"$in": unit_ids}},
            {"unitNumber": 1, "rentAmount": 1, "isOccupied": 1,"depositAmount":1,"status":1}
        ).to_list(None)
        
        # Format units
        serialized_units = [
            {
                "_id": str(u["_id"]),
                "name": u.get("unitNumber", "Unknown"),
                "price": u.get("rentAmount"),
                "deposit_amount":u.get("depositAmount"),
                "occupied": u.get("isOccupied", False),
                "status": u.get("status", False),
            }
            for u in units
        ]

        # Human-readable unit name(s)
        if len(serialized_units) == 1:
            unit_name_display = serialized_units[0]["name"]
        elif len(serialized_units) > 1:
            unit_name_display = ", ".join(
                [u["name"] for u in serialized_units if u.get("name")]
            )
        else:
            unit_name_display = "No Units"

        lease_terms = c.get("lease_terms", {})
        financial_details = c.get("financial_details", {})

        results.append({
            "_id": str(c["_id"]),
            "property_id": str(c["property_id"]),
            "property_name": prop["name"] if prop else "Unknown",
            "property_location": prop["location"] if prop else None,
            "unit_name": unit_name_display,
            "units": serialized_units,
            "tenant_id": str(c["tenant_id"]),
            "tenant_name": tenant["full_name"] if tenant else c["tenant_details"]["full_name"],
            "tenant_details": tenant or c.get("tenant_details", {}),
            "start_date": lease_terms.get("start_date"),
            "end_date": lease_terms.get("end_date"),
            "rent_amount": lease_terms.get("rent_amount"),
            "deposit_amount": lease_terms.get("deposit_amount"),
            "rent_cycle": lease_terms.get("rent_cycle", "monthly"),
            "payment_due_day": lease_terms.get("payment_due_day", 1),
            "currency": financial_details.get("currency", "KES"),
            "deposit_paid": financial_details.get("deposit_paid", False),
            "deposit_paid_amount": financial_details.get("deposit_paid_amount", 0),
            "status": c.get("status", "pending"),
            "tenant_signature": c.get("tenant_signature"),
            "landlord_signature": c.get("landlord_signature"),
            "tenant_signed_date": c.get("tenant_signed_date"),
            "landlord_signed_date": c.get("landlord_signed_date"),
            "created_at": c.get("created_at"),
            "clauses": c.get("clauses", []),
            "utilities": c.get("utilities", [])
        })

    return {
        "total": len(results),
        "page": 1,
        "limit": len(results),
        "property_leases": serialize_doc(results)
    }
    
@router.get("/contracts/{contract_id}/landlord-sign")
async def landlord_sign_request(request: Request, contract_id: str):
    """
    If landlord hasn't signed yet, return signing page URL.
    Otherwise, respond with 'Landlord already signed'.
    """
    db = request.app.state.adb
    contract = await db["property_leases"].find_one({"_id": contract_id})
    if not contract:
        raise HTTPException(404, "Contract not found")

    if contract.get("landlord_signature"):
        return {"message": "✅ Landlord already signed this contract"}

    sign_url = request.url_for("contract_sign_page", contract_id=contract_id, role="landlord")
    return {"message": "Landlord signature required", "sign_url": str(sign_url)}


@router.post("/properties/{property_id}/units")
async def add_unit_to_property(request: Request, property_id: str, unit_new: UnitCreate):
    """
    Add a new unit (room/house) to an existing property.
    """
    db = request.app.state.adb

    # Check that property exists
    prop = await db["properties"].find_one({"_id": property_id})
    if not prop:
        raise HTTPException(404, detail="Property not found")
    
    # # Create the Unit object
    unit = Unit(
        **unit_new.model_dump(),
        property_id=property_id,
        created_at=datetime.now(timezone.utc),
    )

    await db["units"].insert_one(unit.model_dump(by_alias=True))

    # Update property "updated_at"
    await db["properties"].update_one(
        {"_id": property_id},
        {"$set": {"updated_at": datetime.now(timezone.utc)}}
    )

    return {
        "message": f"Unit '{unit.name}' added successfully to property {prop['name']}",
        "unit_id": unit.id,
        "property_id": property_id
    }
@router.patch("/unit/{unit_id}",response_model=UnitResponse)
async def update_unit_of_property(request: Request, unit_id: str, up: UnitUpdate):
    db = request.app.state.adb
    unit = await db["units"].find_one({"_id": ObjectId(unit_id)})
    if not unit:
        raise HTTPException(404, detail="Property Unit not found")
    
    update_data = up.model_dump(exclude_unset=True, exclude_none=True,by_alias=True)
    raise HTTPException(404, detail="Property Unit not found")
    if not update_data:
        # No fields to update
        unit["_id"] = str(unit["_id"])
        return unit
    
    # Handle nested objects and lists
    update_operations = {}
    
    def compare_and_update(new_data, old_data, prefix=""):
        for key, new_value in new_data.items():
            field_path = f"{prefix}.{key}" if prefix else key
            old_value = old_data.get(key)
            
            if isinstance(new_value, dict) and isinstance(old_value, dict):
                # Recursively compare nested objects
                compare_and_update(new_value, old_value, field_path)
            elif isinstance(new_value, list) and isinstance(old_value, list):
                # Compare lists - only update if different
                if new_value != old_value:
                    update_operations[field_path] = new_value
            else:
                # Compare simple values - only update if different
                if new_value != old_value:
                    update_operations[field_path] = new_value
    
    compare_and_update(update_data, unit)
    
    if not update_operations:
        # No actual changes detected
        print("No actual changes detected")
        unit["_id"] = str(unit["_id"])
        return unit
    
    
    # Perform the update
    print()
    result = await db["units"].update_one(
        {"_id": ObjectId(unit_id)},
        {"$set": update_operations}
    )
    print(f"{result.modified_count } and {result.matched_count}")
    unit = await db["units"].find_one({"_id": ObjectId(unit_id)})
    
    
    unit["_id"]=str(unit["_id"])
    return unit
    
    
    
@router.get("/contracts/{contract_id}/sign/{role}", response_class=HTMLResponse, name="contract_sign_page")
async def render_sign_page(request: Request, contract_id: str, role: str = "tenant"):
    """
    Renders the signing page for tenant or landlord.
    """
    db = request.app.state.adb
    contract = await db["property_leases"].find_one({"_id": ObjectId(contract_id)})
    if not contract:
        raise HTTPException(404, "Contract not found")

    # prevent re-signing
    if role == "tenant" and contract.get("tenant_signature"):
        return HTMLResponse("<h3>✅ Tenant already signed this contract.</h3>")
    if role == "landlord" and contract.get("landlord_signature"):
        return HTMLResponse("<h3>✅ Landlord already signed this contract.</h3>")

    return templates.TemplateResponse(
        "contract_sign.html",
        {"request": request, "contract_id": contract_id, "role": role}
    )

@router.post("/contracts/{contract_id}/sign")
async def sign_contract(request: Request, contract_id: str, data: ContractSignRequest):
    """
    Tenant signs the contract. Once signed:
    - Marks contract as 'signed'
    - Creates a Tenant record (if not exists)
    - Marks the assigned Unit as occupied
    - Optionally generates the first invoice
    """
    db = request.app.state.adb
    contract = await db["property_leases"].find_one({"_id": ObjectId(contract_id)})
    if not contract:  
        raise HTTPException(404, "Contract not found")
     # Extract signature info
    role = data.role.lower()
    signature = data.signature

    # --- Handle signing logic ---
    update_fields = {}
    signed_date = datetime.now(timezone.utc)
    
    
    if role == "tenant":
        if contract.get("tenant_signature"):
            return {"message": "Tenant already signed"}
        update_fields["tenant_signature"] = signature
        update_fields["status"] = "signed" if contract.get("landlord_signature") else "pending"
        
        tenant_details = contract.get("tenant_details", {})
        tenant_name = tenant_details.get("full_name", "Unknown Tenant")
        tenant_email = tenant_details.get("email", "")
        # print(tenant_details)
        signature_metadata = await capture_signature_metadata(
            request=request,
            signer_name=tenant_name,
            signer_email=tenant_email,
            document_id=contract_id,
            signature_data=signature
        )
        update_fields["tenant_signed_date"] = signed_date
        update_fields["tenant_signature_metadata"] = signature_metadata

        # Auto-create tenant if missing
        c = contract
        c["_id"] = str(c["_id"])
        c["tenant_id"] = str(c["tenant_id"])
        c = LeaseInDB(**c)
        if not contract["tenant_id"]:
            tenant_id=ObjectId()
            update_fields['tenant_id']=tenant_id
            default_user = contract["tenant_details"] if "tenant_details" in contract  else  {}
            default_user.update({
                "_id": tenant_id,
                "property_id": contract["property_id"],
                "units_id": contract["units_id"],
                "joined_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "active": True,
            })
         
            await db["property_tenants"].insert_one(default_user)
            tenant = await db["property_tenants"].find_one({"_id": tenant_id})
            
        else:  
            tenant = await db["property_tenants"].find_one({"_id": ObjectId(contract["tenant_id"])})
            
        if not tenant:
            raise Exception(f"Tenant Not Found {contract['tenant_id']}")
            
        # --- Update unit occupancy ---
        await ensureRoomAssigned(contract,db)
        
        lease_terms = contract.get("lease_terms", {})
        property = await db["properties"].find_one({"_id": str(c.property_id)})
        units = await db["units"].find({"_id": {"$in": [ObjectId(e) for e in contract["units_id"]]}},{"_id": 1, "unitName": 1,"unitNumber":1,"rentAmount":1} ).to_list(None)
        # --- Optionally: auto-generate first invoice ---
        # Loop for each unit to iclude rent per unit line
        def join_units(units):
            nums = [str(u.get("unitNumber")) for u in units if u.get("unitNumber")]
            return ", ".join(nums) if len(nums) > 1 else (nums[0] if nums else None)
        
        unit_label = join_units(units)
        start_date = c.lease_terms.start_date.date()
        rates = prorated_rent_charges(monthly_rent=lease_terms.get("rent_amount"),contract_start=start_date,rent_prefix=unit_label)
        items = []
        
        for rate in rates.get("line_items",[]):
            meta={
                "period":rate.get("period",[]),
                "days_billed":rate.get("days_billed",None),
                "denominator_days": rate.get("denominator_days",None),
            }
            items.append(
                 LineItem.create(description=rate.get("description"), amount=rate.get("amount"),category="rent",meta=meta),
            )
        items.append(
            LineItem.create(description="Rent Deposit", amount=lease_terms.get("deposit_amount"),category="deposit"),
        )
        # Add Utility Deposits if available
        for u in c.utilities:
           
            if u.get("isDepositRequired",False):
               
                refundable_text = "Refundable" if u.get("isRefundable", False) else "Non-Refundable"
                deposit_amount = float(u.get("depositAmount", 0)) or 0
         
                if deposit_amount > 0:
                    items.append(
                        LineItem.create(
                            description=f"{u.get('name')} Deposit ({refundable_text})",
                            amount=deposit_amount,
                            category="deposit",
                        )
                    )
       
        invoice = Invoice.create(
            tenant_id=str(contract["tenant_id"]),
            property_id=contract["property_id"],
            units_id=contract["units_id"],
            date_issued=signed_date,
            due_date=(signed_date + timedelta(days=2)),
            items=items,
        )
        
        
        invoice.meta={
            "tenant":{
                "full_name":c.tenant_details.full_name
            },
            "property":{
                "name":property["name"] if property else None,
                "location":property["location"] if property else None
            },
            "units":units
        }
        print(invoice.meta)
        ledger=Ledger(db)
        entries=await ledger.post_invoice_to_ledger(invoice=invoice)


    elif role == "landlord":
        if contract.get("landlord_signature"):
            return {"message": "Landlord already signed"}
        update_fields["landlord_signature"] = signature
        update_fields["status"] = "signed" if contract.get("tenant_signature") else "pending"
        
        property_doc = await db["properties"].find_one({"_id": (contract["property_id"])})
        landlord_name = property_doc.get("landlord_name") or property_doc.get("name", "Unknown Landlord")
        landlord_email = property_doc.get("email", "")
        
        # Capture signature metadata
        signature_metadata = await capture_signature_metadata(
            request=request,
            signer_name=landlord_name,
            signer_email=landlord_email,
            document_id=contract_id,
            signature_data=signature
        )
        
        update_fields["landlord_signed_date"] = signed_date
        update_fields["landlord_signature_metadata"] = signature_metadata
        update_fields["updated_at"]= signed_date
        # Save landlord signature on property for reuse
        await db["properties"].update_one(
            {"_id": contract["property_id"]},
            {"$set": {"landlord_signature": signature,"landlord_signature_metadata":signature_metadata}}
        )

    else:
        raise HTTPException(400, "Invalid role")

    await db["property_leases"].update_one(
        {"_id": ObjectId(contract_id)},
        {"$set": update_fields}
    )
    
    
    return {
        "message": f"{role.capitalize()} signed successfully",
        "contract_id": contract_id,
        "status": update_fields.get("status"),
        "signed_at": signed_date.isoformat(),
        "metadata_captured": True
    }

  

@router.get("/contracts/{contract_id}/pdf")
async def get_contract_pdf(request: Request, contract_id: str):
    """Generate and return contract PDF with complete data"""
    db = request.app.state.adb
  
    # Validate contract_id
    if not ObjectId.is_valid(contract_id):
        raise HTTPException(400, "Invalid contract ID format")
    
    # Fetch contract
    contract = await db["property_leases"].find_one({"_id": ObjectId(contract_id)})
    if not contract:
        raise HTTPException(404, "Contract not found")
    
    # Prepare complete contract data
    contract_data = await prepare_contract_data(db, contract, request)
   
    # Generate PDF (you'll need to implement this function)
    pdf_path = await generate_pdf(
        "contract0.html", 
        contract_data, 
        prefix="contract_"
    )
    
    # Generate filename
    tenant_name = contract_data["tenant"]["full_name"].replace(" ", "_")
    unit_number = contract_data["unit"]["unit_number"].replace(" ", "_")
    filename = f"Tenancy_Agreement_{tenant_name}_{unit_number}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=filename
    )

@router.post("/", response_model=PropertyInDB)
async def create_property(request: Request, data: PropertyCreate,
                          user: SessionInfo = Depends(get_current_user)):
    """Create a new property owned by current user"""
    db = request.app.state.adb
    id = ObjectId()
    import json

    await db["properties_data"].insert_one({
        "raw_json": json.dumps(data.model_dump(by_alias=True), default=str)
    })
    prop = PropertyInDB(**data.model_dump(),id=str(id), owner_id=user.user_id)
  
    if prop.gallery:
        for u in prop.gallery:
            image = await upload_image(u.url)
            u.url = image.get("url")
        
    if(not prop.custom_image and len(prop.gallery)>0):
        prop.custom_image=prop.gallery[0].url
    
    
    
     # Auto-generate units if enabled
    if prop.auto_generate_units:
        generated_units = auto_generate_units(prop.model_dump())
        inserted = await batch_insert_units(generated_units,prop.id,db)
        print(f"Inserted {inserted} as initial units")
        prop.units_total= len(generated_units)
        prop.units_occupied = 0
        prop.occupancy_rate=0.0
    await db["properties"].insert_one(prop.model_dump(by_alias=True))
    
    return prop
@router.patch("/{property_id}", response_model=PropertyResponse)
async def update_property(
    request: Request,
    property_id: str,
    data: PropertyUpdate,
    user: SessionInfo = Depends(get_current_user)
):
    """
    Update property - only fields that changed are updated
    
    Permissions:
    - Owner/Admin: Full access
    - Property Manager: Limited access (no structural changes)
    
    Returns:
        Updated property with list of changed fields
    """
    adb = request.app.state.adb
    property_doc = await adb.properties.find_one({"_id": (property_id)})
    if not property_doc:
        raise HTTPException(status_code=404, detail="Property not found")
    updates = data.model_dump(by_alias=True)
    updates["updated_by"]=user.user_id
    updates["propertyId"]=property_id
    await adb.properties_changes.insert_one(updates)
    
    
    return property_doc
    
@router.get("/", response_model=PropertyListResponse)
async def list_properties(request: Request, user: SessionInfo = Depends(get_current_user)):
    """
    List all properties owned by the current user, including unit summaries
    (units, tenants, utilities, occupancy metrics).
    """
    db = request.app.state.adb

    # Fetch all properties for this owner
    props = await db["properties"].find({"owner_id": user.user_id}).to_list(None)
    if not props:
        return PropertyListResponse(
            total=0,
            page=1,
            limit=10,
            properties=[]
        )

    async def enrich_property(p):
        # Fetch all units for this property
        units = await db["units"].find({"propertyId": str(p["_id"])}).to_list(None)
        # enriched_units = []
        for u in units:
            tenant_name = None
            if u.get("tenant_id"):
                tenant = await db["property_tenants"].find_one({"_id": u["tenant_id"]}, {"full_name": 1})
                tenant_name = tenant["full_name"] if tenant else None
            u["tenant_name"]=tenant_name
            u["_id"]=str(u["_id"])
        #     enriched_units.append(UnitListItem(**u).model_dump(by_alias=True))

        total_units = len(units)
        occupied_units = sum(1 for u in units if u.get("occupied"))
        occupancy_rate = (occupied_units / total_units) * 100 if total_units else 0.00
        p["property_units"]=units
        p["_id"]= str(p["_id"])
        p["unitsTotal"] = total_units  # Changed from units_total
        p["unitsOccupied"] = occupied_units  # Changed from units_occupied
        p["occupancyRate"] = occupancy_rate  # Changed from occupancy_rate
        # p["units"] = enriched_units
        p["createdAt"] = p.get("createdAt") or p.get("created_at")  # Handle both cases
        p["updatedAt"] = p.get("updatedAt") or p.get("updated_at")  # Handle both cases
        
        return p

    results = await asyncio.gather(*(enrich_property(p) for p in props))

    return {
        "total": len(results),
        "page": 1,
        "limit": len(results),
        "properties": [
            PropertyResponse(**prop).model_dump(by_alias=True) 
            for prop in results
        ]
    }

@router.get("/{property_id}", response_model=PropertyDetailResponse)
async def get_property_summary(
    request: Request,
    property_id: str,
    page: int = 1,
    limit: int = 20,
    include_tenants: bool = True,
    user: SessionInfo = Depends(get_current_user)
):
    return await get_property_detail(request,property_id,user,page,limit,include_tenants)
        
            

@router.get("/{property_id}/units")
async def list_property_units(request: Request, property_id: str, user: SessionInfo = Depends(get_current_user)):
    """List all units under a given property."""
    db = request.app.state.adb

    # Ensure property belongs to user
    prop = await db["properties"].find_one({"_id": property_id, "owner_id": user.user_id})
    if not prop:
        raise HTTPException(404, "Property not found or unauthorized")

    # Fetch all units
    units = await db["units"].find({"property_id": property_id}).to_list(None)

    # Attach tenant info for occupied units
    for u in units:
        if u.get("tenant_id"):
            tenant = await db["property_tenants"].find_one({"_id": u["tenant_id"]}, {"full_name": 1})
            u["tenant_name"] = tenant["full_name"] if tenant else None

    return {
        "property_id": property_id,
        "property_name": prop["name"],
        "units": units
    }

@router.post("/tenant/add", response_model=Tenant)
async def add_tenant(request: Request, tenant: Tenant):
    """Add a tenant and mark unit occupied"""
    db = request.app.state.adb
    await db["property_tenants"].insert_one(tenant.model_dump(by_alias=True))
    await db["units"].update_one(
        {"_id": tenant.unit_id},
        {"$set": {"occupied": True, "tenant_id": tenant.id}}
    )
    return tenant


@router.delete("/tenant/{tenant_id}")
async def remove_tenant(request: Request, tenant_id: str):
    """Remove tenant and free up their unit"""
    db = request.app.state.adb
    tenant = await db["property_tenants"].find_one({"_id": tenant_id})
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    await db["units"].update_one(
        {"_id": tenant["unit_id"]},
        {"$set": {"occupied": False, "tenant_id": None}}
    )
    await db["property_tenants"].delete_one({"_id": tenant_id})
    return {"message": "Tenant removed"}


@router.post("/units/{unit_id}/meter")
async def update_water_meter(request: Request, unit_id: str, payload: MeterUpdate):
    """Record current water meter reading for a unit"""
    db = request.app.state.adb
    unit = await db["units"].find_one({"_id": unit_id})
    if not unit:
        raise HTTPException(404, "Unit not found")

    await db["units"].update_one(
        {"_id": unit_id},
        {"$set": {"water_meter_current": payload.current_reading}}
    )
    return {"message": f"Meter updated for {unit['name']}", "reading": payload.current_reading}

@router.get("/invoices/summary")
async def invoices_summary(
    request: Request,
    property_id: str | None = Query(
        default=None,
        description="Filter by property ID (optional). If not provided, returns all properties accessible to user."
    ),
    month: str = Query(default=(date.today() - timedelta(days=60)).strftime("%Y-%m"), description="Format: YYYY-MM"),
    inv_status: str | None = Query(
        default=None,
        description="Invoice status filter: paid | partial | issued | overpaid | any (optional)"
    ),
    q: str = Query("", description="Search by tenant name, email, or unit"),
    user: Any = Depends(get_current_user)
):
    """
    Fetches filtered invoices and computes financial + forecast metrics for a given property/month.
    """
    db = request.app.state.adb

    # --- 1️⃣ Authorization ---
    if property_id:
        await authorize_property(db, property_id, user.user_id)
        query[ "property_id"]= property_id

    # --- 2️⃣ Date range from month ---
    try:
        start_date = datetime.strptime(month, "%Y-%m")
    except ValueError:
        raise ValueError("Invalid month format. Expected YYYY-MM")
    next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_date = next_month

    # --- 3️⃣ Base query ---
    query: Dict[str, Any] = {
       
        # "date_issued": {"$gte": start_date, "$lt": end_date}
    }
    
    if property_id:
        await authorize_property(db, property_id, user.user_id)
        query[ "property_id"]= property_id
    
    

    # --- 4️⃣ Optional filters ---
    if inv_status and inv_status.lower() != "any":
        query["status"] = inv_status.lower()

    if q:
        query["$or"] = [
            {"tenant_name": Regex(q, "i")},
            {"tenant_email": Regex(q, "i")},
            {"unit_id": Regex(q, "i")},
        ]
   
    # --- 5️⃣ Fetch invoices + related entries in parallel ---
    invoices_cursor = db.property_invoices.find(query)
    invoices = await invoices_cursor.to_list(None)

    tenant_ids = [str(inv["tenant_id"]) for inv in invoices if "tenant_id" in inv]
    ledger_query={
       
        "date": {"$gte": start_date, "$lt": end_date}
    }
    units_query={}
    if property_id:
        ledger_query["property_id"]= str(property_id)
        units_query["property_id"]= str(property_id)
        
    ledger_query["tenant_id"]= {"$in": tenant_ids}
    
    ledger_entries = await db.property_ledger_entries.find(ledger_query).to_list(None)
    
    units = await db.units.find(units_query).to_list(None)
        
   

    # --- 6️⃣ Detect moving out tenants ---
    moving_out_next_month = []

    # --- 7️⃣ Compute analytics ---
    total_units = len(units)
    vacant_units = len([u for u in units if u.get("status") != "occupied"])
    occupied_units = len([u for u in units if u.get("status") == "occupied"])
    
   
    
    invoices = [Invoice(**inv) for inv in invoices]
    ledger_entries   = [
        LedgerEntry(**{**entry, "_id": str(entry.pop("_id", ""))})
        for entry in ledger_entries
    ]
    
    
    financial_metrics = compute_financial_metrics(
        invoices=invoices,
        ledger_entries=ledger_entries,
        moving_out_next_month=moving_out_next_month,
        total_units=total_units,
        vacant_units=vacant_units,
        occupied_units=occupied_units,
    )
   
    forecast_metrics = compute_forecast_metrics(invoices, ledger_entries)

    # --- 8️⃣ Response payload ---
 
    from core.MongoORJSONResponse import normalize_bson
    # print(invoices)
    results= {
        "property_id": property_id,
        "month": month,
        "filters": {
            "status": inv_status or "any",
            "search": q or "",
        },
        "metrics": {
            "financial": financial_metrics,
            "forecast": forecast_metrics,
        },
        "counts": {
            "total_units": total_units,
            "vacant_units": vacant_units,
            "occupied_units": occupied_units,
        },
        "invoices": invoices,
    }
   
    
    return results
    
@router.post("/invoices/generate")
async def generate_invoices(request: Request,
                            property_id: str = Body(...),
                            month: str = Body(...),
                            user: SessionInfo = Depends(get_current_user)):
    """Generate monthly invoices for occupied units."""
    db = request.app.state.adb
    await authorize_property(db, property_id, user.user_id)

    # utilities = {
    #     u["name"].lower(): u
    #     for u in await db["utilities"].find({"active": True}).to_list(100)
    # }
    # water_utility = utilities.get("water")

    # async with await db.client.start_session() as s:
    #     async with s.start_transaction():
    for unit in await db["units"].find({"property_id": property_id, "occupied": True}).to_list(200):
                print("Has Unit")
                tenant = await db["property_tenants"].find_one({"unit_id": unit["_id"]})
                if not tenant:
                    continue
                print("Has Tenant")
                items = [{"label": "Rent", "amount": unit["price"]}]
               
                # Water usage logic
                water_utility:Utility = find_utility(unit, "water")
                
                if water_utility:
                   
                    prev = unit.get("water_meter_base", 0)
                    current = unit.get("water_meter_current", prev)
                    usage_units = max(0, current - prev)
                    rate = unit.get("water_rate_per_unit", water_utility.price_rate_per_unit)
                    amount = round(usage_units * rate, 2)
                    items.append({
                        "label": f"Water ({usage_units:.2f} m³)",
                        "amount": amount,
                        "usage_units": usage_units
                    })
                    # Update base only after success
                    await db["units"].update_one(
                        {"_id": unit["_id"]},
                        {"$set": {"water_meter_base": current}},
                        # session=s
                    )

                # Other utilities
                for u in unit.get("utilities", []):
                    u_lower = u.get("name").lower()
                    if u_lower == "water":
                        continue
                    _utility:Utility = find_utility(unit, u_lower)
                    if _utility:
                        items.append({
                            "label": _utility.name.capitalize(),
                            "amount": _utility.price_per_month
                        })
                       

                inv = Invoice(
                    tenant_id=tenant["_id"],
                    property_id=property_id,
                    unit_id=unit["_id"],
                    month=month,
                    items=[LineItem(**i) for i in items]
                )
                inv = await recalc_invoice(inv.model_dump())
                await db["invoices"].insert_one(inv)
                await db["ledger"].insert_one({
                    "tenant_id": tenant["_id"],
                    "entry_type": "invoice",
                    "description": f"Invoice for {month}",
                    "debit": inv["total"],
                    "balance_after": inv["balance"],
                    "created_at": datetime.now(timezone.utc)
                })
    return {"message": "Invoices generated successfully"}


@router.get("/tenants/insights/best")
async def get_best_performing_tenants(
    request: Request,
    sort_by_performance: str = Query("best_tenant"),
    status: str = Query("all"),
    search: str = Query(None),
    property_id: str | None = Query(None, description="Filter by property ID"),
    sort_by: str = Query("on_time_rate", description="Sort field"),
    order: int = Query(-1, description="Sort direction (-1=desc, 1=asc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    Paginated, ranked tenant performance insights
    combining financial, utility, and behavioral metrics.
    """
    db = request.app.state.adb
    match = {"active": True}
    if property_id:
        match["property_id"] = property_id
    if status != "all":
        match["status"] = status
    if search:
        match["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}},
            {"property_name": {"$regex": search, "$options": "i"}},
            {"unit_name": {"$regex": search, "$options": "i"}},
        ]
        
    sort_field = f"meta.finance_metrics.{sort_by}" if not sort_by.startswith("meta.") else sort_by
    skip = (page - 1) * page_size

    total_count = await db.property_tenants.count_documents(match)

    cursor = (
        db.property_tenants.find(match)
        .sort([(sort_field, order)])
        .skip(skip)
        .limit(page_size)
    )
    
   

    tenants = await cursor.to_list(length=page_size)
    results = []

    for t in tenants:
        meta = t.get("meta", {})
        fm = meta.get("finance_metrics", {})
        rc = meta.get("risk_components", {})
        utils = fm.get("utility_summary", {})
        behavior_metrics = fm.get("behavior_metrics", {})
        # Average daily utility use across utilities
        # avg_daily_utility_use = (
        #     mean([v.get("usage_avg_per_day", 0) for v in utils.values()])
        #     if utils else 0
        # )
        
        avg_daily_utility_use = {
            name: {
                "total": round(v.get("usage_avg_per_day", 0), 3),
                "unit": v.get("unit", "")
            }
            for name, v in utils.items()
        }

        total_outstanding = fm.get("total_outstanding", 0)
        total_paid = fm.get("total_invoice_paid", 0)
        total_util_amt = sum(v.get("amount", 0) for v in utils.values())
        utility_cost_ratio = (
            round((total_util_amt / total_paid) * 100, 2)
            if total_paid > 0 else 0
        )

        # Extract property/unit display info
        property_name = meta.get("property", {}).get("name")
        unit_name = None
        if meta.get("property", {}).get("units"):
            unit_name = meta["property"]["units"][0].get("unitName", None)
        elif t.get("units_id"):
            unit_name = t["units_id"][0]

        results.append({
            "tenant_id": str(t["_id"]),
            "name": t.get("full_name"),
            "property_id": t.get("property_id"),
            "property_name": property_name,
            "unit_name": unit_name,
            "on_time_rate": fm.get("on_time_rate"),
            "collection_rate": fm.get("collection_rate"),
            "outstanding_balance": total_outstanding,
            "tenant_stability_index": fm.get("tenant_stability_index"),
            "avg_delay_days": fm.get("avg_delay_days"),
            "days_to_lease_expiry": fm.get("days_to_lease_expiry"),
            "avg_daily_utility_use": avg_daily_utility_use,
            "utility_cost_ratio": utility_cost_ratio,
            "risk_score": rc.get("risk_score", meta.get("risk_score")),
            "risk_level": rc.get("risk_level"),
            "early_payment_score": rc.get("early_payment_score"),
            "payment_volatility_score": rc.get("payment_volatility_score"),
            "consistency_score": rc.get("consistency_score"),
            "tenure":fm.get("months_as_tenant",0),
            "utility_summary":fm.get("utility_summary",{}),
            "meta":meta,
            "recommendation": (
                meta.get("recommendations", [{}])[0].get("message", "")
            ),
            "behavior_metrics":behavior_metrics,
            "last_enriched": meta.get("last_enriched"),
        })

    total_pages = ceil(total_count / page_size)
    
    
    def filter_tenants(tenants: list[dict], filter_type: str) -> list[dict]:
        """
        Filters and ranks tenants based on the selected filter type.
        Expected tenant fields:
        - meta.tenant_score
        - meta.on_time_rate
        - meta.collection_rate
        - meta.late_count
        - meta.early_count
        - meta.balance_due
        - behavior_metrics.move_in_date
        - behavior_metrics.maintenance_requests
        - behavior_metrics.violations
        """
        if not tenants:
            return []

        # Helper: rank best tenants by composite performance
        def rank_best_tenants(data: list[dict]) -> list[dict]:
            for t in data:
                m = t.get("meta", {})
                score = (
                    (m.get("tenant_score", 0) * 0.5)
                    + (m.get("on_time_rate", 0) * 0.3)
                    + (m.get("collection_rate", 0) * 0.2)
                )
                t.setdefault("meta", {})["rank_score"] = round(score, 3)
            return sorted(data, key=lambda x: x["meta"].get("rank_score", 0), reverse=True)

        # === Filter logic ===
        match filter_type:
            case "best_tenant":
                return rank_best_tenants(tenants)

            case "with_arrears":
                return [t for t in tenants if t.get("outstanding_balance",0) > 0]

            case "late_payers":
                return sorted(
                    [t for t in tenants if t.get("behavior_metrics", {}).get("rent_payment_history",{}).get("late",0) > 0],
                    key=lambda x: x["behavior_metrics"].get("rent_payment_history",{}).get("late",0),
                    reverse=True,
                )

            case "early_payers":
                return sorted(
                    [t for t in tenants if t.get("behavior_metrics", {}).get("rent_payment_history",{}).get("on_time",0) > 0],
                    key=lambda x: x["behavior_metrics"].get("rent_payment_history",{}).get("on_time",0),
                    reverse=True,
                )

            case "longest_tenure":
                return sorted(
                    tenants,
                    key=lambda x: x.get("tenure",0),
                    reverse=True,
                )
            case "high_water_user":
                return sorted(
                    tenants,
                    key=lambda x: x.get("avg_daily_utility_use", {}).get("Water", {}).get("total",0),
                    reverse=True
                )

            case "high_maintenance":
                return sorted(
                    [t for t in tenants if t.get("behavior_metrics", {}).get("extra",{}).get("maintenance_requests",0) > 0],
                    key=lambda x: x.get("behavior_metrics", {}).get("extra",{}).get("maintenance_requests", 0),
                    reverse=True,
                )

            case "violations":
                return sorted(
                    [t for t in tenants if t.get("behavior_metrics", {}).get("violations", 0) > 0],
                    key=lambda x: x.get("behavior_metrics", {}).get("violations", 0),
                    reverse=True,
                )
            case 'move_out_notice':
                return sorted(
                    [t for t in tenants if t.get("behavior_metrics", {}).get("extra",{}).get("move_out_notice_given",0) > 0],
                    key=lambda x: x["behavior_metrics"].get("extra",{}).get("move_out_notice_given",0),
                    reverse=True,
                )
            case _:
                return tenants
    
    snapshot=TenantSnapshotManager(db,24*5)
    
    return {
        "criteria": sort_field,
        "snapshot":await snapshot.get_snapshot(),
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "tenants": filter_tenants(results,sort_by_performance),
    }
    
    
@router.post("/invoice/payment", response_model=Payment)
async def record_payment(request: Request, payment: PaymentCreate):
    """Record a payment and update invoice + ledger."""
    try:
        db = request.app.state.adb
    
        inv = await db["property_invoices"].find_one({"_id": ObjectId(payment.invoice_id)})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        ledger=Ledger(db)
        created_at=datetime.now(timezone.utc)
        pay_date=payment.pay_date if payment.pay_date else created_at
        inv['tenant_id']=str(inv['tenant_id'])
        entries=await ledger.post_payment_to_ledger(Invoice(**inv),amount=payment.amount,payment_date=pay_date)
       
        pay_data = payment.model_dump(by_alias=True)
    
        pay_data=Payment(
            **pay_data,
            tenant_id=str(inv['tenant_id']),
        )
        
        
        
        result= await db["property_payments"].insert_one(pay_data.model_dump(by_alias=True))
        pay_data.id=result.inserted_id
        # new_payment = await db["property_payments"].find_one({"_id": result.inserted_id})
        return pay_data
    except Exception as e:
        print(e)
    return JSONResponse({"error": str(e)}, status_code=500)


# ===============================================================
# PDF GENERATION
# ===============================================================

@router.get("/invoice/{invoice_id}/pdf")
async def get_invoice_pdf(request: Request, invoice_id: str, background_tasks: BackgroundTasks):
    """Serve or queue generation of invoice PDF."""
    db = request.app.state.adb
    invoice = await db["invoices"].find_one({"_id": ObjectId(invoice_id)})
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    tenant = await db["property_tenants"].find_one({"_id": invoice["tenant_id"]})
    prop = await db["properties"].find_one({"_id": invoice["property_id"]})

    if invoice.get("pdf_path") and os.path.exists(invoice["pdf_path"]):
        return FileResponse(invoice["pdf_path"])

    ctx = {
        "invoice": invoice,
        "tenant": tenant,
        "property": prop,
        "today": datetime.now().strftime("%B %d, %Y")
    }
    background_tasks.add_task(generate_pdf, "invoice_template.html", ctx, "invoice_")
    return JSONResponse({"message": "Invoice PDF is being generated"})


@router.get("/payment/{payment_id}/receipt")
async def get_receipt_pdf(request: Request, payment_id: str):
    """Generate and return payment receipt PDF."""
    db = request.app.state.adb
    payment = await db["payments"].find_one({"_id": payment_id})
    if not payment:
        raise HTTPException(404, "Payment not found")

    invoice = await db["invoices"].find_one({"_id": payment["invoice_id"]})
    tenant = await db["property_tenants"].find_one({"_id": payment["tenant_id"]})
    prop = await db["properties"].find_one({"_id": invoice["property_id"]})

    pdf_path = await generate_pdf("receipt_template.html", {
        "payment": payment,
        "invoice": invoice,
        "tenant": tenant,
        "property": prop,
        "today": datetime.now().strftime("%B %d, %Y")
    }, prefix="receipt_")
    return FileResponse(pdf_path)


# ===============================================================
# REPORTS
# ===============================================================

@router.get("/reports/summary")
async def monthly_summary(request: Request, month: str = Query(..., example="2025-10")):
    """
    Enriched monthly summary with property-level and tenant-level analytics.
    Includes deposits, late payers, and best payers.
    Runs DB lookups concurrently for speed.
    """
    db = request.app.state.adb

    # === 1. Aggregate invoices by property ===
    invoice_pipeline = [
        {"$match": {"month": month}},
        {"$group": {
            "_id": "$property_id",
            "total_rent": {"$sum": "$total"},
            "collected": {"$sum": "$paid_amount"},
            "invoices": {"$push": "$$ROOT"}
        }}
    ]
    prop_summaries = await db["invoices"].aggregate(invoice_pipeline).to_list(None)

    if not prop_summaries:
        return {"message": f"No invoices found for {month}", "month": month}

    # === 2. Parallel fetch other collections ===
    tenants_task = db["property_tenants"].find({}, {"full_name": 1, "email": 1}).to_list(None)
    units_task = db["units"].find({}, {"occupied": 1}).to_list(None)
    deposits_task = db["payments"].aggregate([
        {"$match": {"type": "deposit"}},  # ensure you mark deposit payments with type='deposit'
        {"$group": {"_id": None, "total_deposits": {"$sum": "$amount"}}}
    ]).to_list(1)

    property_tasks = [
        db["properties"].find_one({"_id": p["_id"]}, {"name": 1})
        for p in prop_summaries
    ]

    tenants_data, units, deposit_summary, *property_results = await asyncio.gather(
        tenants_task, units_task, deposits_task, *property_tasks
    )

    tenants = {t["_id"]: t for t in tenants_data}

    total_deposits = (
        deposit_summary[0]["total_deposits"] if deposit_summary else 0
    )

    # === 3. Compute totals ===
    total_rent = sum(p["total_rent"] for p in prop_summaries)
    total_collected = sum(p["collected"] for p in prop_summaries)
    unpaid = total_rent - total_collected

    # === 4. Build property-level summaries ===
    properties = []
    for p, prop_doc in zip(prop_summaries, property_results):
        prop_name = prop_doc["name"] if prop_doc else "Unknown Property"
        overpaid = sum(max(inv["paid_amount"] - inv["total"], 0) for inv in p["invoices"])

        properties.append({
            "property_id": str(p["_id"]),
            "name": prop_name,
            "total_rent": round(p["total_rent"], 2),
            "collected": round(p["collected"], 2),
            "unpaid": round(p["total_rent"] - p["collected"], 2),
            "overpaid": round(overpaid, 2),
            "collection_rate": f"{(p['collected'] / p['total_rent'] * 100):.1f}%" if p["total_rent"] else "0%"
        })

    # === 5. Calculate occupancy ===
    total_units = len(units)
    occupied = sum(1 for u in units if u.get("occupied"))
    occupancy_rate = f"{(occupied / total_units * 100) if total_units else 0:.2f}%"

    # === 6. Identify best and late payers ===
    invoices = [i for p in prop_summaries for i in p["invoices"]]
    loop = asyncio.get_event_loop()
    best_payers, late_payers = await asyncio.gather(
        loop.run_in_executor(None, lambda: sorted(invoices, key=lambda i: i.get("paid_amount", 0), reverse=True)[:3]),
        loop.run_in_executor(None, lambda: [i for i in invoices if i.get("status") == "late"])
    )

    best_payer_list = [
        {
            "tenant": tenants.get(bp["tenant_id"], {}).get("full_name", "Unknown"),
            "amount_paid": bp["paid_amount"],
            "property_id": str(bp["property_id"]),
            "month": bp["month"]
        } for bp in best_payers
    ]

    late_payer_list = [
        {
            "tenant": tenants.get(lp["tenant_id"], {}).get("full_name", "Unknown"),
            "balance": lp.get("balance", 0),
            "property_id": str(lp["property_id"]),
            "month": lp["month"]
        } for lp in late_payers
    ]

    # === 7. Return full summary ===
    return {
        "month": month,
        "totals": {
            "properties_count": len(prop_summaries),
            "total_rent": round(total_rent, 2),
            "rent_collected": round(total_collected, 2),
            "unpaid": round(unpaid, 2),
            "total_deposits": round(total_deposits, 2),
            "occupancy_rate": occupancy_rate
        },
        "by_property": properties,
        "best_payers": best_payer_list,
        "late_payers": late_payer_list
    }
@router.post("/contracts/{contract_id}/deposit")
async def record_deposit_payment(request: Request, contract_id: str, data: DepositTransaction):
    db = request.app.state.adb
    contract = await db["property_leases"].find_one({"_id": ObjectId(contract_id)})
    if not contract:
        raise HTTPException(404, "Contract not found")

    # Add deposit transaction
    contract.setdefault("deposit_transactions", []).append(data.model_dump())
    
    contract["deposit_paid"] = sum(d["amount"] for d in contract["deposit_transactions"])
    # contract["deposit_balance"] = max(0, contract["deposit_amount"] - contract["deposit_paid"])
    # True balance (can be negative if overpaid)
    contract["deposit_balance"] = round(contract["deposit_amount"] - contract["deposit_paid"], 2)

    # Optional derived field for clarity
    if contract["deposit_balance"] < 0:
        contract["overpaid_deposit_amount"] = abs(contract["deposit_balance"])
    else:
        contract["overpaid_deposit_amount"] = 0.0
    contract["updated_at"] = datetime.now(timezone.utc)
    
    await db["property_leases"].update_one(
    {"_id": ObjectId(contract_id)},
    {
        "$set": contract
    },
    upsert=True  # ✅ create the document if it doesn't exist
)

    # Add ledger entry
    await db["ledger"].insert_one({
        "tenant_id": contract["tenant_id"],
        "entry_type": "deposit_payment",
        "description": f"Deposit payment of ${data.amount}",
        "credit": data.amount,
        "balance_after": contract["deposit_balance"],
        "created_at": datetime.now(timezone.utc)
    })

    return {
        "message": "Deposit payment recorded",
        "deposit_paid": contract["deposit_paid"],
        "deposit_balance": contract["deposit_balance"]
    }
@router.get("/metrics")
async def get_property_metrics(
    request: Request,
    month: Optional[str] = Query(None, example="2025-10"),
    user: SessionInfo = Depends(get_current_user),
):
    """
    Get metrics for all properties owned by the user:
    - Number of units
    - Occupancy rate
    - Deposits collected
    - Rent expected vs collected
    - Previous month balance
    - Probable defaulters (low payment ratio)
    """
    db = request.app.state.adb

    # --- Filters ---
    month = month or datetime.now().strftime("%Y-%m")
    prev_month = (
        (datetime.strptime(month, "%Y-%m") - timedelta(days=30)).strftime("%Y-%m")
    )

    # --- Fetch all properties for this owner ---
    properties = await db["properties"].find({"owner_id": user.user_id}).to_list(None)
    if not properties:
        return []

    # --- Async gather metrics per property ---
    async def compute_metrics(prop):
        prop_id = prop["_id"]

        # Units
        total_units = await db["units"].count_documents({"property_id": prop_id})
        occupied_units = await db["units"].count_documents(
            {"property_id": prop_id, "occupied": True}
        )
        occupancy_rate = (occupied_units / total_units * 100) if total_units else 0

        # Invoices (current month)
        invoices = await db["invoices"].find({"property_id": prop_id, "month": month}).to_list(None)
        total_expected = sum(inv.get("total", 0) for inv in invoices)
        total_collected = sum(inv.get("paid_amount", 0) for inv in invoices)
        probable_defaults = [
            inv for inv in invoices if inv.get("balance", 0) > 0 and inv.get("status") != "paid"
        ]

        # Previous month balance
        prev_invoices = await db["invoices"].find(
            {"property_id": prop_id, "month": prev_month}
        ).to_list(None)
        prev_balance = sum(inv.get("balance", 0) for inv in prev_invoices)

        # Deposits
        contracts = await db["property_leases"].find({"property_id": prop_id}).to_list(None)
        deposits_paid = sum(c.get("deposit_paid", 0) for c in contracts)
        deposits_due = sum(
            max(c.get("deposit_amount", 0) - c.get("deposit_paid", 0), 0)
            for c in contracts
        )

        return {
            "property_id": str(prop_id),
            "name": prop.get("name"),
            "location": prop.get("location"),
            "units_total": total_units,
            "units_occupied": occupied_units,
            "occupancy_rate": round(occupancy_rate, 2),
            "rent_expected": round(total_expected, 2),
            "rent_collected": round(total_collected, 2),
            "prev_month_balance": round(prev_balance, 2),
            "probable_defaulters": len(probable_defaults),
            "deposits_paid": round(deposits_paid, 2),
            "deposits_due": round(deposits_due, 2),
            "collection_rate": f"{(total_collected / total_expected * 100):.1f}%" if total_expected else "0%",
        }

    metrics = await asyncio.gather(*(compute_metrics(p) for p in properties))

    # --- Sort by occupancy descending ---
    metrics.sort(key=lambda x: x["occupancy_rate"], reverse=True)
    return {"month": month, "properties": metrics}

@router.get("/{property_id}/tenants")
async def get_property_tenants(
    request: Request, property_id: str, user: SessionInfo = Depends(get_current_user)
):
    """
    Drill-down: list tenants in a property with their invoices and payment status.
    """
    db = request.app.state.adb

    # Authorization
    prop = await db["properties"].find_one({"_id": (property_id), "owner_id": user.user_id})
    if not prop:
        raise HTTPException(404, "Property not found or unauthorized")

    # Find tenants
    tenants = await db["property_tenants"].find({"property_id": property_id}).to_list(None)

    async def enrich_tenant(t):
        invoices = await db["invoices"].find({"tenant_id": t["_id"]}).to_list(None)
        payments = await db["payments"].find({"tenant_id": t["_id"]}).to_list(None)

        unpaid = [i for i in invoices if i.get("status") != "paid"]
        paid = [i for i in invoices if i.get("status") == "paid"]

        return {
            "tenant_id": str(t["_id"]),
            "full_name": t["full_name"],
            "unit_id": t.get("unit_id"),
            "email": t.get("email"),
            "phone": t.get("phone"),
            "invoices_summary": {
                "total_invoices": len(invoices),
                "paid": len(paid),
                "unpaid": len(unpaid),
                "total_due": round(sum(i.get("balance", 0) for i in unpaid), 2),
                "total_paid": round(sum(i.get("paid_amount", 0) for i in paid), 2),
            },
            "invoices": invoices,
            "payments": payments,
        }

    tenants_detail = await asyncio.gather(*(enrich_tenant(t) for t in tenants))

    return {
        "property": {"id": str(prop["_id"]), "name": prop["name"]},
        "tenants": serialize_doc(tenants_detail),
    }
    
@router.get("/{property_id}/summary")
async def get_property_summary(request: Request, property_id: str, user: SessionInfo = Depends(get_current_user)):
    """Summary view for one property — key metrics and quick stats."""
    db = request.app.state.adb
    prop = await db["properties"].find_one({"_id": property_id, "owner_id": user.user_id})
    if not prop:
        raise HTTPException(404, "Property not found")

    units = await db["units"].find({"property_id": property_id}).to_list(None)
    tenants = await db["property_tenants"].count_documents({"property_id": property_id})
    invoices = await db["invoices"].find({"property_id": property_id}).to_list(None)

    total_units = len(units)
    occupied = sum(1 for u in units if u.get("occupied"))
    total_rent = sum(i.get("total", 0) for i in invoices)
    total_collected = sum(i.get("paid_amount", 0) for i in invoices)
    total_due = total_rent - total_collected

    return {
        "property_id": str(prop["_id"]),
        "name": prop["name"],
        "units_total": total_units,
        "units_occupied": occupied,
        "occupancy_rate": round((occupied / total_units * 100) if total_units else 0, 2),
        "tenants_count": tenants,
        "rent_collected": total_collected,
        "rent_due": total_due,
        "collection_rate": f"{(total_collected / total_rent * 100):.1f}%" if total_rent else "0%",
    }


@router.get("/tenants/due")
async def get_due_tenants(request: Request, days: int = Query(5)):
    """List tenants whose invoices are due or overdue within N days."""
    db = request.app.state.adb
    today = datetime.now(timezone.utc)
    threshold = today - timedelta(days=days)

    due_invoices = await db["invoices"].find({
        "due_date": {"$lte": today, "$gte": threshold},
        "status": {"$ne": "paid"}
    }).to_list(None)

    result = []
    for inv in due_invoices:
        tenant = await db["property_tenants"].find_one({"_id": inv["tenant_id"]}, {"full_name": 1, "phone": 1})
        if tenant:
            result.append({
                "tenant": tenant["full_name"],
                "phone": tenant.get("phone"),
                "amount_due": inv["balance"],
                "due_date": inv["due_date"]
            })
    return result


@router.get("/ledger/{tenant_id}")
async def get_tenant_ledger(request: Request, tenant_id: str):
    """Full financial ledger for a tenant."""
    db = request.app.state.adb
    entries = await db["ledger"].find({"tenant_id": tenant_id}).sort("created_at", 1).to_list(None)
    return {"tenant_id": tenant_id, "transactions": serialize_doc(entries)}

@router.get("/analytics/trends")
async def get_trends(request: Request, months: int = 6, user: SessionInfo = Depends(get_current_user)):
    """Rent trends for last N months across all properties."""
    db = request.app.state.adb
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30 * months)
    start_month = start_date.strftime("%Y-%m")

    pipeline = [
        {"$match": {"month": {"$gte": start_month}}},
        {"$group": {
            "_id": "$month",
            "expected": {"$sum": "$total"},
            "collected": {"$sum": "$paid_amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    trend_data = await db["invoices"].aggregate(pipeline).to_list(None)
    return {"months": months, "trend": serialize_doc(trend_data)}

@router.post("/auto/invoice/generate")
async def auto_generate_invoices(request: Request, month: Optional[str] = None):
    """Generate invoices for all properties at once."""
    db = request.app.state.adb
    month = month or datetime.now().strftime("%Y-%m")

    props = await db["properties"].find({}).to_list(None)
    results = []
    for prop in props:
        res = await request.app.state.router.url_path_for("generate_invoices")
        results.append({"property": prop["name"], "status": "queued"})
    return {"month": month, "queued_properties": results}




@router.get("/tenant/{tenant_id}/balance")
async def get_tenant_balance(request: Request, tenant_id: str):
    db = request.app.state.adb
    invoices = await db["invoices"].find({"tenant_id": tenant_id}).to_list(None)
    payments = await db["payments"].find({"tenant_id": tenant_id}).to_list(None)
    contracts = await db["property_leases"].find({"tenant_id": tenant_id}).to_list(None)

    total_due = sum(i["balance"] for i in invoices)
    total_paid = sum(p["amount"] for p in payments)
    deposits = sum(c.get("deposit_paid", 0) for c in contracts)
    credit = await db["property_tenants"].find_one({"_id": tenant_id}, {"credit_balance": 1}) or {}
    
    return {
        "tenant_id": tenant_id,
        "due": round(total_due, 2),
        "paid": round(total_paid, 2),
        "deposits": round(deposits, 2),
        "credit_balance": round(credit.get("credit_balance", 0), 2),
        "net_balance": round(total_due - credit.get("credit_balance", 0), 2)
    }



@router.get("/{property_id}/water-usage")
async def get_water_usage(request: Request, property_id: str):
    """Aggregate monthly water usage per property."""
    db = request.app.state.adb
    pipeline = [
        {"$match": {"property_id": property_id, "items.label": {"$regex": "^Water"}}},
        {"$unwind": "$items"},
        {"$match": {"items.label": {"$regex": "^Water"}}},
        {"$group": {
            "_id": "$month",
            "total_usage": {"$sum": "$items.usage_units"},
            "total_billed": {"$sum": "$items.amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    usage = await db["invoices"].aggregate(pipeline).to_list(None)
    return {"property_id": property_id, "water_usage": serialize_doc(usage)}



@router.post("/notifications/due-reminders")
async def send_due_reminders(request: Request, background: BackgroundTasks):
    db = request.app.state.adb
    due_invoices = await db["invoices"].find({"status": "late"}).to_list(None)

    async def send_alerts():
        for inv in due_invoices:
            tenant = await db["property_tenants"].find_one({"_id": inv["tenant_id"]})
            if tenant and tenant.get("phone"):
                # TODO: integrate Twilio here
                print(f"Reminder sent to {tenant['full_name']} for balance {inv['balance']}")

    background.add_task(send_alerts)
    return {"message": f"{len(due_invoices)} reminders queued"}


@router.get("/contracts/{contract_id}/audit")
async def get_contract_audit(request: Request, contract_id: str):
    db = request.app.state.adb
    logs = await db["ledger"].find({"description": {"$regex": contract_id}}).sort("created_at", -1).to_list(None)
    return {"contract_id": contract_id, "audit_trail": serialize_doc(logs)}

@router.get("/contracts/verify/{contract_id}")
async def verify_contract(request: Request, contract_id: str):
    """
    Public endpoint to verify contract authenticity and signature metadata
    Returns verification details without exposing sensitive contract information
    """
    db = request.app.state.adb
    
    # Validate contract ID
    if not ObjectId.is_valid(contract_id):
        raise HTTPException(400, "Invalid contract ID format")
    
    contract = await db["property_leases"].find_one({"_id": ObjectId(contract_id)})
    if not contract:
        raise HTTPException(404, "Contract not found or does not exist")
    
    # Fetch related data
    property_doc = await db["properties"].find_one({"_id": ObjectId(contract["property_id"])})
    tenant_details = contract.get("tenant_details", {})
    
    # Build verification response
    verification_data = {
        "contract_id": contract_id,
        "verification_timestamp": datetime.utcnow().isoformat() + "Z",
        "contract_status": contract.get("status", "pending"),
        "is_valid": True,
        "is_fully_signed": bool(contract.get("tenant_signature") and contract.get("landlord_signature")),
        
        # Basic contract info (non-sensitive)
        "contract_info": {
            "created_at": contract.get("created_at").isoformat() if contract.get("created_at") else None,
            "lease_start": contract.get("start_date").isoformat() if contract.get("start_date") else None,
            "lease_end": contract.get("end_date").isoformat() if contract.get("end_date") else None,
            "property_name": property_doc.get("name", "N/A") if property_doc else "N/A",
            "property_location": property_doc.get("location", "N/A") if property_doc else "N/A"
        },
        
        # Tenant signature verification
        "tenant_signature": {
            "signed": bool(contract.get("tenant_signature")),
            "signed_date": contract.get("tenant_signed_date").isoformat() if contract.get("tenant_signed_date") else None,
            "signer_name": tenant_details.get("full_name", "N/A"),
            "metadata": contract.get("tenant_signature_metadata") if contract.get("tenant_signature") else None
        },
        
        # Landlord signature verification
        "landlord_signature": {
            "signed": bool(contract.get("landlord_signature")),
            "signed_date": contract.get("landlord_signed_date").isoformat() if contract.get("landlord_signed_date") else None,
            "signer_name": property_doc.get("landlord_name", property_doc.get("name", "N/A")) if property_doc else "N/A",
            "metadata": contract.get("landlord_signature_metadata") if contract.get("landlord_signature") else None
        },
        
        # Document integrity
        "document_integrity": {
            "hash_algorithm": "SHA-256",
            "tenant_document_hash": contract.get("tenant_signature_metadata", {}).get("document_hash") if contract.get("tenant_signature_metadata") else None,
            "landlord_document_hash": contract.get("landlord_signature_metadata", {}).get("document_hash") if contract.get("landlord_signature_metadata") else None,
            "tenant_signature_hash": contract.get("tenant_signature_metadata", {}).get("signature_hash") if contract.get("tenant_signature_metadata") else None,
            "landlord_signature_hash": contract.get("landlord_signature_metadata", {}).get("signature_hash") if contract.get("landlord_signature_metadata") else None
        },
        
        # Legal compliance
        "legal_compliance": {
            "governed_by": "Laws of Kenya",
            "evidence_act": "Cap 80",
            "electronic_transactions_act": "Kenya Information and Communications Act",
            "digital_signature_valid": True,
            "tamper_evident": True
        },
        
        # Verification instructions
        "verification_instructions": {
            "how_to_verify": "Compare the document and signature hashes with the original document",
            "hash_verification": "Any modification to the contract will result in different hash values",
            "metadata_authenticity": "Timestamp, IP, and location data are captured at signing and cannot be altered",
            "contact_support": property_doc.get("email", "support@cecilhomes.com") if property_doc else "support@cecilhomes.com"
        }
    }
    
    return verification_data

@router.get("/contracts/verify/{contract_id}/html")
async def verify_contract_html(request: Request, contract_id: str):
    """
    Public HTML page for contract verification
    User-friendly web page showing verification status
    """
    
    db = request.app.state.adb
    
    # Validate contract ID
    if not ObjectId.is_valid(contract_id):
        return HTMLResponse(content="""
        <html>
            <head><title>Invalid Contract</title></head>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1 style="color: #c62828;">Invalid Contract ID</h1>
                <p>The contract ID format is invalid.</p>
            </body>
        </html>
        """, status_code=400)
    
    contract = await db["property_leases"].find_one({"_id": ObjectId(contract_id)})
    if not contract:
        return HTMLResponse(content="""
        <html>
            <head><title>Contract Not Found</title></head>
            <body style="font-family: Arial; padding: 40px; text-align: center;">
                <h1 style="color: #c62828;">Contract Not Found</h1>
                <p>This contract does not exist in our system.</p>
            </body>
        </html>
        """, status_code=404)
        
    # Fetch related data
    property_doc = await db["properties"].find_one({"_id": ObjectId(contract["property_id"])})
    tenant_details = contract.get("tenant_details", {})
    
    # Get signature status
    tenant_signed = bool(contract.get("tenant_signature"))
    landlord_signed = bool(contract.get("landlord_signature"))
    fully_signed = tenant_signed and landlord_signed
    
    # Get metadata
    tenant_metadata = contract.get("tenant_signature_metadata", {})
    landlord_metadata = contract.get("landlord_signature_metadata", {})
    
    # Build HTML
    status_color = "#28a745" if fully_signed else "#ffc107"
    status_text = "FULLY SIGNED & VALID" if fully_signed else "PARTIALLY SIGNED"
    
    context = {
        "request": request,
        "contract_id": contract_id,
        "status_color": status_color,
        "status_text": status_text,
        
        # Contract information
        "contract": {
            "status": contract.get("status", "pending"),
            "lease_start": contract.get("start_date").strftime("%B %d, %Y") if contract.get("start_date") else "N/A",
            "lease_end": contract.get("end_date").strftime("%B %d, %Y") if contract.get("end_date") else "N/A",
            "created_at": contract.get("created_at").strftime("%B %d, %Y") if contract.get("created_at") else "N/A"
        },
        
        # Property information
        "property": {
            "name": property_doc.get("name", "N/A") if property_doc else "N/A",
            "location": property_doc.get("location", "N/A") if property_doc else "N/A",
            "email": property_doc.get("email", "support@cecilhomes.com") if property_doc else "support@cecilhomes.com"
        },
        
        # Tenant signature
        "tenant_signature": {
            "signed": tenant_signed,
            "signer_name": tenant_details.get("full_name", "N/A"),
            "signed_date": contract.get("tenant_signed_date").strftime("%B %d, %Y at %I:%M %p UTC") if contract.get("tenant_signed_date") else None,
            "metadata": {
                "ip_address": tenant_metadata.get("ip_address", "N/A"),
                "location": tenant_metadata.get("location", "N/A"),
                "platform": tenant_metadata.get("platform", "N/A"),
                "browser": tenant_metadata.get("browser", "N/A"),
                "device_type": tenant_metadata.get("device_type", "N/A"),
                "signature_hash": tenant_metadata.get("signature_hash", "N/A"),
                "user_agent": tenant_metadata.get("user_agent", "N/A")
            } if tenant_signed else {}
        },
        
        # Landlord signature
        "landlord_signature": {
            "signed": landlord_signed,
            "signer_name": property_doc.get("landlord_name", property_doc.get("name", "N/A")) if property_doc else "N/A",
            "signed_date": contract.get("landlord_signed_date").strftime("%B %d, %Y at %I:%M %p UTC") if contract.get("landlord_signed_date") else None,
            "metadata": {
                "ip_address": landlord_metadata.get("ip_address", "N/A"),
                "location": landlord_metadata.get("location", "N/A"),
                "platform": landlord_metadata.get("platform", "N/A"),
                "browser": landlord_metadata.get("browser", "N/A"),
                "device_type": landlord_metadata.get("device_type", "N/A"),
                "signature_hash": landlord_metadata.get("signature_hash", "N/A"),
                "user_agent": landlord_metadata.get("user_agent", "N/A")
            } if landlord_signed else {}
        },
        
        # Verification info
        "verification_timestamp": datetime.utcnow().strftime("%B %d, %Y at %I:%M %p UTC")
    }
    
    return templates.TemplateResponse(
        "verified.html",
        context
    )
    
    
import io, csv
from fastapi.responses import StreamingResponse

@router.get("/reports/export")
async def export_monthly_csv(request: Request, month: str = Query(...)):
    db = request.app.state.adb
    invoices = await db["invoices"].find({"month": month}).to_list(None)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tenant", "Property", "Total", "Paid", "Balance", "Status"])

    for inv in invoices:
        tenant = await db["property_tenants"].find_one({"_id": inv["tenant_id"]})
        prop = await db["properties"].find_one({"_id": inv["property_id"]})
        writer.writerow([
            tenant.get("full_name", "Unknown"),
            prop.get("name", "N/A"),
            inv["total"], inv["paid_amount"], inv["balance"], inv["status"]
        ])
    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={month}_report.csv"})


# ===============================================================
# Vendo
# ===============================================================

# ===============================================================
# INDEX SETUP + INIT
# ===============================================================

async def ensure_indexes(db):
    await db["invoices"].create_index([("tenant_id", 1), ("month", 1)])
    await db["units"].create_index("property_id")
    await db["payments"].create_index("invoice_id")


def init_plugin(app: FastAPI):
    """Initialize plugin, register router, and ensure indexes."""
    global router
    # app.include_router(router)
    # app.add_event_handler("startup", lambda: ensure_indexes(app.state.adb))
    router = add_routes(router)
    return {"router": router}
