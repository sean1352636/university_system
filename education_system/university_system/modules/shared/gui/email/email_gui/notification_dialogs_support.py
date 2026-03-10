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
    from education_system.university_system.modules.shared.utils.i18n import (
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

from .email_manager_main import EmailManagerGUI

class TicketNotificationDialog:
    """Dialog for sending helpdesk ticket notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Ticket Notification")
        self.dialog.geometry("500x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Ticket ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ticket_id_entry = ttk.Entry(main_frame, width=40)
        self.ticket_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=40)
        self.subject_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(main_frame, width=40)
        self.username_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Admin Emails (comma-separated):").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.admins_text = scrolledtext.ScrolledText(main_frame, width=40, height=6)
        self.admins_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

    def send_notification(self):
        if not all([self.ticket_id_entry.get(), self.subject_entry.get(), self.username_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        admin_list = [a.strip() for a in self.admins_text.get(1.0, tk.END).split(',') if a.strip()] or None

        try:
            if send_ticket_notification is not None:
                if send_ticket_notification(
                    self.ticket_id_entry.get().strip(),
                    self.subject_entry.get().strip(),
                    self.username_entry.get().strip(),
                    admin_list
                ):
                    messagebox.showinfo("Success", "Ticket notification sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")


class ReplyNotificationDialog:
    """Dialog for sending ticket reply notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Reply Notification")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Ticket ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ticket_id_entry = ttk.Entry(main_frame, width=40)
        self.ticket_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="User ID (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(main_frame, width=40)
        self.username_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Responder:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.responder_entry = ttk.Entry(main_frame, width=40)
        self.responder_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Status Update (optional):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.status_entry = ttk.Entry(main_frame, width=40)
        self.status_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        if not all([self.ticket_id_entry.get(), self.username_entry.get(), self.responder_entry.get()]):
            messagebox.showerror("Error", "Please fill in required fields")
            return

        try:
            if send_reply_notification is not None:
                user_id = self.user_id_entry.get().strip() or None
                status = self.status_entry.get().strip() or None

                if send_reply_notification(
                    self.ticket_id_entry.get().strip(),
                    user_id,
                    self.username_entry.get().strip(),
                    self.responder_entry.get().strip(),
                    None,  # admin_list
                    status
                ):
                    messagebox.showinfo("Success", "Reply notification sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")


class SLAAlertDialog:
    """Dialog for sending SLA alert notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send SLA Alert")
        self.dialog.geometry("500x250")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Ticket ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ticket_id_entry = ttk.Entry(main_frame, width=40)
        self.ticket_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Alert Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.alert_type_var = tk.StringVar(value='overdue')
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=1, column=1, sticky=tk.W, pady=5)
        ttk.Radiobutton(type_frame, text="Overdue", variable=self.alert_type_var, value='overdue').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(type_frame, text="Warning", variable=self.alert_type_var, value='warning').pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_alert).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_alert(self):
        if not self.ticket_id_entry.get():
            messagebox.showerror("Error", "Please enter ticket ID")
            return

        try:
            if send_sla_alert is not None:
                if send_sla_alert(
                    self.ticket_id_entry.get().strip(),
                    self.alert_type_var.get()
                ):
                    messagebox.showinfo("Success", "SLA alert sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send alert")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")


class SatisfactionSurveyDialog:
    """Dialog for sending satisfaction survey"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Satisfaction Survey")
        self.dialog.geometry("500x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Ticket ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.ticket_id_entry = ttk.Entry(main_frame, width=40)
        self.ticket_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Custom Message (optional):").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.message_text = scrolledtext.ScrolledText(main_frame, width=40, height=8)
        self.message_text.grid(row=1, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_survey).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def send_survey(self):
        if not self.ticket_id_entry.get():
            messagebox.showerror("Error", "Please enter ticket ID")
            return

        custom_message = self.message_text.get(1.0, tk.END).strip() or None

        try:
            if send_satisfaction_survey is not None:
                if send_satisfaction_survey(
                    self.ticket_id_entry.get().strip(),
                    custom_message
                ):
                    messagebox.showinfo("Success", "Satisfaction survey sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send survey")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")


class BulkSatisfactionSurveysDialog:
    """Dialog for sending bulk satisfaction surveys"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Bulk Satisfaction Surveys")
        self.dialog.geometry("450x200")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Send surveys to tickets closed within:").pack(pady=10)

        days_frame = ttk.Frame(main_frame)
        days_frame.pack(pady=10)

        ttk.Label(days_frame, text="Days:").pack(side=tk.LEFT, padx=5)
        self.days_spinbox = ttk.Spinbox(days_frame, from_=1, to=30, width=10)
        self.days_spinbox.set(1)
        self.days_spinbox.pack(side=tk.LEFT, padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Send Surveys", command=self.send_surveys).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def send_surveys(self):
        try:
            days = int(self.days_spinbox.get())
            if send_bulk_satisfaction_surveys is not None:
                if send_bulk_satisfaction_surveys(days):
                    messagebox.showinfo("Success", f"Bulk satisfaction surveys sent for tickets closed in last {days} day(s)")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send bulk surveys")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")


def send_ticket_notification_dialog(self):
    """Open ticket notification dialog"""
    TicketNotificationDialog(self.root)

EmailManagerGUI.send_ticket_notification_dialog = send_ticket_notification_dialog

def send_reply_notification_dialog(self):
    """Open reply notification dialog"""
    ReplyNotificationDialog(self.root)

EmailManagerGUI.send_reply_notification_dialog = send_reply_notification_dialog

def send_sla_alert_dialog(self):
    """Open SLA alert dialog"""
    SLAAlertDialog(self.root)

EmailManagerGUI.send_sla_alert_dialog = send_sla_alert_dialog

def send_satisfaction_survey_dialog(self):
    """Open satisfaction survey dialog"""
    SatisfactionSurveyDialog(self.root)

EmailManagerGUI.send_satisfaction_survey_dialog = send_satisfaction_survey_dialog

def send_bulk_satisfaction_surveys_dialog(self):
    """Open bulk satisfaction surveys dialog"""
    BulkSatisfactionSurveysDialog(self.root)

EmailManagerGUI.send_bulk_satisfaction_surveys_dialog = send_bulk_satisfaction_surveys_dialog

