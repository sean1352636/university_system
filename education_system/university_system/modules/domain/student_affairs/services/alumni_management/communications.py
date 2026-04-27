from datetime import datetime
from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection
from education_system.university_system.infrastructure.email.email_service import send_email
from education_system.university_system.infrastructure.email.template_utils import load_template, render_template
from education_system.university_system.modules.domain.student_affairs.services.alumni_management.core import safe_execute, auth


def create_newsletter():
    """Create and send newsletters"""
    global auth

    if not auth or not auth.current_user:
        print("You must be logged in to create newsletters.")
        return

    if not auth.check_permission('send_newsletters'):
        print("You don't have permission to create newsletters.")
        return

    conn = get_connection()
    cursor = conn.cursor()

    print("\nCreate Alumni Newsletter")
    print("========================")

    # Get available templates
    cursor.execute('SELECT template_id, template_name FROM alumni_email_templates WHERE template_type = "newsletter"')
    templates = cursor.fetchall()

    if templates:
        print("\nAvailable Templates:")
        for i, template in enumerate(templates, 1):
            print(f"{i}. {template[1]}")
        print(f"{len(templates) + 1}. Create custom newsletter")

        try:
            template_choice = int(input("Select template: "))
            if 1 <= template_choice <= len(templates):
                template_id = templates[template_choice - 1][0]
                cursor.execute('SELECT template_content FROM alumni_email_templates WHERE template_id = ?', (template_id,))
                base_content = cursor.fetchone()[0]
            else:
                template_id = None
                base_content = ""
        except ValueError:
            template_id = None
            base_content = ""
    else:
        template_id = None
        base_content = ""

    title = input("Newsletter Title: ")
    print("\nEnter newsletter content (press Enter twice to finish):")
    content_lines = []
    while True:
        line = input()
        if line == "" and (not content_lines or content_lines[-1] == ""):
            break
        content_lines.append(line)

    content = base_content + "\n\n" + "\n".join(content_lines)

    # Target audience selection
    print("\nTarget Audience:")
    print("1. All Alumni")
    print("2. By Graduation Year")
    print("3. By Industry")
    print("4. By Location")
    print("5. Donors Only")
    print("6. Mentors Only")

    audience_choice = input("Select target audience: ")
    target_audience = "all"
    audience_filter = None
    filter_params = []

    if audience_choice == '2':
        year = input("Enter graduation year: ")
        target_audience = f"graduation_year:{year}"
        audience_filter = "graduation_year = ?"
        filter_params = [year]
    elif audience_choice == '3':
        industry = input("Enter industry: ")
        target_audience = f"industry:{industry}"
        audience_filter = "industry LIKE ?"
        filter_params = [f"%{escape_like(industry)}%"]
    elif audience_choice == '4':
        location = input("Enter city or country: ")
        target_audience = f"location:{location}"
        audience_filter = "city LIKE ? OR country LIKE ?"
        filter_params = [f"%{escape_like(location)}%", f"%{escape_like(location)}%"]
    elif audience_choice == '5':
        target_audience = "donors"
        audience_filter = "is_donor = 1"
        filter_params = []
    elif audience_choice == '6':
        target_audience = "mentors"
        audience_filter = "is_mentor = 1"
        filter_params = []

    # Schedule or send immediately
    send_choice = input("Send immediately (i) or schedule for later (s): ").lower()

    if send_choice == 's':
        send_date = input("Enter send date (YYYY-MM-DD HH:MM): ")
        try:
            # Validate date format
            datetime.strptime(send_date, "%Y-%m-%d %H:%M")
            status = 'scheduled'
        except ValueError:
            print("Invalid date format. Setting as draft.")
            send_date = None
            status = 'draft'
    else:
        send_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        status = 'sending'

    # Save newsletter
    cursor.execute('''
        INSERT INTO newsletters (title, content, template_id, target_audience, send_date, created_date, created_by, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, content, template_id, target_audience, send_date,
          datetime.now().strftime('%Y-%m-%d %H:%M:%S'), auth.current_user['username'], status))

    newsletter_id = cursor.lastrowid

    if status == 'sending':
        # Send immediately
        send_newsletter_now(newsletter_id, audience_filter, cursor, filter_params)
        cursor.execute('UPDATE newsletters SET status = "sent" WHERE newsletter_id = ?', (newsletter_id,))

    conn.commit()
    conn.close()

    print(f"Newsletter created successfully! ID: {newsletter_id}")
    if status == 'sending':
        print("Newsletter has been sent to recipients.")
    elif status == 'scheduled':
        print(f"Newsletter scheduled for: {send_date}")

def send_newsletter_now(newsletter_id, audience_filter, cursor, filter_params=None):
    """Send newsletter to target audience"""
    # Get newsletter content
    cursor.execute('SELECT title, content FROM newsletters WHERE newsletter_id = ?', (newsletter_id,))
    newsletter_info = cursor.fetchone()
    if not newsletter_info:
        return

    title, content = newsletter_info

    # Get recipient list
    if audience_filter:
        query = f"SELECT email_address, first_name, last_name FROM alumni WHERE {audience_filter}"
        cursor.execute(query, filter_params or [])
    else:
        cursor.execute('SELECT email_address, first_name, last_name FROM alumni')

    recipients = cursor.fetchall()

    print(f"Sending newsletter to {len(recipients)} recipients...")

    # Load email template
    template = load_template('alumni/alumni_newsletter')

    sent_count = 0
    failed_count = 0
    for recipient in recipients:
        email, first_name, last_name = recipient[0], recipient[1], recipient[2] if len(recipient) > 2 else ""
        recipient_name = f"{first_name} {last_name}".strip() if last_name else first_name

        if not email:
            continue

        try:
            if template:
                template_vars = {
                    'recipient_name': recipient_name,
                    'newsletter_title': title,
                    'newsletter_content': content
                }
                subject, body = render_template('alumni_newsletter', template_vars)
                if subject and body:
                    send_email(email, subject, body)
                    sent_count += 1
                else:
                    # Fallback to direct send if template rendering fails
                    send_email(email, title, content)
                    sent_count += 1
            else:
                # No template available, send directly
                send_email(email, title, content)
                sent_count += 1

            print(f"Sent to {email}")
        except Exception as e:
            print(f"Failed to send to {email}: {e}")
            failed_count += 1

    print(f"Newsletter sent successfully to {sent_count} recipients!")
    if failed_count > 0:
        print(f"Failed to send to {failed_count} recipients.")
