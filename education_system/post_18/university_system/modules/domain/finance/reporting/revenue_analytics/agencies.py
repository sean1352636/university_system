from education_system.post_18.university_system.infrastructure.database.db import get_connection
from datetime import datetime


def manage_collection_agencies():
    """Manage collection agencies"""
    while True:
        print("\n" + "=" * 40)
        print("COLLECTION AGENCIES MANAGEMENT")
        print("=" * 40)
        print("1. View Collection Agencies")
        print("2. Add New Agency")
        print("3. Edit Agency")
        print("4. Deactivate Agency")
        print("5. Agency Performance")
        print("6. Return to Collection Menu")

        choice = input("Enter your choice (1-6): ").strip()

        if choice == '1':
            view_collection_agencies()
        elif choice == '2':
            add_collection_agency()
        elif choice == '3':
            edit_collection_agency()
        elif choice == '4':
            deactivate_collection_agency()
        elif choice == '5':
            from education_system.post_18.university_system.modules.domain.finance.reporting.revenue_analytics.collection_reports import agency_performance_report
            agency_performance_report()
        elif choice == '6':
            return
        else:
            print("Invalid choice. Please try again.")

def view_collection_agencies():
    """View all collection agencies"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
        SELECT agency_id, agency_name, contact_email, contact_phone,
               commission_rate, minimum_amount, is_active
        FROM collection_agencies
        ORDER BY is_active DESC, agency_name
        ''')

        agencies = cursor.fetchall()

        if not agencies:
            print("No collection agencies found.")
            return

        print("\nCollection Agencies:")
        print("=" * 100)
        print(f"{'ID':<5} {'Name':<25} {'Email':<30} {'Phone':<15} {'Commission':<10} {'Min Amount':<10} {'Active':<8}")
        print("-" * 100)

        for agency in agencies:
            agency_id, name, email, phone, commission, min_amount, active = agency
            active_str = "Yes" if active else "No"

            print(f"{agency_id:<5} {name:<25} {email or 'N/A':<30} {phone or 'N/A':<15} {commission or 0:.1f}%{'':<5} £{min_amount or 0:<9.2f} {active_str:<8}")

        print("=" * 100)

        conn.close()

    except Exception as e:
        print(f"Error viewing collection agencies: {e}")

def add_collection_agency():
    """Add a new collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nAdding New Collection Agency:")

        agency_name = input("Enter agency name: ").strip()
        if not agency_name:
            print("Agency name is required.")
            return

        contact_email = input("Enter contact email: ").strip()
        contact_phone = input("Enter contact phone: ").strip()

        try:
            commission_rate = float(input("Enter commission rate (%): "))
            minimum_amount = float(input("Enter minimum debt amount: £"))
        except ValueError:
            print("Invalid numeric input.")
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO collection_agencies
        (agency_name, contact_email, contact_phone, commission_rate, minimum_amount, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (agency_name, contact_email, contact_phone, commission_rate, minimum_amount, 1, now, now))

        agency_id = cursor.lastrowid

        conn.commit()

        print("\nCollection agency added successfully!")
        print(f"Agency ID: {agency_id}")
        print(f"Name: {agency_name}")
        print(f"Commission: {commission_rate}%")
        print(f"Minimum Amount: £{minimum_amount:.2f}")

        conn.close()

    except Exception as e:
        print(f"Error adding collection agency: {e}")

def edit_collection_agency():
    """Edit an existing collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        agency_id = input("Enter agency ID to edit: ").strip()

        # Get current agency details
        cursor.execute('''
        SELECT agency_name, contact_email, contact_phone, commission_rate, minimum_amount
        FROM collection_agencies
        WHERE agency_id = ?
        ''', (agency_id,))

        agency = cursor.fetchone()

        if not agency:
            print("Agency not found.")
            return

        current_name, current_email, current_phone, current_commission, current_minimum = agency

        print(f"\nEditing Agency {agency_id}: {current_name}")

        # Get new values
        new_name = input(f"Enter new name (current: {current_name}): ").strip()
        if not new_name:
            new_name = current_name

        new_email = input(f"Enter new email (current: {current_email}): ").strip()
        if not new_email:
            new_email = current_email

        new_phone = input(f"Enter new phone (current: {current_phone}): ").strip()
        if not new_phone:
            new_phone = current_phone

        commission_input = input(f"Enter new commission rate (current: {current_commission}%): ").strip()
        if commission_input:
            try:
                new_commission = float(commission_input)
            except ValueError:
                print("Invalid commission rate, keeping current value.")
                new_commission = current_commission
        else:
            new_commission = current_commission

        minimum_input = input(f"Enter new minimum amount (current: £{current_minimum}): ").strip()
        if minimum_input:
            try:
                new_minimum = float(minimum_input)
            except ValueError:
                print("Invalid minimum amount, keeping current value.")
                new_minimum = current_minimum
        else:
            new_minimum = current_minimum

        # Update agency
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE collection_agencies
        SET agency_name = ?, contact_email = ?, contact_phone = ?,
            commission_rate = ?, minimum_amount = ?, updated_at = ?
        WHERE agency_id = ?
        ''', (new_name, new_email, new_phone, new_commission, new_minimum, now, agency_id))

        conn.commit()

        print(f"Agency {agency_id} updated successfully!")

        conn.close()

    except Exception as e:
        print(f"Error editing collection agency: {e}")

def deactivate_collection_agency():
    """Deactivate a collection agency"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        agency_id = input("Enter agency ID to deactivate: ").strip()

        # Get agency details
        cursor.execute('''
        SELECT agency_name FROM collection_agencies
        WHERE agency_id = ? AND is_active = 1
        ''', (agency_id,))

        agency = cursor.fetchone()

        if not agency:
            print("Agency not found or already inactive.")
            return

        agency_name = agency[0]

        # Check for active cases
        cursor.execute('''
        SELECT COUNT(*) FROM collection_cases
        WHERE agency_id = ? AND case_status NOT IN ('resolved', 'closed')
        ''', (agency_id,))

        active_cases = cursor.fetchone()[0]

        if active_cases > 0:
            print(f"Warning: Agency has {active_cases} active cases.")
            confirm = input("Deactivate anyway? Cases will need to be reassigned. (y/n): ").strip().lower()
            if confirm != 'y':
                return

        confirm = input(f"Deactivate agency '{agency_name}'? (y/n): ").strip().lower()
        if confirm != 'y':
            return

        # Deactivate agency
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        UPDATE collection_agencies
        SET is_active = 0, updated_at = ?
        WHERE agency_id = ?
        ''', (now, agency_id))

        conn.commit()

        print(f"Agency '{agency_name}' deactivated successfully!")

        if active_cases > 0:
            print(f"Remember to reassign {active_cases} active cases to other agencies.")

        conn.close()

    except Exception as e:
        print(f"Error deactivating collection agency: {e}")

def setup_collection_workflows():
    """Setup automated collection workflows"""
    print("\nCollection Workflow Setup:")
    print("This would configure automated workflows for:")
    print("- Automatic case creation for overdue accounts")
    print("- Agency assignment based on debt amount")
    print("- Escalation procedures")
    print("- Reminder schedules")
    print("\n[Feature would be implemented with workflow engine]")
