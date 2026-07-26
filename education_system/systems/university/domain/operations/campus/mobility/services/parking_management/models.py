class ParkingPermit:
    def __init__(self, permit_id, user_id, full_name, email, zone, permit_type,
                start_date, end_date, active_status, vehicle_id, issue_date):
        self.permit_id = permit_id
        self.user_id = user_id
        self.full_name = full_name
        self.email = email
        self.zone = zone
        self.permit_type = permit_type
        self.start_date = start_date
        self.end_date = end_date
        self.active_status = active_status
        self.vehicle_id = vehicle_id
        self.issue_date = issue_date


class Vehicle:
    def __init__(self, vehicle_id, license_plate, make, model, year, color,
                vehicle_type, owner_id, registration_state):
        self.vehicle_id = vehicle_id
        self.license_plate = license_plate
        self.make = make
        self.model = model
        self.year = year
        self.color = color
        self.vehicle_type = vehicle_type
        self.owner_id = owner_id
        self.registration_state = registration_state


class ParkingViolation:
    def __init__(self, violation_id, vehicle_id, license_plate, violation_type,
                violation_date, fine_amount, payment_status, location, officer_id):
        self.violation_id = violation_id
        self.vehicle_id = vehicle_id
        self.license_plate = license_plate
        self.violation_type = violation_type
        self.violation_date = violation_date
        self.fine_amount = fine_amount
        self.payment_status = payment_status
        self.location = location
        self.officer_id = officer_id
