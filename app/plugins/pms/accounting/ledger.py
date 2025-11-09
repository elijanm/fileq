from datetime import datetime, date, timezone
from typing import List, Tuple, Optional, Literal
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

# Import external chart of accounts helper
from plugins.pms.accounting.chart_of_accounts import resolve_account, CHART_OF_ACCOUNTS,_priority_rank,_resolve_ar_for_category
from plugins.pms.models.ledger_entry import (
    LedgerEntry, Invoice, InvoiceLineItem
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
    async def sync_invoice_payment_status(
        self,
        invoice: "Invoice",
        payment_date: datetime = None
    ) -> Tuple[str, List[LedgerEntry]]:
        """
        Synchronize invoice payment status with ledger entries.
        Handles overpayment by creating tenant credit entries.
        """
        # ------------------------------------------------------
        # 1️⃣ Compute total paid and handle overpayment
        # ------------------------------------------------------
        cash = CHART_OF_ACCOUNTS["cash"]
        
        paid = await self.db[LEDGER_COLL].aggregate([
            {"$match": {"invoice_id": ObjectId(invoice.id), "account": cash["account"]}},
            {"$group": {"_id": None, "total": {"$sum": "$debit"}}}
        ]).to_list(length=1)
        total_paid = round(paid[0]["total"], 2) if paid else 0.0

        overpaid = max(0.0, total_paid - invoice.total_amount)
        effective_paid = min(total_paid, invoice.total_amount)

        # Overpayment → tenant credit
        entries = []
        if overpaid > 0 and payment_date:
            tc = CHART_OF_ACCOUNTS["tenant_credit"]
            credit_entry = LedgerEntry.create(
                date=payment_date,
                account=tc["account"],
                account_code=tc["code"],
                credit=round(overpaid, 2),
                category="overpayment",
                description=f"Overpayment credit for tenant {invoice.tenant_id}",
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
                transaction_type="tenant_credit",
                reference=f"CR-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            )
            await self.db[LEDGER_COLL].insert_one(credit_entry.model_dump(by_alias=True))
            entries.append(credit_entry)
            print(f"💳 Overpayment {overpaid:.2f} recorded as Tenant Credit")

        # ------------------------------------------------------
        # 2️⃣ Update invoice totals
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
        
        return (new_status, entries)

    # 🧾 Post invoice issuance
    async def post_invoice_to_ledger_old(self, invoice: "Invoice") -> List["LedgerEntry"]:
        """Post invoice to ledger with double-entry accounting."""
        entries: List[LedgerEntry] = []

        existing = await self.db[INVOICE_COLL].find_one({"_id": invoice.id})
        if not existing:
            await self.db[INVOICE_COLL].insert_one(invoice.model_dump(by_alias=True))

        for item in invoice.line_items:
            # Skip balance forwarded items - they're not new revenue
            if getattr(item, "is_balance_forwarded", False):
                continue
            
            acc = resolve_account(item.category_key() if hasattr(item, 'category_key') else item.category)
            entries.append(LedgerEntry.create(
                date=invoice.date_issued,
                account=acc["account"],
                account_code=acc["code"],
                credit=item.amount,
                category=item.category,
                description=f"{item.category.capitalize()} for invoice {invoice.id}",
                invoice_id=ObjectId(invoice.id),
                line_item_id=item.id,
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
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
            invoice_id=ObjectId(invoice.id),
            property_id=invoice.property_id,
            tenant_id=ObjectId(invoice.tenant_id),
            transaction_type="invoice_issue",
            reference=f"INV-{invoice.date_issued.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
        ))

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])

        await self.sync_invoice_payment_status(invoice, None)
        print(f"📘 Posted {len(entries)} ledger entries for invoice {invoice.id}")
        return entries
    async def post_invoice_to_ledger(self, invoice: "Invoice") -> List["LedgerEntry"]:
        """
        Post an issued invoice into the general ledger with full double-entry accounting.
        Dynamically links line items to correct Income/Liability/AR accounts.

        - Credits each income/tax/deposit/fee line per CHART_OF_ACCOUNTS
        - Debits per-category A/R (ar_rent, ar_utility_water, ar_taxes, etc.)
        - Skips forwarded balances
        - Validates and inserts all entries atomically
        """
        entries: List[LedgerEntry] = []

        # Ensure invoice exists in DB
        existing = await self.db[INVOICE_COLL].find_one({"_id": invoice.id})
        if not existing:
            await self.db[INVOICE_COLL].insert_one(invoice.model_dump(by_alias=True))

        # ----------------------------------------------------------------------
        # 1️⃣ Credit Income / Liability per line item
        # ----------------------------------------------------------------------
        for item in invoice.line_items:
            if getattr(item, "is_balance_forwarded", False):
                continue

            category = item.category_key() if hasattr(item, "category_key") else item.category
            mapping = resolve_account(category)

            # Credit: revenue / liability
            entries.append(LedgerEntry.create(
                date=invoice.date_issued,
                account=mapping["account"],
                account_code=mapping["code"],
                credit=round(item.amount, 2),
                category=category,
                description=f"{mapping['account']} - {category} for invoice {invoice.invoice_number or invoice.id}",
                invoice_id=ObjectId(invoice.id),
                line_item_id=item.id,
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
                transaction_type="invoice_issue",
                reference=f"INV-{invoice.date_issued.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))

            # ------------------------------------------------------------------
            # 2️⃣ Debit correct A/R (per category)
            # ------------------------------------------------------------------
            ar_account = _resolve_ar_for_category(category)
            entries.append(LedgerEntry.create(
                date=invoice.date_issued,
                account=ar_account["account"],
                account_code=ar_account["code"],
                debit=round(item.amount, 2),
                category=category,
                description=f"Receivable - {category} for invoice {invoice.invoice_number or invoice.id}",
                invoice_id=ObjectId(invoice.id),
                line_item_id=item.id,
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
                transaction_type="invoice_issue",
                reference=f"INV-{invoice.date_issued.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))

        # ----------------------------------------------------------------------
        # 3️⃣ Special deposit issuance / refund handling
        # ----------------------------------------------------------------------
        if getattr(invoice.meta, "is_deposit_issue", False):
            dep_liab = CHART_OF_ACCOUNTS["deposit"]
            dep_ar = _resolve_ar_for_category("deposit")

            # Debit tenant’s deposit receivable, credit liability
            entries.extend([
                LedgerEntry.create(
                    date=invoice.date_issued,
                    account=dep_ar["account"],
                    account_code=dep_ar["code"],
                    debit=invoice.total_amount,
                    category="deposit_issue",
                    description="Deposit Receivable",
                    invoice_id=ObjectId(invoice.id),
                    property_id=invoice.property_id,
                    tenant_id=ObjectId(invoice.tenant_id),
                    transaction_type="deposit_issue",
                ),
                LedgerEntry.create(
                    date=invoice.date_issued,
                    account=dep_liab["account"],
                    account_code=dep_liab["code"],
                    credit=invoice.total_amount,
                    category="deposit_issue",
                    description="Tenant Deposit Liability",
                    invoice_id=ObjectId(invoice.id),
                    property_id=invoice.property_id,
                    tenant_id=ObjectId(invoice.tenant_id),
                    transaction_type="deposit_issue",
                )
            ])

        elif getattr(invoice.meta, "is_deposit_refund", False):
            dep_liab = CHART_OF_ACCOUNTS["deposit"]
            cash = CHART_OF_ACCOUNTS["cash"]
            # Debit liability, credit cash
            entries.extend([
                LedgerEntry.create(
                    date=invoice.date_issued,
                    account=dep_liab["account"],
                    account_code=dep_liab["code"],
                    debit=invoice.total_amount,
                    category="deposit_refund",
                    description="Deposit Refund (reduce liability)",
                    invoice_id=ObjectId(invoice.id),
                    property_id=invoice.property_id,
                    tenant_id=ObjectId(invoice.tenant_id),
                    transaction_type="deposit_refund",
                ),
                LedgerEntry.create(
                    date=invoice.date_issued,
                    account=cash["account"],
                    account_code=cash["code"],
                    credit=invoice.total_amount,
                    category="deposit_refund",
                    description="Deposit refund paid to tenant",
                    invoice_id=ObjectId(invoice.id),
                    property_id=invoice.property_id,
                    tenant_id=ObjectId(invoice.tenant_id),
                    transaction_type="deposit_refund",
                )
            ])

        # ----------------------------------------------------------------------
        # 4️⃣ Validate and persist
        # ----------------------------------------------------------------------
        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        await self.sync_invoice_payment_status(invoice, None)

        print(f"📘 Posted {len(entries)} ledger entries for invoice {invoice.id}")
        return entries

    # 💰 Post payment
    async def post_payment_to_ledger_old(
        self,
        invoice: "Invoice",
        amount: float,
        payment_date: datetime = None
    ) -> List["LedgerEntry"]:
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
            payment_date = datetime.now(timezone.utc)

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
            invoice_id=ObjectId(invoice.id),
            property_id=invoice.property_id,
            tenant_id=ObjectId(invoice.tenant_id),
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
        sorted_items = sorted(invoice.line_items, key=lambda i: priority_order.get(i.category, 9))

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

            category_key = item.category_key() if hasattr(item, "category_key") else item.category
            entries.append(LedgerEntry.create(
                date=payment_date,
                account=f"{ar['account']} ({item.description or item.category})",
                account_code=ar["code"],
                credit=allocated,
                category=category_key,
                description=f"Payment applied to {item.description or item.category}",
                invoice_id=ObjectId(invoice.id),
                line_item_id=item.id,
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
                transaction_type="payment_received",
                reference=f"RCPT-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))

        # ------------------------------------------------------
        # 4️⃣ Validate balance and insert entries
        # ------------------------------------------------------
        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        new_status, addition_entries = await self.sync_invoice_payment_status(invoice, payment_date)
        
        entries.extend(addition_entries)
        print(f"💰 Payment {amount:.2f} allocated across {len(allocations)} items → {new_status}")
        return entries
    # ======================================================================
    # 💰 Post payment
    # ======================================================================
    async def post_payment_to_ledger(
    self,
    invoice: "Invoice",
    amount: float,
    payment_date: datetime | None = None
) -> List["LedgerEntry"]:
        """
        Record a tenant payment and allocate intelligently across line items.

        Handles:
        - Partial and proportional payments by priority (ALLOCATION_PRIORITY)
        - Per-category AR subaccount mapping
        - Overpayments → Tenant Credit (Liability)
        - Full balance validation
        """
        if amount <= 0:
            raise ValueError("Payment amount must be positive.")

        existing = await self.db[INVOICE_COLL].find_one({"_id": invoice.id})
        if not existing:
            raise Exception("Invoice must exist in DB")

        cash = CHART_OF_ACCOUNTS["cash"]
        tenant_credit_liab = CHART_OF_ACCOUNTS["tenant_credit"]

        entries: List[LedgerEntry] = []
        if not payment_date:
            payment_date = datetime.now(timezone.utc)

        # ------------------------------------------------------
        # 1️⃣ Cash receipt (Debit)
        # ------------------------------------------------------
        entries.append(LedgerEntry.create(
            date=payment_date,
            account=cash["account"],
            account_code=cash["code"],
            debit=round(amount, 2),
            category="payment",
            description=f"Payment received for invoice {invoice.invoice_number or invoice.id}",
            invoice_id=ObjectId(invoice.id),
            property_id=invoice.property_id,
            tenant_id=ObjectId(invoice.tenant_id),
            transaction_type="payment_received",
            reference=f"RCPT-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
        ))

        # ------------------------------------------------------
        # 2️⃣ Allocation logic (priority-based)
        # ------------------------------------------------------
        items = [i for i in invoice.line_items if not getattr(i, "is_balance_forwarded", False)]
        if not items:
            # No allocatable lines → entire payment = overpayment
            entries.append(LedgerEntry.create(
                date=payment_date,
                account=tenant_credit_liab["account"],
                account_code=tenant_credit_liab["code"],
                credit=round(amount, 2),
                category="overpayment",
                description="Overpayment → Tenant Credit",
                invoice_id=ObjectId(invoice.id),
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
                transaction_type="overpayment_credit",
                reference=f"RCPT-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))
            self._validate_balance(entries)
            await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
            await self.sync_invoice_payment_status(invoice, payment_date)
            return entries

        # Sort items by priority rank
        sorted_items = sorted(
            items,
            key=lambda i: _priority_rank(
                i.category_key() if hasattr(i, "category_key") else i.category
            )
        )

        remaining = round(amount, 2)
        allocations: list[tuple["InvoiceLineItem", float]] = []

        for item in sorted_items:
            if remaining <= 0:
                break
            item_total = round(float(item.amount), 2)
            allocate = min(remaining, item_total)
            allocations.append((item, allocate))
            remaining = round(remaining - allocate, 2)

        # Rounding adjustment (ensure total allocations ≤ payment)
        allocated_total = round(sum(v for _, v in allocations), 2)
        if allocated_total > amount:
            diff = allocated_total - amount
            if allocations:
                allocations[-1] = (allocations[-1][0], round(allocations[-1][1] - diff, 2))
            allocated_total = round(sum(v for _, v in allocations), 2)

        overpay = round(amount - allocated_total, 2)

        # ------------------------------------------------------
        # 3️⃣ AR Credits (per line item)
        # ------------------------------------------------------
        for item, allocated in allocations:
            if allocated <= 0:
                continue
            category = item.category_key() if hasattr(item, "category_key") else item.category
            ar = _resolve_ar_for_category(category)

            entries.append(LedgerEntry.create(
                date=payment_date,
                account=ar["account"],
                account_code=ar["code"],
                credit=allocated,
                category=category,
                description=f"Payment applied to {item.description or category}",
                invoice_id=ObjectId(invoice.id),
                line_item_id=item.id,
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
                transaction_type="payment_received",
                reference=f"RCPT-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))

        # ------------------------------------------------------
        # 4️⃣ Overpayment → Tenant Credit (Liability)
        # ------------------------------------------------------
        if overpay > 0.0:
            entries.append(LedgerEntry.create(
                date=payment_date,
                account=tenant_credit_liab["account"],
                account_code=tenant_credit_liab["code"],
                credit=overpay,
                category="overpayment",
                description="Overpayment → Tenant Credit",
                invoice_id=ObjectId(invoice.id),
                property_id=invoice.property_id,
                tenant_id=ObjectId(invoice.tenant_id),
                transaction_type="overpayment_credit",
                reference=f"RCPT-{payment_date.strftime('%y%m%d')}-{str(invoice.id)[-4:]}"
            ))

        # ------------------------------------------------------
        # 5️⃣ Validate and persist
        # ------------------------------------------------------
        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])

        new_status, extra = await self.sync_invoice_payment_status(invoice, payment_date)
        entries.extend(extra)

        print(f"💰 Payment {amount:.2f} applied to {len(allocations)} items (overpay {overpay:.2f}) → {new_status}")
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
        """Apply tenant credit to reduce invoice amount."""
        entries: List[LedgerEntry] = []

        pipeline = [
            {"$match": {"tenant_id": ObjectId(tenant_id), "account": "Tenant Credit / Prepaid Rent"}},
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
                tenant_id=ObjectId(tenant_id),
                transaction_type="credit_applied"
            ),
            LedgerEntry.create(
                date=date_applied,
                account=apply_to_account,
                credit=to_apply,
                category="credit_applied",
                description=description,
                tenant_id=ObjectId(tenant_id),
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
        """Refund security deposit with optional deduction."""
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
                tenant_id=ObjectId(tenant_id),
                transaction_type="deposit_refund"
            ),
            LedgerEntry.create(
                date=refund_date,
                account="Cash",
                credit=net_refund,
                category="deposit_refund",
                description=f"Refund to tenant {tenant_id} after {int(deduction_ratio * 100)}% deduction",
                property_id=property_id,
                tenant_id=ObjectId(tenant_id),
                transaction_type="deposit_refund"
            ),
            LedgerEntry.create(
                date=refund_date,
                account="Maintenance Income",
                credit=deduction,
                category="deposit_deduction",
                description=f"Deposit deduction recognized as income ({int(deduction_ratio * 100)}%)",
                property_id=property_id,
                tenant_id=ObjectId(tenant_id),
                transaction_type="deposit_refund"
            ),
        ]

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])
        print(f"📘 Posted {len(entries)} ledger entries for refund_deposit_with_deduction {tenant_id}")
        return entries

    # 🏗️ Post CAPEX
    async def post_capex(self, when: date, property_id: str, amount: float) -> List["LedgerEntry"]:
        """Post capital expenditure."""
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
        """Post monthly depreciation expense."""
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

    # ➕ Add line item to invoice
    async def add_line_item_to_invoice(
        self,
        invoice_id: str,
        line_item: InvoiceLineItem,
        reason: str = "",
        transaction_type:str="line_item_addition",
        adjustment_date: Optional[datetime] = None
    ) -> Tuple[List[LedgerEntry], Invoice]:
        """
        Add a new line item to an existing invoice with proper ledger entries.
        
        Works with both SUM and ITEMIZED consolidation methods.
        """
        if not adjustment_date:
            adjustment_date = datetime.now(timezone.utc)

        # Get current invoice
        invoice_doc = await self.db[INVOICE_COLL].find_one({"_id": ObjectId(invoice_id)})
        if not invoice_doc:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Check if editable
        if invoice_doc["status"] in ["paid", "cancelled", "finalized"]:
            raise ValueError(f"Cannot modify invoice with status: {invoice_doc['status']}")

        # Post ledger entries for the new line item
        entries = []
        
        # Credit revenue account
        acc = resolve_account(line_item.category_key() if hasattr(line_item, 'category_key') else line_item.category)
        entries.append(LedgerEntry.create(
            date=adjustment_date,
            account=acc["account"],
            account_code=acc["code"],
            credit=line_item.amount,
            category=line_item.category,
            description=f"{line_item.description} (Added: {reason})",
            invoice_id=ObjectId(invoice_id),
            line_item_id=line_item.id,
            property_id=invoice_doc["property_id"],
            tenant_id=ObjectId(invoice_doc["tenant_id"]),
            transaction_type="line_item_addition",
            reference=f"ADD-{adjustment_date.strftime('%y%m%d')}-{str(invoice_id)[-4:]}"
        ))

        # Debit Accounts Receivable
        ar = CHART_OF_ACCOUNTS["accounts_receivable"]
        entries.append(LedgerEntry.create(
            date=adjustment_date,
            account=ar["account"],
            account_code=ar["code"],
            debit=line_item.amount,
            category=line_item.category,
            description=f"A/R increase for: {line_item.description}",
            invoice_id=ObjectId(invoice_id),
            line_item_id=line_item.id,
            property_id=invoice_doc["property_id"],
            tenant_id=ObjectId(invoice_doc["tenant_id"]),
            transaction_type=transaction_type,
            reference=f"ADD-{adjustment_date.strftime('%y%m%d')}-{str(invoice_id)[-4:]}"
        ))

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])

        # Update invoice document
        line_item_dict = line_item.model_dump(by_alias=True)
        line_item_dict["meta"] = line_item_dict.get("meta", {})
        line_item_dict["meta"]["added_manually"] = True
        line_item_dict["meta"]["added_at"] = adjustment_date.isoformat()
        line_item_dict["meta"]["reason"] = reason

        new_total = invoice_doc["total_amount"] + line_item.amount
        new_balance = new_total - invoice_doc["total_paid"]

        await self.db[INVOICE_COLL].update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$push": {
                    "line_items": line_item_dict,
                    "meta.audit_trail": {
                        "action": "line_item_added",
                        "line_item_id": line_item.id,
                        "amount": line_item.amount,
                        "reason": reason,
                        "timestamp": adjustment_date
                    }
                },
                "$set": {
                    "total_amount": new_total,
                    "balance_amount": max(0, new_balance),
                    "updated_at": adjustment_date
                }
            }
        )

        # Get updated invoice and sync payment status
        updated_invoice_doc = await self.db[INVOICE_COLL].find_one({"_id": ObjectId(invoice_id)})
        updated_invoice = Invoice(**updated_invoice_doc)
        await self.sync_invoice_payment_status(updated_invoice, adjustment_date)

        print(f"✅ Added line item: {line_item.description} - {line_item.amount}")
        return entries, updated_invoice

    # ➖ Remove line item from invoice
    async def remove_line_item_from_invoice(
        self,
        invoice_id: str,
        line_item_id: str,
        reason: str = "",
        adjustment_date: Optional[datetime] = None,
        allow_balance_item_removal: bool = False
    ) -> Tuple[List[LedgerEntry], Invoice]:
        """
        Remove a line item from an existing invoice with reversal ledger entries.
        
        Creates offsetting entries to maintain ledger integrity.
        """
        if not adjustment_date:
            adjustment_date = datetime.now(timezone.utc)

        # Get current invoice
        invoice_doc = await self.db[INVOICE_COLL].find_one({"_id": ObjectId(invoice_id)})
        if not invoice_doc:
            raise ValueError(f"Invoice {invoice_id} not found")

        # Check if editable
        if invoice_doc["status"] in ["paid", "cancelled", "finalized"]:
            raise ValueError(f"Cannot modify invoice with status: {invoice_doc['status']}")

        # Find the line item
        line_item = next(
            (item for item in invoice_doc["line_items"] if str(item["_id"]) == line_item_id),
            None
        )
        
        if not line_item:
            raise ValueError(f"Line item {line_item_id} not found in invoice")

        # Check if it's a balance forward item
        if line_item["category"] == "balance_brought_forward" and not allow_balance_item_removal:
            raise ValueError(
                "Cannot remove balance_brought_forward items. "
                "Use allow_balance_item_removal=True to override (not recommended)"
            )

        # Create reversal ledger entries
        entries = []
        
        # Debit revenue account (reversal)
        category = line_item.get("category", "misc")
        acc = resolve_account(category)
        entries.append(LedgerEntry.create(
            date=adjustment_date,
            account=acc["account"],
            account_code=acc["code"],
            debit=line_item["amount"],  # Opposite of original credit
            category=category,
            description=f"REVERSAL: {line_item['description']} (Reason: {reason})",
            invoice_id=ObjectId(invoice_id),
            line_item_id=line_item_id,
            property_id=invoice_doc["property_id"],
            tenant_id=ObjectId(invoice_doc["tenant_id"]),
            transaction_type="line_item_reversal",
            reference=f"REV-{adjustment_date.strftime('%y%m%d')}-{str(invoice_id)[-4:]}"
        ))

        # Credit Accounts Receivable (reversal)
        ar = CHART_OF_ACCOUNTS["accounts_receivable"]
        entries.append(LedgerEntry.create(
            date=adjustment_date,
            account=ar["account"],
            account_code=ar["code"],
            credit=line_item["amount"],  # Opposite of original debit
            category=category,
            description=f"A/R reversal for: {line_item['description']}",
            invoice_id=ObjectId(invoice_id),
            line_item_id=line_item_id,
            property_id=invoice_doc["property_id"],
            tenant_id=ObjectId(invoice_doc["tenant_id"]),
            transaction_type="line_item_reversal",
            reference=f"REV-{adjustment_date.strftime('%y%m%d')}-{str(invoice_id)[-4:]}"
        ))

        self._validate_balance(entries)
        await self.db[LEDGER_COLL].insert_many([e.model_dump(by_alias=True) for e in entries])

        # Update invoice document
        new_total = invoice_doc["total_amount"] - line_item["amount"]
        new_balance = new_total - invoice_doc["total_paid"]

        await self.db[INVOICE_COLL].update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$pull": {"line_items": {"_id": line_item_id}},
                "$push": {
                    "meta.audit_trail": {
                        "action": "line_item_removed",
                        "line_item_id": line_item_id,
                        "amount": line_item["amount"],
                        "description": line_item["description"],
                        "reason": reason,
                        "timestamp": adjustment_date
                    }
                },
                "$set": {
                    "total_amount": new_total,
                    "balance_amount": max(0, new_balance),
                    "updated_at": adjustment_date
                }
            }
        )

        # Get updated invoice and sync payment status
        updated_invoice_doc = await self.db[INVOICE_COLL].find_one({"_id": ObjectId(invoice_id)})
        updated_invoice = Invoice(**updated_invoice_doc)
        await self.sync_invoice_payment_status(updated_invoice, adjustment_date)

        print(f"✅ Removed line item: {line_item['description']} - {line_item['amount']}")
        return entries, updated_invoice

    # 🔍 Get tenant credit balance from ledger
    async def get_tenant_credit_balance(self, tenant_id: str) -> float:
        """Get tenant's current credit balance from ledger entries."""
        tc = CHART_OF_ACCOUNTS["tenant_credit"]
        
        pipeline = [
            {
                "$match": {
                    "tenant_id": ObjectId(tenant_id),
                    "account": tc["account"]
                }
            },
            {
                "$group": {
                    "_id": None,
                    "credit": {"$sum": "$credit"},
                    "debit": {"$sum": "$debit"}
                }
            }
        ]
        
        docs = await self.db[LEDGER_COLL].aggregate(pipeline).to_list(length=1)
        available = (docs[0]["credit"] - docs[0]["debit"]) if docs else 0.0
        return round(available, 2)