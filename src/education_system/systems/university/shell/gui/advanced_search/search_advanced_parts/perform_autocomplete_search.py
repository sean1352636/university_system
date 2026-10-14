"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_autocomplete_search(self, term):
    """Perform auto-complete search"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        SELECT * FROM students
        WHERE LOWER(first_name || ' ' || last_name) LIKE ?
           OR LOWER(email_address) LIKE ?
           OR LOWER(student_id) LIKE ?
        """
        params = [f'%{term.lower()}%'] * 3

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Auto-complete search error: {str(e)}")
