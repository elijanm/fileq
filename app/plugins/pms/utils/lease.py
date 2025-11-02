from fastapi import Request
from bson import ObjectId
from datetime import datetime
import os
from typing import Optional, Dict, Any
import hashlib


async def get_signature_metadata(request: Request, session_id: str = None) -> Dict[str, Any]:
    """Capture signature metadata for e-signature verification"""
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "Unknown")
    
    # You can enhance this with actual geolocation service
    # For now, using a placeholder
    location = "Nairobi, Kenya"  # Replace with actual geolocation lookup
    
    # Generate cryptographic hashes (implement actual hashing in production)
    import hashlib
    timestamp = datetime.utcnow().isoformat()
    
    return {
        "timestamp": timestamp,
        "ip_address": client_ip,
        "location": location,
        "user_agent": user_agent,
        "session_id": session_id or f"sess_{ObjectId()}",
        "document_hash": hashlib.sha256(f"{timestamp}{client_ip}".encode()).hexdigest(),
        "signature_hash": hashlib.sha256(f"{timestamp}{user_agent}".encode()).hexdigest()
    }


async def prepare_contract_data(db, contract: dict, request: Request) -> dict:
    """Prepare complete contract data for PDF generation"""
    
    # Fetch related documents
    tenant = await db["property_tenants"].find_one({"_id": ObjectId(contract["tenant_id"])})
    property_doc = await db["properties"].find_one({"_id": (contract["property_id"])})
    
    # Fetch unit details
    units = []
    if "units_id" in contract and contract["units_id"]:
        for unit_id in contract["units_id"]:
            unit = await db["units"].find_one({"_id": ObjectId(unit_id)})
            if unit:
                units.append(unit)
    
    # Get first unit for primary details (or aggregate if multiple)
    primary_unit = units[0] if units else {}
    primary_unit["_id"]=str(primary_unit["_id"])

    # Extract lease terms
    lease_terms = contract.get("lease_terms", {})
    financial = contract.get("financial_details", {})
    tenant_details = contract.get("tenant_details", {})
    
    # Calculate lease duration in months
    start_date = lease_terms.get("start_date") or contract.get("start_date")
    end_date = lease_terms.get("end_date") or contract.get("end_date")
    
    if isinstance(start_date, str):
        start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    if isinstance(end_date, str):
        end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    
    lease_duration_months = ((end_date.year - start_date.year) * 12 + 
                            end_date.month - start_date.month)
    
    # Prepare brand information
    brand = {
        "company": "Cecil Homes Property Management",  # Customize based on your system
        "logo": property_doc.get("logo", ""),
        "tagline": "Your Lifestyle & Beyond",
        "watermark": property_doc.get("custom_image", ""),
        "watermark_url": property_doc.get("custom_image", ""),
        "color": "#2e7d32",
        "postal_address": "103793-00101",  # Add to property model
        "city": "Nairobi",
        "phone": property_doc.get("phone", ""),
        "email": property_doc.get("email", ""),
        "website": "www.cecilhomes.com",  # Add to property model
        "verification_url": f"{request.base_url}api/contracts"
    }
    
    # Prepare tenant information
    tenant_info = {
        "full_name": tenant_details.get("full_name") or tenant.get("full_name", ""),
        "email": tenant_details.get("email") or tenant.get("email", ""),
        "phone": tenant_details.get("phone") or tenant.get("phone", ""),
        "id_number": tenant_details.get("id_number", ""),
        "id_type": "National ID",  # Add to tenant model
        "postal_address": tenant_details.get("postal_address", ""),
        "city":tenant_details.get("postal_address", ""),
    }
    
    # Prepare property information
    property_info = {
        "name": property_doc.get("name", ""),
        "location": property_doc.get("location", ""),
        "landlord_name": property_doc.get("owner_name", property_doc.get("name", "")),
        "landlord_postal_address": property_doc.get("postal_address", ""),
        "owner_id_type": "National ID",
        "unitsTotal": property_doc.get("unitsTotal", ""),
        "owner_id_number": property_doc.get("owner_id_number", ""),
        "estate_name": property_doc.get("location", "").split(",")[-1].strip() if "," in property_doc.get("location", "") else ""
    }
    
    # Prepare unit information
    unit_info = {
        "unit_number": primary_unit.get("unitNumber", ""),
        "unit_name": primary_unit.get("unitName", ""),
        "furnishing_status": primary_unit.get("furnishing_status", "Unfurnished"),
        "unit_type": primary_unit.get("unitType", ""),
        "floor": primary_unit.get("floor", 0),
        "bedrooms": primary_unit.get("bedrooms", 0),
        "bathrooms": primary_unit.get("bathrooms", 0),
        "size_sqft": primary_unit.get("size_sqft", 0)
    }
    
    # Prepare financial details
    rent_amount = financial.get("rent_amount") or lease_terms.get("rent_amount") or contract.get("rent_amount", 0)
    deposit_amount = financial.get("deposit_amount") or contract.get("deposit_amount", 0)
    
    financial_info = {
        "rent_amount": float(rent_amount),
        "deposit_amount": float(deposit_amount),
        "service_charge": primary_unit.get("service_charge", 0),
        "agreement_fee": 0.00,  # Add to contract model
        "currency": property_doc.get("currency", "KES")
    }
    
    # Prepare utilities with proper formatting
    utilities = []
    property_utilities = property_doc.get("utilities", [])
    unit_utilities = primary_unit.get("utilities", [])
    cu =  contract.get("utilities", {})
    total_utility_deposits=0.0
    # Merge property and unit level utilities
    # for utility in  cu:
    #     if utility.get("isActive"):
    #         deposit_amount = float(utility.get("deposit_amount", 0.0))
    #         if(deposit_amount>0):
    #             total_utility_deposits += deposit_amount
                
    #         utilities.append({
    #             "name": utility.get("name", ""),
    #             "description": utility.get("description", ""),
    #             "type": utility.get("type", "mandatory"),
    #             "isActive": utility.get("isActive", True),
    #             "paymentType": utility.get("paymentType", "billable"),
    #             "billingFrequency": utility.get("billingFrequency", "monthly"),
    #             "billingBasis": utility.get("billingBasis", "fixed"),
    #             "billingLevel": utility.get("billingLevel", "unit"),
    #             "rate": utility.get("rate", 0),
    #             "unitOfMeasure": utility.get("unitOfMeasure", ""),
    #             "billTo": utility.get("billTo", "tenant"),
    #             "hasMeter": utility.get("hasMeter", False),
    #             "deposit_amount": deposit_amount
    #         })
    for utility in  cu:
      if utility.get("isDepositRequired"):
        deposit_amount = float(utility.get("depositAmount", 0.0))
        if(deposit_amount>0):
            total_utility_deposits += deposit_amount
            
        utilities.append({
            "name": utility.get("name", ""),
            "description": utility.get("description", ""),
            "type": utility.get("type", "mandatory"),
            "isActive": utility.get("isActive", True),
            "paymentType": utility.get("paymentType", "billable"),
            "billingFrequency": utility.get("billingFrequency", "monthly"),
            "billingBasis": utility.get("billingBasis", "fixed"),
            "billingLevel": utility.get("billingLevel", "unit"),
            "rate": utility.get("rate", 0),
            "unitOfMeasure": utility.get("unitOfMeasure", ""),
            "billTo": utility.get("billTo", "tenant"),
            "hasMeter": utility.get("hasMeter", False),
            "deposit_amount": deposit_amount,
            "depositAmount":deposit_amount,
            "isDepositRequired":utility.get("isDepositRequired"),
            "isRefundable":utility.get("isRefundable"),
            "units":utility.get("units"),
        })
    
    # Prepare payment details
    integrations = property_doc.get("integrations", {})
    payment_config = integrations.get("payments", {}) if integrations else {}
    paybill_config = payment_config.get("paybill_no", {}) if payment_config else {}
    till_config = payment_config.get("tillNo", {}) if payment_config else {}
    payment_info = {
        "bank_name": "EQUITY BANK",  # Add to property integrations
        "branch": "KILIMANI",  # Add to property integrations
        "account_number": "123456789",  # Add to property integrations
        "till_no": till_config.get("till_no", ""),
        "paybill_no": paybill_config.get("paybill_no", "234432") if isinstance(paybill_config, dict) else "",
        "account": paybill_config.get("account", "{unit#}") if isinstance(paybill_config, dict) else "{unit#}"
    }
    
    # Prepare contract terms
    contract_terms = {
        "start_date": start_date,
        "end_date": end_date,
        "lease_duration_months": lease_duration_months or 11,
        "notice_period_days": contract.get("notice_period_days", 30),
        "renewal_notice_months": 3,  # Add to contract model
        "late_penalty_rate": 10,  # Add to property model
        "bounced_cheque_fee": 3500.00,  # Add to property model
        "rent_cycle": lease_terms.get("rent_cycle", "monthly"),
        "payment_due_day": lease_terms.get("payment_due_day", 5)
    }
    
    # Prepare clauses
    clauses = contract.get("clauses", [])
    formatted_clauses = []
    for clause in clauses:
        formatted_clauses.append({
            "title": clause.get("title", ""),
            "description": clause.get("description", ""),
            "mandatory": clause.get("mandatory", True)
        })
    
    # Prepare signature metadata
    tenant_signature = contract.get("tenant_signature")
    landlord_signature = contract.get("landlord_signature")
    
    tenant_signature_metadata = None
    landlord_signature_metadata = None
    
    if tenant_signature:
        # If metadata already exists, use it; otherwise create placeholder
        tenant_signature_metadata = contract.get("tenant_signature_metadata")
        if not tenant_signature_metadata:
            tenant_signature_metadata = await get_signature_metadata(request)
    
    if landlord_signature:
        landlord_signature_metadata = contract.get("landlord_signature_metadata")
        if not landlord_signature_metadata:
            landlord_signature_metadata = await get_signature_metadata(request)
    
    # Compile complete contract data
    contract_data = {
        "brand": brand,
        "property": property_info,
        "tenant": tenant_info,
        "unit": unit_info,
        "contract": {
            "id": str(contract["_id"]),
            "property_id": str(contract["property_id"]),
            "start_date": start_date,
            "end_date": end_date,
            "rent_amount": financial_info["rent_amount"],
            "deposit_amount": financial_info["deposit_amount"],
            "service_charge": financial_info["service_charge"],
            "agreement_fee": financial_info["agreement_fee"],
            "lease_duration_months": contract_terms["lease_duration_months"],
            "notice_period_days": contract_terms["notice_period_days"],
            "renewal_notice_months": contract_terms["renewal_notice_months"],
            "late_penalty_rate": contract_terms["late_penalty_rate"],
            "bounced_cheque_fee": contract_terms["bounced_cheque_fee"],
            "clauses": formatted_clauses,
            "total_utility_deposits": total_utility_deposits,
            "tenant_signature": tenant_signature,
            "landlord_signature": landlord_signature,
            "tenant_signature_metadata": tenant_signature_metadata,
            "landlord_signature_metadata": landlord_signature_metadata,
            "tenant_signed_date": contract.get("tenant_signed_date", ""),
            "landlord_signed_date": contract.get("landlord_signed_date", ""),
            "status": contract.get("status", "pending"),
            "generated_at": datetime.utcnow().isoformat(),
            "created_at": contract.get("created_at", datetime.utcnow()).isoformat()
        },
        "payment": payment_info,
        "utilities": utilities,
        "today": datetime.utcnow().strftime("%B %d, %Y")
    }
    
    return contract_data

async def capture_signature_metadata(
    request: Request, 
    signer_name: str,
    signer_email: str,
    document_id: str,
    signature_data: str
) -> Dict[str, Any]:
    """
    Capture comprehensive signature metadata for e-signature verification
    
    Args:
        request: FastAPI Request object
        signer_name: Name of the person signing
        signer_email: Email of the signer
        document_id: Unique document/contract ID
        signature_data: Base64 signature image data
    
    Returns:
        Dictionary containing all signature metadata
    """
    # Extract request information
    client_ip = request.client.host
    user_agent = request.headers.get("user-agent", "Unknown")
    timestamp = datetime.utcnow()
    timestamp_iso = timestamp.isoformat() + "Z"
    
    # Get additional headers for forensics
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # Get real IP if behind proxy
        client_ip = x_forwarded_for.split(",")[0].strip()
    
    # Generate session ID (you can replace with actual session ID from your auth system)
    session_id = f"sess_{ObjectId()}"
    
    # Geolocation (placeholder - integrate with IP geolocation service in production)
    # You can use services like: ipapi.co, ip-api.com, or MaxMind GeoIP2
    location = await get_location_from_ip(client_ip) if client_ip != "127.0.0.1" else "Nairobi, Kenya"
    
    # Generate cryptographic hashes for verification
    document_hash = hashlib.sha256(
        f"{document_id}{timestamp_iso}{signer_email}".encode()
    ).hexdigest()
    
    signature_hash = hashlib.sha256(
        f"{signature_data}{timestamp_iso}{client_ip}{user_agent}".encode()
    ).hexdigest()
    
    # Compile metadata
    metadata = {
        "timestamp": timestamp_iso,
        "ip_address": client_ip,
        "location": location,
        "user_agent": user_agent,
        "session_id": session_id,
        "document_hash": document_hash,
        "signature_hash": signature_hash,
        "signer_name": signer_name,
        "signer_email": signer_email,
        "platform": get_platform_from_user_agent(user_agent),
        "browser": get_browser_from_user_agent(user_agent),
        "device_type": get_device_type_from_user_agent(user_agent)
    }
    
    return metadata


async def get_location_from_ip(ip: str) -> str:
    """
    Get location from IP address using geolocation service
    In production, integrate with actual geolocation API
    """
    # Placeholder implementation
    # TODO: Integrate with ipapi.co, ip-api.com, or MaxMind
    try:
        # Example with ipapi.co (free tier):
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(f"https://ipapi.co/{ip}/json/")
        #     if response.status_code == 200:
        #         data = response.json()
        #         return f"{data.get('city', 'Unknown')}, {data.get('country_name', 'Unknown')}"
        return "Nairobi, Kenya"  # Default fallback
    except Exception:
        return "Unknown Location"


def get_platform_from_user_agent(user_agent: str) -> str:
    """Extract platform/OS from user agent string"""
    ua_lower = user_agent.lower()
    if "windows" in ua_lower:
        return "Windows"
    elif "mac" in ua_lower:
        return "macOS"
    elif "linux" in ua_lower:
        return "Linux"
    elif "android" in ua_lower:
        return "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        return "iOS"
    return "Unknown"


def get_browser_from_user_agent(user_agent: str) -> str:
    """Extract browser from user agent string"""
    ua_lower = user_agent.lower()
    if "edg" in ua_lower:
        return "Microsoft Edge"
    elif "chrome" in ua_lower:
        return "Google Chrome"
    elif "firefox" in ua_lower:
        return "Mozilla Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        return "Safari"
    elif "opera" in ua_lower or "opr" in ua_lower:
        return "Opera"
    return "Unknown Browser"


def get_device_type_from_user_agent(user_agent: str) -> str:
    """Determine device type from user agent"""
    ua_lower = user_agent.lower()
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        return "Mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        return "Tablet"
    return "Desktop"