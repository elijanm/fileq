# Testing Guide for Ledger and AsyncLeaseInvoiceManager

## 📋 Overview

This test suite provides comprehensive testing for:

- **Ledger System**: Double-entry accounting with invoice posting and payments
- **AsyncLeaseInvoiceManager**: Invoice generation, consolidation, and line item adjustments
- **Integration**: Full workflow testing with real-world scenarios

## 🚀 Quick Start

### Prerequisites

```bash
# Install required packages
pip install motor pymongo pytest pytest-asyncio

# Ensure MongoDB is running
mongod --dbpath /path/to/data
```

### Run All Tests

```bash
python test_ledger_system.py
```

### Run Individual Test Categories

```python
# In Python shell or script
import asyncio
from test_ledger_system import *

# Run specific test category
asyncio.run(TestLedgerBasics.test_full_payment())
asyncio.run(TestLineItemAdjustments.test_add_line_item())
asyncio.run(TestComplexScenarios.test_payment_with_consolidation())
```

## 🧪 Test Categories

### 1. Basic Ledger Tests (`TestLedgerBasics`)

Tests fundamental ledger operations:

- **`test_invoice_posting()`** - Invoice creation with double-entry ledger
- **`test_full_payment()`** - Full payment clears invoice
- **`test_partial_payment()`** - Partial payment updates balance
- **`test_overpayment()`** - Overpayment creates tenant credit

### 2. Line Item Adjustment Tests (`TestLineItemAdjustments`)

Tests adding/removing line items:

- **`test_add_line_item()`** - Add line item with ledger entries
- **`test_remove_line_item()`** - Remove line item with reversals
- **`test_remove_balance_forward_protection()`** - Prevents removing consolidated items

### 3. Consolidation Method Tests (`TestConsolidationMethods`)

Tests SUM vs ITEMIZED methods:

- **`test_sum_method_with_payment()`** - Single consolidated balance line
- **`test_itemized_method_with_payment()`** - Multiple itemized balance lines

### 4. Complex Scenario Tests (`TestComplexScenarios`)

Tests real-world workflows:

- **`test_payment_with_consolidation()`** - Payment allocation to old invoices
- **`test_utility_addition_workflow()`** - Meter reading → line item → finalize
- **`test_add_remove_line_item_workflow()`** - Multiple adjustments with audit trail

## 📝 Custom Test Scenarios

### Scenario 1: Test Payment Allocation Priority

```python
async def test_custom_payment_priority():
    """Test that oldest invoices get paid first"""
    client, db = await TestSetup.setup_test_db()
    manager = AsyncLeaseInvoiceManager(client, "pms_test_db")

    tenant_id = "tenant_123"

    # Create 3 invoices with different dates
    for month in [1, 2, 3]:
        await db.property_invoices.insert_one({
            "_id": ObjectId(),
            "tenant_id": ObjectId(tenant_id),
            "date_issued": datetime(2024, month, 1, tzinfo=timezone.utc),
            "total_amount": 10000.0,
            "balance_amount": 10000.0,
            "status": "overdue"
        })

    # Make payment that only covers first 2 invoices
    result = await manager.process_payment(
        tenant_id=tenant_id,
        amount=20000.0,
        payment_method="mpesa",
        reference="TEST001"
    )

    # Verify oldest 2 are paid, newest still has balance
    print(f"Allocations: {result['allocations']}")

    await client.close()

# Run it
asyncio.run(test_custom_payment_priority())
```

### Scenario 2: Test Multiple Line Item Adjustments

```python
async def test_multiple_adjustments():
    """Test adding multiple charges and credits"""
    client, db = await TestSetup.setup_test_db()
    manager = AsyncLeaseInvoiceManager(client, "pms_test_db")

    # Create base invoice
    invoice_id = str(ObjectId())
    invoice = Invoice(
        id=invoice_id,
        property_id=str(ObjectId()),
        tenant_id=str(ObjectId()),
        date_issued=datetime.now(timezone.utc),
        line_items=[
            InvoiceLineItem(
                id=str(ObjectId()),
                description="Rent",
                amount=15000.0,
                category="rent"
            )
        ],
        total_amount=15000.0,
        balance_amount=15000.0,
        status=InvoiceStatus.READY,
        meta={"audit_trail": []}
    )

    await manager.ledger.post_invoice_to_ledger(invoice)

    # Add charges
    await manager.add_line_item_to_invoice(
        invoice_id=invoice_id,
        line_item=InvoiceLineItem(
            id=str(ObjectId()),
            description="Late Fee",
            amount=500.0,
            category="misc"
        ),
        reason="Late payment"
    )

    await manager.add_line_item_to_invoice(
        invoice_id=invoice_id,
        line_item=InvoiceLineItem(
            id=str(ObjectId()),
            description="Damage Charge",
            amount=2000.0,
            category="maintenance"
        ),
        reason="Broken window"
    )

    # Add credit (negative amount)
    await manager.add_line_item_to_invoice(
        invoice_id=invoice_id,
        line_item=InvoiceLineItem(
            id=str(ObjectId()),
            description="Maintenance Discount",
            amount=-1000.0,
            category="credit"
        ),
        reason="Tenant did own repairs"
    )

    # Check final totals
    final = await db.property_invoices.find_one({"_id": invoice_id})
    print(f"Final Total: KES {final['total_amount']:,.2f}")
    print(f"Line Items: {len(final['line_items'])}")

    await client.close()

asyncio.run(test_multiple_adjustments())
```

### Scenario 3: Test Overpayment Recovery

```python
async def test_overpayment_recovery():
    """Test that overpayment credit is applied to next invoice"""
    client, db = await TestSetup.setup_test_db()
    manager = AsyncLeaseInvoiceManager(client, "pms_test_db")

    tenant_id = str(ObjectId())

    # Setup tenant
    await db.property_tenants.insert_one({
        "_id": ObjectId(tenant_id),
        "full_name": "Test Tenant",
        "credit_balance": 0.0
    })

    # Create Invoice 1
    invoice1 = Invoice(
        id=str(ObjectId()),
        property_id=str(ObjectId()),
        tenant_id=tenant_id,
        date_issued=datetime.now(timezone.utc),
        line_items=[
            InvoiceLineItem(
                id=str(ObjectId()),
                description="Rent",
                amount=10000.0,
                category="rent"
            )
        ],
        total_amount=10000.0,
        balance_amount=10000.0,
        status=InvoiceStatus.READY,
        meta={}
    )

    await manager.ledger.post_invoice_to_ledger(invoice1)

    # Overpay Invoice 1 by 5000
    await manager.process_payment(
        tenant_id=tenant_id,
        amount=15000.0,
        payment_method="mpesa",
        reference="PAY001"
    )

    # Check tenant credit
    credit = await manager.get_tenant_overpayment(tenant_id)
    print(f"Tenant Credit After Overpayment: KES {credit:,.2f}")
    assert credit == 5000.0, "Should have 5000 credit"

    # Create Invoice 2 - should auto-apply credit
    invoice2 = Invoice(
        id=str(ObjectId()),
        property_id=str(ObjectId()),
        tenant_id=tenant_id,
        date_issued=datetime.now(timezone.utc),
        line_items=[
            InvoiceLineItem(
                id=str(ObjectId()),
                description="Rent",
                amount=12000.0,
                category="rent"
            ),
            InvoiceLineItem(
                id=str(ObjectId()),
                description="Credit Applied",
                amount=-5000.0,
                category="overpayment_credit"
            )
        ],
        total_amount=7000.0,  # 12000 - 5000
        balance_amount=7000.0,
        status=InvoiceStatus.READY,
        meta={}
    )

    await manager.ledger.post_invoice_to_ledger(invoice2)

    # Verify credit is used
    new_credit = await manager.get_tenant_overpayment(tenant_id)
    print(f"Tenant Credit After Second Invoice: KES {new_credit:,.2f}")

    await client.close()

asyncio.run(test_overpayment_recovery())
```

### Scenario 4: Test Ledger Balance After Adjustments

```python
async def test_ledger_integrity():
    """Verify ledger stays balanced through multiple operations"""
    client, db = await TestSetup.setup_test_db()
    manager = AsyncLeaseInvoiceManager(client, "pms_test_db")

    invoice_id = str(ObjectId())

    # Create invoice
    invoice = Invoice(
        id=invoice_id,
        property_id=str(ObjectId()),
        tenant_id=str(ObjectId()),
        date_issued=datetime.now(timezone.utc),
        line_items=[
            InvoiceLineItem(
                id=str(ObjectId()),
                description="Rent",
                amount=10000.0,
                category="rent"
            )
        ],
        total_amount=10000.0,
        balance_amount=10000.0,
        status=InvoiceStatus.READY,
        meta={"audit_trail": []}
    )

    await manager.ledger.post_invoice_to_ledger(invoice)

    async def check_balance():
        entries = await db[LEDGER_COLL].find(
            {"invoice_id": invoice_id}
        ).to_list(length=None)
        debits = sum(e.get("debit", 0) for e in entries)
        credits = sum(e.get("credit", 0) for e in entries)
        balanced = abs(debits - credits) < 0.01
        print(f"Debits: {debits:,.2f} | Credits: {credits:,.2f} | Balanced: {balanced}")
        return balanced

    # Check after creation
    print("After Invoice Creation:")
    assert await check_balance()

    # Add line item
    await manager.add_line_item_to_invoice(
        invoice_id=invoice_id,
        line_item=InvoiceLineItem(
            id=str(ObjectId()),
            description="Fee",
            amount=500.0,
            category="misc"
        ),
        reason="Test"
    )

    print("After Adding Line Item:")
    assert await check_balance()

    # Make payment
    await manager.process_payment(
        tenant_id=invoice.tenant_id,
        amount=5000.0,
        payment_method="mpesa",
        reference="TEST",
        target_invoice_id=invoice_id
    )

    print("After Payment:")
    assert await check_balance()

    print("\n✅ Ledger integrity maintained through all operations!")

    await client.close()

asyncio.run(test_ledger_integrity())
```

## 🎯 Common Test Patterns

### Pattern 1: Test Error Handling

```python
async def test_error_scenarios():
    """Test that system handles errors gracefully"""
    client, db = await TestSetup.setup_test_db()
    manager = AsyncLeaseInvoiceManager(client, "pms_test_db")

    # Test 1: Cannot modify paid invoice
    invoice_id = str(ObjectId())
    await db.property_invoices.insert_one({
        "_id": invoice_id,
        "status": "paid",
        "line_items": [],
        "meta": {"audit_trail": []}
    })

    try:
        await manager.add_line_item_to_invoice(
            invoice_id=invoice_id,
            line_item=InvoiceLineItem(
                id=str(ObjectId()),
                description="Fee",
                amount=100.0,
                category="misc"
            )
        )
        print("❌ Should have raised error")
    except ValueError as e:
        print(f"✅ Correctly prevented: {e}")

    # Test 2: Cannot remove non-existent line item
    try:
        await manager.remove_line_item_from_invoice(
            invoice_id=invoice_id,
            line_item_id="fake_id",
            reason="Test"
        )
        print("❌ Should have raised error")
    except ValueError as e:
        print(f"✅ Correctly prevented: {e}")

    await client.close()

asyncio.run(test_error_scenarios())
```

### Pattern 2: Test Data Consistency

```python
async def test_data_consistency():
    """Verify invoice totals match ledger entries"""
    client, db = await TestSetup.setup_test_db()
    manager = AsyncLeaseInvoiceManager(client, "pms_test_db")

    invoice_id = str(ObjectId())

    # Create and manipulate invoice
    invoice = Invoice(
        id=invoice_id,
        property_id=str(ObjectId()),
        tenant_id=str(ObjectId()),
        date_issued=datetime.now(timezone.utc),
        line_items=[
            InvoiceLineItem(
                id=str(ObjectId()),
                description="Rent",
                amount=15000.0,
                category="rent"
            )
        ],
        total_amount=15000.0,
        balance_amount=15000.0,
        status=InvoiceStatus.READY,
        meta={"audit_trail": []}
    )

    await manager.ledger.post_invoice_to_ledger(invoice)

    # Add some items
    for i in range(3):
        await manager.add_line_item_to_invoice(
            invoice_id=invoice_id,
            line_item=InvoiceLineItem(
                id=str(ObjectId()),
                description=f"Fee {i+1}",
                amount=100.0 * (i+1),
                category="misc"
            ),
            reason=f"Fee {i+1}"
        )

    # Get invoice total
    invoice_doc = await db.property_invoices.find_one({"_id": invoice_id})
    invoice_total = invoice_doc['total_amount']

    # Calculate from line items
    line_item_total = sum(item['amount'] for item in invoice_doc['line_items'])

    # Get A/R from ledger
    ar_entries = await db[LEDGER_COLL].find({
        "invoice_id": invoice_id,
        "account": {"$regex": "Accounts Receivable"}
    }).to_list(length=None)

    ar_total = sum(e.get("debit", 0) - e.get("credit", 0) for e in ar_entries)

    print(f"Invoice Total: {invoice_total:,.2f}")
    print(f"Line Items Total: {line_item_total:,.2f}")
    print(f"A/R Ledger Total: {ar_total:,.2f}")

    assert invoice_total == line_item_total == ar_total, "Totals must match!"
    print("✅ All totals consistent!")

    await client.close()

asyncio.run(test_data_consistency())
```

## 📊 Expected Test Output

When you run the full test suite, you should see output like:

```
================================================================================
RUNNING COMPREHENSIVE TEST SUITE
================================================================================

### BASIC LEDGER TESTS ###

================================================================================
TEST: Invoice Posting to Ledger
================================================================================

✅ Posted 3 ledger entries
   - Rent Income: Debit=0.0, Credit=15000.0
   - Utility Income: Debit=0.0, Credit=500.0
   - Accounts Receivable: Debit=15500.0, Credit=0.0

📊 Balance Check:
   Total Debits: 15500.0
   Total Credits: 15500.0
   Balanced: ✅ YES

💾 Invoice saved: ✅ YES

... (more tests) ...

================================================================================
TEST SUMMARY
================================================================================
invoice_posting.......................... ✅ PASS
full_payment............................. ✅ PASS
partial_payment.......................... ✅ PASS
overpayment.............................. ✅ PASS
add_line_item............................ ✅ PASS
remove_line_item......................... ✅ PASS
balance_forward_protection............... ✅ PASS
sum_method............................... ✅ PASS
itemized_method.......................... ✅ PASS
payment_consolidation.................... ✅ PASS
utility_workflow......................... ✅ PASS
add_remove_workflow...................... ✅ PASS

TOTAL........................................ 12/12 PASSED
================================================================================
```

## 🐛 Debugging Failed Tests

If a test fails:

1. **Check MongoDB Connection**

   ```bash
   mongo --eval "db.runCommand({ping:1})"
   ```

2. **Inspect Database State**

   ```python
   async def inspect_db():
       client = AsyncIOMotorClient("mongodb://localhost:27017")
       db = client["pms_test_db"]

       invoice_count = await db.property_invoices.count_documents({})
       ledger_count = await db.property_ledger_entries.count_documents({})

       print(f"Invoices: {invoice_count}")
       print(f"Ledger Entries: {ledger_count}")

       await client.close()

   asyncio.run(inspect_db())
   ```

3. **Enable Verbose Logging**

   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

4. **Check Ledger Balance**
   ```python
   # Add to any test
   entries = await db[LEDGER_COLL].find({}).to_list(length=None)
   total_dr = sum(e.get("debit", 0) for e in entries)
   total_cr = sum(e.get("credit", 0) for e in entries)
   print(f"DR: {total_dr}, CR: {total_cr}, Diff: {total_dr - total_cr}")
   ```

## 💡 Tips

1. **Always clean test data** - Use `TestSetup.setup_test_db()` at start
2. **Test in isolation** - Each test should be independent
3. **Verify ledger balance** - After every operation
4. **Check audit trails** - Ensure all changes are logged
5. **Test edge cases** - Zero amounts, negative amounts, very large numbers

## 📚 Additional Resources

- MongoDB Motor Documentation: https://motor.readthedocs.io/
- Double-Entry Accounting: https://en.wikipedia.org/wiki/Double-entry_bookkeeping
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
