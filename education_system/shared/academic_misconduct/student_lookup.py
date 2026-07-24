"""Student lookup and course validation for the Academic Misconduct Panel.

System-aware: handles different table schemas across university, college,
secondary, and primary systems.

Schema differences:
  University:  students(student_id PK, first_name, last_name, email_address, course)
  College:     students(student_id UNIQUE, first_name, last_name, email, major)
  Secondary:   students(student_id UNIQUE, first_name, last_name, email, year_group, form_group)
  Primary:     pupils(pupil_id UNIQUE, first_name, last_name, class_name, year_group)
               (no email on pupils; parent emails in parent1_email)
"""

from education_system.shared.academic_misconduct._imports import tk, messagebox, _t, sqlite3


def _table_exists(cursor, table_name):
    """Check whether *table_name* exists in the connected database."""
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


# Per-system student lookup queries.  Each returns (name, email, course).
# The queries are tried in order; the first one that finds a row wins.

_STUDENT_QUERIES = {
    'university': [
        # University: students table with email_address and course columns
        (
            "students",
            "SELECT first_name, last_name, email_address AS email, course "
            "FROM students WHERE student_id = ?",
            lambda row: (
                f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(),
                row['email'] or '',
                row['course'] or '',
            ),
        ),
    ],
    'sixth_form': [
        # College: students table with email and major columns
        (
            "students",
            "SELECT first_name, last_name, email, major "
            "FROM students WHERE student_id = ?",
            lambda row: (
                f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(),
                row['email'] or '',
                row['major'] or '',
            ),
        ),
    ],
    'secondary': [
        # Secondary: students table with email, year_group, form_group
        (
            "students",
            "SELECT first_name, last_name, email, year_group, form_group "
            "FROM students WHERE student_id = ?",
            lambda row: (
                f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(),
                row['email'] or '',
                f"Year {row['year_group'] or '?'}" + (f" ({row['form_group']})" if row['form_group'] else ''),
            ),
        ),
    ],
    'primary': [
        # Primary: pupils table with pupil_id, no direct email
        (
            "pupils",
            "SELECT first_name, last_name, parent1_email, class_name, year_group "
            "FROM pupils WHERE pupil_id = ?",
            lambda row: (
                f"{row['first_name'] or ''} {row['last_name'] or ''}".strip(),
                row['parent1_email'] or '',
                f"{row['year_group'] or '?'}" + (f" ({row['class_name']})" if row['class_name'] else ''),
            ),
        ),
    ],
}

# Fallback chain: try all systems in order if system_key is None (superadmin)
_FALLBACK_ORDER = ['university', 'sixth_form', 'secondary', 'primary']


class MisconductStudentLookupMixin:
    """Mixin providing student lookup and course validation."""

    def _get_student_queries(self):
        """Return the ordered list of (table, sql, extractor) tuples for the current system."""
        system_key = getattr(self, 'system_key', None)
        if system_key and system_key in _STUDENT_QUERIES:
            return _STUDENT_QUERIES[system_key]
        # Superadmin: try all systems
        queries = []
        for sk in _FALLBACK_ORDER:
            queries.extend(_STUDENT_QUERIES[sk])
        return queries

    def lookup_student(self, student_id_entry, entries):
        """Look up student by ID and auto-fill details including course."""
        student_id = student_id_entry.get().strip()
        if not student_id:
            messagebox.showwarning(_t("misconduct.msg_titles.missing_id"), "Please enter a Student ID to look up.")
            return

        try:
            conn = sqlite3.connect(self._get_system_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            student_name = None
            student_email = None
            student_course = None

            # Try system-specific queries
            for table_name, sql, extractor in self._get_student_queries():
                if not _table_exists(cursor, table_name):
                    continue
                try:
                    cursor.execute(sql, (student_id,))
                    row = cursor.fetchone()
                    if row:
                        student_name, student_email, student_course = extractor(row)
                        break
                except Exception:
                    continue

            # Fallback: try users table (present in all systems via shared auth)
            if not student_name:
                try:
                    cursor.execute(
                        "SELECT username, email FROM users WHERE id = ? OR username = ?",
                        (student_id, student_id),
                    )
                    user = cursor.fetchone()
                    if user:
                        student_name = user['username'] or ''
                        student_email = user['email'] or ''
                except Exception:
                    pass

            # Get enrolled modules (university/college only)
            modules_list = []
            if _table_exists(cursor, 'student_modules'):
                try:
                    cursor.execute(
                        "SELECT DISTINCT module_code FROM student_modules WHERE student_id = ?",
                        (student_id,),
                    )
                    modules_list = [m['module_code'] for m in cursor.fetchall()]
                except Exception:
                    pass

            conn.close()

            if student_name:
                if 'student' in entries:
                    entries['student'].delete(0, tk.END)
                    entries['student'].insert(0, student_name)
                if 'student_email' in entries:
                    entries['student_email'].delete(0, tk.END)
                    entries['student_email'].insert(0, student_email)
                if 'course' in entries and student_course:
                    entries['course'].delete(0, tk.END)
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
        """Get assignments/homework for a student from the database.

        Schema differences:
          University:  assignments(module_code, title, due_date, is_active)
          College:     assignments(course_id, title, due_date)
          Secondary:   homework(subject_id, title, due_date, status)
          Primary:     homework(class_name, subject_code, title, due_date, status)
        """
        assignments = []
        try:
            conn = sqlite3.connect(self._get_system_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            system_key = getattr(self, 'system_key', None)
            has_assignments = _table_exists(cursor, 'assignments')
            has_homework = _table_exists(cursor, 'homework')

            if not has_assignments and not has_homework:
                conn.close()
                return assignments

            if system_key in ('secondary', 'primary') and has_homework:
                # Secondary/Primary use a homework table
                if not student_id:
                    cursor.execute('''
                        SELECT id, title, due_date
                        FROM homework
                        WHERE status = 'active' OR status = 'Active'
                        ORDER BY due_date DESC
                        LIMIT 50
                    ''')
                else:
                    # No direct student-homework link; return all active
                    cursor.execute('''
                        SELECT id, title, due_date
                        FROM homework
                        WHERE status = 'active' OR status = 'Active'
                        ORDER BY due_date DESC
                        LIMIT 50
                    ''')
                assignments = [dict(row) for row in cursor.fetchall()]

            elif system_key == 'sixth_form' and has_assignments:
                # College: assignments with course_id (no module_code)
                if not student_id:
                    cursor.execute('''
                        SELECT id, title, due_date
                        FROM assignments
                        ORDER BY due_date DESC
                        LIMIT 50
                    ''')
                    assignments = [dict(row) for row in cursor.fetchall()]
                else:
                    # Fallback: all assignments
                    cursor.execute('''
                        SELECT id, title, due_date
                        FROM assignments
                        ORDER BY due_date DESC
                        LIMIT 50
                    ''')
                    assignments = [dict(row) for row in cursor.fetchall()]

            elif has_assignments:
                # University: assignments with module_code, is_active
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
                    # Try submission join
                    if _table_exists(cursor, 'assignment_submissions'):
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

                    # Try enrolled modules
                    if not assignments and _table_exists(cursor, 'student_modules'):
                        cursor.execute('''
                            SELECT DISTINCT a.id, a.title, a.module_code, a.due_date
                            FROM assignments a
                            INNER JOIN student_modules sm ON a.module_code = sm.module_code
                            WHERE sm.student_id = ?
                            ORDER BY a.due_date DESC
                            LIMIT 50
                        ''', (student_id,))
                        assignments = [dict(row) for row in cursor.fetchall()]

                    # Fallback: all active assignments
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
            conn = sqlite3.connect(self._get_system_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            existing_codes = set()

            system_key = getattr(self, 'system_key', None)

            # University / College: courses table
            if _table_exists(cursor, 'courses'):
                try:
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
                        existing_codes.add(row['code'])
                except Exception:
                    pass

            # University: degree_programs
            if _table_exists(cursor, 'degree_programs'):
                try:
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
                except Exception:
                    pass

            # Get distinct courses/majors from the students or pupils table
            if system_key == 'primary' and _table_exists(cursor, 'pupils'):
                try:
                    cursor.execute('''
                        SELECT DISTINCT class_name FROM pupils
                        WHERE class_name IS NOT NULL AND class_name != ''
                        ORDER BY class_name
                    ''')
                    for row in cursor.fetchall():
                        val = row['class_name']
                        if val not in existing_codes:
                            courses.append({'code': val, 'name': val, 'display': val})
                            existing_codes.add(val)
                except Exception:
                    pass
            elif system_key == 'secondary' and _table_exists(cursor, 'students'):
                try:
                    cursor.execute('''
                        SELECT DISTINCT form_group FROM students
                        WHERE form_group IS NOT NULL AND form_group != ''
                        ORDER BY form_group
                    ''')
                    for row in cursor.fetchall():
                        val = row['form_group']
                        if val not in existing_codes:
                            courses.append({'code': val, 'name': val, 'display': val})
                            existing_codes.add(val)
                except Exception:
                    pass
            elif system_key == 'sixth_form' and _table_exists(cursor, 'students'):
                try:
                    cursor.execute('''
                        SELECT DISTINCT major FROM students
                        WHERE major IS NOT NULL AND major != ''
                        ORDER BY major
                    ''')
                    for row in cursor.fetchall():
                        val = row['major']
                        if val not in existing_codes:
                            courses.append({'code': val, 'name': val, 'display': val})
                            existing_codes.add(val)
                except Exception:
                    pass
            elif _table_exists(cursor, 'students'):
                # University or fallback
                try:
                    cursor.execute('''
                        SELECT DISTINCT course FROM students
                        WHERE course IS NOT NULL AND course != ''
                        ORDER BY course
                    ''')
                    for row in cursor.fetchall():
                        val = row['course']
                        if val not in existing_codes:
                            courses.append({'code': val, 'name': val, 'display': val})
                            existing_codes.add(val)
                except Exception:
                    pass

            conn.close()
        except Exception as e:
            print(f"Error getting courses: {e}")

        return courses

    def validate_course(self, course_code):
        """Validate if a course/program code exists in the database."""
        if not course_code:
            return False, "Course code is required"

        code = course_code.split(' - ')[0].strip()
        code = code.split('(')[0].strip()
        code_upper = code.upper()

        try:
            conn = sqlite3.connect(self._get_system_db_path())
            cursor = conn.cursor()

            system_key = getattr(self, 'system_key', None)

            # Try courses table (university/college)
            if _table_exists(cursor, 'courses'):
                try:
                    cursor.execute(
                        "SELECT code, name FROM courses WHERE UPPER(code) = ?",
                        (code_upper,),
                    )
                    result = cursor.fetchone()
                    if result:
                        conn.close()
                        return True, f"Valid course: {result[0]} - {result[1]}"
                except Exception:
                    pass

            # University: degree_programs
            if _table_exists(cursor, 'degree_programs'):
                try:
                    cursor.execute(
                        "SELECT program_code, program_name FROM degree_programs WHERE UPPER(program_code) = ?",
                        (code_upper,),
                    )
                    result = cursor.fetchone()
                    if result:
                        conn.close()
                        return True, f"Valid program: {result[0]} - {result[1]}"
                except Exception:
                    pass

            # System-specific student/pupil table check
            if system_key == 'primary' and _table_exists(cursor, 'pupils'):
                cursor.execute(
                    "SELECT DISTINCT class_name FROM pupils WHERE UPPER(class_name) = ?",
                    (code_upper,),
                )
                result = cursor.fetchone()
                if result:
                    conn.close()
                    return True, f"Valid class: {result[0]}"
            elif system_key == 'secondary' and _table_exists(cursor, 'students'):
                cursor.execute(
                    "SELECT DISTINCT form_group FROM students WHERE UPPER(form_group) = ?",
                    (code_upper,),
                )
                result = cursor.fetchone()
                if result:
                    conn.close()
                    return True, f"Valid form group: {result[0]}"
            elif system_key == 'sixth_form' and _table_exists(cursor, 'students'):
                cursor.execute(
                    "SELECT DISTINCT major FROM students WHERE UPPER(major) = ?",
                    (code_upper,),
                )
                result = cursor.fetchone()
                if result:
                    conn.close()
                    return True, f"Valid major: {result[0]}"
            elif _table_exists(cursor, 'students'):
                cursor.execute(
                    "SELECT DISTINCT course FROM students WHERE UPPER(course) = ?",
                    (code_upper,),
                )
                result = cursor.fetchone()
                if result:
                    conn.close()
                    return True, f"Valid course: {result[0]}"

            conn.close()
            return False, f"Course '{code}' not found in the system"

        except Exception as e:
            return False, f"Error validating course: {str(e)}"

    def get_assignment_files(self, assignment_id, student_id):
        """Get files submitted for an assignment by a student."""
        files = []
        try:
            conn = sqlite3.connect(self._get_system_db_path())
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if not _table_exists(cursor, 'assignment_submissions'):
                conn.close()
                return files

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
