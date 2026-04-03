# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import logging

# Import utility functions
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    _safe_entry_insert,
    _safe_set_combobox,
)

# Import i18n
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import database connection
from education_system.university_system.infrastructure.database.db import get_db_connection, get_connection, transaction
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608

logger = logging.getLogger(__name__)

def show_student_records(self):
    """Show student records interface in a new window"""
    # Check if current user is a student - if so, show only their own record
    if self.auth and self.auth.current_user:
        user_role = self.auth.current_user.get('role', '')

        # If student, directly show their own record
        if user_role == 'student':
            student_id = self.auth.current_user.get('student_id') or self.auth.current_user.get('username')
            if student_id:
                print(f"✅ Student user '{student_id}' viewing their own record")
                self.show_student_details(student_id)
                return
            else:
                messagebox.showerror(_t("common.error"), _t("student.unable_retrieve_id"))
                return

    # For staff/admin: Create new window with full student list
    records_window = tk.Toplevel(self.root)
    records_window.title(_t("student.records_management"))
    records_window.geometry("1400x800")
    records_window.transient(self.root)

    # Main frame
    main_frame = ttk.Frame(records_window, padding=10)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Title
    ttk.Label(main_frame, text=_t("student.records_management"),
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Action buttons frame
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, pady=(0, 10))

    ttk.Button(button_frame, text=_t("student.create_student"),
              command=self.create_student_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("student.search_students"),
              command=self.search_students_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("student.export_data"),
              command=self.export_data_dialog).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.refresh"),
              command=lambda: self.view_students_in_window(tree)).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.close"),
              command=records_window.destroy).pack(side=tk.RIGHT, padx=5)

    # Create student list interface
    records_frame = ttk.LabelFrame(main_frame, text=_t("student.records"), padding="10")
    records_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    # Create treeview in this window
    tree_frame = ttk.Frame(records_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (_t("student.col_id"), _t("student.col_name"), _t("student.col_email"), _t("student.col_course"), _t("student.col_reg_date"))
    tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=30)

    # Configure columns
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=200)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack widgets
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Bind double-click event
    tree.bind('<Double-1>', lambda event: self.on_student_double_click_window(event, tree))

    # Store reference to this window's tree
    self.student_tree = tree

    # Load student data
    self.view_students_in_window(tree)
def create_student_treeview(self, parent):
    """Create treeview widget for displaying student data"""
    tree_frame = ttk.Frame(parent)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    columns = (_t("student.col_id"), _t("student.col_name"), _t("student.col_email"), _t("student.col_course"), _t("student.col_reg_date"))
    self.student_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=30)

    # Configure columns
    for col in columns:
        self.student_tree.heading(col, text=col)
        self.student_tree.column(col, width=150)

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.student_tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.student_tree.xview)
    self.student_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack widgets
    self.student_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Bind events
    self.student_tree.bind('<Double-1>', self.on_student_double_click)
def view_students(self):
    """Load and display student data in treeview"""
    try:
        # Check if student_tree exists and is still valid
        if not hasattr(self, 'student_tree') or not self.student_tree:
            return
        if not self.student_tree.winfo_exists():
            return

        # Clear existing data
        for item in self.student_tree.get_children():
            self.student_tree.delete(item)

        # Fetch data from database
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            if self.auth.check_permission('view_any_student'):
                cursor.execute('SELECT * FROM students ORDER BY last_name, first_name')
            else:
                cursor.execute('SELECT * FROM students WHERE student_id = ?',
                             (self.auth.current_user.get('student_id'),))

            students = cursor.fetchall()

            # Populate treeview
            for student in students:
                student_id = student[0]
                email_address = student[1]
                first_name = student[3] or ''
                middle_name = student[4] or ''
                last_name = student[5] or ''
                course = student[9]
                reg_date = student[10]
                full_name = f"{first_name} {middle_name} {last_name}".replace('  ', ' ').strip()

                self.student_tree.insert('', tk.END, values=(
                    student_id, full_name, email_address, course, reg_date[:10] if reg_date else 'N/A'
                ))

            conn.close()

    except tk.TclError:
        pass  # Widget was destroyed, ignore
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_student_data", error=str(e)))
def view_students_in_window(self, tree):
    """Load and display student data in a specific treeview widget"""
    try:
        # Check if tree widget is still valid
        if not tree.winfo_exists():
            return

        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)

        # Fetch data from database
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            select_cols = 'student_id, first_name, middle_name, last_name, email_address, course, registration_datetime'
            if self.auth.check_permission('view_any_student'):
                cursor.execute(f'SELECT {select_cols} FROM students ORDER BY last_name, first_name')
            else:
                cursor.execute(f'SELECT {select_cols} FROM students WHERE student_id = ?',
                             (self.auth.current_user.get('student_id'),))

            students = cursor.fetchall()

            # Populate treeview
            for student in students:
                student_id, first_name, middle_name, last_name, email_address, course, reg_date = student
                full_name = f"{first_name or ''} {middle_name or ''} {last_name or ''}".replace('  ', ' ').strip()

                tree.insert('', tk.END, values=(
                    student_id, full_name, email_address, course, reg_date[:10] if reg_date else 'N/A'
                ))

            conn.close()

    except tk.TclError:
        pass  # Widget was destroyed, ignore
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.failed_load_student_data", error=str(e)))
def on_student_double_click(self, event):
    """Handle double-click on student record"""
    try:
        if not hasattr(self, 'student_tree') or not self.student_tree:
            return

        selection = self.student_tree.selection()
        if selection:
            item = self.student_tree.item(selection[0])
            student_values = item.get('values', [])
            if student_values:
                student_id = student_values[0]
                self.show_student_details(student_id)
    except (AttributeError, IndexError, tk.TclError) as e:
        messagebox.showerror(_t("common.error"), _t("student.unable_access_details"))
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.error_occurred", error=str(e)))
def on_student_double_click_window(self, event, tree):
    """Handle double-click on student record in separate window"""
    try:
        selection = tree.selection()
        if selection:
            item = tree.item(selection[0])
            student_values = item.get('values', [])
            if student_values:
                student_id = student_values[0]
                self.show_student_details(student_id)
    except (AttributeError, IndexError, tk.TclError) as e:
        messagebox.showerror(_t("common.error"), _t("student.unable_access_details"))
    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student.error_occurred", error=str(e)))
def show_student_details(self, student_id):
    """Enhanced student details viewer with comprehensive information display"""
    detail_window = tk.Toplevel(self.root)
    detail_window.title(_t("student_details.window_title", student_id=student_id))
    detail_window.geometry("900x700")
    detail_window.transient(self.root)

    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror(_t("common.error"), _t("student_details.error_db_connection"))
            detail_window.destroy()
            return

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM students WHERE student_id = ?', (student_id,))
        student = cursor.fetchone()

        if not student:
            messagebox.showerror(_t("common.error"), _t("student_details.error_student_not_found"))
            detail_window.destroy()
            return

        # Create notebook for tabbed interface
        notebook = ttk.Notebook(detail_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Personal Information Tab
        personal_tab = ttk.Frame(notebook)
        notebook.add(personal_tab, text=_t("student_details.tab_personal_info"))

        personal_frame = ttk.LabelFrame(personal_tab, text=_t("student_details.student_information"), padding=20)
        personal_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create scrollable text for personal info
        personal_text = scrolledtext.ScrolledText(personal_frame, wrap=tk.WORD, height=25,
                                                 font=('Courier', 11))
        personal_text.pack(fill=tk.BOTH, expand=True)

        # Format personal information with None checks
        na = _t("student_details.na")
        title = student[2] if student[2] else na
        first_name = student[3] if student[3] else na
        middle_name = student[4] if student[4] else ''
        last_name = student[5] if student[5] else na
        gender = student[6].title() if student[6] else na
        course = student[9] if student[9] else na

        # Build full name safely
        name_parts = []
        if student[2]:  # title
            name_parts.append(student[2])
        if student[3]:  # first name
            name_parts.append(student[3])
        if student[4]:  # middle name
            name_parts.append(student[4])
        if student[5]:  # last name
            name_parts.append(student[5])
        full_name = ' '.join(name_parts) if name_parts else na

        years_text = _t("student_details.label_years")
        personal_info = f"""{_t("student_details.header_student_record")}
{'='*80}

{_t("student_details.header_personal_info")}
  {_t("student_details.label_student_id"):18}{student[0] or na}
  {_t("student_details.label_email_address"):18}{student[1] or na}
  {_t("student_details.label_title"):18}{title}
  {_t("student_details.label_first_name"):18}{first_name}
  {_t("student_details.label_middle_name"):18}{middle_name or na}
  {_t("student_details.label_last_name"):18}{last_name}
  {_t("student_details.label_full_name"):18}{full_name}

{_t("student_details.header_demographics")}
  {_t("student_details.label_gender"):18}{gender}
  {_t("student_details.label_date_of_birth"):18}{student[7] or na}
  {_t("student_details.label_age"):18}{student[8] or na} {years_text}

{_t("student_details.header_academic_info")}
  {_t("student_details.label_course"):18}{course}
  {_t("student_details.label_registration"):18}{student[10] or na}

{'='*80}
"""

        personal_text.insert(tk.END, personal_info)
        personal_text.config(state=tk.DISABLED)

        # Academic Information Tab
        academic_tab = ttk.Frame(notebook)
        notebook.add(academic_tab, text=_t("student_details.tab_academic_records"))

        # Refresh button at the top
        btn_frame = ttk.Frame(academic_tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Button(btn_frame, text=_t("common.refresh", default="Refresh"),
                   command=lambda: self._load_academic_data(student_id, academic_text, na)).pack(side=tk.RIGHT)

        academic_frame = ttk.LabelFrame(academic_tab, text=_t("student_details.modules_academic_data"), padding=20)
        academic_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        academic_text = scrolledtext.ScrolledText(academic_frame, wrap=tk.WORD, height=25,
                                                 font=('Courier', 11))
        academic_text.pack(fill=tk.BOTH, expand=True)

        self._load_academic_data(student_id, academic_text, na)

        # Actions Tab
        actions_tab = ttk.Frame(notebook)
        notebook.add(actions_tab, text=_t("student_details.tab_actions"))

        actions_frame = ttk.LabelFrame(actions_tab, text=_t("student_details.available_actions"), padding=20)
        actions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Action buttons
        if self.auth.check_permission('update_any_student'):
            ttk.Button(actions_frame, text=_t("student_details.btn_edit_student"),
                      command=lambda: self.update_student_dialog(student_id),
                      width=30).pack(pady=10)

        if self.auth.check_permission('manage_grades'):
            ttk.Button(actions_frame, text=_t("student_details.btn_manage_grades"),
                      command=lambda: self.manage_student_grades(student_id, student[3], student[5]),
                      width=30).pack(pady=5)

        # Show attendance button for staff with manage_attendance, or students viewing their own record
        own_record = self.auth.current_user and self.auth.current_user.get('student_id') == student_id
        if self.auth.check_permission('manage_attendance') or own_record:
            ttk.Button(actions_frame, text=_t("student_details.btn_view_attendance"),
                      command=lambda: self.view_student_attendance(student_id, student[1], student[3], student[5]),
                      width=30).pack(pady=5)

        # View Timetable button (available to all users)
        ttk.Button(actions_frame, text=_t("student_details.btn_view_timetable"),
                  command=lambda: self.view_student_timetable(student_id, student[3], student[5]),
                  width=30).pack(pady=5)

        if self.auth.check_permission('export_data'):
            ttk.Button(actions_frame, text=_t("student_details.btn_export_data"),
                      command=lambda: self.export_individual_student_data(student_id, student[3], student[5]),
                      width=30).pack(pady=5)

        # Contact information if available
        contact_frame = ttk.LabelFrame(actions_tab, text=_t("student_details.contact_information"), padding=20)
        contact_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Label(contact_frame, text=f"{_t('student_details.label_email')} {student[1]}").pack(anchor=tk.W)
        ttk.Button(contact_frame, text=_t("student_details.btn_send_email"),
                  command=lambda: self.send_email_to_student(student[1], student[3], student[5]),
                  width=20).pack(pady=5)

        conn.close()

    except Exception as e:
        messagebox.showerror(_t("common.error"), _t("student_details.error_load_details", error=str(e)))
        detail_window.destroy()

def _load_academic_data(self, student_id, academic_text, na):
    """Load (or refresh) academic data into the text widget."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT m.module_type, sm.module_code, m.module_name
            FROM student_modules sm
            JOIN modules m ON sm.module_code = m.module_code
            WHERE sm.student_id = ?
            ORDER BY m.module_type, sm.module_code
        ''', (student_id,))
        modules = cursor.fetchall()

        cursor.execute('''
            SELECT a.module_code, a.title as assessment_name,
                   s.grade, s.submission_date as grade_date
            FROM assignments a
            LEFT JOIN assignment_submissions s ON a.id = s.assignment_id
            WHERE s.student_id = ? AND s.grade IS NOT NULL
            UNION ALL
            SELECT a.module_code, a.assessment_name,
                   g.score as grade, g.submission_date as grade_date
            FROM assessments a
            LEFT JOIN grades g ON a.assessment_id = g.assessment_id
            WHERE g.student_id = ? AND g.score IS NOT NULL
            ORDER BY grade_date DESC
            LIMIT 20
        ''', (student_id, student_id))
        grades = cursor.fetchall()

        cursor.execute('''
            SELECT module_code, date, status, notes
            FROM attendance_records
            WHERE student_id = ?
            ORDER BY date DESC
            LIMIT 10
        ''', (student_id,))
        attendance = cursor.fetchall()

        conn.close()

        academic_info = f"""{_t("student_details.header_academic_records")}
{'='*80}

{_t("student_details.header_enrolled_modules")}
{'-'*40}
"""

        if modules:
            current_type = None
            modules_suffix = _t("student_details.modules_type_suffix")
            for module in modules:
                if current_type != module[0]:
                    current_type = module[0]
                    type_display = current_type.upper() if current_type else _t("student_details.unknown").upper()
                    academic_info += f"\n{type_display} {modules_suffix}\n"
                module_code = module[1] if module[1] else na
                module_name = module[2] if module[2] else _t("student_details.unknown_module")
                academic_info += f"  {module_code} - {module_name}\n"
        else:
            academic_info += f"  {_t('student_details.no_modules_enrolled')}\n"

        academic_info += f"\n{_t('student_details.header_grades_assessments')}\n{'-'*40}\n"
        if grades:
            for grade in grades:
                module_code = grade[0] if grade[0] else na
                assessment_name = grade[1] if grade[1] else _t("student_details.unknown_assessment")
                grade_value = grade[2] if grade[2] else _t("student_details.no_grade")
                grade_date = grade[3] if grade[3] else _t("student_details.unknown_date")
                academic_info += f"  {module_code} - {assessment_name}: {grade_value} ({_t('student_details.label_date')} {grade_date})\n"
        else:
            academic_info += f"  {_t('student_details.no_grades_recorded')}\n"

        academic_info += f"\n{_t('student_details.header_recent_attendance')}\n{'-'*40}\n"
        if attendance:
            for att in attendance:
                module_code = att[0] if att[0] else na
                att_date = att[1] if att[1] else _t("student_details.unknown_date")
                status = att[2] if att[2] else _t("student_details.unknown")
                reason_text = f" - {att[3]}" if att[3] else ""
                academic_info += f"  {att_date} ({module_code}): {status}{reason_text}\n"
        else:
            academic_info += f"  {_t('student_details.no_attendance_records')}\n"

        academic_info += f"\n{'='*80}"

        academic_text.config(state=tk.NORMAL)
        academic_text.delete('1.0', tk.END)
        academic_text.insert(tk.END, academic_info)
        academic_text.config(state=tk.DISABLED)

    except Exception as e:
        academic_text.config(state=tk.NORMAL)
        academic_text.delete('1.0', tk.END)
        academic_text.insert(tk.END, f"Error loading academic data: {e}")
        academic_text.config(state=tk.DISABLED)

def search_students_dialog(self):
    """Create search dialog"""
    dialog = self.create_themed_toplevel(_t("student.search_students"), "400x300")
    dialog.grab_set()

    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    # Search criteria
    ttk.Label(main_frame, text=_t("student.search_by")).grid(row=0, column=0, sticky=tk.W, pady=5)
    search_type = ttk.Combobox(main_frame, values=[
        _t("student.first_name"), _t("student.last_name"), _t("student.student_id"), _t("student.col_course"), _t("common.email")
    ], state='readonly', width=25)
    search_type.grid(row=0, column=1, pady=5, padx=(10, 0))
    search_type.set(_t("student.first_name"))

    ttk.Label(main_frame, text=_t("student.search_term")).grid(row=1, column=0, sticky=tk.W, pady=5)
    search_term = ttk.Entry(main_frame, width=28)
    search_term.grid(row=1, column=1, pady=5, padx=(10, 0))

    def perform_search():
        """Perform search and update treeview"""
        term = search_term.get().strip()
        if not term:
            messagebox.showerror(_t("common.error"), _t("student.enter_search_term"))
            return

        try:
            # Check if student_tree exists
            if not hasattr(self, 'student_tree') or not self.student_tree:
                # Offer to open Student Records window
                if messagebox.askyesno(_t("student.open_records_title"),
                                      _t("student.open_records_msg")):
                    dialog.destroy()
                    self.show_student_records()
                return

            # Clear existing data
            for item in self.student_tree.get_children():
                self.student_tree.delete(item)

            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Build query based on search type
                search_field_map = {
                    _t("student.first_name"): 'first_name',
                    _t("student.last_name"): 'last_name',
                    _t("student.student_id"): 'student_id',
                    _t("student.col_course"): 'course',
                    _t("common.email"): 'email_address'
                }

                field = search_field_map.get(search_type.get(), 'first_name')

                safe_field = validate_identifier(field, "column")
                if field == 'student_id':
                    query = 'SELECT * FROM students WHERE [' + safe_field + '] = ?'
                    cursor.execute(query, (term,))
                else:
                    query = 'SELECT * FROM students WHERE LOWER([' + safe_field + ']) LIKE LOWER(?)'
                    cursor.execute(query, (f'%{term}%',))

                results = cursor.fetchall()

                # Populate treeview with results
                for student in results:
                    student_id = student[0]
                    email_address = student[1]
                    first_name = student[3] or ''
                    middle_name = student[4] or ''
                    last_name = student[5] or ''
                    course = student[9]
                    reg_date = student[10]
                    full_name = f"{first_name} {middle_name} {last_name}".replace('  ', ' ').strip()

                    self.student_tree.insert('', tk.END, values=(
                        student_id, full_name, email_address, course, reg_date[:10] if reg_date else 'N/A'
                    ))

                conn.close()

                if not results:
                    messagebox.showinfo(_t("student.search_students"), _t("student.no_results"))
                else:
                    messagebox.showinfo(_t("student.search_students"), _t("student.found_results").replace("{count}", str(len(results))))

                dialog.destroy()

        except Exception as e:
            messagebox.showerror(_t("common.error"), f"Search failed: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.grid(row=2, column=0, columnspan=2, pady=20)

    def show_all_and_close():
        """Show all students and close search dialog"""
        try:
            if hasattr(self, 'student_tree') and self.student_tree:
                self.view_students()
            dialog.destroy()
        except Exception as e:
            print(f"Error showing all students: {e}")
            dialog.destroy()

    ttk.Button(button_frame, text=_t("common.search"), command=perform_search).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("gui.show_all"), command=show_all_and_close).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_t("common.cancel"), command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    search_term.focus()
