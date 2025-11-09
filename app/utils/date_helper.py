from datetime import date, datetime, timedelta,time
import calendar
import re
from typing import Optional, Tuple
from fastapi import HTTPException

def ensure_datetime(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        # default to midnight
        return datetime.combine(value, time.min)
    return value

def parse_period_query(period: Optional[str], default: int = 90) -> Tuple[datetime, datetime]:
    # """
    #     Parse a flexible period string into (start_datetime, end_datetime) UTC.

    #     Supports:
    #     - Keywords: today, yesterday, this_week, last_week, this_month, last_month
    #     - Rolling: last_7_days, last_3_months
    #     - Specific months or ranges: '2025-09' or '2025-09_2025-11'
    #     - Default (None): last `default` days (default=90)

    #     Returns:
    #         (start_datetime, end_datetime) such that end is *exclusive* (next midnight).
    # """
    today = date.today()
    p = (period or "").lower().strip()

    # --- Default (last N days) ---
    if not p:
        start = today - timedelta(days=default)
        end = today + timedelta(days=1)
        return ensure_datetime(start), ensure_datetime(end)

    # --- Day keywords ---
    if p == "today":
        return ensure_datetime(today), ensure_datetime(today + timedelta(days=1))

    if p == "yesterday":
        y = today - timedelta(days=1)
        return ensure_datetime(y), ensure_datetime(today)

    # --- Weeks ---
    if p == "this_week":
        start = today - timedelta(days=today.weekday())  # Monday
        end = today + timedelta(days=1)                  # include all of today
        return ensure_datetime(start), ensure_datetime(end)

    if p == "last_week":
        end = today - timedelta(days=today.weekday())    # this Monday
        start = end - timedelta(days=7)
        return ensure_datetime(start), ensure_datetime(end)

    # --- Months ---
    if p == "this_month":
        start = today.replace(day=1)
        end = today + timedelta(days=1)                  # up to tomorrow 00:00
        return ensure_datetime(start), ensure_datetime(end)

    if p == "last_month":
        first_this = today.replace(day=1)
        last_day_prev = first_this - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        end = first_this                                # exclusive
        return ensure_datetime(start), ensure_datetime(end)

    # --- Rolling periods ---
    match = re.match(r"^last_(\d+)_?(days?|months?)$", p)
    if match:
        num, unit = int(match.group(1)), match.group(2)
        if "day" in unit:
            start = today - timedelta(days=num)
            end = today + timedelta(days=1)
            return ensure_datetime(start), ensure_datetime(end)
        elif "month" in unit:
            m, y = today.month - num, today.year
            while m <= 0:
                m += 12
                y -= 1
            start = date(y, m, 1)
            end = today + timedelta(days=1)
            return ensure_datetime(start), ensure_datetime(end)

    # --- Specific month or month range ---
    month_match = re.findall(r"\d{4}-\d{2}", p)
    if len(month_match) == 1:
        y, m = map(int, month_match[0].split("-"))
        start = date(y, m, 1)
        _, last_day = calendar.monthrange(y, m)
        end = date(y, m, last_day) + timedelta(days=1)
        return ensure_datetime(start), ensure_datetime(end)

    if len(month_match) == 2:
        y1, m1 = map(int, month_match[0].split("-"))
        y2, m2 = map(int, month_match[1].split("-"))
        start = date(y1, m1, 1)
        _, last_day = calendar.monthrange(y2, m2)
        end = date(y2, m2, last_day) + timedelta(days=1)
        return ensure_datetime(start), ensure_datetime(end)

    # --- Invalid format ---
    raise HTTPException(status_code=400, detail=f"Invalid period format: {period}")
