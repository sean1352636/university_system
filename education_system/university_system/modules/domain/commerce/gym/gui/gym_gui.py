"""
Gym/Fitness Center GUI

Provides a comprehensive GUI for university gym services including
memberships, class bookings, equipment, and personal training with
email and finance integration.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from typing import Optional, Dict, List

from education_system.university_system.modules.shared.utils.i18n import get_text as _t
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

from education_system.university_system.modules.domain.commerce.gym.services.gym_core import (
    MembershipManager, ClassManager, PTSessionManager, EquipmentManager,
    TransactionManager, ReportManager, init_gym_db,
    MEMBERSHIP_TYPES, CLASS_TYPES, PT_SESSION_FEES,
    generate_reference
)

try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    EMAIL_AVAILABLE = True
except ImportError:
    EMAIL_AVAILABLE = False
    def send_email(*args, **kwargs): return False
    render_template = None


def _send_gym_email(recipient: str, subject: str, body: str) -> bool:
    """Helper function to send emails with proper error handling and logging."""
    if not EMAIL_AVAILABLE:
        print(f"[Gym] Email service not available - would send to {recipient}: {subject}")
        return False
    if not recipient:
        print(f"[Gym] No recipient email provided for: {subject}")
        return False
    try:
        result = send_email(recipient, subject, body)
        if result:
            log_activity('email_sent', 'gym', details={'to': recipient, 'subject': subject})
            print(f"[Gym] Email sent successfully to {recipient}: {subject}")
            return True
        else:
            print(f"[Gym] Email send returned False for {recipient}: {subject}")
            return False
    except Exception as e:
        print(f"[Gym] Email send error for {recipient}: {e}")
        log_activity('email_failed', 'gym', details={'to': recipient, 'subject': subject, 'error': str(e)})
        return False


class GymGUI:
    """Gym/Fitness Center GUI with 25 functions."""

    def __init__(self, root, auth):
        """Function 1: Initialize the Gym GUI."""
        self.root = root
        self.auth = auth
        self.current_user = auth.current_user if auth else None
        if not self.current_user:
            messagebox.showerror(_t("gym.window_title"), _t("gym.errors.login_required"))
            root.destroy()
            return
        self.user_id = self.current_user.get('username', 'unknown')
        self.user_role = self.current_user.get('role', 'student')
        self.user_email = self.current_user.get('email', '')

        # If email not in current_user, fetch from database
        if not self.user_email:
            self.user_email = self._get_user_email()

        self.current_report = None
        self.membership = None
        self._init_database()
        self._load_membership()
        self.create_widgets()

    def _get_user_email(self) -> str:
        """Fetch user email from the users table."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute(
                    "SELECT email FROM users WHERE username = ?",
                    (self.user_id,)
                )
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
        except Exception as e:
            print(f"Error fetching user email: {e}")
        return ''

    def create_widgets(self):
        """Function 2: Create all GUI widgets."""
        self.root.title(_t("gym.window_title"))
        header = ttk.Frame(self.root, padding="10")
        header.pack(fill=tk.X)
        ttk.Label(header, text=_t("gym.title"), font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        ttk.Label(header, text=f"User: {self.user_id} | Role: {self.user_role}").pack(side=tk.RIGHT)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.create_membership_tab()
        self.create_classes_tab()
        self.create_pt_tab()
        self.create_equipment_tab()
        if self.user_role in ('admin', 'staff'):
            self.create_payments_tab()
            self.create_admin_tab()
        footer = ttk.Frame(self.root, padding="10")
        footer.pack(fill=tk.X)
        ttk.Button(footer, text=_t("common.refresh"), command=self.refresh_all_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(footer, text=_t("common.close"), command=self.return_to_homescreen).pack(side=tk.RIGHT, padx=5)

    def _init_database(self):
        """Function 3: Initialize database tables."""
        try:
            if not init_gym_db():
                messagebox.showwarning(_t("gym.window_title"), _t("gym.warnings.db_init"))
        except Exception as e:
            messagebox.showwarning(_t("gym.window_title"), f"DB init error: {e}")

    def return_to_homescreen(self):
        """Function 4: Close window."""
        self.root.destroy()

    def refresh_all_data(self):
        """Function 5: Refresh all data."""
        self._load_membership()
        self._refresh_membership_info()
        self._refresh_classes_list()
        self._refresh_bookings_list()
        self._refresh_equipment_list()
        if self.user_role in ('admin', 'staff'):
            self._refresh_payments_list()
        messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.data_refreshed"))

    def _load_membership(self):
        self.membership = MembershipManager.get_membership(user_id=self.user_id)

    def create_membership_tab(self):
        """Function 6: Create membership tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("gym.tabs.membership"))
        self.membership_frame = ttk.LabelFrame(tab, text=_t("gym.my_membership"), padding="10")
        self.membership_frame.pack(fill=tk.X, pady=(0, 10))
        self.membership_info_label = ttk.Label(self.membership_frame, text="")
        self.membership_info_label.pack()
        options_frame = ttk.LabelFrame(tab, text=_t("gym.membership_options"), padding="10")
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        columns = ('type', 'monthly_fee', 'features')
        self.membership_tree = ttk.Treeview(options_frame, columns=columns, show='headings', height=6)
        self.membership_tree.heading('type', text=_t("gym.labels.membership_type"))
        self.membership_tree.heading('monthly_fee', text=_t("gym.labels.monthly_fee"))
        self.membership_tree.heading('features', text=_t("gym.labels.features"))
        for mtype, info in MEMBERSHIP_TYPES.items():
            self.membership_tree.insert('', tk.END, values=(info['name'], f"GBP {info['monthly_fee']:.2f}", ', '.join(info['features'])))
        self.membership_tree.pack(fill=tk.BOTH, expand=True)
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X)
        ttk.Button(action_frame, text=_t("gym.btn.join"), command=self.join_gym).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("gym.btn.renew"), command=self.renew_membership).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("gym.btn.cancel_membership"), command=self.cancel_membership).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("gym.btn.check_in"), command=self.check_in).pack(side=tk.LEFT, padx=5)
        self._refresh_membership_info()

    def join_gym(self):
        """Function 7: Join the gym."""
        if self.membership:
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.already_member"))
            return
        selected = self.membership_tree.selection()
        if not selected:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.select_membership"))
            return
        type_name = self.membership_tree.item(selected[0])['values'][0]
        membership_type = next((k for k, v in MEMBERSHIP_TYPES.items() if v['name'] == type_name), None)
        if not membership_type:
            return
        months = simpledialog.askinteger(_t("gym.window_title"), _t("gym.prompts.membership_months"), minvalue=1, maxvalue=12)
        if not months:
            return
        total_fee = MEMBERSHIP_TYPES[membership_type]['monthly_fee'] * months

        # Show payment method selection dialog
        payment_method = self._show_payment_dialog(total_fee, f"Gym Membership - {type_name} ({months} months)")
        if not payment_method:
            return  # User cancelled payment selection

        emergency_contact = simpledialog.askstring(_t("gym.window_title"), _t("gym.prompts.emergency_contact"))
        emergency_phone = simpledialog.askstring(_t("gym.window_title"), _t("gym.prompts.emergency_phone"))

        # Handle student account payment
        if payment_method == 'Student Account':
            if not self._deduct_from_student_account(total_fee):
                messagebox.showerror(_t("gym.window_title"), "Payment failed. Please try another payment method.")
                return

        result = MembershipManager.create_membership(user_id=self.user_id, user_name=self.user_id, user_email=self.user_email, membership_type=membership_type, months=months, emergency_contact=emergency_contact, emergency_phone=emergency_phone, created_by=self.user_id)
        if result:
            self.process_payment('membership', total_fee, f"Gym membership - {type_name}")
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.membership_created").format(member_number=result['member_number']))
            self._load_membership()
            self._refresh_membership_info()
            # Send membership confirmation email
            user_email = self.user_email or self._get_user_email()
            if user_email:
                features_list = '\n'.join('- ' + f for f in MEMBERSHIP_TYPES[membership_type]['features'])
                # Render email from template
                subject, body = render_template('commerce/gym/membership_confirmation', {
                    'member_name': self.user_id,
                    'member_number': result['member_number'],
                    'membership_type': type_name,
                    'duration': f"{months} month(s)",
                    'start_date': result.get('start_date', datetime.now().strftime('%Y-%m-%d')),
                    'end_date': result.get('end_date', 'N/A'),
                    'amount': f"GBP {total_fee:.2f}",
                    'payment_method': payment_method,
                    'features_list': features_list,
                    'emergency_contact': emergency_contact or 'Not provided',
                    'emergency_phone': emergency_phone or 'Not provided'
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Gym Membership Confirmation"
                    body = f"""Dear {self.user_id},

Welcome to the University Gym! Your membership has been confirmed.

MEMBERSHIP DETAILS
==================
Member Number: {result['member_number']}
Membership Type: {type_name}
Duration: {months} month(s)
Start Date: {result.get('start_date', datetime.now().strftime('%Y-%m-%d'))}
End Date: {result.get('end_date', 'N/A')}
Total Paid: GBP {total_fee:.2f}
Payment Method: {payment_method}

FEATURES INCLUDED
{features_list}

Emergency Contact: {emergency_contact or 'Not provided'}
Emergency Phone: {emergency_phone or 'Not provided'}

You can now access the gym facilities during operating hours. Remember to check in each visit.

University Gym & Fitness Center"""
                if _send_gym_email(user_email, subject, body):
                    messagebox.showinfo(_t("gym.window_title"), f"Confirmation email sent to {user_email}")
            else:
                print("[Gym] No email address on file for membership confirmation")

    def renew_membership(self):
        """Function 8: Renew membership."""
        if not self.membership:
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.no_membership"))
            return
        months = simpledialog.askinteger(_t("gym.window_title"), _t("gym.prompts.renewal_months"), minvalue=1, maxvalue=12)
        if not months:
            return
        total_fee = self.membership['monthly_fee'] * months

        # Show payment method selection dialog
        payment_method = self._show_payment_dialog(total_fee, f"Gym Membership Renewal ({months} months)")
        if not payment_method:
            return  # User cancelled payment selection

        # Handle student account payment
        if payment_method == 'Student Account':
            if not self._deduct_from_student_account(total_fee):
                messagebox.showerror(_t("gym.window_title"), "Payment failed. Please try another payment method.")
                return

        result = MembershipManager.renew_membership(self.membership['membership_id'], months)
        if result:
            self.process_payment('membership_renewal', total_fee, "Gym membership renewal")
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.membership_renewed").format(end_date=result['new_end_date']))
            self._load_membership()
            self._refresh_membership_info()
            # Send renewal confirmation email
            user_email = self.user_email or self._get_user_email()
            if user_email:
                # Render email from template
                subject, body = render_template('commerce/gym/membership_renewal', {
                    'member_name': self.user_id,
                    'member_number': self.membership['member_number'],
                    'membership_type': self.membership['membership_type'],
                    'renewal_period': f"{months} month(s)",
                    'new_end_date': result['new_end_date'],
                    'amount': f"GBP {total_fee:.2f}",
                    'payment_method': payment_method
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Gym Membership Renewal Confirmation"
                    body = f"""Dear {self.user_id},

Your gym membership has been successfully renewed.

RENEWAL DETAILS
===============
Member Number: {self.membership['member_number']}
Membership Type: {self.membership['membership_type']}
Renewal Period: {months} month(s)
New Expiry Date: {result['new_end_date']}
Amount Paid: GBP {total_fee:.2f}
Payment Method: {payment_method}

Thank you for continuing with us!

University Gym & Fitness Center"""
                if _send_gym_email(user_email, subject, body):
                    messagebox.showinfo(_t("gym.window_title"), f"Renewal confirmation email sent to {user_email}")
            else:
                print("[Gym] No email address on file for renewal confirmation")

    def cancel_membership(self):
        """Function 9: Cancel membership."""
        if not self.membership:
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.no_membership"))
            return
        if messagebox.askyesno(_t("gym.window_title"), _t("gym.confirm.cancel_membership")):
            # Store membership details before cancellation
            member_number = self.membership['member_number']
            membership_type = self.membership['membership_type']
            end_date = self.membership['end_date']

            if MembershipManager.cancel_membership(self.membership['membership_id']):
                messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.membership_cancelled"))
                # Send cancellation email
                user_email = self.user_email or self._get_user_email()
                if user_email:
                    # Render email from template
                    subject, body = render_template('commerce/gym/membership_cancellation', {
                        'member_name': self.user_id,
                        'member_number': member_number,
                        'membership_type': membership_type,
                        'original_end_date': end_date,
                        'cancellation_date': datetime.now().strftime('%Y-%m-%d')
                    })

                    # Fallback if template not found
                    if not subject or not body:
                        subject = "Gym Membership Cancellation Confirmation"
                        body = f"""Dear {self.user_id},

Your gym membership has been cancelled as requested.

CANCELLED MEMBERSHIP DETAILS
============================
Member Number: {member_number}
Membership Type: {membership_type}
Original End Date: {end_date}
Cancellation Date: {datetime.now().strftime('%Y-%m-%d')}

We're sorry to see you go. If you wish to rejoin in the future, you can sign up for a new membership at any time through the Gym portal.

If you did not request this cancellation, please contact us immediately.

University Gym & Fitness Center"""
                    if _send_gym_email(user_email, subject, body):
                        messagebox.showinfo(_t("gym.window_title"), f"Cancellation confirmation email sent to {user_email}")
                else:
                    print("[Gym] No email address on file for cancellation confirmation")
                self._load_membership()
                self._refresh_membership_info()

    def check_in(self):
        """Function 10: Check in to gym."""
        if not self.membership or self.membership['status'] != 'active':
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.no_active_membership"))
            return
        if MembershipManager.check_in(self.membership['membership_id']):
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.checked_in"))

    def _refresh_membership_info(self):
        if self.membership:
            info = f"Member #: {self.membership['member_number']} | Type: {self.membership['membership_type']} | Status: {self.membership['status']} | Expires: {self.membership['end_date']}"
        else:
            info = _t("gym.messages.no_membership_info")
        self.membership_info_label.config(text=info)

    def create_classes_tab(self):
        """Function 11: Create classes tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("gym.tabs.classes"))
        classes_frame = ttk.LabelFrame(tab, text=_t("gym.available_classes"), padding="5")
        classes_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        columns = ('name', 'type', 'instructor', 'day', 'time', 'spots')
        self.classes_tree = ttk.Treeview(classes_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.classes_tree.heading(col, text=col.title())
            self.classes_tree.column(col, width=80)
        self.classes_tree.pack(fill=tk.BOTH, expand=True)
        bookings_frame = ttk.LabelFrame(tab, text=_t("gym.my_bookings"), padding="5")
        bookings_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        columns = ('class', 'date', 'time', 'status')
        self.bookings_tree = ttk.Treeview(bookings_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.bookings_tree.heading(col, text=col.title())
            self.bookings_tree.column(col, width=80)
        self.bookings_tree.pack(fill=tk.BOTH, expand=True)
        action_frame = ttk.Frame(bookings_frame)
        action_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(action_frame, text=_t("gym.btn.book_class"), command=self.book_class).pack(side=tk.LEFT, padx=2)
        ttk.Button(action_frame, text=_t("gym.btn.cancel_booking"), command=self.cancel_class_booking).pack(side=tk.LEFT, padx=2)
        self._refresh_classes_list()
        self._refresh_bookings_list()

    def book_class(self):
        """Function 12: Book a fitness class."""
        if not self.membership or self.membership['status'] != 'active':
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.no_active_membership"))
            return
        selected = self.classes_tree.selection()
        if not selected:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.select_class"))
            return

        # Get class details
        values = self.classes_tree.item(selected[0])['values']
        class_name = values[0]
        class_type = values[1]
        instructor = values[2]
        schedule_day = values[3]
        schedule_time = values[4]

        classes = ClassManager.get_all_classes()
        gym_class = next((c for c in classes if c['class_name'] == class_name), None)
        if not gym_class:
            return
        booking_date = simpledialog.askstring(_t("gym.window_title"), _t("gym.prompts.booking_date"), initialvalue=datetime.now().strftime('%Y-%m-%d'))
        if not booking_date:
            return
        result = ClassManager.book_class(class_id=gym_class['class_id'], member_id=self.membership['membership_id'], booking_date=booking_date)
        if result:
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.class_booked").format(booking_ref=result['booking_ref']))
            self._refresh_classes_list()
            self._refresh_bookings_list()

            # Send confirmation email
            user_email = self.user_email or self._get_user_email()
            if user_email:
                # Render email from template
                subject, body = render_template('commerce/gym/class_booking', {
                    'member_name': self.user_id,
                    'booking_ref': result['booking_ref'],
                    'class_name': class_name,
                    'class_type': class_type,
                    'instructor': instructor,
                    'schedule_day': schedule_day,
                    'schedule_time': schedule_time,
                    'booking_date': booking_date
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Fitness Class Booking Confirmation"
                    body = f"""Dear {self.user_id},

Your fitness class has been booked successfully.

CLASS DETAILS
=============
Booking Reference: {result['booking_ref']}
Class: {class_name}
Type: {class_type}
Instructor: {instructor}
Day: {schedule_day}
Time: {schedule_time}
Booking Date: {booking_date}

Please arrive 5-10 minutes early. Classes are included with your gym membership.

University Gym & Fitness Center"""
                if _send_gym_email(user_email, subject, body):
                    messagebox.showinfo(_t("gym.window_title"), f"Confirmation email sent to {user_email}")
            else:
                print("[Gym] No email address on file for class booking confirmation")
        else:
            messagebox.showerror(_t("gym.window_title"), _t("gym.errors.booking_failed"))

    def cancel_class_booking(self):
        """Function 13: Cancel class booking."""
        selected = self.bookings_tree.selection()
        if not selected:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.select_booking"))
            return

        # Get booking details before cancellation
        values = self.bookings_tree.item(selected[0])['values']
        class_name = values[0]
        booking_date = values[1]
        booking_time = values[2]

        if messagebox.askyesno(_t("gym.window_title"), _t("gym.confirm.cancel_booking")):
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.booking_cancelled"))

            # Send cancellation email
            user_email = self.user_email or self._get_user_email()
            if user_email:
                # Render email from template
                subject, body = render_template('commerce/gym/class_cancellation', {
                    'member_name': self.user_id,
                    'class_name': class_name,
                    'booking_date': booking_date,
                    'booking_time': booking_time,
                    'cancellation_date': datetime.now().strftime('%Y-%m-%d')
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Fitness Class Booking Cancelled"
                    body = f"""Dear {self.user_id},

Your fitness class booking has been cancelled as requested.

CANCELLED BOOKING DETAILS
=========================
Class: {class_name}
Date: {booking_date}
Time: {booking_time}
Cancellation Date: {datetime.now().strftime('%Y-%m-%d')}

To book another class, please visit the Gym portal.

University Gym & Fitness Center"""
                if _send_gym_email(user_email, subject, body):
                    messagebox.showinfo(_t("gym.window_title"), f"Cancellation email sent to {user_email}")
            else:
                print("[Gym] No email address on file for class cancellation")

            self._refresh_bookings_list()

    def view_class_schedule(self):
        """Function 14: View class schedule."""
        classes = ClassManager.get_all_classes()
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("gym.class_schedule"))
        dialog.geometry("700x500")
        text = tk.Text(dialog, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        for day in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
            day_classes = [c for c in classes if c['schedule_day'] == day]
            if day_classes:
                text.insert(tk.END, f"\n=== {day} ===\n")
                for c in sorted(day_classes, key=lambda x: x['start_time']):
                    text.insert(tk.END, f"  {c['start_time']}: {c['class_name']} - {c['instructor_name']}\n")

    def _refresh_classes_list(self):
        for item in self.classes_tree.get_children():
            self.classes_tree.delete(item)
        for cls in ClassManager.get_all_classes():
            spots = cls['max_capacity'] - cls['current_enrolled']
            self.classes_tree.insert('', tk.END, values=(cls['class_name'], cls['class_type'], cls['instructor_name'], cls['schedule_day'], cls['start_time'], f"{spots}/{cls['max_capacity']}"))

    def _refresh_bookings_list(self):
        for item in self.bookings_tree.get_children():
            self.bookings_tree.delete(item)
        if self.membership:
            for b in ClassManager.get_member_bookings(self.membership['membership_id']):
                self.bookings_tree.insert('', tk.END, values=(b['class_name'], b['booking_date'], b['start_time'], b['status']))

    def create_pt_tab(self):
        """Function 15: Create personal training tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("gym.tabs.personal_training"))
        info_frame = ttk.LabelFrame(tab, text=_t("gym.pt_info"), padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(info_frame, text=_t("gym.labels.pt_pricing")).pack(anchor=tk.W)
        for stype, fee in PT_SESSION_FEES.items():
            ttk.Label(info_frame, text=f"  {stype}: GBP {fee:.2f}").pack(anchor=tk.W)
        booking_frame = ttk.LabelFrame(tab, text=_t("gym.book_pt_session"), padding="10")
        booking_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(booking_frame, text=_t("gym.labels.trainer") + ":").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.trainer_var = tk.StringVar()
        ttk.Combobox(booking_frame, textvariable=self.trainer_var, values=['Mike Thompson', 'Sarah Johnson', 'James Brown', 'Emma Wilson'], width=30).grid(row=0, column=1, pady=2)
        ttk.Label(booking_frame, text=_t("gym.labels.session_date") + ":").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.pt_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(booking_frame, textvariable=self.pt_date_var, width=33).grid(row=1, column=1, pady=2)
        ttk.Label(booking_frame, text=_t("gym.labels.session_time") + ":").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.pt_time_var = tk.StringVar()
        ttk.Combobox(booking_frame, textvariable=self.pt_time_var, values=['09:00', '10:00', '11:00', '14:00', '15:00', '16:00', '17:00'], width=30).grid(row=2, column=1, pady=2)
        ttk.Label(booking_frame, text=_t("gym.labels.session_type") + ":").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.pt_type_var = tk.StringVar(value='single')
        ttk.Combobox(booking_frame, textvariable=self.pt_type_var, values=list(PT_SESSION_FEES.keys()), width=30).grid(row=3, column=1, pady=2)
        ttk.Button(booking_frame, text=_t("gym.btn.book_pt"), command=self.book_pt_session).grid(row=4, column=1, pady=10)
        sessions_frame = ttk.LabelFrame(tab, text=_t("gym.my_pt_sessions"), padding="5")
        sessions_frame.pack(fill=tk.BOTH, expand=True)
        columns = ('date', 'time', 'trainer', 'type', 'status')
        self.pt_tree = ttk.Treeview(sessions_frame, columns=columns, show='headings', height=8)
        for col in columns:
            self.pt_tree.heading(col, text=col.title())
            self.pt_tree.column(col, width=80)
        self.pt_tree.pack(fill=tk.BOTH, expand=True)
        self._refresh_pt_sessions()

    def book_pt_session(self):
        """Function 16: Book PT session."""
        if not self.membership or self.membership['status'] != 'active':
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.no_active_membership"))
            return
        if not self.trainer_var.get() or not self.pt_date_var.get() or not self.pt_time_var.get():
            messagebox.showerror(_t("gym.window_title"), _t("gym.errors.fill_required"))
            return
        session_type = self.pt_type_var.get()
        trainer_name = self.trainer_var.get()
        session_date = self.pt_date_var.get()
        session_time = self.pt_time_var.get()
        fee = PT_SESSION_FEES.get(session_type, PT_SESSION_FEES['single'])

        # Show payment method selection dialog
        payment_method = self._show_payment_dialog(fee, f"Personal Training - {session_type}")
        if not payment_method:
            return  # User cancelled

        # Handle student account payment
        if payment_method == 'Student Account':
            if not self._deduct_from_student_account(fee):
                messagebox.showerror(_t("gym.window_title"), "Payment failed. Please try another payment method.")
                return

        result = PTSessionManager.book_session(member_id=self.membership['membership_id'], trainer_name=trainer_name, session_date=session_date, session_time=session_time, session_type=session_type)
        if result:
            self.process_payment('pt_session', fee, f"Personal training - {session_type}")
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.pt_booked").format(booking_ref=result['booking_ref']))
            self._refresh_pt_sessions()

            # Send confirmation email
            user_email = self.user_email or self._get_user_email()
            if user_email:
                # Render email from template
                subject, body = render_template('commerce/gym/pt_session_booking', {
                    'member_name': self.user_id,
                    'booking_ref': result['booking_ref'],
                    'trainer_name': trainer_name,
                    'session_date': session_date,
                    'session_time': session_time,
                    'session_type': session_type,
                    'fee': f"GBP {fee:.2f}",
                    'payment_method': payment_method
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Personal Training Session Confirmation"
                    body = f"""Dear {self.user_id},

Your personal training session has been booked successfully.

SESSION DETAILS
===============
Booking Reference: {result['booking_ref']}
Trainer: {trainer_name}
Date: {session_date}
Time: {session_time}
Session Type: {session_type}
Fee: GBP {fee:.2f}
Payment Method: {payment_method}

Please arrive 5 minutes early for your session. If you need to cancel or reschedule, please do so at least 24 hours in advance.

University Gym & Fitness Center"""
                if _send_gym_email(user_email, subject, body):
                    messagebox.showinfo(_t("gym.window_title"), f"Confirmation email sent to {user_email}")
            else:
                print("[Gym] No email address on file for PT booking confirmation")

    def cancel_pt_session(self):
        """Function 17: Cancel PT session."""
        selected = self.pt_tree.selection()
        if not selected:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.select_session"))
            return

        # Get session details before cancellation
        values = self.pt_tree.item(selected[0])['values']
        session_date = values[0]
        session_time = values[1]
        trainer_name = values[2]
        session_type = values[3]

        if messagebox.askyesno(_t("gym.window_title"), _t("gym.confirm.cancel_pt")):
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.pt_cancelled"))

            # Send cancellation email
            user_email = self.user_email or self._get_user_email()
            if user_email:
                # Render email from template
                subject, body = render_template('commerce/gym/pt_session_cancellation', {
                    'member_name': self.user_id,
                    'trainer_name': trainer_name,
                    'session_date': session_date,
                    'session_time': session_time,
                    'session_type': session_type,
                    'cancellation_date': datetime.now().strftime('%Y-%m-%d')
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Personal Training Session Cancelled"
                    body = f"""Dear {self.user_id},

Your personal training session has been cancelled as requested.

CANCELLED SESSION DETAILS
=========================
Trainer: {trainer_name}
Date: {session_date}
Time: {session_time}
Session Type: {session_type}
Cancellation Date: {datetime.now().strftime('%Y-%m-%d')}

To book a new session, please visit the Gym portal.

University Gym & Fitness Center"""
                if _send_gym_email(user_email, subject, body):
                    messagebox.showinfo(_t("gym.window_title"), f"Cancellation email sent to {user_email}")
            else:
                print("[Gym] No email address on file for PT cancellation")

            self._refresh_pt_sessions()

    def _refresh_pt_sessions(self):
        for item in self.pt_tree.get_children():
            self.pt_tree.delete(item)
        if self.membership:
            for s in PTSessionManager.get_member_sessions(self.membership['membership_id']):
                self.pt_tree.insert('', tk.END, values=(s['session_date'], s['session_time'], s['trainer_name'], s['session_type'], s['status']))

    def create_equipment_tab(self):
        """Function 18: Create equipment tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("gym.tabs.equipment"))
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(filter_frame, text=_t("gym.labels.category") + ":").pack(side=tk.LEFT)
        self.equipment_category_var = tk.StringVar(value='all')
        ttk.Combobox(filter_frame, textvariable=self.equipment_category_var, values=['all', 'cardio', 'strength', 'free_weights', 'machines', 'accessories'], width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(filter_frame, text=_t("gym.btn.filter"), command=self._refresh_equipment_list).pack(side=tk.LEFT)
        list_frame = ttk.LabelFrame(tab, text=_t("gym.equipment_list"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        columns = ('name', 'category', 'location', 'status')
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)
        for col in columns:
            self.equipment_tree.heading(col, text=col.title())
            self.equipment_tree.column(col, width=120)
        self.equipment_tree.pack(fill=tk.BOTH, expand=True)
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X)
        ttk.Button(action_frame, text=_t("gym.btn.report_issue"), command=self.report_equipment_issue).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("gym.btn.view_equipment"), command=self.view_equipment_details).pack(side=tk.LEFT, padx=5)
        self._refresh_equipment_list()

    def report_equipment_issue(self):
        """Function 19: Report equipment issue."""
        selected = self.equipment_tree.selection()
        if not selected:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.select_equipment"))
            return
        issue = simpledialog.askstring(_t("gym.window_title"), _t("gym.prompts.describe_issue"))
        if issue:
            messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.issue_reported"))

    def view_equipment_details(self):
        """Function 20: View equipment details."""
        selected = self.equipment_tree.selection()
        if not selected:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.errors.select_equipment"))
            return
        values = self.equipment_tree.item(selected[0])['values']
        messagebox.showinfo(_t("gym.equipment_details"), f"Name: {values[0]}\nCategory: {values[1]}\nLocation: {values[2]}\nStatus: {values[3]}")

    def _refresh_equipment_list(self):
        for item in self.equipment_tree.get_children():
            self.equipment_tree.delete(item)
        category = self.equipment_category_var.get()
        if category == 'all':
            category = None
        for e in EquipmentManager.get_all_equipment(category=category):
            self.equipment_tree.insert('', tk.END, values=(e['equipment_name'], e['category'], e.get('location', 'Main Floor'), e['status']))

    def create_payments_tab(self):
        """Create payments and refunds tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text="Payments & Refunds")

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_frame, text=_t("gym.labels.payments_header"),
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W)
        ttk.Label(header_frame, text=_t("gym.labels.payments_note"),
                 font=('Arial', 9, 'italic'), foreground='gray').pack(anchor=tk.W)

        # Search/Filter frame
        search_frame = ttk.LabelFrame(tab, text=_t("gym.labels.search_payments"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_t("gym.labels.user_id")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.payment_search_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=self.payment_search_var, width=20).grid(row=0, column=1, padx=5)

        ttk.Button(search_frame, text=_t("gym.btn.search"), command=self._refresh_payments_list).grid(row=0, column=2, padx=5)
        ttk.Button(search_frame, text=_t("gym.btn.show_all"), command=lambda: [self.payment_search_var.set(''), self._refresh_payments_list()]).grid(row=0, column=3, padx=5)

        # Payments list frame
        list_frame = ttk.LabelFrame(tab, text=_t("gym.labels.membership_pt_only"), padding="5")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        columns = ('transaction_id', 'reference', 'user_id', 'type', 'amount', 'method', 'date', 'status')
        self.payments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.payments_tree.heading('transaction_id', text=_t('gym.columns.id'))
        self.payments_tree.heading('reference', text=_t('gym.columns.reference'))
        self.payments_tree.heading('user_id', text=_t('gym.columns.user_id'))
        self.payments_tree.heading('type', text=_t('gym.columns.type'))
        self.payments_tree.heading('amount', text=_t('gym.columns.amount_gbp'))
        self.payments_tree.heading('method', text=_t('gym.columns.method'))
        self.payments_tree.heading('date', text=_t('gym.columns.date'))
        self.payments_tree.heading('status', text=_t('gym.columns.status'))

        self.payments_tree.column('transaction_id', width=50)
        self.payments_tree.column('reference', width=120)
        self.payments_tree.column('user_id', width=100)
        self.payments_tree.column('type', width=120)
        self.payments_tree.column('amount', width=80)
        self.payments_tree.column('method', width=80)
        self.payments_tree.column('date', width=120)
        self.payments_tree.column('status', width=80)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.payments_tree.yview)
        self.payments_tree.configure(yscrollcommand=scrollbar.set)

        self.payments_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons frame
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X)

        ttk.Button(action_frame, text=_t("gym.btn.process_refund"), command=self.process_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("gym.btn.view_details"), command=self.view_payment_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text=_t("gym.btn.export_csv"), command=self.export_payments_csv).pack(side=tk.LEFT, padx=5)

        self._refresh_payments_list()

    def create_admin_tab(self):
        """Function 21: Create admin tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_t("gym.tabs.admin"))
        stats_frame = ttk.LabelFrame(tab, text=_t("gym.membership_stats"), padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 10))
        self.stats_label = ttk.Label(stats_frame, text="")
        self.stats_label.pack()
        ttk.Button(stats_frame, text=_t("gym.btn.refresh_stats"), command=self._refresh_stats).pack(pady=5)
        report_frame = ttk.LabelFrame(tab, text=_t("gym.reports.title"), padding="10")
        report_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(report_frame, text=_t("gym.labels.report_type") + ":").grid(row=0, column=0, sticky=tk.W)
        self.report_type_var = tk.StringVar(value='daily')
        ttk.Combobox(report_frame, textvariable=self.report_type_var, values=['daily', 'monthly', 'membership'], width=20).grid(row=0, column=1, padx=5)
        ttk.Button(report_frame, text=_t("gym.btn.generate_report"), command=self.generate_admin_report).grid(row=0, column=2, padx=5)
        ttk.Button(report_frame, text=_t("gym.btn.email_report"), command=self.email_admin_report).grid(row=0, column=3, padx=5)
        output_frame = ttk.LabelFrame(tab, text=_t("gym.report_output"), padding="5")
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.report_text = tk.Text(output_frame, height=15, wrap=tk.WORD)
        self.report_text.pack(fill=tk.BOTH, expand=True)
        self._refresh_stats()

    def view_all_members(self):
        """Function 22: View all members."""
        members = MembershipManager.get_all_memberships()
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("gym.all_members"))
        dialog.geometry("800x500")
        columns = ('member_number', 'name', 'type', 'status', 'end_date')
        tree = ttk.Treeview(dialog, columns=columns, show='headings')
        for col in columns:
            tree.heading(col, text=col.replace('_', ' ').title())
        for m in members:
            tree.insert('', tk.END, values=(m['member_number'], m['user_name'], m['membership_type'], m['status'], m['end_date']))
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def generate_admin_report(self):
        """Function 23: Generate admin report."""
        report_type = self.report_type_var.get()
        if report_type == 'daily':
            data = ReportManager.get_daily_attendance()
            report = f"=== Daily Attendance Report ===\nDate: {data.get('date', 'N/A')}\nCheck-ins: {data.get('check_ins', 0)}\nRevenue: GBP {data.get('revenue', 0):.2f}"
        elif report_type == 'membership':
            data = ReportManager.get_membership_stats()
            report = f"=== Membership Statistics ===\nTotal Active: {data.get('total_active', 0)}\n\nBy Type:\n"
            for mtype, info in data.get('by_type', {}).items():
                report += f"  {mtype}: {info['count']} (GBP {info['revenue']:.2f}/month)\n"
        else:
            data = ReportManager.get_monthly_summary()
            report = f"=== Monthly Summary ===\nPeriod: {data.get('month', '')}/{data.get('year', '')}\nRevenue: GBP {data.get('total_revenue', 0):.2f}\nNew Members: {data.get('new_members', 0)}\nClass Bookings: {data.get('class_bookings', 0)}"
        self.current_report = report
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", report)
        messagebox.showinfo(_t("gym.window_title"), _t("gym.messages.report_generated"))

    def _get_admin_emails(self) -> List[str]:
        """Get email addresses of all admin users."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT email FROM users
                    WHERE role = 'admin' AND email IS NOT NULL AND email != ''
                ''')
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting admin emails: {e}")
            return []

    def email_admin_report(self):
        """Function 24: Email report to admin automatically."""
        if not self.current_report:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.warnings.generate_report_first"))
            return

        if not EMAIL_AVAILABLE:
            messagebox.showwarning(_t("gym.window_title"), _t("gym.warnings.email_unavailable"))
            return

        # Auto-detect admin emails
        admin_emails = self._get_admin_emails()

        if not admin_emails:
            # Fallback: prompt for email if no admins found
            admin_email = simpledialog.askstring(
                _t("gym.window_title"),
                "No admin emails found. Enter admin email manually:"
            )
            if admin_email:
                admin_emails = [admin_email]
            else:
                return

        # Send report to all admins
        subject = f"Gym Report - {datetime.now().strftime('%Y-%m-%d')}"
        success_count = 0
        for email in admin_emails:
            if _send_gym_email(email, subject, self.current_report):
                success_count += 1

        if success_count > 0:
            messagebox.showinfo(
                _t("gym.window_title"),
                f"Report sent to {success_count} admin(s): {', '.join(admin_emails)}"
            )
        else:
            messagebox.showerror(_t("gym.window_title"), _t("gym.errors.email_failed"))

    def _refresh_stats(self):
        stats = ReportManager.get_membership_stats()
        self.stats_label.config(text=f"Total Active Members: {stats.get('total_active', 0)}")

    def _get_student_account_balance(self) -> Optional[float]:
        """Get student's finance account balance."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (self.user_id,))
                row = cursor.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            print(f"Error getting student balance: {e}")
            return None

    def _deduct_from_student_account(self, amount: float) -> bool:
        """Deduct amount from student's finance account."""
        try:
            from education_system.university_system.infrastructure.database.db import transaction as db_transaction
            with db_transaction() as conn:
                # Get account_id and balance
                cursor = conn.execute('''
                    SELECT account_id, balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (self.user_id,))
                row = cursor.fetchone()
                if not row or float(row[1]) < amount:
                    return False

                account_id = row[0]
                balance_before = float(row[1])
                balance_after = balance_before - amount

                # Deduct from balance
                conn.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ?
                ''', (balance_after, account_id))

                # Record transaction with account_id
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before, balance_after, description, created_at)
                    VALUES ('student_finance', ?, ?, 'debit', ?, ?, ?, 'Gym Payment', CURRENT_TIMESTAMP)
                ''', (account_id, self.user_id, amount, balance_before, balance_after))
            return True
        except Exception as e:
            print(f"Error deducting from student account: {e}")
            return False

    def _refresh_payments_list(self):
        """Refresh the payments list - ONLY BOOKINGS (membership, membership_renewal, pt_session)."""
        for item in self.payments_tree.get_children():
            self.payments_tree.delete(item)

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                search_term = self.payment_search_var.get().strip()

                # Only show bookings: membership, membership_renewal, pt_session
                if search_term:
                    cursor = conn.execute('''
                        SELECT transaction_id, reference_number, student_id, transaction_type,
                               amount, payment_method, created_at, status
                        FROM transactions
                        WHERE source_type = 'gym' AND transaction_type IN ('membership', 'membership_renewal', 'pt_session')
                          AND student_id LIKE ?
                        ORDER BY created_at DESC
                    ''', (f'%{search_term}%',))
                else:
                    cursor = conn.execute('''
                        SELECT transaction_id, reference_number, student_id, transaction_type,
                               amount, payment_method, created_at, status
                        FROM transactions
                        WHERE source_type = 'gym' AND transaction_type IN ('membership', 'membership_renewal', 'pt_session')
                        ORDER BY created_at DESC
                        LIMIT 100
                    ''')

                for row in cursor.fetchall():
                    # Ensure all 8 values are present, use defaults for None
                    values = list(row)
                    while len(values) < 8:
                        values.append('N/A')
                    # Format amount as currency if it's a number
                    if values[4] and values[4] != 'N/A':
                        try:
                            values[4] = f"{float(values[4]):.2f}"
                        except (ValueError, TypeError):
                            pass
                    self.payments_tree.insert('', tk.END, values=values)
        except Exception as e:
            print(f"Error loading payments: {e}")
            messagebox.showerror(_t("gym.msg_titles.error"), f"Failed to load payments: {e}")

    def view_payment_details(self):
        """View detailed payment information."""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_t("gym.msg_titles.no_selection"), "Please select a payment to view details")
            return

        try:
            values = self.payments_tree.item(selection[0])['values']

            # Ensure we have all required values
            if len(values) < 8:
                messagebox.showerror(_t("gym.msg_titles.data_error"),
                    "Payment record is incomplete. Please refresh the list and try again.")
                return

            details = f"""PAYMENT DETAILS
================
Transaction ID: {values[0]}
Reference: {values[1]}
User ID: {values[2]}
Type: {values[3]}
Amount: GBP {values[4]}
Payment Method: {values[5]}
Date: {values[6]}
Status: {values[7]}
"""
            messagebox.showinfo(_t("gym.msg_titles.payment_details"), details)
        except Exception as e:
            messagebox.showerror(_t("gym.msg_titles.error"), f"Error viewing payment details: {e}")

    def export_payments_csv(self):
        """Export payments to CSV file."""
        try:
            from tkinter import filedialog
            import csv

            filepath = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile=f"gym_payments_{datetime.now().strftime('%Y%m%d')}.csv"
            )

            if filepath:
                with open(filepath, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Transaction ID', 'Reference', 'User ID', 'Type',
                                   'Amount', 'Method', 'Date', 'Status'])

                    for item in self.payments_tree.get_children():
                        values = self.payments_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo(_t("gym.msg_titles.export_successful"), f"Payments exported to:\n{filepath}")
                log_activity('export', 'gym_payments', details={'file': filepath})
        except Exception as e:
            messagebox.showerror(_t("gym.msg_titles.export_error"), f"Failed to export payments: {e}")

    def process_refund(self):
        """Process a refund with cash/card/student account options."""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_t("gym.msg_titles.no_selection"), "Please select a payment to refund")
            return

        try:
            values = self.payments_tree.item(selection[0])['values']

            # Ensure we have all required values
            if len(values) < 8:
                messagebox.showerror(_t("gym.msg_titles.data_error"),
                    "Payment record is incomplete. Please refresh the list and try again.")
                return

            transaction_id = values[0]
            reference = values[1]
            user_id = values[2]
            transaction_type = values[3]
            amount = float(values[4])
            status = values[7]
        except (IndexError, ValueError) as e:
            messagebox.showerror(_t("gym.msg_titles.error"), f"Error reading payment data: {e}")
            return

        if status == 'refunded':
            messagebox.showinfo(_t("gym.msg_titles.refund_already_made"), "Refund already made")
            return

        # Confirm refund
        if not messagebox.askyesno(_t("gym.msg_titles.confirm_refund"),
                                   f"Refund GBP {amount:.2f} to {user_id}?\n\n"
                                   f"Transaction: {reference}\n"
                                   f"Type: {transaction_type}"):
            return

        # Show refund method selection dialog
        refund_method = self._show_refund_method_dialog(amount, user_id)
        if not refund_method:
            return

        # Process based on method
        success = False
        if refund_method == 'Student Account':
            success = self._add_to_student_account(user_id, amount, reference)
        else:
            # For cash/card, just record the refund
            success = True

        if success:
            # Update transaction status to refunded
            try:
                from education_system.university_system.infrastructure.database.db import transaction as db_transaction
                with db_transaction() as conn:
                    conn.execute('''
                        UPDATE transactions
                        SET status = 'refunded'
                        WHERE source_type = 'gym' AND transaction_id = ?
                    ''', (transaction_id,))

                    # Record refund transaction
                    refund_ref = f"REFUND-{generate_reference()}"
                    conn.execute('''
                        INSERT INTO transactions
                        (source_type, reference_number, student_id, transaction_type, amount, payment_method, status, processed_by)
                        VALUES ('gym', ?, ?, ?, ?, ?, 'completed', ?)
                    ''', (refund_ref, user_id, f'refund_{transaction_type}', amount,
                          refund_method.lower().replace(' ', '_'), self.user_id))

                # Send refund receipt email
                self._send_refund_receipt(user_id, amount, refund_method, reference, refund_ref)

                # Notify finance GUI
                self._notify_finance_gui(user_id, amount, refund_method, refund_ref)

                messagebox.showinfo(_t("gym.msg_titles.refund_processed"),
                                  f"Refund of GBP {amount:.2f} processed successfully\n\n"
                                  f"Method: {refund_method}\n"
                                  f"Refund Reference: {refund_ref}")

                log_activity('refund', 'gym_payment', details={
                    'original_ref': reference,
                    'refund_ref': refund_ref,
                    'amount': amount,
                    'method': refund_method,
                    'user_id': user_id,
                    'processed_by': self.user_id
                })

                self._refresh_payments_list()
            except Exception as e:
                messagebox.showerror(_t("gym.msg_titles.refund_error"), f"Failed to process refund: {e}")
        else:
            messagebox.showerror(_t("gym.msg_titles.refund_failed"), "Failed to process student account refund")

    def _show_refund_method_dialog(self, amount: float, user_id: str) -> Optional[str]:
        """Show refund method selection dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Refund Method")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        result = {'method': None}

        # Refund info frame
        info_frame = ttk.LabelFrame(dialog, text=_t("gym.labels.refund_details"), padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"User ID: {user_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Refund Amount: GBP {amount:.2f}",
                 font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance
        balance = self._get_student_account_balance_for_user(user_id)
        if balance is not None:
            ttk.Label(info_frame, text=f"Current Account Balance: GBP {balance:.2f}").pack(
                anchor=tk.W, pady=(5, 0))
            ttk.Label(info_frame, text=f"Balance After Refund: GBP {balance + amount:.2f}",
                     foreground='green').pack(anchor=tk.W)

        # Refund method selection
        method_frame = ttk.LabelFrame(dialog, text=_t("gym.labels.select_refund_method"), padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        ttk.Button(method_frame, text=_t("gym.btn.cash"), width=20,
                  command=lambda: select_method('Cash')).pack(pady=5)

        # Card button
        ttk.Button(method_frame, text=_t("gym.btn.card_original"), width=30,
                  command=lambda: select_method('Card')).pack(pady=5)

        # Student Account button
        ttk.Button(method_frame, text=_t("gym.btn.student_finance"), width=30,
                  command=lambda: select_method('Student Account')).pack(pady=5)

        # Cancel button
        ttk.Button(dialog, text=_t("gym.btn.cancel_refund"), command=dialog.destroy).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def _get_student_account_balance_for_user(self, user_id: str) -> Optional[float]:
        """Get student's finance account balance by user ID."""
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute('''
                    SELECT balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (user_id,))
                row = cursor.fetchone()
                return float(row[0]) if row else None
        except Exception as e:
            print(f"Error getting student balance: {e}")
            return None

    def _add_to_student_account(self, user_id: str, amount: float, original_ref: str) -> bool:
        """Add refund amount to student's finance account."""
        try:
            from education_system.university_system.infrastructure.database.db import transaction as db_transaction
            with db_transaction() as conn:
                # Get account_id and balance
                cursor = conn.execute('''
                    SELECT account_id, balance FROM student_finance_accounts
                    WHERE student_id = ? AND account_status = 'active'
                ''', (user_id,))
                row = cursor.fetchone()

                if not row:
                    # Try to create account if it doesn't exist
                    cursor = conn.execute('''
                        INSERT INTO student_finance_accounts
                        (student_id, account_type, balance, account_status, created_at)
                        VALUES (?, 'standard', ?, 'active', CURRENT_TIMESTAMP)
                    ''', (user_id, amount))
                    account_id = cursor.lastrowid
                    balance_before = 0
                    balance_after = amount
                else:
                    account_id = row[0]
                    balance_before = float(row[1])
                    balance_after = balance_before + amount

                    # Add to balance
                    conn.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE account_id = ?
                    ''', (balance_after, account_id))

                # Record transaction
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before,
                     balance_after, description, created_at)
                    VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (account_id, user_id, amount, balance_before, balance_after,
                      f'Gym Refund - Ref: {original_ref}'))

            return True
        except Exception as e:
            print(f"Error adding to student account: {e}")
            return False

    def _send_refund_receipt(self, user_id: str, amount: float, method: str,
                            original_ref: str, refund_ref: str):
        """Send refund receipt email to user."""
        try:
            # Get user email
            from education_system.university_system.infrastructure.database.db import get_connection
            with get_connection() as conn:
                cursor = conn.execute("SELECT email FROM users WHERE username = ?", (user_id,))
                row = cursor.fetchone()
                email = row[0] if row and row[0] else None

            if email:
                # Get balance text for student account
                balance_text = ""
                if method == 'Student Account':
                    balance = self._get_student_account_balance_for_user(user_id)
                    if balance is not None:
                        balance_text = f"Your new Student Finance Account balance: GBP {balance:.2f}"

                # Render email from template
                subject, body = render_template('commerce/gym/refund_receipt', {
                    'member_name': user_id,
                    'refund_ref': refund_ref,
                    'original_ref': original_ref,
                    'refund_amount': f"GBP {amount:.2f}",
                    'refund_method': method,
                    'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'processed_by': self.user_id,
                    'balance_text': balance_text
                })

                # Fallback if template not found
                if not subject or not body:
                    subject = "Gym Payment Refund Receipt"
                    body = f"""Dear {user_id},

Your gym payment refund has been processed successfully.

REFUND RECEIPT
==============
Refund Reference: {refund_ref}
Original Payment Ref: {original_ref}
Refund Amount: GBP {amount:.2f}
Refund Method: {method}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
Processed By: {self.user_id}

"""
                    if balance_text:
                        body += f"\n{balance_text}\n"

                    body += """\nIf you have any questions about this refund, please contact the Gym reception.

University Gym & Fitness Center"""

                if _send_gym_email(email, subject, body):
                    print(f"[Gym] Refund receipt sent to {email}")
            else:
                print(f"[Gym] No email found for user {user_id}")
        except Exception as e:
            print(f"Error sending refund receipt: {e}")

    def _notify_finance_gui(self, user_id: str, amount: float, method: str, refund_ref: str):
        """Record refund in finance system for integration."""
        try:
            from education_system.university_system.infrastructure.database.db import transaction as db_transaction
            from datetime import datetime
            with db_transaction() as conn:
                # Insert into unified refunds table
                try:
                    conn.execute('''
                        INSERT INTO unified_refunds
                        (student_id, refund_reference, source_type, reference_type,
                         amount, refund_method, refund_date, processed_by, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        refund_ref,
                        'gym',
                        'gym_service',
                        amount,
                        method.lower().replace(' ', '_'),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        self.user_id,
                        'Gym Service Refund'
                    ))
                    print(f"[Gym] Refund recorded in finance system: {refund_ref}")
                except Exception as e:
                    print(f"[Gym] Error recording refund in finance system: {e}")
                    import traceback
                    traceback.print_exc()
        except Exception as e:
            print(f"Error notifying finance GUI: {e}")

    def _show_payment_dialog(self, amount: float, description: str) -> Optional[str]:
        """Show payment method selection dialog. Returns payment method or None if cancelled."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Payment Method")
        dialog.geometry("400x350")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        result = {'method': None}

        # Payment info frame
        info_frame = ttk.LabelFrame(dialog, text=_t("gym.msg_titles.payment_details"), padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Description: {description}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Amount Due: GBP {amount:.2f}", font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Student account balance
        balance = self._get_student_account_balance()
        if balance is not None:
            ttk.Label(info_frame, text=f"Student Account Balance: GBP {balance:.2f}").pack(anchor=tk.W, pady=(5, 0))
            if balance < amount:
                ttk.Label(info_frame, text=_t("gym.labels.insufficient_funds"), foreground='red').pack(anchor=tk.W)

        # Payment method selection
        method_frame = ttk.LabelFrame(dialog, text=_t("gym.labels.select_payment_method"), padding="10")
        method_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_method(method):
            result['method'] = method
            dialog.destroy()

        # Cash button
        ttk.Button(method_frame, text=_t("gym.btn.cash"), width=20,
                  command=lambda: select_method('cash')).pack(pady=5)

        # Card button
        ttk.Button(method_frame, text=_t("gym.btn.card"), width=20,
                  command=lambda: select_method('card')).pack(pady=5)

        # Student Account button
        account_btn = ttk.Button(method_frame, text=_t("gym.btn.student_account"), width=20,
                                command=lambda: select_method('Student Account'))
        account_btn.pack(pady=5)

        # Disable student account if insufficient funds
        if balance is None or balance < amount:
            account_btn.config(state='disabled')

        # Cancel button
        ttk.Button(dialog, text=_t("gym.btn.cancel_refund"), command=dialog.destroy).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def process_payment(self, transaction_type: str, amount: float, description: str):
        """Function 25: Process payment with finance integration."""
        try:
            result = TransactionManager.record_payment(
                user_id=self.user_id,
                transaction_type=transaction_type,
                amount=amount,
                payment_method='account',
                member_id=self.membership['membership_id'] if self.membership else None,
                processed_by=self.user_id
            )
            if result:
                # Record payment in central payments table for finance integration
                try:
                    from education_system.university_system.infrastructure.database.db import transaction as db_transaction
                    with db_transaction() as conn:
                        # Insert into payments table for finance tracking
                        conn.execute('''
                            INSERT INTO payments
                            (student_id, amount, payment_method, payment_date, status, notes, created_by)
                            VALUES (?, ?, ?, date("now"), ?, ?, ?)
                        ''', (self.user_id, amount, 'gym_service', 'completed',
                              f"Gym: {description} (Ref: {result['reference']})", self.user_id))

                        # Try to record revenue for finance reporting
                        try:
                            conn.execute('''
                                INSERT INTO service_payments
                                (service_type, user_id, amount, reference, description, payment_date)
                                VALUES (?, ?, ?, ?, ?, date("now"))
                            ''', ('gym_fitness', self.user_id, amount, result['reference'], description))
                        except Exception:
                            pass  # Table may not exist
                except Exception as e:
                    print(f"Finance integration error: {e}")

                # Send detailed receipt email
                user_email = self.user_email or self._get_user_email()
                if user_email:
                    member_number = self.membership.get('member_number', 'N/A') if self.membership else 'N/A'
                    receipt_subject = "Gym Payment Receipt"
                    # Render email from template
                    receipt_subject, receipt_body = render_template('commerce/gym/payment_receipt', {
                        'member_name': self.user_id,
                        'reference': result['reference'],
                        'payment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'description': description,
                        'amount': f"GBP {amount:.2f}",
                        'payment_method': 'Account',
                        'member_number': member_number
                    })

                    # Fallback if template not found
                    if not receipt_subject or not receipt_body:
                        receipt_subject = "Gym Payment Receipt"
                        receipt_body = f"""Dear {self.user_id},

Thank you for your payment to the University Gym & Fitness Center.

PAYMENT RECEIPT
===============
Reference: {result['reference']}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Description: {description}
Amount Paid: GBP {amount:.2f}
Payment Method: Account
Status: Completed

Member Number: {member_number}

If you have any questions about this payment, please contact the Gym reception.

University Gym & Fitness Center"""
                    if _send_gym_email(user_email, receipt_subject, receipt_body):
                        print(f"[Gym] Receipt email sent to {user_email}")
                else:
                    print("[Gym] No email address on file for payment receipt")

                log_activity('payment', 'gym_service',
                            details={'amount': amount, 'type': transaction_type, 'ref': result['reference'],
                                    'user_id': self.user_id, 'description': description})
                return result
        except Exception as e:
            print(f"Payment error: {e}")
        return None


def launch_gym_gui(root=None, auth=None):
    """Launch the Gym GUI."""
    if root is None:
        root = tk.Tk()
    GymGUI(root, auth)
    return root
