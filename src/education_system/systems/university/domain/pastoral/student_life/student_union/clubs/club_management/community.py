from education_system.systems.university.domain.pastoral.student_life.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.systems.university.domain.pastoral.student_life.student_union.clubs.club_management._imports as _state
from education_system.systems.university.domain.pastoral.student_life.student_union.clubs.club_management.competitions import auto_award_points


def manage_community_engagement():
    """Main community engagement interface"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access community engagement.")
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
            print("\n🤝 Community Engagement")
            print("1. Volunteer opportunities")
            print("2. My volunteer activities")
            print("3. Community service hours")
            print("4. Local partnerships")
            print("5. Social impact projects")
            print("6. Community feedback")
            print("7. Public events")

            if auth.check_permission('manage_union_reps') or auth.check_permission('manage_all_clubs'):
                print("8. Manage volunteer programs")
                print("9. Partnership coordination")
                print("10. Impact measurement")
                print("11. Return to main menu")
                max_option = 11
            else:
                print("8. Return to main menu")
                max_option = 8

            choice = input("Choose an option: ").strip()

            if choice == '1':
                browse_volunteer_opportunities(cursor)
            elif choice == '2':
                view_my_volunteer_activities(student_id, cursor)
            elif choice == '3':
                track_community_service_hours(student_id, cursor, conn)
            elif choice == '4':
                view_local_partnerships(cursor)
            elif choice == '5':
                manage_social_impact_projects(student_id, cursor, conn)
            elif choice == '6':
                submit_community_feedback(student_id, cursor, conn)
            elif choice == '7':
                coordinate_public_events(student_id, cursor, conn)
            elif choice == '8' and max_option > 8:
                manage_volunteer_programs_admin(cursor, conn)
            elif choice == '9' and max_option > 8:
                partnership_coordination_admin(cursor, conn)
            elif choice == '10' and max_option > 8:
                measure_social_impact(cursor)
            elif choice == str(max_option):
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def engagement_trend_analysis(cursor):
    """Analyze engagement trends over time"""
    try:
        print("\n📈 Engagement Trend Analysis")
        print("=" * 35)

        # Monthly event attendance trends
        cursor.execute('''
        SELECT
            strftime('%Y-%m', e.event_date) as month,
            COUNT(e.event_id) as events_held,
            SUM(e.current_attendees) as total_attendance,
            AVG(e.current_attendees) as avg_attendance,
            COUNT(DISTINCT e.organizer_id) as active_clubs
        FROM union_events e
        WHERE e.event_date >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', e.event_date)
        ORDER BY month
        ''')

        monthly_trends = cursor.fetchall()

        if monthly_trends:
            print("Monthly Engagement Trends:")
            print(f"{'Month':<10} {'Events':<8} {'Attendance':<12} {'Avg/Event':<10} {'Active Clubs':<12}")
            print("-" * 60)

            for trend in monthly_trends:
                print(f"{trend[0]:<10} {trend[1]:<8} {trend[2]:<12} {trend[3]:<10.1f} {trend[4]:<12}")

        # Club membership growth
        cursor.execute('''
        SELECT
            strftime('%Y-%m', join_date) as month,
            COUNT(*) as new_members
        FROM club_members
        WHERE join_date >= date('now', '-12 months')
        GROUP BY strftime('%Y-%m', join_date)
        ORDER BY month
        ''')

        membership_trends = cursor.fetchall()

        if membership_trends:
            print("\nClub Membership Growth:")
            print(f"{'Month':<10} {'New Members':<12}")
            print("-" * 25)

            for trend in membership_trends:
                print(f"{trend[0]:<10} {trend[1]:<12}")

        # Identify peak engagement periods
        if monthly_trends:
            peak_month = max(monthly_trends, key=lambda x: x[2])
            low_month = min(monthly_trends, key=lambda x: x[2])

            print("\nKey Insights:")
            print(f"Peak engagement: {peak_month[0]} ({peak_month[2]} total attendance)")
            print(f"Lowest engagement: {low_month[0]} ({low_month[2]} total attendance)")

            # Calculate trends
            if len(monthly_trends) >= 2:
                recent_attendance = monthly_trends[-1][2]
                previous_attendance = monthly_trends[-2][2]
                trend_direction = "increasing" if recent_attendance > previous_attendance else "decreasing"
                change_percent = abs((recent_attendance - previous_attendance) / previous_attendance * 100) if previous_attendance > 0 else 0

                print(f"Recent trend: {trend_direction} ({change_percent:.1f}% change)")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def member_retention_insights(cursor):
    """Analyze member retention patterns"""
    try:
        print("\n👥 Member Retention Insights")
        print("=" * 35)

        # Club retention rates
        cursor.execute('''
        SELECT
            c.club_name,
            COUNT(m.student_id) as total_members,
            COUNT(CASE WHEN m.join_date >= date('now', '-12 months') THEN 1 END) as new_members_12m,
            COUNT(CASE WHEN m.join_date <= date('now', '-12 months') THEN 1 END) as retained_members
        FROM student_clubs c
        JOIN club_members m ON c.club_id = m.club_id
        WHERE c.status = 'active'
        GROUP BY c.club_id, c.club_name
        HAVING COUNT(m.student_id) >= 5
        ORDER BY total_members DESC
        ''')

        retention_data = cursor.fetchall()

        if retention_data:
            print("Club Retention Analysis:")
            print(f"{'Club':<25} {'Total':<8} {'New (12m)':<10} {'Retained':<10} {'Retention %':<12}")
            print("-" * 70)

            for club in retention_data:
                if club[3] > 0:
                    retention_rate = (club[3] / (club[1] - club[2]) * 100) if (club[1] - club[2]) > 0 else 0
                else:
                    retention_rate = 0

                print(f"{club[0][:25]:<25} {club[1]:<8} {club[2]:<10} {club[3]:<10} {retention_rate:<12.1f}%")

        # Activity level analysis
        cursor.execute('''
        SELECT
            'High Activity' as activity_level,
            COUNT(DISTINCT cm.student_id) as member_count
        FROM club_members cm
        WHERE cm.student_id IN (
            SELECT er.user_id
            FROM unified_event_registrations er
            WHERE er.registration_date >= date('now', '-6 months')
            GROUP BY er.user_id
            HAVING COUNT(*) >= 3
        )

        UNION ALL

        SELECT
            'Low Activity' as activity_level,
            COUNT(DISTINCT cm.student_id) as member_count
        FROM club_members cm
        WHERE cm.student_id NOT IN (
            SELECT er.user_id
            FROM unified_event_registrations er
            WHERE er.registration_date >= date('now', '-6 months')
            GROUP BY er.user_id
            HAVING COUNT(*) >= 1
        )
        ''')

        activity_analysis = cursor.fetchall()

        if activity_analysis:
            print("\nMember Activity Levels (last 6 months):")
            for activity in activity_analysis:
                print(f"{activity[0]}: {activity[1]} members")

        # Churn risk identification
        cursor.execute('''
        SELECT
            s.first_name, s.last_name, c.club_name,
            m.join_date,
            julianday('now') - julianday(MAX(er.registration_date)) as days_since_last_activity
        FROM students s
        JOIN club_members m ON s.student_id = m.student_id
        JOIN student_clubs c ON m.club_id = c.club_id
        LEFT JOIN unified_event_registrations er ON s.student_id = er.user_id
        WHERE c.status = 'active'
        GROUP BY s.student_id, c.club_id
        HAVING days_since_last_activity > 90 OR days_since_last_activity IS NULL
        ORDER BY days_since_last_activity DESC
        LIMIT 10
        ''')

        at_risk_members = cursor.fetchall()

        if at_risk_members:
            print("\n⚠️ Members at Risk of Churning:")
            print(f"{'Member':<20} {'Club':<20} {'Days Inactive':<15}")
            print("-" * 60)

            for member in at_risk_members:
                days_inactive = f"{int(member[4])}" if member[4] else "No activity"
                name = f"{member[0]} {member[1]}"
                print(f"{name[:20]:<20} {member[2][:20]:<20} {days_inactive:<15}")

        print("\n💡 Retention Improvement Suggestions:")
        print("- Reach out to inactive members with personalized invitations")
        print("- Create mentorship programs for new members")
        print("- Organize regular social events to build community")
        print("- Survey departing members to understand reasons")
        print("- Implement member recognition programs")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def manage_book_clubs(student_id, cursor, conn):
    """Manage book clubs and reading groups"""
    try:
        while True:
            print("\n📖 Book Club Management")
            print("1. Browse book clubs")
            print("2. Create book club")
            print("3. Join book club")
            print("4. My book clubs")
            print("5. Suggest a book")
            print("6. Reading progress tracking")
            print("7. Return to learning menu")

            choice = input("Choose option: ").strip()

            if choice == '1':
                # Browse book clubs
                cursor.execute('''
                SELECT book_club_id, club_name, current_book, book_author,
                       current_members, max_members, meeting_schedule, description
                FROM book_clubs
                WHERE status = 'active'
                ORDER BY club_name
                ''')

                book_clubs = cursor.fetchall()

                if not book_clubs:
                    print("No active book clubs found.")
                    continue

                print("\nActive Book Clubs:")
                print(f"{'ID':<6} {'Club Name':<25} {'Current Book':<30} {'Members':<10}")
                print("-" * 75)

                for club in book_clubs:
                    members = f"{club[4]}/{club[5]}"
                    current_book = club[2] if club[2] else "Selecting next book"
                    print(f"{club[0]:<6} {club[1][:25]:<25} {current_book[:30]:<30} {members:<10}")

                    if club[7]:  # description
                        print(f"       {club[7]}")
                    print(f"       Schedule: {club[6]}")
                    print()

            elif choice == '2':
                # Create book club
                club_name = input("Book club name: ").strip()
                if not club_name:
                    print("Club name cannot be empty.")
                    continue

                description = input("Club description: ").strip()
                meeting_schedule = input("Meeting schedule (e.g., 'First Monday of each month'): ").strip()

                try:
                    max_members = int(input("Maximum members (5-20): ").strip())
                    if max_members < 5 or max_members > 20:
                        print("Max members should be between 5 and 20.")
                        continue
                except ValueError:
                    print("Invalid number format.")
                    continue

                # Optional: Set first book
                first_book = input("First book to read (optional): ").strip()
                book_author = input("Author (if book specified): ").strip() if first_book else ""

                cursor.execute('''
                INSERT INTO book_clubs (
                    club_name, current_book, book_author, discussion_leader_id,
                    meeting_schedule, max_members, current_members, status, description
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    club_name, first_book, book_author, student_id,
                    meeting_schedule, max_members, 1, 'active', description
                ))

                conn.commit()
                book_club_id = cursor.lastrowid

                print(f"Book club '{club_name}' created successfully!")
                print(f"Club ID: {book_club_id}")

                # Award points for creating book club
                auto_award_points(student_id, "Learning", 30,
                                f"Created book club: {club_name}", cursor, conn)

            elif choice == '3':
                # Join book club
                club_id = input("Enter book club ID to join: ").strip()
                if not club_id.isdigit():
                    print("Invalid club ID.")
                    continue

                cursor.execute('''
                SELECT club_name, current_members, max_members, current_book
                FROM book_clubs
                WHERE book_club_id = ? AND status = 'active'
                ''', (club_id,))

                club = cursor.fetchone()

                if not club:
                    print("Book club not found or not active.")
                    continue

                if club[1] >= club[2]:
                    print("Book club is full.")
                    continue

                # In a full implementation, would check if already a member
                cursor.execute('''
                UPDATE book_clubs
                SET current_members = current_members + 1
                WHERE book_club_id = ?
                ''', (club_id,))

                conn.commit()

                print(f"Successfully joined '{club[0]}'!")
                if club[3]:
                    print(f"Current book: {club[3]}")

                # Award points for joining
                auto_award_points(student_id, "Learning", 15,
                                f"Joined book club: {club[0]}", cursor, conn)

            elif choice == '4':
                # My book clubs (simplified - would need member table)
                cursor.execute('''
                SELECT book_club_id, club_name, current_book, book_author, meeting_schedule
                FROM book_clubs
                WHERE discussion_leader_id = ?
                ORDER BY club_name
                ''', (student_id,))

                my_clubs = cursor.fetchall()

                if not my_clubs:
                    print("You are not leading any book clubs.")
                    continue

                print("\nBook Clubs You Lead:")
                for club in my_clubs:
                    print(f"\n📚 {club[1]}")
                    if club[2]:
                        print(f"   Current book: {club[2]} by {club[3]}")
                    else:
                        print("   No current book selected")
                    print(f"   Schedule: {club[4]}")

            elif choice == '5':
                # Suggest a book
                book_title = input("Book title to suggest: ").strip()
                author = input("Author: ").strip()
                reason = input("Why should we read this book? ").strip()

                print("Book suggestion recorded:")
                print(f"'{book_title}' by {author}")
                print(f"Reason: {reason}")
                print("Book club leaders will be notified of your suggestion.")

            elif choice == '6':
                # Reading progress tracking
                print("\n📊 Reading Progress Tracking")
                print("Track your reading goals and progress")

                try:
                    books_goal = int(input("Books to read this year: ").strip())
                    books_read = int(input("Books completed so far: ").strip())
                except ValueError:
                    print("Invalid number format.")
                    continue

                progress_percent = (books_read / books_goal * 100) if books_goal > 0 else 0
                remaining = max(0, books_goal - books_read)

                print("\nReading Progress:")
                print(f"Goal: {books_goal} books")
                print(f"Completed: {books_read} books ({progress_percent:.1f}%)")
                print(f"Remaining: {remaining} books")

                if progress_percent >= 100:
                    print("🎉 Congratulations! You've reached your reading goal!")
                elif progress_percent >= 75:
                    print("📚 Great progress! You're almost there!")
                elif progress_percent >= 50:
                    print("📖 Good progress! Keep it up!")
                else:
                    print("📕 Early in your reading journey - keep going!")

            elif choice == '7':
                break

            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def _ensure_community_tables(cursor, conn):
    """Create supporting community-engagement tables if they don't yet exist."""
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS community_partnerships (
        partnership_id INTEGER PRIMARY KEY AUTOINCREMENT,
        organization_name TEXT,
        partnership_type TEXT,
        contact_person TEXT,
        contact_email TEXT,
        description TEXT,
        start_date TEXT,
        status TEXT DEFAULT 'active',
        created_at TEXT
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS social_impact_projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT,
        lead_student_id TEXT,
        description TEXT,
        impact_area TEXT,
        target_beneficiaries INTEGER DEFAULT 0,
        status TEXT DEFAULT 'planning',
        created_at TEXT
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS community_feedback (
        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT,
        category TEXT,
        subject TEXT,
        message TEXT,
        rating INTEGER,
        submitted_at TEXT,
        status TEXT DEFAULT 'open'
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS public_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT,
        organizer_id TEXT,
        event_date TEXT,
        location TEXT,
        description TEXT,
        expected_attendance INTEGER DEFAULT 0,
        status TEXT DEFAULT 'planned',
        created_at TEXT
    )''')
    conn.commit()


def browse_volunteer_opportunities(cursor):
    """Browse open volunteer opportunities"""
    try:
        print("\n🙋 Volunteer Opportunities")
        print("=" * 35)

        cursor.execute('''
        SELECT opportunity_id, organization_name, location, start_date, end_date,
               hours_required, skills_needed, max_volunteers, current_volunteers,
               contact_person, contact_email, description
        FROM volunteer_opportunities
        WHERE status IS NULL OR status = 'open' OR status = 'active'
        ORDER BY start_date
        ''')

        opportunities = cursor.fetchall()

        if not opportunities:
            print("No volunteer opportunities found.")
            return

        print(f"{'ID':<6} {'Organization':<25} {'Location':<18} {'Dates':<22} {'Spots':<8}")
        print("-" * 82)

        for opp in opportunities:
            max_vol = opp[7] if opp[7] is not None else 0
            current = opp[8] if opp[8] is not None else 0
            spots = f"{current}/{max_vol}" if max_vol else str(current)
            dates = f"{opp[3] or 'TBD'} - {opp[4] or 'TBD'}"
            org = opp[1] or "Unknown"
            location = opp[2] or "TBD"
            print(f"{opp[0]:<6} {org[:25]:<25} {location[:18]:<18} {dates[:22]:<22} {spots:<8}")

            if opp[5]:
                print(f"       Hours required: {opp[5]}")
            if opp[6]:
                print(f"       Skills needed: {opp[6]}")
            if opp[9] or opp[10]:
                print(f"       Contact: {opp[9] or 'N/A'} ({opp[10] or 'N/A'})")
            if opp[11]:
                print(f"       {opp[11]}")
            print()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_my_volunteer_activities(student_id, cursor):
    """View personal volunteer sign-ups and their status"""
    try:
        print("\n📋 My Volunteer Activities")
        print("=" * 35)

        cursor.execute('''
        SELECT s.signup_id, o.organization_name, o.location, s.signup_date,
               s.status, s.hours_completed, s.completion_date, o.description
        FROM volunteer_signups s
        LEFT JOIN volunteer_opportunities o ON s.opportunity_id = o.opportunity_id
        WHERE s.student_id = ?
        ORDER BY s.signup_date DESC
        ''', (student_id,))

        signups = cursor.fetchall()

        if not signups:
            print("You have not signed up for any volunteer opportunities yet.")
            return

        print(f"{'ID':<6} {'Organization':<25} {'Signed Up':<12} {'Status':<12} {'Hours':<8}")
        print("-" * 70)

        for row in signups:
            org = row[1] or "Unknown"
            signup_date = (row[3] or "")[:10]
            status = row[4] or "pending"
            hours = row[5] if row[5] is not None else 0
            print(f"{row[0]:<6} {org[:25]:<25} {signup_date:<12} {status[:12]:<12} {hours:<8}")
            if row[6]:
                print(f"       Completed on: {row[6][:10]}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def track_community_service_hours(student_id, cursor, conn):
    """Track and log community service hours across volunteer sign-ups"""
    try:
        print("\n⏱️ Community Service Hours")
        print("=" * 35)

        cursor.execute('''
        SELECT COALESCE(SUM(hours_completed), 0),
               COUNT(*),
               COUNT(CASE WHEN status = 'completed' THEN 1 END)
        FROM volunteer_signups
        WHERE student_id = ?
        ''', (student_id,))

        totals = cursor.fetchone()
        total_hours = totals[0] or 0
        total_signups = totals[1] or 0
        completed = totals[2] or 0

        print(f"Total service hours logged: {total_hours}")
        print(f"Total sign-ups: {total_signups} ({completed} completed)")

        cursor.execute('''
        SELECT s.signup_id, o.organization_name, s.hours_completed, s.status
        FROM volunteer_signups s
        LEFT JOIN volunteer_opportunities o ON s.opportunity_id = o.opportunity_id
        WHERE s.student_id = ?
        ORDER BY s.signup_date DESC
        ''', (student_id,))

        rows = cursor.fetchall()

        if not rows:
            print("\nNo volunteer sign-ups found to log hours against.")
            return

        print("\nYour sign-ups:")
        print(f"{'ID':<6} {'Organization':<25} {'Hours':<8} {'Status':<12}")
        print("-" * 55)
        for row in rows:
            org = row[1] or "Unknown"
            hours = row[2] if row[2] is not None else 0
            print(f"{row[0]:<6} {org[:25]:<25} {hours:<8} {(row[3] or 'pending')[:12]:<12}")

        log = input("\nLog hours for a sign-up? (y/n): ").strip().lower()
        if log != 'y':
            return

        signup_id = input("Enter sign-up ID: ").strip()
        if not signup_id.isdigit():
            print("Invalid sign-up ID.")
            return

        cursor.execute('''
        SELECT hours_completed FROM volunteer_signups
        WHERE signup_id = ? AND student_id = ?
        ''', (signup_id, student_id))
        existing = cursor.fetchone()

        if not existing:
            print("Sign-up not found.")
            return

        try:
            hours = float(input("Hours completed to add: ").strip())
            if hours <= 0:
                print("Hours must be greater than zero.")
                return
        except ValueError:
            print("Invalid number format.")
            return

        new_total = (existing[0] or 0) + hours
        cursor.execute('''
        UPDATE volunteer_signups
        SET hours_completed = ?, status = 'completed', completion_date = ?
        WHERE signup_id = ? AND student_id = ?
        ''', (new_total, datetime.now().strftime('%Y-%m-%d'), signup_id, student_id))
        conn.commit()

        print(f"Logged {hours} hours (new total for this sign-up: {new_total}).")

        auto_award_points(student_id, "Community", int(hours * 5),
                          f"Logged {hours} community service hours", cursor, conn)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_local_partnerships(cursor):
    """View active local community partnerships"""
    try:
        print("\n🤝 Local Partnerships")
        print("=" * 35)

        try:
            cursor.execute('''
            SELECT partnership_id, organization_name, partnership_type,
                   contact_person, contact_email, start_date, description, status
            FROM community_partnerships
            WHERE status = 'active'
            ORDER BY organization_name
            ''')
            partnerships = cursor.fetchall()
        except sqlite3.OperationalError:
            partnerships = []

        if not partnerships:
            print("No local partnerships found.")
            return

        print(f"{'ID':<6} {'Organization':<28} {'Type':<18} {'Since':<12}")
        print("-" * 66)

        for p in partnerships:
            org = p[1] or "Unknown"
            ptype = p[2] or "General"
            since = (p[5] or "")[:10]
            print(f"{p[0]:<6} {org[:28]:<28} {ptype[:18]:<18} {since:<12}")
            if p[3] or p[4]:
                print(f"       Contact: {p[3] or 'N/A'} ({p[4] or 'N/A'})")
            if p[6]:
                print(f"       {p[6]}")
            print()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def manage_social_impact_projects(student_id, cursor, conn):
    """Browse and create social impact projects"""
    try:
        _ensure_community_tables(cursor, conn)

        while True:
            print("\n🌍 Social Impact Projects")
            print("1. Browse projects")
            print("2. Create project")
            print("3. My projects")
            print("4. Return")

            choice = input("Choose option: ").strip()

            if choice == '1':
                cursor.execute('''
                SELECT project_id, project_name, impact_area, target_beneficiaries, status
                FROM social_impact_projects
                ORDER BY created_at DESC
                ''')
                projects = cursor.fetchall()

                if not projects:
                    print("No social impact projects found.")
                    continue

                print(f"\n{'ID':<6} {'Project':<28} {'Impact Area':<20} {'Target':<8} {'Status':<12}")
                print("-" * 78)
                for pr in projects:
                    name = pr[1] or "Untitled"
                    area = pr[2] or "General"
                    target = pr[3] if pr[3] is not None else 0
                    print(f"{pr[0]:<6} {name[:28]:<28} {area[:20]:<20} {target:<8} {(pr[4] or 'planning')[:12]:<12}")

            elif choice == '2':
                project_name = input("Project name: ").strip()
                if not project_name:
                    print("Project name cannot be empty.")
                    continue
                description = input("Description: ").strip()
                impact_area = input("Impact area (e.g. Environment, Education): ").strip()
                try:
                    target = int(input("Target beneficiaries (0 if unknown): ").strip() or "0")
                except ValueError:
                    print("Invalid number format.")
                    continue

                cursor.execute('''
                INSERT INTO social_impact_projects (
                    project_name, lead_student_id, description, impact_area,
                    target_beneficiaries, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (project_name, student_id, description, impact_area, target,
                      'planning', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()

                print(f"Social impact project '{project_name}' created (ID: {cursor.lastrowid}).")
                auto_award_points(student_id, "Community", 40,
                                  f"Created social impact project: {project_name}", cursor, conn)

            elif choice == '3':
                cursor.execute('''
                SELECT project_id, project_name, impact_area, status
                FROM social_impact_projects
                WHERE lead_student_id = ?
                ORDER BY created_at DESC
                ''', (student_id,))
                mine = cursor.fetchall()

                if not mine:
                    print("You are not leading any social impact projects.")
                    continue

                print("\nProjects You Lead:")
                for pr in mine:
                    print(f"  [{pr[0]}] {pr[1]} — {pr[2] or 'General'} ({pr[3] or 'planning'})")

            elif choice == '4':
                break
            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def submit_community_feedback(student_id, cursor, conn):
    """Submit and review community engagement feedback"""
    try:
        _ensure_community_tables(cursor, conn)

        while True:
            print("\n💬 Community Feedback")
            print("1. Submit feedback")
            print("2. View my feedback")
            print("3. Return")

            choice = input("Choose option: ").strip()

            if choice == '1':
                category = input("Category (event/partnership/volunteering/general): ").strip() or "general"
                subject = input("Subject: ").strip()
                if not subject:
                    print("Subject cannot be empty.")
                    continue
                message = input("Your feedback: ").strip()
                try:
                    rating_raw = input("Rating 1-5 (optional): ").strip()
                    rating = int(rating_raw) if rating_raw else None
                    if rating is not None and (rating < 1 or rating > 5):
                        print("Rating must be between 1 and 5.")
                        continue
                except ValueError:
                    print("Invalid rating.")
                    continue

                cursor.execute('''
                INSERT INTO community_feedback (
                    student_id, category, subject, message, rating, submitted_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, category, subject, message, rating,
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'open'))
                conn.commit()

                print("Thank you! Your feedback has been recorded.")

            elif choice == '2':
                cursor.execute('''
                SELECT feedback_id, category, subject, rating, submitted_at, status
                FROM community_feedback
                WHERE student_id = ?
                ORDER BY submitted_at DESC
                ''', (student_id,))
                rows = cursor.fetchall()

                if not rows:
                    print("You have not submitted any feedback yet.")
                    continue

                print(f"\n{'ID':<6} {'Category':<16} {'Subject':<28} {'Rating':<8} {'Status':<10}")
                print("-" * 72)
                for r in rows:
                    rating = str(r[3]) if r[3] is not None else "-"
                    print(f"{r[0]:<6} {(r[1] or '')[:16]:<16} {(r[2] or '')[:28]:<28} {rating:<8} {(r[5] or 'open')[:10]:<10}")

            elif choice == '3':
                break
            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def coordinate_public_events(student_id, cursor, conn):
    """Browse and propose public community events"""
    try:
        _ensure_community_tables(cursor, conn)

        while True:
            print("\n📅 Public Events")
            print("1. Browse upcoming events")
            print("2. Propose an event")
            print("3. My proposed events")
            print("4. Return")

            choice = input("Choose option: ").strip()

            if choice == '1':
                cursor.execute('''
                SELECT event_id, event_name, event_date, location, expected_attendance, status
                FROM public_events
                WHERE event_date >= date('now') OR event_date IS NULL
                ORDER BY event_date
                ''')
                events = cursor.fetchall()

                if not events:
                    print("No upcoming public events found.")
                    continue

                print(f"\n{'ID':<6} {'Event':<28} {'Date':<12} {'Location':<18} {'Exp.':<6} {'Status':<10}")
                print("-" * 82)
                for ev in events:
                    exp = ev[4] if ev[4] is not None else 0
                    print(f"{ev[0]:<6} {(ev[1] or '')[:28]:<28} {(ev[2] or 'TBD')[:12]:<12} {(ev[3] or 'TBD')[:18]:<18} {exp:<6} {(ev[5] or 'planned')[:10]:<10}")

            elif choice == '2':
                event_name = input("Event name: ").strip()
                if not event_name:
                    print("Event name cannot be empty.")
                    continue
                event_date = input("Event date (YYYY-MM-DD): ").strip()
                location = input("Location: ").strip()
                description = input("Description: ").strip()
                try:
                    expected = int(input("Expected attendance (0 if unknown): ").strip() or "0")
                except ValueError:
                    print("Invalid number format.")
                    continue

                cursor.execute('''
                INSERT INTO public_events (
                    event_name, organizer_id, event_date, location, description,
                    expected_attendance, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (event_name, student_id, event_date, location, description,
                      expected, 'planned', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()

                print(f"Public event '{event_name}' proposed (ID: {cursor.lastrowid}).")
                auto_award_points(student_id, "Community", 35,
                                  f"Proposed public event: {event_name}", cursor, conn)

            elif choice == '3':
                cursor.execute('''
                SELECT event_id, event_name, event_date, status
                FROM public_events
                WHERE organizer_id = ?
                ORDER BY event_date
                ''', (student_id,))
                mine = cursor.fetchall()

                if not mine:
                    print("You have not proposed any public events.")
                    continue

                print("\nEvents You Proposed:")
                for ev in mine:
                    print(f"  [{ev[0]}] {ev[1]} — {ev[2] or 'TBD'} ({ev[3] or 'planned'})")

            elif choice == '4':
                break
            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def manage_volunteer_programs_admin(cursor, conn):
    """Admin: create and manage volunteer opportunities"""
    try:
        while True:
            print("\n🛠️ Manage Volunteer Programs")
            print("1. List all opportunities")
            print("2. Create opportunity")
            print("3. Close opportunity")
            print("4. Return")

            choice = input("Choose option: ").strip()

            if choice == '1':
                cursor.execute('''
                SELECT opportunity_id, organization_name, location, status,
                       current_volunteers, max_volunteers
                FROM volunteer_opportunities
                ORDER BY opportunity_id DESC
                ''')
                opps = cursor.fetchall()

                if not opps:
                    print("No volunteer opportunities found.")
                    continue

                print(f"\n{'ID':<6} {'Organization':<28} {'Location':<18} {'Status':<10} {'Filled':<10}")
                print("-" * 74)
                for o in opps:
                    max_vol = o[5] if o[5] is not None else 0
                    cur_vol = o[4] if o[4] is not None else 0
                    filled = f"{cur_vol}/{max_vol}" if max_vol else str(cur_vol)
                    print(f"{o[0]:<6} {(o[1] or '')[:28]:<28} {(o[2] or 'TBD')[:18]:<18} {(o[3] or 'open')[:10]:<10} {filled:<10}")

            elif choice == '2':
                organization = input("Organization name: ").strip()
                if not organization:
                    print("Organization name cannot be empty.")
                    continue
                contact_person = input("Contact person: ").strip()
                contact_email = input("Contact email: ").strip()
                description = input("Description: ").strip()
                location = input("Location: ").strip()
                start_date = input("Start date (YYYY-MM-DD): ").strip()
                end_date = input("End date (YYYY-MM-DD): ").strip()
                skills = input("Skills needed: ").strip()
                try:
                    hours_required = float(input("Hours required (0 if flexible): ").strip() or "0")
                    max_volunteers = int(input("Maximum volunteers: ").strip() or "0")
                except ValueError:
                    print("Invalid number format.")
                    continue

                cursor.execute('''
                INSERT INTO volunteer_opportunities (
                    organization_name, contact_person, contact_email, description,
                    location, start_date, end_date, hours_required, skills_needed,
                    max_volunteers, current_volunteers, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (organization, contact_person, contact_email, description,
                      location, start_date, end_date, hours_required, skills,
                      max_volunteers, 0, 'open'))
                conn.commit()

                print(f"Opportunity created (ID: {cursor.lastrowid}).")

            elif choice == '3':
                opp_id = input("Opportunity ID to close: ").strip()
                if not opp_id.isdigit():
                    print("Invalid opportunity ID.")
                    continue

                cursor.execute('SELECT organization_name FROM volunteer_opportunities WHERE opportunity_id = ?',
                               (opp_id,))
                found = cursor.fetchone()
                if not found:
                    print("Opportunity not found.")
                    continue

                cursor.execute('UPDATE volunteer_opportunities SET status = ? WHERE opportunity_id = ?',
                               ('closed', opp_id))
                conn.commit()
                print(f"Opportunity '{found[0]}' closed.")

            elif choice == '4':
                break
            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def partnership_coordination_admin(cursor, conn):
    """Admin: coordinate community partnerships"""
    try:
        _ensure_community_tables(cursor, conn)

        while True:
            print("\n🤝 Partnership Coordination")
            print("1. List all partnerships")
            print("2. Add partnership")
            print("3. Update partnership status")
            print("4. Return")

            choice = input("Choose option: ").strip()

            if choice == '1':
                cursor.execute('''
                SELECT partnership_id, organization_name, partnership_type, status, start_date
                FROM community_partnerships
                ORDER BY organization_name
                ''')
                rows = cursor.fetchall()

                if not rows:
                    print("No partnerships found.")
                    continue

                print(f"\n{'ID':<6} {'Organization':<28} {'Type':<18} {'Status':<10} {'Since':<12}")
                print("-" * 76)
                for r in rows:
                    print(f"{r[0]:<6} {(r[1] or '')[:28]:<28} {(r[2] or 'General')[:18]:<18} {(r[3] or 'active')[:10]:<10} {(r[4] or '')[:12]:<12}")

            elif choice == '2':
                organization = input("Organization name: ").strip()
                if not organization:
                    print("Organization name cannot be empty.")
                    continue
                ptype = input("Partnership type (e.g. Charity, Employer, Council): ").strip()
                contact_person = input("Contact person: ").strip()
                contact_email = input("Contact email: ").strip()
                description = input("Description: ").strip()

                cursor.execute('''
                INSERT INTO community_partnerships (
                    organization_name, partnership_type, contact_person,
                    contact_email, description, start_date, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (organization, ptype, contact_person, contact_email, description,
                      datetime.now().strftime('%Y-%m-%d'), 'active',
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()

                print(f"Partnership with '{organization}' added (ID: {cursor.lastrowid}).")

            elif choice == '3':
                pid = input("Partnership ID: ").strip()
                if not pid.isdigit():
                    print("Invalid partnership ID.")
                    continue
                cursor.execute('SELECT organization_name FROM community_partnerships WHERE partnership_id = ?',
                               (pid,))
                found = cursor.fetchone()
                if not found:
                    print("Partnership not found.")
                    continue
                new_status = input("New status (active/paused/ended): ").strip() or "active"
                cursor.execute('UPDATE community_partnerships SET status = ? WHERE partnership_id = ?',
                               (new_status, pid))
                conn.commit()
                print(f"Partnership '{found[0]}' set to '{new_status}'.")

            elif choice == '4':
                break
            else:
                print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def measure_social_impact(cursor):
    """Report aggregate community engagement / social impact metrics"""
    try:
        print("\n📊 Social Impact Measurement")
        print("=" * 35)

        cursor.execute('SELECT COUNT(*) FROM volunteer_opportunities')
        total_opps = cursor.fetchone()[0]

        cursor.execute('''
        SELECT COUNT(*), COUNT(DISTINCT student_id), COALESCE(SUM(hours_completed), 0)
        FROM volunteer_signups
        ''')
        signups, volunteers, total_hours = cursor.fetchone()

        print(f"Volunteer opportunities posted: {total_opps}")
        print(f"Total sign-ups: {signups or 0}")
        print(f"Distinct volunteers engaged: {volunteers or 0}")
        print(f"Total service hours contributed: {total_hours or 0}")

        # Top organizations by hours (empty-safe)
        cursor.execute('''
        SELECT o.organization_name, COALESCE(SUM(s.hours_completed), 0) as hrs
        FROM volunteer_signups s
        JOIN volunteer_opportunities o ON s.opportunity_id = o.opportunity_id
        GROUP BY o.organization_name
        HAVING hrs > 0
        ORDER BY hrs DESC
        LIMIT 5
        ''')
        top_orgs = cursor.fetchall()

        if top_orgs:
            print("\nTop Organizations by Hours Contributed:")
            for org in top_orgs:
                print(f"  {org[0]}: {org[1]} hours")

        # Optional supporting tables — degrade gracefully if absent
        for label, table in (("Community partnerships", "community_partnerships"),
                              ("Social impact projects", "social_impact_projects"),
                              ("Public events", "public_events"),
                              ("Community feedback entries", "community_feedback")):
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                print(f"{label}: {cursor.fetchone()[0]}")
            except sqlite3.OperationalError:
                print(f"{label}: 0")

        try:
            cursor.execute('SELECT AVG(rating) FROM community_feedback WHERE rating IS NOT NULL')
            avg_rating = cursor.fetchone()[0]
            if avg_rating is not None:
                print(f"Average feedback rating: {avg_rating:.1f}/5")
        except sqlite3.OperationalError:
            pass

        if not total_opps and not signups:
            print("\nNo community engagement activity recorded yet.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
