from __future__ import annotations
from datetime import datetime, date,timezone
from typing import Optional, Literal,List,Any,Dict
from bson import ObjectId
from pydantic import Field,BaseModel
from core.MongoORJSONResponse import normalize_bson,PyObjectId,MongoModel

from enum import Enum

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

Task.model_rebuild()
Notification.model_rebuild()