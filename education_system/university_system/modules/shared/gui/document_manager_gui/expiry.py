import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import logging

try:
    from education_system.university_system.infrastructure.database.db import get_connection, transaction
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    transaction = get_connection

logger = logging.getLogger(__name__)


class ExpiryManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def display_expiry_alerts(self, parent_frame):
        """Display expiry alerts for documents"""
        try:
            ttk.Label(parent_frame, text="Document Expiry Alerts",
                     font=("Arial", 12, "bold")).pack(pady=5)

            filter_frame = ttk.Frame(parent_frame)
            filter_frame.pack(fill='x', pady=5)

            ttk.Label(filter_frame, text="Show:").pack(side='left', padx=5)
            filter_combo = ttk.Combobox(filter_frame, width=20, state='readonly')
            filter_combo['values'] = ['Expired', 'Expiring in 7 days', 'Expiring in 30 days', 'All with expiry dates']
            filter_combo.current(2)
            filter_combo.pack(side='left', padx=5)

            # Treeview
            tree_frame = ttk.Frame(parent_frame)
            tree_frame.pack(fill='both', expand=True, pady=5)

            tree = ttk.Treeview(tree_frame,
                               columns=('ID', 'Student', 'Type', 'File', 'Expiry', 'Days', 'Status'),
                               show='headings', height=15)
            tree.heading('ID', text='Doc ID')
            tree.heading('Student', text='Student ID')
            tree.heading('Type', text='Type')
            tree.heading('File', text='File Name')
            tree.heading('Expiry', text='Expiry Date')
            tree.heading('Days', text='Days Until')
            tree.heading('Status', text='Status')

            tree.column('ID', width=70)
            tree.column('Student', width=100)
            tree.column('Type', width=120)
            tree.column('File', width=180)
            tree.column('Expiry', width=100)
            tree.column('Days', width=120)
            tree.column('Status', width=100)

            scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            def load_expiry_alerts():
                """Load expiry alerts based on filter"""
                for item in tree.get_children():
                    tree.delete(item)

                filter_value = filter_combo.get()

                if filter_value == 'Expired':
                    days_filter = "AND DATE(expiry_date) < DATE('now')"
                elif filter_value == 'Expiring in 7 days':
                    days_filter = "AND DATE(expiry_date) BETWEEN DATE('now') AND DATE('now', '+7 days')"
                elif filter_value == 'Expiring in 30 days':
                    days_filter = "AND DATE(expiry_date) BETWEEN DATE('now') AND DATE('now', '+30 days')"
                else:
                    days_filter = ""

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"""
                        SELECT id, student_id, document_type, file_name, expiry_date,
                               JULIANDAY(expiry_date) - JULIANDAY('now') as days_until,
                               status
                        FROM documents
                        WHERE expiry_date IS NOT NULL
                        {days_filter}
                        ORDER BY expiry_date ASC
                        LIMIT 200
                    """)
                    results = cursor.fetchall()

                for row in results:
                    doc_id, student_id, doc_type, file_name, expiry_date, days_until, status = row
                    days_until = int(days_until)

                    # Color code based on urgency
                    if days_until < 0:
                        tag = 'expired'
                    elif days_until <= 7:
                        tag = 'urgent'
                    elif days_until <= 30:
                        tag = 'warning'
                    else:
                        tag = 'normal'

                    days_text = f"{days_until} days" if days_until >= 0 else f"{abs(days_until)} days overdue"

                    tree.insert('', 'end', values=(doc_id, student_id, doc_type, file_name,
                                                  expiry_date, days_text, status), tags=(tag,))

                # Configure tags
                tree.tag_configure('expired', background='#ffcccc')
                tree.tag_configure('urgent', background='#ffe6cc')
                tree.tag_configure('warning', background='#ffffcc')

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Bind filter change
            filter_combo.bind('<<ComboboxSelected>>', lambda e: load_expiry_alerts())

            # Initial load
            load_expiry_alerts()

            # Button frame
            button_frame = ttk.Frame(parent_frame)
            button_frame.pack(fill='x', pady=5)

            ttk.Button(button_frame, text="Send Expiry Notifications",
                      command=lambda: self.send_expiry_notifications()).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Export Expiry Report",
                      command=lambda: self.gui.export_expiry_report(tree)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Refresh",
                      command=load_expiry_alerts).pack(side='left', padx=5)

        except Exception as e:
            ttk.Label(parent_frame, text=f"Error loading expiry alerts: {e}").pack()

    def send_expiry_notifications(self):
        """Send expiry notifications to students"""
        messagebox.showinfo("Send Notifications",
                          "Expiry notifications will be sent to affected students.\n\n"
                          "This would integrate with the email service to send automated reminders.")
        self.gui.log_event('send', 'expiry_notifications',
                      details='Triggered expiry notification batch')

    def check_document_expiry(self):
        """Check document expiry status and generate report"""
        if not self.gui.ensure_login():
            return

        try:
            # Create expiry check window
            expiry_window = tk.Toplevel(self.root)
            expiry_window.title("Document Expiry Check")
            expiry_window.geometry("1100x700")
            expiry_window.transient(self.root)
            expiry_window.grab_set()

            # Title
            ttk.Label(expiry_window, text="Document Expiry Status Check",
                     font=("Arial", 14, "bold")).pack(pady=10)

            # Stats frame
            stats_frame = ttk.Frame(expiry_window)
            stats_frame.pack(fill='x', padx=10, pady=5)

            with get_connection() as conn:
                cursor = conn.cursor()

                # Expired
                cursor.execute("""
                    SELECT COUNT(*) FROM documents
                    WHERE expiry_date IS NOT NULL AND DATE(expiry_date) < DATE('now')
                """)
                expired_count = cursor.fetchone()[0]

                # Expiring soon (30 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM documents
                    WHERE expiry_date IS NOT NULL
                    AND DATE(expiry_date) BETWEEN DATE('now') AND DATE('now', '+30 days')
                """)
                expiring_soon = cursor.fetchone()[0]

                # Valid (not expiring)
                cursor.execute("""
                    SELECT COUNT(*) FROM documents
                    WHERE expiry_date IS NOT NULL AND DATE(expiry_date) > DATE('now', '+30 days')
                """)
                valid_count = cursor.fetchone()[0]

                # No expiry date
                cursor.execute("""
                    SELECT COUNT(*) FROM documents WHERE expiry_date IS NULL
                """)
                no_expiry = cursor.fetchone()[0]

            # Create stat cards
            cards = [
                ("Expired", expired_count, "#e74c3c"),
                ("Expiring Soon", expiring_soon, "#f39c12"),
                ("Valid", valid_count, "#27ae60"),
                ("No Expiry Date", no_expiry, "#95a5a6")
            ]

            for title, value, color in cards:
                card_frame = tk.Frame(stats_frame, bg=color, relief='raised', bd=2)
                card_frame.pack(side='left', fill='both', expand=True, padx=5)

                value_label = tk.Label(card_frame, text=str(value), font=("Arial", 20, "bold"),
                                      bg=color, fg='white')
                value_label.pack(pady=(10, 0))

                title_label = tk.Label(card_frame, text=title, font=("Arial", 9),
                                      bg=color, fg='white')
                title_label.pack(pady=(0, 10))

            # Documents list
            list_frame = ttk.LabelFrame(expiry_window, text="Documents with Expiry Dates", padding=10)
            list_frame.pack(fill='both', expand=True, padx=10, pady=10)

            # Filter
            filter_frame = ttk.Frame(list_frame)
            filter_frame.pack(fill='x', pady=(0, 5))

            ttk.Label(filter_frame, text="Filter:").pack(side='left', padx=5)
            filter_combo = ttk.Combobox(filter_frame, width=25, state='readonly')
            filter_combo['values'] = ['All', 'Expired Only', 'Expiring in 30 days', 'Valid']
            filter_combo.current(0)
            filter_combo.pack(side='left', padx=5)

            # Treeview
            tree = ttk.Treeview(list_frame,
                               columns=('ID', 'Student', 'Type', 'Expiry', 'Days', 'Status'),
                               show='headings', height=20)
            tree.heading('ID', text='Doc ID')
            tree.heading('Student', text='Student ID')
            tree.heading('Type', text='Document Type')
            tree.heading('Expiry', text='Expiry Date')
            tree.heading('Days', text='Days Remaining')
            tree.heading('Status', text='Status')

            tree.column('ID', width=70)
            tree.column('Student', width=100)
            tree.column('Type', width=150)
            tree.column('Expiry', width=120)
            tree.column('Days', width=120)
            tree.column('Status', width=100)

            scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)

            def load_documents():
                """Load documents based on filter"""
                for item in tree.get_children():
                    tree.delete(item)

                filter_value = filter_combo.get()

                if filter_value == 'Expired Only':
                    where_clause = "AND DATE(expiry_date) < DATE('now')"
                elif filter_value == 'Expiring in 30 days':
                    where_clause = "AND DATE(expiry_date) BETWEEN DATE('now') AND DATE('now', '+30 days')"
                elif filter_value == 'Valid':
                    where_clause = "AND DATE(expiry_date) > DATE('now', '+30 days')"
                else:
                    where_clause = ""

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"""
                        SELECT id, student_id, document_type, expiry_date,
                               JULIANDAY(expiry_date) - JULIANDAY('now') as days_remaining,
                               status
                        FROM documents
                        WHERE expiry_date IS NOT NULL
                        {where_clause}
                        ORDER BY expiry_date ASC
                        LIMIT 300
                    """)
                    results = cursor.fetchall()

                for row in results:
                    doc_id, student_id, doc_type, expiry_date, days_remaining, status = row
                    days_remaining = int(days_remaining)

                    # Determine tag
                    if days_remaining < 0:
                        tag = 'expired'
                        days_text = f"{abs(days_remaining)} days overdue"
                    elif days_remaining <= 30:
                        tag = 'warning'
                        days_text = f"{days_remaining} days left"
                    else:
                        tag = 'valid'
                        days_text = f"{days_remaining} days left"

                    tree.insert('', 'end', values=(doc_id, student_id, doc_type,
                                                  expiry_date, days_text, status), tags=(tag,))

                # Configure tags
                tree.tag_configure('expired', background='#ffcccc')
                tree.tag_configure('warning', background='#fff4cc')
                tree.tag_configure('valid', background='#ccffcc')

            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            filter_combo.bind('<<ComboboxSelected>>', lambda e: load_documents())
            load_documents()

            # Button frame
            button_frame = ttk.Frame(expiry_window)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="Export Report",
                      command=lambda: self.gui.export_expiry_report(tree)).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Refresh",
                      command=load_documents).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Close",
                      command=expiry_window.destroy).pack(side='right', padx=5)

            # Log activity
            self.gui.log_event('view', 'expiry_check', details='Performed document expiry check')

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check document expiry: {e}")

    def update_document_status(self, document_id=None):
        """Update document status with audit trail"""
        if not self.gui.ensure_login():
            return

        # Create status update window
        status_window = tk.Toplevel(self.root)
        status_window.title("Update Document Status")
        status_window.geometry("600x500")
        status_window.transient(self.root)
        status_window.grab_set()

        # Title
        ttk.Label(status_window, text="Update Document Status",
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(status_window, padding=20)
        form_frame.pack(fill='both', expand=True)

        # Document ID
        ttk.Label(form_frame, text="Document ID: *").grid(row=0, column=0, sticky='w', pady=5)
        doc_id_entry = ttk.Entry(form_frame, width=40)
        if document_id:
            doc_id_entry.insert(0, str(document_id))
        doc_id_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Current status label
        current_status_label = ttk.Label(form_frame, text="Current Status: N/A",
                                        font=("Arial", 9, "italic"))
        current_status_label.grid(row=1, column=0, columnspan=2, sticky='w', pady=5)

        # New status
        ttk.Label(form_frame, text="New Status: *").grid(row=2, column=0, sticky='w', pady=5)
        status_combo = ttk.Combobox(form_frame, width=38, state='readonly')
        status_combo['values'] = ['Pending', 'Approved', 'Rejected', 'Under Review',
                                  'Expired', 'Archived']
        status_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Reason/Notes
        ttk.Label(form_frame, text="Reason for Change: *").grid(row=3, column=0, sticky='w', pady=5)
        reason_text = tk.Text(form_frame, width=40, height=6)
        reason_text.grid(row=3, column=1, sticky='ew', pady=5)

        # Notify student
        notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Send notification to student",
                       variable=notify_var).grid(row=4, column=0, columnspan=2, sticky='w', pady=5)

        form_frame.columnconfigure(1, weight=1)

        def load_current_status():
            """Load current status of document"""
            doc_id = doc_id_entry.get()
            if not doc_id:
                return

            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT status, student_id, document_type, file_name
                        FROM documents WHERE id = ?
                    """, (doc_id,))
                    result = cursor.fetchone()

                if result:
                    status, student_id, doc_type, file_name = result
                    current_status_label.config(
                        text=f"Current Status: {status}\n"
                             f"Student: {student_id} | Type: {doc_type} | File: {file_name}"
                    )
                    return status
                else:
                    current_status_label.config(text="Document not found")
                    return None

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load document: {e}")
                return None

        def submit_status_update():
            """Submit status update"""
            doc_id = doc_id_entry.get().strip()
            new_status = status_combo.get()
            reason = reason_text.get('1.0', 'end-1c').strip()

            if not doc_id:
                messagebox.showwarning("Validation Error", "Document ID is required")
                return

            if not new_status:
                messagebox.showwarning("Validation Error", "Please select new status")
                return

            if not reason:
                messagebox.showwarning("Validation Error", "Please provide a reason for the change")
                return

            try:
                # Get current status
                current_status = load_current_status()
                if not current_status:
                    return

                if current_status == new_status:
                    messagebox.showwarning("No Change", "New status is same as current status")
                    return

                # Update status
                with transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE documents
                        SET status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (new_status, doc_id))

                messagebox.showinfo("Success",
                                  f"Document status updated successfully!\n\n"
                                  f"Document ID: {doc_id}\n"
                                  f"Old Status: {current_status}\n"
                                  f"New Status: {new_status}")

                # Log activity
                self.gui.log_event('update', 'document_status', entity_id=doc_id,
                              details=f'Status changed from {current_status} to {new_status}. Reason: {reason}')

                if notify_var.get():
                    messagebox.showinfo("Notification",
                                      "Student notification would be sent via email")

                status_window.destroy()

            except Exception as e:
                messagebox.showerror("Update Error", f"Failed to update status: {e}")

        # Load button
        ttk.Button(form_frame, text="Load Document",
                  command=load_current_status).grid(row=0, column=2, padx=5)

        # Button frame
        button_frame = ttk.Frame(status_window)
        button_frame.pack(fill='x', padx=20, pady=10)

        ttk.Button(button_frame, text="Update Status",
                  command=submit_status_update).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=status_window.destroy).pack(side='right', padx=5)
