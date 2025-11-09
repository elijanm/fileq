from calendar import monthrange
from datetime import datetime,date,timedelta
from typing import List,Dict,Optional
from plugins.pms.accounting.chart_of_accounts import resolve_account, CHART_OF_ACCOUNTS
from plugins.pms.models.ledger_entry import(
    LedgerEntry
)
from collections import defaultdict

def account_balance(entries: List[LedgerEntry], up_to: date) -> Dict[str, float]:
    """Aggregate account balances up to a specific date."""
    bal = {}
    for e in entries:
        if e.date <= up_to:
            bal[e.account] = bal.get(e.account, 0.0) + (e.debit - e.credit)
    return bal

class ReportGenerator:
    def __init__(self, entries: List[LedgerEntry], property_units: int, vacant_units: int, loan_payment: float = 0.0):
        self.entries = entries
        self.total_units = property_units
        self.vacant_units = vacant_units
        self.loan_payment = loan_payment

    def _filter(self, start: date, end: date) -> List[LedgerEntry]:
        return [e for e in self.entries if start <= e.date <= end]

    def income_statement_old(self, start: date, end: date) -> Dict[str, float]:
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
    def income_statement(self, start: date, end: date) -> Dict[str, Dict]:
        """
        Generate a grouped, chart-aware Income Statement.
        Includes subtotals by 'group' and full category breakdown.
        """
        entries = self._filter(start, end)
        if not entries:
            return {
                "Income": {},
                "Expenses": {},
                "Totals": {"EGI": 0.0, "Operating Expenses": 0.0,
                        "NOI": 0.0, "Depreciation": 0.0,
                        "Interest": 0.0, "Net Income": 0.0}
            }

        # --- Chart lookups ---
        income_chart = {v["account"]: v for v in CHART_OF_ACCOUNTS.values() if v.get("type") == "Income"}
        expense_chart = {v["account"]: v for v in CHART_OF_ACCOUNTS.values() if v.get("type") == "Expense"}

        income_groups = defaultdict(lambda: defaultdict(float))
        expense_groups = defaultdict(lambda: defaultdict(float))

        # --- Helpers ---
        def is_revenue(e: LedgerEntry) -> bool:
            desc = (e.description or "").lower()
            return (
                "income" in e.account.lower()
                and not any(x in desc for x in ("balance", "forward", "deposit", "credit"))
            )

        def is_expense(e: LedgerEntry) -> bool:
            return "expense" in e.account.lower()

        # --- Income aggregation ---
        for e in entries:
            if not is_revenue(e):
                continue
            amount = e.credit - e.debit
            matched = next((acct for acct in income_chart if acct in e.account), None)
            if not matched:
                income_groups["Other Income"]["Uncategorized Income"] += amount
                continue

            info = income_chart[matched]
            group = info.get("group", "Other Income")
            income_groups[group][matched] += amount

        # --- Expense aggregation ---
        for e in entries:
            if not is_expense(e):
                continue
            amount = e.debit - e.credit
            matched = next((acct for acct in expense_chart if acct in e.account), None)
            if not matched:
                expense_groups["Other Expense"]["Uncategorized Expense"] += amount
                continue

            info = expense_chart[matched]
            group = info.get("group", "Operating Expenses")
            expense_groups[group][matched] += amount

        # --- Compute subtotals ---
        income_group_totals = {g: sum(v.values()) for g, v in income_groups.items()}
        expense_group_totals = {g: sum(v.values()) for g, v in expense_groups.items()}

        # --- Depreciation / Interest ---
        depreciation = sum(e.debit - e.credit for e in entries if e.account == "Depreciation Expense")
        interest = sum(e.debit - e.credit for e in entries if e.account == "Loan Interest Expense")

        # --- Totals ---
        total_income = sum(income_group_totals.values())
        total_expense = sum(expense_group_totals.values())
        noi = total_income - total_expense
        net_income = noi - depreciation - interest

        return {
            "Income": {
                g: {"accounts": {k: round(v, 2) for k, v in v.items()},
                    "subtotal": round(income_group_totals[g], 2)}
                for g, v in income_groups.items()
            },
            "Expenses": {
                g: {"accounts": {k: round(v, 2) for k, v in v.items()},
                    "subtotal": round(expense_group_totals[g], 2)}
                for g, v in expense_groups.items()
            },
            "Totals": {
                "EGI": round(total_income, 2),
                "Operating Expenses": round(total_expense, 2),
                "NOI": round(noi, 2),
                "Depreciation": round(depreciation, 2),
                "Interest": round(interest, 2),
                "Net Income": round(net_income, 2),
            },
        }
    

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
        """
        Chart-driven Balance Sheet with dynamic grouping.
        Automatically computes retained earnings and validates total balance.
        """
        # --- 1️⃣ Calculate balances up to date
        bal = account_balance(self.entries, up_to=as_of)

        # --- 2️⃣ Compute YTD Net Income from Income Statement
        start_year = date(as_of.year, 1, 1)
        is_ytd = self.income_statement(start_year, as_of)
        ytd_net_income = is_ytd["Totals"]["Net Income"] if "Totals" in is_ytd else is_ytd.get("Net Income", 0.0)
        retained_earnings = beginning_retained_earnings + ytd_net_income

        # --- 3️⃣ Group accounts from chart by section
        groups = {
            "Assets": defaultdict(float),
            "Liabilities": defaultdict(float),
            "Equity": defaultdict(float),
        }

        # Optional: allow "subgroup" (current, non-current) if present
        def section_of(account_name: str) -> str:
            for key, data in CHART_OF_ACCOUNTS.items():
                if data.get("account") == account_name:
                    return data.get("section", None)
            return None

        def subgroup_of(account_name: str) -> str:
            for key, data in CHART_OF_ACCOUNTS.items():
                if data.get("account") == account_name:
                    return data.get("subgroup", None)
            return None

        for account, amount in bal.items():
            sec = section_of(account)
            sub = subgroup_of(account)
            if not sec:
                # attempt auto-detection
                if "payable" in account.lower() or "liability" in account.lower():
                    sec, sub = "Liabilities", "Current"
                elif "capital" in account.lower() or "equity" in account.lower():
                    sec, sub = "Equity", "Capital"
                elif "receivable" in account.lower() or "cash" in account.lower():
                    sec, sub = "Assets", "Current"
                elif "property" in account.lower() or "equipment" in account.lower():
                    sec, sub = "Assets", "Non-current"
                elif "accumulated depreciation" in account.lower():
                    sec, sub = "Assets", "Non-current"
                else:
                    sec, sub = "Assets", "Other"
            groups[sec][(sub or "Other") + ":" + account] += amount

        # --- 4️⃣ Adjust signs
        # In accounting convention: Assets normally debit (+), Liabilities/Equity credit (-)
        for sec, accs in groups.items():
            if sec in ("Liabilities", "Equity"):
                for k in accs:
                    groups[sec][k] = -groups[sec][k]

        # --- 5️⃣ Add retained earnings to equity
        groups["Equity"]["Retained Earnings"] += retained_earnings

        # --- 6️⃣ Calculate section totals
        total_assets = sum(groups["Assets"].values())
        total_liab = sum(groups["Liabilities"].values())
        total_equity = sum(groups["Equity"].values())
        total_liab_equity = total_liab + total_equity
        balanced = abs(total_assets - total_liab_equity) < 1e-3

        # --- 7️⃣ Organize hierarchical structure
        def organize(section_dict):
            organized = defaultdict(lambda: {"accounts": {}, "subtotal": 0.0})
            for key, value in section_dict.items():
                if ":" in key:
                    sub, acct = key.split(":", 1)
                else:
                    sub, acct = "Other", key
                organized[sub]["accounts"][acct] = round(value, 2)
                organized[sub]["subtotal"] += value
            return {k: {"accounts": v["accounts"], "subtotal": round(v["subtotal"], 2)} for k, v in organized.items()}

        # --- 8️⃣ Return final structure
        return {
            "Assets": organize(groups["Assets"]),
            "Liabilities": organize(groups["Liabilities"]),
            "Equity": organize(groups["Equity"]),
            "Totals": {
                "Total Assets": round(total_assets, 2),
                "Total Liabilities": round(total_liab, 2),
                "Total Equity": round(total_equity, 2),
                "Liabilities + Equity": round(total_liab_equity, 2),
                "Balanced": balanced,
                "Retained Earnings": round(retained_earnings, 2),
                "YTD Net Income": round(ytd_net_income, 2),
                "Imbalance": round(total_assets - total_liab_equity, 2),
            },
        }

    def kpis(
        self,
        start: date,
        end: date,
        avg_rent_per_unit: float,
        owner_equity: float,
        opening_cash: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Computes key property performance metrics for the given period.
        Integrates with ledger + chart for realism (DSCR, OpEx, ROI, etc.)
        """
        is_stmt = self.income_statement(start, end)
        cf_stmt = self.cash_flow_indirect(start, end, opening_cash=opening_cash)

        # ---------- Occupancy / Rent Metrics ----------
        gpr = self.total_units * avg_rent_per_unit  # Gross potential rent
        vacancy_units = self.vacant_units
        vacancy_loss = vacancy_units * avg_rent_per_unit
        vacancy_pct = (vacancy_loss / gpr * 100.0) if gpr else 0.0
        occupancy_rate = ((self.total_units - vacancy_units) / self.total_units * 100.0) if self.total_units else 0.0

        # ---------- Income & Expense Ratios ----------
        egi = gpr - vacancy_loss  # Effective Gross Income
        noi = is_stmt["Totals"]["NOI"] if "Totals" in is_stmt else is_stmt.get("NOI", 0.0)
        op_exp = is_stmt["Totals"]["Operating Expenses"] if "Totals" in is_stmt else is_stmt.get("Operating Expenses", 0.0)
        opex_ratio = (op_exp / egi * 100.0) if egi else 0.0

        # ---------- Loan Coverage ----------
        loan_payment = self.loan_payment or 0.0
        dscr = (noi / loan_payment) if loan_payment else float("inf")
        debt_yield = (noi / loan_payment * 100.0) if loan_payment else 0.0

        # ---------- Capital Expenditure ----------
        capex_out = sum(e.debit for e in self._filter(start, end) if e.account in ("Property", "Equipment"))
        capex_ratio = (capex_out / egi * 100.0) if egi else 0.0

        # ---------- Profitability & Return Metrics ----------
        net_income = is_stmt["Totals"]["Net Income"] if "Totals" in is_stmt else is_stmt.get("Net Income", 0.0)
        cash_on_cash = (net_income / owner_equity * 100.0) if owner_equity else 0.0

        # From cash flow statement
        cfo = cf_stmt["Operating"]["Net Cash from Operating"]
        net_change_cash = cf_stmt["Reconciliation"]["Net Change in Cash"]
        cash_yield = (cfo / owner_equity * 100.0) if owner_equity else 0.0

        # ---------- Expense Efficiency ----------
        repairs = sum(e.debit for e in self._filter(start, end) if "Repairs" in e.account)
        repairs_ratio = (repairs / op_exp * 100.0) if op_exp else 0.0

        # ---------- Reserve Adequacy ----------
        closing_cash = cf_stmt["Reconciliation"]["Closing Cash (GL)"]
        monthly_opex = (op_exp / ((end - start).days / 30)) if (end - start).days >= 28 else op_exp
        reserve_months = (closing_cash / monthly_opex) if monthly_opex else float("inf")

        # ---------- Leverage & Equity Metrics ----------
        equity_multiple = ((net_income + owner_equity) / owner_equity) if owner_equity else 0.0
        return_on_assets = (net_income / (owner_equity + loan_payment) * 100.0) if (owner_equity + loan_payment) else 0.0

        # ---------- Summary Dictionary ----------
        return {
            # Rent / Occupancy
            "Total Units": self.total_units,
            "Vacant Units": vacancy_units,
            "Occupancy %": round(occupancy_rate, 2),
            "GPR": round(gpr, 2),
            "Vacancy Loss": round(vacancy_loss, 2),
            "Vacancy Loss %": round(vacancy_pct, 2),

            # Income / Expense
            "EGI": round(egi, 2),
            "Operating Expenses": round(op_exp, 2),
            "OpEx Ratio %": round(opex_ratio, 2),
            "NOI": round(noi, 2),

            # Financing
            "DSCR": round(dscr, 2),
            "Debt Yield %": round(debt_yield, 2),

            # Profitability
            "Net Income": round(net_income, 2),
            "Cash-on-Cash %": round(cash_on_cash, 2),
            "Cash Yield %": round(cash_yield, 2),

            # CapEx & Reserves
            "CapEx Outflow": round(capex_out, 2),
            "CapEx Ratio %": round(capex_ratio, 2),
            "Repairs Ratio %": round(repairs_ratio, 2),
            "Reserve Months": round(reserve_months, 2),

            # Balance & Equity
            "Return on Assets %": round(return_on_assets, 2),
            "Equity Multiple": round(equity_multiple, 2),
        }
    def generate_monthly_summary(
        self,
        year: int,
        avg_rent_per_unit: float,
        owner_equity: float,
        opening_cash: Optional[float] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Generate monthly summaries for the given year:
        - Income Statement metrics (NOI, Net Income, OpEx %, etc.)
        - Cash Flow (Net Change, Closing Cash)
        - KPIs (DSCR, Cash Yield, Vacancy %, etc.)
        Rolls forward closing cash automatically each month.
        """
        summary = {}
        cash_opening = opening_cash or 0.0
        totals = {
            "Rental Income": 0.0,
            "Other Income": 0.0,
            "Operating Expenses": 0.0,
            "NOI": 0.0,
            "Net Income": 0.0,
            "Cash Flow": 0.0,
        }

        for month in range(1, 13):
            start = date(year, month, 1)
            end_day = monthrange(year, month)[1]
            end = date(year, month, end_day)

            # Income Statement (chart-aware)
            is_stmt = self.income_statement(start, end)
            totals_node = is_stmt.get("Totals", is_stmt)
            rental_income = (
                totals_node.get("Rental Income", 0.0)
                if "Rental Income" in totals_node
                else sum(v for k, v in is_stmt.get("Income", {}).items() if "rent" in k.lower())
            )
            other_income = (
                totals_node.get("Other Income", 0.0)
                if "Other Income" in totals_node
                else totals_node.get("EGI", 0.0) - rental_income
            )

            # Cash Flow
            cf_stmt = self.cash_flow_indirect(start, end, opening_cash=cash_opening)
            closing_cash = cf_stmt["Reconciliation"]["Closing Cash (GL)"]
            net_change_cash = cf_stmt["Reconciliation"]["Net Change in Cash"]
            cash_opening = closing_cash  # roll forward

            # KPIs (integrated from improved kpis())
            kpi_stmt = self.kpis(start, end, avg_rent_per_unit, owner_equity, opening_cash)

            # Build month summary
            month_label = datetime(year, month, 1).strftime("%b")
            summary[month_label] = {
                # Income Statement core
                "Rental Income": round(rental_income, 2),
                "Other Income": round(other_income, 2),
                "Operating Expenses": round(totals_node.get("Operating Expenses", 0.0), 2),
                "NOI": round(totals_node.get("NOI", 0.0), 2),
                "Depreciation": round(totals_node.get("Depreciation", 0.0), 2),
                "Interest": round(totals_node.get("Interest", 0.0), 2),
                "Net Income": round(totals_node.get("Net Income", 0.0), 2),

                # KPI metrics
                "DSCR": round(kpi_stmt.get("DSCR", 0.0), 2),
                "Vacancy %": round(kpi_stmt.get("Vacancy Loss %", 0.0), 2),
                "OpEx %": round(kpi_stmt.get("OpEx Ratio %", 0.0), 2),
                "Cash Yield %": round(kpi_stmt.get("Cash Yield %", 0.0), 2),
                "Cash-on-Cash %": round(kpi_stmt.get("Cash-on-Cash %", 0.0), 2),
                "CapEx %": round(kpi_stmt.get("CapEx Ratio %", 0.0), 2),

                # Cash Flow
                "Cash Flow": round(net_change_cash, 2),
                "Closing Cash": round(closing_cash, 2),
            }

            # Update totals
            totals["Rental Income"] += rental_income
            totals["Other Income"] += other_income
            totals["Operating Expenses"] += totals_node.get("Operating Expenses", 0.0)
            totals["NOI"] += totals_node.get("NOI", 0.0)
            totals["Net Income"] += totals_node.get("Net Income", 0.0)
            totals["Cash Flow"] += net_change_cash

        # Add yearly totals
        summary["Total"] = {
            k: round(v, 2) for k, v in totals.items()
        }
        summary["Total"]["Average DSCR"] = round(
            sum(m["DSCR"] for m in summary.values() if isinstance(m, dict) and "DSCR" in m) / 12, 2
        )
        summary["Total"]["Average OpEx %"] = round(
            sum(m["OpEx %"] for m in summary.values() if isinstance(m, dict) and "OpEx %" in m) / 12, 2
        )
        summary["Total"]["Average Cash Yield %"] = round(
            sum(m["Cash Yield %"] for m in summary.values() if isinstance(m, dict) and "Cash Yield %" in m) / 12, 2
        )

        return summary