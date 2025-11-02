from datetime import datetime, timezone
from typing import Dict, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio


# ============================================================================
# SCHEMA DEFINITIONS
# ============================================================================

"""
Collection: lease_snapshots
Purpose: Historical snapshots of lease state for trend analysis and audit trail
"""
LEASE_SNAPSHOT_SCHEMA = {
    "_id": ObjectId,  # Unique snapshot ID
    "snapshot_id": str,  # Human-readable snapshot ID (e.g., "SNAP-2025-10-30-001")
    "lease_id": ObjectId,  # Reference to property_leases
    "snapshot_date": datetime,  # When this snapshot was taken
    "snapshot_type": str,  # "monthly", "on_change", "manual", "end_of_term"
    
    # Lease Basic Info (at time of snapshot)
    "lease_info": {
        "property_id": str,
        "property_name": str,
        "tenant_id": ObjectId,
        "tenant_name": str,
        "units_id": list,  # List of unit IDs
        "unit_numbers": list,  # List of unit numbers (e.g., ["A-01", "A-02"])
        "status": str,  # "signed", "active", "expired", "terminated"
        "lease_start_date": datetime,
        "lease_end_date": datetime,
        "days_remaining": int,  # Days until lease expires
    },
    
    # Financial Info (at time of snapshot)
    "financial_snapshot": {
        "monthly_rent": float,
        "deposit_amount": float,
        "deposit_paid": bool,
        "total_rent_collected": float,  # Total collected since lease start
        "total_rent_expected": float,  # Total expected since lease start
        "current_balance": float,  # Outstanding balance at snapshot time
        "arrears_months": float,  # Number of months in arrears
        "collection_rate": float,  # Percentage (0-100)
    },
    
    # Payment History (at time of snapshot)
    "payment_metrics": {
        "total_invoices": int,
        "paid_invoices": int,
        "unpaid_invoices": int,
        "partially_paid_invoices": int,
        "overdue_invoices": int,
        "on_time_payments": int,
        "late_payments": int,
        "average_payment_delay_days": float,
        "last_payment_date": datetime,
        "last_payment_amount": float,
    },
    
    # Utilities Snapshot
    "utilities": [
        {
            "utility_name": str,  # "Water", "Electricity"
            "billing_basis": str,  # "metered", "fixed"
            "current_reading": float,
            "previous_reading": float,
            "consumption": float,
            "cost": float,
            "rate": float,
        }
    ],
    
    # Compliance & Issues
    "compliance": {
        "has_active_violations": bool,
        "violation_count": int,
        "has_maintenance_issues": bool,
        "open_tickets": int,
        "contract_breaches": int,
    },
    
    # Changes Since Last Snapshot
    "changes_since_last": {
        "rent_changed": bool,
        "status_changed": bool,
        "payment_received": bool,
        "new_violations": int,
        "changes_description": str,
    },
    
    # Metadata
    "created_at": datetime,
    "created_by": str,  # User ID or "system"
    "notes": str,  # Optional notes
}


"""
Collection: property_occupancy_snapshots
Purpose: Track property-level occupancy metrics over time
"""
PROPERTY_OCCUPANCY_SNAPSHOT_SCHEMA = {
    "_id": ObjectId,
    "snapshot_id": str,  # "OCC-SNAP-2025-10-30"
    "property_id": str,
    "property_name": str,
    "snapshot_date": datetime,
    "snapshot_period": str,  # "2025-10" for monthly, "2025-Q4" for quarterly
    "snapshot_type": str,  # "daily", "weekly", "monthly", "quarterly", "annual"
    
    # Unit Statistics
    "unit_stats": {
        "total_units": int,
        "occupied_units": int,
        "vacant_units": int,
        "reserved_units": int,  # Units with signed lease but not yet moved in
        "maintenance_units": int,  # Units under maintenance
        "occupancy_rate": float,  # Percentage (0-100)
        "vacancy_rate": float,  # Percentage (0-100)
    },
    
    # Breakdown by Unit Type
    "unit_type_breakdown": [
        {
            "bedrooms": int,  # 1, 2, 3, etc.
            "total": int,
            "occupied": int,
            "vacant": int,
            "occupancy_rate": float,
        }
    ],
    
    # Lease Statistics
    "lease_stats": {
        "active_leases": int,
        "expiring_this_month": int,
        "expiring_next_month": int,
        "expiring_next_3_months": int,
        "new_leases_this_period": int,
        "terminated_leases_this_period": int,
        "renewed_leases_this_period": int,
        "average_lease_duration_months": float,
    },
    
    # Financial Performance
    "financial_performance": {
        "expected_monthly_rent": float,  # From all active leases
        "actual_collected_rent": float,  # For this period
        "collection_rate": float,  # Percentage
        "total_outstanding": float,
        "average_rent_per_unit": float,
        "revenue_per_occupied_unit": float,
        "potential_revenue_loss": float,  # From vacant units
    },
    
    # Tenant Turnover
    "turnover_metrics": {
        "move_ins_this_period": int,
        "move_outs_this_period": int,
        "net_change": int,
        "turnover_rate": float,  # Percentage
        "average_tenant_tenure_months": float,
    },
    
    # Market Comparison (optional)
    "market_comparison": {
        "market_average_rent": float,
        "property_vs_market": float,  # Percentage difference
        "market_occupancy_rate": float,
        "competitive_position": str,  # "above", "at", "below" market
    },
    
    # Trends (comparison to previous snapshot)
    "trends": {
        "occupancy_change": float,  # Percentage points change
        "collection_rate_change": float,
        "rent_change": float,
        "trend_direction": str,  # "improving", "stable", "declining"
    },
    
    # Metadata
    "created_at": datetime,
    "created_by": str,
    "notes": str,
}


"""
Collection: tenant_performance
Purpose: Track individual tenant payment behavior and performance metrics
"""
TENANT_PERFORMANCE_SCHEMA = {
    "_id": ObjectId,
    "performance_id": str,  # "PERF-TENANT-2025-10-30-001"
    "tenant_id": ObjectId,
    "tenant_name": str,
    "tenant_email": str,
    "tenant_phone": str,
    "property_id": str,
    "property_name": str,
    "lease_id": ObjectId,
    
    # Time Period
    "evaluation_date": datetime,
    "evaluation_period": str,  # "2025-10" or "2025-Q4" or "2025"
    "period_type": str,  # "monthly", "quarterly", "annual", "lifetime"
    
    # Basic Tenant Info
    "tenant_info": {
        "move_in_date": datetime,
        "lease_start_date": datetime,
        "lease_end_date": datetime,
        "months_as_tenant": float,
        "current_lease_status": str,  # "active", "expiring_soon", "expired"
        "unit_numbers": list,
        "monthly_rent": float,
    },
    
    # Payment Performance
    "payment_performance": {
        "total_invoices": int,
        "paid_invoices": int,
        "partially_paid_invoices": int,
        "unpaid_invoices": int,
        "overdue_invoices": int,
        
        # Payment Timing
        "on_time_payments": int,
        "late_payments": int,
        "on_time_payment_rate": float,  # Percentage
        "average_days_to_pay": float,
        "average_days_late": float,  # Only for late payments
        
        # Financial Metrics
        "total_billed": float,
        "total_paid": float,
        "current_balance": float,
        "highest_balance": float,  # Peak outstanding balance
        "average_monthly_balance": float,
        "collection_rate": float,  # Percentage
        
        # Payment Methods
        "payment_method_preference": str,  # Most used method
        "payment_methods_used": dict,  # {"mpesa": 15, "bank": 5, "cash": 2}
    },
    
    # Risk Assessment
    "risk_assessment": {
        "risk_score": float,  # 0-100 (0=low risk, 100=high risk)
        "risk_level": str,  # "LOW", "MEDIUM", "HIGH"
        "risk_factors": [
            {
                "factor": str,  # "late_payments", "high_balance", etc.
                "score": float,
                "weight": float,
            }
        ],
        "days_overdue": int,
        "months_in_arrears": float,
        "probability_of_default": float,  # Percentage
    },
    
    # Behavioral Patterns
    "behavioral_patterns": {
        "payment_consistency": str,  # "excellent", "good", "poor", "erratic"
        "payment_trend": str,  # "improving", "stable", "declining"
        "seasonal_patterns": bool,
        "preferred_payment_day": int,  # Day of month (1-31)
        "typical_payment_delay": int,  # Days after due date
    },
    
    # Communication History
    "communication": {
        "reminder_emails_sent": int,
        "reminder_sms_sent": int,
        "phone_calls_made": int,
        "meetings_held": int,
        "last_contact_date": datetime,
        "response_rate": float,  # Percentage
        "escalation_count": int,  # Number of times escalated
    },
    
    # Compliance & Issues
    "compliance": {
        "lease_violations": int,
        "noise_complaints": int,
        "property_damage_incidents": int,
        "unauthorized_occupants": int,
        "maintenance_issues_reported": int,
        "maintenance_issues_caused": int,
        "has_active_disputes": bool,
        "compliance_score": float,  # 0-100
    },
    
    # Utilities Performance (for metered utilities)
    "utilities_performance": [
        {
            "utility_name": str,
            "average_monthly_consumption": float,
            "average_monthly_cost": float,
            "consumption_trend": str,  # "increasing", "stable", "decreasing"
            "anomalies_detected": int,
        }
    ],
    
    # Comparative Metrics
    "comparative_metrics": {
        "rank_among_property_tenants": int,  # 1 = best performer
        "percentile": float,  # 0-100
        "vs_property_average": {
            "collection_rate_diff": float,
            "payment_timing_diff": float,
        },
    },
    
    # Predictions & Recommendations
    "predictions": {
        "predicted_next_payment_date": datetime,
        "predicted_payment_amount": float,
        "renewal_likelihood": float,  # Percentage
        "churn_risk": float,  # Percentage
    },
    
    "recommendations": [
        {
            "type": str,  # "action", "alert", "opportunity"
            "priority": str,  # "high", "medium", "low"
            "recommendation": str,
            "reason": str,
        }
    ],
    
    # Historical Comparison
    "historical_comparison": {
        "last_period_risk_score": float,
        "risk_score_change": float,
        "last_period_collection_rate": float,
        "collection_rate_change": float,
        "performance_trend": str,  # "improving", "stable", "declining"
    },
    
    # Metadata
    "created_at": datetime,
    "updated_at": datetime,
    "created_by": str,
    "notes": str,
    "tags": list,  # ["vip", "watch_list", "excellent_payer", etc.]
}


# ============================================================================
# HELPER FUNCTIONS TO CREATE SNAPSHOTS
# ============================================================================

class SnapshotManager:
    """Manager for creating and maintaining snapshots"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_lease_snapshot(
        self,
        lease_id: str,
        snapshot_type: str = "monthly",
        notes: str = ""
    ) -> str:
        """
        Create a lease snapshot
        
        Args:
            lease_id: Lease ID
            snapshot_type: Type of snapshot
            notes: Optional notes
        
        Returns:
            Snapshot ID
        """
        
        if isinstance(lease_id, str):
            lease_id = ObjectId(lease_id)
        
        # Get lease data
        lease = await self.db.property_leases.find_one({"_id": lease_id})
        if not lease:
            raise ValueError(f"Lease {lease_id} not found")
        
        # Get property data
        property_data = await self.db.properties.find_one({"_id": lease["property_id"]})
        
        # Get tenant data
        tenant = await self.db.property_tenants.find_one({"_id": lease["tenant_id"]})
        
        # Get all invoices for this lease
        invoices_cursor = self.db.property_invoices.find({"lease_id": str(lease_id)})
        invoices = await invoices_cursor.to_list(length=None)
        
        # Calculate financial metrics
        total_expected = sum(inv.get("total_amount", 0) for inv in invoices)
        total_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        current_balance = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        # Calculate payment metrics
        paid_count = sum(1 for inv in invoices if inv.get("status") == "paid")
        unpaid_count = sum(1 for inv in invoices if inv.get("status") == "unpaid")
        partial_count = sum(1 for inv in invoices if inv.get("status") == "partially_paid")
        overdue_count = sum(1 for inv in invoices if inv.get("status") == "overdue")
        
        # Calculate days remaining
        current_date = datetime.now(timezone.utc)
        end_date = lease["lease_terms"]["end_date"]
        days_remaining = (end_date - current_date).days if end_date > current_date else 0
        
        # Generate snapshot ID
        snapshot_id = f"SNAP-{current_date.strftime('%Y-%m-%d')}-{str(ObjectId())[:8]}"
        
        # Create snapshot document
        snapshot = {
            "_id": ObjectId(),
            "snapshot_id": snapshot_id,
            "lease_id": lease_id,
            "snapshot_date": current_date,
            "snapshot_type": snapshot_type,
            
            "lease_info": {
                "property_id": lease["property_id"],
                "property_name": property_data.get("name", "Unknown"),
                "tenant_id": lease["tenant_id"],
                "tenant_name": tenant.get("full_name", "Unknown") if tenant else "Unknown",
                "units_id": lease.get("units_id", []),
                "unit_numbers": [],  # TODO: Fetch from units collection
                "status": lease.get("status", "active"),
                "lease_start_date": lease["lease_terms"]["start_date"],
                "lease_end_date": lease["lease_terms"]["end_date"],
                "days_remaining": days_remaining,
            },
            
            "financial_snapshot": {
                "monthly_rent": lease["lease_terms"]["rent_amount"],
                "deposit_amount": lease["lease_terms"]["deposit_amount"],
                "deposit_paid": lease["financial_details"].get("deposit_paid", False),
                "total_rent_collected": round(total_collected, 2),
                "total_rent_expected": round(total_expected, 2),
                "current_balance": round(current_balance, 2),
                "arrears_months": round(current_balance / lease["lease_terms"]["rent_amount"], 2) if lease["lease_terms"]["rent_amount"] > 0 else 0,
                "collection_rate": round((total_collected / total_expected * 100) if total_expected > 0 else 0, 2),
            },
            
            "payment_metrics": {
                "total_invoices": len(invoices),
                "paid_invoices": paid_count,
                "unpaid_invoices": unpaid_count,
                "partially_paid_invoices": partial_count,
                "overdue_invoices": overdue_count,
                "on_time_payments": paid_count,  # Simplified
                "late_payments": overdue_count,
                "average_payment_delay_days": 0.0,  # TODO: Calculate
                "last_payment_date": None,  # TODO: Get from payments
                "last_payment_amount": 0.0,
            },
            
            "utilities": [],  # TODO: Add utility snapshots
            
            "compliance": {
                "has_active_violations": False,
                "violation_count": 0,
                "has_maintenance_issues": False,
                "open_tickets": 0,
                "contract_breaches": 0,
            },
            
            "changes_since_last": {
                "rent_changed": False,
                "status_changed": False,
                "payment_received": False,
                "new_violations": 0,
                "changes_description": "",
            },
            
            "created_at": current_date,
            "created_by": "system",
            "notes": notes,
        }
        
        # Insert snapshot
        await self.db.lease_snapshots.insert_one(snapshot)
        
        print(f"✅ Created lease snapshot: {snapshot_id}")
        return snapshot_id
    
    async def create_property_occupancy_snapshot(
        self,
        property_id: str,
        snapshot_type: str = "monthly"
    ) -> str:
        """Create property occupancy snapshot"""
        
        current_date = datetime.now(timezone.utc)
        period = current_date.strftime("%Y-%m")
        
        # Get property data
        property_data = await self.db.properties.find_one({"_id": property_id})
        if not property_data:
            raise ValueError(f"Property {property_id} not found")
        
        # Get all units
        units_cursor = self.db.property_units.find({"property_id": property_id})
        all_units = await units_cursor.to_list(length=None)
        total_units = len(all_units)
        
        # Get active leases
        active_leases_cursor = self.db.property_leases.find({
            "property_id": property_id,
            "status": "signed"
        })
        active_leases = await active_leases_cursor.to_list(length=None)
        
        occupied_units = len(set(
            unit_id
            for lease in active_leases
            for unit_id in lease.get("units_id", [])
        ))
        
        vacant_units = total_units - occupied_units
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Expected monthly rent
        expected_rent = sum(lease["lease_terms"]["rent_amount"] for lease in active_leases)
        
        # Get current month invoices
        month_start = datetime(current_date.year, current_date.month, 1, tzinfo=timezone.utc)
        if current_date.month == 12:
            month_end = datetime(current_date.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            month_end = datetime(current_date.year, current_date.month + 1, 1, tzinfo=timezone.utc)
        
        invoices_cursor = self.db.property_invoices.find({
            "property_id": property_id,
            "date_issued": {"$gte": month_start, "$lt": month_end}
        })
        invoices = await invoices_cursor.to_list(length=None)
        
        actual_collected = sum(inv.get("total_paid", 0) for inv in invoices)
        collection_rate = (actual_collected / expected_rent * 100) if expected_rent > 0 else 0
        
        # Generate snapshot ID
        snapshot_id = f"OCC-SNAP-{period}"
        
        snapshot = {
            "_id": ObjectId(),
            "snapshot_id": snapshot_id,
            "property_id": property_id,
            "property_name": property_data.get("name"),
            "snapshot_date": current_date,
            "snapshot_period": period,
            "snapshot_type": snapshot_type,
            
            "unit_stats": {
                "total_units": total_units,
                "occupied_units": occupied_units,
                "vacant_units": vacant_units,
                "reserved_units": 0,
                "maintenance_units": 0,
                "occupancy_rate": round(occupancy_rate, 2),
                "vacancy_rate": round(100 - occupancy_rate, 2),
            },
            
            "unit_type_breakdown": [],  # TODO: Add breakdown by bedrooms
            
            "lease_stats": {
                "active_leases": len(active_leases),
                "expiring_this_month": 0,  # TODO: Calculate
                "expiring_next_month": 0,
                "expiring_next_3_months": 0,
                "new_leases_this_period": 0,
                "terminated_leases_this_period": 0,
                "renewed_leases_this_period": 0,
                "average_lease_duration_months": 12.0,
            },
            
            "financial_performance": {
                "expected_monthly_rent": round(expected_rent, 2),
                "actual_collected_rent": round(actual_collected, 2),
                "collection_rate": round(collection_rate, 2),
                "total_outstanding": 0.0,  # TODO: Calculate
                "average_rent_per_unit": round(expected_rent / total_units, 2) if total_units > 0 else 0,
                "revenue_per_occupied_unit": round(actual_collected / occupied_units, 2) if occupied_units > 0 else 0,
                "potential_revenue_loss": 0.0,  # TODO: Calculate from vacant units
            },
            
            "turnover_metrics": {
                "move_ins_this_period": 0,
                "move_outs_this_period": 0,
                "net_change": 0,
                "turnover_rate": 0.0,
                "average_tenant_tenure_months": 0.0,
            },
            
            "market_comparison": {
                "market_average_rent": 0.0,
                "property_vs_market": 0.0,
                "market_occupancy_rate": 0.0,
                "competitive_position": "at",
            },
            
            "trends": {
                "occupancy_change": 0.0,
                "collection_rate_change": 0.0,
                "rent_change": 0.0,
                "trend_direction": "stable",
            },
            
            "created_at": current_date,
            "created_by": "system",
            "notes": "",
        }
        
        await self.db.property_occupancy_snapshots.insert_one(snapshot)
        
        print(f"✅ Created property occupancy snapshot: {snapshot_id}")
        return snapshot_id
    
    async def create_tenant_performance_record(
        self,
        tenant_id: str,
        period_type: str = "monthly"
    ) -> str:
        """Create tenant performance record"""
        
        if isinstance(tenant_id, str):
            tenant_id = ObjectId(tenant_id)
        
        current_date = datetime.now(timezone.utc)
        period = current_date.strftime("%Y-%m")
        
        # Get tenant data
        tenant = await self.db.property_tenants.find_one({"_id": tenant_id})
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")
        
        # Get lease
        lease = await self.db.property_leases.find_one({"tenant_id": tenant_id, "status": "signed"})
        
        # Get all invoices
        invoices_cursor = self.db.property_invoices.find({"tenant_id": tenant_id})
        invoices = await invoices_cursor.to_list(length=None)
        
        # Calculate metrics
        total_billed = sum(inv.get("total_amount", 0) for inv in invoices)
        total_paid = sum(inv.get("total_paid", 0) for inv in invoices)
        current_balance = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        paid_count = sum(1 for inv in invoices if inv.get("status") == "paid")
        unpaid_count = sum(1 for inv in invoices if inv.get("status") == "unpaid")
        
        # Generate performance ID
        performance_id = f"PERF-{str(tenant_id)[:8]}-{period}"
        
        performance = {
            "_id": ObjectId(),
            "performance_id": performance_id,
            "tenant_id": tenant_id,
            "tenant_name": tenant.get("full_name"),
            "tenant_email": tenant.get("email"),
            "tenant_phone": tenant.get("phone"),
            "property_id": tenant.get("property_id"),
            "property_name": "",  # TODO: Fetch
            "lease_id": lease["_id"] if lease else None,
            
            "evaluation_date": current_date,
            "evaluation_period": period,
            "period_type": period_type,
            
            "tenant_info": {
                "move_in_date": tenant.get("move_in_date"),
                "lease_start_date": lease["lease_terms"]["start_date"] if lease else None,
                "lease_end_date": lease["lease_terms"]["end_date"] if lease else None,
                "months_as_tenant": 0.0,  # TODO: Calculate
                "current_lease_status": "active",
                "unit_numbers": [],
                "monthly_rent": lease["lease_terms"]["rent_amount"] if lease else 0,
            },
            
            "payment_performance": {
                "total_invoices": len(invoices),
                "paid_invoices": paid_count,
                "partially_paid_invoices": 0,
                "unpaid_invoices": unpaid_count,
                "overdue_invoices": 0,
                
                "on_time_payments": paid_count,
                "late_payments": 0,
                "on_time_payment_rate": round((paid_count / len(invoices) * 100) if invoices else 0, 2),
                "average_days_to_pay": 0.0,
                "average_days_late": 0.0,
                
                "total_billed": round(total_billed, 2),
                "total_paid": round(total_paid, 2),
                "current_balance": round(current_balance, 2),
                "highest_balance": round(current_balance, 2),
                "average_monthly_balance": round(current_balance, 2),
                "collection_rate": round((total_paid / total_billed * 100) if total_billed > 0 else 0, 2),
                
                "payment_method_preference": "mpesa",
                "payment_methods_used": {},
            },
            
            "risk_assessment": {
                "risk_score": 0.0,
                "risk_level": "LOW",
                "risk_factors": [],
                "days_overdue": 0,
                "months_in_arrears": 0.0,
                "probability_of_default": 0.0,
            },
            
            "behavioral_patterns": {
                "payment_consistency": "good",
                "payment_trend": "stable",
                "seasonal_patterns": False,
                "preferred_payment_day": 5,
                "typical_payment_delay": 0,
            },
            
            "communication": {
                "reminder_emails_sent": 0,
                "reminder_sms_sent": 0,
                "phone_calls_made": 0,
                "meetings_held": 0,
                "last_contact_date": None,
                "response_rate": 0.0,
                "escalation_count": 0,
            },
            
            "compliance": {
                "lease_violations": 0,
                "noise_complaints": 0,
                "property_damage_incidents": 0,
                "unauthorized_occupants": 0,
                "maintenance_issues_reported": 0,
                "maintenance_issues_caused": 0,
                "has_active_disputes": False,
                "compliance_score": 100.0,
            },
            
            "utilities_performance": [],
            
            "comparative_metrics": {
                "rank_among_property_tenants": 0,
                "percentile": 0.0,
                "vs_property_average": {
                    "collection_rate_diff": 0.0,
                    "payment_timing_diff": 0.0,
                },
            },
            
            "predictions": {
                "predicted_next_payment_date": None,
                "predicted_payment_amount": 0.0,
                "renewal_likelihood": 0.0,
                "churn_risk": 0.0,
            },
            
            "recommendations": [],
            
            "historical_comparison": {
                "last_period_risk_score": 0.0,
                "risk_score_change": 0.0,
                "last_period_collection_rate": 0.0,
                "collection_rate_change": 0.0,
                "performance_trend": "stable",
            },
            
            "created_at": current_date,
            "updated_at": current_date,
            "created_by": "system",
            "notes": "",
            "tags": [],
        }
        
        await self.db.tenant_performance.insert_one(performance)
        
        print(f"✅ Created tenant performance record: {performance_id}")
        return performance_id


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def create_all_snapshots_example():
    """Example of creating all snapshot types"""
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    db = client["fq_db"]
    
    manager = SnapshotManager(db)
    
    try:
        # Get sample data
        lease = await db.property_leases.find_one({"status": "signed"})
        property_data = await db.properties.find_one({})
        tenant = await db.property_tenants.find_one({})
        
        if lease:
            print("\n1. Creating Lease Snapshot...")
            await manager.create_lease_snapshot(str(lease["_id"]), "monthly")
        
        if property_data:
            print("\n2. Creating Property Occupancy Snapshot...")
            await manager.create_property_occupancy_snapshot(property_data["_id"], "monthly")
        
        if tenant:
            print("\n3. Creating Tenant Performance Record...")
            await manager.create_tenant_performance_record(str(tenant["_id"]), "monthly")
        
        print("\n✅ All snapshots created successfully!")
        
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(create_all_snapshots_example())