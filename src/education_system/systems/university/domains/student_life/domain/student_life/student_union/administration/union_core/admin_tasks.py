"""Student Union admin tasks: election set-up and union reps.

Split out of ``student_union_core.py``, which re-exports every name here;
callers keep importing from ``student_union_core``.
"""

from datetime import datetime

from education_system.systems.university.infrastructure.database.db import get_connection


def set_up_election(cursor=None, conn=None):
    """Set up a new election"""
    print("\n=== Set Up Election ===")
    title = input("Enter election title: ").strip()
    description = input("Enter description: ").strip()
    start_date = input("Enter start date (YYYY-MM-DD): ").strip()
    end_date = input("Enter end date (YYYY-MM-DD): ").strip()

    close_conn = False
    if conn is None:
        conn = get_connection()
        cursor = conn.cursor()
        close_conn = True

    try:
        cursor.execute('''
            INSERT INTO elections (title, description, start_date, end_date,
                                   voting_start, voting_end, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, description, start_date, end_date, start_date, end_date,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        print("✓ Election created successfully!")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if close_conn and conn:
            conn.close()

def manage_union_reps():
    """Manage union representatives"""
    print("\n=== Manage Union Representatives ===")

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS union_representatives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                position TEXT,
                term_start TEXT,
                term_end TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')

        print("1. Add representative")
        print("2. View representatives")
        print("3. Remove representative")
        choice = input("Select option: ").strip()

        if choice == '1':
            # This one genuinely is somebody else's ID — an officer is being
            # appointed — so it stays a prompt, but it has to name a real student.
            student_id = input("Student ID of the representative: ").strip()
            if not student_id:
                print("Cancelled.")
                return
            cursor.execute(
                "SELECT first_name, last_name FROM students WHERE student_id = ?",
                (student_id,))
            student = cursor.fetchone()
            if not student:
                print(f"No student found with ID {student_id}.")
                return
            print(f"Appointing: {(student[0] or '')} {(student[1] or '')}".rstrip())
            position = input("Position: ").strip()
            term_start = input("Term start (YYYY-MM-DD): ").strip()
            term_end = input("Term end (YYYY-MM-DD): ").strip()

            cursor.execute('''
                INSERT INTO union_representatives (student_id, position, term_start, term_end)
                VALUES (?, ?, ?, ?)
            ''', (student_id, position, term_start, term_end))
            conn.commit()
            print("✓ Representative added!")

        elif choice == '2':
            cursor.execute('''
                SELECT student_id, position, term_start, term_end
                FROM union_representatives
                WHERE status = 'active'
            ''')
            reps = cursor.fetchall()
            if not reps:
                print("No active representatives.")
            else:
                for sid, pos, start, end in reps:
                    print(f"\n• {sid} - {pos}")
                    print(f"  Term: {start} to {end}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()
