# ===============================================================
# HELPERS
# ===============================================================
from plugins.pms.models.models import Utility
from bson import ObjectId
from datetime import datetime
from typing import Any
from decimal import Decimal, ROUND_HALF_UP


async def verify_property_access(db, property_id, user_id):
    if not await db["properties"].find_one({"_id": property_id, "owner_id": user_id}):
        raise HTTPException(403, "Unauthorized")


def money(val): return float(Decimal(val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def serialize_doc(doc: Any) -> Any:
    """
    Recursively convert MongoDB documents (or lists of them)
    into JSON-serializable structures.
    Handles ObjectId, datetime, nested lists, and dicts.
    """
    if doc is None:
        return None

    # If list of documents → recurse
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]

    # If dictionary → walk through fields
    if isinstance(doc, dict):
        serialized = {}
        for k, v in doc.items():
            if isinstance(v, ObjectId):
                serialized[k] = str(v)
            elif isinstance(v, datetime):
                serialized[k] = v.isoformat()
            elif isinstance(v, (list, dict)):
                serialized[k] = serialize_doc(v)
            else:
                serialized[k] = v
        return serialized

    # If scalar → return as-is
    return doc



async def recalc_invoice(inv: dict) -> dict:
    total = sum(i["amount"] for i in inv["items"]) + inv.get("late_fee", 0)
    paid = inv.get("paid_amount", 0)
    balance = total - paid
    status = "paid" if balance <= 0 else "partial" if paid > 0 else "unpaid"
    inv.update({"total": total, "balance": balance, "status": status})
    return inv



def find_utility(unit: dict, name: str) -> Utility | None:
    """Find and return a Utility object from a unit by name (case-insensitive)."""
    for u in unit.get("utilities", []):
        if isinstance(u, dict) and u.get("name", "").strip().lower() == name.lower():
            return Utility(**u)
        elif isinstance(u, Utility) and u.name.strip().lower() == name.lower():
            return u
    return None