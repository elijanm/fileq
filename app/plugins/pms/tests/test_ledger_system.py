"""
Comprehensive Test Suite for Ledger and AsyncLeaseInvoiceManager

Tests various scenarios:
1. Basic invoice creation and ledger posting
2. Payment allocation (full, partial, overpayment)
3. Line item additions and removals
4. Sum vs Itemized consolidation methods
5. Utility additions
6. Edge cases and error handling
"""

import asyncio
import pytest
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from decimal import Decimal

from plugins.pms.accounting.ledger import Ledger, LEDGER_COLL, INVOICE_COLL
from plugins.pms.accounting.invoice_manager import AsyncLeaseInvoiceManager
from plugins.pms.models.ledger_entry import Invoice, InvoiceLineItem, InvoiceStatus
from plugins.pms.models.extra import UtilityUsageRecord


class TestSetup:
    """Test setup and teardown utilities"""
    
    @staticmethod
    async def setup_test_db():
        """Setup test database connection"""
        client= AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
        db = client["pms_test_db"]
        
        # Clean up existing test data
        await db[INVOICE_COLL].delete_many({})
        await db[LEDGER_COLL].delete_many({})
        await db.property_tenants.delete_many({})
        await db.properties.delete_many({})
        await db.property_leases.delete_many({})
        await db.units.delete_many({})
        await db.property_tickets.delete_many({})
        await db.property_notifications.delete_many({})
        await db.property_payments.delete_many({})
        
        return client, db
    
    @staticmethod
    async def create_test_property(db) -> str:
        """Create a test property"""
        property_id = str(ObjectId())
        await db.properties.insert_one({
            "_id": property_id,
            "name": "Test Property",
            "location": "Nairobi, Kenya",
            "owner_id": str(ObjectId()),
            "billing_cycle": {
                "due_day": 5,
                "billing_day": 1
            },
            "integrations": {
                "sms": {"enabled": False},
                "email": {"enabled": True},
                "payments": {
                    "paybillNo": {
                        "enabled": True,
                        "paybill_no": "123456",
                        "account": "{unit#}"
                    }
                }
            }
        })
        return property_id
    
    @staticmethod
    async def create_test_tenant(db, property_id: str) -> str:
        """Create a test tenant"""
        tenant_id = str(ObjectId())
        await db.property_tenants.insert_one({
            "_id": ObjectId(tenant_id),
            "property_id": property_id,
            "full_name": "John Doe",
            "email": "john@example.com",
            "phone": "+254712345678",
            "credit_balance": 0.0
        })
        return tenant_id
    
    @staticmethod
    async def create_test_unit(db, property_id: str) -> str:
        """Create a test unit"""
        unit_id = str(ObjectId())
        await db.units.insert_one({
            "_id": unit_id,
            "property_id": property_id,
            "unitNumber": "A101",
            "unitName": "Studio Apartment",
            "rentAmount": 15000.0
        })
        return unit_id
    
    @staticmethod
    async def create_test_lease(db, property_id: str, tenant_id: str, unit_id: str) -> str:
        """Create a test lease"""
        lease_id = str(ObjectId())
        i=await db.property_leases.insert_one({
            "_id": ObjectId(lease_id),
            "property_id": property_id,
            "tenant_id": ObjectId(tenant_id),
            "units_id": [unit_id],
            "status": "active",
            "lease_terms": {
                "rent_amount": 15000.0,
                "start_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "end_date": datetime(2024, 12, 31, tzinfo=timezone.utc)
            },
            "tenant_details": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+254712345678"
            },
            "utilities": [
                {
                    "name": "Water",
                    "billingBasis": "metered",
                    "unitOfMeasure": "m³",
                    "rate": 50.0
                },
                {
                    "name": "Garbage Collection",
                    "billingBasis": "monthly",
                    "rate": 500.0
                }
            ]
        })
        print(f"{i} inserted")
        return lease_id


class TestLedgerBasics:
    """Test basic ledger operations"""
    
    @staticmethod
    async def test_invoice_posting():
        """Test posting invoice to ledger"""
        print("\n" + "="*80)
        print("TEST: Invoice Posting to Ledger")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        ledger = Ledger(db)
        
        # Create test invoice
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=str(ObjectId()),
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=15000.0,
                    category="rent"
                ),
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Garbage Collection",
                    amount=500.0,
                    category="utility"
                )
            ],
            total_amount=15500.0,
            total_paid=0.0,
            balance_amount=15500.0,
            status=InvoiceStatus.READY,
            meta={}
        )
        
        # Post to ledger
        entries = await ledger.post_invoice_to_ledger(invoice)
        
        # Verify entries
        print(f"\n✅ Posted {len(entries)} ledger entries")
        for entry in entries:
            print(f"   - {entry.account}: Debit={entry.debit}, Credit={entry.credit}")
        
        # Verify balance
        total_debits = sum(e.debit for e in entries)
        total_credits = sum(e.credit for e in entries)
        print(f"\n📊 Balance Check:")
        print(f"   Total Debits: {total_debits}")
        print(f"   Total Credits: {total_credits}")
        print(f"   Balanced: {'✅ YES' if total_debits == total_credits else '❌ NO'}")
        
        # Verify invoice in DB
        saved_invoice = await db[INVOICE_COLL].find_one({"_id": invoice.id})
        print(f"\n💾 Invoice saved: {'✅ YES' if saved_invoice else '❌ NO'}")
        
        client.close()
        return entries
    
    @staticmethod
    async def test_full_payment():
        """Test full payment processing"""
        print("\n" + "="*80)
        print("TEST: Full Payment Processing")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        ledger = Ledger(db)
        
        # Create and post invoice
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=str(ObjectId()),
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=10000.0,
                    category="rent"
                )
            ],
            total_amount=10000.0,
            total_paid=0.0,
            balance_amount=10000.0,
            status=InvoiceStatus.READY,
            meta={}
        )
        
        await ledger.post_invoice_to_ledger(invoice)
        print(f"\n📄 Invoice Total: KES {invoice.total_amount:,.2f}")
        
        # Process full payment
        payment_entries = await ledger.post_payment_to_ledger(
            invoice=invoice,
            amount=10000.0,
            payment_date=datetime.now(timezone.utc)
        )
        
        print(f"\n💰 Payment Processed: KES 10,000.00")
        print(f"✅ Created {len(payment_entries)} ledger entries")
        
        # Check invoice status
        updated_invoice = await db[INVOICE_COLL].find_one({"_id": invoice.id})
        print(f"\n📊 Invoice Status: {updated_invoice['status']}")
        print(f"   Total Paid: KES {updated_invoice['total_paid']:,.2f}")
        print(f"   Balance: KES {updated_invoice['balance_amount']:,.2f}")
        print(f"   Status should be 'paid': {'✅ YES' if updated_invoice['status'] == 'paid' else '❌ NO'}")
        
        client.close()
        return updated_invoice
    
    @staticmethod
    async def test_partial_payment():
        """Test partial payment processing"""
        print("\n" + "="*80)
        print("TEST: Partial Payment Processing")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        ledger = Ledger(db)
        
        # Create invoice
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=str(ObjectId()),
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=15000.0,
                    category="rent"
                ),
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Utility",
                    amount=2000.0,
                    category="utility"
                )
            ],
            total_amount=17000.0,
            total_paid=0.0,
            balance_amount=17000.0,
            status=InvoiceStatus.READY,
            meta={}
        )
        
        await ledger.post_invoice_to_ledger(invoice)
        print(f"\n📄 Invoice Total: KES {invoice.total_amount:,.2f}")
        print(f"   Line Items:")
        for item in invoice.line_items:
            print(f"   - {item.description}: KES {item.amount:,.2f}")
        
        # Process partial payment
        payment_amount = 10000.0
        payment_entries = await ledger.post_payment_to_ledger(
            invoice=invoice,
            amount=payment_amount,
            payment_date=datetime.now(timezone.utc)
        )
        
        print(f"\n💰 Partial Payment: KES {payment_amount:,.2f}")
        print(f"✅ Created {len(payment_entries)} ledger entries")
        
        # Check invoice status
        updated_invoice = await db[INVOICE_COLL].find_one({"_id": invoice.id})
        print(f"\n📊 Invoice Status: {updated_invoice['status']}")
        print(f"   Total Paid: KES {updated_invoice['total_paid']:,.2f}")
        print(f"   Balance Remaining: KES {updated_invoice['balance_amount']:,.2f}")
        print(f"   Status should be 'partial': {'✅ YES' if updated_invoice['status'] == 'partial' else '❌ NO'}")
        
        client.close()
        return updated_invoice
    
    @staticmethod
    async def test_overpayment():
        """Test overpayment creates tenant credit"""
        print("\n" + "="*80)
        print("TEST: Overpayment Creates Tenant Credit")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        ledger = Ledger(db)
        
        tenant_id = str(ObjectId())
        
        # Create invoice
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=tenant_id,
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=10000.0,
                    category="rent"
                )
            ],
            total_amount=10000.0,
            total_paid=0.0,
            balance_amount=10000.0,
            status=InvoiceStatus.READY,
            meta={}
        )
        
        await ledger.post_invoice_to_ledger(invoice)
        print(f"\n📄 Invoice Total: KES {invoice.total_amount:,.2f}")
        
        # Process overpayment
        payment_amount = 12000.0
        payment_entries = await ledger.post_payment_to_ledger(
            invoice=invoice,
            amount=payment_amount,
            payment_date=datetime.now(timezone.utc)
        )
        
        print(f"\n💰 Payment Amount: KES {payment_amount:,.2f}")
        print(f"   Overpayment: KES {payment_amount - invoice.total_amount:,.2f}")
        
        # Check invoice status
        updated_invoice = await db[INVOICE_COLL].find_one({"_id": invoice.id})
        print(f"\n📊 Invoice Status: {updated_invoice['status']}")
        print(f"   Total Paid: KES {updated_invoice['total_paid']:,.2f}")
        print(f"   Overpaid Amount: KES {updated_invoice.get('overpaid_amount', 0):,.2f}")
        
        # Check tenant credit in ledger
        tenant_credit = await ledger.get_tenant_credit_balance(tenant_id)
        print(f"\n💳 Tenant Credit Balance: KES {tenant_credit:,.2f}")
        print(f"   Credit should be 2000: {'✅ YES' if tenant_credit == 2000.0 else '❌ NO'}")
        
        client.close()
        return tenant_credit


class TestLineItemAdjustments:
    """Test line item additions and removals"""
    
    @staticmethod
    async def test_add_line_item():
        """Test adding a line item to existing invoice"""
        print("\n" + "="*80)
        print("TEST: Add Line Item to Invoice")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        ledger = Ledger(db)
        
        # Create initial invoice
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=str(ObjectId()),
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=10000.0,
                    category="rent"
                )
            ],
            total_amount=10000.0,
            total_paid=0.0,
            balance_amount=10000.0,
            status=InvoiceStatus.READY,
            meta={"audit_trail": []}
        )
        
        await ledger.post_invoice_to_ledger(invoice)
        print(f"\n📄 Initial Invoice Total: KES {invoice.total_amount:,.2f}")
        print(f"   Line Items: {len(invoice.line_items)}")
        
        # Add new line item
        new_line_item = InvoiceLineItem(
            id=str(ObjectId()),
            description="Late Fee",
            amount=500.0,
            category="misc"
        )
        
        entries, updated_invoice = await ledger.add_line_item_to_invoice(
            invoice_id=invoice.id,
            line_item=new_line_item,
            reason="Applied late fee per lease terms"
        )
        
        print(f"\n➕ Added Line Item: {new_line_item.description} - KES {new_line_item.amount:,.2f}")
        print(f"✅ Created {len(entries)} ledger entries")
        
        # Verify updated invoice
        invoice_doc = await db[INVOICE_COLL].find_one({"_id": invoice.id})
        print(f"\n📊 Updated Invoice:")
        print(f"   Total Amount: KES {invoice_doc['total_amount']:,.2f}")
        print(f"   Line Items: {len(invoice_doc['line_items'])}")
        print(f"   Balance: KES {invoice_doc['balance_amount']:,.2f}")
        
        # Verify ledger balance
        ledger_entries = await db[LEDGER_COLL].find({"invoice_id": invoice.id}).to_list(length=None)
        total_debits = sum(e.get("debit", 0) for e in ledger_entries)
        total_credits = sum(e.get("credit", 0) for e in ledger_entries)
        print(f"\n📊 Ledger Balance:")
        print(f"   Total Debits: {total_debits:,.2f}")
        print(f"   Total Credits: {total_credits:,.2f}")
        print(f"   Balanced: {'✅ YES' if total_debits == total_credits else '❌ NO'}")
        
        client.close()
        return invoice_doc
    
    @staticmethod
    async def test_remove_line_item():
        """Test removing a line item from invoice"""
        print("\n" + "="*80)
        print("TEST: Remove Line Item from Invoice")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        ledger = Ledger(db)
        
        # Create invoice with multiple line items
        late_fee_id = str(ObjectId())
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=str(ObjectId()),
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=10000.0,
                    category="rent"
                ),
                InvoiceLineItem(
                    id=late_fee_id,
                    description="Late Fee",
                    amount=500.0,
                    category="misc"
                )
            ],
            total_amount=10500.0,
            total_paid=0.0,
            balance_amount=10500.0,
            status=InvoiceStatus.READY,
            meta={"audit_trail": []}
        )
        
        await ledger.post_invoice_to_ledger(invoice)
        print(f"\n📄 Initial Invoice Total: KES {invoice.total_amount:,.2f}")
        print(f"   Line Items: {len(invoice.line_items)}")
        for item in invoice.line_items:
            print(f"   - {item.description}: KES {item.amount:,.2f}")
        
        # Remove late fee
        reversal_entries, updated_invoice = await ledger.remove_line_item_from_invoice(
            invoice_id=invoice.id,
            line_item_id=late_fee_id,
            reason="Waived as courtesy"
        )
        
        print(f"\n➖ Removed Line Item: Late Fee - KES 500.00")
        print(f"✅ Created {len(reversal_entries)} reversal entries")
        
        # Verify updated invoice
        invoice_doc = await db[INVOICE_COLL].find_one({"_id": ObjectId(invoice.id)})
        print(f"\n📊 Updated Invoice:")
        print(f"   Total Amount: KES {invoice_doc['total_amount']:,.2f}")
        print(f"   Line Items: {len(invoice_doc['line_items'])}")
        print(f"   Removed late fee: {'✅ YES' if len(invoice_doc['line_items']) == 1 else '❌ NO'}")
        
        # Verify ledger balance (including reversals)
        ledger_entries = await db[LEDGER_COLL].find({"invoice_id": invoice.id}).to_list(length=None)
        total_debits = sum(e.get("debit", 0) for e in ledger_entries)
        total_credits = sum(e.get("credit", 0) for e in ledger_entries)
        print(f"\n📊 Ledger Balance (with reversals):")
        print(f"   Total Debits: {total_debits:,.2f}")
        print(f"   Total Credits: {total_credits:,.2f}")
        print(f"   Balanced: {'✅ YES' if total_debits == total_credits else '❌ NO'}")
        
        client.close()
        return invoice_doc
    
    @staticmethod
    async def test_remove_balance_forward_protection():
        """Test that balance forward items cannot be removed"""
        print("\n" + "="*80)
        print("TEST: Balance Forward Item Removal Protection")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        ledger = Ledger(db)
        
        # Create invoice with balance forward item
        balance_forward_id = str(ObjectId())
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=str(ObjectId()),
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=balance_forward_id,
                    description="Balance Brought Forward",
                    amount=5000.0,
                    category="balance_brought_forward"
                ),
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=10000.0,
                    category="rent"
                )
            ],
            total_amount=15000.0,
            total_paid=0.0,
            balance_amount=15000.0,
            status=InvoiceStatus.READY,
            meta={"audit_trail": []}
        )
        
        await ledger.post_invoice_to_ledger(invoice)
        print(f"\n📄 Invoice with Balance Forward created")
        
        # Try to remove balance forward item (should fail)
        try:
            await ledger.remove_line_item_from_invoice(
                invoice_id=invoice.id,
                line_item_id=balance_forward_id,
                reason="Test removal"
            )
            print(f"\n❌ ERROR: Should have raised ValueError!")
            success = False
        except ValueError as e:
            print(f"\n✅ Protection Working: {str(e)}")
            success = True
        
        client.close()
        return success


class TestConsolidationMethods:
    """Test SUM vs ITEMIZED consolidation methods"""
    
    @staticmethod
    async def test_sum_method_with_payment():
        """Test SUM consolidation method with payment allocation"""
        print("\n" + "="*80)
        print("TEST: SUM Method - Previous Balance Consolidation")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        manager = AsyncLeaseInvoiceManager(client, "pms_test_db")
        
        # Setup test data
        property_id = await TestSetup.create_test_property(db)
        tenant_id = await TestSetup.create_test_tenant(db, property_id)
        unit_id = await TestSetup.create_test_unit(db, property_id)
        lease_id = await TestSetup.create_test_lease(db, str(property_id), str(tenant_id), unit_id)
        total_leases = await db.property_leases.count_documents({})
       
        
        # Create old unpaid invoice (Jan 2024)
        old_invoice_id = str(ObjectId())
        await db.property_invoices.insert_one({
            "_id": ObjectId(old_invoice_id),
            "tenant_id": ObjectId(tenant_id),
            "property_id": property_id,
            "date_issued": datetime(2024, 1, 1, tzinfo=timezone.utc),
            "due_date": datetime(2024, 1, 5, tzinfo=timezone.utc),
            "total_amount": 15000.0,
            "total_paid": 10000.0,
            "balance_amount": 5000.0,
            "status": "partial",
            "meta": {"billing_period": "2024-01","lease_id":lease_id},
            "line_items": [
                    {
                        "id":str(ObjectId()),
                        "description":"Monthly Rent",
                        "amount":15000.0,
                        "category":"rent"
                    }
                    
                
                
            ],
            "balance_forwarded": False
        })
        
        print(f"\n📄 Old Invoice (Jan 2024):")
        print(f"   Total: KES 15,000.00")
        print(f"   Paid: KES 10,000.00")
        print(f"   Balance: KES 5,000.00")
        
        # Process Feb 2024 invoice with SUM method
        results = await manager.process_all_leases(
            billing_month="2024-02",
            force=True,
            balance_method="sum"
        )
        
        
        print(f"\n✅ Feb Invoice Generated")
        print(f"   Invoices Created: {len(results['invoices_created'])}")
        print(f"   Invoices Consolidated: {len(results['invoices_consolidated'])}")
        
        # Check new invoice
        new_invoice = await db.property_invoices.find_one({
            "_id": ObjectId(results['invoices_created'][0])
        })
        
        print(f"\n📊 New Invoice (Feb 2024):")
        print(f"   Total: KES {new_invoice['total_amount']:,.2f}")
        print(f"   Line Items: {len(new_invoice['line_items'])}")
        for item in new_invoice['line_items']:
            print(f"   - {item['description']}: KES {item['amount']:,.2f}")
        
        # Check if balance forward is present as single line
        balance_items = [
            item for item in new_invoice['line_items'] 
            if item['category'] == 'balance_brought_forward'
        ]
        print(f"\n✅ Balance Forward Items: {len(balance_items)}")
        print(f"   Should be 1 (SUM method): {'✅ YES' if len(balance_items) == 1 else '❌ NO'}")
        
        client.close()
        return new_invoice
    
    @staticmethod
    async def test_itemized_method_with_payment():
        """Test ITEMIZED consolidation method"""
        print("\n" + "="*80)
        print("TEST: ITEMIZED Method - Previous Balance Consolidation")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        manager = AsyncLeaseInvoiceManager(client, "pms_test_db")
        
        # Setup test data
        property_id = await TestSetup.create_test_property(db)
        tenant_id = await TestSetup.create_test_tenant(db, property_id)
        unit_id = await TestSetup.create_test_unit(db, property_id)
        lease_id = await TestSetup.create_test_lease(db, property_id, str(tenant_id), unit_id)
        
        print(f"✓ Created property: {property_id}")
        print(f"✓ Created tenant: {tenant_id}")
        print(f"✓ Created unit: {unit_id}")
        print(f"✓ Created lease: {lease_id}")
        
        # VERIFY LEASE IS ACTIVE
        lease_check = await db.property_leases.find_one({"_id": ObjectId(lease_id)})
        if lease_check:
            print(f"✓ Lease status: {lease_check['status']}")
            # Ensure lease is active
            if lease_check['status'] not in ['active', 'signed']:
                await db.property_leases.update_one(
                    {"_id": ObjectId(lease_id)},
                    {"$set": {"status": "active"}}
                )
                print(f"✓ Updated lease status to: active")
        else:
            print(f"❌ ERROR: Lease not found!")
            client.close()
            return None
        
     
        # Create multiple old unpaid invoices
        old_invoices = [
            {
                "_id": ObjectId(),
                "tenant_id": ObjectId(tenant_id),
                "property_id": property_id,
                "date_issued": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "due_date": datetime(2024, 1, 5, tzinfo=timezone.utc),
                "total_amount": 15000.0,
                "total_paid": 0.0,
                "balance_amount": 15000.0,
                "status": "overdue",
                "meta": {"billing_period": "2024-01"},
                "line_items": [],
                "balance_forwarded": False
            },
            {
                "_id": ObjectId(),
                "tenant_id": ObjectId(tenant_id),
                "property_id": property_id,
                "date_issued": datetime(2024, 2, 1, tzinfo=timezone.utc),
                "due_date": datetime(2024, 2, 5, tzinfo=timezone.utc),
                "total_amount": 16000.0,
                "total_paid": 6000.0,
                "balance_amount": 10000.0,
                "status": "partial",
                "meta": {"billing_period": "2024-02"},
                "line_items": [],
                "balance_forwarded": False
            }
        ]
        
        await db.property_invoices.insert_many(old_invoices)
        
        print(f"\n📄 Old Invoices:")
        print(f"   Jan 2024: Balance KES 15,000.00")
        print(f"   Feb 2024: Balance KES 10,000.00")
        print(f"   Total Outstanding: KES 25,000.00")
        
        # Process Mar 2024 invoice with ITEMIZED method
        results = await manager.process_all_leases(
            billing_month="2024-03",
            force=True,
            balance_method="itemized"
        )
       
        # Check new invoice
        new_invoice = await db.property_invoices.find_one({
            "_id": ObjectId(results['invoices_created'][0])
        })
        
     
        print(f"\n📊 New Invoice (Mar 2024):")
        print(f"   Total: KES {new_invoice['total_amount']:,.2f}")
        print(f"   Line Items: {len(new_invoice['line_items'])}")
        
        # Check itemized balance forward items
        balance_items = [
            item for item in new_invoice['line_items'] 
            if item['category'] == 'balance_brought_forward'
        ]
        print(f"\n✅ Balance Forward Items: {len(balance_items)}")
        print(f"   Should be 2 (ITEMIZED method): {'✅ YES' if len(balance_items) == 2 else '❌ NO'}")
        
        for item in balance_items:
            print(f"   - {item['description']}: KES {item['amount']:,.2f}")
        
        client.close()
        return new_invoice


class TestComplexScenarios:
    """Test complex real-world scenarios"""
    
    @staticmethod
    async def test_payment_with_consolidation():
        """Test payment allocation to consolidated invoices"""
        print("\n" + "="*80)
        print("TEST: Payment Allocation with Consolidated Invoices")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        manager = AsyncLeaseInvoiceManager(client, "pms_test_db")
        
        # Setup
        property_id = await TestSetup.create_test_property(db)
        tenant_id = await TestSetup.create_test_tenant(db, property_id)
        
        
        # Create old invoices
        old_invoice_ids = []
        for month in range(1, 4):  # Jan, Feb, Mar
            inv_id = str(ObjectId())
            await db.property_invoices.insert_one({
                "_id": ObjectId(inv_id),
                "tenant_id": ObjectId(tenant_id),
                "property_id": property_id,
                "date_issued": datetime(2024, month, 1, tzinfo=timezone.utc),
                "total_amount": 15500.0,
                "total_paid": 0.0,
                "balance_amount": 15500.0,
                "status": "overdue",
                "meta": {"billing_period": f"2024-{month:02d}"},
                "line_items": [{
                        "id":str(ObjectId()),
                        "description":"Monthly Rent",
                        "amount":15000.0,
                        "category":"rent"
                    },
                    {
                        "id":str(ObjectId()),
                        "description":"Garbage Collection",
                        "amount":500.0,
                        "category":"utility"
                    }
                    
                ],
                "balance_forwarded": False
            })
            old_invoice_ids.append(inv_id)
        
        print(f"\n📄 Created 3 Unpaid Invoices:")
        print(f"   Jan-Mar 2024: KES 15,500 each")
        print(f"   Total Outstanding: KES 46,500.00")
        
        # Make payment for oldest invoice first
        payment_result = await manager.process_payment(
            tenant_id=ObjectId(tenant_id),
            amount=20000.0,
            payment_method="mpesa",
            reference="TEST001"
        )
        
        print(f"\n💰 Payment Processed: KES 20,000.00")
        print(f"   Allocations: {len(payment_result['allocations'])}")
        
        for allocation in payment_result['allocations']:
            print(f"   - {allocation['billing_period']}: KES {allocation['amount']:,.2f} ({allocation['invoice_status']})")
        
        # Verify oldest invoice is paid
        jan_invoice = await db.property_invoices.find_one({"_id": ObjectId(old_invoice_ids[0])})
        feb_invoice = await db.property_invoices.find_one({"_id": ObjectId(old_invoice_ids[1])})
        
        print(f"\n📊 Invoice Status After Payment:")
        print(f"   Jan: {jan_invoice['status']} (Balance: KES {jan_invoice['balance_amount']:,.2f})")
        print(f"   Feb: {feb_invoice['status']} (Balance: KES {feb_invoice['balance_amount']:,.2f})")
        
        client.close()
        return payment_result
    
    @staticmethod
    async def test_utility_addition_workflow():
        """Test complete utility reading workflow"""
        print("\n" + "="*80)
        print("TEST: Utility Addition Workflow")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        manager = AsyncLeaseInvoiceManager(client, "pms_test_db")
        
        # Setup
        property_id = await TestSetup.create_test_property(db)
        tenant_id = await TestSetup.create_test_tenant(db, property_id)
        unit_id = await TestSetup.create_test_unit(db, property_id)
        lease_id = await TestSetup.create_test_lease(db, property_id, str(tenant_id), unit_id)
        
        # Generate invoice with pending utilities
        results = await manager.process_all_leases(
            billing_month="2024-04",
            force=True,
            balance_method="sum"
        )
        
        invoice = await db.property_invoices.find_one({
            "_id": ObjectId(results['invoices_created'][0])
        })
        
        print(f"\n📄 Invoice Created:")
        print(f"   Status: {invoice['status']}")
        print(f"   Total: KES {invoice['total_amount']:,.2f}")
        print(f"   Pending Utilities: {invoice['meta'].get('pending_utilities', 0)}")
        
        # Get ticket
        ticket = await db.property_tickets.find_one({
            "metadata.billing_month": "2024-04"
        })
        
        if ticket:
            print(f"\n🎫 Ticket Created:")
            print(f"   Tasks: {len(ticket['tasks'])}")
            
            # Process utility reading
            task_id = ticket['tasks'][0]['id']
            reading_result = await manager.process_utility_reading(
                task_id=task_id,
                current_reading=120.5
            )
            
            print(f"\n📏 Utility Reading Processed:")
            print(f"   Usage: {reading_result['usage_record']['usage']} {reading_result['usage_record']['unit_of_measure']}")
            print(f"   Amount: KES {reading_result['usage_record']['amount']:,.2f}")
            
            # Check updated invoice
            updated_invoice = await db.property_invoices.find_one({"_id": invoice['_id']})
            print(f"\n📊 Updated Invoice:")
            print(f"   Status: {updated_invoice['status']}")
            print(f"   Total: KES {updated_invoice['total_amount']:,.2f}")
            print(f"   Line Items: {len(updated_invoice['line_items'])}")
            
            # Verify utility line item added
            utility_items = [
                item for item in updated_invoice['line_items']
                if item['category'] == 'utility' and 'metered' in item.get('meta', {}).get('utility_type', '')
            ]
            print(f"   Metered Utilities Added: {len(utility_items)}")
            
        client.close()
        return invoice
    
    @staticmethod
    async def test_add_remove_line_item_workflow():
        """Test adding and removing line items in sequence"""
        print("\n" + "="*80)
        print("TEST: Add/Remove Line Item Workflow")
        print("="*80)
        
        client, db = await TestSetup.setup_test_db()
        manager = AsyncLeaseInvoiceManager(client, "pms_test_db")
        ledger = manager.ledger
        
        # Create base invoice
        invoice = Invoice(
            id=str(ObjectId()),
            property_id=str(ObjectId()),
            tenant_id=str(ObjectId()),
            date_issued=datetime.now(timezone.utc),
            due_date=datetime.now(timezone.utc),
            units_id=[str(ObjectId())],
            line_items=[
                InvoiceLineItem(
                    id=str(ObjectId()),
                    description="Monthly Rent",
                    amount=15000.0,
                    category="rent"
                )
            ],
            total_amount=15000.0,
            total_paid=0.0,
            balance_amount=15000.0,
            status=InvoiceStatus.READY,
            meta={"audit_trail": []}
        )
        
        await ledger.post_invoice_to_ledger(invoice)
        print(f"\n📄 Initial Invoice: KES {invoice.total_amount:,.2f}")
        
        # Add late fee
        late_fee_id = str(ObjectId())
        add_result = await manager.add_line_item_to_invoice(
            invoice_id=invoice.id,
            line_item=InvoiceLineItem(
                id=late_fee_id,
                description="Late Fee",
                amount=500.0,
                category="misc"
            ),
            reason="Late payment"
        )
        
        print(f"\n➕ Added Late Fee: KES 500.00")
        invoice_v2 = await db.property_invoices.find_one({"_id": invoice.id})
        print(f"   New Total: KES {invoice_v2['total_amount']:,.2f}")
        
        # Add parking fee
        parking_fee_id = str(ObjectId())
        await manager.add_line_item_to_invoice(
            invoice_id=invoice.id,
            line_item=InvoiceLineItem(
                id=parking_fee_id,
                description="Parking Fee",
                amount=1000.0,
                category="misc"
            ),
            reason="Monthly parking"
        )
        
        print(f"\n➕ Added Parking Fee: KES 1,000.00")
        invoice_v3 = await db.property_invoices.find_one({"_id": invoice.id})
        print(f"   New Total: KES {invoice_v3['total_amount']:,.2f}")
        print(f"   Line Items: {len(invoice_v3['line_items'])}")
        
        # Remove late fee (waived)
        await manager.remove_line_item_from_invoice(
            invoice_id=invoice.id,
            line_item_id=late_fee_id,
            reason="Waived as courtesy"
        )
        
        print(f"\n➖ Removed Late Fee")
        final_invoice = await db.property_invoices.find_one({"_id": invoice.id})
        print(f"   Final Total: KES {final_invoice['total_amount']:,.2f}")
        print(f"   Line Items: {len(final_invoice['line_items'])}")
        
        # Verify audit trail
        print(f"\n📋 Audit Trail: {len(final_invoice['meta']['audit_trail'])} entries")
        for entry in final_invoice['meta']['audit_trail']:
            print(f"   - {entry['action']}: {entry.get('reason', 'N/A')}")
        
        # Verify ledger balance
        ledger_entries = await db[LEDGER_COLL].find({"invoice_id": invoice.id}).to_list(length=None)
        total_debits = sum(e.get("debit", 0) for e in ledger_entries)
        total_credits = sum(e.get("credit", 0) for e in ledger_entries)
        print(f"\n📊 Final Ledger Balance:")
        print(f"   Debits: KES {total_debits:,.2f}")
        print(f"   Credits: KES {total_credits:,.2f}")
        print(f"   Balanced: {'✅ YES' if total_debits == total_credits else '❌ NO'}")
        
        client.close()
        return final_invoice


# Test Runner
async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*80)
    print("RUNNING COMPREHENSIVE TEST SUITE")
    print("="*80)
    
    test_results = {}
    
    # Basic Ledger Tests
    print("\n\n### BASIC LEDGER TESTS ###")
    try:
        await TestLedgerBasics.test_invoice_posting()
        test_results["invoice_posting"] = "✅ PASS"
    except Exception as e:
        test_results["invoice_posting"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestLedgerBasics.test_full_payment()
        test_results["full_payment"] = "✅ PASS"
    except Exception as e:
        test_results["full_payment"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestLedgerBasics.test_partial_payment()
        test_results["partial_payment"] = "✅ PASS"
    except Exception as e:
        test_results["partial_payment"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestLedgerBasics.test_overpayment()
        test_results["overpayment"] = "✅ PASS"
    except Exception as e:
        test_results["overpayment"] = f"❌ FAIL: {str(e)}"
    
    # Line Item Tests
    print("\n\n### LINE ITEM ADJUSTMENT TESTS ###")
    try:
        await TestLineItemAdjustments.test_add_line_item()
        test_results["add_line_item"] = "✅ PASS"
    except Exception as e:
        test_results["add_line_item"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestLineItemAdjustments.test_remove_line_item()
        test_results["remove_line_item"] = "✅ PASS"
    except Exception as e:
        test_results["remove_line_item"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestLineItemAdjustments.test_remove_balance_forward_protection()
        test_results["balance_forward_protection"] = "✅ PASS"
    except Exception as e:
        test_results["balance_forward_protection"] = f"❌ FAIL: {str(e)}"
    
    # Consolidation Tests
    print("\n\n### CONSOLIDATION METHOD TESTS ###")
    try:
        await TestConsolidationMethods.test_sum_method_with_payment()
        test_results["sum_method"] = "✅ PASS"
    except Exception as e:
        test_results["sum_method"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestConsolidationMethods.test_itemized_method_with_payment()
        test_results["itemized_method"] = "✅ PASS"
    except Exception as e:
        test_results["itemized_method"] = f"❌ FAIL: {str(e)}"
    
    # Complex Scenarios
    print("\n\n### COMPLEX SCENARIO TESTS ###")
    try:
        await TestComplexScenarios.test_payment_with_consolidation()
        test_results["payment_consolidation"] = "✅ PASS"
    except Exception as e:
        test_results["payment_consolidation"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestComplexScenarios.test_utility_addition_workflow()
        test_results["utility_workflow"] = "✅ PASS"
    except Exception as e:
        test_results["utility_workflow"] = f"❌ FAIL: {str(e)}"
    
    try:
        await TestComplexScenarios.test_add_remove_line_item_workflow()
        test_results["add_remove_workflow"] = "✅ PASS"
    except Exception as e:
        test_results["add_remove_workflow"] = f"❌ FAIL: {str(e)}"
    
    # Summary
    print("\n\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, result in test_results.items():
        print(f"{test_name:.<40} {result}")
    
    passed = sum(1 for r in test_results.values() if r.startswith("✅"))
    total = len(test_results)
    print(f"\n{'TOTAL':.>40} {passed}/{total} PASSED")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(run_all_tests())