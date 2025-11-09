#!/usr/bin/env python3
"""
OPTIMIZED 3-Year Property Management Financial Test (Upgraded & Fixed)

Additions (kept):
1) Rent inflation per year (+3–6%)
2) Monthly occupancy tracking
3) Vacancy loss ledger entries (per vacant month)
4) Automatic lease turnover (end old lease, refund deposit with deduction, new tenant after 1–6 months)
5) Utility breakdown (Water/Electricity/Garbage) in invoices & ledgers
6) Deposit lifecycle in ledger: issue/receive at start, refund minus deduction at end

Performance:
- Bulk inserts
- Precompute in memory
- Ledger-only financial reporting
- Timing summaries

Fixes/Improvements:
- Persist ended leases to DB (distinct('status') shows 'active' + 'ended')
- Single canonical lease store (self.leases_docs) with real dicts referenced everywhere
- Consistent ObjectId usage across all collections
- Turnover-created tenants/leases included in bulk insert
- Removed stray early return; made turnover updates deterministic
- Unique invoice_number suffix to avoid collisions
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple
from plugins.pms.accounting.chart_of_accounts import resolve_account, CHART_OF_ACCOUNTS
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import random
import time

timings: Dict[str, float] = {}


def _rand_suffix(n: int = 4) -> str:
    return "".join(random.choice("0123456789ABCDEFGHJKMNPQRSTUVWXYZ") for _ in range(n))


class OptimizedFinancialTest:
    """Ultra-fast bulk data generation with ledger-based reporting (Upgraded & Fixed)"""

    def __init__(self, client, db_name="pms_financial_optimized"):
        self.client = client
        self.db = client[db_name]

        # In-memory canonical docs that will be bulk-inserted
        self.property_id = ObjectId()
        self.property_doc: Dict = {}
        self.units_docs: List[Dict] = []
        self.tenants_docs: List[Dict] = []
        self.leases_docs: List[Dict] = []

        # Handy mirrors (lightweight lookups)
        self.units: List[Dict] = []    # each: {"id": ObjectId, "number": str, "rent": float}
        self.tenants: List[Dict] = []  # each: {"id": ObjectId, "name": str, "unit_idx": int}

        # Transaction batches
        self.invoices_batch: List[Dict] = []
        self.payments_batch: List[Dict] = []
        self.ledger_batch: List[Dict] = []
        self.maintenance_batch: List[Dict] = []

        # Occupancy: {'YYYY-MM': {unit_id (str): bool}}
        self.occupancy_by_month: Dict[str, Dict[str, bool]] = {}

        random.seed(42)

    # ---------------------------- Utilities ---------------------------------
    def time_operation(name):
        def decorator(func):
            async def wrapper(self, *args, **kwargs):
                start = time.time()
                result = await func(self, *args, **kwargs)
                elapsed = time.time() - start
                timings[name] = elapsed
                print(f"  ⏱️  {name}: {elapsed:.2f}s")
                return result
            return wrapper
        return decorator

    # ---------------------------- Setup DB ----------------------------------
    @time_operation(name="Database Setup")
    async def setup_database(self):
        print("\n" + "="*80)
        print("OPTIMIZED 3-YEAR FINANCIAL TEST — UPGRADED & FIXED")
        print("="*80)

        collections = [
            'properties', 'units', 'property_tenants', 'property_leases',
            'property_invoices', 'property_payments', 'property_ledger_entries',
            'maintenance_records'
        ]
        for coll in collections:
            await self.db[coll].delete_many({})
        print("✓ Database cleaned")

    # ------------------------- Static Data Gen ------------------------------
    def generate_static_data(self):
        print("\n📦 Generating static data in memory...")

        # Property
        self.property_doc = {
            "_id": self.property_id,
            "name": "Sunset Apartments",
            "location": "Westlands, Nairobi",
            "owner_id": ObjectId(),
            "billing_cycle": {"due_day": 5, "billing_day": 1},
            "integrations": {"sms": {"enabled": True}, "email": {"enabled": True}},
            "created_at": datetime(2022, 1, 1, tzinfo=timezone.utc)
        }

        # Units (10) with ObjectId _id
        unit_configs = [
            {"number": "101", "rent": 18000}, {"number": "102", "rent": 18000},
            {"number": "103", "rent": 25000}, {"number": "201", "rent": 19000},
            {"number": "202", "rent": 19000}, {"number": "203", "rent": 26000},
            {"number": "301", "rent": 20000}, {"number": "302", "rent": 27000},
            {"number": "303", "rent": 35000}, {"number": "PH1", "rent": 50000},
        ]
        self.units_docs = []
        self.units = []
        for cfg in unit_configs:
            unit_id = ObjectId()
            self.units_docs.append({
                "_id": unit_id,
                "property_id": self.property_id,
                "unitNumber": cfg["number"],
                "rentAmount": cfg["rent"],
                "status": "occupied",
            })
            self.units.append({"id": unit_id, "number": cfg["number"], "rent": cfg["rent"]})

        # Tenants (10) with ObjectId _id
        self.tenants_docs = []
        self.tenants = []
        tenant_names = [
            "James Kamau", "Mary Wanjiku", "Peter Ochieng", "Sarah Akinyi",
            "David Mwangi", "Grace Njeri", "John Kipchoge", "Lucy Adhiambo",
            "Michael Otieno", "Anne Wambui"
        ]
        for i, name in enumerate(tenant_names):
            tenant_id = ObjectId()
            self.tenants_docs.append({
                "_id": tenant_id,
                "property_id": self.property_id,
                "full_name": name,
                "email": f"tenant{i+1}@example.com",
                "phone": f"+25471234{i+1:04d}",
                "credit_balance": 0.0
            })
            self.tenants.append({"id": tenant_id, "name": name, "unit_idx": i})

        # Leases (10) — canonical store
        self.leases_docs = []
        for i, unit in enumerate(self.units):
            lease_id = ObjectId()
            deposit_amount = unit["rent"]  # 1 month deposit
            lease_doc = {
                "_id": lease_id,
                "property_id": self.property_id,
                "tenant_id": self.tenants[i]["id"],
                "units_id": [unit["id"]],
                "status": "active",
                "lease_terms": {
                    "rent_amount": unit["rent"],
                    "start_date": datetime(2022, 1, 1, tzinfo=timezone.utc),
                    "end_date": datetime(2024, 12, 31, tzinfo=timezone.utc),
                    "deposit_amount": deposit_amount
                },
                "tenant_details": {
                    "full_name": self.tenants[i]["name"],
                    "email": f"tenant{i+1}@example.com",
                    "phone": f"+25471234{i+1:04d}"
                },
                "utilities": [
                    {"name": "Water", "billingBasis": "metered", "rate": 50.0},
                    {"name": "Garbage", "billingBasis": "monthly", "rate": 500.0}
                ]
            }
            self.leases_docs.append(lease_doc)

            # Initial deposit invoice + payment + ledger
            dep_invoice = self.generate_invoice_data(
                year=2022, month=1, unit={"id": unit["id"], "number": unit["number"], "rent": unit["rent"]},
                tenant={"id": self.tenants[i]["id"], "name": self.tenants[i]["name"]},
                is_deposit=True
            )
            self.invoices_batch.append(dep_invoice)

            dep_payment_date = self.generate_payment_date(2022, 1)
            dep_payment = {
                "_id": ObjectId(),
                "invoice_id": dep_invoice["_id"],
                "tenant_id": dep_invoice["tenant_id"],
                "amount": dep_invoice["total_amount"],
                "payment_method": "mpesa",
                "reference": f"DEP-{unit['number']}",
                "payment_date": dep_payment_date,
                "created_at": dep_payment_date
            }
            self.payments_batch.append(dep_payment)
            self.ledger_batch.extend(self.generate_ledger_entries(dep_invoice, dep_payment["amount"], dep_payment_date))

        print(f"  ✓ Generated: 1 property, {len(self.units_docs)} units, {len(self.tenants_docs)} tenants, {len(self.leases_docs)} leases")

        return self.property_doc, self.units_docs, self.tenants_docs, self.leases_docs

    # ------------------- Rent Inflation Helper -----------------------------
    def _adjust_rent_with_inflation(self, base_rent: float, year: int) -> float:
        if year <= 2022:
            return base_rent
        rate = random.uniform(0.03, 0.06)
        return round(base_rent * (1 + rate), -2)

    # ----------------------- Invoice Data ----------------------------------
    def generate_invoice_data(self, year: int, month: int, unit: dict, tenant: dict, is_deposit: bool = False) -> dict:
        invoice_id = ObjectId()

        rent = unit["rent"]
        # Utility breakdown
        utility_water = round(random.uniform(200, 800), 2)
        utility_electricity = round(random.uniform(400, 1200), 2)
        utility_garbage = 500.00
        utilities_total = utility_water + utility_electricity + utility_garbage
        deposit_amount = rent if is_deposit else 0.0

        line_items = [
            {"id": ObjectId(), "description": "Monthly Rent", "amount": rent, "category": "rent"},
            {"id": ObjectId(), "description": "Water", "amount": utility_water, "category": "utility_water"},
            {"id": ObjectId(), "description": "Electricity", "amount": utility_electricity, "category": "utility_electricity"},
            {"id": ObjectId(), "description": "Garbage Collection", "amount": utility_garbage, "category": "utility_garbage"},
        ]
        if is_deposit:
            line_items.append({"id": ObjectId(), "description": "Security Deposit", "amount": deposit_amount, "category": "deposit"})

        total_amount = rent + utilities_total + deposit_amount

        return {
            "_id": invoice_id,
            "invoice_number": f"INV-{year}-{month:02d}-{unit['number']}-{_rand_suffix()}",
            "tenant_id": tenant["id"],
            "property_id": self.property_id,
            "units_id": [unit["id"]],
            "date_issued": datetime(year, month, 1, tzinfo=timezone.utc),
            "due_date": datetime(year, month, 5, tzinfo=timezone.utc),
            "total_amount": total_amount,
            "total_paid": 0.0,
            "balance_amount": total_amount,
            "status": "ready",
            "meta": {"billing_period": f"{year}-{month:02d}"},
            "line_items": line_items,
            "balance_forwarded": False
        }

    # ----------------------- Payment Date ----------------------------------
    def generate_payment_date(self, year: int, month: int) -> datetime:
        r = random.random()
        if r < 0.70:
            day = random.randint(1, 7)
            return datetime(year, month, day, tzinfo=timezone.utc)
        elif r < 0.85:
            day = random.randint(8, 15)
            return datetime(year, month, day, tzinfo=timezone.utc)
        elif r < 0.95:
            day = min(random.randint(16, 28), 28)
            return datetime(year, month, day, tzinfo=timezone.utc)
        else:
            next_month = month + 1 if month < 12 else 1
            next_year = year if month < 12 else year + 1
            day = random.randint(5, 15)
            return datetime(next_year, next_month, day, tzinfo=timezone.utc)

    # --------------------- Ledger Entries ----------------------------------
    def generate_ledger_entries_old(
    self,
    invoice: dict,
    payment_amount: float,
    payment_date: datetime
) -> List[dict]:
        """
        Create ledger entries with Accounts Receivable broken down by component.

        - On invoice issue:
            * credit income / liability per line item (as before)
            * debit AR subaccount per line item (e.g. Rent Receivable 1201)
        - On payment:
            * debit Cash (single entry) for payment_amount
            * credit AR subaccounts according to allocation priority until payment_amount exhausted
        """

        entries: List[dict] = []

        # Mapping from invoice line category -> (Account Name, Account Code, AR subaccount name, AR code)
        ar_map = {
            "rent": ("Rent Income", "4100", "Rent Receivable", "1201"),
            "utility_water": ("Water Income", "4210", "Water Receivable", "1202"),
            "utility_electricity": ("Electricity Income", "4220", "Electricity Receivable", "1203"),
            "utility_garbage": ("Garbage Income", "4230", "Garbage Receivable", "1204"),
            "deposit": ("Tenant Deposit (not income)", "2200", "Deposit Receivable", "1205"),
            # fallback
            "other": ("Utility/Other Income", "4200", "Other Receivable", "1210"),
        }

        # ---- 1) Invoice issuance: credit revenue/liability and debit AR-subaccount per line item ----
        for item in invoice["line_items"]:
            category = item.get("category", "other")
            amount = float(item.get("amount", 0.0))

            # get accounts (fall back to 'other' mapping)
            acct_name, acct_code, ar_name, ar_code = ar_map.get(category, ar_map["other"])

            # Credit revenue / liability (same as before)
            entries.append({
                "_id": ObjectId(),
                "date": invoice["date_issued"],
                "account": acct_name,
                "account_code": acct_code,
                "debit": 0.0,
                "credit": amount,
                "category": category,
                "description": item.get("description", ""),
                "invoice_id": str(invoice["_id"]),
                "tenant_id": str(invoice["tenant_id"]),
                "property_id": str(self.property_id),
                "transaction_type": "invoice_issue"
            })

            # Debit AR subaccount for this line item (separate AR accounts)
            entries.append({
                "_id": ObjectId(),
                "date": invoice["date_issued"],
                "account": ar_name,
                "account_code": ar_code,
                "debit": amount,
                "credit": 0.0,
                "category": f"{category}_receivable",
                "description": f"Receivable - {item.get('description','')}",
                "invoice_id": str(invoice["_id"]),
                "tenant_id": str(invoice["tenant_id"]),
                "property_id": str(self.property_id),
                "transaction_type": "invoice_issue"
            })

        # ---- 2) Payment handling: debit Cash, credit AR subaccounts (allocation) ----
        # Create a cash debit for the actual payment amount (if any)
        payment_amount = float(payment_amount or 0.0)
        if payment_amount > 0:
            entries.append({
                "_id": ObjectId(),
                "date": payment_date,
                "account": "Cash",
                "account_code": "1010",
                "debit": payment_amount,
                "credit": 0.0,
                "category": "payment",
                "description": f"Payment for {invoice['invoice_number']}",
                "invoice_id": str(invoice["_id"]),
                "tenant_id": str(invoice["tenant_id"]),
                "property_id": str(self.property_id),
                "transaction_type": "payment_received"
            })

            # Allocation order (configurable). Adjust if you prefer a different priority.
            allocation_priority = ["rent", "utility_electricity", "utility_water", "utility_garbage", "other", "deposit"]

            remaining = payment_amount

            # Pre-build a list of invoice line items keyed by category to know their amounts
            lines_by_cat = []
            for item in invoice["line_items"]:
                lines_by_cat.append({
                    "category": item.get("category", "other"),
                    "amount": float(item.get("amount", 0.0)),
                    "description": item.get("description", "")
                })

            # For deterministic allocation, iterate priority and within that the line occurrences
            for cat in allocation_priority:
                if remaining <= 0:
                    break
                for line in [l for l in lines_by_cat if l["category"] == cat]:
                    if remaining <= 0:
                        break
                    alloc = min(remaining, line["amount"])
                    if alloc <= 0:
                        continue

                    # Credit the matching AR subaccount by allocated amount
                    # Map category to ar subaccount name/code as above
                    _, _, ar_name, ar_code = ar_map.get(cat, ar_map["other"])

                    entries.append({
                        "_id": ObjectId(),
                        "date": payment_date,
                        "account": ar_name,
                        "account_code": ar_code,
                        "debit": 0.0,
                        "credit": alloc,
                        "category": f"{cat}_payment",
                        "description": f"Payment allocation to {line['description']}",
                        "invoice_id": str(invoice["_id"]),
                        "tenant_id": str(invoice["tenant_id"]),
                        "property_id": str(self.property_id),
                        "transaction_type": "payment_allocation"
                    })

                    remaining = round(remaining - alloc, 2)

            # If any remaining (shouldn't happen normally), allocate to Accounts Receivable master (catch-all)
            if remaining > 0.0001:
                entries.append({
                    "_id": ObjectId(),
                    "date": payment_date,
                    "account": "Accounts Receivable",
                    "account_code": "1200",
                    "debit": 0.0,
                    "credit": remaining,
                    "category": "payment_allocation_residual",
                    "description": "Residual payment allocation",
                    "invoice_id": str(invoice["_id"]),
                    "tenant_id": str(invoice["tenant_id"]),
                    "property_id": str(self.property_id),
                    "transaction_type": "payment_allocation"
                })

        return entries
    def generate_ledger_entries(self, invoice: dict, payment_amount: float, payment_date: datetime) -> List[dict]:
        """Generate double-entry ledger entries dynamically using CHART_OF_ACCOUNTS."""

        entries = []

        # --------------------------
        # 1. Invoice issued
        # --------------------------
        for item in invoice["line_items"]:
            category = item.get("category", "misc_income")
            mapping = resolve_account(category)

            # Credit revenue
            entries.append({
                "_id": ObjectId(),
                "date": invoice["date_issued"],
                "account": mapping["account"],
                "account_code": mapping["code"],
                "debit": 0.0,
                "credit": item["amount"],
                "category": category,
                "description": item.get("description", ""),
                "invoice_id": str(invoice["_id"]),
                "tenant_id": str(invoice["tenant_id"]),
                "property_id": str(self.property_id),
                "transaction_type": "invoice_issue"
            })

            # Debit the related receivable (based on income type)
            receivable_map = {
                "Income": f"ar_{category}" if f"ar_{category}" in CHART_OF_ACCOUNTS else "accounts_receivable",
                "Contra-Income": "ar_adjustment"
            }
            receivable_key = receivable_map.get(mapping["type"], "accounts_receivable")
            receivable = CHART_OF_ACCOUNTS.get(receivable_key, CHART_OF_ACCOUNTS["accounts_receivable"])

            entries.append({
                "_id": ObjectId(),
                "date": invoice["date_issued"],
                "account": receivable["account"],
                "account_code": receivable["code"],
                "debit": item["amount"],
                "credit": 0.0,
                "category": category,
                "description": f"Receivable for {invoice.get('invoice_number', 'N/A')}",
                "invoice_id": str(invoice["_id"]),
                "tenant_id": str(invoice["tenant_id"]),
                "property_id": str(self.property_id),
                "transaction_type": "invoice_issue"
            })

        # --------------------------
        # 2. Payment received
        # --------------------------
        entries.append({
            "_id": ObjectId(),
            "date": payment_date,
            "account": CHART_OF_ACCOUNTS["cash"]["account"],
            "account_code": CHART_OF_ACCOUNTS["cash"]["code"],
            "debit": payment_amount,
            "credit": 0.0,
            "category": "payment",
            "description": f"Payment received for {invoice.get('invoice_number', 'N/A')}",
            "invoice_id": str(invoice["_id"]),
            "tenant_id": str(invoice["tenant_id"]),
            "property_id": str(self.property_id),
            "transaction_type": "payment_received"
        })

        entries.append({
            "_id": ObjectId(),
            "date": payment_date,
            "account": CHART_OF_ACCOUNTS["accounts_receivable"]["account"],
            "account_code": CHART_OF_ACCOUNTS["accounts_receivable"]["code"],
            "debit": 0.0,
            "credit": payment_amount,
            "category": "payment",
            "description": f"Payment applied to {invoice.get('invoice_number', 'N/A')}",
            "invoice_id": str(invoice["_id"]),
            "tenant_id": str(invoice["tenant_id"]),
            "property_id": str(self.property_id),
            "transaction_type": "payment_received"
        })

        return entries
    # ------------------ Maintenance Ledger ---------------------------------
    def generate_maintenance_ledger(self, amount: float, description: str, date: datetime, unit_id: ObjectId) -> dict:
        return {
            "_id": ObjectId(),
            "date": date,
            "account": "Maintenance & Repairs", "account_code": "5100",
            "debit": amount, "credit": 0.0,
            "category": "maintenance", "description": description,
            "property_id": self.property_id,
            "transaction_type": "expense",
            "meta": {"unit_id": unit_id}
        }

    # -------------- Helpers for turnover / vacancy -------------------------
    def _record_vacancy_loss_for_month(self, year: int, month: int, unit_rent: float):
        self.ledger_batch.append({
            "_id": ObjectId(),
            "date": datetime(year, month, 28, tzinfo=timezone.utc),
            "account": "Vacancy Loss", "account_code": "5200",
            "debit": unit_rent, "credit": 0.0,
            "category": "vacancy_loss",
            "description": "Missed rent due to vacancy",
            "property_id": self.property_id,
            "transaction_type": "vacancy_loss",
        })

    def _end_lease_and_refund(self, lease_doc: Dict, end_year: int, end_month: int) -> datetime:
        lease_doc["status"] = "ended"
        end_date = datetime(end_year, end_month, 28, tzinfo=timezone.utc)

        deposit_amount = lease_doc["lease_terms"]["deposit_amount"]
        deduction_pct = random.uniform(0.05, 0.25)
        maintenance_deduction = round(deposit_amount * deduction_pct, 2)
        refund_balance = round(deposit_amount - maintenance_deduction, 2)

        tenant_id = lease_doc["tenant_id"]

        # Deduction as income
        self.ledger_batch.append({
            "_id": ObjectId(),
            "date": end_date,
            "account": "Maintenance Income", "account_code": "4300",
            "debit": 0.0, "credit": maintenance_deduction,
            "category": "maintenance_income",
            "description": f"Deposit deduction {deduction_pct:.0%}",
            "tenant_id": tenant_id,
            "property_id": self.property_id,
            "transaction_type": "deposit_deduction",
        })

        # Refund (debit liability, credit cash)
        self.ledger_batch.extend([
            {
                "_id": ObjectId(),
                "date": end_date,
                "account": "Tenant Deposit Liability", "account_code": "2200",
                "debit": refund_balance, "credit": 0.0,
                "category": "deposit_refund",
                "description": "Deposit refund after deductions",
                "tenant_id": tenant_id,
                "property_id": self.property_id,
                "transaction_type": "deposit_refund",
            },
            {
                "_id": ObjectId(),
                "date": end_date,
                "account": "Cash", "account_code": "1010",
                "debit": 0.0, "credit": refund_balance,
                "category": "deposit_refund",
                "description": "Refund paid to tenant",
                "tenant_id": tenant_id,
                "property_id": self.property_id,
                "transaction_type": "deposit_refund",
            },
        ])
        return end_date

    def _create_new_lease_after_vacancy(self, unit: Dict, start_date: datetime):
        if start_date.year > 2024:
            return None  # out of reporting horizon

        # New tenant
        new_tenant_id = ObjectId()
        self.tenants_docs.append({
            "_id": new_tenant_id,
            "property_id": self.property_id,
            "full_name": f"Tenant_{unit['number']}_{start_date.year}",
            "email": f"{unit['number'].lower()}_{start_date.year}@example.com",
            "phone": f"+2547{random.randint(10000000, 99999999)}",
            "credit_balance": 0.0
        })

        # Market-adjusted rent
        new_rent = round(unit["rent"] * random.uniform(0.95, 1.15), -2)
        deposit_amount = new_rent

        new_lease_id = ObjectId()
        lease_doc = {
            "_id": new_lease_id,
            "property_id": self.property_id,
            "tenant_id": new_tenant_id,
            "units_id": [unit["id"]],
            "status": "active",
            "lease_terms": {
                "rent_amount": new_rent,
                "start_date": start_date,
                "end_date": datetime(2024, 12, 31, tzinfo=timezone.utc),
                "deposit_amount": deposit_amount
            },
            "tenant_details": {
                "full_name": f"Tenant_{unit['number']}_{start_date.year}",
                "email": f"{unit['number'].lower()}_{start_date.year}@example.com",
                "phone": f"+2547{random.randint(10000000, 99999999)}"
            },
            "utilities": [
                {"name": "Water", "billingBasis": "metered", "rate": 50.0},
                {"name": "Garbage", "billingBasis": "monthly", "rate": 500.0}
            ]
        }
        self.leases_docs.append(lease_doc)

        # Deposit invoice + payment + ledger for the new lease
        dep_invoice = self.generate_invoice_data(
            start_date.year, start_date.month,
            unit={"id": unit["id"], "number": unit["number"], "rent": new_rent},
            tenant={"id": new_tenant_id}, is_deposit=True
        )
        self.invoices_batch.append(dep_invoice)

        dep_payment_date = start_date + timedelta(days=random.randint(0, 5))
        dep_payment = {
            "_id": ObjectId(),
            "invoice_id": dep_invoice["_id"],
            "tenant_id": new_tenant_id,
            "amount": dep_invoice["total_amount"],
            "payment_method": "mpesa",
            "reference": f"DEP-{unit['number']}-{start_date.year}{start_date.month:02d}",
            "payment_date": dep_payment_date,
            "created_at": dep_payment_date
        }
        self.payments_batch.append(dep_payment)
        self.ledger_batch.extend(self.generate_ledger_entries(dep_invoice, dep_payment["amount"], dep_payment_date))

        print(f"🏠 New tenant for unit {unit['number']} starting {start_date.date()} (rent KES {new_rent:,.0f})")
        return lease_doc

    # --------------------- All Transactions --------------------------------
    def _iter_lease_docs_for_unit(self, unit_id: ObjectId):
        """Yield live references to canonical lease docs for a given unit."""
        for ld in self.leases_docs:
            if unit_id in ld.get("units_id", []):
                yield ld

    def _month_span(self, year: int, month: int, months: int) -> List[Tuple[int, int]]:
        res = []
        y, m = year, month
        for _ in range(months):
            m += 1
            if m > 12:
                m = 1; y += 1
            res.append((y, m))
        return res

    def generate_all_transactions(self):
        print("\n💰 Generating all transactions (2022-2024)...")
        start = time.time()

        years_months = [
            (2022, range(1, 13)),
            (2023, range(1, 13)),
            (2024, range(1, 7)),  # Invoices/payments through June; turnover may post deposits later in 2024
        ]

        total_invoices = total_payments = total_ledger = 0

        for year, months in years_months:
            for month in months:
                ym_key = f"{year}-{month:02d}"
                self.occupancy_by_month.setdefault(ym_key, {})

                for i, unit in enumerate(self.units):
                    active_lease_doc = None
                    for ld in self._iter_lease_docs_for_unit(unit["id"]):
                        if ld["status"] != "active":
                            continue
                        start_date = ld["lease_terms"]["start_date"]
                        end_date = ld["lease_terms"]["end_date"]
                        mid = datetime(year, month, 15, tzinfo=timezone.utc)
                        if start_date <= mid <= end_date:
                            active_lease_doc = ld
                            break

                    if active_lease_doc is None:
                        self.occupancy_by_month[ym_key][str(unit["id"])] = False
                        self._record_vacancy_loss_for_month(year, month, unit["rent"])
                        continue

                    # Random turnover (>= 2023)
                    end_now = (random.random() < 0.05) and (year >= 2023)
                    if end_now:
                        self._end_lease_and_refund(active_lease_doc, year, month)

                        # Vacancy gap 1–6 months
                        gap = random.randint(1, 6)
                        gap_months = self._month_span(year, month, gap)
                        for vy, vm in gap_months:
                            vym_key = f"{vy}-{vm:02d}"
                            self.occupancy_by_month.setdefault(vym_key, {})[str(unit["id"])] = False
                            self._record_vacancy_loss_for_month(vy, vm, unit["rent"])

                        next_start_year, next_start_month = gap_months[-1]
                        next_start = datetime(next_start_year, next_start_month, 28, tzinfo=timezone.utc) + timedelta(days=3)
                        self._create_new_lease_after_vacancy(unit, next_start)

                        # Occupied in the month until end
                        self.occupancy_by_month[ym_key][str(unit["id"])] = True
                        continue

                    # Hard-coded vacancy scenarios (kept)
                    if year == 2023 and month in [3, 4] and i == 2:
                        self.occupancy_by_month[ym_key][str(unit["id"])] = False
                        self._record_vacancy_loss_for_month(year, month, unit["rent"])
                        continue
                    if year == 2023 and month == 6 and i == 5:
                        self.occupancy_by_month[ym_key][str(unit["id"])] = False
                        self._record_vacancy_loss_for_month(year, month, unit["rent"])
                        continue
                    if year == 2023 and month in [8, 9, 10] and i == 8:
                        self.occupancy_by_month[ym_key][str(unit["id"])] = False
                        self._record_vacancy_loss_for_month(year, month, unit["rent"])
                        continue
                    if year == 2024 and month == 4 and i == 4:
                        self.occupancy_by_month[ym_key][str(unit["id"])] = False
                        self._record_vacancy_loss_for_month(year, month, unit["rent"])
                        continue

                    # Normal invoicing/payment for active lease
                    base_rent = active_lease_doc["lease_terms"]["rent_amount"]
                    adj_rent = self._adjust_rent_with_inflation(base_rent, year)
                    unit_for_invoice = {"id": unit["id"], "number": unit["number"], "rent": adj_rent}
                    
                    invoice = self.generate_invoice_data(year, month, unit_for_invoice, {"id": active_lease_doc["tenant_id"]})
                    self.invoices_batch.append(invoice)
                    total_invoices += 1

                    # --- Simulate unpaid / partial invoices in 2024 ---
                    if year == 2024  and month==6 and random.random() < 0.25:
                        # 25% chance: UNPAID (no payment at all)
                        invoice["status"] = "unpaid"
                        invoice["total_paid"] = 0.0
                        invoice["balance_amount"] = invoice["total_amount"]
                        print(f"⚠️  Simulated UNPAID invoice for {invoice['invoice_number']}")
                        continue
                    elif year == 2024 and month==6  and random.random() < 0.25:
                        # 25% chance: PARTIAL PAYMENT (50–90%)
                        partial_ratio = random.uniform(0.5, 0.9)
                        paid_amount = round(invoice["total_amount"] * partial_ratio, 2)
                        invoice["status"] = "partial"
                        invoice["total_paid"] = paid_amount
                        invoice["balance_amount"] = invoice["total_amount"] - paid_amount
                        print(f"⚠️  Simulated PARTIAL invoice for {invoice['invoice_number']} ({partial_ratio*100:.0f}%)")
                        payment_amount = paid_amount
                    else:
                        # Normal full payment
                        invoice["status"] = "paid"
                        invoice["total_paid"] = invoice["total_amount"]
                        invoice["balance_amount"] = 0.0
                        payment_amount = invoice["total_amount"]

                    # Create payment entry only if paid or partial
                    if invoice["status"] in ("paid", "partial"):
                        payment_date = self.generate_payment_date(year, month)
                        payment = {
                            "_id": ObjectId(),
                            "invoice_id": invoice["_id"],
                            "tenant_id": invoice["tenant_id"],
                            "amount": payment_amount,
                            "payment_method": "mpesa",
                            "reference": f"MP{year}{month:02d}{i:02d}",
                            "payment_date": payment_date,
                            "created_at": payment_date
                        }
                        self.payments_batch.append(payment)
                        total_payments += 1

                        # Ledger entries for the actual payment
                        ledgers = self.generate_ledger_entries(invoice, payment_amount, payment_date)
                        self.ledger_batch.extend(ledgers)
                        total_ledger += len(ledgers)

                    self.occupancy_by_month[ym_key][str(unit["id"])] = True

        # Sample maintenance items + ledger
        maintenance_scenarios = [
            (3500,  "Fixed leaking sink",                 datetime(2022, 3, 15, tzinfo=timezone.utc), self.units[0]["id"]),
            (5000,  "Replaced circuit breaker",           datetime(2022, 5, 10, tzinfo=timezone.utc), self.units[2]["id"]),
            (25000, "Renovation - repaint & flooring",    datetime(2023, 4, 15, tzinfo=timezone.utc), self.units[2]["id"]),
            (45000, "Deep cleaning after eviction",       datetime(2023, 9, 10, tzinfo=timezone.utc), self.units[8]["id"]),
            (55000, "Kitchen & bathroom renovation",      datetime(2024, 4, 20, tzinfo=timezone.utc), self.units[4]["id"]),
        ]
        for amount, desc, date, unit_id in maintenance_scenarios:
            self.maintenance_batch.append({
                "_id": ObjectId(),
                "property_id": self.property_id,
                "unit_id": unit_id,
                "amount": amount,
                "description": desc,
                "date": date,
                "category": "maintenance",
                "responsible_party": "landlord"
            })
            self.ledger_batch.append(self.generate_maintenance_ledger(amount, desc, date, unit_id))
            total_ledger += 1

        elapsed = time.time() - start
        print(f"  ✓ Generated in {elapsed:.2f}s:")
        print(f"    - {total_invoices} invoices")
        print(f"    - {total_payments} payments")
        print(f"    - {total_ledger} ledger entries")
        print(f"    - {len(self.maintenance_batch)} maintenance records")

    # -------------------- Bulk Inserts -------------------------------------
    @time_operation("Bulk Insert - Static Data")
    async def bulk_insert_static(self, property_doc, units_docs, tenants_docs, leases_docs):
        print("\n💾 Bulk inserting static data...")
        await self.db.properties.insert_one(property_doc)
        if units_docs:   await self.db.units.insert_many(units_docs)
        if tenants_docs: await self.db.property_tenants.insert_many(tenants_docs)
        if leases_docs:  await self.db.property_leases.insert_many(leases_docs)
        print(f"  ✓ Inserted: 1 property, {len(units_docs)} units, {len(tenants_docs)} tenants, {len(leases_docs)} leases")

    @time_operation("Bulk Insert - Transactions")
    async def bulk_insert_transactions(self):
        print("\n💾 Bulk inserting transaction data...")
        if self.invoices_batch:
            await self.db.property_invoices.insert_many(self.invoices_batch)
            print(f"  ✓ Inserted {len(self.invoices_batch)} invoices")
        if self.payments_batch:
            await self.db.property_payments.insert_many(self.payments_batch)
            print(f"  ✓ Inserted {len(self.payments_batch)} payments")
        if self.ledger_batch:
            await self.db.property_ledger_entries.insert_many(self.ledger_batch)
            print(f"  ✓ Inserted {len(self.ledger_batch)} ledger entries")
        if self.maintenance_batch:
            await self.db.maintenance_records.insert_many(self.maintenance_batch)
            print(f"  ✓ Inserted {len(self.maintenance_batch)} maintenance records")

    # -------------------- Financial Reports --------------------------------
    @time_operation("Generate Financial Reports from Ledger")
    async def generate_financial_reports(self):
        print("\n" + "="*80)
        print("FINANCIAL REPORTS (FROM LEDGER)")
        print("="*80)

        all_entries = await self.db.property_ledger_entries.find({}).to_list(length=None)

        years_data: Dict[str, List[Dict]] = {"2022": [], "2023": [], "2024": []}
        for e in all_entries:
            y = str(e["date"].year)
            if y in years_data:
                years_data[y].append(e)

        # Income Statement
        print(f"\n{'INCOME STATEMENT (FROM LEDGER)':^80}")
        print("="*80)
        print(f"{'Account':<40} {'2022':>12} {'2023':>12} {'2024':>12}")
        print("-"*80)

        print(f"{'REVENUE':^80}")
        revenues = {}
        for y in ["2022", "2023", "2024"]:
            revenues[y] = {
                "rental_income": sum(e["credit"] for e in years_data[y] if e.get("account_code") == "4100"),
                "utility_income": sum(e["credit"] for e in years_data[y] if e.get("account_code") in {"4210", "4220", "4230", "4200"}),
                "maintenance_income": sum(e["credit"] for e in years_data[y] if e.get("account_code") == "4300"),
            }
        print(f"{'  Rental Income':<40} {revenues['2022']['rental_income']:>12,.2f} {revenues['2023']['rental_income']:>12,.2f} {revenues['2024']['rental_income']:>12,.2f}")
        print(f"{'  Utility Income':<40} {revenues['2022']['utility_income']:>12,.2f} {revenues['2023']['utility_income']:>12,.2f} {revenues['2024']['utility_income']:>12,.2f}")
        print(f"{'  Maintenance Income (deposit deductions)':<40} {revenues['2022']['maintenance_income']:>12,.2f} {revenues['2023']['maintenance_income']:>12,.2f} {revenues['2024']['maintenance_income']:>12,.2f}")
        print("-"*80)

        total_revenue = {y: sum(revenues[y].values()) for y in ["2022", "2023", "2024"]}
        print(f"{'Total Revenue':<40} {total_revenue['2022']:>12,.2f} {total_revenue['2023']:>12,.2f} {total_revenue['2024']:>12,.2f}")
        print()

        # Expenses
        print(f"{'EXPENSES':^80}")
        expenses = {}
        for y in ["2022", "2023", "2024"]:
            expenses[y] = {
                "maintenance": sum(e["debit"] for e in years_data[y] if e.get("account_code") == "5100"),
                "vacancy_loss": sum(e["debit"] for e in years_data[y] if e.get("account_code") == "5200"),
            }
        print(f"{'  Maintenance & Repairs':<40} {expenses['2022']['maintenance']:>12,.2f} {expenses['2023']['maintenance']:>12,.2f} {expenses['2024']['maintenance']:>12,.2f}")
        print(f"{'  Vacancy Loss':<40} {expenses['2022']['vacancy_loss']:>12,.2f} {expenses['2023']['vacancy_loss']:>12,.2f} {expenses['2024']['vacancy_loss']:>12,.2f}")
        print("-"*80)

        total_expenses = {y: expenses[y]["maintenance"] + expenses[y]["vacancy_loss"] for y in ["2022", "2023", "2024"]}
        print(f"{'Total Expenses':<40} {total_expenses['2022']:>12,.2f} {total_expenses['2023']:>12,.2f} {total_expenses['2024']:>12,.2f}")
        print()

        # Taxes (approx): 7.5% of all cash receipts (payment_received to Cash)
        # Note: includes utilities & deposits; refine if you want rent-only cash tax.
        print(f"{'TAXES':^80}")
        tax_rate = 0.075
        taxes = {}
        for y in ["2022", "2023", "2024"]:
            cash_in = sum(
                e["debit"]
                for e in years_data[y]
                if e.get("account") == "Cash" and e.get("transaction_type") == "payment_received"
            )
            taxes[y] = cash_in * tax_rate
        print(f"{'  Rental Income Tax (proxy @7.5%)':<40} {taxes['2022']:>12,.2f} {taxes['2023']:>12,.2f} {taxes['2024']:>12,.2f}")
        print("-"*80)
        print(f"{'Total Taxes':<40} {taxes['2022']:>12,.2f} {taxes['2023']:>12,.2f} {taxes['2024']:>12,.2f}")
        print("="*80)

        noi = {y: total_revenue[y] - total_expenses[y] - taxes[y] for y in ["2022", "2023", "2024"]}
        print(f"{'NET OPERATING INCOME (After Tax)':<40} {noi['2022']:>12,.2f} {noi['2023']:>12,.2f} {noi['2024']:>12,.2f}")

        # Balance Sheet snapshot
        print(f"\n{'BALANCE SHEET (as of Jun 30, 2024) - FROM LEDGER':^80}")
        asset_entries = [e for e in all_entries if str(e.get("account_code", "")).startswith("1")]
        cash = sum(e["debit"] - e["credit"] for e in asset_entries if e.get("account") == "Cash")
        # ar   = sum(e["debit"] - e["credit"] for e in asset_entries if e.get("account") == "Accounts Receivable")
        receivable_codes = {
            "1201": "Rent Receivable",
            "1202": "Water Receivable",
            "1203": "Electricity Receivable",
            "1204": "Garbage Receivable",
            "1205": "Deposit Receivable",
            "1210": "Other Receivable",
        }
        receivables_breakdown = {
            code: sum(e["debit"] - e["credit"] for e in asset_entries if e.get("account_code") == code)
            for code in receivable_codes
        }

        # Compute totals
        total_receivables = sum(receivables_breakdown.values())
        total_assets = cash + total_receivables

        # Print
        print(f"{'  Cash':<40} {cash:>12,.2f}")
        for code, label in receivable_codes.items():
            val = receivables_breakdown[code]
            if abs(val) > 0.005:  # only show nonzero accounts
                print(f"{'  '+label:<40} {val:>12,.2f}")
        print("-"*80)
        print(f"{'  Total Receivables':<40} {total_receivables:>12,.2f}")
        print(f"{'  Total Assets':<40} {total_assets:>12,.2f}")

        print(f"\n{'LIABILITIES':^80}")
        deposits_liab = sum((e["credit"] - e["debit"]) for e in all_entries if e.get("account_code") == "2200")
        print(f"{'  Tenant Deposits Payable':<40} {deposits_liab:>12,.2f}")
        print("-"*80)
        print(f"{'Total Liabilities':<40} {deposits_liab:>12,.2f}")

        equity = (cash + total_receivables) - deposits_liab
        print(f"\n{'EQUITY':^80}")
        print(f"{'  Owner Equity':<40} {equity:>12,.2f}")
        print("="*80)
        print(f"{'Total Liabilities & Equity':<40} {deposits_liab + equity:>12,.2f}")
        print("="*80)

        # Cash Flow
        print(f"\n{'CASH FLOW STATEMENT - FROM LEDGER':^80}")
        for y in ["2022", "2023", "2024"]:
            cash_entries = [e for e in years_data[y] if e.get("account") == "Cash"]
            inflows = sum(e["debit"] for e in cash_entries)
            outflows = sum(e["credit"] for e in cash_entries)
            print(f"\n{y}:")
            print(f"  Cash Inflows:  KES {inflows:>12,.2f}")
            print(f"  Cash Outflows: KES {outflows:>12,.2f}")
            print(f"  Net Cash Flow: KES {inflows - outflows:>12,.2f}")

        # Occupancy KPIs
        print("\n" + "="*80)
        print(f"\n{'KEY PERFORMANCE INDICATORS':^80}")
        print("="*80)
        for ym in sorted(self.occupancy_by_month.keys()):
            mm = self.occupancy_by_month[ym]
            if not mm:
                continue
            occ = sum(1 for v in mm.values() if v)
            rate = occ / len(self.units) * 100 if self.units else 0.0
            print(f"{ym}: {occ}/{len(self.units)} occupied ({rate:.1f}%)")
        print("\n" + "="*80)

    # ----------------------------- Runner ----------------------------------
    async def run_optimized_test(self):
        print("\n🚀 Starting Optimized Financial Test (Upgraded & Fixed)")
        print("="*80)

        overall_start = time.time()
        try:
            await self.setup_database()

            # Build canonical in-memory docs
            property_doc, units_docs, tenants_docs, leases_docs = self.generate_static_data()

            # Generate transactions (may create NEW tenants/leases before inserts)
            self.generate_all_transactions()

            # Bulk insert everything (includes turnovers & ended leases)
            await self.bulk_insert_static(property_doc, self.units_docs, self.tenants_docs, self.leases_docs)
            await self.bulk_insert_transactions()

            # Optionally: helpful index hints (uncomment if you like)
            # await self.db.property_leases.create_index("status")
            # await self.db.property_leases.create_index([("property_id", 1), ("status", 1)])
            # await self.db.property_invoices.create_index([("tenant_id", 1), ("date_issued", 1)])
            # await self.db.property_ledger_entries.create_index([("account_code", 1), ("date", 1)])

            await self.generate_financial_reports()

            overall_time = time.time() - overall_start
            print("\n" + "="*80)
            print("PERFORMANCE SUMMARY")
            print("="*80)
            print(f"\n{'Operation':<40} {'Time':>12}")
            print("-"*80)
            for name, elapsed in timings.items():
                print(f"{name:<40} {elapsed:>11.2f}s")
            print("-"*80)
            print(f"{'TOTAL TIME':<40} {overall_time:>11.2f}s")
            print("="*80)

            print(f"\n✅ TEST COMPLETE")
            print(f"   - Generated 2.5 years of data incl. turnovers")
            print(f"   - 10 units, ~300 invoices, ~300 payments (plus deposits)")
            print(f"   - Double-entry ledger w/ deposits & vacancy")
            print(f"   - Ended leases are persisted (check distinct('status'))")
            return True

        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False


# ---------------------------------- Main -------------------------------------
async def main():
    client = AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
    test = OptimizedFinancialTest(client)
    success = await test.run_optimized_test()
    client.close()
    if success:
        print(f"\n🎉 Optimized test completed successfully!")
    else:
        print(f"\n❌ Test encountered errors")


if __name__ == "__main__":
    asyncio.run(main())
