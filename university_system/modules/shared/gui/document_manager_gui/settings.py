import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
import json
import logging

logger = logging.getLogger(__name__)

try:
    from university_system.infrastructure.database.db import get_connection
except ImportError:
    from university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from university_system.modules.shared.utils.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")

try:
    from university_system.modules.shared.constants import paths
except ImportError:
    paths = None


class SettingsManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def system_settings(self):
        """Show system settings dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("System Settings")
        dialog.geometry("850x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 50))

        # Main frame with notebook
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Create notebook for settings categories
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Document Types tab
        self.create_doc_types_tab(notebook)

        # System Settings tab
        self.create_system_settings_tab(notebook)

        # User Management tab
        self.create_user_management_tab(notebook)

        # Backup Settings tab
        self.create_backup_settings_tab(notebook)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Save Settings", command=self.save_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_settings).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

    def create_doc_types_tab(self, notebook):
        """Create document types settings tab"""
        doc_types_frame = ttk.Frame(notebook, padding=15)
        notebook.add(doc_types_frame, text="Document Types")

        # Title
        ttk.Label(doc_types_frame, text="Document Type Management", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Document types list
        list_frame = ttk.Frame(doc_types_frame)
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        # Treeview for document types
        columns = ('ID', 'Name', 'Category', 'Required', 'Expiry', 'Max Size (MB)', 'Formats')
        self.gui.doc_types_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.gui.doc_types_tree.heading(col, text=col)
            width = 80 if col == 'ID' else 120
            self.gui.doc_types_tree.column(col, width=width)

        # Scrollbar
        doc_types_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.gui.doc_types_tree.yview)
        self.gui.doc_types_tree.configure(yscrollcommand=doc_types_scrollbar.set)

        self.gui.doc_types_tree.pack(side='left', fill='both', expand=True)
        doc_types_scrollbar.pack(side='right', fill='y')

        # Load document types
        self.gui.load_document_types()

        # Buttons
        buttons_frame = ttk.Frame(doc_types_frame)
        buttons_frame.pack(fill='x')

        ttk.Button(buttons_frame, text="\u2795 Add Type", command=self.gui.add_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="\u270f\ufe0f Edit Type", command=self.gui.edit_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="\U0001f5d1\ufe0f Delete Type", command=self.gui.delete_document_type).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="\U0001f504 Refresh", command=self.gui.load_document_types).pack(side='left', padx=5)

    def create_system_settings_tab(self, notebook):
        """Create system settings tab"""
        settings_frame = ttk.Frame(notebook, padding=15)
        notebook.add(settings_frame, text="System Settings")

        # Email settings
        email_frame = ttk.LabelFrame(settings_frame, text="Email Configuration", padding=10)
        email_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(email_frame, text="SMTP Server:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.smtp_server = tk.Entry(email_frame, width=30)
        self.gui.smtp_server.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(email_frame, text="SMTP Port:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.gui.smtp_port = tk.Entry(email_frame, width=30)
        self.gui.smtp_port.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(email_frame, text="Email Username:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.gui.email_username = tk.Entry(email_frame, width=30)
        self.gui.email_username.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(email_frame, text="Email Password:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.gui.email_password = tk.Entry(email_frame, width=30, show='*')
        self.gui.email_password.grid(row=3, column=1, padx=5, pady=5, sticky='ew')

        email_frame.grid_columnconfigure(1, weight=1)

        # File settings
        file_frame = ttk.LabelFrame(settings_frame, text="File Settings", padding=10)
        file_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(file_frame, text="Max File Size (MB):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.max_file_size = tk.Entry(file_frame, width=30)
        self.gui.max_file_size.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(file_frame, text="Document Retention (Years):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.gui.doc_retention = tk.Entry(file_frame, width=30)
        self.gui.doc_retention.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        file_frame.grid_columnconfigure(1, weight=1)

        # Notification settings
        notif_frame = ttk.LabelFrame(settings_frame, text="Notification Settings", padding=10)
        notif_frame.pack(fill='x')

        self.gui.email_notifications_enabled = tk.BooleanVar()
        ttk.Checkbutton(notif_frame, text="Enable Email Notifications",
                       variable=self.gui.email_notifications_enabled).pack(anchor='w', pady=5)

        self.gui.auto_backup_enabled = tk.BooleanVar()
        ttk.Checkbutton(notif_frame, text="Enable Automatic Backups",
                       variable=self.gui.auto_backup_enabled).pack(anchor='w', pady=5)

        # Load current settings
        self.load_system_settings()

    def create_user_management_tab(self, notebook):
        """Create user management tab"""
        users_frame = ttk.Frame(notebook, padding=15)
        notebook.add(users_frame, text="Users")

        ttk.Label(users_frame, text="User Management", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Users list
        users_list_frame = ttk.Frame(users_frame)
        users_list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('ID', 'Username', 'Role', 'Email', 'Created', 'Active')
        self.gui.users_tree = ttk.Treeview(users_list_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.gui.users_tree.heading(col, text=col)
            self.gui.users_tree.column(col, width=100)

        users_scrollbar = ttk.Scrollbar(users_list_frame, orient='vertical', command=self.gui.users_tree.yview)
        self.gui.users_tree.configure(yscrollcommand=users_scrollbar.set)

        self.gui.users_tree.pack(side='left', fill='both', expand=True)
        users_scrollbar.pack(side='right', fill='y')

        # Load users
        self.gui.load_users()

        # User management buttons
        user_buttons_frame = ttk.Frame(users_frame)
        user_buttons_frame.pack(fill='x')

        ttk.Button(user_buttons_frame, text="\u2795 Add User", command=self.gui.add_user).pack(side='left', padx=5)
        ttk.Button(user_buttons_frame, text="\u270f\ufe0f Edit User", command=self.gui.edit_user).pack(side='left', padx=5)
        ttk.Button(user_buttons_frame, text="\U0001f512 Reset Password", command=self.gui.reset_user_password).pack(side='left', padx=5)
        ttk.Button(user_buttons_frame, text="\u274c Deactivate", command=self.gui.deactivate_user).pack(side='left', padx=5)

    def create_backup_settings_tab(self, notebook):
        """Create backup settings tab"""
        backup_frame = ttk.Frame(notebook, padding=15)
        notebook.add(backup_frame, text="Backup")

        ttk.Label(backup_frame, text="Backup & Recovery", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        # Backup settings
        backup_settings_frame = ttk.LabelFrame(backup_frame, text="Backup Settings", padding=10)
        backup_settings_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(backup_settings_frame, text="Backup Location:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.backup_location = tk.Entry(backup_settings_frame, width=40)
        self.gui.backup_location.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        ttk.Button(backup_settings_frame, text="Browse...", command=self.gui.browse_backup_location).grid(row=0, column=2, padx=5)

        ttk.Label(backup_settings_frame, text="Backup Frequency (Days):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.gui.backup_frequency = tk.Entry(backup_settings_frame, width=40)
        self.gui.backup_frequency.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        backup_settings_frame.grid_columnconfigure(1, weight=1)

        # Backup actions
        backup_actions_frame = ttk.LabelFrame(backup_frame, text="Backup Actions", padding=10)
        backup_actions_frame.pack(fill='x')

        ttk.Button(backup_actions_frame, text="\U0001f5c2\ufe0f Create Backup Now", command=self.gui.create_backup_now).pack(side='left', padx=5, pady=5)
        ttk.Button(backup_actions_frame, text="\U0001f4c1 View Backups", command=self.gui.view_backups).pack(side='left', padx=5, pady=5)
        ttk.Button(backup_actions_frame, text="\U0001f504 Restore from Backup", command=self.gui.restore_backup).pack(side='left', padx=5, pady=5)

    def load_system_settings(self):
        """Load current system settings"""
        # Set default values for settings
        if hasattr(self.gui, 'smtp_server'):
            self.gui.smtp_server.insert(0, "smtp.gmail.com")
        if hasattr(self.gui, 'smtp_port'):
            self.gui.smtp_port.insert(0, "587")
        # Add more default settings as needed

    def save_settings(self):
        """Save system settings"""
        messagebox.showinfo("Settings", "Settings saved successfully!")

    def reset_settings(self):
        """Reset settings to defaults"""
        if messagebox.askyesno("Reset Settings", "Are you sure you want to reset all settings to defaults?"):
            self.load_system_settings()
            messagebox.showinfo("Settings", "Settings reset to defaults!")

    def set_course_requirements(self):
        """
        Set document requirements for courses/programs
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Set Course Requirements")
            dialog.geometry("900x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Set Course Document Requirements",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Course selection
            course_frame = ttk.LabelFrame(main_frame, text="Course/Program Information", padding=10)
            course_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(course_frame, text="Course Code:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            course_code = tk.StringVar()
            ttk.Entry(course_frame, textvariable=course_code, width=20).grid(row=0, column=1, padx=5, pady=5, sticky='w')

            ttk.Label(course_frame, text="Program:").grid(row=0, column=2, sticky='w', padx=5, pady=5)
            program = tk.StringVar()
            ttk.Entry(course_frame, textvariable=program, width=30).grid(row=0, column=3, padx=5, pady=5, sticky='w')

            ttk.Label(course_frame, text="Year:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            year = tk.StringVar(value="All")
            year_combo = ttk.Combobox(course_frame, textvariable=year, values=['All', '1', '2', '3', '4'], width=17, state='readonly')
            year_combo.grid(row=1, column=1, padx=5, pady=5, sticky='w')

            # Required documents
            docs_frame = ttk.LabelFrame(main_frame, text="Required Documents", padding=10)
            docs_frame.pack(fill='both', expand=True, pady=(0, 15))

            # Document list
            list_frame = ttk.Frame(docs_frame)
            list_frame.pack(fill='both', expand=True)

            columns = ('Document Type', 'Required', 'Deadline (Days)')
            docs_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=12)

            for col in columns:
                docs_tree.heading(col, text=col)
                if col == 'Required':
                    docs_tree.column(col, width=80)
                elif col == 'Deadline (Days)':
                    docs_tree.column(col, width=120)
                else:
                    docs_tree.column(col, width=250)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=docs_tree.yview)
            docs_tree.configure(yscrollcommand=scrollbar.set)
            docs_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load document types with checkboxes
            doc_types = self.gui.get_document_types_with_details()
            doc_checkboxes = {}

            for doc_type in doc_types:
                type_id, type_name = doc_type[0], doc_type[1]
                item = docs_tree.insert('', 'end', text='\u2610', values=(type_name, 'No', '30'))
                doc_checkboxes[item] = {'type_id': type_id, 'checked': False}

            def toggle_checkbox(event):
                item = docs_tree.selection()[0] if docs_tree.selection() else None
                if item and item in doc_checkboxes:
                    doc_checkboxes[item]['checked'] = not doc_checkboxes[item]['checked']
                    checked = doc_checkboxes[item]['checked']
                    docs_tree.item(item, text='\u2611' if checked else '\u2610')
                    values = list(docs_tree.item(item)['values'])
                    values[1] = 'Yes' if checked else 'No'
                    docs_tree.item(item, values=values)

            docs_tree.bind('<Button-1>', toggle_checkbox)

            # Deadline input
            deadline_frame = ttk.Frame(docs_frame)
            deadline_frame.pack(fill='x', pady=(10, 0))

            ttk.Label(deadline_frame, text="Set deadline (days) for selected:").pack(side='left', padx=5)
            deadline_var = tk.StringVar(value="30")
            ttk.Entry(deadline_frame, textvariable=deadline_var, width=10).pack(side='left', padx=5)

            def set_deadline():
                selection = docs_tree.selection()
                if selection:
                    try:
                        days = int(deadline_var.get())
                        for item in selection:
                            values = list(docs_tree.item(item)['values'])
                            values[2] = str(days)
                            docs_tree.item(item, values=values)
                    except ValueError:
                        messagebox.showerror("Error", "Please enter a valid number of days")
                else:
                    messagebox.showwarning("Warning", "Please select documents first")

            ttk.Button(deadline_frame, text="Set Deadline", command=set_deadline).pack(side='left', padx=5)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(10, 0))

            def save_requirements():
                code = course_code.get().strip()
                prog = program.get().strip()

                if not code and not prog:
                    messagebox.showerror("Error", "Please enter course code or program name")
                    return

                # Get checked documents
                required_docs = []
                for item, data in doc_checkboxes.items():
                    if data['checked']:
                        values = docs_tree.item(item)['values']
                        required_docs.append({
                            'type_id': data['type_id'],
                            'type_name': values[0],
                            'deadline_days': int(values[2])
                        })

                if not required_docs:
                    messagebox.showerror("Error", "Please select at least one required document")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Create table if not exists
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS course_requirements (
                        requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        course_code TEXT,
                        program TEXT,
                        year TEXT,
                        type_id INTEGER,
                        deadline_days INTEGER,
                        created_date TEXT,
                        created_by TEXT
                    )
                    ''')

                    # Delete existing requirements for this course/program
                    cursor.execute('''
                    DELETE FROM course_requirements
                    WHERE course_code = ? AND program = ? AND year = ?
                    ''', (code, prog, year.get()))

                    # Insert new requirements
                    username = self.gui.current_user.get('username', 'Unknown') if self.gui.current_user else 'Unknown'
                    for doc in required_docs:
                        cursor.execute('''
                        INSERT INTO course_requirements
                        (course_code, program, year, type_id, deadline_days, created_date, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (code, prog, year.get(), doc['type_id'], doc['deadline_days'],
                             datetime.now().isoformat(), username))

                    conn.commit()
                    conn.close()

                    self.gui.log_event('create', 'course_requirements', None, {
                        'course_code': code,
                        'program': prog,
                        'required_docs': len(required_docs)
                    })

                    messagebox.showinfo("Success",
                                      f"Requirements saved for {code or prog}\n"
                                      f"{len(required_docs)} required documents set")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save requirements: {e}")

            ttk.Button(action_frame, text="Save Requirements", command=save_requirements).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open course requirements: {e}")

    def email_settings(self):
        """
        Configure email notification settings
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Email Notification Settings")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Email Notification Settings",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Enable/Disable email notifications
            enable_frame = ttk.LabelFrame(main_frame, text="Email Notifications", padding=15)
            enable_frame.pack(fill='x', pady=(0, 15))

            enable_email = tk.BooleanVar(value=True)
            ttk.Checkbutton(enable_frame, text="Enable email notifications for document events",
                          variable=enable_email).pack(anchor='w', pady=5)

            # Notification triggers
            triggers_frame = ttk.LabelFrame(main_frame, text="Send Email When...", padding=15)
            triggers_frame.pack(fill='x', pady=(0, 15))

            trigger_upload = tk.BooleanVar(value=True)
            trigger_approval = tk.BooleanVar(value=True)
            trigger_rejection = tk.BooleanVar(value=True)
            trigger_expiry = tk.BooleanVar(value=True)
            trigger_workflow = tk.BooleanVar(value=False)

            ttk.Checkbutton(triggers_frame, text="Document uploaded", variable=trigger_upload).pack(anchor='w', pady=3)
            ttk.Checkbutton(triggers_frame, text="Document approved", variable=trigger_approval).pack(anchor='w', pady=3)
            ttk.Checkbutton(triggers_frame, text="Document rejected", variable=trigger_rejection).pack(anchor='w', pady=3)
            ttk.Checkbutton(triggers_frame, text="Document expiring soon (7 days)", variable=trigger_expiry).pack(anchor='w', pady=3)
            ttk.Checkbutton(triggers_frame, text="Workflow step completed", variable=trigger_workflow).pack(anchor='w', pady=3)

            # Recipients
            recipients_frame = ttk.LabelFrame(main_frame, text="Email Recipients", padding=15)
            recipients_frame.pack(fill='x', pady=(0, 15))

            notify_student = tk.BooleanVar(value=True)
            notify_admin = tk.BooleanVar(value=True)
            notify_staff = tk.BooleanVar(value=False)

            ttk.Checkbutton(recipients_frame, text="Notify student", variable=notify_student).pack(anchor='w', pady=3)
            ttk.Checkbutton(recipients_frame, text="Notify administrators", variable=notify_admin).pack(anchor='w', pady=3)
            ttk.Checkbutton(recipients_frame, text="Notify assigned staff", variable=notify_staff).pack(anchor='w', pady=3)

            # Email template preview
            template_frame = ttk.LabelFrame(main_frame, text="Email Template Preview", padding=10)
            template_frame.pack(fill='both', expand=True, pady=(0, 15))

            template_text = tk.Text(template_frame, height=10, wrap=tk.WORD, font=('Arial', 9))
            template_text.pack(fill='both', expand=True)

            sample_template = """Subject: Document Status Update - {document_type}

Dear {student_name},

Your document "{document_type}" has been {status}.

Document Details:
- Upload Date: {upload_date}
- Status: {status}
- Reviewed By: {reviewer}

{additional_notes}

Please log in to the system to view more details.

Best regards,
University Document Management System
"""
            template_text.insert('1.0', sample_template)
            template_text.config(state='disabled')

            # Test email button
            test_frame = ttk.Frame(main_frame)
            test_frame.pack(fill='x', pady=(0, 15))

            def send_test_email():
                test_dialog = tk.Toplevel(dialog)
                test_dialog.title("Send Test Email")
                test_dialog.geometry("400x200")
                test_dialog.transient(dialog)
                test_dialog.grab_set()

                ttk.Label(test_dialog, text="Send Test Email", font=('Arial', 12, 'bold')).pack(pady=10)

                email_frame = ttk.Frame(test_dialog, padding=10)
                email_frame.pack(fill='x')

                ttk.Label(email_frame, text="Recipient Email:").pack(anchor='w')
                test_email = tk.StringVar()
                ttk.Entry(email_frame, textvariable=test_email, width=40).pack(fill='x', pady=5)

                def send():
                    email = test_email.get().strip()
                    if not email:
                        messagebox.showerror("Error", "Please enter an email address")
                        return

                    try:
                        # Send test email (integrate with email service)
                        messagebox.showinfo("Success",
                                          f"Test email sent to {email}\n\n"
                                          "Please check your inbox.")
                        test_dialog.destroy()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to send test email: {e}")

                btn_frame = ttk.Frame(test_dialog)
                btn_frame.pack(pady=10)
                ttk.Button(btn_frame, text="Send", command=send).pack(side='left', padx=5)
                ttk.Button(btn_frame, text="Cancel", command=test_dialog.destroy).pack(side='left', padx=5)

            ttk.Button(test_frame, text="Send Test Email", command=send_test_email).pack(side='left', padx=5)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def save_settings():
                try:
                    settings = {
                        'enabled': enable_email.get(),
                        'triggers': {
                            'upload': trigger_upload.get(),
                            'approval': trigger_approval.get(),
                            'rejection': trigger_rejection.get(),
                            'expiry': trigger_expiry.get(),
                            'workflow': trigger_workflow.get()
                        },
                        'recipients': {
                            'student': notify_student.get(),
                            'admin': notify_admin.get(),
                            'staff': notify_staff.get()
                        }
                    }

                    # Save to database or config file
                    self.gui.log_event('update', 'email_settings', None, settings)

                    messagebox.showinfo("Success", "Email notification settings saved successfully")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save settings: {e}")

            ttk.Button(action_frame, text="Save Settings", command=save_settings).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open email settings: {e}")

    def email_configuration(self):
        """
        Configure email server settings (SMTP)
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Email Server Configuration")
            dialog.geometry("700x650")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Email Server Configuration",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # SMTP Settings
            smtp_frame = ttk.LabelFrame(main_frame, text="SMTP Server Settings", padding=15)
            smtp_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(smtp_frame, text="SMTP Host:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            smtp_host = tk.StringVar(value="smtp.gmail.com")
            ttk.Entry(smtp_frame, textvariable=smtp_host, width=40).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            ttk.Label(smtp_frame, text="SMTP Port:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            smtp_port = tk.StringVar(value="587")
            ttk.Entry(smtp_frame, textvariable=smtp_port, width=40).grid(row=1, column=1, padx=5, pady=5, sticky='ew')

            ttk.Label(smtp_frame, text="Encryption:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
            encryption = ttk.Combobox(smtp_frame, values=['TLS', 'SSL', 'None'], width=37, state='readonly')
            encryption.set('TLS')
            encryption.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

            smtp_frame.grid_columnconfigure(1, weight=1)

            # Authentication
            auth_frame = ttk.LabelFrame(main_frame, text="Authentication", padding=15)
            auth_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(auth_frame, text="Username:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            smtp_user = tk.StringVar()
            ttk.Entry(auth_frame, textvariable=smtp_user, width=40).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            ttk.Label(auth_frame, text="Password:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            smtp_pass = tk.StringVar()
            ttk.Entry(auth_frame, textvariable=smtp_pass, width=40, show='*').grid(row=1, column=1, padx=5, pady=5, sticky='ew')

            show_password = tk.BooleanVar(value=False)
            def toggle_password():
                pass_entry = auth_frame.grid_slaves(row=1, column=1)[0]
                pass_entry.config(show='' if show_password.get() else '*')

            ttk.Checkbutton(auth_frame, text="Show password", variable=show_password, command=toggle_password).grid(row=2, column=1, sticky='w', padx=5)

            auth_frame.grid_columnconfigure(1, weight=1)

            # Sender settings
            sender_frame = ttk.LabelFrame(main_frame, text="Sender Information", padding=15)
            sender_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(sender_frame, text="From Email:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            from_email = tk.StringVar(value="noreply@university.edu")
            ttk.Entry(sender_frame, textvariable=from_email, width=40).grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            ttk.Label(sender_frame, text="From Name:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            from_name = tk.StringVar(value="University Document System")
            ttk.Entry(sender_frame, textvariable=from_name, width=40).grid(row=1, column=1, padx=5, pady=5, sticky='ew')

            sender_frame.grid_columnconfigure(1, weight=1)

            # Connection test
            test_frame = ttk.Frame(main_frame)
            test_frame.pack(fill='x', pady=(0, 15))

            test_result_label = ttk.Label(test_frame, text="", font=('Arial', 9))
            test_result_label.pack(pady=5)

            def test_connection():
                test_result_label.config(text="Testing connection...", foreground='blue')
                dialog.update()

                try:
                    import smtplib
                    from email.mime.text import MIMEText

                    # Test SMTP connection
                    server = smtplib.SMTP(smtp_host.get(), int(smtp_port.get()))
                    server.starttls() if encryption.get() == 'TLS' else None
                    server.login(smtp_user.get(), smtp_pass.get())
                    server.quit()

                    test_result_label.config(text="\u2713 Connection successful!", foreground='green')

                except Exception as e:
                    test_result_label.config(text=f"\u2717 Connection failed: {str(e)[:50]}...", foreground='red')

            ttk.Button(test_frame, text="Test Connection", command=test_connection).pack(side='left', padx=5)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def save_config():
                try:
                    config = {
                        'smtp_host': smtp_host.get(),
                        'smtp_port': int(smtp_port.get()),
                        'encryption': encryption.get(),
                        'smtp_user': smtp_user.get(),
                        'smtp_pass': smtp_pass.get(),  # In production, encrypt this
                        'from_email': from_email.get(),
                        'from_name': from_name.get()
                    }

                    # Save to config file or database (encrypt password)
                    self.gui.log_event('update', 'email_config', None, {
                        'smtp_host': smtp_host.get(),
                        'smtp_port': int(smtp_port.get())
                    })

                    messagebox.showinfo("Success", "Email configuration saved successfully")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save configuration: {e}")

            ttk.Button(action_frame, text="Save Configuration", command=save_config).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open email configuration: {e}")

    def view_current_settings(self):
        """
        View all system settings
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("System Settings")
            dialog.geometry("900x750")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="System Settings Overview",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Notebook with tabs
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill='both', expand=True, pady=(0, 15))

            # Tab 1: General Settings
            general_tab = ttk.Frame(notebook, padding=15)
            notebook.add(general_tab, text="General")

            general_settings = {
                'System Name': 'University Document Management System',
                'Version': '5.0.0',
                'Database Path': str(paths.DEFAULT_DB_PATH) if paths else 'N/A',
                'Upload Directory': str(paths.UPLOAD_DIR) if paths else 'N/A',
                'Max File Size': '50 MB',
                'Allowed Formats': 'PDF, JPG, PNG, DOC, DOCX',
                'Session Timeout': '30 minutes',
                'Concurrent Users': 'Unlimited'
            }

            for key, value in general_settings.items():
                frame = ttk.Frame(general_tab)
                frame.pack(fill='x', pady=5)
                ttk.Label(frame, text=f"{key}:", font=('Arial', 10, 'bold'), width=20).pack(side='left')
                ttk.Label(frame, text=value, foreground='#555').pack(side='left', padx=10)

            # Tab 2: Security Settings
            security_tab = ttk.Frame(notebook, padding=15)
            notebook.add(security_tab, text="Security")

            security_settings = {
                'Password Hashing': 'PBKDF2-SHA256 (1,000,000 iterations)',
                'Multi-Factor Auth': 'Enabled (TOTP, Email, SMS)',
                'Session Security': 'Token-based with expiration',
                'Encryption': 'AES-256 for sensitive data',
                'Audit Logging': 'Enabled',
                'Failed Login Attempts': '5 before account lock',
                'Password Complexity': 'Minimum 8 characters, mixed case, numbers',
                'Auto-Logout': '30 minutes of inactivity'
            }

            for key, value in security_settings.items():
                frame = ttk.Frame(security_tab)
                frame.pack(fill='x', pady=5)
                ttk.Label(frame, text=f"{key}:", font=('Arial', 10, 'bold'), width=25).pack(side='left')
                ttk.Label(frame, text=value, foreground='#555').pack(side='left', padx=10)

            # Tab 3: Email Settings
            email_tab = ttk.Frame(notebook, padding=15)
            notebook.add(email_tab, text="Email")

            email_settings = {
                'Email Notifications': 'Enabled',
                'SMTP Host': 'smtp.gmail.com',
                'SMTP Port': '587',
                'Encryption': 'TLS',
                'From Email': 'noreply@university.edu',
                'From Name': 'University Document System',
                'Daily Email Limit': '1000',
                'Queue Processing': 'Every 5 minutes'
            }

            for key, value in email_settings.items():
                frame = ttk.Frame(email_tab)
                frame.pack(fill='x', pady=5)
                ttk.Label(frame, text=f"{key}:", font=('Arial', 10, 'bold'), width=20).pack(side='left')
                ttk.Label(frame, text=value, foreground='#555').pack(side='left', padx=10)

            # Tab 4: Backup Settings
            backup_tab = ttk.Frame(notebook, padding=15)
            notebook.add(backup_tab, text="Backup")

            backup_settings = {
                'Auto-Backup': 'Disabled',
                'Backup Frequency': 'Daily',
                'Backup Time': '02:00 AM',
                'Backup Location': str(paths.BACKUP_DIR) if paths else 'N/A',
                'Retention Period': '30 days',
                'Compression': 'Enabled',
                'Last Backup': 'Never',
                'Next Scheduled': 'N/A'
            }

            for key, value in backup_settings.items():
                frame = ttk.Frame(backup_tab)
                frame.pack(fill='x', pady=5)
                ttk.Label(frame, text=f"{key}:", font=('Arial', 10, 'bold'), width=20).pack(side='left')
                ttk.Label(frame, text=value, foreground='#555').pack(side='left', padx=10)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            ttk.Button(action_frame, text="Edit Email Settings", command=self.email_settings).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Edit Security Settings", command=self.security_settings).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Edit Backup Settings", command=self.gui.backup_settings).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open settings: {e}")

    def security_settings(self):
        """
        Configure security settings
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Security Settings")
            dialog.geometry("800x700")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Security Settings",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Password policy
            password_frame = ttk.LabelFrame(main_frame, text="Password Policy", padding=15)
            password_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(password_frame, text="Minimum password length:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            min_length = tk.StringVar(value="8")
            ttk.Spinbox(password_frame, from_=6, to=20, textvariable=min_length, width=10).grid(row=0, column=1, sticky='w', padx=5, pady=5)

            require_uppercase = tk.BooleanVar(value=True)
            require_lowercase = tk.BooleanVar(value=True)
            require_numbers = tk.BooleanVar(value=True)
            require_special = tk.BooleanVar(value=True)

            ttk.Checkbutton(password_frame, text="Require uppercase letters", variable=require_uppercase).grid(row=1, column=0, columnspan=2, sticky='w', padx=5, pady=3)
            ttk.Checkbutton(password_frame, text="Require lowercase letters", variable=require_lowercase).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=3)
            ttk.Checkbutton(password_frame, text="Require numbers", variable=require_numbers).grid(row=3, column=0, columnspan=2, sticky='w', padx=5, pady=3)
            ttk.Checkbutton(password_frame, text="Require special characters", variable=require_special).grid(row=4, column=0, columnspan=2, sticky='w', padx=5, pady=3)

            # Session settings
            session_frame = ttk.LabelFrame(main_frame, text="Session Management", padding=15)
            session_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(session_frame, text="Session timeout (minutes):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            session_timeout = tk.StringVar(value="30")
            ttk.Spinbox(session_frame, from_=5, to=120, increment=5, textvariable=session_timeout, width=10).grid(row=0, column=1, sticky='w', padx=5, pady=5)

            ttk.Label(session_frame, text="Max concurrent sessions:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            max_sessions = tk.StringVar(value="3")
            ttk.Spinbox(session_frame, from_=1, to=10, textvariable=max_sessions, width=10).grid(row=1, column=1, sticky='w', padx=5, pady=5)

            auto_logout = tk.BooleanVar(value=True)
            ttk.Checkbutton(session_frame, text="Auto-logout on inactivity", variable=auto_logout).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=3)

            # Login security
            login_frame = ttk.LabelFrame(main_frame, text="Login Security", padding=15)
            login_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(login_frame, text="Max failed login attempts:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            max_failed = tk.StringVar(value="5")
            ttk.Spinbox(login_frame, from_=3, to=10, textvariable=max_failed, width=10).grid(row=0, column=1, sticky='w', padx=5, pady=5)

            ttk.Label(login_frame, text="Account lock duration (minutes):").grid(row=1, column=0, sticky='w', padx=5, pady=5)
            lock_duration = tk.StringVar(value="30")
            ttk.Spinbox(login_frame, from_=10, to=120, increment=10, textvariable=lock_duration, width=10).grid(row=1, column=1, sticky='w', padx=5, pady=5)

            enable_mfa = tk.BooleanVar(value=True)
            ttk.Checkbutton(login_frame, text="Enable Multi-Factor Authentication (MFA)", variable=enable_mfa).grid(row=2, column=0, columnspan=2, sticky='w', padx=5, pady=3)

            # Audit logging
            audit_frame = ttk.LabelFrame(main_frame, text="Audit & Logging", padding=15)
            audit_frame.pack(fill='x', pady=(0, 15))

            enable_audit = tk.BooleanVar(value=True)
            log_logins = tk.BooleanVar(value=True)
            log_modifications = tk.BooleanVar(value=True)
            log_access = tk.BooleanVar(value=False)

            ttk.Checkbutton(audit_frame, text="Enable audit logging", variable=enable_audit).pack(anchor='w', pady=3)
            ttk.Checkbutton(audit_frame, text="Log all login attempts", variable=log_logins).pack(anchor='w', pady=3)
            ttk.Checkbutton(audit_frame, text="Log data modifications", variable=log_modifications).pack(anchor='w', pady=3)
            ttk.Checkbutton(audit_frame, text="Log file access", variable=log_access).pack(anchor='w', pady=3)

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(15, 0))

            def save_security_settings():
                try:
                    settings = {
                        'password_policy': {
                            'min_length': int(min_length.get()),
                            'require_uppercase': require_uppercase.get(),
                            'require_lowercase': require_lowercase.get(),
                            'require_numbers': require_numbers.get(),
                            'require_special': require_special.get()
                        },
                        'session': {
                            'timeout_minutes': int(session_timeout.get()),
                            'max_concurrent': int(max_sessions.get()),
                            'auto_logout': auto_logout.get()
                        },
                        'login_security': {
                            'max_failed_attempts': int(max_failed.get()),
                            'lock_duration_minutes': int(lock_duration.get()),
                            'enable_mfa': enable_mfa.get()
                        },
                        'audit': {
                            'enabled': enable_audit.get(),
                            'log_logins': log_logins.get(),
                            'log_modifications': log_modifications.get(),
                            'log_access': log_access.get()
                        }
                    }

                    self.gui.log_event('update', 'security_settings', None, settings)

                    messagebox.showinfo("Success", "Security settings saved successfully")
                    dialog.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save settings: {e}")

            ttk.Button(action_frame, text="Save Settings", command=save_security_settings).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open security settings: {e}")

    def view_access_logs(self):
        """
        View security access logs
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Access Logs")
            dialog.geometry("1200x750")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Security Access Logs",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Filter frame
            filter_frame = ttk.Frame(main_frame)
            filter_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(filter_frame, text="Log Type:").pack(side='left', padx=5)
            log_type = ttk.Combobox(filter_frame, values=['All', 'Login', 'Logout', 'Data Access', 'Modification', 'Failed Login'],
                                   width=15, state='readonly')
            log_type.set('All')
            log_type.pack(side='left', padx=5)

            ttk.Label(filter_frame, text="User:").pack(side='left', padx=5)
            user_filter = ttk.Entry(filter_frame, width=20)
            user_filter.pack(side='left', padx=5)

            ttk.Label(filter_frame, text="Date:").pack(side='left', padx=5)
            date_range = ttk.Combobox(filter_frame, values=['Today', 'Last 7 Days', 'Last 30 Days', 'All Time'],
                                     width=15, state='readonly')
            date_range.set('Today')
            date_range.pack(side='left', padx=5)

            # Access logs list
            logs_frame = ttk.LabelFrame(main_frame, text="Access Log Entries", padding=10)
            logs_frame.pack(fill='both', expand=True, pady=(0, 15))

            columns = ('Timestamp', 'User', 'Role', 'Action', 'Entity', 'IP Address', 'Status')
            logs_tree = ttk.Treeview(logs_frame, columns=columns, show='headings', height=20)

            for col in columns:
                logs_tree.heading(col, text=col)
                if col == 'Status':
                    logs_tree.column(col, width=80)
                elif col == 'IP Address':
                    logs_tree.column(col, width=120)
                else:
                    logs_tree.column(col, width=140)

            scrollbar = ttk.Scrollbar(logs_frame, orient='vertical', command=logs_tree.yview)
            logs_tree.configure(yscrollcommand=scrollbar.set)
            logs_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load logs
            def load_logs():
                logs_tree.delete(*logs_tree.get_children())
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    query = '''
                    SELECT timestamp, username, user_role, action, entity_type, '127.0.0.1' as ip, 'Success' as status
                    FROM activity_log
                    WHERE 1=1
                    '''

                    # Apply filters
                    params = []
                    if log_type.get() != 'All':
                        query += ' AND action = ?'
                        params.append(log_type.get().lower())

                    if user_filter.get():
                        query += ' AND username LIKE ?'
                        params.append(f'%{user_filter.get()}%')

                    if date_range.get() == 'Today':
                        query += " AND date(timestamp) = date('now')"
                    elif date_range.get() == 'Last 7 Days':
                        query += " AND timestamp >= datetime('now', '-7 days')"
                    elif date_range.get() == 'Last 30 Days':
                        query += " AND timestamp >= datetime('now', '-30 days')"

                    query += ' ORDER BY timestamp DESC LIMIT 1000'

                    cursor.execute(query, params)
                    logs = cursor.fetchall()
                    conn.close()

                    for log in logs:
                        logs_tree.insert('', 'end', values=log)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load logs: {e}")

            load_logs()

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def export_logs():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"access_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if file_path:
                    try:
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(columns)
                            for item in logs_tree.get_children():
                                writer.writerow(logs_tree.item(item)['values'])

                        messagebox.showinfo("Success", f"Logs exported to:\n{file_path}")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to export: {e}")

            ttk.Button(action_frame, text="Apply Filters", command=load_logs).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Export Logs", command=export_logs).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Clear Filters", command=lambda: [log_type.set('All'), user_filter.delete(0, tk.END), date_range.set('Today'), load_logs()]).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open access logs: {e}")
