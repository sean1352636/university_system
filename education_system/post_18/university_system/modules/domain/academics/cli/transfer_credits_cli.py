"""Transfer Credits CLI menu.

Provides a command-line interface for managing transfer credit records
including adding, viewing, approving, rejecting, searching, and
generating reports. Migrated from the legacy academicaffairs module
with enhanced functionality.
"""

import logging
import uuid
from datetime import datetime

from education_system.post_18.university_system.infrastructure.database.db import get_connection

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
#  Table initialisation
# --------------------------------------------------------------------------- #

_TABLE_INITIALISED = False


def _ensure_table():
    """Create the transfer_credits table if it does not already exist."""
    global _TABLE_INITIALISED
    if _TABLE_INITIALISED:
        return
    conn = None
    try:
        conn = get_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS transfer_credits (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                institution TEXT,
                course_name TEXT,
                grade TEXT,
                credits REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                date_requested TEXT NOT NULL,
                date_approved TEXT,
                approved_by TEXT,
                notes TEXT
            )
        ''')
        conn.commit()
        _TABLE_INITIALISED = True
    except Exception as e:
        logger.error("Error creating transfer_credits table: %s", e)
        raise
    finally:
        if conn:
            conn.close()


# --------------------------------------------------------------------------- #
#  Entry point
# --------------------------------------------------------------------------- #


def display_transfer_credits_menu(auth=None):
    """Display the transfer credits management CLI menu."""
    _ensure_table()

    if not auth or not getattr(auth, 'current_user', None):
        print("\n--- Please log in to access transfer credits.")
        input("Press Enter to continue...")
        return

    role = auth.current_user.get('role', '')
    is_admin = role in ('admin', 'staff', 'instructor')

    while True:
        print("\n" + "=" * 60)
        print("      TRANSFER CREDITS MANAGEMENT")
        print("=" * 60)

        option_num = 1
        options = {}

        print(f"{option_num}. Add Transfer Credit")
        options[str(option_num)] = 'add'
        option_num += 1

        print(f"{option_num}. View Transfer Credits")
        options[str(option_num)] = 'view'
        option_num += 1

        print(f"{option_num}. Search Transfer Credits")
        options[str(option_num)] = 'search'
        option_num += 1

        if is_admin:
            print(f"{option_num}. Approve Transfer Credits")
            options[str(option_num)] = 'approve'
            option_num += 1

            print(f"{option_num}. Reject Transfer Credits")
            options[str(option_num)] = 'reject'
            option_num += 1

            print(f"{option_num}. Delete Transfer Credit")
            options[str(option_num)] = 'delete'
            option_num += 1

        print(f"{option_num}. Generate Transfer Credit Report")
        options[str(option_num)] = 'report'
        option_num += 1

        print(f"{option_num}. Return to Main Menu")
        options[str(option_num)] = 'return'

        print("=" * 60)
        choice = input("\nEnter your choice: ").strip()

        if choice not in options:
            print("Invalid choice. Please try again.")
            continue

        action = options[choice]

        if action == 'return':
            break
        elif action == 'add':
            _add_transfer_credit()
        elif action == 'view':
            _view_transfer_credits()
        elif action == 'search':
            _search_transfer_credits()
        elif action == 'approve':
            _approve_transfer_credits(auth)
        elif action == 'reject':
            _reject_transfer_credits(auth)
        elif action == 'delete':
            _delete_transfer_credit()
        elif action == 'report':
            _generate_transfer_credit_report()


# --------------------------------------------------------------------------- #
#  Helper functions
# --------------------------------------------------------------------------- #


def _add_transfer_credit():
    """Add a new transfer credit record."""
    print("\n--- Add Transfer Credit ---")

    student_id = input("Student ID: ").strip()
    if not student_id:
        print("Student ID is required.")
        input("Press Enter to continue...")
        return

    institution = input("Originating Institution: ").strip()
    course_name = input("Course Name: ").strip()
    grade = input("Grade Received: ").strip()

    credits_str = input("Number of Credits: ").strip()
    try:
        credits = float(credits_str)
        if credits <= 0:
            raise ValueError
    except ValueError:
        print("Invalid credits value. Please enter a positive number.")
        input("Press Enter to continue...")
        return

    notes = input("Notes (optional): ").strip()

    record_id = str(uuid.uuid4())
    current_date = datetime.now().strftime("%Y-%m-%d")

    conn = None
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO transfer_credits "
            "(id, student_id, institution, course_name, grade, credits, "
            "status, date_requested, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (record_id, student_id, institution, course_name, grade,
             credits, "Pending", current_date, notes or None),
        )
        conn.commit()
        print(f"\nTransfer credit record added successfully (ID: {record_id[:8]}...).")
    except Exception as e:
        logger.error("Error adding transfer credit: %s", e)
        print(f"\nError adding transfer credit: {e}")
    finally:
        if conn:
            conn.close()

    input("Press Enter to continue...")


def _view_transfer_credits():
    """View all transfer credits, optionally filtered by student."""
    print("\n--- View Transfer Credits ---")

    student_id = input("Filter by Student ID (leave blank for all): ").strip()

    conn = None
    try:
        conn = get_connection()
        if student_id:
            rows = conn.execute(
                "SELECT * FROM transfer_credits WHERE student_id = ? "
                "ORDER BY date_requested DESC",
                (student_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transfer_credits ORDER BY date_requested DESC"
            ).fetchall()

        if not rows:
            print("\nNo transfer credit records found.")
            input("Press Enter to continue...")
            return

        _print_records(rows)
    except Exception as e:
        logger.error("Error viewing transfer credits: %s", e)
        print(f"\nError retrieving transfer credits: {e}")
    finally:
        if conn:
            conn.close()

    input("\nPress Enter to continue...")


def _search_transfer_credits():
    """Search transfer credits by student ID or institution."""
    print("\n--- Search Transfer Credits ---")
    print("1. Search by Student ID")
    print("2. Search by Institution")

    search_choice = input("\nEnter your choice: ").strip()

    if search_choice == "1":
        term = input("Enter Student ID: ").strip()
        query = ("SELECT * FROM transfer_credits "
                 "WHERE student_id LIKE ? ORDER BY date_requested DESC")
        params = (f"%{term}%",)
    elif search_choice == "2":
        term = input("Enter Institution name: ").strip()
        query = ("SELECT * FROM transfer_credits "
                 "WHERE institution LIKE ? ORDER BY date_requested DESC")
        params = (f"%{term}%",)
    else:
        print("Invalid choice.")
        input("Press Enter to continue...")
        return

    if not term:
        print("Search term is required.")
        input("Press Enter to continue...")
        return

    conn = None
    try:
        conn = get_connection()
        rows = conn.execute(query, params).fetchall()

        if not rows:
            print("\nNo matching transfer credit records found.")
            input("Press Enter to continue...")
            return

        _print_records(rows)
    except Exception as e:
        logger.error("Error searching transfer credits: %s", e)
        print(f"\nError searching transfer credits: {e}")
    finally:
        if conn:
            conn.close()

    input("\nPress Enter to continue...")


def _approve_transfer_credits(auth):
    """Approve pending transfer credit records."""
    print("\n--- Approve Transfer Credits ---")

    conn = None
    try:
        conn = get_connection()
        pending = conn.execute(
            "SELECT * FROM transfer_credits WHERE status = 'Pending' "
            "ORDER BY date_requested ASC"
        ).fetchall()

        if not pending:
            print("No pending transfer credit records to approve.")
            input("Press Enter to continue...")
            return

        print("\nPending Transfer Credit Records:")
        print(f"\n{'#':<4}{'Student':<14}{'Institution':<22}"
              f"{'Course':<20}{'Credits':<10}{'Date':<12}")
        print("-" * 82)
        for idx, r in enumerate(pending, 1):
            print(f"{idx:<4}{_val(r, 'student_id'):<14}"
                  f"{_val(r, 'institution'):<22}"
                  f"{_val(r, 'course_name'):<20}"
                  f"{_val(r, 'credits'):<10}"
                  f"{_val(r, 'date_requested'):<12}")

        choice_str = input(
            "\nEnter the number of the record to approve (or 0 to cancel): "
        ).strip()
        try:
            choice = int(choice_str)
        except ValueError:
            print("Invalid selection.")
            input("Press Enter to continue...")
            return

        if choice == 0:
            print("Approval cancelled.")
            input("Press Enter to continue...")
            return

        if 1 <= choice <= len(pending):
            record = pending[choice - 1]
            record_id = _val(record, 'id')
            current_date = datetime.now().strftime("%Y-%m-%d")
            approver = auth.current_user.get('username', 'unknown')

            conn.execute(
                "UPDATE transfer_credits "
                "SET status = 'Approved', date_approved = ?, approved_by = ? "
                "WHERE id = ?",
                (current_date, approver, record_id),
            )
            conn.commit()
            print("\nTransfer credit record approved successfully.")
        else:
            print("Invalid selection.")
    except Exception as e:
        logger.error("Error approving transfer credit: %s", e)
        print(f"\nError approving transfer credit: {e}")
    finally:
        if conn:
            conn.close()

    input("Press Enter to continue...")


def _reject_transfer_credits(auth):
    """Reject pending transfer credit records."""
    print("\n--- Reject Transfer Credits ---")

    conn = None
    try:
        conn = get_connection()
        pending = conn.execute(
            "SELECT * FROM transfer_credits WHERE status = 'Pending' "
            "ORDER BY date_requested ASC"
        ).fetchall()

        if not pending:
            print("No pending transfer credit records to reject.")
            input("Press Enter to continue...")
            return

        print("\nPending Transfer Credit Records:")
        print(f"\n{'#':<4}{'Student':<14}{'Institution':<22}"
              f"{'Course':<20}{'Credits':<10}{'Date':<12}")
        print("-" * 82)
        for idx, r in enumerate(pending, 1):
            print(f"{idx:<4}{_val(r, 'student_id'):<14}"
                  f"{_val(r, 'institution'):<22}"
                  f"{_val(r, 'course_name'):<20}"
                  f"{_val(r, 'credits'):<10}"
                  f"{_val(r, 'date_requested'):<12}")

        choice_str = input(
            "\nEnter the number of the record to reject (or 0 to cancel): "
        ).strip()
        try:
            choice = int(choice_str)
        except ValueError:
            print("Invalid selection.")
            input("Press Enter to continue...")
            return

        if choice == 0:
            print("Rejection cancelled.")
            input("Press Enter to continue...")
            return

        if 1 <= choice <= len(pending):
            record = pending[choice - 1]
            record_id = _val(record, 'id')
            reason = input("Reason for rejection (optional): ").strip()
            approver = auth.current_user.get('username', 'unknown')

            conn.execute(
                "UPDATE transfer_credits "
                "SET status = 'Rejected', approved_by = ?, notes = "
                "CASE WHEN notes IS NOT NULL AND notes != '' "
                "THEN notes || ' | Rejected: ' || ? "
                "ELSE 'Rejected: ' || ? END "
                "WHERE id = ?",
                (approver, reason or 'No reason given',
                 reason or 'No reason given', record_id),
            )
            conn.commit()
            print("\nTransfer credit record rejected.")
        else:
            print("Invalid selection.")
    except Exception as e:
        logger.error("Error rejecting transfer credit: %s", e)
        print(f"\nError rejecting transfer credit: {e}")
    finally:
        if conn:
            conn.close()

    input("Press Enter to continue...")


def _delete_transfer_credit():
    """Delete a transfer credit record."""
    print("\n--- Delete Transfer Credit ---")

    record_id = input("Enter the Transfer Credit ID to delete: ").strip()
    if not record_id:
        print("Record ID is required.")
        input("Press Enter to continue...")
        return

    conn = None
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM transfer_credits WHERE id = ? OR id LIKE ?",
            (record_id, f"{record_id}%"),
        ).fetchone()

        if not row:
            print("\nNo transfer credit record found with that ID.")
            input("Press Enter to continue...")
            return

        full_id = _val(row, 'id')
        print(f"\nRecord: Student={_val(row, 'student_id')} | "
              f"Institution={_val(row, 'institution')} | "
              f"Course={_val(row, 'course_name')} | "
              f"Credits={_val(row, 'credits')} | "
              f"Status={_val(row, 'status')}")

        confirm = input("Are you sure you want to delete this record? (yes/no): ").strip()
        if confirm.lower() != 'yes':
            print("Deletion cancelled.")
            input("Press Enter to continue...")
            return

        conn.execute("DELETE FROM transfer_credits WHERE id = ?", (full_id,))
        conn.commit()
        print("\nTransfer credit record deleted successfully.")
    except Exception as e:
        logger.error("Error deleting transfer credit: %s", e)
        print(f"\nError deleting transfer credit: {e}")
    finally:
        if conn:
            conn.close()

    input("Press Enter to continue...")


def _generate_transfer_credit_report():
    """Generate a report of approved transfer credits with totals."""
    print("\n--- Transfer Credit Report ---")

    student_id = input("Student ID (leave blank for all students): ").strip()

    conn = None
    try:
        conn = get_connection()
        if student_id:
            rows = conn.execute(
                "SELECT * FROM transfer_credits "
                "WHERE status = 'Approved' AND student_id = ? "
                "ORDER BY date_approved DESC",
                (student_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM transfer_credits "
                "WHERE status = 'Approved' ORDER BY student_id, date_approved DESC"
            ).fetchall()

        if not rows:
            print("\nNo approved transfer credits to report.")
            input("Press Enter to continue...")
            return

        total_credits = sum(float(_val(r, 'credits') or 0) for r in rows)

        print(f"\nTotal Approved Transfer Credits: {total_credits}")
        print(f"Number of Approved Records: {len(rows)}")
        print(f"\n{'Student':<14}{'Institution':<22}{'Course':<20}"
              f"{'Grade':<8}{'Credits':<10}{'Approved':<12}")
        print("-" * 86)
        for r in rows:
            print(f"{_val(r, 'student_id'):<14}"
                  f"{_val(r, 'institution'):<22}"
                  f"{_val(r, 'course_name'):<20}"
                  f"{_val(r, 'grade'):<8}"
                  f"{_val(r, 'credits'):<10}"
                  f"{_val(r, 'date_approved'):<12}")
    except Exception as e:
        logger.error("Error generating transfer credit report: %s", e)
        print(f"\nError generating report: {e}")
    finally:
        if conn:
            conn.close()

    input("\nPress Enter to continue...")


# --------------------------------------------------------------------------- #
#  Utility helpers
# --------------------------------------------------------------------------- #


def _val(row, key):
    """Safely extract a value from a sqlite3.Row or tuple-like result."""
    try:
        return row[key] if row[key] is not None else ''
    except (IndexError, TypeError):
        return ''


def _print_records(rows):
    """Print a formatted table of transfer credit records."""
    print(f"\n{'ID':<10}{'Student':<14}{'Institution':<22}"
          f"{'Course':<20}{'Grade':<8}{'Credits':<10}"
          f"{'Status':<12}{'Requested':<12}")
    print("-" * 108)
    for r in rows:
        rid = str(_val(r, 'id'))
        short_id = rid[:8] + '..' if len(rid) > 10 else rid
        print(f"{short_id:<10}{_val(r, 'student_id'):<14}"
              f"{_val(r, 'institution'):<22}"
              f"{_val(r, 'course_name'):<20}"
              f"{_val(r, 'grade'):<8}"
              f"{_val(r, 'credits'):<10}"
              f"{_val(r, 'status'):<12}"
              f"{_val(r, 'date_requested'):<12}")
