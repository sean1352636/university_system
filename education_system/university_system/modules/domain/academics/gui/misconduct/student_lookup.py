"""Student lookup and course validation for the Academic Misconduct Panel."""

from ._imports import tk, messagebox, _t, sqlite3, DEFAULT_DB_PATH


class MisconductStudentLookupMixin:
    """Mixin providing student lookup and course validation."""

    def lookup_student(self, student_id_entry, entries):
        """Look up student by ID and auto-fill details including course."""
        student_id = student_id_entry.get().strip()
        if not student_id:
            messagebox.showwarning(_t("misconduct.msg_titles.missing_id"), "Please enter a Student ID to look up.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            student_name = None
            student_email = None
            student_course = None

            # Try to find student in students table
            cursor.execute('''
                SELECT first_name, last_name, email_address, course FROM students WHERE student_id = ?
            ''', (student_id,))
            student = cursor.fetchone()

            if student:
                # Combine first and last name
                first = student['first_name'] or ''
                last = student['last_name'] or ''
                student_name = f"{first} {last}".strip()
                student_email = student['email_address'] or ''
                student_course = student['course'] or ''
            else:
                # Try users table as fallback
                cursor.execute('''
                    SELECT username, email FROM users WHERE id = ? OR username = ?
                ''', (student_id, student_id))
                user = cursor.fetchone()
                if user:
                    student_name = user['username'] or ''
                    student_email = user['email'] or ''

            # Get enrolled modules for the student (from student_modules table)
            modules_list = []
            try:
                cursor.execute('''
                    SELECT DISTINCT module_code FROM student_modules WHERE student_id = ?
                ''', (student_id,))
                modules = cursor.fetchall()
                modules_list = [m['module_code'] for m in modules]
            except Exception:
                pass

            conn.close()

            if student_name:
                # Clear and fill entries
                if 'student' in entries:
                    entries['student'].delete(0, tk.END)
                    entries['student'].insert(0, student_name)
                if 'student_email' in entries:
                    entries['student_email'].delete(0, tk.END)
                    entries['student_email'].insert(0, student_email)
                if 'course' in entries and student_course:
                    entries['course'].delete(0, tk.END)
                    # Include modules if available
                    course_info = student_course
                    if modules_list:
                        course_info += f" (Modules: {', '.join(modules_list[:5])})"
                    entries['course'].insert(0, course_info)

                info_msg = f"Student '{student_name}' found and details filled."
                if student_course:
                    info_msg += f"\nCourse: {student_course}"
                if modules_list:
                    info_msg += f"\nEnrolled in {len(modules_list)} module(s)"
                messagebox.showinfo(_t("misconduct.msg_titles.found"), info_msg)
            else:
                messagebox.showinfo(_t("misconduct.msg_titles.not_found"), f"No student found with ID '{student_id}'.")

        except Exception as e:
            messagebox.showerror(_t("misconduct.msg_titles.error"), f"Failed to look up student: {str(e)}")

    def get_student_assignments(self, student_id):
        """Get assignments for a student from the database."""
        assignments = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # If no student_id provided, get all active assignments
            if not student_id:
                cursor.execute('''
                    SELECT id, title, module_code, due_date
                    FROM assignments
                    WHERE is_active = 1
                    ORDER BY due_date DESC
                    LIMIT 50
                ''')
                assignments = [dict(row) for row in cursor.fetchall()]
            else:
                # Get assignments the student has submitted to
                cursor.execute('''
                    SELECT DISTINCT a.id, a.title, a.module_code, a.due_date,
                           s.file_name as submitted_file
                    FROM assignments a
                    INNER JOIN assignment_submissions s ON a.id = s.assignment_id
                    WHERE s.student_id = ?
                    ORDER BY a.due_date DESC
                    LIMIT 50
                ''', (student_id,))
                assignments = [dict(row) for row in cursor.fetchall()]

                # If no submissions, get assignments from enrolled modules (student_modules table)
                if not assignments:
                    cursor.execute('''
                        SELECT DISTINCT a.id, a.title, a.module_code, a.due_date
                        FROM assignments a
                        INNER JOIN student_modules sm ON a.module_code = sm.module_code
                        WHERE sm.student_id = ?
                        ORDER BY a.due_date DESC
                        LIMIT 50
                    ''', (student_id,))
                    assignments = [dict(row) for row in cursor.fetchall()]

                # If still no assignments, show all active assignments as fallback
                if not assignments:
                    cursor.execute('''
                        SELECT id, title, module_code, due_date
                        FROM assignments
                        WHERE is_active = 1
                        ORDER BY due_date DESC
                        LIMIT 50
                    ''')
                    assignments = [dict(row) for row in cursor.fetchall()]

            conn.close()
        except Exception as e:
            print(f"Error getting assignments: {e}")

        return assignments

    def get_valid_courses(self):
        """Get all valid course/program codes from the database."""
        courses = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get from courses table first (main courses/modules)
            cursor.execute('''
                SELECT code, name FROM courses
                WHERE code IS NOT NULL AND status = 'active'
                ORDER BY code
            ''')
            for row in cursor.fetchall():
                courses.append({
                    'code': row['code'],
                    'name': row['name'],
                    'display': f"{row['code']} - {row['name']}"
                })

            existing_codes = {c['code'] for c in courses}

            # Get from degree_programs table
            cursor.execute('''
                SELECT program_code, program_name FROM degree_programs
                WHERE program_code IS NOT NULL AND is_active = 1
                ORDER BY program_code
            ''')
            for row in cursor.fetchall():
                if row['program_code'] not in existing_codes:
                    courses.append({
                        'code': row['program_code'],
                        'name': row['program_name'],
                        'display': f"{row['program_code']} - {row['program_name']}"
                    })
                    existing_codes.add(row['program_code'])

            # Also get distinct courses from students table (in case not in courses or degree_programs)
            cursor.execute('''
                SELECT DISTINCT course FROM students
                WHERE course IS NOT NULL AND course != ''
                ORDER BY course
            ''')
            for row in cursor.fetchall():
                if row['course'] not in existing_codes:
                    courses.append({
                        'code': row['course'],
                        'name': row['course'],
                        'display': row['course']
                    })

            conn.close()
        except Exception as e:
            print(f"Error getting courses: {e}")

        return courses

    def validate_course(self, course_code):
        """Validate if a course/program code exists in the database."""
        if not course_code:
            return False, "Course code is required"

        # Extract just the code if it's in "CODE - Name" or "CODE (Modules: ...)" format
        code = course_code.split(' - ')[0].strip()  # Handle "CODE - Name"
        code = code.split('(')[0].strip()  # Handle "CODE (Modules: ...)"
        code = code.upper()

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check in courses table first (main courses/modules table)
            cursor.execute('''
                SELECT code, name FROM courses
                WHERE UPPER(code) = ? OR UPPER(course_code) = ?
            ''', (code, code))
            result = cursor.fetchone()

            if result:
                conn.close()
                return True, f"Valid course: {result[0]} - {result[1]}"

            # Check in degree_programs table
            cursor.execute('''
                SELECT program_code, program_name FROM degree_programs
                WHERE UPPER(program_code) = ?
            ''', (code,))
            result = cursor.fetchone()

            if result:
                conn.close()
                return True, f"Valid program: {result[0]} - {result[1]}"

            # Also check if it's a course used in students table
            cursor.execute('''
                SELECT DISTINCT course FROM students
                WHERE UPPER(course) = ?
            ''', (code,))
            result = cursor.fetchone()
            conn.close()

            if result:
                return True, f"Valid course: {result[0]}"
            else:
                return False, f"Course '{code}' not found in the system"

        except Exception as e:
            return False, f"Error validating course: {str(e)}"

    def get_assignment_files(self, assignment_id, student_id):
        """Get files submitted for an assignment by a student."""
        files = []
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('''
                SELECT file_name, file_path, submitted_at
                FROM assignment_submissions
                WHERE assignment_id = ? AND student_id = ?
            ''', (assignment_id, student_id))
            files = [dict(row) for row in cursor.fetchall()]

            conn.close()
        except Exception as e:
            print(f"Error getting assignment files: {e}")

        return files
