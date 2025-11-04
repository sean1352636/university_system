# Standard library imports
import os
import random
from university_system.infrastructure.database.db import sqlite3
import string
from datetime import datetime
from typing import Optional

# Local imports
from university_system.infrastructure.database.db import DatabaseManager, get_connection
from university_system.infrastructure.email import send_confirmation_email
from university_system.modules.domain.academics.services.academic_calendar import AcademicCalendarManager

# --- Shared auth wiring ---
try:
    from university_system.infrastructure.auth.user_authentication import UserAuth, get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    # Fallback so type hints don't explode if import order differs in some environments
    class UserAuth:  # type: ignore
        pass
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

# This module will receive the shared auth instance from the app entrypoint.
auth: Optional[UserAuth] = None

def set_auth(auth_obj: UserAuth) -> None:
    """Inject the shared authentication instance for this module."""
    global auth
    auth = auth_obj
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_obj)
# --- end auth wiring ---

def manage_equipment_system():
    """Main equipment management interface"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the equipment system.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        while True:
            print(f"\nEquipment Management System")
            print("1. Browse available equipment")
            print("2. Check out equipment")
            print("3. Return equipment")
            print("4. My equipment checkouts")
            print("5. Search equipment")
            
            if auth.check_permission('manage_facilities') or auth.check_permission('manage_all_clubs'):
                print("6. Add new equipment")
                print("7. Update equipment status")
                print("8. View all checkouts")
                print("9. Equipment maintenance tracking")
                print("10. Generate equipment reports")
                print("11. Return to main menu")
                max_option = 11
            else:
                print("6. Return to main menu")
                max_option = 6
            
            choice = input("Choose an option: ").strip()
            
            if choice == '1':
                browse_available_equipment(cursor)
            elif choice == '2':
                check_out_equipment(student_id, cursor, conn)
            elif choice == '3':
                return_equipment(student_id, cursor, conn)
            elif choice == '4':
                view_my_equipment_checkouts(student_id, cursor)
            elif choice == '5':
                search_equipment(cursor)
            elif choice == '6' and max_option > 6:
                add_new_equipment(cursor, conn)
            elif choice == '7' and max_option > 6:
                update_equipment_status(cursor, conn)
            elif choice == '8' and max_option > 6:
                view_all_checkouts(cursor)
            elif choice == '9' and max_option > 6:
                equipment_maintenance_tracking(cursor, conn)
            elif choice == '10' and max_option > 6:
                generate_equipment_reports(cursor)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def browse_available_equipment(cursor):
    """Browse available equipment for checkout"""
    try:
        cursor.execute('''
        SELECT equipment_id, equipment_name, category, description, location,
               condition_status, availability_status
        FROM union_equipment
        WHERE availability_status = 'available'
        ORDER BY category, equipment_name
        ''')
        
        equipment = cursor.fetchall()
        
        if not equipment:
            print("No equipment available for checkout.")
            return
        
        print(f"\nAvailable Equipment:")
        print(f"{'ID':<6} {'Name':<25} {'Category':<15} {'Location':<15} {'Condition':<12}")
        print("-" * 80)
        
        current_category = ""
        for item in equipment:
            if item[2] != current_category:
                current_category = item[2]
                print(f"\n--- {current_category.upper()} ---")
            
            print(f"{item[0]:<6} {item[1][:25]:<25} {item[2]:<15} {item[4]:<15} {item[5]:<12}")
            if item[3]:
                print(f"       Description: {item[3]}")
        
        # Show detailed info for specific item
        item_id = input("\nEnter equipment ID for details (or press Enter to continue): ").strip()
        if item_id.isdigit():
            view_equipment_details(int(item_id), cursor)
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_equipment_details(equipment_id, cursor):
    """View detailed information about specific equipment"""
    try:
        cursor.execute('''
        SELECT equipment_name, category, description, serial_number, purchase_date,
               condition_status, location, availability_status, maintenance_due, replacement_cost
        FROM union_equipment
        WHERE equipment_id = ?
        ''', (equipment_id,))
        
        equipment = cursor.fetchone()
        
        if not equipment:
            print("Equipment not found.")
            return
        
        print(f"\nEquipment Details:")
        print("=" * 40)
        print(f"Name: {equipment[0]}")
        print(f"Category: {equipment[1]}")
        print(f"Description: {equipment[2] or 'No description'}")
        print(f"Serial Number: {equipment[3] or 'N/A'}")
        print(f"Purchase Date: {equipment[4] or 'Unknown'}")
        print(f"Condition: {equipment[5]}")
        print(f"Location: {equipment[6]}")
        print(f"Availability: {equipment[7]}")
        print(f"Next Maintenance: {equipment[8] or 'Not scheduled'}")
        print(f"Replacement Cost: £{equipment[9]:.2f}" if equipment[9] else "Unknown")
        
        # Show recent checkout history
        cursor.execute('''
        SELECT c.checkout_date, c.expected_return, c.actual_return,
               s.first_name, s.last_name, c.condition_out, c.condition_in
        FROM equipment_checkouts c
        JOIN students s ON c.borrower_id = s.student_id
        WHERE c.equipment_id = ?
        ORDER BY c.checkout_date DESC
        LIMIT 5
        ''', (equipment_id,))
        
        history = cursor.fetchall()
        
        if history:
            print(f"\nRecent Checkout History:")
            print(f"{'Borrower':<20} {'Checkout':<12} {'Return':<12} {'Condition Out':<12} {'Condition In':<12}")
            print("-" * 70)
            
            for record in history:
                return_date = record[2] if record[2] else "Not returned"
                condition_in = record[6] if record[6] else "N/A"
                print(f"{record[3]} {record[4]:<20} {record[0]:<12} {return_date:<12} {record[5]:<12} {condition_in:<12}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def check_out_equipment(student_id, cursor, conn):
    """Check out equipment to a student"""
    try:
        # Get student's club memberships for club checkouts
        cursor.execute('''
        SELECT c.club_id, c.club_name, m.role
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE m.student_id = ? AND c.status = 'active'
        AND m.role IN ('President', 'Treasurer', 'Secretary')
        ''', (student_id,))
        
        clubs = cursor.fetchall()
        
        # Show available equipment
        cursor.execute('''
        SELECT equipment_id, equipment_name, category, location, condition_status
        FROM union_equipment
        WHERE availability_status = 'available'
        ORDER BY category, equipment_name
        ''')
        
        available_equipment = cursor.fetchall()
        
        if not available_equipment:
            print("No equipment available for checkout.")
            return
        
        print(f"\nAvailable Equipment for Checkout:")
        print(f"{'ID':<6} {'Name':<30} {'Category':<15} {'Location':<15} {'Condition':<12}")
        print("-" * 80)
        
        for item in available_equipment:
            print(f"{item[0]:<6} {item[1][:30]:<30} {item[2]:<15} {item[3]:<15} {item[4]:<12}")
        
        equipment_id = input("\nEnter equipment ID to check out: ").strip()
        if not equipment_id.isdigit():
            print("Invalid equipment ID.")
            return
        
        equipment_id = int(equipment_id)
        
        # Verify equipment is available
        cursor.execute('''
        SELECT equipment_name, availability_status FROM union_equipment
        WHERE equipment_id = ?
        ''', (equipment_id,))
        
        equipment_info = cursor.fetchone()
        
        if not equipment_info:
            print("Equipment not found.")
            return
        
        if equipment_info[1] != 'available':
            print(f"Equipment '{equipment_info[0]}' is not available for checkout.")
            return
        
        print(f"\nChecking out: {equipment_info[0]}")
        
        # Checkout type
        checkout_type = input("Checkout for personal use or club? (personal/club): ").strip().lower()
        
        club_id = None
        if checkout_type == 'club':
            if not clubs:
                print("You are not an officer of any club. Checking out for personal use.")
            else:
                print("\nYour clubs:")
                for i, club in enumerate(clubs):
                    print(f"{i+1}. {club[1]} ({club[2]})")
                
                club_choice = input("Select club (enter number): ").strip()
                if club_choice.isdigit() and 1 <= int(club_choice) <= len(clubs):
                    club_id = clubs[int(club_choice)-1][0]
                else:
                    print("Invalid selection. Checking out for personal use.")
        
        # Checkout details
        expected_return = input("Expected return date (YYYY-MM-DD): ").strip()
        if not expected_return:
            print("Expected return date cannot be empty.")
            return
        
        try:
            datetime.strptime(expected_return, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return
        
        condition_out = input("Current condition of equipment (good/fair/poor): ").strip().lower()
        if condition_out not in ['good', 'fair', 'poor']:
            condition_out = 'good'
        
        notes = input("Additional notes (optional): ").strip()
        
        checkout_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create checkout record
        cursor.execute('''
        INSERT INTO equipment_checkouts (
            equipment_id, borrower_id, club_id, checkout_date, expected_return,
            condition_out, notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            equipment_id, student_id, club_id, checkout_date, expected_return,
            condition_out, notes, 'checked_out'
        ))
        
        # Update equipment availability
        cursor.execute('''
        UPDATE union_equipment 
        SET availability_status = 'checked_out'
        WHERE equipment_id = ?
        ''', (equipment_id,))
        
        conn.commit()
        
        checkout_id = cursor.lastrowid
        print(f"Equipment checked out successfully! Checkout ID: {checkout_id}")
        print(f"Please return by: {expected_return}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def return_equipment(student_id, cursor, conn):
    """Return checked out equipment"""
    try:
        # Get student's current checkouts
        cursor.execute('''
        SELECT c.checkout_id, e.equipment_name, c.checkout_date, c.expected_return,
               cl.club_name
        FROM equipment_checkouts c
        JOIN union_equipment e ON c.equipment_id = e.equipment_id
        LEFT JOIN student_clubs cl ON c.club_id = cl.club_id
        WHERE c.borrower_id = ? AND c.status = 'checked_out'
        ORDER BY c.expected_return
        ''', (student_id,))
        
        checkouts = cursor.fetchall()
        
        if not checkouts:
            print("You have no equipment checked out.")
            return
        
        print(f"\nYour Current Equipment Checkouts:")
        print(f"{'ID':<6} {'Equipment':<30} {'Checkout Date':<15} {'Due Date':<12} {'For Club':<20}")
        print("-" * 85)
        
        for checkout in checkouts:
            club_name = checkout[4] if checkout[4] else "Personal"
            print(f"{checkout[0]:<6} {checkout[1][:30]:<30} {checkout[2][:10]:<15} {checkout[3]:<12} {club_name:<20}")
        
        checkout_id = input("\nEnter checkout ID to return: ").strip()
        if not checkout_id.isdigit():
            print("Invalid checkout ID.")
            return
        
        checkout_id = int(checkout_id)
        
        # Verify checkout belongs to student
        cursor.execute('''
        SELECT c.equipment_id, e.equipment_name
        FROM equipment_checkouts c
        JOIN union_equipment e ON c.equipment_id = e.equipment_id
        WHERE c.checkout_id = ? AND c.borrower_id = ? AND c.status = 'checked_out'
        ''', (checkout_id, student_id))
        
        checkout_info = cursor.fetchone()
        
        if not checkout_info:
            print("Checkout not found or already returned.")
            return
        
        equipment_id = checkout_info[0]
        equipment_name = checkout_info[1]
        
        print(f"\nReturning: {equipment_name}")
        
        condition_in = input("Current condition of equipment (good/fair/poor/damaged): ").strip().lower()
        if condition_in not in ['good', 'fair', 'poor', 'damaged']:
            condition_in = 'good'
        
        notes = input("Return notes (any issues, damage, etc.): ").strip()
        
        actual_return = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update checkout record
        cursor.execute('''
        UPDATE equipment_checkouts 
        SET actual_return = ?, condition_in = ?, notes = COALESCE(notes, '') || ? || ?, status = 'returned'
        WHERE checkout_id = ?
        ''', (actual_return, condition_in, '\nReturn notes: ' if notes else '', notes, checkout_id))
        
        # Update equipment status
        new_availability = 'available'
        new_condition = condition_in
        
        if condition_in == 'damaged':
            new_availability = 'maintenance_required'
            new_condition = 'poor'
        elif condition_in == 'poor':
            new_availability = 'maintenance_required'
        
        cursor.execute('''
        UPDATE union_equipment 
        SET availability_status = ?, condition_status = ?
        WHERE equipment_id = ?
        ''', (new_availability, new_condition, equipment_id))
        
        conn.commit()
        
        print(f"Equipment returned successfully!")
        
        if new_availability == 'maintenance_required':
            print("Note: Equipment has been marked for maintenance due to its condition.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_my_equipment_checkouts(student_id, cursor):
    """View all equipment checkouts for the student"""
    try:
        cursor.execute('''
        SELECT c.checkout_id, e.equipment_name, c.checkout_date, c.expected_return,
               c.actual_return, c.condition_out, c.condition_in, c.status,
               cl.club_name
        FROM equipment_checkouts c
        JOIN union_equipment e ON c.equipment_id = e.equipment_id
        LEFT JOIN student_clubs cl ON c.club_id = cl.club_id
        WHERE c.borrower_id = ?
        ORDER BY c.checkout_date DESC
        ''', (student_id,))
        
        checkouts = cursor.fetchall()
        
        if not checkouts:
            print("You have no equipment checkout history.")
            return
        
        print(f"\nYour Equipment Checkout History:")
        print(f"{'ID':<6} {'Equipment':<25} {'Checkout':<12} {'Due':<12} {'Returned':<12} {'Status':<12} {'For':<15}")
        print("-" * 100)
        
        for checkout in checkouts:
            returned_date = checkout[4][:10] if checkout[4] else "Not returned"
            club_name = checkout[8] if checkout[8] else "Personal"
            print(f"{checkout[0]:<6} {checkout[1][:25]:<25} {checkout[2][:10]:<12} {checkout[3]:<12} {returned_date:<12} {checkout[7]:<12} {club_name:<15}")
        
        # Show statistics
        total_checkouts = len(checkouts)
        overdue_count = sum(1 for c in checkouts if c[7] == 'checked_out' and c[3] < datetime.now().strftime('%Y-%m-%d'))
        on_time_returns = sum(1 for c in checkouts if c[4] and c[4][:10] <= c[3])
        
        print(f"\nCheckout Statistics:")
        print(f"Total Checkouts: {total_checkouts}")
        print(f"Currently Overdue: {overdue_count}")
        print(f"On-time Returns: {on_time_returns}/{len([c for c in checkouts if c[4]])}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def search_equipment(cursor):
    """Search equipment by name, category, or description"""
    try:
        search_term = input("Enter search term (name, category, or description): ").strip()
        if not search_term:
            print("Search term cannot be empty.")
            return
        
        cursor.execute('''
        SELECT equipment_id, equipment_name, category, description, location,
               condition_status, availability_status
        FROM union_equipment
        WHERE equipment_name LIKE ? OR category LIKE ? OR description LIKE ?
        ORDER BY availability_status, category, equipment_name
        ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
        
        results = cursor.fetchall()
        
        if not results:
            print(f"No equipment found matching '{search_term}'.")
            return
        
        print(f"\nSearch Results for '{search_term}':")
        print(f"{'ID':<6} {'Name':<25} {'Category':<15} {'Location':<15} {'Condition':<12} {'Status':<15}")
        print("-" * 95)
        
        for item in results:
            print(f"{item[0]:<6} {item[1][:25]:<25} {item[2]:<15} {item[4]:<15} {item[5]:<12} {item[6]:<15}")
            if item[3]:
                print(f"       Description: {item[3]}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def add_new_equipment(cursor, conn):
    """Add new equipment to the inventory (admin only)"""
    try:
        print("\nAdd New Equipment")
        print("=================")
        
        equipment_name = input("Equipment name: ").strip()
        if not equipment_name:
            print("Equipment name cannot be empty.")
            return
        
        category = input("Category: ").strip()
        description = input("Description: ").strip()
        serial_number = input("Serial number (optional): ").strip()
        location = input("Location: ").strip()
        
        try:
            replacement_cost = float(input("Replacement cost (£): ").strip())
        except ValueError:
            replacement_cost = 0.0
        
        purchase_date = input("Purchase date (YYYY-MM-DD, optional): ").strip()
        if purchase_date:
            try:
                datetime.strptime(purchase_date, '%Y-%m-%d')
            except ValueError:
                print("Invalid date format. Leaving purchase date empty.")
                purchase_date = None
        else:
            purchase_date = None
        
        condition_status = input("Condition (good/fair/poor): ").strip().lower()
        if condition_status not in ['good', 'fair', 'poor']:
            condition_status = 'good'
        
        cursor.execute('''
        INSERT INTO union_equipment (
            equipment_name, category, description, serial_number, purchase_date,
            condition_status, location, availability_status, replacement_cost
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            equipment_name, category, description, serial_number, purchase_date,
            condition_status, location, 'available', replacement_cost
        ))
        
        conn.commit()
        equipment_id = cursor.lastrowid
        
        print(f"Equipment added successfully! Equipment ID: {equipment_id}")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def update_equipment_status(cursor, conn):
    """Update equipment status and condition (admin only)"""
    try:
        equipment_id = input("Enter equipment ID to update: ").strip()
        if not equipment_id.isdigit():
            print("Invalid equipment ID.")
            return
        
        equipment_id = int(equipment_id)
        
        # Get current equipment info
        cursor.execute('''
        SELECT equipment_name, condition_status, availability_status, location
        FROM union_equipment
        WHERE equipment_id = ?
        ''', (equipment_id,))
        
        equipment = cursor.fetchone()
        
        if not equipment:
            print("Equipment not found.")
            return
        
        print(f"\nUpdating: {equipment[0]}")
        print(f"Current condition: {equipment[1]}")
        print(f"Current availability: {equipment[2]}")
        print(f"Current location: {equipment[3]}")
        
        print(f"\nWhat would you like to update?")
        print("1. Condition status")
        print("2. Availability status")
        print("3. Location")
        print("4. Schedule maintenance")
        print("5. Cancel")
        
        choice = input("Choose option: ").strip()
        
        if choice == '1':
            new_condition = input("New condition (good/fair/poor): ").strip().lower()
            if new_condition in ['good', 'fair', 'poor']:
                cursor.execute('''
                UPDATE union_equipment 
                SET condition_status = ?
                WHERE equipment_id = ?
                ''', (new_condition, equipment_id))
                print("Condition updated.")
            else:
                print("Invalid condition.")
        
        elif choice == '2':
            print("Availability options:")
            print("- available")
            print("- checked_out")
            print("- maintenance_required")
            print("- out_of_service")
            
            new_availability = input("New availability: ").strip().lower()
            if new_availability in ['available', 'checked_out', 'maintenance_required', 'out_of_service']:
                cursor.execute('''
                UPDATE union_equipment 
                SET availability_status = ?
                WHERE equipment_id = ?
                ''', (new_availability, equipment_id))
                print("Availability updated.")
            else:
                print("Invalid availability status.")
        
        elif choice == '3':
            new_location = input("New location: ").strip()
            if new_location:
                cursor.execute('''
                UPDATE union_equipment 
                SET location = ?
                WHERE equipment_id = ?
                ''', (new_location, equipment_id))
                print("Location updated.")
        
        elif choice == '4':
            maintenance_date = input("Next maintenance date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(maintenance_date, '%Y-%m-%d')
                cursor.execute('''
                UPDATE union_equipment 
                SET maintenance_due = ?
                WHERE equipment_id = ?
                ''', (maintenance_date, equipment_id))
                print("Maintenance scheduled.")
            except ValueError:
                print("Invalid date format.")
        
        elif choice == '5':
            return
        
        else:
            print("Invalid choice.")
            return
        
        conn.commit()
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def equipment_maintenance_tracking(cursor, conn):
    """Track equipment maintenance (admin only)"""
    try:
        print("\nEquipment Maintenance Tracking")
        print("=" * 40)
        
        print("1. View equipment needing maintenance")
        print("2. Schedule maintenance")
        print("3. Complete maintenance")
        print("4. View maintenance history")
        print("5. Return to equipment menu")
        
        choice = input("Choose option: ").strip()
        
        if choice == '1':
            # View equipment needing maintenance
            cursor.execute('''
            SELECT equipment_id, equipment_name, condition_status, availability_status,
                   maintenance_due, location
            FROM union_equipment
            WHERE availability_status = 'maintenance_required' 
            OR condition_status IN ('poor', 'damaged')
            OR (maintenance_due IS NOT NULL AND maintenance_due <= date('now'))
            ORDER BY maintenance_due, condition_status
            ''')
            
            maintenance_needed = cursor.fetchall()
            
            if not maintenance_needed:
                print("No equipment currently needs maintenance.")
            else:
                print(f"\nEquipment Needing Maintenance:")
                print(f"{'ID':<6} {'Name':<25} {'Condition':<12} {'Status':<20} {'Due Date':<12} {'Location':<15}")
                print("-" * 95)
                
                for item in maintenance_needed:
                    due_date = item[4] if item[4] else "Not scheduled"
                    print(f"{item[0]:<6} {item[1][:25]:<25} {item[2]:<12} {item[3]:<20} {due_date:<12} {item[5]:<15}")
        
        elif choice == '2':
            # Schedule maintenance
            equipment_id = input("Enter equipment ID to schedule maintenance: ").strip()
            if not equipment_id.isdigit():
                print("Invalid equipment ID.")
                return
            
            maintenance_date = input("Maintenance date (YYYY-MM-DD): ").strip()
            try:
                datetime.strptime(maintenance_date, '%Y-%m-%d')
                
                cursor.execute('''
                UPDATE union_equipment 
                SET maintenance_due = ?, availability_status = 'maintenance_required'
                WHERE equipment_id = ?
                ''', (maintenance_date, equipment_id))
                
                conn.commit()
                print("Maintenance scheduled successfully.")
                
            except ValueError:
                print("Invalid date format.")
        
        elif choice == '3':
            # Complete maintenance
            equipment_id = input("Enter equipment ID for completed maintenance: ").strip()
            if not equipment_id.isdigit():
                print("Invalid equipment ID.")
                return
            
            new_condition = input("Equipment condition after maintenance (good/fair/poor): ").strip().lower()
            if new_condition not in ['good', 'fair', 'poor']:
                new_condition = 'good'
            
            new_availability = 'available' if new_condition in ['good', 'fair'] else 'maintenance_required'
            
            # Schedule next maintenance
            next_maintenance = input("Next maintenance date (YYYY-MM-DD, optional): ").strip()
            if next_maintenance:
                try:
                    datetime.strptime(next_maintenance, '%Y-%m-%d')
                except ValueError:
                    print("Invalid date format for next maintenance. Leaving empty.")
                    next_maintenance = None
            else:
                next_maintenance = None
            
            cursor.execute('''
            UPDATE union_equipment 
            SET condition_status = ?, availability_status = ?, maintenance_due = ?
            WHERE equipment_id = ?
            ''', (new_condition, new_availability, next_maintenance, equipment_id))
            
            conn.commit()
            print("Maintenance completed and equipment status updated.")
        
        elif choice == '4':
            # View maintenance history (simplified - would need separate maintenance log table for full history)
            print("Maintenance history feature would require additional database tables.")
            print("Currently showing equipment with recent maintenance dates.")
            
            cursor.execute('''
            SELECT equipment_id, equipment_name, condition_status, maintenance_due
            FROM union_equipment
            WHERE maintenance_due IS NOT NULL
            ORDER BY maintenance_due DESC
            ''')
            
            items = cursor.fetchall()
            
            if items:
                print(f"{'ID':<6} {'Name':<30} {'Condition':<12} {'Last/Next Maintenance':<20}")
                print("-" * 70)
                
                for item in items:
                    print(f"{item[0]:<6} {item[1][:30]:<30} {item[2]:<12} {item[3]:<20}")
        
        elif choice == '5':
            return
        
        else:
            print("Invalid choice.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def generate_equipment_reports(cursor):
    """Generate equipment usage and status reports (admin only)"""
    try:
        print("\nEquipment Reports")
        print("=" * 20)
        
        print("1. Equipment inventory summary")
        print("2. Usage statistics")
        print("3. Overdue equipment report")
        print("4. Maintenance schedule")
        print("5. Return to equipment menu")
        
        choice = input("Choose report: ").strip()
        
        if choice == '1':
            # Equipment inventory summary
            cursor.execute('''
            SELECT 
                category,
                COUNT(*) as total_items,
                SUM(CASE WHEN availability_status = 'available' THEN 1 ELSE 0 END) as available,
                SUM(CASE WHEN availability_status = 'checked_out' THEN 1 ELSE 0 END) as checked_out,
                SUM(CASE WHEN availability_status = 'maintenance_required' THEN 1 ELSE 0 END) as maintenance,
                SUM(CASE WHEN availability_status = 'out_of_service' THEN 1 ELSE 0 END) as out_of_service
            FROM union_equipment
            GROUP BY category
            ORDER BY category
            ''')
            
            inventory = cursor.fetchall()
            
            print(f"\nEquipment Inventory Summary:")
            print(f"{'Category':<20} {'Total':<8} {'Available':<10} {'Checked Out':<12} {'Maintenance':<12} {'Out of Service':<15}")
            print("-" * 80)
            
            total_items = 0
            total_available = 0
            total_checked_out = 0
            total_maintenance = 0
            total_out_of_service = 0
            
            for cat in inventory:
                print(f"{cat[0]:<20} {cat[1]:<8} {cat[2]:<10} {cat[3]:<12} {cat[4]:<12} {cat[5]:<15}")
                total_items += cat[1]
                total_available += cat[2]
                total_checked_out += cat[3]
                total_maintenance += cat[4]
                total_out_of_service += cat[5]
            
            print("-" * 80)
            print(f"{'TOTAL':<20} {total_items:<8} {total_available:<10} {total_checked_out:<12} {total_maintenance:<12} {total_out_of_service:<15}")
            
            utilization_rate = (total_checked_out / total_items * 100) if total_items > 0 else 0
            print(f"\nOverall utilization rate: {utilization_rate:.1f}%")
        
        elif choice == '2':
            # Usage statistics
            cursor.execute('''
            SELECT 
                e.equipment_name,
                COUNT(c.checkout_id) as total_checkouts,
                AVG(julianday(COALESCE(c.actual_return, date('now'))) - julianday(c.checkout_date)) as avg_checkout_days
            FROM union_equipment e
            LEFT JOIN equipment_checkouts c ON e.equipment_id = c.equipment_id
            GROUP BY e.equipment_id, e.equipment_name
            HAVING COUNT(c.checkout_id) > 0
            ORDER BY total_checkouts DESC
            LIMIT 20
            ''')
            
            usage_stats = cursor.fetchall()
            
            print(f"\nTop 20 Most Used Equipment:")
            print(f"{'Equipment':<30} {'Total Checkouts':<16} {'Avg Days Out':<12}")
            print("-" * 60)
            
            for stat in usage_stats:
                avg_days = f"{stat[2]:.1f}" if stat[2] else "N/A"
                print(f"{stat[0][:30]:<30} {stat[1]:<16} {avg_days:<12}")
        
        elif choice == '3':
            # Overdue equipment report
            cursor.execute('''
            SELECT e.equipment_name, s.first_name, s.last_name, s.email,
                   c.expected_return, c.checkout_date,
                   (julianday('now') - julianday(c.expected_return)) as days_overdue
            FROM equipment_checkouts c
            JOIN union_equipment e ON c.equipment_id = e.equipment_id
            JOIN students s ON c.borrower_id = s.student_id
            WHERE c.status = 'checked_out' AND c.expected_return < date('now')
            ORDER BY days_overdue DESC
            ''')
            
            overdue = cursor.fetchall()
            
            print(f"\nOverdue Equipment Report:")
            print(f"{'Equipment':<25} {'Borrower':<20} {'Email':<25} {'Due Date':<12} {'Days Overdue':<12}")
            print("-" * 100)
            
            for item in overdue:
                borrower = f"{item[1]} {item[2]}"
                print(f"{item[0][:25]:<25} {borrower[:20]:<20} {item[3][:25]:<25} {item[4]:<12} {int(item[6]):<12}")
            
            if overdue:
                print(f"\nTotal overdue items: {len(overdue)}")
            else:
                print("No overdue equipment.")
        
        elif choice == '4':
            # Maintenance schedule
            cursor.execute('''
            SELECT equipment_id, equipment_name, maintenance_due, condition_status, location
            FROM union_equipment
            WHERE maintenance_due IS NOT NULL
            ORDER BY maintenance_due
            ''')
            
            maintenance = cursor.fetchall()
            
            print(f"\nMaintenance Schedule:")
            print(f"{'ID':<6} {'Equipment':<30} {'Due Date':<12} {'Condition':<12} {'Location':<15}")
            print("-" * 80)
            
            for item in maintenance:
                print(f"{item[0]:<6} {item[1][:30]:<30} {item[2]:<12} {item[3]:<12} {item[4]:<15}")
            
            if not maintenance:
                print("No maintenance scheduled.")
        
        elif choice == '5':
            return
        
        else:
            print("Invalid choice.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def request_facility_booking():
    """Request to book a facility"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to book facilities.")
        return
    
    if not auth.check_permission('request_facility_booking'):
        print("You don't have permission to book facilities.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Show available facilities
        view_facilities()
        
        facility_id = input("\nEnter the ID of the facility you want to book: ").strip()
        if not facility_id.isdigit():
            print("Invalid facility ID.")
            conn.close()
            return
        
        # Check if facility exists
        cursor.execute('''
        SELECT facility_name FROM union_facilities
        WHERE facility_id = ? AND status = 'available'
        ''', (facility_id,))
        
        facility = cursor.fetchone()
        
        if not facility:
            print("Facility not found or not available.")
            conn.close()
            return
        
        # Ask for booking details
        date = input("Booking date (YYYY-MM-DD): ").strip()
        start_time = input("Start time (HH:MM): ").strip()
        end_time = input("End time (HH:MM): ").strip()
        
        # Check if booking slot is available
        cursor.execute('''
        SELECT COUNT(*) FROM facility_bookings
        WHERE facility_name = ? AND booking_date = ? AND 
        ((start_time <= ? AND end_time > ?) OR
         (start_time < ? AND end_time >= ?) OR
         (start_time >= ? AND end_time <= ?))
        AND status IN ('approved', 'pending')
        ''', (facility[0], date, start_time, start_time, end_time, end_time, start_time, end_time))
        
        if cursor.fetchone()[0] > 0:
            print("Sorry, this facility is already booked for the requested time slot.")
            conn.close()
            return
        
        # Ask if booking for self or for a club
        booking_type = input("Is this booking for a club? (y/n): ").strip().lower()
        club_id = None
        
        if booking_type == 'y':
            # Show clubs the student is an officer of
            cursor.execute('''
            SELECT c.club_id, c.club_name
            FROM student_clubs c
            WHERE (c.president_id = ? OR c.treasurer_id = ? OR c.secretary_id = ?)
            AND c.status = 'active'
            ''', (student_id, student_id, student_id))
            
            clubs = cursor.fetchall()
            
            if not clubs:
                print("You are not an officer of any club.")
                booking_type = 'n'
            else:
                print("\nYour clubs:")
                for i, club in enumerate(clubs):
                    print(f"{i+1}. {club[1]}")
                
                choice = input("Select a club (enter number): ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(clubs):
                    club_id = clubs[int(choice)-1][0]
                else:
                    print("Invalid selection. Booking as individual.")
                    booking_type = 'n'
        
        purpose = input("Purpose of booking: ").strip()
        notes = input("Additional notes (optional): ").strip()
        
        # Create the booking request
        cursor.execute('''
        INSERT INTO facility_bookings (
            facility_name, booker_id, club_id, booking_date, start_time, end_time,
            purpose, status, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            facility[0], student_id, club_id, date, start_time, end_time,
            purpose, 'pending', notes
        ))
        
        conn.commit()
        
        booking_id = cursor.lastrowid
        print(f"Booking request submitted with ID: {booking_id}")
        print("Your booking is pending approval.")
        
        # Send confirmation email
        send_confirmation_email(student_id, f"Facility Booking Request: {facility[0]}", 
                                f"Your booking request for {facility[0]} on {date} from {start_time} to {end_time} has been submitted and is pending approval.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_my_bookings():
    """View my facility bookings"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to view your bookings.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        
        if not result:
            print("No student record is associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Get bookings
        cursor.execute('''
        SELECT b.booking_id, b.facility_name, b.booking_date, b.start_time, b.end_time,
               c.club_name, b.purpose, b.status
        FROM facility_bookings b
        LEFT JOIN student_clubs c ON b.club_id = c.club_id
        WHERE b.booker_id = ?
        ORDER BY b.booking_date, b.start_time
        ''', (student_id,))
        
        bookings = cursor.fetchall()
        
        if not bookings:
            print("You have no facility bookings.")
            conn.close()
            return
        
        print("\nYour Facility Bookings:")
        print("=======================")
        
        for booking in bookings:
            print(f"\nBooking ID: {booking[0]}")
            print(f"Facility: {booking[1]}")
            print(f"Date: {booking[2]}")
            print(f"Time: {booking[3]} - {booking[4]}")
            
            if booking[5]:
                print(f"Booked for: {booking[5]} (Club)")
            else:
                print("Booked for: Personal use")
                
            print(f"Purpose: {booking[6]}")
            print(f"Status: {booking[7]}")
            print("-" * 40)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def approve_facility_bookings():
    """Approve or reject facility booking requests (for admin or union reps)"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to manage bookings.")
        return
    
    if not (auth.check_permission('approve_facility_bookings') or auth.check_permission('manage_facilities')):
        print("You don't have permission to approve facility bookings.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get pending bookings
        cursor.execute('''
        SELECT b.booking_id, b.facility_name, b.booking_date, b.start_time, b.end_time,
               s.first_name, s.last_name, c.club_name, b.purpose
        FROM facility_bookings b
        JOIN students s ON b.booker_id = s.student_id
        LEFT JOIN student_clubs c ON b.club_id = c.club_id
        WHERE b.status = 'pending'
        ORDER BY b.booking_date, b.start_time
        ''')
        
        bookings = cursor.fetchall()
        
        if not bookings:
            print("No pending facility booking requests.")
            conn.close()
            return
        
        print("\nPending Facility Booking Requests:")
        print("=================================")
        
        for i, booking in enumerate(bookings):
            print(f"\n{i+1}. Booking ID: {booking[0]}")
            print(f"   Facility: {booking[1]}")
            print(f"   Date: {booking[2]}")
            print(f"   Time: {booking[3]} - {booking[4]}")
            print(f"   Booker: {booking[5]} {booking[6]}")
            
            if booking[7]:
                print(f"   Booked for: {booking[7]} (Club)")
            else:
                print("   Booked for: Personal use")
                
            print(f"   Purpose: {booking[8]}")
        
        print("\nEnter the number of the booking you want to process (or 0 to exit):")
        choice = input().strip()
        
        if choice == '0':
            conn.close()
            return
            
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(bookings):
            print("Invalid selection.")
            conn.close()
            return
        
        selected = bookings[int(choice)-1]
        booking_id = selected[0]
        
        print(f"\nProcessing Booking ID: {booking_id}")
        print("1. Approve booking")
        print("2. Reject booking")
        print("3. Request more information")
        
        action = input("Choose an action: ").strip()
        
        if action == '1':
            # Approve booking
            cursor.execute(
                'UPDATE facility_bookings SET status = ? WHERE booking_id = ?',
                ('approved', booking_id)
            )
            status = 'approved'
            message = f"Your facility booking request for {selected[1]} on {selected[2]} has been approved."
        
        elif action == '2':
            # Reject booking
            reason = input("Reason for rejection: ").strip()
            cursor.execute(
                'UPDATE facility_bookings SET status = ?, notes = ? WHERE booking_id = ?',
                ('rejected', f"Rejected: {reason}", booking_id)
            )
            status = 'rejected'
            message = f"Your facility booking request for {selected[1]} on {selected[2]} has been rejected. Reason: {reason}"
        
        elif action == '3':
            # Request more info
            info_needed = input("What additional information is needed? ").strip()
            cursor.execute(
                'UPDATE facility_bookings SET notes = ? WHERE booking_id = ?',
                (f"More information needed: {info_needed}", booking_id)
            )
            status = 'pending'
            message = f"Additional information needed for your facility booking request: {info_needed}"
        
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        conn.commit()
        print(f"Booking {booking_id} status updated to: {status}")
        
        # Get booker's student ID for email notification
        cursor.execute('SELECT booker_id FROM facility_bookings WHERE booking_id = ?', (booking_id,))
        booker_id = cursor.fetchone()[0]
        
        # Send email notification
        send_confirmation_email(booker_id, f"Facility Booking Update: {selected[1]}", message)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def display_facility_menu():
    """Display the facility management menu"""
    global auth
    
    while True:
        print("\nFacilities")
        print("==========")
        
        # Options
        print("1. View Available Facilities")
        
        if auth.check_permission('request_facility_booking'):
            print("2. Request Facility Booking")
            print("3. View My Bookings")
            max_option = 4
        else:
            max_option = 2
        
        if auth.check_permission('approve_facility_bookings') or auth.check_permission('manage_facilities'):
            print(f"{max_option}. Approve Facility Bookings")
            max_option += 1
        
        print(f"{max_option}. Return to Student Union Menu")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1':
            # View Facilities
            view_facilities()
        elif choice == '2' and auth.check_permission('request_facility_booking'):
            # Request Booking
            request_facility_booking()
        elif choice == '3' and auth.check_permission('request_facility_booking'):
            # View My Bookings
            view_my_bookings()
        elif (choice == '4' and auth.check_permission('approve_facility_bookings')) or \
             (choice == '2' and not auth.check_permission('request_facility_booking') and 
              auth.check_permission('approve_facility_bookings')):
            # Approve Bookings
            approve_facility_bookings()
        elif choice == str(max_option):
            # Return to Student Union Menu
            return
        else:
            print("Invalid choice. Please try again.")
