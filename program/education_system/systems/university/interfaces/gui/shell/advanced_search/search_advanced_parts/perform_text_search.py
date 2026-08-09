"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_text_search(self, pattern, search_type, field):
    """Perform advanced text search"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if search_type == "wildcard":
            # Convert wildcard to SQL LIKE pattern
            sql_pattern = pattern.replace('*', '%').replace('?', '_')
            safe_field = validate_identifier(field, "column")
            query = "SELECT * FROM students WHERE [" + safe_field + "] LIKE ?"
            cursor.execute(query, (sql_pattern,))

        elif search_type == "regex":
            # For SQLite, we'll use LIKE with basic pattern conversion
            # In a full implementation, you'd need a regex extension
            sql_pattern = f"%{escape_like(pattern)}%"
            safe_field = validate_identifier(field, "column")
            query = "SELECT * FROM students WHERE [" + safe_field + "] LIKE ?"
            cursor.execute(query, (sql_pattern,))

        elif search_type == "all_fields":
            search_pattern = f"%{escape_like(pattern)}%"
            query = '''
            SELECT * FROM students WHERE
            student_id LIKE ? OR
            email_address LIKE ? OR
            first_name LIKE ? OR
            middle_name LIKE ? OR
            last_name LIKE ?
            '''
            params = [search_pattern] * 5
            cursor.execute(query, params)

        elif search_type == "phonetic":
            # Simple phonetic search implementation
            cursor.execute("SELECT * FROM students")
            all_students = cursor.fetchall()
            results = []

            def simple_soundex(word):
                if not word:
                    return "0000"
                word = word.upper()
                result = word[0]
                mapping = {'BFPV': '1', 'CGJKQSXZ': '2', 'DT': '3', 'L': '4', 'MN': '5', 'R': '6'}
                for char in word[1:]:
                    for key, value in mapping.items():
                        if char in key and result[-1] != value:
                            result += value
                            break
                return (result + '0000')[:4]

            target_soundex = simple_soundex(pattern)

            for student in all_students:
                if (simple_soundex(student[3]) == target_soundex or  # first_name
                    simple_soundex(student[5]) == target_soundex):   # last_name
                    results.append(student)

            conn.close()
            return results

        results = cursor.fetchall()
        conn.close()
        return results

    except Exception as e:
        raise Exception(f"Text search error: {str(e)}")
