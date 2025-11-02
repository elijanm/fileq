# This script regenerates the single PDF AND creates an Excel workbook
# with all statements (Journal, Trial Balance, Income Statement, Cash Flow, Balance Sheet, KPIs).
# Files will be saved to /mnt/data and download links will be printed at the end. 
from __future__ import annotations
from datetime import date, timedelta,datetime
from typing import List, Optional, Dict, Literal, Tuple,Union
from uuid import uuid4
from bson import ObjectId
from collections import defaultdict
from dataclasses import dataclass,field,asdict
import random, calendar, math, textwrap, os
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.MongoORJSONResponse import normalize_bson
# Matplotlib for PDF pages (no seaborn, no custom styles)
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import pandas as pd

# =============================
# Data Models (lightweight)
# =============================

from pydantic import BaseModel, Field,ConfigDict,field_serializer,field_validator
from datetime import date
from typing import List, Optional
from bson import ObjectId
from pydantic_core import core_schema
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler


# --- Helper for ObjectId compatibility ---
def generate_collection_insight(total_invoiced, total_collected, avg_due_days, overdue_invoices, move_outs):
    rate = (total_collected / total_invoiced * 100) if total_invoiced else 0
    if rate == 0:
        severity = "High"
        tone = "🔴 Collection Rate Needs Attention"
        suggestion = "Send reminders and verify tenant payment status."
    elif rate < 70:
        severity = "Moderate"
        tone = "🟠 Partial Collections Detected"
        suggestion = "Follow up with remaining tenants."
    else:
        severity = "Good"
        tone = "🟢 Healthy Collections"
        suggestion = "Continue normal follow-up."
    return {
        "title": "Financial Insights",
        "summary": tone,
        "details": f"{rate:.1f}% collected ({total_collected:.2f} / {total_invoiced:.2f}). "
                   f"{len(overdue_invoices)} invoices overdue by avg {avg_due_days} days. "
                   f"{len(move_outs)} tenants moving out next month.",
        "severity": severity,
        "recommendation": suggestion
    }
def compute_financial_metrics(
    invoices,
    ledger_entries,
    moving_out_next_month,
    total_units,
    vacant_units,
    occupied_units,
):
    today =  datetime.combine(date.today(), datetime.min.time())

    # --- Invoice totals ---
    total_invoiced = sum(inv.total_amount for inv in invoices if inv.status in ["issued", "paid", "partial","unpaid"])

    # --- Cash collected ---
    total_collected = sum(e.debit for e in ledger_entries if e.account == "Cash")

    # --- Overdue invoices ---
    overdue_invoices = [inv for inv in invoices if inv.due_date < today and inv.status in ["issued","unpaid"]]
    avg_due_days = (
        sum((today - inv.due_date).days for inv in overdue_invoices) / len(overdue_invoices)
        if overdue_invoices else 0
    )

    # --- Movement / tenancy metrics ---
    move_outs = list(moving_out_next_month)

    # --- Derived metrics (safe divisions) ---
    collection_rate = (total_collected / total_invoiced * 100) if total_invoiced > 0 else 0
    vacancy_rate = (vacant_units / total_units * 100) if total_units > 0 else 0
    arrears_balance = total_invoiced - total_collected
    average_rent_per_unit = (total_invoiced / occupied_units) if occupied_units > 0 else 0
    
    invoices_by_status = {
        "paid": len([i for i in invoices if i.status == "paid"]),
        "partial": len([i for i in invoices if i.status == "partial"]),
        "unpaid": len([i for i in invoices if i.status in ["issued","unpaid"]]),
        "overpaid": len([i for i in invoices if i.status == "overpaid"]) if any(i.status == "overpaid" for i in invoices) else 0,
    }

    # --- Summary dictionary ---
    
     # --- Derived balances ---
    total_pending = total_invoiced - total_collected if total_invoiced else 0

    # Overdue invoices
    overdue_invoices = [i for i in invoices if i.due_date < today and i.status != "paid"]
    total_overdue = sum(i.total_amount for i in overdue_invoices)
    avg_due_days = (
        sum((today - i.due_date).days for i in overdue_invoices) / len(overdue_invoices)
        if overdue_invoices else 0
    )

    # Expected this month (could be based on issued invoices)
    expected_this_month = sum(
        i.total_amount for i in invoices if i.date_issued.month == today.month and i.date_issued.year == today.year
    )
   
   
  
    return {
        "total_invoiced": round(total_invoiced, 2),
        "total_collected": round(total_collected, 2),
        "total_pending": round(total_pending, 2),
        "total_overdue": round(total_overdue, 2),
        "expected_this_month": round(expected_this_month, 2),
        "collection_rate": round(collection_rate, 1),
        "vacancy_rate": round(vacancy_rate, 1),
        "arrears_balance": round(arrears_balance, 2),
        "avg_due_days": round(avg_due_days, 1),
        "average_rent_per_unit": round(average_rent_per_unit, 2),
        "overdue_count": len(overdue_invoices),
        "move_outs": move_outs,
        "invoices_by_status": invoices_by_status,
    }
def compute_forecast_metrics(invoices, ledger_entries):
    today =  datetime.combine(date.today(), datetime.min.time())
    start_of_month = date(today.year, today.month, 1)
    current_month_str = today.strftime("%Y-%m")

    # Define forecast periods
    next_30 = today + timedelta(days=30)
    next_60 = today + timedelta(days=60)

    # --- Base calculations ---
    expected_collections = sum(
        inv.total_amount for inv in invoices
        if inv.date_issued.month == today.month and inv.date_issued.year == today.year
    )

    pending_invoices = [inv for inv in invoices if inv.status not in ["paid", "overpaid"]]
    pending_total = sum(inv.total_amount for inv in pending_invoices)

    overdue_invoices = [inv for inv in invoices if inv.due_date < today and inv.status != "paid"]
    overdue_amount = sum(inv.total_amount for inv in overdue_invoices)

    # --- Forecasting ---
    next_30_days_expected = sum(
        inv.total_amount for inv in invoices
        if today < inv.due_date <= next_30
    )
    next_60_days_expected = sum(
        inv.total_amount for inv in invoices
        if today < inv.due_date <= next_60
    )

    # --- Optional: Add receipts forecasting (from ledger) ---
    collected_this_month = sum(
        e.debit for e in ledger_entries
        if e.account == "Cash" and e.date.month == today.month and e.date.year == today.year
    )

    forecast_balance = expected_collections - collected_this_month

    return {
        "current_month": current_month_str,
        "expected_collections": round(expected_collections, 2),
        "pending_invoices": round(pending_total, 2),
        "overdue_amount": round(overdue_amount, 2),
        "next_30_days_expected": round(next_30_days_expected, 2),
        "next_60_days_expected": round(next_60_days_expected, 2),
        "forecast_balance": round(forecast_balance, 2),
    }

class PyObjectId(ObjectId):
    """Pydantic v2 compatible ObjectId wrapper that accepts both str and ObjectId."""

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            try:
                return ObjectId(v)
            except Exception:
                raise ValueError(f"Invalid ObjectId string: {v}")
        raise TypeError(f"Expected str or ObjectId, got {type(v)}")

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler: GetCoreSchemaHandler):
        # Validate string → ObjectId conversion
        return core_schema.no_info_after_validator_function(cls.validate, core_schema.union_schema([
            core_schema.str_schema(),
            core_schema.is_instance_schema(ObjectId)
        ]))

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler: GetJsonSchemaHandler):
        json_schema = handler(core_schema)
        json_schema.update(type="string", examples=["671fb57ef25e3e94c611b9b0"])
        return json_schema
    def __str__(self):
        return str(ObjectId(self))



# ============================================================
# MODELS
# ============================================================

class LineItem(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    description: str
    amount: float
    category: str="utilities"  # rent, deposit, maintenance, utilities, taxes, investment, loan, other
    usage_units: Optional[float] = None
    meta: Optional[dict] = Field(default_factory=dict)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }
    )
    
    @field_serializer("meta", when_used="json")
    def serialize_meta(self, v,info):
        """Recursively convert ObjectId/date inside meta to JSON-safe strings."""
        return normalize_bson(v)

    @staticmethod
    def create(description: str, amount: float, category: str,meta:dict={}) -> "LineItem":
        return LineItem(description=description, amount=amount, category=category,meta=meta)


class Invoice(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    property_id: str
    tenant_id: Union[str, ObjectId]
    date_issued: datetime
    payment_date: Optional[datetime]=None
    due_date: datetime
    units_id: List[str]=Field(None,)
    line_items: List[LineItem]
    total_amount: float
    total_paid: Optional[float]=0.00
    effective_paid: Optional[float]=0.00
    overpaid_amount: Optional[float]=0.00
    balance_amount: Optional[float]=0.00
    meta: Optional[dict]={}
    status: str = "issued"

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={
            ObjectId: str,
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat(),
        }
    )
    @field_validator("tenant_id", mode="before")
    @classmethod
    def normalize_tenant_id(cls, v):
        """Accept ObjectId or string, store as string."""
        if isinstance(v, ObjectId):
            return str(v)
        elif isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid tenant_id: must be ObjectId or valid string")
    
    @field_serializer("meta", when_used="json")
    def serialize_meta(self, v,info):
        """Recursively convert ObjectId/date inside meta to JSON-safe strings."""
        return normalize_bson(v)

    @staticmethod
    def create(
        property_id: str,
        tenant_id: str,
        date_issued: date,
        due_date: date,
        items: List[LineItem],
        units_id: Optional[List[str]] = None,
    ) -> "Invoice":
        return Invoice(
            property_id=property_id,
            tenant_id=tenant_id,
            date_issued=date_issued,
            due_date=due_date,
            line_items=items,
            total_amount=sum(i.amount for i in items),
            units_id=units_id,
            status="issued",
        )


class LedgerEntry(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    date: datetime
    account: str
    debit: float = 0.0
    credit: float = 0.0
    description: Optional[str] = None
    invoice_id: Optional[PyObjectId] = None
    line_item_id: Optional[PyObjectId] = None
    property_id: Optional[str] = None
    tenant_id: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

    @staticmethod
    def create(**kwargs) -> "LedgerEntry":
        kwargs.setdefault("id", PyObjectId())
        return LedgerEntry(**kwargs)


# =============================
# Chart of Accounts Metadata
# =============================

ACCOUNT_META = {
    "Cash": ("asset", "current_asset", "debit"),
    "Accounts Receivable": ("asset", "current_asset", "debit"),
    "Property": ("asset", "noncurrent_asset", "debit"),
    "Equipment": ("asset", "noncurrent_asset", "debit"),
    "Accumulated Depreciation": ("contra_asset", "noncurrent_asset", "credit"),
    "Accounts Payable": ("liability", "current_liability", "credit"),
    "Security Deposit Liability": ("liability", "current_liability", "credit"),
    "Loan Payable": ("liability", "noncurrent_liability", "credit"),
    "Owner Capital": ("equity", "equity", "credit"),
    "Retained Earnings": ("equity", "equity", "credit"),
    "Rental Income": ("income", "operating_revenue", "credit"),
    "Utilities Income": ("income", "operating_revenue", "credit"),
    "Maintenance Income": ("income", "other_revenue", "credit"),
    "Tax Income": ("income", "other_revenue", "credit"),
    "Misc Income": ("income", "other_revenue", "credit"),
    "Maintenance Expense": ("expense", "operating_expense", "debit"),
    "Utilities Expense": ("expense", "operating_expense", "debit"),
    "Property Taxes": ("expense", "operating_expense", "debit"),
    "Management Fees": ("expense", "operating_expense", "debit"),
    "Depreciation Expense": ("expense", "noncash_expense", "debit"),
    "Loan Interest Expense": ("expense", "financing_expense", "debit"),
}

# =============================
# Helpers
# =============================

def account_balance(entries: List[LedgerEntry], up_to: Optional[date] = None) -> Dict[str, float]:
    bal = defaultdict(float)
    for e in entries:
        if up_to and e.date > up_to:
            continue
        bal[e.account] += e.debit - e.credit
    return bal

# =============================
# Ledger Posting Utilities
# =============================

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

# =============================
# Report Generator + KPIs
# =============================

class ReportGenerator:
    def __init__(self, entries: List[LedgerEntry], property_units: int, vacant_units: int, loan_payment: float = 0.0):
        self.entries = entries
        self.total_units = property_units
        self.vacant_units = vacant_units
        self.loan_payment = loan_payment

    def _filter(self, start: date, end: date) -> List[LedgerEntry]:
        return [e for e in self.entries if start <= e.date <= end]

    def income_statement(self, start: date, end: date) -> Dict[str, float]:
        entries = self._filter(start, end)
        rental_income = sum(e.credit - e.debit for e in entries if e.account == "Rental Income")
        other_income = sum(e.credit - e.debit for e in entries if "Income" in e.account and e.account != "Rental Income")
        operating_exp = sum(e.debit - e.credit for e in entries
                            if "Expense" in e.account and e.account not in ("Depreciation Expense", "Loan Interest Expense"))
        depreciation = sum(e.debit - e.credit for e in entries if e.account == "Depreciation Expense")
        interest = sum(e.debit - e.credit for e in entries if e.account == "Loan Interest Expense")
        egi = rental_income + other_income
        noi = egi - operating_exp
        net_income = noi - depreciation - interest
        return {"Rental Income": rental_income, "Other Income": other_income, "EGI": egi,
                "Operating Expenses": operating_exp, "NOI": noi, "Depreciation": depreciation,
                "Interest": interest, "Net Income": net_income}

    def cash_flow_indirect(self, start: date, end: date, opening_cash: Optional[float] = None) -> Dict:
        bal_start = account_balance(self.entries, up_to=(start - timedelta(days=1)))
        bal_end = account_balance(self.entries, up_to=end)
        is_stmt = self.income_statement(start, end)
        net_income = is_stmt["Net Income"]
        chg_ar = bal_end.get("Accounts Receivable", 0.0) - bal_start.get("Accounts Receivable", 0.0)
        chg_ap = bal_end.get("Accounts Payable", 0.0) - bal_start.get("Accounts Payable", 0.0)
        depreciation = is_stmt["Depreciation"]
        cfo = net_income + depreciation - chg_ar + chg_ap
        capex_out = sum(e.debit for e in self._filter(start, end) if e.account in ("Property", "Equipment"))
        cfi = -capex_out
        chg_deposits = bal_end.get("Security Deposit Liability", 0.0) - bal_start.get("Security Deposit Liability", 0.0)
        chg_loans = bal_end.get("Loan Payable", 0.0) - bal_start.get("Loan Payable", 0.0)
        cff = chg_deposits + chg_loans
        net_change_cash = cfo + cfi + cff
        if opening_cash is None:
            opening_cash = bal_start.get("Cash", 0.0)
        closing_calc = opening_cash + net_change_cash
        closing_gl = bal_end.get("Cash", 0.0)
        return {
            "Operating": {"Net Income": net_income, "Depreciation (add-back)": depreciation,
                          "Δ AR (subtract if increase)": -chg_ar, "Δ AP (add if increase)": chg_ap,
                          "Net Cash from Operating": cfo},
            "Investing": {"Capital Expenditures": cfi},
            "Financing": {"Δ Security Deposits": chg_deposits, "Δ Loans": chg_loans,
                          "Net Cash from Financing": cff},
            "Reconciliation": {"Opening Cash": opening_cash, "Net Change in Cash": net_change_cash,
                               "Closing Cash (calc)": closing_calc, "Closing Cash (GL)": closing_gl,
                               "Balanced": abs(closing_calc - closing_gl) < 1e-6}
        }

    def balance_sheet(self, as_of: date, beginning_retained_earnings: float = 0.0) -> Dict:
        bal = account_balance(self.entries, up_to=as_of)
        start_year = date(as_of.year, 1, 1)
        is_ytd = self.income_statement(start_year, as_of)
        ytd_ni = is_ytd["Net Income"]
        retained_earnings = beginning_retained_earnings + ytd_ni
        def amt(a): return bal.get(a, 0.0)
        assets_current = {"Cash": amt("Cash"), "Accounts Receivable": amt("Accounts Receivable")}
        assets_noncurrent = {"Property": amt("Property"), "Equipment": amt("Equipment"),
                             "Accumulated Depreciation": -amt("Accumulated Depreciation")}
        liab_current = {"Accounts Payable": -amt("Accounts Payable"),
                        "Security Deposit Liability": -amt("Security Deposit Liability")}
        liab_noncurrent = {"Loan Payable": -amt("Loan Payable")}
        equity = {"Owner Capital": -amt("Owner Capital"), "Retained Earnings": retained_earnings}
        total_assets = sum(assets_current.values()) + sum(assets_noncurrent.values())
        total_liab = sum(liab_current.values()) + sum(liab_noncurrent.values())
        total_equity = sum(equity.values())
        balanced = abs(total_assets - (total_liab + total_equity)) < 1e-6
        return {"Assets": {"Current": assets_current, "Non-current": assets_noncurrent},
                "Liabilities": {"Current": liab_current, "Non-current": liab_noncurrent},
                "Equity": equity,
                "Totals": {"Total Assets": total_assets, "Total Liabilities": total_liab,
                           "Total Equity": total_equity, "Liabilities + Equity": total_liab + total_equity,
                           "Balanced": balanced, "YTD Net Income": ytd_ni, "Retained Earnings": retained_earnings}}

    def kpis(self, start: date, end: date, avg_rent_per_unit: float, owner_equity: float) -> Dict[str, float]:
        is_stmt = self.income_statement(start, end)
        gpr = self.total_units * avg_rent_per_unit
        vacancy_loss = self.vacant_units * avg_rent_per_unit
        vacancy_pct = (vacancy_loss / gpr * 100.0) if gpr else 0.0
        egi = gpr - vacancy_loss
        opex_ratio = (is_stmt["Operating Expenses"] / egi * 100.0) if egi else 0.0
        dscr = (is_stmt["NOI"] / self.loan_payment) if self.loan_payment else float("inf")
        capex_out = sum(e.debit for e in self._filter(start, end) if e.account in ("Property", "Equipment"))
        capex_ratio = (capex_out / egi * 100.0) if egi else 0.0
        cash_on_cash = (is_stmt["Net Income"] / owner_equity * 100.0) if owner_equity else 0.0
        return {"GPR": gpr, "Vacancy Loss": vacancy_loss, "Vacancy Loss %": vacancy_pct, "EGI": egi,
                "NOI": is_stmt["NOI"], "OpEx Ratio %": opex_ratio, "DSCR": dscr,
                "CapEx Ratio %": capex_ratio, "Cash-on-Cash %": cash_on_cash}

# =============================
# Text-to-PDF helpers
# =============================

def add_page(pdf: PdfPages, title: str, lines: List[str], footer: Optional[str] = None):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4 portrait
    plt.axis('off')
    y = 0.96
    plt.text(0.5, y, title, ha='center', va='top', fontsize=14, fontweight='bold', family='monospace')
    y -= 0.04
    max_lines = 60
    body_lines = lines[:max_lines]
    txt = "\n".join(body_lines)
    plt.text(0.05, y, txt, ha='left', va='top', fontsize=9.5, family='monospace')
    if footer:
        plt.text(0.5, 0.02, footer, ha='center', va='bottom', fontsize=8, family='monospace')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)
    return lines[max_lines:]

def paginate_and_add(pdf: PdfPages, title: str, lines: List[str]):
    remainder = lines
    first = True
    page_num = 1
    while remainder:
        head = f"{title}" if first else f"{title} (cont. {page_num})"
        remainder = add_page(pdf, head, remainder)
        first = False
        page_num += 1

def format_kv_table(d: Dict, key_w: int = 32, val_w: int = 14) -> List[str]:
    lines = []
    for k, v in d.items():
        if isinstance(v, float):
            lines.append(f"{k:<{key_w}} {v:>{val_w}.2f}")
        else:
            lines.append(f"{k:<{key_w}} {str(v):>{val_w}}")
    return lines

def format_nested_table(d: Dict[str, Dict[str, float]], key_w: int = 28, val_w: int = 14) -> List[str]:
    lines = []
    for section, rows in d.items():
        lines.append(f"[{section}]")
        for k, v in rows.items():
            lines.append(f"  {k:<{key_w}} {v:>{val_w}.2f}")
        lines.append("")
    return lines

def format_ledger(entries: List[LedgerEntry]) -> List[str]:
    lines = []
    header = f"{'Date':<12}{'Account':<32}{'Debit':>14}{'Credit':>14}  Description"
    lines.append(header)
    lines.append("-" * len(header))
    for e in sorted(entries, key=lambda x: (x.date, x.account)):
        lines.append(f"{e.date.isoformat():<12}{e.account:<32}{e.debit:>14.2f}{e.credit:>14.2f}  {e.description or ''}")
    return lines

def format_trial_balance(entries: List[LedgerEntry]) -> List[str]:
    tb = defaultdict(lambda: {"debit": 0.0, "credit": 0.0})
    for e in entries:
        tb[e.account]["debit"] += e.debit
        tb[e.account]["credit"] += e.credit
    lines = []
    header = f"{'Account':<40}{'Dr':>14}{'Cr':>14}"
    lines.append(header)
    lines.append("-"*len(header))
    total_dr = total_cr = 0.0
    for acct in sorted(tb.keys()):
        dr, cr = tb[acct]["debit"], tb[acct]["credit"]
        total_dr += dr
        total_cr += cr
        lines.append(f"{acct:<40}{dr:>14.2f}{cr:>14.2f}")
    lines.append("-"*len(header))
    lines.append(f"{'TOTAL':<40}{total_dr:>14.2f}{total_cr:>14.2f}")
    return lines

# =============================
# Simulation / Data Build
# =============================

# random.seed(42)
# PROPERTY_ID = "PROP-001"
# UTILITIES_FLAT = 2000
# DEPOSIT_MULT = 2

# def build_units_24() -> List[Tuple[str, int]]:
#     return [("1BR", 10000)] * 8 + [("2BR", 20000)] * 8 + [("3BR", 30000)] * 4 + [("4BR", 40000)] * 4

# unit_specs = build_units_24()
# unit_ids = [f"U{str(i+1).zfill(2)}" for i in range(24)]
# units = list(zip(unit_ids, unit_specs))
# vacant_units = set(random.sample(unit_ids, 4))
# occupied_units = [u for u in unit_ids if u not in vacant_units]

# tenants_active = [f"TEN-{str(i+1).zfill(3)}" for i in range(20)]
# new_tenants = set(random.sample(tenants_active, 2))
# moving_out_next_month = set(random.sample(sorted(set(tenants_active) - new_tenants), 2))

# former_tenants = [("TEN-901", 0.30), ("TEN-902", 0.40)]
# sample_rents_for_formers = [20000, 30000]

# unit_type_by_id = {uid: spec[0] for uid, spec in units}
# unit_rent_by_id = {uid: spec[1] for uid, spec in units}
# assigned_pairs = list(zip(tenants_active, occupied_units[:20]))

# ledger = Ledger(db=None)
# all_entries: List[LedgerEntry] = []

# for tenant_id, unit_id in assigned_pairs:
#     rent = unit_rent_by_id[unit_id]
#     items = [
#         LineItem.create(f"{unit_type_by_id[unit_id]} Rent", rent, "rent"),
#         LineItem.create("Utilities", UTILITIES_FLAT, "utilities"),
#     ]
#     if tenant_id in new_tenants:
#         items.append(LineItem.create("Security Deposit (2 months)", DEPOSIT_MULT * rent, "deposit"))
#     inv = Invoice.create(PROPERTY_ID, tenant_id, date(2025,10,1), date(2025,10,5), items,unit_id)
#     all_entries += ledger.post_invoice_to_ledger(inv)
#     all_entries += ledger.post_payment_to_ledger(inv, inv.total_amount, date(2025,10,4))

# all_entries.append(LedgerEntry.create(date=date(2025,10,12), account="Maintenance Expense", debit=350.00,
#                                       description="Common area repainting", property_id=PROPERTY_ID))
# all_entries.append(LedgerEntry.create(date=date(2025,10,12), account="Cash", credit=350.00,
#                                       description="Paid contractor", property_id=PROPERTY_ID))

# for (former_id, ratio), rent in zip(former_tenants, sample_rents_for_formers):
#     deposit_amount = DEPOSIT_MULT * rent
#     all_entries += ledger.refund_deposit_with_deduction(former_id, PROPERTY_ID, deposit_amount, ratio, date(2025,10,10))

# all_entries += ledger.post_capex(date(2025,10,15), PROPERTY_ID, 3000.00)
# all_entries += ledger.post_monthly_depreciation(date(2025,10,31), PROPERTY_ID, 1200.00)

# period_start = date(2025,10,1)
# period_end = date(2025,10,31)
# loan_payment_assumption = 10000.0

# rep = ReportGenerator(all_entries, property_units=24, vacant_units=len(vacant_units), loan_payment=loan_payment_assumption)

# is_data = rep.income_statement(period_start, period_end)
# cf_data = rep.cash_flow_indirect(period_start, period_end)
# bs_data = rep.balance_sheet(period_end, beginning_retained_earnings=0.0)
# kpis = rep.kpis(period_start, period_end, avg_rent_per_unit=20000.0, owner_equity=3_000_000.0)

# # =============================
# # Build PDF
# # =============================

# pdf_path = "Property_Financial_Report_Oct_2025.pdf"
# with PdfPages(pdf_path) as pdf:
#     scenario_lines = [
#         f"Property ID: {PROPERTY_ID}",
#         f"Period: {period_start.isoformat()} to {period_end.isoformat()}",
#         f"Units Total: 24",
#         f"Vacant Units: {len(vacant_units)}  -> {sorted(list(vacant_units))}",
#         f"Occupied Units: {len(occupied_units)}",
#         f"New Tenants (Deposit collected): {sorted(list(new_tenants))}",
#         f"Moving Out Next Month: {sorted(list(moving_out_next_month))}",
#         f"Former Tenants Refunded (with deductions): {[f'{tid} ({int(r*100)}%)' for tid, r in former_tenants]}",
#     ]
#     paginate_and_add(pdf, "Property Financial Report — October 2025 (Scenario Summary)", scenario_lines)

#     journal_lines = format_ledger(all_entries)
#     paginate_and_add(pdf, "General Journal — Detailed", journal_lines)

#     tb_lines = format_trial_balance(all_entries)
#     paginate_and_add(pdf, "Trial Balance", tb_lines)

#     is_lines = [
#         "INCOME STATEMENT (Detailed)",
#         "",
#         *format_kv_table({
#             "Rental Income": is_data["Rental Income"],
#             "Other Income": is_data["Other Income"],
#             "EGI (Effective Gross Income)": is_data["EGI"],
#             "Operating Expenses": is_data["Operating Expenses"],
#             "NOI": is_data["NOI"],
#             "Depreciation": is_data["Depreciation"],
#             "Interest": is_data["Interest"],
#             "Net Income": is_data["Net Income"],
#         })
#     ]
#     paginate_and_add(pdf, "Income Statement — October 2025", is_lines)

#     cf_lines = ["CASH FLOW STATEMENT (Indirect) — October 2025", "", "[Operating Activities]"]
#     cf_lines += format_kv_table(cf_data["Operating"])
#     cf_lines += ["", "[Investing Activities]"]
#     cf_lines += format_kv_table(cf_data["Investing"])
#     cf_lines += ["", "[Financing Activities]"]
#     cf_lines += format_kv_table(cf_data["Financing"])
#     cf_lines += ["", "[Reconciliation]"]
#     cf_lines += [f"{k:<32} {v:>14.2f}" if isinstance(v, (int, float)) else f"{k:<32} {str(v):>14}" for k, v in cf_data["Reconciliation"].items()]
#     paginate_and_add(pdf, "Cash Flow (Indirect) — October 2025", cf_lines)

#     bs_lines = ["BALANCE SHEET (Detailed) — as of 2025-10-31", ""]
#     bs_lines += format_nested_table(bs_data["Assets"])
#     bs_lines += format_nested_table(bs_data["Liabilities"])
#     bs_lines += ["[Equity]"]
#     for k, v in bs_data["Equity"].items():
#         bs_lines.append(f"  {k:<28} {v:>14.2f}")
#     bs_lines += ["", "[Totals]"]
#     for k, v in bs_data["Totals"].items():
#         bs_lines.append(f"{k:<32} {v:>14.2f}" if isinstance(v, (int, float)) else f"{k:<32} {str(v):>14}")
#     paginate_and_add(pdf, "Balance Sheet — Detailed", bs_lines)

#     kpi_lines = [
#         "PROPERTY KPIs — October 2025",
#         "",
#         *format_kv_table(kpis),
#         "",
#         "Notes:",
#         "- GPR assumes average market rent per unit for the month.",
#         "- Vacancy Loss % = Vacancy Loss / GPR.",
#         "- EGI = GPR - Vacancy Loss (no concessions or bad debt modeled).",
#         "- NOI excludes depreciation and interest.",
#         "- DSCR = NOI / Debt Service (loan payment assumption applied).",
#         "- CapEx Ratio = CapEx / EGI.",
#         "- Cash-on-Cash uses Net Income / Owner Equity.",
#     ]
#     paginate_and_add(pdf, "KPIs — GPR, Vacancy, EGI, DSCR, OpEx, etc.", kpi_lines)

# # =============================
# # Build Excel Workbook
# # =============================

# excel_path = "Property_Financial_Report_Oct_2025.xlsx"

# # Prepare DataFrames
# journal_df = pd.DataFrame([{
#     "Date": e.date.isoformat(),
#     "Account": e.account,
#     "Debit": e.debit,
#     "Credit": e.credit,
#     "Description": e.description,
#     "Invoice ID": e.invoice_id,
#     "Line Item ID": e.line_item_id,
#     "Property ID": e.property_id,
#     "Tenant ID": e.tenant_id,
# } for e in sorted(all_entries, key=lambda x: (x.date, x.account))])

# # Trial Balance DF
# tb_map = defaultdict(lambda: {"Dr": 0.0, "Cr": 0.0})
# for e in all_entries:
#     tb_map[e.account]["Dr"] += e.debit
#     tb_map[e.account]["Cr"] += e.credit
# tb_df = pd.DataFrame([{"Account": k, "Dr": v["Dr"], "Cr": v["Cr"]} for k, v in tb_map.items()]).sort_values("Account")

# # Income Statement DF
# is_df = pd.DataFrame([{"Metric": k, "Amount": v} for k, v in is_data.items()])

# # Cash Flow DF (flatten)
# def flatten_cf(cf: Dict) -> List[Dict]:
#     rows = []
#     for sec in ["Operating", "Investing", "Financing", "Reconciliation"]:
#         for k, v in cf[sec].items():
#             rows.append({"Section": sec, "Item": k, "Amount": float(v) if isinstance(v, (int, float)) else v})
#     return rows
# cf_df = pd.DataFrame(flatten_cf(cf_data))

# # Balance Sheet DF (Assets/Liabilities/Equity/Totals)
# def nested_to_rows(section_name: str, d: Dict[str, Dict[str, float]]) -> List[Dict]:
#     rows = []
#     for grp, rows_dict in d.items():
#         for k, v in rows_dict.items():
#             rows.append({"Section": section_name, "Group": grp, "Account": k, "Amount": v})
#     return rows

# bs_rows = []
# bs_rows += nested_to_rows("Assets", bs_data["Assets"])
# bs_rows += nested_to_rows("Liabilities", bs_data["Liabilities"])
# bs_equity_rows = [{"Section": "Equity", "Group": "", "Account": k, "Amount": v} for k, v in bs_data["Equity"].items()]
# bs_totals_rows = [{"Section": "Totals", "Group": "", "Account": k, "Amount": v} for k, v in bs_data["Totals"].items()]
# bs_df = pd.DataFrame(bs_rows + bs_equity_rows + bs_totals_rows)

# # KPIs DF
# kpi_df = pd.DataFrame([{"KPI": k, "Value": v} for k, v in kpis.items()])

# with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
#     journal_df.to_excel(writer, sheet_name="Journal", index=False)
#     tb_df.to_excel(writer, sheet_name="Trial Balance", index=False)
#     is_df.to_excel(writer, sheet_name="Income Statement", index=False)
#     cf_df.to_excel(writer, sheet_name="Cash Flow", index=False)
#     bs_df.to_excel(writer, sheet_name="Balance Sheet", index=False)
#     kpi_df.to_excel(writer, sheet_name="KPIs", index=False)

# (pdf_path, excel_path)
