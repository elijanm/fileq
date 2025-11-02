import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Literal
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import calendar
from collections import defaultdict


class LeaseLifecycleReportGenerator:
    """
    Generate comprehensive lease lifecycle reports tracking the entire tenant journey
    from lease signing to termination
    """
    
    def __init__(self, db):
        self.db = db
    
    async def generate_complete_lifecycle_report(
        self,
        lease_id: str,
        include_predictions: bool = True
    ) -> Dict:
        """
        Generate a complete lifecycle report for a specific lease
        
        This is the MASTER report that shows:
        - Lease timeline and milestones
        - Financial performance over time
        - Payment behavior trends
        - Key events and changes
        - Current status and health
        - Future predictions
        
        Args:
            lease_id: Lease ID
            include_predictions: Include future predictions
        
        Returns:
            Complete lifecycle report
        """
        
        if isinstance(lease_id, str):
            lease_id = ObjectId(lease_id)
        
        print("\n" + "=" * 100)
        print(" LEASE LIFECYCLE REPORT")
        print("=" * 100)
        
        # Get lease data
        lease = await self.db.property_leases.find_one({"_id": lease_id})
        if not lease:
            return {"error": "Lease not found"}
        
        # Build comprehensive report
        report = {
            "report_id": f"LIFECYCLE-{str(lease_id)[:8]}-{datetime.now().strftime('%Y%m%d')}",
            "generated_at": datetime.now(timezone.utc),
            "lease_id": str(lease_id),
            
            # Section 1: Basic Information
            "basic_info": await self._get_basic_info(lease),
            
            # Section 2: Timeline & Milestones
            "timeline": await self._get_timeline(lease),
            
            # Section 3: Financial Performance
            "financial_performance": await self._get_financial_performance(lease),
            
            # Section 4: Payment Behavior Analysis
            "payment_behavior": await self._get_payment_behavior(lease),
            
            # Section 5: Lifecycle Stages
            "lifecycle_stages": await self._analyze_lifecycle_stages(lease),
            
            # Section 6: Key Events
            "key_events": await self._get_key_events(lease),
            
            # Section 7: Health Score
            "health_assessment": await self._calculate_lease_health(lease),
            
            # Section 8: Utilities & Consumption
            "utilities_analysis": await self._analyze_utilities(lease),
            
            # Section 9: Compliance & Issues
            "compliance": await self._get_compliance_info(lease),
            
            # Section 10: Comparative Analysis
            "comparative_analysis": await self._compare_to_property_average(lease),
        }
        
        # Section 11: Predictions (if requested)
        if include_predictions:
            report["predictions"] = await self._generate_predictions(lease, report)
        
        # Print formatted report
        await self._print_lifecycle_report(report)
        
        return report
    
    async def _get_basic_info(self, lease: Dict) -> Dict:
        """Extract basic lease information"""
        
        # Get tenant
        tenant = await self.db.property_tenants.find_one({"_id": lease["tenant_id"]})
        
        # Get property
        property_data = await self.db.properties.find_one({"_id": lease["property_id"]})
        
        # Get units
        unit_ids = lease.get("units_id", [])
        units_cursor = self.db.property_units.find({"_id": {"$in": unit_ids}})
        units = await units_cursor.to_list(length=None)
        
        current_date = datetime.now(timezone.utc)
        start_date = lease["lease_terms"]["start_date"]
        end_date = lease["lease_terms"]["end_date"]
        
        days_active = (current_date - start_date).days if current_date > start_date else 0
        days_remaining = (end_date - current_date).days if end_date > current_date else 0
        total_days = (end_date - start_date).days
        
        return {
            "lease_number": str(lease["_id"])[:12],
            "status": lease.get("status", "active"),
            "tenant": {
                "id": str(lease["tenant_id"]),
                "name": tenant.get("full_name") if tenant else "Unknown",
                "email": tenant.get("email") if tenant else "",
                "phone": tenant.get("phone") if tenant else "",
            },
            "property": {
                "id": lease["property_id"],
                "name": property_data.get("name") if property_data else "Unknown",
                "location": property_data.get("location") if property_data else "",
            },
            "units": [
                {
                    "unit_id": str(unit["_id"]),
                    "unit_number": unit.get("unitNumber"),
                    "bedrooms": unit.get("bedrooms"),
                }
                for unit in units
            ],
            "duration": {
                "start_date": start_date,
                "end_date": end_date,
                "total_duration_days": total_days,
                "total_duration_months": round(total_days / 30, 1),
                "days_active": days_active,
                "days_remaining": days_remaining,
                "months_active": round(days_active / 30, 1),
                "months_remaining": round(days_remaining / 30, 1),
                "progress_percentage": round((days_active / total_days * 100) if total_days > 0 else 0, 1),
            },
            "rent": {
                "monthly_amount": lease["lease_terms"]["rent_amount"],
                "deposit_amount": lease["lease_terms"]["deposit_amount"],
                "payment_due_day": lease["lease_terms"].get("payment_due_day", 5),
                "rent_cycle": lease["lease_terms"].get("rent_cycle", "monthly"),
            }
        }
    
    async def _get_timeline(self, lease: Dict) -> Dict:
        """Get complete timeline of lease lifecycle"""
        
        timeline = {
            "milestones": [],
            "phases": []
        }
        
        start_date = lease["lease_terms"]["start_date"]
        end_date = lease["lease_terms"]["end_date"]
        current_date = datetime.now(timezone.utc)
        
        # Key milestones
        milestones = [
            {
                "event": "Lease Signed",
                "date": lease.get("tenant_signed_date") or start_date,
                "status": "completed",
                "description": "Tenant and landlord signed the lease agreement"
            },
            {
                "event": "Move-in Date",
                "date": lease.get("move_in_date") or start_date,
                "status": "completed",
                "description": "Tenant officially moved into the property"
            },
            {
                "event": "First Payment Due",
                "date": start_date + timedelta(days=5),  # Assuming due on 5th
                "status": "completed",
                "description": "First rent payment was due"
            },
        ]
        
        # Add mid-term review (6 months in)
        mid_term = start_date + timedelta(days=180)
        if mid_term <= current_date:
            milestones.append({
                "event": "Mid-term Review",
                "date": mid_term,
                "status": "completed",
                "description": "6-month lease review milestone"
            })
        elif mid_term > current_date:
            milestones.append({
                "event": "Mid-term Review",
                "date": mid_term,
                "status": "upcoming",
                "description": "Upcoming 6-month lease review"
            })
        
        # Renewal notice period (90 days before end)
        renewal_notice = end_date - timedelta(days=90)
        if renewal_notice <= current_date:
            milestones.append({
                "event": "Renewal Notice Period",
                "date": renewal_notice,
                "status": "completed",
                "description": "Period to notify about renewal intentions"
            })
        elif renewal_notice > current_date:
            milestones.append({
                "event": "Renewal Notice Period",
                "date": renewal_notice,
                "status": "upcoming",
                "description": "Upcoming renewal decision period"
            })
        
        # Lease end
        if end_date <= current_date:
            milestones.append({
                "event": "Lease Ended",
                "date": end_date,
                "status": "completed",
                "description": "Lease term concluded"
            })
        else:
            milestones.append({
                "event": "Lease End Date",
                "date": end_date,
                "status": "upcoming",
                "description": "Scheduled lease termination date"
            })
        
        timeline["milestones"] = milestones
        
        # Lifecycle phases
        total_days = (end_date - start_date).days
        days_elapsed = (current_date - start_date).days
        
        phases = [
            {
                "phase": "Early Stage",
                "period": "Months 1-3",
                "status": "completed" if days_elapsed > 90 else "current",
                "description": "Settling in, establishing payment patterns",
                "days_range": (0, 90)
            },
            {
                "phase": "Stable Stage",
                "period": "Months 4-9",
                "status": "completed" if days_elapsed > 270 else "current" if days_elapsed > 90 else "upcoming",
                "description": "Routine rental period, consistent payments expected",
                "days_range": (91, 270)
            },
            {
                "phase": "Late Stage",
                "period": "Months 10-12",
                "status": "completed" if days_elapsed > 330 else "current" if days_elapsed > 270 else "upcoming",
                "description": "Approaching renewal decision, potential move-out preparation",
                "days_range": (271, total_days)
            }
        ]
        
        timeline["phases"] = phases
        
        return timeline
    
    async def _get_financial_performance(self, lease: Dict) -> Dict:
        """Analyze financial performance throughout lifecycle"""
        
        lease_id = str(lease["_id"])
        
        # Get all invoices
        invoices_cursor = self.db.property_invoices.find({
            "lease_id": lease_id
        }).sort("date_issued", 1)
        invoices = await invoices_cursor.to_list(length=None)
        
        # Overall metrics
        total_expected = sum(inv.get("total_amount", 0) for inv in invoices)
        total_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        total_outstanding = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        # Monthly breakdown
        monthly_performance = []
        monthly_data = defaultdict(lambda: {
            "expected": 0,
            "collected": 0,
            "outstanding": 0,
            "invoices": []
        })
        
        for inv in invoices:
            if inv.get("date_issued"):
                month_key = inv["date_issued"].strftime("%Y-%m")
                monthly_data[month_key]["expected"] += inv.get("total_amount", 0)
                monthly_data[month_key]["collected"] += inv.get("total_paid", 0)
                monthly_data[month_key]["outstanding"] += inv.get("balance_amount", 0)
                monthly_data[month_key]["invoices"].append(str(inv["_id"]))
        
        for month in sorted(monthly_data.keys()):
            data = monthly_data[month]
            collection_rate = (data["collected"] / data["expected"] * 100) if data["expected"] > 0 else 0
            
            monthly_performance.append({
                "month": month,
                "expected": round(data["expected"], 2),
                "collected": round(data["collected"], 2),
                "outstanding": round(data["outstanding"], 2),
                "collection_rate": round(collection_rate, 2),
                "invoice_count": len(data["invoices"])
            })
        
        # Calculate trends
        if len(monthly_performance) >= 2:
            recent_avg = sum(m["collection_rate"] for m in monthly_performance[-3:]) / min(3, len(monthly_performance[-3:]))
            early_avg = sum(m["collection_rate"] for m in monthly_performance[:3]) / min(3, len(monthly_performance[:3]))
            trend = "improving" if recent_avg > early_avg else "declining" if recent_avg < early_avg else "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "summary": {
                "total_expected": round(total_expected, 2),
                "total_collected": round(total_collected, 2),
                "total_outstanding": round(total_outstanding, 2),
                "overall_collection_rate": round((total_collected / total_expected * 100) if total_expected > 0 else 0, 2),
                "total_invoices": len(invoices),
                "months_billed": len(monthly_data),
            },
            "monthly_performance": monthly_performance,
            "trend_analysis": {
                "trend": trend,
                "recent_3_month_avg": round(recent_avg, 2) if len(monthly_performance) >= 2 else 0,
                "early_3_month_avg": round(early_avg, 2) if len(monthly_performance) >= 2 else 0,
            }
        }
    
    async def _get_payment_behavior(self, lease: Dict) -> Dict:
        """Analyze payment behavior patterns"""
        
        lease_id = str(lease["_id"])
        
        # Get all invoices with payments
        invoices_cursor = self.db.property_invoices.find({
            "lease_id": lease_id
        }).sort("date_issued", 1)
        invoices = await invoices_cursor.to_list(length=None)
        
        # Analyze payment timing
        early_payments = 0
        on_time_payments = 0
        late_payments = 0
        unpaid = 0
        
        payment_delays = []
        
        for inv in invoices:
            status = inv.get("status")
            due_date = inv.get("due_date")
            
            if status == "unpaid":
                unpaid += 1
            elif status == "paid" and due_date:
                # Check when it was paid
                payments = inv.get("payments", [])
                if payments:
                    first_payment = min(payments, key=lambda p: p.get("payment_date", datetime.max))
                    payment_date = first_payment.get("payment_date")
                    
                    if payment_date:
                        days_diff = (payment_date - due_date).days
                        payment_delays.append(days_diff)
                        
                        if days_diff < 0:
                            early_payments += 1
                        elif days_diff == 0:
                            on_time_payments += 1
                        else:
                            late_payments += 1
        
        total_paid = early_payments + on_time_payments + late_payments
        avg_delay = sum(payment_delays) / len(payment_delays) if payment_delays else 0
        
        # Payment pattern classification
        if total_paid == 0:
            pattern = "no_data"
        elif early_payments / total_paid > 0.5:
            pattern = "early_payer"
        elif on_time_payments / total_paid > 0.7:
            pattern = "on_time_payer"
        elif late_payments / total_paid > 0.5:
            pattern = "late_payer"
        else:
            pattern = "mixed"
        
        return {
            "payment_timing": {
                "early_payments": early_payments,
                "on_time_payments": on_time_payments,
                "late_payments": late_payments,
                "unpaid": unpaid,
                "on_time_rate": round((on_time_payments / total_paid * 100) if total_paid > 0 else 0, 2),
            },
            "payment_delays": {
                "average_delay_days": round(avg_delay, 1),
                "min_delay": min(payment_delays) if payment_delays else 0,
                "max_delay": max(payment_delays) if payment_delays else 0,
            },
            "behavior_classification": {
                "pattern": pattern,
                "reliability_score": round((early_payments + on_time_payments) / total_paid * 100 if total_paid > 0 else 0, 1),
            }
        }
    
    async def _analyze_lifecycle_stages(self, lease: Dict) -> Dict:
        """Analyze performance at different lifecycle stages"""
        
        lease_id = str(lease["_id"])
        start_date = lease["lease_terms"]["start_date"]
        current_date = datetime.now(timezone.utc)
        
        # Get invoices
        invoices_cursor = self.db.property_invoices.find({
            "lease_id": lease_id
        }).sort("date_issued", 1)
        invoices = await invoices_cursor.to_list(length=None)
        
        # Define stage boundaries
        stage_1_end = start_date + timedelta(days=90)  # First 3 months
        stage_2_end = start_date + timedelta(days=270)  # Months 4-9
        
        stages = {
            "early_stage": {"invoices": [], "expected": 0, "collected": 0},
            "stable_stage": {"invoices": [], "expected": 0, "collected": 0},
            "late_stage": {"invoices": [], "expected": 0, "collected": 0},
        }
        
        for inv in invoices:
            issue_date = inv.get("date_issued")
            if not issue_date:
                continue
            
            expected = inv.get("total_amount", 0)
            collected = inv.get("total_paid", 0)
            
            if issue_date <= stage_1_end:
                stages["early_stage"]["invoices"].append(str(inv["_id"]))
                stages["early_stage"]["expected"] += expected
                stages["early_stage"]["collected"] += collected
            elif issue_date <= stage_2_end:
                stages["stable_stage"]["invoices"].append(str(inv["_id"]))
                stages["stable_stage"]["expected"] += expected
                stages["stable_stage"]["collected"] += collected
            else:
                stages["late_stage"]["invoices"].append(str(inv["_id"]))
                stages["late_stage"]["expected"] += expected
                stages["late_stage"]["collected"] += collected
        
        # Calculate rates
        result = {}
        for stage_name, data in stages.items():
            collection_rate = (data["collected"] / data["expected"] * 100) if data["expected"] > 0 else 0
            result[stage_name] = {
                "invoice_count": len(data["invoices"]),
                "expected": round(data["expected"], 2),
                "collected": round(data["collected"], 2),
                "collection_rate": round(collection_rate, 2),
            }
        
        return result
    
    async def _get_key_events(self, lease: Dict) -> List[Dict]:
        """Get key events in lease lifecycle"""
        
        events = []
        
        # Lease signing
        if lease.get("tenant_signed_date"):
            events.append({
                "date": lease["tenant_signed_date"],
                "event_type": "lease_signed",
                "description": "Lease agreement signed by tenant",
                "impact": "positive"
            })
        
        # Move-in
        if lease.get("move_in_date"):
            events.append({
                "date": lease["move_in_date"],
                "event_type": "move_in",
                "description": "Tenant moved into property",
                "impact": "neutral"
            })
        
        # Get payment events
        lease_id = str(lease["_id"])
        invoices_cursor = self.db.property_invoices.find({
            "lease_id": lease_id,
            "status": {"$in": ["overdue", "paid"]}
        }).sort("date_issued", 1).limit(20)
        invoices = await invoices_cursor.to_list(length=None)
        
        for inv in invoices:
            if inv.get("status") == "overdue":
                events.append({
                    "date": inv.get("due_date"),
                    "event_type": "payment_overdue",
                    "description": f"Payment overdue for invoice {inv.get('invoice_number')}",
                    "impact": "negative",
                    "amount": inv.get("balance_amount")
                })
        
        # Sort by date
        events.sort(key=lambda x: x["date"])
        
        return events
    
    async def _calculate_lease_health(self, lease: Dict) -> Dict:
        """Calculate overall lease health score"""
        
        lease_id = str(lease["_id"])
        
        # Get financial data
        invoices_cursor = self.db.property_invoices.find({"lease_id": lease_id})
        invoices = await invoices_cursor.to_list(length=None)
        
        if not invoices:
            return {
                "health_score": 100,
                "health_level": "EXCELLENT",
                "components": {},
                "recommendations": []
            }
        
        # Calculate component scores (0-100)
        
        # 1. Payment timeliness (40% weight)
        on_time = sum(1 for inv in invoices if inv.get("status") == "paid")
        timeliness_score = (on_time / len(invoices) * 100) if invoices else 100
        
        # 2. Collection rate (30% weight)
        total_expected = sum(inv.get("total_amount", 0) for inv in invoices)
        total_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        collection_score = (total_collected / total_expected * 100) if total_expected > 0 else 100
        
        # 3. Outstanding balance (20% weight)
        total_outstanding = sum(inv.get("balance_amount", 0) for inv in invoices)
        monthly_rent = lease["lease_terms"]["rent_amount"]
        months_overdue = total_outstanding / monthly_rent if monthly_rent > 0 else 0
        balance_score = max(0, 100 - (months_overdue * 25))  # Deduct 25 points per month overdue
        
        # 4. Lease duration progress (10% weight)
        # Being further along in lease without issues is positive
        start_date = lease["lease_terms"]["start_date"]
        end_date = lease["lease_terms"]["end_date"]
        current_date = datetime.now(timezone.utc)
        
        total_days = (end_date - start_date).days
        days_elapsed = (current_date - start_date).days
        progress = (days_elapsed / total_days * 100) if total_days > 0 else 0
        duration_score = min(100, progress)  # Longer without issues = better
        
        # Calculate weighted health score
        health_score = (
            (timeliness_score * 0.40) +
            (collection_score * 0.30) +
            (balance_score * 0.20) +
            (duration_score * 0.10)
        )
        
        # Determine health level
        if health_score >= 90:
            health_level = "EXCELLENT"
            color = "🟢"
        elif health_score >= 75:
            health_level = "GOOD"
            color = "🟢"
        elif health_score >= 60:
            health_level = "FAIR"
            color = "🟡"
        elif health_score >= 40:
            health_level = "POOR"
            color = "🟠"
        else:
            health_level = "CRITICAL"
            color = "🔴"
        
        # Generate recommendations
        recommendations = []
        
        if timeliness_score < 70:
            recommendations.append({
                "area": "Payment Timeliness",
                "priority": "high",
                "action": "Send payment reminders 3 days before due date",
                "reason": "Multiple late payments detected"
            })
        
        if collection_score < 80:
            recommendations.append({
                "area": "Collection Rate",
                "priority": "high",
                "action": "Review and follow up on outstanding balances",
                "reason": "Collection rate below target"
            })
        
        if months_overdue > 1:
            recommendations.append({
                "area": "Outstanding Balance",
                "priority": "critical",
                "action": "Immediate follow-up required - consider legal action",
                "reason": f"{months_overdue:.1f} months rent overdue"
            })
        
        return {
            "health_score": round(health_score, 1),
            "health_level": health_level,
            "color": color,
            "components": {
                "payment_timeliness": {
                    "score": round(timeliness_score, 1),
                    "weight": 40,
                    "status": "good" if timeliness_score >= 70 else "poor"
                },
                "collection_rate": {
                    "score": round(collection_score, 1),
                    "weight": 30,
                    "status": "good" if collection_score >= 80 else "poor"
                },
                "outstanding_balance": {
                    "score": round(balance_score, 1),
                    "weight": 20,
                    "status": "good" if balance_score >= 75 else "poor"
                },
                "duration_progress": {
                    "score": round(duration_score, 1),
                    "weight": 10,
                    "status": "good"
                }
            },
            "recommendations": recommendations
        }
    
    async def _analyze_utilities(self, lease: Dict) -> Dict:
        """Analyze utility consumption throughout lifecycle"""
        
        lease_id = str(lease["_id"])
        
        # Get invoices with utility line items
        invoices_cursor = self.db.property_invoices.find({
            "lease_id": lease_id
        }).sort("date_issued", 1)
        invoices = await invoices_cursor.to_list(length=None)
        
        utilities_data = defaultdict(lambda: {
            "total_consumption": 0,
            "total_cost": 0,
            "months": []
        })
        
        for inv in invoices:
            for item in inv.get("line_items", []):
                if item.get("type") == "utility":
                    utility_name = item.get("utility_name")
                    meta = item.get("meta", {})
                    
                    usage = meta.get("usage", item.get("quantity", 0))
                    cost = item.get("amount", 0)
                    
                    utilities_data[utility_name]["total_consumption"] += usage
                    utilities_data[utility_name]["total_cost"] += cost
                    utilities_data[utility_name]["months"].append({
                        "period": inv["date_issued"].strftime("%Y-%m") if inv.get("date_issued") else "Unknown",
                        "consumption": usage,
                        "cost": cost
                    })
        
        result = {}
        for utility_name, data in utilities_data.items():
            months_count = len(data["months"])
            avg_consumption = data["total_consumption"] / months_count if months_count > 0 else 0
            avg_cost = data["total_cost"] / months_count if months_count > 0 else 0
            
            result[utility_name] = {
                "total_consumption": round(data["total_consumption"], 2),
                "total_cost": round(data["total_cost"], 2),
                "average_monthly_consumption": round(avg_consumption, 2),
                "average_monthly_cost": round(avg_cost, 2),
                "months_data": data["months"]
            }
        
        return result
    
    async def _get_compliance_info(self, lease: Dict) -> Dict:
        """Get compliance and issues information"""
        
        # For now, return placeholder
        # TODO: Implement ticket/violation tracking
        
        return {
            "violations": 0,
            "maintenance_requests": 0,
            "complaints": 0,
            "compliance_score": 100,
            "issues": []
        }
    
    async def _compare_to_property_average(self, lease: Dict) -> Dict:
        """Compare lease performance to property average"""
        
        property_id = lease["property_id"]
        lease_id = str(lease["_id"])
        
        # Get this lease's performance
        invoices_cursor = self.db.property_invoices.find({"lease_id": lease_id})
        invoices = await invoices_cursor.to_list(length=None)
        
        lease_expected = sum(inv.get("total_amount", 0) for inv in invoices)
        lease_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        lease_collection_rate = (lease_collected / lease_expected * 100) if lease_expected > 0 else 0
        
        # Get property average
        property_invoices_cursor = self.db.property_invoices.find({"property_id": property_id})
        property_invoices = await property_invoices_cursor.to_list(length=None)
        
        prop_expected = sum(inv.get("total_amount", 0) for inv in property_invoices)
        prop_collected = sum(inv.get("total_paid", 0) for inv in property_invoices)
        prop_collection_rate = (prop_collected / prop_expected * 100) if prop_expected > 0 else 0
        
        difference = lease_collection_rate - prop_collection_rate
        
        return {
            "lease_collection_rate": round(lease_collection_rate, 2),
            "property_average_rate": round(prop_collection_rate, 2),
            "difference": round(difference, 2),
            "performance": "above_average" if difference > 5 else "below_average" if difference < -5 else "average",
        }
    
    async def _generate_predictions(self, lease: Dict, report: Dict) -> Dict:
        """Generate predictions for lease future"""
        
        end_date = lease["lease_terms"]["end_date"]
        current_date = datetime.now(timezone.utc)
        days_until_end = (end_date - current_date).days
        
        # Predict renewal likelihood based on health score
        health_score = report["health_assessment"]["health_score"]
        
        if health_score >= 90:
            renewal_likelihood = 85
        elif health_score >= 75:
            renewal_likelihood = 70
        elif health_score >= 60:
            renewal_likelihood = 50
        else:
            renewal_likelihood = 20
        
        # Predict total revenue
        monthly_rent = lease["lease_terms"]["rent_amount"]
        months_remaining = days_until_end / 30
        collection_rate = report["financial_performance"]["summary"]["overall_collection_rate"]
        
        predicted_revenue = monthly_rent * months_remaining * (collection_rate / 100)
        
        return {
            "renewal_likelihood": round(renewal_likelihood, 1),
            "predicted_remaining_revenue": round(predicted_revenue, 2),
            "risk_level": "low" if health_score >= 75 else "medium" if health_score >= 50 else "high",
            "recommended_actions": [
                "Monitor payment patterns closely" if health_score < 70 else "Prepare renewal offer",
                "Schedule tenant check-in meeting" if days_until_end < 90 else None
            ]
        }
    
    async def _print_lifecycle_report(self, report: Dict):
        """Print formatted lifecycle report"""
        
        print("\n" + "=" * 100)
        print(f" LEASE LIFECYCLE REPORT - {report['report_id']}")
        print(f" Generated: {report['generated_at'].strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        
        # Basic Info
        info = report['basic_info']
        print(f"\n📋 BASIC INFORMATION")
        print(f"   Tenant: {info['tenant']['name']}")
        print(f"   Property: {info['property']['name']}")
        print(f"   Units: {', '.join([u['unit_number'] for u in info['units']])}")
        print(f"   Status: {info['status'].upper()}")
        print(f"   Monthly Rent: KES {info['rent']['monthly_amount']:,.2f}")
        
        # Duration
        dur = info['duration']
        print(f"\n⏱️  LEASE DURATION")
        print(f"   Start Date: {dur['start_date'].strftime('%Y-%m-%d')}")
        print(f"   End Date: {dur['end_date'].strftime('%Y-%m-%d')}")
        print(f"   Progress: {dur['months_active']:.1f} / {dur['total_duration_months']:.1f} months ({dur['progress_percentage']:.1f}%)")
        print(f"   Remaining: {dur['months_remaining']:.1f} months ({dur['days_remaining']} days)")
        
        # Health Score
        health = report['health_assessment']
        print(f"\n{health['color']} LEASE HEALTH SCORE: {health['health_score']}/100 ({health['health_level']})")
        
        # Financial Performance
        fin = report['financial_performance']['summary']
        print(f"\n💰 FINANCIAL PERFORMANCE")
        print(f"   Total Expected: KES {fin['total_expected']:,.2f}")
        print(f"   Total Collected: KES {fin['total_collected']:,.2f}")
        print(f"   Outstanding: KES {fin['total_outstanding']:,.2f}")
        print(f"   Collection Rate: {fin['overall_collection_rate']:.1f}%")
        
        # Payment Behavior
        behavior = report['payment_behavior']['payment_timing']
        print(f"\n📊 PAYMENT BEHAVIOR")
        print(f"   On-Time Rate: {behavior['on_time_rate']:.1f}%")
        print(f"   Early: {behavior['early_payments']}, On-Time: {behavior['on_time_payments']}, Late: {behavior['late_payments']}")
        
        # Recommendations
        if health['recommendations']:
            print(f"\n⚠️  RECOMMENDATIONS:")
            for i, rec in enumerate(health['recommendations'], 1):
                print(f"   {i}. [{rec['priority'].upper()}] {rec['action']}")
        
        # Predictions
        if 'predictions' in report:
            pred = report['predictions']
            print(f"\n🔮 PREDICTIONS")
            print(f"   Renewal Likelihood: {pred['renewal_likelihood']:.1f}%")
            print(f"   Risk Level: {pred['risk_level'].upper()}")
    
    async def generate_batch_lifecycle_reports(
        self,
        property_id: Optional[str] = None,
        status: Optional[str] = "signed"
    ) -> List[Dict]:
        """
        Generate lifecycle reports for multiple leases
        
        Args:
            property_id: Filter by property
            status: Filter by status
        
        Returns:
            List of lifecycle reports
        """
        
        query = {}
        if property_id:
            query["property_id"] = property_id
        if status:
            query["status"] = status
        
        leases_cursor = self.db.property_leases.find(query)
        leases = await leases_cursor.to_list(length=None)
        
        print(f"\n{'='*100}")
        print(f" BATCH LIFECYCLE REPORT GENERATION")
        print(f" Generating reports for {len(leases)} leases...")
        print(f"{'='*100}")
        
        reports = []
        for i, lease in enumerate(leases, 1):
            print(f"\nProcessing {i}/{len(leases)}: Lease {str(lease['_id'])[:12]}...")
            
            report = await self.generate_complete_lifecycle_report(
                str(lease["_id"]),
                include_predictions=True
            )
            reports.append(report)
        
        # Generate summary
        print(f"\n{'='*100}")
        print(f" BATCH SUMMARY")
        print(f"{'='*100}")
        
        avg_health = sum(r["health_assessment"]["health_score"] for r in reports) / len(reports) if reports else 0
        
        excellent = sum(1 for r in reports if r["health_assessment"]["health_score"] >= 90)
        good = sum(1 for r in reports if 75 <= r["health_assessment"]["health_score"] < 90)
        fair = sum(1 for r in reports if 60 <= r["health_assessment"]["health_score"] < 75)
        poor = sum(1 for r in reports if r["health_assessment"]["health_score"] < 60)
        
        print(f"\n📊 Health Distribution:")
        print(f"   Excellent (90-100): {excellent}")
        print(f"   Good (75-89): {good}")
        print(f"   Fair (60-74): {fair}")
        print(f"   Poor (<60): {poor}")
        print(f"   Average Health Score: {avg_health:.1f}/100")
        
        return reports


# Usage examples

async def example_single_lease_report():
    """Generate report for a single lease"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    
    generator = LeaseLifecycleReportGenerator(db)
    
    try:
        # Get first active lease
        lease = await db.property_leases.find_one({"status": "signed"})
        
        if lease:
            report = await generator.generate_complete_lifecycle_report(
                str(lease["_id"]),
                include_predictions=True
            )
            
            print("\n✅ Report generated successfully!")
        else:
            print("No active leases found")
    
    finally:
        client.close()


async def example_batch_reports():
    """Generate reports for all leases in a property"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    
    generator = LeaseLifecycleReportGenerator(db)
    
    try:
        # Get first property
        property_data = await db.properties.find_one({})
        
        if property_data:
            reports = await generator.generate_batch_lifecycle_reports(
                property_id=property_data["_id"],
                status="signed"
            )
            
            print(f"\n✅ Generated {len(reports)} lifecycle reports!")
    
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    print("""
    Lease Lifecycle Report Generator
    =================================
    
    1. Single lease report
    2. Batch reports (all active leases)
    
    """)
    
    choice = input("Choose option (1-2): ").strip()
    
    if choice == "1":
        asyncio.run(example_single_lease_report())
    elif choice == "2":
        asyncio.run(example_batch_reports())
    else:
        print("Invalid choice")
        
# How the Lease Lifecycle Report Works:
# 10 Report Sections:

# Basic Information - Tenant, property, units, duration
# Timeline & Milestones - Key dates and phases
# Financial Performance - Month-by-month revenue analysis
# Payment Behavior - Timing patterns and reliability
# Lifecycle Stages - Performance at early/stable/late stages
# Key Events - Important moments in lease history
# Health Assessment - Overall lease health score (0-100)
# Utilities Analysis - Consumption trends
# Compliance - Violations and issues
# Predictions - Renewal likelihood, revenue forecast

# Health Score Components:

# Payment Timeliness (40%)
# Collection Rate (30%)
# Outstanding Balance (20%)
# Duration Progress (10%)