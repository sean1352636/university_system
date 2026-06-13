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
    from education_system.university_system.core.i18n import (
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

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI

class BookCheckoutConfirmationDialog:
    """Dialog for sending book checkout confirmations"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("library.notifications.checkout_confirmation_title"))
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("library.notifications.user_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.book_id")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.book_id_entry = ttk.Entry(main_frame, width=40)
        self.book_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.book_title")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.due_date")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("common.send"), command=self.send_confirmation).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_confirmation(self):
        if not all([self.user_id_entry.get(), self.book_id_entry.get(),
                    self.title_entry.get(), self.due_date_entry.get()]):
            messagebox.showerror(_t("common.error"), _t("library.notifications.fill_all_fields"))
            return

        try:
            if send_book_checkout_confirmation is not None:
                if send_book_checkout_confirmation(
                    self.user_id_entry.get().strip(),
                    self.book_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.due_date_entry.get().strip()
                ):
                    messagebox.showinfo(_t("common.success"), _t("library.notifications.checkout_confirmation_sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t("common.error"), _t("library.notifications.failed_to_send_confirmation"))
            else:
                messagebox.showerror(_t("common.error"), _t("library.notifications.function_not_available"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("library.notifications.error_occurred", error=str(e)))


class BookReturnReminderDialog:
    """Dialog for sending book return reminders"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("library.notifications.return_reminder_title"))
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("library.notifications.user_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.book_id")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.book_id_entry = ttk.Entry(main_frame, width=40)
        self.book_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.book_title")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.due_date")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("common.send"), command=self.send_reminder).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_reminder(self):
        if not all([self.user_id_entry.get(), self.book_id_entry.get(),
                    self.title_entry.get(), self.due_date_entry.get()]):
            messagebox.showerror(_t("common.error"), _t("library.notifications.fill_all_fields"))
            return

        try:
            if send_book_return_reminder is not None:
                if send_book_return_reminder(
                    self.user_id_entry.get().strip(),
                    self.book_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.due_date_entry.get().strip()
                ):
                    messagebox.showinfo(_t("common.success"), _t("library.notifications.return_reminder_sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t("common.error"), _t("library.notifications.failed_to_send_reminder"))
            else:
                messagebox.showerror(_t("common.error"), _t("library.notifications.function_not_available"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("library.notifications.error_occurred", error=str(e)))


class OverdueNotificationDialog:
    """Dialog for sending overdue book notifications"""
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_t("library.notifications.overdue_notice_title"))
        self.dialog.geometry("450x350")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=_t("library.notifications.user_id")).grid(row=0, column=0, sticky=tk.W, pady=5)
        self.user_id_entry = ttk.Entry(main_frame, width=40)
        self.user_id_entry.grid(row=0, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.book_id")).grid(row=1, column=0, sticky=tk.W, pady=5)
        self.book_id_entry = ttk.Entry(main_frame, width=40)
        self.book_id_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.book_title")).grid(row=2, column=0, sticky=tk.W, pady=5)
        self.title_entry = ttk.Entry(main_frame, width=40)
        self.title_entry.grid(row=2, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.due_date")).grid(row=3, column=0, sticky=tk.W, pady=5)
        self.due_date_entry = ttk.Entry(main_frame, width=40)
        self.due_date_entry.grid(row=3, column=1, sticky=tk.EW, pady=5)

        ttk.Label(main_frame, text=_t("library.notifications.days_overdue")).grid(row=4, column=0, sticky=tk.W, pady=5)
        self.days_entry = ttk.Entry(main_frame, width=40)
        self.days_entry.grid(row=4, column=1, sticky=tk.EW, pady=5)

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=2, pady=20)

        ttk.Button(button_frame, text=_t("common.send"), command=self.send_notification).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("common.cancel"), command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        main_frame.columnconfigure(1, weight=1)

    def send_notification(self):
        if not all([self.user_id_entry.get(), self.book_id_entry.get(),
                    self.title_entry.get(), self.due_date_entry.get(), self.days_entry.get()]):
            messagebox.showerror(_t("common.error"), _t("library.notifications.fill_all_fields"))
            return

        try:
            if send_overdue_notification is not None:
                if send_overdue_notification(
                    self.user_id_entry.get().strip(),
                    self.book_id_entry.get().strip(),
                    self.title_entry.get().strip(),
                    self.due_date_entry.get().strip(),
                    int(self.days_entry.get())
                ):
                    messagebox.showinfo(_t("common.success"), _t("library.notifications.overdue_notice_sent"))
                    self.dialog.destroy()
                else:
                    messagebox.showerror(_t("common.error"), _t("library.notifications.failed_to_send_notice"))
            else:
                messagebox.showerror(_t("common.error"), _t("library.notifications.function_not_available"))
        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("library.notifications.error_occurred", error=str(e)))


def send_book_checkout_confirmation_dialog(self):
    """Open book checkout confirmation dialog"""
    BookCheckoutConfirmationDialog(self.root)

EmailManagerGUI.send_book_checkout_confirmation_dialog = send_book_checkout_confirmation_dialog

def send_book_return_reminder_dialog(self):
    """Open book return reminder dialog"""
    BookReturnReminderDialog(self.root)

EmailManagerGUI.send_book_return_reminder_dialog = send_book_return_reminder_dialog

def send_overdue_notification_dialog(self):
    """Open overdue notification dialog"""
    OverdueNotificationDialog(self.root)

EmailManagerGUI.send_overdue_notification_dialog = send_overdue_notification_dialog

