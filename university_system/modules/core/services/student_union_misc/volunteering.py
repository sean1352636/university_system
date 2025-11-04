from __future__ import annotations

from datetime import datetime
from university_system.infrastructure.database.db import sqlite3, get_connection
from university_system.modules.core.services.student_union_misc import context as ctx
from university_system.modules.core.services.student_union_misc.union_context import auto_award_points

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
            print("No volunteer opportunities currently available.")
            return

        print(f"\n🌟 Available Volunteer Opportunities")
        print("=" * 45)

        for opp in opportunities:
            print(f"\nID: {opp[0]}")
            print(f"Organization: {opp[1]}")
            print(f"Description: {opp[2]}")
            print(f"Location: {opp[3]}")
            print(f"Period: {opp[4]} to {opp[5]}")
            print(f"Time commitment: {opp[6]} hours")
            if opp[7]:
                print(f"Skills needed: {opp[7]}")
            print(f"Volunteers: {opp[9]}/{opp[8]}")
            print("-" * 40)

        # Option to sign up
        signup_id = input("\nEnter opportunity ID to sign up (or press Enter to continue): ").strip()
        if signup_id.isdigit():
            signup_for_volunteer_opportunity(int(signup_id), cursor)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

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
            print("Opportunity not found or not available.")
            return

        if opp[3] >= opp[2]:
            print("This opportunity is full.")
            return

        # Check if already signed up
        cursor.execute('''
        SELECT COUNT(*) FROM volunteer_signups
        WHERE opportunity_id = ? AND student_id = ?
        ''', (opportunity_id, student_id))

        if cursor.fetchone()[0] > 0:
            print("You are already signed up for this opportunity.")
            return

        print(f"Signing up for: {opp[0]}")
        print(f"Activity: {opp[1]}")

        confirm = input("Confirm signup? (y/n): ").strip().lower()
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

            print("Successfully signed up for volunteer opportunity!")
            print("You will receive further details via email.")

            # Award points for volunteering commitment
            auto_award_points(student_id, "Community Service", 20, 
                            f"Signed up for volunteer opportunity: {opp[0]}", cursor, None)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

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
            print("You have no volunteer activities.")
            return

        print(f"\n🤝 Your Volunteer Activities")
        print("=" * 35)
        print(f"{'Organization':<25} {'Period':<20} {'Hours':<8} {'Status':<12}")
        print("-" * 70)

        total_hours = 0
        for activity in activities:
            period = f"{activity[3]} to {activity[4]}"
            hours = activity[5] if activity[5] else 0
            total_hours += hours

            print(f"{activity[0][:25]:<25} {period[:20]:<20} {hours:<8.1f} {activity[6]:<12}")

        print("-" * 70)
        print(f"{'TOTAL VOLUNTEER HOURS:':<53} {total_hours:<8.1f}")

        # Show impact summary
        completed_activities = len([a for a in activities if a[6] == 'completed'])
        active_activities = len([a for a in activities if a[6] == 'signed_up'])

        print(f"\nVolunteer Summary:")
        print(f"Completed activities: {completed_activities}")
        print(f"Active commitments: {active_activities}")
        print(f"Total volunteer hours: {total_hours:.1f}")

        # Calculate volunteer level
        if total_hours >= 100:
            level = "🏆 Community Champion"
        elif total_hours >= 50:
            level = "🥇 Dedicated Volunteer"
        elif total_hours >= 20:
            level = "🥈 Active Volunteer"
        elif total_hours >= 5:
            level = "🥉 Community Helper"
        else:
            level = "🌱 Getting Started"

        print(f"Volunteer level: {level}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

def track_community_service_hours(student_id, cursor, conn):
    """Track and log community service hours"""
    try:
        print(f"\n⏱️ Community Service Hour Tracking")
        print("=" * 40)

        print("1. Log completed volunteer hours")
        print("2. View hour summary")
        print("3. Generate service verification")
        print("4. Set volunteer goals")

        choice = input("Choose option: ").strip()

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
                print("No active volunteer commitments to log hours for.")
                return

            print("Active volunteer opportunities:")
            for i, opp in enumerate(active_opportunities):
                print(f"{i+1}. {opp[1]} - {opp[2]}")

            opp_choice = input("Select opportunity to log hours (enter number): ").strip()
            if not opp_choice.isdigit() or int(opp_choice) < 1 or int(opp_choice) > len(active_opportunities):
                print("Invalid selection.")
                return

            selected_opp = active_opportunities[int(opp_choice)-1]
            opportunity_id = selected_opp[0]

            try:
                hours = float(input("Hours completed: ").strip())
                if hours <= 0:
                    print("Hours must be positive.")
                    return
            except ValueError:
                print("Invalid hours format.")
                return

            completion_date = input("Completion date (YYYY-MM-DD) or leave blank for today: ").strip()
            if not completion_date:
                completion_date = datetime.now().strftime('%Y-%m-%d')

            feedback = input("Brief description of activities: ").strip()

            # Update signup record
            cursor.execute('''
            UPDATE volunteer_signups 
            SET hours_completed = COALESCE(hours_completed, 0) + ?,
                completion_date = ?, feedback = ?, status = 'completed'
            WHERE opportunity_id = ? AND student_id = ?
            ''', (hours, completion_date, feedback, opportunity_id, student_id))

            conn.commit()

            print(f"Logged {hours} volunteer hours successfully!")

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

            print(f"\nVolunteer Hour Summary:")
            print(f"Total hours: {summary[0] or 0:.1f}")
            print(f"Activities participated: {summary[1] or 0}")
            print(f"Completed activities: {summary[2] or 0}")

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
                print(f"\nMonthly Breakdown:")
                print(f"{'Month':<10} {'Hours':<8}")
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
                print("No completed volunteer hours to verify.")
                return

            cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
            student_name = cursor.fetchone()

            print(f"\n📜 Community Service Verification")
            print("=" * 40)
            print(f"Student: {student_name[0]} {student_name[1]}")
            print(f"Student ID: {student_id}")
            print(f"Total verified volunteer hours: {total_hours:.1f}")
            print(f"Verification date: {datetime.now().strftime('%Y-%m-%d')}")
            print(f"Issued by: Student Union Community Engagement Office")
            print()
            print("This document verifies the above volunteer service hours")
            print("completed through official university programs.")

        elif choice == '4':
            # Set volunteer goals
            current_year = datetime.now().year

            try:
                goal_hours = float(input(f"Set volunteer hour goal for {current_year}: ").strip())
                if goal_hours <= 0:
                    print("Goal must be positive.")
                    return
            except ValueError:
                print("Invalid goal format.")
                return

            # Get current year hours
            cursor.execute('''
            SELECT SUM(hours_completed) as current_hours
            FROM volunteer_signups
            WHERE student_id = ? AND strftime('%Y', completion_date) = ?
            ''', (student_id, str(current_year)))

            current_hours = cursor.fetchone()[0] or 0

            print(f"\nVolunteer Goal Set: {goal_hours} hours for {current_year}")
            print(f"Current progress: {current_hours:.1f} hours ({current_hours/goal_hours*100:.1f}%)")
            print(f"Remaining: {max(0, goal_hours - current_hours):.1f} hours")

            if current_hours >= goal_hours:
                print("🎉 Congratulations! You've already achieved your goal!")
            else:
                months_remaining = 12 - datetime.now().month + 1
                hours_per_month = (goal_hours - current_hours) / months_remaining
                print(f"Suggested pace: {hours_per_month:.1f} hours per month")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
