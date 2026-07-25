"""Core attendance record CRUD operations."""

import datetime
from education_system.systems.university.infrastructure.database.db import get_connection


def get_modules():
    """Get list of available modules"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Check if student_modules table exists and has module_name column
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='student_modules'")
        student_modules_exists = cursor.fetchone() is not None

        if student_modules_exists:
            # Check if module_name column exists
            cursor.execute("PRAGMA table_info(student_modules)")
            columns = [row[1] for row in cursor.fetchall()]
            has_module_name = 'module_name' in columns

            if has_module_name:
                # Use the original query with module_name
                cursor.execute('''
                SELECT module_code,
                       COALESCE(MAX(module_name), module_code) as module_name
                FROM (
                    SELECT DISTINCT module_code, NULL as module_name
                    FROM attendance_records
                    UNION ALL
                    SELECT DISTINCT module_code, module_name
                    FROM student_modules
                )
                GROUP BY module_code
                ORDER BY module_code
                ''')
            else:
                # Use simplified query without module_name
                cursor.execute('''
                SELECT DISTINCT module_code, module_code as module_name
                FROM (
                    SELECT DISTINCT module_code FROM attendance_records
                    UNION
                    SELECT DISTINCT module_code FROM student_modules
                )
                ORDER BY module_code
                ''')
        else:
            # Only use attendance_records
            cursor.execute('''
            SELECT DISTINCT module_code, module_code as module_name
            FROM attendance_records
            ORDER BY module_code
            ''')

        modules = cursor.fetchall()
        conn.close()

        return modules

    except Exception as e:
        print(f"Error getting modules: {e}")
        return []


def get_attendance_records(student_id=None, module_code=None, date_from=None, date_to=None):
    """Get attendance records with optional filters"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = '''
        SELECT ar.student_id, s.first_name, s.last_name, ar.module_code,
               ar.id, ar.date, ar.status, ar.notes
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.student_id
        WHERE 1=1
        '''

        params = []

        if student_id:
            query += ' AND ar.student_id = ?'
            params.append(student_id)

        if module_code:
            query += ' AND ar.module_code = ?'
            params.append(module_code)

        if date_from:
            query += ' AND ar.date >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND ar.date <= ?'
            params.append(date_to)

        query += ' ORDER BY ar.date DESC, ar.student_id'

        cursor.execute(query, params)
        records = cursor.fetchall()
        conn.close()

        return records

    except Exception as e:
        print(f"Error getting attendance records: {e}")
        return []


def get_student_attendance(student_id, module_code=None):
    """Get student attendance statistics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        if module_code:
            query = '''
            SELECT ar.module_code,
                   COUNT(*) as total_sessions,
                   SUM(CASE WHEN ar.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
                   AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as percentage
            FROM attendance_records ar
            WHERE ar.student_id = ? AND ar.module_code = ?
            GROUP BY ar.module_code
            '''
            cursor.execute(query, (student_id, module_code))
        else:
            query = '''
            SELECT ar.module_code,
                   COUNT(*) as total_sessions,
                   SUM(CASE WHEN ar.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
                   AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as percentage
            FROM attendance_records ar
            WHERE ar.student_id = ?
            GROUP BY ar.module_code
            '''
            cursor.execute(query, (student_id,))

        results = cursor.fetchall()
        conn.close()

        stats = {}
        for module_code, total, attended, percentage in results:
            stats[module_code] = {
                'total_sessions': total,
                'attended': attended,
                'percentage': percentage or 0
            }

        return stats

    except Exception as e:
        print(f"Error getting student attendance: {e}")
        return {}


def get_module_attendance(module_code):
    """Get module attendance statistics"""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Overall module stats
        cursor.execute('''
        SELECT
            COUNT(DISTINCT ar.student_id) as total_students,
            COUNT(*) as total_sessions,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as overall_percentage
        FROM attendance_records ar
        WHERE ar.module_code = ?
        ''', (module_code,))

        overall_stats = cursor.fetchone()

        # Per student stats
        cursor.execute('''
        SELECT
            ar.student_id,
            s.first_name,
            s.last_name,
            COUNT(*) as sessions,
            SUM(CASE WHEN ar.status IN ('Present', 'Late') THEN 1 ELSE 0 END) as attended,
            AVG(CASE WHEN ar.status IN ('Present', 'Late') THEN 1.0 ELSE 0.0 END) * 100 as percentage
        FROM attendance_records ar
        JOIN students s ON ar.student_id = s.student_id
        WHERE ar.module_code = ?
        GROUP BY ar.student_id, s.first_name, s.last_name
        ORDER BY percentage DESC
        ''', (module_code,))

        student_stats = cursor.fetchall()
        conn.close()

        return {
            'total_students': overall_stats[0] or 0,
            'total_sessions': overall_stats[1] or 0,
            'overall_percentage': overall_stats[2] or 0,
            'students': [
                {
                    'student_id': row[0],
                    'name': f"{row[1]} {row[2]}",
                    'sessions': row[3],
                    'attended': row[4],
                    'percentage': row[5] or 0
                }
                for row in student_stats
            ]
        }

    except Exception as e:
        print(f"Error getting module attendance: {e}")
        return {'total_students': 0, 'total_sessions': 0, 'overall_percentage': 0, 'students': []}


def record_attendance(module_code, date, attendance_data, recorded_by="System"):
    """Record attendance for multiple students.

    Find-or-creates an ``attendance_sessions`` row from ``module_schedule``
    for the given (module, date) so each ``attendance_records`` row is
    stamped with a ``session_id``. If no module_schedule slot exists for
    the date, the records are still written (without a session_id) so
    ad-hoc / makeup sessions don't fail.
    """
    session_id = None
    try:
        from education_system.systems.university.domain.academics.services.course_management.attendance_sessions_sync import (
            find_or_create_session,
        )
        session_id = find_or_create_session(module_code, date)
    except Exception as _exc:
        # Best-effort — don't block recording on session resolution.
        pass

    affected_students: list[str] = []
    try:
        conn = get_connection()
        cursor = conn.cursor()

        for student_id, status, notes in attendance_data:
            cursor.execute('''
            INSERT OR REPLACE INTO attendance_records
            (student_id, module_code, date, status, notes, recorded_by,
             recorded_at, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, module_code, date, status, notes, recorded_by,
                  datetime.datetime.now().isoformat(), session_id))
            affected_students.append(str(student_id))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"Error recording attendance: {e}")
        return False

    # Recompute each affected student's running attendance % for this
    # module and route through attendance_bus when below threshold.
    # Best-effort — we already committed the writes, so a flag failure
    # cannot fail the user-facing call.
    try:
        from education_system.systems.university.services.bus.attendance_bus import (
            flag_student_concern,
        )
        threshold = 70.0
        conn2 = get_connection()
        for sid in set(affected_students):
            row = conn2.execute(
                "SELECT "
                "  SUM(CASE WHEN LOWER(status) IN ('present','late','excused') "
                "           THEN 1 ELSE 0 END) AS attended, "
                "  COUNT(*) AS total "
                "FROM attendance_records "
                "WHERE student_id = ? AND module_code = ?",
                (sid, module_code),
            ).fetchone()
            if not row or not row[1]:
                continue
            pct = (float(row[0] or 0) / float(row[1])) * 100.0
            if pct < threshold:
                flag_student_concern(
                    sid, threshold_pct=pct,
                    description=(
                        f"Auto: {pct:.0f}% attendance in {module_code}"
                    ),
                    opened_by=recorded_by,
                )
        conn2.close()
    except Exception:
        pass

    return True
