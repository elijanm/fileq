from datetime import datetime, timedelta, timezone
from collections import defaultdict
from statistics import mean

def make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to timezone-aware UTC datetime"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt

class TenantSnapshotManager:
    """
    Manages portfolio-level snapshots for property management analytics.
    - Caches latest snapshot in DB
    - Auto-refreshes if expired (default 24h)
    - Modular: add new components easily via self.compute_<name>()
    """

    def __init__(self, db, cache_ttl_hours: int = 24):
        self.db = db
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.snapshot_type = "portfolio"

    async def get_snapshot(self, force_refresh: bool = False):
        """
        Return the latest portfolio snapshot (cached or freshly generated).
        """
        now = datetime.now(timezone.utc)
        latest = await self.db.system_snapshots.find_one(
            {"type": self.snapshot_type},
            sort=[("created_at", -1)]
        )

        if latest and not force_refresh:
            created = make_aware(latest.get("created_at"))
            if created and (now - created) < self.cache_ttl:
                print("⚡ Using cached snapshot from", created)
                return latest["data"]

        print("♻️ Cache expired or forced refresh — generating new snapshot...")
        new_snapshot = await self.generate_snapshot()
        await self.db.system_snapshots.insert_one({
            "type": self.snapshot_type,
            "created_at": now,
            "data": new_snapshot,
        })
        return new_snapshot

    async def generate_snapshot(self):
        """
        Compute all major metrics for the portfolio.
        Modular design allows adding new compute_* methods.
        """
        tenants = await self.db.property_tenants.find({}).to_list(None)
        invoices = await self.db.property_invoices.find({}).to_list(None)

        # Merge subcomponents
        active_tenants=[t for t in tenants if t.get("active") is True]
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tenants": await self.compute_tenant_metrics(active_tenants),
            "rent": await self.compute_rent_metrics(invoices, active_tenants),
            "utilities": await self.compute_utility_metrics(active_tenants),
            "trend": await self.compute_trends(),
        }
        return snapshot

    # -----------------------------------------------------------------------
    # 🧮 Metric Modules
    # -----------------------------------------------------------------------

    async def compute_tenant_metrics(self, tenants):
        total = len(tenants)
        active = len([t for t in tenants if t.get("active")])
        expiring_soon, vacated, will_vacate = [], [], []

        for t in tenants:
            lease_days = t.get("meta", {}).get("finance_metrics", {}).get("days_to_lease_expiry")
            if lease_days is None:
                continue
            if 0 <= lease_days <= 30:
                expiring_soon.append(t)
            elif lease_days < 0:
                vacated.append(t)
            elif 30 < lease_days <= 60:
                will_vacate.append(t)

        return {
            "total": total,
            "active": active,
            "active_pct": round((active / total * 100) if total else 0, 1),
            "expiring_this_month": len(expiring_soon),
            "vacated_units": len(vacated),
            "will_vacate_next_30_days": len(will_vacate),
        }

    async def compute_rent_metrics(self, invoices, tenants):
        now = datetime.now(timezone.utc)
        delayed = []
        for inv in invoices:
            due = make_aware(inv.get("due_date"))
            if not due:
                continue
            try:
                due_dt = due
            except Exception:
                continue
            if inv.get("status") in ["overdue", "unpaid", "partially_paid"] and (now - due_dt).days > 5:
                delayed.append(inv)

        avg_rent = mean([
            inv.get("total_amount", 0)
            for inv in invoices
            if any(li.get("type") == "rent" for li in inv.get("line_items", []))
        ]) if invoices else 0

        avg_delay = mean([
            t.get("meta", {}).get("finance_metrics", {}).get("avg_delay_days", 0)
            for t in tenants
            if t.get("meta", {}).get("finance_metrics")
        ]) if tenants else 0

        return {
            "delayed_invoices_count": len(delayed),
            "delayed_amount": round(sum(inv.get("balance_amount", 0) for inv in delayed), 2),
            "average_rent": round(avg_rent, 2),
            "average_payment_delay_days": round(avg_delay, 2),
        }

    async def compute_utility_metrics(self, tenants):
        totals = defaultdict(lambda: {"usage": 0, "amount": 0, "unit": None, "days": 0})
        for t in tenants:
            utils = t.get("meta", {}).get("finance_metrics", {}).get("utility_summary") or {}
            for name, data in utils.items():
                
                totals[name]["usage"] += data.get("summary",{}).get("usage_total", 0)
                totals[name]["amount"] += data.get("summary",{}).get("amount", 0)
                totals[name]["unit"] = data.get("summary",{}).get("unit")
                totals[name]["days"] += data.get("summary",{}).get("period_days", 30)

        avg_daily = {}
        for name, v in totals.items():
            days = v["days"] or 30
            avg_per_tenant = (v["usage"] / (len(tenants) or 1)) / (days / len(tenants) or 30)
            avg_daily[name] = {
                "value": round(avg_per_tenant, 3),
                "unit": v["unit"] or ""
            }

        return {
            "avg_daily_usage": avg_daily,
            "total_monthly_usage": {
                n: {
                    "usage_total": round(v["usage"], 2),
                    "amount": round(v["amount"], 2),
                    "unit": v["unit"]
                } for n, v in totals.items()
            }
        }

    async def compute_trends(self):
        """
        Compare current vs previous month's snapshot to produce deltas.
        """
        now = datetime.now(timezone.utc)
        prev_month_start = (now.replace(day=1) - timedelta(days=1)).replace(day=1)
        prev_month_end = now.replace(day=1) - timedelta(seconds=1)

        prev = await self.db.system_snapshots.find_one({
            "type": self.snapshot_type,
            "created_at": {"$gte": prev_month_start, "$lte": prev_month_end}
        })

        if not prev:
            return {}

        curr_data = await self.db.system_snapshots.find_one(
            {"type": self.snapshot_type}, sort=[("created_at", -1)]
        )
        curr = curr_data["data"] if curr_data else {}

        def delta(curr, prev):
            if not prev or prev == 0:
                return 0
            return round(((curr - prev) / prev) * 100, 1)

        trend = {}
        rent_now, rent_prev = curr.get("rent", {}), prev["data"].get("rent", {})
        trend["rent_avg_change_pct"] = delta(rent_now.get("average_rent", 0), rent_prev.get("average_rent", 0))
        trend["delay_change_pct"] = delta(rent_now.get("average_payment_delay_days", 0), rent_prev.get("average_payment_delay_days", 0))
        trend["delayed_amount_change_pct"] = delta(rent_now.get("delayed_amount", 0), rent_prev.get("delayed_amount", 0))

        utils_now = curr.get("utilities", {}).get("avg_daily_usage", {})
        utils_prev = prev["data"].get("utilities", {}).get("avg_daily_usage", {})
        for name, u_now in utils_now.items():
            if name in utils_prev:
                trend[f"{name.lower()}_usage_change_pct"] = delta(u_now["value"], utils_prev[name]["value"])

        return trend
