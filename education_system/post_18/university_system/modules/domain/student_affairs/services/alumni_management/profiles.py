from datetime import datetime
from education_system.post_18.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.post_18.university_system.infrastructure.email import send_alumni_welcome_email
from education_system.post_18.university_system.core.sql_safety import validate_identifier  # nosec B608
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.core import get_db_connection, safe_execute, auth
from education_system.post_18.university_system.modules.domain.student_affairs.services.alumni_management.gamification import award_engagement_points


# ALUMNI DIRECTORY & SEARCH FEATURES

def setup_alumni_directory():
    """Set up alumni directory preferences"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to set up directory preferences.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Get current user's alumni ID
    alumni_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user.get('user_id') or auth.current_user.get('id'),))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        alumni_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return

    print("\nAlumni Directory Privacy Settings")
    print("=================================")

    # Check if settings exist
    cursor.execute('SELECT * FROM alumni_directory_settings WHERE alumni_id = ?', (alumni_id,))
    existing_settings = cursor.fetchone()

    if existing_settings:
        print("Current settings:")
        print(f"Show Contact Info: {'Yes' if existing_settings[1] else 'No'}")
        print(f"Show Employment: {'Yes' if existing_settings[2] else 'No'}")
        print(f"Show Education: {'Yes' if existing_settings[3] else 'No'}")
        print(f"Searchable: {'Yes' if existing_settings[4] else 'No'}")
        print(f"Available for Networking: {'Yes' if existing_settings[5] else 'No'}")
        print(f"Available as Mentor: {'Yes' if existing_settings[6] else 'No'}")

    print("\nUpdate your directory settings:")
    show_contact = input("Show contact information in directory? (y/n): ").lower() == 'y'
    show_employment = input("Show employment information? (y/n): ").lower() == 'y'
    show_education = input("Show education information? (y/n): ").lower() == 'y'
    searchable = input("Make profile searchable? (y/n): ").lower() == 'y'
    networking_available = input("Available for networking? (y/n): ").lower() == 'y'
    mentor_available = input("Available as mentor? (y/n): ").lower() == 'y'

    # Update or insert settings
    cursor.execute('''
        INSERT OR REPLACE INTO alumni_directory_settings
        (alumni_id, show_contact_info, show_employment, show_education, searchable, networking_available, mentor_available)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, show_contact, show_employment, show_education, searchable, networking_available, mentor_available))

    conn.commit()
    conn.close()

    print("Directory settings updated successfully!")

def register_alumni():
    """Register a new alumni"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to register alumni.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to register alumni.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nRegister New Alumni")
        print("===================")

        # Generate alumni ID
        while True:
            try:
                cursor.execute('SELECT COUNT(*) FROM alumni')
                count = cursor.fetchone()[0]
                alumni_id = f"A{count + 1:06d}"  # Format: A000001, A000002, etc.

                # Check if ID already exists
                cursor.execute('SELECT alumni_id FROM alumni WHERE alumni_id = ?', (alumni_id,))
                if not cursor.fetchone():
                    break

            except sqlite3.Error as e:
                print(f"Error generating alumni ID: {e}")
                conn.close()
                return

        print(f"New Alumni ID: {alumni_id}")

        # Get student ID (optional)
        student_id = input("Student ID (if applicable, press Enter to skip): ").strip()
        if student_id:
            try:
                cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
                if not cursor.fetchone():
                    print("Warning: Student ID not found in student records.")
                    confirm = input("Continue anyway? (y/n): ").lower()
                    if confirm != 'y':
                        conn.close()
                        return
            except sqlite3.Error as e:
                print(f"Error validating student ID: {e}")

        # Personal Information
        print("\nPersonal Information:")
        title = input("Title (Mr./Ms./Dr./etc.): ").strip()

        first_name = input("First Name: ").strip()
        while not first_name:
            print("Error: First name is required.")
            first_name = input("First Name: ").strip()

        middle_name = input("Middle Name (optional): ").strip()

        last_name = input("Last Name: ").strip()
        while not last_name:
            print("Error: Last name is required.")
            last_name = input("Last Name: ").strip()

        # Email validation
        email_address = input("Email Address: ").strip()
        while not email_address or '@' not in email_address:
            print("Error: Valid email address is required.")
            email_address = input("Email Address: ").strip()

        # Check for duplicate email
        try:
            cursor.execute('SELECT alumni_id FROM alumni WHERE email_address = ?', (email_address,))
            if cursor.fetchone():
                print("Error: Email address already exists in alumni records.")
                conn.close()
                return
        except sqlite3.Error as e:
            print(f"Error checking email: {e}")

        # Gender
        gender_options = ["Male", "Female", "Other", "Prefer not to say"]
        print("\nGender Options:")
        for i, option in enumerate(gender_options, 1):
            print(f"{i}. {option}")

        while True:
            try:
                gender_choice = input("Select gender (1-4): ").strip()
                if gender_choice.isdigit() and 1 <= int(gender_choice) <= 4:
                    gender = gender_options[int(gender_choice) - 1]
                    break
                else:
                    print("Please enter a number between 1 and 4.")
            except ValueError:
                print("Please enter a valid number.")

        # Date of Birth
        while True:
            dob = input("Date of Birth (YYYY-MM-DD): ").strip()
            if not dob:
                break  # Optional field
            try:
                datetime.strptime(dob, "%Y-%m-%d")
                # Check if reasonable date
                birth_year = int(dob.split('-')[0])
                current_year = datetime.now().year
                if birth_year < 1900 or birth_year > current_year - 16:
                    print("Please enter a reasonable birth year.")
                    continue
                break
            except ValueError:
                print("Error: Invalid date format. Use YYYY-MM-DD or press Enter to skip.")

        # Academic Information
        print("\nAcademic Information:")
        while True:
            try:
                graduation_year = int(input("Graduation Year: "))
                current_year = datetime.now().year
                if graduation_year < 1900 or graduation_year > current_year + 10:
                    print("Please enter a reasonable graduation year.")
                    continue
                break
            except ValueError:
                print("Error: Please enter a valid year.")

        degree_earned = input("Degree Earned: ").strip()
        while not degree_earned:
            print("Error: Degree information is required.")
            degree_earned = input("Degree Earned: ").strip()

        # Employment Information
        print("\nEmployment Information (optional):")
        current_employer = input("Current Employer: ").strip()
        job_title = input("Job Title: ").strip()
        industry = input("Industry: ").strip()

        # Contact Information
        print("\nContact Information:")
        address = input("Address: ").strip()
        city = input("City: ").strip()
        country = input("Country: ").strip()

        phone = input("Phone Number: ").strip()
        linkedin_url = input("LinkedIn URL (optional): ").strip()

        # Additional Information
        print("\nAdditional Information (optional):")
        bio = input("Biography/Description: ").strip()
        skills = input("Skills (comma-separated): ").strip()
        achievements = input("Notable Achievements: ").strip()

        # Role assignments
        print("\nRole Assignments:")
        is_donor = input("Is this alumni a donor? (y/n): ").lower() == 'y'
        is_mentor = input("Available as mentor? (y/n): ").lower() == 'y'
        is_board_member = input("Is board member? (y/n): ").lower() == 'y'
        is_ambassador = input("Alumni ambassador? (y/n): ").lower() == 'y'

        # Privacy settings
        privacy_level = 1  # Default public
        privacy_choice = input("Privacy Level (1=Public, 2=Alumni Only, 3=Private): ").strip()
        if privacy_choice in ['1', '2', '3']:
            privacy_level = int(privacy_choice)

        # Insert alumni record
        try:
            current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            safe_execute(cursor, '''
                INSERT INTO alumni
                (alumni_id, student_id, email_address, title, first_name, middle_name,
                 last_name, gender, dob, graduation_year, degree_earned, current_employer,
                 job_title, industry, address, city, country, phone, linkedin_url,
                 date_registered, is_donor, is_mentor, is_board_member, bio, skills,
                 achievements, privacy_level, is_ambassador, engagement_score, last_activity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (alumni_id, student_id, email_address, title, first_name, middle_name,
                  last_name, gender, dob, graduation_year, degree_earned, current_employer,
                  job_title, industry, address, city, country, phone, linkedin_url,
                  current_datetime, is_donor, is_mentor, is_board_member, bio, skills,
                  achievements, privacy_level, is_ambassador, 0, current_datetime))

            # Set up default directory settings
            safe_execute(cursor, '''
                INSERT INTO alumni_directory_settings
                (alumni_id, show_contact_info, show_employment, show_education,
                 searchable, networking_available, mentor_available)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (alumni_id, True, True, True, True, True, is_mentor))

            conn.commit()

            print("\n\u2705 Alumni registered successfully!")
            print(f"Alumni ID: {alumni_id}")
            print(f"Name: {first_name} {last_name}")
            print(f"Email: {email_address}")
            print(f"Graduation Year: {graduation_year}")

            # Award initial engagement points
            award_engagement_points(alumni_id, 'profile_complete', 50)

            # Send welcome email (if email utilities are available)
            try:
                send_alumni_welcome_email(alumni_id, email_address, first_name)
                print("Welcome email sent successfully!")
            except Exception as e:
                print(f"Note: Could not send welcome email: {e}")

        except sqlite3.Error as e:
            print(f"Error inserting alumni record: {e}")
            conn.rollback()

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def view_alumni():
    """View alumni records"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view alumni records.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        print("\nView Alumni Records")
        print("===================")
        print("1. View All Alumni")
        print("2. Search by Name")
        print("3. Search by Graduation Year")
        print("4. Search by Industry")
        print("5. Search by Location")
        print("6. View Alumni Details")

        choice = input("Enter your choice: ").strip()

        alumni_list = []

        if choice == '1':
            # View all alumni (with permission check)
            if not auth.check_permission('view_alumni'):
                print("You don't have permission to view all alumni records.")
                conn.close()
                return

            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year,
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    ORDER BY last_name, first_name
                ''')
                alumni_list = cursor.fetchall()

            except sqlite3.Error as e:
                print(f"Error retrieving alumni records: {e}")
                conn.close()
                return

        elif choice == '2':
            # Search by name
            search_name = input("Enter name (partial match allowed): ").strip()
            if not search_name:
                print("Search term cannot be empty.")
                conn.close()
                return

            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year,
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE first_name LIKE ? OR last_name LIKE ?
                    ORDER BY last_name, first_name
                ''', (f'%{search_name}%', f'%{search_name}%'))
                alumni_list = cursor.fetchall()

            except sqlite3.Error as e:
                print(f"Error searching alumni: {e}")
                conn.close()
                return

        elif choice == '3':
            # Search by graduation year
            try:
                grad_year = int(input("Enter graduation year: "))

                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year,
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE graduation_year = ?
                    ORDER BY last_name, first_name
                ''', (grad_year,))
                alumni_list = cursor.fetchall()

            except ValueError:
                print("Error: Please enter a valid year.")
                conn.close()
                return
            except sqlite3.Error as e:
                print(f"Error searching by graduation year: {e}")
                conn.close()
                return

        elif choice == '4':
            # Search by industry
            industry = input("Enter industry: ").strip()
            if not industry:
                print("Industry cannot be empty.")
                conn.close()
                return

            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year,
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE industry LIKE ?
                    ORDER BY last_name, first_name
                ''', (f'%{industry}%',))
                alumni_list = cursor.fetchall()

            except sqlite3.Error as e:
                print(f"Error searching by industry: {e}")
                conn.close()
                return

        elif choice == '5':
            # Search by location
            location = input("Enter city or country: ").strip()
            if not location:
                print("Location cannot be empty.")
                conn.close()
                return

            try:
                safe_execute(cursor, '''
                    SELECT alumni_id, first_name, last_name, graduation_year,
                           current_employer, job_title, city, country, email_address
                    FROM alumni
                    WHERE city LIKE ? OR country LIKE ?
                    ORDER BY last_name, first_name
                ''', (f'%{location}%', f'%{location}%'))
                alumni_list = cursor.fetchall()

            except sqlite3.Error as e:
                print(f"Error searching by location: {e}")
                conn.close()
                return

        elif choice == '6':
            # View specific alumni details
            alumni_id = input("Enter Alumni ID: ").strip()
            if not alumni_id:
                print("Alumni ID cannot be empty.")
                conn.close()
                return

            view_alumni_details(alumni_id, cursor)
            conn.close()
            return

        else:
            print("Invalid choice.")
            conn.close()
            return

        # Display results
        if not alumni_list:
            print("No alumni found matching your criteria.")
        else:
            print(f"\nFound {len(alumni_list)} alumni:")
            print("-" * 100)
            print(f"{'ID':<8} {'Name':<25} {'Year':<6} {'Employer':<20} {'Title':<20} {'Location':<15}")
            print("-" * 100)

            for alumni in alumni_list:
                alumni_id, first_name, last_name, grad_year, employer, job_title, city, country, email = alumni

                name = f"{first_name} {last_name}"
                employer = employer or "N/A"
                job_title = job_title or "N/A"
                location = f"{city or ''}, {country or ''}".strip(', ') or "N/A"

                print(f"{alumni_id:<8} {name[:24]:<25} {grad_year:<6} {employer[:19]:<20} {job_title[:19]:<20} {location[:14]:<15}")

            print("-" * 100)

            # Option to view details
            if auth.check_permission('view_alumni'):
                view_details = input("\nWould you like to view details for a specific alumni? (y/n): ").lower()
                if view_details == 'y':
                    alumni_id = input("Enter Alumni ID: ").strip()
                    if alumni_id:
                        view_alumni_details(alumni_id, cursor)

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def view_alumni_details(alumni_id, cursor):
    """View detailed information for a specific alumni"""
    try:
        safe_execute(cursor, 'SELECT * FROM alumni WHERE alumni_id = ?', (alumni_id,))
        alumni_data = cursor.fetchone()

        if not alumni_data:
            print(f"Alumni with ID {alumni_id} not found.")
            return

        # Check privacy permissions
        privacy_level = alumni_data[18] if len(alumni_data) > 18 else 1

        current_user_id = None
        if auth and auth.current_user:
            cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user.get('user_id') or auth.current_user.get('id'),))
            result = cursor.fetchone()
            if result:
                current_user_id = result[0]

        # Privacy check
        if privacy_level == 3 and current_user_id != alumni_id and not auth.check_permission('view_alumni'):
            print("This alumni profile is private.")
            return

        print(f"\n{'='*60}")
        print(f"ALUMNI DETAILS - {alumni_data[0]}")
        print(f"{'='*60}")

        # Personal Information
        print("\nPersonal Information:")
        print(f"Name: {alumni_data[3] or ''} {alumni_data[4]} {alumni_data[5] or ''} {alumni_data[6]}")
        print(f"Email: {alumni_data[2]}")
        print(f"Gender: {alumni_data[7] or 'Not specified'}")
        print(f"Date of Birth: {alumni_data[8] or 'Not specified'}")
        print(f"Phone: {alumni_data[17] or 'Not specified'}")

        # Academic Information
        print("\nAcademic Information:")
        print(f"Student ID: {alumni_data[1] or 'Not specified'}")
        print(f"Graduation Year: {alumni_data[9]}")
        print(f"Degree: {alumni_data[10]}")

        # Employment Information
        if privacy_level <= 2 or current_user_id == alumni_id or auth.check_permission('view_alumni'):
            print("\nEmployment Information:")
            print(f"Current Employer: {alumni_data[11] or 'Not specified'}")
            print(f"Job Title: {alumni_data[12] or 'Not specified'}")
            print(f"Industry: {alumni_data[13] or 'Not specified'}")

        # Contact Information
        if privacy_level <= 1 or current_user_id == alumni_id or auth.check_permission('view_alumni'):
            print("\nContact Information:")
            print(f"Address: {alumni_data[14] or 'Not specified'}")
            print(f"City: {alumni_data[15] or 'Not specified'}")
            print(f"Country: {alumni_data[16] or 'Not specified'}")
            print(f"LinkedIn: {alumni_data[18] or 'Not specified'}")

        # Additional Information
        if len(alumni_data) > 23 and alumni_data[23]:  # bio
            print("\nBiography:")
            print(alumni_data[23])

        if len(alumni_data) > 24 and alumni_data[24]:  # skills
            print(f"\nSkills: {alumni_data[24]}")

        if len(alumni_data) > 25 and alumni_data[25]:  # achievements
            print(f"\nAchievements: {alumni_data[25]}")

        # Status Information
        print("\nStatus:")
        status_items = []
        if alumni_data[20]:  # is_donor
            status_items.append("Donor")
        if alumni_data[21]:  # is_mentor
            status_items.append("Mentor")
        if alumni_data[22]:  # is_board_member
            status_items.append("Board Member")
        if len(alumni_data) > 27 and alumni_data[27]:  # is_ambassador
            status_items.append("Ambassador")

        print(f"Roles: {', '.join(status_items) if status_items else 'None'}")
        print(f"Registration Date: {alumni_data[19]}")

        if len(alumni_data) > 28:  # engagement_score
            print(f"Engagement Score: {alumni_data[28] or 0}")

        if len(alumni_data) > 29:  # last_activity
            print(f"Last Activity: {alumni_data[29] or 'Never'}")

        print(f"{'='*60}")

    except sqlite3.Error as e:
        print(f"Error retrieving alumni details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def update_alumni():
    """Update alumni record"""
    global auth

    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to update alumni records.")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Determine which alumni record to update
        if auth.check_permission("manage_alumni"):
            alumni_id = input("Enter Alumni ID to update: ").strip()
            if not alumni_id:
                print("Alumni ID cannot be empty.")
                conn.close()
                return
        else:
            cursor.execute("SELECT username FROM users WHERE id = ?", (auth.current_user["id"],))
            result = cursor.fetchone()
            if result and result[0].startswith("A"):
                alumni_id = result[0]
            else:
                print("You do not have permission to update this alumni record.")
                conn.close()
                return

        # Fetch current data
        cursor.execute("SELECT * FROM alumni WHERE alumni_id = ?", (alumni_id,))
        current_data = cursor.fetchone()
        if not current_data:
            print(f"No alumni found with ID {alumni_id}")
            conn.close()
            return

        # Map current_data to a list for index access if needed
        updates = {}

        def prompt_bool(field_name, current_value, prompt_text):
            new = input(f"{prompt_text} (current: {current_value}) (y/n): ").strip().lower()
            if new in ("y", "n"):
                return new == "y"
            return None

        # Example of updating flags
        if len(current_data) > 20:
            current_donor = current_data[20]
            new_donor = prompt_bool("is_donor", current_donor, "Is Donor")
            if new_donor is not None:
                updates["is_donor"] = new_donor

            current_mentor = current_data[21]
            new_mentor = prompt_bool("is_mentor", current_mentor, "Is Mentor")
            if new_mentor is not None:
                updates["is_mentor"] = new_mentor

            current_board = current_data[22]
            new_board = prompt_bool("is_board_member", current_board, "Is Board Member")
            if new_board is not None:
                updates["is_board_member"] = new_board

            if len(current_data) > 27:
                current_ambassador = current_data[27]
                new_ambassador = prompt_bool("is_ambassador", current_ambassador, "Is Ambassador")
                if new_ambassador is not None:
                    updates["is_ambassador"] = new_ambassador

        if not updates:
            print("No changes made.")
            conn.close()
            return

        # Build update query safely
        _ALLOWED_COLUMNS = frozenset({
            'is_donor', 'is_mentor', 'is_board_member', 'is_ambassador',
            'first_name', 'last_name', 'email', 'phone', 'address',
            'city', 'state', 'country', 'graduation_year', 'degree',
            'major', 'employer', 'job_title', 'industry', 'linkedin_url',
        })
        set_clauses = []
        values = []
        for field, value in updates.items():
            if field not in _ALLOWED_COLUMNS:
                raise ValueError(f"Invalid column name: {field}")
            set_clauses.append(f"{validate_identifier(field, 'column')} = ?")
            values.append(value)
        values.append(alumni_id)
        query = f"UPDATE alumni SET {', '.join(set_clauses)} WHERE alumni_id = ?"
        try:
            cursor.execute(query, tuple(values))
            conn.commit()
            print(f"Updated alumni {alumni_id}: {', '.join(updates.keys())}")
        except Exception as e:
            print(f"Failed to update alumni: {e}")
            conn.rollback()
        finally:
            conn.close()

    except Exception as exc:
        print(f"Unexpected error in update_alumni: {exc}")
