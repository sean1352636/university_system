from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core._imports import _, messagebox, tk, sqlite3, DEFAULT_DB_PATH


class SearchFilterMixin:
    """Search, filtering, course display, and course selector operations."""

    def on_search_change(self, event=None):
        """Handle search text change"""
        self._page = 0  # new search collapses back to page 1
        self.filter_courses()

    def on_filter_change(self, event=None):
        """Handle filter change"""
        self._page = 0
        self.filter_courses()

    def filter_courses(self):
        """Filter courses based on search and filter criteria, paginated."""
        try:
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)

            search_text = self.search_var.get().strip()
            dept_filter = self.dept_filter.get()
            status_filter = self.status_filter.get()

            where_sql = (" WHERE COALESCE(course_code, code) IS NOT NULL "
                         "AND COALESCE(course_name, name) IS NOT NULL")
            params = []

            if search_text:
                where_sql += " AND (course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)"
                search_param = f"%{escape_like(search_text)}%"
                params.extend([search_param, search_param, search_param])

            # `_("common.all")` is what populates the filter combo, so compare
            # against that — not the literal "All" — to honour translations.
            all_label = _("common.all")
            if dept_filter and dept_filter not in ("All", all_label):
                where_sql += " AND department = ?"
                params.append(dept_filter)

            if status_filter and status_filter not in ("All", all_label):
                where_sql += " AND status = ?"
                params.append(status_filter)

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                # db-audit: ignore[DBW001] - string literal
                cursor.execute(f"SELECT COUNT(*) FROM courses{where_sql}", params)
                self._page_total = cursor.fetchone()[0] or 0
                if hasattr(self, "_update_pager_label"):
                    self._update_pager_label()

                page_size = max(1, getattr(self, "_page_size", 50))
                page = getattr(self, "_page", 0)
                offset = page * page_size

                # The enrolment figure is counted live rather than read from
                # the denormalised courses.current_enrollment, which drifts
                # whenever a student is added by a path that forgets to bump
                # it. Maintenance > Recalculate Enrollment Numbers writes the
                # stored counter back in line.
                from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core.enrolment_sync import (
                    HEADCOUNT_SQL,
                )
                query = f"""
                SELECT id, COALESCE(course_code, code) as course_code,
                       COALESCE(course_name, name) as course_name,
                       COALESCE(department, 'N/A') as department,
                       COALESCE(level, 'N/A') as level,
                       COALESCE(credit_hours, credits, 3.0) as credit_hours,
                       {{headcount}} || '/' || COALESCE(max_enrollment, 0) as enrollment,
                       COALESCE(status, 'Active') as status
                FROM courses c{where_sql}
                ORDER BY course_code
                LIMIT ? OFFSET ?
                """.replace("{headcount}", HEADCOUNT_SQL)
                cursor.execute(query, (*params, page_size, offset))
                courses = cursor.fetchall()

            for course in courses:
                self.course_tree.insert("", tk.END, values=course)

            self.update_status(
                f"Showing {len(courses)} of {self._page_total} matching course(s).")

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.search_failed").format(error=e))

    def load_filter_options(self):
        """Load options for filter dropdowns"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Load departments
                cursor.execute("SELECT DISTINCT department FROM courses WHERE course_code IS NOT NULL AND department IS NOT NULL ORDER BY department")
                departments = ["All"] + [row[0] for row in cursor.fetchall()]
                self.dept_filter['values'] = departments
                self.dept_filter.set("All")

        except sqlite3.Error:
            pass

    def on_course_double_click(self, event):
        """Handle double-click on a course row.

        Double-clicking the *Name* column opens the enrolled-students popup;
        double-clicking anywhere else keeps the existing course-details view.
        """
        selection = self.course_tree.selection()
        if not selection:
            return
        item = self.course_tree.item(selection[0])
        values = item['values']
        if not values:
            return

        # Name is the 3rd Treeview column: (ID, Code, Name, ...) -> '#3'
        if self.course_tree.identify_column(event.x) == '#3':
            course_code = str(values[1])
            # Strip conflict / over-capacity display prefixes off the code.
            for prefix in ("⚠ ", "🔥 "):
                if course_code.startswith(prefix):
                    course_code = course_code[len(prefix):]
            self.show_enrolled_students(course_code, str(values[2]))
            return

        self.show_course_details(values[0])

    def show_enrolled_students(self, course_code, course_name=""):
        """Popup for one course: enrolled students and the course's modules.

        Two tabs rather than one list — the students on a course and the
        modules that make it up are the two things you want when you click a
        course, and they were previously a list and nowhere respectively.
        """
        from tkinter import ttk
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core.course_modules import (
            COLUMNS as MODULE_COLUMNS,
            modules_for_course,
        )
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core.enrolment_sync import (
            students_for_course,
        )

        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                # Matched on the course name as well as its code: students.course
                # is free text, and a few rows hold 'Computer Science' rather
                # than 'CS'. A code-only lookup left those people off the list.
                students = students_for_course(conn, course_code, course_name)
                modules = modules_for_course(course_code, conn)
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"),
                                 _("course_management.messages.search_failed").format(error=e))
            return

        win = tk.Toplevel(self.course_tree.winfo_toplevel())
        title_code = f"{course_name} ({course_code})" if course_name else course_code
        win.title(f"Course — {title_code}")
        win.geometry("760x520")
        win.minsize(560, 380)
        win.transient(self.course_tree.winfo_toplevel())
        try:
            win.grab_set()
        except tk.TclError:
            pass

        tk.Label(win, text=title_code,
                 font=("Arial", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        def _table(parent, columns, rows, widths, empty_message):
            """A scrolled Treeview filled with *rows*, or an empty-state row."""
            holder = ttk.Frame(parent)
            holder.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
            y_scroll = ttk.Scrollbar(holder, orient=tk.VERTICAL)
            tree = ttk.Treeview(holder, columns=columns, show="headings",
                                yscrollcommand=y_scroll.set)
            y_scroll.config(command=tree.yview)
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=widths.get(col, 100))
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
            for row in rows:
                tree.insert("", tk.END, values=row)
            if not rows:
                # Pad to the column count so the message lands in the first column.
                tree.insert("", tk.END,
                            values=(empty_message,) + ("",) * (len(columns) - 1))
            return tree

        # --- Students tab ---
        students_tab = ttk.Frame(notebook)
        notebook.add(students_tab, text=f"Enrolled Students ({len(students)})")
        _table(
            students_tab,
            ("ID", "Name", "Email", "Year", "Status"),
            students,
            {"ID": 90, "Name": 200, "Email": 220, "Year": 60, "Status": 90},
            "No students enrolled on this course.",
        )

        # --- Modules tab ---
        modules_tab = ttk.Frame(notebook)
        notebook.add(modules_tab, text=f"Modules ({len(modules)})")
        _table(
            modules_tab,
            MODULE_COLUMNS,
            modules,
            {"Code": 110, "Module": 240, "Credits": 70, "Semester": 90,
             "Type": 90, "Instructor": 150, "Status": 80},
            "No modules are mapped to this course.",
        )

        ttk.Button(win, text=_("common.close"), command=win.destroy).pack(pady=(0, 12))

    def show_course_details(self, course_id):
        """Show detailed course information"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                # Rows come back keyed by column name: the detail card used to
                # read this row by position against an out-of-date column
                # order, which is why "Available Spots" showed N/A while the
                # list tab showed a real enrolment figure.
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
                course = cursor.fetchone()

                if not course:
                    messagebox.showerror(_("common.error"), _("course_management.messages.course_not_found"))
                    return

                # Switch to details tab and populate the card layout. The
                # modules are read on this connection so the card can list them.
                self.notebook.select(1)  # Details tab
                self.render_course_details(course, conn=conn)

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_load_course_details", error=str(e)))

    def format_course_details(self, course):
        """Format course data for display."""
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui.core.course_fields import (
            available_spots,
            course_fields,
            is_legacy,
        )

        data = course_fields(course)

        def get(name, default="N/A"):
            v = data.get(name)
            return v if v not in (None, "") else default

        def years(name):
            v = data.get(name)
            if v in (None, ""):
                return "N/A"
            # ``duration`` already reads "3 years" for most rows; only a bare
            # number needs the unit appending.
            text = str(v)
            return text if not text.replace(".", "", 1).isdigit() else f"{text} years"

        def money(name):
            v = data.get(name)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return f"£{v:,.2f}"
            return "N/A" if v in (None, "") else str(v)

        def yesno(name):
            v = data.get(name)
            if v in (None, ""):
                return "N/A"
            return "Yes" if bool(v) else "No"

        def avail_spots():
            return available_spots(data)

        if is_legacy(course):
            # Basic format for legacy schema
            details = f"""COURSE DETAILS
    {'='*50}

    Course ID: {get("id")}
    Course Code: {get("course_code")}
    Course Name: {get("course_name")}
    Description: {get("description")}
    Duration: {years("duration")}
    Level: {get("level")}
    Department: {get("department")}
    """
        else:
            # Enhanced format for full schema
            details = f"""COURSE DETAILS
    {'='*50}

    BASIC INFORMATION:
    Course ID: {get("id")}
    Course Code: {get("course_code")}
    Course Name: {get("course_name")}
    Description: {get("description")}
    Department: {get("department")}
    Level: {get("level")}
    Course Type: {get("course_type")}
    Status: {get("status")}

    ACADEMIC DETAILS:
    Credit Hours: {get("credit_hours")}
    Contact Hours/Week: {get("contact_hours_per_week")}
    Duration: {years("duration")}
    Lab Required: {yesno("lab_required")}
    Online Available: {yesno("online_available")}

    ENROLLMENT:
    Max Enrollment: {get("max_enrollment")}
    Current Enrollment: {get("current_enrollment")}
    Available Spots: {avail_spots()}

    ADDITIONAL INFORMATION:
    Learning Outcomes: {get("learning_outcomes")}
    Assessment Methods: {get("assessment_methods")}
    Required Textbooks: {get("required_textbooks")}
    Course Fee: {money("course_fee")}
    Tags: {get("tags")}
    Availability: {get("availability_periods")}

    TIMESTAMPS:
    Created: {get("created_at")}
    Last Updated: {get("updated_at")}
    """
        return details

    def load_course_selector_options(self):
        """Load course options for the selector"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Match the Course List tab's filter shape: any row that
                # has a code and a name. Don't constrain on status or
                # course_type — the original query required
                # ``course_type = 'Degree Program'`` which silently
                # hid every row whose type was 'Bachelors', 'Masters',
                # 'Certificate', etc., so the dropdown looked empty
                # despite the list tab showing the same courses fine.
                cursor.execute(
                    "SELECT id, "
                    "       COALESCE(course_code, code) AS ccode, "
                    "       COALESCE(course_name, name) AS cname "
                    "FROM courses "
                    "WHERE COALESCE(course_code, code) IS NOT NULL "
                    "AND   COALESCE(course_name, name) IS NOT NULL "
                    "ORDER BY ccode"
                )
                courses = cursor.fetchall()

                course_options = [f"{course[1]} - {course[2]}" for course in courses if course[1] and course[2]]
                self.course_selector['values'] = course_options

                # Store course IDs for mapping
                self.course_id_map = {f"{course[1]} - {course[2]}": course[0] for course in courses if course[1] and course[2]}

        except sqlite3.Error:
            pass

    def on_course_select(self, event=None):
        """Handle course selection from dropdown"""
        selected_text = self.course_selector.get()
        if selected_text in self.course_id_map:
            course_id = self.course_id_map[selected_text]
            self.show_course_details(course_id)
