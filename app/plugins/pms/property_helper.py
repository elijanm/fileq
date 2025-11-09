import asyncio
from datetime import datetime, timedelta
from typing import Optional
from routes.auth import SessionInfo
from plugins.pms.models.models import (
    PropertySummary,
UnitMetrics,
TenantMetrics,
FinancialMetrics,
PropertyMetrics,
UnitListItem,
TenantListItem,
PropertyDetailResponse
)
from fastapi import (
    HTTPException, Request,Depends,
)


async def get_property_with_counts(db, property_id: str, user_id: str) -> Optional[dict]:
    """Get property details with unit counts using aggregation."""
    pipeline = [
        {
            "$match": {
                "_id": property_id,
                "owner_id": user_id
            }
        },
        {
            "$lookup": {
                "from": "units",
                "let": {"prop_id": {"$toString": "$_id"}},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$propertyId", "$$prop_id"]}
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": 1},
                            "occupied": {
                                "$sum": {"$cond": ["$isOccupied", 1, 0]}
                            }
                        }
                    }
                ],
                "as": "unit_stats"
            }
        },
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "name": 1,
                "description": 1,
                "location": 1,
                "propertyType": "$propertyType",
                "currency": {"$ifNull": ["$currency", "KES"]},
                "customImage": "$customImage",
                "createdAt": {
                    "$cond": [
                        {"$ne": ["$createdAt", None]},
                        {"$dateToString": {"format": "%Y-%m-%dT%H:%M:%S.%LZ", "date": "$createdAt"}},
                        None
                    ]
                },
                "totalUnits": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$unit_stats.total", 0]},
                        0
                    ]
                },
                "occupiedUnits": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$unit_stats.occupied", 0]},
                        0
                    ]
                },
                "vacantUnits": {
                    "$subtract": [
                        {"$ifNull": [{"$arrayElemAt": ["$unit_stats.total", 0]}, 0]},
                        {"$ifNull": [{"$arrayElemAt": ["$unit_stats.occupied", 0]}, 0]}
                    ]
                },
                "occupancyRate": {
                    "$cond": [
                        {"$gt": [{"$arrayElemAt": ["$unit_stats.total", 0]}, 0]},
                        {
                            "$round": [
                                {
                                    "$multiply": [
                                        {
                                            "$divide": [
                                                {"$arrayElemAt": ["$unit_stats.occupied", 0]},
                                                {"$arrayElemAt": ["$unit_stats.total", 0]}
                                            ]
                                        },
                                        100
                                    ]
                                },
                                2
                            ]
                        },
                        0
                    ]
                }
            }
        }
    ]
    
    result = await db["properties"].aggregate(pipeline).to_list(1)
    return result[0] if result else None


async def calculate_property_metrics(db, property_id: str) -> dict:
    """Calculate all property metrics with parallel sub-queries."""
    current_date = datetime.now()
    thirty_days_from_now = current_date + timedelta(days=30)
    current_month_start = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Run all metric calculations in parallel
    results = await asyncio.gather(
        calculate_unit_metrics(db, property_id),
        calculate_tenant_metrics(db, property_id, current_date, thirty_days_from_now, current_month_start),
        calculate_financial_metrics(db, property_id, current_month_start)
    )
    
    unit_metrics, tenant_metrics, financial_metrics = results
    
    return {
        "units": unit_metrics,
        "tenants": tenant_metrics,
        "financial": financial_metrics
    }


async def calculate_unit_metrics(db, property_id: str) -> dict:
    """Calculate unit metrics with grouping by type and status"""
    pipeline = [
        {"$match": {"propertyId": property_id}},
        {
            "$facet": {
                "overall": [
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": 1},
                            "occupied": {"$sum": {"$cond": ["$isOccupied", 1, 0]}},
                            "vacant": {"$sum": {"$cond": ["$isOccupied", 0, 1]}}
                        }
                    }
                ],
                "by_type": [
                    {
                        "$group": {
                            "_id": "$unitType",
                            "count": {"$sum": 1},
                            "occupied": {"$sum": {"$cond": ["$isOccupied", 1, 0]}}
                        }
                    }
                ],
                "by_status": [
                    {
                        "$group": {
                            "_id": "$status",
                            "count": {"$sum": 1}
                        }
                    }
                ]
            }
        }
    ]
    
    result = await db["units"].aggregate(pipeline).to_list(1)
    
    if result and result[0]["overall"]:
        overall_data = result[0]["overall"][0]
        total = overall_data["total"]
        occupied = overall_data["occupied"]
        occupancy_rate = (occupied / total * 100) if total > 0 else 0
        
        # Process by_type
        by_type = {
            item["_id"]: {
                "total": item["count"],
                "occupied": item["occupied"],
                "vacant": item["count"] - item["occupied"]
            }
            for item in result[0]["by_type"]
        }
        
        # Process by_status
        by_status = {
            item["_id"]: item["count"]
            for item in result[0]["by_status"]
        }
    else:
        total = occupied = occupancy_rate = 0
        by_type = {}
        by_status = {}
    
    return {
        "total": total,
        "occupied": occupied,
        "vacant": total - occupied,
        "occupancyRate": round(occupancy_rate, 2),
        "byType": by_type,
        "byStatus": by_status
    }


async def calculate_tenant_metrics(db, property_id: str, current_date, thirty_days_from_now, current_month_start) -> dict:
    """Calculate tenant metrics"""
    lease_pipeline = [
        {"$match": {"propertyId": property_id, "currentTenantId": {"$ne": None}}},
        {
            "$lookup": {
                "from": "leases",
                "localField": "currentTenantId",
                "foreignField": "tenant_id",
                "as": "lease_info"
            }
        },
        {"$unwind": {"path": "$lease_info", "preserveNullAndEmptyArrays": True}},
        {
            "$match": {
                "$or": [
                    {"lease_info.end_date": {"$gte": current_date}},
                    {"lease_info.end_date": None},
                    {"lease_info": {"$exists": False}}
                ]
            }
        },
        {
            "$group": {
                "_id": None,
                "total_tenants": {"$addToSet": "$currentTenantId"},
                "active_leases": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$lease_info", None]},
                                    {"$gte": ["$lease_info.end_date", current_date]}
                                ]
                            },
                            1,
                            0
                        ]
                    }
                },
                "expiring_soon": {
                    "$sum": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$gte": ["$lease_info.end_date", current_date]},
                                    {"$lte": ["$lease_info.end_date", thirty_days_from_now]}
                                ]
                            },
                            1,
                            0
                        ]
                    }
                }
            }
        }
    ]
    
    payment_pipeline = [
        {"$match": {
            "property_id": property_id,
            "due_date": {"$gte": current_month_start}
        }},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    tenant_result, payment_results = await asyncio.gather(
        db["units"].aggregate(lease_pipeline).to_list(1),
        db["invoices"].aggregate(payment_pipeline).to_list(None)
    )
    
    if tenant_result:
        total_tenants = len(tenant_result[0].get("total_tenants", []))
        active_leases = tenant_result[0].get("active_leases", 0)
        expiring_soon = tenant_result[0].get("expiring_soon", 0)
    else:
        total_tenants = active_leases = expiring_soon = 0
    
    paid_count = 0
    overdue_count = 0
    for result in payment_results:
        if result["_id"] == "paid":
            paid_count = result["count"]
        elif result["_id"] == "overdue":
            overdue_count = result["count"]
    
    return {
        "totalTenants": total_tenants,
        "activeLeases": active_leases,
        "expiringSoon": expiring_soon,
        "paidThisMonth": paid_count,
        "overdueThisMonth": overdue_count
    }


async def calculate_financial_metrics(db, property_id: str, current_month_start) -> dict:
    """Calculate financial metrics including deposits and service charges"""
    financial_pipeline = [
        {"$match": {"propertyId": property_id}},
        {
            "$group": {
                "_id": None,
                "potential_monthly_rent": { "$sum": { "$ifNull": [ "$rentAmount", 0 ] } },
                "expected_monthly": {"$sum": {"$cond": ["$isOccupied", "$rentAmount", 0]}},
                "total_deposits": {"$sum": {"$cond": ["$isOccupied", "$depositAmount", 0]}},
                "total_service_charges": {"$sum": {"$cond": ["$isOccupied", "$serviceCharge", 0]}}
            }
        }
    ]
    
    collection_pipeline = [
        {"$match": {
            "property_id": property_id,
            "due_date": {"$gte": current_month_start}
        }},
        {"$group": {
            "_id": "$status",
            "amount": {"$sum": "$amount"}
        }}
    ]
    
    financial_result, collection_results = await asyncio.gather(
        db["units"].aggregate(financial_pipeline).to_list(1),
        db["invoices"].aggregate(collection_pipeline).to_list(None)
    )
    
    if financial_result:
        potential_monthly_rent = financial_result[0].get("potential_monthly_rent", 0)
        expected_monthly = financial_result[0].get("expected_monthly", 0)
        total_deposits = financial_result[0].get("total_deposits", 0)
        total_service_charges = financial_result[0].get("total_service_charges", 0)
    else:
        expected_monthly = total_deposits = total_service_charges = 0
    
    collected = 0
    overdue = 0
    for result in collection_results:
        if result["_id"] == "paid":
            collected = result["amount"]
        elif result["_id"] == "overdue":
            overdue = result["amount"]
    
    collection_rate = (collected / expected_monthly * 100) if expected_monthly > 0 else 0
    
    return {
        "potentialMonthlyRent": round(potential_monthly_rent, 2),
        "expectedMonthlyRent": round(expected_monthly, 2),
        "collectedRent": round(collected, 2),
        "totalOverdue": round(overdue, 2),
        "collectionRate": round(collection_rate, 2),
        "totalDeposits": round(total_deposits, 2),
        "totalServiceCharges": round(total_service_charges, 2)
    }


async def get_paginated_units(db, property_id: str, skip: int, limit: int) -> list[dict]:
    """Get paginated units with tenant information using aggregation."""
    current_month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    pipeline = [
        {"$match": {"propertyId": property_id}},
        {"$sort": {"unitNumber": 1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "property_tenants",
                "localField": "currentTenantId",
                "foreignField": "_id",
                "as": "tenant_info"
            }
        },
        {
            "$lookup": {
                "from": "invoices",
                "let": {"unit_tenant_id": "$currentTenantId"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$tenant_id", "$$unit_tenant_id"]},
                                    {"$gte": ["$due_date", current_month_start]}
                                ]
                            }
                        }
                    },
                    {"$limit": 1}
                ],
                "as": "current_invoice"
            }
        },
        {
            "$project": {
                "_id": {"$toString": "$_id"},
                "unitNumber": 1,
                "unitName": 1,
                "unitType": 1,
                "floor": 1,
                "wing": 1,
                "bedrooms": 1,
                "bathrooms": 1,
                "sizeSqft": 1,
                "sizeSqm": 1,
                "rentAmount": 1,
                "depositAmount": 1,
                "serviceCharge": 1,
                "status": 1,
                "isOccupied": 1,
                "utilities": 1,
                "setupDone":1,
                "furnishingStatus": 1,
                "hasBalcony": 1,
                "hasParking": 1,
                "parkingSpots": {"$ifNull": ["$parkingSpots", 0]},
                "tenantId": {"$toString": "$currentTenantId"},
                "tenantName": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$tenant_info.full_name", 0]},
                        None
                    ]
                },
                "leaseStart": {
                    "$cond": [
                        {"$ne": ["$leaseStartDate", None]},
                        {"$dateToString": {"format": "%Y-%m-%d", "date": "$leaseStartDate"}},
                        None
                    ]
                },
                "leaseEnd": {
                    "$cond": [
                        {"$ne": ["$leaseEndDate", None]},
                        {"$dateToString": {"format": "%Y-%m-%d", "date": "$leaseEndDate"}},
                        None
                    ]
                },
                "rentStatus": {
                    "$cond": [
                        {"$gt": [{"$size": "$current_invoice"}, 0]},
                        {"$arrayElemAt": ["$current_invoice.status", 0]},
                        None
                    ]
                }
            }
        }
    ]
    
    units = await db["units"].aggregate(pipeline).to_list(None)
    return units


async def get_property_tenants(db, property_id: str) -> list[dict]:
    """Get all tenants for a property with comprehensive details."""
    current_date = datetime.now()
    thirty_days_from_now = current_date + timedelta(days=30)
    
    pipeline = [
        {"$match": {"propertyId": property_id, "currentTenantId": {"$ne": None}}},
        {
            "$lookup": {
                "from": "property_tenants",
                "localField": "currentTenantId",
                "foreignField": "_id",
                "as": "tenant"
            }
        },
        {"$unwind": "$tenant"},
        {
            "$lookup": {
                "from": "leases",
                "let": {"tenant_id": "$currentTenantId", "unit_id": "$_id"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$tenant_id", "$$tenant_id"]},
                                    {"$eq": ["$unit_id", "$$unit_id"]}
                                ]
                            }
                        }
                    },
                    {"$sort": {"start_date": -1}},
                    {"$limit": 1}
                ],
                "as": "lease"
            }
        },
        {"$unwind": {"path": "$lease", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "payments",
                "let": {"tenant_id": "$currentTenantId"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$tenant_id", "$$tenant_id"]}
                        }
                    },
                    {"$sort": {"payment_date": -1}},
                    {"$limit": 1}
                ],
                "as": "last_payment"
            }
        },
        {
            "$lookup": {
                "from": "payments",
                "let": {"tenant_id": "$currentTenantId"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {"$eq": ["$tenant_id", "$$tenant_id"]}
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "total": {"$sum": "$amount"}
                        }
                    }
                ],
                "as": "payment_summary"
            }
        },
        {
            "$lookup": {
                "from": "invoices",
                "let": {"tenant_id": "$currentTenantId"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$tenant_id", "$$tenant_id"]},
                                    {"$in": ["$status", ["pending", "overdue"]]}
                                ]
                            }
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "outstanding": {"$sum": "$amount"}
                        }
                    }
                ],
                "as": "outstanding_summary"
            }
        },
        {
            "$project": {
                "_id": {"$toString": "$tenant._id"},
                "fullName": "$tenant.full_name",
                "email": "$tenant.email",
                "phone": "$tenant.phone",
                "unitNumber": "$unitNumber",
                "unitName": "$unitName",
                "unitType": "$unitType",
                "rentAmount": "$rentAmount",
                "depositAmount": "$depositAmount",
                "serviceCharge": "$serviceCharge",
                "leaseStatus": {
                    "$cond": [
                        {"$gte": ["$lease.end_date", thirty_days_from_now]},
                        "active",
                        {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$lease.end_date", current_date]},
                                        {"$lt": ["$lease.end_date", thirty_days_from_now]}
                                    ]
                                },
                                "expiring_soon",
                                {
                                    "$cond": [
                                        {"$lt": ["$lease.end_date", current_date]},
                                        "expired",
                                        "active"
                                    ]
                                }
                            ]
                        }
                    ]
                },
                "leaseStart": {
                    "$cond": [
                        {"$ne": ["$lease.start_date", None]},
                        {"$dateToString": {"format": "%Y-%m-%d", "date": "$lease.start_date"}},
                        {
                            "$cond": [
                                {"$ne": ["$leaseStartDate", None]},
                                {"$dateToString": {"format": "%Y-%m-%d", "date": "$leaseStartDate"}},
                                None
                            ]
                        }
                    ]
                },
                "leaseEnd": {
                    "$cond": [
                        {"$ne": ["$lease.end_date", None]},
                        {"$dateToString": {"format": "%Y-%m-%d", "date": "$lease.end_date"}},
                        {
                            "$cond": [
                                {"$ne": ["$leaseEndDate", None]},
                                {"$dateToString": {"format": "%Y-%m-%d", "date": "$leaseEndDate"}},
                                None
                            ]
                        }
                    ]
                },
                "lastPaymentDate": {
                    "$cond": [
                        {"$gt": [{"$size": "$last_payment"}, 0]},
                        {
                            "$dateToString": {
                                "format": "%Y-%m-%d",
                                "date": {"$arrayElemAt": ["$last_payment.payment_date", 0]}
                            }
                        },
                        None
                    ]
                },
                "lastPaymentAmount": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$last_payment.amount", 0]},
                        None
                    ]
                },
                "totalPaid": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$payment_summary.total", 0]},
                        0
                    ]
                },
                "outstandingBalance": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$outstanding_summary.outstanding", 0]},
                        0
                    ]
                }
            }
        },
        {"$sort": {"fullName": 1}}
    ]
    
    tenants = await db["units"].aggregate(pipeline).to_list(None)
    return tenants

async def get_property_detail(
    request: Request,
    property_id: str,
    user: SessionInfo,
    page: int = 1,
    limit: int = 20,
    include_tenants: bool = True
    
):
    """
    Get property details with metrics, paginated units, and tenant information.
    Runs all queries in parallel for optimal performance.
    """
    db = request.app.state.adb
    print(property_id)
    return {}
    # Run all queries in parallel using asyncio.gather
    skip = (page - 1) * limit
    
    results = await asyncio.gather(
        # 1. Get property with counts
        get_property_with_counts(db, property_id, user.user_id),
        # 2. Calculate metrics
        calculate_property_metrics(db, property_id),
        # 3. Get paginated units
        get_paginated_units(db, property_id, skip, limit),
        # 4. Get tenants (if requested)
        get_property_tenants(db, property_id) if include_tenants else asyncio.sleep(0, result=[]),
        # 5. Get total unit count for pagination
        db["units"].count_documents({"property_id": property_id})
    )
    
    prop, metrics, units, tenants, total_units = results
    
    if not prop:
        raise HTTPException(404, "Property not found or unauthorized")
    
    return {
        "property": prop,
        "units": units,
        "tenants": tenants,
        "metrics": metrics,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_units,
            "totalPages": (total_units + limit - 1) // limit
        }
    }