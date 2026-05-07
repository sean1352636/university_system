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

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI, get_stored_emails, delete_stored_email
from education_system.university_system.modules.shared.gui.email.email_gui.email_dialogs import (
    ComposeEmailDialog,
    BulkEmailDialog,
    ScheduleEmailDialog,
    TemplateManagerDialog,
    EmailConfigDialog,
    EmailDetailsDialog,
)

def create_email_tab(self):
    """Create the email management tab"""
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.email", default="All Emails"))

    # Email toolbar
    toolbar_frame = ttk.Frame(tab_frame)
    toolbar_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(toolbar_frame, text=_t("email.menu.compose", default="Compose"), command=self.compose_email).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.menu.send_bulk", default="Send Bulk"), command=self.send_bulk_email).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.menu.templates", default="Templates"), command=self.manage_templates).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.schedule", default="Schedule"), command=self.schedule_email).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("email.queue_workers", default="Queue & Workers"), command=self.open_queue_manager).pack(side=tk.LEFT, padx=5)
    ttk.Button(toolbar_frame, text=_t("common.refresh", default="Refresh"), command=self.refresh_emails).pack(side=tk.RIGHT, padx=5)

    # Email list
    self.create_email_list(tab_frame)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_email_tab = create_email_tab

def create_email_list(self, parent):
    """Create email list with treeview"""
    list_frame = ttk.LabelFrame(parent, text=_t("email.stored_emails", default="Stored Emails"), padding=10)
    list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Create treeview
    columns = ("ID", "Recipient", "Subject", "Date", "Template", "Status")
    column_headers = (
        _t("email.columns.id", default="ID"),
        _t("email.columns.recipient", default="Recipient"),
        _t("email.columns.subject", default="Subject"),
        _t("email.columns.date", default="Date"),
        _t("email.columns.template", default="Template"),
        _t("email.columns.status", default="Status")
    )
    self.email_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

    # Configure columns
    for col, header in zip(columns, column_headers):
        self.email_tree.heading(col, text=header)
        if col == "ID":
            self.email_tree.column(col, width=50)
        elif col == "Subject":
            self.email_tree.column(col, width=300)
        else:
            self.email_tree.column(col, width=150)

    # Add scrollbar
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.email_tree.yview)
    self.email_tree.configure(yscrollcommand=scrollbar.set)

    # Pack elements
    self.email_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind double-click
    self.email_tree.bind("<Double-1>", self.view_email_details)

    # Context menu
    self.email_tree.bind("<Button-3>", self.show_email_context_menu)

# Bind method to EmailManagerGUI
EmailManagerGUI.create_email_list = create_email_list

def refresh_emails(self):
    """Refresh the email list"""
    try:
        # Clear existing items
        for item in self.email_tree.get_children():
            self.email_tree.delete(item)

        # Get stored emails
        if 'get_stored_emails' in globals():
            # Check user role - non-admin users only see their own sent emails
            sender_filter = None
            if self.auth and self.auth.current_user:
                user_role = self.auth.current_user.get('role', '')
                if user_role in ('student', 'staff', 'instructor'):
                    # Filter by sender email for non-admin users
                    sender_filter = self.auth.current_user.get('email', '')

            emails_data = get_stored_emails(limit=100, sender_filter=sender_filter)

            for email in emails_data['emails']:
                self.email_tree.insert('', tk.END, values=(
                    email['id'],
                    email['recipient_email'],
                    email['subject'][:50] + ('...' if len(email['subject']) > 50 else ''),
                    email['created_date'],
                    email['template_name'] or 'Direct',
                    'Stored'
                ))

        self.update_status(_t("email.list_refreshed", default="Email list refreshed"))

    except Exception as e:
        messagebox.showerror(_t("common.error", default="Error"), _t("email.refresh_failed", default="Failed to refresh emails: {error}", error=str(e)))

# Bind method to EmailManagerGUI
EmailManagerGUI.refresh_emails = refresh_emails

def view_email_details(self, event):
    """View details of selected email"""
    selection = self.email_tree.selection()
    if selection:
        item = self.email_tree.item(selection[0])
        email_id = item['values'][0]
        EmailDetailsDialog(self.root, email_id)

# Bind method to EmailManagerGUI
EmailManagerGUI.view_email_details = view_email_details

def show_email_context_menu(self, event):
    """Show context menu for email"""
    # Create context menu
    context_menu = tk.Menu(self.root, tearoff=0)
    context_menu.add_command(label=_t("email.view_details", default="View Details"), command=lambda: self.view_email_details(event))
    context_menu.add_command(label=_t("common.delete", default="Delete"), command=self.delete_selected_email)
    context_menu.add_separator()
    context_menu.add_command(label=_t("common.export", default="Export"), command=self.export_selected_email)

    try:
        context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        context_menu.grab_release()

# Bind method to EmailManagerGUI
EmailManagerGUI.show_email_context_menu = show_email_context_menu

def delete_selected_email(self):
    """Delete selected email"""
    selection = self.email_tree.selection()
    if selection:
        item = self.email_tree.item(selection[0])
        email_id = item['values'][0]

        if messagebox.askyesno(_t("email.confirm_delete", default="Confirm Delete"), _t("email.delete_confirm_message", default="Delete email ID {email_id}?", email_id=email_id)):
            try:
                if 'delete_stored_email' in globals():
                    if delete_stored_email(email_id):
                        self.refresh_emails()
                        self.update_status(_t("email.deleted", default="Email {email_id} deleted", email_id=email_id))
                    else:
                        messagebox.showerror(_t("common.error", default="Error"), _t("email.delete_failed", default="Failed to delete email"))
            except Exception as e:
                messagebox.showerror(_t("common.error", default="Error"), _t("email.delete_error", default="Error deleting email: {error}", error=str(e)))

# Bind method to EmailManagerGUI
EmailManagerGUI.delete_selected_email = delete_selected_email

def export_selected_email(self):
    """Export selected email"""
    selection = self.email_tree.selection()
    if not selection:
        messagebox.showwarning(_t("common.no_selection", default="No Selection"), _t("email.select_to_export", default="Please select an email to export"))
        return

    item = self.email_tree.item(selection[0])
    email_id = item['values'][0]

    # Ask user for export format
    export_dialog = tk.Toplevel(self.root)
    export_dialog.title(_t("email.export_email", default="Export Email"))
    export_dialog.geometry("300x150")
    export_dialog.transient(self.root)
    export_dialog.grab_set()

    ttk.Label(export_dialog, text=_t("email.select_export_format", default="Select Export Format:"), font=('Arial', 10, 'bold')).pack(pady=10)

    format_var = tk.StringVar(value="txt")
    ttk.Radiobutton(export_dialog, text=_t("email.format_txt", default="Text File (.txt)"), variable=format_var, value="txt").pack(anchor=tk.W, padx=20)
    ttk.Radiobutton(export_dialog, text=_t("email.format_html", default="HTML File (.html)"), variable=format_var, value="html").pack(anchor=tk.W, padx=20)
    ttk.Radiobutton(export_dialog, text=_t("email.format_json", default="JSON File (.json)"), variable=format_var, value="json").pack(anchor=tk.W, padx=20)

    def do_export():
        format_type = format_var.get()
        export_dialog.destroy()

        # Get email details
        try:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
            email_data = cursor.fetchone()
            conn.close()

            if not email_data:
                messagebox.showerror(_t("common.error", default="Error"), _t("email.not_found", default="Email not found"))
                return

            # Ask for file location
            file_types = {
                "txt": [("Text files", "*.txt"), ("All files", "*.*")],
                "html": [("HTML files", "*.html"), ("All files", "*.*")],
                "json": [("JSON files", "*.json"), ("All files", "*.*")]
            }

            file_path = filedialog.asksaveasfilename(
                title="Save Email Export",
                defaultextension=f".{format_type}",
                filetypes=file_types.get(format_type, [("All files", "*.*")])
            )

            if not file_path:
                return

            # Export based on format
            if format_type == "txt":
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Email ID: {email_data[0]}\n")
                    f.write(f"Recipient: {email_data[1]}\n")
                    f.write(f"Subject: {email_data[2]}\n")
                    f.write(f"Sent At: {email_data[6]}\n")
                    f.write(f"Status: {email_data[7]}\n")
                    f.write(f"\n{'='*50}\n\n")
                    f.write(f"{email_data[3]}\n")

            elif format_type == "html":
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"<!DOCTYPE html>\n<html>\n<head>\n<title>{email_data[2]}</title>\n</head>\n<body>\n")
                    f.write(f"<h2>{email_data[2]}</h2>\n")
                    f.write(f"<p><strong>Recipient:</strong> {email_data[1]}</p>\n")
                    f.write(f"<p><strong>Sent:</strong> {email_data[6]}</p>\n")
                    f.write(f"<hr>\n<div>{email_data[3]}</div>\n")
                    f.write(f"</body>\n</html>")

            elif format_type == "json":
                email_dict = {
                    "id": email_data[0],
                    "recipient": email_data[1],
                    "subject": email_data[2],
                    "body": email_data[3],
                    "cc": email_data[4],
                    "bcc": email_data[5],
                    "sent_at": email_data[6],
                    "status": email_data[7]
                }
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(email_dict, f, indent=4)

            messagebox.showinfo(_t("common.success", default="Success"), _t("email.export_success", default="Email exported successfully to {file_path}", file_path=file_path))

        except Exception as e:
            messagebox.showerror(_t("email.export_error", default="Export Error"), _t("email.export_failed", default="Failed to export email: {error}", error=str(e)))

    ttk.Button(export_dialog, text=_t("common.export", default="Export"), command=do_export).pack(pady=10)
    ttk.Button(export_dialog, text=_t("common.cancel", default="Cancel"), command=export_dialog.destroy).pack()

# Bind method to EmailManagerGUI
EmailManagerGUI.export_selected_email = export_selected_email

def compose_email(self, recipient=None):
    """Open compose email dialog with optional pre-filled recipient"""
    ComposeEmailDialog(self.root, self.auth, recipient=recipient)

# Bind method to EmailManagerGUI
EmailManagerGUI.compose_email = compose_email

def send_bulk_email(self):
    """Open bulk email dialog"""
    BulkEmailDialog(self.root, self.auth)

# Bind method to EmailManagerGUI
EmailManagerGUI.send_bulk_email = send_bulk_email

def schedule_email(self):
    """Open schedule email dialog"""
    ScheduleEmailDialog(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.schedule_email = schedule_email

def manage_templates(self):
    """Open template management dialog"""
    TemplateManagerDialog(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.manage_templates = manage_templates

def open_queue_manager(self):
    """Open email queue & scheduler manager"""
    from education_system.university_system.modules.shared.gui.email.email_queue_scheduler_gui import EmailQueueSchedulerGUI
    EmailQueueSchedulerGUI(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.open_queue_manager = open_queue_manager

def email_configuration(self):
    """Open email configuration dialog"""
    EmailConfigDialog(self.root)

# Bind method to EmailManagerGUI
EmailManagerGUI.email_configuration = email_configuration

