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
    from university_system.modules.shared.utils.i18n import (
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

class RegistrationConfirmationDialog:
    """Dialog for sending registration confirmation emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Registration Confirmation")
        self.dialog.geometry("400x200")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=30)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        student_id = self.student_id_entry.get().strip()

        if not student_id:
            messagebox.showerror("Error", "Please enter a student ID")
            return

        try:
            if send_registration_confirmation is not None:
                if send_registration_confirmation(student_id):
                    messagebox.showinfo("Success", "Registration confirmation sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send confirmation. Student may not exist.")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending confirmation: {e}")


class AssignmentNotificationDialog:
    """Dialog for sending assignment notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Assignment Notification")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Assignment ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.assignment_id_entry = ttk.Entry(main_frame, width=40)
        self.assignment_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Assignment Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Description:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.description_text = scrolledtext.ScrolledText(main_frame, width=40, height=8)
        self.description_text.grid(row=4, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

    def send_notification(self):
        assignment_id = self.assignment_id_entry.get().strip()
        title = self.title_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        due_date = self.due_date_entry.get().strip()
        description = self.description_text.get(1.0, tk.END).strip()

        if not all([assignment_id, title, module_code, due_date]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            if send_assignment_notification is not None:
                if send_assignment_notification(assignment_id, title, module_code, due_date, description):
                    messagebox.showinfo("Success", "Assignment notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")


class ModuleGradeNotificationDialog:
    """Dialog for sending module grade notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Module Grade Notification")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=40)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Name:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_name_entry = ttk.Entry(main_frame, width=40)
        self.module_name_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Grade:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.grade_entry = ttk.Entry(main_frame, width=40)
        self.grade_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        student_id = self.student_id_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        module_name = self.module_name_entry.get().strip()
        grade = self.grade_entry.get().strip()

        if not all([student_id, module_code, module_name, grade]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_grade_notification is not None:
                # This is the first version that takes student_id
                if send_grade_notification(student_id, module_code, module_name, grade):
                    messagebox.showinfo("Success", "Grade notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")


class AssignmentGradeNotificationDialog:
    """Dialog for sending assignment grade notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Assignment Grade Notification")
        self.dialog.geometry("500x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Assignment Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Grade:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.grade_entry = ttk.Entry(main_frame, width=40)
        self.grade_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Feedback (Optional):").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.feedback_text = scrolledtext.ScrolledText(main_frame, width=40, height=6)
        self.feedback_text.grid(row=4, column=1, sticky=tk.NSEW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

    def send_notification(self):
        email = self.email_entry.get().strip()
        title = self.title_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        grade = self.grade_entry.get().strip()
        feedback = self.feedback_text.get(1.0, tk.END).strip()

        if not all([email, title, module_code, grade]):
            messagebox.showerror("Error", "Please fill in all required fields")
            return

        try:
            if send_grade_notification is not None:
                # This is the second version that takes email directly
                if send_grade_notification(email, title, module_code, grade, feedback if feedback else None):
                    messagebox.showinfo("Success", "Grade notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")


class ExtensionNotificationDialog:
    """Dialog for sending extension notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Extension Notification")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Assignment Title:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Module Code:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.module_code_entry = ttk.Entry(main_frame, width=40)
        self.module_code_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="New Due Date (YYYY-MM-DD):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.new_due_date_entry = ttk.Entry(main_frame, width=40)
        self.new_due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Extension Days:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.extension_days_entry = ttk.Entry(main_frame, width=40)
        self.extension_days_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        email = self.email_entry.get().strip()
        title = self.title_entry.get().strip()
        module_code = self.module_code_entry.get().strip()
        new_due_date = self.new_due_date_entry.get().strip()
        extension_days = self.extension_days_entry.get().strip()

        if not all([email, title, module_code, new_due_date, extension_days]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_extension_notification is not None:
                if send_extension_notification(email, title, module_code, new_due_date, extension_days):
                    messagebox.showinfo("Success", "Extension notification sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending notification: {e}")


class UpdateConfirmationDialog:
    """Dialog for sending update confirmation emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Update Confirmation")
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student Email:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.email_entry = ttk.Entry(main_frame, width=40)
        self.email_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Updated Fields (comma-separated):").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.fields_text = scrolledtext.ScrolledText(main_frame, width=40, height=10)
        self.fields_text.grid(row=1, column=1, sticky=tk.NSEW, pady=5)

        ttk.Label(main_frame, text="Example: name, email, phone", font=('Arial', 8, 'italic')).grid(row=2, column=1, sticky=tk.W)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

    def send_confirmation(self):
        email = self.email_entry.get().strip()
        fields_text = self.fields_text.get(1.0, tk.END).strip()

        if not email or not fields_text:
            messagebox.showerror("Error", "Please fill in all fields")
            return

        # Convert to list
        updated_fields = [f.strip() for f in fields_text.split(',') if f.strip()]

        if not updated_fields:
            messagebox.showerror("Error", "Please enter at least one updated field")
            return

        try:
            if send_update_confirmation is not None:
                if send_update_confirmation(email, updated_fields):
                    messagebox.showinfo("Success", "Update confirmation sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send confirmation")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending confirmation: {e}")


class PasswordResetDialog:
    """Dialog for sending password reset emails"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Password Reset")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Student ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.student_id_entry = ttk.Entry(main_frame, width=30)
        self.student_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Reset Code:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.reset_code_entry = ttk.Entry(main_frame, width=30)
        self.reset_code_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Button(main_frame, text="Generate Code", command=self.generate_code).grid(row=1, column=2, padx=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=3, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_reset).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def generate_code(self):
        """Generate a random reset code"""
        import random
        import string
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        self.reset_code_entry.delete(0, tk.END)
        self.reset_code_entry.insert(0, code)

    def send_reset(self):
        student_id = self.student_id_entry.get().strip()
        reset_code = self.reset_code_entry.get().strip()

        if not student_id or not reset_code:
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            if send_password_reset is not None:
                if send_password_reset(student_id, reset_code):
                    messagebox.showinfo("Success", "Password reset email sent successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send reset email. Student may not exist.")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending reset email: {e}")


class ScheduleChangeNotificationDialog:
    """Dialog for sending schedule change notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Schedule Change Notification")
        self.dialog.geometry("500x250")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Schedule ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.schedule_id_entry = ttk.Entry(main_frame, width=40)
        self.schedule_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="Old Value:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.old_value_entry = ttk.Entry(main_frame, width=40)
        self.old_value_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text="New Value:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.new_value_entry = ttk.Entry(main_frame, width=40)
        self.new_value_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text="Send", command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        if not all([self.schedule_id_entry.get(), self.old_value_entry.get(), self.new_value_entry.get()]):
            messagebox.showerror("Error", "Please fill in all fields")
            return

        try:
            schedule_id = int(self.schedule_id_entry.get())
            old_data = {'value': self.old_value_entry.get().strip()}
            new_data = {'value': self.new_value_entry.get().strip()}

            if send_schedule_change_notification is not None:
                if send_schedule_change_notification(schedule_id, old_data, new_data):
                    messagebox.showinfo("Success", "Schedule change notification sent")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send notification")
            else:
                messagebox.showerror("Error", "Function not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error: {e}")


def send_registration_confirmation_dialog(self):
    """Open registration confirmation dialog"""
    RegistrationConfirmationDialog(self.root)

EmailManagerGUI.send_registration_confirmation_dialog = send_registration_confirmation_dialog

def send_assignment_notification_dialog(self):
    """Open assignment notification dialog"""
    AssignmentNotificationDialog(self.root)

EmailManagerGUI.send_assignment_notification_dialog = send_assignment_notification_dialog

def send_module_grade_notification_dialog(self):
    """Open module grade notification dialog"""
    ModuleGradeNotificationDialog(self.root)

EmailManagerGUI.send_module_grade_notification_dialog = send_module_grade_notification_dialog

def send_assignment_grade_notification_dialog(self):
    """Open assignment grade notification dialog"""
    AssignmentGradeNotificationDialog(self.root)

EmailManagerGUI.send_assignment_grade_notification_dialog = send_assignment_grade_notification_dialog

def send_extension_notification_dialog(self):
    """Open extension notification dialog"""
    ExtensionNotificationDialog(self.root)

EmailManagerGUI.send_extension_notification_dialog = send_extension_notification_dialog

def send_update_confirmation_dialog(self):
    """Open update confirmation dialog"""
    UpdateConfirmationDialog(self.root)

EmailManagerGUI.send_update_confirmation_dialog = send_update_confirmation_dialog

def send_password_reset_dialog(self):
    """Open password reset dialog"""
    PasswordResetDialog(self.root)

EmailManagerGUI.send_password_reset_dialog = send_password_reset_dialog

def send_schedule_change_notification_dialog(self):
    """Open schedule change notification dialog"""
    ScheduleChangeNotificationDialog(self.root)

EmailManagerGUI.send_schedule_change_notification_dialog = send_schedule_change_notification_dialog

