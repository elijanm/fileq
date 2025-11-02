import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from bson import ObjectId
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import hashlib
from invoice_manager import AsyncLeaseInvoiceManager

class RealisticPaymentScenarios:
    """Generate realistic payment patterns from January 2025 to now"""
    
    TENANT_TYPES = {
        "excellent": {
            "probability": 0.30,
            "payment_pattern": {"fully_paid": 0.95, "partially_paid": 0.05, "unpaid": 0.00, "overpaid": 0.00}
        },
        "good": {
            "probability": 0.40,
            "payment_pattern": {"fully_paid": 0.85, "partially_paid": 0.10, "unpaid": 0.05, "overpaid": 0.00}
        },
        "struggling": {
            "probability": 0.20,
            "payment_pattern": {"fully_paid": 0.50, "partially_paid": 0.30, "unpaid": 0.20, "overpaid": 0.00}
        },
        "problematic": {
            "probability": 0.08,
            "payment_pattern": {"fully_paid": 0.30, "partially_paid": 0.25, "unpaid": 0.45, "overpaid": 0.00}
        },
        "generous": {
            "probability": 0.02,
            "payment_pattern": {"fully_paid": 0.70, "partially_paid": 0.00, "unpaid": 0.00, "overpaid": 0.30}
        }
    }
    
    @staticmethod
    def assign_tenant_type() -> str:
        rand = random.random()
        cumulative = 0
        
        for tenant_type, config in RealisticPaymentScenarios.TENANT_TYPES.items():
            cumulative += config["probability"]
            if rand <= cumulative:
                return tenant_type
        
        return "good"
    
    @staticmethod
    def get_payment_scenario(tenant_type: str) -> str:
        pattern = RealisticPaymentScenarios.TENANT_TYPES[tenant_type]["payment_pattern"]
        rand = random.random()
        cumulative = 0
        
        for scenario, probability in pattern.items():
            cumulative += probability
            if rand <= cumulative:
                return scenario
        
        return "fully_paid"
    
    @staticmethod
    def generate_scenarios_from_lease_start(lease_start: datetime, move_in_date: Optional[datetime]) -> Tuple[List[str], str, str]:
        """
        Generate payment scenarios from lease/move-in date to now.
        
        Args:
            lease_start: Official lease start date
            move_in_date: Actual move-in date (if different)
            
        Returns:
            Tuple of (scenarios_list, billing_start_month, tenant_type)
        """
        current_date = datetime.now(timezone.utc)
        tenant_type = RealisticPaymentScenarios.assign_tenant_type()
        
        # Determine first billing month
        if move_in_date:
            first_billing_date = move_in_date
        else:
            first_billing_date = lease_start
        
        # Generate month list from first billing to current
        start_year = first_billing_date.year
        start_month = first_billing_date.month
        current_year = current_date.year
        current_month = current_date.month
        
        scenarios = []
        
        year = start_year
        month = start_month
        
        while (year < current_year) or (year == current_year and month <= current_month):
            scenario = RealisticPaymentScenarios.get_payment_scenario(tenant_type)
            scenarios.append(scenario)
            
            month += 1
            if month > 12:
                month = 1
                year += 1
        
        billing_start_month = f"{start_year}-{start_month:02d}"
        
        return scenarios, billing_start_month, tenant_type


class MeteredUtilityTracker:
    """Track metered utility readings and generate line items"""
    
    @staticmethod
    def generate_realistic_reading(
        utility_name: str,
        previous_reading: float,
        is_first_reading: bool = False
    ) -> float:
        """Generate realistic meter reading based on utility type"""
        if is_first_reading:
            if utility_name.lower() == "water":
                return round(random.uniform(100, 500), 2)
            elif utility_name.lower() == "electricity":
                return round(random.uniform(1000, 5000), 2)
            else:
                return round(random.uniform(0, 100), 2)
        
        consumption_ranges = {
            "water": (5, 25),
            "electricity": (100, 400)
        }
        
        utility_key = utility_name.lower()
        min_usage, max_usage = consumption_ranges.get(utility_key, (10, 50))
        
        usage = round(random.uniform(min_usage, max_usage), 2)
        new_reading = previous_reading + usage
        
        return round(new_reading, 2)
    
    @staticmethod
    def create_utility_line_item(
        utility_name: str,
        rate: float,
        previous_reading: float,
        current_reading: float,
        unit_of_measure: str,
        period: str
    ) -> Dict:
        """Create invoice line item for metered utility"""
        usage = current_reading - previous_reading
        amount = usage * rate
        
        return {
            "description": f"{utility_name} - {period}",
            "type": "utility",
            "utility_name": utility_name,
            "quantity": round(usage, 2),
            "unit_price": rate,
            "amount": round(amount, 2),
            "meta": {
                "billing_basis": "metered",
                "previous_reading": previous_reading,
                "current_reading": current_reading,
                "usage": round(usage, 2),
                "unit_of_measure": unit_of_measure,
                "rate": rate,
                "period": period,
                "reading_date": datetime.now(timezone.utc)
            }
        }


class RealisticDataGenerator:
    """Generate realistic test data matching your exact schema"""
    
    KENYAN_NAMES = [
        ("John", "Kamau"), ("Mary", "Wanjiku"), ("Peter", "Omondi"),
        ("Grace", "Achieng"), ("David", "Mutua"), ("Sarah", "Njeri"),
        ("James", "Kipchoge"), ("Lucy", "Wambui"), ("Daniel", "Otieno"),
        ("Faith", "Chebet"), ("Michael", "Karanja"), ("Elizabeth", "Nyambura"),
        ("Patrick", "Mwangi"), ("Anne", "Akinyi"), ("Joseph", "Kiplagat"),
        ("Jane", "Wangari"), ("Samuel", "Odhiambo"), ("Rose", "Chemutai"),
        ("Francis", "Kiprono"), ("Margaret", "Wairimu")
    ]
    
    LOCATIONS = [
        "Westlands", "Kilimani", "South B", "South C", "Lavington",
        "Kileleshwa", "Parklands", "Eastleigh", "Upperhill", "Karen",
        "Runda", "Muthaiga", "Spring Valley", "Riverside", "Ngong Road"
    ]
    
    PROPERTY_TYPES = ["apartment", "townhouse", "villa", "studio"]
    
    def __init__(self, manager: AsyncLeaseInvoiceManager):
        self.manager = manager
        self.db = manager.db
        self.current_date = datetime.now(timezone.utc)
        self.utility_tracker = MeteredUtilityTracker()
        self.meter_readings = {}
    
    def generate_signature(self) -> str:
        """Generate a realistic base64 signature placeholder"""
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    
    def generate_phone(self) -> str:
        """Generate realistic Kenyan phone number"""
        prefixes = ["0701", "0702", "0710", "0711", "0720", "0721", "0722", "0733", "0734", "0740", "0741", "0757", "0790", "0791"]
        return f"{random.choice(prefixes)}{random.randint(100000, 999999)}"
    
    def generate_id_number(self) -> str:
        """Generate realistic Kenyan ID number"""
        return f"{random.randint(10000000, 99999999)}"
    
    def generate_email(self, first_name: str, last_name: str) -> str:
        """Generate realistic email"""
        domains = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
        separators = [".", "_", ""]
        sep = random.choice(separators)
        return f"{first_name.lower()}{sep}{last_name.lower()}{random.randint(1, 999)}@{random.choice(domains)}"
    
    def generate_random_lease_dates(self) -> Tuple[datetime, datetime, Optional[datetime]]:
        """Generate realistic lease dates between January 2025 and now"""
        start_of_year = datetime(2025, 1, 1, tzinfo=timezone.utc)
        days_since_start = (self.current_date - start_of_year).days
        
        if days_since_start > 0:
            random_days = random.randint(0, days_since_start)
            lease_start = start_of_year + timedelta(days=random_days)
        else:
            lease_start = start_of_year
        
        lease_end = lease_start + timedelta(days=365)
        
        move_in_date = None
        if random.random() < 0.3:
            days_early = random.randint(1, 14)
            move_in_date = lease_start - timedelta(days=days_early)
        
        return lease_start, lease_end, move_in_date
    
    def get_meter_reading(self, unit_id: str, utility_name: str, period: str) -> float:
        """Get or generate meter reading for a unit/utility/period"""
        if unit_id not in self.meter_readings:
            self.meter_readings[unit_id] = {}
        
        if utility_name not in self.meter_readings[unit_id]:
            self.meter_readings[unit_id][utility_name] = {}
        
        utility_readings = self.meter_readings[unit_id][utility_name]
        
        if period in utility_readings:
            return utility_readings[period]
        
        periods = sorted(utility_readings.keys())
        
        if not periods:
            reading = self.utility_tracker.generate_realistic_reading(
                utility_name, 0, is_first_reading=True
            )
        else:
            previous_period = periods[-1]
            previous_reading = utility_readings[previous_period]
            reading = self.utility_tracker.generate_realistic_reading(
                utility_name, previous_reading, is_first_reading=False
            )
        
        utility_readings[period] = reading
        return reading
    
    def get_previous_meter_reading(self, unit_id: str, utility_name: str, current_period: str) -> float:
        """Get previous period's meter reading"""
        if unit_id not in self.meter_readings:
            return 0.0
        
        if utility_name not in self.meter_readings[unit_id]:
            return 0.0
        
        utility_readings = self.meter_readings[unit_id][utility_name]
        periods = sorted([p for p in utility_readings.keys() if p < current_period])
        
        if not periods:
            return 0.0
        
        return utility_readings[periods[-1]]
    
    async def clone_property(self, source_property_id: str, num_units: int = 10) -> Dict:
        """Clone a property with realistic data and create units"""
        source = await self.db.properties.find_one({"_id": source_property_id})
        if not source:
            raise ValueError(f"Source property {source_property_id} not found")
        
        property_id = str(ObjectId())
        location = random.choice(self.LOCATIONS)
        property_name = f"{location} {random.choice(['Apartments', 'Residences', 'Court', 'Towers', 'Heights'])}"
        
        property_data = {
            "_id": property_id,
            "name": property_name,
            "phone": self.generate_phone(),
            "email": f"management@{property_name.lower().replace(' ', '')}.co.ke",
            "propertyType": random.choice(self.PROPERTY_TYPES),
            "yearBuilt": random.randint(2010, 2024),
            "location": location,
            "description": f"Modern {property_name} in {location}",
            "customImage": None,
            "unitsTotal": num_units,
            "unitsOccupied": num_units,  # Will be updated later
            "occupancyRate": 100.0,  # Will be updated later
            "utilities": [
                {
                    "name": "Water",
                    "description": None,
                    "type": "mandatory",
                    "isActive": True,
                    "paymentType": "billable",
                    "billingFrequency": "monthly",
                    "billingBasis": "metered",
                    "billingLevel": "unit",
                    "shared": None,
                    "sharedCostType": None,
                    "sharedUnits": None,
                    "rate": round(random.uniform(8.0, 12.0), 2),
                    "unitOfMeasure": "m3",
                    "billTo": "tenant",
                    "includeInInvoice": True,
                    "weightingFactor": None,
                    "customWeights": None,
                    "propertyMeterReading": None,
                    "hasMeter": True,
                    "meter_readings": None,
                    "iotDevices": []
                },
                {
                    "name": "Electricity",
                    "description": None,
                    "type": "mandatory",
                    "isActive": True,
                    "paymentType": "billable",
                    "billingFrequency": "monthly",
                    "billingBasis": "metered",
                    "billingLevel": "unit",
                    "shared": None,
                    "sharedCostType": None,
                    "sharedUnits": None,
                    "rate": round(random.uniform(2.5, 3.5), 2),
                    "unitOfMeasure": "kWh",
                    "billTo": "tenant",
                    "includeInInvoice": True,
                    "weightingFactor": None,
                    "customWeights": None,
                    "propertyMeterReading": None,
                    "hasMeter": True,
                    "meter_readings": None,
                    "iotDevices": []
                },
                {
                    "name": "Garbage Collection",
                    "description": None,
                    "type": "mandatory",
                    "isActive": True,
                    "paymentType": "billable",
                    "billingFrequency": "monthly",
                    "billingBasis": "monthly",
                    "billingLevel": "property",
                    "shared": None,
                    "sharedCostType": None,
                    "sharedUnits": None,
                    "rate": round(random.uniform(400, 600), 2),
                    "unitOfMeasure": None,
                    "billTo": "tenant",
                    "includeInInvoice": True,
                    "weightingFactor": None,
                    "customWeights": None,
                    "propertyMeterReading": None,
                    "hasMeter": False,
                    "meter_readings": None,
                    "iotDevices": []
                }
            ],
            "gallery": [],
            "logo": None,
            "currency": "KES",
            "enableGuestManagement": False,
            "enableParkingManagement": False,
            "defaultRentCycle": "monthly",
            "propertyValue": str(round(random.uniform(5000000, 20000000), 2)),
            "titleDeedNumber": f"LR/{random.randint(1000, 9999)}/{random.randint(100, 999)}",
            "includeInInvoice": True,
            "ownershipType": "freehold",
            "propertyTaxNumber": f"PT{random.randint(100000, 999999)}",
            "insuranceProvider": random.choice(["Jubilee", "CIC", "UAP", "Britam", "APA"]),
            "insurancePolicyNo": f"POL{random.randint(100000, 999999)}",
            "depositTermsInMonth": random.choice([1, 2]),
            "integrations": {
                "payments": {
                    "mpesaApi": {"enabled": False, "key": "", "secret": "", "shortcode": None, "passkey": None, "environment": "sandbox"},
                    "mpesaSync": {"enabled": False, "syncInterval": 5},
                    "tillNo": {"enabled": False, "till_no": ""},
                    "paybillNo": {"enabled": True, "paybill_no": str(random.randint(100000, 999999)), "account": "{unit#}"}
                },
                "sms": {"enabled": False, "gateway": "", "apiKey": "", "senderId": None},
                "email": {"enabled": False, "smtp": "", "port": None, "username": "", "password": "", "useTls": True, "fromEmail": None}
            },
            "billing_cycle": {
                "enabled": True,
                "prep_start_day": 25,
                "close_day": 30,
                "issue_day": 1,
                "due_day": 5,
                "auto_generate_invoices": True,
                "allow_manual_review": True
            },
            "wingConfig": None,
            "numberOfFloors": random.randint(1, 5),
            "floorConfig": [],
            "wingFloorConfig": None,
            "autoGenerateUnits": True,
            "units": [],
            "owner_id": source.get("owner_id", str(ObjectId())),
            "createdAt": self.current_date,
            "updatedAt": self.current_date,
            "createdBy": None,
            "isActive": True,
            "landlord_signature": self.generate_signature()
        }
        
        await self.db.properties.insert_one(property_data)
        print(f"✓ Created property: {property_name} ({property_id})")
        
        unit_ids = await self.create_units(property_id, num_units)
        
        return {
            "property_id": property_id,
            "property_name": property_name,
            "unit_ids": unit_ids,
            "location": location
        }
    
    async def create_units(self, property_id: str, count: int) -> List[str]:
        """Create units matching your exact schema"""
        units = []
        rent_ranges = {
            1: (8000, 12000),
            2: (12000, 18000),
            3: (18000, 25000)
        }
        
        for i in range(count):
            unit_id = str(ObjectId())
            unit_number = f"A-{i+1:02d}"
            floor = (i // 4) + 1
            bedrooms = random.choice([1, 2, 3])
            
            min_rent, max_rent = rent_ranges[bedrooms]
            rent_amount = random.randrange(min_rent, max_rent, 500)
            
            unit_data = {
                "_id": unit_id,
                "property_id": property_id,
                "unitNumber": unit_number,
                "unitName": f"Unit {unit_number}",
                "rentAmount": rent_amount,
                "floor": floor,
                "bedrooms": bedrooms,
                "status": "occupied",
                "created_at": self.current_date,
                "updated_at": self.current_date
            }
            
            await self.db.property_units.insert_one(unit_data)
            units.append(unit_id)
        
        print(f"✓ Created {count} units")
        return units
    
    async def update_property_occupancy(self, property_id: str):
        """Update property occupancy statistics"""
        # Get total units
        total_units = await self.db.property_units.count_documents({"property_id": property_id})
        
        # Get occupied units (units with active leases)
        active_leases = await self.db.property_leases.count_documents({
            "property_id": property_id,
            "status": "signed"
        })
        
        occupied_units = active_leases
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        # Update property
        await self.db.properties.update_one(
            {"_id": property_id},
            {
                "$set": {
                    "unitsTotal": total_units,
                    "unitsOccupied": occupied_units,
                    "occupancyRate": round(occupancy_rate, 2),
                    "updatedAt": datetime.now(timezone.utc)
                }
            }
        )
        
        print(f"    Updated property occupancy: {occupied_units}/{total_units} ({occupancy_rate:.1f}%)")
    
    async def create_lease_with_tenant(
        self,
        property_id: str,
        unit_ids: List[str]
    ) -> Tuple[str, str, datetime, Optional[datetime]]:
        """Create both tenant and lease with realistic dates"""
        
        tenant_id = str(ObjectId())
        lease_id = str(ObjectId())
        
        lease_start, lease_end, move_in_date = self.generate_random_lease_dates()
        
        first_name, last_name = random.choice(self.KENYAN_NAMES)
        full_name = f"{first_name} {last_name}"
        
        property_data = await self.db.properties.find_one({"_id": property_id})
        location = property_data.get("location", "Nairobi")
        
        units_cursor = self.db.property_units.find({"_id": {"$in": unit_ids}})
        units = await units_cursor.to_list(length=None)
        
        total_rent = sum(u.get("rentAmount", 10000) for u in units)
        deposit_multiplier = random.choice([1, 2])
        deposit_amount = total_rent * deposit_multiplier
        
        # Create tenant
        tenant_data = {
            "_id": ObjectId(tenant_id),
            "full_name": full_name,
            "email": self.generate_email(first_name, last_name),
            "phone": self.generate_phone(),
            "id_number": self.generate_id_number(),
            "id_type": "National ID",
            "postal_address": f"P.O. Box {random.randint(1000, 99999)}, {location}",
            "location": location,
            "property_id": property_id,
            "units_id": unit_ids,
            "joined_at": move_in_date if move_in_date else lease_start,
            "move_in_date": move_in_date,
            "active": True,
            "credit_balance": 0.0
        }
        
        await self.db.property_tenants.insert_one(tenant_data)
        
        # Get property utilities
        property_utilities = property_data.get("utilities", [])
        
        # Map utilities to lease format
        lease_utilities = []
        for util in property_utilities:
            if util["billingBasis"] == "metered":
                lease_utilities.append({
                    "name": util["name"],
                    "type": "mandatory",
                    "paymentType": "billable",
                    "billingBasis": "metered",
                    "billingLevel": "unit",
                    "actual_rate": util["rate"],
                    "rate": util["rate"],
                    "unitOfMeasure": util["unitOfMeasure"],
                    "billTo": "tenant",
                    "shared": False,
                    "isCommonUtility": False,
                    "units": [
                        {
                            "unitId": unit_id,
                            "utilityId": util["name"],
                            "rate": util["rate"],
                            "enabled": True,
                            "isCommonUtility": False
                        }
                        for unit_id in unit_ids
                    ]
                })
            else:
                lease_utilities.append({
                    "name": util["name"],
                    "type": "mandatory",
                    "paymentType": "billable",
                    "billingBasis": "monthly",
                    "billingLevel": "property",
                    "rate": util["rate"],
                    "billTo": "tenant",
                    "shared": True,
                    "isCommonUtility": True
                })
        
        # Create lease
        lease_data = {
            "_id": ObjectId(lease_id),
            "property_id": property_id,
            "units_id": unit_ids,
            "tenant_id": ObjectId(tenant_id),
            "tenant_details": {
                "full_name": full_name,
                "email": tenant_data["email"],
                "phone": tenant_data["phone"],
                "id_number": tenant_data["id_number"],
                "id_type": "National ID",
                "postal_address": tenant_data["postal_address"],
                "location": location
            },
            "lease_terms": {
                "start_date": lease_start,
                "end_date": lease_end,
                "rent_amount": total_rent,
                "deposit_amount": deposit_amount,
                "rent_cycle": "monthly",
                "payment_due_day": 5
            },
            "move_in_date": move_in_date,
            "utilities": lease_utilities,
            "financial_details": {
                "rent_amount": total_rent,
                "deposit_amount": deposit_amount,
                "currency": "KES",
                "deposit_paid": random.choice([True, False]),
                "deposit_paid_date": lease_start if random.choice([True, False]) else None,
                "deposit_paid_amount": deposit_amount if random.choice([True, False]) else 0
            },
            "clauses": [
                {"title": "Rent Payment", "description": "Rent is due on the 5th of each month", "mandatory": True},
                {"title": "Security Deposit", "description": "Refundable within 14 days after move-out", "mandatory": True},
                {"title": "Notice Period", "description": "30 days notice required before vacating", "mandatory": True}
            ],
            "auto_renew": False,
            "notice_period_days": 30,
            "status": "signed",
            "tenant_signature": self.generate_signature(),
            "landlord_signature": self.generate_signature(),
            "landlord_signature_metadata": {
                "timestamp": lease_start.isoformat(),
                "ip_address": "127.0.0.1",
                "location": "Nairobi, Kenya",
                "user_agent": "Mozilla/5.0",
                "session_id": f"sess_{ObjectId()}",
                "document_hash": hashlib.sha256(lease_id.encode()).hexdigest(),
                "signature_hash": hashlib.sha256(f"landlord_{lease_id}".encode()).hexdigest(),
                "signer_name": property_data.get("name", "Property Management"),
                "signer_email": property_data.get("email", "management@property.co.ke"),
                "platform": "Web",
                "browser": "Chrome",
                "device_type": "Desktop"
            },
            "landlord_signed_date": lease_start,
            "created_at": lease_start,
            "updated_at": lease_start,
            "tenant_signature_metadata": {
                "timestamp": lease_start.isoformat(),
                "ip_address": "127.0.0.1",
                "location": "Nairobi, Kenya",
                "user_agent": "Mozilla/5.0",
                "session_id": f"sess_{ObjectId()}",
                "document_hash": hashlib.sha256(lease_id.encode()).hexdigest(),
                "signature_hash": hashlib.sha256(f"tenant_{lease_id}".encode()).hexdigest(),
                "signer_name": full_name,
                "signer_email": tenant_data["email"],
                "platform": "Web",
                "browser": "Chrome",
                "device_type": "Desktop"
            },
            "tenant_signed_date": lease_start
        }
        
        await self.db.property_leases.insert_one(lease_data)
        
        return tenant_id, lease_id, lease_start, move_in_date


class InvoiceSimulatorWithMeters:
    """Extended invoice simulator with metered utility support"""
    
    def __init__(self, manager: AsyncLeaseInvoiceManager, data_generator: RealisticDataGenerator):
        self.manager = manager
        self.db = manager.db
        self.data_gen = data_generator
        self.utility_tracker = MeteredUtilityTracker()
    
    async def generate_invoice_with_meters(
        self,
        lease_id: str,
        period: str,
        payment_scenario: str = "fully_paid",
        meta={}
    ) -> str:
        """Generate invoice with proper metered utility line items"""
        
        lease = await self.db.property_leases.find_one({"_id": ObjectId(lease_id)})
        if not lease:
            raise ValueError(f"Lease {lease_id} not found")
        
        year, month = map(int, period.split("-"))
        invoice_date = datetime(year, month, 1, tzinfo=timezone.utc)
        due_date = invoice_date + timedelta(days=4)
        
        rent_amount = lease["lease_terms"]["rent_amount"]
        
        line_items = []
        
        # 1. Rent line item
        line_items.append({
            "description": f"Rent - {period}",
            "type": "rent",
            "quantity": 1,
            "unit_price": rent_amount,
            "amount": rent_amount,
            "meta": {
                "period": period,
                "rent_cycle": "monthly"
            }|meta
        })
        
        # 2. Metered utilities
        for utility in lease.get("utilities", []):
            if utility.get("billingBasis") == "metered":
                utility_name = utility["name"]
                rate = utility["rate"]
                unit_of_measure = utility["unitOfMeasure"]
                
                unit_ids = lease["units_id"]
                
                for unit_id in unit_ids:
                    current_reading = self.data_gen.get_meter_reading(
                        str(unit_id),
                        utility_name,
                        period
                    )
                    
                    previous_reading = self.data_gen.get_previous_meter_reading(
                        str(unit_id),
                        utility_name,
                        period
                    )
                    
                    utility_line_item = self.utility_tracker.create_utility_line_item(
                        utility_name,
                        rate,
                        previous_reading,
                        current_reading,
                        unit_of_measure,
                        period
                    )
                    
                    line_items.append(utility_line_item)
                    
                    print(f"      {utility_name}: {previous_reading} → {current_reading} = {current_reading - previous_reading} {unit_of_measure} × KES {rate} = KES {(current_reading - previous_reading) * rate:,.2f}")
        
        # 3. Fixed utilities
        for utility in lease.get("utilities", []):
            if utility.get("billingBasis") != "metered":
                utility_name = utility["name"]
                rate = utility["rate"]
                
                line_items.append({
                    "description": f"{utility_name} - {period}",
                    "type": "utility",
                    "utility_name": utility_name,
                    "quantity": 1,
                    "unit_price": rate,
                    "amount": rate,
                    "meta": {
                        "billing_basis": "fixed",
                        "period": period
                    }|meta
                })
        
        total_amount = sum(item["amount"] for item in line_items)
        
        invoice_id = str(ObjectId())
        correct_date_issued = due_date - timedelta(days=3)
        invoice_data = {
            "_id": invoice_id,
            "property_id": lease["property_id"],
            "lease_id": lease_id,
            "tenant_id": lease["tenant_id"],
            "units_id": lease["units_id"],
            "invoice_number": f"INV-{period}-{random.randint(1000, 9999)}",
            "date_issued": correct_date_issued,
            "due_date": due_date, 
            "payment_date":None,
            "total_amount": round(total_amount, 2),
            "total_paid": 0,
            "balance_amount": round(total_amount, 2),
            "status": "unpaid",
            "line_items": line_items,
            "meta": {
                "billing_period": period,
                "billing_cycle": "monthly",
                "rent_amount": rent_amount,
                "has_metered_utilities": True,
            }|meta,
            "payments": [],
            "created_at": invoice_date,
            "updated_at": invoice_date
        }
        
        await self.db.property_invoices.insert_one(invoice_data)
        
        return invoice_id
    
    async def generate_historical_invoices_with_meters(
        self,
        lease_id: str,
        start_period: str,
        end_period: str,
        payment_scenarios: List[str]
    ) -> Dict:
        """Generate historical invoices with metered utilities"""
        
        results = {
            "invoices_created": [],
            "payments_made": [],
            "meter_readings_recorded": 0,
            "final_balances": {
                "total_outstanding": 0.0,
                "credit_balance": 0.0
            }
        }
        
        start_year, start_month = map(int, start_period.split("-"))
        end_year, end_month = map(int, end_period.split("-"))
        
        current = datetime(start_year, start_month, 1)
        end = datetime(end_year, end_month, 1)
        
        month_index = 0
        
        # Calculate final balances
        lease = await self.db.property_leases.find_one({"_id": ObjectId(lease_id)})
        tenant_id = lease["tenant_id"]
        
        # Get tenant credit balance #Todo get from ledger  entries
        tenant = await self.db.property_tenants.find_one({"_id": ObjectId(tenant_id)},{"full_name":1,"_id":0})
        property = await self.db.properties.find_one({"_id": str(lease["property_id"])},{"name":1,"_id":0})
        
        unit_ids = [str(u) if not isinstance(u, ObjectId) else u for u in lease.get("units_id", [])]

        cursor = self.db.units.find(
            {"_id": {"$in": unit_ids}},
            {"unitName": 1, "unitNumber": 1, "_id": 0}
        )

        units = await cursor.to_list(length=None)
        meta={
            "property":property,
            "tenant":tenant,
            "units":units
        }
        
        while current <= end:
            period = current.strftime("%Y-%m")
            
            if month_index < len(payment_scenarios):
                scenario = payment_scenarios[month_index]
            else:
                scenario = "fully_paid"
            
            invoice_id = await self.generate_invoice_with_meters(
                lease_id,
                period,
                scenario,meta
            )
            
            results["invoices_created"].append(invoice_id)
            
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)
            
            month_index += 1
        
        
        results["final_balances"]["credit_balance"] = tenant.get("credit_balance", 0.0) if tenant else 0.0
        
        # Get total outstanding from invoices
        cursor = self.db.property_invoices.find({
            "tenant_id": tenant_id,
            "balance_amount": {"$gt": 0}
        })
        invoices = await cursor.to_list(length=None)
        results["final_balances"]["total_outstanding"] = sum(inv.get("balance_amount", 0) for inv in invoices)
        
        return results


class CompleteDataGenerator:
    """Complete data generation workflow with metered utilities"""
    
    def __init__(self, manager: AsyncLeaseInvoiceManager):
        self.manager = manager
        self.data_gen = RealisticDataGenerator(manager)
        self.simulator = InvoiceSimulatorWithMeters(manager, self.data_gen)
    
    async def generate_complete_dataset(
        self,
        source_property_id: str,
        num_properties: int = 3,
        units_per_property: int = 10
    ) -> Dict:
        """Generate complete dataset with metered utilities"""
        
        results = {
            "properties_created": [],
            "tenants_created": [],
            "leases_created": [],
            "invoices_generated": 0,
            "payments_processed": 0,
            "meter_readings_recorded": 0,
            "tenant_profiles": {},
            "early_move_ins": 0
        }
        
        print("=" * 80)
        print(" GENERATING COMPLETE REALISTIC DATASET WITH METERED UTILITIES")
        print(f" Properties: {num_properties} | Units per property: {units_per_property}")
        print(" Period: Varied dates from January 2025 to Present")
        print("=" * 80)
        
        for prop_num in range(num_properties):
            print(f"\n{'─' * 80}")
            print(f" PROPERTY {prop_num + 1}/{num_properties}")
            print(f"{'─' * 80}")
            
            property_info = await self.data_gen.clone_property(
                source_property_id,
                units_per_property
            )
            
            property_id = property_info["property_id"]
            property_name = property_info["property_name"]
            unit_ids = property_info["unit_ids"]
            
            results["properties_created"].append({
                "property_id": property_id,
                "name": property_name,
                "units": len(unit_ids)
            })
            
            for i, unit_id in enumerate(unit_ids):
                print(f"\n  Tenant {i+1}/{len(unit_ids)}:")
                
                tenant_id, lease_id, lease_start, move_in_date = await self.data_gen.create_lease_with_tenant(
                    property_id,
                    [unit_id]
                )
                
                tenant = await self.manager.db.property_tenants.find_one({"_id": ObjectId(tenant_id)})
                
                scenarios, billing_start_month, tenant_type = RealisticPaymentScenarios.generate_scenarios_from_lease_start(
                    lease_start,
                    move_in_date
                )
                
                print(f"    Name: {tenant['full_name']}")
                print(f"    Type: {tenant_type.upper()}")
                print(f"    Lease Start: {lease_start.strftime('%Y-%m-%d')}")
                if move_in_date:
                    print(f"    Move-in Date: {move_in_date.strftime('%Y-%m-%d')} (EARLY by {(lease_start - move_in_date).days} days)")
                    results["early_move_ins"] += 1
                print(f"    Billing From: {billing_start_month}")
                print(f"    Months to Bill: {len(scenarios)}")
                
                current_date = datetime.now(timezone.utc)
                end_month = f"{current_date.year}-{current_date.month:02d}"
                
                print(f"    Generating invoices with meter readings from {billing_start_month} to {end_month}...")
                
                invoice_results = await self.simulator.generate_historical_invoices_with_meters(
                    lease_id,
                    billing_start_month,
                    end_month,
                    payment_scenarios=scenarios
                )
                
                results["tenants_created"].append({
                    "tenant_id": tenant_id,
                    "name": tenant['full_name'],
                    "type": tenant_type,
                    "property": property_name,
                    "unit": unit_id,
                    "lease_start": lease_start.strftime('%Y-%m-%d'),
                    "move_in_early": move_in_date is not None
                })
                
                results["leases_created"].append(lease_id)
                results["invoices_generated"] += len(invoice_results["invoices_created"])
                results["payments_processed"] += len(invoice_results.get("payments_made", []))
                
                # FIXED: Access dict properly
                final_balance = invoice_results["final_balances"]["total_outstanding"]
                credit_balance = invoice_results["final_balances"]["credit_balance"]
                
                results["tenant_profiles"][tenant_id] = {
                    "name": tenant['full_name'],
                    "type": tenant_type,
                    "property": property_name,
                    "lease_start": lease_start,
                    "move_in_date": move_in_date,
                    "scenarios": scenarios,
                    "final_balance": final_balance,
                    "credit": credit_balance
                }
                
                print(f"    ✓ Generated {len(invoice_results['invoices_created'])} invoices with meter readings")
                print(f"    ✓ Processed {len(invoice_results.get('payments_made', []))} payments")
                print(f"    Balance: KES {final_balance:,.2f}")
                if credit_balance > 0:
                    print(f"    Credit: KES {credit_balance:,.2f}")
            
            # Update property occupancy after all leases created
            await self.data_gen.update_property_occupancy(property_id)
        
        return results
    
    def print_final_summary(self, results: Dict):
        """Print comprehensive final summary"""
        print("\n" + "=" * 80)
        print(" GENERATION COMPLETE - FINAL SUMMARY")
        print("=" * 80)
        
        print(f"\n📊 Overall Statistics:")
        print(f"   Properties Created: {len(results['properties_created'])}")
        print(f"   Tenants Created: {len(results['tenants_created'])}")
        print(f"   Leases Created: {len(results['leases_created'])}")
        print(f"   Early Move-ins: {results['early_move_ins']}")
        print(f"   Total Invoices: {results['invoices_generated']:,}")
        print(f"   Total Payments: {results['payments_processed']:,}")
        
        tenant_types = {}
        for profile in results["tenant_profiles"].values():
            t_type = profile["type"]
            tenant_types[t_type] = tenant_types.get(t_type, 0) + 1
        
        print(f"\n👥 Tenant Distribution:")
        for t_type, count in sorted(tenant_types.items()):
            percentage = (count / len(results["tenant_profiles"]) * 100)
            print(f"   {t_type.capitalize():15s}: {count:3d} ({percentage:5.1f}%)")
        
        total_outstanding = sum(p["final_balance"] for p in results["tenant_profiles"].values())
        total_credit = sum(p["credit"] for p in results["tenant_profiles"].values())
        
        print(f"\n💰 Financial Summary:")
        print(f"   Total Outstanding: KES {total_outstanding:,.2f}")
        print(f"   Total Credits: KES {total_credit:,.2f}")
        print(f"   Net Outstanding: KES {(total_outstanding - total_credit):,.2f}")
        
        print(f"\n🏢 Properties Created:")
        for prop in results["properties_created"]:
            print(f"   {prop['name']:30s}: {prop['units']} units")


async def run_complete_generation():
    """Main function to run complete data generation with metered utilities"""
    
    print("=" * 80)
    print(" REALISTIC DATA GENERATION WITH METERED UTILITIES")
    print("=" * 80)
    
    client = AsyncIOMotorClient(
        "mongodb://admin:password@95.110.228.29:8711/fq_db?authSource=admin"
    )
    manager = AsyncLeaseInvoiceManager(client, database_name="fq_db")
    
    generator = CompleteDataGenerator(manager)
    
    source_property_id = "68fa95fc9422760b6b31858a"
    
    try:
        results = await generator.generate_complete_dataset(
            source_property_id=source_property_id,
            num_properties=3,
            units_per_property=10
        )
        
        generator.print_final_summary(results)
        
        print("\n" + "=" * 80)
        print(" SUCCESS - ALL DATA GENERATED")
        print("=" * 80)
        print("\n✅ What was created:")
        print("   ✓ 3 properties with realistic data")
        print("   ✓ 30 units (10 per property)")
        print("   ✓ 30 tenants with varied join dates")
        print("   ✓ 30 leases with random start dates")
        print("   ✓ Invoices with METERED utility readings")
        print("   ✓ Water & Electricity readings month-by-month")
        print("   ✓ Realistic consumption patterns")
        print("   ✓ Complete line items with meta data")
        print("   ✓ Usage calculations (current - previous)")
        print("   ✓ Property occupancy auto-calculated")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(run_complete_generation())