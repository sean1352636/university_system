from __future__ import annotations

from datetime import datetime
from university_system.infrastructure.database.db import sqlite3
from university_system.modules.domain.student_affairs.student_union.services.union_context import check_and_award_badges
from university_system.modules.shared.utils.i18n import get_text as _t

def view_all_checkouts(cursor):
    """View all equipment checkouts (admin only)"""
    try:
        print("\n" + _t("student_union.points.all_equipment_checkouts"))
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
            print(_t("student_union.points.no_checkouts_found"))
            return

        print(f"{_t('common.id'):<6} {_t('student_union.points.equipment'):<20} {_t('student_union.points.borrower'):<20} {_t('student_union.points.checkout'):<12} {_t('student_union.points.due'):<12} {_t('student_union.points.returned'):<12} {_t('common.status'):<12}")
        print("-" * 100)

        for checkout in checkouts:
            returned = checkout[6][:10] if checkout[6] else _t("student_union.points.not_returned")
            borrower = f"{checkout[2]} {checkout[3]}"
            print(f"{checkout[0]:<6} {checkout[1][:20]:<20} {borrower[:20]:<20} {checkout[4][:10]:<12} {checkout[5]:<12} {returned:<12} {checkout[7]:<12}")

        # Show overdue items
        cursor.execute('''
        SELECT COUNT(*) FROM equipment_checkouts
        WHERE status = 'checked_out' AND expected_return < date('now')
        ''')

        overdue_count = cursor.fetchone()[0]

        if overdue_count > 0:
            print(f"\n⚠️  " + _t("student_union.points.overdue_warning", count=overdue_count))

            show_overdue = input(_t("student_union.points.show_overdue_prompt")).strip().lower()
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

                print(f"\n" + _t("student_union.points.overdue_items"))
                print(f"{_t('student_union.points.equipment'):<25} {_t('student_union.points.borrower'):<20} {_t('student_union.points.due_date'):<12} {_t('student_union.points.days_overdue'):<12}")
                print("-" * 70)

                for item in overdue_items:
                    borrower = f"{item[1]} {item[2]}"
                    print(f"{item[0][:25]:<25} {borrower[:20]:<20} {item[3]:<12} {int(item[4]):<12}")

    except sqlite3.Error as e:
        print(_t("common.database_error_msg", error=str(e)))
    except Exception as e:
        print(_t("common.error_occurred", error=str(e)))

def view_leaderboard(cursor):
    """View points leaderboard"""
    try:
        print(f"\n" + _t("student_union.points.engagement_leaderboard"))
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
            print(_t("student_union.points.no_engagement_data"))
            return

        print(f"{_t('student_union.points.rank'):<6} {_t('common.name'):<25} {_t('student_union.points.points'):<8} {_t('student_union.points.badges'):<8}")
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
            print(f"\n" + _t("student_union.points.monthly_top_performers"))
            print(f"{_t('student_union.points.rank'):<6} {_t('common.name'):<25} {_t('student_union.points.points'):<8}")
            print("-" * 40)

            for i, entry in enumerate(monthly_leaders, 1):
                name = f"{entry[0]} {entry[1]}"
                print(f"{i:<6} {name[:25]:<25} {entry[2]:<8}")

    except sqlite3.Error as e:
        print(_t("common.database_error_msg", error=str(e)))
    except Exception as e:
        print(_t("common.error_occurred", error=str(e)))

def view_point_opportunities(cursor):
    """Show ways students can earn points"""
    try:
        print(f"\n" + _t("student_union.points.ways_to_earn"))
        print("=" * 25)

        opportunities = [
            (_t("student_union.points.opp_event_attendance"), _t("student_union.points.opp_event_attendance_desc"), _t("student_union.points.opp_event_attendance_pts")),
            (_t("student_union.points.opp_event_organization"), _t("student_union.points.opp_event_organization_desc"), _t("student_union.points.opp_event_organization_pts")),
            (_t("student_union.points.opp_club_leadership"), _t("student_union.points.opp_club_leadership_desc"), _t("student_union.points.opp_club_leadership_pts")),
            (_t("student_union.points.opp_volunteering"), _t("student_union.points.opp_volunteering_desc"), _t("student_union.points.opp_volunteering_pts")),
            (_t("student_union.points.opp_academic_achievement"), _t("student_union.points.opp_academic_achievement_desc"), _t("student_union.points.opp_academic_achievement_pts")),
            (_t("student_union.points.opp_mentorship"), _t("student_union.points.opp_mentorship_desc"), _t("student_union.points.opp_mentorship_pts")),
            (_t("student_union.points.opp_competition"), _t("student_union.points.opp_competition_desc"), _t("student_union.points.opp_competition_pts")),
            (_t("student_union.points.opp_feedback"), _t("student_union.points.opp_feedback_desc"), _t("student_union.points.opp_feedback_pts")),
            (_t("student_union.points.opp_recruiting"), _t("student_union.points.opp_recruiting_desc"), _t("student_union.points.opp_recruiting_pts")),
            (_t("student_union.points.opp_sustainability"), _t("student_union.points.opp_sustainability_desc"), _t("student_union.points.opp_sustainability_pts"))
        ]

        print(f"{_t('student_union.points.activity'):<25} {_t('common.description'):<35} {_t('student_union.points.points'):<15}")
        print("-" * 75)

        for activity, description, points in opportunities:
            print(f"{activity:<25} {description:<35} {points:<15}")

        print(f"\n" + _t("student_union.points.auto_award_note"))
        print(_t("student_union.points.check_balance_note"))

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
            print(f"\n" + _t("student_union.points.upcoming_point_events"))
            print(f"{_t('student_union.points.event'):<30} {_t('student_union.points.club'):<20} {_t('common.date'):<12}")
            print("-" * 65)

            for event in upcoming_events:
                print(f"{event[0][:30]:<30} {event[1][:20]:<20} {event[2]:<12}")

    except sqlite3.Error as e:
        print(_t("common.database_error_msg", error=str(e)))
    except Exception as e:
        print(_t("common.error_occurred", error=str(e)))

def award_points_to_student(cursor, conn):
    """Award points to a student (admin function)"""
    try:
        print(f"\n" + _t("student_union.points.award_points_title"))
        print("=" * 25)

        student_id = input(_t("student_union.points.enter_student_id")).strip()
        if not student_id:
            print(_t("student_union.points.student_id_required"))
            return

        # Verify student exists
        cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            print(_t("student_union.points.no_student_found", student_id=student_id))
            return

        print(_t("student_union.points.awarding_points_to", name=f"{student[0]} {student[1]}"))

        try:
            points = int(input(_t("student_union.points.points_to_award")).strip())
            if points <= 0:
                print(_t("student_union.points.points_must_be_positive"))
                return
        except ValueError:
            print(_t("student_union.points.invalid_points_format"))
            return

        activity_type = input(_t("student_union.points.enter_activity_type")).strip()
        if not activity_type:
            print(_t("student_union.points.activity_type_required"))
            return

        description = input(_t("student_union.points.enter_activity_description")).strip()
        if not description:
            print(_t("student_union.points.description_required"))
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

        print(_t("student_union.points.points_awarded_success", points=points, name=f"{student[0]} {student[1]}"))
        print(_t("student_union.points.new_balance", balance=new_balance))

        # Check for new badges
        check_and_award_badges(student_id, cursor)

    except sqlite3.Error as e:
        print(_t("common.database_error_msg", error=str(e)))
    except Exception as e:
        print(_t("common.error_occurred", error=str(e)))

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
