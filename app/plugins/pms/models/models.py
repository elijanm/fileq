from datetime import datetime, timezone
from typing import Optional, List,Literal,Dict,Union
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator, conlist, confloat
from dataclasses import dataclass
from bson import ObjectId
from enum import Enum
from uuid import uuid4
from core.MongoORJSONResponse import PyObjectId
# ============================================
# Enums
# ============================================

class UtilityType(str, Enum):
    """Utility types available"""
    # GYM = "gym"
    # POOL = "pool"
    # PARKING = "parking"
    # WATER = "water"
    # ELECTRICITY = "electricity"
    # INTERNET = "internet"
    # OTHER = "other"


class BillingFrequency(str, Enum):
    """Billing frequency options"""
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    PER_USE = "per-use"
    ONE_TIME = "one-time"


class BillableTo(str, Enum):
    """Who is responsible for payment"""
    TENANT = "tenant"
    LANDLORD = "landlord"
    SHARED = "shared"


class OwnershipType(str, Enum):
    """Property ownership types"""
    FREEHOLD = "freehold"
    LEASEHOLD = "leasehold"
    CO_OPERATIVE = "co-operative"
    CONDOMINIUM = "condominium"


class Currency(str, Enum):
    """Supported currencies"""
    KES = "KES"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    ZAR = "ZAR"
    NGN = "NGN"
    GHS = "GHS"


class RentCycle(str, Enum):
    """Default rent billing cycles"""
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    BIANNUAL = "biannual"
    ANNUAL = "annual"



# Response Models
class PropertySummary(BaseModel):
    id: str = Field(alias="_id")
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    property_type: Optional[str] = Field(None, alias="propertyType")
    total_units: int = Field(alias="totalUnits")
    occupied_units: int = Field(alias="occupiedUnits")
    vacant_units: int = Field(alias="vacantUnits")
    occupancy_rate: float = Field(alias="occupancyRate")
    currency: str = Field(default="KES")
    custom_image: Optional[str] = Field(None, alias="customImage")
    created_at: Optional[str] = Field(None, alias="createdAt")

class UnitMetrics(BaseModel):
    total: int = Field(alias="total")
    occupied: int = Field(alias="occupied")
    vacant: int = Field(alias="vacant")
    occupancy_rate: float = Field(alias="occupancyRate")

class TenantMetrics(BaseModel):
    total_tenants: int = Field(alias="totalTenants")
    active_leases: int = Field(alias="activeLeases")
    expiring_soon: int = Field(alias="expiringSoon")
    paid_this_month: int = Field(alias="paidThisMonth")
    overdue_this_month: int = Field(alias="overdueThisMonth")

class FinancialMetrics(BaseModel):
    potential_monthly_rent: float = Field(alias="potentialMonthlyRent")
    expected_monthly_rent: float = Field(alias="expectedMonthlyRent")
    collected_rent: float = Field(alias="collectedRent")
    total_overdue: float = Field(alias="totalOverdue")
    collection_rate: float = Field(alias="collectionRate")

class PropertyMetrics(BaseModel):
    units: UnitMetrics
    tenants: TenantMetrics
    financial: FinancialMetrics



class TenantListItem(BaseModel):
    id: str = Field(alias="_id")
    full_name: str = Field(alias="fullName")
    email: Optional[str] = None
    phone: Optional[str] = None
    occupation: Optional[str] = None
    avatar:Optional[str] = None
    unit_number: str = Field(alias="unitNumber")
    unit_name: str = Field(alias="unitName")
    unit_type: Optional[str] = Field(None, alias="unitType")
    rent_amount: float = Field(alias="rentAmount")
    deposit_amount: float = Field(alias="depositAmount")
    service_charge: float = Field(alias="serviceCharge")
    lease_status: str = Field(alias="leaseStatus")
    lease_start: Optional[str] = Field(None, alias="leaseStart")
    lease_end: Optional[str] = Field(None, alias="leaseEnd")
    last_payment_date: Optional[str] = Field(None, alias="lastPaymentDate")
    last_payment_amount: Optional[float] = Field(None, alias="lastPaymentAmount")
    total_paid: float = Field(alias="totalPaid")
    outstanding_balance: float = Field(alias="outstandingBalance")
    payment_status: float = Field(alias="outstandingPaymentStatus")



class UtilityUnit(BaseModel):
    id: str
    name: str
    area_sq_ft: Optional[float] = Field(None, alias="areaSqFt")
    tenants_count: Optional[int] = Field(None, alias="tenantsCount")
    usage: Optional[Dict[str, float]] = None  # {utilityId: usageValue}


class UnitType(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    unit_type: str
    count: int
    rent_amount: float = 0.0
    deposit_amount: float = 0.0


class WingConfig(BaseModel):
    layout_type: Literal['single', 'two-wing', 'four-wing', 'corridor']
    wings: List[str]
    units_per_wing_per_floor: Optional[int] = Field(None, alias="units_per_wing_per_floor")


class FloorConfig(BaseModel):
    floor_number: int
    floor_name: str
    units: List[UnitType]


class WingFloorConfig(BaseModel):
    wing_name: str
    floors: List[FloorConfig]





class MeterReading(BaseModel):
    unit_id: Optional[str] = Field(None, alias="unitId")
    previous_reading: float = Field(alias="previousReading")
    current_reading: float = Field(alias="currentReading")
    usage: Optional[float] = None
    reading_date: str = Field(alias="readingDate")  # ISO date string
    billed: Optional[bool] = False


class CustomWeights(BaseModel):
    id:Optional[str]= Field(None,alias="id")
    unit_id: Optional[str] = Field(None,alias="unitId")
    weight: float
# ============================================
# Sub-Models
# ============================================
@dataclass
class IoTInfo:
    enabled: bool = False
    device_ref: Optional[str] = None
    device_type: Optional[Literal['power_meter', 'water_meter', 'gas_meter', 'parking_sensor']] = None
    firmware_version: Optional[str] = None
    network: Optional[Literal['wifi', 'ethernet', 'lorawan', 'zigbee']] = None
    last_sync: Optional[datetime] = None
    sync_interval_minutes: int = 15
    last_reading_value: Optional[float] = None
    last_reading_timestamp: Optional[datetime] = None
    reading_unit: Optional[str] = None
    cumulative_usage: float = 0.0
    baseline_usage: float = 0.0
    reading_source: Optional[Literal['iot', 'manual', 'imported']] = None
    supports_remote_shutdown: bool = False
    control_enabled: bool = False
    control_topic: Optional[str] = None
    data_topic: Optional[str] = None
    battery_level: Optional[float] = None
    signal_strength: Optional[int] = None
    status: Optional[Literal['online', 'offline', 'error']] = 'offline'
    last_error: Optional[str] = None
class TenantLandlordSplit(BaseModel):
    landlord: int = Field(..., ge=0, description="Landlord share ratio")
    tenant: int = Field(..., ge=0, description="Tenant share ratio")

    @field_validator("*", mode="after")
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError("Share ratio values must be non-negative.")
        return v


class CommonUtilityChargePolicy(BaseModel):
    """Defines how a property-level utility cost is shared between tenants and landlord."""

    enabled: bool = Field(
        True, description="Whether the cost-sharing scheme is active"
    )

    shared_cost_distribution: Literal["equal", "weighted", "hybrid"] = Field(
        "equal",
        alias="sharedCostDistribution",
        description="Distribution method (equal, weighted, or hybrid)",
    )

    absorb_vacant_share: bool = Field(
        True,
        alias="absorbVacantShare",
        description="Whether landlord absorbs cost for vacant units",
    )

    vacancy_absorption_threshold: confloat(ge=0, le=1) = Field(
        0.5,
        alias="vacancyAbsorptionThreshold",
        description="Occupancy ratio below which landlord covers remaining cost",
    )

    tenant_landlord_split: TenantLandlordSplit = Field(
        ..., alias="tenantLandlordSplit", description="Split ratio between landlord and tenants"
    )

    weighting_factor: Optional[conlist(str, min_length=1)] = Field(
        default_factory=lambda: ["sizeSqft"],
        alias="weightingFactor",
        description="List of fields to use for weighted distribution",
    )

    rounding_mode: Literal["nearest", "up", "down"] = Field(
        "nearest", alias="roundingMode", description="How per-tenant charges are rounded"
    )

    min_charge_per_tenant: Optional[float] = Field(
        0.0, alias="minChargePerTenant", description="Minimum charge allowed per tenant"
    )

    max_charge_per_tenant: Optional[float] = Field(
        None, alias="maxChargePerTenant", description="Maximum charge allowed per tenant"
    )

    apply_to: Literal["property", "unit-group", "tenant-class"] = Field(
        "property", alias="applyTo", description="Target level this scheme applies to"
    )

    effective_date: Optional[datetime] = Field(
        None, alias="effectiveDate", description="Effective start date for this policy"
    )

    # ---------- Validators ----------
    @field_validator("effective_date", mode="before")
    def parse_date(cls, v):
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v).date()
            except ValueError:
                raise ValueError("effectiveDate must be a valid ISO date (YYYY-MM-DD)")
        return v

    @field_validator("tenant_landlord_split")
    def validate_split(cls, v: TenantLandlordSplit):
        total = v.landlord + v.tenant
        if total <= 0:
            raise ValueError("Sum of landlord and tenant ratios must be > 0")
        return v

    model_config = {
        "populate_by_name": True,
        "use_enum_values": True,
        "json_schema_extra": {
            "example": {
                "enabled": True,
                "sharedCostDistribution": "equal",
                "absorbVacantShare": True,
                "vacancyAbsorptionThreshold": 0.5,
                "tenantLandlordSplit": {"landlord": 3, "tenant": 7},
                "weightingFactor": ["sizeSqft"],
                "roundingMode": "nearest",
                "minChargePerTenant": 100,
                "maxChargePerTenant": None,
                "applyTo": "property",
                "effectiveDate": "2025-01-01",
            }
        },
    }
class Utility(BaseModel):
    """Utility model for property amenities"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Swimming Pool Access",
                "type": "pool",
                "billingType": "monthly",
                "billableTo": "tenant",
                "amount": 50.00,
                "description": "Access to heated pool and jacuzzi"
            }
        }
    )

    # id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=100, description="Utility name")
    description: Optional[str] = Field(None, max_length=500, description="Additional details")
    type: Literal['optional', 'mandatory'] = Field(..., description="Type of utility")
    is_active: bool = Field(default=True, alias="isActive", description="Whether utility is currently active")
    payment_type: Optional[Literal['free', 'billable']] = Field(None, alias="paymentType")
    billing_frequency: Optional[BillingFrequency] = Field(None, alias="billingFrequency", description="How often to bill")
    billing_basis: Optional[Literal['metered', 'monthly']] = Field(None, alias="billingBasis")
    billing_level: Optional[Literal['unit', 'property']] = Field(None, alias="billingLevel")
    common_utility_charge_policy:Optional[CommonUtilityChargePolicy]=None
    shared: Optional[bool] = None
    shared_cost_type: Optional[Literal['equal', 'weighted']] = Field(None, alias="sharedCostType")
    shared_units: Optional[List[str]] = Field(None, alias="sharedUnits")
    rate: Optional[float] = None
    unit_of_measure: Optional[str] = Field(None, alias="unitOfMeasure")
    bill_to: Optional[Literal['tenant', 'landlord']] = Field(None, alias="billTo")
    include_in_invoice: Optional[bool] = Field(None, alias="includeInInvoice")
    weighting_factor: Optional[str] = Field(None, alias="weightingFactor")
    custom_weights: Optional[List[CustomWeights]] = Field(None, alias="customWeights")
    description: Optional[str] = None
    property_meter_reading: Optional[MeterReading] = Field(None, alias="propertyMeterReading")
    is_deposit_required: Optional[bool] = Field(None, alias="isDepositRequired")
    deposit_amount: Optional[float] = Field(None, alias="depositAmount")
    is_refundable: Optional[bool] = Field(None, alias="isRefundable")

    # MeteredUtility
    has_meter: bool = Field(alias="hasMeter")
    meter_readings: Optional[List[MeterReading]] = None
    iot_devices:List[IoTInfo] = Field(
        default_factory=list,
        alias="iotDevices",
        description="List of associated IoT devices"
    )
  
class MeteredUtility(Utility):
    has_meter: bool = Field(alias="hasMeter")
    unit_of_measure:  Optional[str] = Field(None, alias="unitOfMeasure")
    readings: Optional[List[MeterReading]] = None


class ParkingSlot(BaseModel):
    id: str
    number: str
    assigned_unit: Optional[str] = Field(None, alias="assignedUnit")
    occupied: Optional[bool] = None
    reserved: Optional[bool] = None


class ParkingRule(BaseModel):
    mode: Literal['assigned', 'free-style', 'capped']
    slots_per_unit: Optional[int] = Field(None, alias="slotsPerUnit")
    max_slots_per_unit: Optional[int] = Field(None, alias="maxSlotsPerUnit")
    free_slots: Optional[int] = Field(None, alias="freeSlots")
    extra_slot_rate: Optional[float] = Field(None, alias="extraSlotRate")
    total_slots: Optional[int] = Field(None, alias="totalSlots")
    allow_guest_parking: Optional[bool] = Field(None, alias="allowGuestParking")


class ParkingUtility(Utility):
    parking_rule: Optional[ParkingRule] = Field(alias="parkingRule")
    slots: Optional[List[ParkingSlot]] = None
class UnitListItem(BaseModel):
    id: str = Field(alias="_id")
    unit_number: str = Field(alias="unitNumber")
    unit_name: str = Field(alias="unitName")
    unit_type: str = Field(alias="unitType")
    floor: int
    wing: Optional[str] = None
    bedrooms: int
    bathrooms: int
    size_sqft: Optional[float] = Field(None, alias="sizeSqft")
    size_sqm: Optional[float] = Field(None, alias="sizeSqm")
    rent_amount: float = Field(alias="rentAmount")
    deposit_amount: Optional[float] = Field(None, alias="depositAmount")
    service_charge: Optional[float] = Field(None, alias="serviceCharge")
    status: str  # available, occupied, maintenance
    is_occupied: bool = Field(alias="isOccupied")
    setup_done:bool=Field(False,alias="setupDone")
    utilities:Optional[List[Utility]] =None
    furnishing_status: Optional[str] = Field(None, alias="furnishingStatus")
    tenant_id: Optional[str] = Field(None, alias="tenantId")
    tenant_name: Optional[str] = Field(None, alias="tenantName")
    lease_start: Optional[str] = Field(None, alias="leaseStart")
    lease_end: Optional[str] = Field(None, alias="leaseEnd")
    rent_status: Optional[str] = Field(None, alias="rentStatus")  # paid, pending, overdue
    has_balcony: bool = Field(alias="hasBalcony")
    has_parking: bool = Field(alias="hasParking")
    parking_spots: int = Field(default=0, alias="parkingSpots")
class PropertyDetailResponse(BaseModel):
    property: PropertySummary
    units: list[UnitListItem]
    tenants: list[TenantListItem]
    metrics: PropertyMetrics
    pagination: dict
class GalleryImage(BaseModel):
    """Gallery image with tags"""
    model_config = ConfigDict(populate_by_name=True)

    url: str = Field(..., description="Image URL or base64 data")
    tags: List[str] = Field(default_factory=list, description="Image tags for categorization")
    caption: Optional[str] = Field(None, max_length=200, description="Image caption")
    uploaded_at: datetime = Field(default_factory=datetime.utcnow, alias="uploadedAt")
    is_primary: bool = Field(default=False, alias="isPrimary", description="Primary property image")


class MpesaApiConfig(BaseModel):
    """M-Pesa API configuration"""
    enabled: bool = Field(default=False)
    key: Optional[str] = Field(None, description="Consumer Key")
    secret: Optional[str] = Field(None, description="Consumer Secret")
    shortcode: Optional[str] = Field(None, description="Business shortcode")
    passkey: Optional[str] = Field(None, description="Lipa Na M-Pesa passkey")
    environment: str = Field(default="sandbox", description="sandbox or production")

    @field_validator('key', 'secret')
    @classmethod
    def validate_credentials(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('API credentials required when M-Pesa is enabled')
        return v
class MpesaTillConfig(BaseModel):
    """M-Pesa API configuration"""
    enabled: bool = Field(default=False)
    till_no: Optional[str] = Field(None, description="M-Pesa Till Numbery")

    @field_validator('till_no')
    @classmethod
    def validate_credentials(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('Till Number required when M-Pesa Till is enabled')
        return v
class MpesaPaybillConfig(BaseModel):
    """M-Pesa API configuration"""
    enabled: bool = Field(default=False)
    paybill_no: Optional[str] = Field(None, description="M-Pesa Paybill Number",max_length=20)
    account: Optional[str] = Field(None, description="Account Pattern",max_length=20)

    @field_validator('paybill_no', 'account')
    @classmethod
    def validate_credentials(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('Paybill number and account pattern required when enabled')
        return v
class BankConfig(BaseModel):
    """M-Pesa API configuration"""
    enabled: bool = Field(default=False)
    account_name: Optional[str] = Field(None, description="Account Number",max_length=20)
    account_no: Optional[str] = Field(None, description="Account No",max_length=20)
    branch: Optional[str] = Field(None, description="Account Branch",max_length=20)
    ref: Optional[str] = Field("{unit#}", description="Account REF",max_length=20)

    @field_validator('account_name', 'account_no','branch','ref')
    @classmethod
    def validate_credentials(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('All account information required when enabled')
        return v
class MpesaSyncConfig(BaseModel):
    """M-Pesa auto-sync configuration"""
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = Field(default=False)
    sync_interval: int = Field(
        default=5, 
        ge=1, 
        le=60, 
        alias="syncInterval", 
        description="Sync interval in minutes"
    )


class PaymentIntegrations(BaseModel):
    """Payment integration settings"""
    model_config = ConfigDict(populate_by_name=True)

    mpesa_api: MpesaApiConfig = Field(default_factory=MpesaApiConfig, alias="mpesaApi")
    mpesa_sync: MpesaSyncConfig = Field(default_factory=MpesaSyncConfig, alias="mpesaSync")
    till_no: MpesaTillConfig = Field(default_factory=MpesaTillConfig, alias="tillNo")
    paybill_no: MpesaPaybillConfig = Field(default_factory=MpesaPaybillConfig, alias="paybillNo")
    bank_info: BankConfig = Field(default_factory=BankConfig, alias="bankInfo")
   
    @field_validator('till_no', 'paybill_no', mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if v == '':
            return None
        return v


class SMSIntegration(BaseModel):
    """SMS gateway integration"""
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = Field(default=False)
    gateway: Optional[str] = Field(None, description="SMS gateway provider")
    api_key: Optional[str] = Field(None, alias="apiKey", description="Gateway API key")
    sender_id: Optional[str] = Field(None, alias="senderId", max_length=11, description="SMS Sender ID")

    
    @field_validator('gateway', 'api_key')
    @classmethod
    def validate_sms_config(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('Gateway and API key required when SMS is enabled')
        return v


class EmailIntegration(BaseModel):
    """Email configuration"""
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = Field(default=False)
    smtp: Optional[str] = Field(None, description="SMTP server address")
    port: Optional[int] = Field(None, ge=1, le=65535, description="SMTP port")
    username: Optional[str] = Field(None, description="SMTP username")
    password: Optional[str] = Field(None, description="SMTP password")
    use_tls: bool = Field(default=True, alias="useTls", description="Use TLS encryption")
    from_email: Optional[EmailStr] = Field(None, alias="fromEmail", description="Default sender email")
    
    @field_validator('port',mode='before')
    @classmethod
    def empty_string_to_none(cls, v):
        if v == '':
            return None
        return v
    @field_validator('smtp', 'port', 'username', 'password')
    @classmethod
    def validate_email_config(cls, v, info):
        if info.data.get('enabled') and not v:
            raise ValueError('Complete SMTP configuration required when email is enabled')
        return v


class PropertyIntegrations(BaseModel):
    """All property integrations"""
    payments: PaymentIntegrations = Field(default_factory=PaymentIntegrations)
    sms: SMSIntegration = Field(default_factory=SMSIntegration)
    email: EmailIntegration = Field(default_factory=EmailIntegration)
    
    # @field_validator("*", mode="before")
    # @classmethod
    # def empty_string_to_default(cls, v):
    #     if v in ("", None):
    #         return {}
    #     return v


class Location(BaseModel):
    """Property location details"""
    model_config = ConfigDict(populate_by_name=True)

    address: str = Field(..., min_length=1, max_length=500)
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=100)
    country: Optional[str] = Field(None, max_length=100)
    postal_code: Optional[str] = Field(None, alias="postalCode", max_length=20)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
class Wing(BaseModel):
    """A single building wing"""
    name: str = Field(..., description="Human-readable name of the wing, e.g., East or West")
    code: str = Field(..., description="Short code for the wing, e.g., E or W")
    units_per_floor: int = Field(..., ge=1, description="Number of units per floor in this wing")

class WingLayout(BaseModel):
    """Layout configuration for property wings"""
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = Field(default=False, description="Whether wing layout is active")
    type: Optional[Literal["two-wing", "four-wing", "corridor"]] = Field(
        None, description="Layout type"
    )
    wings: List[Wing] = Field(default_factory=list, description="List of wings in this layout")

    # 👇 allow empty string or None for wings (e.g. from frontend)
    @field_validator("wings", mode="before")
    @classmethod
    def empty_string_to_default(cls, v):
        if v in ("", None):
            return []
        return v
class BillingCycleConfig(BaseModel):
    enabled: bool = True
    prep_start_day: int = Field(25, ge=1, le=31, description="Day of month to start preparing invoices")
    close_day: int = Field(30, ge=1, le=31, description="Day of month to finalize and lock invoice data")
    issue_day: int = Field(1, ge=1, le=31, description="Day of month to issue invoices")
    due_day: Optional[int] = Field(5, ge=1, le=31, description="Optional payment due date after invoice issue")
    auto_generate_invoices: bool = True
    allow_manual_review: bool = True

# ============================================
# Main Property Models
# ============================================


# ===============================================================
# CORE MODELS
# ===============================================================
class Clause(BaseModel):
    title: str
    description: str
    mandatory: bool = True
    
class TenantSnapshot(BaseModel):
    """Embed tenant details at the time of contract signing (immutable snapshot)."""
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    id_number: Optional[str] = Field("National ID", alias="idNumber")
    id_type: Optional[str] = Field("National ID Type", alias="idType")
    postal_address: Optional[str] = Field(None, alias="postalAddress")
    location: Optional[str] = Field(None, alias="location")
    
    
    model_config = ConfigDict(populate_by_name=True, by_alias=True)

class DepositTransaction(BaseModel):
    """Each deposit payment entry (supports staggered or split payments)."""
    # date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    amount: float
    method: Optional[str] = None
    reference: Optional[str] = None
    note: Optional[str] = None
    
class ContractCreate(BaseModel):
   
    property_id: str
    unit_id: str
    tenant_details: Optional[TenantSnapshot] = None
    start_date: datetime
    end_date: datetime
    rent_amount: float
    deposit_amount: float
    deposit_paid: float = 0.0  # cumulative
    deposit_balance: float = 0.0  # auto-calculated = deposit_amount - deposit_paid
    deposit_transactions: List[DepositTransaction] = Field(default_factory=list)
    clauses: list[Clause] = Field(default_factory=list)
    
class ContractSignRequest(BaseModel):
    role: str = Field(..., description="Role of signer: 'tenant' or 'landlord'")
    signature: str = Field(..., description="Base64-encoded PNG signature image")
       
class Contract(ContractCreate):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    tenant_id: str
    status: str = "pending"  # pending, active, signed, completed
    tenant_signature: Optional[str] = None  # base64 or file path
    landlord_signature: Optional[str] = None
    deposit_paid:Optional[bool] = False
    deposit_balance:Optional[float] = 0.00
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LeaseTerms(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)
     
    start_date: datetime = Field(alias="startDate")
    end_date: datetime = Field(alias="endDate")
    rent_amount: float = Field(alias="rentAmount")
    deposit_amount: float = Field(alias="depositAmount")
    rent_cycle: str = Field(default="monthly", alias="rentCycle")
    payment_due_day: int = Field(default=1, alias="paymentDueDay")

class FinancialDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=True)
     
    rent_amount: float = Field(alias="rentAmount")
    deposit_amount: float = Field(alias="depositAmount")
    currency: str = Field(default="KES")
    deposit_paid: bool = Field(default=False, alias="depositPaid")
    deposit_paid_date: Optional[datetime] = Field(None, alias="depositPaidDate")
    deposit_paid_amount: float = Field(default=0, alias="depositPaidAmount")

class LeaseCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, by_alias=False)
    
    property_id: str = Field(alias="propertyId")
    units_id: List[str] = Field(default_factory=list,alias="unitIds")
    tenant_id: Optional[str] = Field(None, alias="tenantId")
    tenant_details: TenantSnapshot = Field(alias="tenantDetails")
    lease_terms: LeaseTerms = Field(alias="leaseTerms")
    utilities: List[dict] = Field(default_factory=list)
    financial_details: FinancialDetails = Field(alias="financialDetails")
    clauses: List[Clause] = Field(default_factory=list)
    auto_renew: bool = Field(default=False, alias="autoRenew")
    notice_period_days: int = Field(default=30, alias="noticePeriodDays")
   
class LeaseInDB(LeaseCreate):
     model_config = ConfigDict(populate_by_name=True, by_alias=True)
     
     id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
     status: str = "pending"  # pending, active, signed, completed
     tenant_signature: Optional[str] = None  # base64 or file path
     landlord_signature: Optional[str] = None
     deposit_paid:Optional[bool] = False
     deposit_balance:Optional[float] = 0.00
     # LEASE TERMS (Add these if missing)
     lease_duration_months: Optional[int] = Field(11, alias="leaseDurationMonths")
     renewal_notice_months: Optional[int] = Field(3, alias="renewalNoticeMonths")
     agreement_fee: Optional[float] = Field(2000.00, alias="agreementFee")
     # SIGNATURE TRACKING (Add these)
     tenant_signature_metadata: Optional[Dict] = Field(None, alias="tenantSignatureMetadata")
     landlord_signature_metadata: Optional[Dict] = Field(None, alias="landlordSignatureMetadata")
     tenant_signed_date: Optional[datetime] = Field(None, alias="tenantSignedDate")
     landlord_signed_date: Optional[datetime] = Field(None, alias="landlordSignedDate")
    
    
     created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
     updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
     created_by: Optional[str] = Field(None, alias="createdBy")
     
class Tenant(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    unit_ids: Optional[List[str]] = None
    property_id: Optional[str] = None
    active: bool = True
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    credit_balance: float = 0.0

class UnitType(str, Enum):
    """Unit/Room types"""
    STUDIO = "studio"
    ONE_BEDROOM = "1-bedroom"
    TWO_BEDROOM = "2-bedroom"
    THREE_BEDROOM = "3-bedroom"
    FOUR_BEDROOM = "4-bedroom"
    PENTHOUSE = "penthouse"
    DUPLEX = "duplex"
    LOFT = "loft"


class UnitStatus(str, Enum):
    """Unit availability status"""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    RESERVED = "reserved"
    UNAVAILABLE = "unavailable"


class FloorPlan(str, Enum):
    """Floor plan types"""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    CUSTOM = "custom"


class FurnishingStatus(str, Enum):
    """Furnishing options"""
    FURNISHED = "furnished"
    SEMI_FURNISHED = "semi-furnished"
    UNFURNISHED = "unfurnished"


class ViewType(str, Enum):
    """Unit view types"""
    CITY = "city"
    OCEAN = "ocean"
    MOUNTAIN = "mountain"
    GARDEN = "garden"
    POOL = "pool"
    STREET = "street"
    COURTYARD = "courtyard"
    NO_VIEW = "no-view"


# ============================================
# Sub-Models
# ============================================

class UnitAmenity(BaseModel):
    """Individual amenity"""
    name: str = Field(..., max_length=100)
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = Field(None, max_length=200)
    is_premium: bool = Field(default=False, alias="isPremium")

    model_config = ConfigDict(populate_by_name=True)


class UnitDimensions(BaseModel):
    """Unit dimensions and measurements"""
    size_sqft: float = Field(..., gt=0, alias="sizeSqft", description="Size in square feet")
    size_sqm: Optional[float] = Field(None, gt=0, alias="sizeSqm", description="Size in square meters")
    ceiling_height: Optional[float] = Field(None, gt=0, alias="ceilingHeight", description="Ceiling height in feet")
    balcony_sqft: Optional[float] = Field(None, ge=0, alias="balconySqft", description="Balcony size")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator('size_sqm', mode='before')
    @classmethod
    def calculate_sqm(cls, v, info):
        """Auto-calculate sqm from sqft if not provided"""
        if v is None and info.data.get('size_sqft'):
            return info.data['size_sqft'] * 0.092903
        return v
class UnitUtility(BaseModel):
    """Utility charges for the unit"""
    utility_name: str = Field(..., alias="utilityName", max_length=100)
    charge_type: str = Field(..., alias="chargeType", description="fixed, metered, included")
    amount: Optional[float] = Field(None, ge=0, description="Fixed amount if applicable")
    is_included: bool = Field(default=False, alias="isIncluded", description="Included in rent")

    model_config = ConfigDict(populate_by_name=True)


class MaintenanceRecord(BaseModel):
    """Maintenance history"""
    date: datetime
    type: str = Field(..., max_length=50, description="repair, inspection, upgrade")
    description: str = Field(..., max_length=500)
    cost: Optional[float] = Field(None, ge=0)
    performed_by: Optional[str] = Field(None, alias="performedBy", max_length=200)
    status: str = Field(default="completed", description="pending, in-progress, completed")

    model_config = ConfigDict(populate_by_name=True)
    
# ============================================
# Main Unit Models
# ============================================

class UnitBase(BaseModel):
    """Base unit model with common fields"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True
    )

    # Property Reference
    property_id: str = Field(..., alias="propertyId", description="Reference to property")
    
    # Basic Info
    unit_number: str = Field(..., alias="unitNumber", min_length=1, max_length=20, description="Unit number (e.g., 101, A-5)")
    unit_name: Optional[str] = Field(None, alias="unitName", max_length=100, description="Optional unit name")
    unit_type: UnitType = Field(..., alias="unitType", description="Type of unit")
    floor: int = Field(..., ge=0, description="Floor number (0 for ground)")
    floor_plan: FloorPlan = Field(default=FloorPlan.A, alias="floorPlan")
    wing: Optional[str] = Field(None, description="A, B, East, West, North, South")
    section: Optional[str] = Field(None, description="Corner, Center, End")
    position_in_wing: int = Field(..., description="Position within the wing")
    is_corner_unit: bool = Field(default=False)
    is_end_unit: bool =  Field(default=False)
    facing_direction: Optional[str] =  Field(default=False)
    # Room Details
    bedrooms: int = Field(..., ge=0, le=20, description="Number of bedrooms")
    bathrooms: float = Field(..., ge=0, le=20, description="Number of bathrooms (0.5 for half bath)")
    
    # Size & Dimensions
    size_sqft: float = Field(..., gt=0, alias="sizeSqft", description="Size in square feet")
    size_sqm: Optional[float] = Field(None, gt=0, alias="sizeSqm", description="Size in square meters")
    
    # Financial
    rent_amount: float = Field(..., gt=0, alias="rentAmount", description="Monthly rent amount")
    deposit_amount: Optional[float] = Field(None, ge=0, alias="depositAmount", description="Security deposit")
    service_charge: Optional[float] = Field(None, ge=0, alias="serviceCharge", description="Monthly service charge")
    
    # Status
    status: UnitStatus = Field(default=UnitStatus.AVAILABLE, description="Current unit status")
    is_occupied: bool = Field(default=False, alias="isOccupied")
    utilities:Optional[List[Utility]]=None
    furnishing_status: FurnishingStatus = Field(default=FurnishingStatus.UNFURNISHED, alias="furnishingStatus")
    
    # Features
    description: Optional[str] = Field(None, max_length=2000, description="Unit description")
    amenities: List[str] = Field(default_factory=list, description="List of amenities")
    features: List[str] = Field(default_factory=list, description="Special features")
    view_type: Optional[ViewType] = Field(None, alias="viewType")
    
    # Additional Details
    has_balcony: bool = Field(default=False, alias="hasBalcony")
    has_parking: bool = Field(default=False, alias="hasParking")
    parking_spots: int = Field(default=0, ge=0, alias="parkingSpots", description="Number of parking spots")
    pet_friendly: bool = Field(default=False, alias="petFriendly")
    
    # Lease Info (if occupied)
    current_tenant_id: Optional[str] = Field(None, alias="currentTenantId")
    lease_start_date: Optional[datetime] = Field(None, alias="leaseStartDate")
    lease_end_date: Optional[datetime] = Field(None, alias="leaseEndDate")
    
    # Media
    images: List[str] = Field(default_factory=list, description="Image URLs")
    floor_plan_image: Optional[str] = Field(None, alias="floorPlanImage", description="Floor plan image URL")
    virtual_tour_url: Optional[str] = Field(None, alias="virtualTourUrl", description="360° tour URL")

    @field_validator('size_sqm')
    @classmethod
    def calculate_sqm(cls, v, info):
        """Auto-calculate sqm from sqft if not provided"""
        if v is None and info.data.get('size_sqft'):
            return round(info.data['size_sqft'] * 0.092903, 2)
        return v

    @field_validator('lease_end_date')
    @classmethod
    def validate_lease_dates(cls, v, info):
        """Ensure lease end date is after start date"""
        start_date = info.data.get('lease_start_date')
        if v and start_date and v <= start_date:
            raise ValueError('Lease end date must be after start date')
        return v


class UnitCreate(UnitBase):
    """Model for creating a new unit"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "propertyId": "507f1f77bcf86cd799439011",
                "unitNumber": "203",
                "unitType": "2-bedroom",
                "floor": 2,
                "floorPlan": "B",
                "bedrooms": 2,
                "bathrooms": 2,
                "sizeSqft": 950,
                "rentAmount": 1800,
                "depositAmount": 1800,
                "status": "available",
                "furnishingStatus": "unfurnished",
                "description": "Spacious 2-bedroom apartment with city views",
                "amenities": ["Air Conditioning", "Balcony", "Dishwasher"],
                "hasBalcony": True,
                "hasParking": True,
                "parkingSpots": 1,
                "petFriendly": False
            }
        }
    )


class UnitUpdate(BaseModel):
    """Model for updating a unit (all fields optional)"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True
    )

    unit_number: Optional[str] = Field(None, alias="unitNumber", min_length=1, max_length=20)
    unit_name: Optional[str] = Field(None, alias="unitName", max_length=100)
    unit_type: Optional[UnitType] = Field(None, alias="unitType")
    floor: Optional[int] = Field(None, ge=0)
    floor_plan: Optional[FloorPlan] = Field(None, alias="floorPlan")
    bedrooms: Optional[int] = Field(None, ge=0, le=20)
    bathrooms: Optional[float] = Field(None, ge=0, le=20)
    size_sqft: Optional[float] = Field(None, gt=0, alias="sizeSqft")
    size_sqm: Optional[float] = Field(None, gt=0, alias="sizeSqm")
    rent_amount: Optional[float] = Field(None, gt=0, alias="rentAmount")
    deposit_amount: Optional[float] = Field(None, ge=0, alias="depositAmount")
    service_charge: Optional[float] = Field(None, ge=0, alias="serviceCharge")
    status: Optional[UnitStatus] = None
    is_occupied: Optional[bool] = Field(None, alias="isOccupied")
    furnishing_status: Optional[FurnishingStatus] = Field(None, alias="furnishingStatus")
    description: Optional[str] = Field(None, max_length=2000)
    amenities: Optional[List[str]] = None
    features: Optional[List[str]] = None
    view_type: Optional[ViewType] = Field(None, alias="viewType")
    has_balcony: Optional[bool] = Field(None, alias="hasBalcony")
    has_parking: Optional[bool] = Field(None, alias="hasParking")
    parking_spots: Optional[int] = Field(None, ge=0, alias="parkingSpots")
    pet_friendly: Optional[bool] = Field(None, alias="petFriendly")
    current_tenant_id: Optional[str] = Field(None, alias="currentTenantId")
    lease_start_date: Optional[datetime] = Field(None, alias="leaseStartDate")
    lease_end_date: Optional[datetime] = Field(None, alias="leaseEndDate")
    images: Optional[List[str]] = None
    floor_plan_image: Optional[str] = Field(None, alias="floorPlanImage")
    virtual_tour_url: Optional[str] = Field(None, alias="virtualTourUrl")


class UnitInDB(UnitBase):
    """Unit model as stored in database"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True
    )

    id: str = Field(..., alias="_id", description="Unit ID")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")
    created_by: Optional[str] = Field(None, alias="createdBy")
    last_modified_by: Optional[str] = Field(None, alias="lastModifiedBy")
    
    # Additional tracking
    is_active: bool = Field(default=True, alias="isActive")
    last_inspection_date: Optional[datetime] = Field(None, alias="lastInspectionDate")
    next_inspection_date: Optional[datetime] = Field(None, alias="nextInspectionDate")
    maintenance_history: List[MaintenanceRecord] = Field(default_factory=list, alias="maintenanceHistory")
    
    # Analytics
    total_rent_collected: float = Field(default=0.0, ge=0, alias="totalRentCollected")
    occupancy_duration_days: int = Field(default=0, ge=0, alias="occupancyDurationDays")
    vacancy_duration_days: int = Field(default=0, ge=0, alias="vacancyDurationDays")


class UnitResponse(UnitInDB):
    """Unit model for API responses"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439012",
                "propertyId": "507f1f77bcf86cd799439011",
                "unitNumber": "203",
                "unitType": "2-bedroom",
                "floor": 2,
                "bedrooms": 2,
                "bathrooms": 2,
                "sizeSqft": 950,
                "rentAmount": 1800,
                "status": "occupied",
                "isOccupied": True,
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-15T00:00:00Z"
            }
        }
    )


class UnitListResponse(BaseModel):
    """Response model for unit list"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 100,
                "page": 1,
                "limit": 20,
                "property_id": "507f1f77bcf86cd799439011",
                "units": [
                    {
                        "_id": "507f1f77bcf86cd799439012",
                        "unitNumber": "203",
                        "unitType": "2-bedroom",
                        "rentAmount": 1800,
                        "status": "occupied"
                    }
                ]
            }
        }
    )

    total: int = Field(..., description="Total number of units")
    page: int = Field(default=1, ge=1, description="Current page")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    property_id: Optional[str] = Field(None, alias="propertyId", description="Filter by property")
    units: List[UnitResponse] = Field(..., description="List of units")


class UnitSummary(BaseModel):
    """Summary statistics for units"""
    total_units: int = Field(..., alias="totalUnits")
    available_units: int = Field(..., alias="availableUnits")
    occupied_units: int = Field(..., alias="occupiedUnits")
    maintenance_units: int = Field(..., alias="maintenanceUnits")
    reserved_units: int = Field(..., alias="reservedUnits")
    occupancy_rate: float = Field(..., ge=0, le=100, alias="occupancyRate", description="Percentage")
    average_rent: float = Field(..., ge=0, alias="averageRent")
    total_potential_rent: float = Field(..., ge=0, alias="totalPotentialRent")
    total_actual_rent: float = Field(..., ge=0, alias="totalActualRent")

    model_config = ConfigDict(populate_by_name=True)

# ============================================
# Filter/Query Models
# ============================================

class UnitFilter(BaseModel):
    """Filter parameters for unit queries"""
    property_id: Optional[str] = Field(None, alias="propertyId")
    status: Optional[UnitStatus] = None
    unit_type: Optional[UnitType] = Field(None, alias="unitType")
    min_bedrooms: Optional[int] = Field(None, ge=0, alias="minBedrooms")
    max_bedrooms: Optional[int] = Field(None, ge=0, alias="maxBedrooms")
    min_rent: Optional[float] = Field(None, ge=0, alias="minRent")
    max_rent: Optional[float] = Field(None, ge=0, alias="maxRent")
    floor: Optional[int] = Field(None, ge=0)
    pet_friendly: Optional[bool] = Field(None, alias="petFriendly")
    has_parking: Optional[bool] = Field(None, alias="hasParking")
    furnishing_status: Optional[FurnishingStatus] = Field(None, alias="furnishingStatus")

    model_config = ConfigDict(populate_by_name=True)

    # created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  
class UnitCreate(BaseModel):
    name: str
    price: float
    price_currency:Optional[str] = "KES"
    utilities: List[Utility] = Field(default_factory=list)
    water_meter_base: float = 0.0       # previous/base reading (m³)
    water_meter_current: float = 0.0    # latest reading
  
    
     
class Unit(UnitCreate):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    property_id: str
    tenant_id: Optional[str] = None
    
    occupied: bool = False
    water_meter_base: float = 0.0       # previous/base reading (m³)
    water_meter_current: float = 0.0    # latest reading
    water_rate_per_unit: float = 2.5    # $ per m³ (default)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))



class PropertyBase(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        by_alias=False,
        # by_alias=True
    )

    # id: str = Field(alias="_id")
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    property_type: Optional[Literal['apartment', 'villa', 'single-family', 'commercial', 'mixed','townhouse','studio']] = Field(
        None, alias="propertyType"
    )
    
    owner_name: Optional[str] = Field(None, alias="ownerName")
    owner_id_number: Optional[str] = Field(None, alias="ownerIdNumber")
    owner_id_type: Optional[str] = Field("National ID", alias="ownerIdType")
    
    postal_address: Optional[str] = Field(None, alias="postalAddress")
    city: Optional[str] = None
    
    late_penalty_rate: Optional[int] = Field(10, alias="latePenaltyRate")  # percentage
    bounced_cheque_fee: Optional[float] = Field(3500.00, alias="bouncedChequeFee")
    
    property_tax: Optional[float] = Field(None, alias="propertyTax")
    
    website: Optional[str] = None
    tagline: Optional[str] = None
    
    year_built: Optional[int] = Field(None, alias="yearBuilt")
    location: str
    description: Optional[str] = None
    custom_image: Optional[str] = Field(None, alias="customImage")
    units_total: Optional[int] = Field(0, alias="unitsTotal")
    units_occupied: Optional[int] = Field(0, alias="unitsOccupied")
    occupancy_rate: Optional[float] = Field(0, alias="occupancyRate")
    utilities: Optional[List[Union[Utility, MeteredUtility, ParkingUtility]]] = None
    gallery: Optional[List[GalleryImage]] = None
    logo: Optional[str] = None
    currency: Optional[str] = None
    enable_guest_management: Optional[bool] = Field(None, alias="enableGuestManagement")
    enable_parking_management: Optional[bool] = Field(None, alias="enableParkingManagement")
    default_rent_cycle: Optional[str] = Field(None, alias="defaultRentCycle")
    property_value: Optional[str] = Field(None, alias="propertyValue")
    title_deed_number: Optional[str] = Field(None, alias="titleDeedNumber")
    include_in_invoice: bool = Field(alias="includeInInvoice")
    ownership_type: Optional[str] = Field(None, alias="ownershipType")
    property_tax_number: Optional[str] = Field(None, alias="propertyTaxNumber")
    insurance_provider: Optional[str] = Field(None, alias="insuranceProvider")
    insurance_policy_no: Optional[str] = Field(None, alias="insurancePolicyNo")
    deposit_terms_in_month: Optional[int] = Field(1, alias="depositTermsInMonth")
    integrations: Optional[PropertyIntegrations] = None
    billing_cycle: Optional[BillingCycleConfig] = BillingCycleConfig()
    wing_config: Optional[WingConfig] = Field(None, alias="wingConfig")
    number_of_floors: Optional[int] = Field(None, alias="numberOfFloors")
    floor_config: Optional[List[FloorConfig]] = Field(None, alias="floorConfig")
    wing_floor_config: Optional[List[WingFloorConfig]] = Field(None, alias="wingFloorConfig")
    auto_generate_units: bool = Field(alias="autoGenerateUnits")
    units_share_ditribution: Optional[List[UtilityUnit]] = None
    property_units:Optional[List[UnitListItem]]=None

class PropertyCreate(PropertyBase):
    """Model for creating a new property"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Cecil Homes",
                "phone": "+254700000000",
                "email": "info@cecilhomes.com",
                "location": "Nairobi, Kilimani",
                "description": "Modern apartment complex with state-of-the-art amenities",
                "currency": "KES",
                "defaultRentCycle": "monthly",
                "propertyValue": 50000000,
                "ownershipType": "freehold",
                "titleDeedNumber": "LR NO. 209/12345",
                "enableGuestManagement": True,
                "enableParkingManagement": True,
                "utilities": [
                    {
                        "name": "Gym Access",
                        "type": "gym",
                        "billingType": "monthly",
                        "billableTo": "tenant",
                        "amount": 30.00
                    }
                ]
            }
        }
    )


class PropertyUpdate(BaseModel):
    """Model for updating a property (all fields optional)"""
    model_config = ConfigDict(
        use_enum_values=True,
        populate_by_name=True
    )

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    location: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None, max_length=2000)
    custom_image: Optional[str] = Field(None, alias="customImage")
    logo: Optional[str] = None
    currency: Optional[Currency] = None
    default_rent_cycle: Optional[RentCycle] = Field(None, alias="defaultRentCycle")
    property_value: Optional[float] = Field(None, alias="propertyValue", ge=0)
    ownership_type: Optional[OwnershipType] = Field(None, alias="ownershipType")
    title_deed_number: Optional[str] = Field(None, alias="titleDeedNumber", max_length=100)
    property_tax_number: Optional[str] = Field(None, alias="propertyTaxNumber", max_length=100)
    insurance_provider: Optional[str] = Field(None, alias="insuranceProvider", max_length=200)
    insurance_policy_no: Optional[str] = Field(None, alias="insurancePolicyNo", max_length=100)
    enable_guest_management: Optional[bool] = Field(None, alias="enableGuestManagement")
    enable_parking_management: Optional[bool] = Field(None, alias="enableParkingManagement")
    utilities: Optional[List[Utility]] = None
    gallery: Optional[List[GalleryImage]] = None
    integrations: Optional[PropertyIntegrations] = None


class PropertyInDB(PropertyBase):
    """Property model as stored in database"""
    model_config = ConfigDict(
        use_enum_values=True,
        by_alias=False,
        populate_by_name=True
        
    )

    id: str = Field(..., alias="_id", description="Property ID")
    # id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    

    owner_id:str
    units_total: int = Field(default=0, alias="unitsTotal", ge=0, description="Total number of units")
    units_occupied: int = Field(default=0, alias="unitsOccupied", ge=0, description="Occupied units")
    occupancy_rate: float = Field(default=0.0, alias="occupancyRate", description="Occupancy percentage")
    created_at: datetime = Field(default_factory=datetime.utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=datetime.utcnow, alias="updatedAt")
    created_by: Optional[str] = Field(None, alias="createdBy", description="User who created the property")
    is_active: bool = Field(default=True, alias="isActive", description="Whether property is active")

    @field_validator('occupancy_rate')
    @classmethod
    def calculate_occupancy_rate(cls, v, info):
        """Calculate occupancy rate from units"""
        total = info.data.get('units_total', 0)
        occupied = info.data.get('units_occupied', 0)
        if total > 0:
            rate = (occupied / total) * 100
            return rate
        return  0.0


class PropertyResponse(PropertyInDB):
    """Property model for API responses"""
    model_config = ConfigDict(
        use_enum_values=True,
        by_alias=False,
        # populate_by_name=True,
        json_schema_extra={
            "example": {
                "_id": "507f1f77bcf86cd799439011",
                "name": "Cecil Homes",
                "phone": "+254700000000",
                "email": "info@cecilhomes.com",
                "location": "Nairobi, Kilimani",
                "description": "Modern apartment complex",
                "currency": "KES",
                "defaultRentCycle": "monthly",
                "unitsTotal": 20,
                "unitsOccupied": 15,
                "occupancyRate": "75%",
                "createdAt": "2024-01-01T00:00:00Z",
                "updatedAt": "2024-01-15T00:00:00Z",
                "isActive": True
            }
        }
    )


class PropertyListResponse(BaseModel):
    """Response model for property list"""
    model_config = ConfigDict(
        by_alias=False,
        json_schema_extra={
            "example": {
                "total": 50,
                "page": 1,
                "limit": 10,
                "properties": [
                    {
                        "_id": "507f1f77bcf86cd799439011",
                        "name": "Cecil Homes",
                        "location": "Nairobi, Kilimani",
                        "unitsTotal": 20,
                        "unitsOccupied": 15,
                        "occupancyRate": "75%"
                    }
                ]
            }
        }
    )

    total: int = Field(..., description="Total number of properties")
    page: int = Field(default=1, ge=1, description="Current page number")
    limit: int = Field(default=10, ge=1, le=100, description="Items per page")
    properties: List[PropertyResponse] = Field(..., description="List of properties")


# ===============================================================
# BILLING MODELS
# ===============================================================

# class InvoiceItem(BaseModel):
#     label: str
#     amount: float
#     usage_units: Optional[float] = None
    


# class Invoice(BaseModel):
#     id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
#     tenant_id: str
#     property_id: str
#     units_id: List[str]
#     month: str
#     items: List[InvoiceItem]
#     total: float = 0.0
#     paid_amount: float = 0.0
#     balance: float = 0.0
#     late_fee: float = 0.0
#     status: str = "unpaid"
#     pdf_path: Optional[str] = None
#     created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
#     updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PaymentCreate(BaseModel):
    # id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    # tenant_id: str
    invoice_id: PyObjectId
    amount: float
    method: Optional[str] = None
    pay_date:Optional[datetime] = None
    reference: str
def generate_receipt_ref(prefix="RCPT"):
    import uuid
    date_part = datetime.now().strftime("%y%m%d")  # YYMMDD
    short_uid = uuid.uuid4().hex[:6].upper()       # random 6 chars
    return f"{prefix}-{date_part}-{short_uid}"

class Payment(PaymentCreate):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    tenant_id: PyObjectId
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    receipt_no: str = Field(default_factory=lambda: generate_receipt_ref())


class LedgerEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    tenant_id: str
    entry_type: str  # invoice, payment, fee, adjustment, etc.
    description: str
    debit: float = 0.0
    credit: float = 0.0
    balance_after: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WaterUsage(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    tenant_id: str
    property_id: str
    unit_id: str
    month: str             # e.g. "2025-09"
    units_used: float      # m³ or gallons
    rate_per_unit: float
    amount: float          # computed = units_used * rate_per_unit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ===============================================================
# SERVICE / UTILITY MODELS
# ===============================================================

class MeterUpdate(BaseModel):
    current_reading: float

class Vendor(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    name: str                                   # Company or individual name
    category: Literal[
        "plumbing",
        "electrical",
        "maintenance",
        "cleaning",
        "landscaping",
        "security",
        "other"
    ] = "other"
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None

    # Integration for external vendor system (API)
    external_api_url: Optional[str] = None
    api_key: Optional[str] = None
    last_sync_at: Optional[datetime] = None

    # Relationship tracking
    assigned_tasks: List[str] = []              # IDs of tasks handled by this vendor
    active: bool = True
    rating: Optional[float] = None              # Average from feedback / audits

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
class InvoiceGroup(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    tenant_id: str
    property_id: str
    period_start: str
    period_end: str
    previous_balance: float = 0.0
    new_invoices: List[str] = []
    total_due: float = 0.0

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    unit_id: str
    ticket_id: str
    vendor_id: str
    title: str
    description: str
    status: Literal["open","in_progress","completed","closed"] = "open"
    assigned_to: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expenses: List[str] = []  # expense IDs
    invoice_id: Optional[str] = None

class Expense(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    task_id: Optional[str]
    unit_id: str
    property_id: str
    label: str
    amount: float
    payer: Literal["tenant","landlord"]
    added_to_invoice: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
