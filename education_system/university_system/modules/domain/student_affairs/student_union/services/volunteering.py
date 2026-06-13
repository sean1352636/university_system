from __future__ import annotations

from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.modules.domain.student_affairs.student_union.services import union_context as ctx
from education_system.university_system.modules.domain.student_affairs.student_union.services.union_context import auto_award_points
from education_system.university_system.core.i18n import get_text as _t

def browse_volunteer_opportunities(cursor):
    """Browse available volunteer opportunities"""
    try:
        cursor.execute('''
        SELECT opportunity_id, organization_name, description, location,
               start_date, end_date, hours_required, skills_needed,
               max_volunteers, current_volunteers, status
        FROM volunteer_opportunities
        WHERE status = 'open' AND start_date >= date('now')
        ORDER BY start_date
        ''')

        opportunities = cursor.fetchall()

        if not opportunities:
            print(_t("student_union.volunteer.no_opportunities"))
            return

        print(f"\n{_t('student_union.volunteer.available_header')}")
        print("=" * 45)

        for opp in opportunities:
            print(f"\n{_t('student_union.volunteer.id_label')} {opp[0]}")
            print(f"{_t('student_union.volunteer.organization_label')} {opp[1]}")
            print(f"{_t('student_union.volunteer.description_label')} {opp[2]}")
            print(f"{_t('student_union.volunteer.location_label')} {opp[3]}")
            print(f"{_t('student_union.volunteer.period_label')} {_t('student_union.volunteer.period_format', start=opp[4], end=opp[5])}")
            print(_t("student_union.volunteer.time_commitment", hours=opp[6]))
            if opp[7]:
                print(f"{_t('student_union.volunteer.skills_needed')} {opp[7]}")
            print(f"{_t('student_union.volunteer.volunteers_label')} {_t('student_union.volunteer.volunteers_format', current=opp[9], max=opp[8])}")
            print("-" * 40)

        # Option to sign up
        signup_id = input(f"\n{_t('student_union.volunteer.enter_opportunity_id')} ").strip()
        if signup_id.isdigit():
            signup_for_volunteer_opportunity(int(signup_id), cursor)

    except sqlite3.Error as e:
        print(f"{_t('student_union.volunteer.database_error')} {e}")
    except Exception as e:
        print(f"{_t('student_union.volunteer.error_occurred')} {e}")

def signup_for_volunteer_opportunity(opportunity_id, cursor):
    """Sign up for a volunteer opportunity"""
    try:

        # Get student ID
        cursor.execute('SELECT student_id FROM users WHERE id = ?', (ctx.auth.current_user['id'],))
        result = cursor.fetchone()
        student_id = result[0]

        # Check opportunity details
        cursor.execute('''
        SELECT organization_name, description, max_volunteers, current_volunteers
        FROM volunteer_opportunities
        WHERE opportunity_id = ? AND status = 'open'
        ''', (opportunity_id,))

        opp = cursor.fetchone()

        if not opp:
            print(_t("student_union.volunteer.opportunity_not_found"))
            return

        if opp[3] >= opp[2]:
            print(_t("student_union.volunteer.opportunity_full"))
            return

        # Check if already signed up
        cursor.execute('''
        SELECT COUNT(*) FROM volunteer_signups
        WHERE opportunity_id = ? AND student_id = ?
        ''', (opportunity_id, student_id))

        if cursor.fetchone()[0] > 0:
            print(_t("student_union.volunteer.already_signed_up"))
            return

        print(f"{_t('student_union.volunteer.signing_up_for')} {opp[0]}")
        print(f"{_t('student_union.volunteer.activity_label')} {opp[1]}")

        confirm = input(f"{_t('student_union.volunteer.confirm_signup')} ").strip().lower()
        if confirm == 'y':
            signup_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
            INSERT INTO volunteer_signups (
                opportunity_id, student_id, signup_date, status
            ) VALUES (?, ?, ?, ?)
            ''', (opportunity_id, student_id, signup_date, 'signed_up'))

            # Update volunteer count
            cursor.execute('''
            UPDATE volunteer_opportunities
            SET current_volunteers = current_volunteers + 1
            WHERE opportunity_id = ?
            ''', (opportunity_id,))

            print(_t("student_union.volunteer.signup_success"))
            print(_t("student_union.volunteer.email_notification"))

            # Award points for volunteering commitment
            auto_award_points(student_id, "Community Service", 20,
                            f"Signed up for volunteer opportunity: {opp[0]}", cursor, None)

    except sqlite3.Error as e:
        print(f"{_t('student_union.volunteer.database_error')} {e}")
    except Exception as e:
        print(f"{_t('student_union.volunteer.error_occurred')} {e}")

def view_my_volunteer_activities(student_id, cursor):
    """View student's volunteer activities"""
    try:
        cursor.execute('''
        SELECT vo.organization_name, vo.description, vs.signup_date,
               vo.start_date, vo.end_date, vs.hours_completed, vs.status
        FROM volunteer_signups vs
        JOIN volunteer_opportunities vo ON vs.opportunity_id = vo.opportunity_id
        WHERE vs.student_id = ?
        ORDER BY vs.signup_date DESC
        ''', (student_id,))

        activities = cursor.fetchall()

        if not activities:
            print(_t("student_union.volunteer.no_activities"))
            return

        print(f"\n{_t('student_union.volunteer.your_activities_header')}")
        print("=" * 35)
        print(f"{_t('student_union.volunteer.activities_table_org'):<25} {_t('student_union.volunteer.activities_table_period'):<20} {_t('student_union.volunteer.activities_table_hours'):<8} {_t('student_union.volunteer.activities_table_status'):<12}")
        print("-" * 70)

        total_hours = 0
        for activity in activities:
            period = f"{activity[3]} to {activity[4]}"
            hours = activity[5] if activity[5] else 0
            total_hours += hours

            print(f"{activity[0][:25]:<25} {period[:20]:<20} {hours:<8.1f} {activity[6]:<12}")

        print("-" * 70)
        print(f"{_t('student_union.volunteer.total_hours'):<53} {total_hours:<8.1f}")

        # Show impact summary
        completed_activities = len([a for a in activities if a[6] == 'completed'])
        active_activities = len([a for a in activities if a[6] == 'signed_up'])

        print(f"\n{_t('student_union.volunteer.summary_header')}")
        print(f"{_t('student_union.volunteer.completed_activities')} {completed_activities}")
        print(f"{_t('student_union.volunteer.active_commitments')} {active_activities}")
        print(f"{_t('student_union.volunteer.total_hours_label')} {total_hours:.1f}")

        # Calculate volunteer level
        if total_hours >= 100:
            level = f"{_t('student_union.volunteer.level_champion')}"
        elif total_hours >= 50:
            level = f"{_t('student_union.volunteer.level_dedicated')}"
        elif total_hours >= 20:
            level = f"{_t('student_union.volunteer.level_active')}"
        elif total_hours >= 5:
            level = f"{_t('student_union.volunteer.level_helper')}"
        else:
            level = f"{_t('student_union.volunteer.level_getting_started')}"

        print(f"{_t('student_union.volunteer.volunteer_level')} {level}")

    except sqlite3.Error as e:
        print(f"{_t('student_union.volunteer.database_error')} {e}")
    except Exception as e:
        print(f"{_t('student_union.volunteer.error_occurred')} {e}")

def track_community_service_hours(student_id, cursor, conn):
    """Track and log community service hours"""
    try:
        print(f"\n{_t('student_union.volunteer.tracking_header')}")
        print("=" * 40)

        print(_t("student_union.volunteer.menu_log_hours"))
        print(_t("student_union.volunteer.menu_view_summary"))
        print(_t("student_union.volunteer.menu_generate_verification"))
        print(_t("student_union.volunteer.menu_set_goals"))

        choice = input(f"{_t('student_union.volunteer.choose_option')} ").strip()

        if choice == '1':
            # Log volunteer hours
            cursor.execute('''
            SELECT vs.opportunity_id, vo.organization_name, vo.description
            FROM volunteer_signups vs
            JOIN volunteer_opportunities vo ON vs.opportunity_id = vo.opportunity_id
            WHERE vs.student_id = ? AND vs.status = 'signed_up'
            ORDER BY vo.start_date
            ''', (student_id,))

            active_opportunities = cursor.fetchall()

            if not active_opportunities:
                print(_t("student_union.volunteer.no_active_commitments"))
                return

            print(_t("student_union.volunteer.active_opportunities"))
            for i, opp in enumerate(active_opportunities):
                print(f"{i+1}. {opp[1]} - {opp[2]}")

            opp_choice = input(f"{_t('student_union.volunteer.select_opportunity')} ").strip()
            if not opp_choice.isdigit() or int(opp_choice) < 1 or int(opp_choice) > len(active_opportunities):
                print(_t("student_union.volunteer.invalid_selection"))
                return

            selected_opp = active_opportunities[int(opp_choice)-1]
            opportunity_id = selected_opp[0]

            try:
                hours = float(input(f"{_t('student_union.volunteer.hours_completed_prompt')} ").strip())
                if hours <= 0:
                    print(_t("student_union.volunteer.hours_must_positive"))
                    return
            except ValueError:
                print(_t("student_union.volunteer.invalid_hours_format"))
                return

            completion_date = input(f"{_t('student_union.volunteer.completion_date_prompt')} ").strip()
            if not completion_date:
                completion_date = datetime.now().strftime('%Y-%m-%d')

            feedback = input(f"{_t('student_union.volunteer.activity_description')} ").strip()

            # Update signup record
            cursor.execute('''
            UPDATE volunteer_signups
            SET hours_completed = COALESCE(hours_completed, 0) + ?,
                completion_date = ?, feedback = ?, status = 'completed'
            WHERE opportunity_id = ? AND student_id = ?
            ''', (hours, completion_date, feedback, opportunity_id, student_id))

            conn.commit()

            print(_t("student_union.volunteer.logged_hours_success", hours=hours))

            # Award points based on hours
            points = min(50, int(hours * 5))  # 5 points per hour, max 50
            auto_award_points(student_id, "Community Service", points,
                            f"Completed {hours} hours of volunteer work", cursor, conn)

        elif choice == '2':
            # View hour summary
            cursor.execute('''
            SELECT
                SUM(hours_completed) as total_hours,
                COUNT(DISTINCT opportunity_id) as activities,
                COUNT(DISTINCT
                    CASE WHEN status = 'completed' THEN opportunity_id END
                ) as completed_activities
            FROM volunteer_signups
            WHERE student_id = ? AND hours_completed > 0
            ''', (student_id,))

            summary = cursor.fetchone()

            print(f"\n{_t('student_union.volunteer.hour_summary_header')}")
            print(f"{_t('student_union.volunteer.summary_total_hours')} {summary[0] or 0:.1f}")
            print(f"{_t('student_union.volunteer.summary_activities')} {summary[1] or 0}")
            print(f"{_t('student_union.volunteer.summary_completed')} {summary[2] or 0}")

            # Monthly breakdown
            cursor.execute('''
            SELECT
                strftime('%Y-%m', completion_date) as month,
                SUM(hours_completed) as monthly_hours
            FROM volunteer_signups
            WHERE student_id = ? AND completion_date IS NOT NULL
            GROUP BY strftime('%Y-%m', completion_date)
            ORDER BY month DESC
            LIMIT 6
            ''', (student_id,))

            monthly_data = cursor.fetchall()

            if monthly_data:
                print(f"\n{_t('student_union.volunteer.monthly_breakdown')}")
                print(f"{_t('student_union.volunteer.month_header'):<10} {_t('student_union.volunteer.hours_header'):<8}")
                print("-" * 20)
                for month in monthly_data:
                    print(f"{month[0]:<10} {month[1]:<8.1f}")

        elif choice == '3':
            # Generate service verification
            cursor.execute('''
            SELECT SUM(hours_completed) as total_hours
            FROM volunteer_signups
            WHERE student_id = ? AND status = 'completed'
            ''', (student_id,))

            total_hours = cursor.fetchone()[0] or 0

            if total_hours == 0:
                print(_t("student_union.volunteer.no_completed_hours"))
                return

            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student_name = cursor.fetchone()

            print(f"\n{_t('student_union.volunteer.verification_header')}")
            print("=" * 40)
            print(f"{_t('student_union.volunteer.student_label')} {student_name[0]} {student_name[1]}")
            print(f"{_t('student_union.volunteer.student_id_label')} {student_id}")
            print(f"{_t('student_union.volunteer.total_verified_hours')} {total_hours:.1f}")
            print(f"{_t('student_union.volunteer.verification_date')} {datetime.now().strftime('%Y-%m-%d')}")
            print(_t("student_union.volunteer.issued_by"))
            print()
            print(_t("student_union.volunteer.verification_text1"))
            print(_t("student_union.volunteer.verification_text2"))

        elif choice == '4':
            # Set volunteer goals
            current_year = datetime.now().year

            try:
                goal_hours = float(input(f"{_t('student_union.volunteer.set_goal_prompt', year=current_year)} ").strip())
                if goal_hours <= 0:
                    print(_t("student_union.volunteer.goal_must_positive"))
                    return
            except ValueError:
                print(_t("student_union.volunteer.invalid_goal_format"))
                return

            # Get current year hours
            cursor.execute('''
            SELECT SUM(hours_completed) as current_hours
            FROM volunteer_signups
            WHERE student_id = ? AND strftime('%Y', completion_date) = ?
            ''', (student_id, str(current_year)))

            current_hours = cursor.fetchone()[0] or 0

            print(f"\n{_t('student_union.volunteer.goal_set', hours=goal_hours, year=current_year)}")
            print(_t("student_union.volunteer.current_progress", hours=f"{current_hours:.1f}", percent=f"{current_hours/goal_hours*100:.1f}"))
            print(_t("student_union.volunteer.remaining_hours", hours=f"{max(0, goal_hours - current_hours):.1f}"))

            if current_hours >= goal_hours:
                print(_t("student_union.volunteer.goal_achieved"))
            else:
                months_remaining = 12 - datetime.now().month + 1
                hours_per_month = (goal_hours - current_hours) / months_remaining
                print(_t("student_union.volunteer.suggested_pace", hours=f"{hours_per_month:.1f}"))

    except sqlite3.Error as e:
        print(f"{_t('student_union.volunteer.database_error')} {e}")
    except Exception as e:
        print(f"{_t('student_union.volunteer.error_occurred')} {e}")
