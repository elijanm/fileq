from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import calendar
from plugins.pms.accounting.ledger import Ledger
from core.MongoORJSONResponse import PyObjectId
from plugins.pms.models.ledger_entry import Invoice,InvoiceLineItem,InvoiceStatus
class LeaseStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SIGNED = "signed"
    EXPIRING = "expiring"
    EXPIRED = "expired"
    COMPLETED = "completed"


class TicketStatus(str, Enum):
    OPEN = "open"
    PENDING_INPUT = "pending_input"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CLOSED = "closed"


class TaskStatus(str, Enum):
    PENDING = "pending"
    AWAITING_INPUT = "awaiting_input"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CLOSED = "closed"





class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TicketCategory(str, Enum):
    INVOICE_PREP = "invoice_preparation"
    UTILITY_READING = "utility_reading"
    MAINTENANCE = "maintenance"
    GENERAL = "general"



class PaymentAllocationRule(BaseModel):
    """Rule for allocating payments to old invoices"""
    source_invoice_id: str
    billing_period: str
    amount: float
    priority: int = 1  # Lower number = higher priority


class ConsolidationInfo(BaseModel):
    """Information about invoice consolidation"""
    consolidated_into_invoice_id: str
    consolidated_date: datetime
    consolidated_billing_period: str
    balance_at_consolidation: float
    original_balance: float
    payments_after_consolidation: List[Dict] = Field(default_factory=list)


class UtilityUsageRecord(BaseModel):
    utility_name: str
    previous_reading: float
    current_reading: float
    usage: float
    rate: float
    amount: float
    reading_date: str
    unit_of_measure: str





class Task(BaseModel):
    """Task within a ticket"""
    id: str = Field(default_factory=lambda: str(ObjectId()))
    title: str
    description: str
    status: TaskStatus
    priority: TicketPriority = TicketPriority.MEDIUM
    assigned_to: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class Ticket(BaseModel):
    """Ticket model"""
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority = TicketPriority.MEDIUM
    category: TicketCategory = TicketCategory.INVOICE_PREP
    assigned_to: Optional[str] = None
    created_by: str
    tasks: List[Task] = Field(default_factory=list)
    comments: List[Dict] = Field(default_factory=list)
    metadata: Dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    
    model_config = {
        "populate_by_name":True,
        "json_encoders": {
            ObjectId: str,
            PyObjectId: str,
        }
    }
    


class Notification(BaseModel):
    id: str
    recipient_type: str
    recipient_id: str
    notification_type: NotificationType
    email: Optional[str]
    phone: Optional[str]
    subject: str
    message: str
    metadata: Dict
    created_at: datetime
    sent_at: Optional[datetime] = None
    status: str


class Payment(BaseModel):
    """Payment record"""
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    tenant_id: str
    property_id: str
    amount: float
    payment_date: datetime
    payment_method: str  # mpesa, bank, cash, etc
    reference: str
    allocations: List[Dict] = Field(default_factory=list)
    meta: Dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True


class AsyncLeaseInvoiceManager:
    """
    Comprehensive async lease and invoice management system.
    
    Features:
    - Previous balance consolidation
    - Overpayment credit handling
    - Payment allocation to old invoices
    - Multiple consolidations support
    - Partial payment tracking
    - Complete audit trail
    """
    
    def __init__(
        self, 
        db_connection: AsyncIOMotorClient, 
        database_name: str,
        expiration_threshold_months: int = 2
    ):
        self.client = db_connection
        self.db = self.client[database_name]
        self.expiration_threshold_months = expiration_threshold_months
        self.current_date = datetime.now(timezone.utc)
        
    async def get_tenant_overpayment(self, tenant_id: str) -> float:
        """Get tenant's current overpayment/credit balance."""
        tenant = await self.db.property_tenants.find_one({"_id": ObjectId(tenant_id)})
        if tenant:
            return tenant.get("credit_balance", 0.0)
        return 0.0
    
    async def get_tenant_previous_balance(
        self, 
        tenant_id: str, 
        current_billing_month: str,
        method: str = "sum"
    ) -> Tuple[float, List[Dict]]:
        """
        Get tenant's previous unpaid balance.
        Excludes already consolidated invoices.
        """
        year, month = map(int, current_billing_month.split("-"))
        current_date = datetime(year, month, 1, tzinfo=timezone.utc)
        
        # Exclude consolidated, paid, and cancelled invoices
        cursor = self.db.property_invoices.find({
            "tenant_id": ObjectId(tenant_id),
            "balance_amount": {"$gt": 0},
            "date_issued": {"$lt": current_date},
            "status": {"$nin": [
                InvoiceStatus.CONSOLIDATED.value, 
                InvoiceStatus.PAID.value, 
                InvoiceStatus.CANCELLED.value
            ]},
            "balance_forwarded": {"$ne": True}  # Not already forwarded
        }).sort("date_issued", 1)
        
        unpaid_invoices = await cursor.to_list(length=None)
        
        
        total_balance = 0.0
        itemized_balances = []
        
        for invoice in unpaid_invoices:
            balance = invoice["balance_amount"]
            total_balance += balance
            
            billing_period = invoice.get("meta", {}).get("billing_period", "Unknown")
            itemized_balances.append({
                "invoice_id": str(invoice["_id"]),
                "billing_period": billing_period,
                "balance_amount": balance,
                "date_issued": invoice["date_issued"],
                "original_total": invoice["total_amount"],
                "total_paid": invoice["total_paid"]
            })
        
        return total_balance, itemized_balances
    
    async def process_all_leases(
        self, 
        billing_month: Optional[str] = None,
        force: bool = False,
        balance_method: str = "sum"
    ) -> Dict:
        """Main entry point - processes all leases and generates invoices."""
        if not billing_month:
            billing_month = self.current_date.strftime("%Y-%m")
            
        results = {
            "billing_period": billing_month,
            "leases_processed": 0,
            "leases_expiring": [],
            "leases_expired": [],
            "invoices_created": [],
            "invoices_regenerated": [],
            "invoices_consolidated": [],
            "tickets_created": [],
            "notifications_queued": [],
            "errors": []
        }
        
        try:
            #ToDo: candidate for cache
            await self._update_lease_statuses(results)
            active_leases_by_property = await self._get_active_leases_by_property()
            
            for property_id, leases in active_leases_by_property.items():
                try:
                    await self._process_property_leases(
                        property_id, 
                        leases, 
                        billing_month, 
                        force,
                        balance_method,
                        results
                    )
                except Exception as e:
                    results["errors"].append({
                        "property_id": property_id,
                        "error": str(e)
                    })
                    
            await self._generate_landlord_summaries(billing_month, results)
            
        except Exception as e:
            results["errors"].append({
                "stage": "main_process",
                "error": str(e)
            })
            
        return results
    
    def _normalize_datetime(self, dt) -> datetime:
        """Normalize datetime to timezone-aware UTC datetime."""
        if isinstance(dt, dict) and "$date" in dt:
            date_value = dt["$date"]
            if isinstance(date_value, str):
                dt = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            elif isinstance(date_value, int):
                dt = datetime.fromtimestamp(date_value / 1000, tz=timezone.utc)
            else:
                dt = date_value
        elif isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        
        if isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        elif isinstance(dt, datetime) and dt.tzinfo != timezone.utc:
            dt = dt.astimezone(timezone.utc)
        
        return dt
    
    async def _update_lease_statuses(self, results: Dict):
        """Check and update lease expiration statuses."""
        cursor = self.db.property_leases.find({
            "status": {"$in": ["active", "signed", "expiring"]}
        })
        
        expiration_threshold = self.current_date + timedelta(
            days=self.expiration_threshold_months * 30
        )
        
        async for lease in cursor:
            lease_id = lease["_id"]
            end_date = lease["lease_terms"]["end_date"]
            end_date = self._normalize_datetime(end_date)
            
            if end_date < self.current_date:
                await self.db.property_leases.update_one(
                    {"_id": lease_id},
                    {
                        "$set": {
                            "status": LeaseStatus.EXPIRED.value,
                            "updated_at": self.current_date
                        }
                    }
                )
                results["leases_expired"].append(str(lease_id))
                await self._queue_expiration_notification(lease, "expired")
                
            elif end_date < expiration_threshold and lease["status"] != "expiring":
                await self.db.property_leases.update_one(
                    {"_id": lease_id},
                    {
                        "$set": {
                            "status": LeaseStatus.EXPIRING.value,
                            "updated_at": self.current_date
                        }
                    }
                )
                results["leases_expiring"].append(str(lease_id))
                await self._queue_expiration_notification(lease, "expiring")

    async def _get_active_leases_by_property(self) -> Dict[str, List[Dict]]:
        """Get all active and signed leases grouped by property."""
        cursor = self.db.property_leases.find({
            "status": {"$in": ["active", "signed"]}
        })
        
        leases_by_property = {}
        async for lease in cursor:
            property_id = lease["property_id"]
            if property_id not in leases_by_property:
                leases_by_property[property_id] = []
            leases_by_property[property_id].append(lease)
        
        return leases_by_property
    
    async def _process_property_leases(
        self, 
        property_id: str,
        leases: List[Dict], 
        billing_month: str,
        force: bool,
        balance_method: str,
        results: Dict
    ):
        """Process all leases for a single property."""
        property_data = await self.db.properties.find_one({"_id": property_id})
        if not property_data:
            raise ValueError(f"Property {property_id} not found")
        
        property_name = property_data["name"]
        utility_tasks = []
        invoices_created_for_property = []
        
        for lease in leases:
            try:
                invoice_result = await self._process_single_lease(
                    lease, 
                    billing_month, 
                    property_data,
                    force,
                    balance_method,
                    results
                )
                
                if invoice_result:
                    invoices_created_for_property.append(invoice_result["invoice_id"])
                    
                    if invoice_result.get("utility_tasks"):
                        utility_tasks.extend(invoice_result["utility_tasks"])
                        
            except Exception as e:
                import traceback
                traceback.print_exception(e)
                results["errors"].append({
                    "lease_id": str(lease.get("_id")),
                    "error": str(e)
                })
        
        if utility_tasks:
            ticket = await self._create_property_ticket(
                property_id,
                property_name,
                billing_month,
                utility_tasks,
                property_data.get("owner_id")
            )
            results["tickets_created"].append(str(ticket.id))
    
    async def _process_single_lease(
        self, 
        lease: Dict, 
        billing_month: str,
        property_data: Dict,
        force: bool,
        balance_method: str,
        results: Dict
    ) -> Optional[Dict]:
        """Process a single lease for invoice generation."""
        lease_id = str(lease["_id"])
        property_id = lease["property_id"]
        tenant_id = str(lease["tenant_id"])
        units_id = lease["units_id"]
        
        # Check if invoice already exis
        existing_invoice = await self.db.property_invoices.find_one({
            "$or": [
                {"lease_id": str(lease_id)},
                {"meta.lease_id": str(lease_id)},
            ],
            "meta.billing_period": billing_month
        })
        
        if existing_invoice and not force:
            raise ValueError(
                f"Invoice already exists for lease {lease_id} in {billing_month}. "
                f"Use force=True to regenerate. {existing_invoice['_id']}"
            )
        
        if existing_invoice and force:
            await self._delete_existing_invoice_and_tickets(
                str(existing_invoice["_id"]), 
                billing_month
            )
            results["invoices_regenerated"].append(str(existing_invoice["_id"]))
        
        # Initialize invoice
        invoice_id = str(ObjectId())
        line_items = []
        
        # Get unit details
        units_info = []
        unit_numbers = []
        
        for unit_id in units_id:
            unit = await self.db.units.find_one({"_id": str(unit_id)})
            if unit:
                unit_number = unit.get("unitNumber", "")
                unit_numbers.append(unit_number)
                units_info.append({
                    "_id": unit["_id"],
                    "unitNumber": unit_number,
                    "unitName": unit.get("unitName", ""),
                    "rentAmount": unit.get("rentAmount", 0)
                })
        
        unit_numbers_str = ", ".join(unit_numbers)
        
        # Calculate due date
        billing_cycle = property_data.get("billing_cycle", {})
        due_day = billing_cycle.get("due_day", 5)
        year, month = map(int, billing_month.split("-"))
        
        try:
            due_date = datetime(year, month, due_day, tzinfo=timezone.utc)
        except ValueError:
            last_day = calendar.monthrange(year, month)[1]
            due_day = min(due_day, last_day)
            due_date = datetime(year, month, due_day, tzinfo=timezone.utc)
        
        # Get tenant's previous balance
        previous_balance, itemized_balances = await self.get_tenant_previous_balance(
            tenant_id, 
            billing_month,
            balance_method
        )
        
        # Get tenant's overpayment
        tenant_overpayment = await self.get_tenant_overpayment(tenant_id)
        
        # Invoice metadata
        invoice_meta = {
            "lease_id": lease_id,
            "billing_period": billing_month,
            "tenant": {
                "full_name": lease["tenant_details"]["full_name"],
                "is_lease_active":True,
                # "email": lease["tenant_details"].get("email"),
                # "phone": lease["tenant_details"].get("phone")
            },
            "property": {
                "name": property_data["name"],
                "location": property_data.get("location", "")
            },
            "units": units_info,
            "unit_numbers": unit_numbers,
            "unit_numbers_str":unit_numbers_str,
            "billing_cycle": billing_cycle,
            "utilities_usage": {},
            "previous_balance_method": balance_method,
            "itemized_balances": itemized_balances if balance_method == "itemized" else [],
            "tenant_overpayment_applied": tenant_overpayment,
            "payment_allocation_rules": []
        }
        
        # Add previous balance line items
        if previous_balance > 0:
            if balance_method == "sum":
                line_items.append(InvoiceLineItem(
                    id=str(ObjectId()),
                    description=f"Balance Brought Forward (Previous Outstanding)",
                    amount=previous_balance,
                    category="balance_brought_forward",
                    usage_units=None,
                    meta={
                        "total_previous_balance": previous_balance,
                        "invoices_count": len(itemized_balances)
                    }
                ))
            else:
                for item in itemized_balances:
                    line_items.append(InvoiceLineItem(
                        id=str(ObjectId()),
                        description=f"Balance from {item['billing_period']}",
                        amount=item["balance_amount"],
                        category="balance_brought_forward",
                        usage_units=None,
                        meta={
                            "original_invoice_id": item["invoice_id"],
                            "billing_period": item["billing_period"],
                            "date_issued": item["date_issued"].isoformat() if isinstance(item["date_issued"], datetime) else item["date_issued"]
                        }
                    ))
            
            # Add payment allocation rules
            for i, item in enumerate(itemized_balances):
                invoice_meta["payment_allocation_rules"].append({
                    "source_invoice_id": item["invoice_id"],
                    "billing_period": item["billing_period"],
                    "amount": item["balance_amount"],
                    "priority": i + 1  # Older invoices get higher priority
                })
        
        # Add current month's rent
        rent_amount = lease["lease_terms"]["rent_amount"]
        line_items.append(InvoiceLineItem(
            id=str(ObjectId()),
            description=f"{unit_numbers_str}, Monthly Rent - {billing_month}",
            amount=rent_amount,
            category="rent",
            usage_units=None,
            meta={
                "billing_period": billing_month,
                "unit_numbers": unit_numbers
            }
        ))
        
        # Process utilities
        metered_utilities = []
        utility_tasks_data = []
        
        for utility in lease.get("utilities", []):
            if utility.get("billingBasis") == "metered":
                metered_utilities.append(utility)
                
                previous_reading = await self._get_previous_utility_reading(
                    str(lease["_id"]), 
                    utility["name"],
                    billing_month
                )
                
                task_data = {
                    "utility": utility,
                    "lease_id": lease_id,
                    "tenant_name": lease["tenant_details"]["full_name"],
                    "tenant_id": tenant_id,
                    "invoice_id": invoice_id,
                    "billing_period":billing_month,
                    "previous_reading": previous_reading,
                    "units_id": units_id,
                    "unit_numbers": unit_numbers,
                    "unit_numbers_str": unit_numbers_str
                }
                utility_tasks_data.append(task_data)
                
            elif utility.get("billingBasis") == "monthly":
                line_items.append(InvoiceLineItem(
                    id=str(ObjectId()),
                    description=f"{unit_numbers_str}, {utility['name']} - {billing_month}",
                    amount=utility.get("rate", 0),
                    category="utility",
                    usage_units=None,
                    meta={
                        "utility_type": "fixed",
                        "billing_period": billing_month,
                        "unit_numbers": unit_numbers
                    }
                ))
        
        # Calculate subtotal before overpayment
        subtotal = sum(item.amount for item in line_items)
        
        # Apply tenant overpayment/credit
        overpayment_applied = 0.0
        remaining_credit = tenant_overpayment
        
        if tenant_overpayment > 0:
            overpayment_applied = min(tenant_overpayment, subtotal)
            remaining_credit = tenant_overpayment - overpayment_applied
            
            line_items.append(InvoiceLineItem(
                id=str(ObjectId()),
                description=f"Overpayment Credit Applied",
                amount=-overpayment_applied,
                category="overpayment_credit",
                usage_units=None,
                meta={
                    "tenant_credit_balance": tenant_overpayment,
                    "credit_applied": overpayment_applied,
                    "remaining_credit": remaining_credit
                }
            ))
            
            # Update tenant's credit balance
            await self.db.property_tenants.update_one(
                {"_id": ObjectId(tenant_id)},
                {
                    "$set": {
                        "credit_balance": remaining_credit,
                        "last_credit_update": self.current_date
                    }
                }
            )
        
        # Determine invoice status
        if metered_utilities:
            invoice_status = InvoiceStatus.PENDING_UTILITIES
            invoice_meta["pending_utilities"] = len(metered_utilities)
        else:
            invoice_status = InvoiceStatus.READY
        
        # Calculate final totals
        total_amount = sum(item.amount for item in line_items)
        
        # Handle overpayment exceeding total
        overpaid_amount = 0.0
        balance_amount = total_amount
        
        if total_amount < 0:
            overpaid_amount = abs(total_amount)
            balance_amount = 0.0
            total_amount = 0.0
            
            # Add excess to tenant credit
            await self.db.property_tenants.update_one(
                {"_id": ObjectId(tenant_id)},
                {
                    "$inc": {"credit_balance": overpaid_amount}
                }
            )
        
        # Create invoice
        invoice = Invoice(
            id=invoice_id,
            property_id=property_id,
            tenant_id=tenant_id,
            date_issued=self.current_date,
            lease_id=lease_id,
            due_date=due_date,
            units_id=units_id,
            line_items=line_items,
            total_amount=total_amount,
            total_paid=0.0,
            effective_paid=0.0,
            overpaid_amount=overpaid_amount,
            balance_amount=balance_amount,
            status=invoice_status,
            balance_forwarded=False,
            meta=invoice_meta
        )
        
        # Save invoice
        await self._save_invoice(invoice)
        results["invoices_created"].append(invoice_id)
        results["leases_processed"] += 1
        
        # Consolidate previous invoices
        if previous_balance > 0 and itemized_balances:
            consolidated_ids = await self._consolidate_previous_invoices(
                itemized_balances,
                invoice_id,
                billing_month
            )
            results["invoices_consolidated"].extend(consolidated_ids)
        
        # If ready, finalize and notify
        if invoice_status == InvoiceStatus.READY:
            await self._finalize_and_notify_invoice(invoice, property_data, results)
        
        return {
            "invoice_id": invoice_id,
            "utility_tasks": utility_tasks_data if metered_utilities else None
        }
    
    async def _consolidate_previous_invoices(
        self,
        itemized_balances: List[Dict],
        new_invoice_id: str,
        billing_month: str
    ) -> List[str]:
        """
        Mark previous invoices as consolidated.
        Returns list of consolidated invoice IDs.
        """
        consolidated_ids = []
        
        for item in itemized_balances:
            old_invoice_id = item["invoice_id"]
            balance_amount = item["balance_amount"]
            
            consolidation_info = {
                "consolidated_into_invoice_id": new_invoice_id,
                "consolidated_date": self.current_date,
                "consolidated_billing_period": billing_month,
                "balance_at_consolidation": balance_amount,
                "original_balance": item["balance_amount"],
                "original_total": item["original_total"],
                "total_paid_before_consolidation": item["total_paid"],
                "payments_after_consolidation": []
            }
            
            # Update old invoice
            await self.db.property_invoices.update_one(
                {"_id": ObjectId(old_invoice_id)},
                {
                    "$set": {
                        "status": InvoiceStatus.CONSOLIDATED.value,
                        "balance_forwarded": True,
                        "meta.consolidation": consolidation_info
                    }
                }
            )
            
            consolidated_ids.append(old_invoice_id)
        
        return consolidated_ids
    
    async def _delete_existing_invoice_and_tickets(
        self, 
        invoice_id: str, 
        billing_month: str
    ):
        """Delete existing invoice and related tickets."""
        # Get invoice to check if it has consolidated others
        invoice = await self.db.property_invoices.find_one({"_id": ObjectId(invoice_id)})
        
        if invoice:
            # Restore consolidated invoices
            payment_rules = invoice.get("meta", {}).get("payment_allocation_rules", [])
            for rule in payment_rules:
                source_invoice_id = rule.get("source_invoice_id")
                if source_invoice_id:
                    await self.db.property_invoices.update_one(
                        {"_id": ObjectId(source_invoice_id)},
                        {
                            "$set": {
                                "status": InvoiceStatus.OVERDUE.value,
                                "balance_forwarded": False
                            },
                            "$unset": {
                                "meta.consolidation": ""
                            }
                        }
                    )
        
        # Delete invoice , tickets and ledger entries
        await self.db.property_invoices.delete_one({"_id": ObjectId(invoice_id)})
        await self.db.property_tickets.delete_many({
            "metadata.billing_month": billing_month,
            "tasks.metadata.invoice_id": invoice_id
        })
        await self.db.property_ledger_entries.delete_many({
            "invoice_id":  ObjectId(invoice_id)
        })
    
    async def _create_property_ticket(
        self,
        property_id: str,
        property_name: str,
        billing_month: str,
        utility_tasks_data: List[Dict],
        created_by: str
    ) -> Ticket:
        """Create ONE ticket for a property with multiple utility reading tasks."""
        ticket_id = str(ObjectId())
        
        year, month = map(int, billing_month.split("-"))
        month_name = calendar.month_name[month]
        
        tasks = []
        for task_data in utility_tasks_data:
            utility = task_data["utility"]
            unit_numbers_str = task_data["unit_numbers_str"]
            
            task = Task(
                id=str(ObjectId()),
                title=f"{utility['name']} Reading - {unit_numbers_str} - {task_data['tenant_name']}",
                description=f"Submit {utility['name']} meter reading for {unit_numbers_str} ({task_data['tenant_name']}) - {month_name} {year}",
                status=TaskStatus.AWAITING_INPUT,
                priority=TicketPriority.MEDIUM,
                metadata={
                    "utility_name": utility["name"],
                    "unit_of_measure": utility.get("unitOfMeasure", ""),
                    "rate": utility.get("rate", 0),
                    "previous_reading": task_data["previous_reading"],
                    "billing_month": billing_month,
                    "lease_id": task_data["lease_id"],
                    "tenant_id": task_data["tenant_id"],
                    "tenant_name": task_data["tenant_name"],
                    "invoice_id": task_data["invoice_id"],
                    "units_id": task_data["units_id"],
                    "unit_numbers": task_data["unit_numbers"],
                    "unit_numbers_str": unit_numbers_str,
                    "requires_deposit": utility.get("isDepositRequired", False),
                    "deposit_amount": utility.get("depositAmount", 0),
                    "is_refundable": utility.get("isRefundable", False)
                }
            )
            tasks.append(task)
        
        ticket = Ticket(
            id=ticket_id,
            title=f"Invoice Preparation - {property_name} - {month_name} {year}",
            description=f"Utility meter readings required for invoice generation at {property_name} for {month_name} {year}. Total {len(tasks)} readings needed.",
            status=TicketStatus.PENDING_INPUT,
            priority=TicketPriority.MEDIUM,
            category=TicketCategory.INVOICE_PREP,
            created_by=created_by or "system",
            tasks=tasks,
            metadata={
                "property_id": property_id,
                "property_name": property_name,
                "billing_month": billing_month,
                "total_tasks": len(tasks),
                "completed_tasks": 0
            }
        )
        
        await self._save_ticket(ticket)
        return ticket
    
    async def process_utility_reading(
        self, 
        task_id: str, 
        current_reading: float,
        reading_date: Optional[str] = None
    ) -> Dict:
        """Process a utility meter reading input."""
        result = {
            "success": False,
            "task_id": task_id,
            "invoice_updated": False,
            "ticket_closed": False,
            "notifications_sent": False,
            "error": None
        }
        
        try:
            ticket = await self.db.property_tickets.find_one({"tasks.id": task_id})
            if not ticket:
                raise ValueError(f"Task {task_id} not found in any ticket")
            
            task = next((t for t in ticket["tasks"] if t["id"] == task_id), None)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            previous_reading = task["metadata"]["previous_reading"]
            if current_reading < previous_reading:
                raise ValueError(
                    f"Current reading ({current_reading}) cannot be less than "
                    f"previous reading ({previous_reading})"
                )
            
            usage = current_reading - previous_reading
            rate = task["metadata"]["rate"]
            amount = usage * rate
            unit_of_measure = task["metadata"]["unit_of_measure"]
            
            usage_record = UtilityUsageRecord(
                utility_name=task["metadata"]["utility_name"],
                previous_reading=previous_reading,
                current_reading=current_reading,
                usage=usage,
                rate=rate,
                amount=amount,
                reading_date=reading_date or self.current_date.isoformat(),
                unit_of_measure=unit_of_measure
            )
            
            await self.db.property_tickets.update_one(
                {"_id": ticket["_id"], "tasks.id": task_id},
                {
                    "$set": {
                        "tasks.$.status": TaskStatus.COMPLETED.value,
                        "tasks.$.completed_at": self.current_date,
                        "tasks.$.updated_at": self.current_date,
                        "tasks.$.metadata.current_reading": current_reading,
                        "tasks.$.metadata.usage": usage,
                        "tasks.$.metadata.amount": amount,
                        "tasks.$.metadata.reading_date": usage_record.reading_date,
                        "updated_at": self.current_date
                    }
                }
            )
            
            invoice_id = task["metadata"]["invoice_id"]
            await self._add_utility_to_invoice(invoice_id, usage_record, task["metadata"])
            result["invoice_updated"] = True
            
            ticket = await self.db.property_tickets.find_one({"_id": ticket["_id"]})
            completed_tasks = sum(1 for t in ticket["tasks"] if t["status"] == TaskStatus.COMPLETED.value)
            total_tasks = len(ticket["tasks"])
            
            await self.db.property_tickets.update_one(
                {"_id": ticket["_id"]},
                {
                    "$set": {
                        "metadata.completed_tasks": completed_tasks,
                        "updated_at": self.current_date
                    }
                }
            )
            
            all_completed = (completed_tasks == total_tasks)
            
            if all_completed:
                await self.db.property_tickets.update_one(
                    {"_id": ticket["_id"]},
                    {
                        "$set": {
                            "status": TicketStatus.CLOSED.value,
                            "closed_at": self.current_date,
                            "updated_at": self.current_date
                        }
                    }
                )
                result["ticket_closed"] = True
                
                unique_invoice_ids = set()
                for t in ticket["tasks"]:
                    if "invoice_id" in t["metadata"]:
                        unique_invoice_ids.add(t["metadata"]["invoice_id"])
                
                property_data = await self.db.properties.find_one(
                    {"_id": ticket["metadata"]["property_id"]}
                )
                
                for inv_id in unique_invoice_ids:
                    invoice = await self.db.property_invoices.find_one({"_id": inv_id})
                    if invoice:
                        await self._finalize_invoice(inv_id)
                        await self._send_invoice_notification(invoice, property_data)
                
                result["notifications_sent"] = True
            
            result["success"] = True
            result["usage_record"] = usage_record.model_dump()
            result["progress"] = {
                "completed_tasks": completed_tasks,
                "total_tasks": total_tasks,
                "percentage": round((completed_tasks / total_tasks) * 100, 2)
            }
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def _add_utility_to_invoice(
        self, 
        invoice_id: str, 
        usage_record: UtilityUsageRecord,
        task_metadata: Dict
    ):
        """Add utility charge to invoice as a line item."""
        unit_numbers_str = task_metadata.get("unit_numbers_str", "")
        unit_numbers = task_metadata.get("unit_numbers", [])
        
        utility_line_item = {
            "_id": str(ObjectId()),
            "description": f"{unit_numbers_str}, {usage_record.utility_name} Usage - {usage_record.usage} {usage_record.unit_of_measure}",
            "amount": usage_record.amount,
            "category": "utility",
            "usage_units": usage_record.usage,
            "rate": usage_record.rate,
            "meta": {
                "utility_type": "metered",
                "utility_name": usage_record.utility_name,
                "previous_reading": usage_record.previous_reading,
                "current_reading": usage_record.current_reading,
                "reading_date": usage_record.reading_date,
                "unit_of_measure": usage_record.unit_of_measure,
                "unit_numbers": unit_numbers
            }
        }
        
        invoice = await self.db.property_invoices.find_one({"_id": invoice_id})
        new_total = invoice["total_amount"] + usage_record.amount
        new_balance = new_total - invoice["total_paid"]
        
        usage_key = f"{usage_record.utility_name.lower().replace(' ', '_')}_usage"
        
        await self.db.property_invoices.update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$push": {"line_items": utility_line_item},
                "$set": {
                    "total_amount": new_total,
                    "balance_amount": new_balance,
                    f"meta.utilities_usage.{usage_key}": {
                        "reading_date": usage_record.reading_date,
                        "previous_reading": usage_record.previous_reading,
                        "current_reading": usage_record.current_reading,
                        "usage": usage_record.usage,
                        "rate": usage_record.rate,
                        "amount": usage_record.amount,
                        "unit": usage_record.unit_of_measure,
                        "unit_numbers": unit_numbers
                    }
                }
            }
        )
    
    async def process_payment(
        self,
        tenant_id: str,
        amount: float,
        payment_method: str,
        reference: str,
        payment_date: Optional[datetime] = None,
        target_invoice_id: Optional[str] = None
    ) -> Dict:
        """
        Process a payment from tenant.
        Allocates to old consolidated invoices first, then current invoice.
        
        Args:
            tenant_id: Tenant ID
            amount: Payment amount
            payment_method: Payment method (mpesa, bank, cash, etc)
            reference: Payment reference
            payment_date: Date of payment (defaults to now)
            target_invoice_id: Specific invoice to pay (optional)
            
        Returns:
            Payment allocation details
        """
        if payment_date is None:
            payment_date = self.current_date
        
        result = {
            "success": False,
            "payment_id": None,
            "total_amount": amount,
            "allocations": [],
            "remaining_amount": amount,
            "overpayment_credited": 0.0,
            "error": None
        }
        
        try:
            # Get tenant info
            tenant = await self.db.property_tenants.find_one({"_id": ObjectId(tenant_id)})
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            property_id = tenant.get("property_id")
            
            # If target invoice specified, pay only that invoice
            if target_invoice_id:
                invoice = await self.db.property_invoices.find_one({"_id": target_invoice_id})
                if not invoice:
                    raise ValueError(f"Invoice {target_invoice_id} not found")
                
                allocation_result = await self._allocate_payment_to_invoice(
                    target_invoice_id,
                    amount,
                    payment_date
                )
                
                result["allocations"] = allocation_result["allocations"]
                result["remaining_amount"] = allocation_result["remaining_amount"]
                
            else:
                # Auto-allocate: Find invoices with balance, prioritize old ones
                cursor = self.db.property_invoices.find({
                    "tenant_id": ObjectId(tenant_id),
                    "balance_amount": {"$gt": 0},
                    "status": {"$nin": [InvoiceStatus.CANCELLED.value]}
                }).sort("date_issued", 1)  # Oldest first
                
                invoices_with_balance = await cursor.to_list(length=None)
                
                remaining = amount
                for invoice in invoices_with_balance:
                    if remaining <= 0:
                        break
                    
                    invoice_id = str(invoice["_id"])
                    allocation_result = await self._allocate_payment_to_invoice(
                        invoice_id,
                        remaining,
                        payment_date
                    )
                    
                    result["allocations"].extend(allocation_result["allocations"])
                    remaining = allocation_result["remaining_amount"]
                
                result["remaining_amount"] = remaining
            
            # Handle overpayment - add to tenant credit
            if result["remaining_amount"] > 0:
                await self.db.property_tenants.update_one(
                    {"_id": ObjectId(tenant_id)},
                    {
                        "$inc": {"credit_balance": result["remaining_amount"]},
                        "$set": {"last_credit_update": self.current_date}
                    }
                )
                result["overpayment_credited"] = result["remaining_amount"]
            
            # Create payment record
            payment = Payment(
                id=str(ObjectId()),
                tenant_id=tenant_id,
                property_id=property_id,
                amount=amount,
                payment_date=payment_date,
                payment_method=payment_method,
                reference=reference,
                allocations=result["allocations"],
                meta={
                    "overpayment_credited": result["overpayment_credited"],
                    "processed_at": self.current_date
                }
            )
            
            await self._save_payment(payment)
            result["payment_id"] = payment.id
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def _allocate_payment_to_invoice(
        self,
        invoice_id: str,
        payment_amount: float,
        payment_date: datetime
    ) -> Dict:
        """
        Allocate payment to an invoice and its consolidated sources.
        
        Returns:
            Dict with allocations and remaining amount
        """
        invoice = await self.db.property_invoices.find_one({"_id": invoice_id})
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        allocations = []
        remaining = payment_amount
        
        # Get payment allocation rules (for consolidated invoices)
        allocation_rules = invoice.get("meta", {}).get("payment_allocation_rules", [])
        allocation_rules.sort(key=lambda x: x.get("priority", 999))
        
        # First, allocate to old consolidated invoices
        for rule in allocation_rules:
            if remaining <= 0:
                break
            
            source_invoice_id = rule["source_invoice_id"]
            source_invoice = await self.db.property_invoices.find_one({"_id": source_invoice_id})
            
            if not source_invoice:
                continue
            
            # How much does this old invoice need?
            needed = source_invoice["balance_amount"]
            amount_to_allocate = min(remaining, needed)
            
            if amount_to_allocate > 0:
                # Update old consolidated invoice
                new_paid = source_invoice["total_paid"] + amount_to_allocate
                new_balance = source_invoice["total_amount"] - new_paid
                
                new_status = InvoiceStatus.PAID.value if new_balance <= 0 else InvoiceStatus.PARTIALLY_PAID.value
                
                await self.db.property_invoices.update_one(
                    {"_id": ObjectId(source_invoice_id)},
                    {
                        "$set": {
                            "total_paid": new_paid,
                            "effective_paid": new_paid,
                            "balance_amount": max(0, new_balance),
                            "status": new_status
                        },
                        "$push": {
                            "meta.consolidation.payments_after_consolidation": {
                                "amount": amount_to_allocate,
                                "date": payment_date,
                                "allocated_from_invoice": invoice_id,
                                "reference": f"Payment via {invoice['meta']['billing_period']}"
                            }
                        }
                    }
                )
                
                allocations.append({
                    "invoice_id": source_invoice_id,
                    "billing_period": rule["billing_period"],
                    "amount": amount_to_allocate,
                    "invoice_status": new_status
                })
                
                remaining -= amount_to_allocate
        
        # Then allocate remaining to current invoice
        if remaining > 0:
            needed = invoice["balance_amount"]
            amount_to_allocate = min(remaining, needed)
            
            if amount_to_allocate > 0:
                new_paid = invoice["total_paid"] + amount_to_allocate
                new_balance = invoice["total_amount"] - new_paid
                
                new_status = InvoiceStatus.PAID.value if new_balance <= 0 else InvoiceStatus.PARTIALLY_PAID.value
                
                await self.db.property_invoices.update_one(
                    {"_id": ObjectId(invoice_id)},
                    {
                        "$set": {
                            "total_paid": new_paid,
                            "effective_paid": new_paid,
                            "balance_amount": max(0, new_balance),
                            "status": new_status
                        }
                    }
                )
                
                allocations.append({
                    "invoice_id": invoice_id,
                    "billing_period": invoice["meta"]["billing_period"],
                    "amount": amount_to_allocate,
                    "invoice_status": new_status
                })
                
                remaining -= amount_to_allocate
        
        return {
            "allocations": allocations,
            "remaining_amount": remaining
        }
    
    async def _finalize_invoice(self, invoice_id: str):
        """Mark invoice as ready."""
        await self.db.property_invoices.update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$set": {
                    "status": InvoiceStatus.READY.value
                },
                "$unset": {
                    "meta.pending_utilities": ""
                }
            }
        )
    
    async def _finalize_and_notify_invoice(
        self, 
        invoice: Invoice, 
        property_data: Dict,
        results: Dict
    ):
        """Finalize invoice and send notification."""
        await self._finalize_invoice(invoice.id)
        updated_invoice = await self.db.property_invoices.find_one({"_id": invoice.id})
        await self._send_invoice_notification(updated_invoice, property_data)
        results["notifications_queued"].append({
            "type": "tenant_invoice",
            "invoice_id": invoice.id,
            "tenant_id": invoice.tenant_id
        })
    
    async def _send_invoice_notification(self, invoice: Dict, property_data: Dict):
        """Send invoice notification to tenant."""
        tenant = await self.db.property_tenants.find_one({"_id": ObjectId(invoice["tenant_id"])})
        if not tenant:
            print(f"Tenant {invoice['tenant_id']} not found")
            return
        
        payment_methods = self._build_payment_methods(property_data)
        breakdown = self._build_invoice_breakdown(invoice)
        
        subject = f"Invoice for {invoice['meta']['billing_period']} - {property_data['name']}"
        message = self._build_tenant_invoice_message(
            invoice, tenant, property_data, breakdown, payment_methods
        )
        
        notification = Notification(
            id=str(ObjectId()),
            recipient_type="tenant",
            recipient_id=str(tenant["_id"]),
            notification_type=self._get_notification_type(property_data),
            email=tenant.get("email"),
            phone=tenant.get("phone"),
            subject=subject,
            message=message,
            metadata={
                "invoice_id": str(invoice["_id"]),
                "billing_period": invoice['meta']['billing_period'],
                "total_amount": invoice["total_amount"],
                "balance_amount": invoice["balance_amount"],
                "due_date": invoice["due_date"].isoformat() if invoice.get("due_date") else None
            },
            created_at=self.current_date,
            status="pending"
        )
        
        await self._save_notification(notification)
    
    async def _generate_landlord_summaries(self, billing_month: str, results: Dict):
        """Generate and send landlord summary notifications."""
        cursor = self.db.properties.find({})
        
        async for property_data in cursor:
            property_id = property_data["_id"]
            
            invoice_cursor = self.db.property_invoices.find({
                "property_id": property_id,
                "meta.billing_period": billing_month
            })
            invoices = await invoice_cursor.to_list(length=None)
            
            if not invoices:
                continue
            
            summary = {
                "property_name": property_data["name"],
                "billing_period": billing_month,
                "total_invoices": len(invoices),
                "total_amount": sum(inv["total_amount"] for inv in invoices),
                "total_collected": sum(inv["total_paid"] for inv in invoices),
                "total_outstanding": sum(inv["balance_amount"] for inv in invoices),
                "invoices_ready": len([inv for inv in invoices if inv["status"] == "ready"]),
                "invoices_pending": len([inv for inv in invoices if inv["status"] == "pending_utilities"]),
                "invoices_paid": len([inv for inv in invoices if inv["status"] == "paid"]),
                "invoices_consolidated": len(results.get("invoices_consolidated", [])),
                "pending_tickets": []
            }
            
            ticket_cursor = self.db.property_tickets.find({
                "metadata.property_id": property_id,
                "status": {"$in": ["pending_input", "in_progress", "open"]},
                "metadata.billing_month": billing_month
            })
            
            async for ticket in ticket_cursor:
                pending_tasks = [t for t in ticket["tasks"] if t["status"] != TaskStatus.COMPLETED.value]
                if pending_tasks:
                    summary["pending_tickets"].append({
                        "ticket_id": str(ticket["_id"]),
                        "ticket_title": ticket["title"],
                        "total_tasks": len(ticket["tasks"]),
                        "completed_tasks": ticket["metadata"].get("completed_tasks", 0),
                        "pending_tasks": len(pending_tasks)
                    })
            
            subject = f"Invoice Summary - {billing_month} - {property_data['name']}"
            message = self._build_landlord_summary_message(summary, property_data)
            
            notification = Notification(
                id=str(ObjectId()),
                recipient_type="landlord",
                recipient_id=property_data["owner_id"],
                notification_type=self._get_notification_type(property_data),
                email=property_data.get("email"),
                phone=property_data.get("phone"),
                subject=subject,
                message=message,
                metadata={
                    "property_id": str(property_id),
                    "billing_period": billing_month,
                    "summary": summary
                },
                created_at=self.current_date,
                status="pending"
            )
            
            await self._save_notification(notification)
            results["notifications_queued"].append({
                "type": "landlord_summary",
                "property_id": str(property_id)
            })
    
    async def _get_previous_utility_reading(
        self, 
        lease_id: str, 
        utility_name: str,
        current_billing_month: str
    ) -> float:
        """Get previous utility reading from last invoice."""
        year, month = map(int, current_billing_month.split("-"))
        
        if month == 1:
            prev_month = 12
            prev_year = year - 1
        else:
            prev_month = month - 1
            prev_year = year
        
        prev_billing_month = f"{prev_year}-{prev_month:02d}"
        
        prev_invoice = await self.db.property_invoices.find_one({
            "$or": [
                {"lease_id": str(lease_id)},
                {"meta.lease_id": str(lease_id)},
            ],
            "meta.billing_period": prev_billing_month
        })
        
        if prev_invoice:
            utilities = [l for l in prev_invoice.get("line_items", []) if utility_name.lower() in l.get("utility_name","").lower() ]
            if len(utilities)>0:
                li_meta=utilities[0].get("meta",{})
                return li_meta.get("current_reading", 0.0)
                
            # usage_key = f"{utility_name.lower().replace(' ', '_')}_usage"
            # usage_data = prev_invoice.get("meta", {}).get("utilities_usage", {}).get(usage_key)
            # if usage_data:
            #     return usage_data.get("current_reading", 0.0)
        
        return 0.0
    
    def _build_payment_methods(self, property_data: Dict) -> List[Dict]:
        """Build list of available payment methods."""
        methods = []
        integrations = property_data.get("integrations", {})
        payments = integrations.get("payments", {})
        
        paybill = payments.get("paybillNo", {})
        if paybill.get("enabled"):
            methods.append({
                "type": "mpesa_paybill",
                "name": "M-Pesa Paybill",
                "details": {
                    "business_number": paybill.get("paybill_no"),
                    "account_pattern": paybill.get("account")
                }
            })
        
        till = payments.get("tillNo", {})
        if till.get("enabled"):
            methods.append({
                "type": "mpesa_till",
                "name": "M-Pesa Till",
                "details": {
                    "till_number": till.get("till_no")
                }
            })
        
        bank = payments.get("bankInfo", {})
        if bank.get("enabled"):
            methods.append({
                "type": "bank_transfer",
                "name": "Bank Transfer",
                "details": {
                    "account_name": bank.get("account_name"),
                    "account_number": bank.get("account_no"),
                    "branch": bank.get("branch"),
                    "reference_pattern": bank.get("ref")
                }
            })
        
        return methods
    
    def _build_invoice_breakdown(self, invoice: Dict) -> str:
        """Build detailed invoice breakdown for tenant."""
        lines = []
        lines.append("INVOICE BREAKDOWN")
        lines.append("=" * 50)
        lines.append(f"Invoice #: {invoice['_id']}")
        lines.append(f"Date Issued: {invoice['date_issued'].strftime('%Y-%m-%d')}")
        lines.append(f"Due Date: {invoice['due_date'].strftime('%Y-%m-%d')}")
        lines.append("")
        lines.append("Line Items:")
        lines.append("-" * 50)
        
        for item in invoice["line_items"]:
            category = f"[{item['category']}]"
            if item.get("usage_units"):
                lines.append(
                    f"{category} {item['description']}: "
                    f"{item['usage_units']} × "
                    f"KES {item.get('rate', 0):.2f} = "
                    f"KES {item['amount']:.2f}"
                )
            else:
                prefix = "  CREDIT: " if item['amount'] < 0 else "  "
                lines.append(f"{prefix}{category} {item['description']}: KES {abs(item['amount']):.2f}")
        
        lines.append("-" * 50)
        lines.append(f"Total Amount: KES {invoice['total_amount']:.2f}")
        
        if invoice['total_paid'] > 0:
            lines.append(f"Amount Paid: KES {invoice['total_paid']:.2f}")
        
        lines.append(f"Balance Due: KES {invoice['balance_amount']:.2f}")
        
        if invoice.get('overpaid_amount', 0) > 0:
            lines.append(f"Credit/Overpayment: KES {invoice['overpaid_amount']:.2f}")
        
        return "\n".join(lines)
    
    def _build_tenant_invoice_message(
        self, 
        invoice: Dict, 
        tenant: Dict,
        property_data: Dict,
        breakdown: str,
        payment_methods: List[Dict]
    ) -> str:
        """Build tenant invoice notification message."""
        lines = []
        lines.append(f"Dear {tenant['full_name']},")
        lines.append("")
        
        unit_numbers = invoice.get("meta", {}).get("unit_numbers", [])
        unit_str = ", ".join(unit_numbers) if unit_numbers else "your unit"
        
        lines.append(
            f"Your invoice for {invoice['meta']['billing_period']} at "
            f"{property_data['name']} ({unit_str}) is ready."
        )
        lines.append("")
        lines.append(breakdown)
        lines.append("")
        lines.append("PAYMENT METHODS:")
        lines.append("=" * 50)
        
        for method in payment_methods:
            lines.append(f"\n{method['name']}:")
            for key, value in method['details'].items():
                if value:
                    if "{unit#}" in str(value) and unit_numbers:
                        value = str(value).replace("{unit#}", ", ".join(unit_numbers))
                    lines.append(f"  {key.replace('_', ' ').title()}: {value}")
        
        lines.append("")
        lines.append("=" * 50)
        lines.append(f"Best regards,")
        lines.append(f"{property_data['name']} Management")
        
        return "\n".join(lines)
    
    def _build_landlord_summary_message(
        self, 
        summary: Dict,
        property_data: Dict
    ) -> str:
        """Build landlord summary notification message."""
        lines = []
        lines.append(f"MONTHLY INVOICE SUMMARY")
        lines.append("=" * 50)
        lines.append(f"Property: {summary['property_name']}")
        lines.append(f"Billing Period: {summary['billing_period']}")
        lines.append("")
        lines.append(f"Total Invoices Generated: {summary['total_invoices']}")
        lines.append(f"Total Amount: KES {summary['total_amount']:.2f}")
        lines.append(f"Total Collected: KES {summary['total_collected']:.2f}")
        lines.append(f"Total Outstanding: KES {summary['total_outstanding']:.2f}")
        lines.append(f"Invoices Paid: {summary['invoices_paid']}")
        lines.append(f"Invoices Ready: {summary['invoices_ready']}")
        lines.append(f"Invoices Pending Utilities: {summary['invoices_pending']}")
        lines.append(f"Old Invoices Consolidated: {summary['invoices_consolidated']}")
        
        if summary['pending_tickets']:
            lines.append("")
            lines.append("PENDING UTILITY READINGS:")
            lines.append("-" * 50)
            for ticket in summary['pending_tickets']:
                lines.append(
                    f"- {ticket['ticket_title']}: "
                    f"{ticket['pending_tasks']}/{ticket['total_tasks']} tasks pending"
                )
        
        lines.append("")
        lines.append("=" * 50)
        lines.append(f"{property_data['name']} Management System")
        
        return "\n".join(lines)
    
    def _get_notification_type(self, property_data: Dict) -> NotificationType:
        """Determine notification type from property integrations."""
        integrations = property_data.get("integrations", {})
        
        sms_enabled = integrations.get("sms", {}).get("enabled", False)
        email_enabled = integrations.get("email", {}).get("enabled", False)
        
        if sms_enabled and email_enabled:
            return NotificationType.BOTH
        elif sms_enabled:
            return NotificationType.SMS
        elif email_enabled:
            return NotificationType.EMAIL
        else:
            return NotificationType.EMAIL
    
    async def _queue_expiration_notification(self, lease: Dict, notification_type: str):
        """Queue notification for lease expiration."""
        tenant = await self.db.property_tenants.find_one({"_id": ObjectId(lease["tenant_id"])})
        if not tenant:
            return
        
        property_data = await self.db.properties.find_one({"_id": lease["property_id"]})
        end_date = self._normalize_datetime(lease["lease_terms"]["end_date"])
        
        if notification_type == "expired":
            subject = f"Lease Expired - {property_data['name']}"
            message = (
                f"Dear {tenant['full_name']},\n\n"
                f"Your lease at {property_data['name']} has expired as of "
                f"{end_date.strftime('%Y-%m-%d')}.\n\n"
                f"Please contact management to discuss renewal or move-out procedures.\n\n"
                f"Best regards,\n{property_data['name']} Management"
            )
        else:
            days_remaining = (end_date - self.current_date).days
            subject = f"Lease Expiring Soon - {property_data['name']}"
            message = (
                f"Dear {tenant['full_name']},\n\n"
                f"Your lease at {property_data['name']} will expire in {days_remaining} days "
                f"on {end_date.strftime('%Y-%m-%d')}.\n\n"
                f"Please contact management if you wish to renew your lease.\n\n"
                f"Best regards,\n{property_data['name']} Management"
            )
        
        notification = Notification(
            id=str(ObjectId()),
            recipient_type="tenant",
            recipient_id=str(tenant["_id"]),
            notification_type=self._get_notification_type(property_data),
            email=tenant.get("email"),
            phone=tenant.get("phone"),
            subject=subject,
            message=message,
            metadata={
                "lease_id": str(lease["_id"]),
                "notification_type": notification_type,
                "end_date": end_date.isoformat()
            },
            created_at=self.current_date,
            status="pending"
        )
        
        await self._save_notification(notification)
    
    async def _save_invoice(self, invoice: Invoice):
        """Save invoice to database."""
        invoice_dict = {
            "_id": ObjectId(invoice.id),
            "property_id": invoice.property_id,
            "tenant_id": ObjectId(invoice.tenant_id),
            "date_issued": invoice.date_issued,
            "due_date": invoice.due_date,
            "units_id": invoice.units_id,
            "line_items": [item.model_dump(by_alias=True) for item in invoice.line_items],
            "total_amount": invoice.total_amount,
            "total_paid": invoice.total_paid,
            "effective_paid": invoice.effective_paid,
            "overpaid_amount": invoice.overpaid_amount,
            "balance_amount": invoice.balance_amount,
            "status": invoice.status.value,
            "balance_forwarded": invoice.balance_forwarded,
            "meta": invoice.meta
        }
        await self.db.property_invoices.insert_one(invoice_dict)
    
    async def _save_ticket(self, ticket: Ticket):
        """Save ticket to database."""
        ticket_dict = ticket.model_dump(by_alias=True)
        ticket_dict["_id"]=ObjectId(ticket_dict["_id"])
        ticket_dict["tasks"] = [task.model_dump() for task in ticket.tasks]
        
        for task in ticket_dict["tasks"]:
            if task.get("created_at") and isinstance(task["created_at"], datetime):
                task["created_at"] = task["created_at"]
            if task.get("updated_at") and isinstance(task["updated_at"], datetime):
                task["updated_at"] = task["updated_at"]
            if task.get("completed_at") and isinstance(task["completed_at"], datetime):
                task["completed_at"] = task["completed_at"]
        
        await self.db.property_tickets.insert_one(ticket_dict)
    
    async def _save_notification(self, notification: Notification):
        """Save notification to database."""
        notification_dict = {
            "_id": ObjectId(notification.id),
            "recipient_type": notification.recipient_type,
            "recipient_id": notification.recipient_id,
            "notification_type": notification.notification_type.value,
            "email": notification.email,
            "phone": notification.phone,
            "subject": notification.subject,
            "message": notification.message,
            "metadata": notification.metadata,
            "created_at": notification.created_at,
            "sent_at": notification.sent_at,
            "status": notification.status
        }
        await self.db.property_notifications.insert_one(notification_dict)
    
    async def _save_payment(self, payment: Payment):
        """Save payment to database."""
        payment_dict = payment.model_dump(by_alias=True)
        payment_dict["_id"]=ObjectId(payment_dict["_id"])
        await self.db.property_payments.insert_one(payment_dict)
    async def get_tenant_balance(self,id):
        return 0
    async def get_tenant_invoice_history(
        self,
        tenant_id: str,
        include_consolidated: bool = True
    ) -> List[Dict]:
        """Get complete invoice history for a tenant with consolidation info."""
        query = {"tenant_id": ObjectId(tenant_id)}
        
        if not include_consolidated:
            query["status"] = {"$ne": InvoiceStatus.CONSOLIDATED.value}
        
        cursor = self.db.property_invoices.find(query).sort("date_issued", -1)
        invoices = await cursor.to_list(length=None)
        
        for invoice in invoices:
            if invoice.get("status") == InvoiceStatus.CONSOLIDATED.value:
                consolidation = invoice.get("meta", {}).get("consolidation", {})
                consolidated_into = consolidation.get("consolidated_into_invoice_id")
                
                if consolidated_into:
                    new_invoice = await self.db.property_invoices.find_one(
                        {"_id": consolidated_into},
                        {"meta.billing_period": 1, "date_issued": 1}
                    )
                    if new_invoice:
                        invoice["consolidated_into_info"] = {
                            "invoice_id": consolidated_into,
                            "billing_period": new_invoice.get("meta", {}).get("billing_period"),
                            "date_issued": new_invoice.get("date_issued")
                        }
        
        return invoices

class OptimizedAsyncLeaseInvoiceManager(AsyncLeaseInvoiceManager):
    """Manager with optimized connection pooling"""
    
    def __init__(
        self,
        mongo_uri: str,
        database_name: str,
        max_pool_size: int = 200,  # Increased for high concurrency
        min_pool_size: int = 50,
        max_idle_time_ms: int = 30000,
        **kwargs
    ):
        # Configure connection pool
        client = AsyncIOMotorClient(
            mongo_uri,
            maxPoolSize=max_pool_size,
            minPoolSize=min_pool_size,
            maxIdleTimeMS=max_idle_time_ms,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            retryWrites=True,
            retryReads=True,
            w="majority"  # Write concern for consistency
        )
        
        super().__init__(client, database_name, **kwargs)

# Complete workflow example with all edge cases
async def complete_workflow_with_edge_cases():
    """
    Comprehensive workflow demonstrating:
    1. Invoice generation with previous balances
    2. Overpayment credit handling
    3. Partial payments
    4. Multiple consolidations
    5. Payment allocation
    """
    
    client = AsyncIOMotorClient("mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin")
    manager = AsyncLeaseInvoiceManager(
        client, 
        database_name="fq_db",
        expiration_threshold_months=2
    )
    
    db=client["fq_db"]
    # async with await client.start_session() as session:
    #     async with session.start_transaction():
    #         # perform your DB operations here
    #         result = await db.test.insert_one({"name": "Elijah"}, session=session)
    #         inserted_id = result.inserted_id

    #         # Example update (make sure `id` is a valid ObjectId)
    #         await db.test.update_one(
    #             {"_id": inserted_id}, 
    #             {"$set": {"status": "done"}}, 
    #             session=session
    #         )

    #         print("Transaction successful")
    # return 
    from bson import ObjectId
    import json
    # res=await manager._get_previous_utility_reading(ObjectId("690429e84c74bcbb048b4c65"),"Water","2025-09")
    # print(res)
    
    # results = {
    #         "billing_period": "2025-11",
    #         "leases_processed": 0,
    #         "leases_expiring": [],
    #         "leases_expired": [],
    #         "invoices_created": [],
    #         "invoices_regenerated": [],
    #         "invoices_consolidated": [],
    #         "tickets_created": [],
    #         "notifications_queued": [],
    #         "errors": []
    # }
    
    # lease=await db.property_leases.find_one({"_id": ObjectId("69042a294c74bcbb048b4d00")})
    # if not lease:
    #     print("lease not found")
    #     return
    # property_data=await db.properties.find_one({"_id": str(lease['property_id'])})
    # x=await manager._process_single_lease(
    #     lease=lease, 
    #     billing_month="2025-11",
    #     property_data=property_data,
    #     force=True,
    #     balance_method="itemized",
    #     results=results
    # )
    # results["tasks"]=x
    # print(json.dumps(results,indent=4))
    # return
    print("=" * 80)
    print(" COMPREHENSIVE INVOICE WORKFLOW WITH EDGE CASES")
    print("=" * 80)
    
    # SCENARIO 1: Generate invoices with previous balances
    print("\n" + "=" * 80)
    print(" SCENARIO 1: Generate Invoices with Previous Balances")
    print("=" * 80)
    
    billing_month = "2025-11"
    results = await manager.process_all_leases(
        billing_month=billing_month, 
        force=True,
        balance_method="itemized"
    )
    
    print(f"\n✓ Processed {results['leases_processed']} leases")
    print(f"✓ Created {len(results['invoices_created'])} invoices")
    print(f"✓ Consolidated {len(results['invoices_consolidated'])} old invoices")
    print(f"✓ Created {len(results['tickets_created'])} tickets")
    
    if results['errors']:
        print(f"\n⚠️  Errors:")
        for error in results['errors']:
            print(f"    - {error}")
    
    # View sample invoice
    if results['invoices_created']:
        invoice_id = results['invoices_created'][0]
        invoice = await manager.db.property_invoices.find_one({"_id": ObjectId(invoice_id)})
        
        print("\n" + "-" * 80)
        print("Sample Invoice Details:")
        print("-" * 80)
        print(f"Invoice ID: {invoice['_id']}")
        print(f"Tenant: {invoice['meta']['tenant']['full_name']}")
        print(f"Unit(s): {', '.join(invoice['meta']['unit_numbers'])}")
        print(f"Billing Period: {invoice['meta']['billing_period']}")
        print(f"\nLine Items:")
        
        for item in invoice['line_items']:
            category = item['category']
            desc = item['description']
            amount = item['amount']
            
            if category == "balance_brought_forward":
                print(f"  📋 {desc}: KES {amount:.2f}")
            elif category == "overpayment_credit":
                print(f"  💳 {desc}: -KES {abs(amount):.2f} (CREDIT)")
            elif category == "rent":
                print(f"  🏠 {desc}: KES {amount:.2f}")
            elif category == "utility":
                if item.get('usage_units'):
                    print(f"  ⚡ {desc}: {item['usage_units']} × KES {item.get('rate', 0):.2f} = KES {amount:.2f}")
                else:
                    print(f"  ⚡ {desc}: KES {amount:.2f}")
        
        print(f"\n{'─' * 40}")
        print(f"Total Amount: KES {invoice['total_amount']:.2f}")
        print(f"Balance Due: KES {invoice['balance_amount']:.2f}")
        
        if invoice.get('meta', {}).get('payment_allocation_rules'):
            print(f"\n📊 Payment Allocation Rules (Old Invoices First):")
            for rule in invoice['meta']['payment_allocation_rules']:
                print(f"  Priority {rule['priority']}: {rule['billing_period']} - KES {rule['amount']:.2f}")
    
    # SCENARIO 2: Process utility readings
    # if results['tickets_created']:
    #     print("\n" + "=" * 80)
    #     print(" SCENARIO 2: Process Utility Readings")
    #     print("=" * 80)
        
    #     ticket_id = results['tickets_created'][0]
    #     ticket = await manager.db.property_tickets.find_one({"_id": ticket_id})
        
    #     print(f"\nTicket: {ticket['title']}")
    #     print(f"Total Tasks: {len(ticket['tasks'])}")
        
    #     for i, task in enumerate(ticket['tasks'][:2], 1):  # Process first 2 tasks
    #         if task['status'] == TaskStatus.AWAITING_INPUT.value:
    #             task_id = task['id']
    #             current_reading = task['metadata']['previous_reading'] + 25.5
                
    #             print(f"\n🔧 Processing Task {i}: {task['title']}")
    #             print(f"   Previous: {task['metadata']['previous_reading']}")
    #             print(f"   Current: {current_reading}")
                
    #             result = await manager.process_utility_reading(
    #                 task_id=task_id,
    #                 current_reading=current_reading,
    #                 reading_date="2025-11-28"
    #             )
                
    #             if result['success']:
    #                 print(f"   ✓ Usage: {result['usage_record']['usage']} {result['usage_record']['unit_of_measure']}")
    #                 print(f"   ✓ Amount: KES {result['usage_record']['amount']:.2f}")
    #                 print(f"   ✓ Progress: {result['progress']['percentage']}%")
    
    # SCENARIO 3: Make partial payment
    # print("\n" + "=" * 80)
    # print(" SCENARIO 3: Process Partial Payment")
    # print("=" * 80)
    
    # if results['invoices_created']:
    #     invoice_id = results['invoices_created'][0]
    #     invoice = await manager.db.property_invoices.find_one({"_id": invoice_id})
    #     tenant_id = invoice['tenant_id']
        
    #     # Pay only 60% of total
    #     partial_amount = invoice['total_amount'] * 0.6
        
    #     print(f"\n💰 Making partial payment of KES {partial_amount:.2f}")
    #     print(f"   (60% of total KES {invoice['total_amount']:.2f})")
        
    #     payment_result = await manager.process_payment(
    #         tenant_id=tenant_id,
    #         amount=partial_amount,
    #         payment_method="mpesa",
    #         reference="MPAY123456",
    #         target_invoice_id=invoice_id
    #     )
        
    #     if payment_result['success']:
    #         print(f"\n✓ Payment processed successfully")
    #         print(f"  Payment ID: {payment_result['payment_id']}")
    #         print(f"\n📊 Payment Allocation:")
            
    #         for allocation in payment_result['allocations']:
    #             print(f"  → {allocation['billing_period']}: KES {allocation['amount']:.2f} ({allocation['invoice_status']})")
            
    #         if payment_result['remaining_amount'] > 0:
    #             print(f"\n💳 Remaining credited to tenant: KES {payment_result['remaining_amount']:.2f}")
    
    # SCENARIO 4: Make full payment (using credit + cash)
    # print("\n" + "=" * 80)
    # print(" SCENARIO 4: Full Payment with Credit Applied")
    # print("=" * 80)
    
    # if results['invoices_created']:
    #     invoice_id = results['invoices_created'][0]
    #     invoice = await manager.db.property_invoices.find_one({"_id": invoice_id})
    #     tenant_id = invoice['tenant_id']
        
    #     # Get current balance
    #     remaining_balance = invoice['balance_amount']
        
    #     # Get tenant credit
    #     tenant = await manager.db.property_tenants.find_one({"_id": ObjectId(tenant_id)})
    #     if not tenant:
    #         raise Exception(f"Unable to get tenant {tenant_id}")
    #     credit_balance = tenant.get('credit_balance', 0)
        
    #     # Calculate payment needed (balance - credit)
    #     payment_needed = max(0, remaining_balance - credit_balance)
        
    #     print(f"\n📋 Invoice Balance: KES {remaining_balance:.2f}")
    #     print(f"💳 Tenant Credit: KES {credit_balance:.2f}")
    #     print(f"💵 Payment Needed: KES {payment_needed:.2f}")
        
    #     if payment_needed > 0:
    #         payment_result = await manager.process_payment(
    #             tenant_id=tenant_id,
    #             amount=payment_needed,
    #             payment_method="bank",
    #             reference="BANK789012",
    #             target_invoice_id=invoice_id
    #         )
            
    #         if payment_result['success']:
    #             print(f"\n✓ Full payment processed")
    #             print(f"  Payment ID: {payment_result['payment_id']}")
                
    #             for allocation in payment_result['allocations']:
    #                 print(f"  → {allocation['billing_period']}: KES {allocation['amount']:.2f} ({allocation['invoice_status']})")
    
    # SCENARIO 5: Generate next month with multiple consolidations
    # print("\n" + "=" * 80)
    # print(" SCENARIO 5: Next Month - Multiple Consolidations")
    # print("=" * 80)
    
    # next_month = "2025-12"
    # results2 = await manager.process_all_leases(
    #     billing_month=next_month,
    #     force=False,
    #     balance_method="sum"  # Use sum method this time
    # )
    
    # print(f"\n✓ Processed {results2['leases_processed']} leases for {next_month}")
    # print(f"✓ Created {len(results2['invoices_created'])} invoices")
    # print(f"✓ Consolidated {len(results2['invoices_consolidated'])} old invoices")
    
    # # View invoice with multiple consolidations
    # if results2['invoices_created']:
    #     invoice_id = results2['invoices_created'][0]
    #     invoice = await manager.db.property_invoices.find_one({"_id": invoice_id})
        
    #     print(f"\n📄 Invoice for {next_month}:")
    #     print(f"   Tenant: {invoice['meta']['tenant']['full_name']}")
        
    #     # Count consolidated invoices
    #     allocation_rules = invoice.get('meta', {}).get('payment_allocation_rules', [])
    #     if allocation_rules:
    #         print(f"   📚 Consolidating {len(allocation_rules)} previous invoices:")
    #         for rule in allocation_rules:
    #             print(f"      - {rule['billing_period']}: KES {rule['amount']:.2f}")
    
    # SCENARIO 6: View tenant invoice history
    # print("\n" + "=" * 80)
    # print(" SCENARIO 6: Tenant Invoice History")
    # print("=" * 80)
    
    # if results['invoices_created']:
    #     invoice = await manager.db.property_invoices.find_one({"_id": results['invoices_created'][0]})
    #     tenant_id = invoice['tenant_id']
        
    #     history = await manager.get_tenant_invoice_history(tenant_id, include_consolidated=True)
        
    #     print(f"\n📊 Invoice History for Tenant {invoice['meta']['tenant']['full_name']}:")
    #     print(f"   Total Invoices: {len(history)}\n")
        
    #     for inv in history[:5]:  # Show last 5
    #         billing_period = inv.get('meta', {}).get('billing_period', 'N/A')
    #         status = inv['status']
    #         total = inv['total_amount']
    #         balance = inv['balance_amount']
            
    #         status_emoji = {
    #             'paid': '✅',
    #             'consolidated': '📦',
    #             'ready': '📄',
    #             'partially_paid': '⏳',
    #             'overdue': '⚠️'
    #         }.get(status, '❓')
            
    #         print(f"   {status_emoji} {billing_period} - {status.upper()}")
    #         print(f"      Total: KES {total:.2f} | Balance: KES {balance:.2f}")
            
    #         if status == 'consolidated':
    #             consolidated_into = inv.get('consolidated_into_info', {})
    #             if consolidated_into:
    #                 print(f"      → Consolidated into {consolidated_into.get('billing_period', 'N/A')}")
            
    #         print()
    
    # print("=" * 80)
    # print(" WORKFLOW COMPLETE - ALL EDGE CASES HANDLED")
    # print("=" * 80)
    # print("\n✓ Previous balances consolidated")
    # print("✓ Overpayment credits applied")
    # print("✓ Partial payments processed")
    # print("✓ Multiple consolidations tracked")
    # print("✓ Payment allocation working correctly")
    # print("✓ Complete audit trail maintained")
    
    client.close()


if __name__ == "__main__":
    asyncio.run(complete_workflow_with_edge_cases())