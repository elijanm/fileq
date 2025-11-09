from datetime import datetime, date,timezone
from typing import List, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

# Import external chart of accounts helper
from plugins.pms.accounting.chart_of_accounts import resolve_account, CHART_OF_ACCOUNTS
from plugins.pms.models.ledger_entry import(
    LedgerEntry,Invoice,InvoiceLineItem
)

LEDGER_COLL = "property_ledger_entries"
INVOICE_COLL = "property_invoices"


class Ledger:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    # ✅ Validate double-entry integrity
    @staticmethod
    def _validate_balance(entries: List["LedgerEntry"]) -> None:
        total_debit = round(sum(e.debit for e in entries), 2)
        total_credit = round(sum(e.credit for e in entries), 2)
        if total_debit != total_credit:
            raise ValueError(f"Ledger imbalance: debit {total_debit} ≠ credit {total_credit}")

    # 🔄 Sync invoice payment totals and status
    async def sync_invoice_payment_status(self,invoice:Invoice,payment_date:datetime=None)->Tuple[str,List[LedgerEntry]]:
        # ------------------------------------------------------
        # 1 Compute total paid and handle overpayment
        # ------------------------------------------------------
        cash = CHART_OF_ACCOUNTS["cash"]
        
        paid = await self.db[LEDGER_COLL].aggregate([
            {"$match": {"invoice_id": invoice.id, "account": cash["account"]}},
            {"$group": {"_id": None, "total": {"$sum": "$debit"}}}
        ]).to_list(length=1)
        total_paid = round(paid[0]["total"], 2) if paid else 0.0

        overpaid = max(0.0, total_paid - invoice.total_amount)
        effective_paid = min(total_paid, invoice.total_amount)

        # Overpayment → tenant credit
        entries=[]
        if overpaid > 0:
            tc = CHART_OF_ACCOUNTS["tenant_credit"]
            credit_entry = LedgerEntry.create(
                date=payment_date,
                account=tc["account"],
                account_code=tc["code"],
                credit=round(overpaid, 2),
                category="overpayment",
                description=f"Overpayment credit for tenant {invoice.tenant_id}",
                property_id=invoice.property_id,
                tenant_id=invoice.tenant_id,
                transaction_type="tenant_credit",
                reference=f"CR-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            )
            await self.db[LEDGER_COLL].insert_one(credit_entry.model_dump(by_alias=True))
            entries.append(credit_entry)
            print(f"💳 Overpayment {overpaid:.2f} recorded as Tenant Credit")

        # ------------------------------------------------------
        # 6️⃣ Update invoice totals
        # ------------------------------------------------------
        new_status = "paid" if total_paid >= invoice.total_amount else "partial"
        await self.db[INVOICE_COLL].update_one(
            {"_id": invoice.id},
            {"$set": {
                "status": new_status,
                "total_paid": total_paid,
                "effective_paid": effective_paid,
                "overpaid_amount": overpaid,
                "balance_amount": round(invoice.total_amount - effective_paid, 2),
                "payment_date": payment_date
            }}
        )
        
        return (new_status,entries)
    # 🧾 Post invoice issuance
    async def post_invoice_to_ledger(self, invoice: "Invoice") -> List["LedgerEntry"]:
        entries: List[LedgerEntry] = []

        existing = await self.db[INVOICE_COLL].find_one({"_id": invoice.id})
        if not existing:
            await self.db[INVOICE_COLL].insert_one(invoice.model_dump(by_alias=True))

        for item in invoice.line_items:
            
            if getattr(item, "is_balance_forwarded", False):
                # 👇 skip it, it’s not new revenue
                continue
            
            acc = resolve_account(item.category_key())
            entries.append(LedgerEntry.create(
                date=invoice.date_issued,
                account=acc["account"],
                account_code=acc["code"],
                credit=item.amount,
                category=item.category,
                description=f"{item.category.capitalize()} for invoice {invoice.id}",
                invoice_id=invoice.id,
                line_item_id=item.id,
                property_id=invoice.property_id,
                tenant_id=invoice.tenant_id,
                transaction_type="invoice_issue",
                reference=f"INV-{invoice.date_issued.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))

        # Debit Accounts Receivable
        ar = CHART_OF_ACCOUNTS["accounts_receivable"]
        entries.append(LedgerEntry.create(
            date=invoice.date_issued,
            account=ar["account"],
            account_code=ar["code"],
            debit=invoice.total_amount,
            category="rent",
            description=f"Invoice {invoice.id} receivable",
            invoice_id=invoice.id,
            property_id=invoice.property_id,
            tenant_id=invoice.tenant_id,
            transaction_type="invoice_issue",
            reference=f"INV-{invoice.date_issued.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
        ))

        self._validate_balance(entries)
        # TODO: Wrap in MongoDB transaction later
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])

        await self.sync_invoice_payment_status(invoice.id,None)
        print(f"📘 Posted {len(entries)} ledger entries for invoice {invoice.id}")
        return entries

    # 💰 Post payment
    async def post_payment_to_ledger(self, invoice: "Invoice", amount: float, payment_date: datetime=None) -> List["LedgerEntry"]:
        """
        Record a tenant payment, allocating it across invoice line items intelligently.

        Handles:
        - partial payments (priority + proportional)
        - rounding remainders
        - overpayments (creates tenant credit)
        - line-item level A/R references
        """
        existing = await self.db[INVOICE_COLL].find_one({"_id": invoice.id})
        if not existing:
            raise Exception("Invoice must exist in DB")

        cash = CHART_OF_ACCOUNTS["cash"]
        ar = CHART_OF_ACCOUNTS["accounts_receivable"]

        entries: List[LedgerEntry] = []
        if not payment_date:
            payment_date=datetime.now(timezone.utc)

        # ------------------------------------------------------
        # 1️⃣ Cash receipt (one debit entry)
        # ------------------------------------------------------
        entries.append(LedgerEntry.create(
            date=payment_date,
            account=cash["account"],
            account_code=cash["code"],
            debit=round(amount, 2),
            category="payment",
            description=f"Payment received for invoice {invoice.invoice_number or invoice.id}",
            invoice_id=invoice.id,
            property_id=invoice.property_id,
            tenant_id=invoice.tenant_id,
            transaction_type="payment_received",
            reference=f"RCPT-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
        ))

        # ------------------------------------------------------
        # 2️⃣ Smart allocation logic
        # ------------------------------------------------------
        total_due = sum(item.amount for item in invoice.line_items)
        if total_due <= 0:
            raise ValueError("Invoice has no line item total to allocate against.")

        remaining = round(amount, 2)
        allocations: list[tuple["InvoiceLineItem", float]] = []
        small_threshold = 50.0  # minimum meaningful allocation

        # Priority order: rent first, then utilities, then others
        priority_order = {"rent": 1, "utility": 2, "maintenance": 3, "deposit": 4, "misc": 5}
        sorted_items = sorted(invoice.line_items, key=lambda i: priority_order.get(i.type, 9))

        for item in sorted_items:
            if remaining <= 0:
                break

            item_total = round(item.amount, 2)

            # If we can pay full item
            if remaining >= item_total:
                allocated = item_total
            # If partial but still meaningful
            elif remaining >= small_threshold:
                allocated = remaining
            else:
                allocated = 0.0

            if allocated > 0:
                allocations.append((item, round(allocated, 2)))
                remaining = round(remaining - allocated, 2)

        # Fix rounding residue (e.g. 0.01 leftover)
        allocated_sum = round(sum(a[1] for a in allocations), 2)
        if allocated_sum < amount and allocations:
            diff = round(amount - allocated_sum, 2)
            allocations[0] = (allocations[0][0], round(allocations[0][1] + diff, 2))

        # ------------------------------------------------------
        # 3️⃣ Create A/R credits for each allocation
        # ------------------------------------------------------
        for item, allocated in allocations:
            if allocated <= 0:
                continue

            category_key = item.category_key() if hasattr(item, "category_key") else item.type
            entries.append(LedgerEntry.create(
                date=payment_date,
                account=f"{ar['account']} ({item.description or item.type})",
                account_code=ar["code"],
                credit=allocated,
                category=category_key,
                description=f"Payment applied to {item.description or item.type}",
                invoice_id=invoice.id,
                line_item_id=item.id,
                property_id=invoice.property_id,
                tenant_id=invoice.tenant_id,
                transaction_type="payment_received",
                reference=f"RCPT-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))

        # ------------------------------------------------------
        # 4️⃣ Validate balance and insert entries
        # ------------------------------------------------------
        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        new_status,addition_entry=self.sync_invoice_payment_status(invoice,payment_date)
        
        entries.append(addition_entry)
        print(f"💰 Payment {amount:.2f} allocated across {len(allocations)} items → {new_status}")
        return entries

    # 💳 Apply tenant credit
    async def apply_tenant_credit(
        self,
        tenant_id: str,
        amount: float,
        date_applied: date,
        apply_to_account: str = "Accounts Receivable",
        description: str = "Auto-applied tenant credit to new invoice"
    ) -> Tuple[List["LedgerEntry"], float]:
        entries: List[LedgerEntry] = []

        pipeline = [
            {"$match": {"tenant_id": tenant_id, "account": "Tenant Credit / Prepaid Rent"}},
            {"$group": {"_id": None, "credit": {"$sum": "$credit"}, "debit": {"$sum": "$debit"}}},
        ]
        docs = await self.db[LEDGER_COLL].aggregate(pipeline).to_list(length=1)
        available = (docs[0]["credit"] - docs[0]["debit"]) if docs else 0.0

        if available <= 0:
            print(f"⚠️ Tenant {tenant_id} has no credit to apply.")
            return [], amount

        to_apply = min(amount, available)
        remaining = max(0.0, amount - to_apply)

        entries.extend([
            LedgerEntry.create(
                date=date_applied,
                account="Tenant Credit / Prepaid Rent",
                debit=to_apply,
                category="credit_applied",
                description=f"Applied tenant credit for {tenant_id}",
                tenant_id=tenant_id,
                transaction_type="credit_applied"
            ),
            LedgerEntry.create(
                date=date_applied,
                account=apply_to_account,
                credit=to_apply,
                category="credit_applied",
                description=description,
                tenant_id=tenant_id,
                transaction_type="credit_applied"
            ),
        ])

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        print(f"💳 Applied {to_apply:.2f} credit for {tenant_id}. Remaining to invoice {remaining:.2f}")
        return entries, remaining

    # 💵 Refund deposit with deduction
    async def refund_deposit_with_deduction(
        self,
        tenant_id: str,
        property_id: str,
        deposit_amount: float,
        deduction_ratio: float,
        refund_date: date
    ) -> List["LedgerEntry"]:
        deduction = round(deposit_amount * deduction_ratio, 2)
        net_refund = round(deposit_amount - deduction, 2)

        entries = [
            LedgerEntry.create(
                date=refund_date,
                account="Security Deposit Liability",
                debit=deposit_amount,
                category="deposit_refund",
                description=f"Deposit refund (full) for tenant {tenant_id}",
                property_id=property_id,
                tenant_id=tenant_id,
                transaction_type="deposit_refund"
            ),
            LedgerEntry.create(
                date=refund_date,
                account="Cash",
                credit=net_refund,
                category="deposit_refund",
                description=f"Refund to tenant {tenant_id} after {int(deduction_ratio * 100)}% deduction",
                property_id=property_id,
                tenant_id=tenant_id,
                transaction_type="deposit_refund"
            ),
            LedgerEntry.create(
                date=refund_date,
                account="Maintenance Income",
                credit=deduction,
                category="deposit_deduction",
                description=f"Deposit deduction recognized as income ({int(deduction_ratio * 100)}%)",
                property_id=property_id,
                tenant_id=tenant_id,
                transaction_type="deposit_refund"
            ),
        ]

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        print(f"📘 Posted {len(entries)} ledger entries for refund_deposit_with_deduction {tenant_id}")
        return entries

    # 🏗️ Post CAPEX
    async def post_capex(self, when: date, property_id: str, amount: float) -> List["LedgerEntry"]:
        equipment = CHART_OF_ACCOUNTS["equipment"]
        cash = CHART_OF_ACCOUNTS["cash"]

        entries = [
            LedgerEntry.create(
                date=when,
                account=equipment["account"],
                account_code=equipment["code"],
                debit=amount,
                category="capex",
                description="Capital expenditure",
                property_id=property_id,
                transaction_type="capex"
            ),
            LedgerEntry.create(
                date=when,
                account=cash["account"],
                account_code=cash["code"],
                credit=amount,
                category="capex",
                description="Capex payment",
                property_id=property_id,
                transaction_type="capex"
            ),
        ]

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        print(f"📘 Posted capex entries for property {property_id}")
        return entries

    # 🧮 Monthly depreciation
    async def post_monthly_depreciation(self, when: date, property_id: str, amount: float) -> List["LedgerEntry"]:
        dexp = CHART_OF_ACCOUNTS["depreciation_expense"]
        adep = CHART_OF_ACCOUNTS["accum_depreciation"]

        entries = [
            LedgerEntry.create(
                date=when,
                account=dexp["account"],
                account_code=dexp["code"],
                debit=amount,
                category="depreciation",
                description="Monthly depreciation",
                property_id=property_id,
                transaction_type="depreciation"
            ),
            LedgerEntry.create(
                date=when,
                account=adep["account"],
                account_code=adep["code"],
                credit=amount,
                category="depreciation",
                description="Accumulated depreciation",
                property_id=property_id,
                transaction_type="depreciation"
            ),
        ]

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        print(f"📘 Posted depreciation entries for property {property_id}")
        return entries
