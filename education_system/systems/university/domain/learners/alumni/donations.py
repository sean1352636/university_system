from datetime import datetime
from education_system.systems.university.infrastructure.database.db import sqlite3, get_connection
from education_system.systems.university.infrastructure.email import send_donation_receipt
from education_system.systems.university.infrastructure.utils.finance_integration import record_revenue_to_finance
from education_system.systems.university.domain.learners.alumni.core import get_db_connection, safe_execute, auth


def record_donation():
    """Record a donation"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to record a donation.")
        return

    try:
        amount = float(input("Enter donation amount: $"))
        purpose = input("Enter donation purpose (scholarship/infrastructure/general): ") or "general"

        conn = get_db_connection()
        cursor = conn.cursor()

        donation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO alumni_donations (user_id, amount, purpose, donation_date, payment_status)
            VALUES (?, ?, ?, ?, 'completed')
        ''', (auth.current_user['user_id'], amount, purpose, donation_date))

        donation_id = cursor.lastrowid
        conn.commit()

        # Record donation to central finance system
        finance_payment_id = record_revenue_to_finance(
            student_id=auth.current_user.get('username', 'EXTERNAL'),
            amount=amount,
            revenue_category='Donation',
            transaction_source='Alumni',
            transaction_ref=f'DONATION-{donation_id}',
            payment_method='Various',
            notes=f'Alumni donation for {purpose}'
        )

        print(f"Donation of £{amount:.2f} recorded successfully. Thank you for your generosity!")
        if finance_payment_id:
            print(f"Finance System Payment ID: {finance_payment_id}")

        # Automatically send donation receipt email
        try:
            # Get alumni ID and email from current user
            cursor.execute('''
                SELECT ap.alumni_id, ap.email
                FROM alumni_profiles ap
                JOIN users u ON ap.alumni_id = u.username
                WHERE u.id = ?
            ''', (auth.current_user['user_id'],))

            result = cursor.fetchone()
            if result:
                alumni_id, email = result
                send_donation_receipt(
                    alumni_id=alumni_id,
                    donation_id=donation_id,
                    email_address=email,
                    amount=amount,
                    donation_date=donation_date,
                    purpose=purpose
                )
                print("\u2709\ufe0f  Donation receipt sent to your email")
            else:
                print("\u26a0\ufe0f  Could not send receipt: Alumni profile not found")
        except Exception as e:
            print(f"\u26a0\ufe0f  Could not send donation receipt email: {e}")

        conn.close()
    except ValueError:
        print("Invalid amount entered.")
    except Exception as e:
        print(f"Error recording donation: {e}")

def view_donations():
    """View donations"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to view donations.")
        return

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT donation_id, amount, purpose, donation_date, payment_status
            FROM alumni_donations
            WHERE user_id = ?
            ORDER BY donation_date DESC
        ''', (auth.current_user['user_id'],))

        donations = cursor.fetchall()
        conn.close()

        if not donations:
            print("\nNo donations found.")
            return

        print("\n--- Your Donations ---")
        print(f"{'ID':<10} {'Amount':<12} {'Purpose':<20} {'Date':<20} {'Status':<15}")
        print("-" * 80)
        for donation in donations:
            print(f"{donation[0]:<10} £{donation[1]:<11.2f} {donation[2]:<20} {donation[3]:<20} {donation[4]:<15}")

        total = sum(d[1] for d in donations)
        print(f"\nTotal donations: £{total:.2f}")
    except Exception as e:
        print(f"Error viewing donations: {e}")

def manage_campaigns():
    """Manage fundraising campaigns"""
    global auth
    if not auth or not auth.current_user:
        print("You must be logged in to manage campaigns.")
        return

    if not auth.check_permission('manage_alumni'):
        print("You don't have permission to manage campaigns.")
        return

    try:
        print("\n--- Manage Fundraising Campaigns ---")
        print("1. Create New Campaign")
        print("2. View All Campaigns")
        print("3. Update Campaign")
        print("4. View Campaign Progress")
        choice = input("Enter your choice (1-4): ")

        conn = get_db_connection()
        cursor = conn.cursor()

        if choice == '1':
            name = input("Enter campaign name: ")
            goal = float(input("Enter fundraising goal: $"))
            end_date = input("Enter end date (YYYY-MM-DD): ")
            description = input("Enter description: ")

            cursor.execute('''
                INSERT INTO alumni_campaigns (name, goal, current_amount, end_date, description, status, created_date)
                VALUES (?, ?, 0, ?, ?, 'active', ?)
            ''', (name, goal, end_date, description, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            print("Campaign created successfully!")

        elif choice == '2':
            cursor.execute('''
                SELECT campaign_id, name, goal, current_amount, end_date, status
                FROM alumni_campaigns
                ORDER BY created_date DESC
            ''')
            campaigns = cursor.fetchall()

            print("\n--- All Campaigns ---")
            print(f"{'Campaign ID':<15} {'Name':<25} {'Goal':<12} {'Current':<12} {'End Date':<15} {'Status':<12}")
            print("-" * 95)
            for campaign in campaigns:
                progress = (campaign[3] / campaign[2] * 100) if campaign[2] > 0 else 0
                print(f"{campaign[0]:<15} {campaign[1]:<25} £{campaign[2]:<11.2f} £{campaign[3]:<11.2f} {campaign[4]:<15} {campaign[5]:<12}")

        elif choice == '3':
            campaign_id = input("Enter campaign ID to update: ")
            new_goal = input("Enter new goal (or press Enter to skip): ")
            new_status = input("Enter new status (active/completed/cancelled, or press Enter to skip): ")

            if new_goal:
                cursor.execute('UPDATE alumni_campaigns SET goal = ? WHERE campaign_id = ?', (float(new_goal), campaign_id))
            if new_status:
                cursor.execute('UPDATE alumni_campaigns SET status = ? WHERE campaign_id = ?', (new_status, campaign_id))

            conn.commit()
            print("Campaign updated successfully!")

        elif choice == '4':
            campaign_id = input("Enter campaign ID: ")
            cursor.execute('''
                SELECT name, goal, current_amount, end_date, status
                FROM alumni_campaigns
                WHERE campaign_id = ?
            ''', (campaign_id,))
            campaign = cursor.fetchone()

            if campaign:
                progress = (campaign[2] / campaign[1] * 100) if campaign[1] > 0 else 0
                print("\n--- Campaign Progress ---")
                print(f"Name: {campaign[0]}")
                print(f"Goal: £{campaign[1]:.2f}")
                print(f"Current Amount: £{campaign[2]:.2f}")
                print(f"Progress: {progress:.1f}%")
                print(f"End Date: {campaign[3]}")
                print(f"Status: {campaign[4]}")
            else:
                print("Campaign not found.")

        conn.close()
    except ValueError:
        print("Invalid input.")
    except Exception as e:
        print(f"Error managing campaigns: {e}")

def create_fundraising_campaign():
    """Create a new fundraising campaign"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create fundraising campaigns.")
        return

    if not auth.check_permission('manage_campaigns'):
        print("You don't have permission to create fundraising campaigns.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nCreate Fundraising Campaign")
    print("===========================")

    campaign_name = input("Campaign Name: ")
    while not campaign_name:
        print("Error: Campaign name is required.")
        campaign_name = input("Campaign Name: ")

    description = input("Campaign Description: ")

    # Goal amount
    while True:
        try:
            goal_amount = float(input("Goal Amount ($): "))
            if goal_amount <= 0:
                print("Error: Goal amount must be greater than zero.")
                continue
            break
        except ValueError:
            print("Error: Please enter a valid amount.")

    # Campaign dates
    start_date = input("Start Date (YYYY-MM-DD, press Enter for today): ")
    if not start_date:
        start_date = datetime.now().strftime('%Y-%m-%d')
    else:
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
        except ValueError:
            print("Invalid date format, using today.")
            start_date = datetime.now().strftime('%Y-%m-%d')

    end_date = input("End Date (YYYY-MM-DD): ")
    while True:
        try:
            end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')
            start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
            if end_date_obj <= start_date_obj:
                print("Error: End date must be after start date.")
                end_date = input("End Date (YYYY-MM-DD): ")
                continue
            break
        except ValueError:
            print("Error: Invalid date format.")
            end_date = input("End Date (YYYY-MM-DD): ")

    # Campaign categories
    categories = [
        "Annual Fund", "Scholarship Fund", "Building Fund", "Research Fund",
        "Athletics Fund", "Library Fund", "Emergency Fund", "Endowment",
        "Student Support", "Faculty Support", "Infrastructure", "Other"
    ]

    print("\nCampaign Categories:")
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

    is_featured = input("Feature this campaign on the main page? (y/n): ").lower() == 'y'

    # Insert campaign
    cursor.execute('''
        INSERT INTO fundraising_campaigns
        (campaign_name, description, goal_amount, start_date, end_date,
         created_by, created_date, category, is_featured)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (campaign_name, description, goal_amount, start_date, end_date,
          auth.current_user['username'], datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
          category, is_featured))

    campaign_id = cursor.lastrowid

    conn.commit()
    conn.close()

    print("\nFundraising campaign created successfully!")
    print(f"Campaign ID: {campaign_id}")
    print(f"Goal: £{goal_amount:,.2f}")
    print(f"Duration: {start_date} to {end_date}")

def view_fundraising_campaigns():
    """View and manage fundraising campaigns"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to view campaigns.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nFundraising Campaigns")
    print("=====================")
    print("1. View Active Campaigns")
    print("2. View All Campaigns")
    print("3. Campaign Performance")
    if auth.check_permission('manage_campaigns'):
        print("4. Manage Campaigns")

    choice = input("Enter your choice: ")

    if choice == '1':
        # Active campaigns
        cursor.execute('''
            SELECT * FROM fundraising_campaigns
            WHERE status = 'active' AND end_date >= date('now')
            ORDER BY is_featured DESC, created_date DESC
        ''')

    elif choice == '2':
        # All campaigns
        cursor.execute('''
            SELECT * FROM fundraising_campaigns
            ORDER BY created_date DESC
        ''')

    elif choice == '3':
        # Campaign performance
        view_campaign_performance(cursor)
        conn.close()
        return

    elif choice == '4' and auth.check_permission('manage_campaigns'):
        # Manage campaigns
        manage_campaigns(cursor)
        conn.close()
        return
    else:
        print("Invalid choice.")
        conn.close()
        return

    campaigns = cursor.fetchall()

    if not campaigns:
        print("No campaigns found.")
    else:
        print(f"\nFound {len(campaigns)} campaigns:")
        print("-" * 80)

        for campaign in campaigns:
            progress_percentage = (campaign[4] / campaign[3] * 100) if campaign[3] > 0 else 0

            print(f"Campaign: {campaign[1]}")
            print(f"Goal: £{campaign[3]:,.2f} | Raised: £{campaign[4]:,.2f} ({progress_percentage:.1f}%)")
            print(f"Period: {campaign[5]} to {campaign[6]}")
            print(f"Category: {campaign[9]} | Status: {campaign[8]}")
            if campaign[10]:  # is_featured
                print("\u2b50 FEATURED CAMPAIGN")
            print(f"Description: {campaign[2][:100]}...")
            print("-" * 80)

    conn.close()

def view_campaign_performance(cursor):
    """View detailed campaign performance analytics"""
    # Get campaign performance data
    cursor.execute('''
        SELECT
            fc.campaign_id,
            fc.campaign_name,
            fc.goal_amount,
            fc.current_amount,
            COUNT(d.donation_id) as total_donations,
            AVG(d.amount) as avg_donation,
            MAX(d.amount) as largest_donation,
            COUNT(DISTINCT d.alumni_id) as unique_donors
        FROM fundraising_campaigns fc
        LEFT JOIN donations d ON fc.campaign_id = d.campaign_id
        GROUP BY fc.campaign_id
        ORDER BY fc.current_amount DESC
    ''')

    performance_data = cursor.fetchall()

    if not performance_data:
        print("No campaign performance data available.")
        return

    print("\nCampaign Performance Report")
    print("===========================")

    for data in performance_data:
        campaign_id, name, goal, current, total_donations, avg_donation, largest, unique_donors = data
        progress = (current / goal * 100) if goal > 0 else 0

        print(f"\nCampaign: {name}")
        print(f"Progress: £{current:,.2f} / £{goal:,.2f} ({progress:.1f}%)")
        print(f"Total Donations: {total_donations}")
        print(f"Unique Donors: {unique_donors}")
        if avg_donation:
            print(f"Average Donation: £{avg_donation:.2f}")
        if largest:
            print(f"Largest Donation: £{largest:.2f}")

        # Progress bar
        bar_length = 40
        filled_length = int(bar_length * progress / 100)
        bar = '\u2588' * filled_length + '\u2591' * (bar_length - filled_length)
        print(f"[{bar}] {progress:.1f}%")
        print("-" * 50)

def manage_donor_recognition():
    """Manage donor recognition levels and benefits"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to manage donor recognition.")
        return

    if not auth.check_permission('manage_campaigns'):
        print("You don't have permission to manage donor recognition.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nDonor Recognition Management")
    print("============================")
    print("1. View Current Recognition Levels")
    print("2. Update Alumni Recognition Levels")
    print("3. Recognition Level Report")

    choice = input("Enter your choice: ")

    if choice == '1':
        # View current levels
        cursor.execute('''
            SELECT dr.*, a.first_name, a.last_name
            FROM donor_recognition dr
            JOIN alumni a ON dr.alumni_id = a.alumni_id
            ORDER BY dr.total_donated DESC
        ''')

        recognitions = cursor.fetchall()

        if recognitions:
            print("\nCurrent Donor Recognition Levels:")
            print("-" * 70)
            for rec in recognitions:
                name = f"{rec[5]} {rec[6]}"
                print(f"{name}: {rec[2]} (£{rec[3]:,.2f} total)")
                if rec[4]:  # benefits
                    print(f"  Benefits: {rec[4]}")
                print("-" * 70)
        else:
            print("No donor recognition records found.")

    elif choice == '2':
        # Update recognition levels
        update_donor_recognition_levels(cursor)

    elif choice == '3':
        # Recognition report
        generate_recognition_report(cursor)
    else:
        print("Invalid choice.")

    conn.close()

def update_donor_recognition_levels(cursor):
    """Update donor recognition levels based on total donations"""
    # Define recognition levels
    recognition_levels = [
        ("Bronze Supporter", 100, "Newsletter subscription, alumni directory access"),
        ("Silver Supporter", 500, "Event invitations, recognition in publications"),
        ("Gold Supporter", 1000, "VIP event access, annual appreciation dinner"),
        ("Platinum Supporter", 5000, "Board meeting invitations, naming opportunities"),
        ("Diamond Supporter", 10000, "Personal meetings with leadership, legacy society membership"),
        ("Benefactor", 25000, "Permanent recognition, advisory board invitation")
    ]

    # Get all donors with their total donations
    cursor.execute('''
        SELECT alumni_id, SUM(amount) as total_donated
        FROM donations
        GROUP BY alumni_id
        HAVING total_donated > 0
    ''')

    donors = cursor.fetchall()

    print(f"Updating recognition levels for {len(donors)} donors...")

    updated_count = 0
    for alumni_id, total_donated in donors:
        # Determine recognition level
        recognition_level = "Supporter"
        benefits = "Basic alumni benefits"

        for level_name, min_amount, level_benefits in reversed(recognition_levels):
            if total_donated >= min_amount:
                recognition_level = level_name
                benefits = level_benefits
                break

        # Update or insert recognition record
        cursor.execute('''
            INSERT OR REPLACE INTO donor_recognition
            (alumni_id, recognition_level, total_donated, recognition_date, benefits)
            VALUES (?, ?, ?, ?, ?)
        ''', (alumni_id, recognition_level, total_donated,
              datetime.now().strftime('%Y-%m-%d'), benefits))

        updated_count += 1

    print(f"Updated {updated_count} donor recognition levels.")

def generate_recognition_report(cursor):
    """Generate donor recognition report"""
    cursor.execute('''
        SELECT recognition_level, COUNT(*) as count, SUM(total_donated) as total_amount
        FROM donor_recognition
        GROUP BY recognition_level
        ORDER BY total_amount DESC
    ''')

    report_data = cursor.fetchall()

    if report_data:
        print("\nDonor Recognition Level Report")
        print("==============================")

        total_donors = 0
        total_amount = 0

        for level, count, amount in report_data:
            total_donors += count
            total_amount += amount
            print(f"{level}: {count} donors (£{amount:,.2f})")

        print("-" * 40)
        print(f"Total: {total_donors} donors (£{total_amount:,.2f})")
    else:
        print("No recognition data available.")
