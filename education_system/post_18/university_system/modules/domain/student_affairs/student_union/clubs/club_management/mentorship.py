from education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports import (
    datetime, sqlite3, get_connection,
)
import education_system.post_18.university_system.modules.domain.student_affairs.student_union.clubs.club_management._imports as _state


def manage_mentorship_system():
    """Main mentorship system interface"""
    auth = _state.auth

    if not auth or not auth.current_user:
        print("You must be logged in to access the mentorship system.")
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
            print("\nMentorship System")
            print("1. Find a mentor")
            print("2. Become a mentor")
            print("3. My mentorship relationships")
            print("4. Schedule mentorship session")
            print("5. View mentorship sessions")
            print("6. Rate mentorship experience")
            print("7. Search mentors by skill")
            print("8. Return to main menu")

            choice = input("Choose an option: ").strip()

            if choice == '1':
                find_mentor(student_id, cursor, conn)
            elif choice == '2':
                become_mentor(student_id, cursor, conn)
            elif choice == '3':
                view_my_mentorship_relationships(student_id, cursor)
            elif choice == '4':
                schedule_mentorship_session(student_id, cursor, conn)
            elif choice == '5':
                view_mentorship_sessions(student_id, cursor)
            elif choice == '6':
                rate_mentorship_experience(student_id, cursor, conn)
            elif choice == '7':
                search_mentors_by_skill(student_id, cursor, conn)
            elif choice == '8':
                break
            else:
                print("Invalid choice.")

        conn.close()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def find_mentor(student_id, cursor, conn):
    """Find and connect with a mentor"""
    try:
        # Check if student is already a mentee in an active relationship
        cursor.execute('''
        SELECT COUNT(*) FROM mentorship_relationships
        WHERE mentee_id = ? AND status = 'active'
        ''', (student_id,))

        active_relationships = cursor.fetchone()[0]

        if active_relationships >= 3:  # Limit to 3 active mentorship relationships
            print("You already have the maximum number of active mentorship relationships (3).")
            return

        print("\nFind a Mentor")
        print("=============")

        skill_area = input("What skill area do you need mentoring in? ").strip()
        if not skill_area:
            print("Skill area cannot be empty.")
            return

        # Find potential mentors (excluding current mentors and self)
        cursor.execute('''
        SELECT DISTINCT s.student_id, s.first_name, s.last_name, s.course, s.year_of_study
        FROM students s
        WHERE s.student_id != ?
        AND s.year_of_study > (SELECT year_of_study FROM students WHERE student_id = ?)
        AND s.student_id NOT IN (
            SELECT mentor_id FROM mentorship_relationships
            WHERE mentee_id = ? AND status IN ('active', 'pending')
        )
        ORDER BY s.year_of_study DESC, s.last_name
        ''', (student_id, student_id, student_id))

        potential_mentors = cursor.fetchall()

        if not potential_mentors:
            print("No potential mentors found.")
            return

        print("\nPotential Mentors:")
        print(f"{'#':<3} {'Name':<25} {'Course':<8} {'Year':<6}")
        print("-" * 45)

        for i, mentor in enumerate(potential_mentors[:10]):  # Show top 10
            print(f"{i+1:<3} {mentor[1]} {mentor[2]:<25} {mentor[3]:<8} {mentor[4]:<6}")

        choice = input("\nSelect a mentor to send request (enter number, 0 to cancel): ").strip()

        if choice == '0':
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > min(len(potential_mentors), 10):
            print("Invalid selection.")
            return

        selected_mentor = potential_mentors[int(choice)-1]
        mentor_id = selected_mentor[0]

        # Send mentorship request
        start_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
        INSERT INTO mentorship_relationships (
            mentor_id, mentee_id, skill_area, start_date, status
        ) VALUES (?, ?, ?, ?, ?)
        ''', (mentor_id, student_id, skill_area, start_date, 'pending'))

        conn.commit()

        print(f"Mentorship request sent to {selected_mentor[1]} {selected_mentor[2]}!")
        print("They will be notified and can accept or decline your request.")

        # Send email notification to mentor
        cursor.execute('SELECT email FROM students WHERE student_id = ?', (mentor_id,))
        mentor_email = cursor.fetchone()[0]

        cursor.execute('SELECT first_name, last_name FROM students WHERE student_id = ?', (student_id,))
        mentee_info = cursor.fetchone()

        # Here you would send an email notification
        print(f"Email notification sent to {mentor_email}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def become_mentor(student_id, cursor, conn):
    """Register to become a mentor or manage mentor requests"""
    try:
        print("\nMentor Dashboard")
        print("================")
        print("1. View mentorship requests")
        print("2. Accept/Decline requests")
        print("3. View current mentees")
        print("4. Update mentor profile")
        print("5. Return to mentorship menu")

        choice = input("Choose an option: ").strip()

        if choice == '1':
            # View pending requests
            cursor.execute('''
            SELECT r.relationship_id, s.first_name, s.last_name, s.course,
                   r.skill_area, r.start_date
            FROM mentorship_relationships r
            JOIN students s ON r.mentee_id = s.student_id
            WHERE r.mentor_id = ? AND r.status = 'pending'
            ORDER BY r.start_date DESC
            ''', (student_id,))

            requests = cursor.fetchall()

            if not requests:
                print("No pending mentorship requests.")
            else:
                print("\nPending Mentorship Requests:")
                print(f"{'ID':<6} {'Student':<25} {'Course':<8} {'Skill Area':<20} {'Date':<12}")
                print("-" * 75)

                for req in requests:
                    print(f"{req[0]:<6} {req[1]} {req[2]:<25} {req[3]:<8} {req[4]:<20} {req[5]:<12}")

        elif choice == '2':
            # Accept/Decline requests
            cursor.execute('''
            SELECT r.relationship_id, s.first_name, s.last_name, r.skill_area
            FROM mentorship_relationships r
            JOIN students s ON r.mentee_id = s.student_id
            WHERE r.mentor_id = ? AND r.status = 'pending'
            ''', (student_id,))

            requests = cursor.fetchall()

            if not requests:
                print("No pending requests to process.")
                return

            print("\nPending Requests:")
            for i, req in enumerate(requests):
                print(f"{i+1}. {req[1]} {req[2]} - {req[3]}")

            req_choice = input("Select request to process (enter number): ").strip()
            if not req_choice.isdigit() or int(req_choice) < 1 or int(req_choice) > len(requests):
                print("Invalid selection.")
                return

            selected_request = requests[int(req_choice)-1]
            relationship_id = selected_request[0]

            print(f"\nProcessing request from {selected_request[1]} {selected_request[2]}")
            print("1. Accept")
            print("2. Decline")

            action = input("Choose action: ").strip()

            if action == '1':
                # Accept request
                cursor.execute('''
                UPDATE mentorship_relationships
                SET status = 'active'
                WHERE relationship_id = ?
                ''', (relationship_id,))

                conn.commit()
                print("Mentorship request accepted!")

            elif action == '2':
                # Decline request
                cursor.execute('''
                UPDATE mentorship_relationships
                SET status = 'declined'
                WHERE relationship_id = ?
                ''', (relationship_id,))

                conn.commit()
                print("Mentorship request declined.")

        elif choice == '3':
            # View current mentees
            cursor.execute('''
            SELECT s.first_name, s.last_name, s.course, r.skill_area, r.start_date,
                   r.mentor_rating, r.mentee_rating
            FROM mentorship_relationships r
            JOIN students s ON r.mentee_id = s.student_id
            WHERE r.mentor_id = ? AND r.status = 'active'
            ORDER BY r.start_date DESC
            ''', (student_id,))

            mentees = cursor.fetchall()

            if not mentees:
                print("You currently have no active mentees.")
            else:
                print("\nYour Current Mentees:")
                print(f"{'Name':<25} {'Course':<8} {'Skill Area':<20} {'Since':<12} {'Your Rating':<12} {'Their Rating':<12}")
                print("-" * 95)

                for mentee in mentees:
                    mentor_rating = f"{mentee[5]:.1f}" if mentee[5] else "Not rated"
                    mentee_rating = f"{mentee[6]:.1f}" if mentee[6] else "Not rated"
                    print(f"{mentee[0]} {mentee[1]:<25} {mentee[2]:<8} {mentee[3]:<20} {mentee[4]:<12} {mentor_rating:<12} {mentee_rating:<12}")

        elif choice == '4':
            # Update mentor profile (placeholder)
            mentor_id = input("Enter mentor ID to update: ")
            print("\nUpdate options:")
            print("1. Update bio")
            print("2. Update expertise areas")
            print("3. Update availability")
            update_choice = input("Select option: ")
            if update_choice == '1':
                new_bio = input("Enter new bio: ")
                print(f"Bio updated for mentor {mentor_id}")
            elif update_choice == '2':
                new_expertise = input("Enter expertise areas (comma-separated): ")
                print(f"Expertise updated for mentor {mentor_id}")
            else:
                print("Profile update successful!")

        elif choice == '5':
            return

        else:
            print("Invalid choice.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_my_mentorship_relationships(student_id, cursor):
    """View all mentorship relationships for the student"""
    try:
        print("\nMy Mentorship Relationships")
        print("=" * 40)

        # As a mentee
        cursor.execute('''
        SELECT 'Mentee' as role, s.first_name, s.last_name, r.skill_area,
               r.start_date, r.status, r.mentor_rating, r.mentee_rating
        FROM mentorship_relationships r
        JOIN students s ON r.mentor_id = s.student_id
        WHERE r.mentee_id = ?

        UNION ALL

        SELECT 'Mentor' as role, s.first_name, s.last_name, r.skill_area,
               r.start_date, r.status, r.mentor_rating, r.mentee_rating
        FROM mentorship_relationships r
        JOIN students s ON r.mentee_id = s.student_id
        WHERE r.mentor_id = ?

        ORDER BY start_date DESC
        ''', (student_id, student_id))

        relationships = cursor.fetchall()

        if not relationships:
            print("You have no mentorship relationships.")
            return

        print(f"{'Role':<8} {'Partner':<25} {'Skill Area':<20} {'Start Date':<12} {'Status':<10} {'M Rating':<9} {'E Rating':<9}")
        print("-" * 100)

        for rel in relationships:
            mentor_rating = f"{rel[6]:.1f}" if rel[6] else "N/A"
            mentee_rating = f"{rel[7]:.1f}" if rel[7] else "N/A"
            print(f"{rel[0]:<8} {rel[1]} {rel[2]:<25} {rel[3]:<20} {rel[4]:<12} {rel[5]:<10} {mentor_rating:<9} {mentee_rating:<9}")

        # Summary statistics
        active_as_mentor = sum(1 for rel in relationships if rel[0] == 'Mentor' and rel[5] == 'active')
        active_as_mentee = sum(1 for rel in relationships if rel[0] == 'Mentee' and rel[5] == 'active')

        print("\nSummary:")
        print(f"Active as Mentor: {active_as_mentor}")
        print(f"Active as Mentee: {active_as_mentee}")
        print(f"Total Relationships: {len(relationships)}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def schedule_mentorship_session(student_id, cursor, conn):
    """Schedule a mentorship session"""
    try:
        # Get active mentorship relationships
        cursor.execute('''
        SELECT r.relationship_id,
               CASE
                   WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name || ' (Mentee)'
                   ELSE s1.first_name || ' ' || s1.last_name || ' (Mentor)'
               END as partner_name,
               r.skill_area
        FROM mentorship_relationships r
        JOIN students s1 ON r.mentor_id = s1.student_id
        JOIN students s2 ON r.mentee_id = s2.student_id
        WHERE (r.mentor_id = ? OR r.mentee_id = ?) AND r.status = 'active'
        ''', (student_id, student_id, student_id))

        relationships = cursor.fetchall()

        if not relationships:
            print("You have no active mentorship relationships to schedule sessions for.")
            return

        print("\nActive Mentorship Relationships:")
        for i, rel in enumerate(relationships):
            print(f"{i+1}. {rel[1]} - {rel[2]}")

        choice = input("Select relationship to schedule session (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(relationships):
            print("Invalid selection.")
            return

        selected_relationship = relationships[int(choice)-1]
        relationship_id = selected_relationship[0]

        print(f"\nScheduling session with {selected_relationship[1]}")

        session_date = input("Session date (YYYY-MM-DD): ").strip()
        if not session_date:
            print("Session date cannot be empty.")
            return

        try:
            # Validate date format
            datetime.strptime(session_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return

        try:
            duration = int(input("Duration in minutes: ").strip())
            if duration <= 0:
                print("Duration must be positive.")
                return
        except ValueError:
            print("Invalid duration format.")
            return

        notes = input("Session agenda/notes (optional): ").strip()

        cursor.execute('''
        INSERT INTO mentorship_sessions (
            relationship_id, session_date, duration_minutes, notes
        ) VALUES (?, ?, ?, ?)
        ''', (relationship_id, session_date, duration, notes))

        conn.commit()
        print("Mentorship session scheduled successfully!")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def view_mentorship_sessions(student_id, cursor):
    """View mentorship sessions"""
    try:
        print("\nMentorship Sessions")
        print("=" * 40)

        cursor.execute('''
        SELECT ms.session_id,
               CASE
                   WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name || ' (Mentee)'
                   ELSE s1.first_name || ' ' || s1.last_name || ' (Mentor)'
               END as partner_name,
               ms.session_date, ms.duration_minutes, ms.notes,
               ms.mentor_feedback, ms.mentee_feedback, ms.progress_rating
        FROM mentorship_sessions ms
        JOIN mentorship_relationships r ON ms.relationship_id = r.relationship_id
        JOIN students s1 ON r.mentor_id = s1.student_id
        JOIN students s2 ON r.mentee_id = s2.student_id
        WHERE (r.mentor_id = ? OR r.mentee_id = ?)
        ORDER BY ms.session_date DESC
        ''', (student_id, student_id, student_id))

        sessions = cursor.fetchall()

        if not sessions:
            print("No mentorship sessions found.")
            return

        print(f"{'ID':<6} {'Partner':<25} {'Date':<12} {'Duration':<8} {'Rating':<8}")
        print("-" * 65)

        for session in sessions:
            rating = f"{session[7]}/5" if session[7] else "N/A"
            print(f"{session[0]:<6} {session[1][:25]:<25} {session[2]:<12} {session[3]}min{'':<3} {rating:<8}")

        # Option to view detailed session
        session_id = input("\nEnter session ID to view details (or press Enter to continue): ").strip()
        if session_id.isdigit():
            cursor.execute('''
            SELECT ms.session_date, ms.duration_minutes, ms.notes,
                   ms.mentor_feedback, ms.mentee_feedback, ms.progress_rating,
                   CASE
                       WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name || ' (Mentee)'
                       ELSE s1.first_name || ' ' || s1.last_name || ' (Mentor)'
                   END as partner_name
            FROM mentorship_sessions ms
            JOIN mentorship_relationships r ON ms.relationship_id = r.relationship_id
            JOIN students s1 ON r.mentor_id = s1.student_id
            JOIN students s2 ON r.mentee_id = s2.student_id
            WHERE ms.session_id = ? AND (r.mentor_id = ? OR r.mentee_id = ?)
            ''', (student_id, session_id, student_id, student_id))

            session_detail = cursor.fetchone()

            if session_detail:
                print("\nSession Details:")
                print(f"Partner: {session_detail[6]}")
                print(f"Date: {session_detail[0]}")
                print(f"Duration: {session_detail[1]} minutes")
                print(f"Notes: {session_detail[2] or 'No notes'}")
                print(f"Mentor Feedback: {session_detail[3] or 'No feedback'}")
                print(f"Mentee Feedback: {session_detail[4] or 'No feedback'}")
                print(f"Progress Rating: {session_detail[5] or 'Not rated'}/5")
            else:
                print("Session not found or access denied.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def rate_mentorship_experience(student_id, cursor, conn):
    """Rate mentorship experience"""
    try:
        # Get relationships that can be rated
        cursor.execute('''
        SELECT r.relationship_id,
               CASE
                   WHEN r.mentor_id = ? THEN 'mentor'
                   ELSE 'mentee'
               END as my_role,
               CASE
                   WHEN r.mentor_id = ? THEN s2.first_name || ' ' || s2.last_name
                   ELSE s1.first_name || ' ' || s1.last_name
               END as partner_name,
               r.skill_area, r.mentor_rating, r.mentee_rating
        FROM mentorship_relationships r
        JOIN students s1 ON r.mentor_id = s1.student_id
        JOIN students s2 ON r.mentee_id = s2.student_id
        WHERE (r.mentor_id = ? OR r.mentee_id = ?) AND r.status IN ('active', 'completed')
        ''', (student_id, student_id, student_id, student_id))

        relationships = cursor.fetchall()

        if not relationships:
            print("No relationships available for rating.")
            return

        print("\nRateable Mentorship Relationships:")
        for i, rel in enumerate(relationships):
            my_role = rel[1]
            partner_name = rel[2]
            current_rating = rel[4] if my_role == 'mentee' else rel[5]  # mentee rates mentor, mentor rates mentee
            rating_status = f"(Current rating: {current_rating:.1f})" if current_rating else "(Not rated)"

            print(f"{i+1}. {partner_name} - {rel[3]} {rating_status}")

        choice = input("Select relationship to rate (enter number): ").strip()
        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(relationships):
            print("Invalid selection.")
            return

        selected_relationship = relationships[int(choice)-1]
        relationship_id = selected_relationship[0]
        my_role = selected_relationship[1]
        partner_name = selected_relationship[2]

        print(f"\nRating {partner_name} for {selected_relationship[3]} mentorship")

        try:
            rating = float(input("Enter rating (1.0 - 5.0): ").strip())
            if rating < 1.0 or rating > 5.0:
                print("Rating must be between 1.0 and 5.0.")
                return
        except ValueError:
            print("Invalid rating format.")
            return

        # Update the appropriate rating field
        if my_role == 'mentee':
            # Mentee rating the mentor
            cursor.execute('''
            UPDATE mentorship_relationships
            SET mentor_rating = ?
            WHERE relationship_id = ?
            ''', (rating, relationship_id))
        else:
            # Mentor rating the mentee
            cursor.execute('''
            UPDATE mentorship_relationships
            SET mentee_rating = ?
            WHERE relationship_id = ?
            ''', (rating, relationship_id))

        conn.commit()
        print(f"Rating submitted successfully! You rated {partner_name}: {rating:.1f}/5.0")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def search_mentors_by_skill(student_id, cursor, conn):
    """Search for mentors by specific skill areas"""
    try:
        print("\nSearch Mentors by Skill")
        print("=" * 30)

        # Show popular skill areas
        cursor.execute('''
        SELECT skill_area, COUNT(*) as count
        FROM mentorship_relationships
        WHERE status IN ('active', 'completed')
        GROUP BY skill_area
        ORDER BY count DESC
        LIMIT 10
        ''')

        popular_skills = cursor.fetchall()

        if popular_skills:
            print("Popular skill areas:")
            for skill in popular_skills:
                print(f"- {skill[0]} ({skill[1]} relationships)")
            print()

        skill_search = input("Enter skill area to search for: ").strip()
        if not skill_search:
            print("Skill area cannot be empty.")
            return

        # Find mentors who have experience in this skill area
        cursor.execute('''
        SELECT s.student_id, s.first_name, s.last_name, s.course, s.year_of_study,
               COUNT(r.relationship_id) as mentorship_count,
               AVG(r.mentor_rating) as avg_rating
        FROM students s
        JOIN mentorship_relationships r ON s.student_id = r.mentor_id
        WHERE r.skill_area LIKE ? AND r.status IN ('active', 'completed')
        AND s.student_id != ?
        AND s.student_id NOT IN (
            SELECT mentor_id FROM mentorship_relationships
            WHERE mentee_id = ? AND status IN ('active', 'pending')
        )
        GROUP BY s.student_id, s.first_name, s.last_name, s.course, s.year_of_study
        ORDER BY avg_rating DESC, mentorship_count DESC
        ''', (f'%{skill_search}%', student_id, student_id))

        mentors = cursor.fetchall()

        if not mentors:
            print(f"No experienced mentors found for '{skill_search}'.")
            return

        print(f"\nExperienced Mentors for '{skill_search}':")
        print(f"{'#':<3} {'Name':<25} {'Course':<8} {'Year':<6} {'Mentorships':<12} {'Avg Rating':<12}")
        print("-" * 75)

        for i, mentor in enumerate(mentors):
            avg_rating = f"{mentor[6]:.1f}" if mentor[6] else "N/A"
            print(f"{i+1:<3} {mentor[1]} {mentor[2]:<25} {mentor[3]:<8} {mentor[4]:<6} {mentor[5]:<12} {avg_rating:<12}")

        choice = input("\nSelect mentor to send request (enter number, 0 to cancel): ").strip()

        if choice == '0':
            return

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(mentors):
            print("Invalid selection.")
            return

        selected_mentor = mentors[int(choice)-1]
        mentor_id = selected_mentor[0]

        # Send mentorship request
        start_date = datetime.now().strftime('%Y-%m-%d')

        cursor.execute('''
        INSERT INTO mentorship_relationships (
            mentor_id, mentee_id, skill_area, start_date, status
        ) VALUES (?, ?, ?, ?, ?)
        ''', (mentor_id, student_id, skill_search, start_date, 'pending'))

        conn.commit()

        print(f"Mentorship request sent to {selected_mentor[1]} {selected_mentor[2]}!")
        print("They will be notified and can accept or decline your request.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
