
from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.systems.university.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.systems.university.infrastructure.auth import UserAuth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.systems.university.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.systems.university.domains.academics.domain.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.systems.university.domains.academics.interfaces.gui.parent_portal.base import ParentPortalGUI

def show_all_parent_accounts(self):
    """Show all parent accounts in the system (admin only)"""
    # Verify admin access
    current_user = self.get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.access_denied', default="Access Denied"), _t('gui.academics.parent_portal.admin.dialogs.only_administrators_can_view_all_parent_accounts', default="Only administrators can view all parent accounts."))
        return

    self.clear_content()
    self.update_status("Viewing All Parent Accounts")

    # Title
    title = ttk.Label(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.all_parent_accounts', default="All Parent Accounts"),
                     style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Search/Filter frame
    filter_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.search_filter', default="Search & Filter"), padding=10)
    filter_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

    ttk.Label(filter_frame, text=_t('gui.academics.parent_portal.admin.labels.search', default="Search:")).pack(side=tk.LEFT, padx=5)
    search_var = tk.StringVar()
    search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=30)
    search_entry.pack(side=tk.LEFT, padx=5)

    ttk.Label(filter_frame, text=_t('gui.academics.parent_portal.admin.labels.filter_by_status', default="Filter by Status:")).pack(side=tk.LEFT, padx=(20, 5))
    status_var = tk.StringVar(value=_t('gui.academics.parent_portal.admin.values.all', default="All"))
    status_combo = ttk.Combobox(filter_frame, textvariable=status_var,
                               values=["All", "Active", "Inactive"], state="readonly", width=15)
    status_combo.pack(side=tk.LEFT, padx=5)

    # Main content frame
    main_frame = ttk.Frame(self.content_frame)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Summary frame
    summary_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.admin.labels.summary', default="Summary"), padding=10)
    summary_frame.pack(fill=tk.X, pady=(0, 10))

    # Parent accounts table
    accounts_frame = ttk.LabelFrame(main_frame, text=_t('gui.academics.parent_portal.admin.labels.parent_accounts', default="Parent Accounts"), padding=10)
    accounts_frame.pack(fill=tk.BOTH, expand=True)

    def load_parent_accounts(search_text="", status_filter="All"):
        # Clear existing data
        for widget in accounts_frame.winfo_children():
            widget.destroy()
        for widget in summary_frame.winfo_children():
            widget.destroy()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if parent_accounts table exists
            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='parent_accounts'
            """)

            if cursor.fetchone():
                # Build query based on filters
                query = """
                SELECT
                    p.parent_id,
                    p.first_name,
                    p.last_name,
                    p.email,
                    p.phone,
                    p.address,
                    p.registration_date,
                    COUNT(DISTINCT ps.student_id) as num_children
                FROM parent_accounts p
                LEFT JOIN parent_student_links ps ON p.parent_id = ps.parent_id
                WHERE 1=1
                """

                params = []

                # Add search filter
                if search_text:
                    query += " AND (p.first_name LIKE ? OR p.last_name LIKE ? OR p.email LIKE ? OR p.parent_id LIKE ?)"
                    search_pattern = f"%{escape_like(search_text)}%"
                    params.extend([search_pattern, search_pattern, search_pattern, search_pattern])

                # Status filter is no longer supported since is_active column doesn't exist
                # All accounts are considered active by default

                query += " GROUP BY p.parent_id ORDER BY p.last_name, p.first_name"

                cursor.execute(query, params)
                accounts = cursor.fetchall()

                # Update summary
                total_accounts = len(accounts)
                active_accounts = total_accounts  # All accounts are active since is_active column doesn't exist
                inactive_accounts = 0
                total_children = sum(acc[7] for acc in accounts)

                ttk.Label(summary_frame, text=f"Total Accounts: {total_accounts}",
                         font=('Arial', 10, 'bold')).pack(side=tk.LEFT, padx=20)
                ttk.Label(summary_frame, text=f"Active: {active_accounts}",
                         font=('Arial', 10), foreground='green').pack(side=tk.LEFT, padx=20)
                ttk.Label(summary_frame, text=f"Inactive: {inactive_accounts}",
                         font=('Arial', 10), foreground='orange').pack(side=tk.LEFT, padx=20)
                ttk.Label(summary_frame, text=f"Total Children Linked: {total_children}",
                         font=('Arial', 10)).pack(side=tk.LEFT, padx=20)

                if accounts:
                    # Create treeview
                    columns = ("Parent ID", "Name", "Email", "Phone", "Children", "Created", "Status")
                    tree = ttk.Treeview(accounts_frame, columns=columns, show="headings", height=20)

                    tree.heading("Parent ID", text=_t('gui.academics.parent_portal.admin.headings.parent_id', default="Parent ID"))
                    tree.heading("Name", text=_t('gui.academics.parent_portal.admin.headings.name', default="Name"))
                    tree.heading("Email", text=_t('gui.academics.parent_portal.admin.headings.email', default="Email"))
                    tree.heading("Phone", text=_t('gui.academics.parent_portal.admin.headings.phone', default="Phone"))
                    tree.heading("Children", text=_t('gui.academics.parent_portal.admin.headings.children', default="Children"))
                    tree.heading("Created", text=_t('gui.academics.parent_portal.admin.headings.created_date', default="Created Date"))
                    tree.heading("Status", text=_t('gui.academics.parent_portal.admin.headings.status', default="Status"))

                    tree.column("Parent ID", width=100)
                    tree.column("Name", width=200)
                    tree.column("Email", width=250)
                    tree.column("Phone", width=150)
                    tree.column("Children", width=80)
                    tree.column("Created", width=120)
                    tree.column("Status", width=80)

                    for acc in accounts:
                        parent_id = acc[0]
                        full_name = f"{acc[1]} {acc[2]}"
                        email = acc[3] or "N/A"
                        phone = acc[4] or "N/A"
                        num_children = acc[7]
                        registration_date = acc[6] or "N/A"
                        status = "Active"

                        tree.insert('', tk.END, values=(parent_id, full_name, email, phone, num_children, registration_date, status))

                    tree.tag_configure('active', foreground='green')
                    tree.tag_configure('inactive', foreground='gray')

                    scrollbar = ttk.Scrollbar(accounts_frame, orient=tk.VERTICAL, command=tree.yview)
                    tree.configure(yscrollcommand=scrollbar.set)

                    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    # Action buttons
                    btn_frame = ttk.Frame(accounts_frame)
                    btn_frame.pack(fill=tk.X, pady=10)

                    def view_parent_details():
                        selected = tree.selection()
                        if selected:
                            item = tree.item(selected[0])
                            parent_id = item['values'][0]
                            self.view_parent_account_details(parent_id)
                        else:
                            messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.no_selection', default="No Selection"), _t('gui.academics.parent_portal.admin.dialogs.please_select_a_parent_account_to_view', default="Please select a parent account to view."))

                    def export_to_csv():
                        from tkinter import filedialog
                        filename = filedialog.asksaveasfilename(
                            defaultextension=".csv",
                            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                            title=_t('gui.academics.parent_portal.admin.dialogs.export_parent_accounts', default="Export Parent Accounts")
                        )
                        if filename:
                            import csv
                            with open(filename, 'w', newline='') as f:
                                writer = csv.writer(f)
                                writer.writerow(["Parent ID", "First Name", "Last Name", "Email", "Phone", "Address", "Children", "Registration Date", "Status"])
                                for acc in accounts:
                                    writer.writerow([acc[0], acc[1], acc[2], acc[3], acc[4], acc[5], acc[7], acc[6], "Active"])
                            messagebox.showinfo(_t('gui.academics.parent_portal.admin.dialogs.export_complete', default="Export Complete"), f"Parent accounts exported to:\n{filename}")

                    ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.admin.buttons.view_details', default="View Details"), command=view_parent_details).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.admin.buttons.export_to_csv', default="Export to CSV"), command=export_to_csv).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.admin.buttons.refresh', default="Refresh"), command=lambda: load_parent_accounts(search_var.get(), status_var.get())).pack(side=tk.LEFT, padx=5)

                else:
                    ttk.Label(accounts_frame, text=_t('gui.academics.parent_portal.admin.labels.no_parent_accounts_found_matching_the_criteria', default="No parent accounts found matching the criteria."),
                             font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(summary_frame, text=_t('gui.academics.parent_portal.admin.labels.parent_accounts_table_not_found_in_database', default="Parent accounts table not found in database."),
                         font=('Arial', 10)).pack(pady=10)
                ttk.Label(accounts_frame, text=_t('gui.academics.parent_portal.admin.labels.parent_accounts_system_not_configured', default="Parent accounts system not configured."),
                         font=('Arial', 11)).pack(pady=50)

            conn.close()

        except Exception as e:
            ttk.Label(accounts_frame, text=f"Error loading parent accounts: {str(e)}",
                     font=('Arial', 10)).pack(pady=50)

    # Bind search and filter
    search_entry.bind('<Return>', lambda e: load_parent_accounts(search_var.get(), status_var.get()))
    status_combo.bind('<<ComboboxSelected>>', lambda e: load_parent_accounts(search_var.get(), status_var.get()))

    ttk.Button(filter_frame, text=_t('gui.academics.parent_portal.admin.buttons.search', default="Search"), command=lambda: load_parent_accounts(search_var.get(), status_var.get())).pack(side=tk.LEFT, padx=5)
    ttk.Button(filter_frame, text=_t('gui.academics.parent_portal.admin.buttons.clear', default="Clear"), command=lambda: [search_var.set(""), status_var.set("All"), load_parent_accounts()]).pack(side=tk.LEFT, padx=5)

    # Load initial data
    load_parent_accounts()
ParentPortalGUI.show_all_parent_accounts = show_all_parent_accounts

def view_parent_account_details(self, parent_id):
    """View detailed information about a specific parent account"""
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Parent Account Details - {parent_id}")
    dialog.geometry("700x600")
    dialog.transient(self.root)
    dialog.grab_set()

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Get parent account details
        cursor.execute("""
        SELECT parent_id, first_name, last_name, email, phone, address, registration_date
        FROM parent_accounts
        WHERE parent_id = ?
        """, (parent_id,))

        parent = cursor.fetchone()

        if parent:
            # Title
            title_frame = ttk.Frame(dialog, padding=20)
            title_frame.pack(fill=tk.X)
            ttk.Label(title_frame, text=f"Parent: {parent[1]} {parent[2]}",
                     font=('Arial', 16, 'bold')).pack(anchor='w')
            ttk.Label(title_frame, text=f"Parent ID: {parent[0]}",
                     font=('Arial', 10), foreground='gray').pack(anchor='w')

            # Account information
            info_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.parent_portal.admin.labels.account_information', default="Account Information"), padding=20)
            info_frame.pack(fill=tk.X, padx=20, pady=10)

            ttk.Label(info_frame, text=f"Email: {parent[3] or 'N/A'}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)
            ttk.Label(info_frame, text=f"Phone: {parent[4] or 'N/A'}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)
            ttk.Label(info_frame, text=f"Address: {parent[5] or 'N/A'}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)
            ttk.Label(info_frame, text=f"Registration Date: {parent[6] or 'N/A'}",
                     font=('Arial', 10)).pack(anchor='w', pady=3)
            ttk.Label(info_frame, text=_t('gui.academics.parent_portal.admin.labels.status_active', default="Status: Active"),
                     font=('Arial', 10), foreground='green').pack(anchor='w', pady=3)

            # Linked children
            children_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.parent_portal.admin.labels.linked_children', default="Linked Children"), padding=20)
            children_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            cursor.execute("""
            SELECT s.student_id, s.first_name, s.last_name, s.course, s.status
            FROM students s
            INNER JOIN parent_student_links ps ON s.student_id = ps.student_id
            WHERE ps.parent_id = ?
            ORDER BY s.last_name, s.first_name
            """, (parent_id,))

            children = cursor.fetchall()

            if children:
                for child in children:
                    child_card = ttk.Frame(children_frame)
                    child_card.pack(fill=tk.X, pady=5)
                    ttk.Label(child_card, text=f"• {child[1]} {child[2]} (ID: {child[0]})",
                             font=('Arial', 10, 'bold')).pack(anchor='w')
                    ttk.Label(child_card, text=f"  Year: {child[3] or 'N/A'} | Program: {child[4] or 'N/A'}",
                             font=('Arial', 9)).pack(anchor='w', padx=20)
            else:
                ttk.Label(children_frame, text=_t('gui.academics.parent_portal.admin.labels.no_students_linked_to_this_account', default="No students linked to this account."),
                         font=('Arial', 10)).pack(pady=20)

        else:
            ttk.Label(dialog, text=_t('gui.academics.parent_portal.admin.labels.parent_account_not_found', default="Parent account not found."),
                     font=('Arial', 11)).pack(pady=50)

        conn.close()

    except Exception as e:
        ttk.Label(dialog, text=f"Error loading parent account details: {str(e)}",
                 font=('Arial', 10)).pack(pady=50)

    # Close button
    ttk.Button(dialog, text=_t('gui.academics.parent_portal.admin.buttons.close', default="Close"), command=dialog.destroy).pack(pady=10)
ParentPortalGUI.view_parent_account_details = view_parent_account_details

def show_create_parent_account_interface(self):
    """Show interface for creating a new parent account (admin only)"""
    # Check admin role dynamically
    current_user = self.get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.access_denied', default="Access Denied"), _t('gui.academics.parent_portal.admin.dialogs.only_administrators_can_create_parent_accounts', default="Only administrators can create parent accounts."))
        return

    self.clear_content()
    self.update_status("Create Parent Account")

    title = ttk.Label(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.create_new_parent_account', default="Create New Parent Account"),
                     style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Form frame
    form_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.parent_information', default="Parent Information"), padding=20)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # First Name
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.first_name', default="First Name:"), font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
    first_name_entry = ttk.Entry(form_frame, width=40)
    first_name_entry.grid(row=0, column=1, pady=5, sticky='ew')

    # Last Name
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.last_name', default="Last Name:"), font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky='w', pady=5)
    last_name_entry = ttk.Entry(form_frame, width=40)
    last_name_entry.grid(row=1, column=1, pady=5, sticky='ew')

    # Email
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.email', default="Email:"), font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
    email_entry = ttk.Entry(form_frame, width=40)
    email_entry.grid(row=2, column=1, pady=5, sticky='ew')

    # Phone
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.phone', default="Phone:"), font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=5)
    phone_entry = ttk.Entry(form_frame, width=40)
    phone_entry.grid(row=3, column=1, pady=5, sticky='ew')

    # Address
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.address', default="Address:"), font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='nw', pady=5)
    address_text = scrolledtext.ScrolledText(form_frame, width=40, height=4)
    address_text.grid(row=4, column=1, pady=5, sticky='ew')

    form_frame.columnconfigure(1, weight=1)

    # Result display
    result_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.created_account_details', default="Created Account Details"), padding=20)
    result_frame.pack(fill=tk.X, padx=20, pady=10)
    result_label = ttk.Label(result_frame, text=_t('gui.academics.parent_portal.admin.labels.account_details_will_appear_here_after_creation', default="Account details will appear here after creation"),
                            font=('Arial', 10, 'italic'))
    result_label.pack()

    # Buttons
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=10)

    def create_account():
        first_name = first_name_entry.get().strip()
        last_name = last_name_entry.get().strip()
        email = email_entry.get().strip()
        phone = phone_entry.get().strip()
        address = address_text.get('1.0', tk.END).strip()

        # Validation
        if not first_name or not last_name:
            messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.validation_error', default="Validation Error"), _t('gui.academics.parent_portal.admin.dialogs.first_name_and_last_name_are_required', default="First name and last name are required."))
            return

        if not email or '@' not in email:
            messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.validation_error', default="Validation Error"), _t('gui.academics.parent_portal.admin.dialogs.please_enter_a_valid_email_address', default="Please enter a valid email address."))
            return

        try:
            import random
            import secrets
            import string
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute('SELECT email FROM parent_accounts WHERE email = ?', (email,))
            if cursor.fetchone():
                messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), _t('gui.academics.parent_portal.admin.dialogs.this_email_is_already_registered', default="This email is already registered."))
                conn.close()
                return

            # Generate parent_id
            parent_id = f"P{random.randint(10000, 99999)}"

            # Insert parent account
            cursor.execute('''
            INSERT INTO parent_accounts (parent_id, first_name, last_name, email, phone, address)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (parent_id, first_name, last_name, email, phone, address))

            # Generate username and password
            # Use underscores instead of dots (dots not allowed by username validation)
            username = f"{first_name.lower()}_{last_name.lower()}_{random.randint(100, 999)}"
            password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

            # Close the connection - we'll use central auth now
            conn.commit()
            conn.close()

            # Create user account using central authentication (SECURE)
            if not self.auth:
                messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), _t('gui.academics.parent_portal.admin.dialogs.authentication_system_not_available', default="Authentication system not available."))
                return

            success = self.auth.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='parent',
                password_reset_required=True  # Force password change on first login
            )

            if not success:
                messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), _t('gui.academics.parent_portal.admin.dialogs.failed_to_create_user_account', default="Failed to create user account."))
                # Rollback parent account creation
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                try:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM parent_accounts WHERE parent_id = ?', (parent_id,))
                    conn.commit()
                finally:
                    conn.close()
                return

            # Get the created user ID
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM user_accounts WHERE username = ?', (username,))
            user_result = cursor.fetchone()

            if not user_result:
                messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), _t('gui.academics.parent_portal.admin.dialogs.user_created_but_id_not_found', default="User created but ID not found."))
                conn.close()
                return

            user_id = user_result[0]

            # Link user to parent
            cursor.execute('''
            INSERT INTO parent_user_mapping (user_id, parent_id)
            VALUES (?, ?)
            ''', (user_id, parent_id))

            conn.commit()
            conn.close()

            # Log activity
            try:
                from education_system.systems.university.infrastructure.activity_logger import log_activity
                log_activity('create', 'parent_account',
                            details={'parent_id': parent_id, 'username': username, 'email': email})
            except Exception as log_error:
                print(f"Activity logging failed: {log_error}")

            # Show success and account details
            result_text = f"Parent ID: {parent_id}\n\n" \
                         f"Username: {username}\n" \
                         f"Temporary Password: {password}\n\n" \
                         f"IMPORTANT: Please save these credentials!\n" \
                         f"The parent should change the password on first login."

            result_label.config(text=result_text, font=('Arial', 10), foreground='green')

            messagebox.showinfo(_t('gui.academics.parent_portal.admin.dialogs.success', default="Success"),
                f"Parent account created successfully!\n\n"
                f"Username: {username}\n"
                f"Password: {password}\n\n"
                f"Please provide these credentials to the parent.")

            self.update_status("Parent account created successfully")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), f"Failed to create parent account: {str(e)}")

    ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.admin.buttons.create_account', default="Create Account"), command=create_account).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.admin.buttons.back_to_admin_panel', default="Back to Admin Panel"), command=self.show_admin_menu).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.show_create_parent_account_interface = show_create_parent_account_interface

def show_link_student_interface(self):
    """Show interface for linking a student to a parent (admin only)"""
    # Check admin role dynamically
    current_user = self.get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.access_denied', default="Access Denied"), _t('gui.academics.parent_portal.admin.dialogs.only_administrators_can_link_students_to_parents', default="Only administrators can link students to parents."))
        return

    self.clear_content()
    self.update_status("Link Student to Family Account")

    title = ttk.Label(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.link_student_to_family_account', default="Link Student to Family Account"),
                     style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    # Form frame
    form_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.link_information', default="Link Information"), padding=20)
    form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    # Family Account ID
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.family_account_id', default="Family Account ID:"), font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
    parent_id_entry = ttk.Entry(form_frame, width=40)
    parent_id_entry.grid(row=0, column=1, pady=5, sticky='ew')

    ttk.Button(form_frame, text=_t('gui.academics.parent_portal.admin.buttons.search_account', default="Search Account"),
              command=lambda: search_parent(parent_id_entry.get())).grid(row=0, column=2, padx=5)

    # Parent info display
    parent_info_label = ttk.Label(form_frame, text="", font=('Arial', 9))
    parent_info_label.grid(row=1, column=0, columnspan=3, sticky='w', pady=5)

    # Student ID
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.student_id', default="Student ID:"), font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', pady=5)
    student_id_entry = ttk.Entry(form_frame, width=40)
    student_id_entry.grid(row=2, column=1, pady=5, sticky='ew')

    ttk.Button(form_frame, text=_t('gui.academics.parent_portal.admin.buttons.search_student', default="Search Student"),
              command=lambda: search_student(student_id_entry.get())).grid(row=2, column=2, padx=5)

    # Student info display
    student_info_label = ttk.Label(form_frame, text="", font=('Arial', 9))
    student_info_label.grid(row=3, column=0, columnspan=3, sticky='w', pady=5)

    # Relationship
    ttk.Label(form_frame, text=_t('gui.academics.parent_portal.admin.labels.relationship', default="Relationship:"), font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky='w', pady=5)
    relationship_var = tk.StringVar()
    relationship_combo = ttk.Combobox(form_frame, textvariable=relationship_var, width=37, state='readonly')
    relationship_combo['values'] = ["Parent", "Guardian", "Spouse", "Sibling", "Other Family"]
    relationship_combo.current(0)
    relationship_combo.grid(row=4, column=1, pady=5, sticky='ew')

    form_frame.columnconfigure(1, weight=1)

    def search_parent(parent_id):
        if not parent_id:
            messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.validation_error', default="Validation Error"), _t('gui.academics.parent_portal.admin.dialogs.please_enter_a_parent_id', default="Please enter a parent ID."))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT first_name, last_name, email, phone
            FROM parent_accounts
            WHERE parent_id = ?
            ''', (parent_id,))

            parent = cursor.fetchone()
            conn.close()

            if parent:
                parent_info_label.config(
                    text=f"Parent: {parent[0]} {parent[1]} | Email: {parent[2]} | Phone: {parent[3] or 'N/A'}",
                    foreground='green'
                )
            else:
                parent_info_label.config(text=_t('gui.academics.parent_portal.admin.text.parent_not_found', default="Parent not found!"), foreground='red')

        except Exception as e:
            messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), f"Failed to search parent: {str(e)}")

    def search_student(student_id):
        if not student_id:
            messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.validation_error', default="Validation Error"), _t('gui.academics.parent_portal.admin.dialogs.please_enter_a_student_id', default="Please enter a student ID."))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('''
            SELECT first_name, last_name, dob, course
            FROM students
            WHERE student_id = ?
            ''', (student_id,))

            student = cursor.fetchone()
            conn.close()

            if student:
                student_info_label.config(
                    text=f"Student: {student[0]} {student[1]} | DOB: {student[2]} | Year: {student[3]}",
                    foreground='green'
                )
            else:
                student_info_label.config(text=_t('gui.academics.parent_portal.admin.text.student_not_found', default="Student not found!"), foreground='red')

        except Exception as e:
            messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), f"Failed to search student: {str(e)}")

    # Buttons
    btn_frame = ttk.Frame(self.content_frame)
    btn_frame.pack(pady=20)

    def link_accounts():
        parent_id = parent_id_entry.get().strip()
        student_id = student_id_entry.get().strip()
        relationship = relationship_var.get()

        if not parent_id or not student_id:
            messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.validation_error', default="Validation Error"), _t('gui.academics.parent_portal.admin.dialogs.please_enter_both_parent_id_and_student_id', default="Please enter both parent ID and student ID."))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Verify parent exists
            cursor.execute('SELECT parent_id FROM parent_accounts WHERE parent_id = ?', (parent_id,))
            if not cursor.fetchone():
                messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), _t('gui.academics.parent_portal.admin.dialogs.parent_id_not_found', default="Parent ID not found."))
                conn.close()
                return

            # Verify student exists
            cursor.execute('SELECT student_id FROM students WHERE student_id = ?', (student_id,))
            if not cursor.fetchone():
                messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), _t('gui.academics.parent_portal.admin.dialogs.student_id_not_found', default="Student ID not found."))
                conn.close()
                return

            # Check if link already exists
            cursor.execute('''
            SELECT * FROM parent_student_links
            WHERE parent_id = ? AND student_id = ?
            ''', (parent_id, student_id))

            if cursor.fetchone():
                messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.duplicate', default="Duplicate"), _t('gui.academics.parent_portal.admin.dialogs.this_parent_is_already_linked_to_this_student', default="This parent is already linked to this student."))
                conn.close()
                return

            # Create link
            cursor.execute('''
            INSERT INTO parent_student_links (parent_id, student_id, relationship)
            VALUES (?, ?, ?)
            ''', (parent_id, student_id, relationship))

            conn.commit()
            conn.close()

            messagebox.showinfo(_t('gui.academics.parent_portal.admin.dialogs.success', default="Success"),
                f"Student {student_id} successfully linked to parent {parent_id}\n"
                f"Relationship: {relationship}")

            self.update_status("Student linked to parent successfully")

            # Clear form
            parent_id_entry.delete(0, tk.END)
            student_id_entry.delete(0, tk.END)
            parent_info_label.config(text="")
            student_info_label.config(text="")

        except Exception as e:
            messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), f"Failed to link accounts: {str(e)}")

    ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.admin.buttons.link_accounts', default="Link Accounts"), command=link_accounts).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text=_t('gui.academics.parent_portal.admin.buttons.back_to_admin_panel', default="Back to Admin Panel"), command=self.show_admin_menu).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.show_link_student_interface = show_link_student_interface

def show_view_parent_dashboard_interface(self):
    """Show interface to view any parent's dashboard (admin only)"""
    current_user = self.get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.access_denied', default="Access Denied"), _t('gui.academics.parent_portal.admin.dialogs.only_administrators_can_view_parent_dashboards', default="Only administrators can view parent dashboards."))
        return

    self.clear_content()
    self.update_status("View Parent Dashboard")

    title = ttk.Label(
        self.content_frame,
        text=_t('gui.academics.parent_portal.admin.labels.view_parent_dashboard', default="View Parent Dashboard"),
        style='Title.TLabel',
        font=('Arial', 20, 'bold')
    )
    title.pack(pady=20)

    # Search frame
    search_frame = ttk.LabelFrame(self.content_frame, text=_t('gui.academics.parent_portal.admin.labels.search_for_parent', default="Search for Parent"), padding=20)
    search_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(search_frame, text=_t('gui.academics.parent_portal.admin.labels.parent_id_or_email', default="Parent ID or Email:"), font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=5)
    search_entry = ttk.Entry(search_frame, width=40, font=('Arial', 10))
    search_entry.grid(row=0, column=1, padx=10, pady=5)

    parent_info_label = ttk.Label(search_frame, text="", font=('Arial', 9))
    parent_info_label.grid(row=1, column=0, columnspan=2, pady=5)

    def search_parent():
        search_value = search_entry.get().strip()
        if not search_value:
            messagebox.showwarning(_t('gui.academics.parent_portal.admin.dialogs.input_required', default="Input Required"), _t('gui.academics.parent_portal.admin.dialogs.please_enter_a_parent_id_or_email', default="Please enter a parent ID or email"))
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Search by parent_id or email
            cursor.execute('''
                SELECT parent_id, first_name, last_name, email, phone
                FROM parent_accounts
                WHERE parent_id = ? OR email = ?
            ''', (search_value, search_value))

            parent = cursor.fetchone()
            conn.close()

            if parent:
                parent_info_label.config(
                    text=f"Found: {parent[1]} {parent[2]} | Email: {parent[3]} | Phone: {parent[4] or 'N/A'}",
                    foreground='green'
                )

                # Show view dashboard button
                if hasattr(search_frame, 'view_btn'):
                    search_frame.view_btn.destroy()

                def view_dashboard():
                    # Temporarily set parent_id to view their dashboard
                    original_parent_id = self.parent_id
                    self.parent_id = parent[0]

                    # Load that parent's students
                    self.load_user_data()

                    # Show dashboard
                    self.show_dashboard()

                    # Reset parent_id
                    self.parent_id = original_parent_id

                search_frame.view_btn = ttk.Button(
                    search_frame,
                    text=_t('gui.academics.parent_portal.admin.buttons.view_this_parent_s_dashboard', default="View This Parent's Dashboard"),
                    command=view_dashboard
                )
                search_frame.view_btn.grid(row=2, column=0, columnspan=2, pady=10)
            else:
                parent_info_label.config(text=_t('gui.academics.parent_portal.admin.text.parent_not_found', default="Parent not found!"), foreground='red')

        except Exception as e:
            messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), f"Database error: {str(e)}")

    ttk.Button(search_frame, text=_t('gui.academics.parent_portal.admin.buttons.search', default="Search"), command=search_parent).grid(row=0, column=2, padx=5)
    ttk.Button(self.content_frame, text=_t('gui.academics.parent_portal.admin.buttons.back_to_admin_panel', default="Back to Admin Panel"), command=self.show_admin_menu).pack(pady=20)
ParentPortalGUI.show_view_parent_dashboard_interface = show_view_parent_dashboard_interface

def show_parent_reports_interface(self):
    """Show parent account reports interface (admin only)"""
    current_user = self.get_current_user()
    if not current_user or current_user.get('role') != 'admin':
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.access_denied', default="Access Denied"), _t('gui.academics.parent_portal.admin.dialogs.only_administrators_can_view_reports', default="Only administrators can view reports."))
        return

    self.clear_content()
    self.update_status("Parent Account Reports")

    title = ttk.Label(
        self.content_frame,
        text=_t('gui.academics.parent_portal.admin.labels.parent_account_reports', default="Parent Account Reports"),
        style='Title.TLabel',
        font=('Arial', 20, 'bold')
    )
    title.pack(pady=20)

    # Reports frame
    reports_frame = ttk.Frame(self.content_frame)
    reports_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    # Statistics
    stats_frame = ttk.LabelFrame(reports_frame, text=_t('gui.academics.parent_portal.admin.labels.system_statistics', default="System Statistics"), padding=15)
    stats_frame.pack(fill=tk.X, pady=10)

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Total parents
        cursor.execute("SELECT COUNT(*) FROM parent_accounts")
        total_parents = cursor.fetchone()[0]

        # Total relationships
        cursor.execute("SELECT COUNT(*) FROM parent_student_relationships")
        total_links = cursor.fetchone()[0]

        # Recent registrations (last 30 days)
        cursor.execute("""
            SELECT COUNT(*) FROM parent_accounts
            WHERE registration_date >= date('now', '-30 days')
        """)
        recent_registrations = cursor.fetchone()[0]

        conn.close()

        ttk.Label(stats_frame, text=f"Total Parent Accounts: {total_parents}", font=('Arial', 10)).pack(anchor='w', pady=2)
        ttk.Label(stats_frame, text=f"Total Parent-Student Links: {total_links}", font=('Arial', 10)).pack(anchor='w', pady=2)
        ttk.Label(stats_frame, text=f"New Registrations (30 days): {recent_registrations}", font=('Arial', 10)).pack(anchor='w', pady=2)

    except Exception as e:
        ttk.Label(stats_frame, text=f"Error loading statistics: {str(e)}", foreground='red').pack()

    # Report options
    report_options_frame = ttk.LabelFrame(reports_frame, text=_t('gui.academics.parent_portal.admin.labels.generate_reports', default="Generate Reports"), padding=15)
    report_options_frame.pack(fill=tk.X, pady=10)

    ttk.Button(
        report_options_frame,
        text=_t('gui.academics.parent_portal.admin.buttons.export_all_parent_accounts_csv', default="Export All Parent Accounts (CSV)"),
        command=self.export_parent_accounts_csv
    ).pack(fill=tk.X, pady=5)

    ttk.Button(
        report_options_frame,
        text=_t('gui.academics.parent_portal.admin.buttons.view_parent_activity_log', default="View Parent Activity Log"),
        command=self.view_parent_activity_log_interface
    ).pack(fill=tk.X, pady=5)

    ttk.Button(self.content_frame, text=_t('gui.academics.parent_portal.admin.buttons.back_to_admin_panel', default="Back to Admin Panel"), command=self.show_admin_menu).pack(pady=20)
ParentPortalGUI.show_parent_reports_interface = show_parent_reports_interface

def export_parent_accounts_csv(self):
    """Export all parent accounts to CSV file"""
    try:
        # Prompt user to select save location
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"parent_accounts_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not file_path:
            return  # User cancelled

        # Connect to database
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Fetch all parent accounts with their associated children
        cursor.execute('''
            SELECT
                pa.parent_id,
                pa.first_name,
                pa.last_name,
                pa.email,
                pa.phone,
                pa.address,
                pa.emergency_contact,
                pa.registration_date,
                pa.two_factor_enabled,
                COUNT(DISTINCT pc.student_id) as child_count
            FROM parent_accounts pa
            LEFT JOIN parent_children pc ON pa.parent_id = pc.parent_id
            GROUP BY pa.parent_id
            ORDER BY pa.last_name, pa.first_name
        ''')

        parent_data = cursor.fetchall()

        if not parent_data:
            messagebox.showinfo(_t('gui.academics.parent_portal.admin.dialogs.no_data', default="No Data"), _t('gui.academics.parent_portal.admin.dialogs.no_parent_accounts_found_to_export', default="No parent accounts found to export."))
            conn.close()
            return

        # Write to CSV
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)

            # Write header
            csv_writer.writerow([
                'Parent ID',
                'First Name',
                'Last Name',
                'Email',
                'Phone',
                'Address',
                'Emergency Contact',
                'Registration Date',
                '2FA Enabled',
                'Number of Children'
            ])

            # Write data rows
            for row in parent_data:
                # Format boolean and date values
                formatted_row = list(row)
                formatted_row[6] = 'Yes' if row[6] else 'No'  # Emergency contact
                formatted_row[8] = 'Yes' if row[8] else 'No'  # 2FA enabled
                csv_writer.writerow(formatted_row)

        conn.close()

        # Log the activity
        from education_system.systems.university.infrastructure.activity_logger import log_activity
        current_user = self.get_current_user()
        if current_user:
            log_activity(
                'export',
                'parent_accounts',
                user_id=current_user.get('id'),
                details={
                    'export_type': 'csv',
                    'record_count': len(parent_data),
                    'file_path': file_path
                }
            )

        messagebox.showinfo(
            _t('gui.academics.parent_portal.admin.dialogs.export_successful', default="Export Successful"),
            f"Successfully exported {len(parent_data)} parent account(s) to:\n{file_path}"
        )
        self.update_status(f"Exported {len(parent_data)} parent accounts to CSV")

    except Exception as e:
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.export_error', default="Export Error"), f"Failed to export parent accounts:\n{str(e)}")
        print(f"Error exporting parent accounts: {e}")
ParentPortalGUI.export_parent_accounts_csv = export_parent_accounts_csv

def view_parent_activity_log_interface(self):
    """View parent activity log for all parents (admin function)"""
    try:
        # Create new window for activity log
        log_window = tk.Toplevel(self.root)
        log_window.title(_t('gui.academics.parent_portal.admin.windows.parent_activity_log', default="Parent Activity Log"))
        log_window.geometry("1000x600")

        # Title
        title_frame = ttk.Frame(log_window)
        title_frame.pack(fill=tk.X, padx=20, pady=10)

        title_label = ttk.Label(
            title_frame,
            text=_t('gui.academics.parent_portal.admin.labels.parent_activity_log', default="Parent Activity Log"),
            font=('Arial', 18, 'bold')
        )
        title_label.pack(side=tk.LEFT)

        # Filter controls
        filter_frame = ttk.LabelFrame(log_window, text=_t('gui.academics.parent_portal.admin.labels.filters', default="Filters"), padding=10)
        filter_frame.pack(fill=tk.X, padx=20, pady=10)

        # Parent ID filter
        ttk.Label(filter_frame, text=_t('gui.academics.parent_portal.admin.labels.parent_id', default="Parent ID:")).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        parent_id_var = tk.StringVar()
        parent_id_entry = ttk.Entry(filter_frame, textvariable=parent_id_var, width=20)
        parent_id_entry.grid(row=0, column=1, padx=5, pady=5)

        # Action filter
        ttk.Label(filter_frame, text=_t('gui.academics.parent_portal.admin.labels.action', default="Action:")).grid(row=0, column=2, padx=5, pady=5, sticky='w')
        action_var = tk.StringVar(value=_t('gui.academics.parent_portal.admin.values.all', default="All"))
        action_combo = ttk.Combobox(
            filter_frame,
            textvariable=action_var,
            values=["All", "login", "view", "update", "message", "absence_report", "emergency_contact_update"],
            state='readonly',
            width=20
        )
        action_combo.grid(row=0, column=3, padx=5, pady=5)

        # Date range
        ttk.Label(filter_frame, text=_t('gui.academics.parent_portal.admin.labels.days_back', default="Days Back:")).grid(row=0, column=4, padx=5, pady=5, sticky='w')
        days_var = tk.StringVar(value="7")
        days_combo = ttk.Combobox(
            filter_frame,
            textvariable=days_var,
            values=["1", "7", "30", "90", "365"],
            state='readonly',
            width=10
        )
        days_combo.grid(row=0, column=5, padx=5, pady=5)

        # Activity log table
        table_frame = ttk.Frame(log_window)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        columns = ('Timestamp', 'Parent ID', 'Parent Name', 'Action', 'Details')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)

        # Configure columns
        tree.column('Timestamp', width=150)
        tree.column('Parent ID', width=100)
        tree.column('Parent Name', width=150)
        tree.column('Action', width=150)
        tree.column('Details', width=350)

        for col in columns:
            tree.heading(col, text=col)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Load data function
        def load_activity_data():
            # Clear existing data
            for item in tree.get_children():
                tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Build query based on filters
                days_back = int(days_var.get())
                cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_back)).strftime('%Y-%m-%d %H:%M:%S')

                query = '''
                    SELECT
                        pal.timestamp,
                        pal.parent_id,
                        pa.first_name || ' ' || pa.last_name as parent_name,
                        pal.action,
                        pal.details
                    FROM parent_activity_log pal
                    LEFT JOIN parent_accounts pa ON pal.parent_id = pa.parent_id
                    WHERE pal.timestamp >= ?
                '''
                params = [cutoff_date]

                # Add parent ID filter
                if parent_id_var.get().strip():
                    query += ' AND pal.parent_id LIKE ?'
                    params.append(f'%{parent_id_var.get().strip()}%')

                # Add action filter
                if action_var.get() != "All":
                    query += ' AND pal.action = ?'
                    params.append(action_var.get())

                query += ' ORDER BY pal.timestamp DESC LIMIT 500'

                cursor.execute(query, params)
                activities = cursor.fetchall()

                # Insert data into tree
                for activity in activities:
                    tree.insert('', tk.END, values=activity)

                conn.close()

                # Update status label
                status_label.config(text=f"Showing {len(activities)} activities")

            except Exception as e:
                messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), f"Failed to load activity log:\n{str(e)}")
                print(f"Error loading activity log: {e}")

        # Buttons
        button_frame = ttk.Frame(log_window)
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(
            button_frame,
            text=_t('gui.academics.parent_portal.admin.buttons.apply_filters', default="Apply Filters"),
            command=load_activity_data
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t('gui.academics.parent_portal.admin.buttons.export_to_csv', default="Export to CSV"),
            command=lambda: self.export_activity_log_csv(tree)
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text=_t('gui.academics.parent_portal.admin.buttons.refresh', default="Refresh"),
            command=load_activity_data
        ).pack(side=tk.LEFT, padx=5)

        # Status label
        status_label = ttk.Label(button_frame, text="", font=('Arial', 9))
        status_label.pack(side=tk.RIGHT, padx=5)

        ttk.Button(
            button_frame,
            text=_t('gui.academics.parent_portal.admin.buttons.close', default="Close"),
            command=log_window.destroy
        ).pack(side=tk.RIGHT, padx=5)

        # Load initial data
        load_activity_data()

        # Log this admin action
        from education_system.systems.university.infrastructure.activity_logger import log_activity
        current_user = self.get_current_user()
        if current_user:
            log_activity(
                'view',
                'parent_activity_log',
                user_id=current_user.get('id'),
                details={'action': 'viewed_activity_log_interface'}
            )

    except Exception as e:
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.error', default="Error"), f"Failed to open activity log viewer:\n{str(e)}")
        print(f"Error opening activity log viewer: {e}")
ParentPortalGUI.view_parent_activity_log_interface = view_parent_activity_log_interface

def export_activity_log_csv(self, tree):
    """Export activity log data from tree to CSV"""
    try:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"parent_activity_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        if not file_path:
            return

        # Get all items from tree
        items = tree.get_children()

        if not items:
            messagebox.showinfo(_t('gui.academics.parent_portal.admin.dialogs.no_data', default="No Data"), _t('gui.academics.parent_portal.admin.dialogs.no_activity_log_data_to_export', default="No activity log data to export."))
            return

        # Write to CSV
        with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)

            # Write header
            csv_writer.writerow(['Timestamp', 'Parent ID', 'Parent Name', 'Action', 'Details'])

            # Write data rows
            for item in items:
                values = tree.item(item)['values']
                csv_writer.writerow(values)

        messagebox.showinfo(
            _t('gui.academics.parent_portal.admin.dialogs.export_successful', default="Export Successful"),
            f"Successfully exported {len(items)} activity log entries to:\n{file_path}"
        )

    except Exception as e:
        messagebox.showerror(_t('gui.academics.parent_portal.admin.dialogs.export_error', default="Export Error"), f"Failed to export activity log:\n{str(e)}")
ParentPortalGUI.export_activity_log_csv = export_activity_log_csv
