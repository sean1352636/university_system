from __future__ import annotations

from datetime import datetime
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.core.services.student_union_misc.union_context import check_and_award_badges

def view_all_checkouts(cursor):
    """View all equipment checkouts (admin only)"""
    try:
        print("\nAll Equipment Checkouts")
        print("=" * 40)

        cursor.execute('''
        SELECT c.checkout_id, e.equipment_name, s.first_name, s.last_name,
               c.checkout_date, c.expected_return, c.actual_return, c.status,
               cl.club_name
        FROM equipment_checkouts c
        JOIN union_equipment e ON c.equipment_id = e.equipment_id
        JOIN students s ON c.borrower_id = s.student_id
        LEFT JOIN student_clubs cl ON c.club_id = cl.club_id
        ORDER BY c.checkout_date DESC
        LIMIT 50
        ''')

        checkouts = cursor.fetchall()

        if not checkouts:
            print("No equipment checkouts found.")
            return

        print(f"{'ID':<6} {'Equipment':<20} {'Borrower':<20} {'Checkout':<12} {'Due':<12} {'Returned':<12} {'Status':<12}")
        print("-" * 100)

        for checkout in checkouts:
            returned = checkout[6][:10] if checkout[6] else "Not returned"
            borrower = f"{checkout[2]} {checkout[3]}"
            print(f"{checkout[0]:<6} {checkout[1][:20]:<20} {borrower[:20]:<20} {checkout[4][:10]:<12} {checkout[5]:<12} {returned:<12} {checkout[7]:<12}")

        # Show overdue items
        cursor.execute('''
        SELECT COUNT(*) FROM equipment_checkouts
        WHERE status = 'checked_out' AND expected_return < date('now')
        ''')

        overdue_count = cursor.fetchone()[0]

        if overdue_count > 0:
            print(f"\n⚠️  Warning: {overdue_count} items are overdue!")

            show_overdue = input("Show overdue items? (y/n): ").strip().lower()
            if show_overdue == 'y':
                cursor.execute('''
                SELECT e.equipment_name, s.first_name, s.last_name, c.expected_return,
                       (julianday('now') - julianday(c.expected_return)) as days_overdue
                FROM equipment_checkouts c
                JOIN union_equipment e ON c.equipment_id = e.equipment_id
                JOIN students s ON c.borrower_id = s.student_id
                WHERE c.status = 'checked_out' AND c.expected_return < date('now')
                ORDER BY days_overdue DESC
                ''')

                overdue_items = cursor.fetchall()

                print(f"\nOverdue Items:")
                print(f"{'Equipment':<25} {'Borrower':<20} {'Due Date':<12} {'Days Overdue':<12}")
                print("-" * 70)

                for item in overdue_items:
                    borrower = f"{item[1]} {item[2]}"
                    print(f"{item[0][:25]:<25} {borrower[:20]:<20} {item[3]:<12} {int(item[4]):<12}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_leaderboard(cursor):
    """View points leaderboard"""
    try:
        print(f"\nEngagement Leaderboard")
        print("=" * 30)

        # Overall points leaderboard
        cursor.execute('''
        SELECT s.first_name, s.last_name, 
               COALESCE(SUM(sp.points_earned), 0) as total_points,
               COUNT(sb.badge_id) as badge_count
        FROM students s
        LEFT JOIN student_points sp ON s.student_id = sp.student_id
        LEFT JOIN student_badges sb ON s.student_id = sb.student_id
        GROUP BY s.student_id, s.first_name, s.last_name
        HAVING total_points > 0
        ORDER BY total_points DESC
        LIMIT 20
        ''')

        leaderboard = cursor.fetchall()

        if not leaderboard:
            print("No engagement data available.")
            return

        print(f"{'Rank':<6} {'Name':<25} {'Points':<8} {'Badges':<8}")
        print("-" * 50)

        for i, entry in enumerate(leaderboard, 1):
            name = f"{entry[0]} {entry[1]}"
            print(f"{i:<6} {name[:25]:<25} {entry[2]:<8} {entry[3]:<8}")

        # Monthly leaderboard
        current_month = datetime.now().strftime('%Y-%m')

        cursor.execute('''
        SELECT s.first_name, s.last_name, 
               COALESCE(SUM(sp.points_earned), 0) as monthly_points
        FROM students s
        LEFT JOIN student_points sp ON s.student_id = sp.student_id
        WHERE sp.earned_date LIKE ?
        GROUP BY s.student_id, s.first_name, s.last_name
        HAVING monthly_points > 0
        ORDER BY monthly_points DESC
        LIMIT 10
        ''', (f'{current_month}%',))

        monthly_leaders = cursor.fetchall()

        if monthly_leaders:
            print(f"\nThis Month's Top Performers:")
            print(f"{'Rank':<6} {'Name':<25} {'Points':<8}")
            print("-" * 40)

            for i, entry in enumerate(monthly_leaders, 1):
                name = f"{entry[0]} {entry[1]}"
                print(f"{i:<6} {name[:25]:<25} {entry[2]:<8}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def view_point_opportunities(cursor):
    """Show ways students can earn points"""
    try:
        print(f"\nWays to Earn Points:")
        print("=" * 25)

        opportunities = [
            ("Event Attendance", "Attend club events", "5-15 points"),
            ("Event Organization", "Help organize events", "20-50 points"),
            ("Club Leadership", "Hold club officer position", "100 points/semester"),
            ("Volunteering", "Participate in volunteer activities", "10-25 points"),
            ("Academic Achievement", "High grades, awards", "25-100 points"),
            ("Mentorship", "Be a mentor or mentee", "30 points/relationship"),
            ("Competition Participation", "Join inter-club competitions", "15-40 points"),
            ("Feedback & Reviews", "Rate events and experiences", "2-5 points"),
            ("Recruiting", "Bring new members to clubs", "10 points/new member"),
            ("Sustainability", "Participate in green initiatives", "5-20 points")
        ]

        print(f"{'Activity':<25} {'Description':<35} {'Points':<15}")
        print("-" * 75)

        for activity, description, points in opportunities:
            print(f"{activity:<25} {description:<35} {points:<15}")

        print(f"\nNote: Points are awarded automatically for most activities.")
        print("Check your points balance regularly to see your progress!")

        # Show upcoming events that award points
        cursor.execute('''
        SELECT e.event_name, c.club_name, e.event_date
        FROM union_events e
        JOIN student_clubs c ON e.organizer_id = c.club_id
        WHERE e.event_date >= date('now') AND e.status = 'upcoming'
        ORDER BY e.event_date
        LIMIT 5
        ''')

        upcoming_events = cursor.fetchall()

        if upcoming_events:
            print(f"\nUpcoming Point-Earning Events:")
            print(f"{'Event':<30} {'Club':<20} {'Date':<12}")
            print("-" * 65)

            for event in upcoming_events:
                print(f"{event[0][:30]:<30} {event[1][:20]:<20} {event[2]:<12}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def award_points_to_student(cursor, conn):
    """Award points to a student (admin function)"""
    try:
        print(f"\nAward Points to Student")
        print("=" * 25)

        student_id = input("Enter student ID: ").strip()
        if not student_id:
            print("Student ID cannot be empty.")
            return

        # Verify student exists
        cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            print(f"No student found with ID {student_id}.")
            return

        print(f"Awarding points to: {student[0]} {student[1]}")

        try:
            points = int(input("Points to award: ").strip())
            if points <= 0:
                print("Points must be positive.")
                return
        except ValueError:
            print("Invalid points format.")
            return

        activity_type = input("Activity type: ").strip()
        if not activity_type:
            print("Activity type cannot be empty.")
            return

        description = input("Activity description: ").strip()
        if not description:
            print("Description cannot be empty.")
            return

        earned_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Get current balance
        cursor.execute('''
        SELECT COALESCE(SUM(points_earned) - SUM(points_spent), 0) as current_balance
        FROM student_points
        WHERE student_id = ?
        ''', (student_id,))

        current_balance = cursor.fetchone()[0]
        new_balance = current_balance + points

        # Award points
        cursor.execute('''
        INSERT INTO student_points (
            student_id, points_earned, current_balance, activity_type,
            activity_description, earned_date
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, points, new_balance, activity_type, description, earned_date))

        conn.commit()

        print(f"Successfully awarded {points} points to {student[0]} {student[1]}!")
        print(f"New balance: {new_balance} points")

        # Check for new badges
        check_and_award_badges(student_id, cursor)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def auto_award_points(student_id, activity_type, points, description, cursor, conn):
    """Automatically award points for activities (called by other functions)"""
    try:
        # Get current balance
        cursor.execute('''
        SELECT COALESCE(SUM(points_earned) - SUM(points_spent), 0) as current_balance
        FROM student_points
        WHERE student_id = ?
        ''', (student_id,))

        current_balance = cursor.fetchone()[0]
        new_balance = current_balance + points

        earned_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
        INSERT INTO student_points (
            student_id, points_earned, current_balance, activity_type,
            activity_description, earned_date
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, points, new_balance, activity_type, description, earned_date))

        conn.commit()
        return True

    except sqlite3.Error:
        return False
