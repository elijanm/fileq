import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Literal
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import random,json
import requests
import random
import string
import concurrent.futures
from datetime import datetime, timedelta

async def get_invoices_by_due_date_with_payment_dates(
    mongo_uri: str,
    database_name: str,
    start_due_date: Optional[datetime] = None,
    end_due_date: Optional[datetime] = None,
    property_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    status: Optional[str] = None,
    payment_scenario: Literal["before", "on", "after", "mixed", "random"] = "random",
    days_range: tuple = (-7, 14)  # Range for random dates (7 days before to 14 days after)
) -> List[Dict]:
    """
    Get all invoices by due date with random payment dates
    
    Args:
        mongo_uri: MongoDB connection string
        database_name: Database name
        start_due_date: Filter invoices from this due date (optional)
        end_due_date: Filter invoices until this due date (optional)
        property_id: Filter by property (optional)
        tenant_id: Filter by tenant (optional)
        status: Filter by status (optional)
        payment_scenario: Payment date scenario:
            - "before": Payment date before due date (early payment)
            - "on": Payment date on due date (on-time payment)
            - "after": Payment date after due date (late payment)
            - "mixed": Mix of before, on, and after
            - "random": Completely random within days_range
        days_range: Tuple of (min_days, max_days) from due date for random dates
    
    Returns:
        List of dicts with:
            - _id: Invoice ID
            - invoice_number: Invoice number
            - tenant_name: Tenant name
            - due_date: Due date
            - total_amount: Total invoice amount
            - total_paid: Amount already paid
            - balance_amount: Outstanding balance
            - status: Invoice status
            - random_payment_date: Generated random payment date
            - payment_timing: "before", "on", or "after" due date
            - days_difference: Days between payment date and due date
    """
    
    client = AsyncIOMotorClient(mongo_uri)
    db = client[database_name]
    
    try:
        # Build query
        query = {}
        
        # Due date filters
        if start_due_date or end_due_date:
            query["due_date"] = {}
            if start_due_date:
                query["due_date"]["$gte"] = start_due_date
            if end_due_date:
                query["due_date"]["$lte"] = end_due_date
        
        # Other filters
        if property_id:
            query["property_id"] = property_id
        
        if tenant_id:
            if isinstance(tenant_id, str):
                tenant_id = ObjectId(tenant_id)
            query["tenant_id"] = tenant_id
        
        if status:
            query["status"] = status
        
        # Get invoices sorted by due date
        cursor = db.property_invoices.find(query).sort("due_date", 1)
        invoices = await cursor.to_list(length=None)
        
        print(f"\n{'='*80}")
        print(f" INVOICES BY DUE DATE WITH RANDOM PAYMENT DATES")
        print(f" Payment Scenario: {payment_scenario.upper()}")
        print(f"{'='*80}")
        print(f"\nFound {len(invoices)} invoices")
        
        result = []
        
        for inv in invoices:
            invoice_id = str(inv["_id"])
            due_date = inv.get("due_date")
            
            if not due_date:
                continue
            
            # Get tenant name
            tenant_id_obj = inv.get("tenant_id")
            tenant = await db.property_tenants.find_one({"_id": tenant_id_obj})
            tenant_name = tenant.get("full_name") if tenant else "Unknown"
            
            # Generate random payment date based on scenario
            random_payment_date = _generate_payment_date(
                due_date, 
                payment_scenario, 
                days_range
            )
            
            # Calculate timing
            days_diff = (random_payment_date - due_date).days
            
            if days_diff < 0:
                payment_timing = "before"
            elif days_diff == 0:
                payment_timing = "on"
            else:
                payment_timing = "after"
            
            invoice_data = {
                "_id": invoice_id,
                "invoice_number": inv.get("invoice_number"),
                "tenant_id": str(tenant_id_obj),
                "tenant_name": tenant_name,
                "property_id": inv.get("property_id"),
                "due_date": due_date,
                "date_issued": inv.get("date_issued"),
                "total_amount": inv.get("total_amount", 0),
                "total_paid": inv.get("total_paid", 0),
                "balance_amount": inv.get("balance_amount", 0),
                "status": inv.get("status"),
                "random_payment_date": random_payment_date,
                "payment_timing": payment_timing,
                "days_difference": days_diff
            }
            
            result.append(invoice_data)
        
        # Print summary
        _print_summary(result, payment_scenario)
        
        return result
        
    finally:
        client.close()


def _generate_payment_date(
    due_date: datetime,
    scenario: str,
    days_range: tuple
) -> datetime:
    """
    Generate a random payment date based on scenario
    
    Args:
        due_date: Invoice due date
        scenario: Payment scenario
        days_range: Range for random dates
    
    Returns:
        Random payment date
    """
    
    if scenario == "before":
        # Payment 1-7 days before due date
        days_before = random.randint(1, 7)
        return due_date - timedelta(days=days_before)
    
    elif scenario == "on":
        # Payment on due date
        return due_date
    
    elif scenario == "after":
        # Payment 1-14 days after due date
        days_after = random.randint(1, 14)
        return due_date + timedelta(days=days_after)
    
    elif scenario == "mixed":
        # Mix of before (40%), on (20%), after (40%)
        rand = random.random()
        
        if rand < 0.4:  # 40% before
            days_before = random.randint(1, 7)
            return due_date - timedelta(days=days_before)
        elif rand < 0.6:  # 20% on time
            return due_date
        else:  # 40% after
            days_after = random.randint(1, 14)
            return due_date + timedelta(days=days_after)
    
    else:  # "random"
        # Completely random within days_range
        min_days, max_days = days_range
        random_days = random.randint(min_days, max_days)
        return due_date + timedelta(days=random_days)


def _print_summary(invoices: List[Dict], scenario: str):
    """Print summary of invoices with payment dates"""
    
    if not invoices:
        print("\nNo invoices found.")
        return
    
    # Calculate statistics
    total_amount = sum(inv["total_amount"] for inv in invoices)
    total_balance = sum(inv["balance_amount"] for inv in invoices)
    
    before_count = sum(1 for inv in invoices if inv["payment_timing"] == "before")
    on_count = sum(1 for inv in invoices if inv["payment_timing"] == "on")
    after_count = sum(1 for inv in invoices if inv["payment_timing"] == "after")
    
    print(f"\n{'='*80}")
    print(f" SUMMARY")
    print(f"{'='*80}")
    
    print(f"\n💰 Financial Summary:")
    print(f"   Total Amount: KES {total_amount:,.2f}")
    print(f"   Total Balance: KES {total_balance:,.2f}")
    
    print(f"\n📊 Payment Timing Distribution:")
    print(f"   Before Due Date: {before_count} ({before_count/len(invoices)*100:.1f}%)")
    print(f"   On Due Date: {on_count} ({on_count/len(invoices)*100:.1f}%)")
    print(f"   After Due Date: {after_count} ({after_count/len(invoices)*100:.1f}%)")
    
    # Show sample invoices
    print(f"\n📋 Sample Invoices (First 10):")
    print(f"   {'Invoice #':<15} {'Tenant':<25} {'Due Date':<12} {'Payment Date':<12} {'Timing':<8} {'Days':>5} {'Balance':>12}")
    print(f"   {'-'*110}")
    
    for inv in invoices[:10]:
        timing_emoji = {
            "before": "🟢",
            "on": "🟡",
            "after": "🔴"
        }.get(inv["payment_timing"], "⚪")
        
        print(f"   {inv['invoice_number']:<15} "
              f"{inv['tenant_name'][:24]:<25} "
              f"{inv['due_date'].strftime('%Y-%m-%d'):<12} "
              f"{inv['random_payment_date'].strftime('%Y-%m-%d'):<12} "
              f"{timing_emoji} {inv['payment_timing']:<6} "
              f"{inv['days_difference']:>5} "
              f"KES {inv['balance_amount']:>8,.2f}")


async def get_invoices_grouped_by_timing(
    mongo_uri: str,
    database_name: str,
    payment_scenario: str = "mixed"
) -> Dict[str, List[Dict]]:
    """
    Get invoices grouped by payment timing (before/on/after)
    
    Returns:
        Dict with keys "before", "on", "after" containing invoice lists
    """
    
    invoices = await get_invoices_by_due_date_with_payment_dates(
        mongo_uri,
        database_name,
        payment_scenario=payment_scenario
    )
    
    grouped = {
        "before": [],
        "on": [],
        "after": []
    }
    
    for inv in invoices:
        timing = inv["payment_timing"]
        grouped[timing].append(inv)
    
    print(f"\n{'='*80}")
    print(f" GROUPED BY PAYMENT TIMING")
    print(f"{'='*80}")
    
    for timing, invoice_list in grouped.items():
        total_balance = sum(inv["balance_amount"] for inv in invoice_list)
        print(f"\n{timing.upper()}: {len(invoice_list)} invoices, KES {total_balance:,.2f}")
    
    return grouped


async def get_overdue_invoices_with_projected_payment(
    mongo_uri: str,
    database_name: str,
    property_id: Optional[str] = None
) -> List[Dict]:
    """
    Get all overdue invoices with projected payment dates
    
    Returns:
        List of overdue invoices with projected payment dates
    """
    
    current_date = datetime.now(timezone.utc)
    
    return await get_invoices_by_due_date_with_payment_dates(
        mongo_uri=mongo_uri,
        database_name=database_name,
        end_due_date=current_date,
        property_id=property_id,
        status="unpaid",
        payment_scenario="after",
        days_range=(1, 30)  # Project payment 1-30 days after due date
    )


async def simulate_payment_collections(
    mongo_uri: str,
    database_name: str,
    property_id: str,
    period: str,
    payment_behavior: Literal["excellent", "good", "poor", "mixed"] = "mixed"
) -> Dict:
    """
    Simulate payment collection for a specific period with different behaviors
    
    Args:
        mongo_uri: MongoDB connection string
        database_name: Database name
        property_id: Property ID
        period: Period (YYYY-MM)
        payment_behavior: Tenant payment behavior
    
    Returns:
        Simulation results
    """
    
    # Map behavior to scenarios
    behavior_map = {
        "excellent": {"scenario": "before", "days_range": (-5, -1)},
        "good": {"scenario": "mixed", "days_range": (-3, 3)},
        "poor": {"scenario": "after", "days_range": (5, 30)},
        "mixed": {"scenario": "mixed", "days_range": (-7, 14)}
    }
    
    config = behavior_map[payment_behavior]
    
    # Parse period
    year, month = map(int, period.split("-"))
    start_date = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    
    invoices = await get_invoices_by_due_date_with_payment_dates(
        mongo_uri=mongo_uri,
        database_name=database_name,
        start_due_date=start_date,
        end_due_date=end_date,
        property_id=property_id,
        payment_scenario=config["scenario"],
        days_range=config["days_range"]
    )
    
    # Analyze simulation
    total_amount = sum(inv["total_amount"] for inv in invoices)
    on_time_count = sum(1 for inv in invoices if inv["payment_timing"] in ["before", "on"])
    late_count = sum(1 for inv in invoices if inv["payment_timing"] == "after")
    
    avg_days_late = sum(
        inv["days_difference"] for inv in invoices if inv["payment_timing"] == "after"
    ) / late_count if late_count > 0 else 0
    
    result = {
        "property_id": property_id,
        "period": period,
        "behavior": payment_behavior,
        "total_invoices": len(invoices),
        "total_amount": round(total_amount, 2),
        "on_time_payments": on_time_count,
        "late_payments": late_count,
        "on_time_rate": round((on_time_count / len(invoices) * 100) if invoices else 0, 2),
        "avg_days_late": round(avg_days_late, 2),
        "invoices": invoices
    }
    
    print(f"\n{'='*80}")
    print(f" PAYMENT COLLECTION SIMULATION")
    print(f" Behavior: {payment_behavior.upper()}")
    print(f"{'='*80}")
    
    print(f"\n📊 Simulation Results:")
    print(f"   Total Invoices: {result['total_invoices']}")
    print(f"   Total Amount: KES {result['total_amount']:,.2f}")
    print(f"   On-Time Payments: {result['on_time_payments']} ({result['on_time_rate']:.1f}%)")
    print(f"   Late Payments: {result['late_payments']}")
    print(f"   Avg Days Late: {result['avg_days_late']:.1f} days")
    
    return result


async def export_invoices_for_payment_processing(
    mongo_uri: str,
    database_name: str,
    output_format: Literal["csv", "json"] = "json"
) -> str:
    """
    Export invoices with random payment dates for payment processing
    
    Returns:
        File path or JSON string
    """
    
    invoices = await get_invoices_by_due_date_with_payment_dates(
        mongo_uri=mongo_uri,
        database_name=database_name,
        payment_scenario="mixed"
    )
    
    if output_format == "json":
        import json
        
        # Convert datetime to string for JSON serialization
        export_data = []
        for inv in invoices:
            inv_copy = inv.copy()
            inv_copy["due_date"] = inv_copy["due_date"].isoformat()
            inv_copy["date_issued"] = inv_copy["date_issued"].isoformat() if inv_copy.get("date_issued") else None
            inv_copy["random_payment_date"] = inv_copy["random_payment_date"].isoformat()
            export_data.append(inv_copy)
        
        json_str = json.dumps(export_data, indent=2)
        
        # Save to file
        filename = f"invoices_payment_dates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            f.write(json_str)
        
        print(f"\n✅ Exported {len(invoices)} invoices to {filename}")
        return filename
    
    else:  # CSV
        import csv
        
        filename = f"invoices_payment_dates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filename, 'w', newline='') as f:
            if invoices:
                fieldnames = [
                    "_id", "invoice_number", "tenant_name", "due_date",
                    "total_amount", "balance_amount", "random_payment_date",
                    "payment_timing", "days_difference"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for inv in invoices:
                    row = {
                        "_id": inv["_id"],
                        "invoice_number": inv["invoice_number"],
                        "tenant_name": inv["tenant_name"],
                        "due_date": inv["due_date"].strftime('%Y-%m-%d'),
                        "total_amount": inv["total_amount"],
                        "balance_amount": inv["balance_amount"],
                        "random_payment_date": inv["random_payment_date"].strftime('%Y-%m-%d'),
                        "payment_timing": inv["payment_timing"],
                        "days_difference": inv["days_difference"]
                    }
                    writer.writerow(row)
        
        print(f"\n✅ Exported {len(invoices)} invoices to {filename}")
        return filename


# Main execution examples

async def example_basic_usage():
    """Basic usage example"""
    
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    # Get all invoices with random payment dates
    invoices = await get_invoices_by_due_date_with_payment_dates(
        mongo_uri=mongo_uri,
        database_name=database_name,
        payment_scenario="mixed"
    )
    
    print(f"\n✅ Retrieved {len(invoices)} invoices with random payment dates")
    
    # Access individual invoice data
    if invoices:
        sample = invoices[0]
        print(f"\nSample Invoice:")
        print(f"  ID: {sample['_id']}")
        print(f"  Tenant: {sample['tenant_name']}")
        print(f"  Balance: KES {sample['balance_amount']:,.2f}")
        print(f"  Due Date: {sample['due_date'].strftime('%Y-%m-%d')}")
        print(f"  Payment Date: {sample['random_payment_date'].strftime('%Y-%m-%d')}")
        print(f"  Timing: {sample['payment_timing']} ({sample['days_difference']} days)")



def add_random_time(date_str: str) -> str:
    """
    Takes a date string like '2025-07-30 00:00:00' and adds random hour/min/sec.
    Returns formatted 'YYYY-MM-DD HH:MM:SS'
    """
    try:
        base_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # fallback for ISO format
        base_date = datetime.fromisoformat(date_str)

    random_time = timedelta(
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )
    new_date = base_date + random_time
    return new_date.strftime("%Y-%m-%d %H:%M:%S")

class PaymentPoster:
    def __init__(self, url: str, invoices:list, max_workers: int = 20,simulate=True):
        self.url = url
        self.invoices = invoices
        self.total_records = len(invoices)
        self.max_workers = max_workers
        self.simulate=simulate

    # 🔹 Generate random alphanumeric reference
    def _random_reference(self, length: int = 10) -> str:
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

    # 🔹 Build fake payload
    def _make_payload(self, invoice: dict) -> dict:
       

        # total_amount
        # balance_amount
        return {
            "invoice_id": invoice['_id'],
            "amount": invoice['total_amount'],
            "method": "mpesa",
            "pay_date": add_random_time(str(invoice['random_payment_date'])),
            "reference": self._random_reference(),
        }

    # 🔹 POST to server
    def _send_payment(self, invoice:dict):
        payload = self._make_payload(invoice)
        try:
            if self.simulate:
                print(json.dumps(payload,indent=4,default=str))
                return
            response = requests.post(self.url, json=payload, timeout=100)
            response.raise_for_status()
            res=response.json()
            res=res if res else {}
            
            print(f"✅ {invoice['_id']}: {response.status_code} -> {res.get('receipt_no')}")
        except Exception as e:
            print(f"❌ {invoice['_id']}: {e}")

    # 🔹 Run all requests in threads
    def run(self):
        
        print(f"🚀 Sending {self.total_records} simulated payments to {self.url} using {self.max_workers} threads...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            executor.map(self._send_payment, self.invoices)

        print("✅ Finished all requests.")
         
async def example_filtered_usage():
    """Filtered usage example"""
    
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    # Get invoices for specific period
    start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2025, 9, 30, tzinfo=timezone.utc)
    
    invoices = await get_invoices_by_due_date_with_payment_dates(
        mongo_uri=mongo_uri,
        database_name=database_name,
        start_due_date=start_date,
        end_due_date=end_date,
        payment_scenario="mixed",  # All late payments
        days_range=(1, 10)  # 1-10 days late
        status="ready"
    )
    
    poster = PaymentPoster(
        url="http://localhost:8000/pms/property/invoice/payment",
        invoices=invoices,
        max_workers=5,
        simulate=False
    )
    poster.run()
    print(f"\n✅ Retrieved {len(invoices)} invoices due between {start_date}-{end_date} 2025")


async def example_grouped_usage():
    """Grouped by timing example"""
    
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    grouped = await get_invoices_grouped_by_timing(
        mongo_uri=mongo_uri,
        database_name=database_name,
        payment_scenario="mixed"
    )
    
    print(f"\n✅ Grouped invoices:")
    print(f"   Before: {len(grouped['before'])} invoices")
    print(f"   On Time: {len(grouped['on'])} invoices")
    print(f"   After: {len(grouped['after'])} invoices")


async def example_simulation():
    """Simulation example"""
    
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    # Get first property
    client = AsyncIOMotorClient(mongo_uri)
    db = client[database_name]
    property_data = await db.properties.find_one({})
    client.close()
    
    if property_data:
        property_id = property_data["_id"]
        
        # Simulate different payment behaviors
        for behavior in ["excellent", "good", "poor", "mixed"]:
            print(f"\n{'='*80}")
            print(f" SIMULATING {behavior.upper()} PAYMENT BEHAVIOR")
            print(f"{'='*80}")
            
            result = await simulate_payment_collections(
                mongo_uri=mongo_uri,
                database_name=database_name,
                property_id=property_id,
                period="2025-10",
                payment_behavior=behavior
            )


async def example_export():
    """Export example"""
    
    mongo_uri = "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    database_name = "fq_db"
    
    # Export to JSON
    json_file = await export_invoices_for_payment_processing(
        mongo_uri=mongo_uri,
        database_name=database_name,
        output_format="json"
    )
    
    # Export to CSV
    csv_file = await export_invoices_for_payment_processing(
        mongo_uri=mongo_uri,
        database_name=database_name,
        output_format="csv"
    )


if __name__ == "__main__":
    import sys
    
    print("""
    Invoice Payment Date Generator
    ==============================
    
    Choose an option:
    1. Basic usage - Get all invoices with random payment dates
    2. Filtered usage - Get invoices for specific period
    3. Grouped by timing - Group invoices by payment timing
    4. Simulate payment behaviors
    5. Export to file (JSON/CSV)
    
    """)
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == "1":
        asyncio.run(example_basic_usage())
    elif choice == "2":
        asyncio.run(example_filtered_usage())
    elif choice == "3":
        asyncio.run(example_grouped_usage())
    elif choice == "4":
        asyncio.run(example_simulation())
    elif choice == "5":
        asyncio.run(example_export())
    else:
        print("Invalid choice")