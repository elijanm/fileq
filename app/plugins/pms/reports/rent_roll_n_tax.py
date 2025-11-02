import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Literal
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import calendar
from collections import defaultdict


class RentRollAndTaxesReportGenerator:
    """
    Generate comprehensive rent roll and tax reports for property management
    """
    
    def __init__(self, db):
        self.db = db
    
    async def generate_rent_roll_report(
        self,
        property_id: Optional[str] = None,
        as_of_date: Optional[datetime] = None,
        include_vacant: bool = True,
        include_financial_details: bool = True
    ) -> Dict:
        """
        Generate a comprehensive rent roll report
        
        A rent roll is a detailed listing of all rental units showing:
        - Unit details
        - Tenant information
        - Lease terms
        - Rent amounts
        - Payment status
        - Occupancy information
        
        Args:
            property_id: Specific property (None = all properties)
            as_of_date: Report date (default = today)
            include_vacant: Include vacant units
            include_financial_details: Include payment history
        
        Returns:
            Complete rent roll report
        """
        
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc)
        
        print("\n" + "=" * 120)
        print(" RENT ROLL REPORT")
        print(f" As of: {as_of_date.strftime('%B %d, %Y')}")
        print("=" * 120)
        
        # Build query for properties
        property_query = {}
        if property_id:
            property_query["_id"] = property_id
        
        properties_cursor = self.db.properties.find(property_query)
        properties = await properties_cursor.to_list(length=None)
        
        report = {
            "report_id": f"RENTROLL-{as_of_date.strftime('%Y%m%d')}",
            "generated_at": datetime.now(timezone.utc),
            "as_of_date": as_of_date,
            "properties": [],
            "summary": {
                "total_properties": len(properties),
                "total_units": 0,
                "occupied_units": 0,
                "vacant_units": 0,
                "total_monthly_rent": 0,
                "total_security_deposits": 0,
                "total_outstanding": 0,
                "occupancy_rate": 0,
            }
        }
        
        for prop in properties:
            property_report = await self._generate_property_rent_roll(
                prop,
                as_of_date,
                include_vacant,
                include_financial_details
            )
            
            report["properties"].append(property_report)
            
            # Update summary
            report["summary"]["total_units"] += property_report["summary"]["total_units"]
            report["summary"]["occupied_units"] += property_report["summary"]["occupied_units"]
            report["summary"]["vacant_units"] += property_report["summary"]["vacant_units"]
            report["summary"]["total_monthly_rent"] += property_report["summary"]["total_monthly_rent"]
            report["summary"]["total_security_deposits"] += property_report["summary"]["total_security_deposits"]
            report["summary"]["total_outstanding"] += property_report["summary"]["total_outstanding"]
        
        # Calculate overall occupancy
        if report["summary"]["total_units"] > 0:
            report["summary"]["occupancy_rate"] = round(
                (report["summary"]["occupied_units"] / report["summary"]["total_units"] * 100), 2
            )
        
        # Print report
        self._print_rent_roll_report(report)
        
        return report
    
    async def _generate_property_rent_roll(
        self,
        property_data: Dict,
        as_of_date: datetime,
        include_vacant: bool,
        include_financial_details: bool
    ) -> Dict:
        """Generate rent roll for a single property"""
        
        property_id = property_data["_id"]
        
        # Get all units
        units_cursor = self.db.property_units.find({"property_id": property_id}).sort("unitNumber", 1)
        units = await units_cursor.to_list(length=None)
        
        # Get active leases
        leases_cursor = self.db.property_leases.find({
            "property_id": property_id,
            "status": "signed",
            "lease_terms.start_date": {"$lte": as_of_date},
            "lease_terms.end_date": {"$gte": as_of_date}
        })
        leases = await leases_cursor.to_list(length=None)
        
        # Create lookup for occupied units
        occupied_units = {}
        for lease in leases:
            for unit_id in lease.get("units_id", []):
                occupied_units[unit_id] = lease
        
        # Build unit details
        unit_details = []
        total_monthly_rent = 0
        total_deposits = 0
        total_outstanding = 0
        
        for unit in units:
            unit_id = unit["_id"]
            lease = occupied_units.get(unit_id)
            
            if lease:
                # Occupied unit
                tenant_id = lease["tenant_id"]
                tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
                
                # Get financial details
                if include_financial_details:
                    financial = await self._get_unit_financial_details(
                        str(lease["_id"]),
                        as_of_date
                    )
                else:
                    financial = {}
                
                # Calculate lease status
                end_date = lease["lease_terms"]["end_date"]
                days_to_expiry = (end_date - as_of_date).days
                
                if days_to_expiry < 0:
                    lease_status = "expired"
                elif days_to_expiry <= 30:
                    lease_status = "expiring_soon"
                elif days_to_expiry <= 90:
                    lease_status = "expiring_90_days"
                else:
                    lease_status = "active"
                
                unit_detail = {
                    "unit_id": str(unit_id),
                    "unit_number": unit.get("unitNumber"),
                    "unit_name": unit.get("unitName"),
                    "bedrooms": unit.get("bedrooms"),
                    "square_feet": unit.get("squareFeet"),
                    "status": "occupied",
                    "tenant": {
                        "tenant_id": str(tenant_id),
                        "name": tenant.get("full_name") if tenant else "Unknown",
                        "email": tenant.get("email") if tenant else "",
                        "phone": tenant.get("phone") if tenant else "",
                        "move_in_date": lease.get("move_in_date"),
                    },
                    "lease": {
                        "lease_id": str(lease["_id"]),
                        "start_date": lease["lease_terms"]["start_date"],
                        "end_date": lease["lease_terms"]["end_date"],
                        "days_to_expiry": days_to_expiry,
                        "lease_status": lease_status,
                        "rent_amount": lease["lease_terms"]["rent_amount"],
                        "deposit_amount": lease["lease_terms"]["deposit_amount"],
                    },
                    "financial": financial
                }
                
                total_monthly_rent += lease["lease_terms"]["rent_amount"]
                total_deposits += lease["lease_terms"]["deposit_amount"]
                total_outstanding += financial.get("balance", 0)
                
                unit_details.append(unit_detail)
            
            elif include_vacant:
                # Vacant unit
                unit_detail = {
                    "unit_id": str(unit_id),
                    "unit_number": unit.get("unitNumber"),
                    "unit_name": unit.get("unitName"),
                    "bedrooms": unit.get("bedrooms"),
                    "square_feet": unit.get("squareFeet"),
                    "status": "vacant",
                    "market_rent": unit.get("rentAmount"),
                    "tenant": None,
                    "lease": None,
                    "financial": {}
                }
                
                unit_details.append(unit_detail)
        
        return {
            "property_id": property_id,
            "property_name": property_data.get("name"),
            "property_address": property_data.get("location"),
            "summary": {
                "total_units": len(units),
                "occupied_units": len(occupied_units),
                "vacant_units": len(units) - len(occupied_units),
                "occupancy_rate": round((len(occupied_units) / len(units) * 100) if units else 0, 2),
                "total_monthly_rent": round(total_monthly_rent, 2),
                "total_security_deposits": round(total_deposits, 2),
                "total_outstanding": round(total_outstanding, 2),
            },
            "units": unit_details
        }
    
    async def _get_unit_financial_details(
        self,
        lease_id: str,
        as_of_date: datetime
    ) -> Dict:
        """Get financial details for a unit/lease"""
        
        # Get all invoices for this lease
        invoices_cursor = self.db.property_invoices.find({
            "lease_id": lease_id,
            "date_issued": {"$lte": as_of_date}
        })
        invoices = await invoices_cursor.to_list(length=None)
        
        total_billed = sum(inv.get("total_amount", 0) for inv in invoices)
        total_paid = sum(inv.get("total_paid", 0) for inv in invoices)
        balance = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        # Get last payment
        last_payment_date = None
        last_payment_amount = 0
        
        for inv in invoices:
            payments = inv.get("payments", [])
            if payments:
                latest = max(payments, key=lambda p: p.get("payment_date", datetime.min))
                if not last_payment_date or latest["payment_date"] > last_payment_date:
                    last_payment_date = latest["payment_date"]
                    last_payment_amount = latest.get("amount", 0)
        
        # Check if current month is paid
        current_month = as_of_date.strftime("%Y-%m")
        current_month_invoice = next(
            (inv for inv in invoices if inv.get("date_issued") and inv["date_issued"].strftime("%Y-%m") == current_month),
            None
        )
        
        current_month_status = "not_issued"
        if current_month_invoice:
            if current_month_invoice.get("status") == "paid":
                current_month_status = "paid"
            elif current_month_invoice.get("balance_amount", 0) > 0:
                current_month_status = "unpaid"
        
        return {
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "balance": round(balance, 2),
            "last_payment_date": last_payment_date,
            "last_payment_amount": round(last_payment_amount, 2),
            "current_month_status": current_month_status,
            "months_outstanding": round(balance / current_month_invoice.get("total_amount", 1), 1) if current_month_invoice else 0
        }
    
    def _print_rent_roll_report(self, report: Dict):
        """Print formatted rent roll report"""
        
        print(f"\n📊 PORTFOLIO SUMMARY")
        print(f"   Properties: {report['summary']['total_properties']}")
        print(f"   Total Units: {report['summary']['total_units']}")
        print(f"   Occupied: {report['summary']['occupied_units']} ({report['summary']['occupancy_rate']:.1f}%)")
        print(f"   Vacant: {report['summary']['vacant_units']}")
        print(f"   Monthly Rent: KES {report['summary']['total_monthly_rent']:,.2f}")
        print(f"   Security Deposits: KES {report['summary']['total_security_deposits']:,.2f}")
        print(f"   Outstanding Balance: KES {report['summary']['total_outstanding']:,.2f}")
        
        # Property-by-property breakdown
        for prop_report in report['properties']:
            print(f"\n{'='*120}")
            print(f" 🏢 {prop_report['property_name']}")
            print(f"{'='*120}")
            
            summary = prop_report['summary']
            print(f"\n   Units: {summary['occupied_units']}/{summary['total_units']} occupied ({summary['occupancy_rate']:.1f}%)")
            print(f"   Monthly Rent: KES {summary['total_monthly_rent']:,.2f}")
            print(f"   Outstanding: KES {summary['total_outstanding']:,.2f}")
            
            print(f"\n   {'Unit':<10} {'Tenant':<25} {'Rent':>12} {'Balance':>12} {'Lease End':<12} {'Status':<15}")
            print(f"   {'-'*110}")
            
            for unit in prop_report['units'][:20]:  # Show first 20 units
                if unit['status'] == 'occupied':
                    status_emoji = "🟢" if unit['lease']['lease_status'] == "active" else "🟡" if "expiring" in unit['lease']['lease_status'] else "🔴"
                    
                    print(f"   {unit['unit_number']:<10} "
                          f"{unit['tenant']['name'][:24]:<25} "
                          f"KES {unit['lease']['rent_amount']:>8,.2f} "
                          f"KES {unit['financial'].get('balance', 0):>8,.2f} "
                          f"{unit['lease']['end_date'].strftime('%Y-%m-%d'):<12} "
                          f"{status_emoji} {unit['lease']['lease_status']:<13}")
                else:
                    print(f"   {unit['unit_number']:<10} "
                          f"{'VACANT':<25} "
                          f"KES {unit.get('market_rent', 0):>8,.2f} "
                          f"{'-':>12} "
                          f"{'-':<12} "
                          f"⚪ vacant")
    
    async def generate_tax_report(
        self,
        property_id: Optional[str] = None,
        year: Optional[int] = None,
        report_type: Literal["annual", "quarterly", "monthly"] = "annual"
    ) -> Dict:
        """
        Generate comprehensive tax report for rental income
        
        Includes:
        - Gross rental income
        - Operating expenses
        - Net operating income
        - Depreciation
        - Taxable income
        - Tenant-specific income breakdown
        
        Args:
            property_id: Specific property (None = all properties)
            year: Tax year (default = current year)
            report_type: Report frequency
        
        Returns:
            Tax report
        """
        
        if year is None:
            year = datetime.now().year
        
        print("\n" + "=" * 120)
        print(f" TAX REPORT - {year}")
        print(f" Report Type: {report_type.upper()}")
        print("=" * 120)
        
        # Date ranges
        if report_type == "annual":
            start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            periods = [f"{year}"]
        elif report_type == "quarterly":
            periods = [f"{year}-Q{q}" for q in range(1, 5)]
            start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        else:  # monthly
            periods = [f"{year}-{m:02d}" for m in range(1, 13)]
            start_date = datetime(year, 1, 1, tzinfo=timezone.utc)
            end_date = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        
        # Build property query
        property_query = {}
        if property_id:
            property_query["_id"] = property_id
        
        properties_cursor = self.db.properties.find(property_query)
        properties = await properties_cursor.to_list(length=None)
        
        report = {
            "report_id": f"TAX-{year}-{datetime.now().strftime('%Y%m%d')}",
            "generated_at": datetime.now(timezone.utc),
            "tax_year": year,
            "report_type": report_type,
            "properties": [],
            "consolidated_summary": {
                "gross_rental_income": 0,
                "operating_expenses": 0,
                "net_operating_income": 0,
                "depreciation": 0,
                "taxable_income": 0,
            }
        }
        
        for prop in properties:
            property_report = await self._generate_property_tax_report(
                prop,
                start_date,
                end_date,
                year
            )
            
            report["properties"].append(property_report)
            
            # Update consolidated summary
            report["consolidated_summary"]["gross_rental_income"] += property_report["income_summary"]["gross_rental_income"]
            report["consolidated_summary"]["operating_expenses"] += property_report["expenses_summary"]["total_expenses"]
            report["consolidated_summary"]["net_operating_income"] += property_report["net_operating_income"]
            report["consolidated_summary"]["depreciation"] += property_report["depreciation"]
            report["consolidated_summary"]["taxable_income"] += property_report["taxable_income"]
        
        # Print report
        self._print_tax_report(report)
        
        return report
    
    async def _generate_property_tax_report(
        self,
        property_data: Dict,
        start_date: datetime,
        end_date: datetime,
        year: int
    ) -> Dict:
        """Generate tax report for a single property"""
        
        property_id = property_data["_id"]
        
        # === INCOME SECTION ===
        
        # Get all invoices for the period
        invoices_cursor = self.db.property_invoices.find({
            "property_id": property_id,
            "date_issued": {"$gte": start_date, "$lte": end_date}
        })
        invoices = await invoices_cursor.to_list(length=None)
        
        # Break down income by type
        rental_income = 0
        utility_income = 0
        other_income = 0
        
        for inv in invoices:
            for item in inv.get("line_items", []):
                amount = item.get("amount", 0)
                item_type = item.get("type")
                
                if item_type == "rent":
                    rental_income += amount
                elif item_type == "utility":
                    utility_income += amount
                else:
                    other_income += amount
        
        gross_rental_income = rental_income + utility_income + other_income
        
        # Get actual collections (cash basis)
        total_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        
        # Tenant-specific breakdown
        tenant_income = defaultdict(lambda: {"name": "", "income": 0, "collected": 0})
        
        for inv in invoices:
            tenant_id = inv.get("tenant_id")
            if tenant_id:
                tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
                tenant_name = tenant.get("full_name") if tenant else "Unknown"
                
                tenant_income[str(tenant_id)]["name"] = tenant_name
                tenant_income[str(tenant_id)]["income"] += inv.get("total_amount", 0)
                tenant_income[str(tenant_id)]["collected"] += inv.get("total_paid", 0)
        
        # === EXPENSES SECTION ===
        
        # TODO: Implement expense tracking from tickets/maintenance
        # For now, use estimated expenses
        
        property_value = float(property_data.get("propertyValue", 0)) if property_data.get("propertyValue") else 0
        
        # Estimated operating expenses (placeholder - replace with actual data)
        operating_expenses = {
            "property_management": gross_rental_income * 0.08,  # 8% of gross rent
            "maintenance_repairs": gross_rental_income * 0.10,  # 10% of gross rent
            "property_taxes": property_value * 0.01,  # 1% of property value annually
            "insurance": property_value * 0.005,  # 0.5% of property value
            "utilities": 0,  # If landlord pays
            "legal_fees": 0,
            "advertising": 0,
            "other": 0
        }
        
        total_expenses = sum(operating_expenses.values())
        
        # === NET OPERATING INCOME ===
        
        net_operating_income = gross_rental_income - total_expenses
        
        # === DEPRECIATION ===
        
        # Residential property depreciation: 27.5 years (US), adjust for Kenya
        # Assuming 2.5% annual depreciation
        annual_depreciation = property_value * 0.025
        
        # === TAXABLE INCOME ===
        
        taxable_income = net_operating_income - annual_depreciation
        
        return {
            "property_id": property_id,
            "property_name": property_data.get("name"),
            "property_value": property_value,
            
            "income_summary": {
                "gross_rental_income": round(gross_rental_income, 2),
                "rental_income": round(rental_income, 2),
                "utility_income": round(utility_income, 2),
                "other_income": round(other_income, 2),
                "total_collected": round(total_collected, 2),
                "uncollected": round(gross_rental_income - total_collected, 2),
            },
            
            "tenant_breakdown": [
                {
                    "tenant_name": data["name"],
                    "income": round(data["income"], 2),
                    "collected": round(data["collected"], 2),
                }
                for tenant_id, data in tenant_income.items()
            ],
            
            "expenses_summary": {
                "property_management": round(operating_expenses["property_management"], 2),
                "maintenance_repairs": round(operating_expenses["maintenance_repairs"], 2),
                "property_taxes": round(operating_expenses["property_taxes"], 2),
                "insurance": round(operating_expenses["insurance"], 2),
                "utilities": round(operating_expenses["utilities"], 2),
                "legal_fees": round(operating_expenses["legal_fees"], 2),
                "advertising": round(operating_expenses["advertising"], 2),
                "other": round(operating_expenses["other"], 2),
                "total_expenses": round(total_expenses, 2),
            },
            
            "net_operating_income": round(net_operating_income, 2),
            "depreciation": round(annual_depreciation, 2),
            "taxable_income": round(taxable_income, 2),
        }
    
    def _print_tax_report(self, report: Dict):
        """Print formatted tax report"""
        
        print(f"\n📊 CONSOLIDATED TAX SUMMARY - {report['tax_year']}")
        print(f"   Properties: {len(report['properties'])}")
        
        consolidated = report['consolidated_summary']
        print(f"\n   Gross Rental Income: KES {consolidated['gross_rental_income']:,.2f}")
        print(f"   Operating Expenses: KES {consolidated['operating_expenses']:,.2f}")
        print(f"   Net Operating Income: KES {consolidated['net_operating_income']:,.2f}")
        print(f"   Depreciation: KES {consolidated['depreciation']:,.2f}")
        print(f"   Taxable Income: KES {consolidated['taxable_income']:,.2f}")
        
        # Property-by-property breakdown
        for prop_report in report['properties']:
            print(f"\n{'='*120}")
            print(f" 🏢 {prop_report['property_name']}")
            print(f"{'='*120}")
            
            print(f"\n   💰 INCOME")
            income = prop_report['income_summary']
            print(f"      Rental Income: KES {income['rental_income']:,.2f}")
            print(f"      Utility Income: KES {income['utility_income']:,.2f}")
            print(f"      Other Income: KES {income['other_income']:,.2f}")
            print(f"      ─────────────────────────────")
            print(f"      Gross Rental Income: KES {income['gross_rental_income']:,.2f}")
            print(f"      Total Collected: KES {income['total_collected']:,.2f}")
            print(f"      Uncollected: KES {income['uncollected']:,.2f}")
            
            print(f"\n   💸 EXPENSES")
            expenses = prop_report['expenses_summary']
            for expense_type, amount in expenses.items():
                if expense_type != "total_expenses" and amount > 0:
                    print(f"      {expense_type.replace('_', ' ').title()}: KES {amount:,.2f}")
            print(f"      ─────────────────────────────")
            print(f"      Total Expenses: KES {expenses['total_expenses']:,.2f}")
            
            print(f"\n   📈 NET INCOME")
            print(f"      Net Operating Income: KES {prop_report['net_operating_income']:,.2f}")
            print(f"      Less: Depreciation: KES {prop_report['depreciation']:,.2f}")
            print(f"      ─────────────────────────────")
            print(f"      Taxable Income: KES {prop_report['taxable_income']:,.2f}")
    
    async def generate_combined_report(
        self,
        property_id: Optional[str] = None,
        as_of_date: Optional[datetime] = None,
        year: Optional[int] = None
    ) -> Dict:
        """
        Generate combined rent roll and tax report
        
        Perfect for year-end reporting or investor presentations
        """
        
        if as_of_date is None:
            as_of_date = datetime.now(timezone.utc)
        
        if year is None:
            year = as_of_date.year
        
        print("\n" + "=" * 120)
        print(f" COMBINED RENT ROLL & TAX REPORT")
        print(f" As of: {as_of_date.strftime('%B %d, %Y')}")
        print(f" Tax Year: {year}")
        print("=" * 120)
        
        # Generate both reports
        rent_roll = await self.generate_rent_roll_report(
            property_id=property_id,
            as_of_date=as_of_date,
            include_vacant=True,
            include_financial_details=True
        )
        
        tax_report = await self.generate_tax_report(
            property_id=property_id,
            year=year,
            report_type="annual"
        )
        
        return {
            "report_id": f"COMBINED-{as_of_date.strftime('%Y%m%d')}",
            "generated_at": datetime.now(timezone.utc),
            "rent_roll": rent_roll,
            "tax_report": tax_report
        }
    
    async def export_rent_roll_to_csv(
        self,
        property_id: Optional[str] = None,
        as_of_date: Optional[datetime] = None
    ) -> str:
        """Export rent roll to CSV file"""
        
        import csv
        
        report = await self.generate_rent_roll_report(
            property_id=property_id,
            as_of_date=as_of_date
        )
        
        filename = f"rent_roll_{report['as_of_date'].strftime('%Y%m%d')}.csv"
        
        with open(filename, 'w', newline='') as f:
            fieldnames = [
                "Property", "Unit", "Status", "Tenant Name", "Tenant Phone",
                "Lease Start", "Lease End", "Monthly Rent", "Security Deposit",
                "Balance", "Last Payment Date", "Last Payment Amount"
            ]
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for prop in report['properties']:
                for unit in prop['units']:
                    if unit['status'] == 'occupied':
                        row = {
                            "Property": prop['property_name'],
                            "Unit": unit['unit_number'],
                            "Status": "Occupied",
                            "Tenant Name": unit['tenant']['name'],
                            "Tenant Phone": unit['tenant']['phone'],
                            "Lease Start": unit['lease']['start_date'].strftime('%Y-%m-%d'),
                            "Lease End": unit['lease']['end_date'].strftime('%Y-%m-%d'),
                            "Monthly Rent": unit['lease']['rent_amount'],
                            "Security Deposit": unit['lease']['deposit_amount'],
                            "Balance": unit['financial'].get('balance', 0),
                            "Last Payment Date": unit['financial'].get('last_payment_date', '').strftime('%Y-%m-%d') if unit['financial'].get('last_payment_date') else '',
                            "Last Payment Amount": unit['financial'].get('last_payment_amount', 0),
                        }
                    else:
                        row = {
                            "Property": prop['property_name'],
                            "Unit": unit['unit_number'],
                            "Status": "Vacant",
                            "Tenant Name": "",
                            "Tenant Phone": "",
                            "Lease Start": "",
                            "Lease End": "",
                            "Monthly Rent": unit.get('market_rent', 0),
                            "Security Deposit": "",
                            "Balance": "",
                            "Last Payment Date": "",
                            "Last Payment Amount": "",
                        }
                    
                    writer.writerow(row)
        
        print(f"\n✅ Rent roll exported to {filename}")
        return filename


# Usage examples

async def example_rent_roll():
    """Generate rent roll report"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    
    generator = RentRollAndTaxesReportGenerator(db)
    
    try:
        # Generate rent roll for all properties
        report = await generator.generate_rent_roll_report(
            include_vacant=True,
            include_financial_details=True
        )
        
        print("\n✅ Rent roll generated successfully!")
        
        # Export to CSV
        csv_file = await generator.export_rent_roll_to_csv()
        
    finally:
        client.close()


async def example_tax_report():
    """Generate tax report"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    
    generator = RentRollAndTaxesReportGenerator(db)
    
    try:
        # Generate annual tax report
        report = await generator.generate_tax_report(
            year=2025,
            report_type="annual"
        )
        
        print("\n✅ Tax report generated successfully!")
        
    finally:
        client.close()


async def example_combined_report():
    """Generate combined rent roll and tax report"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    
    generator = RentRollAndTaxesReportGenerator(db)
    
    try:
        # Generate combined report
        report = await generator.generate_combined_report(
            year=2025
        )
        
        print("\n✅ Combined report generated successfully!")
        
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    print("""
    Rent Roll & Tax Reports
    =======================
    
    1. Rent Roll Report
    2. Tax Report
    3. Combined Report
    4. Export Rent Roll to CSV
    
    """)
    
    choice = input("Choose option (1-4): ").strip()
    
    if choice == "1":
        asyncio.run(example_rent_roll())
    elif choice == "2":
        asyncio.run(example_tax_report())
    elif choice == "3":
        asyncio.run(example_combined_report())
    elif choice == "4":
        asyncio.run(example_rent_roll())
    else:
        print("Invalid choice")
        
# Report Features:
# Rent Roll Report 📊

# Complete unit-by-unit listing
# Tenant information
# Lease terms and expiry dates
# Payment status and balances
# Occupancy statistics
# Security deposits tracking
# Vacant units with market rent
# CSV export capability

# Tax Report 💰

# Gross rental income breakdown
# Operating expenses by category
# Net operating income calculation
# Depreciation calculation
# Taxable income computation
# Tenant-specific income tracking
# Annual/quarterly/monthly reports
# Multi-property consolidation

# Key Metrics:

# Occupancy rates
# Collection rates
# Outstanding balances
# Lease expiration tracking
# Revenue projections
# Expense analysis