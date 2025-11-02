from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from typing import List, Dict
import asyncio


def make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to timezone-aware UTC datetime"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt


def calculate_age_days(date_issued: datetime) -> int:
    """Calculate age in days, handling both aware and naive datetimes"""
    if not date_issued:
        return None
    
    # Make both datetimes timezone-aware
    date_issued_aware = make_aware(date_issued)
    now_aware = datetime.now(timezone.utc)
    
    # Calculate difference
    age = (now_aware - date_issued_aware).days
    return age


async def get_old_invoices(
    mongo_uri: str,
    database_name: str,
    days_old: int = 60
) -> List[Dict]:
    """
    Get all invoices older than specified days with their amount and _id
    
    Args:
        mongo_uri: MongoDB connection string
        database_name: Database name
        days_old: Number of days (default 60)
    
    Returns:
        List of dicts with _id, amount, date_issued, due_date, age_days
    """
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[database_name]
    
    try:
        # Calculate cutoff date (timezone-aware)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        print(f"Finding invoices older than {days_old} days (before {cutoff_date.strftime('%Y-%m-%d')})")
        
        # Query invoices - need to handle both aware and naive dates
        cursor = db.property_invoices.find({})
        
        invoices = []
        
        async for invoice in cursor:
            date_issued = invoice.get("date_issued")
            
            # Skip if no date_issued
            if not date_issued:
                continue
            
            # Make date_issued aware for comparison
            date_issued_aware = make_aware(date_issued)
            
            # Check if older than cutoff
            if date_issued_aware < cutoff_date:
                invoice_data = {
                    "_id": str(invoice["_id"]),
                    "amount": invoice.get("total_amount", 0),
                    "date_issued": date_issued,
                    "due_date": invoice.get("due_date"),
                    "status": invoice.get("status"),
                    "property_id": invoice.get("property_id"),
                    "lease_id": invoice.get("lease_id"),
                    "age_days": calculate_age_days(date_issued)
                }
                
                invoices.append(invoice_data)
        
        return invoices
    
    finally:
        client.close()


async def get_old_invoices_simple(
    mongo_uri: str,
    database_name: str,
    days_old: int = 60
) -> List[Dict]:
    """
    Simpler version - just returns _id and amount
    
    Returns:
        List of dicts with just _id and amount
    """
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[database_name]
    
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        cursor = db.property_invoices.find({})
        
        invoices = []
        
        async for invoice in cursor:
            date_issued = invoice.get("date_issued")
            
            if not date_issued:
                continue
            
            # Make aware for comparison
            date_issued_aware = make_aware(date_issued)
            
            if date_issued_aware < cutoff_date:
                invoices.append({
                    "_id": str(invoice["_id"]),
                    "amount": invoice.get("total_amount", 0)
                })
        
        return invoices
    
    finally:
        client.close()


async def get_old_unpaid_invoices(
    mongo_uri: str,
    database_name: str,
    days_old: int = 60
) -> List[Dict]:
    """
    Get old invoices that are still unpaid or partially paid
    
    Returns:
        List of old unpaid invoices
    """
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[database_name]
    
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        cursor = db.property_invoices.find({
            "status": {"$in": ["unpaid", "partially_paid", "overdue"]}
        })
        
        invoices = []
        
        async for invoice in cursor:
            date_issued = invoice.get("date_issued")
            
            if not date_issued:
                continue
            
            # Make aware for comparison
            date_issued_aware = make_aware(date_issued)
            
            if date_issued_aware < cutoff_date:
                total = invoice.get("total_amount", 0)
                paid = invoice.get("amount_paid", 0)
                balance = total - paid
                
                invoice_data = {
                    "_id": str(invoice["_id"]),
                    "total_amount": total,
                    "amount_paid": paid,
                    "balance": balance,
                    "date_issued": date_issued,
                    "due_date": invoice.get("due_date"),
                    "status": invoice.get("status"),
                    "age_days": calculate_age_days(date_issued)
                }
                
                invoices.append(invoice_data)
        
        return invoices
    
    finally:
        client.close()


async def print_old_invoices(days_old: int = 60):
    """Print old invoices with details"""
    
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    invoices = await get_old_invoices(mongo_uri, database_name, days_old)
    
    print("\n" + "=" * 80)
    print(f" INVOICES OLDER THAN {days_old} DAYS")
    print("=" * 80)
    
    if not invoices:
        print("\nNo invoices found.")
        return
    
    print(f"\nFound {len(invoices)} invoices")
    
    # Calculate totals
    total_amount = sum(inv["amount"] for inv in invoices)
    
    print(f"Total Amount: KES {total_amount:,.2f}\n")
    
    # Print details
    print(f"{'Invoice ID':<25} {'Amount':>12} {'Age':>8} {'Status':<12} {'Issued':<12}")
    print("-" * 80)
    
    for inv in sorted(invoices, key=lambda x: x.get("age_days", 0) or 0, reverse=True):
        invoice_id = inv["_id"][:20] + "..."
        amount = f"KES {inv['amount']:,.2f}"
        age = f"{inv['age_days']} days" if inv['age_days'] else "N/A"
        status = inv.get("status", "N/A")
        
        # Handle both aware and naive datetimes for display
        if inv["date_issued"]:
            issued = inv["date_issued"].strftime("%Y-%m-%d")
        else:
            issued = "N/A"
        
        print(f"{invoice_id:<25} {amount:>12} {age:>8} {status:<12} {issued:<12}")
    
    print("-" * 80)
    print(f"{'TOTAL':<25} {f'KES {total_amount:,.2f}':>12}\n")


async def get_old_invoices_by_property(
    mongo_uri: str,
    database_name: str,
    property_id: str,
    days_old: int = 60
) -> List[Dict]:
    """
    Get old invoices for a specific property
    """
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[database_name]
    
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        cursor = db.property_invoices.find({
            "property_id": property_id
        })
        
        invoices = []
        
        async for invoice in cursor:
            date_issued = invoice.get("date_issued")
            
            if not date_issued:
                continue
            
            # Make aware for comparison
            date_issued_aware = make_aware(date_issued)
            
            if date_issued_aware < cutoff_date:
                invoices.append({
                    "_id": str(invoice["_id"]),
                    "amount": invoice.get("total_amount", 0),
                    "date_issued": date_issued,
                    "status": invoice.get("status"),
                    "age_days": calculate_age_days(date_issued)
                })
        
        return invoices
    
    finally:
        client.close()


# Quick usage examples

async def main():
    """Main function with examples"""
    
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    print("\n1. Getting simple list (_id and amount only)...")
    simple = await get_old_invoices_simple(mongo_uri, database_name, days_old=1)
    print(f"Found {len(simple)} old invoices")
    for inv in simple[:5]:
        print(f"  - {inv['_id']}: KES {inv['amount']:,.2f}")
    
    print("\n2. Getting detailed list...")
    await print_old_invoices(days_old=1)
    
    print("\n3. Getting old UNPAID invoices only...")
    unpaid = await get_old_unpaid_invoices(mongo_uri, database_name, days_old=1)
    print(f"Found {len(unpaid)} old unpaid invoices")
    if unpaid:
        total_outstanding = sum(inv['balance'] for inv in unpaid)
        print(f"Total Outstanding: KES {total_outstanding:,.2f}")
    
    # print("\n4. Getting by specific property...")
    # property_id = "68f44ea8c5181f3902abe14d"  # Example
    # by_property = await get_old_invoices_by_property(
    #     mongo_uri, 
    #     database_name, 
    #     property_id, 
    #     days_old=60
    # )
    # print(f"Found {len(by_property)} old invoices for property {property_id}")


if __name__ == "__main__":
    asyncio.run(main())