import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import csv
import logging

from education_system.university_system.core.sql_safety import escape_like

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.database.db import get_connection
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))

try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class SearchManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def advanced_search_dialog(self):
        """Show advanced search dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Search")
        dialog.geometry("900x700")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 50))

        # Main frame
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Title
        ttk.Label(main_frame, text="Advanced Document Search", font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Search criteria frame
        criteria_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=15)
        criteria_frame.pack(fill='x', pady=(0, 15))

        # Student search
        ttk.Label(criteria_frame, text="Student (Name or ID):").grid(row=0, column=0, sticky='w', padx=5, pady=5)
        self.gui.search_student = tk.Entry(criteria_frame, width=30)
        self.gui.search_student.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # Document type
        ttk.Label(criteria_frame, text="Document Type:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        self.gui.search_doc_type = ttk.Combobox(criteria_frame, values=['All'] + self.gui.get_document_types())
        self.gui.search_doc_type.set('All')
        self.gui.search_doc_type.grid(row=1, column=1, padx=5, pady=5, sticky='ew')

        # Status
        ttk.Label(criteria_frame, text="Status:").grid(row=2, column=0, sticky='w', padx=5, pady=5)
        self.gui.search_status = ttk.Combobox(criteria_frame, values=['All', 'Pending', 'Verified', 'Rejected', 'Expired'])
        self.gui.search_status.set('All')
        self.gui.search_status.grid(row=2, column=1, padx=5, pady=5, sticky='ew')

        # Date range
        ttk.Label(criteria_frame, text="From Date:").grid(row=3, column=0, sticky='w', padx=5, pady=5)
        self.gui.search_from_date = tk.Entry(criteria_frame, width=15)
        self.gui.search_from_date.grid(row=3, column=1, padx=5, pady=5, sticky='w')

        ttk.Label(criteria_frame, text="To Date:").grid(row=4, column=0, sticky='w', padx=5, pady=5)
        self.gui.search_to_date = tk.Entry(criteria_frame, width=15)
        self.gui.search_to_date.grid(row=4, column=1, padx=5, pady=5, sticky='w')

        # Tags
        ttk.Label(criteria_frame, text="Tags:").grid(row=5, column=0, sticky='w', padx=5, pady=5)
        self.gui.search_tags = tk.Entry(criteria_frame, width=30)
        self.gui.search_tags.grid(row=5, column=1, padx=5, pady=5, sticky='ew')

        criteria_frame.grid_columnconfigure(1, weight=1)

        # Results frame
        results_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=10)
        results_frame.pack(fill='both', expand=True, pady=(0, 15))

        # Results tree
        columns = ('ID', 'Student', 'Document Type', 'Status', 'Upload Date')
        self.gui.search_results_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=10)

        for col in columns:
            self.gui.search_results_tree.heading(col, text=col)
            self.gui.search_results_tree.column(col, width=100)

        # Scrollbar for results
        results_scrollbar = ttk.Scrollbar(results_frame, orient='vertical', command=self.gui.search_results_tree.yview)
        self.gui.search_results_tree.configure(yscrollcommand=results_scrollbar.set)

        self.gui.search_results_tree.pack(side='left', fill='both', expand=True)
        results_scrollbar.pack(side='right', fill='y')

        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill='x')

        ttk.Button(buttons_frame, text="🔍 Search", command=self.perform_advanced_search).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="📊 Export Results", command=self.export_search_results_internal).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Clear", command=self.clear_search_criteria).pack(side='left', padx=5)
        ttk.Button(buttons_frame, text="Close", command=dialog.destroy).pack(side='right', padx=5)

        # Store dialog reference
        self.gui.search_dialog = dialog

    def perform_advanced_search(self):
        """Perform advanced search"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Build dynamic query
            query = '''
            SELECT sd.document_id,
                   s.first_name || ' ' || s.last_name as student_name,
                   dt.type_name,
                   sd.verification_status,
                   DATE(sd.upload_date) as upload_date
            FROM documents sd
            JOIN students s ON sd.owner_id = s.student_id
            JOIN document_types dt ON dt.type_id = CAST(sd.document_type AS INTEGER)
            WHERE sd.source_type = 'student' AND sd.is_current_version = 1
            '''

            params = []

            # Add search conditions
            if self.gui.search_student.get():
                query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.student_id LIKE ?)"
                search_term = f"%{escape_like(self.gui.search_student.get())}%"
                params.extend([search_term, search_term, search_term])

            if self.gui.search_doc_type.get() and self.gui.search_doc_type.get() != 'All':
                query += " AND dt.type_name LIKE ?"
                params.append(f"%{escape_like(self.gui.search_doc_type.get())}%")

            if self.gui.search_status.get() and self.gui.search_status.get() != 'All':
                query += " AND sd.verification_status = ?"
                params.append(self.gui.search_status.get())

            if self.gui.search_from_date.get():
                query += " AND DATE(sd.upload_date) >= ?"
                params.append(self.gui.search_from_date.get())

            if self.gui.search_to_date.get():
                query += " AND DATE(sd.upload_date) <= ?"
                params.append(self.gui.search_to_date.get())

            if self.gui.search_tags.get():
                tag_list = [tag.strip() for tag in self.gui.search_tags.get().split(',')]
                tag_conditions = []
                for tag in tag_list:
                    tag_conditions.append("sd.tags LIKE ?")
                    params.append(f"%{escape_like(tag)}%")
                query += " AND (" + " OR ".join(tag_conditions) + ")"

            query += " ORDER BY sd.upload_date DESC LIMIT 100"

            cursor.execute(query, params)
            results = cursor.fetchall()

            # Clear existing results
            for item in self.gui.search_results_tree.get_children():
                self.gui.search_results_tree.delete(item)

            # Insert new results
            for result in results:
                self.gui.search_results_tree.insert('', 'end', values=result)

            conn.close()

            # Update status
            self.gui.status_var.set(f"Search completed: {len(results)} results found")

        except Exception as e:
            messagebox.showerror("Search Error", f"Search failed: {str(e)}")

    def clear_search_criteria(self):
        """Clear all search criteria"""
        self.gui.search_student.delete(0, 'end')
        self.gui.search_doc_type.set('All')
        self.gui.search_status.set('All')
        self.gui.search_from_date.delete(0, 'end')
        self.gui.search_to_date.delete(0, 'end')
        self.gui.search_tags.delete(0, 'end')

        # Clear results
        for item in self.gui.search_results_tree.get_children():
            self.gui.search_results_tree.delete(item)

    def advanced_search(self):
        """Advanced search interface with multiple filters"""
        if not self.gui.ensure_login():
            return

        # Create advanced search window
        search_window = tk.Toplevel(self.root)
        search_window.title("Advanced Search")
        search_window.geometry("1000x750")
        search_window.transient(self.root)
        search_window.grab_set()

        # Title
        title_label = ttk.Label(search_window, text="Advanced Document Search",
                               font=("Arial", 16, "bold"))
        title_label.pack(pady=10)

        # Main container with scrollbar
        main_frame = ttk.Frame(search_window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Left frame - Search criteria
        left_frame = ttk.LabelFrame(main_frame, text="Search Criteria", padding=10)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 5))

        # Student ID
        ttk.Label(left_frame, text="Student ID:").grid(row=0, column=0, sticky='w', pady=5)
        student_id_entry = ttk.Entry(left_frame, width=30)
        student_id_entry.grid(row=0, column=1, sticky='ew', pady=5)

        # Document Type
        ttk.Label(left_frame, text="Document Type:").grid(row=1, column=0, sticky='w', pady=5)
        doc_type_combo = ttk.Combobox(left_frame, width=28, state='readonly')
        doc_type_combo['values'] = ['All Types', 'Transcript', 'ID Card', 'Health Form',
                                     'Enrollment', 'Financial', 'Other']
        doc_type_combo.current(0)
        doc_type_combo.grid(row=1, column=1, sticky='ew', pady=5)

        # Status
        ttk.Label(left_frame, text="Status:").grid(row=2, column=0, sticky='w', pady=5)
        status_combo = ttk.Combobox(left_frame, width=28, state='readonly')
        status_combo['values'] = ['All Statuses', 'Pending', 'Approved', 'Rejected', 'Expired']
        status_combo.current(0)
        status_combo.grid(row=2, column=1, sticky='ew', pady=5)

        # Date Range
        ttk.Label(left_frame, text="Upload Date From:").grid(row=3, column=0, sticky='w', pady=5)
        date_from_entry = ttk.Entry(left_frame, width=30)
        date_from_entry.insert(0, "YYYY-MM-DD")
        date_from_entry.grid(row=3, column=1, sticky='ew', pady=5)

        ttk.Label(left_frame, text="Upload Date To:").grid(row=4, column=0, sticky='w', pady=5)
        date_to_entry = ttk.Entry(left_frame, width=30)
        date_to_entry.insert(0, "YYYY-MM-DD")
        date_to_entry.grid(row=4, column=1, sticky='ew', pady=5)

        # Tags
        ttk.Label(left_frame, text="Tags (comma-separated):").grid(row=5, column=0, sticky='w', pady=5)
        tags_entry = ttk.Entry(left_frame, width=30)
        tags_entry.grid(row=5, column=1, sticky='ew', pady=5)

        # File Name
        ttk.Label(left_frame, text="File Name Contains:").grid(row=6, column=0, sticky='w', pady=5)
        filename_entry = ttk.Entry(left_frame, width=30)
        filename_entry.grid(row=6, column=1, sticky='ew', pady=5)

        # Expiry Status
        ttk.Label(left_frame, text="Expiry Status:").grid(row=7, column=0, sticky='w', pady=5)
        expiry_combo = ttk.Combobox(left_frame, width=28, state='readonly')
        expiry_combo['values'] = ['All', 'Not Expired', 'Expiring Soon (30 days)', 'Expired']
        expiry_combo.current(0)
        expiry_combo.grid(row=7, column=1, sticky='ew', pady=5)

        # Advanced options
        advanced_frame = ttk.LabelFrame(left_frame, text="Advanced Options", padding=5)
        advanced_frame.grid(row=8, column=0, columnspan=2, sticky='ew', pady=10)

        case_sensitive_var = tk.BooleanVar()
        ttk.Checkbutton(advanced_frame, text="Case Sensitive",
                       variable=case_sensitive_var).pack(anchor='w')

        include_archived_var = tk.BooleanVar()
        ttk.Checkbutton(advanced_frame, text="Include Archived Documents",
                       variable=include_archived_var).pack(anchor='w')

        exact_match_var = tk.BooleanVar()
        ttk.Checkbutton(advanced_frame, text="Exact Match Only",
                       variable=exact_match_var).pack(anchor='w')

        left_frame.columnconfigure(1, weight=1)

        # Right frame - Results
        right_frame = ttk.LabelFrame(main_frame, text="Search Results", padding=10)
        right_frame.pack(side='right', fill='both', expand=True, padx=(5, 0))

        # Results info
        results_info_label = ttk.Label(right_frame, text="No search performed yet",
                                       font=("Arial", 10))
        results_info_label.pack(pady=5)

        # Results treeview
        results_tree = ttk.Treeview(right_frame, columns=('ID', 'Student', 'Type', 'Status', 'Upload Date'),
                                    show='tree headings', height=20)
        results_tree.heading('#0', text='File Name')
        results_tree.heading('ID', text='Doc ID')
        results_tree.heading('Student', text='Student ID')
        results_tree.heading('Type', text='Type')
        results_tree.heading('Status', text='Status')
        results_tree.heading('Upload Date', text='Upload Date')

        results_tree.column('#0', width=150)
        results_tree.column('ID', width=60)
        results_tree.column('Student', width=80)
        results_tree.column('Type', width=100)
        results_tree.column('Status', width=80)
        results_tree.column('Upload Date', width=100)

        results_scrollbar = ttk.Scrollbar(right_frame, orient='vertical', command=results_tree.yview)
        results_tree.configure(yscrollcommand=results_scrollbar.set)

        results_tree.pack(side='left', fill='both', expand=True)
        results_scrollbar.pack(side='right', fill='y')

        # Button frame
        button_frame = ttk.Frame(search_window)
        button_frame.pack(fill='x', padx=10, pady=10)

        def perform_search():
            """Execute the advanced search"""
            self.execute_advanced_search(
                results_tree, results_info_label,
                student_id=student_id_entry.get(),
                doc_type=doc_type_combo.get(),
                status=status_combo.get(),
                date_from=date_from_entry.get(),
                date_to=date_to_entry.get(),
                tags=tags_entry.get(),
                filename=filename_entry.get(),
                expiry_status=expiry_combo.get(),
                case_sensitive=case_sensitive_var.get(),
                include_archived=include_archived_var.get(),
                exact_match=exact_match_var.get()
            )

        ttk.Button(button_frame, text="Search", command=perform_search).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Clear Filters",
                  command=lambda: [student_id_entry.delete(0, 'end'),
                                  doc_type_combo.current(0),
                                  status_combo.current(0),
                                  date_from_entry.delete(0, 'end'),
                                  date_from_entry.insert(0, "YYYY-MM-DD"),
                                  date_to_entry.delete(0, 'end'),
                                  date_to_entry.insert(0, "YYYY-MM-DD"),
                                  tags_entry.delete(0, 'end'),
                                  filename_entry.delete(0, 'end'),
                                  expiry_combo.current(0)]).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Export Results",
                  command=lambda: self.export_search_results(results_tree)).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Close",
                  command=search_window.destroy).pack(side='right', padx=5)

        # Log activity
        self.gui.log_event('open', 'advanced_search', details='Opened advanced search interface')

    def execute_advanced_search(self, results_tree, results_label, **filters):
        """Execute advanced search with given filters"""
        try:
            # Clear existing results
            for item in results_tree.get_children():
                results_tree.delete(item)

            # Build SQL query based on filters
            query = "SELECT id, student_id, document_type, file_name, status, upload_date FROM documents WHERE 1=1"
            params = []

            if filters.get('student_id') and filters['student_id'].strip():
                query += " AND student_id LIKE ?"
                params.append(f"%{escape_like(filters['student_id'])}%")

            if filters.get('doc_type') and filters['doc_type'] != 'All Types':
                query += " AND document_type = ?"
                params.append(filters['doc_type'])

            if filters.get('status') and filters['status'] != 'All Statuses':
                query += " AND status = ?"
                params.append(filters['status'])

            if filters.get('filename') and filters['filename'].strip():
                if filters.get('case_sensitive'):
                    query += " AND file_name LIKE ?"
                else:
                    query += " AND LOWER(file_name) LIKE LOWER(?)"
                if filters.get('exact_match'):
                    params.append(filters['filename'])
                else:
                    params.append(f"%{escape_like(filters['filename'])}%")

            # Date filters
            if filters.get('date_from') and filters['date_from'] != 'YYYY-MM-DD':
                query += " AND upload_date >= ?"
                params.append(filters['date_from'])

            if filters.get('date_to') and filters['date_to'] != 'YYYY-MM-DD':
                query += " AND upload_date <= ?"
                params.append(filters['date_to'])

            query += " ORDER BY upload_date DESC LIMIT 500"

            # Execute search
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                results = cursor.fetchall()

            # Populate results
            for row in results:
                doc_id, student_id, doc_type, file_name, status, upload_date = row
                results_tree.insert('', 'end', text=file_name,
                                  values=(doc_id, student_id, doc_type, status, upload_date))

            # Update results label
            results_label.config(text=f"Found {len(results)} document(s)")

            # Log activity
            self.gui.log_event('search', 'advanced_search',
                          details=f'Search returned {len(results)} results')

        except Exception as e:
            messagebox.showerror("Search Error", f"Failed to execute search: {e}")
            self.gui.log_event('error', 'advanced_search', details=str(e))

    def export_search_results(self, results_tree):
        """Export search results to CSV"""
        try:
            items = results_tree.get_children()
            if not items:
                messagebox.showwarning("No Results", "No search results to export")
                return

            # Ask for save location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                title="Export Search Results"
            )

            if not file_path:
                return

            # Write to CSV
            with open(file_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['File Name', 'Document ID', 'Student ID', 'Type', 'Status', 'Upload Date'])

                for item in items:
                    file_name = results_tree.item(item, 'text')
                    values = results_tree.item(item, 'values')
                    writer.writerow([file_name] + list(values))

            messagebox.showinfo("Export Successful", f"Search results exported to:\n{file_path}")
            self.gui.log_event('export', 'search_results', details=f'Exported {len(items)} results')

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export search results: {e}")

    def export_search_results_internal(self):
        """Export search results to CSV (uses self.gui.search_results_tree)"""
        try:
            if not hasattr(self.gui, 'search_results_tree'):
                messagebox.showwarning("Warning", "No search results to export")
                return

            # Get results from tree
            items = self.gui.search_results_tree.get_children()
            if not items:
                messagebox.showwarning("Warning", "No search results to export")
                return

            # Ask for save location
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )

            if not filename:
                return

            # Export to CSV
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write headers
                columns = self.gui.search_results_tree['columns']
                writer.writerow(columns)

                # Write data
                for item in items:
                    values = self.gui.search_results_tree.item(item)['values']
                    writer.writerow(values)

            messagebox.showinfo("Success", f"Search results exported to {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export search results: {e}")
