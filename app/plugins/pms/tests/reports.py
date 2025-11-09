#!/usr/bin/env python3
"""
Comprehensive Financial Reporting System (Final with Monthly + Key Metrics)

All reports are generated from the LEDGER (single source of truth).

Includes:
- Income Statement (with utility breakdowns & profitability)
- Balance Sheet (accurate Tenant Deposit detection)
- Cash Flow Statement
- Tax Report (7.5% rental income tax, cash-basis)
- Month-to-Month Analysis (within each year)
- Year-over-Year Analysis (with key metrics)
- Key Metrics: Occupancy %, Avg Rent/Unit, Vacancy Loss %, Utility Recovery, Operating Margin,
               Cash Conversion, Deposit-Liability Ratio
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from calendar import monthrange
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId


def month_bounds(year: int, month: int) -> Tuple[datetime, datetime]:
    """Return timezone-aware [start, end] bounds for a month (inclusive end)."""
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    last_day = monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


class FinancialReports:
    """Generate complete, multi-year financial reports from the property ledger"""

    def __init__(self, db: AsyncIOMotorDatabase, property_id: Optional[str] = None):
        self.db = db
        self.property_id = property_id
        self.tax_rate = 0.075  # 7.5% rental income tax

        # Canonical account codes used throughout
        self.account_codes = {
            "cash": "1010",
            "accounts_receivable": "1200",
            "rental_income": "4100",
            "water_income": "4210",
            "electricity_income": "4220",
            "garbage_income": "4230",
            "maintenance": "5100",
            "vacancy_loss": "5200",
            "water_expense": "5310",
            "electricity_expense": "5320",
            "garbage_expense": "5330",
            "other_expenses": "5400",
        }

    # ----------------------------------------------------------------------
    # Core retrieval helpers
    # ----------------------------------------------------------------------
    async def get_ledger_entries(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        account_codes: Optional[List[str]] = None,
    ) -> List[Dict]:
        """Get all ledger entries matching filters."""
        query: Dict = {}
        if self.property_id:
            query["property_id"] = self.property_id
        if start_date or end_date:
            query["date"] = {}
            if start_date:
                query["date"]["$gte"] = start_date
            if end_date:
                query["date"]["$lte"] = end_date
        if account_codes:
            query["account_code"] = {"$in": account_codes}
        return await self.db.property_ledger_entries.find(query).to_list(length=None)

    async def get_units_count(self) -> int:
        """Count units for the property."""
        q: Dict = {"property_id": ObjectId(self.property_id)} if self.property_id else {}
        return await self.db.units.count_documents(q)

    async def get_active_leases_for_month(self, year: int, month: int) -> List[Dict]:
        """
        Return leases active at any point within the month.
        A lease is 'active' in month if start_date <= month_end and (end_date is None or end_date >= month_start)
        and status not 'ended'.
        """
        start, end = month_bounds(year, month)
        lease_q: Dict = {
            "lease_terms.start_date": {"$lte": end},
            "$or": [
                {"lease_terms.end_date": {"$exists": False}},
                {"lease_terms.end_date": {"$gte": start}},
            ],
            "status": {"$nin": ["ended", "terminated"]},
        }
        if self.property_id:
            lease_q["property_id"] = ObjectId(self.property_id)
        return await self.db.property_leases.find(lease_q).to_list(length=None)

    # ----------------------------------------------------------------------
    # Yearly revenue / expense / taxes
    # ----------------------------------------------------------------------
    async def get_revenue_by_year(self, years: List[int]) -> Dict[int, Dict[str, float]]:
        """Revenue breakdown by year and category."""
        revenue = {}
        for year in years:
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            entries = await self.get_ledger_entries(
                start_date=start,
                end_date=end,
                account_codes=["4100", "4210", "4220", "4230", "4300", "4400"],
            )
            revenue[year] = {
                "rental_income": sum(e["credit"] for e in entries if e["account_code"] == "4100"),
                "water_income": sum(e["credit"] for e in entries if e["account_code"] == "4210"),
                "electricity_income": sum(e["credit"] for e in entries if e["account_code"] == "4220"),
                "garbage_income": sum(e["credit"] for e in entries if e["account_code"] == "4230"),
                "maintenance_income": sum(e["credit"] for e in entries if e.get("account_code") == "4300"),
                "other_income": sum(e["credit"] for e in entries if e.get("account_code") == "4400"),
            }
        return revenue

    async def get_expenses_by_year(self, years: List[int]) -> Dict[int, Dict[str, float]]:
        """Expense breakdown by year and category."""
        expenses = {}
        for year in years:
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            entries = await self.get_ledger_entries(
                start_date=start,
                end_date=end,
                account_codes=["5100", "5200", "5310", "5320", "5330", "5400"],
            )
            expenses[year] = {
                "maintenance": sum(e["debit"] for e in entries if e["account_code"] == "5100"),
                "vacancy_loss": sum(e["debit"] for e in entries if e["account_code"] == "5200"),
                "water_expense": sum(e["debit"] for e in entries if e["account_code"] == "5310"),
                "electricity_expense": sum(e["debit"] for e in entries if e["account_code"] == "5320"),
                "garbage_expense": sum(e["debit"] for e in entries if e["account_code"] == "5330"),
                "other_expenses": sum(e["debit"] for e in entries if e["account_code"] == "5400"),
            }
        return expenses

    async def calculate_taxes_by_year(self, years: List[int]) -> Dict[int, Dict[str, float]]:
        """Compute annual rental income tax based on actual cash received (payments)."""
        taxes = {}
        for year in years:
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            entries = await self.get_ledger_entries(start_date=start, end_date=end, account_codes=["1010"])
            cash_collected = sum(e["debit"] for e in entries if e.get("transaction_type") == "payment_received")
            tax_amount = cash_collected * self.tax_rate
            taxes[year] = {
                "cash_collected": cash_collected,
                "taxable_income": cash_collected,
                "tax_amount": tax_amount,
                "tax_rate": self.tax_rate,
                "effective_tax_rate": (tax_amount / cash_collected * 100) if cash_collected > 0 else 0,
            }
        return taxes

    # ----------------------------------------------------------------------
    # Balance sheet (correct tenant deposit handling)
    # ----------------------------------------------------------------------
    async def get_balance_sheet_data(self, as_of_date: datetime) -> Dict[str, float]:
        """Accurate balance sheet using account codes and keyword detection for deposits."""
        entries = await self.get_ledger_entries(end_date=as_of_date)
        balances: Dict[str, float] = {}
        for e in entries:
            account = e.get("account", "")
            code = e.get("account_code", "")
            key = account or code 
            balances[key] = balances.get(key, 0) + (e.get("debit", 0) - e.get("credit", 0))

        # assets = {
        #     "cash": balances.get("1010", 0.0) + balances.get("Cash", 0.0),
        #     "accounts_receivable": balances.get("1200", 0.0) + balances.get("Accounts Receivable", 0.0),
        # }
        receivable_codes = {
            "1201": "Rent Receivable",
            "1202": "Water Receivable",
            "1203": "Electricity Receivable",
            "1204": "Garbage Receivable",
            "1205": "Deposit Receivable",
            "1210": "Other Receivable",
        }
        receivables = {
            label: balances.get(label, 0.0) for code, label in receivable_codes.items()
        }
        receivables_total = sum(receivables.values())

        assets = {
            "cash": balances.get("1010", 0.0) + balances.get("Cash", 0.0),
            "receivables_total": receivables_total,
            **{f"{k.replace(' ', '_').lower()}": v for k, v in receivables.items()},
        }

        # Detect all tenant deposit-related liabilities (by keywords or separate liability code if you add one)
        tenant_deposits = 0.0
        for key, value in balances.items():
            low = key.lower()
            if any(kw in low for kw in ["tenant deposit","Tenant Deposit Liability", "tenant_deposit", "deposits payable", "deposit liability", "deposit"]):
                tenant_deposits += abs(value)

        liabilities = {
            "tenant_deposits": tenant_deposits,
            "tenant_credit": abs(
                balances.get("Tenant Credit", 0.0)
                + balances.get("tenant_credit", 0.0)
            ),
        }

        total_assets = sum(assets.values())
        total_liabilities = sum(liabilities.values())
        equity = {"owner_equity": total_assets - total_liabilities}

        return {"assets": assets, "liabilities": liabilities, "equity": equity}

    # ----------------------------------------------------------------------
    # Cash flow by year
    # ----------------------------------------------------------------------
    async def get_cash_flow_by_year(self, years: List[int]) -> Dict[int, Dict[str, float]]:
        """Compute yearly cash inflows and outflows."""
        flows = {}
        for year in years:
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            entries = await self.get_ledger_entries(start_date=start, end_date=end, account_codes=["1010"])
            inflows = sum(e["debit"] for e in entries)
            outflows = sum(e["credit"] for e in entries)
            flows[year] = {
                "cash_inflows": inflows,
                "cash_outflows": outflows,
                "net_cash_flow": inflows - outflows,
            }
        return flows

    # ----------------------------------------------------------------------
    # Monthly summary + metrics
    # ----------------------------------------------------------------------
    async def get_monthly_summary(self, year: int) -> Dict[int, Dict[str, float]]:
        """
        Build monthly totals for the year: revenue, expenses, NOI, cash flows, occupancy, vacancy loss.
        Returns {month: {...}}.
        """
        monthly: Dict[int, Dict[str, float]] = {}
        total_units = await self.get_units_count()

        for m in range(1, 13):
            start, end = month_bounds(year, m)

            # Revenue entries
            rev_entries = await self.get_ledger_entries(
                start_date=start, end_date=end,
                account_codes=["4100", "4210", "4220", "4230", "4300", "4400"]
            )
            total_revenue = sum(e["credit"] for e in rev_entries)

            # Expense entries
            exp_entries = await self.get_ledger_entries(
                start_date=start, end_date=end,
                account_codes=["5100", "5200", "5310", "5320", "5330", "5400"]
            )
            total_expenses = sum(e["debit"] for e in exp_entries)
            vacancy_loss = sum(e["debit"] for e in exp_entries if e.get("account_code") == "5200")

            # Cash entries
            cash_entries = await self.get_ledger_entries(
                start_date=start, end_date=end, account_codes=["1010"]
            )
            cash_in = sum(e["debit"] for e in cash_entries)
            cash_out = sum(e["credit"] for e in cash_entries)

            # Occupancy: count active leases in this month
            active_leases = await self.get_active_leases_for_month(year, m)
            occupied_units = len(active_leases)
            occupancy_rate = (occupied_units / total_units * 100) if total_units else 0.0

            monthly[m] = {
                "revenue": total_revenue,
                "expenses": total_expenses,
                "noi": total_revenue - total_expenses,
                "cash_inflows": cash_in,
                "cash_outflows": cash_out,
                "cash_net": cash_in - cash_out,
                "occupancy_rate": occupancy_rate,
                "vacancy_loss": vacancy_loss,
                "occupied_units": occupied_units,
                "total_units": total_units,
            }

        return monthly

    # ----------------------------------------------------------------------
    async def calculate_key_metrics(self, years: List[int]) -> Dict[int, Dict[str, float]]:
        """
        Compute advanced metrics for each year using ledger + leases + units.
        Returns {year: {metric_name: value}}.
        """
        results: Dict[int, Dict[str, float]] = {}
        total_units = await self.get_units_count()

        for year in years:
            # Year ranges
            start = datetime(year, 1, 1, tzinfo=timezone.utc)
            end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

            # Revenues & expenses
            revenues = await self.get_revenue_by_year([year])
            expenses = await self.get_expenses_by_year([year])
            rev = revenues[year]
            exp = expenses[year]
            total_revenue = sum(rev.values())
            total_expenses = sum(exp.values())

            rental_income = rev.get("rental_income", 0.0)
            utility_income_total = rev.get("water_income", 0.0) + rev.get("electricity_income", 0.0) + rev.get("garbage_income", 0.0)
            utility_expense_total = exp.get("water_expense", 0.0) + exp.get("electricity_expense", 0.0) + exp.get("garbage_expense", 0.0)

            # Cash collected (rent) = all cash debits tagged payment_received (assume rents)
            cash_entries = await self.get_ledger_entries(start_date=start, end_date=end, account_codes=["1010"])
            cash_collected = sum(e["debit"] for e in cash_entries if e.get("transaction_type") == "payment_received")

            # Occupancy (average across months)
            occ_sum = 0.0
            months_count = 0
            monthly = await self.get_monthly_summary(year)
            for m in monthly:
                occ_sum += monthly[m]["occupancy_rate"]
                months_count += 1
            avg_occupancy = (occ_sum / months_count) if months_count else 0.0

            # Avg rent per unit (approximate: rental income / months / avg occupied units)
            avg_occupied_units = (sum(monthly[m]["occupied_units"] for m in monthly) / months_count) if months_count else 0.0
            avg_rent_per_unit = (rental_income / months_count / avg_occupied_units) if avg_occupied_units > 0 else 0.0

            # Vacancy loss % of potential rent (use ledger 5200 / rental_income + 5200)
            vacancy_loss_total = exp.get("vacancy_loss", 0.0)
            potential_rent_approx = rental_income + vacancy_loss_total
            vacancy_loss_pct = (vacancy_loss_total / potential_rent_approx * 100) if potential_rent_approx > 0 else 0.0

            # Utility recovery ratio (income / expense)
            utility_recovery = (utility_income_total / utility_expense_total) if utility_expense_total > 0 else 0.0

            # Operating margin (NOI / total revenue)
            noi = total_revenue - total_expenses
            operating_margin = (noi / total_revenue * 100) if total_revenue > 0 else 0.0

            # Cash conversion ratio (cash collected / rental income)
            cash_conversion = (cash_collected / rental_income) if rental_income > 0 else 0.0

            # Deposit-Liability ratio (tenant deposits / total liabilities) at year end
            bs = await self.get_balance_sheet_data(end)
            total_liab = sum(bs["liabilities"].values())
            deposit_liab = bs["liabilities"].get("tenant_deposits", 0.0)
            deposit_liab_ratio = (deposit_liab / total_liab * 100) if total_liab > 0 else 0.0

            results[year] = {
                "avg_occupancy_rate": avg_occupancy,
                "avg_rent_per_unit": avg_rent_per_unit,
                "vacancy_loss_pct": vacancy_loss_pct,
                "utility_recovery_ratio": utility_recovery,
                "operating_margin_pct": operating_margin,
                "cash_conversion_ratio": cash_conversion,
                "deposit_liability_ratio_pct": deposit_liab_ratio,
            }

        return results

    # ----------------------------------------------------------------------
    # Report: Income Statement
    # ----------------------------------------------------------------------
    async def display_income_statement(self, years: List[int]):
        print("\n" + "=" * 100)
        print(f"{'INCOME STATEMENT (FROM LEDGER)':^100}")
        print("=" * 100)

        revenues = await self.get_revenue_by_year(years)
        expenses = await self.get_expenses_by_year(years)
        taxes = await self.calculate_taxes_by_year(years)

        print(f"{'Account':<40}", end="")
        for y in years:
            print(f"{y:>18}", end="")
        print("\n" + "-" * 100)

        def row(label, key, src):
            print(f"{label:<40}", end="")
            for y in years:
                print(f"{src[y].get(key, 0):>18,.2f}", end="")
            print()

        print(f"\n{'REVENUE':^100}")
        for k in [
            ("Rental Income", "rental_income"),
            ("Water Income", "water_income"),
            ("Electricity Income", "electricity_income"),
            ("Garbage Income", "garbage_income"),
            ("Maintenance Income", "maintenance_income"),
            ("Other Income", "other_income"),
        ]:
            row(f"  {k[0]}", k[1], revenues)
        print("-" * 100)

        print(f"{'Total Revenue':<40}", end="")
        totals = {}
        for y in years:
            totals[y] = sum(revenues[y].values())
            print(f"{totals[y]:>18,.2f}", end="")
        print("\n")

        print(f"{'UTILITY CONTRIBUTION (% of Total)':^100}")
        for util in ["water_income", "electricity_income", "garbage_income"]:
            print(f"{'  ' + util.replace('_', ' ').title():<40}", end="")
            for y in years:
                pct = (revenues[y][util] / totals[y] * 100) if totals[y] else 0
                print(f"{pct:>18.2f}%", end="")
            print()
        print("-" * 100)

        print(f"\n{'EXPENSES':^100}")
        for k in [
            ("Maintenance & Repairs", "maintenance"),
            ("Vacancy Loss", "vacancy_loss"),
            ("Water Expense", "water_expense"),
            ("Electricity Expense", "electricity_expense"),
            ("Garbage Expense", "garbage_expense"),
            ("Other Expenses", "other_expenses"),
        ]:
            row(f"  {k[0]}", k[1], expenses)
        print("-" * 100)

        print(f"{'Total Expenses':<40}", end="")
        exp_totals = {}
        for y in years:
            exp_totals[y] = sum(expenses[y].values())
            print(f"{exp_totals[y]:>18,.2f}", end="")
        print("\n")

        print(f"{'UTILITY PROFITABILITY (Income - Expense)':^100}")
        for util in ["water", "electricity", "garbage"]:
            print(f"{'  ' + util.title():<40}", end="")
            for y in years:
                inc = revenues[y].get(f"{util}_income", 0)
                exp = expenses[y].get(f"{util}_expense", 0)
                profit = inc - exp
                print(f"{profit:>18,.2f}", end="")
            print()
        print("-" * 100)

        print(f"\n{'TAXES':^100}")
        row("  Rental Income Tax (7.5%)", "tax_amount", taxes)
        print("-" * 100)

        print(f"{'NET OPERATING INCOME (After Tax)':<40}", end="")
        for y in years:
            noi = totals[y] - exp_totals[y] - taxes[y]["tax_amount"]
            print(f"{noi:>18,.2f}", end="")
        print("\n" + "=" * 100)

    # ----------------------------------------------------------------------
    # Report: Tax Report
    # ----------------------------------------------------------------------
    async def display_tax_report(self, years: List[int]):
        print("\n" + "=" * 100)
        print(f"{'TAX REPORT - YEAR BY YEAR':^100}")
        print("=" * 100)
        taxes = await self.calculate_taxes_by_year(years)
        for year in years:
            t = taxes[year]
            print(f"\nTAX YEAR {year}")
            print("-" * 100)
            print(f"{'Collected Rental Income (Cash-Basis):':<50} KES {t['cash_collected']:>15,.2f}")
            print(f"{'Tax Rate (7.5%)':<50} {t['tax_rate']*100:>15.2f}%")
            print(f"{'Tax Due:':<50} KES {t['tax_amount']:>15,.2f}")
        print("=" * 100)

    # ----------------------------------------------------------------------
    # Report: Balance Sheet
    # ----------------------------------------------------------------------
    async def display_balance_sheet(self, as_of_date: datetime):
        print("\n" + "=" * 100)
        print(f"{'BALANCE SHEET (FROM LEDGER)':^100}")
        print(f"{'As of ' + as_of_date.strftime('%B %d, %Y'):^100}")
        print("=" * 100)
        data = await self.get_balance_sheet_data(as_of_date)

        print(f"\n{'ASSETS':^100}")
        for k, v in data["assets"].items():
            print(f"{k.replace('_', ' ').title():<50} KES {v:>15,.2f}")
        total_assets = sum(data["assets"].values())

        print(f"\n{'LIABILITIES':^100}")
        for k, v in data["liabilities"].items():
            print(f"{k.replace('_', ' ').title():<50} KES {v:>15,.2f}")
        total_liab = sum(data["liabilities"].values())

        print(f"\n{'EQUITY':^100}")
        for k, v in data["equity"].items():
            print(f"{k.replace('_', ' ').title():<50} KES {v:>15,.2f}")
        total_equity = sum(data["equity"].values())

        print("\n" + "-" * 100)
        print(f"{'TOTAL ASSETS':<50} KES {total_assets:>15,.2f}")
        print(f"{'TOTAL LIABILITIES + EQUITY':<50} KES {total_liab + total_equity:>15,.2f}")
        print("=" * 100)

    # ----------------------------------------------------------------------
    # Report: Cash Flow Statement
    # ----------------------------------------------------------------------
    async def display_cash_flow_statement(self, years: List[int]):
        print("\n" + "=" * 100)
        print(f"{'CASH FLOW STATEMENT (FROM LEDGER)':^100}")
        print("=" * 100)
        flows = await self.get_cash_flow_by_year(years)
        print(f"{'Description':<40}", end="")
        for y in years:
            print(f"{y:>18}", end="")
        print("\n" + "-" * 100)
        for label, key in [
            ("Cash Inflows", "cash_inflows"),
            ("Cash Outflows", "cash_outflows"),
            ("Net Cash Flow", "net_cash_flow"),
        ]:
            print(f"{label:<40}", end="")
            for y in years:
                print(f"{flows[y][key]:>18,.2f}", end="")
            print()
        print("=" * 100)

    # ----------------------------------------------------------------------
    # Report: Month-to-Month Analysis (per year)
    # ----------------------------------------------------------------------
    async def display_month_to_month_analysis(self, years: List[int]):
        print("\n" + "=" * 100)
        print(f"{'MONTH-TO-MONTH ANALYSIS':^100}")
        print("=" * 100)

        month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

        for year in years:
            monthly = await self.get_monthly_summary(year)
            print(f"\n{year}")
            print("-" * 100)
            print(f"{'Month':<8}{'Revenue':>14}{'Expenses':>14}{'NOI':>14}{'Cash In':>14}{'Cash Out':>14}{'Occ%':>8}{'VacLoss':>14}")
            for m in range(1, 13):
                row = monthly.get(m, {
                    "revenue": 0, "expenses": 0, "noi": 0,
                    "cash_inflows": 0, "cash_outflows": 0,
                    "occupancy_rate": 0, "vacancy_loss": 0
                })
                print(f"{month_names[m-1]:<8}"
                      f"{row['revenue']:>14,.2f}"
                      f"{row['expenses']:>14,.2f}"
                      f"{row['noi']:>14,.2f}"
                      f"{row['cash_inflows']:>14,.2f}"
                      f"{row['cash_outflows']:>14,.2f}"
                      f"{row['occupancy_rate']:>8.1f}"
                      f"{row['vacancy_loss']:>14,.2f}")
        print("=" * 100)

    # ----------------------------------------------------------------------
    # Report: Year-over-Year Analysis (now with metrics)
    # ----------------------------------------------------------------------
    async def display_year_over_year_analysis(self, years: List[int]):
        """Clearer and safer YoY comparison, enriched with key metrics."""
        print("\n" + "=" * 100)
        print(f"{'YEAR-OVER-YEAR ANALYSIS':^100}")
        print("=" * 100)

        revenues = await self.get_revenue_by_year(years)
        expenses = await self.get_expenses_by_year(years)
        taxes = await self.calculate_taxes_by_year(years)
        metrics = await self.calculate_key_metrics(years)

        totals = {}
        for y in years:
            totals[y] = {
                "revenue": sum(revenues[y].values()),
                "expenses": sum(expenses[y].values()),
                "noi": sum(revenues[y].values()) - sum(expenses[y].values()) - taxes[y]["tax_amount"],
            }

        def safe_growth(curr, prev):
            return ((curr - prev) / prev * 100) if prev > 0 else 0.0

        for i in range(1, len(years)):
            prev, curr = years[i - 1], years[i]
            print(f"\n{curr} vs {prev}")
            print("-" * 100)

            # Revenue / Expense / NOI
            for key, label in [
                ("revenue", "Revenue Growth"),
                ("expenses", "Expense Growth"),
                ("noi", "NOI Growth"),
            ]:
                change = totals[curr][key] - totals[prev][key]
                growth = safe_growth(totals[curr][key], totals[prev][key])
                print(f"{label:<40} {growth:>15.2f}%")
                print(f"{'  Prev Year:':<40} KES {totals[prev][key]:>15,.2f}")
                print(f"{'  Curr Year:':<40} KES {totals[curr][key]:>15,.2f}")
                print(f"{'  Change:':<40} KES {change:>15,.2f}")

            # Key Metrics YoY
            print("\nKEY METRICS")
            def metric_line(name, key, suffix=""):
                prev_v = metrics[prev][key]
                curr_v = metrics[curr][key]
                delta = curr_v - prev_v
                # Show ratio as % if suffix contains '%'
                if "ratio" in key or key.endswith("_pct"):
                    print(f"{name:<40} {curr_v:>15.2f}{suffix}")
                    print(f"{'  Prev Year:':<40} {prev_v:>15.2f}{suffix}")
                    print(f"{'  Change:':<40} {delta:>15.2f}{suffix}")
                else:
                    # numeric currency values (e.g., avg rent per unit)
                    print(f"{name:<40} KES {curr_v:>14,.2f}")
                    print(f"{'  Prev Year:':<40} KES {prev_v:>14,.2f}")
                    print(f"{'  Change:':<40} KES {delta:>14,.2f}")

            metric_line("Avg Occupancy Rate", "avg_occupancy_rate", "%")
            metric_line("Avg Rent per Unit", "avg_rent_per_unit")
            metric_line("Vacancy Loss % of Potential", "vacancy_loss_pct", "%")
            metric_line("Utility Recovery Ratio (x)", "utility_recovery_ratio")
            metric_line("Operating Margin", "operating_margin_pct", "%")
            metric_line("Cash Conversion Ratio (x)", "cash_conversion_ratio")
            metric_line("Deposit-Liability Ratio", "deposit_liability_ratio_pct", "%")

        print("=" * 100)

    # ----------------------------------------------------------------------
    # Report: All-in-one
    # ----------------------------------------------------------------------
    async def display_all_reports(self, years: Optional[List[int]] = None):
        """Generate full set of financial reports (including monthly + metrics)."""
        if years is None:
            years = [2022, 2023, 2024]

        print("\n" + "=" * 100)
        print(f"{'COMPREHENSIVE FINANCIAL REPORTS':^100}")
        print(f"{'Generated from Ledger Database':^100}")
        print(f"{'Date: ' + datetime.now().strftime('%B %d, %Y %I:%M %p'):^100}")
        print("=" * 100)

        # 1) Income Statement
        await self.display_income_statement(years)

        # 2) Tax Report
        await self.display_tax_report(years)

        # 3) Balance Sheet (as of last day of the latest year)
        latest = datetime(max(years), 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        await self.display_balance_sheet(latest)

        # 4) Cash Flow Statement
        await self.display_cash_flow_statement(years)

        # 5) Month-to-Month
        await self.display_month_to_month_analysis(years)

        # 6) Year-over-Year + metrics
        await self.display_year_over_year_analysis(years)

        print("\n" + "=" * 100)
        print(f"{'END OF REPORTS':^100}")
        print("=" * 100)


# Example usage function
async def example_usage():
    """Example of how to use the FinancialReports class"""
    from motor.motor_asyncio import AsyncIOMotorClient

    # Adjust DSN / DB as needed
    client = AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
    db = client["pms_financial_optimized"]

    # Optionally pass property_id=str(ObjectId(...)) to scope reports per property
    reports = FinancialReports(db)

    # Display all reports for 2022–2024
    await reports.display_all_reports(years=[2022, 2023, 2024])

    client.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
