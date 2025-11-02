import asyncio
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import Dict, List


class InvoiceDateCorrector:
    """Correct date_issued to be 1-5 days before due_date"""
    
    def __init__(self, mongo_uri: str, database_name: str):
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client[database_name]
    
    async def analyze_invoices(self) -> Dict:
        """Analyze invoices to find date issues"""
        
        print("=" * 80)
        print(" INVOICE DATE ANALYSIS")
        print("=" * 80)
        
        results = {
            "total_invoices": 0,
            "invoices_with_issues": [],
            "correct_invoices": 0,
            "issues_by_type": {
                "issued_after_due": 0,
                "issued_same_as_due": 0,
                "issued_too_early": 0,  # More than 5 days before
                "missing_date_issued": 0,
                "missing_due_date": 0
            }
        }
        
        cursor = self.db.property_invoices.find({})
        
        async for invoice in cursor:
            results["total_invoices"] += 1
            invoice_id = str(invoice["_id"])
            
            date_issued = invoice.get("date_issued")
            due_date = invoice.get("due_date")
            
            # Check for missing dates
            if not date_issued:
                results["issues_by_type"]["missing_date_issued"] += 1
                results["invoices_with_issues"].append({
                    "invoice_id": invoice_id,
                    "issue": "missing_date_issued",
                    "date_issued": None,
                    "due_date": due_date
                })
                continue
            
            if not due_date:
                results["issues_by_type"]["missing_due_date"] += 1
                results["invoices_with_issues"].append({
                    "invoice_id": invoice_id,
                    "issue": "missing_due_date",
                    "date_issued": date_issued,
                    "due_date": None
                })
                continue
            
            # Calculate days difference
            days_diff = (due_date - date_issued).days
            
            if days_diff < 0:
                # Issued after due date
                results["issues_by_type"]["issued_after_due"] += 1
                results["invoices_with_issues"].append({
                    "invoice_id": invoice_id,
                    "issue": "issued_after_due",
                    "date_issued": date_issued,
                    "due_date": due_date,
                    "days_diff": days_diff
                })
            elif days_diff == 0:
                # Issued same day as due
                results["issues_by_type"]["issued_same_as_due"] += 1
                results["invoices_with_issues"].append({
                    "invoice_id": invoice_id,
                    "issue": "issued_same_as_due",
                    "date_issued": date_issued,
                    "due_date": due_date,
                    "days_diff": days_diff
                })
            elif days_diff > 5:
                # Issued more than 5 days before due
                results["issues_by_type"]["issued_too_early"] += 1
                results["invoices_with_issues"].append({
                    "invoice_id": invoice_id,
                    "issue": "issued_too_early",
                    "date_issued": date_issued,
                    "due_date": due_date,
                    "days_diff": days_diff
                })
            else:
                # Correct: 1-5 days before due date
                results["correct_invoices"] += 1
        
        return results
    
    def print_analysis(self, results: Dict):
        """Print analysis results"""
        
        print(f"\n📊 Analysis Results:")
        print(f"   Total Invoices: {results['total_invoices']:,}")
        print(f"   Correct Invoices: {results['correct_invoices']:,}")
        print(f"   Invoices with Issues: {len(results['invoices_with_issues']):,}")
        
        print(f"\n⚠️  Issues Breakdown:")
        for issue_type, count in results['issues_by_type'].items():
            if count > 0:
                print(f"   {issue_type.replace('_', ' ').title()}: {count:,}")
        
        if results['invoices_with_issues']:
            print(f"\n📋 Sample Issues (first 10):")
            for i, issue in enumerate(results['invoices_with_issues'][:10]):
                print(f"\n   {i+1}. Invoice: {issue['invoice_id'][:16]}...")
                print(f"      Issue: {issue['issue']}")
                if issue.get('date_issued'):
                    print(f"      Date Issued: {issue['date_issued'].strftime('%Y-%m-%d')}")
                if issue.get('due_date'):
                    print(f"      Due Date: {issue['due_date'].strftime('%Y-%m-%d')}")
                if issue.get('days_diff') is not None:
                    print(f"      Days Difference: {issue['days_diff']}")
    
    async def correct_invoice_dates(
        self,
        dry_run: bool = True,
        days_before_due: int = 1
    ) -> Dict:
        """
        Correct date_issued to be X days before due_date
        
        Args:
            dry_run: If True, only simulate changes without updating
            days_before_due: How many days before due_date to set date_issued (1-5)
        
        Returns:
            Dictionary with correction results
        """
        
        if not 1 <= days_before_due <= 5:
            raise ValueError("days_before_due must be between 1 and 5")
        
        print("\n" + "=" * 80)
        if dry_run:
            print(" DRY RUN - SIMULATING CORRECTIONS (NO CHANGES WILL BE MADE)")
        else:
            print(" CORRECTING INVOICE DATES")
        print("=" * 80)
        print(f"\nSetting date_issued to {days_before_due} day(s) before due_date")
        
        results = {
            "total_invoices": 0,
            "corrected_invoices": 0,
            "skipped_invoices": 0,
            "corrections": [],
            "errors": []
        }
        
        cursor = self.db.property_invoices.find({})
        
        async for invoice in cursor:
            results["total_invoices"] += 1
            invoice_id = str(invoice["_id"])
            
            date_issued = invoice.get("date_issued")
            due_date = invoice.get("due_date")
            
            # Skip if due_date is missing
            if not due_date:
                results["skipped_invoices"] += 1
                continue
            
            # Calculate correct date_issued
            correct_date_issued = due_date - timedelta(days=days_before_due)
            
            # Check if correction is needed
            needs_correction = False
            reason = None
            
            if not date_issued:
                needs_correction = True
                reason = "missing_date_issued"
            elif date_issued != correct_date_issued:
                days_diff = (due_date - date_issued).days
                if days_diff < 1 or days_diff > 5:
                    needs_correction = True
                    reason = f"date_issued_{days_diff}_days_before_due"
            
            if needs_correction:
                old_date_issued = date_issued
                
                correction = {
                    "invoice_id": invoice_id,
                    "old_date_issued": old_date_issued,
                    "new_date_issued": correct_date_issued,
                    "due_date": due_date,
                    "reason": reason
                }
                
                results["corrections"].append(correction)
                
                if not dry_run:
                    try:
                        # Update the invoice
                        await self.db.property_invoices.update_one(
                            {"_id": invoice["_id"]},
                            {
                                "$set": {
                                    "date_issued": correct_date_issued,
                                    "updated_at": datetime.now(timezone.utc)
                                }
                            }
                        )
                        results["corrected_invoices"] += 1
                        
                    except Exception as e:
                        results["errors"].append({
                            "invoice_id": invoice_id,
                            "error": str(e)
                        })
            else:
                results["skipped_invoices"] += 1
        
        return results
    
    def print_correction_results(self, results: Dict, dry_run: bool = True):
        """Print correction results"""
        
        print(f"\n📊 Correction Results:")
        print(f"   Total Invoices Processed: {results['total_invoices']:,}")
        
        if dry_run:
            print(f"   Would Correct: {len(results['corrections']):,}")
        else:
            print(f"   Corrected: {results['corrected_invoices']:,}")
        
        print(f"   Skipped (Already Correct): {results['skipped_invoices']:,}")
        
        if results['errors']:
            print(f"   Errors: {len(results['errors'])}")
        
        if results['corrections']:
            print(f"\n📋 Sample Corrections (first 10):")
            for i, correction in enumerate(results['corrections'][:10]):
                print(f"\n   {i+1}. Invoice: {correction['invoice_id'][:16]}...")
                print(f"      Reason: {correction['reason']}")
                if correction['old_date_issued']:
                    print(f"      Old Date Issued: {correction['old_date_issued'].strftime('%Y-%m-%d')}")
                else:
                    print(f"      Old Date Issued: None")
                print(f"      New Date Issued: {correction['new_date_issued'].strftime('%Y-%m-%d')}")
                print(f"      Due Date: {correction['due_date'].strftime('%Y-%m-%d')}")
        
        if results['errors']:
            print(f"\n❌ Errors:")
            for error in results['errors'][:5]:
                print(f"   - Invoice {error['invoice_id'][:16]}...: {error['error']}")
    
    async def correct_specific_invoice(
        self,
        invoice_id: str,
        days_before_due: int = 1,
        dry_run: bool = True
    ) -> Dict:
        """
        Correct a specific invoice's date_issued
        
        Args:
            invoice_id: Invoice ID to correct
            days_before_due: Days before due_date
            dry_run: If True, only simulate
        
        Returns:
            Correction details
        """
        
        invoice = await self.db.property_invoices.find_one({"_id": invoice_id})
        
        if not invoice:
            return {"error": f"Invoice {invoice_id} not found"}
        
        due_date = invoice.get("due_date")
        if not due_date:
            return {"error": "Invoice has no due_date"}
        
        correct_date_issued = due_date - timedelta(days=days_before_due)
        old_date_issued = invoice.get("date_issued")
        
        result = {
            "invoice_id": invoice_id,
            "old_date_issued": old_date_issued,
            "new_date_issued": correct_date_issued,
            "due_date": due_date,
            "dry_run": dry_run
        }
        
        if not dry_run:
            await self.db.property_invoices.update_one(
                {"_id": invoice_id},
                {
                    "$set": {
                        "date_issued": correct_date_issued,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            result["updated"] = True
        
        return result
    
    async def correct_by_property(
        self,
        property_id: str,
        days_before_due: int = 1,
        dry_run: bool = True
    ) -> Dict:
        """
        Correct all invoices for a specific property
        
        Args:
            property_id: Property ID
            days_before_due: Days before due_date
            dry_run: If True, only simulate
        
        Returns:
            Correction results
        """
        
        print(f"\n{'='*80}")
        print(f" Correcting invoices for property: {property_id}")
        print(f"{'='*80}")
        
        results = {
            "property_id": property_id,
            "total_invoices": 0,
            "corrected": 0,
            "skipped": 0,
            "corrections": []
        }
        
        cursor = self.db.property_invoices.find({"property_id": property_id})
        
        async for invoice in cursor:
            results["total_invoices"] += 1
            invoice_id = str(invoice["_id"])
            
            due_date = invoice.get("due_date")
            if not due_date:
                results["skipped"] += 1
                continue
            
            correct_date_issued = due_date - timedelta(days=days_before_due)
            old_date_issued = invoice.get("date_issued")
            
            if old_date_issued != correct_date_issued:
                correction = {
                    "invoice_id": invoice_id,
                    "old_date_issued": old_date_issued,
                    "new_date_issued": correct_date_issued,
                    "due_date": due_date
                }
                
                results["corrections"].append(correction)
                
                if not dry_run:
                    await self.db.property_invoices.update_one(
                        {"_id": invoice["_id"]},
                        {
                            "$set": {
                                "date_issued": correct_date_issued,
                                "updated_at": datetime.now(timezone.utc)
                            }
                        }
                    )
                    results["corrected"] += 1
            else:
                results["skipped"] += 1
        
        return results
    
    def close(self):
        """Close database connection"""
        self.client.close()


# Main execution functions

async def analyze_only():
    """Run analysis without making changes"""
    
    corrector = InvoiceDateCorrector(
        mongo_uri="mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin",
        database_name="fq_db"
    )
    
    try:
        # Analyze
        results = await corrector.analyze_invoices()
        corrector.print_analysis(results)
        
    finally:
        corrector.close()


async def dry_run_corrections(days_before_due: int = 1):
    """Simulate corrections without making changes"""
    
    corrector = InvoiceDateCorrector(
        mongo_uri="mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin",
        database_name="fq_db"
    )
    
    try:
        # First analyze
        print("Step 1: Analyzing invoices...")
        analysis = await corrector.analyze_invoices()
        corrector.print_analysis(analysis)
        
        # Then simulate corrections
        print("\nStep 2: Simulating corrections...")
        results = await corrector.correct_invoice_dates(
            dry_run=True,
            days_before_due=days_before_due
        )
        corrector.print_correction_results(results, dry_run=True)
        
    finally:
        corrector.close()


async def apply_corrections(days_before_due: int = 1):
    """Apply corrections to database"""
    
    corrector = InvoiceDateCorrector(
        mongo_uri="mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin",
        database_name="fq_db"
    )
    
    try:
        # First analyze
        print("Step 1: Analyzing invoices...")
        analysis = await corrector.analyze_invoices()
        corrector.print_analysis(analysis)
        
        # Ask for confirmation
        print("\n" + "="*80)
        print(" ⚠️  WARNING: This will modify invoice dates in the database!")
        print("="*80)
        confirmation = input("\nType 'YES' to proceed with corrections: ")
        
        if confirmation != "YES":
            print("\n❌ Cancelled. No changes made.")
            return
        
        # Apply corrections
        print("\nStep 2: Applying corrections...")
        results = await corrector.correct_invoice_dates(
            dry_run=False,
            days_before_due=days_before_due
        )
        corrector.print_correction_results(results, dry_run=False)
        
        print("\n✅ Corrections applied successfully!")
        
    finally:
        corrector.close()


async def correct_specific_property(property_id: str, days_before_due: int = 1):
    """Correct invoices for a specific property"""
    
    corrector = InvoiceDateCorrector(
        mongo_uri="mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin",
        database_name="fq_db"
    )
    
    try:
        # Dry run first
        print("Step 1: Simulating corrections...")
        results = await corrector.correct_by_property(
            property_id=property_id,
            days_before_due=days_before_due,
            dry_run=True
        )
        
        print(f"\nWould correct {len(results['corrections'])} invoices")
        
        if results['corrections']:
            print("\nSample corrections:")
            for correction in results['corrections'][:5]:
                print(f"  - Invoice {correction['invoice_id'][:16]}...")
                print(f"    {correction['old_date_issued']} → {correction['new_date_issued']}")
        
        # Ask for confirmation
        confirmation = input("\nType 'YES' to apply corrections: ")
        
        if confirmation == "YES":
            print("\nStep 2: Applying corrections...")
            results = await corrector.correct_by_property(
                property_id=property_id,
                days_before_due=days_before_due,
                dry_run=False
            )
            print(f"\n✅ Corrected {results['corrected']} invoices")
        else:
            print("\n❌ Cancelled")
        
    finally:
        corrector.close()


# Usage examples
if __name__ == "__main__":
    import sys
    
    print("""
    Invoice Date Corrector
    =====================
    
    Choose an option:
    1. Analyze invoices (no changes)
    2. Dry run (simulate corrections)
    3. Apply corrections (modify database)
    4. Correct specific property
    
    """)
    
    choice = input("Enter choice (1-4): ").strip()
    
    if choice == "1":
        asyncio.run(analyze_only())
    
    elif choice == "2":
        days = input("Days before due date (1-5, default 1): ").strip()
        days = int(days) if days else 1
        asyncio.run(dry_run_corrections(days_before_due=days))
    
    elif choice == "3":
        days = input("Days before due date (1-5, default 1): ").strip()
        days = int(days) if days else 1
        asyncio.run(apply_corrections(days_before_due=days))
    
    elif choice == "4":
        property_id = input("Enter property ID: ").strip()
        days = input("Days before due date (1-5, default 1): ").strip()
        days = int(days) if days else 1
        asyncio.run(correct_specific_property(property_id, days_before_due=days))
    
    else:
        print("Invalid choice")