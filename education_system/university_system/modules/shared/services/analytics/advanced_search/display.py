"""Result display, student detail view, academic history, and email simulation."""
import csv
import logging

from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.shared.services.analytics.advanced_search import _globals
from education_system.university_system.modules.shared.services.analytics.advanced_search.export import export_single_student


def _parse_row_selection(raw, max_row):
    """Parse a selection string like '1-3,5,8' into a sorted unique list of 0-based indices.

    Returns [] on empty input and raises ValueError on malformed input.
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.lower() == "all":
        return list(range(max_row))
    picked = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo_s, hi_s = part.split("-", 1)
            lo, hi = int(lo_s), int(hi_s)
            if lo > hi:
                lo, hi = hi, lo
            for i in range(lo, hi + 1):
                if 1 <= i <= max_row:
                    picked.add(i - 1)
        else:
            i = int(part)
            if 1 <= i <= max_row:
                picked.add(i - 1)
    return sorted(picked)


def _copy_column(rows, column_index, label):
    """Print a column's values one-per-line and as a comma-joined list for easy terminal copy."""
    values = []
    for r in rows:
        if column_index < len(r) and r[column_index] not in (None, ""):
            values.append(str(r[column_index]))
    if not values:
        print(f"No {label} values found in the selected rows.")
        return
    print(f"\n📋 {label} ({len(values)} value(s)) — one per line:")
    for v in values:
        print(v)
    print(f"\nComma-joined: {', '.join(values)}")


def _export_rows_csv(rows):
    """Export the provided rows to a user-supplied CSV path."""
    if not rows:
        print("No rows to export.")
        return
    path = input("CSV path [selected_results.csv]: ").strip() or "selected_results.csv"
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "student_id", "email", "title", "first_name", "middle_name",
                "last_name", "gender", "dob", "age", "course", "registration",
            ])
            for r in rows:
                writer.writerow(r[:11])
        print(f"✅ Exported {len(rows)} row(s) to {path}")
    except Exception as e:
        print(f"❌ Export failed: {e}")


def _bulk_actions_menu(results):
    """Offer bulk actions over a user-selected subset of results."""
    print(f"\nSelect rows (e.g. '1-3,5,8' or 'all') from 1..{len(results)}:")
    raw = input("Rows: ").strip()
    try:
        indices = _parse_row_selection(raw, len(results))
    except ValueError:
        print("Invalid row selection.")
        return
    if not indices:
        print("No valid rows selected.")
        return
    subset = [results[i] for i in indices]
    print(f"Selected {len(subset)} row(s).")

    print("\nBulk actions:")
    print("  1. Copy IDs")
    print("  2. Copy Emails")
    print("  3. Copy Names")
    print("  4. Export selected to CSV")
    print("  Enter) Cancel")
    action = input("Action: ").strip()
    if action == "1":
        _copy_column(subset, 0, "IDs")
    elif action == "2":
        _copy_column(subset, 1, "Emails")
    elif action == "3":
        for r in subset:
            fn = r[3] if len(r) > 3 else ""
            ln = r[5] if len(r) > 5 else ""
            print(f"{fn} {ln}".strip())
    elif action == "4":
        _export_rows_csv(subset)
    else:
        print("Cancelled.")


def display_search_results(results):
    """Enhanced search results display with pagination and bulk actions."""
    if not results:
        print("No matching records found.")
        _globals.last_search_results = []
        return

    _globals.last_search_results = results

    print(f"\n🔍 {len(results)} matching records found")

    # Pagination for large result sets
    page_size = 10
    current_page = 0

    while True:
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(results))

        print(f"\n📄 Page {current_page + 1} of {(len(results) - 1) // page_size + 1}")
        print("=" * 80)

        for i in range(start_idx, end_idx):
            student = results[i]
            # Guard against rows from non-student entity searches (shorter tuples).
            def _col(idx, default=""):
                return student[idx] if idx < len(student) and student[idx] is not None else default
            print(f"\n{i+1}. ID: {_col(0)}")
            if len(student) >= 6:
                print(f"   Name: {_col(2)} {_col(3)} {_col(4, '')} {_col(5)}")
            if len(student) >= 2:
                print(f"   Email: {_col(1)}")
            if len(student) >= 10:
                print(f"   Gender: {_col(6)} | Age: {_col(8)} | Course: {_col(9)}")
            if len(student) >= 11:
                print(f"   Registration: {_col(10)}")

        # Navigation options
        print(f"\nOptions:")
        options = []
        if current_page > 0:
            options.append("p) Previous page")
        if end_idx < len(results):
            options.append("n) Next page")

        options.extend([
            "d) View detailed info",
            "e) Export all results",
            "b) Bulk actions on selected rows",
            "s) Save search",
            "Enter) Continue",
        ])

        print(" | ".join(options))

        choice = input("\nChoice: ").strip().lower()

        if choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'n' and end_idx < len(results):
            current_page += 1
        elif choice == 'd':
            try:
                student_num = int(input("Enter student number for details: ")) - 1
                if 0 <= student_num < len(results):
                    display_student_detail(results[student_num])
                else:
                    print("Invalid student number.")
            except ValueError:
                print("Invalid input.")
        elif choice == 'e':
            from education_system.university_system.modules.shared.services.analytics.advanced_search.bulk_ops import save_last_search_results
            save_last_search_results()
        elif choice == 'b':
            _bulk_actions_menu(results)
        elif choice == 's':
            from education_system.university_system.modules.shared.services.analytics.advanced_search.saved_searches import save_search_profile
            save_search_profile()
        elif choice == '' or choice == 'enter':
            break
        else:
            print("Invalid choice.")

def display_student_detail(student):
    """Enhanced detailed information display for a specific student"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\n" + "="*80)
        print(f"📋 DETAILED STUDENT INFORMATION - ID: {student[0]}")
        print("="*80)

        # Basic Information
        print(f"📧 Email Address: {student[1]}")
        print(f"👤 Title: {student[2]}")
        print(f"🏷️  Name: {student[3]} {student[4] or ''} {student[5]}")
        print(f"⚧  Gender: {student[6]}")
        print(f"🎂 Date of Birth: {student[7]}")
        print(f"📅 Age: {student[8]}")
        print(f"🎓 Course: {student[9]}")
        print(f"📝 Registration: {student[10]}")

        # Module Information
        cursor.execute('''
        SELECT module_type, module_code, module_name, grade, enrollment_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY module_type, module_name
        ''', (student[0],))

        modules = cursor.fetchall()

        print(f"\n📚 ENROLLED MODULES ({len(modules)} total):")
        print("-" * 80)

        if modules:
            print(f"{'Type':<15} {'Code':<10} {'Name':<30} {'Grade':<8} {'Enrolled':<12}")
            print("-" * 80)

            for module in modules:
                module_type, code, name, grade, enrolled_date = module
                grade_display = grade if grade else "In Progress"
                enrolled_display = enrolled_date[:10] if enrolled_date else "N/A"
                print(f"{module_type:<15} {code:<10} {name:<30} {grade_display:<8} {enrolled_display:<12}")
        else:
            print("No modules enrolled.")

        # Additional Analytics
        if modules:
            completed_modules = sum(1 for m in modules if m[3] is not None)
            completion_rate = (completed_modules / len(modules)) * 100

            print(f"\n📊 ACADEMIC SUMMARY:")
            print("-" * 40)
            print(f"Total Modules: {len(modules)}")
            print(f"Completed: {completed_modules}")
            print(f"In Progress: {len(modules) - completed_modules}")
            print(f"Completion Rate: {completion_rate:.1f}%")

        print("="*80)

        # Action options
        print("\nActions:")
        print("1. Export student data")
        print("2. Add to favorites")
        print("3. Send email (simulation)")
        print("4. View academic history")
        print("5. Return")

        action = input("Select action (1-5): ").strip()

        if action == '1':
            export_single_student(student, modules)
        elif action == '2':
            print(f"✅ Student {student[0]} added to favorites")
        elif action == '3':
            simulate_send_email(student)
        elif action == '4':
            view_academic_history(student[0])

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")

def simulate_send_email(student):
    """Simulate sending email to student"""
    print(f"\n📧 EMAIL SIMULATION")
    print("-" * 30)
    print(f"To: {student[1]} ({student[3]} {student[5]})")

    subject = input("Email subject: ").strip()
    message = input("Email message: ").strip()

    if subject and message:
        print(f"\n✅ Email simulated successfully!")
        print(f"Subject: {subject}")
        print(f"Message: {message}")

        # Log the email simulation
        logging.info(f"Email simulated - To: {student[1]}, Subject: {subject}")
    else:
        print("❌ Email cancelled - missing subject or message")

def view_academic_history(student_id):
    """View detailed academic history"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        print(f"\n📈 ACADEMIC HISTORY - Student {student_id}")
        print("="*60)

        # Get modules with timeline
        cursor.execute('''
        SELECT module_code, module_name, module_type, grade,
               enrollment_date, completion_date
        FROM student_modules
        WHERE student_id = ?
        ORDER BY enrollment_date
        ''', (student_id,))

        history = cursor.fetchall()

        if history:
            print(f"{'Date':<12} {'Code':<8} {'Name':<25} {'Type':<10} {'Grade':<8}")
            print("-" * 70)

            for module in history:
                code, name, mod_type, grade, enroll_date, complete_date = module
                date_display = enroll_date[:10] if enroll_date else "N/A"
                grade_display = grade if grade else "In Progress"
                print(f"{date_display:<12} {code:<8} {name:<25} {mod_type:<10} {grade_display:<8}")
        else:
            print("No academic history found.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
