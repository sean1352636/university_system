#!/usr/bin/env python3
"""
Medical Accommodation CLI
Complete command-line interface for medical accommodation management system
with full feature parity to the GUI version.
"""

import os
import sys
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import csv
import json
from pathlib import Path

# Import accommodation service functions
try:
    from education_system.systems.university.domain.operations.campus.housing.services.accommodation import (
        init_accommodation_db,
        get_accommodation_types,
        validate_student_id,
        validate_date,
        check_conflict,
        add_accommodation,
        update_accommodation,
        remove_accommodation,
        view_accommodation_by_id,
        view_accommodations,
        view_students_by_accommodation,
        approve_accommodation,
        save_template,
        apply_template,
        bulk_import_from_csv,
        notify_student,
        check_expiry_notifications,
        export_accommodations,
        show_dashboard_metrics,
        generate_statistics_report,
        import_from_json,
        log_action,
        set_auth,
        TEMPLATES_TABLE,
        upload_accommodation_document,
    )
    SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Accommodation service not available: {e}")
    SERVICE_AVAILABLE = False

# Validate table name constants at module load time
if SERVICE_AVAILABLE:
    from education_system.systems.university.infrastructure.sql_safety import validate_table_name
    validate_table_name(TEMPLATES_TABLE)

# Database imports
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure import paths

# Activity logging
try:
    from education_system.systems.university.infrastructure.activity_logger import log_activity
except ImportError:
    def log_activity(action, entity, **kwargs):
        print(f"[LOG] {action} {entity}: {kwargs}")

class MedicalAccommodationCLI:
    """Medical Accommodation Command Line Interface"""

    def __init__(self, auth=None):
        """Initialize the CLI with authentication"""
        self.auth = auth
        self.current_user = None

        # Get current user from auth
        if self.auth and hasattr(self.auth, 'current_user'):
            self.current_user = self.auth.current_user
            print(f"\n✓ Logged in as: {self.current_user.get('username', 'Unknown')} ({self.current_user.get('role', 'user')})")

        # Set auth in service module
        if SERVICE_AVAILABLE and self.auth:
            set_auth(self.auth)

        # Initialize database
        if SERVICE_AVAILABLE:
            init_accommodation_db()

    def clear_screen(self):
        """Clear the terminal screen"""
        print("\033[2J\033[H", end="", flush=True)

    def pause(self):
        """Pause and wait for user input"""
        input("\nPress Enter to continue...")

    def print_header(self, title):
        """Print a formatted header"""
        print("\n" + "="*70)
        print(f"  {title}")
        print("="*70)

    def print_section(self, title):
        """Print a section header"""
        print(f"\n{'─'*70}")
        print(f"  {title}")
        print(f"{'─'*70}")

    def get_user_identifier(self):
        """Get current user identifier for logging"""
        if self.current_user:
            return self.current_user.get('username') or self.current_user.get('email') or 'system'
        return 'system'

    # ==================== Main Menu ====================

    def run(self):
        """Main menu loop"""
        while True:
            self.clear_screen()
            self.print_header("🏥 MEDICAL ACCOMMODATION MANAGEMENT SYSTEM")

            print("\n📋 ACCOMMODATION MANAGEMENT:")
            print("  1. Add New Accommodation")
            print("  2. View All Accommodations")
            print("  3. View Accommodation Details")
            print("  4. Update Accommodation")
            print("  5. Remove Accommodation")
            print("  6. Approve/Reject Accommodation")

            print("\n🔍 SEARCH & FILTER:")
            print("  7. Search Accommodations")
            print("  8. View by Accommodation Type")
            print("  9. View by Status")

            print("\n📄 TEMPLATES:")
            print("  10. Create Template")
            print("  11. Apply Template")
            print("  12. View Templates")
            print("  13. Delete Template")

            print("\n📊 DASHBOARD & REPORTS:")
            print("  14. View Dashboard Metrics")
            print("  15. Generate Statistics Report")
            print("  16. View Students by Accommodation")

            print("\n📥 IMPORT/EXPORT:")
            print("  17. Import from CSV")
            print("  18. Import from JSON")
            print("  19. Export Accommodations")

            print("\n📎 DOCUMENTS:")
            print("  20. Upload Document")
            print("  21. View Documents")

            print("\n🔔 NOTIFICATIONS:")
            print("  22. Check Expiry Notifications")
            print("  23. Send Student Notification")

            print("\n  0. Exit")

            choice = input("\n👉 Enter your choice: ").strip()

            if choice == '0':
                print("\n👋 Goodbye!")
                break
            elif choice == '1':
                self.add_accommodation_menu()
            elif choice == '2':
                self.view_all_accommodations()
            elif choice == '3':
                self.view_accommodation_details()
            elif choice == '4':
                self.update_accommodation_menu()
            elif choice == '5':
                self.remove_accommodation_menu()
            elif choice == '6':
                self.approve_reject_menu()
            elif choice == '7':
                self.search_accommodations()
            elif choice == '8':
                self.view_by_type()
            elif choice == '9':
                self.view_by_status()
            elif choice == '10':
                self.create_template_menu()
            elif choice == '11':
                self.apply_template_menu()
            elif choice == '12':
                self.view_templates()
            elif choice == '13':
                self.delete_template_menu()
            elif choice == '14':
                self.view_dashboard()
            elif choice == '15':
                self.generate_statistics()
            elif choice == '16':
                self.view_students_by_accommodation_menu()
            elif choice == '17':
                self.import_csv_menu()
            elif choice == '18':
                self.import_json_menu()
            elif choice == '19':
                self.export_menu()
            elif choice == '20':
                self.upload_document_menu()
            elif choice == '21':
                self.view_documents_menu()
            elif choice == '22':
                self.check_notifications()
            elif choice == '23':
                self.send_notification_menu()
            else:
                print("\n❌ Invalid choice. Please try again.")
                self.pause()

    # ==================== Accommodation Management ====================

    def add_accommodation_menu(self):
        """Add new accommodation"""
        self.clear_screen()
        self.print_header("➕ ADD NEW ACCOMMODATION")

        try:
            # Get student ID
            student_id = input("\n📝 Student ID: ").strip()
            if not student_id:
                print("❌ Student ID is required")
                self.pause()
                return

            # Validate student ID
            if SERVICE_AVAILABLE:
                is_valid, error_msg = validate_student_id(student_id)
                if not is_valid:
                    print(f"❌ {error_msg}")
                    self.pause()
                    return

            # Get accommodation types
            if SERVICE_AVAILABLE:
                types = get_accommodation_types()
            else:
                types = ['Extended Time', 'Alternate Format', 'Note-Taking',
                        'Assistive Technology', 'Flexible Attendance']

            # Display accommodation types
            print("\n📋 Available Accommodation Types:")
            for i, acc_type in enumerate(types, 1):
                print(f"  {i}. {acc_type}")

            type_choice = input("\n👉 Select type (number or name): ").strip()

            # Parse type choice
            if type_choice.isdigit() and 1 <= int(type_choice) <= len(types):
                accommodation_type = types[int(type_choice) - 1]
            elif type_choice in types:
                accommodation_type = type_choice
            else:
                print("❌ Invalid accommodation type")
                self.pause()
                return

            # Get description
            print("\n💬 Description (optional, press Enter to skip):")
            description = input("  ").strip() or None

            # Get dates
            print("\n📅 Start Date (YYYY-MM-DD, or press Enter for today):")
            start_date = input("  ").strip()
            if not start_date:
                start_date = datetime.now().strftime('%Y-%m-%d')
            else:
                if SERVICE_AVAILABLE:
                    is_valid, error_msg = validate_date(start_date)
                    if not is_valid:
                        print(f"❌ {error_msg}")
                        self.pause()
                        return

            print("\n📅 End Date (YYYY-MM-DD, or press Enter for 1 year from start):")
            end_date = input("  ").strip()
            if not end_date:
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end_date = (start + timedelta(days=365)).strftime('%Y-%m-%d')
            else:
                if SERVICE_AVAILABLE:
                    is_valid, error_msg = validate_date(end_date)
                    if not is_valid:
                        print(f"❌ {error_msg}")
                        self.pause()
                        return

            # Get status
            print("\n📊 Status:")
            print("  1. Active")
            print("  2. Pending")
            print("  3. Suspended")
            status_choice = input("👉 Select status (default: Pending): ").strip()
            status_map = {'1': 'active', '2': 'pending', '3': 'suspended'}
            status = status_map.get(status_choice, 'pending')

            # Check for conflicts
            if SERVICE_AVAILABLE:
                has_conflict, conflict_msg = check_conflict(
                    student_id, accommodation_type, start_date, end_date
                )
                if has_conflict:
                    print(f"\n⚠️  Warning: {conflict_msg}")
                    confirm = input("Continue anyway? (y/n): ").strip().lower()
                    if confirm != 'y':
                        print("❌ Cancelled")
                        self.pause()
                        return

            # Additional notes
            print("\n📝 Additional Notes (optional):")
            notes = input("  ").strip() or None

            # Save to database
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO accommodations
                    (student_id, accommodation_type, description, start_date, end_date,
                     status, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, accommodation_type, description, start_date, end_date,
                      status, notes, now, now))

                accommodation_id = cursor.lastrowid
                conn.commit()

            # Log action
            if SERVICE_AVAILABLE:
                log_action('add', accommodation_id,
                          f"Added {accommodation_type} for {student_id}")

            log_activity('create', 'medical_accommodation',
                        accommodation_id=accommodation_id,
                        student_id=student_id,
                        type=accommodation_type)

            print(f"\n✅ Accommodation created successfully (ID: {accommodation_id})")

            # Offer to upload documents
            upload = input("\n📎 Upload supporting document? (y/n): ").strip().lower()
            if upload == 'y' and SERVICE_AVAILABLE:
                self.upload_document_for_accommodation(accommodation_id)

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_all_accommodations(self):
        """View all accommodations in a formatted list"""
        self.clear_screen()
        self.print_header("📋 ALL ACCOMMODATIONS")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.id, a.student_id, a.accommodation_type, a.start_date,
                           a.end_date, a.status, s.first_name, s.last_name
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    ORDER BY a.created_at DESC
                ''')

                accommodations = cursor.fetchall()

            if not accommodations:
                print("\n📭 No accommodations found")
            else:
                print(f"\n📊 Total: {len(accommodations)} accommodation(s)\n")

                # Table header
                print(f"{'ID':<6} {'Student ID':<12} {'Name':<25} {'Type':<25} {'Start':<12} {'End':<12} {'Status':<10}")
                print("─" * 120)

                # Table rows
                for acc in accommodations:
                    acc_id, student_id, acc_type, start, end, status, fname, lname = acc
                    name = f"{fname or ''} {lname or ''}".strip() or "N/A"

                    # Truncate long fields
                    name = name[:24]
                    acc_type = acc_type[:24]

                    # Status indicator
                    status_icon = {
                        'active': '🟢',
                        'pending': '🟡',
                        'suspended': '🔴',
                        'expired': '⚫'
                    }.get(status.lower(), '⚪')

                    print(f"{acc_id:<6} {student_id:<12} {name:<25} {acc_type:<25} "
                          f"{start or 'N/A':<12} {end or 'N/A':<12} {status_icon} {status:<8}")

                print("\n💡 Tip: Use option 3 to view detailed information about a specific accommodation")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_accommodation_details(self):
        """View detailed information about a specific accommodation"""
        self.clear_screen()
        self.print_header("🔍 VIEW ACCOMMODATION DETAILS")

        acc_id = input("\n📝 Enter Accommodation ID: ").strip()
        if not acc_id or not acc_id.isdigit():
            print("❌ Invalid ID")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.*, s.first_name, s.last_name, s.email_address
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    WHERE a.id = ?
                ''', (acc_id,))

                acc = cursor.fetchone()

            if not acc:
                print(f"\n❌ Accommodation {acc_id} not found")
            else:
                # Unpack accommodation data
                (acc_id, student_id, acc_type, description, start_date, end_date,
                 status, approved_by, approval_date, notes, created_at, updated_at,
                 first_name, last_name, email) = acc

                # Display details
                self.print_section("Accommodation Information")
                print(f"  ID:                {acc_id}")
                print(f"  Student ID:        {student_id}")
                print(f"  Student Name:      {first_name or ''} {last_name or ''}")
                print(f"  Email:             {email or 'N/A'}")
                print(f"  Type:              {acc_type}")
                print(f"  Status:            {status}")

                self.print_section("Details")
                print(f"  Description:       {description or 'N/A'}")
                print(f"  Start Date:        {start_date or 'N/A'}")
                print(f"  End Date:          {end_date or 'N/A'}")
                print(f"  Notes:             {notes or 'N/A'}")

                self.print_section("Approval Information")
                print(f"  Approved By:       {approved_by or 'Not approved'}")
                print(f"  Approval Date:     {approval_date or 'N/A'}")

                self.print_section("Metadata")
                print(f"  Created:           {created_at}")
                print(f"  Last Updated:      {updated_at}")

                # Check for documents
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT COUNT(*) FROM documents
                        WHERE source_type = 'accommodation'
                          AND reference_id = ? AND reference_type = 'accommodation'
                    ''', (str(acc_id),))
                    doc_count = cursor.fetchone()[0]

                if doc_count > 0:
                    self.print_section("Documents")
                    print(f"  📎 {doc_count} document(s) attached")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def update_accommodation_menu(self):
        """Update an existing accommodation"""
        self.clear_screen()
        self.print_header("✏️  UPDATE ACCOMMODATION")

        acc_id = input("\n📝 Enter Accommodation ID to update: ").strip()
        if not acc_id or not acc_id.isdigit():
            print("❌ Invalid ID")
            self.pause()
            return

        try:
            # Fetch current data
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM accommodations WHERE id = ?', (acc_id,))
                current = cursor.fetchone()

            if not current:
                print(f"\n❌ Accommodation {acc_id} not found")
                self.pause()
                return

            # Display current values
            print("\n📋 Current Values:")
            print(f"  Student ID:        {current[1]}")
            print(f"  Type:              {current[2]}")
            print(f"  Description:       {current[3] or 'N/A'}")
            print(f"  Start Date:        {current[4] or 'N/A'}")
            print(f"  End Date:          {current[5] or 'N/A'}")
            print(f"  Status:            {current[6]}")
            print(f"  Notes:             {current[9] or 'N/A'}")

            print("\n💡 Press Enter to keep current value, or enter new value:")

            # Get new values
            student_id = input(f"\n📝 Student ID [{current[1]}]: ").strip() or current[1]

            # Get types
            if SERVICE_AVAILABLE:
                types = get_accommodation_types()
            else:
                types = ['Extended Time', 'Alternate Format', 'Note-Taking',
                        'Assistive Technology', 'Flexible Attendance']

            print(f"\n📋 Accommodation Type [{current[2]}]:")
            for i, t in enumerate(types, 1):
                print(f"  {i}. {t}")
            type_input = input("👉 Select (number/name) or press Enter: ").strip()

            if type_input:
                if type_input.isdigit() and 1 <= int(type_input) <= len(types):
                    acc_type = types[int(type_input) - 1]
                elif type_input in types:
                    acc_type = type_input
                else:
                    acc_type = current[2]
            else:
                acc_type = current[2]

            description = input(f"\n💬 Description [{current[3] or 'N/A'}]: ").strip()
            if description:
                description = description
            else:
                description = current[3]

            start_date = input(f"\n📅 Start Date [{current[4] or 'N/A'}]: ").strip() or current[4]
            end_date = input(f"\n📅 End Date [{current[5] or 'N/A'}]: ").strip() or current[5]

            print(f"\n📊 Status [{current[6]}]:")
            print("  1. Active")
            print("  2. Pending")
            print("  3. Suspended")
            print("  4. Expired")
            status_input = input("👉 Select or press Enter: ").strip()
            status_map = {'1': 'active', '2': 'pending', '3': 'suspended', '4': 'expired'}
            status = status_map.get(status_input, current[6])

            notes = input(f"\n📝 Notes [{current[9] or 'N/A'}]: ").strip()
            if notes:
                notes = notes
            else:
                notes = current[9]

            # Update database
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accommodations
                    SET student_id = ?, accommodation_type = ?, description = ?,
                        start_date = ?, end_date = ?, status = ?, notes = ?,
                        updated_at = ?
                    WHERE id = ?
                ''', (student_id, acc_type, description, start_date, end_date,
                      status, notes, now, acc_id))
                conn.commit()

            # Log action
            if SERVICE_AVAILABLE:
                log_action('update', acc_id, "Updated accommodation")

            log_activity('update', 'medical_accommodation',
                        accommodation_id=acc_id)

            print(f"\n✅ Accommodation {acc_id} updated successfully")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def remove_accommodation_menu(self):
        """Remove an accommodation"""
        self.clear_screen()
        self.print_header("🗑️  REMOVE ACCOMMODATION")

        acc_id = input("\n📝 Enter Accommodation ID to remove: ").strip()
        if not acc_id or not acc_id.isdigit():
            print("❌ Invalid ID")
            self.pause()
            return

        try:
            # Show accommodation details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT student_id, accommodation_type, status
                    FROM accommodations WHERE id = ?
                ''', (acc_id,))
                acc = cursor.fetchone()

            if not acc:
                print(f"\n❌ Accommodation {acc_id} not found")
                self.pause()
                return

            student_id, acc_type, status = acc
            print("\n📋 Accommodation Details:")
            print(f"  ID:          {acc_id}")
            print(f"  Student ID:  {student_id}")
            print(f"  Type:        {acc_type}")
            print(f"  Status:      {status}")

            # Confirm deletion
            confirm = input("\n⚠️  Are you sure you want to remove this accommodation? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Cancelled")
                self.pause()
                return

            # Delete from database
            with get_connection() as conn:
                cursor = conn.cursor()
                # Delete associated documents first
                cursor.execute(
                    "DELETE FROM documents WHERE source_type = 'accommodation'"
                    " AND reference_id = ? AND reference_type = 'accommodation'",
                    (str(acc_id),))
                # Delete accommodation
                cursor.execute('DELETE FROM accommodations WHERE id = ?', (acc_id,))
                conn.commit()

            # Log action
            if SERVICE_AVAILABLE:
                log_action('delete', acc_id, f"Removed {acc_type} for {student_id}")

            log_activity('delete', 'medical_accommodation',
                        accommodation_id=acc_id)

            print(f"\n✅ Accommodation {acc_id} removed successfully")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def approve_reject_menu(self):
        """Approve or reject accommodation"""
        self.clear_screen()
        self.print_header("✅ APPROVE/REJECT ACCOMMODATION")

        acc_id = input("\n📝 Enter Accommodation ID: ").strip()
        if not acc_id or not acc_id.isdigit():
            print("❌ Invalid ID")
            self.pause()
            return

        try:
            # Get accommodation details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT student_id, accommodation_type, status
                    FROM accommodations WHERE id = ?
                ''', (acc_id,))
                acc = cursor.fetchone()

            if not acc:
                print(f"\n❌ Accommodation {acc_id} not found")
                self.pause()
                return

            student_id, acc_type, current_status = acc
            print("\n📋 Accommodation Details:")
            print(f"  ID:          {acc_id}")
            print(f"  Student ID:  {student_id}")
            print(f"  Type:        {acc_type}")
            print(f"  Status:      {current_status}")

            # Action choice
            print("\n👉 Choose action:")
            print("  1. Approve")
            print("  2. Reject")
            print("  0. Cancel")

            choice = input("\nEnter choice: ").strip()

            if choice == '0':
                print("❌ Cancelled")
                self.pause()
                return
            elif choice not in ['1', '2']:
                print("❌ Invalid choice")
                self.pause()
                return

            action = 'approved' if choice == '1' else 'rejected'
            new_status = 'active' if choice == '1' else 'rejected'

            # Get approver name
            approver = self.get_user_identifier()

            # Get reason/notes
            reason = input(f"\n📝 Reason for {action} (optional): ").strip() or None

            # Update database
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accommodations
                    SET status = ?, approved_by = ?, approval_date = ?, notes = ?, updated_at = ?
                    WHERE id = ?
                ''', (new_status, approver, now, reason, now, acc_id))
                conn.commit()

            # Log action
            if SERVICE_AVAILABLE:
                log_action(action, acc_id, f"{action.capitalize()} by {approver}")

            log_activity(action, 'medical_accommodation',
                        accommodation_id=acc_id,
                        approver=approver)

            print(f"\n✅ Accommodation {action} successfully")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Search & Filter ====================

    def search_accommodations(self):
        """Search accommodations by various criteria"""
        self.clear_screen()
        self.print_header("🔍 SEARCH ACCOMMODATIONS")

        print("\n💡 Enter search criteria (press Enter to skip):")

        # Get search criteria
        student_id = input("\n📝 Student ID: ").strip() or None

        # Accommodation type
        if SERVICE_AVAILABLE:
            types = get_accommodation_types()
            print("\n📋 Accommodation Type:")
            for i, t in enumerate(types, 1):
                print(f"  {i}. {t}")
            type_input = input("👉 Select (number/name) or press Enter: ").strip()

            if type_input:
                if type_input.isdigit() and 1 <= int(type_input) <= len(types):
                    acc_type = types[int(type_input) - 1]
                elif type_input in types:
                    acc_type = type_input
                else:
                    acc_type = None
            else:
                acc_type = None
        else:
            acc_type = input("\n📋 Accommodation Type: ").strip() or None

        # Status
        print("\n📊 Status:")
        print("  1. Active")
        print("  2. Pending")
        print("  3. Suspended")
        print("  4. Expired")
        status_input = input("👉 Select or press Enter: ").strip()
        status_map = {'1': 'active', '2': 'pending', '3': 'suspended', '4': 'expired'}
        status = status_map.get(status_input, None)

        # Date range
        start_from = input("\n📅 Start Date >= (YYYY-MM-DD): ").strip() or None
        end_before = input("📅 End Date <= (YYYY-MM-DD): ").strip() or None

        # Keyword search
        keyword = input("\n🔎 Keyword (searches description/notes): ").strip() or None

        # Build query
        query = '''
            SELECT a.id, a.student_id, a.accommodation_type, a.start_date,
                   a.end_date, a.status, s.first_name, s.last_name
            FROM accommodations a
            LEFT JOIN students s ON a.student_id = s.student_id
            WHERE 1=1
        '''
        params = []

        if student_id:
            query += " AND a.student_id = ?"
            params.append(student_id)
        if acc_type:
            query += " AND a.accommodation_type = ?"
            params.append(acc_type)
        if status:
            query += " AND a.status = ?"
            params.append(status)
        if start_from:
            query += " AND a.start_date >= ?"
            params.append(start_from)
        if end_before:
            query += " AND a.end_date <= ?"
            params.append(end_before)
        if keyword:
            query += " AND (a.description LIKE ? OR a.notes LIKE ?)"
            params.extend([f"%{escape_like(keyword)}%", f"%{escape_like(keyword)}%"])

        query += " ORDER BY a.created_at DESC"

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()

            self.clear_screen()
            self.print_header("🔍 SEARCH RESULTS")

            if not results:
                print("\n📭 No accommodations found matching your criteria")
            else:
                print(f"\n📊 Found: {len(results)} accommodation(s)\n")

                # Table header
                print(f"{'ID':<6} {'Student ID':<12} {'Name':<25} {'Type':<25} {'Start':<12} {'End':<12} {'Status':<10}")
                print("─" * 120)

                # Table rows
                for acc in results:
                    acc_id, student_id, acc_type, start, end, status, fname, lname = acc
                    name = f"{fname or ''} {lname or ''}".strip() or "N/A"
                    name = name[:24]
                    acc_type = acc_type[:24]

                    status_icon = {
                        'active': '🟢',
                        'pending': '🟡',
                        'suspended': '🔴',
                        'expired': '⚫'
                    }.get(status.lower(), '⚪')

                    print(f"{acc_id:<6} {student_id:<12} {name:<25} {acc_type:<25} "
                          f"{start or 'N/A':<12} {end or 'N/A':<12} {status_icon} {status:<8}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_by_type(self):
        """View accommodations grouped by type"""
        self.clear_screen()
        self.print_header("📋 VIEW BY ACCOMMODATION TYPE")

        if SERVICE_AVAILABLE:
            types = get_accommodation_types()
        else:
            types = ['Extended Time', 'Alternate Format', 'Note-Taking',
                    'Assistive Technology', 'Flexible Attendance']

        print("\n📋 Select Accommodation Type:")
        for i, t in enumerate(types, 1):
            print(f"  {i}. {t}")

        choice = input("\n👉 Enter choice: ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(types):
            acc_type = types[int(choice) - 1]
        else:
            print("❌ Invalid choice")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.id, a.student_id, s.first_name, s.last_name,
                           a.start_date, a.end_date, a.status
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    WHERE a.accommodation_type = ?
                    ORDER BY a.start_date DESC
                ''', (acc_type,))

                results = cursor.fetchall()

            self.clear_screen()
            self.print_header(f"📋 {acc_type.upper()}")

            if not results:
                print(f"\n📭 No accommodations found for type: {acc_type}")
            else:
                print(f"\n📊 Total: {len(results)} accommodation(s)\n")

                # Table header
                print(f"{'ID':<6} {'Student ID':<12} {'Name':<30} {'Start':<12} {'End':<12} {'Status':<10}")
                print("─" * 95)

                # Table rows
                for acc in results:
                    acc_id, student_id, fname, lname, start, end, status = acc
                    name = f"{fname or ''} {lname or ''}".strip() or "N/A"
                    name = name[:29]

                    status_icon = {
                        'active': '🟢',
                        'pending': '🟡',
                        'suspended': '🔴',
                        'expired': '⚫'
                    }.get(status.lower(), '⚪')

                    print(f"{acc_id:<6} {student_id:<12} {name:<30} "
                          f"{start or 'N/A':<12} {end or 'N/A':<12} {status_icon} {status:<8}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_by_status(self):
        """View accommodations by status"""
        self.clear_screen()
        self.print_header("📊 VIEW BY STATUS")

        print("\n📊 Select Status:")
        print("  1. Active")
        print("  2. Pending")
        print("  3. Suspended")
        print("  4. Expired")

        choice = input("\n👉 Enter choice: ").strip()
        status_map = {'1': 'active', '2': 'pending', '3': 'suspended', '4': 'expired'}

        if choice not in status_map:
            print("❌ Invalid choice")
            self.pause()
            return

        status = status_map[choice]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT a.id, a.student_id, s.first_name, s.last_name,
                           a.accommodation_type, a.start_date, a.end_date
                    FROM accommodations a
                    LEFT JOIN students s ON a.student_id = s.student_id
                    WHERE a.status = ?
                    ORDER BY a.start_date DESC
                ''', (status,))

                results = cursor.fetchall()

            self.clear_screen()
            self.print_header(f"📊 {status.upper()} ACCOMMODATIONS")

            if not results:
                print(f"\n📭 No {status} accommodations found")
            else:
                print(f"\n📊 Total: {len(results)} accommodation(s)\n")

                # Table header
                print(f"{'ID':<6} {'Student ID':<12} {'Name':<25} {'Type':<25} {'Start':<12} {'End':<12}")
                print("─" * 110)

                # Table rows
                for acc in results:
                    acc_id, student_id, fname, lname, acc_type, start, end = acc
                    name = f"{fname or ''} {lname or ''}".strip() or "N/A"
                    name = name[:24]
                    acc_type = acc_type[:24]

                    print(f"{acc_id:<6} {student_id:<12} {name:<25} {acc_type:<25} "
                          f"{start or 'N/A':<12} {end or 'N/A':<12}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Templates ====================

    def create_template_menu(self):
        """Create a new accommodation template"""
        self.clear_screen()
        self.print_header("📄 CREATE TEMPLATE")

        try:
            # Template name
            name = input("\n📝 Template Name: ").strip()
            if not name:
                print("❌ Template name is required")
                self.pause()
                return

            # Check if template already exists
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT COUNT(*) FROM {TEMPLATES_TABLE} WHERE name = ?', (name,))
                if cursor.fetchone()[0] > 0:
                    print(f"❌ Template '{name}' already exists")
                    self.pause()
                    return

            # Get accommodation type
            if SERVICE_AVAILABLE:
                types = get_accommodation_types()
            else:
                types = ['Extended Time', 'Alternate Format', 'Note-Taking',
                        'Assistive Technology', 'Flexible Attendance']

            print("\n📋 Accommodation Type:")
            for i, t in enumerate(types, 1):
                print(f"  {i}. {t}")

            type_input = input("\n👉 Select type: ").strip()
            if type_input.isdigit() and 1 <= int(type_input) <= len(types):
                acc_type = types[int(type_input) - 1]
            elif type_input in types:
                acc_type = type_input
            else:
                print("❌ Invalid type")
                self.pause()
                return

            # Description
            description = input("\n💬 Description (optional): ").strip() or None

            # Start offset
            print("\n📅 Start Offset Days (0 = today, negative = past, positive = future):")
            start_offset = input("  ").strip()
            try:
                start_offset = int(start_offset) if start_offset else 0
            except ValueError:
                print("❌ Invalid number")
                self.pause()
                return

            # Duration
            print("\n⏱️  Duration (days):")
            duration = input("  ").strip()
            try:
                duration = int(duration) if duration else 365
            except ValueError:
                print("❌ Invalid number")
                self.pause()
                return

            # Save template
            creator = self.get_user_identifier()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    INSERT INTO {TEMPLATES_TABLE}
                    (name, accommodation_type, description, start_offset_days, duration_days,
                     created_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (name, acc_type, description, start_offset, duration, creator, now, now))
                conn.commit()

            # Log action
            if SERVICE_AVAILABLE:
                log_action('create_template', None, f"Created template: {name}")

            print(f"\n✅ Template '{name}' created successfully")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def apply_template_menu(self):
        """Apply a template to create accommodation"""
        self.clear_screen()
        self.print_header("📄 APPLY TEMPLATE")

        try:
            # Get templates
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT name, accommodation_type, description FROM {TEMPLATES_TABLE} ORDER BY name')
                templates = cursor.fetchall()

            if not templates:
                print("\n📭 No templates available")
                print("💡 Create a template first using option 10")
                self.pause()
                return

            # Display templates
            print("\n📋 Available Templates:")
            for i, (name, acc_type, desc) in enumerate(templates, 1):
                print(f"  {i}. {name}")
                print(f"     Type: {acc_type}")
                if desc:
                    print(f"     Description: {desc}")
                print()

            # Select template
            choice = input("👉 Select template (number or name): ").strip()

            if choice.isdigit() and 1 <= int(choice) <= len(templates):
                template_name = templates[int(choice) - 1][0]
            elif any(t[0] == choice for t in templates):
                template_name = choice
            else:
                print("❌ Invalid choice")
                self.pause()
                return

            # Get student ID
            student_id = input("\n📝 Student ID: ").strip()
            if not student_id:
                print("❌ Student ID is required")
                self.pause()
                return

            # Validate student
            if SERVICE_AVAILABLE:
                is_valid, error_msg = validate_student_id(student_id)
                if not is_valid:
                    print(f"❌ {error_msg}")
                    self.pause()
                    return

            # Get template details
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT accommodation_type, description, start_offset_days, duration_days
                    FROM {TEMPLATES_TABLE} WHERE name = ?
                ''', (template_name,))
                template = cursor.fetchone()

            if not template:
                print("❌ Template not found")
                self.pause()
                return

            acc_type, description, start_offset, duration = template

            # Calculate dates
            start_date = (datetime.now() + timedelta(days=start_offset)).strftime('%Y-%m-%d')
            end_date = (datetime.now() + timedelta(days=start_offset + duration)).strftime('%Y-%m-%d')

            # Display what will be created
            print("\n📋 Template Details:")
            print(f"  Type:        {acc_type}")
            print(f"  Description: {description or 'N/A'}")
            print(f"  Start Date:  {start_date}")
            print(f"  End Date:    {end_date}")

            # Confirm
            confirm = input("\n✅ Create this accommodation? (y/n): ").strip().lower()
            if confirm != 'y':
                print("❌ Cancelled")
                self.pause()
                return

            # Create accommodation
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO accommodations
                    (student_id, accommodation_type, description, start_date, end_date,
                     status, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, acc_type, description, start_date, end_date,
                      'pending', f"Created from template: {template_name}", now, now))

                accommodation_id = cursor.lastrowid
                conn.commit()

            # Log action
            if SERVICE_AVAILABLE:
                log_action('apply_template', accommodation_id,
                          f"Applied template {template_name} for {student_id}")

            log_activity('create', 'medical_accommodation',
                        accommodation_id=accommodation_id,
                        template=template_name)

            print(f"\n✅ Accommodation created from template (ID: {accommodation_id})")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_templates(self):
        """View all templates"""
        self.clear_screen()
        self.print_header("📄 ACCOMMODATION TEMPLATES")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT name, accommodation_type, description, start_offset_days,
                           duration_days, created_by, created_at
                    FROM {TEMPLATES_TABLE}
                    ORDER BY name
                ''')
                templates = cursor.fetchall()

            if not templates:
                print("\n📭 No templates found")
                print("💡 Create a template using option 10")
            else:
                print(f"\n📊 Total: {len(templates)} template(s)\n")

                for i, (name, acc_type, desc, offset, duration, creator, created) in enumerate(templates, 1):
                    print(f"{'═'*70}")
                    print(f"  #{i}. {name}")
                    print(f"{'─'*70}")
                    print(f"  Type:           {acc_type}")
                    print(f"  Description:    {desc or 'N/A'}")
                    print(f"  Start Offset:   {offset} days")
                    print(f"  Duration:       {duration} days")
                    print(f"  Created By:     {creator or 'N/A'}")
                    print(f"  Created:        {created or 'N/A'}")
                    print()

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def delete_template_menu(self):
        """Delete a template"""
        self.clear_screen()
        self.print_header("🗑️  DELETE TEMPLATE")

        try:
            # Get templates
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'SELECT name FROM {TEMPLATES_TABLE} ORDER BY name')
                templates = [row[0] for row in cursor.fetchall()]

            if not templates:
                print("\n📭 No templates available")
                self.pause()
                return

            # Display templates
            print("\n📋 Available Templates:")
            for i, name in enumerate(templates, 1):
                print(f"  {i}. {name}")

            # Select template
            choice = input("\n👉 Select template to delete (number or name): ").strip()

            if choice.isdigit() and 1 <= int(choice) <= len(templates):
                template_name = templates[int(choice) - 1]
            elif choice in templates:
                template_name = choice
            else:
                print("❌ Invalid choice")
                self.pause()
                return

            # Confirm deletion
            confirm = input(f"\n⚠️  Delete template '{template_name}'? (yes/no): ").strip().lower()
            if confirm != 'yes':
                print("❌ Cancelled")
                self.pause()
                return

            # Delete template
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f'DELETE FROM {TEMPLATES_TABLE} WHERE name = ?', (template_name,))
                conn.commit()

            # Log action
            if SERVICE_AVAILABLE:
                log_action('delete_template', None, f"Deleted template: {template_name}")

            print(f"\n✅ Template '{template_name}' deleted successfully")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Dashboard & Reports ====================

    def view_dashboard(self):
        """Display dashboard metrics"""
        self.clear_screen()
        self.print_header("📊 DASHBOARD METRICS")

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Total count
                cursor.execute('SELECT COUNT(*) FROM accommodations')
                total = cursor.fetchone()[0]

                # Active count
                cursor.execute("SELECT COUNT(*) FROM accommodations WHERE status = 'active'")
                active = cursor.fetchone()[0]

                # Pending count
                cursor.execute("SELECT COUNT(*) FROM accommodations WHERE status = 'pending'")
                pending = cursor.fetchone()[0]

                # Suspended count
                cursor.execute("SELECT COUNT(*) FROM accommodations WHERE status = 'suspended'")
                suspended = cursor.fetchone()[0]

                # Expired count
                cursor.execute("SELECT COUNT(*) FROM accommodations WHERE status = 'expired'")
                expired = cursor.fetchone()[0]

                # By type
                cursor.execute('''
                    SELECT accommodation_type, COUNT(*) as count
                    FROM accommodations
                    GROUP BY accommodation_type
                    ORDER BY count DESC
                ''')
                by_type = cursor.fetchall()

                # Expiring soon (next 30 days)
                future_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
                cursor.execute('''
                    SELECT COUNT(*) FROM accommodations
                    WHERE end_date <= ? AND status = 'active'
                ''', (future_date,))
                expiring_soon = cursor.fetchone()[0]

            # Display metrics
            self.print_section("Overall Statistics")
            print(f"  Total Accommodations:     {total}")
            print(f"  Active:                   {active} ({active/total*100:.1f}%)" if total > 0 else "  Active:                   0")
            print(f"  Pending Approval:         {pending}")
            print(f"  Suspended:                {suspended}")
            print(f"  Expired:                  {expired}")
            print(f"  Expiring Soon (30 days):  {expiring_soon}")

            if by_type:
                self.print_section("By Accommodation Type")
                for acc_type, count in by_type:
                    percentage = count/total*100 if total > 0 else 0
                    bar = '█' * int(percentage / 5)
                    print(f"  {acc_type:<30} {count:>4} ({percentage:>5.1f}%) {bar}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def generate_statistics(self):
        """Generate detailed statistics report"""
        self.clear_screen()
        self.print_header("📊 STATISTICS REPORT")

        if not SERVICE_AVAILABLE:
            print("\n❌ Statistics report generation requires the accommodation service")
            self.pause()
            return

        try:
            # Call service function
            print("\n⏳ Generating report...\n")
            generate_statistics_report()
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def view_students_by_accommodation_menu(self):
        """View students grouped by accommodation type"""
        self.clear_screen()
        self.print_header("👥 STUDENTS BY ACCOMMODATION TYPE")

        if not SERVICE_AVAILABLE:
            print("\n❌ This feature requires the accommodation service")
            self.pause()
            return

        try:
            # Call service function (which provides CLI output)
            view_students_by_accommodation()
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Import/Export ====================

    def import_csv_menu(self):
        """Import accommodations from CSV"""
        self.clear_screen()
        self.print_header("📥 IMPORT FROM CSV")

        filepath = input("\n📝 Enter CSV file path: ").strip()

        if not filepath:
            print("❌ File path is required")
            self.pause()
            return

        if not os.path.exists(filepath):
            print(f"❌ File not found: {filepath}")
            self.pause()
            return

        if not SERVICE_AVAILABLE:
            print("\n❌ CSV import requires the accommodation service")
            self.pause()
            return

        try:
            print("\n⏳ Importing accommodations...\n")
            bulk_import_from_csv(filepath)
            print("\n✅ Import completed")
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def import_json_menu(self):
        """Import accommodations from JSON"""
        self.clear_screen()
        self.print_header("📥 IMPORT FROM JSON")

        if not SERVICE_AVAILABLE:
            print("\n❌ JSON import requires the accommodation service")
            self.pause()
            return

        try:
            print("\n⏳ Importing accommodations...\n")
            import_from_json()
            print("\n✅ Import completed")
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def export_menu(self):
        """Export accommodations menu"""
        self.clear_screen()
        self.print_header("📤 EXPORT ACCOMMODATIONS")

        if not SERVICE_AVAILABLE:
            print("\n❌ Export requires the accommodation service")
            self.pause()
            return

        try:
            print("\n⏳ Exporting accommodations...\n")
            export_accommodations()
            print("\n✅ Export completed")
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Documents ====================

    def upload_document_menu(self):
        """Upload document for accommodation"""
        self.clear_screen()
        self.print_header("📎 UPLOAD DOCUMENT")

        acc_id = input("\n📝 Enter Accommodation ID: ").strip()
        if not acc_id or not acc_id.isdigit():
            print("❌ Invalid ID")
            self.pause()
            return

        # Check if accommodation exists
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT student_id FROM accommodations WHERE id = ?', (acc_id,))
                result = cursor.fetchone()

            if not result:
                print(f"❌ Accommodation {acc_id} not found")
                self.pause()
                return

            # Upload document
            if SERVICE_AVAILABLE:
                self.upload_document_for_accommodation(int(acc_id))
            else:
                print("\n❌ Document upload requires the accommodation service")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def upload_document_for_accommodation(self, accommodation_id):
        """Helper to upload document"""
        if not SERVICE_AVAILABLE:
            return

        try:
            upload_accommodation_document(accommodation_id)
        except Exception as e:
            print(f"❌ Error uploading document: {e}")

    def view_documents_menu(self):
        """View documents for an accommodation"""
        self.clear_screen()
        self.print_header("📎 VIEW DOCUMENTS")

        acc_id = input("\n📝 Enter Accommodation ID: ").strip()
        if not acc_id or not acc_id.isdigit():
            print("❌ Invalid ID")
            self.pause()
            return

        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT document_id as id, document_name, file_path as document_path,
                           uploaded_by, upload_date as uploaded_at
                    FROM documents
                    WHERE source_type = 'accommodation'
                      AND reference_id = ? AND reference_type = 'accommodation'
                    ORDER BY upload_date DESC
                ''', (str(acc_id),))

                documents = cursor.fetchall()

            if not documents:
                print(f"\n📭 No documents found for accommodation {acc_id}")
            else:
                print(f"\n📎 Documents for Accommodation {acc_id}:")
                print(f"\n{'ID':<6} {'Name':<40} {'Uploaded By':<20} {'Uploaded At':<20}")
                print("─" * 100)

                for doc_id, name, path, uploader, uploaded in documents:
                    print(f"{doc_id:<6} {name:<40} {uploader or 'N/A':<20} {uploaded or 'N/A':<20}")

                print(f"\n💡 Document paths are stored in: {path if documents else 'N/A'}")

        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    # ==================== Notifications ====================

    def check_notifications(self):
        """Check for expiring accommodations"""
        self.clear_screen()
        self.print_header("🔔 EXPIRY NOTIFICATIONS")

        if not SERVICE_AVAILABLE:
            print("\n❌ Notification check requires the accommodation service")
            self.pause()
            return

        try:
            print("\n⏳ Checking for expiring accommodations...\n")
            check_expiry_notifications()
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

    def send_notification_menu(self):
        """Send notification to student"""
        self.clear_screen()
        self.print_header("📧 SEND NOTIFICATION")

        student_id = input("\n📝 Student ID: ").strip()
        if not student_id:
            print("❌ Student ID is required")
            self.pause()
            return

        subject = input("\n✉️  Subject: ").strip()
        if not subject:
            print("❌ Subject is required")
            self.pause()
            return

        print("\n💬 Message (type 'END' on a new line to finish):")
        message_lines = []
        while True:
            line = input()
            if line.strip() == 'END':
                break
            message_lines.append(line)

        message = '\n'.join(message_lines)

        if not message:
            print("❌ Message is required")
            self.pause()
            return

        if not SERVICE_AVAILABLE:
            print("\n❌ Notification sending requires the accommodation service")
            self.pause()
            return

        try:
            print("\n⏳ Sending notification...")
            notify_student(student_id, subject, message)
            print("✅ Notification sent successfully")
        except Exception as e:
            print(f"\n❌ Error: {e}")

        self.pause()

def launch_medical_accommodation_cli(auth=None):
    """
    Launch the Medical Accommodation CLI

    Args:
        auth: Authentication instance with current user information
    """
    try:
        cli = MedicalAccommodationCLI(auth)
        cli.run()
    except KeyboardInterrupt:
        print("\n\n👋 Exited by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # For testing standalone
    launch_medical_accommodation_cli()
