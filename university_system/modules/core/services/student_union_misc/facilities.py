from __future__ import annotations

from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.core.services.student_union_misc import context as ctx

def view_facilities():
    """View available facilities"""
    
    if not ctx.auth or not ctx.auth.current_user:
        print("You must be logged in to view facilities.")
        return

    if not ctx.auth.check_permission('view_facilities'):
        print("You don't have permission to view facilities.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch all available facilities
        cursor.execute('''
        SELECT facility_id, facility_name, location, capacity, description, equipment, booking_fee
        FROM union_facilities
        WHERE status = 'available'
        ORDER BY facility_name
        ''')

        facilities = cursor.fetchall()

        if not facilities:
            print("No available facilities found.")
            conn.close()
            return

        print("\nAvailable Facilities:")
        print("====================")

        for facility in facilities:
            print(f"\nID: {facility[0]}")
            print(f"Name: {facility[1]}")
            print(f"Location: {facility[2]}")
            print(f"Capacity: {facility[3]} people")
            print(f"Description: {facility[4]}")
            print(f"Equipment: {facility[5]}")
            print(f"Booking Fee: £{facility[6]:.2f}")
            print("-" * 40)

        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
