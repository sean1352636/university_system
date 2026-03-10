from . import common as _common
from .common import (
    sqlite3, datetime, os, get_text, get_connection,
    log_read, log_export, log_search,
)

@log_read(module="housing", description="Generating housing occupancy report")
def generate_occupancy_report():
    """Generate a comprehensive occupancy report"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return

    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to generate reports.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nHousing Occupancy Report")
        print("=" * 50)

        # Overall statistics
        cursor.execute('SELECT COUNT(*) FROM housing_buildings')
        total_buildings = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_rooms')
        total_rooms = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Occupied"')
        occupied_rooms = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_rooms WHERE status = "Available"')
        available_rooms = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_assignments WHERE status = "Active"')
        active_assignments = cursor.fetchone()[0]

        occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0

        print(f"Total Buildings: {total_buildings}")
        print(f"Total Rooms: {total_rooms}")
        print(f"Occupied Rooms: {occupied_rooms}")
        print(f"Available Rooms: {available_rooms}")
        print(f"Active Assignments: {active_assignments}")
        print(f"Occupancy Rate: {occupancy_rate:.1f}%")
        print()

        # Building breakdown
        cursor.execute('''
        SELECT b.building_name, b.total_rooms, b.available_rooms,
               (b.total_rooms - b.available_rooms) as occupied_rooms,
               ROUND((CAST(b.total_rooms - b.available_rooms AS FLOAT) / b.total_rooms) * 100, 1) as occupancy_rate
        FROM housing_buildings b
        ORDER BY b.building_name
        ''')

        buildings = cursor.fetchall()

        print("Building Breakdown:")
        print("-" * 80)
        print(f"{'Building':<25} {'Total':<8} {'Occupied':<10} {'Available':<10} {'Rate':<8}")
        print("-" * 80)

        for building in buildings:
            print(f"{building[0]:<25} {building[1]:<8} {building[3]:<10} {building[2]:<10} {building[4]:.1f}%")

        # Room type breakdown
        print("\nRoom Type Distribution:")
        print("-" * 50)

        cursor.execute('''
        SELECT room_type, COUNT(*) as total,
               SUM(CASE WHEN status = 'Occupied' THEN 1 ELSE 0 END) as occupied,
               SUM(CASE WHEN status = 'Available' THEN 1 ELSE 0 END) as available
        FROM housing_rooms
        GROUP BY room_type
        ORDER BY room_type
        ''')

        room_types = cursor.fetchall()

        print(f"{'Type':<12} {'Total':<8} {'Occupied':<10} {'Available':<10}")
        print("-" * 50)

        for room_type in room_types:
            print(f"{room_type[0]:<12} {room_type[1]:<8} {room_type[2]:<10} {room_type[3]:<10}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating report: {e}")

@log_read(module="housing", description="Generating financial report")
def generate_financial_report():
    """Generate a financial report for housing"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to generate financial reports.")
        return

    if not auth.check_permission('manage_accommodations'):
        print("You don't have permission to generate financial reports.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nHousing Financial Report")
        print("=" * 50)

        # Monthly revenue calculation
        cursor.execute('''
        SELECT SUM(monthly_rent) as monthly_revenue
        FROM housing_assignments
        WHERE status = 'Active'
        ''')

        monthly_revenue = cursor.fetchone()[0] or 0

        print(f"Current Monthly Revenue: ${monthly_revenue:,.2f}")
        print(f"Projected Annual Revenue: ${monthly_revenue * 12:,.2f}")
        print()

        # Payment statistics for current year
        current_year = datetime.datetime.now().year

        cursor.execute('''
        SELECT COUNT(*) as payment_count, SUM(amount) as total_amount
        FROM housing_payments
        WHERE strftime('%Y', payment_date) = ?
        ''', (str(current_year),))

        year_stats = cursor.fetchone()
        payment_count = year_stats[0] or 0
        total_collected = year_stats[1] or 0

        print(f"Payments Collected This Year ({current_year}):")
        print(f"Number of Payments: {payment_count}")
        print(f"Total Amount Collected: ${total_collected:,.2f}")
        print()

        # Revenue by building
        cursor.execute('''
        SELECT b.building_name, COUNT(a.assignment_id) as active_assignments,
               SUM(a.monthly_rent) as monthly_revenue
        FROM housing_buildings b
        LEFT JOIN housing_rooms r ON b.building_id = r.building_id
        LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
        GROUP BY b.building_id, b.building_name
        ORDER BY monthly_revenue DESC
        ''')

        building_revenue = cursor.fetchall()

        print("Revenue by Building:")
        print("-" * 60)
        print(f"{'Building':<25} {'Assignments':<12} {'Monthly Revenue':<15}")
        print("-" * 60)

        for building in building_revenue:
            assignments = building[1] or 0
            revenue = building[2] or 0
            print(f"{building[0]:<25} {assignments:<12} ${revenue:,.2f}")

        # Outstanding payments (simplified - would need more complex logic for real implementation)
        print("\nPayment Status Summary:")
        print("-" * 40)

        cursor.execute('''
        SELECT COUNT(*) as active_assignments
        FROM housing_assignments
        WHERE status = 'Active'
        ''')

        active_count = cursor.fetchone()[0] or 0

        # This is a simplified view - in a real system you'd track payment due dates
        print(f"Active Housing Assignments: {active_count}")
        print(f"Expected Monthly Collections: ${monthly_revenue:,.2f}")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating financial report: {e}")

@log_export(module="housing", description="Exporting housing data")
def export_housing_data():
    """Export housing data to CSV format"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to export data.")
        return

    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to export data.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nHousing Data Export")
        print("=" * 30)
        print("1. Export Building Data")
        print("2. Export Room Data")
        print("3. Export Assignment Data")
        print("4. Export Application Data")
        print("5. Export Payment Data")
        print("6. Export Maintenance Requests")
        print("7. Cancel")

        choice = input("\nSelect data to export (1-7): ")

        if choice == '7':
            conn.close()
            return

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        if choice == '1':
            # Export building data
            cursor.execute('''
            SELECT building_id, building_name, address, campus_location, total_rooms, available_rooms,
                   has_elevator, has_accessible_rooms, has_kitchen, has_laundry, created_at
            FROM housing_buildings
            ORDER BY building_name
            ''')

            data = cursor.fetchall()
            filename = f"housing_buildings_{timestamp}.csv"

            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Building ID', 'Building Name', 'Address', 'Campus Location',
                               'Total Rooms', 'Available Rooms', 'Has Elevator', 'Has Accessible Rooms',
                               'Has Kitchen', 'Has Laundry', 'Created At'])
                writer.writerows(data)

            print(f"Building data exported to {filename}")

        elif choice == '2':
            # Export room data
            cursor.execute('''
            SELECT r.room_id, b.building_name, r.room_number, r.floor_number, r.room_type,
                   r.max_occupants, r.current_occupants, r.is_accessible, r.status, r.monthly_rent
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''')

            data = cursor.fetchall()
            filename = f"housing_rooms_{timestamp}.csv"

            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Room ID', 'Building', 'Room Number', 'Floor', 'Type',
                               'Max Occupants', 'Current Occupants', 'Accessible', 'Status', 'Monthly Rent'])
                writer.writerows(data)

            print(f"Room data exported to {filename}")

        elif choice == '3':
            # Export assignment data
            cursor.execute('''
            SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
                   b.building_name, r.room_number, a.move_in_date, a.planned_move_out_date,
                   a.monthly_rent, a.status, a.assigned_by
            FROM housing_assignments a
            JOIN students s ON a.student_id = s.student_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY a.created_at DESC
            ''')

            data = cursor.fetchall()
            filename = f"housing_assignments_{timestamp}.csv"

            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Assignment ID', 'Student ID', 'First Name', 'Last Name',
                               'Building', 'Room', 'Move In Date', 'Planned Move Out',
                               'Monthly Rent', 'Status', 'Assigned By'])
                writer.writerows(data)

            print(f"Assignment data exported to {filename}")

        elif choice == '4':
            # Export application data
            cursor.execute('''
            SELECT app.application_id, app.student_id, s.first_name, s.last_name,
                   app.application_date, b.building_name, app.preferred_room_type,
                   app.requested_move_in_date, app.requested_duration_months, app.status
            FROM housing_applications app
            JOIN students s ON app.student_id = s.student_id
            LEFT JOIN housing_buildings b ON app.preferred_building_id = b.building_id
            ORDER BY app.application_date DESC
            ''')

            data = cursor.fetchall()
            filename = f"housing_applications_{timestamp}.csv"

            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Application ID', 'Student ID', 'First Name', 'Last Name',
                               'Application Date', 'Preferred Building', 'Preferred Room Type',
                               'Requested Move In', 'Duration (Months)', 'Status'])
                writer.writerows(data)

            print(f"Application data exported to {filename}")

        elif choice == '5':
            # Export payment data
            cursor.execute('''
            SELECT p.payment_id, p.student_id, s.first_name, s.last_name,
                   p.amount, p.payment_date, p.payment_method, p.payment_period_start,
                   p.payment_period_end, p.status, b.building_name, r.room_number
            FROM housing_payments p
            JOIN students s ON p.student_id = s.student_id
            JOIN housing_assignments a ON p.assignment_id = a.assignment_id
            JOIN housing_rooms r ON a.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY p.payment_date DESC
            ''')

            data = cursor.fetchall()
            filename = f"housing_payments_{timestamp}.csv"

            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Payment ID', 'Student ID', 'First Name', 'Last Name',
                               'Amount', 'Payment Date', 'Payment Method', 'Period Start',
                               'Period End', 'Status', 'Building', 'Room'])
                writer.writerows(data)

            print(f"Payment data exported to {filename}")

        elif choice == '6':
            # Export maintenance requests
            cursor.execute('''
            SELECT m.request_id, m.student_id, s.first_name, s.last_name,
                   b.building_name, r.room_number, m.request_date, m.issue_type,
                   m.description, m.priority, m.status, m.assigned_to, m.completion_date
            FROM housing_maintenance_requests m
            JOIN students s ON m.student_id = s.student_id
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            ORDER BY m.request_date DESC
            ''')

            data = cursor.fetchall()
            filename = f"maintenance_requests_{timestamp}.csv"

            with open(filename, 'w', newline='') as csvfile:
                import csv
                writer = csv.writer(csvfile)
                writer.writerow(['Request ID', 'Student ID', 'First Name', 'Last Name',
                               'Building', 'Room', 'Request Date', 'Issue Type',
                               'Description', 'Priority', 'Status', 'Assigned To', 'Completion Date'])
                writer.writerows(data)

            print(f"Maintenance requests exported to {filename}")

        else:
            print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error exporting data: {e}")

@log_read(module="housing", description="Searching housing records")
def search_housing_records():
    """Search across housing records"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to search records.")
        return

    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to search records.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nHousing Records Search")
        print("=" * 30)
        print("1. Search by Student Name/ID")
        print("2. Search by Room Number")
        print("3. Search by Building")
        print("4. Search Maintenance Requests")
        print("5. Cancel")

        choice = input("\nSelect search type (1-5): ")

        if choice == '5':
            conn.close()
            return

        if choice == '1':
            # Search by student
            search_term = input("Enter student name or ID: ").strip()

            cursor.execute('''
            SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.email_address,
                   a.assignment_id, b.building_name, r.room_number, a.status
            FROM students s
            LEFT JOIN housing_assignments a ON s.student_id = a.student_id
            LEFT JOIN housing_rooms r ON a.room_id = r.room_id
            LEFT JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE s.student_id LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
            ORDER BY s.last_name, s.first_name
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

            results = cursor.fetchall()

            if results:
                print(f"\nSearch Results for '{search_term}':")
                print("-" * 80)

                for result in results:
                    print(f"Student: {result[1]} {result[2]} ({result[0]})")
                    print(f"Email: {result[3]}")
                    if result[4]:  # Has assignment
                        print(f"Housing: Room {result[6]} in {result[5]} - Status: {result[7]}")
                    else:
                        print("Housing: No current assignment")
                    print()
            else:
                print(f"No results found for '{search_term}'")

        elif choice == '2':
            # Search by room number
            room_search = input("Enter room number: ").strip()

            cursor.execute('''
            SELECT r.room_id, r.room_number, b.building_name, r.room_type, r.status,
                   r.monthly_rent, a.student_id, s.first_name, s.last_name
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE r.room_number LIKE ?
            ORDER BY b.building_name, r.room_number
            ''', (f'%{room_search}%',))

            results = cursor.fetchall()

            if results:
                print(f"\nRoom Search Results for '{room_search}':")
                print("-" * 80)

                for result in results:
                    print(f"Room {result[1]} in {result[2]}")
                    print(f"Type: {result[3]} | Status: {result[4]} | Rent: ${result[5]}")
                    if result[6]:  # Has occupant
                        print(f"Occupant: {result[7]} {result[8]} ({result[6]})")
                    else:
                        print("Occupant: None")
                    print()
            else:
                print(f"No rooms found matching '{room_search}'")

        elif choice == '3':
            # Search by building
            building_search = input("Enter building name: ").strip()

            cursor.execute('''
            SELECT b.building_name, b.address, b.total_rooms, b.available_rooms,
                   COUNT(a.assignment_id) as active_assignments
            FROM housing_buildings b
            LEFT JOIN housing_rooms r ON b.building_id = r.building_id
            LEFT JOIN housing_assignments a ON r.room_id = a.room_id AND a.status = 'Active'
            WHERE b.building_name LIKE ?
            GROUP BY b.building_id, b.building_name, b.address, b.total_rooms, b.available_rooms
            ORDER BY b.building_name
            ''', (f'%{building_search}%',))

            results = cursor.fetchall()

            if results:
                print(f"\nBuilding Search Results for '{building_search}':")
                print("-" * 80)

                for result in results:
                    print(f"Building: {result[0]}")
                    print(f"Address: {result[1]}")
                    print(f"Total Rooms: {result[2]} | Available: {result[3]} | Active Assignments: {result[4]}")
                    print()
            else:
                print(f"No buildings found matching '{building_search}'")

        elif choice == '4':
            # Search maintenance requests
            search_term = input("Enter search term (issue type, description, or student name): ").strip()

            cursor.execute('''
            SELECT m.request_id, m.request_date, m.issue_type, m.description, m.priority, m.status,
                   s.first_name, s.last_name, b.building_name, r.room_number
            FROM housing_maintenance_requests m
            JOIN students s ON m.student_id = s.student_id
            JOIN housing_rooms r ON m.room_id = r.room_id
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE m.issue_type LIKE ? OR m.description LIKE ? OR s.first_name LIKE ? OR s.last_name LIKE ?
            ORDER BY m.request_date DESC
            ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

            results = cursor.fetchall()

            if results:
                print(f"\nMaintenance Request Search Results for '{search_term}':")
                print("-" * 80)

                for result in results:
                    print(f"Request ID: {result[0]} | Date: {result[1]}")
                    print(f"Issue: {result[2]} | Priority: {result[4]} | Status: {result[5]}")
                    print(f"Student: {result[6]} {result[7]} | Room: {result[9]} in {result[8]}")
                    print(f"Description: {result[3]}")
                    print()
            else:
                print(f"No maintenance requests found matching '{search_term}'")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error searching records: {e}")

@log_read(module="housing", description="Checking room availability")
def check_room_availability():
    """Check room availability and generate availability report"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to check room availability.")
        return

    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to check room availability.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nRoom Availability Check")
        print("=" * 30)
        print("1. Check by Building")
        print("2. Check by Room Type")
        print("3. Check All Available Rooms")
        print("4. Check Accessible Rooms")
        print("5. Cancel")

        choice = input("\nSelect option (1-5): ")

        if choice == '5':
            conn.close()
            return

        if choice == '1':
            # Check by building
            cursor.execute('SELECT building_id, building_name FROM housing_buildings ORDER BY building_name')
            buildings = cursor.fetchall()

            if not buildings:
                print("No buildings found.")
                conn.close()
                return

            print("\nSelect Building:")
            for i, (bid, bname) in enumerate(buildings, 1):
                print(f"{i}. {bname}")

            while True:
                try:
                    bchoice = int(input("\nSelect building (enter number): "))
                    if 1 <= bchoice <= len(buildings):
                        building_id = buildings[bchoice - 1][0]
                        building_name = buildings[bchoice - 1][1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(buildings)}.")
                except ValueError:
                    print("Please enter a valid number.")

            cursor.execute('''
            SELECT room_number, floor_number, room_type, max_occupants, monthly_rent, is_accessible
            FROM housing_rooms
            WHERE building_id = ? AND status = 'Available'
            ORDER BY floor_number, room_number
            ''', (building_id,))

            available_rooms = cursor.fetchall()

            if available_rooms:
                print(f"\nAvailable Rooms in {building_name}:")
                print("-" * 70)
                print(f"{'Room':<8} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}")
                print("-" * 70)

                for room in available_rooms:
                    accessible = "Yes" if room[5] else "No"
                    print(f"{room[0]:<8} {room[1]:<8} {room[2]:<12} {room[3]:<10} ${room[4]:<9.2f} {accessible:<12}")

                print(f"\nTotal Available Rooms: {len(available_rooms)}")
            else:
                print(f"\nNo available rooms in {building_name}")

        elif choice == '2':
            # Check by room type
            room_types = ["Single", "Double", "Triple", "Suite", "Studio", "Apartment"]

            print("\nSelect Room Type:")
            for i, rtype in enumerate(room_types, 1):
                print(f"{i}. {rtype}")

            while True:
                try:
                    tchoice = int(input("\nSelect room type (enter number): "))
                    if 1 <= tchoice <= len(room_types):
                        room_type = room_types[tchoice - 1]
                        break
                    else:
                        print(f"Please enter a number between 1 and {len(room_types)}.")
                except ValueError:
                    print("Please enter a valid number.")

            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.max_occupants,
                   r.monthly_rent, r.is_accessible
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.room_type = ? AND r.status = 'Available'
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''', (room_type,))

            available_rooms = cursor.fetchall()

            if available_rooms:
                print(f"\nAvailable {room_type} Rooms:")
                print("-" * 80)
                print(f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}")
                print("-" * 80)

                for room in available_rooms:
                    accessible = "Yes" if room[5] else "No"
                    print(f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<10} ${room[4]:<9.2f} {accessible:<12}")

                print(f"\nTotal Available {room_type} Rooms: {len(available_rooms)}")
            else:
                print(f"\nNo available {room_type} rooms found")

        elif choice == '3':
            # Check all available rooms
            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.room_type,
                   r.max_occupants, r.monthly_rent, r.is_accessible
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.status = 'Available'
            ORDER BY b.building_name, r.floor_number, r.room_number
            ''')

            available_rooms = cursor.fetchall()

            if available_rooms:
                print(f"\nAll Available Rooms:")
                print("-" * 90)
                print(f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Accessible':<12}")
                print("-" * 90)

                for room in available_rooms:
                    accessible = "Yes" if room[6] else "No"
                    print(f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<12} {room[4]:<10} ${room[5]:<9.2f} {accessible:<12}")

                print(f"\nTotal Available Rooms: {len(available_rooms)}")

                # Summary by type
                cursor.execute('''
                SELECT room_type, COUNT(*) as count
                FROM housing_rooms
                WHERE status = 'Available'
                GROUP BY room_type
                ORDER BY room_type
                ''')

                type_summary = cursor.fetchall()

                print("\nAvailability Summary by Type:")
                print("-" * 30)
                for room_type, count in type_summary:
                    print(f"{room_type}: {count} rooms")

            else:
                print("\nNo available rooms found")

        elif choice == '4':
            # Check accessible rooms
            cursor.execute('''
            SELECT r.room_number, b.building_name, r.floor_number, r.room_type,
                   r.max_occupants, r.monthly_rent, r.status
            FROM housing_rooms r
            JOIN housing_buildings b ON r.building_id = b.building_id
            WHERE r.is_accessible = 1
            ORDER BY r.status, b.building_name, r.floor_number, r.room_number
            ''')

            accessible_rooms = cursor.fetchall()

            if accessible_rooms:
                print(f"\nAccessible Rooms:")
                print("-" * 90)
                print(f"{'Room':<8} {'Building':<20} {'Floor':<8} {'Type':<12} {'Max Occ.':<10} {'Rent':<10} {'Status':<12}")
                print("-" * 90)

                available_count = 0
                for room in accessible_rooms:
                    if room[6] == 'Available':
                        available_count += 1
                    print(f"{room[0]:<8} {room[1]:<20} {room[2]:<8} {room[3]:<12} {room[4]:<10} ${room[5]:<9.2f} {room[6]:<12}")

                print(f"\nTotal Accessible Rooms: {len(accessible_rooms)}")
                print(f"Available Accessible Rooms: {available_count}")

            else:
                print("\nNo accessible rooms found")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error checking availability: {e}")

@log_read(module="housing", description="Generating maintenance summary")
def maintenance_summary():
    """Generate a summary of maintenance requests"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view maintenance summary.")
        return

    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to view maintenance summary.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nMaintenance Requests Summary")
        print("=" * 40)

        # Overall statistics
        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests')
        total_requests = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Open"')
        open_requests = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "In Progress"')
        in_progress = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE status = "Complete"')
        completed = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM housing_maintenance_requests WHERE priority = "Emergency"')
        emergency_requests = cursor.fetchone()[0]

        print(f"Total Requests: {total_requests}")
        print(f"Open Requests: {open_requests}")
        print(f"In Progress: {in_progress}")
        print(f"Completed: {completed}")
        print(f"Emergency Priority: {emergency_requests}")
        print()

        # Requests by status
        cursor.execute('''
        SELECT status, COUNT(*) as count
        FROM housing_maintenance_requests
        GROUP BY status
        ORDER BY
            CASE status
                WHEN 'Open' THEN 1
                WHEN 'In Progress' THEN 2
                WHEN 'Pending Parts' THEN 3
                WHEN 'Complete' THEN 4
                ELSE 5
            END
        ''')

        status_breakdown = cursor.fetchall()

        print("Requests by Status:")
        print("-" * 25)
        for status, count in status_breakdown:
            print(f"{status}: {count}")
        print()

        # Requests by priority
        cursor.execute('''
        SELECT priority, COUNT(*) as count
        FROM housing_maintenance_requests
        GROUP BY priority
        ORDER BY
            CASE priority
                WHEN 'Emergency' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Medium' THEN 3
                WHEN 'Low' THEN 4
                ELSE 5
            END
        ''')

        priority_breakdown = cursor.fetchall()

        print("Requests by Priority:")
        print("-" * 25)
        for priority, count in priority_breakdown:
            print(f"{priority}: {count}")
        print()

        # Requests by issue type
        cursor.execute('''
        SELECT issue_type, COUNT(*) as count
        FROM housing_maintenance_requests
        GROUP BY issue_type
        ORDER BY count DESC
        ''')

        issue_breakdown = cursor.fetchall()

        print("Requests by Issue Type:")
        print("-" * 30)
        for issue_type, count in issue_breakdown:
            print(f"{issue_type}: {count}")
        print()

        # Recent requests (last 7 days)
        seven_days_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')

        cursor.execute('''
        SELECT COUNT(*) FROM housing_maintenance_requests
        WHERE request_date >= ?
        ''', (seven_days_ago,))

        recent_requests = cursor.fetchone()[0]

        print(f"New Requests (Last 7 Days): {recent_requests}")

        # Outstanding emergency requests
        cursor.execute('''
        SELECT COUNT(*) FROM housing_maintenance_requests
        WHERE priority = 'Emergency' AND status != 'Complete'
        ''')

        outstanding_emergency = cursor.fetchone()[0]

        if outstanding_emergency > 0:
            print(f"\n\u26a0\ufe0f  URGENT: {outstanding_emergency} outstanding emergency request(s)")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating maintenance summary: {e}")

@log_read(module="housing", description="Generating upcoming move-outs report")
def upcoming_moveouts_report():
    """Generate a report of upcoming move-outs"""
    auth = _common.auth

    # Check permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view move-outs report.")
        return

    if not (auth.check_permission('manage_accommodations') or auth.check_permission('view_accommodations')):
        print("You don't have permission to view move-outs report.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nUpcoming Move-Outs Report")
        print("=" * 35)

        # Get current date and dates for next 30, 60, 90 days
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        thirty_days = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        sixty_days = (datetime.datetime.now() + datetime.timedelta(days=60)).strftime('%Y-%m-%d')
        ninety_days = (datetime.datetime.now() + datetime.timedelta(days=90)).strftime('%Y-%m-%d')

        # Next 30 days
        cursor.execute('''
        SELECT a.assignment_id, a.student_id, s.first_name, s.last_name,
               b.building_name, r.room_number, a.planned_move_out_date
        FROM housing_assignments a
        JOIN students s ON a.student_id = s.student_id
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.status = 'Active' AND a.planned_move_out_date BETWEEN ? AND ?
        ORDER BY a.planned_move_out_date
        ''', (today, thirty_days))

        next_30_days = cursor.fetchall()

        print(f"Move-outs in Next 30 Days ({len(next_30_days)} assignments):")
        print("-" * 80)

        if next_30_days:
            print(f"{'Student':<25} {'Room':<15} {'Building':<20} {'Move-out Date':<15}")
            print("-" * 80)

            for assignment in next_30_days:
                student_name = f"{assignment[2]} {assignment[3]}"
                room_info = f"{assignment[5]}"
                print(f"{student_name:<25} {room_info:<15} {assignment[4]:<20} {assignment[6]:<15}")
        else:
            print("No move-outs scheduled in the next 30 days.")

        print()

        # Next 31-60 days
        cursor.execute('''
        SELECT COUNT(*)
        FROM housing_assignments
        WHERE status = 'Active' AND planned_move_out_date BETWEEN ? AND ?
        ''', (thirty_days, sixty_days))

        next_31_60_days = cursor.fetchone()[0]

        # Next 61-90 days
        cursor.execute('''
        SELECT COUNT(*)
        FROM housing_assignments
        WHERE status = 'Active' AND planned_move_out_date BETWEEN ? AND ?
        ''', (sixty_days, ninety_days))

        next_61_90_days = cursor.fetchone()[0]

        print("Summary:")
        print(f"Next 30 days: {len(next_30_days)} move-outs")
        print(f"Days 31-60: {next_31_60_days} move-outs")
        print(f"Days 61-90: {next_61_90_days} move-outs")

        # Buildings affected
        cursor.execute('''
        SELECT b.building_name, COUNT(*) as moveouts
        FROM housing_assignments a
        JOIN housing_rooms r ON a.room_id = r.room_id
        JOIN housing_buildings b ON r.building_id = b.building_id
        WHERE a.status = 'Active' AND a.planned_move_out_date BETWEEN ? AND ?
        GROUP BY b.building_id, b.building_name
        ORDER BY moveouts DESC
        ''', (today, ninety_days))

        buildings_affected = cursor.fetchall()

        if buildings_affected:
            print("\nBuildings Affected (Next 90 Days):")
            print("-" * 40)
            for building, count in buildings_affected:
                print(f"{building}: {count} move-outs")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"Error generating move-outs report: {e}")

def display_reports_menu():
    """Display the reports and analytics menu"""
    while True:
        print("\nHousing Reports & Analytics")
        print("==========================")
        print("1. Occupancy Report")
        print("2. Financial Report")
        print("3. Maintenance Summary")
        print("4. Upcoming Move-outs")
        print("5. Room Availability Check")
        print("6. Search Housing Records")
        print("7. Export Data")
        print("8. Back to Housing Menu")

        choice = input("\nEnter your choice (1-8): ")

        if choice == '1':
            generate_occupancy_report()
        elif choice == '2':
            generate_financial_report()
        elif choice == '3':
            maintenance_summary()
        elif choice == '4':
            upcoming_moveouts_report()
        elif choice == '5':
            check_room_availability()
        elif choice == '6':
            search_housing_records()
        elif choice == '7':
            export_housing_data()
        elif choice == '8':
            return
        else:
            print("Invalid choice. Please try again.")
