"""CLI handler for geofencing attendance system."""

import datetime
import os
from education_system.post_18.university_system.modules.domain.academics.services.attendance.records import get_modules
from education_system.post_18.university_system.modules.domain.academics.services.attendance.geofencing import GEOFENCING_SUPPORT


def handle_geofencing_system(geo_system):
    """Handle geofencing system operations"""
    if not GEOFENCING_SUPPORT:
        print("❌ Geofencing not supported. Please install geopy package.")
        return

    print("\n🌍 GEOFENCING ATTENDANCE SYSTEM")
    print("1. Create Geofenced Session")
    print("2. Check Location Attendance")
    print("3. View Geofenced Locations")

    choice = input("Enter your choice (1-3): ")

    if choice == '1':
        modules = get_modules()
        if not modules:
            print("No modules found.")
            return

        print("\nAvailable Modules:")
        for i, (code, name) in enumerate(modules, 1):
            print(f"{i}. {code} - {name}")

        try:
            module_idx = int(input("Select module number: ")) - 1
            if 0 <= module_idx < len(modules):
                module_code = modules[module_idx][0]

                date = input("Enter date (YYYY-MM-DD, leave empty for today): ")
                if not date:
                    date = datetime.date.today().isoformat()

                location_name = input("Enter location name: ")
                latitude = float(input("Enter latitude: "))
                longitude = float(input("Enter longitude: "))
                radius = int(input("Enter geofence radius in meters (default 50): ") or 50)

                session_id = geo_system.create_geofenced_session(
                    module_code, date, location_name, latitude, longitude, radius
                )

                if session_id:
                    print("✅ Geofenced session created successfully!")
                    print(f"Session ID: {session_id}")
                else:
                    print("❌ Failed to create geofenced session")
        except (ValueError, IndexError):
            print("Invalid input.")

    elif choice == '2':
        student_id = input("Enter student ID: ")
        latitude = float(input("Enter current latitude: "))
        longitude = float(input("Enter current longitude: "))

        success, message = geo_system.check_location_attendance(student_id, latitude, longitude)

        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
