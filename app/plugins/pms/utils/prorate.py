from datetime import date, timedelta,datetime
from calendar import monthrange
from decimal import Decimal, ROUND_HALF_UP

def format(x) -> int:
    return int(Decimal(str(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def month_bounds(any_day: date) -> tuple[date, date, int]:
    first = date(any_day.year, any_day.month, 1)
    last = date(any_day.year, any_day.month, monthrange(any_day.year, any_day.month)[1])
    days_in_month = (last - first).days + 1
    return first, last, days_in_month

def next_month(any_day: date) -> date:
    y, m = any_day.year, any_day.month
    if m == 12:
        return date(y + 1, 1, 1)
    return date(y, m + 1, 1)

def prorated_rent_charges(
    monthly_rent: int | float,
    contract_start: date,
    basis: str = "actual",       # "actual" or "30day"
    include_start_day: bool = True,
    rent_prefix:str=None
):
    """
    Returns line items for the first invoice(s) per rule:
      - If contract_start is not the 1st -> prorate remainder of that month + full next month.
      - If contract_start is the 1st -> full current month only.
    """
    first_day, last_day, days_in_month = month_bounds(contract_start)
    
    def to_datetime(d):
        return datetime.combine(d, datetime.min.time())
    # If starting on 1st → just full month
    if contract_start == first_day:
        return {
            "line_items": [
                {
                    "description": f"Rent {contract_start.strftime('%B %Y')} (full month)",
                    "period": (to_datetime(first_day), to_datetime(last_day)),
                    "amount": format(monthly_rent)
                }
            ],
            "total_amount": format(monthly_rent)
        }

    # Prorate for the start month
    denom = 30 if basis == "30day" else days_in_month
    start_bill = contract_start if include_start_day else (contract_start + timedelta(days=1))
    if start_bill > last_day:
        prorated_days = 0
    else:
        prorated_days = (last_day - start_bill).days + 1  # inclusive

    daily = Decimal(str(monthly_rent)) / Decimal(denom)
    prorated_amount = format(daily * prorated_days)

    # Full next month
    nm = next_month(contract_start)
    nm_first, nm_last, _ = month_bounds(nm)
    full_next_amount = format(monthly_rent)
    if rent_prefix:
        rent_prefix=f"{rent_prefix}, "
    line_items = []
    if prorated_days > 0:
        line_items.append({
            "description": f"{rent_prefix}Prorated rent {contract_start.strftime('%b %d')}-{last_day.strftime('%b %d, %Y')}",
            "period": (to_datetime(start_bill), to_datetime(last_day)),
            "days_billed": prorated_days,
            "denominator_days": denom,
            "amount": prorated_amount
        })

    line_items.append({
        "description": f"{rent_prefix}Rent {nm_first.strftime('%B %Y')} (full month)",
        "period": (to_datetime(nm_first), to_datetime(nm_last)),
        "amount": full_next_amount
    })

    return {
        "line_items": line_items,
        "total_amount": sum(i["amount"] for i in line_items)
    }

# from datetime import date
# import json
# res = initial_rent_charges(25000, date(2025, 11, 1))  # Oct 20 start
# print(json.dumps(res,indent=4, default=str))