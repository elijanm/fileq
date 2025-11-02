import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import calendar

def make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to timezone-aware UTC datetime"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt

class RentAnalytics:
    """Comprehensive rent analytics and reporting"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_property_rent_summary(self, property_id: str, period: Optional[str] = None) -> Dict:
        """
        Get comprehensive rent summary for a property
        
        Args:
            property_id: Property ID
            period: Optional period filter (YYYY-MM)
        
        Returns:
            Rent analytics summary
        """
        
        print("\n" + "=" * 80)
        print(f" RENT ANALYTICS - PROPERTY SUMMARY")
        if period:
            print(f" Period: {period}")
        print("=" * 80)
        
        # Get property details
        property_data = await self.db.properties.find_one({"_id": property_id})
        if not property_data:
            return {"error": "Property not found"}
        
        # Build invoice query
        invoice_query = {"property_id": property_id}
        if period:
            year, month = map(int, period.split("-"))
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
            
            invoice_query["date_issued"] = {
                "$gte": start_date,
                "$lt": end_date
            }
        
        # Get all invoices
        invoices_cursor = self.db.property_invoices.find(invoice_query)
        invoices = await invoices_cursor.to_list(length=None)
        
        # Calculate metrics
        total_expected = sum(inv.get("total_amount", 0) for inv in invoices)
        total_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        total_outstanding = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        # Collection rate
        collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0
        
        # Count invoices by status
        status_counts = {}
        for inv in invoices:
            status = inv.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Get active leases
        active_leases = await self.db.property_leases.count_documents({
            "property_id": property_id,
            "status": "signed"
        })
        
        # Expected monthly rent (from active leases)
        leases_cursor = self.db.property_leases.find({
            "property_id": property_id,
            "status": "signed"
        })
        leases = await leases_cursor.to_list(length=None)
        expected_monthly_rent = sum(lease["lease_terms"]["rent_amount"] for lease in leases)
        
        result = {
            "property_id": property_id,
            "property_name": property_data.get("name"),
            "period": period or "All time",
            "active_leases": active_leases,
            "expected_monthly_rent": expected_monthly_rent,
            "financial_summary": {
                "total_expected": round(total_expected, 2),
                "total_collected": round(total_collected, 2),
                "total_outstanding": round(total_outstanding, 2),
                "collection_rate": round(collection_rate, 2)
            },
            "invoice_summary": {
                "total_invoices": len(invoices),
                "by_status": status_counts
            }
        }
        
        self._print_property_summary(result)
        
        return result
    
    def _print_property_summary(self, data: Dict):
        """Print property rent summary"""
        
        print(f"\n🏢 Property: {data['property_name']}")
        print(f"   Period: {data['period']}")
        print(f"   Active Leases: {data['active_leases']}")
        print(f"   Expected Monthly Rent: KES {data['expected_monthly_rent']:,.2f}")
        
        print(f"\n💰 Financial Summary:")
        fs = data['financial_summary']
        print(f"   Expected Revenue: KES {fs['total_expected']:,.2f}")
        print(f"   Collected: KES {fs['total_collected']:,.2f}")
        print(f"   Outstanding: KES {fs['total_outstanding']:,.2f}")
        print(f"   Collection Rate: {fs['collection_rate']:.1f}%")
        
        print(f"\n📊 Invoice Summary:")
        print(f"   Total Invoices: {data['invoice_summary']['total_invoices']}")
        for status, count in data['invoice_summary']['by_status'].items():
            print(f"   {status.capitalize()}: {count}")
    
    async def get_tenant_payment_history(self, tenant_id: str) -> Dict:
        """
        Get detailed payment history for a tenant
        
        Args:
            tenant_id: Tenant ID (string or ObjectId)
        
        Returns:
            Payment history and analytics
        """
        
        # Convert to ObjectId if string
        if isinstance(tenant_id, str):
            tenant_id = ObjectId(tenant_id)
        
        print("\n" + "=" * 80)
        print(f" TENANT PAYMENT HISTORY")
        print("=" * 80)
        
        # Get tenant details
        tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
        if not tenant:
            return {"error": "Tenant not found"}
        
        # Get all invoices
        invoices_cursor = self.db.property_invoices.find({
            "tenant_id": tenant_id
        }).sort("date_issued", 1)
        invoices = await invoices_cursor.to_list(length=None)
        
        # Calculate metrics
        total_invoiced = sum(inv.get("total_amount", 0) for inv in invoices)
        total_paid = sum(inv.get("total_paid", 0) for inv in invoices)
        total_outstanding = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        # Payment performance
        on_time_payments = 0
        late_payments = 0
        unpaid_invoices = 0
        
        for inv in invoices:
            if inv.get("status") == "paid":
                # Check if paid on time (before or on due date)
                # Simplified: just count paid vs unpaid
                if inv.get("total_paid", 0) >= inv.get("total_amount", 0):
                    on_time_payments += 1
                else:
                    late_payments += 1
            elif inv.get("status") in ["partially_paid", "overdue"]:
                late_payments += 1
            else:
                unpaid_invoices += 1
        
        # Average payment time (days from issue to payment)
        payment_times = []
        for inv in invoices:
            if inv.get("payments"):
                for payment in inv["payments"]:
                    payment_date = payment.get("payment_date")
                    issue_date = inv.get("date_issued")
                    if payment_date and issue_date:
                        days = (payment_date - issue_date).days
                        payment_times.append(days)
        
        avg_payment_time = sum(payment_times) / len(payment_times) if payment_times else 0
        
        # Monthly breakdown
        monthly_data = {}
        for inv in invoices:
            if inv.get("date_issued"):
                month_key = inv["date_issued"].strftime("%Y-%m")
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        "expected": 0,
                        "collected": 0,
                        "outstanding": 0
                    }
                monthly_data[month_key]["expected"] += inv.get("total_amount", 0)
                monthly_data[month_key]["collected"] += inv.get("total_paid", 0)
                monthly_data[month_key]["outstanding"] += inv.get("balance_amount", 0)
        
        result = {
            "tenant_id": str(tenant_id),
            "tenant_name": tenant.get("full_name"),
            "tenant_email": tenant.get("email"),
            "tenant_phone": tenant.get("phone"),
            "credit_balance": tenant.get("credit_balance", 0),
            "summary": {
                "total_invoices": len(invoices),
                "total_invoiced": round(total_invoiced, 2),
                "total_paid": round(total_paid, 2),
                "total_outstanding": round(total_outstanding, 2),
                "collection_rate": round((total_paid / total_invoiced * 100) if total_invoiced > 0 else 0, 2)
            },
            "payment_performance": {
                "on_time": on_time_payments,
                "late": late_payments,
                "unpaid": unpaid_invoices,
                "average_payment_days": round(avg_payment_time, 1)
            },
            "monthly_breakdown": monthly_data,
            "invoices": [
                {
                    "invoice_id": str(inv["_id"]),
                    "invoice_number": inv.get("invoice_number"),
                    "date_issued": inv.get("date_issued"),
                    "due_date": inv.get("due_date"),
                    "total_amount": inv.get("total_amount", 0),
                    "total_paid": inv.get("total_paid", 0),
                    "balance": inv.get("balance_amount", 0),
                    "status": inv.get("status")
                }
                for inv in invoices
            ]
        }
        
        self._print_tenant_history(result)
        
        return result
    
    def _print_tenant_history(self, data: Dict):
        """Print tenant payment history"""
        
        print(f"\n👤 Tenant: {data['tenant_name']}")
        print(f"   Email: {data['tenant_email']}")
        print(f"   Phone: {data['tenant_phone']}")
        if data['credit_balance'] > 0:
            print(f"   Credit Balance: KES {data['credit_balance']:,.2f}")
        
        print(f"\n💰 Financial Summary:")
        s = data['summary']
        print(f"   Total Invoices: {s['total_invoices']}")
        print(f"   Total Invoiced: KES {s['total_invoiced']:,.2f}")
        print(f"   Total Paid: KES {s['total_paid']:,.2f}")
        print(f"   Outstanding: KES {s['total_outstanding']:,.2f}")
        print(f"   Collection Rate: {s['collection_rate']:.1f}%")
        
        print(f"\n📊 Payment Performance:")
        p = data['payment_performance']
        print(f"   On Time: {p['on_time']}")
        print(f"   Late: {p['late']}")
        print(f"   Unpaid: {p['unpaid']}")
        print(f"   Avg Payment Time: {p['average_payment_days']:.1f} days")
        
        print(f"\n📅 Recent Invoices:")
        for inv in data['invoices'][-5:]:
            status_emoji = {
                "paid": "✅",
                "partially_paid": "⚠️",
                "unpaid": "❌",
                "overdue": "🔴"
            }.get(inv['status'], "❓")
            
            print(f"   {status_emoji} {inv['invoice_number']}: KES {inv['total_amount']:,.2f} "
                  f"(Paid: KES {inv['total_paid']:,.2f}, Balance: KES {inv['balance']:,.2f})")
    
    async def get_monthly_collection_report(self, property_id: str, year: int, month: int) -> Dict:
        """
        Generate detailed monthly collection report
        
        Args:
            property_id: Property ID
            year: Year
            month: Month (1-12)
        
        Returns:
            Detailed monthly report
        """
        
        period = f"{year}-{month:02d}"
        
        print("\n" + "=" * 80)
        print(f" MONTHLY COLLECTION REPORT - {calendar.month_name[month]} {year}")
        print("=" * 80)
        
        # Date range
        start_date = datetime(year, month, 1, tzinfo=timezone.utc)
        if month == 12:
            end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
        
        # Get invoices for the month
        invoices_cursor = self.db.property_invoices.find({
            "property_id": property_id,
            "date_issued": {
                "$gte": start_date,
                "$lt": end_date
            }
        })
        invoices = await invoices_cursor.to_list(length=None)
        
        # Get property details
        property_data = await self.db.properties.find_one({"_id": property_id})
        
        # Calculate totals
        total_rent = 0
        total_utilities = 0
        total_other = 0
        
        for inv in invoices:
            for item in inv.get("line_items", []):
                amount = item.get("amount", 0)
                if item.get("type") == "rent":
                    total_rent += amount
                elif item.get("type") == "utility":
                    total_utilities += amount
                else:
                    total_other += amount
        
        total_expected = sum(inv.get("total_amount", 0) for inv in invoices)
        total_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        total_outstanding = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        # Tenant-wise breakdown
        tenant_breakdown = []
        tenant_ids = set(inv.get("tenant_id") for inv in invoices if inv.get("tenant_id"))
        
        for tenant_id in tenant_ids:
            tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
            if not tenant:
                continue
            
            tenant_invoices = [inv for inv in invoices if inv.get("tenant_id") == tenant_id]
            
            tenant_expected = sum(inv.get("total_amount", 0) for inv in tenant_invoices)
            tenant_paid = sum(inv.get("total_paid", 0) for inv in tenant_invoices)
            tenant_outstanding = sum(inv.get("balance_amount", 0) for inv in tenant_invoices)
            
            tenant_breakdown.append({
                "tenant_id": str(tenant_id),
                "tenant_name": tenant.get("full_name"),
                "expected": tenant_expected,
                "collected": tenant_paid,
                "outstanding": tenant_outstanding,
                "collection_rate": round((tenant_paid / tenant_expected * 100) if tenant_expected > 0 else 0, 2)
            })
        
        # Sort by collection rate (worst first)
        tenant_breakdown.sort(key=lambda x: x["collection_rate"])
        
        result = {
            "property_id": property_id,
            "property_name": property_data.get("name"),
            "period": period,
            "month_name": calendar.month_name[month],
            "year": year,
            "summary": {
                "total_expected": round(total_expected, 2),
                "total_collected": round(total_collected, 2),
                "total_outstanding": round(total_outstanding, 2),
                "collection_rate": round((total_collected / total_expected * 100) if total_expected > 0 else 0, 2),
                "total_invoices": len(invoices)
            },
            "breakdown_by_type": {
                "rent": round(total_rent, 2),
                "utilities": round(total_utilities, 2),
                "other": round(total_other, 2)
            },
            "tenant_breakdown": tenant_breakdown
        }
        
        self._print_monthly_report(result)
        
        return result
    
    def _print_monthly_report(self, data: Dict):
        """Print monthly collection report"""
        
        print(f"\n🏢 Property: {data['property_name']}")
        print(f"   Period: {data['month_name']} {data['year']}")
        
        print(f"\n💰 Overall Summary:")
        s = data['summary']
        print(f"   Total Expected: KES {s['total_expected']:,.2f}")
        print(f"   Total Collected: KES {s['total_collected']:,.2f}")
        print(f"   Outstanding: KES {s['total_outstanding']:,.2f}")
        print(f"   Collection Rate: {s['collection_rate']:.1f}%")
        print(f"   Total Invoices: {s['total_invoices']}")
        
        print(f"\n📊 Breakdown by Type:")
        b = data['breakdown_by_type']
        print(f"   Rent: KES {b['rent']:,.2f}")
        print(f"   Utilities: KES {b['utilities']:,.2f}")
        print(f"   Other: KES {b['other']:,.2f}")
        
        print(f"\n👥 Tenant-wise Collection (Worst to Best):")
        print(f"   {'Tenant Name':<30} {'Expected':>12} {'Collected':>12} {'Outstanding':>12} {'Rate':>8}")
        print(f"   {'-'*79}")
        
        for tenant in data['tenant_breakdown'][:10]:  # Show top 10
            rate_emoji = "🔴" if tenant['collection_rate'] < 50 else "⚠️" if tenant['collection_rate'] < 80 else "✅"
            print(f"   {tenant['tenant_name']:<30} "
                  f"KES {tenant['expected']:>9,.2f} "
                  f"KES {tenant['collected']:>9,.2f} "
                  f"KES {tenant['outstanding']:>9,.2f} "
                  f"{rate_emoji} {tenant['collection_rate']:>5.1f}%")
    
    async def get_overdue_report(self, property_id: Optional[str] = None) -> Dict:
        """
        Get report of all overdue invoices
        
        Args:
            property_id: Optional property filter
        
        Returns:
            Overdue invoices report
        """
        
        print("\n" + "=" * 80)
        print(f" OVERDUE INVOICES REPORT")
        print("=" * 80)
        
        current_date = datetime.now(timezone.utc)
        
        # Build query
        query = {
            "due_date": {"$lt": current_date},
            "balance_amount": {"$gt": 0}
        }
        
        if property_id:
            query["property_id"] = property_id
        
        # Get overdue invoices
        invoices_cursor = self.db.property_invoices.find(query).sort("due_date", 1)
        invoices = await invoices_cursor.to_list(length=None)
        
        # Calculate totals
        total_overdue = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        # Group by tenant
        tenant_overdue = {}
        for inv in invoices:
            tenant_id = inv.get("tenant_id")
            if tenant_id:
                if tenant_id not in tenant_overdue:
                    tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
                    tenant_overdue[tenant_id] = {
                        "tenant_name": tenant.get("full_name") if tenant else "Unknown",
                        "tenant_phone": tenant.get("phone") if tenant else "",
                        "total_overdue": 0,
                        "invoice_count": 0,
                        "oldest_due_date": None,
                        "invoices": []
                    }
                
                tenant_overdue[tenant_id]["total_overdue"] += inv.get("balance_amount", 0)
                tenant_overdue[tenant_id]["invoice_count"] += 1
                
                due_date = inv.get("due_date")
                if due_date:
                    if not tenant_overdue[tenant_id]["oldest_due_date"] or due_date < tenant_overdue[tenant_id]["oldest_due_date"]:
                        tenant_overdue[tenant_id]["oldest_due_date"] = due_date
                
                days_overdue = ((current_date) - make_aware(due_date)).days if due_date else 0
                
                tenant_overdue[tenant_id]["invoices"].append({
                    "invoice_id": str(inv["_id"]),
                    "invoice_number": inv.get("invoice_number"),
                    "due_date": due_date,
                    "days_overdue": days_overdue,
                    "balance": inv.get("balance_amount", 0)
                })
        
        # Convert to list and sort by total overdue
        tenant_list = []
        for tenant_id, data in tenant_overdue.items():
            data["tenant_id"] = str(tenant_id)
            tenant_list.append(data)
        
        tenant_list.sort(key=lambda x: x["total_overdue"], reverse=True)
        
        result = {
            "total_overdue_amount": round(total_overdue, 2),
            "total_overdue_invoices": len(invoices),
            "total_affected_tenants": len(tenant_list),
            "tenants": tenant_list
        }
        
        self._print_overdue_report(result)
        
        return result
    
    def _print_overdue_report(self, data: Dict):
        """Print overdue report"""
        
        print(f"\n⚠️  Overdue Summary:")
        print(f"   Total Overdue Amount: KES {data['total_overdue_amount']:,.2f}")
        print(f"   Total Overdue Invoices: {data['total_overdue_invoices']}")
        print(f"   Affected Tenants: {data['total_affected_tenants']}")
        
        print(f"\n👥 Tenants with Overdue Payments (Highest to Lowest):")
        print(f"   {'Tenant Name':<30} {'Phone':<15} {'Overdue':>12} {'Invoices':>10} {'Oldest Due':>12}")
        print(f"   {'-'*85}")
        
        for tenant in data['tenants'][:15]:  # Show top 15
            oldest = tenant['oldest_due_date'].strftime('%Y-%m-%d') if tenant['oldest_due_date'] else 'N/A'
            print(f"   {tenant['tenant_name']:<30} "
                  f"{tenant['tenant_phone']:<15} "
                  f"KES {tenant['total_overdue']:>9,.2f} "
                  f"{tenant['invoice_count']:>10} "
                  f"{oldest:>12}")
    
    async def get_utility_consumption_report(
        self,
        property_id: str,
        utility_name: str,
        start_period: str,
        end_period: str
    ) -> Dict:
        """
        Get utility consumption report
        
        Args:
            property_id: Property ID
            utility_name: Utility name (e.g., "Water", "Electricity")
            start_period: Start period (YYYY-MM)
            end_period: End period (YYYY-MM)
        
        Returns:
            Utility consumption report
        """
        
        print("\n" + "=" * 80)
        print(f" UTILITY CONSUMPTION REPORT - {utility_name}")
        print(f" Period: {start_period} to {end_period}")
        print("=" * 80)
        
        # Parse periods
        start_year, start_month = map(int, start_period.split("-"))
        end_year, end_month = map(int, end_period.split("-"))
        
        start_date = datetime(start_year, start_month, 1, tzinfo=timezone.utc)
        if end_month == 12:
            end_date = datetime(end_year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end_date = datetime(end_year, end_month + 1, 1, tzinfo=timezone.utc)
        
        # Get all invoices in period
        invoices_cursor = self.db.property_invoices.find({
            "property_id": property_id,
            "date_issued": {
                "$gte": start_date,
                "$lt": end_date
            }
        })
        invoices = await invoices_cursor.to_list(length=None)
        
        # Extract utility data from line items
        consumption_data = {}
        total_consumption = 0
        total_cost = 0
        
        for inv in invoices:
            period = inv.get("date_issued").strftime("%Y-%m") if inv.get("date_issued") else "Unknown"
            
            for item in inv.get("line_items", []):
                if (item.get("type") == "utility" and 
                    item.get("utility_name", "").lower() == utility_name.lower()):
                    
                    meta = item.get("meta", {})
                    usage = meta.get("usage", item.get("quantity", 0))
                    amount = item.get("amount", 0)
                    
                    if period not in consumption_data:
                        consumption_data[period] = {
                            "usage": 0,
                            "cost": 0,
                            "unit_count": 0
                        }
                    
                    consumption_data[period]["usage"] += usage
                    consumption_data[period]["cost"] += amount
                    consumption_data[period]["unit_count"] += 1
                    
                    total_consumption += usage
                    total_cost += amount
        
        # Calculate averages
        months_count = len(consumption_data)
        avg_monthly_consumption = total_consumption / months_count if months_count > 0 else 0
        avg_monthly_cost = total_cost / months_count if months_count > 0 else 0
        
        result = {
            "property_id": property_id,
            "utility_name": utility_name,
            "start_period": start_period,
            "end_period": end_period,
            "summary": {
                "total_consumption": round(total_consumption, 2),
                "total_cost": round(total_cost, 2),
                "avg_monthly_consumption": round(avg_monthly_consumption, 2),
                "avg_monthly_cost": round(avg_monthly_cost, 2),
                "months_analyzed": months_count
            },
            "monthly_data": consumption_data
        }
        
        self._print_utility_report(result)
        
        return result
    
    def _print_utility_report(self, data: Dict):
        """Print utility consumption report"""
        
        print(f"\n💡 {data['utility_name']} Consumption Analysis")
        
        print(f"\n📊 Summary:")
        s = data['summary']
        print(f"   Total Consumption: {s['total_consumption']:,.2f} units")
        print(f"   Total Cost: KES {s['total_cost']:,.2f}")
        print(f"   Avg Monthly Consumption: {s['avg_monthly_consumption']:,.2f} units")
        print(f"   Avg Monthly Cost: KES {s['avg_monthly_cost']:,.2f}")
        print(f"   Months Analyzed: {s['months_analyzed']}")
        
        print(f"\n📅 Monthly Breakdown:")
        print(f"   {'Period':<10} {'Consumption':>15} {'Cost':>12} {'Units':>8}")
        print(f"   {'-'*50}")
        
        for period in sorted(data['monthly_data'].keys()):
            monthly = data['monthly_data'][period]
            print(f"   {period:<10} {monthly['usage']:>12,.2f} units "
                  f"KES {monthly['cost']:>8,.2f} {monthly['unit_count']:>8}")
    
    async def get_collection_efficiency_report(self, property_id: str, months: int = 6) -> Dict:
        """
        Analyze collection efficiency over time
        
        Args:
            property_id: Property ID
            months: Number of months to analyze
        
        Returns:
            Collection efficiency report
        """
        
        print("\n" + "=" * 80)
        print(f" COLLECTION EFFICIENCY ANALYSIS - Last {months} Months")
        print("=" * 80)
        
        current_date = datetime.now(timezone.utc)
        monthly_data = {}
        
        for i in range(months):
            # Calculate month
            month_date = current_date - timedelta(days=30 * i)
            period = month_date.strftime("%Y-%m")
            year, month = map(int, period.split("-"))
            
            # Get monthly report
            report = await self.get_monthly_collection_report(property_id, year, month)
            
            monthly_data[period] = {
                "expected": report["summary"]["total_expected"],
                "collected": report["summary"]["total_collected"],
                "outstanding": report["summary"]["total_outstanding"],
                "collection_rate": report["summary"]["collection_rate"],
                "invoice_count": report["summary"]["total_invoices"]
            }
        
        # Calculate trends
        periods = sorted(monthly_data.keys())
        if len(periods) >= 2:
            latest = monthly_data[periods[-1]]
            previous = monthly_data[periods[-2]]
            
            trend = {
                "collection_rate_change": latest["collection_rate"] - previous["collection_rate"],
                "revenue_change": latest["collected"] - previous["collected"],
                "improving": latest["collection_rate"] > previous["collection_rate"]
            }
        else:
            trend = None
        
        result = {
            "property_id": property_id,
            "months_analyzed": months,
            "monthly_data": monthly_data,
            "trend": trend
        }
        
        self._print_efficiency_report(result)
        
        return result
    
    def _print_efficiency_report(self, data: Dict):
        """Print collection efficiency report"""
        
        print(f"\n📈 Monthly Collection Trend:")
        print(f"   {'Period':<10} {'Expected':>12} {'Collected':>12} {'Rate':>8} {'Invoices':>10}")
        print(f"   {'-'*60}")
        
        for period in sorted(data['monthly_data'].keys(), reverse=True):
            monthly = data['monthly_data'][period]
            rate_emoji = "✅" if monthly['collection_rate'] >= 90 else "⚠️" if monthly['collection_rate'] >= 70 else "🔴"
            
            print(f"   {period:<10} "
                  f"KES {monthly['expected']:>9,.2f} "
                  f"KES {monthly['collected']:>9,.2f} "
                  f"{rate_emoji} {monthly['collection_rate']:>5.1f}% "
                  f"{monthly['invoice_count']:>10}")
        
        if data['trend']:
            print(f"\n📊 Trend Analysis:")
            t = data['trend']
            trend_emoji = "📈" if t['improving'] else "📉"
            print(f"   {trend_emoji} Collection Rate Change: {t['collection_rate_change']:+.1f}%")
            print(f"   {'📈' if t['revenue_change'] > 0 else '📉'} Revenue Change: KES {t['revenue_change']:+,.2f}")
            print(f"   Status: {'IMPROVING ✅' if t['improving'] else 'DECLINING ⚠️'}")


# Main execution functions

async def run_property_analytics(property_id: str):
    """Run complete property analytics"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    analytics = RentAnalytics(db)
    
    try:
        # 1. Overall property summary
        await analytics.get_property_rent_summary(property_id)
        
        # 2. Current month report
        current = datetime.now()
        await analytics.get_monthly_collection_report(
            property_id,
            current.year,
            current.month
        )
        
        # 3. Overdue report
        await analytics.get_overdue_report(property_id)
        
        # 4. Collection efficiency
        await analytics.get_collection_efficiency_report(property_id, months=6)
        
        # 5. Utility consumption
        await analytics.get_utility_consumption_report(
            property_id,
            "Water",
            "2025-01",
            "2025-10"
        )
        
    finally:
        client.close()


async def run_tenant_analytics(tenant_id: str):
    """Run analytics for a specific tenant"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    analytics = RentAnalytics(db)
    
    try:
        await analytics.get_tenant_payment_history(tenant_id)
    finally:
        client.close()


async def run_all_analytics():
    """Run all analytics reports"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    analytics = RentAnalytics(db)
    
    try:
        # Get all properties
        properties_cursor = db.properties.find({})
        properties = await properties_cursor.to_list(length=None)
        
        print("=" * 80)
        print(" COMPLETE RENT ANALYTICS REPORT")
        print("=" * 80)
        
        for prop in properties:
            property_id = prop["_id"]
            
            print(f"\n\n{'#' * 80}")
            print(f"# PROPERTY: {prop.get('name')}")
            print(f"{'#' * 80}")
            
            # Property summary
            await analytics.get_property_rent_summary(property_id)
            
            # Current month
            current = datetime.now()
            await analytics.get_monthly_collection_report(
                property_id,
                current.year,
                current.month
            )
            
            # Overdue
            await analytics.get_overdue_report(property_id)
            
            # Efficiency
            await analytics.get_collection_efficiency_report(property_id, months=3)
        
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    print("""
    Rent Analytics System
    ====================
    
    Choose an option:
    1. Property analytics (all reports for one property)
    2. Tenant payment history
    3. All properties analytics
    
    """)
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        property_id = input("Enter property ID: ").strip()
        asyncio.run(run_property_analytics(property_id))
    
    elif choice == "2":
        tenant_id = input("Enter tenant ID: ").strip()
        asyncio.run(run_tenant_analytics(tenant_id))
    
    elif choice == "3":
        asyncio.run(run_all_analytics())
    
    else:
        print("Invalid choice")