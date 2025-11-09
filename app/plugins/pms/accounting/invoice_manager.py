from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Optional, Tuple
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import calendar

from plugins.pms.models.extra import LeaseStatus
from plugins.pms.models.ledger_entry import Invoice, InvoiceLineItem, InvoiceStatus
from plugins.pms.models.extra import Ticket, Task, TaskStatus, TicketStatus, TicketPriority, TicketCategory
from plugins.pms.models.extra import Notification, NotificationType
from plugins.pms.models.models import Payment
from plugins.pms.models.extra import UtilityUsageRecord
from plugins.pms.accounting.ledger import Ledger, LEDGER_COLL, INVOICE_COLL


class AsyncLeaseInvoiceManager:
    """
    Comprehensive async lease and invoice management system integrated with Ledger.
    
    Features:
    - Previous balance consolidation (sum/itemized)
    - Overpayment credit handling via ledger
    - Payment allocation to old invoices
    - Multiple consolidations support
    - Partial payment tracking via ledger
    - Complete audit trail through double-entry ledger
    - Line item adjustment (add/remove)
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
        
        # Initialize Ledger system
        self.ledger = Ledger(self.db)
        
    async def get_tenant_overpayment(self, tenant_id: str) -> float:
        """Get tenant's current overpayment/credit balance from ledger."""
        return await self.ledger.get_tenant_credit_balance(tenant_id)
    
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
            "balance_forwarded": {"$ne": True}
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
            # await self._update_lease_statuses(results)
            active_leases_by_property = await self._get_active_leases_by_property()
            print(f"{len(active_leases_by_property.items())} active_leases_by_property")
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

        # Optionally print total leases (for debug only)
        total_count = await self.db.property_leases.count_documents({})
        # print(f"Total leases in DB: {total_count}")
        # print(self.db.name)

        # Only fetch active/signed leases
        cursor = self.db.property_leases.find({
            "status": {"$in": ["active", "signed"]}
        })

        leases_by_property: Dict[str, List[Dict]] = {}

        async for lease in cursor:
            property_id = str(lease.get("property_id", "UNKNOWN"))
            leases_by_property.setdefault(property_id, []).append(lease)

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
        property_data = await self.db.properties.find_one({"_id": ObjectId(property_id)})
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
        
        # Check if invoice already exists
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
        
        # Get tenant's overpayment from ledger
        tenant_overpayment = await self.get_tenant_overpayment(tenant_id)
        
        # Invoice metadata
        invoice_meta = {
            "lease_id": lease_id,
            "billing_period": billing_month,
            "tenant": {
                "full_name": lease["tenant_details"]["full_name"],
                "is_lease_active": True,
            },
            "property": {
                "name": property_data["name"],
                "location": property_data.get("location", "")
            },
            "units": units_info,
            "unit_numbers": unit_numbers,
            "unit_numbers_str": unit_numbers_str,
            "billing_cycle": billing_cycle,
            "utilities_usage": {},
            "previous_balance_method": balance_method,
            "itemized_balances": itemized_balances if balance_method == "itemized" else [],
            "tenant_overpayment_applied": tenant_overpayment,
            "payment_allocation_rules": [],
            "audit_trail": []
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
                    "priority": i + 1
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
                    "billing_period": billing_month,
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
        
        # Apply tenant overpayment/credit (tracked in ledger)
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
        
        # Save invoice and post to ledger
        await self._save_invoice(invoice)
        await self.ledger.post_invoice_to_ledger(invoice)
        
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
        """Mark previous invoices as consolidated."""
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
        """Delete existing invoice, related tickets, and ledger entries."""
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
        
        # Delete invoice, tickets, and ledger entries
        await self.db.property_invoices.delete_one({"_id": ObjectId(invoice_id)})
        await self.db.property_tickets.delete_many({
            "metadata.billing_month": billing_month,
            "tasks.metadata.invoice_id": invoice_id
        })
        await self.db[LEDGER_COLL].delete_many({
            "invoice_id": ObjectId(invoice_id)
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
        """Process a utility meter reading input and add to invoice via ledger."""
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
            
            # Update task status
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
            
            # Add utility to invoice via ledger
            invoice_id = task["metadata"]["invoice_id"]
            await self._add_utility_to_invoice(invoice_id, usage_record, task["metadata"])
            result["invoice_updated"] = True
            
            # Check if all tasks completed
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
                    {"_id": ObjectId(ticket["metadata"]["property_id"])}
                )
                
                for inv_id in unique_invoice_ids:
                    invoice_doc = await self.db.property_invoices.find_one({"_id": inv_id})
                    if invoice_doc:
                        await self._finalize_invoice(inv_id)
                        await self._send_invoice_notification(invoice_doc, property_data)
                
                result["notifications_sent"] = True
            
            result["success"] = True
            result["usage_record"] = usage_record.model_dump()
            result["progress"] = {
                "completed_tasks": completed_tasks,
                "total_tasks": total_tasks,
                "percentage": round((completed_tasks / total_tasks) * 100, 2)
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        return result
    
    async def _add_utility_to_invoice(
        self, 
        invoice_id: str, 
        usage_record: UtilityUsageRecord,
        task_metadata: Dict
    ):
        """Add utility charge to invoice as a line item with ledger entry."""
        unit_numbers_str = task_metadata.get("unit_numbers_str", "")
        unit_numbers = task_metadata.get("unit_numbers", [])
        
        # Create the line item
        utility_line_item = InvoiceLineItem(
            id=str(ObjectId()),
            description=f"{unit_numbers_str}, {usage_record.utility_name} Usage - {usage_record.usage} {usage_record.unit_of_measure}",
            amount=usage_record.amount,
            category="utility",
            usage_units=usage_record.usage,
            rate=usage_record.rate,
            meta={
                "utility_type": "metered",
                "utility_name": usage_record.utility_name,
                "previous_reading": usage_record.previous_reading,
                "current_reading": usage_record.current_reading,
                "reading_date": usage_record.reading_date,
                "unit_of_measure": usage_record.unit_of_measure,
                "unit_numbers": unit_numbers
            }
        )
        
        # Get invoice for ledger posting
        invoice_doc = await self.db.property_invoices.find_one({"_id": ObjectId(invoice_id)})
        if not invoice_doc:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        # Use ledger to add line item (posts double-entry)
        invoice_obj = Invoice(**invoice_doc)
        await self.ledger.add_line_item_to_invoice(
            invoice_id=invoice_id,
            line_item=utility_line_item,
            reason=f"Utility reading: {usage_record.current_reading} {usage_record.unit_of_measure}",
            adjustment_date=self.current_date
        )
        
        # Update invoice metadata for utilities usage
        usage_key = f"{usage_record.utility_name.lower().replace(' ', '_')}_usage"
        await self.db.property_invoices.update_one(
            {"_id": ObjectId(invoice_id)},
            {
                "$set": {
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
        tenant_id: ObjectId,
        amount: float,
        payment_method: str,
        reference: str,
        payment_date: Optional[datetime] = None,
        target_invoice_id: Optional[str] = None
    ) -> Dict:
        """
        Process a payment from tenant using Ledger system.
        Allocates to old consolidated invoices first, then current invoice.
        """
        if payment_date is None:
            payment_date = self.current_date
        
        result = {
            "success": False,
            "payment_id": [],
            "total_amount": amount,
            "allocations": [],
            "remaining_amount": amount,
            "overpayment_credited": 0.0,
            "error": None
        }
        
        try:
            tenant = await self.db.property_tenants.find_one({"_id": ObjectId(tenant_id)})
            if not tenant:
                raise ValueError(f"Tenant {tenant_id} not found")
            
            property_id = tenant.get("property_id")
            
            if target_invoice_id:
                # Pay specific invoice
                invoice_doc = await self.db.property_invoices.find_one({"_id": ObjectId(target_invoice_id)})
                if not invoice_doc:
                    raise ValueError(f"Invoice {target_invoice_id} not found")
                
                invoice_obj = Invoice(**invoice_doc)
                
                # Use ledger to post payment
                ledger_entries = await self.ledger.post_payment_to_ledger(
                    invoice_obj, 
                    amount, 
                    payment_date
                )
                
                # Get updated invoice status
                updated_invoice = await self.db.property_invoices.find_one({"_id": ObjectId(target_invoice_id)})
                
                result["allocations"].append({
                    "invoice_id": target_invoice_id,
                    "billing_period": updated_invoice["meta"]["billing_period"],
                    "amount": amount,
                    "invoice_status": updated_invoice["status"]
                })
                result["remaining_amount"] = 0.0
                
                # Create payment record for audit
                payment = Payment(
                    id=str(ObjectId()),
                    tenant_id=(tenant_id),
                    property_id=property_id,
                    invoice_id=(target_invoice_id),
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
                result["payment_id"].append(payment.id)
                
            else:
                # Auto-allocate: Find invoices with balance, prioritize old ones
                cursor = self.db.property_invoices.find({
                    "tenant_id": ObjectId(tenant_id),
                    "balance_amount": {"$gt": 0},
                    "status": {"$nin": [InvoiceStatus.CANCELLED.value]}
                }).sort("date_issued", 1)
                
                invoices_with_balance = await cursor.to_list(length=None)
                
                remaining = amount
                for invoice_doc in invoices_with_balance:
                    if remaining <= 0:
                        break
                    
                    invoice_obj = Invoice(**invoice_doc)
                    amount_to_pay = min(remaining, invoice_obj.balance_amount)
                    
                    # Use ledger to post payment
                    ledger_entries = await self.ledger.post_payment_to_ledger(
                        invoice_obj,
                        amount_to_pay,
                        payment_date
                    )
                    
                    # Get updated status
                    updated_invoice = await self.db.property_invoices.find_one(
                        {"_id": ObjectId(invoice_obj.id)}
                    )
                    
                    result["allocations"].append({
                        "invoice_id": str(invoice_obj.id),
                        "billing_period": invoice_doc["meta"]["billing_period"],
                        "amount": amount_to_pay,
                        "invoice_status": updated_invoice["status"]
                    })
                    
                    remaining -= amount_to_pay
                    
                    # Create payment record for audit
                    payment = Payment(
                        id=str(ObjectId()),
                        tenant_id=str(tenant_id),
                        property_id=property_id,
                        invoice_id=str(invoice_obj.id),
                        amount=amount_to_pay,
                        payment_date=payment_date,
                        payment_method=payment_method,
                        reference=reference,
                        allocations=result["allocations"],
                        meta={
                            "overpayment_credited": remaining,
                            "processed_at": self.current_date
                        }
                    )
                    
                    await self._save_payment(payment)
                    result["payment_id"].append(payment.id)
                
                result["remaining_amount"] = remaining
            
            # Overpayment is automatically handled by ledger.sync_invoice_payment_status
            # which creates tenant credit entries in the ledger
            if result["remaining_amount"] > 0:
                result["overpayment_credited"] = result["remaining_amount"]
            
            
            result["success"] = True
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        return result
    
    async def add_line_item_to_invoice(
        self,
        invoice_id: str,
        line_item: InvoiceLineItem,
        reason: str = ""
    ) -> Dict:
        """
        Add a new line item to an existing invoice.
        Works with both SUM and ITEMIZED consolidation methods.
        """
        result = {
            "success": False,
            "invoice_id": invoice_id,
            "line_item_added": None,
            "ledger_entries": [],
            "error": None
        }
        
        try:
            # Use ledger to add line item (handles both sum and itemized)
            ledger_entries, updated_invoice = await self.ledger.add_line_item_to_invoice(
                invoice_id=invoice_id,
                line_item=line_item,
                reason=reason,
                adjustment_date=self.current_date
            )
            
            result["success"] = True
            result["line_item_added"] = line_item.id
            result["ledger_entries"] = [str(e.id) for e in ledger_entries]
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        return result
    
    async def remove_line_item_from_invoice(
        self,
        invoice_id: str,
        line_item_id: str,
        reason: str = "",
        allow_balance_item_removal: bool = False
    ) -> Dict:
        """
        Remove a line item from an existing invoice.
        Creates reversal entries in ledger.
        """
        result = {
            "success": False,
            "invoice_id": invoice_id,
            "line_item_removed": None,
            "reversal_entries": [],
            "error": None
        }
        
        try:
            # Use ledger to remove line item (creates reversals)
            reversal_entries, updated_invoice = await self.ledger.remove_line_item_from_invoice(
                invoice_id=invoice_id,
                line_item_id=line_item_id,
                reason=reason,
                adjustment_date=self.current_date,
                allow_balance_item_removal=allow_balance_item_removal
            )
            
            result["success"] = True
            result["line_item_removed"] = line_item_id
            result["reversal_entries"] = [str(e.id) for e in reversal_entries]
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            result["error"] = str(e)
        
        return result
    
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
            utilities = [
                l for l in prev_invoice.get("line_items", []) 
                if utility_name.lower() in l.get("description", "").lower()
            ]
            if len(utilities) > 0:
                li_meta = utilities[0].get("meta", {})
                return li_meta.get("current_reading", 0.0)
        
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
        
        property_data = await self.db.properties.find_one({"_id": ObjectId(lease["property_id"])})
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
        ticket_dict["_id"] = ObjectId(ticket_dict["_id"])
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
        payment_dict["_id"] = ObjectId(payment_dict["_id"])
        await self.db.property_payments.insert_one(payment_dict)
    
    async def get_tenant_balance(self, tenant_id: str) -> float:
        """Get tenant's outstanding balance across all invoices."""
        cursor = self.db.property_invoices.find({
            "tenant_id": ObjectId(tenant_id),
            "balance_amount": {"$gt": 0},
            "status": {"$nin": [InvoiceStatus.CANCELLED.value]}
        })
        
        invoices = await cursor.to_list(length=None)
        total_balance = sum(inv["balance_amount"] for inv in invoices)
        return round(total_balance, 2)
    
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