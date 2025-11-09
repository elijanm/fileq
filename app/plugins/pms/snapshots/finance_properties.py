import hashlib, json
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from bson import ObjectId

class FinancialSnapshotService:
    """
    Computes and caches property-level financial metrics.
    Works with async Motor and integrates with system_snapshots.
    """

    def __init__(self, db, ttl_hours: int = 6):
        self.db = db
        self.invoices_col = db.property_invoices
        self.ledger_col = db.property_ledger_entries
        self.snapshots_col = db.system_snapshots
        self.snapshot_type = "property_financials"
        self.ttl = timedelta(hours=ttl_hours)

    # -------------------------------
    # 🔹 UTILITIES
    # -------------------------------
    def _make_key(self, filters: dict, is_cache: bool = True) -> str:
        """Create a hash key for cache or reuse human period_key for snapshots."""
        if not is_cache and "period_key" in filters:
            return filters["period_key"]
        canonical = json.dumps(filters, sort_keys=True, default=str)
        return hashlib.sha1(canonical.encode()).hexdigest()

    async def _get_cached(self, period_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached snapshot if still fresh."""
        now = datetime.utcnow()
        cached = await self.snapshots_col.find_one({
            "type": self.snapshot_type,
            "period_key": period_key,
            "created_at": {"$gte": now - self.ttl}
        })
        return cached

    async def _save_snapshot(self, period_key: str, filters: dict, results: list, meta: dict):
        """Save computed snapshot to DB."""
        doc = {
            "type": self.snapshot_type,
            "period_key": period_key,
            "created_at": datetime.utcnow(),
            "data": {
                "filters": filters,
                "meta": meta,
                "results": results
            }
        }
        await self.snapshots_col.insert_one(doc)
        return doc

    async def invalidate_cache(self, property_ids: List[str]):
        """Invalidate cache entries for specific properties."""
        res = await self.snapshots_col.delete_many({
            "type": self.snapshot_type,
            "data.filters.property_ids": {"$in": property_ids}
        })
        print(f"🧹 Invalidated {res.deleted_count} cache entries for {property_ids}")

    # -------------------------------
    # 🔹 MAIN PUBLIC METHOD
    # -------------------------------
    async def get_or_refresh_snapshot(
        self,
        filters: dict,
        is_cache: bool = True,
        include_summary: bool = True
    ) -> list:
        """
        Get cached snapshot if valid, otherwise recompute and store a new one.
        """
        period_key = self._make_key(filters, is_cache)
        now = datetime.utcnow()

        if is_cache:
            cached = await self._get_cached(period_key)
            if cached:
                print(f"✅ Cache hit ({period_key[:8]}...)")
                return cached["data"]["results"]

        # Otherwise compute fresh results
        results = await self._compute_flows_and_balances(
            property_ids=filters.get("property_ids"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            include_summary=include_summary
        )

        # Gather metadata
        meta = {
            "invoice_count": await self.invoices_col.estimated_document_count(),
            "ledger_count": await self.ledger_col.estimated_document_count(),
            "generated_at": now.isoformat()
        }

        # Save cache or permanent snapshot
        saved = await self._save_snapshot(period_key, filters, results, meta)
        print(f"💾 Snapshot saved ({'cache' if is_cache else 'snapshot'}:{period_key[:8]}...)")

        return results

    # -------------------------------
    # 🔹 CORE METRIC COMPUTATION
    # -------------------------------
    async def _compute_flows_and_balances(
        self,
        property_ids: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_summary: bool = True
    ) -> List[Dict[str, Any]]:
        """Compute totals per property (async version)."""
        today = datetime.combine(date.today(), datetime.min.time())
        invoice_query, ledger_query = {}, {}

        if property_ids:
            invoice_query["property_id"] = {"$in": property_ids}
            ledger_query["property_id"] = {"$in": property_ids}

        if start_date and end_date:
            invoice_query["date_issued"] = {"$gte": start_date, "$lte": end_date}
            ledger_query["date"] = {"$gte": start_date, "$lte": end_date}

        invoices = [i async for i in self.invoices_col.find(invoice_query)]
        ledgers = [e async for e in self.ledger_col.find(ledger_query)]

        # Aggregate ledgers (Cash only)
        ledger_by_property: Dict[str, float] = {}
        for e in ledgers:
            if e.get("account") == "Cash" and e.get("property_id"):
                pid = e["property_id"]
                ledger_by_property[pid] = ledger_by_property.get(pid, 0.0) + float(e.get("debit", 0.0))

        # Group invoices
        invoice_by_property: Dict[str, List[Dict]] = {}
        for inv in invoices:
            pid = inv.get("property_id")
            if pid:
                invoice_by_property.setdefault(pid, []).append(inv)

        results = []
        totals = dict(period_invoiced=0.0, period_collected=0.0, pending_collection=0.0, overdue_balance=0.0)

        for pid, invs in invoice_by_property.items():
            total_invoiced = sum(float(i.get("total_amount", 0)) for i in invs)
            total_collected = float(ledger_by_property.get(pid, 0.0))
            total_pending = total_invoiced - total_collected if total_invoiced else 0.0

            overdue_invs = [
                i for i in invs
                if i.get("due_date") and i["due_date"] < today and i.get("status") in ["partial", "unpaid"]
            ]
            total_overdue = round(sum(float(i.get("balance_amount", 0)) for i in overdue_invs), 2)

            collection_rate = (total_collected / total_invoiced * 100) if total_invoiced else 0
            overdue_rate = (total_overdue / total_pending * 100) if total_pending else 0

            results.append({
                "property_id": pid,
                "period_invoiced": round(total_invoiced, 2),
                "period_collected": round(total_collected, 2),
                "pending_collection": round(total_pending, 2),
                "overdue_balance": total_overdue,
                "collection_rate": round(collection_rate, 1),
                "overdue_rate": round(overdue_rate, 1),
                "invoice_count": len(invs),
                "overdue_count": len(overdue_invs)
            })

            totals["period_invoiced"] += total_invoiced
            totals["period_collected"] += total_collected
            totals["pending_collection"] += total_pending
            totals["overdue_balance"] += total_overdue

        if include_summary and results:
            results.append({
                "property_id": "ALL",
                "period_invoiced": round(totals["period_invoiced"], 2),
                "period_collected": round(totals["period_collected"], 2),
                "pending_collection": round(totals["pending_collection"], 2),
                "overdue_balance": round(totals["overdue_balance"], 2),
                "collection_rate": round((totals["period_collected"] / totals["period_invoiced"] * 100) if totals["period_invoiced"] else 0.0, 1),
                "overdue_rate": round((totals["overdue_balance"] / totals["pending_collection"] * 100) if totals["pending_collection"] else 0.0, 1),
                "invoice_count": sum(r["invoice_count"] for r in results),
                "overdue_count": sum(r["overdue_count"] for r in results)
            })
        return results
