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

try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
except ImportError:
    get_db_connection = None

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

# Import template functions
list_templates = load_template = None
try:
    from education_system.university_system.infrastructure.email.template_utils import list_templates, load_template
except ImportError:
    pass

class ComposeEmailDialog:
    def __init__(self, parent, auth, recipient=None):
        self.auth = auth
        self.recipient = recipient
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Compose Email")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

        # Pre-fill recipient if provided
        if self.recipient:
            self.to_entry.insert(0, self.recipient)

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Recipients
        ttk.Label(main_frame, text="To:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.to_entry = ttk.Entry(main_frame, width=50)
        self.to_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, pady=5)

        ttk.Button(main_frame, text="Select Recipients", command=self.select_recipients).grid(row=0, column=3, padx=5)

        # CC
        ttk.Label(main_frame, text="CC:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.cc_entry = ttk.Entry(main_frame, width=50)
        self.cc_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, pady=5)

        # Subject
        ttk.Label(main_frame, text="Subject:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=50)
        self.subject_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, pady=5)

        # Template
        ttk.Label(main_frame, text="Template:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(main_frame, textvariable=self.template_var, width=30)
        self.template_combo.grid(row=3, column=1, sticky=tk.W, pady=5)

        ttk.Button(main_frame, text="Load Template", command=self.load_template).grid(row=3, column=2, padx=5)

        # Body
        ttk.Label(main_frame, text="Message:").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.body_text = scrolledtext.ScrolledText(main_frame, width=60, height=15)
        self.body_text.grid(row=4, column=1, columnspan=3, sticky=tk.NSEW, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=5, column=0, columnspan=4, pady=10)

        ttk.Button(button_frame, text="Send", command=self.send_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save Draft", command=self.save_draft).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

        # Load available templates
        self.load_templates()

    def load_templates(self):
        """Load available templates"""
        try:
            if list_templates is not None:
                templates = list_templates()
                template_names = [t['name'] for t in templates]
                self.template_combo['values'] = template_names
        except Exception as e:
            print(f"Error loading templates: {e}")

    def select_recipients(self):
        """Open recipient selection dialog"""
        RecipientSelectorDialog(self.dialog, self.to_entry)

    def load_template(self):
        """Load selected template"""
        template_name = self.template_var.get()
        if template_name and load_template is not None:
            try:
                template_data = load_template(template_name)
                if template_data:
                    body = (template_data.get('body')
                            or template_data.get('body_html')
                            or template_data.get('body_text')
                            or '')

                    self.subject_entry.delete(0, tk.END)
                    self.subject_entry.insert(0, template_data.get('subject', ''))

                    self.body_text.delete(1.0, tk.END)
                    self.body_text.insert(1.0, body)
            except Exception as e:
                messagebox.showerror("Error", f"Error loading template: {e}")

    def send_email(self):
        """Send the composed email"""
        try:
            recipients = [r.strip() for r in self.to_entry.get().split(',') if r.strip()]
            cc = [r.strip() for r in self.cc_entry.get().split(',') if r.strip()] if self.cc_entry.get() else None
            subject = self.subject_entry.get()
            body = self.body_text.get(1.0, tk.END).strip()

            if not recipients:
                messagebox.showerror("Error", "Please enter at least one recipient")
                return

            if not subject:
                messagebox.showerror("Error", "Please enter a subject")
                return

            if not body:
                messagebox.showerror("Error", "Please enter a message")
                return

            # Send emails via university email service
            from education_system.university_system.infrastructure.email.email_service import send_email

            success_count = 0
            errors = []
            for recipient in recipients:
                try:
                    result = send_email(
                        recipient_email=recipient,
                        subject=subject,
                        body=body,
                        cc=cc
                    )
                    if result is not False:
                        success_count += 1
                    else:
                        errors.append(recipient)
                except Exception as send_err:
                    errors.append(f"{recipient}: {send_err}")

            if success_count > 0 and not errors:
                messagebox.showinfo("Success", f"Email sent to {success_count} recipient(s)")
                self.dialog.destroy()
            elif success_count > 0:
                messagebox.showwarning(
                    "Partial Success",
                    f"Sent to {success_count} recipient(s), but failed for:\n" + "\n".join(errors)
                )
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Failed to send emails:\n" + "\n".join(errors))

        except Exception as e:
            messagebox.showerror("Error", f"Error sending email: {e}")

    def save_draft(self):
        """Save email as draft"""
        try:
            from education_system.university_system.infrastructure.database.db import get_db_connection
            from datetime import datetime

            recipients = self.to_entry.get().strip()
            cc = self.cc_entry.get().strip()
            subject = self.subject_entry.get().strip()
            body = self.body_text.get(1.0, tk.END).strip()

            if not recipients and not subject and not body:
                messagebox.showwarning("Empty Draft", "Cannot save an empty draft")
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            # Create drafts table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS email_drafts (
                    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recipients TEXT,
                    cc TEXT,
                    subject TEXT,
                    body TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            ''')

            # Save draft
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO email_drafts (recipients, cc, subject, body, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (recipients, cc, subject, body, now, now))

            draft_id = cursor.lastrowid
            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Draft saved successfully (ID: {draft_id})")
            self.dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save draft: {e}")


class RecipientSelectorDialog:
    def __init__(self, parent, entry_widget):
        self.entry_widget = entry_widget
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Recipients")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.selected_recipients = []
        self.create_widgets()
        self.load_users()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Search
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind('<KeyRelease>', self.on_search)

        # Users list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.users_tree = ttk.Treeview(list_frame, columns=("Name", "Email", "Role"), show="headings", selectmode=tk.EXTENDED)

        for col in ["Name", "Email", "Role"]:
            self.users_tree.heading(col, text=col)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scrollbar.set)

        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Add Selected", command=self.add_selected).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="OK", command=self.confirm_selection).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_users(self):
        """Load users into the tree from database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT username, email, first_name, last_name, role
                    FROM users
                    ORDER BY username
                """)
                users = cursor.fetchall()

                for user in users:
                    # Build full name
                    full_name = f"{user['first_name']} {user['last_name']}".strip()
                    if not full_name:
                        full_name = user['username']

                    self.users_tree.insert('', tk.END, values=(
                        full_name,
                        user['email'] or user['username'],
                        user['role'] or 'user'
                    ))
        except Exception as e:
            print(f"Error loading users from database: {e}")
            # Log error without fallback - database should be properly initialized
            import traceback
            traceback.print_exc()

    def on_search(self, event):
        """Handle search input"""
        search_term = self.search_entry.get().lower()

        # Clear current items
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)

        # Re-load filtered users from database
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT username, email, first_name, last_name, role
                    FROM users
                    WHERE LOWER(username) LIKE ? OR LOWER(email) LIKE ?
                       OR LOWER(first_name) LIKE ? OR LOWER(last_name) LIKE ?
                    ORDER BY username
                """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))
                users = cursor.fetchall()

                for user in users:
                    # Build full name
                    full_name = f"{user['first_name']} {user['last_name']}".strip()
                    if not full_name:
                        full_name = user['username']

                    self.users_tree.insert('', tk.END, values=(
                        full_name,
                        user['email'] or user['username'],
                        user['role'] or 'user'
                    ))
        except Exception as e:
            print(f"Error searching users in database: {e}")
            # Log error without fallback - database should be properly initialized
            import traceback
            traceback.print_exc()

    def add_selected(self):
        """Add selected users to recipients"""
        selection = self.users_tree.selection()
        for item in selection:
            values = self.users_tree.item(item)['values']
            email = values[1]
            if email not in self.selected_recipients:
                self.selected_recipients.append(email)

    def confirm_selection(self):
        """Confirm recipient selection"""
        if self.selected_recipients:
            current_text = self.entry_widget.get()
            if current_text:
                new_text = current_text + ", " + ", ".join(self.selected_recipients)
            else:
                new_text = ", ".join(self.selected_recipients)

            self.entry_widget.delete(0, tk.END)
            self.entry_widget.insert(0, new_text)

        self.dialog.destroy()


class BulkEmailDialog:
    def __init__(self, parent, auth):
        self.auth = auth
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Send Bulk Email")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Target audience
        ttk.Label(main_frame, text="Target Audience:").grid(row=0, column=0, sticky=tk.W, pady=5)

        self.audience_var = tk.StringVar(value="all")
        audience_frame = ttk.Frame(main_frame)
        audience_frame.grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Radiobutton(audience_frame, text="All Users", variable=self.audience_var, value="all").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Students", variable=self.audience_var, value="students").pack(side=tk.LEFT, padx=10)
        ttk.Radiobutton(audience_frame, text="Staff", variable=self.audience_var, value="staff").pack(side=tk.LEFT)
        ttk.Radiobutton(audience_frame, text="Instructors", variable=self.audience_var, value="instructors").pack(side=tk.LEFT, padx=10)

        # Subject
        ttk.Label(main_frame, text="Subject:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.subject_entry = ttk.Entry(main_frame, width=50)
        self.subject_entry.grid(row=1, column=1, sticky=tk.EW, pady=5)

        # Template
        ttk.Label(main_frame, text="Template:").grid(row=2, column=0, sticky=tk.W, pady=5)
        template_frame = ttk.Frame(main_frame)
        template_frame.grid(row=2, column=1, sticky=tk.W, pady=5)

        self.template_var = tk.StringVar()
        self.template_combo = ttk.Combobox(template_frame, textvariable=self.template_var, width=30)
        self.template_combo.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(template_frame, text="Load Template", command=self.load_selected_template).pack(side=tk.LEFT)

        # Body
        ttk.Label(main_frame, text="Message:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.body_text = scrolledtext.ScrolledText(main_frame, width=60, height=15)
        self.body_text.grid(row=3, column=1, sticky=tk.NSEW, pady=5)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text="Send Bulk Email", command=self.send_bulk).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self.preview_email).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # Load templates
        self.load_templates()

    def load_templates(self):
        """Load available templates"""
        try:
            if list_templates is not None:
                templates = list_templates()
                template_names = [t['name'] for t in templates]
                self.template_combo['values'] = template_names
        except Exception as e:
            print(f"Error loading templates: {e}")

    def load_selected_template(self):
        """Load the selected template into subject and body fields"""
        template_name = self.template_var.get()
        if not template_name:
            messagebox.showwarning("No Selection", "Please select a template first")
            return

        try:
            if load_template is not None:
                template_data = load_template(template_name)
                if template_data:
                    # Load subject if provided
                    subject = template_data.get('subject') or ''
                    if subject:
                        self.subject_entry.delete(0, tk.END)
                        self.subject_entry.insert(0, subject)

                    # Body may be stored under any of body / body_html / body_text
                    body = (template_data.get('body')
                            or template_data.get('body_html')
                            or template_data.get('body_text')
                            or '')
                    if body:
                        self.body_text.delete(1.0, tk.END)
                        self.body_text.insert(1.0, body)

                    messagebox.showinfo("Success", f"Template '{template_name}' loaded successfully!")
                else:
                    messagebox.showerror("Error", f"Failed to load template '{template_name}'")
            else:
                messagebox.showerror("Error", "Template loading functionality not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error loading template: {e}")

    def send_bulk(self):
        """Send bulk email"""
        try:
            audience = self.audience_var.get()
            subject = self.subject_entry.get()
            body = self.body_text.get(1.0, tk.END).strip()

            if not subject or not body:
                messagebox.showerror("Error", "Please enter subject and message")
                return

            # Confirm sending
            if not messagebox.askyesno("Confirm", f"Send bulk email to {audience}?"):
                return

            # Use existing bulk send functionality
            if 'send_batch_announcement' in globals():
                # Create filter criteria based on audience
                filter_criteria = {}
                if audience == "students":
                    filter_criteria = {'role': 'student'}
                elif audience == "staff":
                    filter_criteria = {'role': 'staff'}
                elif audience == "instructors":
                    filter_criteria = {'role': 'instructor'}

                success, failed, total = send_batch_announcement(subject, body, filter_criteria)

                messagebox.showinfo("Result",
                    f"Bulk email completed:\n"
                    f"Total: {total}\n"
                    f"Success: {success}\n"
                    f"Failed: {failed}")

                if success > 0:
                    self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Bulk email functionality not available")

        except Exception as e:
            messagebox.showerror("Error", f"Error sending bulk email: {e}")

    def preview_email(self):
        """Preview the email"""
        subject = self.subject_entry.get()
        body = self.body_text.get(1.0, tk.END).strip()

        preview_text = f"Subject: {subject}\n\nMessage:\n{body}"

        preview_dialog = tk.Toplevel(self.dialog)
        preview_dialog.title("Email Preview")
        preview_dialog.geometry("500x400")

        text_widget = scrolledtext.ScrolledText(preview_dialog, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        text_widget.insert(1.0, preview_text)
        text_widget.config(state=tk.DISABLED)


class ScheduleEmailDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Schedule Email")
        self.dialog.geometry("500x600")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text="Schedule Email", font=('Arial', 14, 'bold')).pack(pady=(0, 10))

        # Recipient
        ttk.Label(main_frame, text="Recipient Email:").pack(anchor=tk.W)
        self.recipient_entry = ttk.Entry(main_frame, width=50)
        self.recipient_entry.pack(fill=tk.X, pady=(0, 10))

        # Subject
        ttk.Label(main_frame, text="Subject:").pack(anchor=tk.W)
        self.subject_entry = ttk.Entry(main_frame, width=50)
        self.subject_entry.pack(fill=tk.X, pady=(0, 10))

        # Body
        ttk.Label(main_frame, text="Message Body:").pack(anchor=tk.W)
        self.body_text = scrolledtext.ScrolledText(main_frame, height=10, wrap=tk.WORD)
        self.body_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Schedule date/time frame
        schedule_frame = ttk.LabelFrame(main_frame, text="Schedule For", padding=10)
        schedule_frame.pack(fill=tk.X, pady=(0, 10))

        # Date selection
        date_frame = ttk.Frame(schedule_frame)
        date_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT, padx=(0, 5))

        # Year
        self.year_var = tk.StringVar(value=str(datetime.now().year))
        year_spinbox = ttk.Spinbox(date_frame, from_=datetime.now().year, to=datetime.now().year + 5,
                                   textvariable=self.year_var, width=6)
        year_spinbox.pack(side=tk.LEFT, padx=2)

        # Month
        self.month_var = tk.StringVar(value=str(datetime.now().month))
        month_spinbox = ttk.Spinbox(date_frame, from_=1, to=12, textvariable=self.month_var, width=4)
        month_spinbox.pack(side=tk.LEFT, padx=2)

        # Day
        self.day_var = tk.StringVar(value=str(datetime.now().day))
        day_spinbox = ttk.Spinbox(date_frame, from_=1, to=31, textvariable=self.day_var, width=4)
        day_spinbox.pack(side=tk.LEFT, padx=2)

        # Time selection
        time_frame = ttk.Frame(schedule_frame)
        time_frame.pack(fill=tk.X)

        ttk.Label(time_frame, text="Time:").pack(side=tk.LEFT, padx=(0, 5))

        # Hour
        self.hour_var = tk.StringVar(value=str(datetime.now().hour))
        hour_spinbox = ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self.hour_var, width=4)
        hour_spinbox.pack(side=tk.LEFT, padx=2)

        ttk.Label(time_frame, text=":").pack(side=tk.LEFT)

        # Minute
        self.minute_var = tk.StringVar(value=str(datetime.now().minute))
        minute_spinbox = ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self.minute_var, width=4)
        minute_spinbox.pack(side=tk.LEFT, padx=2)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="Schedule", command=self.schedule_email).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Send Now", command=self.send_now).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

    def schedule_email(self):
        """Schedule the email for later"""
        recipient = self.recipient_entry.get().strip()
        subject = self.subject_entry.get().strip()
        body = self.body_text.get(1.0, tk.END).strip()

        if not recipient or not subject:
            messagebox.showwarning("Missing Information", "Please fill in recipient and subject")
            return

        try:
            # Get scheduled time
            year = int(self.year_var.get())
            month = int(self.month_var.get())
            day = int(self.day_var.get())
            hour = int(self.hour_var.get())
            minute = int(self.minute_var.get())

            scheduled_time = datetime(year, month, day, hour, minute)

            if scheduled_time <= datetime.now():
                messagebox.showwarning("Invalid Time", "Scheduled time must be in the future")
                return

            # Store scheduled email in database
            from education_system.university_system.infrastructure.database.db import get_db_connection
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create scheduled_emails table if it doesn't exist (matches actual schema)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scheduled_emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    template_name TEXT,
                    recipient_email TEXT NOT NULL,
                    template_vars TEXT,
                    scheduled_date TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL
                )
            ''')

            # Store email content as template variables (JSON format)
            import json
            template_vars = json.dumps({
                'subject': subject,
                'body': body
            })

            cursor.execute('''
                INSERT INTO scheduled_emails (template_name, recipient_email, template_vars, scheduled_date, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', ('custom_email', recipient, template_vars, scheduled_time.strftime('%Y-%m-%d %H:%M:%S'),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Email scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M')}")
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Date/Time", f"Please enter valid date and time values: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to schedule email: {e}")

    def send_now(self):
        """Send the email immediately"""
        recipient = self.recipient_entry.get().strip()
        subject = self.subject_entry.get().strip()
        body = self.body_text.get(1.0, tk.END).strip()

        if not recipient or not subject:
            messagebox.showwarning("Missing Information", "Please fill in recipient and subject")
            return

        try:
            if send_email:
                result = send_email(recipient, subject, body)
                if result:
                    messagebox.showinfo("Success", "Email sent successfully!")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to send email")
            else:
                messagebox.showerror("Error", "Email service not available")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send email: {e}")


class TemplateManagerDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Template Manager")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_templates()

    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="Email Template Manager", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(button_frame, text="New Template", command=self.create_new_template).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Edit Selected", command=self.edit_selected_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_selected_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Refresh", command=self.load_templates).pack(side=tk.LEFT, padx=5)

        # Templates list frame
        list_frame = ttk.LabelFrame(main_frame, text="Available Templates", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Create treeview with scrollbar
        tree_frame = ttk.Frame(list_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.templates_tree = ttk.Treeview(tree_frame, columns=('Type', 'Subject', 'Preview'), show='tree headings')
        self.templates_tree.heading('#0', text='Template Name')
        self.templates_tree.heading('Type', text='Type')
        self.templates_tree.heading('Subject', text='Subject')
        self.templates_tree.heading('Preview', text='Body Preview')

        self.templates_tree.column('#0', width=150)
        self.templates_tree.column('Type', width=80)
        self.templates_tree.column('Subject', width=200)
        self.templates_tree.column('Preview', width=300)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.templates_tree.yview)
        self.templates_tree.configure(yscrollcommand=scrollbar.set)

        self.templates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to edit
        self.templates_tree.bind('<Double-1>', lambda e: self.edit_selected_template())

        # Close button
        ttk.Button(main_frame, text="Close", command=self.dialog.destroy).pack(pady=(10, 0))

    def load_templates(self):
        """Load and display templates in the tree"""
        # Clear existing items
        for item in self.templates_tree.get_children():
            self.templates_tree.delete(item)

        try:
            # Import template functions
            from education_system.university_system.infrastructure.email.template_utils import list_templates
            templates = list_templates()

            for template in templates:
                template_type = "Default" if template.get('is_default', False) else "Custom"
                self.templates_tree.insert('', 'end',
                                         text=template['name'],
                                         values=(template_type,
                                               template.get('subject', ''),
                                               template.get('body_preview', '')))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {str(e)}")

    def create_new_template(self):
        """Open dialog to create a new template"""
        dialog = TemplateEditDialog(self.dialog, None)
        if dialog.result:
            self.load_templates()

    def edit_selected_template(self):
        """Edit the selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to edit.")
            return

        template_name = self.templates_tree.item(selection[0])['text']
        dialog = TemplateEditDialog(self.dialog, template_name)
        if dialog.result:
            self.load_templates()

    def delete_selected_template(self):
        """Delete the selected template"""
        selection = self.templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete.")
            return

        template_name = self.templates_tree.item(selection[0])['text']
        template_type = self.templates_tree.item(selection[0])['values'][0]

        if template_type == "Default":
            messagebox.showwarning("Cannot Delete", "Default templates cannot be deleted.")
            return

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the template '{template_name}'?"):
            try:
                from education_system.university_system.infrastructure.email.template_utils import delete_template
                if delete_template(template_name):
                    messagebox.showinfo("Success", f"Template '{template_name}' deleted successfully.")
                    self.load_templates()
                else:
                    messagebox.showerror("Error", f"Failed to delete template '{template_name}'.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {str(e)}")


class TemplateEditDialog:
    def __init__(self, parent, template_name=None):
        self.dialog = tk.Toplevel(parent)
        self.template_name = template_name
        self.result = False

        title = "Edit Template" if template_name else "Create New Template"
        self.dialog.title(title)
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        if template_name:
            self.load_template_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Template name
        ttk.Label(main_frame, text="Template Name:").pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=50)
        self.name_entry.pack(fill=tk.X, pady=(0, 10))

        if self.template_name:
            self.name_var.set(self.template_name)
            self.name_entry.config(state='readonly')

        # Subject
        ttk.Label(main_frame, text="Subject:").pack(anchor=tk.W)
        self.subject_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.subject_var, width=50).pack(fill=tk.X, pady=(0, 10))

        # Body
        ttk.Label(main_frame, text="Body:").pack(anchor=tk.W)
        body_frame = ttk.Frame(main_frame)
        body_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.body_text = scrolledtext.ScrolledText(body_frame, wrap=tk.WORD, height=15)
        self.body_text.pack(fill=tk.BOTH, expand=True)

        # Variables help
        help_frame = ttk.LabelFrame(main_frame, text="Available Variables", padding=5)
        help_frame.pack(fill=tk.X, pady=(0, 10))

        help_text = ("Common variables: $student_name, $student_id, $email_address, $course, "
                    "$module_code, $assignment_title, $due_date, $grade, $signature")
        ttk.Label(help_frame, text=help_text, wraplength=550).pack()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        ttk.Button(button_frame, text="Save", command=self.save_template).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.LEFT)

    def load_template_data(self):
        """Load existing template data"""
        try:
            from education_system.university_system.infrastructure.email.template_utils import load_template
            template_data = load_template(self.template_name)
            if template_data:
                self.subject_var.set(template_data.get('subject', ''))
                self.body_text.insert('1.0', template_data.get('body', ''))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {str(e)}")

    def save_template(self):
        """Save the template"""
        name = self.name_var.get().strip()
        subject = self.subject_var.get().strip()
        body = self.body_text.get('1.0', tk.END).strip()

        if not name or not subject or not body:
            messagebox.showerror("Validation Error", "All fields are required.")
            return

        try:
            if self.template_name:
                # Update existing template
                from education_system.university_system.infrastructure.email.template_utils import update_template
                if update_template(name, subject=subject, body=body):
                    messagebox.showinfo("Success", "Template updated successfully.")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to update template.")
            else:
                # Create new template
                from education_system.university_system.infrastructure.email.template_utils import create_template
                if create_template(name, subject, body):
                    messagebox.showinfo("Success", "Template created successfully.")
                    self.result = True
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to create template. Template may already exist.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {str(e)}")


class EmailConfigDialog:
    def __init__(self, parent):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Email Configuration")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        self.load_config()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Mode selection
        mode_frame = ttk.LabelFrame(main_frame, text="Email Mode", padding=10)
        mode_frame.pack(fill=tk.X, pady=5)

        self.mode_var = tk.StringVar()
        ttk.Radiobutton(mode_frame, text="Database Only Mode", variable=self.mode_var, value="database").pack(anchor=tk.W)
        ttk.Radiobutton(mode_frame, text="SMTP Sending Mode", variable=self.mode_var, value="smtp").pack(anchor=tk.W)

        # SMTP settings
        smtp_frame = ttk.LabelFrame(main_frame, text="SMTP Settings", padding=10)
        smtp_frame.pack(fill=tk.X, pady=5)

        ttk.Label(smtp_frame, text="SMTP Server:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.smtp_server_entry = ttk.Entry(smtp_frame, width=30)
        self.smtp_server_entry.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(smtp_frame, text="SMTP Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.smtp_port_entry = ttk.Entry(smtp_frame, width=10)
        self.smtp_port_entry.grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(smtp_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.username_entry = ttk.Entry(smtp_frame, width=30)
        self.username_entry.grid(row=2, column=1, sticky=tk.W, pady=2)

        ttk.Label(smtp_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.password_entry = ttk.Entry(smtp_frame, width=30, show="*")
        self.password_entry.grid(row=3, column=1, sticky=tk.W, pady=2)

        # Sender settings
        sender_frame = ttk.LabelFrame(main_frame, text="Sender Information", padding=10)
        sender_frame.pack(fill=tk.X, pady=5)

        ttk.Label(sender_frame, text="Sender Email:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sender_email_entry = ttk.Entry(sender_frame, width=40)
        self.sender_email_entry.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(sender_frame, text="Sender Name:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.sender_name_entry = ttk.Entry(sender_frame, width=40)
        self.sender_name_entry.grid(row=1, column=1, sticky=tk.W, pady=2)

        # Options
        options_frame = ttk.LabelFrame(main_frame, text="Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        self.use_tls_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Use TLS", variable=self.use_tls_var).pack(anchor=tk.W)

        self.use_auth_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Use Authentication", variable=self.use_auth_var).pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Test", command=self.test_config).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_config(self):
        """Load current configuration"""
        try:
            if 'config' in globals():
                cfg = config

                # Set mode
                if cfg.get('database_only_mode', True):
                    self.mode_var.set("database")
                else:
                    self.mode_var.set("smtp")

                # Set SMTP settings
                self.smtp_server_entry.insert(0, cfg.get('smtp_server', ''))
                self.smtp_port_entry.insert(0, str(cfg.get('smtp_port', 587)))
                self.username_entry.insert(0, cfg.get('username', ''))

                # Set sender settings
                self.sender_email_entry.insert(0, cfg.get('sender_email', ''))
                self.sender_name_entry.insert(0, cfg.get('sender_name', ''))

                # Set options
                self.use_tls_var.set(cfg.get('use_tls', True))
                self.use_auth_var.set(cfg.get('use_authentication', True))

        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        """Save configuration"""
        try:
            if 'config' in globals():
                # Update global config
                config['database_only_mode'] = (self.mode_var.get() == "database")
                config['smtp_server'] = self.smtp_server_entry.get()
                config['smtp_port'] = int(self.smtp_port_entry.get() or 587)
                config['username'] = self.username_entry.get()
                config['sender_email'] = self.sender_email_entry.get()
                config['sender_name'] = self.sender_name_entry.get()
                config['use_tls'] = self.use_tls_var.get()
                config['use_authentication'] = self.use_auth_var.get()

                if self.password_entry.get():
                    config['password'] = self.password_entry.get()

                # Save to file
                if 'save_config' in globals():
                    save_config()

                messagebox.showinfo("Success", "Configuration saved successfully")
                self.dialog.destroy()
            else:
                messagebox.showerror("Error", "Configuration system not available")

        except Exception as e:
            messagebox.showerror("Error", f"Error saving configuration: {e}")

    def test_config(self):
        """Test email configuration"""
        try:
            if 'test_email_configuration' in globals():
                test_email_configuration()
                messagebox.showinfo("Test", "Check console for test results")
            else:
                messagebox.showinfo("Test", "Test functionality not available")
        except Exception as e:
            messagebox.showerror("Error", f"Error testing configuration: {e}")


class EmailDetailsDialog:
    def __init__(self, parent, email_id):
        self.email_id = email_id
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Email Details - ID {email_id}")
        self.dialog.geometry("600x500")
        self.dialog.transient(parent)

        self.create_widgets()
        self.load_email_details()

        # Set grab after window is fully initialized and visible
        self.dialog.after(100, self.dialog.grab_set)

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Details display
        self.details_text = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.details_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def load_email_details(self):
        """Load email details"""
        try:
            # Get email details using existing function
            def _get_email_details(cursor):
                cursor.execute('''
                SELECT id, recipient_email, subject, body, sender_email, sender_name,
                       cc_recipients, bcc_recipients, attachment_paths, created_date,
                       template_name, template_vars, related_to, student_id
                FROM stored_emails WHERE id = ?
                ''', (self.email_id,))
                return cursor.fetchone()

            if 'execute_db_operation' in globals():
                email_data = execute_db_operation(_get_email_details)

                if email_data:
                    details = f"Email ID: {email_data[0]}\n"
                    details += f"To: {email_data[1]}\n"
                    details += f"From: {email_data[5]} <{email_data[4]}>\n"
                    details += f"Subject: {email_data[2]}\n"
                    details += f"Date: {email_data[9]}\n"

                    if email_data[6]:  # CC
                        details += f"CC: {email_data[6]}\n"
                    if email_data[7]:  # BCC
                        details += f"BCC: {email_data[7]}\n"
                    if email_data[8]:  # Attachments
                        details += f"Attachments: {email_data[8]}\n"
                    if email_data[10]:  # Template
                        details += f"Template: {email_data[10]}\n"

                    details += "\n" + "-" * 50 + "\n\n"
                    details += email_data[3]  # Body

                    self.details_text.config(state=tk.NORMAL)
                    self.details_text.insert(1.0, details)
                    self.details_text.config(state=tk.DISABLED)
                else:
                    self.details_text.config(state=tk.NORMAL)
                    self.details_text.insert(1.0, "Email not found")
                    self.details_text.config(state=tk.DISABLED)

        except Exception as e:
            self.details_text.config(state=tk.NORMAL)
            self.details_text.insert(1.0, f"Error loading email details: {e}")
            self.details_text.config(state=tk.DISABLED)


class TemplateEditor:
    """Advanced template editor with syntax highlighting"""
    def __init__(self, parent, template_name=None):
        self.template_name = template_name
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Template Editor - {template_name or 'New Template'}")
        self.dialog.geometry("700x500")
        self.dialog.transient(parent)
        # Defer grab_set to avoid "window not viewable" error
        self.dialog.after(100, lambda: self.dialog.grab_set() if self.dialog.winfo_exists() else None)

        self.create_widgets()
        if template_name:
            self.load_template()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Template info
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text="Name:").grid(row=0, column=0, sticky=tk.W)
        self.name_entry = ttk.Entry(info_frame, width=30)
        self.name_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Subject
        ttk.Label(main_frame, text="Subject:").pack(anchor=tk.W)
        self.subject_entry = ttk.Entry(main_frame, width=80)
        self.subject_entry.pack(fill=tk.X, pady=5)

        # Body with variable hints
        body_frame = ttk.Frame(main_frame)
        body_frame.pack(fill=tk.BOTH, expand=True)

        # Variables panel
        vars_frame = ttk.LabelFrame(body_frame, text="Available Variables", padding=5)
        vars_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))

        variables = [
            "$student_id", "$email_address", "$title", "$first_name",
            "$last_name", "$course", "$modules_list", "$signature"
        ]

        for var in variables:
            btn = ttk.Button(vars_frame, text=var, width=15,
                           command=lambda v=var: self.insert_variable(v))
            btn.pack(fill=tk.X, pady=1)

        # Body editor
        editor_frame = ttk.Frame(body_frame)
        editor_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(editor_frame, text="Body:").pack(anchor=tk.W)
        self.body_text = scrolledtext.ScrolledText(editor_frame, wrap=tk.WORD)
        self.body_text.pack(fill=tk.BOTH, expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="Save", command=self.save_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Preview", command=self.preview_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)

    def insert_variable(self, variable):
        """Insert variable at cursor position"""
        self.body_text.insert(tk.INSERT, variable)
        self.body_text.focus()

    def load_template(self):
        """Load existing template"""
        if self.template_name and 'load_template' in globals():
            try:
                template_data = load_template(self.template_name)
                if template_data:
                    body = (template_data.get('body')
                            or template_data.get('body_html')
                            or template_data.get('body_text')
                            or '')
                    self.name_entry.insert(0, self.template_name)
                    self.subject_entry.insert(0, template_data.get('subject', ''))
                    self.body_text.insert(1.0, body)
            except Exception as e:
                messagebox.showerror("Error", f"Error loading template: {e}")

    def save_template(self):
        """Save template"""
        try:
            name = self.name_entry.get().strip()
            subject = self.subject_entry.get().strip()
            body = self.body_text.get(1.0, tk.END).strip()

            if not name or not subject or not body:
                messagebox.showerror("Error", "Please fill in all fields")
                return

            if 'create_template' in globals():
                if create_template(name, subject, body):
                    messagebox.showinfo("Success", f"Template '{name}' saved successfully")
                    self.dialog.destroy()
                else:
                    messagebox.showerror("Error", "Failed to save template")
            else:
                messagebox.showerror("Error", "Template system not available")

        except Exception as e:
            messagebox.showerror("Error", f"Error saving template: {e}")

    def preview_template(self):
        """Preview template with sample data"""
        subject = self.subject_entry.get()
        body = self.body_text.get(1.0, tk.END).strip()

        # Sample template variables
        sample_vars = {
            'student_id': 'STU12345',
            'email_address': 'john.doe@university.edu',
            'title': 'Mr',
            'first_name': 'John',
            'last_name': 'Doe',
            'course': 'Computer Science',
            'modules_list': '- CS101: Programming\n- CS102: Data Structures',
            'signature': '\n\nBest regards,\nUniversity Administration'
        }

        # Simple variable substitution
        preview_subject = subject
        preview_body = body

        for var, value in sample_vars.items():
            preview_subject = preview_subject.replace(f'£{var}', str(value))
            preview_body = preview_body.replace(f'£{var}', str(value))

        # Show preview
        preview_dialog = tk.Toplevel(self.dialog)
        preview_dialog.title("Template Preview")
        preview_dialog.geometry("500x400")

        preview_frame = ttk.Frame(preview_dialog, padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(preview_frame, text=f"Subject: {preview_subject}", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=5)

        preview_text = scrolledtext.ScrolledText(preview_frame, wrap=tk.WORD, state=tk.DISABLED)
        preview_text.pack(fill=tk.BOTH, expand=True)

        preview_text.config(state=tk.NORMAL)
        preview_text.insert(1.0, preview_body)
        preview_text.config(state=tk.DISABLED)

        ttk.Button(preview_frame, text="Close", command=preview_dialog.destroy).pack(pady=10)


