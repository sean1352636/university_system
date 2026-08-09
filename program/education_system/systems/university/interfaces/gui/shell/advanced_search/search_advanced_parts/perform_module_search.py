"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_module_search(self, module_codes, match_type):
    """Perform module enrollment search"""
    try:
        conn = get_connection()
        if not conn:
            raise Exception("Database connection failed")

        cursor = conn.cursor()

        if match_type == "all":
            # Students enrolled in ALL modules
            query = "SELECT s.* FROM students s WHERE "
            conditions = []
            params = []

            for module_code in module_codes:
                conditions.append("""
                EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
                """)
                params.append(module_code)

            query += " AND ".join(conditions)
        else:
            # Students enrolled in ANY module
            placeholders = ",".join(["?" for _ in module_codes])
            query = f"""
            SELECT DISTINCT s.* FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code IN ({placeholders})
            """
            params = module_codes

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Module search error: {str(e)}")
