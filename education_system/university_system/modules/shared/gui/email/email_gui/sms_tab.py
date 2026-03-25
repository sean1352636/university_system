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

from education_system.university_system.core.sql_safety import escape_like

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

from education_system.university_system.modules.shared.gui.email.email_gui.email_manager_main import EmailManagerGUI

# Import database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
except ImportError:
    get_db_connection = None

def create_sms_tab(self):
    """Create the SMS messaging tab"""
    tab_frame = ttk.Frame(self.notebook)
    self.notebook.add(tab_frame, text=_t("email.tabs.sms", default="SMS"))

    # Create main paned window for compose and history
    paned = ttk.PanedWindow(tab_frame, orient=tk.VERTICAL)
    paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Top pane - SMS Composer
    compose_frame = ttk.LabelFrame(paned, text="📱 Compose SMS", padding=10)
    paned.add(compose_frame, weight=1)

    # Recipient selection
    recipient_frame = ttk.Frame(compose_frame)
    recipient_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Label(recipient_frame, text="Recipient:").pack(side=tk.LEFT, padx=(0, 5))

    # Recipient type selection
    self.sms_recipient_type = tk.StringVar(value="individual")
    ttk.Radiobutton(recipient_frame, text="Individual", variable=self.sms_recipient_type,
                   value="individual", command=self.on_sms_recipient_type_change).pack(side=tk.LEFT, padx=5)
    ttk.Radiobutton(recipient_frame, text="Group", variable=self.sms_recipient_type,
                   value="group", command=self.on_sms_recipient_type_change).pack(side=tk.LEFT, padx=5)
    ttk.Radiobutton(recipient_frame, text="Role", variable=self.sms_recipient_type,
                   value="role", command=self.on_sms_recipient_type_change).pack(side=tk.LEFT, padx=5)

    # Recipient input area
    recipient_input_frame = ttk.Frame(compose_frame)
    recipient_input_frame.pack(fill=tk.X, pady=(0, 10))

    # Phone number entry (for individual)
    phone_frame = ttk.Frame(recipient_input_frame)
    phone_frame.pack(fill=tk.X)
    ttk.Label(phone_frame, text="Phone Number:").pack(side=tk.LEFT, padx=(0, 5))
    self.sms_phone_entry = ttk.Entry(phone_frame, width=20)
    self.sms_phone_entry.pack(side=tk.LEFT, padx=(0, 5))
    ttk.Label(phone_frame, text="(Format: +1234567890)", foreground='gray').pack(side=tk.LEFT)

    # User selection combobox (for individual user lookup)
    user_frame = ttk.Frame(recipient_input_frame)
    ttk.Label(user_frame, text="Or select user:").pack(side=tk.LEFT, padx=(0, 5))
    self.sms_user_combo = ttk.Combobox(user_frame, width=30, state='readonly')
    self.sms_user_combo.pack(side=tk.LEFT, padx=(0, 5))
    self.sms_user_combo.bind('<<ComboboxSelected>>', self.on_sms_user_selected)
    ttk.Button(user_frame, text="🔄 Refresh Users", command=self.load_sms_users).pack(side=tk.LEFT, padx=5)

    # Group/Role selection (hidden by default)
    self.sms_group_frame = ttk.Frame(recipient_input_frame)
    ttk.Label(self.sms_group_frame, text="Select Group/Role:").pack(side=tk.LEFT, padx=(0, 5))
    self.sms_group_combo = ttk.Combobox(self.sms_group_frame, width=30, state='readonly')
    self.sms_group_combo.pack(side=tk.LEFT, padx=(0, 5))

    # Message area
    message_frame = ttk.Frame(compose_frame)
    message_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    ttk.Label(message_frame, text="Message:").pack(anchor=tk.W, pady=(0, 5))

    # Character counter
    counter_frame = ttk.Frame(message_frame)
    counter_frame.pack(fill=tk.X, pady=(0, 5))
    self.sms_char_label = ttk.Label(counter_frame, text="0 / 160 characters", foreground='gray')
    self.sms_char_label.pack(side=tk.RIGHT)

    # Text area with scrollbar
    text_scroll_frame = ttk.Frame(message_frame)
    text_scroll_frame.pack(fill=tk.BOTH, expand=True)

    self.sms_message_text = scrolledtext.ScrolledText(text_scroll_frame, height=5, wrap=tk.WORD)
    self.sms_message_text.pack(fill=tk.BOTH, expand=True)
    self.sms_message_text.bind('<KeyRelease>', self.update_sms_char_count)

    # Action buttons
    button_frame = ttk.Frame(compose_frame)
    button_frame.pack(fill=tk.X)

    ttk.Button(button_frame, text="📤 Send SMS", command=self.send_sms).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="🗑️ Clear", command=self.clear_sms_form).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="📋 Template", command=self.sms_templates).pack(side=tk.LEFT, padx=5)

    # Bottom pane - SMS History
    history_frame = ttk.LabelFrame(paned, text="📋 SMS History", padding=10)
    paned.add(history_frame, weight=2)

    # History toolbar
    history_toolbar = ttk.Frame(history_frame)
    history_toolbar.pack(fill=tk.X, pady=(0, 10))

    ttk.Button(history_toolbar, text="🔄 Refresh", command=self.refresh_sms_history).pack(side=tk.LEFT, padx=5)
    ttk.Button(history_toolbar, text="🗑️ Delete", command=self.delete_sms).pack(side=tk.LEFT, padx=5)
    ttk.Button(history_toolbar, text="📊 Statistics", command=self.sms_statistics).pack(side=tk.LEFT, padx=5)

    # Search frame
    search_frame = ttk.Frame(history_toolbar)
    search_frame.pack(side=tk.RIGHT)
    ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT, padx=(0, 5))
    self.sms_search_entry = ttk.Entry(search_frame, width=20)
    self.sms_search_entry.pack(side=tk.LEFT)
    self.sms_search_entry.bind('<KeyRelease>', lambda e: self.refresh_sms_history())

    # History tree
    tree_frame = ttk.Frame(history_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    # Scrollbars
    vsb = ttk.Scrollbar(tree_frame, orient="vertical")
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
    hsb.pack(side=tk.BOTTOM, fill=tk.X)

    self.sms_history_tree = ttk.Treeview(
        tree_frame,
        columns=("ID", "Date", "Recipient", "Phone", "Message", "Status"),
        show="headings",
        selectmode='browse',
        yscrollcommand=vsb.set,
        xscrollcommand=hsb.set
    )
    self.sms_history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    vsb.config(command=self.sms_history_tree.yview)
    hsb.config(command=self.sms_history_tree.xview)

    # Configure columns
    self.sms_history_tree.heading("ID", text="ID")
    self.sms_history_tree.column("ID", width=50, minwidth=50)

    self.sms_history_tree.heading("Date", text="Date & Time")
    self.sms_history_tree.column("Date", width=150, minwidth=120)

    self.sms_history_tree.heading("Recipient", text="Recipient")
    self.sms_history_tree.column("Recipient", width=150, minwidth=100)

    self.sms_history_tree.heading("Phone", text="Phone Number")
    self.sms_history_tree.column("Phone", width=120, minwidth=100)

    self.sms_history_tree.heading("Message", text="Message")
    self.sms_history_tree.column("Message", width=300, minwidth=200)

    self.sms_history_tree.heading("Status", text="Status")
    self.sms_history_tree.column("Status", width=100, minwidth=80)

    # Status tags
    self.sms_history_tree.tag_configure('sent', background='#E8F8E8')
    self.sms_history_tree.tag_configure('failed', background='#FFE8E8')
    self.sms_history_tree.tag_configure('pending', background='#FFF8E8')

    # Load initial data
    self.load_sms_users()
    self.refresh_sms_history()

# Bind method to EmailManagerGUI
EmailManagerGUI.create_sms_tab = create_sms_tab

def on_sms_recipient_type_change(self):
    """Handle recipient type change"""
    recipient_type = self.sms_recipient_type.get()

    # Show/hide appropriate inputs
    if recipient_type == "individual":
        # Show phone and user selection
        self.sms_phone_entry.config(state='normal')
        self.sms_user_combo.config(state='readonly')
        self.sms_group_frame.pack_forget()
    else:
        # Hide individual inputs, show group/role selector
        self.sms_phone_entry.config(state='disabled')
        self.sms_user_combo.config(state='disabled')
        self.sms_group_frame.pack(fill=tk.X, pady=(10, 0))

        # Load appropriate values
        if recipient_type == "group":
            self.load_sms_groups()
        elif recipient_type == "role":
            self.load_sms_roles()

# Bind method to EmailManagerGUI
EmailManagerGUI.on_sms_recipient_type_change = on_sms_recipient_type_change

def on_sms_user_selected(self, event=None):
    """Auto-fill phone number when user is selected"""
    try:
        selected = self.sms_user_combo.get()
        if not selected:
            return

        # Extract username from the combo value (format: "username (Name)")
        username = selected.split(' (')[0]

        # Try to look up phone number from student emergency contacts
        with get_db_connection() as conn:
            # First try to get student_id from users table
            cursor = conn.execute("""
                SELECT u.student_id
                FROM users u
                WHERE u.username = ?
            """, (username,))
            user_result = cursor.fetchone()

            if user_result and user_result[0]:
                # Look up emergency contact phone
                student_id = user_result[0]
                cursor = conn.execute("""
                    SELECT phone_primary
                    FROM emergency_contacts
                    WHERE student_id = ?
                    AND phone_primary IS NOT NULL
                    ORDER BY priority_order
                    LIMIT 1
                """, (student_id,))
                phone_result = cursor.fetchone()

                if phone_result and phone_result[0]:
                    self.sms_phone_entry.delete(0, tk.END)
                    self.sms_phone_entry.insert(0, phone_result[0])
                else:
                    # Clear field and let user enter manually
                    self.sms_phone_entry.delete(0, tk.END)
                    print(f"ℹ️ No phone number found for {username}. Please enter manually.")
            else:
                # Not a student or no student_id - let user enter phone manually
                self.sms_phone_entry.delete(0, tk.END)
                print(f"ℹ️ User {username} is not a student. Please enter phone number manually.")
    except Exception as e:
        print(f"Error loading user phone: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.on_sms_user_selected = on_sms_user_selected

def load_sms_users(self):
    """Load users into the SMS recipient combobox"""
    try:
        with get_db_connection() as conn:
            # Get all users - phone numbers will need to be entered manually
            # or loaded from emergency_contacts for students
            cursor = conn.execute("""
                SELECT username, first_name, last_name, email
                FROM users
                ORDER BY last_name, first_name
            """)
            users = cursor.fetchall()

            # Format: "username (Full Name)"
            user_list = [f"{user[0]} ({user[1]} {user[2]})" for user in users]
            self.sms_user_combo['values'] = user_list

            print(f"✅ Loaded {len(users)} users (phone numbers must be entered manually)")
    except Exception as e:
        print(f"⚠️ Error loading SMS users: {e}")
        self.sms_user_combo['values'] = []

# Bind method to EmailManagerGUI
EmailManagerGUI.load_sms_users = load_sms_users

def load_sms_groups(self):
    """Load groups for bulk SMS"""
    try:
        # Load student groups, courses, etc.
        with get_db_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT group_name FROM student_groups
                WHERE group_name IS NOT NULL
                ORDER BY group_name
            """)
            groups = cursor.fetchall()

            group_list = [group[0] for group in groups]
            self.sms_group_combo['values'] = group_list

            if not group_list:
                self.sms_group_combo['values'] = ["No groups available"]
    except Exception as e:
        print(f"⚠️ Error loading groups: {e}")
        self.sms_group_combo['values'] = ["Error loading groups"]

# Bind method to EmailManagerGUI
EmailManagerGUI.load_sms_groups = load_sms_groups

def load_sms_roles(self):
    """Load user roles for bulk SMS"""
    # Standard roles
    roles = ["student", "instructor", "staff", "admin"]
    self.sms_group_combo['values'] = roles

# Bind method to EmailManagerGUI
EmailManagerGUI.load_sms_roles = load_sms_roles

def update_sms_char_count(self, event=None):
    """Update SMS character counter"""
    try:
        message = self.sms_message_text.get("1.0", tk.END).strip()
        char_count = len(message)

        # Update label with color coding
        if char_count == 0:
            self.sms_char_label.config(text="0 / 160 characters", foreground='gray')
        elif char_count <= 160:
            self.sms_char_label.config(
                text=f"{char_count} / 160 characters",
                foreground='green'
            )
        else:
            # Calculate number of SMS segments needed
            segments = (char_count // 153) + 1
            self.sms_char_label.config(
                text=f"{char_count} chars ({segments} messages)",
                foreground='orange'
            )
    except Exception as e:
        print(f"Error updating char count: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.update_sms_char_count = update_sms_char_count

def send_sms(self):
    """Send SMS message"""
    try:
        # Get message
        message = self.sms_message_text.get("1.0", tk.END).strip()
        if not message:
            messagebox.showwarning("No Message", "Please enter a message to send.")
            return

        # Get recipients based on type
        recipient_type = self.sms_recipient_type.get()
        recipients = []

        if recipient_type == "individual":
            phone = self.sms_phone_entry.get().strip()
            if not phone:
                messagebox.showwarning("No Recipient", "Please enter a phone number or select a user.")
                return

            # Validate phone format
            if not self.validate_phone_number(phone):
                messagebox.showerror("Invalid Phone", "Phone number must be in format: +1234567890")
                return

            recipients = [(phone, self.sms_user_combo.get() or "Unknown")]

        elif recipient_type in ["group", "role"]:
            group_or_role = self.sms_group_combo.get()
            if not group_or_role:
                messagebox.showwarning("No Selection", f"Please select a {recipient_type}.")
                return

            # Get recipients from group/role
            recipients = self.get_recipients_for_group_or_role(recipient_type, group_or_role)

            if not recipients:
                messagebox.showwarning("No Recipients", f"No users found for {recipient_type}: {group_or_role}")
                return

        # Confirm bulk send
        if len(recipients) > 1:
            if not messagebox.askyesno("Confirm Bulk SMS",
                f"Send SMS to {len(recipients)} recipients?\n\nThis will send {len(recipients)} messages."):
                return

        # Send SMS to all recipients
        success_count = 0
        fail_count = 0

        for phone, recipient_name in recipients:
            try:
                # Store in database (simulated SMS - in production would use Twilio/AWS SNS)
                self.store_sms(phone, recipient_name, message, "sent")
                success_count += 1
            except Exception as e:
                print(f"Failed to send to {phone}: {e}")
                self.store_sms(phone, recipient_name, message, "failed")
                fail_count += 1

        # Show result
        result_msg = f"✅ SMS sent successfully to {success_count} recipient(s)"
        if fail_count > 0:
            result_msg += f"\n⚠️ {fail_count} failed"

        messagebox.showinfo("SMS Sent", result_msg)

        # Log activity
        log_activity(
            'send_sms',
            'communication',
            details={
                'recipient_count': len(recipients),
                'success': success_count,
                'failed': fail_count,
                'message_length': len(message)
            }
        )

        # Clear form and refresh history
        self.clear_sms_form()
        self.refresh_sms_history()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to send SMS: {str(e)}")
        print(f"SMS send error: {e}")

# Bind method to EmailManagerGUI
EmailManagerGUI.send_sms = send_sms

def validate_phone_number(self, phone):
    """Validate phone number format"""
    import re
    # Allow formats: +1234567890, +12345678901, etc.
    pattern = r'^\+\d{10,15}$'
    return bool(re.match(pattern, phone))

# Bind method to EmailManagerGUI
EmailManagerGUI.validate_phone_number = validate_phone_number

def get_recipients_for_group_or_role(self, recipient_type, value):
    """Get phone numbers for group or role"""
    try:
        with get_db_connection() as conn:
            if recipient_type == "role":
                # Get users by role
                cursor = conn.execute("""
                    SELECT phone, name FROM users
                    WHERE role = ? AND phone IS NOT NULL AND phone != ''
                """, (value,))
            else:
                # Get users by group
                cursor = conn.execute("""
                    SELECT u.phone, u.name
                    FROM users u
                    JOIN student_groups sg ON u.username = sg.username
                    WHERE sg.group_name = ? AND u.phone IS NOT NULL AND u.phone != ''
                """, (value,))

            return cursor.fetchall()
    except Exception as e:
        print(f"Error getting recipients: {e}")
        return []

# Bind method to EmailManagerGUI
EmailManagerGUI.get_recipients_for_group_or_role = get_recipients_for_group_or_role

def store_sms(self, phone, recipient_name, message, status):
    """Store SMS in database"""
    try:
        # Create SMS table if not exists
        with transaction() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sms_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_username TEXT,
                    recipient_name TEXT,
                    phone_number TEXT,
                    message TEXT,
                    status TEXT,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Insert SMS record
            conn.execute("""
                INSERT INTO sms_messages
                (sender_username, recipient_name, phone_number, message, status)
                VALUES (?, ?, ?, ?, ?)
            """, (
                self.auth.current_user['username'],
                recipient_name,
                phone,
                message,
                status
            ))

    except Exception as e:
        print(f"Error storing SMS: {e}")
        raise

# Bind method to EmailManagerGUI
EmailManagerGUI.store_sms = store_sms

def clear_sms_form(self):
    """Clear the SMS form"""
    self.sms_phone_entry.delete(0, tk.END)
    self.sms_user_combo.set('')
    self.sms_message_text.delete("1.0", tk.END)
    self.update_sms_char_count()

# Bind method to EmailManagerGUI
EmailManagerGUI.clear_sms_form = clear_sms_form

def sms_templates(self):
    """Show SMS templates dialog for managing reusable SMS messages"""
    dialog = tk.Toplevel(self.root)
    dialog.title("SMS Templates")
    dialog.geometry("700x500")
    dialog.transient(self.root)

    # Main frame with two panes
    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill='both', expand=True, padx=10, pady=10)

    # Left pane - template list
    list_frame = ttk.LabelFrame(main_frame, text="Templates")
    list_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

    # Templates treeview
    templates_tree = ttk.Treeview(list_frame, columns=('name', 'category'), show='headings', height=15)
    templates_tree.heading('name', text='Template Name')
    templates_tree.heading('category', text='Category')
    templates_tree.column('name', width=150)
    templates_tree.column('category', width=100)
    templates_tree.pack(fill='both', expand=True, padx=5, pady=5)

    # Right pane - template editor
    editor_frame = ttk.LabelFrame(main_frame, text="Template Editor")
    editor_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

    ttk.Label(editor_frame, text="Template Name:").pack(anchor='w', padx=5, pady=(5, 0))
    name_var = tk.StringVar()
    ttk.Entry(editor_frame, textvariable=name_var, width=30).pack(fill='x', padx=5, pady=2)

    ttk.Label(editor_frame, text="Category:").pack(anchor='w', padx=5, pady=(5, 0))
    category_var = tk.StringVar()
    category_combo = ttk.Combobox(editor_frame, textvariable=category_var,
                                  values=['Notification', 'Reminder', 'Alert', 'Verification', 'General'],
                                  state='readonly')
    category_combo.pack(fill='x', padx=5, pady=2)
    category_combo.set('General')

    ttk.Label(editor_frame, text="Message (160 chars max):").pack(anchor='w', padx=5, pady=(5, 0))
    message_text = tk.Text(editor_frame, height=5, width=30, wrap='word')
    message_text.pack(fill='x', padx=5, pady=2)

    # Character counter
    char_label = ttk.Label(editor_frame, text="0/160 characters")
    char_label.pack(anchor='w', padx=5)

    def update_char_count(event=None):
        count = len(message_text.get("1.0", "end-1c"))
        char_label.config(text=f"{count}/160 characters",
                        foreground='red' if count > 160 else 'black')

    message_text.bind('<KeyRelease>', update_char_count)

    # Placeholders info
    ttk.Label(editor_frame, text="Available placeholders:", font=('Arial', 9, 'bold')).pack(anchor='w', padx=5, pady=(10, 0))
    placeholders = "{name}, {student_id}, {date}, {time}, {code}"
    ttk.Label(editor_frame, text=placeholders, font=('Arial', 8), foreground='gray').pack(anchor='w', padx=5)

    def load_templates():
        """Load templates from database"""
        for item in templates_tree.get_children():
            templates_tree.delete(item)

        try:
            with get_db_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sms_templates (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT UNIQUE NOT NULL,
                        category TEXT,
                        message TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cursor = conn.execute("SELECT id, name, category FROM sms_templates ORDER BY name")
                for row in cursor.fetchall():
                    templates_tree.insert('', 'end', iid=row[0], values=(row[1], row[2]))

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load templates: {e}")

    def on_template_select(event):
        """Load selected template into editor"""
        selection = templates_tree.selection()
        if not selection:
            return

        template_id = selection[0]
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT name, category, message FROM sms_templates WHERE id = ?",
                    (template_id,)
                )
                row = cursor.fetchone()
                if row:
                    name_var.set(row[0])
                    category_var.set(row[1] or 'General')
                    message_text.delete("1.0", tk.END)
                    message_text.insert("1.0", row[2] or '')
                    update_char_count()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load template: {e}")

    templates_tree.bind('<<TreeviewSelect>>', on_template_select)

    def save_template():
        """Save current template"""
        name = name_var.get().strip()
        if not name:
            messagebox.showwarning("Validation Error", "Please enter a template name")
            return

        message = message_text.get("1.0", "end-1c").strip()
        if not message:
            messagebox.showwarning("Validation Error", "Please enter a message")
            return

        try:
            with get_db_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO sms_templates (name, category, message)
                    VALUES (?, ?, ?)
                """, (name, category_var.get(), message))

            messagebox.showinfo("Success", "Template saved successfully")
            load_templates()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")

    def delete_template():
        """Delete selected template"""
        selection = templates_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a template to delete")
            return

        if messagebox.askyesno("Confirm Delete", "Delete this template?"):
            try:
                with get_db_connection() as conn:
                    conn.execute("DELETE FROM sms_templates WHERE id = ?", (selection[0],))

                name_var.set('')
                category_var.set('General')
                message_text.delete("1.0", tk.END)
                load_templates()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete template: {e}")

    def use_template():
        """Use selected template in SMS composer"""
        message = message_text.get("1.0", "end-1c")
        if message:
            self.sms_message_text.delete("1.0", tk.END)
            self.sms_message_text.insert("1.0", message)
            self.update_sms_char_count()
            dialog.destroy()
            messagebox.showinfo("Success", "Template loaded into SMS composer")

    def new_template():
        """Clear form for new template"""
        name_var.set('')
        category_var.set('General')
        message_text.delete("1.0", tk.END)
        templates_tree.selection_remove(templates_tree.selection())

    # Buttons
    btn_frame = ttk.Frame(editor_frame)
    btn_frame.pack(fill='x', padx=5, pady=10)

    ttk.Button(btn_frame, text="New", command=new_template).pack(side='left', padx=2)
    ttk.Button(btn_frame, text="Save", command=save_template).pack(side='left', padx=2)
    ttk.Button(btn_frame, text="Delete", command=delete_template).pack(side='left', padx=2)
    ttk.Button(btn_frame, text="Use Template", command=use_template).pack(side='left', padx=2)

    # Load initial templates
    load_templates()

# Bind method to EmailManagerGUI
EmailManagerGUI.sms_templates = sms_templates

def refresh_sms_history(self):
    """Refresh SMS history list"""
    try:
        # Clear existing items
        for item in self.sms_history_tree.get_children():
            self.sms_history_tree.delete(item)

        # Get search term
        search_term = self.sms_search_entry.get().lower() if hasattr(self, 'sms_search_entry') else ""

        # Load SMS history
        with get_db_connection() as conn:
            # Check if table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='sms_messages'
            """)
            if not cursor.fetchone():
                # Table doesn't exist yet, create it
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sms_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_username TEXT,
                        recipient_name TEXT,
                        phone_number TEXT,
                        message TEXT,
                        status TEXT,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                return

            query = """
                SELECT id, sent_at, recipient_name, phone_number, message, status
                FROM sms_messages
                WHERE sender_username = ?
            """
            params = [self.auth.current_user['username']]

            if search_term:
                query += """ AND (
                    LOWER(recipient_name) LIKE ? OR
                    LOWER(phone_number) LIKE ? OR
                    LOWER(message) LIKE ?
                )"""
                search_pattern = f"%{escape_like(search_term)}%"
                params.extend([search_pattern, search_pattern, search_pattern])

            query += " ORDER BY sent_at DESC LIMIT 500"

            cursor = conn.execute(query, params)
            messages = cursor.fetchall()

            for msg in messages:
                sms_id, sent_at, recipient, phone, message, status = msg

                # Truncate long messages
                display_msg = message[:50] + "..." if len(message) > 50 else message

                # Determine tag based on status
                tag = status if status in ['sent', 'failed', 'pending'] else 'sent'

                self.sms_history_tree.insert('', 'end', values=(
                    sms_id,
                    sent_at,
                    recipient,
                    phone,
                    display_msg,
                    status.upper()
                ), tags=(tag,))

            print(f"✅ Loaded {len(messages)} SMS messages")

    except Exception as e:
        print(f"⚠️ Error loading SMS history: {e}")
        messagebox.showerror("Error", f"Failed to load SMS history: {str(e)}")

# Bind method to EmailManagerGUI
EmailManagerGUI.refresh_sms_history = refresh_sms_history

def delete_sms(self):
    """Delete selected SMS from history"""
    try:
        selection = self.sms_history_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select an SMS to delete.")
            return

        if not messagebox.askyesno("Confirm Delete", "Delete selected SMS from history?"):
            return

        # Get SMS ID
        item = self.sms_history_tree.item(selection[0])
        sms_id = item['values'][0]

        # Delete from database
        with transaction() as conn:
            conn.execute("DELETE FROM sms_messages WHERE id = ?", (sms_id,))

        # Refresh list
        self.refresh_sms_history()

        messagebox.showinfo("Deleted", "SMS deleted successfully")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete SMS: {str(e)}")

# Bind method to EmailManagerGUI
EmailManagerGUI.delete_sms = delete_sms

def sms_statistics(self):
    """Show SMS statistics"""
    try:
        with get_db_connection() as conn:
            # Check if table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='sms_messages'
            """)
            if not cursor.fetchone():
                messagebox.showinfo("Statistics", "No SMS data available yet.")
                return

            # Get statistics
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as sent,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending
                FROM sms_messages
                WHERE sender_username = ?
            """, (self.auth.current_user['username'],))

            stats = cursor.fetchone()
            total, sent, failed, pending = stats

            # Calculate success rate
            success_rate = (sent / total * 100) if total > 0 else 0

            stats_msg = f"""SMS Statistics for {self.auth.current_user['username']}

Total Messages: {total}
✅ Sent: {sent}
❌ Failed: {failed}
⏳ Pending: {pending}

Success Rate: {success_rate:.1f}%
"""

            messagebox.showinfo("SMS Statistics", stats_msg)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load statistics: {str(e)}")

# Bind method to EmailManagerGUI
EmailManagerGUI.sms_statistics = sms_statistics

