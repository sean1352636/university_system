import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

try:
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.infrastructure.auth import get_current_user
except ImportError:
    from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH
    def get_connection():
        return sqlite3.connect(str(DEFAULT_DB_PATH))
    def get_current_user():
        return {'username': 'admin', 'role': 'admin'}

try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key if "default" not in kwargs else kwargs.get("default")


class HelperManager:
    def __init__(self, gui):
        self.gui = gui
        self.root = gui.root

    def return_to_main_menu(self):
        """Return to the main menu"""
        try:
            # Use the gui_launcher utility to avoid circular imports
            from education_system.university_system.modules.shared.gui.gui_launcher import return_to_main_menu
            return_to_main_menu(self.gui, getattr(self.gui, 'auth', None))
        except Exception as e:
            print(f"Error returning to main menu: {e}")
            import traceback
            traceback.print_exc()

    def log_event(self, action, entity_type, entity_id=None, details=None):
        """
        Log an event/activity to the database

        Args:
            action: Action performed (e.g., 'create', 'update', 'delete', 'view')
            entity_type: Type of entity (e.g., 'document', 'student', 'workflow')
            entity_id: ID of the entity (optional)
            details: Additional details as string or dict (optional)
        """
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get current user info
            username = self.gui.current_user.get('username', 'Unknown') if self.gui.current_user else 'Unknown'
            user_id = self.gui.current_user.get('id', None) if self.gui.current_user else None
            user_role = self.gui.current_user.get('role', 'user') if self.gui.current_user else 'user'

            # Pack role, entity_type, and entity_id into the details JSON
            detail_parts = {}
            if user_role:
                detail_parts['user_role'] = user_role
            if entity_type:
                detail_parts['entity_type'] = entity_type
            if entity_id:
                detail_parts['entity_id'] = entity_id
            if isinstance(details, dict):
                detail_parts.update(details)
            elif details:
                detail_parts['message'] = str(details)
            details_str = json.dumps(detail_parts) if detail_parts else None

            # Use the existing activity_log schema: user_id, username, action, details, timestamp
            cursor.execute('''
                INSERT INTO activity_log (user_id, username, action, details, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, action, details_str, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error logging event: {e}")

    def check_authentication(self):
        """
        Check if user is properly authenticated

        Returns:
            bool: True if authenticated, False otherwise
        """
        try:
            if not self.gui.current_user:
                return False

            # Check if user has required fields
            if not isinstance(self.gui.current_user, dict):
                return False

            if 'username' not in self.gui.current_user or not self.gui.current_user['username']:
                return False

            # If we have a valid current_user with username, consider authenticated
            # This handles both real auth system and standalone/fallback mode
            return True

        except Exception as e:
            print(f"Error checking authentication: {e}")
            return False

    def select_student(self, title="Select Student", allow_search=True):
        """
        Show a dialog to select a student

        Args:
            title: Dialog title
            allow_search: Whether to allow searching for students

        Returns:
            dict: Student info dict with keys: student_id, first_name, last_name, email
                  or None if cancelled
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'selected': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Search frame (if enabled)
            if allow_search:
                search_frame = ttk.Frame(main_frame)
                search_frame.pack(fill='x', pady=(0, 10))

                ttk.Label(search_frame, text="Search:").pack(side='left', padx=(0, 5))
                search_var = tk.StringVar()
                search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
                search_entry.pack(side='left', padx=(0, 5))

            # Student list frame
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            # Listbox with scrollbar
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side='right', fill='y')

            student_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10),
                                         yscrollcommand=scrollbar.set)
            student_listbox.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=student_listbox.yview)

            # Load students
            students = self.gui.get_students_list()
            student_data = []

            for student in students:
                student_id, first_name, last_name = student[0], student[1], student[2]
                display_text = f"{student_id} - {last_name}, {first_name}"
                student_listbox.insert(tk.END, display_text)
                student_data.append({
                    'student_id': student_id,
                    'first_name': first_name,
                    'last_name': last_name
                })

            # Search functionality
            if allow_search:
                def filter_students(*args):
                    search_text = search_var.get().lower()
                    student_listbox.delete(0, tk.END)
                    for i, student in enumerate(students):
                        student_id, first_name, last_name = student[0], student[1], student[2]
                        display_text = f"{student_id} - {last_name}, {first_name}"
                        if search_text in display_text.lower():
                            student_listbox.insert(tk.END, display_text)

                search_var.trace('w', filter_students)

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(20, 0))

            def on_select():
                selection = student_listbox.curselection()
                if selection:
                    index = selection[0]
                    # Find the corresponding student from filtered list
                    selected_text = student_listbox.get(index)
                    student_id = selected_text.split(' - ')[0]

                    # Find full student info
                    for student in student_data:
                        if student['student_id'] == student_id:
                            result['selected'] = student
                            break

                    dialog.destroy()
                else:
                    messagebox.showwarning("Warning", "Please select a student")

            def on_cancel():
                dialog.destroy()

            ttk.Button(button_frame, text="Select", command=on_select).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            # Double-click to select
            student_listbox.bind('<Double-Button-1>', lambda e: on_select())

            dialog.wait_window()
            return result['selected']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show student selection: {e}")
            return None

    def select_document_type(self, title="Select Document Type", show_details=True):
        """
        Show a dialog to select a document type

        Args:
            title: Dialog title
            show_details: Whether to show document type details

        Returns:
            dict: Document type info dict with keys: type_id, type_name, description, etc.
                  or None if cancelled
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title(title)
            dialog.geometry("700x600")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'selected': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text=title, font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Document type list frame
            list_frame = ttk.Frame(main_frame)
            list_frame.pack(fill='both', expand=True)

            # Listbox with scrollbar
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side='right', fill='y')

            doctype_listbox = tk.Listbox(list_frame, height=15, font=('Arial', 10),
                                         yscrollcommand=scrollbar.set)
            doctype_listbox.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=doctype_listbox.yview)

            # Load document types
            doc_types = self.gui.get_document_types_with_details()
            doc_type_data = []

            for doc_type in doc_types:
                type_id, type_name, description = doc_type[0], doc_type[1], doc_type[2]
                display_text = f"{type_name}"
                if show_details and description:
                    display_text += f" - {description[:50]}"
                doctype_listbox.insert(tk.END, display_text)

                doc_type_data.append({
                    'type_id': type_id,
                    'type_name': type_name,
                    'description': description,
                    'is_required': doc_type[3] if len(doc_type) > 3 else False,
                    'has_expiry': doc_type[4] if len(doc_type) > 4 else False,
                    'expiry_reminder_days': doc_type[5] if len(doc_type) > 5 else None,
                    'max_file_size_mb': doc_type[6] if len(doc_type) > 6 else 10,
                    'allowed_formats': doc_type[7] if len(doc_type) > 7 else None
                })

            # Details frame
            if show_details:
                details_frame = ttk.LabelFrame(main_frame, text="Document Type Details", padding=10)
                details_frame.pack(fill='x', pady=(10, 0))

                details_text = tk.Text(details_frame, height=6, wrap=tk.WORD, font=('Arial', 9))
                details_text.pack(fill='x')
                details_text.config(state='disabled')

                def on_selection_change(event):
                    selection = doctype_listbox.curselection()
                    if selection:
                        index = selection[0]
                        doc_type = doc_type_data[index]

                        details_text.config(state='normal')
                        details_text.delete('1.0', tk.END)
                        details_text.insert('1.0', f"Type: {doc_type['type_name']}\n")
                        details_text.insert(tk.END, f"Description: {doc_type['description']}\n")
                        details_text.insert(tk.END, f"Required: {'Yes' if doc_type['is_required'] else 'No'}\n")
                        details_text.insert(tk.END, f"Has Expiry: {'Yes' if doc_type['has_expiry'] else 'No'}\n")
                        details_text.insert(tk.END, f"Max Size: {doc_type['max_file_size_mb']}MB\n")
                        details_text.insert(tk.END, f"Formats: {doc_type['allowed_formats']}\n")
                        details_text.config(state='disabled')

                doctype_listbox.bind('<<ListboxSelect>>', on_selection_change)

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(20, 0))

            def on_select():
                selection = doctype_listbox.curselection()
                if selection:
                    index = selection[0]
                    result['selected'] = doc_type_data[index]
                    dialog.destroy()
                else:
                    messagebox.showwarning("Warning", "Please select a document type")

            def on_cancel():
                dialog.destroy()

            ttk.Button(button_frame, text="Select", command=on_select).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            # Double-click to select
            doctype_listbox.bind('<Double-Button-1>', lambda e: on_select())

            dialog.wait_window()
            return result['selected']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show document type selection: {e}")
            return None

    def get_file_upload_details(self, initial_path=None):
        """
        Get file upload details through file dialog

        Args:
            initial_path: Initial directory path (optional)

        Returns:
            dict: File details with keys: file_path, file_name, file_size, file_size_mb,
                  file_extension, is_valid
                  or None if cancelled
        """
        try:
            # Open file dialog
            file_path = filedialog.askopenfilename(
                title="Select Document File",
                initialdir=initial_path,
                filetypes=[
                    ("All Supported", "*.pdf *.jpg *.jpeg *.png *.doc *.docx *.txt"),
                    ("PDF files", "*.pdf"),
                    ("Image files", "*.jpg *.jpeg *.png"),
                    ("Word documents", "*.doc *.docx"),
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ]
            )

            if not file_path:
                return None

            # Get file details
            if not os.path.exists(file_path):
                messagebox.showerror("Error", "Selected file does not exist")
                return None

            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            file_extension = os.path.splitext(file_path)[1][1:].lower()

            # Validate file size (max 50MB by default)
            is_valid = file_size_mb <= 50

            return {
                'file_path': file_path,
                'file_name': file_name,
                'file_size': file_size,
                'file_size_mb': round(file_size_mb, 2),
                'file_extension': file_extension,
                'is_valid': is_valid
            }

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get file details: {e}")
            return None

    def get_expiry_date(self, doc_type_info=None, allow_manual=True):
        """
        Get or calculate expiry date for a document

        Args:
            doc_type_info: Document type info dict with expiry settings (optional)
            allow_manual: Whether to allow manual date entry

        Returns:
            str: Expiry date in YYYY-MM-DD format or None if not applicable
        """
        try:
            # Check if document type has expiry
            has_expiry = False
            default_days = 365

            if doc_type_info:
                has_expiry = doc_type_info.get('has_expiry', False)
                if doc_type_info.get('expiry_reminder_days'):
                    default_days = doc_type_info['expiry_reminder_days']

            if not has_expiry and not allow_manual:
                return None

            # Show dialog to get expiry date
            dialog = tk.Toplevel(self.root)
            dialog.title("Set Expiry Date")
            dialog.geometry("450x300")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'date': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Set Document Expiry Date",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Options frame
            options_frame = ttk.Frame(main_frame)
            options_frame.pack(fill='both', expand=True)

            # Radio buttons for selection method
            selection_method = tk.StringVar(value='calculated')

            ttk.Radiobutton(options_frame, text="Calculate from today",
                           variable=selection_method, value='calculated').pack(anchor='w', pady=5)

            # Days frame
            days_frame = ttk.Frame(options_frame)
            days_frame.pack(fill='x', padx=(20, 0), pady=5)

            ttk.Label(days_frame, text="Days from today:").pack(side='left')
            days_var = tk.StringVar(value=str(default_days))
            days_entry = ttk.Entry(days_frame, textvariable=days_var, width=10)
            days_entry.pack(side='left', padx=5)

            if allow_manual:
                ttk.Radiobutton(options_frame, text="Enter specific date",
                               variable=selection_method, value='manual').pack(anchor='w', pady=5)

                # Manual date frame
                manual_frame = ttk.Frame(options_frame)
                manual_frame.pack(fill='x', padx=(20, 0), pady=5)

                ttk.Label(manual_frame, text="Date (YYYY-MM-DD):").pack(side='left')
                date_var = tk.StringVar()
                date_entry = ttk.Entry(manual_frame, textvariable=date_var, width=15)
                date_entry.pack(side='left', padx=5)

                # Set default to 1 year from now
                default_date = (datetime.now() + timedelta(days=default_days)).strftime('%Y-%m-%d')
                date_var.set(default_date)

            ttk.Radiobutton(options_frame, text="No expiry date",
                           variable=selection_method, value='none').pack(anchor='w', pady=5)

            # Preview
            preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding=10)
            preview_frame.pack(fill='x', pady=(20, 10))

            preview_label = ttk.Label(preview_frame, text="", font=('Arial', 10, 'bold'))
            preview_label.pack()

            def update_preview(*args):
                method = selection_method.get()
                if method == 'calculated':
                    try:
                        days = int(days_var.get())
                        expiry = datetime.now() + timedelta(days=days)
                        preview_label.config(text=f"Expiry Date: {expiry.strftime('%Y-%m-%d')}")
                    except (ValueError, TypeError):
                        preview_label.config(text="Invalid number of days")
                elif method == 'manual' and allow_manual:
                    date_text = date_var.get()
                    try:
                        datetime.strptime(date_text, '%Y-%m-%d')
                        preview_label.config(text=f"Expiry Date: {date_text}")
                    except ValueError:
                        preview_label.config(text="Invalid date format")
                else:
                    preview_label.config(text="No expiry date")

            selection_method.trace('w', update_preview)
            days_var.trace('w', update_preview)
            if allow_manual:
                date_var.trace('w', update_preview)

            update_preview()

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(10, 0))

            def on_confirm():
                method = selection_method.get()
                if method == 'calculated':
                    try:
                        days = int(days_var.get())
                        expiry = datetime.now() + timedelta(days=days)
                        result['date'] = expiry.strftime('%Y-%m-%d')
                        dialog.destroy()
                    except Exception:
                        messagebox.showerror("Error", "Invalid number of days")
                elif method == 'manual' and allow_manual:
                    date_text = date_var.get()
                    try:
                        datetime.strptime(date_text, '%Y-%m-%d')
                        result['date'] = date_text
                        dialog.destroy()
                    except Exception:
                        messagebox.showerror("Error", "Invalid date format (use YYYY-MM-DD)")
                else:
                    result['date'] = None
                    dialog.destroy()

            def on_cancel():
                result['date'] = None
                dialog.destroy()

            ttk.Button(button_frame, text="Confirm", command=on_confirm).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            dialog.wait_window()
            return result['date']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get expiry date: {e}")
            return None

    def select_tags(self, existing_tags=None, allow_create=True):
        """
        Show a dialog to select or create tags

        Args:
            existing_tags: List of existing tag names (optional)
            allow_create: Whether to allow creating new tags

        Returns:
            list: List of selected tag names or None if cancelled
        """
        try:
            dialog = tk.Toplevel(self.root)
            dialog.title("Select Tags")
            dialog.geometry("600x500")
            dialog.transient(self.root)
            dialog.grab_set()

            result = {'tags': None}

            # Main frame
            main_frame = ttk.Frame(dialog, padding=20)
            main_frame.pack(fill='both', expand=True)

            # Title
            ttk.Label(main_frame, text="Select or Create Tags",
                     font=('Arial', 14, 'bold')).pack(pady=(0, 20))

            # Load existing tags from database
            try:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT tag_name FROM document_tags ORDER BY tag_name')
                db_tags = [row[0] for row in cursor.fetchall()]
                conn.close()
            except Exception:
                db_tags = []

            # Combine with provided tags
            if existing_tags:
                all_tags = list(set(db_tags + existing_tags))
            else:
                all_tags = db_tags

            all_tags.sort()

            # Available tags frame
            available_frame = ttk.LabelFrame(main_frame, text="Available Tags", padding=10)
            available_frame.pack(fill='both', expand=True, pady=(0, 10))

            # Listbox for available tags
            available_list = tk.Listbox(available_frame, height=10, selectmode='multiple',
                                       font=('Arial', 10))
            available_list.pack(side='left', fill='both', expand=True)

            scrollbar = ttk.Scrollbar(available_frame, orient='vertical',
                                     command=available_list.yview)
            scrollbar.pack(side='right', fill='y')
            available_list.config(yscrollcommand=scrollbar.set)

            # Populate tags
            for tag in all_tags:
                available_list.insert(tk.END, tag)

            # New tag frame
            if allow_create:
                new_tag_frame = ttk.LabelFrame(main_frame, text="Create New Tag", padding=10)
                new_tag_frame.pack(fill='x', pady=(0, 10))

                ttk.Label(new_tag_frame, text="Tag Name:").pack(side='left', padx=(0, 5))
                new_tag_var = tk.StringVar()
                new_tag_entry = ttk.Entry(new_tag_frame, textvariable=new_tag_var, width=30)
                new_tag_entry.pack(side='left', padx=(0, 5))

                def add_new_tag():
                    tag_name = new_tag_var.get().strip()
                    if tag_name:
                        if tag_name not in available_list.get(0, tk.END):
                            available_list.insert(tk.END, tag_name)
                            available_list.selection_set(tk.END)
                            new_tag_var.set('')
                        else:
                            messagebox.showinfo("Info", "Tag already exists")
                    else:
                        messagebox.showwarning("Warning", "Please enter a tag name")

                ttk.Button(new_tag_frame, text="Add", command=add_new_tag).pack(side='left')

            # Selected tags display
            selected_frame = ttk.LabelFrame(main_frame, text="Selected Tags", padding=10)
            selected_frame.pack(fill='x')

            selected_label = ttk.Label(selected_frame, text="None selected",
                                      font=('Arial', 9), foreground='gray')
            selected_label.pack()

            def update_selected_display(*args):
                selection = available_list.curselection()
                if selection:
                    selected_tags = [available_list.get(i) for i in selection]
                    selected_label.config(text=', '.join(selected_tags), foreground='black')
                else:
                    selected_label.config(text="None selected", foreground='gray')

            available_list.bind('<<ListboxSelect>>', update_selected_display)

            # Button frame
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=(20, 0))

            def on_confirm():
                selection = available_list.curselection()
                if selection:
                    result['tags'] = [available_list.get(i) for i in selection]
                else:
                    result['tags'] = []
                dialog.destroy()

            def on_cancel():
                result['tags'] = None
                dialog.destroy()

            ttk.Button(button_frame, text="Confirm", command=on_confirm).pack(side='left', padx=5)
            ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side='left', padx=5)

            dialog.wait_window()
            return result['tags']

        except Exception as e:
            messagebox.showerror("Error", f"Failed to show tag selection: {e}")
            return None

    def show_user_guide(self):
        """Show comprehensive user guide"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title("User Guide - Document Management System")
        guide_window.geometry("800x600")
        guide_window.transient(self.root)

        main_frame = ttk.Frame(guide_window, padding=20)
        main_frame.pack(fill='both', expand=True)

        # Create notebook for different guide sections
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Getting Started Tab
        getting_started_frame = ttk.Frame(notebook, padding=15)
        notebook.add(getting_started_frame, text="Getting Started")

        getting_started_text = """GETTING STARTED WITH DOCUMENT MANAGEMENT SYSTEM

    Welcome to the Enhanced Document Management System! This guide will help you navigate and use all the features effectively.

    MAIN DASHBOARD:
    - View system statistics and recent activity
    - Quick access to pending documents and alerts
    - Real-time compliance monitoring

    NAVIGATION:
    - Use the sidebar menu to access different sections
    - Dashboard: System overview and statistics
    - Documents: Manage and view all documents
    - Students: Student information and records
    - Reports: Generate various reports
    - Workflows: Manage document approval processes
    - Search: Advanced search functionality
    - OCR: Text extraction from documents
    - Settings: System configuration

    QUICK ACTIONS:
    - Upload Document: Add new student documents
    - Bulk Operations: Perform actions on multiple documents
    - Process Workflow: Handle document approvals
    - Generate Report: Create compliance and status reports
    - Backup System: Create system backups"""

        getting_started_widget = tk.Text(getting_started_frame, wrap='word', height=20, width=70)
        getting_started_widget.insert('1.0', getting_started_text)
        getting_started_widget.config(state='disabled')
        getting_started_widget.pack(fill='both', expand=True)

        # Document Management Tab
        doc_mgmt_frame = ttk.Frame(notebook, padding=15)
        notebook.add(doc_mgmt_frame, text="Document Management")

        doc_mgmt_text = """DOCUMENT MANAGEMENT

    UPLOADING DOCUMENTS:
    1. Click "Upload Document" from the sidebar or main menu
    2. Select the student from the dropdown or search
    3. Choose the document type from the categorized list
    4. Browse and select the file to upload
    5. Set expiry date if applicable
    6. Add tags and notes as needed
    7. Click "Upload Document" to submit

    VIEWING DOCUMENTS:
    - Go to Documents section to see all documents
    - Use filters to narrow down results by status, type, or date
    - Double-click any document to view detailed information
    - Right-click for context menu with additional options

    DOCUMENT STATUSES:
    - Pending: Awaiting verification
    - Verified: Approved and accepted
    - Rejected: Requires attention or resubmission
    - Expired: Past expiry date

    DOCUMENT VERSIONS:
    - System maintains version history
    - Upload new version to replace existing document
    - View all versions from document details
    - Restore previous versions if needed

    BULK OPERATIONS:
    - Select multiple documents for batch operations
    - Update status for multiple documents at once
    - Apply tags to multiple documents
    - Generate bulk reports"""

        doc_mgmt_widget = tk.Text(doc_mgmt_frame, wrap='word', height=20, width=70)
        doc_mgmt_widget.insert('1.0', doc_mgmt_text)
        doc_mgmt_widget.config(state='disabled')
        doc_mgmt_widget.pack(fill='both', expand=True)

        # Workflows Tab
        workflows_frame = ttk.Frame(notebook, padding=15)
        notebook.add(workflows_frame, text="Workflows")

        workflows_text = """WORKFLOW MANAGEMENT

    UNDERSTANDING WORKFLOWS:
    - Workflows automate document approval processes
    - Each document type can have custom workflow steps
    - Steps can be assigned to different users or roles
    - Track progress through each workflow stage

    PROCESSING WORKFLOWS:
    1. Go to Workflows section
    2. View active workflows in the list
    3. Select a workflow step to process
    4. Choose action: Approve, Reject, or Request Info
    5. Add comments explaining the decision
    6. Submit to move to next step or complete workflow

    WORKFLOW STATUSES:
    - Pending: Awaiting action
    - Completed: Successfully processed
    - Rejected: Stopped due to rejection

    WORKFLOW TEMPLATES:
    - Standard Review: 3-step approval process
    - Express: Fast-track for urgent documents
    - Multi-stage: Complex approval with multiple departments
    - Custom: Build your own workflow steps

    WORKFLOW ANALYTICS:
    - Track average processing times
    - Identify bottlenecks
    - Monitor user performance
    - Generate workflow reports"""

        workflows_widget = tk.Text(workflows_frame, wrap='word', height=20, width=70)
        workflows_widget.insert('1.0', workflows_text)
        workflows_widget.config(state='disabled')
        workflows_widget.pack(fill='both', expand=True)

        # Reports Tab
        reports_frame = ttk.Frame(notebook, padding=15)
        notebook.add(reports_frame, text="Reports")

        reports_text = """REPORTING SYSTEM

    STANDARD REPORTS:
    - Compliance Report: Student document compliance overview
    - Status Report: Document status distribution
    - Expiry Report: Documents expiring soon
    - Student Progress: Individual student progress tracking
    - Monthly Summary: Monthly activity overview

    CUSTOM REPORTS:
    - Use the Custom Report Builder for flexible reporting
    - Select data fields to include
    - Apply filters by date, status, course, etc.
    - Export results to CSV, Excel, or PDF

    GENERATING REPORTS:
    1. Go to Reports section
    2. Select report type
    3. Set filters and parameters
    4. Choose output format
    5. Generate and download report

    REPORT SCHEDULING:
    - Set up automated report generation
    - Email reports to stakeholders
    - Schedule daily, weekly, or monthly reports

    ANALYTICS DASHBOARD:
    - Real-time system metrics
    - Visual charts and graphs
    - Trend analysis
    - Performance indicators"""

        reports_widget = tk.Text(reports_frame, wrap='word', height=20, width=70)
        reports_widget.insert('1.0', reports_text)
        reports_widget.config(state='disabled')
        reports_widget.pack(fill='both', expand=True)

        # Troubleshooting Tab
        troubleshooting_frame = ttk.Frame(notebook, padding=15)
        notebook.add(troubleshooting_frame, text="Troubleshooting")

        troubleshooting_text = """TROUBLESHOOTING & FAQ

    COMMON ISSUES:

    Q: Document upload fails
    A: Check file size (must be under limit), file format (must be allowed), and ensure student exists in system

    Q: Cannot find student
    A: Use the search function, check spelling, or add the student if they don't exist

    Q: Workflow stuck in pending
    A: Check if assigned user has permissions, verify workflow step configuration

    Q: Reports not generating
    A: Verify date ranges, check filter criteria, ensure data exists for selected parameters

    Q: Cannot access certain features
    A: Check user role permissions, contact administrator for access rights

    SYSTEM REQUIREMENTS:
    - Modern web browser (Chrome, Firefox, Safari, Edge)
    - Stable internet connection
    - JavaScript enabled
    - Minimum screen resolution: 1024x768

    BACKUP AND RECOVERY:
    - System automatically creates daily backups
    - Manual backup available in Settings
    - Contact administrator for data recovery

    SUPPORT CONTACT:
    - Email: support@yourschool.edu
    - Phone: (555) 123-4567
    - Help Desk: Available 8 AM - 5 PM EST

    KEYBOARD SHORTCUTS:
    - Ctrl+U: Upload Document
    - Ctrl+S: Advanced Search
    - Ctrl+R: Refresh Current View
    - F1: Show this User Guide"""

        troubleshooting_widget = tk.Text(troubleshooting_frame, wrap='word', height=20, width=70)
        troubleshooting_widget.insert('1.0', troubleshooting_text)
        troubleshooting_widget.config(state='disabled')
        troubleshooting_widget.pack(fill='both', expand=True)

        # Close button
        ttk.Button(main_frame, text="Close Guide", command=guide_window.destroy).pack()

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About",
            "Enhanced Document Management System v2.0\n\n"
            "A comprehensive document management solution for educational institutions.\n\n"
            "Features:\n"
            "• Document upload and management\n"
            "• Student record tracking\n"
            "• Compliance monitoring\n"
            "• Reporting and analytics\n"
            "• User management\n"
            "• Automated workflows")
