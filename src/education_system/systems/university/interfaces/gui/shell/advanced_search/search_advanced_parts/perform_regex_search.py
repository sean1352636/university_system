"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_regex_search(self, pattern, field):
    """Perform regular expression search"""
    try:
        import re
        conn = get_connection()
        cursor = conn.cursor()

        # Get all records and filter with regex
        cursor.execute("SELECT * FROM students")
        all_students = cursor.fetchall()
        conn.close()

        matched_students = []
        compiled_pattern = re.compile(pattern, re.IGNORECASE)

        field_index_map = {
            'student_id': 0, 'email': 1, 'title': 2,
            'first_name': 3, 'middle_name': 4, 'last_name': 5,
            'gender': 6, 'date_of_birth': 7, 'age': 8,
            'course': 9, 'registration_datetime': 10
        }

        field_index = field_index_map.get(field, 3)  # Default to first_name

        for student in all_students:
            if field_index < len(student) and student[field_index]:
                if compiled_pattern.search(str(student[field_index])):
                    matched_students.append(student)

        return matched_students

    except Exception as e:
        raise Exception(f"Regex search error: {str(e)}")
