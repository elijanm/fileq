
"""
Generate Dummy Units for Property
Automatically create units when a property is created
"""

from datetime import datetime, timezone
from typing import List
import random
from fastapi import HTTPException, 
from bson import ObjectId


# ============================================
# Unit Types and Configuration
# ============================================

UNIT_TYPES = ["studio", "1-bedroom", "2-bedroom", "3-bedroom", "penthouse"]
UNIT_STATUS = ["in_creation"]
FLOOR_PLANS = ["A", "B", "C", "D"]


# ============================================
# Helper Functions
# ============================================

def generate_unit_number(floor, wing, position, format_style):
    if format_style == "suffix":
        return f"{floor}{position:02d}{wing[0]}"  # 201E
    elif format_style == "prefix":
        return f"{wing[0]}{floor}{position:02d}"  # E201
    elif format_style == "dash":
        return f"{floor}-{wing[0]}-{position:02d}"  # 2-E-01


def get_unit_type_details(unit_type: str) -> dict:
    """Get default details for each unit type"""
    unit_configs = {
        "studio": {
            "bedrooms": 0,
            "bathrooms": 1,
            "size_sqft": 450,
            "base_rent": 800
        },
        "1-bedroom": {
            "bedrooms": 1,
            "bathrooms": 1,
            "size_sqft": 650,
            "base_rent": 1200
        },
        "2-bedroom": {
            "bedrooms": 2,
            "bathrooms": 2,
            "size_sqft": 950,
            "base_rent": 1800
        },
        "3-bedroom": {
            "bedrooms": 3,
            "bathrooms": 2,
            "size_sqft": 1250,
            "base_rent": 2500
        },
        "penthouse": {
            "bedrooms": 4,
            "bathrooms": 3,
            "size_sqft": 2000,
            "base_rent": 4500
        }
    }
    return unit_configs.get(unit_type, unit_configs["1-bedroom"])


def calculate_floor_from_unit_number(unit_number: int, units_per_floor: int) -> int:
    """Calculate which floor a unit is on"""
    return (unit_number // units_per_floor) + 1


# ============================================
# Main Function: Generate Dummy Units
# ============================================

async def generate_dummy_units(
    db,
    property_id: str,
    num_units: int,
    units_per_floor: int = 4,
    occupancy_rate: float = 0.75  # 75% occupied by default
) -> List[dict]:
    """
    Generate dummy units for a property
    
    Args:
        db: Database connection
        property_id: Property ObjectId
        num_units: Total number of units to create
        units_per_floor: Units per floor (default 4)
        occupancy_rate: Percentage of units to mark as occupied (0.0 to 1.0)
    
    Returns:
        List of created unit dictionaries
    """
    
    # Verify property exists
    prop = await db["properties"].find_one({"_id": ObjectId(property_id)})
    if not prop:
        raise HTTPException(404, detail="Property not found")
    
    created_units = []
    num_occupied = int(num_units * occupancy_rate)
    
    # Shuffle unit indices to randomly assign occupied status
    unit_indices = list(range(num_units))
    random.shuffle(unit_indices)
    occupied_indices = set(unit_indices[:num_occupied])
    
    for i in range(num_units):
        # Calculate floor and position
        floor = (i // units_per_floor) + 1
        position = (i % units_per_floor) + 1
        unit_number = generate_unit_number(floor, position)
        
        # Randomly select unit type (with distribution)
        unit_type = random.choices(
            UNIT_TYPES,
            weights=[10, 40, 30, 15, 5],  # Studios and 1BR more common
            k=1
        )[0]
        
        # Get unit details based on type
        unit_details = get_unit_type_details(unit_type)
        
        # Determine status
        is_occupied = i in occupied_indices
        status = "occupied" if is_occupied else random.choice(["available", "available", "available", "maintenance"])
        
        # Add some variance to rent and size
        rent_variance = random.uniform(0.95, 1.10)  # ±10%
        size_variance = random.uniform(0.95, 1.05)  # ±5%
        
        # Create unit document
        unit_doc = {
            "property_id": property_id,
            "unit_number": unit_number,
            "unit_type": unit_type,
            "floor": floor,
            "floor_plan": random.choice(FLOOR_PLANS),
            "bedrooms": unit_details["bedrooms"],
            "bathrooms": unit_details["bathrooms"],
            "size_sqft": round(unit_details["size_sqft"] * size_variance),
            "rent_amount": round(unit_details["base_rent"] * rent_variance, 2),
            "status": status,
            "is_occupied": is_occupied,
            "description": f"{unit_type.title()} apartment on floor {floor}",
            "amenities": generate_amenities(unit_type),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # If occupied, add tenant info
        if is_occupied:
            unit_doc["current_tenant_id"] = None  # Will be populated when tenants are created
            unit_doc["lease_start_date"] = None
            unit_doc["lease_end_date"] = None
        
        created_units.append(unit_doc)
    
    # Bulk insert all units
    if created_units:
        result = await db["units"].insert_many(created_units)
        
        # Update property with unit counts
        await db["properties"].update_one(
            {"_id": ObjectId(property_id)},
            {
                "$set": {
                    "units_total": num_units,
                    "units_occupied": num_occupied,
                    "occupancy_rate": f"{int(occupancy_rate * 100)}%",
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Add the inserted IDs to the unit documents
        for i, unit_id in enumerate(result.inserted_ids):
            created_units[i]["_id"] = str(unit_id)
    
    return created_units


def generate_amenities(unit_type: str) -> List[str]:
    """Generate amenities based on unit type"""
    base_amenities = ["Air Conditioning", "Heating", "Wi-Fi Ready"]
    
    if unit_type in ["studio", "1-bedroom"]:
        return base_amenities + random.sample([
            "Balcony", "Hardwood Floors", "Dishwasher", "Microwave"
        ], k=2)
    elif unit_type == "2-bedroom":
        return base_amenities + random.sample([
            "Balcony", "Hardwood Floors", "Dishwasher", "Microwave", 
            "Walk-in Closet", "In-Unit Laundry"
        ], k=3)
    elif unit_type == "3-bedroom":
        return base_amenities + [
            "Balcony", "Hardwood Floors", "Dishwasher", "Microwave",
            "Walk-in Closet", "In-Unit Laundry"
        ] + random.sample(["Fireplace", "Extra Storage"], k=1)
    else:  # penthouse
        return base_amenities + [
            "Private Balcony", "Hardwood Floors", "Dishwasher", "Microwave",
            "Walk-in Closet", "In-Unit Laundry", "Fireplace", "City Views",
            "Extra Storage", "Smart Home Features"
        ]
