"""Extract academic history from source system databases for student transfers."""

import json
import sqlite3


def extract_primary_history(primary_db_path, pupil_id):
    """Extract academic history for a pupil from the primary school system.

    Args:
        primary_db_path: Path to primary_school.db
        pupil_id: The pupil's TEXT id (e.g. 'PRI0001')

    Returns dict with grades_summary, attendance_summary, sats_results, phonics_results.
    """
    conn = sqlite3.connect(str(primary_db_path))
    conn.row_factory = sqlite3.Row
    result = {"source_system": "primary", "source_student_id": pupil_id}

    try:
        # Assessments
        rows = conn.execute(
            "SELECT subject_code, assessment_type, level, score, max_score, term, academic_year, year_group "
            "FROM assessments WHERE pupil_id = ? ORDER BY academic_year, term",
            (pupil_id,)
        ).fetchall()
        result["grades_summary"] = [dict(r) for r in rows]
    except Exception:
        result["grades_summary"] = []

    try:
        # SATs results
        rows = conn.execute(
            "SELECT academic_year, key_stage, subject, raw_score, scaled_score, outcome, teacher_assessment "
            "FROM sats_results WHERE pupil_id = ? ORDER BY academic_year",
            (pupil_id,)
        ).fetchall()
        result["sats_results"] = [dict(r) for r in rows]
    except Exception:
        result["sats_results"] = []

    try:
        # Phonics results
        rows = conn.execute(
            "SELECT academic_year, year_group, score, threshold, passed "
            "FROM phonics_results WHERE pupil_id = ? ORDER BY academic_year",
            (pupil_id,)
        ).fetchall()
        result["phonics_results"] = [dict(r) for r in rows]
    except Exception:
        result["phonics_results"] = []

    try:
        # Attendance summary
        total = conn.execute(
            "SELECT COUNT(*) as total FROM attendance_records WHERE pupil_id = ?",
            (pupil_id,)
        ).fetchone()["total"]
        present = conn.execute(
            "SELECT COUNT(*) as cnt FROM attendance_records WHERE pupil_id = ? AND status IN ('Present', 'Late')",
            (pupil_id,)
        ).fetchone()["cnt"]
        auth_absent = conn.execute(
            "SELECT COUNT(*) as cnt FROM attendance_records WHERE pupil_id = ? AND status = 'Authorised Absence'",
            (pupil_id,)
        ).fetchone()["cnt"]
        unauth_absent = conn.execute(
            "SELECT COUNT(*) as cnt FROM attendance_records WHERE pupil_id = ? AND status = 'Unauthorised Absence'",
            (pupil_id,)
        ).fetchone()["cnt"]
        result["attendance_summary"] = {
            "total_sessions": total,
            "present": present,
            "absent_authorised": auth_absent,
            "absent_unauthorised": unauth_absent,
            "percentage": round(present / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        result["attendance_summary"] = {}

    conn.close()
    return result


def extract_secondary_history(secondary_db_path, student_pk):
    """Extract academic history for a student from the secondary school system.

    Args:
        secondary_db_path: Path to secondary_school.db
        student_pk: The student's INTEGER primary key (id)

    Returns dict with grades_summary, attendance_summary.
    """
    conn = sqlite3.connect(str(secondary_db_path))
    conn.row_factory = sqlite3.Row
    result = {"source_system": "secondary"}

    try:
        # Get student_id text
        stu = conn.execute("SELECT student_id FROM students WHERE id = ?", (student_pk,)).fetchone()
        result["source_student_id"] = stu["student_id"] if stu else str(student_pk)
    except Exception:
        result["source_student_id"] = str(student_pk)

    try:
        # Grades
        rows = conn.execute(
            "SELECT g.assessment_type, g.assessment_name, g.score, g.grade, g.term, g.academic_year, "
            "s.title as subject_name, s.subject_code "
            "FROM grades g LEFT JOIN subjects s ON g.subject_id = s.id "
            "WHERE g.student_id = ? ORDER BY g.academic_year, g.term",
            (student_pk,)
        ).fetchall()
        result["grades_summary"] = [dict(r) for r in rows]
    except Exception:
        result["grades_summary"] = []

    try:
        # Exam results
        rows = conn.execute(
            "SELECT e.exam_name, e.subject_id, er.marks_obtained, er.grade "
            "FROM exam_results er JOIN exams e ON er.exam_id = e.id "
            "WHERE er.student_id = ? ORDER BY e.exam_date",
            (student_pk,)
        ).fetchall()
        result["exam_results"] = [dict(r) for r in rows]
    except Exception:
        result["exam_results"] = []

    try:
        # Attendance summary
        total = conn.execute(
            "SELECT COUNT(*) as total FROM attendance_records WHERE student_id = ?",
            (student_pk,)
        ).fetchone()["total"]
        present = conn.execute(
            "SELECT COUNT(*) as cnt FROM attendance_records WHERE student_id = ? AND status IN ('present', 'late')",
            (student_pk,)
        ).fetchone()["cnt"]
        auth_absent = conn.execute(
            "SELECT COUNT(*) as cnt FROM attendance_records WHERE student_id = ? AND status = 'authorised'",
            (student_pk,)
        ).fetchone()["cnt"]
        unauth_absent = conn.execute(
            "SELECT COUNT(*) as cnt FROM attendance_records WHERE student_id = ? AND status = 'unauthorised'",
            (student_pk,)
        ).fetchone()["cnt"]
        result["attendance_summary"] = {
            "total_sessions": total,
            "present": present,
            "absent_authorised": auth_absent,
            "absent_unauthorised": unauth_absent,
            "percentage": round(present / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        result["attendance_summary"] = {}

    conn.close()
    return result


def extract_college_history(college_db_path, student_pk):
    """Extract academic history for a student from the college system.

    Args:
        college_db_path: Path to sixthform.db
        student_pk: The student's INTEGER primary key (id)

    Returns dict with grades_summary, attendance_summary.
    """
    conn = sqlite3.connect(str(college_db_path))
    conn.row_factory = sqlite3.Row
    result = {"source_system": "college"}

    try:
        stu = conn.execute("SELECT student_id FROM students WHERE id = ?", (student_pk,)).fetchone()
        result["source_student_id"] = stu["student_id"] if stu else str(student_pk)
    except Exception:
        result["source_student_id"] = str(student_pk)

    try:
        # Grades
        rows = conn.execute(
            "SELECT g.score, g.letter_grade, g.semester, g.grade_type, g.predicted_grade, g.term, "
            "c.course_code, c.title as course_name "
            "FROM grades g LEFT JOIN courses c ON g.course_id = c.id "
            "WHERE g.student_id = ? ORDER BY g.semester, g.term",
            (student_pk,)
        ).fetchall()
        result["grades_summary"] = [dict(r) for r in rows]
    except Exception:
        result["grades_summary"] = []

    try:
        # Attendance summary (two-table join)
        total = conn.execute(
            "SELECT COUNT(*) as total FROM attendance_records ar "
            "JOIN attendance_sessions s ON ar.session_id = s.id "
            "WHERE ar.student_id = ?",
            (student_pk,)
        ).fetchone()["total"]
        present = conn.execute(
            "SELECT COUNT(*) as cnt FROM attendance_records ar "
            "JOIN attendance_sessions s ON ar.session_id = s.id "
            "WHERE ar.student_id = ? AND ar.status IN ('present', 'late')",
            (student_pk,)
        ).fetchone()["cnt"]
        result["attendance_summary"] = {
            "total_sessions": total,
            "present": present,
            "percentage": round(present / total * 100, 1) if total > 0 else 0,
        }
    except Exception:
        result["attendance_summary"] = {}

    conn.close()
    return result
