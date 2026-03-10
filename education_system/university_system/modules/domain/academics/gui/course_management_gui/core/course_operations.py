from ._imports import _, messagebox, sqlite3, DEFAULT_DB_PATH, CourseEditDialog


class CourseOperationsMixin:
    """Course CRUD operations and cascade deletes."""

    def edit_selected_course(self):
        """Edit the selected course"""
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), _("course_management.messages.select_course_to_edit"))
            return

        item = self.course_tree.item(selection[0])
        course_id = item['values'][0]

        dialog = CourseEditDialog(self.root, self.auth, course_id)
        if dialog.result:
            self.refresh_course_list()
            self.update_status(_("course_management.status.course_updated"))

    def delete_selected_course(self):
        """Delete the selected course"""
        selection = self.course_tree.selection()
        if not selection:
            messagebox.showwarning(_("course_management.messages.no_selection"), _("course_management.messages.select_course_to_delete"))
            return

        item = self.course_tree.item(selection[0])
        course_id = item['values'][0]
        course_code = item['values'][1]
        course_name = item['values'][2]

        # Enhanced delete confirmation with impact analysis
        if self.confirm_course_deletion(course_id, course_code, course_name):
            try:
                with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                    cursor = conn.cursor()

                    # Handle student reassignment before deleting course
                    self.reassign_students_from_deleted_course(cursor, course_code)

                    # Delete related records first
                    cursor.execute("DELETE FROM course_prerequisites WHERE course_id = ? OR prerequisite_course_id = ?", (course_id, course_id))
                    cursor.execute("DELETE FROM course_schedule WHERE course_id = ?", (course_id,))
                    cursor.execute("DELETE FROM course_waitlist WHERE course_id = ?", (course_id,))
                    cursor.execute("DELETE FROM course_history WHERE course_id = ?", (course_id,))

                    # Delete the course
                    cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))

                    conn.commit()

                self.refresh_course_list()
                self.update_status(_("course_management.status.course_deleted").format(course=course_code))

            except sqlite3.Error as e:
                messagebox.showerror(_("common.database_error"), _("course_management.messages.delete_course_failed").format(error=e))

    def reassign_students_from_deleted_course(self, cursor, course_code):
        """Reassign students from a course that's being deleted to other available courses and modules"""
        try:
            # First, delete all modules and assignments for this course
            self.delete_modules_for_course(cursor, course_code)

            # Get students enrolled in the course being deleted
            cursor.execute('''
                SELECT student_id, first_name, last_name
                FROM students
                WHERE course = ?
            ''', (course_code,))
            affected_students = cursor.fetchall()

            if not affected_students:
                return

            # Get available alternative courses (excluding the one being deleted)
            cursor.execute('''
                SELECT course_code FROM courses
                WHERE (status = 'Active' OR status = 'active') AND course_code != ?
                AND course_code IS NOT NULL AND course_code != ''
                AND max_enrollment > current_enrollment
            ''')
            alternative_courses = [row[0] for row in cursor.fetchall()]

            if not alternative_courses:
                # If no alternatives, create a default holding course
                alternative_courses = ['GENERAL']

            import random
            reassignment_count = 0

            # Reassign each student to a random alternative course
            for student_id, first_name, last_name in affected_students:
                new_course = random.choice(alternative_courses)

                # Update student's course
                cursor.execute('''
                    UPDATE students
                    SET course = ?
                    WHERE student_id = ?
                ''', (new_course, student_id))

                # Remove student from modules of the deleted course
                cursor.execute('''
                    DELETE FROM student_modules
                    WHERE student_id = ? AND module_code IN (
                        SELECT module_code FROM modules WHERE department = ?
                    )
                ''', (student_id, course_code))

                # Assign student to modules of the new course
                self.assign_student_to_course_modules(cursor, student_id, new_course)

                # Update course enrollment counts
                cursor.execute('''
                    UPDATE courses
                    SET current_enrollment = current_enrollment + 1
                    WHERE course_code = ?
                ''', (new_course,))

                reassignment_count += 1

            # Decrease enrollment count for the deleted course
            cursor.execute('''
                UPDATE courses
                SET current_enrollment = current_enrollment - ?
                WHERE course_code = ?
            ''', (reassignment_count, course_code))

            print(_("course_management.success.students_reassigned", count=reassignment_count, code=course_code))

        except Exception as e:
            print(_("course_management.errors.student_reassignment", error=str(e)))

    def delete_modules_for_course(self, cursor, course_code):
        """Delete all modules and their assignments for a specific course"""
        try:
            # Get all modules for this course
            cursor.execute('SELECT module_code FROM modules WHERE department = ?', (course_code,))
            modules = [row[0] for row in cursor.fetchall()]

            for module_code in modules:
                # Delete assignments and related data for each module
                self.delete_assignments_for_module(cursor, module_code)

            # Delete all modules for this course
            cursor.execute('DELETE FROM modules WHERE department = ?', (course_code,))
            print(_("course_management.success.modules_deleted", count=len(modules), code=course_code))

        except Exception as e:
            print(_("course_management.errors.module_delete", code=course_code, error=str(e)))

    def delete_assignments_for_module(self, cursor, module_code):
        """Delete all assignments and related data for a specific module"""
        try:
            # Get all assignment IDs for this module
            cursor.execute('SELECT id FROM assignments WHERE module_code = ?', (module_code,))
            assignment_ids = [row[0] for row in cursor.fetchall()]

            if assignment_ids:
                # Delete assignment submissions first
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM assignment_submissions WHERE assignment_id = ?', (assignment_id,))

                # Delete peer reviews for these assignments
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM peer_reviews WHERE assignment_id = ?', (assignment_id,))

                # Delete extension requests for these assignments
                for assignment_id in assignment_ids:
                    cursor.execute('DELETE FROM extension_requests WHERE assignment_id = ?', (assignment_id,))

                # Delete the assignments themselves
                cursor.execute('DELETE FROM assignments WHERE module_code = ?', (module_code,))

            # Also delete any assessments for this module
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='assessments'")
            if cursor.fetchone():
                cursor.execute('DELETE FROM assessments WHERE module_code = ?', (module_code,))

        except Exception as e:
            print(_("course_management.errors.assignment_delete", code=module_code, error=str(e)))

    def assign_student_to_course_modules(self, cursor, student_id, course_code):
        """Assign a student to random modules from their new course"""
        try:
            import random
            from datetime import datetime

            # Get available modules for the new course
            cursor.execute('''
                SELECT module_code, module_name FROM modules
                WHERE department = ? AND is_active = 1
            ''', (course_code,))
            available_modules = cursor.fetchall()

            if available_modules:
                # Randomly select 3-5 modules for the student
                num_modules = min(random.randint(3, 5), len(available_modules))
                selected_modules = random.sample(available_modules, num_modules)

                current_date = datetime.now().strftime('%Y-%m-%d')

                for module_code, module_name in selected_modules:
                    cursor.execute('''
                        INSERT OR IGNORE INTO student_modules (student_id, module_code, enrollment_date, status)
                        VALUES (?, ?, ?, ?)
                    ''', (student_id, module_code, current_date, 'Enrolled'))

                print(_("course_management.success.student_assigned_modules", id=student_id, count=len(selected_modules), code=course_code))

        except Exception as e:
            print(_("course_management.errors.student_assign_modules", id=student_id, error=str(e)))

    def confirm_course_deletion(self, course_id, course_code, course_name):
        """Show enhanced deletion confirmation dialog"""
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()

                # Get impact analysis
                cursor.execute("SELECT current_enrollment FROM courses WHERE id = ?", (course_id,))
                enrolled = cursor.fetchone()
                enrolled_count = enrolled[0] if enrolled and enrolled[0] else 0

                cursor.execute("SELECT COUNT(*) FROM course_prerequisites WHERE prerequisite_course_id = ?", (course_id,))
                prereq_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM course_schedule WHERE course_id = ?", (course_id,))
                schedule_count = cursor.fetchone()[0]

            # Create confirmation dialog
            message = f"Delete Course: {course_code} - {course_name}\n\n"
            message += "IMPACT ANALYSIS:\n"
            message += f"\u2022 Students enrolled: {enrolled_count}\n"
            message += f"\u2022 Courses using as prerequisite: {prereq_count}\n"
            message += f"\u2022 Schedule entries: {schedule_count}\n\n"

            if enrolled_count > 0 or prereq_count > 0:
                message += _("course_management.messages.deletion_warning") + "\n"
                message += _("course_management.messages.consider_inactive") + "\n\n"

            message += _("course_management.messages.action_cannot_be_undone")

            return messagebox.askyesno(_("course_management.dialogs.confirm_deletion"), message)

        except sqlite3.Error:
            return messagebox.askyesno(_("course_management.dialogs.confirm_deletion"), _("course_management.messages.delete_course_confirm").format(code=course_code, name=course_name))
