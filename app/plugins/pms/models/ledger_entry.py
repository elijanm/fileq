from __future__ import annotations
from datetime import datetime, date,timezone
from typing import Optional, Literal,List,Any
from bson import ObjectId
from pydantic import Field, ConfigDict, field_validator,field_serializer
from core.MongoORJSONResponse import normalize_bson,PyObjectId,MongoModel

from enum import Enum
# ---------------- ObjectId Compatibility ----------------


class UtilityName(str, Enum):
    water = "Water"
    electricity = "Electricity"
    garbage = "Garbage"
    internet = "Internet"
    gym = "Gym"
    pool = "Pool"
    other = "Other"

    @classmethod
    def normalize(cls, v: str):
        v = v.lower()
        if "water" in v: return cls.water
        if "electric" in v: return cls.electricity
        if "garbage" in v: return cls.garbage
        if "internet" in v: return cls.internet
        if "gym" in v: return cls.gym
        if "pool" in v: return cls.pool
        return cls.other
    
    
# ---------------- LedgerEntry Model ----------------
class LedgerEntry(MongoModel):
  
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # Core fields
    date: datetime = Field(..., description="Transaction date")
    account: str = Field(..., description="Account name (e.g. Rental Income, Cash)")
    account_code: Optional[str] = Field(None, description="Chart of account code")
    account_type: Optional[
        Literal["Asset", "Liability", "Income", "Expense", "Contra-Asset", "Equity"]
    ] = None

    debit: float = Field(0.0, ge=0, description="Debit amount")
    credit: float = Field(0.0, ge=0, description="Credit amount")

    category: Optional[str] = Field(
        None, description="Category or source of transaction, e.g. rent, utilities"
    )
    description: Optional[str] = Field(None, description="Ledger description")

    # Relational references
    invoice_id: Optional[PyObjectId] = Field(None)
    line_item_id: Optional[PyObjectId] = Field(None)
    property_id: Optional[PyObjectId] = None
    tenant_id: Optional[PyObjectId] = None

    # Metadata
    transaction_type: Optional[
        Literal[
            "invoice_issue",
            "payment_received",
            "tenant_credit",
            "credit_applied",
            "deposit_issue",
            "deposit_received",
            "deposit_refund",
            "capex",
            "depreciation",
            "line_item_addition",
            "line_item_reversal",
            "adjustment",
            "utility_addition",
        ]
    ] = None
    reference: Optional[str] = Field(None, description="Human-readable reference code")

    # Ownership/audit
    owner: Optional[dict] = Field(None, description="Ownership or created_by metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},   # 👈 important
        "extra": "ignore"
    }
    @field_validator("date", mode="before")
    def normalize_date(cls, v):
        if isinstance(v, date) and not isinstance(v, datetime):
            # convert plain date to datetime at midnight UTC
            return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
        return v
    # -------------- Validators ----------------
    @field_validator("debit", "credit")
    def round_amounts(cls, v: float) -> float:
        """Ensure amounts are rounded to 2 decimals."""
        return round(float(v or 0.0), 2)

    @property
    def is_debit(self) -> bool:
        return self.debit > 0 and self.credit == 0

    @property
    def is_credit(self) -> bool:
        return self.credit > 0 and self.debit == 0

    # -------------- Factory Helper ----------------
    @classmethod
    def create(
        cls,
        *,
        date: datetime | date,
        account: str,
        debit: float = 0.0,
        credit: float = 0.0,
        category: Optional[str] = None,
        description: Optional[str] = None,
        invoice_id: Optional[ObjectId] = None,
        line_item_id: Optional[ObjectId] = None,
        property_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        transaction_type: Optional[str] = None,
        reference: Optional[str] = None,
        account_code: Optional[str] = None,
        account_type: Optional[str] = None,
        owner: Optional[dict] = None,
    ) -> "LedgerEntry":
        """Factory method for clean instantiation with defaults."""
        return cls(
            date=date,
            account=account,
            debit=round(debit or 0, 2),
            credit=round(credit or 0, 2),
            category=category,
            description=description,
            invoice_id=invoice_id,
            line_item_id=line_item_id,
            property_id=property_id,
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            reference=reference,
            account_code=account_code,
            account_type=account_type,
            owner=owner,
        )

    def __repr__(self):
        side = "DR" if self.debit > 0 else "CR"
        amount = self.debit or self.credit
        return f"<LedgerEntry {self.account} {side} {amount:.2f} ({self.transaction_type or 'n/a'})>"
    
    
class InvoiceLineItem(MongoModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    description: str = Field(..., description="Item description (e.g. Rent Feb 2025)")
    category: Literal[
        "rent",
        "deposit",
        "maintenance",
        "utilities",
        "utility",
        "taxes",
        "investment",
        "loan",
        "misc",
        "balance_brought_forward"
    ] = "misc"
    utility_name: Optional[UtilityName
    ] = None
    amount: float = Field(..., ge=0.0, description="Line item amount")
    quantity: Optional[float] = Field(1, ge=1)
    usage_units: Optional[float] = None
    unit_price: Optional[float] = None
    meta: Optional[dict] = Field(default_factory=dict)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str},   # 👈 important
        "extra": "ignore"
    }
    
    @field_validator("utility_name", mode="before")
    @classmethod
    def normalize_util(cls, v):
        if v is None:
            return None
        if isinstance(v, UtilityName):
            return v
        if isinstance(v, str):
            return UtilityName.normalize(v)
        return UtilityName.other
    
    

# -------------------- Invoice Model --------------------

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    PENDING_UTILITIES = "pending_utilities"
    READY = "ready"
    ISSUED = "issued"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CONSOLIDATED = "consolidated"  # Balance moved to new invoice
    CANCELLED = "cancelled"
    PARTIAL="partial"
    
class Invoice(MongoModel):


    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")

    # Core fields
    invoice_number: Optional[str] = Field(None, description="Human-readable invoice number, e.g. INV-2025-02")
    date_issued: datetime = Field(default_factory=datetime.utcnow)
    due_date: Optional[datetime] = None
    status: InvoiceStatus = InvoiceStatus.DRAFT

    property_id: Optional[PyObjectId] = None
    tenant_id: Optional[PyObjectId] = None
    lease_id: Optional[PyObjectId] = None
    units_id: Optional[List[str]] = None

    # Financials
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    subtotal_amount: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0
    late_fee: Optional[float]=0.0

    total_paid: float = 0.0
    effective_paid: float = 0.0
    overpaid_amount: float = 0.0
    balance_amount: float = 0.0

    payment_date: Optional[datetime] = None

    # Ownership / audit
    owner: Optional[dict] = Field(None, description="Owner or organization metadata")
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Meta flags
    balance_forwarded: Optional[bool] = False
    notes: Optional[str] = None
    meta: Optional[dict] = Field(default_factory=dict)
    owner:Optional[dict] = Field(default_factory=dict)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str,PyObjectId:str},   # 👈 important
        "extra": "ignore"
    }
    
   
    # --------------- Validators & Helpers ----------------
    @field_validator("total_amount", mode="before")
    def compute_total(cls, v, values):
        """Auto-compute total if not set."""
        if not v and "line_items" in values:
            subtotal = sum(i.amount for i in values["line_items"])
            tax = values.get("tax_amount", 0.0)
            return round(subtotal + tax, 2)
        return v
    @field_validator("tenant_id", mode="before")
    @classmethod
    def normalize_tenant_id(cls, v):
        """Accept ObjectId or string, store as string."""
        if isinstance(v, ObjectId):
            return str(v)
        elif isinstance(v, str) and ObjectId.is_valid(v):
            return v
        raise ValueError("Invalid tenant_id: must be ObjectId or valid string")
    
    @field_serializer("meta", when_used="json")
    def serialize_meta(self, v,info):
        """Recursively convert ObjectId/date inside meta to JSON-safe strings."""
        return normalize_bson(v),
    

    def compute_totals(self) -> None:
        """Manually recompute subtotal, tax, and total."""
        self.subtotal_amount = round(sum(i.amount for i in self.line_items), 2)
        self.total_amount = round(self.subtotal_amount + (self.tax_amount or 0.0), 2)
        self.balance_amount = round(self.total_amount - self.effective_paid, 2)

    def mark_paid(self, payment_date: Optional[datetime] = None) -> None:
        """Helper to mark invoice as paid."""
        self.status = "paid"
        self.payment_date = payment_date or datetime.utcnow()
        self.balance_amount = 0.0
        self.effective_paid = self.total_amount

    def mark_partial(self, amount_paid: float) -> None:
        """Mark invoice as partially paid."""
        self.status = "partial"
        self.total_paid = round(amount_paid, 2)
        self.effective_paid = min(self.total_amount, self.total_paid)
        self.balance_amount = round(self.total_amount - self.effective_paid, 2)

    def mark_cancelled(self) -> None:
        """Cancel invoice without deleting."""
        self.status = "cancelled"

    def as_dict(self) -> dict:
        """Return clean dict for Mongo inserts/updates."""
        return self.model_dump(by_alias=True, exclude_none=True)