
from education_system.systems.university.infrastructure.i18n import get_text as _t
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from tkinter.simpledialog import askstring, askinteger
import threading
import json
from datetime import datetime, timedelta
import webbrowser
import os
import subprocess
import sys
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Import internationalisation (i18n) for multi‑language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: kwargs.get("default", key)
    get_current_language = lambda: "en"

# Add the project root to Python path if not already there
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from education_system.systems.university.shell.gui.email.email_gui.email_manager_main import EmailManagerGUI

try:
    from education_system.systems.university.infrastructure.utils.email_service import (
        send_appointment_confirmation,
        send_health_notification,
        send_internship_notification,
        send_mentorship_notification,
        send_alumni_welcome_email,
        send_event_invitation,
        send_donation_receipt,
        send_application_confirmation,
        send_permit_confirmation,
        send_permit_update_confirmation,
    )
except ImportError:
    send_appointment_confirmation = None
    send_health_notification = None
    send_internship_notification = None
    send_mentorship_notification = None
    send_alumni_welcome_email = None
    send_event_invitation = None
    send_donation_receipt = None
    send_application_confirmation = None
    send_permit_confirmation = None
    send_permit_update_confirmation = None

class AppointmentConfirmationDialog:
    """Dialog for sending appointment confirmation emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_appointment_confirmation', default="Send Appointment Confirmation"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.appointment_id', default="Appointment ID:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.appointment_id_entry = ttk.Entry(main_frame, width=40)
        self.appointment_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.date_yyyy_mm_dd', default="Date (YYYY-MM-DD):")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.date_entry = ttk.Entry(main_frame, width=40)
        self.date_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.time_hh_mm', default="Time (HH:MM):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.time_entry = ttk.Entry(main_frame, width=40)
        self.time_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.provider', default="Provider:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.provider_entry = ttk.Entry(main_frame, width=40)
        self.provider_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.appointment_type', default="Appointment Type:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.type_entry = ttk.Entry(main_frame, width=40)
        self.type_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        if not all([self.student_id_entry.get(), self.appointment_id_entry.get(),
                    self.date_entry.get(), self.time_entry.get(),
                    self.provider_entry.get(), self.type_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_all_fields', default="Please fill in all fields"))
            return

        try:
            if send_appointment_confirmation is not None:
                if send_appointment_confirmation(
                    self.student_id_entry.get().strip(),
                    self.appointment_id_entry.get().strip(),
                    self.date_entry.get().strip(),
                    self.time_entry.get().strip(),
                    self.provider_entry.get().strip(),
                    self.type_entry.get().strip()
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.appointment_confirmation_sent', default="Appointment confirmation sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_confirmation', default="Failed to send confirmation"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class HealthNotificationDialog:
    """Dialog for sending health advisory notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_health_advisory', default="Send Health Advisory"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.advisory_title', default="Advisory Title:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.severity', default="Severity:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.severity_var = tk.StringVar(value=_t('gui.shell.email.email_gui.notification_dialogs_other.values.low', default="low"))
        severity_frame = ttk.Frame(main_frame)
        severity_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(severity_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.low', default="Low"), variable=self.severity_var, value="low").pack(side=tk.LEFT)
        ttk.Radiobutton(severity_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.medium', default="Medium"), variable=self.severity_var, value="medium").pack(side=tk.LEFT)
        ttk.Radiobutton(severity_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.high', default="High"), variable=self.severity_var, value="high").pack(side=tk.LEFT)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.description', default="Description:")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.description_text = scrolledtext.ScrolledText(main_frame, width=40, height=10)
        self.description_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def send_notification(self):
        if not all([self.student_id_entry.get(), self.title_entry.get(),
                    self.description_text.get(1.0, tk.END).strip()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_all_fields', default="Please fill in all fields"))
            return

        try:
            if send_health_notification is not None:
                if send_health_notification(
                    self.student_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.description_text.get(1.0, tk.END).strip(),
                    self.severity_var.get()
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.health_advisory_sent', default="Health advisory sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_advisory', default="Failed to send advisory"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class InternshipNotificationDialog:
    """Dialog for sending internship status notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_internship_notification', default="Send Internship Notification"))
        self.dialog.geometry("500x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.internship_id', default="Internship ID:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.internship_id_entry = ttk.Entry(main_frame, width=40)
        self.internship_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.status', default="Status:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.status_var = tk.StringVar(value=_t('gui.shell.email.email_gui.notification_dialogs_other.values.accepted', default="accepted"))
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=2, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(status_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.accepted', default="Accepted"), variable=self.status_var, value="accepted").pack(side=tk.LEFT)
        ttk.Radiobutton(status_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.rejected', default="Rejected"), variable=self.status_var, value="rejected").pack(side=tk.LEFT)
        ttk.Radiobutton(status_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.pending', default="Pending"), variable=self.status_var, value="pending").pack(side=tk.LEFT)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.feedback_optional', default="Feedback (optional):")).grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.feedback_text = scrolledtext.ScrolledText(main_frame, width=40, height=8)
        self.feedback_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def send_notification(self):
        if not all([self.student_id_entry.get(), self.internship_id_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_required_fields', default="Please fill in required fields"))
            return

        try:
            if send_internship_notification is not None:
                feedback = self.feedback_text.get(1.0, tk.END).strip() or None
                if send_internship_notification(
                    self.student_id_entry.get().strip(),
                    self.internship_id_entry.get().strip(),
                    self.status_var.get(),
                    feedback
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.internship_notification_sent', default="Internship notification sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_notification', default="Failed to send notification"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class MentorshipNotificationDialog:
    """Dialog for sending mentorship pairing notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_mentorship_notification', default="Send Mentorship Notification"))
        self.dialog.geometry("500x450")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.mentor_email', default="Mentor Email:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.mentor_email_entry = ttk.Entry(main_frame, width=40)
        self.mentor_email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.mentee_email', default="Mentee Email:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.mentee_email_entry = ttk.Entry(main_frame, width=40)
        self.mentee_email_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.mentor_name', default="Mentor Name:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.mentor_name_entry = ttk.Entry(main_frame, width=40)
        self.mentor_name_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.mentee_name', default="Mentee Name:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.mentee_name_entry = ttk.Entry(main_frame, width=40)
        self.mentee_name_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.focus_area', default="Focus Area:")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.focus_entry = ttk.Entry(main_frame, width=40)
        self.focus_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.start_date_yyyy_mm_dd', default="Start Date (YYYY-MM-DD):")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ttk.Entry(main_frame, width=40)
        self.start_date_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.end_date_optional', default="End Date (optional):")).grid(row=6, column=0, sticky=tk.W, pady=5)
        self.end_date_entry = ttk.Entry(main_frame, width=40)
        self.end_date_entry.grid(row=6, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        if not all([self.mentor_email_entry.get(), self.mentee_email_entry.get(),
                    self.mentor_name_entry.get(), self.mentee_name_entry.get(),
                    self.focus_entry.get(), self.start_date_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_required_fields', default="Please fill in required fields"))
            return

        try:
            if send_mentorship_notification is not None:
                end_date = self.end_date_entry.get().strip() or None
                if send_mentorship_notification(
                    self.mentor_email_entry.get().strip(),
                    self.mentee_email_entry.get().strip(),
                    self.mentor_name_entry.get().strip(),
                    self.mentee_name_entry.get().strip(),
                    self.focus_entry.get().strip(),
                    self.start_date_entry.get().strip(),
                    end_date
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.mentorship_notification_sent', default="Mentorship notification sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_notification', default="Failed to send notification"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class AlumniWelcomeDialog:
    """Dialog for sending alumni welcome emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_alumni_welcome_email', default="Send Alumni Welcome Email"))
        self.dialog.geometry("450x250")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.alumni_id', default="Alumni ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.alumni_id_entry = ttk.Entry(main_frame, width=40)
        self.alumni_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.email_address', default="Email Address:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.full_name', default="Full Name:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=40)
        self.name_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_welcome).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_welcome(self):
        if not all([self.alumni_id_entry.get(), self.email_entry.get(), self.name_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_all_fields', default="Please fill in all fields"))
            return

        try:
            if send_alumni_welcome_email is not None:
                if send_alumni_welcome_email(
                    self.alumni_id_entry.get().strip(),
                    self.email_entry.get().strip(),
                    self.name_entry.get().strip()
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.welcome_email_sent', default="Welcome email sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_email', default="Failed to send email"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class EventInvitationDialog:
    """Dialog for sending event invitations"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_event_invitation', default="Send Event Invitation"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.alumni_id', default="Alumni ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.alumni_id_entry = ttk.Entry(main_frame, width=40)
        self.alumni_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.event_id_optional', default="Event ID (optional):")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.event_id_entry = ttk.Entry(main_frame, width=40)
        self.event_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.email_address', default="Email Address:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.event_name', default="Event Name:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.event_name_entry = ttk.Entry(main_frame, width=40)
        self.event_name_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.event_date_yyyy_mm_dd', default="Event Date (YYYY-MM-DD):")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.event_date_entry = ttk.Entry(main_frame, width=40)
        self.event_date_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.event_location', default="Event Location:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.location_entry = ttk.Entry(main_frame, width=40)
        self.location_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_invitation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_invitation(self):
        if not all([self.alumni_id_entry.get(), self.email_entry.get(),
                    self.event_name_entry.get(), self.event_date_entry.get(),
                    self.location_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_required_fields', default="Please fill in required fields"))
            return

        try:
            if send_event_invitation is not None:
                event_id = self.event_id_entry.get().strip() or None
                if send_event_invitation(
                    self.alumni_id_entry.get().strip(),
                    event_id,
                    self.email_entry.get().strip(),
                    self.event_name_entry.get().strip(),
                    self.event_date_entry.get().strip(),
                    self.location_entry.get().strip()
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.event_invitation_sent', default="Event invitation sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_invitation', default="Failed to send invitation"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class DonationReceiptDialog:
    """Dialog for sending donation receipts"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_donation_receipt', default="Send Donation Receipt"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.alumni_id', default="Alumni ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.alumni_id_entry = ttk.Entry(main_frame, width=40)
        self.alumni_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.donation_id_optional', default="Donation ID (optional):")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.donation_id_entry = ttk.Entry(main_frame, width=40)
        self.donation_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.email_address', default="Email Address:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.amount', default="Amount ($):")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.amount_entry = ttk.Entry(main_frame, width=40)
        self.amount_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.date_yyyy_mm_dd', default="Date (YYYY-MM-DD):")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.date_entry = ttk.Entry(main_frame, width=40)
        self.date_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.purpose', default="Purpose:")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.purpose_entry = ttk.Entry(main_frame, width=40)
        self.purpose_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_receipt).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_receipt(self):
        if not all([self.alumni_id_entry.get(), self.email_entry.get(),
                    self.amount_entry.get(), self.date_entry.get(), self.purpose_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_required_fields', default="Please fill in required fields"))
            return

        try:
            if send_donation_receipt is not None:
                donation_id = self.donation_id_entry.get().strip() or None
                if send_donation_receipt(
                    self.alumni_id_entry.get().strip(),
                    donation_id,
                    self.email_entry.get().strip(),
                    self.amount_entry.get().strip(),
                    self.date_entry.get().strip(),
                    self.purpose_entry.get().strip()
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.donation_receipt_sent', default="Donation receipt sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_receipt', default="Failed to send receipt"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class ApplicationConfirmationDialog:
    """Dialog for sending internship application confirmation"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_internship_application_confirmation', default="Send Internship Application Confirmation"))
        self.dialog.geometry("500x200")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.student_id', default="Student ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.internship_id', default="Internship ID:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.internship_id_entry = ttk.Entry(main_frame, width=40)
        self.internship_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        if not all([self.student_id_entry.get(), self.internship_id_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_all_fields', default="Please fill in all fields"))
            return

        try:
            if send_application_confirmation is not None:
                if send_application_confirmation(
                    self.student_id_entry.get().strip(),
                    self.internship_id_entry.get().strip()
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.application_confirmation_sent', default="Application confirmation sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_confirmation', default="Failed to send confirmation"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class PermitConfirmationDialog:
    """Dialog for sending parking permit confirmation"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_permit_confirmation', default="Send Permit Confirmation"))
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.permit_id', default="Permit ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.permit_id_entry = ttk.Entry(main_frame, width=40)
        self.permit_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.email', default="Email:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.zone', default="Zone:")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.zone_entry = ttk.Entry(main_frame, width=40)
        self.zone_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.permit_type', default="Permit Type:")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.type_entry = ttk.Entry(main_frame, width=40)
        self.type_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.start_date_yyyy_mm_dd', default="Start Date (YYYY-MM-DD):")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.start_date_entry = ttk.Entry(main_frame, width=40)
        self.start_date_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.end_date_yyyy_mm_dd', default="End Date (YYYY-MM-DD):")).grid(row=5, column=0, sticky=tk.W, pady=5)
        self.end_date_entry = ttk.Entry(main_frame, width=40)
        self.end_date_entry.grid(row=5, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=6, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        if not all([self.permit_id_entry.get(), self.email_entry.get(), self.zone_entry.get(),
                   self.type_entry.get(), self.start_date_entry.get(), self.end_date_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_all_fields', default="Please fill in all fields"))
            return

        try:
            if send_permit_confirmation is not None:
                if send_permit_confirmation(
                    self.permit_id_entry.get().strip(),
                    self.email_entry.get().strip(),
                    self.zone_entry.get().strip(),
                    self.type_entry.get().strip(),
                    self.start_date_entry.get().strip(),
                    self.end_date_entry.get().strip()
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.permit_confirmation_sent', default="Permit confirmation sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_confirmation', default="Failed to send confirmation"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


class PermitUpdateConfirmationDialog:
    """Dialog for sending permit update confirmation"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t('gui.shell.email.email_gui.notification_dialogs_other.windows.send_permit_update_confirmation', default="Send Permit Update Confirmation"))
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.permit_id', default="Permit ID:")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.permit_id_entry = ttk.Entry(main_frame, width=40)
        self.permit_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.email', default="Email:")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.labels.updated_fields_one_per_line', default="Updated Fields (one per line):")).grid(row=2, column=0, sticky=tk.NW, pady=5)
        self.fields_text = scrolledtext.ScrolledText(main_frame, width=40, height=8)
        self.fields_text.grid(row=2, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.send', default="Send"), command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t('gui.shell.email.email_gui.notification_dialogs_other.buttons.cancel', default="Cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

    def send_confirmation(self):
        if not all([self.permit_id_entry.get(), self.email_entry.get()]):
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.please_fill_in_required_fields', default="Please fill in required fields"))
            return

        updated_fields = [f.strip() for f in self.fields_text.get(1.0, tk.END).split('\n') if f.strip()]

        try:
            if send_permit_update_confirmation is not None:
                if send_permit_update_confirmation(
                    self.permit_id_entry.get().strip(),
                    self.email_entry.get().strip(),
                    updated_fields
                ):
                    messagebox.showinfo(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.success', default="Success"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.permit_update_confirmation_sent', default="Permit update confirmation sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.failed_to_send_confirmation', default="Failed to send confirmation"))
            else:
                messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), _t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.function_not_available', default="Function not available"))
        except Exception as e:
            messagebox.showerror(_t('gui.shell.email.email_gui.notification_dialogs_other.dialogs.error', default="Error"), f"Error: {e}")


def send_appointment_confirmation_dialog(self):
    """Open appointment confirmation dialog"""
    AppointmentConfirmationDialog(self.root)

EmailManagerGUI.send_appointment_confirmation_dialog = send_appointment_confirmation_dialog

def send_health_notification_dialog(self):
    """Open health advisory notification dialog"""
    HealthNotificationDialog(self.root)

EmailManagerGUI.send_health_notification_dialog = send_health_notification_dialog

def send_internship_notification_dialog(self):
    """Open internship notification dialog"""
    InternshipNotificationDialog(self.root)

EmailManagerGUI.send_internship_notification_dialog = send_internship_notification_dialog

def send_mentorship_notification_dialog(self):
    """Open mentorship notification dialog"""
    MentorshipNotificationDialog(self.root)

EmailManagerGUI.send_mentorship_notification_dialog = send_mentorship_notification_dialog

def send_alumni_welcome_dialog(self):
    """Open alumni welcome email dialog"""
    AlumniWelcomeDialog(self.root)

EmailManagerGUI.send_alumni_welcome_dialog = send_alumni_welcome_dialog

def send_event_invitation_dialog(self):
    """Open event invitation dialog"""
    EventInvitationDialog(self.root)

EmailManagerGUI.send_event_invitation_dialog = send_event_invitation_dialog

def send_donation_receipt_dialog(self):
    """Open donation receipt dialog"""
    DonationReceiptDialog(self.root)

EmailManagerGUI.send_donation_receipt_dialog = send_donation_receipt_dialog

def send_application_confirmation_dialog(self):
    """Open internship application confirmation dialog"""
    ApplicationConfirmationDialog(self.root)

EmailManagerGUI.send_application_confirmation_dialog = send_application_confirmation_dialog

def send_permit_confirmation_dialog(self):
    """Open permit confirmation dialog"""
    PermitConfirmationDialog(self.root)

EmailManagerGUI.send_permit_confirmation_dialog = send_permit_confirmation_dialog

def send_permit_update_confirmation_dialog(self):
    """Open permit update confirmation dialog"""
    PermitUpdateConfirmationDialog(self.root)

EmailManagerGUI.send_permit_update_confirmation_dialog = send_permit_update_confirmation_dialog

