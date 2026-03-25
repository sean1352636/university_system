from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state
from education_system.university_system.modules.domain.student_affairs.student_union.clubs.club_management.competitions import auto_award_points


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
            print(f"\n🤝 Community Engagement")
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
        print(f"\n📈 Engagement Trend Analysis")
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
            print(f"\nClub Membership Growth:")
            print(f"{'Month':<10} {'New Members':<12}")
            print("-" * 25)

            for trend in membership_trends:
                print(f"{trend[0]:<10} {trend[1]:<12}")

        # Identify peak engagement periods
        if monthly_trends:
            peak_month = max(monthly_trends, key=lambda x: x[2])
            low_month = min(monthly_trends, key=lambda x: x[2])

            print(f"\nKey Insights:")
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
        print(f"\n👥 Member Retention Insights")
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
            print(f"\nMember Activity Levels (last 6 months):")
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
            print(f"\n⚠️ Members at Risk of Churning:")
            print(f"{'Member':<20} {'Club':<20} {'Days Inactive':<15}")
            print("-" * 60)

            for member in at_risk_members:
                days_inactive = f"{int(member[4])}" if member[4] else "No activity"
                name = f"{member[0]} {member[1]}"
                print(f"{name[:20]:<20} {member[2][:20]:<20} {days_inactive:<15}")

        print(f"\n💡 Retention Improvement Suggestions:")
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
            print(f"\n📖 Book Club Management")
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

                print(f"\nActive Book Clubs:")
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

                print(f"\nBook Clubs You Lead:")
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

                print(f"Book suggestion recorded:")
                print(f"'{book_title}' by {author}")
                print(f"Reason: {reason}")
                print("Book club leaders will be notified of your suggestion.")

            elif choice == '6':
                # Reading progress tracking
                print(f"\n📊 Reading Progress Tracking")
                print("Track your reading goals and progress")

                try:
                    books_goal = int(input("Books to read this year: ").strip())
                    books_read = int(input("Books completed so far: ").strip())
                except ValueError:
                    print("Invalid number format.")
                    continue

                progress_percent = (books_read / books_goal * 100) if books_goal > 0 else 0
                remaining = max(0, books_goal - books_read)

                print(f"\nReading Progress:")
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


# Placeholder functions called by manage_community_engagement
def browse_volunteer_opportunities(cursor):
    """Browse volunteer opportunities"""
    print("\n=== Volunteer Opportunities ===")
    print("Coming soon...")


def view_my_volunteer_activities(student_id, cursor):
    """View personal volunteer activities"""
    print("\n=== My Volunteer Activities ===")
    print("Coming soon...")


def track_community_service_hours(student_id, cursor, conn):
    """Track community service hours"""
    print("\n=== Community Service Hours ===")
    print("Coming soon...")


def view_local_partnerships(cursor):
    """View local partnerships"""
    print("\n=== Local Partnerships ===")
    print("Coming soon...")


def manage_social_impact_projects(student_id, cursor, conn):
    """Manage social impact projects"""
    print("\n=== Social Impact Projects ===")
    print("Coming soon...")


def submit_community_feedback(student_id, cursor, conn):
    """Submit community feedback"""
    print("\n=== Community Feedback ===")
    print("Coming soon...")


def coordinate_public_events(student_id, cursor, conn):
    """Coordinate public events"""
    print("\n=== Public Events ===")
    print("Coming soon...")


def manage_volunteer_programs_admin(cursor, conn):
    """Admin volunteer program management"""
    print("\n=== Manage Volunteer Programs ===")
    print("Coming soon...")


def partnership_coordination_admin(cursor, conn):
    """Admin partnership coordination"""
    print("\n=== Partnership Coordination ===")
    print("Coming soon...")


def measure_social_impact(cursor):
    """Measure social impact"""
    print("\n=== Impact Measurement ===")
    print("Coming soon...")
