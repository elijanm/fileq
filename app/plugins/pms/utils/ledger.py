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
from plugins.pms.models.ledger_entry import Invoice,InvoiceLineItem as LineItem,LedgerEntry,PyObjectId
from plugins.pms.accounting.reports import ReportGenerator

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

    # # --- Overdue invoices ---
    # overdue_invoices = [inv for inv in invoices if inv.due_date < today and inv.status in ["issued","unpaid"]]
    # avg_due_days = (
    #     sum((today - inv.due_date).days for inv in overdue_invoices) / len(overdue_invoices)
    #     if overdue_invoices else 0
    # )

    # --- Movement / tenancy metrics ---
    move_outs = list(moving_out_next_month)

    # --- Derived metrics (safe divisions) ---
    collection_rate = (total_collected / total_invoiced * 100) if total_invoiced > 0 else 0
    vacancy_rate = (vacant_units / total_units * 100) if total_units > 0 else 0
    arrears_balance = total_invoiced - total_collected
    # arrears_balance = sum(i.balance_amount for i in invoices if i.balance_amount > 0)
    
    # assert abs(arrears_balance_ - arrears_balance) < 0.05, f"Discrepancy between invoiced - paid and balances!-by {arrears_balance_ - arrears_balance}"

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
    overdue_invoices = [i for i in invoices if i.due_date < today and i.status in ["partial","unpaid"]]
    total_overdue = round(sum(i.balance_amount for i in overdue_invoices), 2)
    partially_paid = round(sum(i.total_paid for i in overdue_invoices if i.status == "partial"))
    unique_statuses = {i.status for i in overdue_invoices}
    credit_balance = round(sum(inv.overpaid_amount for inv in invoices if inv.overpaid_amount > 0))
    net_receivables = arrears_balance - credit_balance
    
    u=[{"id":str(i.id),"balance_amount":i.balance_amount,"total_amount":i.total_amount,"total_paid":i.total_paid} for i in overdue_invoices if i.status == "partial"]
    import json
    print(json.dumps({
        "partially_paid":partially_paid,
        "overdue_invoices":total_overdue,
        "diff":total_overdue-partially_paid,
        "unique_statuses":unique_statuses,
        "net_receivables":net_receivables,
        "arrears_balance_":arrears_balance,
        "data":u
    },indent=4,default=str))
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
