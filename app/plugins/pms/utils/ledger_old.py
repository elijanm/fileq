class Ledger:
    def __init__(self,db:AsyncIOMotorDatabase):
        self.db=db
    async def sync_invoice_payment_status(self, invoice_id: ObjectId) -> None:
        """
        Recalculate totals for a given invoice from ledger_entries.
        Updates invoice fields: total_paid, effective_paid, overpaid_amount, status.
        """
        # Sum all cash debits tied to this invoice
#         If you support multiple partial payments and credit applications across time,
# extend the aggregation with both Cash and Tenant Credit / Prepaid Rent:
#         {"$match": {
#             "invoice_id": invoice_id,
#             "account": {"$in": ["Cash", "Tenant Credit / Prepaid Rent"]}
#         }}
        
        pipeline = [
            {"$match": {"invoice_id": invoice_id, "account": "Cash"}},
            {"$group": {"_id": None, "total_cash": {"$sum": "$debit"}}},
        ]
        cash_docs = await self.db.ledger_entries.aggregate(pipeline).to_list(length=1)
        total_paid = cash_docs[0]["total_cash"] if cash_docs else 0.0

        # Fetch invoice total
        invoice = await self.db.property_invoices.find_one({"_id": invoice_id})
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found in DB")

        invoice_total = invoice.get("total_amount", 0.0)
        orig_status=invoice["status"]
        # Compute effective & overpaid
        effective_paid = min(total_paid, invoice_total)
        overpaid_amount = max(0.0, total_paid - invoice_total)
        new_status = "paid" if total_paid >= invoice_total else "partial"
        new_status=new_status if effective_paid>0 else orig_status
        balance_amount=invoice_total-effective_paid

        # Update invoice doc
        await self.db.property_invoices.update_one(
            {"_id": invoice_id},
            {"$set": {
                "total_paid": total_paid,
                "effective_paid": effective_paid,
                "overpaid_amount": overpaid_amount,
                "balance_amount": balance_amount,
                "status": new_status,
            }}
        )

        print(
            f"🔄 Invoice {invoice_id}: total_paid={total_paid:.2f}, "
            f"effective={effective_paid:.2f}, overpaid={overpaid_amount:.2f}, "
            f"status={new_status}"
        )

    async def post_invoice_to_ledger(self, invoice: Invoice) -> List[LedgerEntry]:
        entries = []
        mapping = {
            "rent": "Rental Income",
            "deposit": "Security Deposit Liability",
            "maintenance": "Maintenance Income",
            "utilities": "Utilities Income",
            "taxes": "Tax Income",
            "investment": "Property",
            "loan": "Loan Payable",
        }
        # 1️⃣ Check if invoice exists
        existing = await self.db.property_invoices.find_one({"_id": invoice.id})
        if not existing:
            await self.db.property_invoices.insert_one(invoice.model_dump(by_alias=True))
            
        for item in invoice.line_items:
            account = mapping.get(item.category, "Misc Income")
            entries.append(LedgerEntry.create(
                date=invoice.date_issued, account=account, credit=item.amount,
                description=f"{item.category.capitalize()} for invoice {invoice.id}",
                invoice_id=invoice.id, line_item_id=item.id,
                property_id=invoice.property_id, tenant_id=invoice.tenant_id
            ))
        entries.append(LedgerEntry.create(
            date=invoice.date_issued, account="Accounts Receivable", debit=invoice.total_amount,
            description=f"Invoice {invoice.id} receivable",
            invoice_id=invoice.id, property_id=invoice.property_id, tenant_id=invoice.tenant_id
        ))
        
        if entries:
            await self.db.property_ledger_entries.insert_many(
                [e.model_dump(by_alias=True) for e in entries]
            )
            await self.sync_invoice_payment_status(invoice.id)
            print(f"📘 Posted {len(entries)} ledger entries for invoice {invoice.id}")
        return entries

    async def post_payment_to_ledger(self, invoice: Invoice, amount: float, payment_date: datetime) -> List[LedgerEntry]:
        existing = await self.db.property_invoices.find_one({"_id": invoice.id})
        if not existing:
            raise Exception("Invoice must be existing in DB")
        entries= [
            LedgerEntry.create(date=payment_date, account="Cash", debit=amount,
                               description=f"Payment received for invoice {invoice.id}",
                               invoice_id=invoice.id, property_id=invoice.property_id, tenant_id=invoice.tenant_id),
            LedgerEntry.create(date=payment_date, account="Accounts Receivable", credit=amount,
                               description=f"Payment applied to invoice {invoice.id}",
                               invoice_id=invoice.id, property_id=invoice.property_id, tenant_id=invoice.tenant_id),
        ]
        if entries:
            await self.db.property_ledger_entries.insert_many(
                [e.model_dump(by_alias=True) for e in entries]
            )
            
            total_paid = (
                await self.db.property_ledger_entries.aggregate([
                    {"$match": {"invoice_id": invoice.id, "account": "Cash"}},
                    {"$group": {"_id": None, "total": {"$sum": "$debit"}}}
                ])
                .to_list(length=1)
            )

            total_paid_amount = total_paid[0]["total"] if total_paid else 0.0
            
            overpaid_amount = max(0.0, total_paid_amount - invoice.total_amount)
            effective_paid = min(total_paid_amount, invoice.total_amount)
            
            # 6️⃣ Post overpayment as tenant credit if any
            if overpaid_amount > 0:
                credit_entry = LedgerEntry(
                    date=payment_date,
                    account="Tenant Credit / Prepaid Rent",
                    credit=overpaid_amount,
                    description=f"Overpayment credit for tenant {invoice.tenant_id}",
                    property_id=invoice.property_id,
                    tenant_id=invoice.tenant_id,
                )
                await self.db.property_ledger_entries.insert_one(credit_entry.model_dump(by_alias=True))
                entries.append(credit_entry)
                print(f"💳 Overpayment of {overpaid_amount:.2f} recorded to Tenant Credit.")

            # 7️⃣ Determine status
            new_status = "paid" if total_paid_amount >= invoice.total_amount else "partial"

            await self.db.property_invoices.update_one(
                {"_id": ObjectId(invoice.id)},
                {"$set": {
                    "status": new_status,
                    "total_paid": total_paid_amount,
                    "effective_paid": effective_paid,
                    "overpaid_amount": overpaid_amount,
                    "balance_amount":invoice.total_amount-effective_paid
                }}
            )
            
            await self.db.property_invoices.update_one(
                {
                    "_id": ObjectId(invoice.id),
                    "$or": [
                        {"payment_date": {"$exists": False}},
                        {"payment_date": None}
                    ]
                },
                {"$set": {"payment_date": payment_date}}
            )
            print(
                f"💰 Payment of {amount:.2f} recorded for invoice {invoice.id}. "
                f"Total paid={total_paid_amount:.2f}, overpaid={overpaid_amount:.2f}, status={new_status.upper()}"
            )
            print(f"📘 Posted {len(entries)} ledger entries for invoice {invoice.id}")
        return entries
    
    async def apply_tenant_credit(
        self,
        tenant_id: str,
        amount: float,
        date_applied: date,
        apply_to_account: str = "Accounts Receivable",
        description: str = "Auto-applied tenant credit to new invoice"
    ) -> Tuple[List[LedgerEntry], float]:
        """
        Automatically applies available tenant credit against an invoice or rent charge.
        Returns (ledger_entries_created, remaining_amount_to_invoice).
        """
        entries: List[LedgerEntry] = []

        # 1️⃣ Calculate total available credit
        pipeline = [
            {"$match": {"tenant_id": tenant_id, "account": "Tenant Credit / Prepaid Rent"}},
            {"$group": {
                "_id": None,
                "total_credit": {"$sum": "$credit"},
                "total_debit": {"$sum": "$debit"}
            }}
        ]
        credit_docs = await self.db.ledger_entries.aggregate(pipeline).to_list(length=1)
        available_credit = 0.0
        if credit_docs:
            c = credit_docs[0]
            available_credit = c["total_credit"] - c["total_debit"]

        if available_credit <= 0:
            # No credit available → return unchanged
            print(f"⚠️ Tenant {tenant_id} has no credit to apply.")
            return [], amount

        # 2️⃣ Determine how much credit to apply
        credit_to_apply = min(amount, available_credit)
        remaining_to_invoice = max(0.0, amount - credit_to_apply)

        # 3️⃣ Post ledger entries
        # Debit Tenant Credit (reduces liability)
        entries.append(
            LedgerEntry(
                date=date_applied,
                account="Tenant Credit / Prepaid Rent",
                debit=credit_to_apply,
                description=f"Applied credit for tenant {tenant_id}",
                tenant_id=tenant_id,
            )
        )

        # Credit AR or other income offset
        entries.append(
            LedgerEntry(
                date=date_applied,
                account=apply_to_account,
                credit=credit_to_apply,
                description=description,
                tenant_id=tenant_id,
            )
        )

        # 4️⃣ Insert entries
        await self.db.ledger_entries.insert_many(
            [e.model_dump(by_alias=True) for e in entries]
        )
        

        # 5️⃣ Log result
        if remaining_to_invoice == 0:
            print(
                f"💳 Tenant {tenant_id} credit of {credit_to_apply:.2f} fully covers invoice. "
                f"Remaining credit reduced to {available_credit - credit_to_apply:.2f}."
            )
        else:
            print(
                f"💳 Tenant {tenant_id} credit of {credit_to_apply:.2f} applied. "
                f"Remaining amount to invoice: {remaining_to_invoice:.2f}. "
                f"Credit balance now: {available_credit - credit_to_apply:.2f}."
            )

        return entries, remaining_to_invoice
    
    
    async def refund_deposit_with_deduction(self, tenant_id: str, property_id: str,
                                      deposit_amount: float, deduction_ratio: float,
                                      refund_date: date) -> List[LedgerEntry]:
        deduction = round(deposit_amount * deduction_ratio, 2)
        net_refund = round(deposit_amount - deduction, 2)
        entries= [
            LedgerEntry.create(date=refund_date, account="Security Deposit Liability", debit=deposit_amount,
                               description=f"Deposit refund (full) for {tenant_id}",
                               property_id=property_id, tenant_id=tenant_id),
            LedgerEntry.create(date=refund_date, account="Cash", credit=net_refund,
                               description=f"Net refund to {tenant_id} after {int(deduction_ratio*100)}% deduction",
                               property_id=property_id, tenant_id=tenant_id),
            LedgerEntry.create(date=refund_date, account="Maintenance Income", credit=deduction,
                               description=f"Deposit deduction recognized as income ({int(deduction_ratio*100)}%)",
                               property_id=property_id, tenant_id=tenant_id),
        ]
        if entries:
            await self.db.property_ledger_entries.insert_many(
                [e.model_dump(by_alias=True) for e in entries]
            )
            print(f"📘 Posted {len(entries)} ledger entries for refund_deposit_with_deduction {property_id}")
        return entries

    async def post_capex(self, when: date, property_id: str, amount: float) -> List[LedgerEntry]:
        entries= [
            LedgerEntry.create(date=when, account="Equipment", debit=amount,
                               description="Capital expenditure", property_id=property_id),
            LedgerEntry.create(date=when, account="Cash", credit=amount,
                               description="Capex paid", property_id=property_id),
        ]
        if entries:
            await self.db.property_ledger_entries.insert_many(
                [e.model_dump(by_alias=True) for e in entries]
            )
            print(f"📘 Posted {len(entries)} ledger entries for post_capex {property_id}")
        return entries

    async def post_monthly_depreciation(self, when: date, property_id: str, amount: float) -> List[LedgerEntry]:
        entries= [
            LedgerEntry.create(date=when, account="Depreciation Expense", debit=amount,
                               description="Monthly depreciation", property_id=property_id),
            LedgerEntry.create(date=when, account="Accumulated Depreciation", credit=amount,
                               description="Accumulated depreciation", property_id=property_id),
        ]
        if entries:
            await self.db.property_ledger_entries.insert_many(
                [e.model_dump(by_alias=True) for e in entries]
            )
            print(f"📘 Posted {len(entries)} ledger entries for post_monthly_depreciation {property_id}")
        return entries
