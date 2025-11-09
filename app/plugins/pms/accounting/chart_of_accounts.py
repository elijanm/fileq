# Allocation order (configurable). Adjust if you prefer a different priority.
ALLOCATION_PRIORITY = [
    # Core rent first
    "rent",
    
    # Utilities next (in descending likelihood of cost impact)
    "utility_water",
    "utility_garbage",
    "utility_electricity",
    "utility_other",
    
    # Maintenance & repairs
    "maintenance",
    
    # Taxes (recoverable or payable adjustments)
    "tax_recovery",                 # recoverable VAT / service tax
    "property_tax_expense",         # landlord-side property or income tax
    
    # Service-related or penalty items
    "late_fee",
    "service_fee",
    
    # Miscellaneous or other operating items
    "other_expense",
    
    # Finally, deposits and credits
    "deposit"
]


# chart_of_accounts.py (or inline above the class)
# ============================================================
#  CHART OF ACCOUNTS (Comprehensive with Fine-Grained Assets)
# ============================================================

CHART_OF_ACCOUNTS = {
    # ----------------------- ASSETS (1xxx) -----------------------
    "cash":                     {"account": "Cash",                           "code": "1000", "type": "Asset"},
    "cash_with_agent":          {"account": "Cash with Agent",                "code": "1050", "type": "Asset"},
    "cash_with_agent_clearing": {"account": "Agent Clearing Account",         "code": "1051", "type": "Asset"},
    "bank":                     {"account": "Bank Account",                   "code": "1010", "type": "Asset"},
    "petty_cash":               {"account": "Petty Cash",                     "code": "1020", "type": "Asset"},
    "investment":               {"account": "Property Investment",            "code": "1500", "type": "Asset"},
    "equipment":                {"account": "Equipment",                      "code": "1600", "type": "Asset"},
    "prepaid_expenses":         {"account": "Prepaid Expenses",               "code": "1215", "type": "Asset"},
    "deposit_asset":            {"account": "Security Deposit (Asset Side)",  "code": "1210", "type": "Asset"},


    # --- Receivables (1200–1299) ---
    "accounts_receivable":      {"account": "Accounts Receivable (Master)",   "code": "1200", "type": "Asset"},
    "ar_agent_receivable":      {"account": "Accounts Receivable - Agent",    "code": "1210","type": "Asset"},
    "ar_agent_clearing":        {"account": "Accounts Receivable - Agent Clearing","code": "1211","type": "Asset"},
    "ar_rent":                  {"account": "Rent Receivable",                "code": "1201", "type": "Asset"},
    "ar_water":                 {"account": "Water Receivable",               "code": "1202", "type": "Asset"},
    "ar_electricity":           {"account": "Electricity Receivable",         "code": "1203", "type": "Asset"},
    "ar_garbage":               {"account": "Garbage Receivable",             "code": "1204", "type": "Asset"},
    "ar_other_utility":         {"account": "Other Utility Receivable",       "code": "1205", "type": "Asset"},
    "ar_deposit":               {"account": "Deposit Receivable",             "code": "1206", "type": "Asset"},
    "ar_late_fee":              {"account": "Late Fee Receivable",            "code": "1207", "type": "Asset"},
    "ar_service_fee":           {"account": "Service Fee Receivable",         "code": "1208", "type": "Asset"},
    "ar_misc":                  {"account": "Miscellaneous Receivable",       "code": "1209", "type": "Asset"},
    "ar_tax_recoverable":       {"account": "Tax Recoverable",                "code": "1210", "type": "Asset"},
    "ar_adjustment":            {"account": "Accounts Receivable Adjustment", "code": "1299", "type": "Asset"},

    # --------------------- LIABILITIES (2xxx) ---------------------
    "deposit":                  {"account": "Tenant Security Deposit",        "code": "2100", "type": "Liability"},
    "tenant_credit":            {"account": "Tenant Credit / Prepaid Rent",   "code": "2300", "type": "Liability"},
    "loan":                     {"account": "Loan Payable",                   "code": "2200", "type": "Liability"},
    "tax_payable":              {"account": "Tax Payable",                    "code": "2400", "type": "Liability"},
    "unearned_income":          {"account": "Unearned Income",                "code": "2500", "type": "Liability"},

    # ----------------------- INCOME (4xxx) -----------------------
    "rent":                     {"account": "Rental Income",                  "code": "4000", "type": "Income"},
    "maintenance":              {"account": "Maintenance Income",             "code": "4010", "type": "Income"},
    "utilities":                {"account": "Utilities Income",               "code": "4020", "type": "Income"},
    "utility_water":            {"account": "Water Income",                   "code": "4021", "type": "Income"},
    "utility_electricity":      {"account": "Electricity Income",             "code": "4022", "type": "Income"},
    "utility_garbage":          {"account": "Garbage Income",                 "code": "4023", "type": "Income"},
    "utility_other":            {"account": "Other Utility Income",           "code": "4024", "type": "Income"},
    "tax_recovery":             {"account": "Tax Recoveries Income",          "code": "4030", "type": "Income"},
    "late_fee":                 {"account": "Late Fee Income",                "code": "4040", "type": "Income"},
    "service_fee":              {"account": "Service Fee Income",             "code": "4060", "type": "Income"},
    "misc_income":              {"account": "Miscellaneous Income",           "code": "4999", "type": "Income"},

    # ---------------------- EXPENSES (5xxx–7xxx) ----------------------
    "maintenance_expense":      {"account": "Maintenance & Repairs",          "code": "5100", "type": "Expense"},
    "vacancy_loss":             {"account": "Vacancy Loss",                   "code": "5200", "type": "Expense"},
    "utility_water_expense":    {"account": "Water Expense",                  "code": "5310", "type": "Expense"},
    "utility_electricity_expense": {"account": "Electricity Expense",         "code": "5320", "type": "Expense"},
    "utility_garbage_expense":  {"account": "Garbage Expense",                "code": "5330", "type": "Expense"},
    "utility_other_expense":    {"account": "Other Utility Expense",          "code": "5340", "type": "Expense"},
    "property_tax_expense":     {"account": "Property Tax Expense",           "code": "5350", "type": "Expense"},
    "insurance_expense":        {"account": "Insurance Expense",              "code": "5360", "type": "Expense"},
    "interest_expense":         {"account": "Loan Interest Expense",          "code": "5370", "type": "Expense"},
    "management_fee":           {"account": "Property Management Fee",        "code": "5380", "type": "Expense"},
    "other_expense":            {"account": "Other General Expense",          "code": "5400", "type": "Expense"},
    "depreciation_expense":     {"account": "Depreciation Expense",           "code": "7000", "type": "Expense"},

    # -------------------- CONTRA & ADJUSTMENTS --------------------
    "accum_depreciation":       {"account": "Accumulated Depreciation",       "code": "1700", "type": "Contra-Asset"},
    "discount":                 {"account": "Sales Discounts",                "code": "4050", "type": "Contra-Income"},
}


def _priority_rank(category: str) -> int:
    """
    Return numeric rank for a category based on ALLOCATION_PRIORITY.
    Lower = higher allocation priority.
    """
    try:
        return ALLOCATION_PRIORITY.index(category)
    except ValueError:
        return len(ALLOCATION_PRIORITY) + 1
    
def _resolve_ar_for_category(category: str, auto_create: bool = True) -> dict:
    """
    Automatically route receivables based on category.
    Handles 'cash_with_agent' and agent-related flows.
    """
    if not category:
        return CHART_OF_ACCOUNTS["accounts_receivable"]

    category = category.lower().replace(" ", "_")
    probes = [f"ar_{category}"]

    # Smart category mapping rules
    if category.startswith("utility_"):
        probes += ["ar_utilities"]
    elif category in {"tax_recovery", "property_tax_expense"}:
        probes += ["ar_taxes"]
    elif "rent" in category:
        probes += ["ar_rent"]
    elif "agent" in category or category.startswith("cash_with"):
        # Route to dedicated agent clearing / holding accounts
        probes += ["cash_with_agent", "cash_with_agent_clearing"]
    else:
        probes += [f"ar_{category}", "accounts_receivable"]

    # Try defined accounts
    for key in probes:
        if key in CHART_OF_ACCOUNTS:
            return CHART_OF_ACCOUNTS[key]

    # Auto-create if missing
    if auto_create:
        new_key = probes[0]
        CHART_OF_ACCOUNTS[new_key] = {
            "account": f"Accounts Receivable - {category.replace('_', ' ').title()}",
            "code": f"12{len([k for k in CHART_OF_ACCOUNTS if k.startswith('ar_')])+1:02d}",
            "type": "Asset",
        }
        print(f"🪄 Auto-created A/R subaccount for category '{category}' → {CHART_OF_ACCOUNTS[new_key]['account']}")
        return CHART_OF_ACCOUNTS[new_key]

    return CHART_OF_ACCOUNTS["accounts_receivable"]


def resolve_account(category: str) -> dict:
    """
    Accepts categories like 'rent', 'utilities', 'utilities.water', etc.
    Falls back to 'misc' if unknown.
    """
    if category in CHART_OF_ACCOUNTS:
        return CHART_OF_ACCOUNTS[category]
    # support 'utilities.<subtype>' even if only base 'utilities' exists
    if category.startswith("utilities.") and "utilities" in CHART_OF_ACCOUNTS:
        return CHART_OF_ACCOUNTS["utilities"]
    return CHART_OF_ACCOUNTS["misc"]
