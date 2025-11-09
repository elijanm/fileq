from typing import List, Optional
import re
from datetime import datetime,timezone
from plugins.pms.models.models import PropertyCreate ,UnitBase
from bson import ObjectId
from datetime import datetime, timezone
from typing import List, Optional

def generate_unit_prefix(wing_name: Optional[str] = None, floor_name: Optional[str] = None) -> str:
    """Generate a unit prefix based on wing and floor names."""
    parts = []
    
    if wing_name:
        wing_words = wing_name.strip().split()
        if len(wing_words) >= 2:
            wing_code = ''.join([w[0].upper() for w in wing_words])
        else:
            wing_code = wing_name[:2].upper()
        parts.append(wing_code)
    
    if floor_name:
        floor_lower = floor_name.lower()
        if 'ground' in floor_lower or floor_lower == 'g':
            floor_code = 'GF'
        elif 'basement' in floor_lower or floor_lower == 'b':
            floor_code = 'B'
        else:
            match = re.search(r'\d+', floor_name)
            if match:
                floor_code = f'F{match.group()}'
            else:
                floor_code = floor_name[0].upper()
        parts.append(floor_code)
    
    return '-'.join(parts) if parts else 'U'


# Mapping from common unit type strings to enum values
UNIT_TYPE_MAPPING = {
    'studio': 'studio',
    '1 bed': '1-bedroom',
    '1 bedroom': '1-bedroom',
    '1bedroom': '1-bedroom',
    '2 bed': '2-bedroom',
    '2 bedroom': '2-bedroom',
    '2bedroom': '2-bedroom',
    '3 bed': '3-bedroom',
    '3 bedroom': '3-bedroom',
    '3bedroom': '3-bedroom',
    '4 bed': '4-bedroom',
    '4 bedroom': '4-bedroom',
    '4bedroom': '4-bedroom',
    'penthouse': 'penthouse',
    'duplex': 'duplex',
    'loft': 'loft',
}

def normalize_unit_type(unit_type_str: str) -> str:
    """Convert user input to valid UnitType enum value."""
    unit_type_lower = unit_type_str.lower().strip()
    
    # Direct match
    for key, value in UNIT_TYPE_MAPPING.items():
        if key in unit_type_lower:
            return value
    
    # Default to 2-bedroom if can't determine
    return '2-bedroom'


def parse_unit_specs(unit_type_enum: str) -> dict:
    """Get bedroom/bathroom/size specs based on unit type enum."""
    specs = {
        'studio': {
            'bedrooms': 0,
            'bathrooms': 1.0,
            'size_sqft': 400,
        },
        '1-bedroom': {
            'bedrooms': 1,
            'bathrooms': 1.0,
            'size_sqft': 650,
        },
        '2-bedroom': {
            'bedrooms': 2,
            'bathrooms': 2.0,
            'size_sqft': 900,
        },
        '3-bedroom': {
            'bedrooms': 3,
            'bathrooms': 2.5,
            'size_sqft': 1200,
        },
        '4-bedroom': {
            'bedrooms': 4,
            'bathrooms': 3.0,
            'size_sqft': 1600,
        },
        'penthouse': {
            'bedrooms': 3,
            'bathrooms': 3.0,
            'size_sqft': 2000,
        },
        'duplex': {
            'bedrooms': 3,
            'bathrooms': 2.5,
            'size_sqft': 1500,
        },
        'loft': {
            'bedrooms': 1,
            'bathrooms': 1.0,
            'size_sqft': 800,
        },
    }
    
    unit_spec = specs.get(unit_type_enum, specs['2-bedroom'])
    unit_spec['size_sqm'] = unit_spec['size_sqft'] * 0.092903
    
    return unit_spec


def auto_generate_units(property_data: dict) -> List[dict]:
    """
    Auto-generate units based on property configuration.
    Returns list of unit dictionaries ready for Unit model instantiation.
    """
    units = []
    wing_floor_config = property_data.get('wing_floor_config') or property_data.get('wingFloorConfig')
    floor_config = property_data.get('floor_config') or property_data.get('floorConfig')
    
    unit_counter = 1
    utilities = property_data.get("utilities", [])
    # --- Filter by billTo ---
    tenant_utilities = [u for u in utilities if u.get("billTo") == "tenant"]
    landlord_utilities = [u for u in utilities if u.get("billTo") == "landlord"]
    
    # Wing-based configuration
    if wing_floor_config:
        for wing_idx, wing_data in enumerate(wing_floor_config):
            wing_name = wing_data.get('wing_name') or wing_data.get('wingName')
            floors = wing_data.get('floors', [])
            
            for floor_data in floors:
                floor_number = floor_data.get('floor_number') or floor_data.get('floorNumber', 0)
                floor_name = floor_data.get('floor_name') or floor_data.get('floorName')
                unit_types = floor_data.get('units', [])
                
                prefix = generate_unit_prefix(wing_name, floor_name)
                
                floor_unit_counter = 1
                for unit_type_data in unit_types:
                    unit_type_str = unit_type_data.get('unit_type') or unit_type_data.get('unitType')
                    count = unit_type_data.get('count', 1)
                    unit_id = unit_type_data.get('id')
                    unit_rent = unit_type_data.get('rent_amount')
                    unit_deposit = unit_type_data.get('deposit_amount')
                    
                    # Normalize to enum value
                    unit_type_enum = normalize_unit_type(unit_type_str)
                    
                    # Get specs based on enum
                    unit_specs = parse_unit_specs(unit_type_enum)
                    
                    for i in range(count):
                        unit_number_val = (floor_number * 100) + floor_unit_counter
                        unit_number = f"{prefix}-{unit_number_val:03d}"
                        
                        # Determine if corner or end unit
                        total_units_in_floor = sum(ut.get('count', 1) for ut in unit_types)
                        is_corner_unit = floor_unit_counter == 1
                        is_end_unit = floor_unit_counter == total_units_in_floor
                        
                        # Calculate rent based on unit type
                        # rent_multiplier = {
                        #     'studio': 10000,
                        #     '1-bedroom': 15000,
                        #     '2-bedroom': 25000,
                        #     '3-bedroom': 35000,
                        #     '4-bedroom': 50000,
                        #     'penthouse': 80000,
                        #     'duplex': 45000,
                        #     'loft': 30000,
                        # }
                        
                        # base_rent = rent_multiplier.get(unit_type_enum, 25000)
                        
                        unit = {
                            'tracking_id':unit_id,
                            'unit_number': unit_number,
                            'unit_name': f"{unit_type_str} - {unit_number}",
                            'unit_type': unit_type_enum,  # Use enum value
                            'floor': floor_number,
                            'floor_plan': 'A',
                            'wing': wing_name,
                            'section': 'center' if not (is_corner_unit or is_end_unit) else 'corner' if is_corner_unit else 'end',
                            'position_in_wing': floor_unit_counter,
                            'is_corner_unit': is_corner_unit,
                            'is_end_unit': is_end_unit,
                            'facing_direction': 'north',
                            'bedrooms': unit_specs['bedrooms'],
                            'bathrooms': unit_specs['bathrooms'],
                            'size_sqft': unit_specs['size_sqft'],
                            'size_sqm': unit_specs['size_sqm'],
                            'rent_amount': unit_rent,
                            'deposit_amount': unit_deposit,
                            'service_charge': 2000,
                            'status': 'available',
                            'is_occupied': False,
                            'utilities':utilities,
                            'furnishing_status': 'unfurnished',
                            'description': f"{unit_type_str} in {wing_name}, {floor_name}",
                            'amenities': [],
                            'features': [],
                            'view_type': None,
                            'has_balcony': unit_specs['bedrooms'] >= 2,
                            'has_parking': unit_specs['bedrooms'] >= 1,
                            'parking_spots': 1 if unit_specs['bedrooms'] >= 1 else 0,
                            'pet_friendly': False,
                            'current_tenant_id': None,
                            'lease_start_date': None,
                            'lease_end_date': None,
                            'images': [],
                            'floor_plan_image': None,
                            'virtual_tour_url': None,
                        }
                        
                        units.append(unit)
                        floor_unit_counter += 1
                        unit_counter += 1
    
    # Simple floor configuration (no wings)
    elif floor_config:
        for floor_data in floor_config:
            floor_number = floor_data.get('floor_number') or floor_data.get('floorNumber', 0)
            floor_name = floor_data.get('floor_name') or floor_data.get('floorName')
            unit_types = floor_data.get('units', [])
            
            prefix = generate_unit_prefix(None, floor_name)
            
            floor_unit_counter = 1
            for unit_type_data in unit_types:
                unit_type_str = unit_type_data.get('unit_type') or unit_type_data.get('unitType')
                count = unit_type_data.get('count', 1)
                unit_id = unit_type_data.get('id')
                unit_rent = unit_type_data.get('rent_amount')
                unit_deposit = unit_type_data.get('deposit_amount')
                
                unit_type_enum = normalize_unit_type(unit_type_str)
                unit_specs = parse_unit_specs(unit_type_enum)
                
                # rent_multiplier = {
                #     'studio': 10000,
                #     '1-bedroom': 15000,
                #     '2-bedroom': 25000,
                #     '3-bedroom': 35000,
                #     '4-bedroom': 50000,
                #     'penthouse': 80000,
                #     'duplex': 45000,
                #     'loft': 30000,
                # }
                
                # base_rent = rent_multiplier.get(unit_type_enum, 25000)
                
                for i in range(count):
                    unit_number_val = (floor_number * 100) + floor_unit_counter
                    unit_number = f"{prefix}-{unit_number_val:03d}"
                    
                    total_units_in_floor = sum(ut.get('count', 1) for ut in unit_types)
                    is_corner_unit = floor_unit_counter == 1
                    is_end_unit = floor_unit_counter == total_units_in_floor
                    
                    unit = {
                        'unit_number': unit_number,
                        'unit_name': f"{unit_type_str} - {unit_number}",
                        'unit_type': unit_type_enum,
                        'floor': floor_number,
                        'floor_plan': 'A',
                        'wing': None,
                        'section': 'center' if not (is_corner_unit or is_end_unit) else 'corner' if is_corner_unit else 'end',
                        'position_in_wing': floor_unit_counter,
                        'is_corner_unit': is_corner_unit,
                        'is_end_unit': is_end_unit,
                        'facing_direction': 'north',
                        'bedrooms': unit_specs['bedrooms'],
                        'bathrooms': unit_specs['bathrooms'],
                        'size_sqft': unit_specs['size_sqft'],
                        'size_sqm': unit_specs['size_sqm'],
                        'rent_amount': unit_rent,
                        'deposit_amount': unit_deposit,
                        'service_charge': 2000,
                        'status': 'available',
                        'is_occupied': False,
                        'utilities':utilities,
                        'furnishing_status': 'unfurnished',
                        'description': f"{unit_type_str} on {floor_name}",
                        'amenities': [],
                        'features': [],
                        'view_type': None,
                        'has_balcony': unit_specs['bedrooms'] >= 2,
                        'has_parking': unit_specs['bedrooms'] >= 1,
                        'parking_spots': 1 if unit_specs['bedrooms'] >= 1 else 0,
                        'pet_friendly': False,
                        'current_tenant_id': None,
                        'lease_start_date': None,
                        'lease_end_date': None,
                        'images': [],
                        'floor_plan_image': None,
                        'virtual_tour_url': None,
                    }
                    
                    units.append(unit)
                    floor_unit_counter += 1
                    unit_counter += 1
    
    return units
async def ensureRoomAssigned(contract,db):
    for unit_id in contract["units_id"]:
        print(f"{unit_id} being assigned")
        await db["units"].update_one(
            {"_id":ObjectId(unit_id)},
            {"$set": {
                    "isOccupied": True,
                    "status": "occupied",
                    "tenant_id": ObjectId(contract["tenant_id"]),
                    "lease_start_date": contract.get("start_date"),
                    "lease_end_date": contract.get("end_date"),
                    "updated_at": datetime.now(timezone.utc)
                    
            }}
        )

async def batch_insert_units(
    generated_units: List[dict],
    property_id: str,
    db
) -> int:
    """Batch insert generated units into the database."""
    if not generated_units:
        return 0
    
    units_to_insert = []
    
    for unit_data in generated_units:
        unit = UnitBase(
            property_id=property_id,
            **unit_data,
            created_at=datetime.now(timezone.utc),
        )
        units_to_insert.append(unit.model_dump(by_alias=True))
    
    if units_to_insert:
        result = await db["units"].insert_many(units_to_insert)
        return len(result.inserted_ids)
    
    return 0