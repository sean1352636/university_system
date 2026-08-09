"""Extracted function implementation."""

from .. import search_advanced_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def perform_combined_filters_search(self, filters):
    """
    Perform combined filters search with student data, modules, and date range.

    Args:
        filters (dict): Dictionary containing:
            - student_data: Dict with student field filters
            - module_codes: List of module codes
            - date_range: Dict with start and end dates
            - module_match_all: Bool for ALL vs ANY module matching

    Returns:
        list: List of matching student records
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Build query based on filters
        if filters["module_codes"] and filters["module_match_all"]:
            # ALL modules - need EXISTS for each module
            query = "SELECT s.* FROM students s WHERE 1=1"
            params = []

            # Student data filters
            for field, op, val in [
                ("student_id", "LIKE", f"%{escape_like(filters['student_data'].get('student_id', ''))}%"),
                ("first_name", "LIKE LOWER", f"%{escape_like(filters['student_data'].get('first_name', ''))}%"),
                ("last_name", "LIKE LOWER", f"%{escape_like(filters['student_data'].get('last_name', ''))}%"),
            ]:
                if filters["student_data"].get(field.replace('_', ' ').title().replace(' ', '')):
                    if "LOWER" in op:
                        query += f" AND LOWER(s.{field}) {op.replace(' LOWER', '')} ?"
                    else:
                        query += f" AND s.{field} {op} ?"
                    params.append(val)

            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender) = LOWER(?)"
                params.append(filters["student_data"]["gender"])

            if "course" in filters["student_data"]:
                query += " AND s.course = ?"
                params.append(filters["student_data"]["course"])

            if "age_min" in filters["student_data"]:
                query += " AND s.age >= ?"
                params.append(filters["student_data"]["age_min"])

            if "age_max" in filters["student_data"]:
                query += " AND s.age <= ?"
                params.append(filters["student_data"]["age_max"])

            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime >= ?"
                params.append(filters["date_range"]["start"])

            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime <= ?"
                params.append(filters["date_range"]["end"])

            # Add EXISTS clause for each module
            for code in filters["module_codes"]:
                query += """
                AND EXISTS (
                    SELECT 1 FROM student_modules sm
                    WHERE sm.student_id = s.student_id AND sm.module_code = ?
                )
                """
                params.append(code)

        else:
            # ANY modules or no modules
            query = "SELECT DISTINCT s.* FROM students s"
            params = []

            if filters["module_codes"]:
                query += " JOIN student_modules sm ON s.student_id = sm.student_id"

            query += " WHERE 1=1"

            # Student data filters
            for field, op in [
                ("student_id", "LIKE"),
                ("first_name", "LIKE LOWER"),
                ("last_name", "LIKE LOWER"),
            ]:
                filter_key = field
                if filters["student_data"].get(filter_key):
                    if "LOWER" in op:
                        query += f" AND LOWER(s.{field}) {op.replace(' LOWER', '')} ?"
                    else:
                        query += f" AND s.{field} {op} ?"
                    params.append(f"%{escape_like(filters['student_data'][filter_key])}%")

            if "gender" in filters["student_data"]:
                query += " AND LOWER(s.gender) = LOWER(?)"
                params.append(filters["student_data"]["gender"])

            if "course" in filters["student_data"]:
                query += " AND s.course = ?"
                params.append(filters["student_data"]["course"])

            if "age_min" in filters["student_data"]:
                query += " AND s.age >= ?"
                params.append(filters["student_data"]["age_min"])

            if "age_max" in filters["student_data"]:
                query += " AND s.age <= ?"
                params.append(filters["student_data"]["age_max"])

            if filters["date_range"]["start"]:
                query += " AND s.registration_datetime >= ?"
                params.append(filters["date_range"]["start"])

            if filters["date_range"]["end"]:
                query += " AND s.registration_datetime <= ?"
                params.append(filters["date_range"]["end"])

            if filters["module_codes"]:
                placeholders = ",".join("?" for _ in filters["module_codes"])
                query += f" AND sm.module_code IN ({placeholders})"
                params.extend(filters["module_codes"])

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return results

    except Exception as e:
        raise Exception(f"Combined filters search error: {str(e)}")
