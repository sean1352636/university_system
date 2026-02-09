"""
Mail/Post System CLI for University Management System

Provides comprehensive package tracking, PO box management, and mail forwarding
services with finance and email integration.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# Import centralized database and authentication
from university_system.infrastructure.database.db import get_connection, transaction
from university_system.infrastructure.shared_context import get_auth

# Import mail core services
try:
    from university_system.modules.domain.mail.services.mail_post_core import (
        init_mail_db, PACKAGE_TYPES, STORAGE_FEES, FORWARDING_FEES,
        PO_BOX_MONTHLY_FEE, generate_tracking_number, generate_reference
    )
    MAIL_CORE_AVAILABLE = True
except ImportError:
    MAIL_CORE_AVAILABLE = False
    PACKAGE_TYPES = ['letter', 'small_parcel', 'large_parcel', 'registered', 'express', 'international']
    STORAGE_FEES = {'letter': 0.00, 'small_parcel': 0.00, 'large_parcel': 2.50, 'registered': 1.00, 'express': 0.00, 'international': 3.00}
    FORWARDING_FEES = {'domestic': 5.00, 'international': 15.00}
    PO_BOX_MONTHLY_FEE = 10.00

    def generate_tracking_number():
        return f"UNI-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    def generate_reference():
        return f"REF-{uuid.uuid4().hex[:12].upper()}"

    def init_mail_db():
        """Fallback database initialization"""
        try:
            with transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS mail_packages (
                        package_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tracking_number TEXT UNIQUE NOT NULL,
                        recipient_id TEXT NOT NULL,
                        recipient_name TEXT NOT NULL,
                        recipient_email TEXT,
                        recipient_phone TEXT,
                        sender_name TEXT,
                        sender_address TEXT,
                        package_type TEXT NOT NULL,
                        description TEXT,
                        weight_kg REAL,
                        dimensions TEXT,
                        status TEXT DEFAULT 'received',
                        storage_location TEXT,
                        received_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        notification_sent INTEGER DEFAULT 0,
                        notification_date TIMESTAMP,
                        collected_date TIMESTAMP,
                        collected_by TEXT,
                        storage_fee REAL DEFAULT 0.00,
                        total_charges REAL DEFAULT 0.00,
                        payment_status TEXT DEFAULT 'pending',
                        notes TEXT,
                        created_by TEXT
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS mail_po_boxes (
                        box_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        box_number TEXT UNIQUE NOT NULL,
                        holder_id TEXT,
                        holder_name TEXT,
                        holder_email TEXT,
                        size TEXT DEFAULT 'standard',
                        monthly_fee REAL DEFAULT 10.00,
                        status TEXT DEFAULT 'available',
                        rental_start DATE,
                        rental_end DATE,
                        auto_renew INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS mail_forwarding (
                        forwarding_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        forwarding_address TEXT NOT NULL,
                        city TEXT,
                        postal_code TEXT,
                        country TEXT DEFAULT 'UK',
                        start_date DATE NOT NULL,
                        end_date DATE,
                        is_active INTEGER DEFAULT 1,
                        forwarding_type TEXT DEFAULT 'domestic',
                        fee REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Create sample PO boxes if none exist
                cursor = conn.execute('SELECT COUNT(*) FROM mail_po_boxes')
                if cursor.fetchone()[0] == 0:
                    sample_boxes = [(f"PO-{i:03d}", 'standard', 10.00, 'available')
                                    for i in range(1, 51)]
                    conn.executemany('''
                        INSERT INTO mail_po_boxes (box_number, size, monthly_fee, status)
                        VALUES (?, ?, ?, ?)
                    ''', sample_boxes)

            return True
        except Exception as e:
            print(f"Database initialization error: {e}")
            return False

# Import email service
try:
    from university_system.infrastructure.email.email_service import send_email
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False

# Import finance integration
try:
    from university_system.modules.shared.utils.finance_integration import (
        record_payment_to_finance,
        get_student_finance_account_balance,
        process_student_finance_account_payment
    )
    FINANCE_AVAILABLE = True
except ImportError:
    FINANCE_AVAILABLE = False

# Import activity logger
try:
    from university_system.modules.shared.utils.activity_logger import log_activity
    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    log_activity = lambda *args, **kwargs: None


def get_current_user():
    """Get current authenticated user"""
    auth = get_auth()
    if auth and hasattr(auth, 'current_user') and auth.current_user:
        return auth.current_user
    return None


def print_header(title: str):
    """Print formatted header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)


def receive_package():
    """Receive and register a new package"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("RECEIVE PACKAGE")

    tracking_number = generate_tracking_number()

    recipient_id = input("\nEnter recipient student/staff ID: ").strip()
    if not recipient_id:
        return

    recipient_name = input("Recipient name: ").strip()
    if not recipient_name:
        return

    recipient_email = input("Recipient email (optional): ").strip()
    recipient_phone = input("Recipient phone (optional): ").strip()

    sender_name = input("Sender name: ").strip()
    sender_address = input("Sender address (optional): ").strip()

    print("\nPackage Types:")
    for i, pkg_type in enumerate(PACKAGE_TYPES, 1):
        fee = STORAGE_FEES.get(pkg_type, 0.00)
        print(f"{i}. {pkg_type.replace('_', ' ').title()} - £{fee:.2f} storage fee")

    pkg_choice = input("\nSelect package type: ").strip()
    try:
        pkg_index = int(pkg_choice) - 1
        if 0 <= pkg_index < len(PACKAGE_TYPES):
            package_type = PACKAGE_TYPES[pkg_index]
        else:
            print("❌ Invalid package type")
            return
    except ValueError:
        print("❌ Invalid input")
        return

    description = input("Package description (optional): ").strip()
    storage_location = input("Storage location (optional): ").strip()

    storage_fee = STORAGE_FEES.get(package_type, 0.00)

    try:
        with transaction() as conn:
            conn.execute('''
                INSERT INTO mail_packages (
                    tracking_number, recipient_id, recipient_name, recipient_email, recipient_phone,
                    sender_name, sender_address, package_type, description, storage_location,
                    status, storage_fee, total_charges, created_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'received', ?, ?, ?)
            ''', (tracking_number, recipient_id, recipient_name, recipient_email or None,
                  recipient_phone or None, sender_name, sender_address or None, package_type,
                  description or None, storage_location or None, storage_fee, storage_fee,
                  user.get('username')))

        print(f"\n✅ Package received successfully")
        print(f"Tracking Number: {tracking_number}")
        print(f"Recipient: {recipient_name} ({recipient_id})")
        print(f"Type: {package_type.replace('_', ' ').title()}")
        if storage_fee > 0:
            print(f"Storage Fee: £{storage_fee:.2f}")

        # Send notification email
        if recipient_email and EMAIL_AVAILABLE:
            subject = f"Package Received - {tracking_number}"
            body = f"""Dear {recipient_name},

A package has been received for you at the University Mail Center.

Tracking Number: {tracking_number}
Sender: {sender_name}
Type: {package_type.replace('_', ' ').title()}
Received: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{'Storage Location: ' + storage_location if storage_location else ''}

Please collect your package during mail center hours.

University Mail Services"""

            try:
                send_email(recipient_email, subject, body)
                print("📧 Notification email sent")
            except Exception as e:
                print(f"⚠️  Email notification failed: {e}")

        log_activity('create', 'mail_package', tracking_number=tracking_number,
                     details={'recipient': recipient_name, 'type': package_type})

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def track_package():
    """Track a package by tracking number"""
    print_header("TRACK PACKAGE")

    tracking = input("\nEnter tracking number: ").strip()
    if not tracking:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM mail_packages
                WHERE tracking_number = ?
            ''', (tracking,))

            package = cursor.fetchone()

            if not package:
                print(f"\n❌ Package not found with tracking number: {tracking}")
            else:
                print(f"\n━━━ Package Details ━━━")
                print(f"Tracking Number: {package[1]}")
                print(f"Recipient: {package[3]} ({package[2]})")
                print(f"Email: {package[4] or 'N/A'}")
                print(f"Sender: {package[6] or 'N/A'}")
                print(f"Type: {package[8].replace('_', ' ').title()}")
                print(f"Description: {package[9] or 'N/A'}")
                print(f"Status: {package[12].upper()}")
                print(f"Received: {package[14][:19] if package[14] else 'N/A'}")

                if package[13]:  # storage_location
                    print(f"Location: {package[13]}")

                if package[17]:  # collected_date
                    print(f"Collected: {package[17][:19]}")
                    print(f"Collected By: {package[18] or 'N/A'}")

                if package[19] > 0:  # storage_fee
                    print(f"\nStorage Fee: £{package[19]:.2f}")
                    print(f"Total Charges: £{package[20]:.2f}")
                    print(f"Payment Status: {package[21]}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_my_packages():
    """View packages for current user"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("MY PACKAGES")

    user_id = user.get('id') or user.get('username')

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT tracking_number, sender_name, package_type, status, received_date, storage_location
                FROM mail_packages
                WHERE recipient_id = ?
                ORDER BY received_date DESC
            ''', (str(user_id),))

            packages = cursor.fetchall()

            if not packages:
                print("\n📦 No packages found")
            else:
                print(f"\nFound {len(packages)} package(s):\n")
                print("Tracking            Sender              Type            Status        Received")
                print("-" * 90)

                for pkg in packages:
                    tracking, sender, pkg_type, status, received, location = pkg
                    received_str = received[:19] if received else 'N/A'
                    print(f"{tracking:<18} {sender or 'Unknown':<18} {pkg_type:<15} {status:<12} {received_str}")

                # Option to view details
                tracking = input("\nEnter tracking number for details (or Enter to return): ").strip()
                if tracking:
                    track_package_details(tracking)

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def track_package_details(tracking: str):
    """Show detailed package information"""
    try:
        with get_connection() as conn:
            cursor = conn.execute('SELECT * FROM mail_packages WHERE tracking_number = ?', (tracking,))
            package = cursor.fetchone()

            if package:
                print(f"\n━━━ Package {tracking} ━━━")
                print(f"Recipient: {package[3]}")
                print(f"Sender: {package[6] or 'N/A'}")
                print(f"Type: {package[8]}")
                print(f"Status: {package[12]}")
                print(f"Received: {package[14][:19] if package[14] else 'N/A'}")
                if package[17]:
                    print(f"Collected: {package[17][:19]}")

    except Exception as e:
        print(f"Error: {e}")


def collect_package():
    """Mark package as collected"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("COLLECT PACKAGE")

    tracking = input("\nEnter tracking number: ").strip()
    if not tracking:
        return

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT package_id, recipient_name, status, storage_fee, payment_status
                FROM mail_packages
                WHERE tracking_number = ?
            ''', (tracking,))

            package = cursor.fetchone()

            if not package:
                print("❌ Package not found")
                input("Press Enter to continue...")
                return

            pkg_id, recipient, status, fee, payment_status = package

            if status == 'collected':
                print("❌ Package already collected")
                input("Press Enter to continue...")
                return

            collected_by = input(f"Name of person collecting (default: {recipient}): ").strip() or recipient

            # Check payment if fee > 0
            if fee > 0 and payment_status != 'paid':
                print(f"\n⚠️  Storage fee due: £{fee:.2f}")
                confirm = input("Mark as paid? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    payment_status = 'paid'
                else:
                    print("❌ Cannot release package - payment required")
                    input("Press Enter to continue...")
                    return

            with transaction() as conn:
                conn.execute('''
                    UPDATE mail_packages
                    SET status = 'collected', collected_date = CURRENT_TIMESTAMP,
                        collected_by = ?, payment_status = ?
                    WHERE package_id = ?
                ''', (collected_by, payment_status, pkg_id))

            print(f"✅ Package {tracking} marked as collected")
            print(f"Collected by: {collected_by}")

            log_activity('update', 'mail_package', package_id=pkg_id, details={'status': 'collected'})

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def manage_po_boxes():
    """Manage PO boxes"""
    while True:
        print_header("PO BOX MANAGEMENT")
        print("\n1. View available PO boxes")
        print("2. Rent a PO box")
        print("3. View my PO box")
        print("4. Cancel PO box rental")
        print("5. View all PO boxes (staff)")
        print("6. Return to main menu")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            view_available_po_boxes()
        elif choice == "2":
            rent_po_box()
        elif choice == "3":
            view_my_po_box()
        elif choice == "4":
            cancel_po_box()
        elif choice == "5":
            view_all_po_boxes()
        elif choice == "6":
            break
        else:
            print("Invalid choice")
            input("Press Enter to continue...")


def view_available_po_boxes():
    """View available PO boxes"""
    print_header("AVAILABLE PO BOXES")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT box_number, size, monthly_fee
                FROM mail_po_boxes
                WHERE status = 'available'
                ORDER BY box_number
            ''')

            boxes = cursor.fetchall()

            if not boxes:
                print("\n❌ No PO boxes available")
            else:
                print(f"\n{len(boxes)} PO box(es) available:\n")
                print("Box Number    Size        Monthly Fee")
                print("-" * 45)
                for box in boxes:
                    print(f"{box[0]:<13} {box[1]:<11} £{box[2]:.2f}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def rent_po_box():
    """Rent a PO box"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("RENT PO BOX")

    box_number = input("\nEnter PO box number: ").strip()
    if not box_number:
        return

    user_id = user.get('id') or user.get('username')
    user_name = user.get('username', 'Unknown')
    user_email = user.get('email', '')

    duration_months = input("Rental duration (months, default 12): ").strip() or "12"

    try:
        duration_months = int(duration_months)
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_months * 30)

        with transaction() as conn:
            # Check if box is available
            cursor = conn.execute('''
                SELECT box_id, monthly_fee, status
                FROM mail_po_boxes
                WHERE box_number = ?
            ''', (box_number,))

            box = cursor.fetchone()

            if not box:
                print("❌ PO box not found")
            elif box[2] != 'available':
                print("❌ PO box is not available")
            else:
                box_id, monthly_fee, _ = box
                total_cost = monthly_fee * duration_months

                print(f"\nMonthly Fee: £{monthly_fee:.2f}")
                print(f"Duration: {duration_months} months")
                print(f"Total Cost: £{total_cost:.2f}")

                confirm = input("\nConfirm rental? (yes/no): ").strip().lower()
                if confirm != 'yes':
                    print("❌ Rental cancelled")
                    input("Press Enter to continue...")
                    return

                # Update PO box
                conn.execute('''
                    UPDATE mail_po_boxes
                    SET holder_id = ?, holder_name = ?, holder_email = ?,
                        status = 'rented', rental_start = ?, rental_end = ?
                    WHERE box_id = ?
                ''', (str(user_id), user_name, user_email or None,
                      start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), box_id))

                print(f"\n✅ PO Box {box_number} rented successfully")
                print(f"Rental Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

                log_activity('create', 'po_box_rental', box_id=box_id,
                             details={'box': box_number, 'duration': duration_months})

                if FINANCE_AVAILABLE:
                    record_payment_to_finance(
                        student_id=str(user_id),
                        amount=total_cost,
                        payment_type="PO Box Rental",
                        description=f"PO Box {box_number} - {duration_months} months",
                        payment_method="Pending"
                    )

    except ValueError:
        print("❌ Invalid duration")
    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_my_po_box():
    """View current user's PO box"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("MY PO BOX")

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT box_number, size, monthly_fee, rental_start, rental_end, status
                FROM mail_po_boxes
                WHERE holder_id = ?
            ''', (user_id,))

            box = cursor.fetchone()

            if not box:
                print("\n📦 You don't have a PO box rental")
            else:
                print(f"\nPO Box: {box[0]}")
                print(f"Size: {box[1]}")
                print(f"Monthly Fee: £{box[2]:.2f}")
                print(f"Rental Start: {box[3]}")
                print(f"Rental End: {box[4]}")
                print(f"Status: {box[5]}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def cancel_po_box():
    """Cancel PO box rental"""
    user = get_current_user()
    if not user:
        print("\n❌ Please log in")
        input("Press Enter to continue...")
        return

    print_header("CANCEL PO BOX RENTAL")

    user_id = str(user.get('id') or user.get('username'))

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT box_id, box_number
                FROM mail_po_boxes
                WHERE holder_id = ? AND status = 'rented'
            ''', (user_id,))

            box = cursor.fetchone()

            if not box:
                print("\n❌ No active PO box rental found")
            else:
                box_id, box_number = box

                confirm = input(f"\nCancel rental for PO Box {box_number}? (yes/no): ").strip().lower()
                if confirm == 'yes':
                    with transaction() as conn:
                        conn.execute('''
                            UPDATE mail_po_boxes
                            SET holder_id = NULL, holder_name = NULL, holder_email = NULL,
                                status = 'available', rental_start = NULL, rental_end = NULL
                            WHERE box_id = ?
                        ''', (box_id,))

                    print(f"✅ PO Box {box_number} rental cancelled")
                    log_activity('delete', 'po_box_rental', box_id=box_id)
                else:
                    print("❌ Cancellation aborted")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_all_po_boxes():
    """View all PO boxes (staff only)"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("ALL PO BOXES")

    try:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT box_number, size, status, holder_name, rental_start, rental_end
                FROM mail_po_boxes
                ORDER BY box_number
            ''')

            boxes = cursor.fetchall()

            print("\nBox Number    Size        Status      Holder              Start         End")
            print("-" * 90)

            for box in boxes:
                box_num, size, status, holder, start, end = box
                holder_str = holder or 'N/A'
                start_str = start or 'N/A'
                end_str = end or 'N/A'
                print(f"{box_num:<13} {size:<11} {status:<11} {holder_str:<19} {start_str:<13} {end_str}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def view_package_statistics():
    """View package statistics (staff)"""
    user = get_current_user()
    if not user or user.get('role') not in ['admin', 'staff']:
        print("\n❌ Staff access required")
        input("Press Enter to continue...")
        return

    print_header("PACKAGE STATISTICS")

    try:
        with get_connection() as conn:
            # Total packages
            cursor = conn.execute('SELECT COUNT(*) FROM mail_packages')
            total = cursor.fetchone()[0]

            # By status
            cursor = conn.execute('''
                SELECT status, COUNT(*)
                FROM mail_packages
                GROUP BY status
            ''')
            by_status = cursor.fetchall()

            # By type
            cursor = conn.execute('''
                SELECT package_type, COUNT(*)
                FROM mail_packages
                GROUP BY package_type
            ''')
            by_type = cursor.fetchall()

            print(f"\n📊 Total Packages: {total}")

            print("\nBy Status:")
            for status, count in by_status:
                print(f"  {status}: {count}")

            print("\nBy Type:")
            for pkg_type, count in by_type:
                print(f"  {pkg_type.replace('_', ' ').title()}: {count}")

    except Exception as e:
        print(f"❌ Error: {e}")

    input("\nPress Enter to continue...")


def mail_post_menu():
    """Main mail/post menu"""
    # Initialize database
    init_mail_db()

    user = get_current_user()
    is_staff = user and user.get('role') in ['admin', 'staff']

    while True:
        print_header("UNIVERSITY MAIL / POST SERVICES")

        if user:
            print(f"\nLogged in as: {user.get('username')} ({user.get('role')})")

        print("\n📦 PACKAGE SERVICES:")
        print("1. Track Package")
        print("2. View My Packages")

        if is_staff:
            print("\n🔧 STAFF OPTIONS:")
            print("3. Receive New Package")
            print("4. Collect Package")
            print("5. Package Statistics")

        print("\n📬 PO BOX SERVICES:")
        print("6. Manage PO Boxes")

        print("\n0. Return to Main Menu")

        choice = input("\nEnter choice: ").strip()

        if choice == "1":
            track_package()
        elif choice == "2":
            view_my_packages()
        elif choice == "3" and is_staff:
            receive_package()
        elif choice == "4" and is_staff:
            collect_package()
        elif choice == "5" and is_staff:
            view_package_statistics()
        elif choice == "6":
            manage_po_boxes()
        elif choice == "0":
            break
        else:
            print("Invalid choice")
            input("Press Enter to continue...")


if __name__ == "__main__":
    mail_post_menu()
