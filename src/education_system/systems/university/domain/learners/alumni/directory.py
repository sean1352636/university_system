from datetime import datetime
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.email.email_service import send_email
from education_system.systems.university.infrastructure.email.template_utils import load_template, render_template
from education_system.systems.university.domain.learners.alumni.core import get_db_connection, auth
from education_system.systems.university.domain.learners.alumni.gamification import award_engagement_points


def update_business_listing():
    """Update existing business listing"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to update business listings.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Find user's existing listings
        cursor.execute('''
            SELECT listing_id, business_name, category, description
            FROM alumni_business_listings
            WHERE user_id = ?
        ''', (auth.current_user['user_id'],))

        listings = cursor.fetchall()

        if not listings:
            print("\nYou don't have any business listings yet.")
            conn.close()
            return

        print("\n--- Your Business Listings ---")
        for i, listing in enumerate(listings, 1):
            print(f"{i}. {listing[1]} ({listing[2]})")

        choice = input("\nEnter listing number to update (or 0 to cancel): ")
        if not choice.isdigit() or not (0 < int(choice) <= len(listings)):
            print("Invalid choice.")
            conn.close()
            return

        selected = listings[int(choice) - 1]
        listing_id = selected[0]

        print(f"\nUpdating: {selected[1]}")
        new_name = input(f"New business name (current: {selected[1]}, press Enter to skip): ")
        new_category = input(f"New category (current: {selected[2]}, press Enter to skip): ")
        new_description = input(f"New description (current: {selected[3]}, press Enter to skip): ")

        if new_name:
            cursor.execute('UPDATE alumni_business_listings SET business_name = ? WHERE listing_id = ?', (new_name, listing_id))
        if new_category:
            cursor.execute('UPDATE alumni_business_listings SET category = ? WHERE listing_id = ?', (new_category, listing_id))
        if new_description:
            cursor.execute('UPDATE alumni_business_listings SET description = ? WHERE listing_id = ?', (new_description, listing_id))

        cursor.execute('UPDATE alumni_business_listings SET updated_date = ? WHERE listing_id = ?',
                      (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), listing_id))

        conn.commit()
        conn.close()
        print("Business listing updated successfully!")
    except Exception as e:
        print(f"Error updating business listing: {e}")


def search_alumni_directory():
    """Advanced alumni directory search"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to search the alumni directory.")
        return

    if not auth.check_permission('access_alumni_directory'):
        print("You don't have permission to access the alumni directory.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nAlumni Directory Search")
    print("=======================")
    print("1. Search by name")
    print("2. Search by graduation year")
    print("3. Search by industry")
    print("4. Search by location")
    print("5. Search by skills")
    print("6. Advanced search")

    choice = input("Select search type: ")

    if choice == '1':
        # Search by name
        name = input("Enter name (partial match allowed): ")
        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND (a.first_name LIKE ? OR a.last_name LIKE ?)
            ORDER BY a.last_name, a.first_name
        ''', (f'%{name}%', f'%{name}%'))

    elif choice == '2':
        # Search by graduation year
        try:
            year = int(input("Enter graduation year: "))
            cursor.execute('''
                SELECT a.*, ads.* FROM alumni a
                LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
                WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
                AND a.graduation_year = ?
                ORDER BY a.last_name, a.first_name
            ''', (year,))
        except ValueError:
            print("Invalid year format.")
            conn.close()
            return

    elif choice == '3':
        # Search by industry
        industry = input("Enter industry: ")
        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND a.industry LIKE ?
            ORDER BY a.last_name, a.first_name
        ''', (f'%{industry}%',))

    elif choice == '4':
        # Search by location
        location = input("Enter city or country: ")
        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND (a.city LIKE ? OR a.country LIKE ?)
            ORDER BY a.last_name, a.first_name
        ''', (f'%{location}%', f'%{location}%'))

    elif choice == '5':
        # Search by skills
        skills = input("Enter skills (comma-separated): ")
        skill_list = [skill.strip() for skill in skills.split(',')]
        skill_conditions = " OR ".join(["a.skills LIKE ?" for _ in skill_list])
        skill_params = [f'%{skill}%' for skill in skill_list]

        cursor.execute('''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE (ads.searchable = 1 OR ads.searchable IS NULL)
            AND (''' + skill_conditions + ''')
            ORDER BY a.last_name, a.first_name
        ''', skill_params)

    elif choice == '6':
        # Advanced search
        print("\nAdvanced Search - Enter criteria (leave blank to skip):")
        name = input("Name: ")
        year_from = input("Graduation year from: ")
        year_to = input("Graduation year to: ")
        industry = input("Industry: ")
        location = input("Location: ")
        company = input("Company: ")

        # Build dynamic query
        conditions = ["(ads.searchable = 1 OR ads.searchable IS NULL)"]
        params = []

        if name:
            conditions.append("(a.first_name LIKE ? OR a.last_name LIKE ?)")
            params.extend([f'%{name}%', f'%{name}%'])

        if year_from:
            try:
                year_from = int(year_from)
                conditions.append("a.graduation_year >= ?")
                params.append(year_from)
            except ValueError:
                pass

        if year_to:
            try:
                year_to = int(year_to)
                conditions.append("a.graduation_year <= ?")
                params.append(year_to)
            except ValueError:
                pass

        if industry:
            conditions.append("a.industry LIKE ?")
            params.append(f'%{industry}%')

        if location:
            conditions.append("(a.city LIKE ? OR a.country LIKE ?)")
            params.extend([f'%{location}%', f'%{location}%'])

        if company:
            conditions.append("a.current_employer LIKE ?")
            params.append(f'%{company}%')

        query = f'''
            SELECT a.*, ads.* FROM alumni a
            LEFT JOIN alumni_directory_settings ads ON a.alumni_id = ads.alumni_id
            WHERE {" AND ".join(conditions)}
            ORDER BY a.last_name, a.first_name
        '''

        cursor.execute(query, params)
    else:
        print("Invalid choice.")
        conn.close()
        return

    results = cursor.fetchall()

    if not results:
        print("No alumni found matching your search criteria.")
    else:
        print(f"\nFound {len(results)} alumni:")
        print("-" * 80)

        for i, alumni in enumerate(results, 1):
            settings = alumni[23:] if len(alumni) > 23 else [1, 1, 1, 1, 1, 0]  # Default settings

            print(f"{i}. {alumni[4]} {alumni[6]} ({alumni[0]})")
            print(f"   Graduated: {alumni[9]} - {alumni[10]}")

            if len(settings) > 2 and settings[2]:  # show_employment
                print(f"   Current: {alumni[12]} at {alumni[11]}")
                print(f"   Industry: {alumni[13]}")

            if len(settings) > 1 and settings[1]:  # show_contact_info
                print(f"   Location: {alumni[15]}, {alumni[16]}")
                print(f"   Email: {alumni[2]}")

            if len(settings) > 5 and settings[5]:  # mentor_available
                print("   Available as Mentor")

            if len(settings) > 4 and settings[4]:  # networking_available
                print("   Available for Networking")

            print("-" * 80)

        # Option to connect with someone
        if auth.check_permission('access_alumni_directory'):
            connect_choice = input("\nWould you like to send a connection request to someone? (y/n): ").lower()
            if connect_choice == 'y':
                try:
                    selection = int(input(f"Enter number (1-{len(results)}): "))
                    if 1 <= selection <= len(results):
                        selected_alumni = results[selection - 1]
                        send_connection_request(selected_alumni[0])  # alumni_id
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Invalid input.")

    conn.close()

def send_connection_request(recipient_id):
    """Send a networking connection request"""
    global auth

    conn = get_connection()
    cursor = conn.cursor()

    # Get current user's alumni ID
    requester_id = None
    cursor.execute('SELECT username FROM users WHERE id = ?', (auth.current_user['id'],))
    result = cursor.fetchone()
    if result and result[0].startswith('A'):
        requester_id = result[0]
    else:
        print("Alumni profile not found for current user.")
        conn.close()
        return

    if requester_id == recipient_id:
        print("You cannot send a connection request to yourself.")
        conn.close()
        return

    # Check if connection already exists
    cursor.execute('''
        SELECT * FROM networking_connections
        WHERE (requester_id = ? AND recipient_id = ?) OR (requester_id = ? AND recipient_id = ?)
    ''', (requester_id, recipient_id, recipient_id, requester_id))

    existing_connection = cursor.fetchone()
    if existing_connection:
        print("A connection request already exists between you and this alumni.")
        conn.close()
        return

    # Get recipient info
    cursor.execute('SELECT first_name, last_name, email_address FROM alumni WHERE alumni_id = ?', (recipient_id,))
    recipient_info = cursor.fetchone()
    if not recipient_info:
        print("Recipient not found.")
        conn.close()
        return

    recipient_name = f"{recipient_info[0]} {recipient_info[1]}"
    recipient_email = recipient_info[2]

    # Get requester info for email notification
    cursor.execute('''
        SELECT first_name, last_name, graduation_year, current_employer, job_title
        FROM alumni WHERE alumni_id = ?
    ''', (requester_id,))
    requester_info = cursor.fetchone()
    requester_name = f"{requester_info[0]} {requester_info[1]}" if requester_info else "A fellow alumni"
    requester_grad_year = requester_info[2] if requester_info else "N/A"
    requester_employer = requester_info[3] if requester_info and requester_info[3] else "Not specified"
    requester_job_title = requester_info[4] if requester_info and requester_info[4] else "Not specified"

    message = input(f"Enter a message for {recipient_name} (optional): ")

    # Insert connection request
    cursor.execute('''
        INSERT INTO networking_connections (requester_id, recipient_id, connection_date, status, message)
        VALUES (?, ?, ?, ?, ?)
    ''', (requester_id, recipient_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending', message))

    conn.commit()
    conn.close()

    print(f"Connection request sent to {recipient_name}!")

    # Send email notification to recipient
    if recipient_email:
        try:
            template = load_template('alumni/alumni_connection_request')
            if template:
                # Build personal message section
                personal_message_section = ""
                if message and message.strip():
                    personal_message_section = f"Personal Message:\n\"{message}\"\n"

                template_vars = {
                    'recipient_name': recipient_name,
                    'requester_name': requester_name,
                    'requester_grad_year': str(requester_grad_year),
                    'requester_employer': requester_employer,
                    'requester_job_title': requester_job_title,
                    'personal_message_section': personal_message_section
                }

                subject, body = render_template('alumni_connection_request', template_vars)
                if subject and body:
                    send_email(recipient_email, subject, body)
                    print("Email notification sent to recipient.")
        except Exception as e:
            print(f"Note: Could not send email notification: {e}")

def view_connection_requests():
    """View and manage connection requests"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view connection requests.")
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

    print("\nConnection Requests")
    print("===================")

    # Get pending requests received
    cursor.execute('''
        SELECT nc.*, a.first_name, a.last_name, a.current_employer, a.job_title
        FROM networking_connections nc
        JOIN alumni a ON nc.requester_id = a.alumni_id
        WHERE nc.recipient_id = ? AND nc.status = 'pending'
        ORDER BY nc.connection_date DESC
    ''', (alumni_id,))

    pending_requests = cursor.fetchall()

    if pending_requests:
        print("\nPending Requests Received:")
        for i, request in enumerate(pending_requests, 1):
            requester_name = f"{request[6]} {request[7]}"
            job_info = f"{request[9]} at {request[8]}" if request[8] else "No employment info"
            print(f"{i}. From: {requester_name}")
            print(f"   {job_info}")
            print(f"   Date: {request[3]}")
            if request[5]:  # message
                print(f"   Message: {request[5]}")
            print()

        # Handle requests
        handle_choice = input("Would you like to respond to any requests? (y/n): ").lower()
        if handle_choice == 'y':
            try:
                selection = int(input(f"Enter request number (1-{len(pending_requests)}): "))
                if 1 <= selection <= len(pending_requests):
                    selected_request = pending_requests[selection - 1]
                    action = input("Accept (a) or Decline (d) this request: ").lower()

                    if action == 'a':
                        cursor.execute('''
                            UPDATE networking_connections
                            SET status = 'accepted'
                            WHERE connection_id = ?
                        ''', (selected_request[0],))
                        print("Connection request accepted!")

                        # Award engagement points
                        award_engagement_points(alumni_id, 'connection_made', 10)
                        award_engagement_points(selected_request[1], 'connection_made', 10)

                    elif action == 'd':
                        cursor.execute('''
                            UPDATE networking_connections
                            SET status = 'declined'
                            WHERE connection_id = ?
                        ''', (selected_request[0],))
                        print("Connection request declined.")
                    else:
                        print("Invalid choice.")
                else:
                    print("Invalid selection.")
            except ValueError:
                print("Invalid input.")
    else:
        print("No pending connection requests.")

    # Show sent requests
    cursor.execute('''
        SELECT nc.*, a.first_name, a.last_name
        FROM networking_connections nc
        JOIN alumni a ON nc.recipient_id = a.alumni_id
        WHERE nc.requester_id = ?
        ORDER BY nc.connection_date DESC
    ''', (alumni_id,))

    sent_requests = cursor.fetchall()

    if sent_requests:
        print("\nRequests You've Sent:")
        for request in sent_requests:
            recipient_name = f"{request[6]} {request[7]}"
            status_color = {"pending": "?", "accepted": "OK", "declined": "X"}
            print(f"{status_color.get(request[4], '?')} To: {recipient_name} - Status: {request[4]} ({request[3]})")

    conn.commit()
    conn.close()


def manage_business_directory():
    """Manage alumni business directory"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to access the business directory.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nAlumni Business Directory")
    print("=========================")
    print("1. View Business Directory")
    print("2. Add My Business")
    print("3. Update My Business")
    print("4. Search Businesses")

    choice = input("Enter your choice: ")

    if choice == '1':
        view_business_directory(cursor)
    elif choice == '2':
        add_business_listing(cursor)
    elif choice == '3':
        update_business_listing(cursor)
    elif choice == '4':
        search_business_directory(cursor)
    else:
        print("Invalid choice.")

    conn.close()

def view_business_directory(cursor):
    """View all business listings"""
    cursor.execute('''
        SELECT b.*, a.first_name, a.last_name
        FROM business_directory b
        JOIN alumni a ON b.alumni_id = a.alumni_id
        ORDER BY b.business_name
    ''')

    businesses = cursor.fetchall()

    if not businesses:
        print("No businesses found in the directory.")
        return

    print(f"\nAlumni Business Directory ({len(businesses)} businesses):")
    print("-" * 80)

    for business in businesses:
        owner_name = f"{business[10]} {business[11]}"

        print(f"Business: {business[2]}")
        print(f"Owner: {owner_name}")
        print(f"Industry: {business[4]}")
        print(f"Location: {business[8]}")
        print(f"Description: {business[3][:100]}...")
        if business[5]:  # website
            print(f"Website: {business[5]}")
        if business[7]:  # services_offered
            print(f"Services: {business[7][:80]}...")
        print("-" * 80)

def add_business_listing(cursor):
    """Add a new business listing"""
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

    # Check if business already exists
    cursor.execute('SELECT * FROM business_directory WHERE alumni_id = ?', (alumni_id,))
    if cursor.fetchone():
        print("You already have a business listing. Use 'Update My Business' to modify it.")
        return

    print("\nAdd Business Listing")
    print("====================")

    business_name = input("Business Name: ")
    while not business_name:
        print("Error: Business name is required.")
        business_name = input("Business Name: ")

    business_description = input("Business Description: ")

    # Industry selection
    industries = [
        "Technology", "Healthcare", "Finance", "Education", "Manufacturing",
        "Retail", "Real Estate", "Legal Services", "Consulting", "Marketing",
        "Construction", "Hospitality", "Transportation", "Entertainment",
        "Non-profit", "Other"
    ]

    print("\nIndustries:")
    for i, industry in enumerate(industries, 1):
        print(f"{i}. {industry}")

    try:
        industry_choice = int(input("Select industry: "))
        if 1 <= industry_choice <= len(industries):
            industry = industries[industry_choice - 1]
        else:
            industry = "Other"
    except ValueError:
        industry = "Other"

    website = input("Website URL (optional): ")
    contact_email = input("Contact Email: ")

    print("\nServices Offered (press Enter twice to finish):")
    services_lines = []
    while True:
        line = input()
        if line == "" and (not services_lines or services_lines[-1] == ""):
            break
        services_lines.append(line)
    services_offered = "\n".join(services_lines)

    location = input("Business Location (city, state/country): ")

    # Insert business listing
    cursor.execute('''
        INSERT INTO business_directory
        (alumni_id, business_name, business_description, industry, website,
         contact_email, services_offered, location, created_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (alumni_id, business_name, business_description, industry, website,
          contact_email, services_offered, location,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

    # Award engagement points
    award_engagement_points(alumni_id, 'business_listed', 25)

    print("Business listing added successfully to the alumni directory!")

def search_business_directory(cursor):
    """Search business directory"""
    print("\nSearch Business Directory")
    print("=========================")
    print("1. Search by Industry")
    print("2. Search by Location")
    print("3. Search by Business Name")
    print("4. Search by Services")

    choice = input("Enter your choice: ")

    if choice == '1':
        # Search by industry
        industry = input("Enter industry: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.industry LIKE ?
            ORDER BY b.business_name
        ''', (f'%{industry}%',))

    elif choice == '2':
        # Search by location
        location = input("Enter location: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.location LIKE ?
            ORDER BY b.business_name
        ''', (f'%{location}%',))

    elif choice == '3':
        # Search by business name
        name = input("Enter business name: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.business_name LIKE ?
            ORDER BY b.business_name
        ''', (f'%{name}%',))

    elif choice == '4':
        # Search by services
        services = input("Enter services/keywords: ")
        cursor.execute('''
            SELECT b.*, a.first_name, a.last_name
            FROM business_directory b
            JOIN alumni a ON b.alumni_id = a.alumni_id
            WHERE b.services_offered LIKE ? OR b.business_description LIKE ?
            ORDER BY b.business_name
        ''', (f'%{services}%', f'%{services}%'))
    else:
        print("Invalid choice.")
        return

    results = cursor.fetchall()

    if not results:
        print("No businesses found matching your search criteria.")
    else:
        print(f"\nFound {len(results)} businesses:")
        print("-" * 80)

        for business in results:
            owner_name = f"{business[10]} {business[11]}"

            print(f"Business: {business[2]}")
            print(f"Owner: {owner_name}")
            print(f"Industry: {business[4]}")
            print(f"Location: {business[8]}")
            if business[5]:  # website
                print(f"Website: {business[5]}")
            if business[6]:  # contact_email
                print(f"Contact: {business[6]}")
            print("-" * 80)
