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

    # Right-click cross-jumps to every module keyed by student_id.
    # The student record is the canonical hub — for the first time this
    # tree points outward (Email Manager, Finance, Library, Audit Log,
    # Loyalty / Careers snapshots, Course Mgmt) instead of just being
    # the destination everything else jumps to.
    try:
        from education_system.university_system.modules.shared.gui.main.students._cross_links import (
            attach_cross_link_menu,
        )
        attach_cross_link_menu(tree, parent=records_window)
    except Exception:
        logger.debug("student records cross-link menu unavailable", exc_info=True)

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
    """Enhanced student details viewer with comprehensive information display.

    Writes a GDPR-relevant audit entry naming the viewer + the subject
    student before opening the window, so every read of a student
    record is auditable. The write is best-effort — a transient audit
    DB failure won't block the viewer from rendering, but a sustained
    gap shows up as missing rows in the audit log itself which is a
    different (and detectable) compliance signal."""
    try:
        from education_system.university_system.modules.shared.gui.main.students._cross_links import (
            audit_student_view,
        )
        viewer = self.auth.current_user if self.auth else None
        if viewer:
            audit_student_view(
                viewer.get('id'),
                viewer.get('username'),
                student_id,
            )
    except Exception:
        logger.debug("student view audit hook failed", exc_info=True)

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

        # ── Personal info tab: structured cards instead of monospaced blob ──
        na = _t("student_details.na")
        title = student[2] if student[2] else na
        first_name = student[3] if student[3] else na
        middle_name = student[4] if student[4] else ''
        last_name = student[5] if student[5] else na
        gender = student[6].title() if student[6] else na
        course = student[9] if student[9] else na

        name_parts = [p for p in (student[2], student[3], student[4], student[5]) if p]
        full_name = ' '.join(name_parts) if name_parts else na

        # Hero header
        hero = ttk.Frame(personal_tab, padding=(20, 14))
        hero.pack(fill=tk.X, padx=10, pady=(10, 0))
        ttk.Label(hero, text=full_name, font=('Arial', 18, 'bold')).pack(anchor='w')
        sub_bits = []
        if student[0]:
            sub_bits.append(f"ID: {student[0]}")
        if course not in (na, ''):
            sub_bits.append(course)
        if student[1]:
            sub_bits.append(student[1])
        if sub_bits:
            ttk.Label(hero, text=' · '.join(sub_bits),
                      font=('Arial', 10), foreground='#555555').pack(anchor='w', pady=(2, 0))
        ttk.Separator(personal_tab, orient='horizontal').pack(fill=tk.X, padx=10, pady=(8, 4))

        # Scrollable container for the cards (works on small windows)
        canvas = tk.Canvas(personal_tab, borderwidth=0, highlightthickness=0)
        vbar = ttk.Scrollbar(personal_tab, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side='left', fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        vbar.pack(side='right', fill='y', pady=(0, 10))

        cards = ttk.Frame(canvas)
        cards_window = canvas.create_window((0, 0), window=cards, anchor='nw')

        def _on_inner(_event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas(event):
            canvas.itemconfigure(cards_window, width=event.width)

        cards.bind('<Configure>', _on_inner)
        canvas.bind('<Configure>', _on_canvas)

        def _add_field(parent, row, label, value):
            ttk.Label(parent, text=label, font=('Arial', 10, 'bold'),
                      foreground='#333333').grid(row=row, column=0, sticky='w', padx=(0, 16), pady=3)
            ttk.Label(parent, text=str(value), font=('Arial', 10)).grid(
                row=row, column=1, sticky='w', pady=3,
            )

        # Card 1 — Identity
        identity = ttk.LabelFrame(cards, text=_t("student_details.header_personal_info"),
                                  padding=15)
        identity.pack(fill=tk.X, pady=6)
        identity.columnconfigure(1, weight=1)
        years_text = _t("student_details.label_years")
        _add_field(identity, 0, _t("student_details.label_student_id"), student[0] or na)
        _add_field(identity, 1, _t("student_details.label_email_address"), student[1] or na)
        _add_field(identity, 2, _t("student_details.label_title"), title)
        _add_field(identity, 3, _t("student_details.label_first_name"), first_name)
        _add_field(identity, 4, _t("student_details.label_middle_name"), middle_name or na)
        _add_field(identity, 5, _t("student_details.label_last_name"), last_name)
        _add_field(identity, 6, _t("student_details.label_full_name"), full_name)

        # Card 2 — Demographics
        demographics = ttk.LabelFrame(cards, text=_t("student_details.header_demographics"),
                                      padding=15)
        demographics.pack(fill=tk.X, pady=6)
        demographics.columnconfigure(1, weight=1)
        age_value = (
            f"{student[8]} {years_text}" if student[8] not in (None, '') else na
        )
        _add_field(demographics, 0, _t("student_details.label_gender"), gender)
        _add_field(demographics, 1, _t("student_details.label_date_of_birth"), student[7] or na)
        _add_field(demographics, 2, _t("student_details.label_age"), age_value)

        # Card 3 — Academic info
        academic_info_card = ttk.LabelFrame(cards, text=_t("student_details.header_academic_info"),
                                            padding=15)
        academic_info_card.pack(fill=tk.X, pady=6)
        academic_info_card.columnconfigure(1, weight=1)
        _add_field(academic_info_card, 0, _t("student_details.label_course"), course)
        _add_field(academic_info_card, 1, _t("student_details.label_registration"),
                   student[10] or na)

        # Academic Information Tab
        academic_tab = ttk.Frame(notebook)
        notebook.add(academic_tab, text=_t("student_details.tab_academic_records"))

        # Top bar: summary line on the left, refresh on the right
        top_bar = ttk.Frame(academic_tab)
        top_bar.pack(fill=tk.X, padx=10, pady=(10, 0))
        academic_summary = ttk.Label(top_bar, text="", font=('Arial', 10, 'italic'),
                                     foreground='#555555')
        academic_summary.pack(side=tk.LEFT)
        ttk.Button(
            top_bar,
            text=_t("common.refresh", default="Refresh"),
            command=lambda: self._load_academic_data(
                student_id, modules_tree, grades_tree, attendance_tree,
                academic_summary, na,
            ),
        ).pack(side=tk.RIGHT)

        # Scrollable container — three Treeviews can't all fit when the
        # window is 700px tall, so wrap them in a Canvas + Scrollbar.
        ac_canvas = tk.Canvas(academic_tab, borderwidth=0, highlightthickness=0)
        ac_vbar = ttk.Scrollbar(academic_tab, orient='vertical', command=ac_canvas.yview)
        ac_canvas.configure(yscrollcommand=ac_vbar.set)
        ac_canvas.pack(side='left', fill=tk.BOTH, expand=True, padx=(10, 0), pady=(8, 10))
        ac_vbar.pack(side='right', fill='y', pady=(8, 10))

        ac_inner = ttk.Frame(ac_canvas)
        ac_window = ac_canvas.create_window((0, 0), window=ac_inner, anchor='nw')

        def _on_ac_inner(_event):
            ac_canvas.configure(scrollregion=ac_canvas.bbox('all'))

        def _on_ac_canvas(event):
            ac_canvas.itemconfigure(ac_window, width=event.width)

        ac_inner.bind('<Configure>', _on_ac_inner)
        ac_canvas.bind('<Configure>', _on_ac_canvas)

        # ── Mousewheel scrolling, scoped to the academic-tab canvas ──
        # The previous implementation used ``bind_all`` (process-global)
        # which leaked: closing this detail window did not unbind, so
        # the next Toplevel's wheel events fired callbacks against a
        # destroyed canvas and produced
        # ``TclError: invalid command name ".!toplevel.!canvas"``
        # on stderr. Now bound directly on the canvas + the inner frame
        # + its children via ``bind`` (window-local), so they go away
        # naturally when the detail window is destroyed.
        def _on_ac_wheel(event):
            try:
                delta = -1 if (getattr(event, 'num', None) == 5
                               or getattr(event, 'delta', 0) < 0) else 1
                ac_canvas.yview_scroll(-delta, 'units')
            except tk.TclError:
                # Canvas already destroyed — race with window close.
                pass
            return "break"

        def _bind_wheel_recursive(widget):
            try:
                for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
                    widget.bind(seq, _on_ac_wheel, add="+")
                for child in widget.winfo_children():
                    _bind_wheel_recursive(child)
            except tk.TclError:
                pass

        # Bind on the canvas itself + the scrolling inner frame; the
        # children-walk catches the Treeviews and labels added below
        # so wheel events anywhere in the academic tab scroll the
        # outer canvas. Re-bind whenever the inner frame's contents
        # change so newly-added widgets pick up the binding.
        ac_canvas.bind('<MouseWheel>', _on_ac_wheel, add="+")
        ac_canvas.bind('<Button-4>', _on_ac_wheel, add="+")
        ac_canvas.bind('<Button-5>', _on_ac_wheel, add="+")
        ac_inner.bind('<Map>', lambda _e: _bind_wheel_recursive(ac_inner))

        # Three stacked panels with Treeviews (now inside the scrollable inner frame)
        modules_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_enrolled_modules", default="Enrolled Modules"),
            padding=10,
        )
        modules_frame.pack(fill=tk.X, padx=4, pady=(0, 6))
        modules_tree = ttk.Treeview(
            modules_frame, columns=("type", "code", "name"),
            show="headings", height=6,
        )
        modules_tree.heading("type", text="Type")
        modules_tree.heading("code", text="Code")
        modules_tree.heading("name", text="Module Name")
        modules_tree.column("type", width=110, anchor="w")
        modules_tree.column("code", width=110, anchor="w")
        modules_tree.column("name", width=400, anchor="w")
        mod_vsb = ttk.Scrollbar(modules_frame, orient="vertical", command=modules_tree.yview)
        modules_tree.configure(yscrollcommand=mod_vsb.set)
        modules_tree.pack(side="left", fill=tk.X, expand=True)
        mod_vsb.pack(side="right", fill="y")
        modules_tree.tag_configure("group", background="#eef2f7", font=('Arial', 10, 'bold'))

        grades_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_grades_assessments", default="Grades & Assessments"),
            padding=10,
        )
        grades_frame.pack(fill=tk.X, padx=4, pady=6)
        grades_tree = ttk.Treeview(
            grades_frame, columns=("module", "assessment", "grade", "date"),
            show="headings", height=6,
        )
        grades_tree.heading("module", text="Module")
        grades_tree.heading("assessment", text="Assessment")
        grades_tree.heading("grade", text="Grade")
        grades_tree.heading("date", text="Date")
        grades_tree.column("module", width=110, anchor="w")
        grades_tree.column("assessment", width=300, anchor="w")
        grades_tree.column("grade", width=80, anchor="center")
        grades_tree.column("date", width=160, anchor="w")
        gr_vsb = ttk.Scrollbar(grades_frame, orient="vertical", command=grades_tree.yview)
        grades_tree.configure(yscrollcommand=gr_vsb.set)
        grades_tree.pack(side="left", fill=tk.X, expand=True)
        gr_vsb.pack(side="right", fill="y")
        grades_tree.tag_configure("good", foreground="#1b7f3a")
        grades_tree.tag_configure("warn", foreground="#b87a00")
        grades_tree.tag_configure("fail", foreground="#b00020")

        attendance_frame = ttk.LabelFrame(
            ac_inner, text=_t("student_details.header_recent_attendance", default="Recent Attendance"),
            padding=10,
        )
        attendance_frame.pack(fill=tk.X, padx=4, pady=(6, 0))
        attendance_tree = ttk.Treeview(
            attendance_frame, columns=("date", "module", "status", "notes"),
            show="headings", height=6,
        )
        attendance_tree.heading("date", text="Date")
        attendance_tree.heading("module", text="Module")
        attendance_tree.heading("status", text="Status")
        attendance_tree.heading("notes", text="Notes")
        attendance_tree.column("date", width=120, anchor="w")
        attendance_tree.column("module", width=110, anchor="w")
        attendance_tree.column("status", width=100, anchor="center")
        attendance_tree.column("notes", width=320, anchor="w")
        att_vsb = ttk.Scrollbar(attendance_frame, orient="vertical", command=attendance_tree.yview)
        attendance_tree.configure(yscrollcommand=att_vsb.set)
        attendance_tree.pack(side="left", fill=tk.X, expand=True)
        att_vsb.pack(side="right", fill="y")
        attendance_tree.tag_configure("present", foreground="#1b7f3a")
        attendance_tree.tag_configure("late", foreground="#b87a00")
        attendance_tree.tag_configure("absent", foreground="#b00020")

        self._load_academic_data(
            student_id, modules_tree, grades_tree, attendance_tree,
            academic_summary, na,
        )

        # Library activity tab — embedded summary widget driven by the
        # cross-module API. Renders an empty/zero panel when the
        # student has no library records.
        try:
            from education_system.university_system.modules.domain.academics.gui.library.cross_module_api import (
                LibrarySummaryFrame,
            )
            library_tab = ttk.Frame(notebook)
            notebook.add(library_tab, text="📚 Library")
            LibrarySummaryFrame(
                library_tab,
                user_id=student_id,
                on_open_library=getattr(self, "show_library_management", None),
            ).pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Could not embed LibrarySummaryFrame")

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

def _load_academic_data(self, student_id, modules_tree, grades_tree,
                        attendance_tree, summary_label, na):
    """Refresh the three academic Treeviews and the summary line."""
    # Clear
    for tree in (modules_tree, grades_tree, attendance_tree):
        for item in tree.get_children():
            tree.delete(item)

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

        # Modules — group by type with a faint header row before each block
        if modules:
            current_type = object()
            for module in modules:
                module_type = (module[0] or _t("student_details.unknown")).strip()
                if module_type != current_type:
                    current_type = module_type
                    modules_tree.insert(
                        "", tk.END,
                        values=(module_type.upper(), "", ""),
                        tags=("group",),
                    )
                modules_tree.insert(
                    "", tk.END,
                    values=(
                        "",
                        module[1] if module[1] else na,
                        module[2] if module[2] else _t("student_details.unknown_module"),
                    ),
                )
        else:
            modules_tree.insert(
                "", tk.END,
                values=("", "", _t("student_details.no_modules_enrolled")),
            )

        # Grades — colour-code by score band
        if grades:
            for grade in grades:
                module_code = grade[0] if grade[0] else na
                assessment_name = grade[1] if grade[1] else _t("student_details.unknown_assessment")
                raw_grade = grade[2]
                grade_value = (
                    raw_grade if raw_grade not in (None, "")
                    else _t("student_details.no_grade")
                )
                grade_date = grade[3] if grade[3] else _t("student_details.unknown_date")

                tag = ()
                try:
                    score = float(raw_grade)
                    if score >= 70:
                        tag = ("good",)
                    elif score >= 40:
                        tag = ("warn",)
                    else:
                        tag = ("fail",)
                except (TypeError, ValueError):
                    pass

                grades_tree.insert(
                    "", tk.END,
                    values=(module_code, assessment_name, grade_value, grade_date),
                    tags=tag,
                )
        else:
            grades_tree.insert(
                "", tk.END,
                values=("", _t("student_details.no_grades_recorded"), "", ""),
            )

        # Attendance — colour-code present/late/absent
        if attendance:
            for att in attendance:
                module_code = att[0] if att[0] else na
                att_date = att[1] if att[1] else _t("student_details.unknown_date")
                status = att[2] if att[2] else _t("student_details.unknown")
                notes = att[3] or ""

                status_lc = (status or "").strip().lower()
                if status_lc == "present":
                    tag = ("present",)
                elif status_lc == "late":
                    tag = ("late",)
                elif status_lc in ("absent", "unauthorised", "unauthorized"):
                    tag = ("absent",)
                else:
                    tag = ()

                attendance_tree.insert(
                    "", tk.END,
                    values=(att_date, module_code, status, notes),
                    tags=tag,
                )
        else:
            attendance_tree.insert(
                "", tk.END,
                values=("", "", _t("student_details.no_attendance_records"), ""),
            )

        summary_label.config(
            text=f"{len(modules)} module(s) · {len(grades)} grade(s) · "
                 f"{len(attendance)} recent attendance entry(ies)"
        )

    except Exception as e:
        summary_label.config(text=f"Error loading academic data: {e}",
                             foreground='#b00020')

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
