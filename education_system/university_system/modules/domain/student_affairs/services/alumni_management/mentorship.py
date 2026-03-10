from datetime import datetime
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.email import send_mentorship_notification
from .core import get_db_connection, safe_execute, auth


def setup_mentorship():
    """Set up a mentorship"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to set up mentorship.")
        return

    try:
        print("\n--- Set Up Mentorship ---")
        print("1. Become a Mentor")
        print("2. Find a Mentor")
        choice = input("Enter your choice (1-2): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            expertise = input("Enter your area of expertise: ")
            availability = input("Enter your availability (weekly/monthly): ") or "monthly"

            cursor.execute('''
                INSERT INTO alumni_mentorships (mentor_id, expertise, availability, status, created_date)
                VALUES (?, ?, ?, 'active', ?)
            ''', (auth.current_user['user_id'], expertise, availability, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            print("You are now registered as a mentor!")

        elif choice == '2':
            cursor.execute('''
                SELECT mentor_id, expertise, availability
                FROM alumni_mentorships
                WHERE status = 'active'
            ''')
            mentors = cursor.fetchall()

            if not mentors:
                print("No mentors currently available.")
                conn.close()
                return

            print("\nAvailable Mentors:")
            for i, mentor in enumerate(mentors, 1):
                print(f"{i}. ID: {mentor[0]}, Expertise: {mentor[1]}, Availability: {mentor[2]}")

            mentor_choice = input("\nEnter mentor number to request mentorship (or 0 to cancel): ")
            if mentor_choice.isdigit() and 0 < int(mentor_choice) <= len(mentors):
                selected_mentor = mentors[int(mentor_choice) - 1]
                cursor.execute('''
                    INSERT INTO alumni_mentorship_requests (mentor_id, mentee_id, request_date, status)
                    VALUES (?, ?, ?, 'pending')
                ''', (selected_mentor[0], auth.current_user['user_id'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
                print("Mentorship request sent!")

        conn.close()
    except Exception as e:
        print(f"Error setting up mentorship: {e}")

def view_mentorships():
    """View mentorships"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view mentorships.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # View as mentor
        cursor.execute('''
            SELECT mentee_id, request_date, status
            FROM alumni_mentorship_requests
            WHERE mentor_id = ?
            ORDER BY request_date DESC
        ''', (auth.current_user['user_id'],))
        mentee_requests = cursor.fetchall()

        # View as mentee
        cursor.execute('''
            SELECT mentor_id, request_date, status
            FROM alumni_mentorship_requests
            WHERE mentee_id = ?
            ORDER BY request_date DESC
        ''', (auth.current_user['user_id'],))
        mentor_requests = cursor.fetchall()

        conn.close()

        print("\n--- Your Mentorships ---")

        if mentee_requests:
            print("\nAs Mentor:")
            print(f"{'Mentee ID':<15} {'Request Date':<20} {'Status':<15}")
            print("-" * 50)
            for req in mentee_requests:
                print(f"{req[0]:<15} {req[1]:<20} {req[2]:<15}")

        if mentor_requests:
            print("\nAs Mentee:")
            print(f"{'Mentor ID':<15} {'Request Date':<20} {'Status':<15}")
            print("-" * 50)
            for req in mentor_requests:
                print(f"{req[0]:<15} {req[1]:<20} {req[2]:<15}")

        if not mentee_requests and not mentor_requests:
            print("No mentorships found.")
    except Exception as e:
        print(f"Error viewing mentorships: {e}")

def smart_mentorship_matching():
    """AI-powered mentorship matching based on interests, industry, etc."""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to use smart matching.")
        return

    if not auth.check_permission('manage_ai_features'):
        print("You don't have permission to use AI features.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nSmart Mentorship Matching")
    print("=========================")

    # Get all potential mentors
    cursor.execute('''
        SELECT alumni_id, first_name, last_name, industry, job_title,
               current_employer, skills, graduation_year
        FROM alumni
        WHERE is_mentor = 1
    ''')

    mentors = cursor.fetchall()

    # Get all potential mentees (for demo, using alumni who aren't mentors)
    cursor.execute('''
        SELECT alumni_id, first_name, last_name, industry, job_title,
               current_employer, skills, graduation_year
        FROM alumni
        WHERE is_mentor = 0 OR is_mentor IS NULL
    ''')

    mentees = cursor.fetchall()

    if not mentors or not mentees:
        print("Insufficient data for matching.")
        conn.close()
        return

    print(f"Analyzing {len(mentors)} mentors and {len(mentees)} potential mentees...")

    # Simple matching algorithm based on industry, skills, and experience gap
    matches = []

    for mentee in mentees:
        mentee_id, m_first, m_last, m_industry, m_job, m_employer, m_skills, m_grad_year = mentee
        mentee_skills = set((m_skills or "").lower().split(','))

        mentor_scores = []

        for mentor in mentors:
            mentor_id, mentor_first, mentor_last, mentor_industry, mentor_job, mentor_employer, mentor_skills, mentor_grad_year = mentor

            score = 0

            # Industry match
            if m_industry and mentor_industry and m_industry.lower() == mentor_industry.lower():
                score += 30

            # Skills overlap
            if m_skills and mentor_skills:
                mentor_skill_set = set(mentor_skills.lower().split(','))
                skill_overlap = len(mentee_skills.intersection(mentor_skill_set))
                score += skill_overlap * 10

            # Experience gap (mentor should be more experienced)
            if mentor_grad_year and m_grad_year and mentor_grad_year < m_grad_year:
                experience_gap = m_grad_year - mentor_grad_year
                if 3 <= experience_gap <= 15:  # Ideal gap
                    score += 20
                elif experience_gap > 15:
                    score += 10

            # Avoid self-matching
            if mentor_id != mentee_id:
                mentor_scores.append((mentor_id, mentor_first, mentor_last, score))

        # Get top 3 matches for this mentee
        mentor_scores.sort(key=lambda x: x[3], reverse=True)
        top_matches = mentor_scores[:3]

        if top_matches and top_matches[0][3] > 0:  # Only include if there's a positive score
            matches.append((mentee_id, f"{m_first} {m_last}", top_matches))

    if matches:
        print(f"\nGenerated {len(matches)} smart mentorship recommendations:")
        print("-" * 80)

        for mentee_id, mentee_name, mentor_matches in matches:
            print(f"Mentee: {mentee_name}")
            print("Recommended Mentors:")

            for i, (mentor_id, mentor_first, mentor_last, score) in enumerate(mentor_matches, 1):
                mentor_name = f"{mentor_first} {mentor_last}"
                match_quality = "Excellent" if score >= 50 else "Good" if score >= 30 else "Fair"
                print(f"  {i}. {mentor_name} (Match Score: {score} - {match_quality})")

            print("-" * 80)

        # Option to create mentorships from recommendations
        create_choice = input("Would you like to create mentorships from these recommendations? (y/n): ").lower()
        if create_choice == 'y':
            create_recommended_mentorships(matches, cursor)
    else:
        print("No suitable mentorship matches found.")

    conn.close()

def create_recommended_mentorships(matches, cursor):
    """Create mentorships from AI recommendations"""
    print("\nCreating Mentorships from Recommendations")
    print("=========================================")

    created_count = 0

    for mentee_id, mentee_name, mentor_matches in matches:
        print(f"\nMentee: {mentee_name}")
        print("Available mentors:")

        for i, (mentor_id, mentor_first, mentor_last, score) in enumerate(mentor_matches, 1):
            mentor_name = f"{mentor_first} {mentor_last}"
            print(f"  {i}. {mentor_name} (Score: {score})")

        choice = input(f"Select mentor for {mentee_name} (1-{len(mentor_matches)}, or 's' to skip): ")

        if choice.isdigit():
            mentor_index = int(choice) - 1
            if 0 <= mentor_index < len(mentor_matches):
                mentor_id, mentor_first, mentor_last, score = mentor_matches[mentor_index]

                # Create the mentorship
                start_date = datetime.now().strftime("%Y-%m-%d")
                focus_area = "AI-Matched General Mentorship"

                cursor.execute('''
                    INSERT INTO mentorships
                    (mentor_id, mentee_id, start_date, status, focus_area, match_score, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (mentor_id, mentee_id, start_date, "Active", focus_area, score/100.0,
                      f"AI-generated match with {score}% compatibility"))

                mentorship_id = cursor.lastrowid
                created_count += 1

                print(f"\u2705 Created mentorship {mentorship_id}: {mentor_first} {mentor_last} \u2192 {mentee_name}")

                # Automatically send mentorship notification emails
                try:
                    # Get mentor email
                    cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (mentor_id,))
                    mentor_result = cursor.fetchone()
                    mentor_email = mentor_result[0] if mentor_result else None

                    # Get mentee email
                    cursor.execute('SELECT email FROM alumni_profiles WHERE alumni_id = ?', (mentee_id,))
                    mentee_result = cursor.fetchone()
                    mentee_email = mentee_result[0] if mentee_result else None

                    if mentor_email and mentee_email:
                        mentor_name = f"{mentor_first} {mentor_last}"
                        send_mentorship_notification(
                            mentor_email=mentor_email,
                            mentee_email=mentee_email,
                            mentor_name=mentor_name,
                            mentee_name=mentee_name,
                            focus_area=focus_area,
                            start_date=start_date,
                            end_date=None
                        )
                        print(f"   \u2709\ufe0f  Email notifications sent to mentor and mentee")
                    else:
                        print(f"   \u26a0\ufe0f  Could not send emails: Missing email address(es)")
                except Exception as e:
                    print(f"   \u26a0\ufe0f  Could not send email notification: {e}")
        elif choice.lower() == 's':
            print(f"Skipped {mentee_name}")
        else:
            print("Invalid choice, skipping.")

    print(f"\nCreated {created_count} mentorships from AI recommendations!")
