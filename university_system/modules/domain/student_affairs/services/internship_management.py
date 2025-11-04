from university_system.infrastructure.database.db import sqlite3, DatabaseManager
from datetime import datetime
import os
from university_system.infrastructure.email import (
    send_internship_notification,
    send_application_confirmation,
)

from university_system.infrastructure.database.db import get_connection

# Global variable to store the auth object from main.py
# Import auth instance management from user_authentication
try:
    from university_system.infrastructure.auth.user_authentication import get_current_user, set_auth_instance
    HAS_AUTH = True
except ImportError:
    HAS_AUTH = False
    get_current_user = lambda: None
    set_auth_instance = lambda x: None

auth = None

def set_auth(auth_instance):
    global auth
    auth = auth_instance
    # Also set it in the global auth instance if available
    if HAS_AUTH:
        set_auth_instance(auth_instance)
def setup_internship_permissions():
    """Set up permissions for the internship module"""
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 1) Insert all internship-related permissions
    permission_defs = [
        ('manage_internships',     'Manage all internship opportunities'),
        ('view_all_applications',  'View all internship applications'),
        ('approve_applications',   'Approve or reject internship applications'),
        ('view_internship_reports','View internship reports and analytics'),
        ('create_internship',      'Create new internship opportunities'),
        ('edit_internship',        'Edit existing internship opportunities'),
        ('delete_internship',      'Delete internship opportunities'),
        ('view_internships',       'View available internships'),
        ('apply_for_internship',   'Apply for internships'),
        ('view_own_applications',  'View own internship applications')
    ]
    for perm, desc in permission_defs:
        cursor.execute(
            'INSERT OR IGNORE INTO permissions (permission_name, description, created_at) VALUES (?, ?, ?)',
            (perm, desc, timestamp)
        )

    # 2) Map them to roles
    role_map = [
        ('admin',    'manage_internships'),
        ('admin',    'view_all_applications'),
        ('admin',    'approve_applications'),
        ('admin',    'view_internship_reports'),
        ('admin',    'create_internship'),
        ('admin',    'edit_internship'),
        ('admin',    'delete_internship'),
        ('staff',    'manage_internships'),
        ('staff',    'view_all_applications'),
        ('staff',    'approve_applications'),
        ('staff',    'view_internship_reports'),
        ('staff',    'create_internship'),
        ('staff',    'edit_internship'),
        ('student',  'view_internships'),
        ('student',  'apply_for_internship'),
        ('student',  'view_own_applications')
    ]
    for role, perm in role_map:
        cursor.execute('SELECT id FROM roles WHERE role_name = ?', (role,))
        r = cursor.fetchone()
        cursor.execute('SELECT id FROM permissions WHERE permission_name = ?', (perm,))
        p = cursor.fetchone()
        if r and p:
            cursor.execute(
                'INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)',
                (r[0], p[0])
            )

    conn.commit()
    conn.close()
        
def init_internship_db():
    """Initialize the internship database tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Create internships table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS internships (
            internship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            description TEXT,
            requirements TEXT,
            start_date TEXT,
            end_date TEXT,
            is_paid BOOLEAN,
            salary TEXT,
            hours_per_week INTEGER,
            posted_date TEXT,
            deadline_date TEXT,
            status TEXT DEFAULT 'active',
            contact_email TEXT,
            course_relevance TEXT,
            created_by TEXT,
            created_date TEXT
        )
        ''')
        
        # Create internship applications table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS internship_applications (
            application_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            internship_id INTEGER,
            application_date TEXT,
            status TEXT DEFAULT 'pending',
            cv_filename TEXT,
            cover_letter TEXT,
            feedback TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (internship_id) REFERENCES internships (internship_id)
        )
        ''')
        
        # Create internship placements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS internship_placements (
            placement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            internship_id INTEGER,
            start_date TEXT,
            end_date TEXT,
            supervisor_name TEXT,
            supervisor_email TEXT,
            status TEXT DEFAULT 'active',
            feedback_student TEXT,
            feedback_employer TEXT,
            FOREIGN KEY (student_id) REFERENCES students (student_id),
            FOREIGN KEY (internship_id) REFERENCES internships (internship_id)
        )
        ''')
        
        # Add sample internships if none exist
        cursor.execute("SELECT COUNT(*) FROM internships")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Add sample internships
            sample_internships = [
                (
                    'Software Development Intern', 'TechCorp', 'London', 
                    'Develop and maintain web applications using Python and JavaScript.',
                    'Proficiency in Python, JavaScript, and web frameworks', 
                    '2025-06-01', '2025-08-31', 1, '£1500/month', 40,
                    '2025-02-01', '2025-04-15', 'active', 'hr@techcorp.com', 'CS',
                    'admin', datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ),
                (
                    'Data Science Intern', 'DataWorks', 'Manchester', 
                    'Analyze large datasets and develop machine learning models.',
                    'Knowledge of Python, R, and statistical methods', 
                    '2025-06-15', '2025-09-15', 1, '£1600/month', 35,
                    '2025-02-10', '2025-04-30', 'active', 'careers@dataworks.co.uk', 'DS',
                    'admin', datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ),
                (
                    'IT Support Intern', 'UniTech', 'Newcastle', 
                    'Provide technical support to university departments.',
                    'Basic knowledge of IT systems and troubleshooting', 
                    '2025-05-01', '2025-07-31', 0, 'Unpaid', 20,
                    '2025-02-15', '2025-03-31', 'active', 'support@unitech.edu', 'CS',
                    'admin', datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
            ]
            
            cursor.executemany('''
            INSERT INTO internships (
                title, company, location, description, requirements, 
                start_date, end_date, is_paid, salary, hours_per_week,
                posted_date, deadline_date, status, contact_email, course_relevance,
                created_by, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', sample_internships)
            
            print("Sample internships added to the database!")
        
        conn.commit()
        conn.close()
        print("Internship database initialized successfully!")
    except sqlite3.Error as e:
        print(f"Error initializing internship database: {e}")

def set_auth(auth_object):
    """Set the authentication object for the internship module"""
    global auth
    auth = auth_object

# Internship Management Functions

def view_available_internships():
    """View all available internships"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view internships.")
        return
    
    if not (auth.check_permission('view_internships') or auth.check_permission('manage_internships')):
        print("You don't have permission to view internships.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # For students, filter by their course
        if auth.current_user['role'] == 'student':
            # Get student's course
            cursor.execute('''
            SELECT course FROM students 
            JOIN users ON students.student_id = users.student_id
            WHERE users.id = ?
            ''', (auth.current_user['id'],))
            
            result = cursor.fetchone()
            if result:
                course = result[0]
                
                # Get internships relevant to the student's course or marked for all courses
                cursor.execute('''
                SELECT internship_id, title, company, location, start_date, end_date, 
                       is_paid, salary, deadline_date, course_relevance
                FROM internships 
                WHERE status = 'active' AND (course_relevance = ? OR course_relevance = 'All')
                AND deadline_date >= ?
                ORDER BY deadline_date ASC
                ''', (course, datetime.now().strftime('%Y-%m-%d')))
            else:
                # If course not found, show all active internships
                cursor.execute('''
                SELECT internship_id, title, company, location, start_date, end_date, 
                       is_paid, salary, deadline_date, course_relevance
                FROM internships 
                WHERE status = 'active' AND deadline_date >= ?
                ORDER BY deadline_date ASC
                ''', (datetime.now().strftime('%Y-%m-%d'),))
        else:
            # For staff/admin, show all internships
            cursor.execute('''
            SELECT internship_id, title, company, location, start_date, end_date, 
                   is_paid, salary, deadline_date, status, course_relevance
            FROM internships 
            ORDER BY status, deadline_date ASC
            ''')
        
        internships = cursor.fetchall()
        
        if not internships:
            print("No internships available at this time.")
            conn.close()
            return
        
        print("\nAvailable Internships:")
        print("=" * 80)
        
        for internship in internships:
            paid_status = "Paid" if internship[6] else "Unpaid"
            
            if auth.current_user['role'] == 'student':
                print(f"ID: {internship[0]}")
                print(f"Title: {internship[1]}")
                print(f"Company: {internship[2]}")
                print(f"Location: {internship[3]}")
                print(f"Duration: {internship[4]} to {internship[5]}")
                print(f"Compensation: {paid_status} - {internship[7]}")
                print(f"Application Deadline: {internship[8]}")
                print(f"Relevant for: {internship[9]}")
                
                # Check if student has already applied
                cursor.execute('''
                SELECT status FROM internship_applications
                WHERE student_id = (
                    SELECT student_id FROM users WHERE id = ?
                ) AND internship_id = ?
                ''', (auth.current_user['id'], internship[0]))
                
                application = cursor.fetchone()
                if application:
                    print(f"Application Status: {application[0]}")
                else:
                    print("Application Status: Not Applied")
            else:
                print(f"ID: {internship[0]}")
                print(f"Title: {internship[1]}")
                print(f"Company: {internship[2]}")
                print(f"Location: {internship[3]}")
                print(f"Duration: {internship[4]} to {internship[5]}")
                print(f"Compensation: {paid_status} - {internship[7]}")
                print(f"Application Deadline: {internship[8]}")
                print(f"Status: {internship[9]}")
                print(f"Relevant for: {internship[10]}")
                
                # Show number of applications for staff/admin
                cursor.execute('''
                SELECT COUNT(*) FROM internship_applications
                WHERE internship_id = ?
                ''', (internship[0],))
                
                app_count = cursor.fetchone()[0]
                print(f"Number of Applications: {app_count}")
            
            print("-" * 80)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_internship_details():
    """View detailed information about a specific internship"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view internship details.")
        return
    
    if not (auth.check_permission('view_internships') or auth.check_permission('manage_internships')):
        print("You don't have permission to view internship details.")
        return
    
    try:
        # Ask for internship ID
        internship_id = input("Enter the ID of the internship you want to view: ")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Fetch internship details
        cursor.execute('''
        SELECT * FROM internships WHERE internship_id = ?
        ''', (internship_id,))
        
        internship = cursor.fetchone()
        
        if not internship:
            print("Internship not found.")
            conn.close()
            return
        
        # Display internship details
        print("\nInternship Details:")
        print("=" * 80)
        print(f"Title: {internship[1]}")
        print(f"Company: {internship[2]}")
        print(f"Location: {internship[3]}")
        print(f"Description: {internship[4]}")
        print(f"Requirements: {internship[5]}")
        print(f"Duration: {internship[6]} to {internship[7]}")
        print(f"Compensation: {'Paid' if internship[8] else 'Unpaid'} - {internship[9]}")
        print(f"Hours per Week: {internship[10]}")
        print(f"Posted Date: {internship[11]}")
        print(f"Application Deadline: {internship[12]}")
        print(f"Status: {internship[13]}")
        print(f"Contact Email: {internship[14]}")
        print(f"Relevant for: {internship[15]}")
        
        # If staff/admin, show application statistics
        if auth.check_permission('view_all_applications'):
            cursor.execute('''
            SELECT status, COUNT(*) FROM internship_applications
            WHERE internship_id = ?
            GROUP BY status
            ''', (internship_id,))
            
            statistics = cursor.fetchall()
            
            print("\nApplication Statistics:")
            if statistics:
                for stat in statistics:
                    print(f"{stat[0]}: {stat[1]}")
            else:
                print("No applications received yet.")
        
        # If student, show application status
        elif auth.current_user['role'] == 'student':
            cursor.execute('''
            SELECT status, application_date FROM internship_applications
            WHERE student_id = (
                SELECT student_id FROM users WHERE id = ?
            ) AND internship_id = ?
            ''', (auth.current_user['id'], internship_id))
            
            application = cursor.fetchone()
            
            print("\nYour Application Status:")
            if application:
                print(f"Status: {application[0]}")
                print(f"Applied on: {application[1]}")
            else:
                print("You have not applied for this internship yet.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def apply_for_internship():
    """Apply for an internship as a student"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to apply for internships.")
        return
    
    if not auth.check_permission('apply_for_internship'):
        print("You don't have permission to apply for internships.")
        return
    
    try:
        # Get student ID
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT student_id FROM users WHERE id = ?
        ''', (auth.current_user['id'],))
        
        result = cursor.fetchone()
        
        if not result or not result[0]:
            print("Error: No student record associated with your account.")
            conn.close()
            return
        
        student_id = result[0]
        
        # Ask for internship ID
        internship_id = input("Enter the ID of the internship you want to apply for: ")
        
        # Check if internship exists and is active
        cursor.execute('''
        SELECT title, company, deadline_date, status FROM internships 
        WHERE internship_id = ? 
        ''', (internship_id,))
        
        internship = cursor.fetchone()
        
        if not internship:
            print("Internship not found.")
            conn.close()
            return
        
        if internship[3] != 'active':
            print(f"This internship is no longer active (Status: {internship[3]}).")
            conn.close()
            return
        
        # Check if deadline has passed
        today = datetime.now().strftime('%Y-%m-%d')
        if today > internship[2]:
            print(f"The application deadline ({internship[2]}) has passed.")
            conn.close()
            return
        
        # Check if already applied
        cursor.execute('''
        SELECT application_id, status FROM internship_applications
        WHERE student_id = ? AND internship_id = ?
        ''', (student_id, internship_id))
        
        existing_app = cursor.fetchone()
        
        if existing_app:
            print(f"You have already applied for this internship (Status: {existing_app[1]}).")
            conn.close()
            return
        
        # Process the application
        print(f"\nApplying for: {internship[0]} at {internship[1]}")
        
        # Get cover letter
        print("\nPlease provide a cover letter for your application:")
        cover_letter = input("Cover Letter (type or paste your text here): ")
        
        # CV handling - just store the filename for this example
        # In a real system, you would handle file uploads
        cv_filename = input("Enter the filename of your CV (e.g., my_cv.pdf): ")
        
        # Create application record
        application_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
        INSERT INTO internship_applications (
            student_id, internship_id, application_date, status, cv_filename, cover_letter
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (student_id, internship_id, application_date, 'pending', cv_filename, cover_letter))
        
        conn.commit()
        
        # Send confirmation to student
        send_application_confirmation(student_id, internship_id)
        
        print("\nApplication submitted successfully!")
        print(f"Application Date: {application_date}")
        print("Status: Pending")
        print("You will be notified when your application status changes.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def view_applications():
    """View internship applications (staff/admin or student)"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to view applications.")
        return
    
    if not (auth.check_permission('view_all_applications') or auth.check_permission('view_own_applications')):
        print("You don't have permission to view applications.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        if auth.check_permission('view_all_applications'):
            # Staff/admin view - all applications
            print("\nFilter options:")
            print("1. View all applications")
            print("2. View applications for a specific internship")
            print("3. View applications with a specific status")
            print("4. View applications for a specific student")
            
            filter_choice = input("Select a filter option (1-4): ")
            
            if filter_choice == '1':
                # All applications
                cursor.execute('''
                SELECT a.application_id, a.student_id, s.first_name, s.last_name,
                       i.title, i.company, a.application_date, a.status
                FROM internship_applications a
                JOIN students s ON a.student_id = s.student_id
                JOIN internships i ON a.internship_id = i.internship_id
                ORDER BY a.application_date DESC
                ''')
            elif filter_choice == '2':
                # Applications for specific internship
                internship_id = input("Enter internship ID: ")
                cursor.execute('''
                SELECT a.application_id, a.student_id, s.first_name, s.last_name,
                       i.title, i.company, a.application_date, a.status
                FROM internship_applications a
                JOIN students s ON a.student_id = s.student_id
                JOIN internships i ON a.internship_id = i.internship_id
                WHERE a.internship_id = ?
                ORDER BY a.application_date DESC
                ''', (internship_id,))
            elif filter_choice == '3':
                # Applications with specific status
                status = input("Enter status (pending/approved/rejected): ")
                cursor.execute('''
                SELECT a.application_id, a.student_id, s.first_name, s.last_name,
                       i.title, i.company, a.application_date, a.status
                FROM internship_applications a
                JOIN students s ON a.student_id = s.student_id
                JOIN internships i ON a.internship_id = i.internship_id
                WHERE a.status = ?
                ORDER BY a.application_date DESC
                ''', (status,))
            elif filter_choice == '4':
                # Applications for specific student
                student_id = input("Enter student ID: ")
                cursor.execute('''
                SELECT a.application_id, a.student_id, s.first_name, s.last_name,
                       i.title, i.company, a.application_date, a.status
                FROM internship_applications a
                JOIN students s ON a.student_id = s.student_id
                JOIN internships i ON a.internship_id = i.internship_id
                WHERE a.student_id = ?
                ORDER BY a.application_date DESC
                ''', (student_id,))
            else:
                print("Invalid option.")
                conn.close()
                return
            
            applications = cursor.fetchall()
            
            if not applications:
                print("No applications found with the selected filter.")
                conn.close()
                return
            
            print("\nInternship Applications:")
            print("=" * 90)
            for app in applications:
                print(f"Application ID: {app[0]}")
                print(f"Student: {app[1]} - {app[2]} {app[3]}")
                print(f"Internship: {app[4]} at {app[5]}")
                print(f"Applied on: {app[6]}")
                print(f"Status: {app[7]}")
                print("-" * 90)
        else:
            # Student view - only own applications
            cursor.execute('''
            SELECT a.application_id, i.title, i.company, a.application_date, a.status,
                   a.feedback
            FROM internship_applications a
            JOIN internships i ON a.internship_id = i.internship_id
            WHERE a.student_id = (
                SELECT student_id FROM users WHERE id = ?
            )
            ORDER BY a.application_date DESC
            ''', (auth.current_user['id'],))
            
            applications = cursor.fetchall()
            
            if not applications:
                print("You haven't applied for any internships yet.")
                conn.close()
                return
            
            print("\nYour Internship Applications:")
            print("=" * 80)
            for app in applications:
                print(f"Application ID: {app[0]}")
                print(f"Internship: {app[1]} at {app[2]}")
                print(f"Applied on: {app[3]}")
                print(f"Status: {app[4]}")
                if app[5]:
                    print(f"Feedback: {app[5]}")
                print("-" * 80)
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def review_application():
    """Review and update the status of an internship application (staff/admin)"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to review applications.")
        return
    
    if not auth.check_permission('approve_applications'):
        print("You don't have permission to review applications.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get application ID
        application_id = input("Enter the ID of the application you want to review: ")
        
        # Check if application exists
        cursor.execute('''
        SELECT a.student_id, a.internship_id, a.status, a.cv_filename, a.cover_letter,
               s.first_name, s.last_name, s.email_address, s.course,
               i.title, i.company
        FROM internship_applications a
        JOIN students s ON a.student_id = s.student_id
        JOIN internships i ON a.internship_id = i.internship_id
        WHERE a.application_id = ?
        ''', (application_id,))
        
        application = cursor.fetchone()
        
        if not application:
            print("Application not found.")
            conn.close()
            return
        
        # Display application details
        print("\nApplication Details:")
        print("=" * 80)
        print(f"Student: {application[5]} {application[6]} (ID: {application[0]})")
        print(f"Email: {application[7]}")
        print(f"Course: {application[8]}")
        print(f"Internship: {application[9]} at {application[10]} (ID: {application[1]})")
        print(f"Current Status: {application[2]}")
        print(f"CV Filename: {application[3]}")
        print("\nCover Letter:")
        print(application[4])
        print("=" * 80)
        
        # Ask for decision
        print("\nUpdate application status:")
        print("1. Approve application")
        print("2. Reject application")
        print("3. Keep as pending")
        
        choice = input("Enter your choice (1-3): ")
        
        if choice == '1':
            new_status = 'approved'
        elif choice == '2':
            new_status = 'rejected'
        elif choice == '3':
            new_status = 'pending'
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        # Add feedback
        feedback = input("Enter feedback for the student (optional): ")
        
        # Update application status
        cursor.execute('''
        UPDATE internship_applications
        SET status = ?, feedback = ?
        WHERE application_id = ?
        ''', (new_status, feedback, application_id))
        
        conn.commit()
        
        print(f"\nApplication status updated to: {new_status}")
        
        # If approved, create placement record
        if new_status == 'approved':
            # Get placement details
            print("\nEnter placement details:")
            
            supervisor_name = input("Supervisor Name: ")
            supervisor_email = input("Supervisor Email: ")
            
            # Get internship dates from the internship record
            cursor.execute('''
            SELECT start_date, end_date FROM internships
            WHERE internship_id = ?
            ''', (application[1],))
            
            dates = cursor.fetchone()
            
            # Create placement record
            cursor.execute('''
            INSERT INTO internship_placements (
                student_id, internship_id, start_date, end_date,
                supervisor_name, supervisor_email, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (application[0], application[1], dates[0], dates[1],
                  supervisor_name, supervisor_email, 'active'))
            
            conn.commit()
            
            print("\nPlacement record created successfully!")
        
        # Send notification to student
        send_internship_notification(application[0], application[1], new_status, feedback)
        
        print("\nNotification sent to student.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def create_internship():
    """Create a new internship opportunity (staff/admin)"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to create internships.")
        return
    
    if not auth.check_permission('create_internship'):
        print("You don't have permission to create internships.")
        return
    
    try:
        # Collect internship details
        print("\nEnter Internship Details:")
        print("=" * 80)
        
        title = input("Title: ")
        company = input("Company: ")
        location = input("Location: ")
        description = input("Description: ")
        requirements = input("Requirements: ")
        
        # Get start and end dates
        while True:
            try:
                start_date = input("Start Date (YYYY-MM-DD): ")
                datetime.strptime(start_date, "%Y-%m-%d")
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        while True:
            try:
                end_date = input("End Date (YYYY-MM-DD): ")
                if end_date < start_date:
                    print("End date must be after start date.")
                    continue
                datetime.strptime(end_date, "%Y-%m-%d")
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        # Get payment details
        is_paid_input = input("Is this a paid internship? (y/n): ")
        is_paid = 1 if is_paid_input.lower() == 'y' else 0
        
        salary = input("Salary/Stipend (e.g., £1500/month or 'Unpaid'): ")
        
        # Get hours per week
        while True:
            try:
                hours_per_week = int(input("Hours per Week: "))
                if hours_per_week <= 0:
                    print("Hours must be greater than 0.")
                    continue
                break
            except ValueError:
                print("Invalid input. Please enter a number.")
        
        # Set posted date to today
        posted_date = datetime.now().strftime('%Y-%m-%d')
        
        # Get application deadline
        while True:
            try:
                deadline_date = input("Application Deadline (YYYY-MM-DD): ")
                if deadline_date < posted_date:
                    print("Deadline must be in the future.")
                    continue
                datetime.strptime(deadline_date, "%Y-%m-%d")
                break
            except ValueError:
                print("Invalid date format. Please use YYYY-MM-DD.")
        
        contact_email = input("Contact Email: ")
        
        # Get course relevance
        print("\nSelect course relevance:")
        print("1. Computer Science (CS)")
        print("2. Data Science (DS)")
        print("3. Both/All Courses")
        
        relevance_choice = input("Enter your choice (1-3): ")
        if relevance_choice == '1':
            course_relevance = 'CS'
        elif relevance_choice == '2':
            course_relevance = 'DS'
        else:
            course_relevance = 'All'
        
        # Save to database
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT INTO internships (
            title, company, location, description, requirements,
            start_date, end_date, is_paid, salary, hours_per_week,
            posted_date, deadline_date, status, contact_email, course_relevance,
            created_by, created_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title, company, location, description, requirements,
            start_date, end_date, is_paid, salary, hours_per_week,
            posted_date, deadline_date, 'active', contact_email, course_relevance,
            auth.current_user['username'], datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        conn.commit()
        
        # Get the ID of the newly created internship
        internship_id = cursor.lastrowid
        
        print(f"\nInternship created successfully! ID: {internship_id}")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def edit_internship():
    """Edit an existing internship (staff/admin)"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to edit internships.")
        return
    
    if not auth.check_permission('edit_internship'):
        print("You don't have permission to edit internships.")
        return
    
    try:
        # Get internship ID
        internship_id = input("Enter the ID of the internship you want to edit: ")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if internship exists
        cursor.execute('''
        SELECT * FROM internships WHERE internship_id = ?
        ''', (internship_id,))
        
        internship = cursor.fetchone()
        
        if not internship:
            print("Internship not found.")
            conn.close()
            return
        
        # Display current details
        print("\nCurrent Internship Details:")
        print("=" * 80)
        print(f"1. Title: {internship[1]}")
        print(f"2. Company: {internship[2]}")
        print(f"3. Location: {internship[3]}")
        print(f"4. Description: {internship[4]}")
        print(f"5. Requirements: {internship[5]}")
        print(f"6. Start Date: {internship[6]}")
        print(f"7. End Date: {internship[7]}")
        print(f"8. Paid Status: {'Yes' if internship[8] else 'No'}")
        print(f"9. Salary: {internship[9]}")
        print(f"10. Hours per Week: {internship[10]}")
        print(f"11. Application Deadline: {internship[12]}")
        print(f"12. Status: {internship[13]}")
        print(f"13. Contact Email: {internship[14]}")
        print(f"14. Course Relevance: {internship[15]}")
        print("15. Cancel Edit")
        
        # Choose field to edit
        field_choice = input("\nEnter the number of the field you want to edit (1-15): ")
        
        if field_choice == '15':
            print("Edit cancelled.")
            conn.close()
            return
        
        # Collect new value based on field choice
        if field_choice == '1':
            new_value = input("New Title: ")
            field_name = 'title'
        elif field_choice == '2':
            new_value = input("New Company: ")
            field_name = 'company'
        elif field_choice == '3':
            new_value = input("New Location: ")
            field_name = 'location'
        elif field_choice == '4':
            new_value = input("New Description: ")
            field_name = 'description'
        elif field_choice == '5':
            new_value = input("New Requirements: ")
            field_name = 'requirements'
        elif field_choice == '6':
            while True:
                try:
                    new_value = input("New Start Date (YYYY-MM-DD): ")
                    datetime.strptime(new_value, "%Y-%m-%d")
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            field_name = 'start_date'
        elif field_choice == '7':
            while True:
                try:
                    new_value = input("New End Date (YYYY-MM-DD): ")
                    datetime.strptime(new_value, "%Y-%m-%d")
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            field_name = 'end_date'
        elif field_choice == '8':
            is_paid_input = input("Is this a paid internship? (y/n): ")
            new_value = 1 if is_paid_input.lower() == 'y' else 0
            field_name = 'is_paid'
        elif field_choice == '9':
            new_value = input("New Salary/Stipend: ")
            field_name = 'salary'
        elif field_choice == '10':
            while True:
                try:
                    new_value = int(input("New Hours per Week: "))
                    if new_value <= 0:
                        print("Hours must be greater than 0.")
                        continue
                    break
                except ValueError:
                    print("Invalid input. Please enter a number.")
            field_name = 'hours_per_week'
        elif field_choice == '11':
            while True:
                try:
                    new_value = input("New Application Deadline (YYYY-MM-DD): ")
                    datetime.strptime(new_value, "%Y-%m-%d")
                    break
                except ValueError:
                    print("Invalid date format. Please use YYYY-MM-DD.")
            field_name = 'deadline_date'
        elif field_choice == '12':
            print("Select new status:")
            print("1. Active")
            print("2. Closed")
            print("3. Filled")
            status_choice = input("Enter your choice (1-3): ")
            if status_choice == '1':
                new_value = 'active'
            elif status_choice == '2':
                new_value = 'closed'
            else:
                new_value = 'filled'
            field_name = 'status'
        elif field_choice == '13':
            new_value = input("New Contact Email: ")
            field_name = 'contact_email'
        elif field_choice == '14':
            print("Select new course relevance:")
            print("1. Computer Science (CS)")
            print("2. Data Science (DS)")
            print("3. Both/All Courses")
            
            relevance_choice = input("Enter your choice (1-3): ")
            if relevance_choice == '1':
                new_value = 'CS'
            elif relevance_choice == '2':
                new_value = 'DS'
            else:
                new_value = 'All'
            field_name = 'course_relevance'
        else:
            print("Invalid choice.")
            conn.close()
            return
        
        # Update the field
        cursor.execute(f'''
        UPDATE internships
        SET {field_name} = ?
        WHERE internship_id = ?
        ''', (new_value, internship_id))
        
        conn.commit()
        
        print(f"\nInternship updated successfully!")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def delete_internship():
    """Delete an internship (admin only)"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to delete internships.")
        return
    
    if not auth.check_permission('delete_internship'):
        print("You don't have permission to delete internships.")
        return
    
    try:
        # Get internship ID
        internship_id = input("Enter the ID of the internship you want to delete: ")
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if internship exists
        cursor.execute('''
        SELECT title, company FROM internships WHERE internship_id = ?
        ''', (internship_id,))
        
        internship = cursor.fetchone()
        
        if not internship:
            print("Internship not found.")
            conn.close()
            return
        
        # Check if there are applications for this internship
        cursor.execute('''
        SELECT COUNT(*) FROM internship_applications
        WHERE internship_id = ?
        ''', (internship_id,))
        
        app_count = cursor.fetchone()[0]
        
        if app_count > 0:
            print(f"Warning: This internship has {app_count} applications.")
            print("Deleting it will also delete all associated applications.")
            
            confirm = input("Are you sure you want to continue? (y/n): ")
            
            if confirm.lower() != 'y':
                print("Deletion cancelled.")
                conn.close()
                return
            
            # Delete associated applications
            cursor.execute('''
            DELETE FROM internship_applications
            WHERE internship_id = ?
            ''', (internship_id,))
            
            # Delete associated placements
            cursor.execute('''
            DELETE FROM internship_placements
            WHERE internship_id = ?
            ''', (internship_id,))
        
        # Delete the internship
        cursor.execute('''
        DELETE FROM internships
        WHERE internship_id = ?
        ''', (internship_id,))
        
        conn.commit()
        
        print(f"\nInternship '{internship[0]}' at '{internship[1]}' deleted successfully!")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def generate_internship_report():
    """Generate report on internship placements (staff/admin)"""
    global auth
    
    # Check for permissions
    if not auth or not auth.current_user:
        print("You must be logged in to generate reports.")
        return
    
    if not auth.check_permission('view_internship_reports'):
        print("You don't have permission to generate internship reports.")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        print("\nInternship Report Options:")
        print("1. Current Placements Summary")
        print("2. Application Success Rate by Course")
        print("3. Companies with Most Placements")
        print("4. Return to Previous Menu")
        
        report_choice = input("Select a report (1-4): ")
        
        if report_choice == '1':
            # Current Placements Summary
            cursor.execute('''
            SELECT i.company, i.title, COUNT(p.placement_id) as placement_count
            FROM internship_placements p
            JOIN internships i ON p.internship_id = i.internship_id
            WHERE p.status = 'active'
            GROUP BY i.company, i.title
            ORDER BY placement_count DESC
            ''')
            
            placements = cursor.fetchall()
            
            print("\nCurrent Placements Summary:")
            print("=" * 80)
            print(f"{'Company':<30} {'Internship Title':<40} {'No. of Students':<15}")
            print("-" * 80)
            
            if not placements:
                print("No active placements found.")
            else:
                for place in placements:
                    print(f"{place[0]:<30} {place[1]:<40} {place[2]:<15}")
        
        elif report_choice == '2':
            # Application Success Rate by Course
            cursor.execute('''
            SELECT s.course,
                   COUNT(a.application_id) as total_applications,
                   SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) as approved_applications,
                   ROUND(100.0 * SUM(CASE WHEN a.status = 'approved' THEN 1 ELSE 0 END) / COUNT(a.application_id), 2) as success_rate
            FROM internship_applications a
            JOIN students s ON a.student_id = s.student_id
            GROUP BY s.course
            ORDER BY success_rate DESC
            ''')
            
            rates = cursor.fetchall()
            
            print("\nApplication Success Rate by Course:")
            print("=" * 80)
            print(f"{'Course':<15} {'Total Applications':<20} {'Approved':<15} {'Success Rate (%)':<20}")
            print("-" * 80)
            
            if not rates:
                print("No application data found.")
            else:
                for rate in rates:
                    print(f"{rate[0]:<15} {rate[1]:<20} {rate[2]:<15} {rate[3]:<20}")
        
        elif report_choice == '3':
            # Companies with Most Placements
            cursor.execute('''
            SELECT i.company,
                   COUNT(p.placement_id) as placement_count,
                   GROUP_CONCAT(DISTINCT i.title) as internship_titles
            FROM internship_placements p
            JOIN internships i ON p.internship_id = i.internship_id
            GROUP BY i.company
            ORDER BY placement_count DESC
            LIMIT 10
            ''')
            
            companies = cursor.fetchall()
            
            print("\nTop Companies by Placement Count:")
            print("=" * 80)
            print(f"{'Company':<30} {'Placement Count':<20} {'Internship Titles':<40}")
            print("-" * 80)
            
            if not companies:
                print("No placement data found.")
            else:
                for company in companies:
                    # Truncate titles if too long
                    titles = company[2]
                    if len(titles) > 40:
                        titles = titles[:37] + "..."
                    
                    print(f"{company[0]:<30} {company[1]:<20} {titles:<40}")
        
        elif report_choice == '4':
            # Return to previous menu
            conn.close()
            return
        
        else:
            print("Invalid choice.")
        
        conn.close()
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def display_internship_menu():
    """Display the internship management menu"""
    global auth
    
    if not auth or not auth.current_user:
        print("You must be logged in to access the internship portal.")
        return
    
    while True:
        print("\nStudent Internship Portal")
        print("=" * 30)
        
        # Show options based on user role and permissions
        if auth.check_permission('view_internships'):
            print("1. View Available Internships")
            print("2. View Internship Details")
        
        if auth.check_permission('apply_for_internship'):
            print("3. Apply for Internship")
        
        if auth.check_permission('view_own_applications'):
            print("4. View My Applications")
        
        if auth.check_permission('manage_internships') or auth.check_permission('view_all_applications'):
            print("5. View All Applications")
            print("6. Review Application")
        
        if auth.check_permission('create_internship'):
            print("7. Create New Internship")
        
        if auth.check_permission('edit_internship'):
            print("8. Edit Internship")
        
        if auth.check_permission('delete_internship'):
            print("9. Delete Internship")
        
        if auth.check_permission('view_internship_reports'):
            print("10. Generate Internship Reports")
        
        print("0. Return to Main Menu")
        
        choice = input("\nEnter your choice: ")
        
        if choice == '1' and auth.check_permission('view_internships'):
            view_available_internships()
        elif choice == '2' and auth.check_permission('view_internships'):
            view_internship_details()
        elif choice == '3' and auth.check_permission('apply_for_internship'):
            apply_for_internship()
        elif choice == '4' and auth.check_permission('view_own_applications'):
            view_applications()
        elif choice == '5' and (auth.check_permission('manage_internships') or auth.check_permission('view_all_applications')):
            view_applications()
        elif choice == '6' and (auth.check_permission('manage_internships') or auth.check_permission('view_all_applications')):
            review_application()
        elif choice == '7' and auth.check_permission('create_internship'):
            create_internship()
        elif choice == '8' and auth.check_permission('edit_internship'):
            edit_internship()
        elif choice == '9' and auth.check_permission('delete_internship'):
            delete_internship()
        elif choice == '10' and auth.check_permission('view_internship_reports'):
            generate_internship_report()
        elif choice == '0':
            return
        else:
            print("Invalid choice or insufficient permissions. Please try again.")
