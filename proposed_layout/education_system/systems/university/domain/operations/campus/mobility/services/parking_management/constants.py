# Define parking zones
PARKING_ZONES = {
    'A': {'name': 'Faculty/Staff', 'hourly_rate': 0, 'annual_fee': 250},
    'B': {'name': 'Commuter Students', 'hourly_rate': 0, 'annual_fee': 180},
    'C': {'name': 'Resident Students', 'hourly_rate': 0, 'annual_fee': 220},
    'V': {'name': 'Visitor', 'hourly_rate': 2.50, 'annual_fee': 0},
    'H': {'name': 'Handicap Accessible', 'hourly_rate': 0, 'annual_fee': 150},
    'M': {'name': 'Metered', 'hourly_rate': 1.75, 'annual_fee': 0},
    'R': {'name': 'Reserved', 'hourly_rate': 0, 'annual_fee': 350},
}

# Define permit types
PERMIT_TYPES = ['Annual', 'Semester', 'Monthly', 'Daily', 'Temporary']

# Define vehicle types
VEHICLE_TYPES = ['Sedan', 'SUV', 'Truck', 'Motorcycle', 'Compact', 'Van']
