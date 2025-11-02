import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import calendar
from collections import defaultdict


from datetime import datetime, timezone
from collections import defaultdict
from statistics import mean
def safe_date(value):
    """Return a proper datetime object from nested or plain date values."""
    if not value:
        return None
    # Case 1: Already a datetime
    if isinstance(value, datetime):
        return value
    # Case 2: Wrapped dict {"$date": "..."}
    if isinstance(value, dict) and "$date" in value:
        value = value["$date"]
    # Case 3: String form
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    

def summarize_utilities_for_tenant(invoices: list):
    """
    Given all invoices for one tenant, compute both:
    1. Average utility usage summary (per type)
    2. Month-by-month utility trends for graphing
    """
    utilities = defaultdict(list)

    for inv in invoices:
        for item in inv.get("line_items", []):
            meta = item.get("meta", {})
            if item.get("type") != "utility" or meta.get("billing_basis") != "metered":
                continue

            name = item.get("utility_name")
            usage = meta.get("usage") or (
                (meta.get("current_reading", 0) - meta.get("previous_reading", 0))
            )
            rate = meta.get("rate", 0)
            amount = item.get("amount", 0)
            unit = meta.get("unit_of_measure")
            period = meta.get("period") or (inv.get("meta", {}).get("billing_period") or "unknown")

            # Estimate days in billing cycle
            reading_date = safe_date(meta.get("reading_date"))
            issued_date = safe_date(inv.get("date_issued"))
            days = 30
            if reading_date and issued_date:
                try:
                    d1 = datetime.fromisoformat(str(issued_date).replace("Z", "+00:00"))
                    d2 = datetime.fromisoformat(str(reading_date).replace("Z", "+00:00"))
                    days = max((d2 - d1).days, 1)
                except Exception:
                    pass

            utilities[name].append({
                "usage_total": usage,
                "usage_avg_per_day": usage / days if days > 0 else 0,
                "unit": unit,
                "period_days": days,
                "rate": rate,
                "amount": amount,
                "period": period
            })

    # ---- aggregate ----
    summary = {}
    for name, records in utilities.items():
        summary[name] = {
            "summary": {
                "usage_total": round(mean([r["usage_total"] for r in records]), 3),
                "usage_avg_per_day": round(mean([r["usage_avg_per_day"] for r in records]), 3),
                "unit": records[0]["unit"],
                "period_days": round(mean([r["period_days"] for r in records]), 1),
                "rate": round(mean([r["rate"] for r in records]), 2),
                "amount": round(mean([r["amount"] for r in records]), 2),
            },
            "month_by_month": sorted([
                {
                    "period": r["period"],
                    "usage": round(r["usage_total"], 3),
                    "amount": round(r["amount"], 2)
                }
                for r in records if r.get("period") != "unknown"
            ], key=lambda x: x["period"])
        }

    return summary


def compute_consistency_score(payment_volatility_score: float,
                              trend_score: float,
                              invoices_count: int) -> float:
    """
    payment_volatility_score: 0–100 (higher = more erratic)
    trend_score: -100–100 (positive = improving)
    invoices_count: number of invoices available for trend calc
    """

    # ---- Normalize inputs ----
    payment_volatility_score = max(0, min(payment_volatility_score, 100))
    trend_score = max(-100, min(trend_score, 100))

    # ---- Dynamically adjust weights ----
    if invoices_count < 3:
        # not enough data; rely almost entirely on volatility
        volatility_weight = 0.95
        trend_weight = 0.05
    elif invoices_count < 6:
        # moderate history
        volatility_weight = 0.80
        trend_weight = 0.20
    else:
        # strong historical base, trend becomes more meaningful
        volatility_weight = 0.65
        trend_weight = 0.35

    # ---- Combine into composite consistency ----
    consistency_score = (100 - (payment_volatility_score * volatility_weight)) \
                        + (trend_score * trend_weight)

    # Clamp 0–100
    consistency_score = max(0, min(consistency_score, 100))
    return round(consistency_score, 2)


def apply_early_bonus(risk_score, total_early_days, on_time_payments):
    avg_early_days = (total_early_days / on_time_payments) if on_time_payments > 0 else 0
    early_bonus = min(avg_early_days * 1.5, 15)   # Up to 15-point benefit
    new_risk_score = max(0, risk_score - early_bonus)
    return round(new_risk_score, 2)

def log_if_abnormal(metrics: dict):
    # detect extreme values that could distort risk
    abnormal = {k: v for k, v in metrics.items() if abs(v) > 120 or v < 0}
    if abnormal:
        print("⚠️ Abnormal metric values detected:")
        for key, val in abnormal.items():
            print(f"   - {key}: {val}")
        print("   Full metrics snapshot:")
        for key, val in metrics.items():
            print(f"     {key:<25} {val}")
        print("-" * 60)
def sanity_check_scores(components: dict, label: str = ""):
    """
    Check all scoring components for correct scale (0–100 range).
    Highlights anomalies or mis-scaled metrics.
    """
    print(f"\n📊 Sanity Check for {label or 'Tenant'}")
    print("-" * 50)

    for key, value in components.items():
        try:
            v = float(value)
        except (TypeError, ValueError):
            
            import json
            try:
                print(json.dumps(value,indent=4,default=str))
            except Exception:
                print(f"⚠️  {key:<25} → non-numeric ({value})")
            continue

        # classify status
        if v < 0:
            status = "🔴 NEGATIVE"
        elif v > 100:
            status = "🟡 >100 (possible ×100 mistake)"
        elif v <= 1:
            status = "🟢 Fractional (likely needs ×100 scaling)"
        elif 0 <= v <= 100:
            status = "✅ OK"
        else:
            status = "⚠️ Unknown"

        print(f"{key:<25} {v:>8.2f}   {status}")

    print("-" * 50)


def auto_datetime(value):
    """
    Convert various date formats into a Python datetime object.
    Handles:
      - datetime objects
      - ISO 8601 strings
      - MongoDB {"$date": "..."} objects
      - Milliseconds since epoch
      - None or invalid input (returns None)
    """
    if not value:
        return None

    # Already a datetime
    if isinstance(value, datetime):
        return value

    # MongoDB-style dict
    if isinstance(value, dict) and "$date" in value:
        value = value["$date"]

    # Epoch milliseconds or seconds
    if isinstance(value, (int, float)):
        # Heuristic: > 10^11 → ms, else seconds
        if value > 1e11:
            value = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
        else:
            value = datetime.fromtimestamp(value, tz=timezone.utc)
        return value

    # ISO8601 or similar string
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            # Try a fallback parser if the string is not strict ISO
            from dateutil import parser
            try:
                return parser.parse(value)
            except Exception:
                return None

    return None

def make_aware(dt: datetime) -> datetime:
    """Convert naive datetime to timezone-aware UTC datetime"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt
def days_to_lease_expiry(end_date):
    if not end_date:
        return None
    end_date = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
    today = datetime.now(timezone.utc)
    return (make_aware(auto_datetime(end_date)) - make_aware(auto_datetime(today))).days

def generate_recommendations(
    late_payment_score: float,
    outstanding_score: float,
    consistency_score: float,
    avg_delay_score: float,
    tenure_score: float,
    risk_score: float
) -> List[Dict[str, str]]:
    """
    Generate structured recommendations based on scored risk metrics (0–100 scale).
    Returns a list of dicts with severity and message keys.
    """

    recommendations: List[Dict[str, str]] = []

    # 1️⃣ Late payments (frequency & severity combined)
    if late_payment_score > 60:
        recommendations.append({
            "type": "warning",
            "message": "High late payment score – consider automated reminders or tighter payment terms."
        })
    elif 40 < late_payment_score <= 60:
        recommendations.append({
            "type": "info",
            "message": "Moderate late payments – review due date reminders or grace period settings."
        })

    # 2️⃣ Outstanding balance
    if outstanding_score > 70:
        recommendations.append({
            "type": "critical",
            "message": "Significant outstanding balance – initiate follow-up or consider a structured payment plan."
        })
    elif 40 < outstanding_score <= 70:
        recommendations.append({
            "type": "warning",
            "message": "Moderate outstanding balance – maintain close communication with tenant."
        })

    # 3️⃣ Consistency trend
    if consistency_score > 60:
        recommendations.append({
            "type": "warning",
            "message": "Recent payment pattern worsening – schedule a review or tenant meeting."
        })

    # 4️⃣ Average delay severity
    if avg_delay_score > 70:
        recommendations.append({
            "type": "critical",
            "message": "High average delay in payments – review late fee policy or enforce stricter follow-ups."
        })
    elif 40 < avg_delay_score <= 70:
        recommendations.append({
            "type": "info",
            "message": "Moderate payment delays – send gentle reminders ahead of due dates."
        })

    # 5️⃣ Tenure factor
    if tenure_score < 40:
        recommendations.append({
            "type": "warning",
            "message": "Short tenant tenure – monitor payment behavior closely during the first few months."
        })
    elif tenure_score > 80:
        recommendations.append({
            "type": "info",
            "message": "Long-term tenant – consider loyalty incentives or early renewal offers."
        })

    # 6️⃣ Overall risk score
    if risk_score > 70:
        recommendations.append({
            "type": "critical",
            "message": "HIGH RISK – consider legal notice, stricter payment terms, or eviction if unresolved."
        })
    elif 40 < risk_score <= 70:
        recommendations.append({
            "type": "warning",
            "message": "Medium risk – monitor tenant activity closely and maintain proactive communication."
        })
    else:
        recommendations.append({
            "type": "info",
            "message": "Low risk – continue regular monitoring and maintain good relationship practices."
        })

    # Return top 3 to avoid overload
    return recommendations
def safe_avg(total: float, count: float) -> float:
    try:
        return round(total / count, 2) if count and count > 0 else 0.0
    except ZeroDivisionError:
        return 0.0
    
class AdvancedRentAnalytics:
    """Advanced analytics and predictive insights"""
    
    def __init__(self, db):
        self.db = db
    
    async def get_tenant_risk_score(self, tenant_id: str,print_=True) -> Dict:
        """
        Calculate risk score for tenant based on payment behavior
        
        Risk factors:
        - Late payment frequency
        - Outstanding balance amount
        - Payment consistency
        - Length of relationship
        - Credit balance usage
        
        Returns:
            Risk assessment with score 0-100 (0=low risk, 100=high risk)
        """
        
        if isinstance(tenant_id, str):
            tenant_id = ObjectId(tenant_id)
        if print_:
            print("\n" + "=" * 80)
            print(f" TENANT RISK ASSESSMENT")
            print("=" * 80)
        
        tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
        if not tenant:
            return {"error": "Tenant not found"}
        
        
       
        prop_id = tenant.get("property_id")
        unit_ids = tenant.get("units_id", [])

        property_data = None
        units_data = []
        has_no_property_meta=tenant.get("meta",{}).get("property",None)==None
        # Fetch property info
        if has_no_property_meta:
            property_data = await  self.db.properties.find_one(
                {"_id": str(prop_id)},
                {"name": 1, "location": 1, "type": 1}
            )

            # Fetch units info
            if unit_ids:
                async for unit in self.db.units.find({"_id": {"$in": [str(uid) for uid in unit_ids]}}, {"unitName": 1, "unitNumber": 1}):
                    units_data.append({
                        "unitName": unit.get("unitName"),
                        "unitNumber": unit.get("unitNumber")
                    })

            update_data = {}
            if property_data:
                update_data["meta.property"] = {
                    "name": property_data.get("name"),
                    "location": property_data.get("location"),
                    "type": property_data.get("type")
                }
            if units_data:
                update_data["meta.property"]['units'] = units_data

            if update_data:
                await self.db.property_tenants.update_one(
                    {"_id": tenant_id},
                    {"$set": update_data}
                )
                tenant["meta"]=tenant["meta"]|update_data
                print(f"✅ Updated tenant {tenant.get('full_name', tenant_id)} with property & unit info.")
        
        # Get all invoices
        invoices_cursor = self.db.property_invoices.find({
            "tenant_id": ObjectId(tenant_id)
        }).sort("date_issued", 1)
        invoices = await invoices_cursor.to_list(length=None)
        
        if not invoices:
            return {
                "tenant_id": str(tenant_id),
                "tenant_name": tenant.get("full_name"),
                "risk_score": 0,
                "risk_level": "LOW",
                "message": "No payment history",
                "risk_components":{} ,
                "metrics": {
                    "tenant_name": tenant.get("full_name"),
                    "property":tenant.get("meta",{}).get("property")
                }
            }
        
        # Calculate risk factors
        total_invoices = len(invoices) or 1
        late_payments = 0
        on_time_payments = 0
        total_delay_days = 0
        delayed_invoices = 0
        total_early_days=0
        total_days_to_pay=0
        paid_invoices=0
        total_create_to_issue_days = 0
        issued_invoices = 0
        total_partials=0
        total_outstanding = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        
            
        total_expected = sum(inv.get("total_amount", 0) for inv in invoices)
        total_paid = sum(inv.get("total_paid", 0) for inv in invoices)
        collection_rate = (total_paid / total_expected) if total_expected > 0 else 0
        delay_offsets = []  # positive = days late, negative = days early    
        # Count on-time payments
       
        for inv in invoices:
            status = inv.get("status")
            # Check if paid before due date
            due_date   = inv.get("due_date")
            date_issued = inv.get("date_issued")
            created_at = inv.get("created_at")
            
            if created_at and date_issued:
                created_at = make_aware(auto_datetime(created_at))
                date_issued = make_aware(auto_datetime(date_issued))
                days_between = (date_issued - created_at).days
                total_create_to_issue_days += max(days_between, 0)
                issued_invoices += 1
            
            if status in ["overdue","unpaid"]:
                late_payments += 1
                delayed_invoices += 1
                
            elif inv.get("status") in ["paid","partial","partially_paid"]:
               
                if inv.get("status") in ["paid"]:
                    paid_invoices+=1
                    
                if due_date:
                    # first_payment = min(payments, key=lambda p: p.get("payment_date", datetime.max))
                    payment_date = make_aware(auto_datetime(inv.get("payment_date")))
                    due_date = make_aware(auto_datetime(due_date))
                    
                    if payment_date and due_date:
                        offset_days = (payment_date - due_date).days
                        delay_offsets.append(offset_days)
                    
                    if payment_date and date_issued:
                        days_to_pay = (payment_date - make_aware(auto_datetime(date_issued))).days
                        total_days_to_pay += days_to_pay
                    if payment_date and payment_date <= due_date:
                        on_time_payments += 1
                        early_days = (due_date - payment_date).days
                        total_early_days += early_days
                        
                        
                    else:
                        late_payments += 1
                        delay_days = max((payment_date - due_date).days, 0)
                        total_delay_days += delay_days
                        delayed_invoices += 1
                        
        
        # on_time_ratio = on_time_payments / len(invoices) if invoices else 0
        # on_time_rate = (on_time_payments / len(invoices) * 100) if invoices else 0
        # avg_delay = total_delay_days / delayed_invoices if delayed_invoices > 0 else 0
        # avg_early = (total_early_days / on_time_payments) if on_time_payments>0 else 0
        # avg_days_to_pay = (total_days_to_pay / paid_invoices) if paid_invoices > 0 else 0
        # avg_create_to_issue = (total_create_to_issue_days / issued_invoices) if issued_invoices>0 else 0
        on_time_ratio      = safe_avg(on_time_payments, len(invoices))
        on_time_rate       = round(on_time_ratio * 100, 2) # expressed as %
        avg_delay          = safe_avg(total_delay_days, delayed_invoices)
        avg_early          = safe_avg(total_early_days, on_time_payments)
        avg_days_to_pay    = safe_avg(total_days_to_pay, paid_invoices)
        avg_create_to_issue = safe_avg(total_create_to_issue_days, issued_invoices)
        
        import statistics

        if len(delay_offsets) >= 2:
            volatility_days = statistics.stdev(delay_offsets)
        else:
            volatility_days = 0
        payment_volatility_score = min((volatility_days / 10) * 100, 100)
        extra_info={"rent_payment_history": {
            "on_time": on_time_payments,
            "late": late_payments,
            "partial": total_partials,
            "total": total_invoices,
            "summary": f"On-time ({on_time_payments}/{total_invoices}), Late ({late_payments}/{total_invoices}), Partial ({total_partials}/{total_invoices})"
        },"extra":{
        "maintenance_requests_count": 0,
        "lease_violations_count": 0,
        "move_out_notice_given": 0,
        "tenant_satisfaction_score": 0
        }
        }
        
            
        
        # Late payment calculation
        # for inv in invoices:
        #     due_date = inv.get("due_date")
        #     status = inv.get("status")
            
        #     if status in ["overdue", "partially_paid","partial","unpaid"]:
        #         late_payments += 1
        #         print("late p")
        #     elif status == "paid":
        #         # Check if paid after due date
        #         payments = inv.get("payments", [])
        #         if payments and due_date:
        #             last_payment = max(payments, key=lambda p: p.get("payment_date", datetime.min))
        #             payment_date = last_payment.get("payment_date")
        #             if payment_date and payment_date > due_date:
        #                 print("late p")
        #                 late_payments += 1
        #             else:
        #                 print("on time")
        #                 on_time_payments += 1
        
        # Calculate individual risk components (0-100 scale)
     
        # 1. Late payment ratio (40% weight)
        overdue_count = sum(1 for inv in invoices if inv.get("status") in ["overdue"])
        partial_count = sum(1 for inv in invoices if inv.get("status") in ["partially_paid","unpaid","partial"])
        unpaid_count = sum(1 for inv in invoices if inv.get("status") in ["unpaid","issued"])
        
        effective_late_ratio = (
            (overdue_count * 1.0) +     # Full weight for invoices past due with no payment
            (partial_count * 0.5) +     # Half weight for invoices with partial payment
            (unpaid_count * 0.2)        # Low weight for invoices not yet due but unpaid
        ) / total_invoices

        late_payment_score = min(effective_late_ratio * 100, 100)
        
        
        # print(f"[DEBUG] overdue={overdue_count}, partial={partial_count}, unpaid={unpaid_count}, total={total_invoices}, late_score={late_payment_score}")
        # from collections import Counter

        # # normalize all statuses to lowercase
        # status_counter = Counter(str(inv.get("status", "")).strip().lower() for inv in invoices if inv.get("status"))

        # print("📊 Invoice Status Counts:")
        # for status, count in status_counter.items():
        #     print(f"   {status:<20} {count}")
        # late_payment_ratio=effective_late_ratio
        # late_payment_ratio = late_payments / total_invoices if total_invoices > 0 else 0
        # late_payment_score = late_payment_ratio * 100
        
        # 2. Outstanding balance (30% weight)
        # Get expected monthly rent
        lease = await self.db.property_leases.find_one({"tenant_id": ObjectId(tenant_id)})
        monthly_rent = lease["lease_terms"]["rent_amount"] if lease else 15000
        outstanding_months = total_outstanding / monthly_rent if monthly_rent > 0 else 0
        outstanding_score = min(outstanding_months * 25, 100)  # 4+ months = max score
        
        lease_end_date = lease["lease_terms"]["end_date"] if lease else None
        if lease_end_date:
            days_to_expiry = days_to_lease_expiry(lease_end_date)
        else:
            days_to_expiry = None
        
        # 3. Payment consistency (20% weight)
        # Check if there's a pattern of increasing late payments
        # recent_invoices = invoices[-6:] if len(invoices) >= 6 else invoices
        
        # status_weights = {
        #     "overdue": 1.0,           # full late
        #     "partial": 0.5,
        #     "partially_paid": 0.5,    # half late
        #     "unpaid": 0.2             # not yet paid, but maybe not overdue
        # }

        # recent_late_score = 0
        # for inv in recent_invoices:
        #     status = inv.get("status", "").lower()
        #     recent_late_score += status_weights.get(status, 0)
        # recent_late = sum(1 for inv in recent_invoices if inv.get("status") in ["overdue", "partially_paid","unpaid","partial"])
        
   
        mid = len(delay_offsets) // 2
        past_avg = sum(delay_offsets[:mid]) / max(mid, 1)
        recent_avg = sum(delay_offsets[mid:]) / max(len(delay_offsets) - mid, 1)
        trend_score = min(max((past_avg - recent_avg) * 10, -100), 100)
        trend_score = max(min((past_avg - recent_avg) * 10, 100), -100)
        # Positive trend_score → paying earlier lately (improving)

        # Negative → getting later (declining)
        # consistency_score = (100 - (payment_volatility_score * 0.8)) + (trend_score * 0.4)
        # consistency_score = max(0, min(consistency_score, 100))
        consistency_score = compute_consistency_score(payment_volatility_score, trend_score, len(invoices))

        # consistency_score = max(0, (100 - payment_volatility_score) + (trend_score * 0.1))
        
        # 4. Tenure factor (10% weight) - longer tenure = lower risk
        joined_date = tenant.get("joined_at", datetime.now(timezone.utc))
        days_as_tenant = (datetime.now(timezone.utc) - make_aware(joined_date)).days
        months_as_tenant = days_as_tenant / 30
        tenure_score = max(0, 100 - (months_as_tenant * 5))  # Decrease by 5 per month
         # 4. pay daelay factor (10% weight) - longer tenure = lower risk
        avg_delay_score = min((avg_delay / 30) * 100, 100)  # 0–30 days normalized
        
        collection_score = (1 - collection_rate) * 100
        avg_days_score = min((avg_days_to_pay / 30) * 100, 100)
        create_to_issue_score = min((avg_create_to_issue / 10) * 100, 100)

        # Calculate weighted risk score
        # risk_score = (
        #     (late_payment_score * 0.35) +
        #     (outstanding_score * 0.30) +
        #     (consistency_score * 0.20) +
        #     (avg_delay_score * 0.10) +
        #     (tenure_score * 0.05)
        # )
        avg_early_days = safe_avg(total_early_days, on_time_payments)
        early_payment_score = 100 - min(avg_early_days * 10, 100)
    
        metrics = {
            "late_payment_score": late_payment_score,
            "outstanding_score": outstanding_score,
            "consistency_score": consistency_score,
            "avg_delay_score": avg_delay_score,
            "avg_days_score": avg_days_score,
            "payment_volatility_score": payment_volatility_score,
            "collection_score": collection_score,
            "create_to_issue_score": create_to_issue_score,
            "tenure_score": tenure_score,
            "early_payment_score":early_payment_score,
            "delay_offsets":delay_offsets
        }

        # log_if_abnormal(metrics)
        sanity_check_scores(metrics, label=f"Tenant {tenant.get('full_name')}")
        
        risk_score = (
            (late_payment_score * 0.23) +     # Frequency of late payments
            (outstanding_score * 0.23) +      # Outstanding balance exposure
            (consistency_score * 0.15) +      # Recent worsening trend
            (avg_delay_score * 0.10) +        # Severity of lateness
            (avg_days_score * 0.07) +         # Real lag from issue to payment
            (payment_volatility_score * 0.05) +  # Predictability of payment timing
            (collection_score * 0.05) +       # Actual collection efficiency
            (create_to_issue_score * 0.04) +  # Internal billing delay
            (tenure_score * 0.03) -           # Loyalty & relationship duration
            (early_payment_score * 0.05)      # 🟢 Reward for early payments
        )
        # risk_score = apply_early_bonus(risk_score, total_early_days, on_time_payments)

        # Determine risk level
        if risk_score < 30:
            risk_level = "LOW"
            color = "🟢"
        elif risk_score < 60:
            risk_level = "MEDIUM"
            color = "🟡"
        else:
            risk_level = "HIGH"
            color = "🔴"
        
        # Generate recommendations
        risk_components={
                "late_payment_score": round(late_payment_score, 2),
                "outstanding_score": round(outstanding_score, 2),
                "consistency_score": round(consistency_score, 2),
                "tenure_score": round(tenure_score, 2),
                "avg_delay_score":round(avg_delay_score,2),
                "risk_score": round(risk_score, 2),
                
            }
        recommendations = generate_recommendations(**risk_components)
        comps={
            "risk_level": risk_level,
            "payment_volatility_score":round(payment_volatility_score,2),
            "trend_score":round(trend_score,2),
            "early_payment_score":round(early_payment_score,2)
        }
        
        result = {
            "tenant_id": str(tenant_id),
            "tenant_name": tenant.get("full_name"),
            "tenant_phone": tenant.get("phone"),
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "risk_components":risk_components|comps ,
            "metrics": {
                "tenant_name": tenant.get("full_name"),
                "property":tenant.get("meta",{}).get("property"),
                "total_invoices": total_invoices,
                "late_payments": late_payments,
                "on_time_payments": on_time_payments,
                "late_payment_ratio": round(late_payment_score, 2),
                "total_outstanding": round(total_outstanding, 2),
                "outstanding_months": round(outstanding_months, 2),
                "months_as_tenant": round(months_as_tenant, 1),
                "collection_rate": round(collection_rate, 2),
                "on_time_rate": round(on_time_rate, 2),
                "total_invoice_paid": round(total_paid, 2),
                "avg_delay_days":round(avg_delay, 2),
                "on_time_ratio":round(on_time_ratio, 2),
                "avg_early":round(avg_early, 2),
                "avg_days_to_pay":round(avg_days_to_pay, 2),
                "avg_create_to_issue":round(avg_create_to_issue, 2),
                "days_to_lease_expiry":days_to_expiry,
                "utility_summary":summarize_utilities_for_tenant(invoices),
                "behavior_metrics":extra_info
            },
            "recommendations": recommendations,
           
        }
        if print_:
           self._print_risk_assessment(result, color)
        
        return result
    
    def _print_risk_assessment(self, data: Dict, color: str):
        """Print risk assessment"""
        
        print(f"\n{color} RISK LEVEL: {data['risk_level']} (Score: {data['risk_score']}/100)")
        print(f"\n👤 Tenant: {data['tenant_name']}")
        print(f"   Phone: {data['tenant_phone']}")
        
        print(f"\n📊 Risk Components:")
        rc = data['risk_components']
        print(f"   Late Payments (40%): {rc['late_payment_score']:.1f}/100")
        print(f"   Outstanding Balance (30%): {rc['outstanding_score']:.1f}/100")
        print(f"   Payment Consistency (20%): {rc['consistency_score']:.1f}/100")
        print(f"   Tenure Factor (10%): {rc['tenure_score']:.1f}/100")
        
        print(f"\n💳 Payment Metrics:")
        m = data['metrics']
        print(f"   Total Invoices: {m['total_invoices']}")
        print(f"   Late Payments: {m['late_payments']} ({m['late_payment_ratio']:.1f}%)")
        print(f"   On-Time Payments: {m['on_time_payments']}")
        print(f"   Outstanding: KES {m['total_outstanding']:,.2f} ({m['outstanding_months']:.1f} months)")
        print(f"   Tenure: {m['months_as_tenant']:.1f} months")
        
        if data['recommendations']:
            print(f"\n⚠️  Recommendations:")
            for i, rec in enumerate(data['recommendations'], 1):
                print(f"   {i}. {rec}")
    
    async def get_property_portfolio_dashboard(self) -> Dict:
        """
        Complete portfolio dashboard across all properties
        
        Returns:
            Comprehensive portfolio metrics
        """
        
        print("\n" + "=" * 80)
        print(f" PORTFOLIO DASHBOARD - ALL PROPERTIES")
        print("=" * 80)
        
        # Get all properties
        properties_cursor = self.db.properties.find({})
        properties = await properties_cursor.to_list(length=None)
        
        portfolio_data = {
            "total_properties": len(properties),
            "total_units": 0,
            "total_occupied": 0,
            "portfolio_occupancy_rate": 0,
            "total_monthly_rent": 0,
            "total_outstanding": 0,
            "total_collected_this_month": 0,
            "portfolio_collection_rate": 0,
            "property_breakdown": []
        }
        
        current_date = datetime.now(timezone.utc)
        current_month_start = datetime(current_date.year, current_date.month, 1, tzinfo=timezone.utc)
        
        for prop in properties:
            property_id = prop["_id"]
            
            # Get units
            total_units = await self.db.units.count_documents({"property_id": property_id})
            
            # Get active leases
            active_leases_cursor = self.db.property_leases.find({
                "property_id": property_id,
                "status": "signed"
            })
            active_leases = await active_leases_cursor.to_list(length=None)
            
            occupied_units = len(active_leases)
            occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
            
            # Expected monthly rent
            expected_rent = sum(lease["lease_terms"]["rent_amount"] for lease in active_leases)
            
            # Get current month invoices
            month_invoices_cursor = self.db.property_invoices.find({
                "property_id": property_id,
                "date_issued": {"$gte": current_month_start}
            })
            month_invoices = await month_invoices_cursor.to_list(length=None)
            
            collected_this_month = sum(inv.get("total_paid", 0) for inv in month_invoices)
            expected_this_month = sum(inv.get("total_amount", 0) for inv in month_invoices)
            
            # Outstanding for property
            outstanding_cursor = self.db.property_invoices.find({
                "property_id": property_id,
                "balance_amount": {"$gt": 0}
            })
            outstanding_invoices = await outstanding_cursor.to_list(length=None)
            property_outstanding = sum(inv.get("balance_amount", 0) for inv in outstanding_invoices)
            
            collection_rate = (collected_this_month / expected_this_month ) if expected_this_month > 0 else 0
            
            property_data = {
                "property_id": property_id,
                "property_name": prop.get("name"),
                "location": prop.get("location"),
                "total_units": total_units,
                "occupied_units": occupied_units,
                "occupancy_rate": round(occupancy_rate, 2),
                "expected_monthly_rent": round(expected_rent, 2),
                "collected_this_month": round(collected_this_month, 2),
                "expected_this_month": round(expected_this_month, 2),
                "collection_rate": round(collection_rate*100, 2),
                "outstanding": round(property_outstanding, 2)
            }
            
            portfolio_data["property_breakdown"].append(property_data)
            portfolio_data["total_units"] += total_units
            portfolio_data["total_occupied"] += occupied_units
            portfolio_data["total_monthly_rent"] += expected_rent
            portfolio_data["total_outstanding"] += property_outstanding
            portfolio_data["total_collected_this_month"] += collected_this_month
        
        # Calculate portfolio-level metrics
        portfolio_data["portfolio_occupancy_rate"] = round(
            (portfolio_data["total_occupied"] / portfolio_data["total_units"] * 100) 
            if portfolio_data["total_units"] > 0 else 0, 2
        )
        
        # Sort properties by collection rate
        portfolio_data["property_breakdown"].sort(key=lambda x: x["collection_rate"])
        
        self._print_portfolio_dashboard(portfolio_data)
        
        return portfolio_data
    
    def _print_portfolio_dashboard(self, data: Dict):
        """Print portfolio dashboard"""
        
        print(f"\n🏢 Portfolio Overview:")
        print(f"   Total Properties: {data['total_properties']}")
        print(f"   Total Units: {data['total_units']}")
        print(f"   Occupied Units: {data['total_occupied']}")
        print(f"   Portfolio Occupancy: {data['portfolio_occupancy_rate']:.1f}%")
        
        print(f"\n💰 Financial Summary:")
        print(f"   Expected Monthly Rent: KES {data['total_monthly_rent']:,.2f}")
        print(f"   Collected This Month: KES {data['total_collected_this_month']:,.2f}")
        print(f"   Total Outstanding: KES {data['total_outstanding']:,.2f}")
        
        print(f"\n📊 Property Performance:")
        print(f"   {'Property':<30} {'Occupancy':>10} {'Collection':>12} {'Outstanding':>12}")
        print(f"   {'-'*70}")
        
        for prop in data['property_breakdown']:
            occ_emoji = "✅" if prop['occupancy_rate'] >= 90 else "⚠️" if prop['occupancy_rate'] >= 70 else "🔴"
            col_emoji = "✅" if prop['collection_rate'] >= 90 else "⚠️" if prop['collection_rate'] >= 70 else "🔴"
            
            print(f"   {prop['property_name']:<30} "
                  f"{occ_emoji} {prop['occupancy_rate']:>6.1f}% "
                  f"{col_emoji} {prop['collection_rate']:>8.1f}% "
                  f"KES {prop['outstanding']:>8,.2f}")
    
    async def get_revenue_forecast(self, property_id: str, months_ahead: int = 3) -> Dict:
        """
        Forecast revenue for upcoming months based on historical trends
        
        Args:
            property_id: Property ID
            months_ahead: Number of months to forecast
        
        Returns:
            Revenue forecast
        """
        
        print("\n" + "=" * 80)
        print(f" REVENUE FORECAST - Next {months_ahead} Months")
        print("=" * 80)
        
        # Get historical data (last 6 months)
        current_date = datetime.now(timezone.utc)
        historical_months = []
        
        for i in range(8):
            month_date = current_date - timedelta(days=30 * i)
            year, month = month_date.year, month_date.month
            
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
            
            invoices_cursor = self.db.property_invoices.find({
                "property_id": str(property_id),
                "date_issued": {"$gte": start_date, "$lt": end_date}
            })
           
            invoices = await invoices_cursor.to_list(length=None)
            print(f"{property_id}:{start_date.month}-{end_date.month}=>{len(invoices)}")
            
            expected = sum(inv.get("total_amount", 0) for inv in invoices)
            collected = sum(inv.get("total_paid", 0) for inv in invoices)
            collection_rate = (collected / expected * 100) if expected > 0 else 0
            
            historical_months.append({
                "period": f"{year}-{month:02d}",
                "expected": expected,
                "collected": collected,
                "collection_rate": collection_rate
            })
        
        # Calculate averages
        avg_expected = sum(m["expected"] for m in historical_months) / len(historical_months)
        avg_collection_rate = sum(m["collection_rate"] for m in historical_months) / len(historical_months)
        
        # Get active leases
        active_leases_cursor = self.db.property_leases.find({
            "property_id": property_id,
            "status": "signed"
        })
        active_leases = await active_leases_cursor.to_list(length=None)
        current_expected_rent = sum(lease["lease_terms"]["rent_amount"] for lease in active_leases)
        
        # Forecast future months
        forecast = []
        for i in range(1, months_ahead + 1):
            future_date = current_date + timedelta(days=30 * i)
            period = f"{future_date.year}-{future_date.month:02d}"
            
            # Simple forecast: use current expected rent + average collection rate
            expected_revenue = current_expected_rent * 1.0  # Can adjust for growth
            predicted_collection = expected_revenue * (avg_collection_rate / 100)
            
            forecast.append({
                "period": period,
                "expected_revenue": round(expected_revenue, 2),
                "predicted_collection": round(predicted_collection, 2),
                "predicted_collection_rate": round(avg_collection_rate, 2)
            })
        
        result = {
            "property_id": property_id,
            "forecast_months": months_ahead,
            "historical_average": {
                "expected": round(avg_expected, 2),
                "collection_rate": round(avg_collection_rate, 2)
            },
            "current_monthly_rent": round(current_expected_rent, 2),
            "historical_data": list(reversed(historical_months)),
            "forecast": forecast
        }
        
        self._print_revenue_forecast(result)
        
        return result
    
    def _print_revenue_forecast(self, data: Dict):
        """Print revenue forecast"""
        
        print(f"\n📊 Historical Performance (Last 8 Months):")
        print(f"   Average Expected: KES {data['historical_average']['expected']:,.2f}")
        print(f"   Average Collection Rate: {data['historical_average']['collection_rate']:.1f}%")
        print(f"   Current Monthly Rent: KES {data['current_monthly_rent']:,.2f}")
        
        print(f"\n📈 Revenue Forecast:")
        print(f"   {'Period':<10} {'Expected':>12} {'Predicted Collection':>20} {'Rate':>8}")
        print(f"   {'-'*60}")
        
        for month in data['forecast']:
            print(f"   {month['period']:<10} "
                  f"KES {month['expected_revenue']:>9,.2f} "
                  f"KES {month['predicted_collection']:>16,.2f} "
                  f"{month['predicted_collection_rate']:>6.1f}%")
    
    async def get_lease_expiry_report(self, property_id: Optional[str] = None, days_ahead: int = 90) -> Dict:
        """
        Report on leases expiring soon
        
        Args:
            property_id: Optional property filter
            days_ahead: Look ahead this many days
        
        Returns:
            Lease expiry report
        """
        
        print("\n" + "=" * 80)
        print(f" LEASE EXPIRY REPORT - Next {days_ahead} Days")
        print("=" * 80)
        
        current_date = datetime.now(timezone.utc)
        future_date = current_date + timedelta(days=days_ahead)
        
        query = {
            "lease_terms.end_date": {
                "$gte": current_date,
                "$lte": future_date
            },
            "status": "signed"
        }
        
        if property_id:
            query["property_id"] = property_id
        
        leases_cursor = self.db.property_leases.find(query).sort("lease_terms.end_date", 1)
        expiring_leases = await leases_cursor.to_list(length=None)
        
        lease_data = []
        total_rent_at_risk = 0
        
        for lease in expiring_leases:
            tenant_id = lease.get("tenant_id")
            tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
            
            end_date = lease["lease_terms"]["end_date"]
            days_until_expiry = (end_date - current_date).days
            
            rent_amount = lease["lease_terms"]["rent_amount"]
            total_rent_at_risk += rent_amount
            
            # Check outstanding balance
            outstanding_cursor = self.db.property_invoices.find({
                "tenant_id": tenant_id,
                "balance_amount": {"$gt": 0}
            })
            outstanding_invoices = await outstanding_cursor.to_list(length=None)
            outstanding_balance = sum(inv.get("balance_amount", 0) for inv in outstanding_invoices)
            
            lease_data.append({
                "lease_id": str(lease["_id"]),
                "tenant_name": tenant.get("full_name") if tenant else "Unknown",
                "tenant_phone": tenant.get("phone") if tenant else "",
                "end_date": end_date,
                "days_until_expiry": days_until_expiry,
                "monthly_rent": rent_amount,
                "outstanding_balance": outstanding_balance,
                "property_id": lease.get("property_id")
            })
        
        result = {
            "total_expiring": len(expiring_leases),
            "total_rent_at_risk": round(total_rent_at_risk, 2),
            "days_ahead": days_ahead,
            "leases": lease_data
        }
        
        self._print_lease_expiry_report(result)
        
        return result
    
    def _print_lease_expiry_report(self, data: Dict):
        """Print lease expiry report"""
        
        print(f"\n⚠️  Summary:")
        print(f"   Leases Expiring: {data['total_expiring']}")
        print(f"   Monthly Rent at Risk: KES {data['total_rent_at_risk']:,.2f}")
        
        print(f"\n📅 Expiring Leases:")
        print(f"   {'Tenant':<25} {'Phone':<15} {'Expires':<12} {'Days':>5} {'Rent':>12} {'Outstanding':>12}")
        print(f"   {'-'*95}")
        
        for lease in data['leases']:
            urgency = "🔴" if lease['days_until_expiry'] <= 30 else "🟡" if lease['days_until_expiry'] <= 60 else "🟢"
            
            print(f"   {lease['tenant_name']:<25} "
                  f"{lease['tenant_phone']:<15} "
                  f"{lease['end_date'].strftime('%Y-%m-%d'):<12} "
                  f"{urgency} {lease['days_until_expiry']:>3} "
                  f"KES {lease['monthly_rent']:>8,.2f} "
                  f"KES {lease['outstanding_balance']:>8,.2f}")
    
    async def get_vacancy_analysis(self, property_id: str) -> Dict:
        """
        Analyze unit vacancies and turnover
        
        Returns:
            Vacancy analysis
        """
        
        print("\n" + "=" * 80)
        print(f" VACANCY ANALYSIS")
        print("=" * 80)
        
        # Get all units
        units_cursor = self.db.units.find({"property_id": property_id})
        all_units = await units_cursor.to_list(length=None)
        
        # Get occupied units (with active leases)
        active_leases_cursor = self.db.property_leases.find({
            "property_id": property_id,
            "status": "signed"
        })
        active_leases = await active_leases_cursor.to_list(length=None)
        
        occupied_unit_ids = set()
        for lease in active_leases:
            occupied_unit_ids.update(lease.get("units_id", []))
        
        # Identify vacant units
        vacant_units = []
        for unit in all_units:
            unit_id = unit["_id"]
            if unit_id not in occupied_unit_ids:
                vacant_units.append({
                    "unit_id": unit_id,
                    "unit_number": unit.get("unitNumber"),
                    "rent_amount": unit.get("rentAmount"),
                    "bedrooms": unit.get("bedrooms"),
                    "status": unit.get("status", "vacant")
                })
        
        total_units = len(all_units)
        occupied_units = len(occupied_unit_ids)
        vacant_count = len(vacant_units)
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Calculate revenue loss
        potential_revenue_loss = sum(u["rent_amount"] for u in vacant_units)
        
        # Historical turnover (last 12 months)
        one_year_ago = datetime.now(timezone.utc) - timedelta(days=365)
        expired_leases_cursor = self.db.property_leases.find({
            "property_id": property_id,
            "lease_terms.end_date": {"$gte": one_year_ago},
            "status": {"$in": ["expired", "terminated"]}
        })
        expired_leases = await expired_leases_cursor.to_list(length=None)
        
        turnover_count = len(expired_leases)
        annual_turnover_rate = (turnover_count / total_units * 100) if total_units > 0 else 0
        
        result = {
            "property_id": property_id,
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": vacant_count,
            "occupancy_rate": round(occupancy_rate, 2),
            "vacancy_rate": round(100 - occupancy_rate, 2),
            "potential_revenue_loss": round(potential_revenue_loss, 2),
            "annual_turnover_rate": round(annual_turnover_rate, 2),
            "vacant_unit_details": vacant_units
        }
        
        self._print_vacancy_analysis(result)
        
        return result
    
    def _print_vacancy_analysis(self, data: Dict):
        """Print vacancy analysis"""
        
        print(f"\n🏠 Occupancy Summary:")
        print(f"   Total Units: {data['total_units']}")
        print(f"   Occupied: {data['occupied_units']}")
        print(f"   Vacant: {data['vacant_units']}")
        print(f"   Occupancy Rate: {data['occupancy_rate']:.1f}%")
        print(f"   Vacancy Rate: {data['vacancy_rate']:.1f}%")
        
        print(f"\n💰 Financial Impact:")
        print(f"   Potential Revenue Loss: KES {data['potential_revenue_loss']:,.2f}/month")
        print(f"   Annual Turnover Rate: {data['annual_turnover_rate']:.1f}%")
        
        if data['vacant_unit_details']:
            print(f"\n🔓 Vacant Units:")
            print(f"   {'Unit':<15} {'Bedrooms':>10} {'Rent':>12}")
            print(f"   {'-'*40}")
            
            for unit in data['vacant_unit_details']:
                print(f"   {unit['unit_number']:<15} "
                      f"{unit['bedrooms']:>10} "
                      f"KES {unit['rent_amount']:>8,.2f}")
    
    async def get_payment_method_analysis(self, property_id: str, period: Optional[str] = None) -> Dict:
        """
        Analyze payment methods used by tenants
        
        Returns:
            Payment method breakdown
        """
        
        print("\n" + "=" * 80)
        print(f" PAYMENT METHOD ANALYSIS")
        print("=" * 80)
        
        # Build query
        query = {"property_id": property_id}
        
        if period:
            year, month = map(int, period.split("-"))
            start_date = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                end_date = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                end_date = datetime(year, month + 1, 1, tzinfo=timezone.utc)
            
            query["date_issued"] = {"$gte": start_date, "$lt": end_date}
        
        # Get all invoices with payments
        invoices_cursor = self.db.property_invoices.find(query)
        invoices = await invoices_cursor.to_list(length=None)
        
        # Analyze payment methods
        method_stats = defaultdict(lambda: {"count": 0, "total_amount": 0})
        
        for inv in invoices:
            payments= await self.db.property_payments.find({"invoice_id":str(inv['_id'])}).to_list(length=None)
            for payment in payments:
                method = payment.get("method", "unknown")
                amount = payment.get("amount", 0)
                
                method_stats[method]["count"] += 1
                method_stats[method]["total_amount"] += amount
        
        # Calculate totals
        total_payments = sum(stat["count"] for stat in method_stats.values())
        total_amount = sum(stat["total_amount"] for stat in method_stats.values())
        
        # Convert to list and calculate percentages
        method_breakdown = []
        for method, stats in method_stats.items():
            percentage = (stats["count"] / total_payments * 100) if total_payments > 0 else 0
            amount_percentage = (stats["total_amount"] / total_amount * 100) if total_amount > 0 else 0
            
            method_breakdown.append({
                "method": method,
                "count": stats["count"],
                "percentage": round(percentage, 2),
                "total_amount": round(stats["total_amount"], 2),
                "amount_percentage": round(amount_percentage, 2),
                "avg_transaction": round(stats["total_amount"] / stats["count"], 2) if stats["count"] > 0 else 0
            })
        
        # Sort by total amount
        method_breakdown.sort(key=lambda x: x["total_amount"], reverse=True)
        
        result = {
            "property_id": property_id,
            "period": period or "All time",
            "total_payments": total_payments,
            "total_amount": round(total_amount, 2),
            "payment_methods": method_breakdown
        }
        
        self._print_payment_method_analysis(result)
        
        return result
    
    def _print_payment_method_analysis(self, data: Dict):
        """Print payment method analysis"""
        
        print(f"\n💳 Payment Summary:")
        print(f"   Period: {data['period']}")
        print(f"   Total Payments: {data['total_payments']}")
        print(f"   Total Amount: KES {data['total_amount']:,.2f}")
        
        print(f"\n📊 Payment Method Breakdown:")
        print(f"   {'Method':<15} {'Count':>8} {'% of Txns':>10} {'Amount':>15} {'% of Value':>12} {'Avg Txn':>12}")
        print(f"   {'-'*80}")
        
        for method in data['payment_methods']:
            print(f"   {method['method'].upper():<15} "
                  f"{method['count']:>8} "
                  f"{method['percentage']:>9.1f}% "
                  f"KES {method['total_amount']:>11,.2f} "
                  f"{method['amount_percentage']:>11.1f}% "
                  f"KES {method['avg_transaction']:>8,.2f}")
    
    async def get_top_performers_report(self, property_id: Optional[str] = None, limit: int = 10) -> Dict:
        """
        Identify top performing tenants
        
        Returns:
            Top performers report
        """
        
        print("\n" + "=" * 80)
        print(f" TOP PERFORMING TENANTS")
        print("=" * 80)
        
        query = {}
        if property_id:
            query["property_id"] = property_id
        
        tenants_cursor = self.db.property_tenants.find(query)
        tenants = await tenants_cursor.to_list(length=None)
        
        tenant_performance = []
        
        for tenant in tenants:
            tenant_id = tenant["_id"]
            
            # Get invoices
            invoices_cursor = self.db.property_invoices.find({"tenant_id": tenant_id})
            invoices = await invoices_cursor.to_list(length=None)
            
            if not invoices:
                continue
            
            total_expected = sum(inv.get("total_amount", 0) for inv in invoices)
            total_paid = sum(inv.get("total_paid", 0) for inv in invoices)
            collection_rate = (total_paid / total_expected * 100) if total_expected > 0 else 0
            
            # Count on-time payments
            on_time = 0
            for inv in invoices:
                if inv.get("status") == "paid":
                    # Check if paid before due date
                    due_date = inv.get("due_date")
                    
                    if due_date:
                        # first_payment = min(payments, key=lambda p: p.get("payment_date", datetime.max))
                        payment_date = make_aware(auto_datetime(inv.get("payment_date")))
                        
                        if payment_date and payment_date <= make_aware(due_date):
                            on_time += 1
            
            on_time_rate = (on_time / len(invoices) * 100) if invoices else 0
            
            tenant_performance.append({
                "tenant_id": str(tenant_id),
                "tenant_name": tenant.get("full_name"),
                "tenant_phone": tenant.get("phone"),
                "total_invoices": len(invoices),
                "collection_rate": round(collection_rate, 2),
                "on_time_rate": round(on_time_rate, 2),
                "total_paid": round(total_paid, 2)
            })
        
        # Sort by collection rate, then on-time rate
        tenant_performance.sort(key=lambda x: (x["collection_rate"], x["on_time_rate"]), reverse=True)
        
        result = {
            "total_tenants_analyzed": len(tenant_performance),
            "top_performers": tenant_performance[:limit]
        }
        
        self._print_top_performers(result)
        
        return result
    
    def _print_top_performers(self, data: Dict):
        """Print top performers"""
        
        print(f"\n🌟 Top {len(data['top_performers'])} Performers:")
        print(f"   {'Rank':<5} {'Tenant Name':<25} {'Phone':<15} {'Collection':>12} {'On-Time':>10} {'Total Paid':>15}")
        print(f"   {'-'*90}")
        
        for i, tenant in enumerate(data['top_performers'], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
            
            print(f"   {medal} #{i:<3} "
                  f"{tenant['tenant_name']:<25} "
                  f"{tenant['tenant_phone']:<15} "
                  f"{tenant['collection_rate']:>10.1f}% "
                  f"{tenant['on_time_rate']:>9.1f}% "
                  f"KES {tenant['total_paid']:>11,.2f}")


# Usage examples

async def run_advanced_analytics():
    """Run all advanced analytics"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    analytics = AdvancedRentAnalytics(db)
    
    try:
        # Get first property for demo
        property_data = await db.properties.find_one({"_id":"690429e54c74bcbb048b4c58"})
        property_id = property_data.get("_id")
        
        # Get first tenant for demo
        tenant_data = await db.property_tenants.find_one({})
        tenant_id = str(tenant_data["_id"]) if tenant_data else None
        
        print("\n" + "="*80)
        print(" RUNNING ALL ADVANCED ANALYTICS")
        print(f" for {property_data['name']}")
        print("="*80)
        
        # 1. Tenant Risk Score
        if tenant_id:
            await analytics.get_tenant_risk_score(tenant_id)
        
        # 2. Portfolio Dashboard
        await analytics.get_property_portfolio_dashboard()
        
        # 3. Revenue Forecast
        await analytics.get_revenue_forecast(property_id, months_ahead=3)
        
        # 4. Lease Expiry Report
        await analytics.get_lease_expiry_report(property_id, days_ahead=90)
        
        # 5. Vacancy Analysis
        await analytics.get_vacancy_analysis(property_id)
        
        # 6. Payment Method Analysis
        await analytics.get_payment_method_analysis(property_id)
        
        # 7. Top Performers
        await analytics.get_top_performers_report(property_id, limit=10)
        
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(run_advanced_analytics())