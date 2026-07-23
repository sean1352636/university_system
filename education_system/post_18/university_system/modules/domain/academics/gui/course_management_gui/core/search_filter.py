from education_system.post_18.university_system.core.sql_safety import escape_like
from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core._imports import _, messagebox, tk, sqlite3, DEFAULT_DB_PATH


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
                cursor.execute(f"SELECT COUNT(*) FROM courses{where_sql}", params)
                self._page_total = cursor.fetchone()[0] or 0
                if hasattr(self, "_update_pager_label"):
                    self._update_pager_label()

                page_size = max(1, getattr(self, "_page_size", 50))
                page = getattr(self, "_page", 0)
                offset = page * page_size

                query = f"""
                SELECT id, COALESCE(course_code, code) as course_code,
                       COALESCE(course_name, name) as course_name,
                       COALESCE(department, 'N/A') as department,
                       COALESCE(level, 'N/A') as level,
                       COALESCE(credit_hours, credits, 3.0) as credit_hours,
                       COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment,
                       COALESCE(status, 'Active') as status
                FROM courses{where_sql}
                ORDER BY course_code
                LIMIT ? OFFSET ?
                """
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
        """Popup listing all students enrolled on *course_code*."""
        from tkinter import ttk

        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT student_id, "
                    "TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS name, "
                    "COALESCE(email_address, '') AS email, "
                    "COALESCE(year_of_study, '') AS year, "
                    "COALESCE(status, '') AS status "
                    "FROM students WHERE course = ? "
                    "ORDER BY last_name, first_name",
                    (course_code,),
                )
                students = cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"),
                                 _("course_management.messages.search_failed").format(error=e))
            return

        win = tk.Toplevel(self.course_tree.winfo_toplevel())
        title_code = f"{course_name} ({course_code})" if course_name else course_code
        win.title(f"Students Enrolled — {title_code}")
        win.geometry("640x460")
        win.minsize(500, 360)
        win.transient(self.course_tree.winfo_toplevel())
        try:
            win.grab_set()
        except tk.TclError:
            pass

        tk.Label(win, text=f"Students enrolled on {title_code}",
                 font=("Arial", 12, "bold")).pack(anchor="w", padx=12, pady=(12, 2))
        count_label = tk.Label(win, text=f"{len(students)} student(s)", fg="gray")
        count_label.pack(anchor="w", padx=12, pady=(0, 8))

        tree_frame = ttk.Frame(win)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        columns = ("ID", "Name", "Email", "Year", "Status")
        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                            yscrollcommand=y_scroll.set)
        y_scroll.config(command=tree.yview)
        widths = {"ID": 90, "Name": 200, "Email": 220, "Year": 60, "Status": 90}
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=widths.get(col, 100))
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for row in students:
            tree.insert("", tk.END, values=row)

        if not students:
            tree.insert("", tk.END, values=("", "No students enrolled on this course.", "", "", ""))

        ttk.Button(win, text=_("common.close"), command=win.destroy).pack(pady=(0, 12))

    def show_course_details(self, course_id):
        """Show detailed course information"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM courses WHERE id = ?", (course_id,))
                course = cursor.fetchone()

                if not course:
                    messagebox.showerror(_("common.error"), _("course_management.messages.course_not_found"))
                    return

                # Switch to details tab and populate the card layout.
                self.notebook.select(1)  # Details tab
                self.render_course_details(course)

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_load_course_details", error=str(e)))

    def format_course_details(self, course):
        """Format course data for display."""

        def get(i, default="N/A"):
            return course[i] if len(course) > i and course[i] not in (None, "") else default

        def years(i):
            v = course[i] if len(course) > i else None
            return f"{v} years" if v not in (None, "") else "N/A"

        def money(i):
            v = course[i] if len(course) > i else None
            if isinstance(v, (int, float)):
                return f"£{v:,.2f}"
            return "N/A" if v in (None, "") else str(v)

        def yesno(i):
            if len(course) <= i:
                return "N/A"
            v = course[i]
            return "Yes" if bool(v) else "No" if v in (False, 0) else "N/A"

        def avail_spots():
            max_e = course[15] if len(course) > 15 else None
            cur_e = course[16] if len(course) > 16 else None
            if isinstance(max_e, (int, float)) and isinstance(cur_e, (int, float)):
                return max_e - cur_e
            return "N/A"

        if len(course) < 10:
            # Basic format for legacy schema
            details = f"""COURSE DETAILS
    {'='*50}

    Course ID: {get(0)}
    Course Code: {get(1)}
    Course Name: {get(2)}
    Description: {get(3)}
    Duration: {years(4)}
    Level: {get(5)}
    Department: {get(6)}
    """
        else:
            # Enhanced format for full schema
            details = f"""COURSE DETAILS
    {'='*50}

    BASIC INFORMATION:
    Course ID: {get(0)}
    Course Code: {get(1)}
    Course Name: {get(2)}
    Description: {get(3)}
    Department: {get(6)}
    Level: {get(5)}
    Course Type: {get(18)}
    Status: {get(17)}

    ACADEMIC DETAILS:
    Credit Hours: {get(7)}
    Contact Hours/Week: {get(8)}
    Duration: {years(4)}
    Lab Required: {yesno(13)}
    Online Available: {yesno(14)}

    ENROLLMENT:
    Max Enrollment: {get(15)}
    Current Enrollment: {get(16)}
    Available Spots: {avail_spots()}

    ADDITIONAL INFORMATION:
    Learning Outcomes: {get(9)}
    Assessment Methods: {get(10)}
    Required Textbooks: {get(11)}
    Course Fee: {money(12)}
    Tags: {get(19)}
    Availability: {get(20)}

    TIMESTAMPS:
    Created: {get(21)}
    Last Updated: {get(22)}
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
