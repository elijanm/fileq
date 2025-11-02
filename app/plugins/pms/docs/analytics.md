# 📊 Lease Performance & Occupancy Tracking System

## Comprehensive Brainstorming Document

---

## 🎯 1. Key Metrics to Track

### A. Occupancy Metrics

| Metric                      | Description                            | Formula                                     |
| --------------------------- | -------------------------------------- | ------------------------------------------- |
| **Physical Occupancy Rate** | Percentage of units occupied           | `(Occupied Units / Total Units) × 100`      |
| **Economic Occupancy Rate** | Percentage of potential rent collected | `(Rent Collected / Potential Rent) × 100`   |
| **Vacancy Rate**            | Percentage of units vacant             | `(Vacant Units / Total Units) × 100`        |
| **Average Days to Fill**    | Time to fill a vacant unit             | `Total Vacant Days / Number of Vacancies`   |
| **Turnover Rate**           | Move-outs per period                   | `(Move-outs / Total Units) × 100`           |
| **Lease Renewal Rate**      | Percentage of leases renewed           | `(Renewals / Expiring Leases) × 100`        |
| **Average Lease Duration**  | Average length of tenancy              | `Sum of Lease Durations / Number of Leases` |

### B. Financial Performance Metrics

| Metric                            | Description                              | Formula                                                  |
| --------------------------------- | ---------------------------------------- | -------------------------------------------------------- |
| **Rent Collection Rate**          | Percentage of rent collected vs expected | `(Actual Collected / Expected Rent) × 100`               |
| **Average Time to First Payment** | Days from move-in to first payment       | Average across all tenants                               |
| **Payment Consistency Score**     | On-time payment percentage               | `(On-time Payments / Total Payments) × 100`              |
| **Bad Debt Ratio**                | Written-off debt as % of total rent      | `(Written Off / Total Rent Due) × 100`                   |
| **Average Rent per Unit**         | Mean rent across property                | `Total Rent / Number of Units`                           |
| **Rent Growth Rate**              | Year-over-year increase                  | `((Current Rent - Previous Rent) / Previous Rent) × 100` |
| **Utility Recovery Rate**         | Utilities collected vs charged           | `(Collected Utilities / Charged Utilities) × 100`        |

### C. Tenant Behavior Metrics

| Metric                            | Description                    | How to Calculate                                          |
| --------------------------------- | ------------------------------ | --------------------------------------------------------- |
| **Average Tenant Score**          | Overall tenant quality         | Distribution across excellent/good/struggling/problematic |
| **Eviction Rate**                 | Percentage of forced move-outs | `(Evictions / Total Move-outs) × 100`                     |
| **Early Termination Rate**        | Leases ended before term       | `(Early Terminations / Total Leases) × 100`               |
| **Average Notice Period**         | Average days notice given      | Mean of all notice periods                                |
| **Deposit Forfeiture Rate**       | Deposits not returned          | `(Forfeited Deposits / Total Deposits) × 100`             |
| **Maintenance Request Frequency** | Requests per tenant per month  | `Total Requests / (Tenants × Months)`                     |

---

## 📅 2. Time-Based Analysis Framework

### Tracking Periods

```
Monthly Snapshots
├── Current month metrics
├── Month-over-month changes
└── Rolling 12-month average

Quarterly Trends
├── Q1 vs Q2 vs Q3 vs Q4
├── Seasonal patterns
└── Quarter-over-quarter growth

Year-over-Year Comparisons
├── Annual performance
├── YoY growth rates
└── Long-term trends

Lease Lifecycle Analysis
├── Onboarding phase (0-30 days)
├── Settling phase (31-90 days)
├── Stable phase (91-330 days)
└── Ending phase (331-365 days)
```

### Critical Dates to Track

```python
lease_timeline = {
    "lease_signed_date": "When lease agreement was signed",
    "lease_start_date": "Official lease start date",
    "move_in_date": "Actual move-in date (may differ from start)",
    "first_payment_date": "Date of first rent payment",
    "last_payment_date": "Most recent payment",
    "notice_date": "When tenant gave notice to vacate",
    "lease_end_date": "Official lease end date",
    "actual_moveout_date": "Actual move-out date",
    "deposit_return_date": "When deposit was returned"
}
```

---

## 🗄️ 3. Data Structure Design

### A. Lease Snapshot Schema

```python
lease_snapshot = {
    "_id": "ObjectId",
    "lease_id": "690114a68f0daba1fd26f7e2",
    "snapshot_date": "2025-10-31T00:00:00Z",
    "snapshot_type": "monthly",  # daily, weekly, monthly, quarterly

    # Status Information
    "status": {
        "lease_status": "active",  # active, expired, terminated, renewed
        "occupancy_days_total": 31,
        "occupancy_days_this_period": 31,
        "days_remaining": 362
    },

    # Financial Data
    "financials": {
        "rent_expected_total": 10000,
        "rent_collected_total": 10000,
        "rent_outstanding": 0,
        "utilities_expected": 3000,
        "utilities_collected": 3000,
        "utilities_outstanding": 0,
        "total_credits": 0,
        "collection_rate": 100.0
    },

    # Payment Behavior
    "payment_behavior": {
        "payments_made": 1,
        "on_time_payments": 1,
        "late_payments": 0,
        "missed_payments": 0,
        "average_days_late": 0,
        "payment_consistency_score": 100.0,
        "tenant_type": "excellent"
    },

    # Maintenance & Issues
    "maintenance": {
        "requests_total": 0,
        "requests_this_period": 0,
        "average_resolution_time": 0,
        "complaints": 0
    },

    # Tenant Engagement
    "engagement": {
        "communication_responsiveness": "high",
        "lease_compliance": "full",
        "violations": 0,
        "warnings_issued": 0
    }
}
```

### B. Property Occupancy Tracker

```python
property_occupancy_snapshot = {
    "_id": "ObjectId",
    "property_id": "68f44ea8c5181f3902abe14d",
    "snapshot_date": "2025-10-31T00:00:00Z",
    "period": "2025-10",

    # Unit Status
    "units": {
        "total_units": 10,
        "occupied_units": 9,
        "vacant_units": 1,
        "under_maintenance": 0,
        "under_renovation": 0
    },

    # Occupancy Metrics
    "occupancy": {
        "physical_occupancy_rate": 90.0,
        "economic_occupancy_rate": 85.0,
        "vacancy_rate": 10.0,
        "unit_days_occupied": 279,  # 9 units × 31 days
        "unit_days_vacant": 31,     # 1 unit × 31 days
        "total_unit_days": 310
    },

    # Financial Aggregates
    "financials": {
        "potential_rent": 100000,
        "collected_rent": 85000,
        "outstanding_rent": 15000,
        "collection_rate": 85.0,
        "average_rent_per_unit": 10000,
        "total_utilities_charged": 27000,
        "total_utilities_collected": 24000
    },

    # Tenant Distribution
    "tenant_quality": {
        "excellent": 3,
        "good": 4,
        "struggling": 2,
        "problematic": 1,
        "average_score": 3.2
    },

    # Movement
    "movement": {
        "move_ins_this_period": 0,
        "move_outs_this_period": 1,
        "renewals_this_period": 0,
        "terminations_this_period": 0
    },

    # Trends
    "trends": {
        "occupancy_change_mom": -5.0,  # Month-over-month %
        "collection_rate_change_mom": 2.0,
        "vacancy_days_trend": "increasing"
    }
}
```

### C. Tenant Performance Profile

```python
tenant_performance = {
    "_id": "ObjectId",
    "tenant_id": "690117cb5443caf223214141",
    "lease_id": "690114a68f0daba1fd26f7e2",
    "property_id": "68f44ea8c5181f3902abe14d",

    # Profile
    "profile": {
        "name": "Meko Menesi",
        "type": "struggling",
        "risk_level": "medium",
        "score": 2.5  # Out of 5
    },

    # Lifecycle Stages
    "lifecycle": {
        "current_stage": "stable",
        "days_in_lease": 92,
        "lease_progress_percent": 25.0,

        "onboarding": {  # Days 0-30
            "collection_rate": 100.0,
            "issues": 0,
            "score": "excellent"
        },
        "settling": {  # Days 31-90
            "collection_rate": 75.0,
            "issues": 1,
            "score": "good"
        },
        "stable": {  # Days 91-330
            "collection_rate": 60.0,
            "issues": 2,
            "score": "struggling"
        }
    },

    # Payment History Summary
    "payment_summary": {
        "total_invoices": 10,
        "fully_paid_invoices": 5,
        "partially_paid_invoices": 3,
        "unpaid_invoices": 2,
        "total_expected": 100000,
        "total_collected": 60000,
        "total_outstanding": 40000,
        "average_days_to_pay": 15,
        "on_time_rate": 50.0
    },

    # Behavioral Patterns
    "patterns": {
        "payment_pattern": "irregular",
        "typical_payment_day": 15,
        "prefers_partial_payments": true,
        "responds_to_reminders": true,
        "communication_quality": "good",
        "maintenance_frequency": "low"
    },

    # Predictive Indicators
    "predictions": {
        "renewal_likelihood": "low",
        "payment_risk": "medium",
        "early_termination_risk": "high",
        "deposit_forfeiture_risk": "medium"
    }
}
```

---

## 📈 4. Report Types & Templates

### A. Property-Level Executive Summary

```
═══════════════════════════════════════════════════════════════
                    PROPERTY PERFORMANCE REPORT
═══════════════════════════════════════════════════════════════

Property: Westlands Apartments
Address: Westlands, Nairobi
Period: January - October 2025 (10 months)
Report Date: October 31, 2025

───────────────────────────────────────────────────────────────
1. OCCUPANCY SUMMARY
───────────────────────────────────────────────────────────────

Physical Occupancy
┌─────────────────────────────────────────────────────────────┐
│ Total Units:                                          10    │
│ Currently Occupied:                                    9    │
│ Currently Vacant:                                      1    │
│ Current Occupancy Rate:                              90%    │
│                                                             │
│ Average Occupancy (10 months):                       87%    │
│ Peak Occupancy:                                     100%    │
│ Lowest Occupancy:                                    70%    │
│                                                             │
│ Total Occupied Unit-Days:                          2,700    │
│ Total Vacant Unit-Days:                              300    │
│ Average Days to Fill Vacancy:                         45    │
└─────────────────────────────────────────────────────────────┘

Economic Occupancy
┌─────────────────────────────────────────────────────────────┐
│ Economic Occupancy Rate:                             85%    │
│ Loss Due to Vacancies:                              13%    │
│ Loss Due to Non-Payment:                             2%    │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────
2. FINANCIAL PERFORMANCE
───────────────────────────────────────────────────────────────

Revenue Analysis
┌─────────────────────────────────────────────────────────────┐
│ Potential Rent Income:              KES 1,000,000          │
│ Actual Rent Collected:              KES   850,000  (85%)   │
│ Rent Outstanding:                   KES   150,000          │
│                                                             │
│ Utilities Charged:                  KES   270,000          │
│ Utilities Collected:                KES   240,000  (89%)   │
│ Utilities Outstanding:              KES    30,000          │
│                                                             │
│ Total Income Potential:             KES 1,270,000          │
│ Total Collected:                    KES 1,090,000  (86%)   │
│ Total Outstanding:                  KES   180,000          │
└─────────────────────────────────────────────────────────────┘

Collection Metrics
┌─────────────────────────────────────────────────────────────┐
│ Overall Collection Rate:                             86%    │
│ On-Time Payment Rate:                                67%    │
│ Average Days to Payment:                              12    │
│ Bad Debt Written Off:               KES     5,000          │
│ Bad Debt Ratio:                                     0.5%    │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────
3. TENANT QUALITY DISTRIBUTION
───────────────────────────────────────────────────────────────

Tenant Breakdown
┌─────────────────────────────────────────────────────────────┐
│ Type           Count    %     Collection Rate   Avg Score   │
├─────────────────────────────────────────────────────────────┤
│ Excellent         3    30%          98%           4.8       │
│ Good              4    40%          89%           3.9       │
│ Struggling        2    20%          65%           2.5       │
│ Problematic       1    10%          40%           1.8       │
├─────────────────────────────────────────────────────────────┤
│ Total/Average    10   100%          85%           3.6       │
└─────────────────────────────────────────────────────────────┘

Quality Score: ★★★☆☆ (3.6/5.0)

───────────────────────────────────────────────────────────────
4. LEASE MOVEMENT & TURNOVER
───────────────────────────────────────────────────────────────

Activity Summary
┌─────────────────────────────────────────────────────────────┐
│ New Leases Started:                                   3     │
│ Leases Renewed:                                       2     │
│ Leases Terminated:                                    1     │
│ Early Terminations:                                   1     │
│                                                             │
│ Turnover Rate:                                      10%     │
│ Renewal Rate:                                       67%     │
│ Average Lease Duration:                        8 months     │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────
5. TRENDS & INSIGHTS
───────────────────────────────────────────────────────────────

Monthly Occupancy Trend
100% │ ████████████████████████████  ██████████████
 90% │ ████████████████████████████  ██████████████
 80% │ ███████████████████████  ████████████████
 70% │ ██████████████████████  ███████████████
 60% │
     └─────────────────────────────────────────────
      J   F   M   A   M   J   J   A   S   O

Key Observations:
✓ Occupancy dip in June-July (summer vacation)
✓ Strong recovery in September
⚠ Collection rate declining trend (-3% MoM)
⚠ One problematic tenant at risk of eviction

───────────────────────────────────────────────────────────────
6. RECOMMENDATIONS
───────────────────────────────────────────────────────────────

Priority Actions:
1. 🔴 Address problematic tenant (Unit A-05) - consider eviction
2. 🟡 Implement payment plans for 2 struggling tenants
3. 🟢 Market vacant unit (A-10) - target 30-day fill time
4. 🟢 Schedule lease renewal discussions for Q4 expirations

Financial Optimization:
- Potential to increase rent by 8% on renewals (market rate)
- Implement auto-payment incentives to improve collection
- Review utility billing accuracy for economic recovery

═══════════════════════════════════════════════════════════════
```

### B. Individual Lease Performance Report

```
═══════════════════════════════════════════════════════════════
                    LEASE PERFORMANCE REPORT
═══════════════════════════════════════════════════════════════

Lease ID: 690114a68f0daba1fd26f7e2
Tenant: Meko Menesi
Unit: A-01 (2 Bedroom)
Property: Westlands Apartments

───────────────────────────────────────────────────────────────
1. LEASE TIMELINE
───────────────────────────────────────────────────────────────

Key Dates
┌─────────────────────────────────────────────────────────────┐
│ Lease Signed:              2025-10-24                       │
│ Lease Start:               2025-10-28                       │
│ Move-in Date:              2025-10-28  (Same day)           │
│ First Payment:             2025-11-05                       │
│ Lease End:                 2026-10-28                       │
│                                                             │
│ Days Active:                    3 days                      │
│ Days Remaining:               362 days                      │
│ Lease Progress:          [▓░░░░░░░░░░░░] 1%                │
│                                                             │
│ Expected Duration:        365 days (12 months)              │
│ Status:                   Active - New Tenant               │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────
2. FINANCIAL SUMMARY
───────────────────────────────────────────────────────────────

Rent Details
┌─────────────────────────────────────────────────────────────┐
│ Monthly Rent:                         KES 10,000            │
│ Security Deposit:                     KES 20,000            │
│ Deposit Status:                       ✓ Paid in Full       │
│                                                             │
│ Total Expected (Lifetime):            KES 120,000           │
│ Total Collected to Date:              KES      0           │
│ Total Outstanding:                    KES      0           │
│                                                             │
│ Collection Rate:                           N/A              │
│ (Too early - first payment due Nov 5)                      │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────
3. PAYMENT HISTORY
───────────────────────────────────────────────────────────────

Monthly Breakdown
┌─────────────────────────────────────────────────────────────┐
│ Month      Expected    Paid    Outstanding  Status   Due    │
├─────────────────────────────────────────────────────────────┤
│ Oct 2025    10,000       0        10,000     ⏳ Pend  Nov 5 │
├─────────────────────────────────────────────────────────────┤
│ Total       10,000       0        10,000                    │
└─────────────────────────────────────────────────────────────┘

Payment Statistics
┌─────────────────────────────────────────────────────────────┐
│ Payments Made:                                 0            │
│ On-Time Payments:                              0            │
│ Late Payments:                                 0            │
│ Missed Payments:                               0            │
│ Average Days Late:                           N/A            │
│                                                             │
│ On-Time Rate:                                N/A            │
│ Consistency Score:                    Not Established       │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────
4. TENANT PERFORMANCE METRICS
───────────────────────────────────────────────────────────────

Current Assessment
┌─────────────────────────────────────────────────────────────┐
│ Tenant Type:                        New Tenant              │
│ Risk Level:                         Unknown                 │
│ Performance Score:                  Not Yet Rated           │
│                                                             │
│ Communication:                      Good (responsive)       │
│ Lease Compliance:                   Full                    │
│ Maintenance Requests:                    0                  │
│ Complaints:                              0                  │
│ Violations:                              0                  │
└─────────────────────────────────────────────────────────────┘

Lifecycle Stage: Onboarding (Days 0-30)
📊 Establishing payment patterns...

───────────────────────────────────────────────────────────────
5. UTILITIES TRACKING
───────────────────────────────────────────────────────────────

Utilities Setup
┌─────────────────────────────────────────────────────────────┐
│ Utility        Billing    Rate        Last Reading          │
├─────────────────────────────────────────────────────────────┤
│ Water          Metered    200/m³      Pending first read    │
│ Electricity    Metered    N/A         Pending first read    │
├─────────────────────────────────────────────────────────────┤
│ Total Charged to Date:                KES 0                 │
│ Total Collected:                      KES 0                 │
└─────────────────────────────────────────────────────────────┘

───────────────────────────────────────────────────────────────
6. LEASE HEALTH INDICATORS
───────────────────────────────────────────────────────────────

Health Score: ⭕ Not Yet Established

Indicators to Monitor:
├─ ⏳ First payment (due Nov 5, 2025)
├─ ⏳ Payment consistency over 3 months
├─ ⏳ Utility payment behavior
├─ ⏳ Communication responsiveness
└─ ⏳ General lease compliance

Next Review: December 1, 2025 (After 2 payments)

───────────────────────────────────────────────────────────────
7. PREDICTIONS & RECOMMENDATIONS
───────────────────────────────────────────────────────────────

Short-term Actions (30 days):
- Monitor first payment closely (due Nov 5)
- Schedule welcome check-in call
- Ensure utility meters are properly registered
- Set up auto-payment reminder system

Risk Assessment:
┌─────────────────────────────────────────────────────────────┐
│ Renewal Likelihood:           Unknown (too early)           │
│ Payment Risk:                 Low (deposit paid)            │
│ Early Termination Risk:       Low                           │
│ Deposit Forfeiture Risk:      Low                           │
└─────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════
```

### C. Comparative Analysis Report

```
═══════════════════════════════════════════════════════════════
              PORTFOLIO COMPARATIVE ANALYSIS REPORT
═══════════════════════════════════════════════════════════════

Portfolio Overview: 3 Properties
Reporting Period: January - October 2025

───────────────────────────────────────────────────────────────
1. PROPERTY COMPARISON
───────────────────────────────────────────────────────────────

Performance by Property
┌─────────────────────────────────────────────────────────────┐
│ Property          Units  Occ%  Coll%  Score  Avg Rent       │
├─────────────────────────────────────────────────────────────┤
│ Westlands Apts      10    90%   85%   3.6   KES 10,000     │
│ Kilimani Court       10    95%   92%   4.1   KES 12,000     │
│ South B Towers       10    80%   78%   3.2   KES  9,000     │
├─────────────────────────────────────────────────────────────┤
│ Portfolio Avg        30    88%   85%   3.6   KES 10,333     │
└─────────────────────────────────────────────────────────────┘

Best Performers:
🥇 Kilimani Court - Highest occupancy & collection rate
🥈 Westlands Apartments - Strong collection, good tenant mix
🥉 South B Towers - Needs attention on occupancy

───────────────────────────────────────────────────────────────
2. FINANCIAL COMPARISON
───────────────────────────────────────────────────────────────

Revenue Performance
┌─────────────────────────────────────────────────────────────┐
│ Property          Potential    Collected    Outstanding     │
├─────────────────────────────────────────────────────────────┤
│ Westlands       1,000,000      850,000        150,000      │
│ Kilimani        1,200,000    1,104,000         96,000      │
│ South B           900,000      702,000        198,000      │
├─────────────────────────────────────────────────────────────┤
│ Total           3,100,000    2,656,000        444,000      │
└─────────────────────────────────────────────────────────────┘

Portfolio Collection Rate: 86%
Industry Benchmark: 88%
Status: ⚠️ Slightly Below Target

───────────────────────────────────────────────────────────────
3. TENANT QUALITY DISTRIBUTION
───────────────────────────────────────────────────────────────

Across Portfolio
┌─────────────────────────────────────────────────────────────┐
│              Westlands  Kilimani  South B   Portfolio       │
├─────────────────────────────────────────────────────────────┤
│ Excellent        30%      40%      20%        30%          │
│ Good             40%      50%      40%        43%          │
│ Struggling       20%       5%      30%        18%          │
│ Problematic      10%       5%      10%         8%          │
└─────────────────────────────────────────────────────────────┘

Insight: Kilimani has highest quality tenant base

───────────────────────────────────────────────────────────────
4. TRENDS OVER TIME
───────────────────────────────────────────────────────────────

Occupancy Trend (10 Months)
     │
100% │     ▓▓▓▓▓    Kilimani
 95% │   ▓▓▓▓▓▓▓▓
 90% │ ▓▓▓▓▓▓▓▓▓▓  ████████  Westlands
 85% │ ██████████████████████
 80% │ ██████████████████████░░░░░░░  South B
 75% │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
     └───────────────────────────────────────
       J  F  M  A  M  J  J  A  S  O

Collection Rate Trend
     │
100% │     ▓▓▓▓▓▓▓▓  Kilimani
 95% │   ▓▓▓▓▓▓▓▓▓▓
 90% │ ▓▓▓▓▓▓▓▓▓▓▓▓
 85% │ ▓▓▓████████████  Westlands
 80% │ ██████████████████
 75% │ ██████████████░░░░░░░░  South B
     └───────────────────────────────────────
       J  F  M  A  M  J  J  A  S  O

───────────────────────────────────────────────────────────────
5. KEY INSIGHTS & RECOMMENDATIONS
───────────────────────────────────────────────────────────────

🔴 URGENT ACTIONS:
   • South B Towers: Address 3 problematic tenants
   • Westlands: Fill vacant unit within 30 days
   • Portfolio: Improve collection rate by 2% to meet benchmark

🟡 OPPORTUNITIES:
   • Kilimani: Potential for 5% rent increase on renewals
   • Westlands: 2 leases expiring Q4 - prioritize retention
   • South B: Consider tenant quality improvement strategy

🟢 BEST PRACTICES (from Kilimani):
   • Strict tenant screening process
   • Auto-payment incentive program
   • Proactive maintenance schedule
   • Regular tenant engagement events

═══════════════════════════════════════════════════════════════
```

---

## 💡 5. Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)

```
✓ Set up lease snapshot schema
✓ Create basic occupancy calculator
✓ Implement payment history tracker
✓ Design tenant scoring algorithm
```

### Phase 2: Core Reports (Weeks 3-4)

```
✓ Property-level monthly report
✓ Individual lease performance report
✓ Payment analysis dashboard
✓ Tenant quality distribution report
```

### Phase 3: Advanced Analytics (Weeks 5-6)

```
✓ Time-series trend analysis
✓ Comparative property reports
✓ Predictive modeling (risk scoring)
✓ Automated alert system
```

### Phase 4: Visualization & API (Weeks 7-8)

```
✓ Interactive dashboards
✓ Chart/graph generation
✓ REST API endpoints
✓ PDF/Excel export functionality
```

---

## 🔧 6. Technical Implementation Notes

### Database Indexes Needed

```python
# For performance optimization
db.lease_snapshots.createIndex({"lease_id": 1, "snapshot_date": -1})
db.lease_snapshots.createIndex({"property_id": 1, "snapshot_date": -1})
db.property_occupancy_snapshots.createIndex({"property_id": 1, "period": -1})
db.tenant_performance.createIndex({"tenant_id": 1})
db.tenant_performance.createIndex({"property_id": 1, "profile.type": 1})
```

### Scheduled Jobs Required

```python
# Cron jobs to run
- Daily: Calculate daily occupancy snapshots
- Weekly: Generate tenant performance updates
- Monthly: Create comprehensive property reports
- Quarterly: Comparative portfolio analysis
- On lease end: Generate lease lifecycle report
```

### API Endpoints Design

```
GET /api/reports/property/{property_id}/occupancy
GET /api/reports/property/{property_id}/financial
GET /api/reports/lease/{lease_id}/performance
GET /api/reports/tenant/{tenant_id}/score
GET /api/reports/portfolio/comparison
GET /api/reports/export/pdf/{report_id}
```

---

## 📊 7. Key Performance Indicators (KPIs) Dashboard

### Executive Dashboard Layout

```
┌─────────────────────┬─────────────────────┬─────────────────────┐
│  Physical Occupancy │  Economic Occupancy │   Collection Rate   │
│        88%          │        85%          │        86%          │
│      ▲ +2%          │      ▼ -1%          │      ▼ -3%          │
└─────────────────────┴─────────────────────┴─────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                     Occupancy Trend (12M)                      │
│  100% ┼──────────────────────────────────────────            │
│   90% ┼████████████████████████████████████                  │
│   80% ┼████████████████████████████████                      │
│   70% ┼                                                       │
│       └───────────────────────────────────────                │
│        J F M A M J J A S O N D                                │
└───────────────────────────────────────────────────────────────┘

┌──────────────────────┬────────────────────────────────────────┐
│  Tenant Distribution │    Top 5 Properties by Performance     │
├──────────────────────┼────────────────────────────────────────┤
│  Excellent    30%    │  1. Kilimani Court        95%/92%      │
│  Good         43%    │  2. Westlands Apts        90%/85%      │
│  Struggling   18%    │  3. Riverside Towers      88%/88%      │
│  Problematic   8%    │  4. Karen Villas          85%/80%      │
│                      │  5. South B Towers        80%/78%      │
└──────────────────────┴────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                        Action Items (5)                        │
├───────────────────────────────────────────────────────────────┤
│  🔴 Address 3 problematic tenants in South B                  │
│  🔴 Fill 2 vacant units (avg 45 days vacant)                  │
│  🟡 Review rent increase for 8 upcoming renewals              │
│  🟡 Implement auto-payment for 15 late-paying tenants         │
│  🟢 Schedule Q4 tenant satisfaction survey                    │
└───────────────────────────────────────────────────────────────┘
```

---

## 🎯 8. Success Metrics

### Report Success Criteria

```
✓ Reports generated in < 5 seconds
✓ 100% data accuracy
✓ Real-time data (< 1 hour lag)
✓ Mobile-friendly visualization
✓ Export capabilities (PDF, Excel, CSV)
✓ Automated distribution via email
✓ User-friendly interface (non-technical)
✓ Customizable date ranges
✓ Drill-down capabilities
✓ Historical comparisons available
```

---

## 📚 9. Documentation Requirements

### User Documentation

- Report interpretation guide
- KPI definitions glossary
- How to export reports
- Troubleshooting guide
- Best practices for data analysis

### Technical Documentation

- Database schema documentation
- API endpoint specifications
- Calculation formulas
- Data pipeline architecture
- Deployment procedures

---

## 🔮 10. Future Enhancements

### Advanced Features (Future Phases)

```
Phase 5: Machine Learning
- Predict tenant payment behavior
- Forecast optimal rent pricing
- Identify early churn signals
- Recommend tenant retention strategies

Phase 6: Integration
- Accounting software integration
- Banking API for payment tracking
- SMS/Email notification system
- Mobile app for landlords

Phase 7: Benchmarking
- Industry comparisons
- Geographic market analysis
- Competitive property analysis
- Regional pricing insights
```

---

## 📝 Conclusion

This comprehensive system will provide:
✅ Complete visibility into property performance
✅ Data-driven decision making
✅ Early warning systems for problems
✅ Optimization opportunities identification
✅ Tenant relationship management insights
✅ Financial health monitoring
✅ Portfolio-wide analytics

**Next Steps:** Choose specific reports to implement first based on priority and begin development.
