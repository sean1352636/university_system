from datetime import datetime, timedelta
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import safe_execute, auth
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.gamification import award_engagement_points


def post_job_opportunity():
    """Post a job opportunity"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to post jobs.")
        return

    if not auth.check_permission('post_jobs'):
        print("You don't have permission to post jobs.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return

    print("\nPost Job Opportunity")
    print("====================")

    company_name = input("Company Name: ")
    job_title = input("Job Title: ")

    # Job categories
    categories = [
        "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
        "Retail", "Government", "Non-profit", "Entertainment", "Consulting",
        "Marketing", "Sales", "Engineering", "Research", "Other"
    ]

    print("\nJob Categories:")
    for i, category in enumerate(categories, 1):
        print(f"{i}. {category}")

    try:
        cat_choice = int(input("Select category: "))
        if 1 <= cat_choice <= len(categories):
            category = categories[cat_choice - 1]
        else:
            category = "Other"
    except ValueError:
        category = "Other"

    location = input("Location (city, state/country): ")

    # Job types
    job_types = ["Full-time", "Part-time", "Contract", "Internship", "Remote"]
    print("\nJob Types:")
    for i, jtype in enumerate(job_types, 1):
        print(f"{i}. {jtype}")

    try:
        type_choice = int(input("Select job type: "))
        if 1 <= type_choice <= len(job_types):
            job_type = job_types[type_choice - 1]
        else:
            job_type = "Full-time"
    except ValueError:
        job_type = "Full-time"

    # Experience levels
    exp_levels = ["Entry Level", "Mid Level", "Senior Level", "Executive", "Any"]
    print("\nExperience Levels:")
    for i, level in enumerate(exp_levels, 1):
        print(f"{i}. {level}")

    try:
        exp_choice = int(input("Select experience level: "))
        if 1 <= exp_choice <= len(exp_levels):
            experience_level = exp_levels[exp_choice - 1]
        else:
            experience_level = "Any"
    except ValueError:
        experience_level = "Any"

    salary_range = input("Salary Range (optional): ")

    print("\nJob Description (press Enter twice to finish):")
    desc_lines = []
    while True:
        line = input()
        if line == "" and (not desc_lines or desc_lines[-1] == ""):
            break
        desc_lines.append(line)
    job_description = "\n".join(desc_lines)

    print("\nRequirements (press Enter twice to finish):")
    req_lines = []
    while True:
        line = input()
        if line == "" and (not req_lines or req_lines[-1] == ""):
            break
        req_lines.append(line)
    requirements = "\n".join(req_lines)

    # Application method
    app_methods = ["Email", "Company Website", "LinkedIn", "Other"]
    print("\nApplication Methods:")
    for i, method in enumerate(app_methods, 1):
        print(f"{i}. {method}")

    try:
        app_choice = int(input("Select application method: "))
        if 1 <= app_choice <= len(app_methods):
            application_method = app_methods[app_choice - 1]
        else:
            application_method = "Email"
    except ValueError:
        application_method = "Email"

    contact_email = input("Contact Email: ")

    # Set expiry date (default 30 days)
    expiry_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    custom_expiry = input(f"Expiry Date (default {expiry_date}, format YYYY-MM-DD): ")
    if custom_expiry:
        try:
            datetime.strptime(custom_expiry, '%Y-%m-%d')
            expiry_date = custom_expiry
        except ValueError:
            print("Invalid date format, using default.")

    # Insert job posting
    cursor.execute('''
        INSERT INTO job_postings
        (posted_by, company_name, job_title, job_description, location, job_type,
         salary_range, requirements, application_method, contact_email, post_date,
         expiry_date, category, experience_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, company_name, job_title, job_description, location, job_type,
          salary_range, requirements, application_method, contact_email,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), expiry_date, category, experience_level))

    job_id = cursor.lastrowid

    # Award engagement points
    award_engagement_points(alumni_id, 'job_posted', 25)

    conn.commit()
    conn.close()

    print(f"Job opportunity posted successfully! Job ID: {job_id}")
    print("The job will be visible to all alumni in the job board.")

def view_job_board():
    """View available job opportunities"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view the job board.")
        return

    if not auth.check_permission('view_job_board'):
        print("You don't have permission to view the job board.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nAlumni Job Board")
    print("================")
    print("1. View All Active Jobs")
    print("2. Search Jobs by Category")
    print("3. Search Jobs by Location")
    print("4. Search Jobs by Experience Level")
    print("5. My Posted Jobs")

    choice = input("Enter your choice: ")

    if choice == '1':
        # View all active jobs
        cursor.execute('''
            SELECT j.*, a.first_name, a.last_name
            FROM job_postings j
            JOIN alumni a ON j.posted_by = a.alumni_id
            WHERE j.is_active = 1 AND j.expiry_date >= date('now')
            ORDER BY j.post_date DESC
        ''')

    elif choice == '2':
        # Search by category
        categories = [
            "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
            "Retail", "Government", "Non-profit", "Entertainment", "Consulting",
            "Marketing", "Sales", "Engineering", "Research", "Other"
        ]

        print("\nJob Categories:")
        for i, category in enumerate(categories, 1):
            print(f"{i}. {category}")

        try:
            cat_choice = int(input("Select category: "))
            if 1 <= cat_choice <= len(categories):
                selected_category = categories[cat_choice - 1]
                cursor.execute('''
                    SELECT j.*, a.first_name, a.last_name
                    FROM job_postings j
                    JOIN alumni a ON j.posted_by = a.alumni_id
                    WHERE j.is_active = 1 AND j.expiry_date >= date('now') AND j.category = ?
                    ORDER BY j.post_date DESC
                ''', (selected_category,))
            else:
                print("Invalid category.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

    elif choice == '3':
        # Search by location
        location = input("Enter location (city, state, or country): ")
        cursor.execute('''
            SELECT j.*, a.first_name, a.last_name
            FROM job_postings j
            JOIN alumni a ON j.posted_by = a.alumni_id
            WHERE j.is_active = 1 AND j.expiry_date >= date('now') AND j.location LIKE ?
            ORDER BY j.post_date DESC
        ''', (f'%{location}%',))

    elif choice == '4':
        # Search by experience level
        exp_levels = ["Entry Level", "Mid Level", "Senior Level", "Executive", "Any"]
        print("\nExperience Levels:")
        for i, level in enumerate(exp_levels, 1):
            print(f"{i}. {level}")

        try:
            exp_choice = int(input("Select experience level: "))
            if 1 <= exp_choice <= len(exp_levels):
                selected_level = exp_levels[exp_choice - 1]
                cursor.execute('''
                    SELECT j.*, a.first_name, a.last_name
                    FROM job_postings j
                    JOIN alumni a ON j.posted_by = a.alumni_id
                    WHERE j.is_active = 1 AND j.expiry_date >= date('now')
                    AND (j.experience_level = ? OR j.experience_level = 'Any')
                    ORDER BY j.post_date DESC
                ''', (selected_level,))
            else:
                print("Invalid choice.")
                conn.close()
                return
        except ValueError:
            print("Invalid input.")
            conn.close()
            return

    elif choice == '5':
        # My posted jobs
        cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
        result = cursor.fetchone()
        if result and result[0].startswith('A'):
            alumni_id = result[0]
            cursor.execute('''
                SELECT j.*, a.first_name, a.last_name
                FROM job_postings j
                JOIN alumni a ON j.posted_by = a.alumni_id
                WHERE j.posted_by = ?
                ORDER BY j.post_date DESC
            ''', (alumni_id,))
        else:
            print("Alumni profile not found.")
            conn.close()
            return
    else:
        print("Invalid choice.")
        conn.close()
        return

    jobs = cursor.fetchall()

    if not jobs:
        print("No job opportunities found.")
    else:
        print(f"\nFound {len(jobs)} job opportunities:")
        print("-" * 80)

        for i, job in enumerate(jobs, 1):
            poster_name = f"{job[16]} {job[17]}"
            print(f"{i}. {job[3]} at {job[2]}")  # job_title at company_name
            print(f"   Posted by: {poster_name}")
            print(f"   Location: {job[5]}")
            print(f"   Type: {job[6]} | Level: {job[14]} | Category: {job[13]}")
            if job[7]:  # salary_range
                print(f"   Salary: {job[7]}")
            print(f"   Posted: {job[11]} | Expires: {job[12]}")
            print(f"   Description: {job[4][:100]}...")
            print("-" * 80)

        # Option to view job details
        view_choice = input(f"\nEnter job number to view details (1-{len(jobs)}) or press Enter to continue: ")
        if view_choice.isdigit():
            job_index = int(view_choice) - 1
            if 0 <= job_index < len(jobs):
                view_job_details(jobs[job_index], cursor)

    conn.close()

def view_job_details(job, cursor):
    """View detailed job information"""
    print(f"\n{'='*60}")
    print(f"Job Title: {job[3]}")
    print(f"Company: {job[2]}")
    print(f"Location: {job[5]}")
    print(f"Job Type: {job[6]}")
    print(f"Experience Level: {job[14]}")
    print(f"Category: {job[13]}")
    if job[7]:
        print(f"Salary Range: {job[7]}")
    print(f"Contact: {job[10]}")
    print(f"Application Method: {job[9]}")
    print(f"Posted: {job[11]}")
    print(f"Expires: {job[12]}")
    print(f"{'='*60}")
    print("\nJob Description:")
    print(job[4])
    print(f"{'='*60}")
    print("\nRequirements:")
    print(job[8])
    print(f"{'='*60}")

    # Option to apply (record interest)
    apply_choice = input("\nWould you like to record your interest in this position? (y/n): ").lower()
    if apply_choice == 'y':
        record_job_interest(job[0], cursor)

def record_job_interest(job_id, cursor):
    """Record alumni interest in a job"""
    global auth

    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        return

    # Check if already applied
    cursor.execute('SELECT * FROM job_applications WHERE job_id = ? AND applicant_id = ?', (job_id, alumni_id))
    if cursor.fetchone():
        print("You have already expressed interest in this position.")
        return

    cover_letter = input("Enter a brief cover letter/message (optional): ")

    # Record the application
    cursor.execute('''
        INSERT INTO job_applications (job_id, applicant_id, application_date, status, cover_letter)
        VALUES (?, ?, ?, ?, ?)
    ''', (job_id, alumni_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'submitted', cover_letter))

    # Award engagement points
    award_engagement_points(alumni_id, 'job_application', 10)

    print("Your interest has been recorded! The job poster will be notified.")

def schedule_career_counseling():
    """Schedule career counseling session"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to schedule career counseling.")
        return

    if not auth.check_permission('schedule_career_counseling'):
        print("You don't have permission to schedule career counseling.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get available counselors
    cursor.execute('''
        SELECT alumni_id, first_name, last_name, job_title, current_employer
        FROM alumni
        WHERE is_mentor = 1
        ORDER BY last_name, first_name
    ''')

    counselors = cursor.fetchall()

    if not counselors:
        print("No career counselors are currently available.")
        conn.close()
        return

    print("\nAvailable Career Counselors:")
    print("============================")

    for i, counselor in enumerate(counselors, 1):
        print(f"{i}. {counselor[1]} {counselor[2]}")
        if counselor[3] and counselor[4]:
            print(f"   {counselor[3]} at {counselor[4]}")
        print()

    try:
        counselor_choice = int(input(f"Select counselor (1-{len(counselors)}): "))
        if 1 <= counselor_choice <= len(counselors):
            selected_counselor = counselors[counselor_choice - 1]
        else:
            print("Invalid selection.")
            conn.close()
            return
    except ValueError:
        print("Invalid input.")
        conn.close()
        return

    # Get current user's alumni ID
    client_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        client_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return

    # Session details
    session_types = ["Career Planning", "Resume Review", "Interview Preparation", "Industry Insights", "Networking Advice"]
    print("\nSession Types:")
    for i, stype in enumerate(session_types, 1):
        print(f"{i}. {stype}")

    try:
        type_choice = int(input("Select session type: "))
        if 1 <= type_choice <= len(session_types):
            session_type = session_types[type_choice - 1]
        else:
            session_type = "Career Planning"
    except ValueError:
        session_type = "Career Planning"

    # Schedule date/time
    session_date = input("Preferred date and time (YYYY-MM-DD HH:MM): ")
    try:
        # Validate date format
        datetime.strptime(session_date, "%Y-%m-%d %H:%M")
    except ValueError:
        print("Invalid date format.")
        conn.close()
        return

    duration = input("Expected duration in minutes (default 60): ")
    try:
        duration = int(duration) if duration else 60
    except ValueError:
        duration = 60

    notes = input("Additional notes or specific topics to discuss: ")

    # Insert counseling session
    cursor.execute('''
        INSERT INTO career_counseling
        (counselor_id, client_id, session_date, session_type, duration, notes, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (selected_counselor[0], client_id, session_date, session_type, duration, notes, 'scheduled'))

    session_id = cursor.lastrowid

    conn.commit()
    conn.close()

    counselor_name = f"{selected_counselor[1]} {selected_counselor[2]}"
    print("\nCareer counseling session scheduled successfully!")
    print(f"Session ID: {session_id}")
    print(f"Counselor: {counselor_name}")
    print(f"Date/Time: {session_date}")
    print(f"Type: {session_type}")
    print("The counselor will be notified and will contact you to confirm the session.")
