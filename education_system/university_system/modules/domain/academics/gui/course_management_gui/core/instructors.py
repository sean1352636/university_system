from education_system.university_system.core.sql_safety import escape_like
from education_system.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, messagebox, tk, sqlite3, DEFAULT_DB_PATH,
    InstructorCreateDialog, AssignInstructorDialog,
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
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Check if instructors table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='instructors'")
                if not cursor.fetchone():
                    instructor_text = "INSTRUCTORS\n"
                    instructor_text += "=" * 50 + "\n\n"
                    instructor_text += "No instructors table found. Please create instructors first.\n"
                else:
                    cursor.execute("""
                    SELECT id, first_name, last_name, email, department, specialization,
                           max_courses_per_semester, status
                    FROM instructors
                    ORDER BY last_name, first_name
                    """)

                    instructors = cursor.fetchall()

                    instructor_text = "INSTRUCTORS\n"
                    instructor_text += "=" * 50 + "\n\n"

                    if instructors:
                        instructor_text += f"{'ID':<5} {'Name':<25} {'Email':<30} {'Department':<15} {'Status':<10}\n"
                        instructor_text += "-" * 85 + "\n"

                        for instructor in instructors:
                            id, first_name, last_name, email, dept, spec, max_courses, status = instructor
                            full_name = f"{first_name} {last_name}"
                            dept_display = dept[:12] + "..." if dept and len(dept) > 15 else dept or "N/A"
                            instructor_text += f"{id:<5} {full_name:<25} {email:<30} {dept_display:<15} {status:<10}\n"

                        instructor_text += f"\nTotal Instructors: {len(instructors)}\n"
                    else:
                        instructor_text += "No instructors found in the system.\n"

            # Update instructor tab
            self.instructor_text.delete(1.0, tk.END)
            self.instructor_text.insert(1.0, instructor_text)

        except sqlite3.Error as e:
            messagebox.showerror(_("common.database_error"), _("course_management.messages.failed_generate_analytics", error=str(e)))

    def show_assign_instructor(self):
        """Show assign instructor to course dialog"""
        dialog = AssignInstructorDialog(self.root, self.auth)
        if dialog.result:
            self.update_status(_("course_management.messages.instructor_assigned_success"))

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
