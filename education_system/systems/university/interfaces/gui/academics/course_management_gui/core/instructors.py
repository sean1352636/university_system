from education_system.systems.university.infrastructure.sql_safety import escape_like
from education_system.systems.university.interfaces.gui.academics.course_management_gui.core._imports import (
    _, messagebox, tk, sqlite3, DEFAULT_DB_PATH,
    InstructorCreateDialog, AssignInstructorDialog, InstructorDetailsDialog,
    AdvancedSearchDialog, PrerequisitesWindow,
)


class InstructorsMixin:
    """Instructor management, search, and prerequisites window."""

    def show_add_instructor(self):
        """Show add instructor dialog"""
        dialog = InstructorCreateDialog(self.root, self.auth)
        if dialog.result:
            self.refresh_instructor_list()
            self.update_status(_("course_management.messages.instructor_added_success", name=dialog.result))

    def refresh_instructor_list(self):
        """Refresh the instructor list"""
        try:
            tree = self.instructor_tree
            # Clear existing rows
            for item in tree.get_children():
                tree.delete(item)

            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check if instructors table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
                if not cursor.fetchone():
                    self.instructor_count_label.config(
                        text="No instructors table found. Please add an instructor first."
                    )
                    return

                cursor.execute("""
                SELECT id, first_name, last_name, email, department, specialization,
                       max_courses_per_semester, status
                FROM instructors
                ORDER BY last_name, first_name
                """)

                instructors = cursor.fetchall()

            if instructors:
                for idx, instructor in enumerate(instructors):
                    id, first_name, last_name, email, dept, spec, max_courses, status = instructor
                    full_name = f"{first_name or ''} {last_name or ''}".strip() or "N/A"
                    tag = "evenrow" if idx % 2 == 0 else "oddrow"
                    tree.insert("", tk.END, values=(
                        id,
                        full_name,
                        email or "N/A",
                        dept or "N/A",
                        spec or "N/A",
                        max_courses if max_courses is not None else "N/A",
                        status or "N/A",
                    ), tags=(tag,))
                self.instructor_count_label.config(text=f"Total Instructors: {len(instructors)}")
            else:
                self.instructor_count_label.config(text="No instructors found in the system.")

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))

    def show_assign_instructor(self):
        """Show assign instructor to course dialog"""
        dialog = AssignInstructorDialog(self.root, self.auth)
        if dialog.result:
            self.update_status(_("course_management.messages.instructor_assigned_success"))

    def on_instructor_double_click(self, event=None):
        """Open the details window for the double-clicked instructor.

        Admins get an editable form plus course-assignment controls; other
        users see a read-only view.
        """
        tree = self.instructor_tree
        selected = tree.focus()
        if not selected:
            return

        values = tree.item(selected, "values")
        if not values:
            return

        try:
            instructor_id = int(values[0])
        except (TypeError, ValueError):
            return

        dialog = InstructorDetailsDialog(
            self.root, self.auth, instructor_id, editable=self.is_admin()
        )
        if getattr(dialog, "result", None):
            self.refresh_instructor_list()

    def show_search_dialog(self):
        """Show advanced search dialog"""
        dialog = AdvancedSearchDialog(self.root)
        if dialog.result:
            # Apply search results to main course list
            self.apply_search_results(dialog.result)

    def apply_search_results(self, search_criteria):
        """Apply search results to course list"""
        try:
            # Clear existing items
            for item in self.course_tree.get_children():
                self.course_tree.delete(item)

            # Build query from search criteria
            query = """
            SELECT id, COALESCE(course_code, code) as course_code,
                   COALESCE(course_name, name) as course_name,
                   department, level, COALESCE(credit_hours, credits, 3.0) as credit_hours,
                   COALESCE(current_enrollment, 0) || '/' || COALESCE(max_enrollment, 0) as enrollment,
                   status
            FROM courses WHERE COALESCE(course_code, code) IS NOT NULL
            AND COALESCE(course_name, name) IS NOT NULL
            """
            params = []

            for field, value in search_criteria.items():
                if field == "available_only" and value:
                    query += " AND COALESCE(current_enrollment, 0) < COALESCE(max_enrollment, 0)"
                elif value and (isinstance(value, str) and value.strip()):
                    if field == "keyword":
                        query += " AND (course_code LIKE ? OR course_name LIKE ? OR description LIKE ?)"
                        search_param = f"%{escape_like(value)}%"
                        params.extend([search_param, search_param, search_param])
                    elif field == "min_credits":
                        query += " AND credit_hours >= ?"
                        params.append(float(value))
                    elif field == "max_credits":
                        query += " AND credit_hours <= ?"
                        params.append(float(value))
                    elif field not in ["available_only"]:
                        query += f" AND {field} LIKE ?"
                        params.append(f"%{escape_like(value)}%")

            query += " ORDER BY course_code"

            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0); conn.execute("PRAGMA journal_mode=WAL")
            try:
                cursor = conn.cursor()
                cursor.execute(query, params)
                courses = cursor.fetchall()
            finally:
                conn.close()

            # Populate results
            for course in courses:
                self.course_tree.insert("", tk.END, values=course)

            self.update_status(_("course_management.messages.search_completed_count", count=len(courses)))

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.search_failed").format(error=e))

    def show_prerequisites_window(self):
        """Show prerequisites management window"""
        PrerequisitesWindow(self.root, self.auth)
