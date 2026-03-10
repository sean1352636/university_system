import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.university_system.infrastructure.database.db import transaction
except ImportError:
    pass

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
    )
    I18N_AVAILABLE = True
except ImportError:
    I18N_AVAILABLE = False
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")
    get_current_language = lambda: "en"


class StudentPortalManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def view_my_documents(self, student_id=None):
        """
        Student view of their own documents
        """
        try:
            if not student_id:
                student_id = self.gui.current_user.get('username', '') if self.gui.current_user else ''

            dialog = tk.Toplevel(self.root)
            dialog.title("My Documents")
            dialog.geometry("1100x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="My Documents",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary cards
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total documents
                cursor.execute('SELECT COUNT(*) FROM student_documents WHERE student_id = ?', (student_id,))
                total = cursor.fetchone()[0]

                # Pending
                cursor.execute("SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND status = 'pending'", (student_id,))
                pending = cursor.fetchone()[0]

                # Approved
                cursor.execute("SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND status = 'approved'", (student_id,))
                approved = cursor.fetchone()[0]

                # Current versions
                cursor.execute('SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND is_current_version = 1', (student_id,))
                current = cursor.fetchone()[0]

                conn.close()

                self.gui.create_stat_card(summary_frame, "Total Documents", total, '#3498db', 0)
                self.gui.create_stat_card(summary_frame, "Pending", pending, '#f39c12', 1)
                self.gui.create_stat_card(summary_frame, "Approved", approved, '#27ae60', 2)
                self.gui.create_stat_card(summary_frame, "Current Versions", current, '#9b59b6', 3)

            except Exception as e:
                pass

            # Documents list
            docs_frame = ttk.LabelFrame(main_frame, text="My Document List", padding=10)
            docs_frame.pack(fill='both', expand=True)

            columns = ('Document Type', 'Upload Date', 'Status', 'Version', 'File Name', 'Notes')
            docs_tree = ttk.Treeview(docs_frame, columns=columns, show='headings', height=15)

            for col in columns:
                docs_tree.heading(col, text=col)
                if col == 'Version':
                    docs_tree.column(col, width=60)
                elif col == 'Status':
                    docs_tree.column(col, width=80)
                else:
                    docs_tree.column(col, width=150)

            scrollbar = ttk.Scrollbar(docs_frame, orient='vertical', command=docs_tree.yview)
            docs_tree.configure(yscrollcommand=scrollbar.set)
            docs_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load documents
            def load_documents():
                docs_tree.delete(*docs_tree.get_children())
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    SELECT dt.type_name, sd.upload_date, sd.verification_status, sd.version_number,
                           sd.original_filename, sd.verification_notes
                    FROM student_documents sd
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    WHERE sd.student_id = ? AND sd.is_current_version = 1
                    ORDER BY sd.upload_date DESC
                    ''', (student_id,))

                    docs = cursor.fetchall()
                    conn.close()

                    for doc in docs:
                        docs_tree.insert('', 'end', values=doc)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load documents: {e}")

            load_documents()

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            ttk.Button(action_frame, text="Upload New Document",
                      command=lambda: self.student_upload_document(student_id)).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Refresh", command=load_documents).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open my documents: {e}")

    def student_upload_document(self, student_id=None):
        """
        Student document upload interface
        """
        try:
            if not student_id:
                student_id = self.gui.current_user.get('username', '') if self.gui.current_user else ''

            dialog = tk.Toplevel(self.root)
            dialog.title("Upload Document")
            dialog.geometry("700x650")
            dialog.transient(self.root)
            dialog.grab_set()

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Upload New Document",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Document type
            type_frame = ttk.LabelFrame(main_frame, text="Document Type", padding=10)
            type_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(type_frame, text="Select Document Type:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            doc_type_combo = ttk.Combobox(type_frame, width=40, state='readonly')
            doc_type_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            # Load document types
            doc_types = self.gui.get_document_types_with_details()
            doc_type_combo['values'] = [f"{dt[1]}" for dt in doc_types]

            type_frame.grid_columnconfigure(1, weight=1)

            # File selection
            file_frame = ttk.LabelFrame(main_frame, text="Select File", padding=10)
            file_frame.pack(fill='x', pady=(0, 15))

            file_path_var = tk.StringVar()
            ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky='w', padx=5, pady=5)
            ttk.Entry(file_frame, textvariable=file_path_var, width=40, state='readonly').grid(row=0, column=1, padx=5, pady=5, sticky='ew')

            def browse_file():
                file_path = filedialog.askopenfilename(
                    title="Select Document",
                    filetypes=[
                        ("PDF files", "*.pdf"),
                        ("Image files", "*.jpg;*.jpeg;*.png"),
                        ("Word documents", "*.doc;*.docx"),
                        ("All files", "*.*")
                    ]
                )
                if file_path:
                    file_path_var.set(file_path)
                    # Show file info
                    size = os.path.getsize(file_path) / (1024 * 1024)
                    file_info_label.config(text=f"Size: {size:.2f} MB")

            ttk.Button(file_frame, text="Browse...", command=browse_file).grid(row=0, column=2, padx=5, pady=5)

            file_info_label = ttk.Label(file_frame, text="", font=('Arial', 9), foreground='gray')
            file_info_label.grid(row=1, column=0, columnspan=3, sticky='w', padx=5)

            file_frame.grid_columnconfigure(1, weight=1)

            # Notes
            notes_frame = ttk.LabelFrame(main_frame, text="Notes (Optional)", padding=10)
            notes_frame.pack(fill='both', expand=True, pady=(0, 15))

            notes_text = tk.Text(notes_frame, height=6, wrap=tk.WORD)
            notes_text.pack(fill='both', expand=True)

            # Upload info
            info_frame = ttk.Frame(main_frame)
            info_frame.pack(fill='x', pady=(0, 15))

            ttk.Label(info_frame, text="Your document will be reviewed by staff",
                     font=('Arial', 9), foreground='blue').pack()

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x')

            def perform_upload():
                doc_type = doc_type_combo.get()
                file_path = file_path_var.get()

                if not doc_type:
                    messagebox.showerror("Error", "Please select document type")
                    return

                if not file_path:
                    messagebox.showerror("Error", "Please select a file")
                    return

                try:
                    # Get type_id
                    type_id = None
                    for dt in doc_types:
                        if dt[1] == doc_type:
                            type_id = dt[0]
                            break

                    if not type_id:
                        messagebox.showerror("Error", "Invalid document type")
                        return

                    # Upload document
                    notes = notes_text.get('1.0', tk.END).strip()
                    result = self.gui.upload_document_to_db(student_id, type_id, file_path, None, '', notes)

                    if result:
                        messagebox.showinfo("Success",
                                          "Document uploaded successfully!\n"
                                          "It will be reviewed by staff shortly.")
                        dialog.destroy()
                    else:
                        messagebox.showerror("Error", "Failed to upload document")

                except Exception as e:
                    messagebox.showerror("Error", f"Upload failed: {e}")

            ttk.Button(action_frame, text="Upload Document", command=perform_upload).pack(side='right', padx=5)
            ttk.Button(action_frame, text="Cancel", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open upload dialog: {e}")

    def student_dashboard(self, student_id=None):
        """
        Comprehensive student dashboard
        """
        try:
            if not student_id:
                student_id = self.gui.current_user.get('username', '') if self.gui.current_user else ''

            dialog = tk.Toplevel(self.root)
            dialog.title("Student Dashboard")
            dialog.geometry("1200x800")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title with student name
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT first_name, last_name, course FROM students WHERE student_id = ?', (student_id,))
                student_info = cursor.fetchone()
                conn.close()

                if student_info:
                    title_text = f"Dashboard - {student_info[0]} {student_info[1]} ({student_info[2]})"
                else:
                    title_text = "Student Dashboard"
            except Exception:
                title_text = "Student Dashboard"

            ttk.Label(main_frame, text=title_text,
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Quick stats
            stats_frame = ttk.Frame(main_frame)
            stats_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Documents
                cursor.execute('SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND is_current_version = 1', (student_id,))
                doc_count = cursor.fetchone()[0]

                # Pending approvals
                cursor.execute("SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND status = 'pending'", (student_id,))
                pending_count = cursor.fetchone()[0]

                # Notifications
                cursor.execute('SELECT COUNT(*) FROM notifications WHERE recipient_id = ? AND is_read = 0', (student_id,))
                notif_count = cursor.fetchone()[0]

                # Missing required docs
                cursor.execute('''
                SELECT COUNT(*) FROM document_types dt
                WHERE dt.is_required = 1
                AND NOT EXISTS (
                    SELECT 1 FROM student_documents sd
                    WHERE sd.student_id = ? AND sd.type_id = dt.type_id
                )
                ''', (student_id,))
                missing_count = cursor.fetchone()[0]

                conn.close()

                self.gui.create_stat_card(stats_frame, "My Documents", doc_count, '#3498db', 0)
                self.gui.create_stat_card(stats_frame, "Pending Approval", pending_count, '#f39c12', 1)
                self.gui.create_stat_card(stats_frame, "Unread Notices", notif_count, '#e74c3c', 2)
                self.gui.create_stat_card(stats_frame, "Missing Required", missing_count, '#e67e22', 3)

            except Exception as e:
                pass

            # Notebook with tabs
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill='both', expand=True)

            # Tab 1: Recent Documents
            docs_tab = ttk.Frame(notebook, padding=10)
            notebook.add(docs_tab, text="Recent Documents")

            columns = ('Type', 'Upload Date', 'Status', 'Version')
            docs_tree = ttk.Treeview(docs_tab, columns=columns, show='headings', height=15)
            for col in columns:
                docs_tree.heading(col, text=col)
                docs_tree.column(col, width=150)
            docs_tree.pack(fill='both', expand=True)

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT dt.type_name, sd.upload_date, sd.verification_status, sd.version_number
                FROM student_documents sd
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE sd.student_id = ? AND sd.is_current_version = 1
                ORDER BY sd.upload_date DESC
                LIMIT 20
                ''', (student_id,))
                docs = cursor.fetchall()
                conn.close()
                for doc in docs:
                    docs_tree.insert('', 'end', values=doc)
            except Exception:
                pass

            # Tab 2: Requirements
            req_tab = ttk.Frame(notebook, padding=10)
            notebook.add(req_tab, text="Requirements")

            ttk.Label(req_tab, text="Required Documents Status", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

            req_tree = ttk.Treeview(req_tab, columns=('Document', 'Status'), show='headings', height=15)
            req_tree.heading('Document', text='Document Type')
            req_tree.heading('Status', text='Status')
            req_tree.column('Document', width=300)
            req_tree.column('Status', width=150)
            req_tree.pack(fill='both', expand=True)

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT type_name FROM document_types WHERE is_required = 1')
                required = cursor.fetchall()

                for req in required:
                    cursor.execute('''
                    SELECT COUNT(*) FROM student_documents
                    WHERE student_id = ? AND type_id = (
                        SELECT type_id FROM document_types WHERE type_name = ?
                    )
                    ''', (student_id, req[0]))
                    has_doc = cursor.fetchone()[0] > 0
                    status = "Submitted" if has_doc else "Missing"
                    req_tree.insert('', 'end', values=(req[0], status))

                conn.close()
            except Exception:
                pass

            # Tab 3: Notifications
            notif_tab = ttk.Frame(notebook, padding=10)
            notebook.add(notif_tab, text="Notifications")

            notif_tree = ttk.Treeview(notif_tab, columns=('Date', 'Title', 'Message'), show='headings', height=15)
            notif_tree.heading('Date', text='Date')
            notif_tree.heading('Title', text='Title')
            notif_tree.heading('Message', text='Message')
            notif_tree.column('Date', width=150)
            notif_tree.column('Title', width=200)
            notif_tree.column('Message', width=400)
            notif_tree.pack(fill='both', expand=True)

            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT created_date, title, message
                FROM notifications
                WHERE recipient_id = ?
                ORDER BY created_date DESC
                LIMIT 50
                ''', (student_id,))
                notifs = cursor.fetchall()
                conn.close()
                for notif in notifs:
                    notif_tree.insert('', 'end', values=notif)
            except Exception:
                pass

            # Quick action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            ttk.Button(action_frame, text="Upload Document",
                      command=lambda: self.student_upload_document(student_id)).pack(side='left', padx=5)
            ttk.Button(action_frame, text="View All Documents",
                      command=lambda: self.view_my_documents(student_id)).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Check Requirements",
                      command=lambda: self.check_my_requirements(student_id)).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open dashboard: {e}")

    def check_my_requirements(self, student_id=None):
        """
        Check document requirements for student
        """
        try:
            if not student_id:
                student_id = self.gui.current_user.get('username', '') if self.gui.current_user else ''

            dialog = tk.Toplevel(self.root)
            dialog.title("My Requirements")
            dialog.geometry("900x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Document Requirements Check",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Total required
                cursor.execute('SELECT COUNT(*) FROM document_types WHERE is_required = 1')
                total_required = cursor.fetchone()[0]

                # Submitted
                cursor.execute('''
                SELECT COUNT(DISTINCT sd.type_id)
                FROM student_documents sd
                JOIN document_types dt ON sd.type_id = dt.type_id
                WHERE sd.student_id = ? AND dt.is_required = 1
                ''', (student_id,))
                submitted = cursor.fetchone()[0]

                # Missing
                missing = total_required - submitted

                # Compliance percentage
                compliance = round((submitted / total_required * 100) if total_required > 0 else 0, 1)

                conn.close()

                self.gui.create_stat_card(summary_frame, "Total Required", total_required, '#3498db', 0)
                self.gui.create_stat_card(summary_frame, "Submitted", submitted, '#27ae60', 1)
                self.gui.create_stat_card(summary_frame, "Missing", missing, '#e74c3c', 2)
                self.gui.create_stat_card(summary_frame, f"Compliance", f"{compliance}%", '#9b59b6', 3)

            except Exception as e:
                pass

            # Requirements list
            req_frame = ttk.LabelFrame(main_frame, text="Requirements Details", padding=10)
            req_frame.pack(fill='both', expand=True)

            columns = ('Document Type', 'Status', 'Last Upload', 'Expiry Date', 'Actions')
            req_tree = ttk.Treeview(req_frame, columns=columns, show='headings', height=15)

            for col in columns:
                req_tree.heading(col, text=col)
                if col == 'Status':
                    req_tree.column(col, width=100)
                elif col == 'Actions':
                    req_tree.column(col, width=80)
                else:
                    req_tree.column(col, width=150)

            scrollbar = ttk.Scrollbar(req_frame, orient='vertical', command=req_tree.yview)
            req_tree.configure(yscrollcommand=scrollbar.set)
            req_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load requirements
            try:
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute('SELECT type_id, type_name FROM document_types WHERE is_required = 1 ORDER BY type_name')
                required_types = cursor.fetchall()

                for type_id, type_name in required_types:
                    cursor.execute('''
                    SELECT upload_date, expiry_date, status
                    FROM student_documents
                    WHERE student_id = ? AND type_id = ? AND is_current_version = 1
                    ORDER BY upload_date DESC
                    LIMIT 1
                    ''', (student_id, type_id))
                    doc = cursor.fetchone()

                    if doc:
                        upload_date, expiry_date, status = doc
                        status_text = f"Submitted ({status.title()})"
                        action = "Update"
                    else:
                        upload_date = "Not uploaded"
                        expiry_date = "-"
                        status_text = "Missing"
                        action = "Upload"

                    req_tree.insert('', 'end', values=(
                        type_name,
                        status_text,
                        upload_date,
                        expiry_date or "-",
                        action
                    ))

                conn.close()
            except Exception as e:
                pass

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            ttk.Button(action_frame, text="Upload Document",
                      command=lambda: self.student_upload_document(student_id)).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Export Report",
                      command=lambda: self.gui.generate_student_progress_report()).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to check requirements: {e}")

    def my_document_status(self, student_id=None):
        """
        Track document processing status
        """
        try:
            if not student_id:
                student_id = self.gui.current_user.get('username', '') if self.gui.current_user else ''

            dialog = tk.Toplevel(self.root)
            dialog.title("Document Status Tracker")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="My Document Status Tracker",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Status summary
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Status counts
                cursor.execute("SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND status = 'pending'", (student_id,))
                pending = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND status = 'approved'", (student_id,))
                approved = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND status = 'rejected'", (student_id,))
                rejected = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM student_documents WHERE student_id = ? AND status = 'verified'", (student_id,))
                verified = cursor.fetchone()[0]

                conn.close()

                self.gui.create_stat_card(summary_frame, "Pending Review", pending, '#f39c12', 0)
                self.gui.create_stat_card(summary_frame, "Approved", approved, '#27ae60', 1)
                self.gui.create_stat_card(summary_frame, "Rejected", rejected, '#e74c3c', 2)
                self.gui.create_stat_card(summary_frame, "Verified", verified, '#3498db', 3)

            except Exception:
                pass

            # Document status list
            status_frame = ttk.LabelFrame(main_frame, text="Document Status Details", padding=10)
            status_frame.pack(fill='both', expand=True)

            columns = ('Document Type', 'Upload Date', 'Current Status', 'Last Updated', 'Reviewer Notes')
            status_tree = ttk.Treeview(status_frame, columns=columns, show='headings', height=15)

            for col in columns:
                status_tree.heading(col, text=col)
                if col == 'Current Status':
                    status_tree.column(col, width=100)
                else:
                    status_tree.column(col, width=150)

            scrollbar = ttk.Scrollbar(status_frame, orient='vertical', command=status_tree.yview)
            status_tree.configure(yscrollcommand=scrollbar.set)
            status_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load status data
            def load_status():
                status_tree.delete(*status_tree.get_children())
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    SELECT dt.type_name, sd.upload_date, sd.verification_status,
                           sd.verification_date, sd.verification_notes
                    FROM student_documents sd
                    JOIN document_types dt ON sd.type_id = dt.type_id
                    WHERE sd.student_id = ? AND sd.is_current_version = 1
                    ORDER BY sd.upload_date DESC
                    ''', (student_id,))

                    docs = cursor.fetchall()
                    conn.close()

                    for doc in docs:
                        status_tree.insert('', 'end', values=doc)

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load status: {e}")

            load_status()

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            ttk.Button(action_frame, text="Refresh", command=load_status).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open status tracker: {e}")

    def my_notifications(self, student_id=None):
        """
        View student notifications
        """
        try:
            if not student_id:
                student_id = self.gui.current_user.get('username', '') if self.gui.current_user else ''

            dialog = tk.Toplevel(self.root)
            dialog.title("My Notifications")
            dialog.geometry("1000x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="My Notifications",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Summary
            summary_frame = ttk.Frame(main_frame)
            summary_frame.pack(fill='x', pady=(0, 20))

            try:
                conn = get_connection()
                cursor = conn.cursor()

                # Unread
                cursor.execute('SELECT COUNT(*) FROM notifications WHERE recipient_id = ? AND is_read = 0', (student_id,))
                unread = cursor.fetchone()[0]

                # Total
                cursor.execute('SELECT COUNT(*) FROM notifications WHERE recipient_id = ?', (student_id,))
                total = cursor.fetchone()[0]

                # High priority
                cursor.execute("SELECT COUNT(*) FROM notifications WHERE recipient_id = ? AND priority = 'high'", (student_id,))
                high_priority = cursor.fetchone()[0]

                conn.close()

                self.gui.create_stat_card(summary_frame, "Unread", unread, '#e74c3c', 0)
                self.gui.create_stat_card(summary_frame, "Total Notifications", total, '#3498db', 1)
                self.gui.create_stat_card(summary_frame, "High Priority", high_priority, '#f39c12', 2)

            except Exception:
                pass

            # Notifications list
            notif_frame = ttk.LabelFrame(main_frame, text="Notifications", padding=10)
            notif_frame.pack(fill='both', expand=True)

            columns = ('Status', 'Date', 'Priority', 'Title', 'Message')
            notif_tree = ttk.Treeview(notif_frame, columns=columns, show='headings', height=15)

            for col in columns:
                notif_tree.heading(col, text=col)
                if col == 'Status':
                    notif_tree.column(col, width=70)
                elif col == 'Priority':
                    notif_tree.column(col, width=80)
                elif col == 'Date':
                    notif_tree.column(col, width=150)
                else:
                    notif_tree.column(col, width=200)

            scrollbar = ttk.Scrollbar(notif_frame, orient='vertical', command=notif_tree.yview)
            notif_tree.configure(yscrollcommand=scrollbar.set)
            notif_tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')

            # Load notifications
            def load_notifications():
                notif_tree.delete(*notif_tree.get_children())
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    cursor.execute('''
                    SELECT notification_id, is_read, created_date, priority, title, message
                    FROM notifications
                    WHERE recipient_id = ?
                    ORDER BY created_date DESC
                    LIMIT 100
                    ''', (student_id,))

                    notifs = cursor.fetchall()
                    conn.close()

                    for notif in notifs:
                        notif_id, is_read, created_date, priority, title, message = notif
                        read_status = "Read" if is_read else "Unread"
                        # Truncate message for display
                        short_message = message[:100] + "..." if len(message) > 100 else message
                        notif_tree.insert('', 'end', values=(
                            read_status, created_date, priority or 'normal', title, short_message
                        ), tags=(notif_id,))

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load notifications: {e}")

            load_notifications()

            def mark_as_read():
                selection = notif_tree.selection()
                if not selection:
                    messagebox.showwarning("Warning", "Please select a notification")
                    return

                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    for item in selection:
                        notif_id = notif_tree.item(item)['tags'][0]
                        cursor.execute('UPDATE notifications SET is_read = 1 WHERE notification_id = ?', (notif_id,))

                    conn.commit()
                    conn.close()

                    messagebox.showinfo("Success", f"Marked {len(selection)} notification(s) as read")
                    load_notifications()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to mark as read: {e}")

            # Action buttons
            action_frame = ttk.Frame(main_frame)
            action_frame.pack(fill='x', pady=(20, 0))

            ttk.Button(action_frame, text="Mark as Read", command=mark_as_read).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Refresh", command=load_notifications).pack(side='left', padx=5)
            ttk.Button(action_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

            load_notifications()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open notifications: {e}")

    def display_admin_menu(self):
        """
        Display admin menu with all administrative options
        """
        try:
            # Check if user is admin
            if not self.gui.ensure_login('admin'):
                return

            dialog = tk.Toplevel(self.root)
            dialog.title("Administrator Menu")
            dialog.geometry("1000x800")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            admin_name = self.gui.current_user.get('username', 'Administrator') if self.gui.current_user else 'Administrator'
            ttk.Label(main_frame, text=f"Administrator Menu - {admin_name}",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Create notebook with tabs
            notebook = ttk.Notebook(main_frame)
            notebook.pack(fill='both', expand=True, pady=(0, 15))

            # Tab 1: Document Management
            doc_tab = ttk.Frame(notebook, padding=15)
            notebook.add(doc_tab, text="Document Management")

            doc_buttons = [
                ("Upload Document", self.gui.upload_document_dialog),
                ("View All Documents", self.gui.view_all_documents),
                ("Verify Documents", self.gui.verify_documents),
                ("Approve/Reject Documents", self.gui.approve_reject_documents),
                ("Archive Old Versions", self.gui.archive_old_versions),
                ("Document Versioning Menu", self.gui.document_versioning_menu),
            ]

            for text, command in doc_buttons:
                ttk.Button(doc_tab, text=text, command=command, width=35).pack(pady=5)

            # Tab 2: User Management
            user_tab = ttk.Frame(notebook, padding=15)
            notebook.add(user_tab, text="User Management")

            user_buttons = [
                ("Manage Students", lambda: messagebox.showinfo("Info", "Student management feature")),
                ("Manage Staff", lambda: messagebox.showinfo("Info", "Staff management feature")),
                ("View Access Logs", self.gui.view_access_logs),
                ("Security Settings", self.gui.security_settings),
            ]

            for text, command in user_buttons:
                ttk.Button(user_tab, text=text, command=command, width=35).pack(pady=5)

            # Tab 3: Workflows & Notifications
            workflow_tab = ttk.Frame(notebook, padding=15)
            notebook.add(workflow_tab, text="Workflows & Notifications")

            workflow_buttons = [
                ("Create Custom Workflow", self.gui.create_custom_workflow),
                ("Workflow Templates", self.gui.workflow_templates),
                ("Workflow Analytics", self.gui.workflow_analytics),
                ("View Pending Notifications", self.gui.view_pending_notifications),
                ("Email Settings", self.gui.email_settings),
                ("Email Configuration", self.gui.email_configuration),
            ]

            for text, command in workflow_buttons:
                ttk.Button(workflow_tab, text=text, command=command, width=35).pack(pady=5)

            # Tab 4: Reports & Analytics
            reports_tab = ttk.Frame(notebook, padding=15)
            notebook.add(reports_tab, text="Reports & Analytics")

            reports_buttons = [
                ("Generate Reports", self.gui.generate_reports_menu),
                ("Custom Report Builder", self.gui.custom_report_builder),
                ("Version Analytics", self.gui.version_analytics),
                ("Template Analytics", self.gui.template_analytics),
                ("Export Data", self.gui.export_data_menu),
            ]

            for text, command in reports_buttons:
                ttk.Button(reports_tab, text=text, command=command, width=35).pack(pady=5)

            # Tab 5: System Management
            system_tab = ttk.Frame(notebook, padding=15)
            notebook.add(system_tab, text="System Management")

            system_buttons = [
                ("View Current Settings", self.gui.view_current_settings),
                ("Database Migrations", self.gui.migrate_tables),
                ("Create Backup", self.gui.create_full_backup),
                ("Backup Settings", self.gui.backup_settings),
                ("Restore from Backup", self.gui.restore_from_backup),
                ("OCR Settings", self.gui.ocr_settings),
                ("Bulk Operations", self.gui.bulk_operations_menu),
            ]

            for text, command in system_buttons:
                ttk.Button(system_tab, text=text, command=command, width=35).pack(pady=5)

            # Tab 6: Advanced
            advanced_tab = ttk.Frame(notebook, padding=15)
            notebook.add(advanced_tab, text="Advanced")

            advanced_buttons = [
                ("API Server Menu", self.gui.api_server_menu),
                ("Web Interface Menu", self.gui.web_interface_menu),
                ("Set Course Requirements", self.gui.set_course_requirements),
                ("Batch OCR Processing", self.gui.batch_ocr_processing),
                ("View OCR Results", self.gui.view_ocr_results),
            ]

            for text, command in advanced_buttons:
                ttk.Button(advanced_tab, text=text, command=command, width=35).pack(pady=5)

            # Close button
            ttk.Button(main_frame, text="Close Menu", command=dialog.destroy).pack(pady=10)

            self.gui.log_event('access', 'admin_menu', None, {'user': admin_name})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open admin menu: {e}")

    def display_student_menu(self):
        """
        Display student menu with student-specific options
        """
        try:
            # Check if user is logged in
            if not self.gui.ensure_login():
                return

            dialog = tk.Toplevel(self.root)
            dialog.title("Student Menu")
            dialog.geometry("700x700")
            dialog.transient(self.root)

            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            student_name = self.gui.current_user.get('username', 'Student') if self.gui.current_user else 'Student'
            ttk.Label(main_frame, text=f"Student Menu - {student_name}",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Welcome message
            welcome_frame = ttk.Frame(main_frame)
            welcome_frame.pack(fill='x', pady=(0, 20))

            ttk.Label(welcome_frame, text="Welcome to the Document Management System",
                     font=('Arial', 11)).pack()
            ttk.Label(welcome_frame, text="Select an option below to manage your documents",
                     font=('Arial', 9), foreground='gray').pack()

            # My Documents section
            docs_frame = ttk.LabelFrame(main_frame, text="My Documents", padding=15)
            docs_frame.pack(fill='x', pady=(0, 15))

            docs_buttons = [
                ("Student Dashboard", self.student_dashboard),
                ("View My Documents", self.view_my_documents),
                ("Upload Document", self.student_upload_document),
                ("Check Requirements", self.check_my_requirements),
                ("Document Status", self.my_document_status),
            ]

            for text, command in docs_buttons:
                ttk.Button(docs_frame, text=text, command=lambda c=command: c(student_name), width=40).pack(pady=5)

            # Notifications section
            notif_frame = ttk.LabelFrame(main_frame, text="Notifications & Help", padding=15)
            notif_frame.pack(fill='x', pady=(0, 15))

            notif_buttons = [
                ("My Notifications", lambda: self.my_notifications(student_name)),
                ("Help & Support", lambda: messagebox.showinfo("Help", "Contact support: support@university.edu")),
            ]

            for text, command in notif_buttons:
                ttk.Button(notif_frame, text=text, command=command, width=40).pack(pady=5)

            # Close button
            ttk.Button(main_frame, text="Close Menu", command=dialog.destroy).pack(pady=10)

            self.gui.log_event('access', 'student_menu', None, {'user': student_name})

        except Exception as e:
            messagebox.showerror("Error", f"Failed to open student menu: {e}")

    def handle_admin_choice(self, choice):
        """
        Handle admin menu choice

        Args:
            choice: Menu choice identifier (string)
        """
        try:
            # Ensure admin access
            if not self.gui.ensure_login('admin'):
                return

            # Map choices to methods
            admin_actions = {
                'upload_document': self.gui.upload_document_dialog,
                'view_all_documents': self.gui.view_all_documents,
                'verify_documents': self.gui.verify_documents,
                'approve_reject': self.gui.approve_reject_documents,
                'archive_versions': self.gui.archive_old_versions,
                'create_workflow': self.gui.create_custom_workflow,
                'workflow_templates': self.gui.workflow_templates,
                'workflow_analytics': self.gui.workflow_analytics,
                'pending_notifications': self.gui.view_pending_notifications,
                'email_settings': self.gui.email_settings,
                'email_config': self.gui.email_configuration,
                'generate_reports': self.gui.generate_reports_menu,
                'custom_reports': self.gui.custom_report_builder,
                'version_analytics': self.gui.version_analytics,
                'template_analytics': self.gui.template_analytics,
                'export_data': self.gui.export_data_menu,
                'view_settings': self.gui.view_current_settings,
                'migrations': self.gui.migrate_tables,
                'create_backup': self.gui.create_full_backup,
                'backup_settings': self.gui.backup_settings,
                'restore_backup': self.gui.restore_from_backup,
                'ocr_settings': self.gui.ocr_settings,
                'bulk_operations': self.gui.bulk_operations_menu,
                'api_server': self.gui.api_server_menu,
                'web_interface': self.gui.web_interface_menu,
                'course_requirements': self.gui.set_course_requirements,
                'batch_ocr': self.gui.batch_ocr_processing,
                'ocr_results': self.gui.view_ocr_results,
                'access_logs': self.gui.view_access_logs,
                'security_settings': self.gui.security_settings,
                'document_versioning': self.gui.document_versioning_menu,
            }

            # Execute the chosen action
            if choice in admin_actions:
                self.gui.log_event('admin_action', 'menu_choice', None, {'choice': choice})
                admin_actions[choice]()
            else:
                messagebox.showwarning("Unknown Choice", f"Action '{choice}' not found")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to handle admin choice: {e}")

    def handle_student_choice(self, choice):
        """
        Handle student menu choice

        Args:
            choice: Menu choice identifier (string)
        """
        try:
            # Ensure student is logged in
            if not self.gui.ensure_login():
                return

            student_id = self.gui.current_user.get('username', '') if self.gui.current_user else ''

            # Map choices to methods
            student_actions = {
                'dashboard': lambda: self.student_dashboard(student_id),
                'view_documents': lambda: self.view_my_documents(student_id),
                'upload_document': lambda: self.student_upload_document(student_id),
                'check_requirements': lambda: self.check_my_requirements(student_id),
                'document_status': lambda: self.my_document_status(student_id),
                'notifications': lambda: self.my_notifications(student_id),
                'help': lambda: messagebox.showinfo("Help", "Contact support: support@university.edu"),
            }

            # Execute the chosen action
            if choice in student_actions:
                self.gui.log_event('student_action', 'menu_choice', None, {
                    'choice': choice,
                    'student_id': student_id
                })
                student_actions[choice]()
            else:
                messagebox.showwarning("Unknown Choice", f"Action '{choice}' not found")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to handle student choice: {e}")
