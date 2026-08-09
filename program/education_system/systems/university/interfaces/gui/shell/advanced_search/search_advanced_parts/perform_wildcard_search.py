"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_wildcard_search(self, pattern, field):
    """Perform wildcard search (* and ?)"""
    try:
        import fnmatch
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        matched_students = []
        field_index_map = {
            'student_id': 0, 'email': 1, 'first_name': 3,
            'last_name': 5, 'course': 9
        }

        field_index = field_index_map.get(field, 3)

        for student in all_students:
            if field_index < len(student) and student[field_index]:
                if fnmatch.fnmatch(str(student[field_index]).lower(), pattern.lower()):
                    matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Wildcard search error: {str(e)}")
