import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH


# =========================================================================
# MODULE-LEVEL UTILITY FUNCTIONS
# =========================================================================

def _get_all_student_emails():
    """Get all active student emails from database (module-level function)"""
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Get students with valid emails, optionally filter by active users
        cursor.execute('''
            SELECT DISTINCT s.email_address, s.first_name, s.last_name, s.student_id
            FROM students s
            LEFT JOIN users u ON s.student_id = u.student_id
            WHERE s.email_address IS NOT NULL
            AND s.email_address != ''
            AND (u.id IS NULL OR u.is_active = 1)
            ORDER BY s.last_name, s.first_name
        ''')

        students = cursor.fetchall()
        conn.close()

        return students
    except sqlite3.Error as e:
        logging.error(f"Error fetching student emails: {e}")
        return []


def _send_email_via_gui(to_email, subject, message):
    """Send email using email service (module-level function)"""
    try:
        from education_system.university_system.infrastructure.email.email_service import send_email

        # Use the email service directly with correct parameter name
        send_email(
            recipient_email=to_email,
            subject=subject,
            body=message
        )
        return True
    except ImportError as e:
        logging.error(f"Email service import error: {e}")
        return False
    except (TypeError, ValueError, AttributeError, KeyError) as e:
        logging.error(f"Error sending email: {e}")
        return False


def _show_email_fallback(root, email, subject, message, email_type):
    """Show fallback dialog for email (module-level function)"""
    try:
        fallback_window = tk.Toplevel(root)
        fallback_window.title(f"{email_type} Email - Manual Send")
        fallback_window.geometry("700x500")
        fallback_window.transient(root)

        ttk.Label(fallback_window,
                 text=f"Email system unavailable. Please manually send this {email_type.lower()}:",
                 font=('Arial', 10, 'bold')).pack(pady=10)

        details_frame = ttk.Frame(fallback_window)
        details_frame.pack(fill='both', expand=True, padx=10, pady=10)

        details_text = scrolledtext.ScrolledText(details_frame, height=20, width=80)
        details_text.pack(fill='both', expand=True)

        email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
        details_text.insert('1.0', email_details)
        details_text.config(state='disabled')

        ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
    except (tk.TclError, AttributeError) as e:
        print(f"Failed to show email fallback: {e}")


# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False


class DatabaseQueryDialog:
    """Generic dialog for database queries with results display"""

    def __init__(self, parent, title, query, columns):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.query = query
        self.columns = columns

        self.create_widgets()
        self.execute_query()

    def create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Results tree
        self.tree = ttk.Treeview(main_frame, columns=self.columns, show='tree headings')

        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)

        scrollbar_y = ttk.Scrollbar(main_frame, orient='vertical', command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(main_frame, orient='horizontal', command=self.tree.xview)

        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar_y.pack(side='right', fill='y')
        scrollbar_x.pack(side='bottom', fill='x')

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=10)

    def execute_query(self):
        """Execute the database query and display results"""
        try:
            conn = student_union_cli.get_connection()
            cursor = conn.cursor()

            cursor.execute(self.query)
            results = cursor.fetchall()

            for result in results:
                self.tree.insert('', 'end', values=result)

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to execute query: {str(e)}")

    # =========================================================================
    # EMAIL INTEGRATION METHODS
    # =========================================================================

    def send_new_club_announcement(self, club_name, club_description):
        """Send email to all students about new club"""
        try:
            # Get all active student emails using helper method
            students = self._get_all_student_emails()

            if not students:
                logging.warning("No student emails found to send club announcement")
                return 0

            emails_sent = 0
            for email, first_name, last_name, student_id in students:
                try:
                    subject, message = render_template("club_created_notification", {
                        "first_name": first_name,
                        "last_name": last_name,
                        "club_name": club_name,
                        "club_description": club_description
                    })

                    if subject and message:
                        if self._send_email_via_gui(email, subject, message):
                            emails_sent += 1
                except (TypeError, ValueError, AttributeError, KeyError) as e:
                    # Error handling - log but continue
                    logging.debug(f"Failed to send club announcement to {email}: {e}")

            logging.info(f"Club announcement sent to {emails_sent}/{len(students)} students")
            return emails_sent

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logging.error(f"Failed to send new club announcements: {e}")
            return 0

    def send_club_invitation(self, club_name, recipient_email, recipient_name, inviter_name):
        """Send club invitation email"""
        try:
            try:
                subject, message = render_template("club_invitation", {
                    "recipient_name": recipient_name,
                    "inviter_name": inviter_name,
                    "club_name": club_name,
                    "invitation_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            except (TypeError, ValueError, AttributeError, KeyError) as e:
                # Error handling
                subject = f"You're Invited to Join {club_name}!"
                message = f"""Dear {recipient_name},

{inviter_name} has invited you to join the {club_name} club!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLUB INVITATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Invited by: {inviter_name}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{inviter_name} thinks you'd be a great addition to our club! Join us to participate in exciting activities, events, and meet new friends who share your interests.

To accept this invitation, log into the Student Union portal and search for "{club_name}".

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club & Student Union Team
"""

            success = self._send_email_via_gui(recipient_email, subject, message)
            if success:
                messagebox.showinfo("Invitation Sent", f"Club invitation sent to {recipient_name}")
            else:
                self._show_email_fallback(recipient_email, subject, message, "Club Invitation")

        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Failed to send club invitation: {e}")

    def send_club_join_confirmation(self, club_name, user_email, user_name):
        """Send confirmation email when user joins a club"""
        try:
            try:
                subject, message = render_template("club_member_welcome", {
                    "user_name": user_name,
                    "club_name": club_name,
                    "join_date": datetime.now().strftime('%Y-%m-%d')
                })

                if not (subject and message):
                    # Fallback if template fails
                    subject = f"Welcome to {club_name}!"
                    message = f"""Dear {user_name},

Welcome to {club_name}! Your membership has been confirmed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Member: {user_name}
Join Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Active Member

What's next:
• Check your Student Union portal for upcoming events
• Visit the club merchandise shop for exclusive items
• Join club trips and activities
• Connect with other club members

We're excited to have you as part of our community!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""
            except (KeyError, AttributeError, TypeError) as e:
                # Error handling
                subject = f"Welcome to {club_name}!"
                message = f"""Dear {user_name},

Welcome to {club_name}! Your membership has been confirmed.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Member: {user_name}
Join Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Active Member

What's next:
• Check your Student Union portal for upcoming events
• Visit the club merchandise shop for exclusive items
• Join club trips and activities
• Connect with other club members

We're excited to have you as part of our community!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""

            self._send_email_via_gui(user_email, subject, message)

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            print(f"Failed to send club join confirmation: {e}")

    def send_club_leave_confirmation(self, club_name, user_email, user_name):
        """Send confirmation email when user leaves a club"""
        try:
            try:
                subject, message = render_template("club_member_goodbye", {
                    "user_name": user_name,
                    "club_name": club_name,
                    "leave_date": datetime.now().strftime('%Y-%m-%d')
                })

                if not (subject and message):
                    # Fallback if template fails
                    subject = f"Thank You for Being Part of {club_name}"
                    message = f"""Dear {user_name},

We're sorry to see you leave {club_name}. Your membership has been updated.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP UPDATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Former Member: {user_name}
Leave Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Membership Ended

Thank you for being part of our community. The door is always open if you'd like to rejoin in the future!

You can explore other clubs and activities through the Student Union portal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""
            except (KeyError, AttributeError, TypeError) as e:
                # Error handling
                subject = f"Thank You for Being Part of {club_name}"
                message = f"""Dear {user_name},

We're sorry to see you leave {club_name}. Your membership has been updated.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MEMBERSHIP UPDATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Club: {club_name}
Former Member: {user_name}
Leave Date: {datetime.now().strftime('%Y-%m-%d')}
Status: Membership Ended

Thank you for being part of our community. The door is always open if you'd like to rejoin in the future!

You can explore other clubs and activities through the Student Union portal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
{club_name} Club Leadership
Student Union Team
"""

            self._send_email_via_gui(user_email, subject, message)

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            print(f"Failed to send club leave confirmation: {e}")

    def send_newsletter_to_club_members(self, club_name, newsletter_subject, newsletter_content):
        """Send newsletter to all club members"""
        try:
            # Get all members of the club
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                SELECT s.email, s.first_name, s.last_name
                FROM students s
                JOIN club_members cm ON s.student_id = cm.student_id
                JOIN student_clubs sc ON cm.club_id = sc.club_id
                WHERE sc.club_name = ? AND s.email IS NOT NULL
            ''', (club_name,))
            members = cursor.fetchall()
            conn.close()

            for email, first_name, last_name in members:
                try:
                    subject, message = render_template("club_newsletter_broadcast", {
                        "first_name": first_name,
                        "last_name": last_name,
                        "club_name": club_name,
                        "newsletter_subject": newsletter_subject,
                        "newsletter_content": newsletter_content
                    })

                    if not (subject and message):
                        # Fallback if template fails
                        subject = f"{club_name} Newsletter: {newsletter_subject}"
                        message = f"""Dear {first_name} {last_name},

Here's the latest newsletter from {club_name}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{club_name.upper()} NEWSLETTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{newsletter_content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stay connected and don't miss out on upcoming events and activities!

Best regards,
{club_name} Leadership Team
"""
                except (KeyError, AttributeError, TypeError) as e:
                    # Error handling
                    subject = f"{club_name} Newsletter: {newsletter_subject}"
                    message = f"""Dear {first_name} {last_name},

Here's the latest newsletter from {club_name}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{club_name.upper()} NEWSLETTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{newsletter_content}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Stay connected and don't miss out on upcoming events and activities!

Best regards,
{club_name} Leadership Team
"""

                self._send_email_via_gui(email, subject, message)

            messagebox.showinfo("Newsletter Sent", f"Newsletter sent to {len(members)} club members")

        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Failed to send newsletter: {e}")

    def send_event_notification_to_all_students(self, event_name, event_description, event_date, event_location):
        """Send event notification to all students"""
        try:
            # Get all active student emails using helper method
            students = self._get_all_student_emails()

            if not students:
                logging.warning("No student emails found to send event notification")
                return

            emails_sent = 0
            for email, first_name, last_name, student_id in students:
                try:
                    subject, message = render_template("event_upcoming", {
                        "first_name": first_name,
                        "last_name": last_name,
                        "event_name": event_name,
                        "event_date": event_date,
                        "event_location": event_location,
                        "event_description": event_description
                    })

                    if not (subject and message):
                        # Fallback if template fails
                        subject = f"Upcoming Event: {event_name}"
                        message = f"""Dear {first_name} {last_name},

Don't miss this exciting upcoming event!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVENT ANNOUNCEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Event: {event_name}
Date: {event_date}
Location: {event_location}

Description:
{event_description}

Register now through the Student Union portal to secure your spot!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Events Team
"""
                except (KeyError, AttributeError, TypeError) as e:
                    # Error handling
                    subject = f"Upcoming Event: {event_name}"
                    message = f"""Dear {first_name} {last_name},

Don't miss this exciting upcoming event!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EVENT ANNOUNCEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Event: {event_name}
Date: {event_date}
Location: {event_location}

Description:
{event_description}

Register now through the Student Union portal to secure your spot!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Events Team
"""

                if self._send_email_via_gui(email, subject, message):
                    emails_sent += 1

            logging.info(f"Event notification sent to {emails_sent}/{len(students)} students")
            return emails_sent

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logging.error(f"Failed to send event notifications: {e}")
            return 0

    def send_trip_announcement(self, trip_name, trip_description, trip_date, trip_cost, organizer_club):
        """Send trip announcement to students"""
        try:
            # Get target audience (club members if specific club, all students if general)
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            if organizer_club:
                # Send to club members
                cursor.execute('''
                    SELECT s.email, s.first_name, s.last_name
                    FROM students s
                    JOIN club_members cm ON s.student_id = cm.student_id
                    JOIN student_clubs sc ON cm.club_id = sc.club_id
                    WHERE sc.club_name = ? AND s.email IS NOT NULL
                ''', (organizer_club,))
            else:
                # Send to all students
                cursor.execute('SELECT email, first_name, last_name FROM students WHERE email IS NOT NULL')

            recipients = cursor.fetchall()
            conn.close()

            subject = f"🧳 Trip Opportunity: {trip_name}"
            organizer_text = f" (organized by {organizer_club})" if organizer_club else ""

            for email, first_name, last_name in recipients:
                message = f"""Dear {first_name} {last_name},

Exciting trip opportunity{organizer_text}!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TRIP ANNOUNCEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Trip: {trip_name}
Date: {trip_date}
Cost: £{trip_cost:.2f}
{f"Organized by: {organizer_club}" if organizer_club else "Organized by: Student Union"}

Description:
{trip_description}

Book your spot now through the Student Union portal. Payment can be made via your student account.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Travel Team
"""

                self._send_email_via_gui(email, subject, message)

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            print(f"Failed to send trip announcements: {e}")

    def send_payment_confirmation(self, payment_type, item_name, amount, user_email, user_name):
        """Send payment confirmation email"""
        try:
            subject = f"💳 Payment Confirmation: {item_name}"

            message = f"""Dear {user_name},

Your payment has been successfully processed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PAYMENT CONFIRMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Payment Type: {payment_type}
Item/Service: {item_name}
Amount: £{amount:.2f}
Payment Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Payment Method: Student Account
Status: Completed

Thank you for your payment. Keep this email as your receipt.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Best regards,
Student Union Finance Team
"""

            self._send_email_via_gui(user_email, subject, message)

        except (TypeError, ValueError, AttributeError, KeyError) as e:
            print(f"Failed to send payment confirmation: {e}")

    def _get_all_student_emails(self):
        """Get all active student emails from database"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get students with valid emails, optionally filter by active users
            cursor.execute('''
                SELECT DISTINCT s.email_address, s.first_name, s.last_name, s.student_id
                FROM students s
                LEFT JOIN users u ON s.student_id = u.student_id
                WHERE s.email_address IS NOT NULL
                AND s.email_address != ''
                AND (u.id IS NULL OR u.is_active = 1)
                ORDER BY s.last_name, s.first_name
            ''')

            students = cursor.fetchall()
            conn.close()

            return students
        except sqlite3.Error as e:
            logging.error(f"Error fetching student emails: {e}")
            return []

    def _send_email_via_gui(self, to_email, subject, message):
        """Send email using email service"""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            # Use the email service directly with correct parameter name
            send_email(
                recipient_email=to_email,
                subject=subject,
                body=message
            )
            return True
        except ImportError as e:
            logging.error(f"Email service import error: {e}")
            return False
        except (TypeError, ValueError, AttributeError, KeyError) as e:
            logging.error(f"Error sending email: {e}")
            return False

    def _show_email_fallback(self, email, subject, message, email_type):
        """Show fallback dialog for email"""
        try:
            fallback_window = tk.Toplevel(self.root)
            fallback_window.title(f"{email_type} Email - Manual Send")
            fallback_window.geometry("700x500")
            fallback_window.transient(self.root)

            ttk.Label(fallback_window,
                     text=f"Email system unavailable. Please manually send this {email_type.lower()}:",
                     font=('Arial', 10, 'bold')).pack(pady=10)

            details_frame = ttk.Frame(fallback_window)
            details_frame.pack(fill='both', expand=True, padx=10, pady=10)

            from tkinter.scrolledtext import ScrolledText
            details_text = ScrolledText(details_frame, height=20, width=80)
            details_text.pack(fill='both', expand=True)

            email_details = f"To: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            details_text.insert('1.0', email_details)
            details_text.config(state='disabled')

            ttk.Button(fallback_window, text="Close", command=fallback_window.destroy).pack(pady=10)
        except (tk.TclError, AttributeError) as e:
            print(f"Failed to show email fallback: {e}")

    # =========================================================================
    # FINANCE INTEGRATION METHODS
    # =========================================================================

    def open_finance_gui_for_club_payment(self, item_name, amount, payment_type="Club Payment"):
        """Open finance GUI for club-related payments"""
        try:
            from education_system.university_system.modules.domain.finance.gui.finance import FinanceGUI

            finance_window = tk.Toplevel(self.root)
            finance_window.title(f"Finance System - {payment_type}")
            finance_window.geometry("1000x700")

            finance_gui = FinanceGUI(finance_window, auth=self.auth_manager)

            # Pre-populate student union payment information if method exists
            if hasattr(finance_gui, 'prepopulate_student_union_payment'):
                finance_gui.prepopulate_student_union_payment(item_name, amount, payment_type)

            messagebox.showinfo("Finance System", f"Finance system opened for {payment_type}: {item_name}")

        except ImportError:
            messagebox.showerror("Error", "Finance system is not available")
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Could not open finance system: {e}")

    def process_student_union_payment(self, student_id, amount, description, payment_type):
        """Process payment through student finance account balance"""
        try:
            # Use finance account integration if available
            if FINANCE_ACCOUNT_AVAILABLE:
                # Check balance first
                current_balance = get_student_finance_account_balance(student_id)
                if current_balance is None:
                    messagebox.showerror("Error",
                        f"No finance account found for student {student_id}.\n"
                        "Please create a finance account first or use a different payment method.")
                    return False

                if current_balance < amount:
                    messagebox.showerror("Insufficient Balance",
                        f"Student finance account balance is insufficient.\n\n"
                        f"Current Balance: £{current_balance:.2f}\n"
                        f"Required Amount: £{amount:.2f}\n\n"
                        f"Please top up the account or use a different payment method.")
                    return False

                # Get student info for email
                student_info = get_student_info(student_id)
                if not student_info:
                    messagebox.showerror("Error", f"Student ID {student_id} not found")
                    return False

                student_name = student_info.get('full_name', student_id)
                student_email = student_info.get('email', '')

                # Process the payment from finance account
                processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
                payment_result = process_student_finance_account_payment(
                    student_id=student_id,
                    amount=amount,
                    description=f"{payment_type}: {description}",
                    transaction_source="Student Union",
                    transaction_ref=f"SU_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    processed_by=processed_by,
                    check_balance=True,
                    send_low_balance_alert=True
                )

                if not payment_result['success']:
                    messagebox.showerror("Payment Failed", payment_result['message'])
                    return False

                new_balance = payment_result.get('new_balance', 0)
                low_balance_email_sent = payment_result.get('email_sent', False)

                # Send payment confirmation email
                if student_email:
                    self.send_payment_confirmation(payment_type, description, amount, student_email, student_name)

                success_msg = f"Payment of £{amount:.2f} deducted from {student_name}'s finance account.\nNew Balance: £{new_balance:.2f}"

                if low_balance_email_sent:
                    success_msg += "\n\n⚠ Low balance alert email sent to student"

                messagebox.showinfo("Payment Processed", success_msg)
                return True

            # Fallback: Legacy method - add to student_fees without balance deduction
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            try:
                cursor = conn.cursor()

                # Get student details
                cursor.execute('SELECT first_name, last_name, email FROM students WHERE student_id = ?', (student_id,))
                student_result = cursor.fetchone()
                if not student_result:
                    messagebox.showerror("Error", f"Student ID {student_id} not found")
            finally:
                conn.close()
                return False

            first_name, last_name, email = student_result

            # Add charge to student's finance account (legacy method)
            fee_id = f"SU_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            current_date = datetime.now().strftime('%Y-%m-%d')

            cursor.execute('''
                INSERT INTO student_fees
                (fee_id, student_id, fee_type, amount, due_date, description, paid_status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                fee_id, student_id, payment_type, amount, current_date,
                f'{description} for {first_name} {last_name}', 'Paid', current_date
            ))

            # Record payment
            try:
                payment_id = f"PAY_{fee_id}"
                cursor.execute('''
                    INSERT INTO payments
                    (payment_id, student_id, amount, payment_method, payment_date, status, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    payment_id, student_id, amount, 'Student Account', current_date, 'completed',
                    f'Student Union payment: {description}'
                ))
            except sqlite3.Error:
                pass  # Payments table might not exist

            conn.commit()
            conn.close()

            # Send payment confirmation email
            self.send_payment_confirmation(payment_type, description, amount, email, f"{first_name} {last_name}")

            messagebox.showinfo("Payment Processed",
                f"Payment of £{amount:.2f} charged to {first_name} {last_name}'s student account (legacy)")
            return True

        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to process payment: {e}")
            return False

    # =========================================================================
    # SHOP INTEGRATION METHODS
    # =========================================================================

    def open_shop_for_club_merchandise(self, club_name):
        """Open shop GUI filtered for club merchandise"""
        try:
            from education_system.university_system.modules.domain.commerce.gui.shop_management_gui.main_gui import UniversityShopGUI

            shop_window = tk.Toplevel(self.root)
            shop_window.title(f"University Shop - {club_name} Merchandise")
            shop_window.geometry("1200x800")

            shop_gui = UniversityShopGUI(shop_window, auth=self.auth_manager)

            # Pre-filter for club merchandise if method exists
            if hasattr(shop_gui, 'filter_club_merchandise'):
                shop_gui.filter_club_merchandise(club_name)

            messagebox.showinfo("Shop Opened", f"Shop opened for {club_name} merchandise")

        except ImportError:
            messagebox.showerror("Error", "Shop system is not available")
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Could not open shop system: {e}")

    def add_club_merchandise_button(self, club_name):
        """Add button to access club merchandise"""
        try:
            merchandise_button = ttk.Button(
                self.content_frame,
                text=f"🛍️ {club_name} Merchandise",
                command=lambda: self.open_shop_for_club_merchandise(club_name)
            )
            merchandise_button.pack(pady=5)
        except (tk.TclError, AttributeError) as e:
            print(f"Could not add merchandise button: {e}")

    # =========================================================================
    # RESTAURANT INTEGRATION METHODS
    # =========================================================================

    def open_restaurant_for_club_booking(self, club_name, event_type="Club Event"):
        """Open restaurant GUI for club event booking"""
        try:
            from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui import RestaurantManagementGUI

            # Pass parent root — show_restaurant_management() creates its own Toplevel
            restaurant_gui = RestaurantManagementGUI(self.root, auth=self.auth_manager)
            restaurant_gui.show_restaurant_management()

            # Pre-populate club booking information if method exists
            if hasattr(restaurant_gui, 'create_club_reservation'):
                restaurant_gui.create_club_reservation(club_name, event_type)

            messagebox.showinfo("Restaurant Opened", f"Restaurant booking opened for {club_name}")

        except ImportError:
            messagebox.showerror("Error", "Restaurant system is not available")
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Could not open restaurant system: {e}")

    def book_club_dining_dialog(self, club_name):
        """Show dialog for club dining reservation"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Book Dining for {club_name}")
            dialog.geometry("400x300")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Restaurant Booking for {club_name}",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Booking options
            ttk.Label(main_frame, text="Event Type:").pack(anchor='w')
            event_type_var = tk.StringVar(value="Club Meeting")
            event_types = ["Club Meeting", "Social Dinner", "Celebration", "Awards Ceremony", "Other"]
            event_combo = ttk.Combobox(main_frame, textvariable=event_type_var, values=event_types)
            event_combo.pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Expected Attendees:").pack(anchor='w')
            attendees_var = tk.StringVar()
            ttk.Entry(main_frame, textvariable=attendees_var).pack(fill='x', pady=5)

            def proceed_booking():
                event_type = event_type_var.get()
                attendees = attendees_var.get()
                if attendees:
                    dialog.destroy()
                    self.open_restaurant_for_club_booking(club_name, event_type)
                else:
                    messagebox.showwarning("Missing Information", "Please specify expected attendees")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Open Restaurant System",
                      command=proceed_booking).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel",
                      command=dialog.destroy).pack(side='left', padx=5)

        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Could not open booking dialog: {e}")

    # =========================================================================
    # TRIP INTEGRATION METHODS
    # =========================================================================

    def open_trip_management_for_club(self, club_name):
        """Open trip management GUI for club"""
        try:
            from education_system.university_system.modules.domain.mobility.gui.trip_management_gui import TripManagementGUI

            trip_window = tk.Toplevel(self.root)
            trip_window.title(f"Trip Management - {club_name}")
            trip_window.geometry("1200x800")

            trip_gui = TripManagementGUI(trip_window, auth=self.auth_manager)

            # Pre-populate club information if method exists
            if hasattr(trip_gui, 'set_organizing_club'):
                trip_gui.set_organizing_club(club_name)

            messagebox.showinfo("Trip Management Opened", f"Trip management opened for {club_name}")

        except ImportError:
            messagebox.showerror("Error", "Trip management system is not available")
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Could not open trip management: {e}")

    def create_club_trip_dialog(self, club_name):
        """Show dialog to create a new club trip"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Create Trip for {club_name}")
            dialog.geometry("500x600")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"New Trip for {club_name}",
                     font=('Arial', 14, 'bold')).pack(pady=10)

            # Trip details form
            fields = {}

            ttk.Label(main_frame, text="Trip Name:").pack(anchor='w')
            fields['name'] = ttk.Entry(main_frame)
            fields['name'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Destination:").pack(anchor='w')
            fields['destination'] = ttk.Entry(main_frame)
            fields['destination'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Trip Date:").pack(anchor='w')
            fields['date'] = ttk.Entry(main_frame)
            fields['date'].pack(fill='x', pady=5)
            fields['date'].insert(0, "YYYY-MM-DD")

            ttk.Label(main_frame, text="Cost per Person (£):").pack(anchor='w')
            fields['cost'] = ttk.Entry(main_frame)
            fields['cost'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Maximum Participants:").pack(anchor='w')
            fields['max_participants'] = ttk.Entry(main_frame)
            fields['max_participants'].pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Description:").pack(anchor='w')
            fields['description'] = tk.Text(main_frame, height=6)
            fields['description'].pack(fill='both', expand=True, pady=5)

            def create_trip():
                try:
                    trip_data = {
                        'name': fields['name'].get(),
                        'destination': fields['destination'].get(),
                        'date': fields['date'].get(),
                        'cost': float(fields['cost'].get()),
                        'max_participants': int(fields['max_participants'].get()),
                        'description': fields['description'].get('1.0', 'end-1c'),
                        'organizing_club': club_name
                    }

                    # Validate required fields
                    if not all([trip_data['name'], trip_data['destination'], trip_data['date']]):
                        messagebox.showerror("Error", "Please fill in all required fields")
                        return

                    # Create trip in database (simplified)
                    conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                    try:
                        cursor = conn.cursor()

                        # Create trips table if it doesn't exist
                        cursor.execute('''
                            CREATE TABLE IF NOT EXISTS student_trips (
                                trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                trip_name TEXT NOT NULL,
                                destination TEXT NOT NULL,
                                trip_date TEXT NOT NULL,
                                cost REAL NOT NULL,
                                max_participants INTEGER,
                                description TEXT,
                                organizing_club TEXT,
                                created_by INTEGER,
                                created_date TEXT DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')

                        cursor.execute('''
                            INSERT INTO student_trips
                            (trip_name, destination, trip_date, cost, max_participants, description, organizing_club, created_by)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            trip_data['name'], trip_data['destination'], trip_data['date'],
                            trip_data['cost'], trip_data['max_participants'], trip_data['description'],
                            club_name, self.current_user.get('id', 0)
                        ))

                        conn.commit()
                    finally:
                        conn.close()

                    # Send trip announcement
                    self.send_trip_announcement(
                        trip_data['name'], trip_data['description'],
                        trip_data['date'], trip_data['cost'], club_name
                    )

                    dialog.destroy()
                    messagebox.showinfo("Trip Created", f"Trip '{trip_data['name']}' created successfully!")

                except ValueError:
                    messagebox.showerror("Error", "Please enter valid numbers for cost and max participants")
                except sqlite3.Error as e:
                    messagebox.showerror("Error", f"Failed to create trip: {e}")

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=20)

            ttk.Button(button_frame, text="Create Trip", command=create_trip).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Open Trip Management",
                      command=lambda: [dialog.destroy(), self.open_trip_management_for_club(club_name)]).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Could not create trip dialog: {e}")

    # =========================================================================
    # ENHANCED UI INTEGRATION METHODS
    # =========================================================================

    def add_integration_buttons_to_club_view(self, club_name):
        """Add integration buttons to club view"""
        try:
            if hasattr(self, 'content_frame'):
                # Create integration buttons frame
                integration_frame = ttk.LabelFrame(self.content_frame, text="Club Services")
                integration_frame.pack(fill='x', padx=10, pady=10)

                # Row 1: Shopping and Dining
                row1_frame = ttk.Frame(integration_frame)
                row1_frame.pack(fill='x', padx=5, pady=5)

                ttk.Button(row1_frame, text="🛍️ Club Merchandise",
                          command=lambda: self.open_shop_for_club_merchandise(club_name)).pack(side='left', padx=5)
                ttk.Button(row1_frame, text="🍽️ Book Club Dining",
                          command=lambda: self.book_club_dining_dialog(club_name)).pack(side='left', padx=5)

                # Row 2: Calendar and Trips
                row2_frame = ttk.Frame(integration_frame)
                row2_frame.pack(fill='x', padx=5, pady=5)

                ttk.Button(row2_frame, text="📅 Club Calendar",
                          command=lambda: self.open_calendar_with_club_events(club_name)).pack(side='left', padx=5)
                ttk.Button(row2_frame, text="🧳 Organize Trip",
                          command=lambda: self.create_club_trip_dialog(club_name)).pack(side='left', padx=5)

                # Row 3: Finance and Communication
                row3_frame = ttk.Frame(integration_frame)
                row3_frame.pack(fill='x', padx=5, pady=5)

                ttk.Button(row3_frame, text="💳 Club Payments",
                          command=lambda: self.open_finance_gui_for_club_payment(f"{club_name} Membership", 0, "Club Fee")).pack(side='left', padx=5)
                ttk.Button(row3_frame, text="📧 Send Newsletter",
                          command=lambda: self.create_newsletter_dialog(club_name)).pack(side='left', padx=5)

        except (tk.TclError, AttributeError) as e:
            print(f"Could not add integration buttons: {e}")

    def create_newsletter_dialog(self, club_name):
        """Create dialog for sending club newsletter"""
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Send Newsletter - {club_name}")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding="20")
            main_frame.pack(fill='both', expand=True)

            ttk.Label(main_frame, text=f"Send Newsletter to {club_name} Members",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            ttk.Label(main_frame, text="Newsletter Subject:").pack(anchor='w')
            subject_entry = ttk.Entry(main_frame)
            subject_entry.pack(fill='x', pady=5)

            ttk.Label(main_frame, text="Newsletter Content:").pack(anchor='w')
            content_text = tk.Text(main_frame, height=15)
            content_text.pack(fill='both', expand=True, pady=5)

            def send_newsletter():
                subject = subject_entry.get().strip()
                content = content_text.get('1.0', 'end-1c').strip()

                if not subject or not content:
                    messagebox.showwarning("Missing Information", "Please provide both subject and content")
                    return

                self.send_newsletter_to_club_members(club_name, subject, content)
                dialog.destroy()

            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)

            ttk.Button(button_frame, text="Send Newsletter", command=send_newsletter).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Could not create newsletter dialog: {e}")


class SearchDialog:
    """Generic search dialog"""

    def __init__(self, parent, title, search_function, display_function):
        self.parent = parent
        self.search_function = search_function
        self.display_function = display_function

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create search dialog widgets"""
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Search input
        ttk.Label(main_frame, text="Search Term:").pack(anchor='w', pady=(0, 5))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(main_frame, textvariable=self.search_var, width=40)
        search_entry.pack(fill='x', pady=(0, 10))
        search_entry.bind('<Return>', lambda e: self.perform_search())
        search_entry.focus()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Search", command=self.perform_search).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def perform_search(self):
        """Perform the search"""
        search_term = self.search_var.get().strip()
        if not search_term:
            messagebox.showwarning("Warning", "Please enter a search term.")
            return

        try:
            results = self.search_function(search_term)
            self.display_function(results)
            self.dialog.destroy()
        except (tk.TclError, AttributeError) as e:
            messagebox.showerror("Error", f"Search failed: {str(e)}")

# Backward compatibility functions for CLI integration

def get_gui_instance():
    """Get the GUI instance for CLI integration"""
    return StudentUnionGUI()


def launch_gui():
    """Launch the GUI application"""
    app = StudentUnionGUI()
    app.run()


def launch_cli():
    """Launch the CLI application"""
    if CLI_AVAILABLE:
        try:
            from part2 import main as cli_main
            cli_main()
        except ImportError:
            print("Error: CLI system not available")
    else:
        print("CLI system not available. Please ensure part2.py is in the same directory.")

# Enhanced CLI-GUI Bridge Class

class CLIGUIBridge:
    """Bridge between CLI and GUI systems for seamless integration"""

    def __init__(self):
        self.gui_app = None
        self.cli_available = CLI_AVAILABLE

    def start_gui(self):
        """Start GUI mode"""
        self.gui_app = StudentUnionGUI()
        self.gui_app.run()

    def start_cli(self):
        """Start CLI mode"""
        if not self.cli_available:
            print("CLI mode not available")
            return

        try:
            from part2 import main as cli_main
            cli_main()
        except ImportError:
            print("Error: Cannot import CLI system")

    def switch_mode(self, current_mode='gui'):
        """Switch between GUI and CLI modes"""
        if current_mode == 'gui':
            if self.gui_app:
                self.gui_app.root.destroy()
            self.start_cli()
        else:
            self.start_gui()


# ============================================================
# NEW DIALOG CLASSES FOR FULLY IMPLEMENTED FEATURES
# ============================================================


def run_gui_with_cli_fallback(function_name, *args, **kwargs):
    """
    Run GUI version if available, otherwise fall back to CLI
    This maintains full backwards compatibility
    """
    try:
        # Try to run GUI version first
        root = tk.Tk()
        root.withdraw()  # Hide root window

        # Create a temporary GUI instance for function calls
        app = StudentUnionGUI()

        if hasattr(app, f"{function_name}_gui"):
            gui_method = getattr(app, f"{function_name}_gui")
            result = gui_method(*args, **kwargs)
            root.destroy()
            return result
        else:
            root.destroy()
            # Fall back to CLI version
            # FIXED: Check if CLI module exists before accessing it
            if CLI_AVAILABLE and 'student_union_cli' in globals():
                if hasattr(student_union_cli, function_name):
                    cli_method = getattr(student_union_cli, function_name)
                    return cli_method(*args, **kwargs)
            raise AttributeError(f"Function {function_name} not found")

    except ImportError:
        # If GUI libraries not available, use CLI
        if CLI_AVAILABLE and 'student_union_cli' in globals():
            if hasattr(student_union_cli, function_name):
                cli_method = getattr(student_union_cli, function_name)
                return cli_method(*args, **kwargs)
        raise AttributeError(f"Function {function_name} not found")

# Export main functions for backwards compatibility

def main_menu():
    """Main menu - can be GUI or CLI depending on availability"""
    try:
        root, app = launch_student_union_gui()
        root.mainloop()
    except ImportError:
        # Fall back to CLI if tkinter not available
        print("GUI not available, falling back to CLI mode...")
        # FIXED: Check CLI availability before calling
        if CLI_AVAILABLE:
            try:
                from part2 import main as cli_main
                cli_main()
            except ImportError:
                print("CLI also not available")

# FIXED: Add missing function definitions

def launch_gui():
    """Launch GUI application"""
    try:
        root, app = launch_student_union_gui()
        root.mainloop()
    except (tk.TclError, AttributeError, RuntimeError) as e:
        print(f"Failed to launch GUI: {e}")


def launch_cli():
    """Launch CLI application"""
    if CLI_AVAILABLE:
        try:
            from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import main as cli_main
            cli_main()
        except ImportError:
            print("Error: Cannot import CLI system")
    else:
        print("CLI system not available")

# Initialize the module
if __name__ == "__main__":
    main()

# Module-level exports for backwards compatibility
__all__ = [
    'run_gui_with_cli_fallback',
    'main_menu',
    'DatabaseQueryDialog',
    'SearchDialog',
]

