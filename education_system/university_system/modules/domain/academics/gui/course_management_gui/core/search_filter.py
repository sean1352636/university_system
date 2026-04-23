from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import _, messagebox, tk, sqlite3, DEFAULT_DB_PATH


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
        """Handle double-click on course item"""
        selection = self.course_tree.selection()
        if selection:
            item = self.course_tree.item(selection[0])
            course_id = item['values'][0]
            self.show_course_details(course_id)

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

                # Switch to details tab and populate
                self.notebook.select(1)  # Details tab

                # Format course details
                details = self.format_course_details(course)

                self.details_text.delete(1.0, tk.END)
                self.details_text.insert(1.0, details)

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
                return f"${v:,.2f}"
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

                cursor.execute(
                    "SELECT id, COALESCE(course_code, code) as ccode, COALESCE(course_name, name) as cname "
                    "FROM courses WHERE COALESCE(course_code, code) IS NOT NULL "
                    "AND COALESCE(course_name, name) IS NOT NULL "
                    "AND LOWER(COALESCE(status, 'active')) = 'active' "
                    "AND COALESCE(course_type, '') = 'Degree Program' "
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
