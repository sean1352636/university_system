"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_search_all_fields(self, search_term):
    """Search across all text fields"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        search_pattern = f"%{escape_like(search_term.lower())}%"
        query = """
        SELECT * FROM students WHERE
        LOWER(student_id) LIKE ? OR
        LOWER(email_address) LIKE ? OR
        LOWER(title) LIKE ? OR
        LOWER(first_name) LIKE ? OR
        LOWER(middle_name) LIKE ? OR
        LOWER(last_name) LIKE ? OR
        LOWER(gender) LIKE ? OR
        LOWER(course) LIKE ? OR
        LOWER(registration_datetime) LIKE ?
        """

        params = [search_pattern] * 9
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Search all fields error: {str(e)}")
