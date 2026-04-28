import tkinter as tk
from education_system.university_system.infrastructure.email.template_utils import render_template
from tkinter import ttk, messagebox, simpledialog, filedialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3, get_connection as db_get_connection
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
from pathlib import Path
import threading
import shutil
from functools import partial

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Import the original functions - backward compatibility
try:
    from education_system.university_system.modules.domain.student_affairs.services.alumni_management import (
        init_alumni_db, register_alumni, view_alumni, update_alumni,
        view_events, create_enhanced_event, event_check_in_system,
        record_donation, view_donations, setup_mentorship, view_mentorships,
        search_alumni_directory, view_connection_requests, manage_business_directory,
        create_newsletter, manage_alumni_forum, post_job_opportunity, view_job_board,
        schedule_career_counseling, view_fundraising_campaigns, create_fundraising_campaign,
        view_engagement_leaderboard, view_my_badges, manage_photo_gallery,
        manage_class_reunions, manage_regional_chapters, setup_alumni_directory,
        generate_alumni_report, set_auth, setup_alumni_permissions,
        smart_mentorship_matching, generate_engagement_recommendations,
        create_alumni_story, view_alumni_stories, get_connection
    )
except ImportError as e:
    import_error_details = str(e)
    print(f"Warning: Could not import some functions: {e}")
    # Define fallback functions
    def placeholder_function(*args, **kwargs):
        func_name = kwargs.get('_func_name', 'Unknown function')
        messagebox.showerror(
            "Module Import Error",
            f"The alumni management module could not be loaded.\n\n"
            f"Function: {func_name}\n"
            f"Error: {import_error_details}\n\n"
            f"Please ensure all required dependencies are installed:\n"
            f"• university_system.alumni module\n"
            f"• All database schema requirements\n\n"
            f"Contact your system administrator for assistance."
        )

    # Assign placeholder to missing functions
    register_alumni = placeholder_function
    view_alumni = placeholder_function



class NotificationsMixin:
        def _send_email_via_gui(self, to_email, subject, message):
            """Send email via email manager GUI"""
            try:
                from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
                email_gui = EmailManagerGUI(self.root, auth=self.auth)
                if hasattr(email_gui, 'send_email'):
                    email_gui.send_email(to_email=to_email, subject=subject, message=message)
                    return True
                return False
            except ImportError:
                return False
            except (AttributeError, TypeError, tk.TclError) as e:
                print(f"Error sending email via GUI: {e}")
                return False

        def _show_email_fallback_dialog(self, to_email, subject, message):
            """Show email dialog as fallback when email system unavailable"""
            dialog = tk.Toplevel(self.root)
            dialog.title("Email Notification")
            dialog.geometry("500x400")
            dialog.configure(bg='white')
            dialog.grab_set()

            tk.Label(dialog, text="Email Notification", font=('Arial', 14, 'bold'),
                    bg='white', fg='#2c3e50').pack(pady=10)

            info_frame = tk.Frame(dialog, bg='white')
            info_frame.pack(fill='x', padx=20, pady=10)

            tk.Label(info_frame, text=f"To: {to_email}", font=('Arial', 11),
                    bg='white', fg='#34495e').pack(anchor='w')
            tk.Label(info_frame, text=f"Subject: {subject}", font=('Arial', 11),
                    bg='white', fg='#34495e').pack(anchor='w')

            tk.Label(dialog, text="Message:", font=('Arial', 11, 'bold'),
                    bg='white', fg='#2c3e50').pack(anchor='w', padx=20, pady=(10, 5))

            message_text = tk.Text(dialog, height=10, wrap='word', font=('Arial', 10))
            message_text.pack(fill='both', expand=True, padx=20, pady=(0, 10))
            message_text.insert('1.0', message)
            message_text.config(state='disabled')

            tk.Button(dialog, text="Close", command=dialog.destroy,
                     bg='#6c757d', fg='white', font=('Arial', 10),
                     padx=20, pady=5, relief='flat').pack(pady=10)

        def send_alumni_registration_confirmation(self, alumni_email, alumni_name):
            """Send confirmation email for alumni registration"""
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'student_name': alumni_name,
                'email': alumni_email,
                'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            subject, message = render_template('alumni_registration_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_club_registration_confirmation(self, alumni_email, alumni_name, club_name):
            """Send confirmation email for club registration via student union"""
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'student_name': alumni_name,
                'club_name': club_name
            }

            subject, message = render_template('club_join_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_course_registration_confirmation(self, alumni_email, alumni_name, course_name, course_code):
            """Send confirmation email for course registration"""
            template_vars = {
                'student_name': alumni_name,
                'course_name': course_name,
                'course_code': course_code,
                'start_date': 'TBD'
            }

            subject, message = render_template('course_registration_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_event_registration_confirmation(self, alumni_email, alumni_name, event_name, event_date):
            """Send confirmation email for event registration via student union"""
            template_vars = {
                'student_name': alumni_name,
                'event_name': event_name,
                'event_date': event_date
            }

            subject, message = render_template('event_registration_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_invoice_receipt(self, alumni_email, alumni_name, invoice_data):
            """Send detailed invoice/receipt via email"""
            items_list = ""
            total_amount = 0
            for item in invoice_data.get('items', []):
                items_list += f"- {item['description']}: £{item['amount']}\n"
                total_amount += float(item['amount'])

            template_vars = {
                'student_name': alumni_name,
                'invoice_number': invoice_data.get('invoice_number', 'N/A'),
                'due_date': invoice_data.get('due_date', 'N/A'),
                'items_list': items_list,
                'total_amount': f"{total_amount:.2f}",
                'payment_status': invoice_data.get('status', 'Paid')
            }

            subject, message = render_template('invoice_receipt', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_module_registration_confirmation(self, alumni_email, alumni_name, module_name, module_code):
            """Send confirmation email for module registration"""
            template_vars = {
                'student_name': alumni_name,
                'module_name': module_name,
                'module_code': module_code
            }

            subject, message = render_template('module_registration_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_payment_confirmation(self, alumni_email, alumni_name, amount, payment_description):
            """Send confirmation email for payments"""
            payment_reference = f"PAY-{datetime.now().strftime('%Y%m%d')}-{alumni_name.replace(' ', '').upper()[:4]}"

            template_vars = {
                'student_name': alumni_name,
                'amount': amount,
                'payment_description': payment_description,
                'payment_reference': payment_reference
            }

            subject, message = render_template('payment_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_profile_deletion_confirmation(self, alumni_email, alumni_name):
            """Send confirmation email for profile deletion"""
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'student_name': alumni_name,
                'deletion_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            subject, message = render_template('profile_deletion_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_profile_update_confirmation(self, alumni_email, alumni_name, update_details):
            """Send confirmation email for profile updates"""
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'student_name': alumni_name,
                'updated_fields': update_details,
                'updated_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            subject, message = render_template('profile_update_confirmation', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

        def send_trip_registration_confirmation(self, alumni_email, alumni_name, trip_name, trip_date):
            """Send confirmation email for trip registration via student union"""
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'student_name': alumni_name,
                'trip_name': trip_name,
                'trip_date': trip_date
            }

            subject, message = render_template('trip_announcement', template_vars)

            if not subject or not message:
                print("Failed to load email template.")
                return

            if not self._send_email_via_gui(alumni_email, subject, message):
                self._show_email_fallback_dialog(alumni_email, subject, message)

