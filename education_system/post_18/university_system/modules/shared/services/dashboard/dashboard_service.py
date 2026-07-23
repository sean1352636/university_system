"""Dashboard service providing role-based dashboard data."""

import logging
from datetime import datetime, timedelta

from education_system.post_18.university_system.infrastructure.database.db import get_connection
from education_system.post_18.university_system.core.sql_safety import validate_table_name

logger = logging.getLogger(__name__)


class DashboardService:
    """Provides aggregated dashboard data for different user roles."""

    @staticmethod
    def get_student_dashboard_data(student_id):
        """Get dashboard data for a student.

        Returns dict with enrolled courses, upcoming assignments, GPA,
        office hour bookings, and TA assignments.
        """
        data = {
            'enrolled_courses': [],
            'upcoming_assignments': [],
            'gpa': None,
            'office_hour_bookings': [],
            'ta_assignments': [],
            'total_credits': 0,
        }

        try:
            with get_connection() as conn:
                # Enrolled modules (student_modules is the actual enrollment table)
                rows = conn.execute(
                    "SELECT m.module_code, m.module_name, m.module_type, m.credits "
                    "FROM modules m "
                    "INNER JOIN student_modules sm ON m.module_code = sm.module_code "
                    "WHERE sm.student_id = ? AND LOWER(sm.status) = 'enrolled'",
                    (student_id,)
                ).fetchall()
                data['enrolled_courses'] = [dict(r) for r in rows] if rows else []
                data['total_credits'] = sum(r['credits'] for r in data['enrolled_courses'] if r.get('credits')) if rows else 0

                # GPA from graded assignment submissions (numeric score -> 4.0 scale)
                try:
                    grade_rows = conn.execute(
                        "SELECT AVG(CASE "
                        "  WHEN s.grade >= 90 THEN 4.0 "
                        "  WHEN s.grade >= 80 THEN 3.0 "
                        "  WHEN s.grade >= 70 THEN 2.0 "
                        "  WHEN s.grade >= 60 THEN 1.0 "
                        "  ELSE 0.0 END) as gpa "
                        "FROM assignment_submissions s "
                        "WHERE s.student_id = ? AND s.grade IS NOT NULL",
                        (student_id,)
                    ).fetchone()
                    if grade_rows and grade_rows['gpa'] is not None:
                        data['gpa'] = round(grade_rows['gpa'], 2)
                except Exception:
                    logger.exception("Failed to calculate student GPA")

                # Upcoming assignments
                try:
                    assignment_rows = conn.execute(
                        "SELECT title, due_date, module_code FROM assignments "
                        "WHERE module_code IN "
                        "(SELECT module_code FROM student_modules WHERE student_id = ? AND LOWER(status) = 'enrolled') "
                        "AND due_date >= ? ORDER BY due_date LIMIT 10",
                        (student_id, datetime.now().strftime('%Y-%m-%d'))
                    ).fetchall()
                    data['upcoming_assignments'] = [dict(r) for r in assignment_rows] if assignment_rows else []
                except Exception:
                    logger.exception("Failed to fetch upcoming assignments")

                # Office hour bookings
                try:
                    booking_rows = conn.execute(
                        "SELECT b.id, b.booking_date, b.status, b.notes, "
                        "oh.instructor_id, oh.day_of_week, oh.start_time, oh.end_time, oh.location "
                        "FROM office_hour_bookings b "
                        "JOIN office_hours oh ON b.office_hour_id = oh.id "
                        "WHERE b.student_id = ? AND b.status = 'confirmed' "
                        "ORDER BY b.booking_date LIMIT 5",
                        (student_id,)
                    ).fetchall()
                    data['office_hour_bookings'] = [dict(r) for r in booking_rows] if booking_rows else []
                except Exception:
                    logger.exception("Failed to fetch office hour bookings")

                # TA assignments
                try:
                    ta_rows = conn.execute(
                        "SELECT module_code, role_type, hours_per_week, status "
                        "FROM teaching_assistants "
                        "WHERE student_id = ? AND status = 'active'",
                        (student_id,)
                    ).fetchall()
                    data['ta_assignments'] = [dict(r) for r in ta_rows] if ta_rows else []
                except Exception:
                    logger.exception("Failed to fetch TA assignments")

        except Exception as e:
            logger.error(f"Error fetching student dashboard data: {e}")

        return data

    @staticmethod
    def get_instructor_dashboard_data(instructor_id):
        """Get dashboard data for an instructor.

        Returns dict with courses taught, pending grading, enrollment counts,
        office hours, and TA assignments.
        """
        data = {
            'courses_taught': [],
            'total_students': 0,
            'pending_grading': 0,
            'office_hours': [],
            'upcoming_bookings': [],
            'ta_assignments': [],
            'at_risk_students': [],
            'grading_backlog': [],
            'announcements': [],
        }

        try:
            with get_connection() as conn:
                # Courses taught
                try:
                    course_rows = conn.execute(
                        "SELECT DISTINCT m.module_code, m.module_name, m.credits FROM modules m "
                        "LEFT JOIN module_schedule ms ON m.module_code = ms.module_code "
                        "WHERE m.instructor = ? OR ms.instructor_id = ? "
                        "OR m.module_code IN "
                        "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)",
                        (instructor_id, instructor_id, instructor_id)
                    ).fetchall()
                    data['courses_taught'] = [dict(r) for r in course_rows] if course_rows else []
                except Exception:
                    logger.exception("Failed to fetch courses taught by instructor")

                # Total enrolled students
                try:
                    count_row = conn.execute(
                        "SELECT COUNT(DISTINCT student_id) as cnt FROM student_modules "
                        "WHERE module_code IN "
                        "(SELECT module_code FROM module_schedule WHERE instructor_id = ?) "
                        "AND LOWER(status) = 'enrolled'",
                        (instructor_id,)
                    ).fetchone()
                    data['total_students'] = count_row['cnt'] if count_row else 0
                except Exception:
                    logger.exception("Failed to count total enrolled students")

                # Pending grading (assignments past due without grades)
                try:
                    pending_row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM assignments "
                        "WHERE module_code IN "
                        "(SELECT module_code FROM module_schedule WHERE instructor_id = ?) "
                        "AND due_date < ? AND status = 'active'",
                        (instructor_id, datetime.now().strftime('%Y-%m-%d'))
                    ).fetchone()
                    data['pending_grading'] = pending_row['cnt'] if pending_row else 0
                except Exception:
                    logger.exception("Failed to count pending grading items")

                # Office hours
                try:
                    oh_rows = conn.execute(
                        "SELECT id, day_of_week, start_time, end_time, location, capacity "
                        "FROM office_hours WHERE instructor_id = ? AND is_active = 1",
                        (instructor_id,)
                    ).fetchall()
                    data['office_hours'] = [dict(r) for r in oh_rows] if oh_rows else []
                except Exception:
                    logger.exception("Failed to fetch instructor office hours")

                # Upcoming bookings
                try:
                    booking_rows = conn.execute(
                        "SELECT b.id, b.student_id, b.booking_date, b.notes, "
                        "oh.day_of_week, oh.start_time, oh.end_time "
                        "FROM office_hour_bookings b "
                        "JOIN office_hours oh ON b.office_hour_id = oh.id "
                        "WHERE oh.instructor_id = ? AND b.status = 'confirmed' "
                        "AND b.booking_date >= ? ORDER BY b.booking_date LIMIT 10",
                        (instructor_id, datetime.now().strftime('%Y-%m-%d'))
                    ).fetchall()
                    data['upcoming_bookings'] = [dict(r) for r in booking_rows] if booking_rows else []
                except Exception:
                    logger.exception("Failed to fetch upcoming office hour bookings")

                # TAs assigned to instructor's courses
                try:
                    ta_rows = conn.execute(
                        "SELECT student_id, module_code, role_type, hours_per_week "
                        "FROM teaching_assistants "
                        "WHERE instructor_id = ? AND status = 'active'",
                        (instructor_id,)
                    ).fetchall()
                    data['ta_assignments'] = [dict(r) for r in ta_rows] if ta_rows else []
                except Exception:
                    logger.exception("Failed to fetch instructor TA assignments")

                # At-risk students in instructor's courses
                try:
                    risk_rows = conn.execute(
                        "SELECT ewp.student_id, s.first_name || ' ' || s.last_name as name, "
                        "sm.module_code, ewp.overall_risk_score, ewp.risk_level "
                        "FROM early_warning_profiles ewp "
                        "JOIN students s ON ewp.student_id = s.student_id "
                        "JOIN student_modules sm ON ewp.student_id = sm.student_id "
                        "JOIN modules m ON sm.module_code = m.module_code "
                        "WHERE (m.instructor = ? OR m.module_code IN "
                        "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)) "
                        "AND LOWER(sm.status) = 'enrolled' "
                        "AND ewp.risk_level IN ('critical', 'high', 'medium') "
                        "ORDER BY ewp.overall_risk_score DESC LIMIT 20",
                        (instructor_id, instructor_id)
                    ).fetchall()
                    data['at_risk_students'] = [dict(r) for r in risk_rows] if risk_rows else []
                except Exception:
                    logger.exception("Failed to fetch at-risk students for instructor")

                # Grading backlog (ungraded submissions)
                try:
                    backlog_rows = conn.execute(
                        "SELECT a.title as assignment, a.module_code, "
                        "COUNT(sub.id) as ungraded_count, a.due_date "
                        "FROM assignments a "
                        "JOIN assignment_submissions sub ON a.id = sub.assignment_id "
                        "JOIN modules m ON a.module_code = m.module_code "
                        "WHERE (m.instructor = ? OR m.module_code IN "
                        "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)) "
                        "AND sub.grade IS NULL "
                        "GROUP BY a.id ORDER BY a.due_date ASC LIMIT 15",
                        (instructor_id, instructor_id)
                    ).fetchall()
                    data['grading_backlog'] = [dict(r) for r in backlog_rows] if backlog_rows else []
                except Exception:
                    logger.exception("Failed to fetch grading backlog")

                # Recent announcements for instructor's courses
                try:
                    # announcements.creator_id is an integer FK to users.id, but
                    # the dashboard passes the username — resolve it first.
                    creator_row = conn.execute(
                        "SELECT id FROM users WHERE username = ?", (instructor_id,)
                    ).fetchone()
                    creator_id = creator_row['id'] if creator_row else instructor_id
                    ann_rows = conn.execute(
                        "SELECT id AS announcement_id, title, content, "
                        "CASE WHEN is_urgent = 1 THEN 'high' ELSE 'normal' END AS priority, "
                        "created_at "
                        "FROM announcements "
                        "WHERE creator_id = ? AND is_active = 1 "
                        "ORDER BY created_at DESC LIMIT 5",
                        (creator_id,)
                    ).fetchall()
                    data['announcements'] = [dict(r) for r in ann_rows] if ann_rows else []
                except Exception:
                    logger.exception("Failed to fetch instructor announcements")

        except Exception as e:
            logger.error(f"Error fetching instructor dashboard data: {e}")

        return data

    @staticmethod
    def get_at_risk_students_for_instructor(instructor_id):
        """Get at-risk students enrolled in instructor's courses."""
        results = []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT ewp.student_id, s.first_name || ' ' || s.last_name as name, "
                    "sm.module_code, ewp.overall_risk_score, ewp.risk_level, "
                    "ewp.academic_risk_score, ewp.attendance_risk_score "
                    "FROM early_warning_profiles ewp "
                    "JOIN students s ON ewp.student_id = s.student_id "
                    "JOIN student_modules sm ON ewp.student_id = sm.student_id "
                    "JOIN modules m ON sm.module_code = m.module_code "
                    "WHERE (m.instructor = ? OR m.module_code IN "
                    "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)) "
                    "AND LOWER(sm.status) = 'enrolled' "
                    "AND ewp.risk_level IN ('critical', 'high', 'medium') "
                    "ORDER BY ewp.overall_risk_score DESC",
                    (instructor_id, instructor_id)
                ).fetchall()
                results = [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching at-risk students: {e}")
        return results

    @staticmethod
    def get_grading_backlog(instructor_id):
        """Get ungraded assignment submissions for instructor's courses."""
        results = []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT a.id as assignment_id, a.title as assignment, a.module_code, "
                    "COUNT(sub.id) as ungraded_count, a.due_date "
                    "FROM assignments a "
                    "JOIN assignment_submissions sub ON a.id = sub.assignment_id "
                    "JOIN modules m ON a.module_code = m.module_code "
                    "WHERE (m.instructor = ? OR m.module_code IN "
                    "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)) "
                    "AND sub.grade IS NULL "
                    "GROUP BY a.id ORDER BY a.due_date ASC",
                    (instructor_id, instructor_id)
                ).fetchall()
                results = [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching grading backlog: {e}")
        return results

    @staticmethod
    def get_instructor_announcements(instructor_id):
        """Get announcements created by the instructor."""
        results = []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT announcement_id, title, content, priority, "
                    "created_at, is_active "
                    "FROM announcements "
                    "WHERE created_by = ? "
                    "ORDER BY created_at DESC LIMIT 20",
                    (instructor_id,)
                ).fetchall()
                results = [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching instructor announcements: {e}")
        return results

    @staticmethod
    def get_course_health_data(instructor_id, role=None):
        """Get health metrics for each course taught by the instructor."""
        results = []
        try:
            with get_connection() as conn:
                if role in ('staff', 'admin'):
                    courses = conn.execute(
                        "SELECT module_code, module_name FROM modules ORDER BY module_code"
                    ).fetchall()
                else:
                    courses = conn.execute(
                        "SELECT DISTINCT m.module_code, m.module_name FROM modules m "
                        "LEFT JOIN module_schedule ms ON m.module_code = ms.module_code "
                        "WHERE m.instructor = ? OR ms.instructor_id = ? "
                        "OR m.module_code IN "
                        "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)",
                        (instructor_id, instructor_id, instructor_id)
                    ).fetchall()

                for course in (courses or []):
                    mc = course['module_code']
                    info = {
                        'module_code': mc,
                        'module_name': course['module_name'],
                        'capacity': 0,
                        'enrolled': 0,
                        'avg_grade': None,
                        'attendance_rate': None,
                        'submission_rate': None,
                        'at_risk_count': 0,
                    }

                    try:
                        row = conn.execute(
                            "SELECT COUNT(*) as cnt FROM student_modules "
                            "WHERE module_code = ? AND LOWER(status) = 'enrolled'", (mc,)
                        ).fetchone()
                        info['enrolled'] = row['cnt'] if row else 0
                    except Exception:
                        logger.exception("Failed to count enrolled students for course %s", mc)

                    try:
                        row = conn.execute(
                            "SELECT ROUND(AVG(sub.grade), 1) as avg_g "
                            "FROM assignment_submissions sub "
                            "JOIN assignments a ON sub.assignment_id = a.id "
                            "WHERE a.module_code = ? AND sub.grade IS NOT NULL", (mc,)
                        ).fetchone()
                        info['avg_grade'] = row['avg_g'] if row and row['avg_g'] is not None else None
                    except Exception:
                        logger.exception("Failed to calculate average grade for course %s", mc)

                    try:
                        row = conn.execute(
                            "SELECT ROUND(AVG(attendance_percentage), 1) as avg_att "
                            "FROM attendance_analytics WHERE module_code = ?", (mc,)
                        ).fetchone()
                        info['attendance_rate'] = row['avg_att'] if row and row['avg_att'] is not None else None
                    except Exception:
                        logger.exception("Failed to fetch attendance rate for course %s", mc)

                    try:
                        total_row = conn.execute(
                            "SELECT COUNT(DISTINCT sm.student_id) as total "
                            "FROM student_modules sm "
                            "JOIN assignments a ON a.module_code = sm.module_code "
                            "WHERE sm.module_code = ? AND LOWER(sm.status) = 'enrolled'", (mc,)
                        ).fetchone()
                        sub_row = conn.execute(
                            "SELECT COUNT(DISTINCT sub.student_id) as submitted "
                            "FROM assignment_submissions sub "
                            "JOIN assignments a ON sub.assignment_id = a.id "
                            "WHERE a.module_code = ?", (mc,)
                        ).fetchone()
                        total = total_row['total'] if total_row else 0
                        submitted = sub_row['submitted'] if sub_row else 0
                        info['submission_rate'] = round((submitted / total) * 100, 1) if total > 0 else None
                    except Exception:
                        logger.exception("Failed to calculate submission rate for course %s", mc)

                    try:
                        row = conn.execute(
                            "SELECT COUNT(*) as cnt FROM early_warning_profiles ewp "
                            "JOIN student_modules sm ON ewp.student_id = sm.student_id "
                            "WHERE sm.module_code = ? AND LOWER(sm.status) = 'enrolled' "
                            "AND ewp.risk_level IN ('critical', 'high')", (mc,)
                        ).fetchone()
                        info['at_risk_count'] = row['cnt'] if row else 0
                    except Exception:
                        logger.exception("Failed to count at-risk students for course %s", mc)

                    results.append(info)
        except Exception as e:
            logger.error(f"Error fetching course health data: {e}")
        return results

    @staticmethod
    def get_semester_comparison_data(instructor_id):
        """Get comparison metrics between current and previous semester."""
        data = {'current': {}, 'previous': {}}
        try:
            now = datetime.now()
            # Approximate current semester: if month >= 8 => Fall, else Spring
            if now.month >= 8:
                curr_start = f"{now.year}-08-01"
                curr_end = f"{now.year}-12-31"
                prev_start = f"{now.year}-01-01"
                prev_end = f"{now.year}-07-31"
                data['current_label'] = f"Fall {now.year}"
                data['previous_label'] = f"Spring {now.year}"
            else:
                curr_start = f"{now.year}-01-01"
                curr_end = f"{now.year}-07-31"
                prev_start = f"{now.year - 1}-08-01"
                prev_end = f"{now.year - 1}-12-31"
                data['current_label'] = f"Spring {now.year}"
                data['previous_label'] = f"Fall {now.year - 1}"

            with get_connection() as conn:
                for label, start, end in [('current', curr_start, curr_end),
                                          ('previous', prev_start, prev_end)]:
                    semester = {'enrollment_count': 0, 'avg_grade': None,
                                'attendance_rate': None, 'submission_rate': None}
                    try:
                        row = conn.execute(
                            "SELECT COUNT(DISTINCT sm.student_id) as cnt "
                            "FROM student_modules sm "
                            "JOIN modules m ON sm.module_code = m.module_code "
                            "WHERE (m.instructor = ? OR m.module_code IN "
                            "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)) "
                            "AND LOWER(sm.status) = 'enrolled'",
                            (instructor_id, instructor_id)
                        ).fetchone()
                        semester['enrollment_count'] = row['cnt'] if row else 0
                    except Exception:
                        logger.exception("Failed to fetch semester enrollment count")

                    try:
                        row = conn.execute(
                            "SELECT ROUND(AVG(sub.grade), 1) as avg_g "
                            "FROM assignment_submissions sub "
                            "JOIN assignments a ON sub.assignment_id = a.id "
                            "JOIN modules m ON a.module_code = m.module_code "
                            "WHERE (m.instructor = ? OR m.module_code IN "
                            "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)) "
                            "AND sub.grade IS NOT NULL "
                            "AND sub.graded_date BETWEEN ? AND ?",
                            (instructor_id, instructor_id, start, end)
                        ).fetchone()
                        semester['avg_grade'] = row['avg_g'] if row and row['avg_g'] is not None else None
                    except Exception:
                        logger.exception("Failed to fetch semester average grade")

                    try:
                        row = conn.execute(
                            "SELECT ROUND(AVG(aa.attendance_percentage), 1) as avg_att "
                            "FROM attendance_analytics aa "
                            "JOIN modules m ON aa.module_code = m.module_code "
                            "WHERE (m.instructor = ? OR m.module_code IN "
                            "(SELECT module_code FROM instructor_modules WHERE instructor_id = ?)) "
                            "AND aa.last_updated BETWEEN ? AND ?",
                            (instructor_id, instructor_id, start, end)
                        ).fetchone()
                        semester['attendance_rate'] = row['avg_att'] if row and row['avg_att'] is not None else None
                    except Exception:
                        logger.exception("Failed to fetch semester attendance rate")

                    data[label] = semester
        except Exception as e:
            logger.error(f"Error fetching semester comparison data: {e}")
        return data

    @staticmethod
    def get_admin_dashboard_data():
        """Get dashboard data for an admin.

        Returns dict with system totals, recent registrations,
        pending approvals, and financial summary.
        """
        data = {
            'total_students': 0,
            'total_instructors': 0,
            'total_courses': 0,
            'total_active_enrollments': 0,
            'recent_registrations': [],
            'system_stats': {},
            'financial_summary': {},
        }

        try:
            with get_connection() as conn:
                # Total students
                row = conn.execute("SELECT COUNT(*) as cnt FROM students").fetchone()
                data['total_students'] = row['cnt'] if row else 0

                # Total instructors (staff role in users table)
                try:
                    row = conn.execute("SELECT COUNT(*) as cnt FROM users WHERE role = 'staff'").fetchone()
                    data['total_instructors'] = row['cnt'] if row else 0
                except Exception:
                    logger.exception("Failed to count total instructors")

                # Total courses (real courses, excluding auto-generated module mirrors)
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM courses WHERE id NOT LIKE 'course_%'"
                    ).fetchone()
                    data['total_courses'] = row['cnt'] if row else 0
                except Exception:
                    logger.exception("Failed to count total courses")

                # Active enrollments
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM student_modules WHERE status IN ('Enrolled', 'enrolled')"
                    ).fetchone()
                    data['total_active_enrollments'] = row['cnt'] if row else 0
                except Exception:
                    logger.exception("Failed to count active enrollments")

                # Recent registrations (last 7 days)
                try:
                    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    recent = conn.execute(
                        "SELECT student_id, first_name || ' ' || last_name as name, "
                        "registration_datetime as created_at FROM students "
                        "WHERE registration_datetime >= ? ORDER BY registration_datetime DESC LIMIT 10",
                        (week_ago,)
                    ).fetchall()
                    data['recent_registrations'] = [dict(r) for r in recent] if recent else []
                except Exception:
                    logger.exception("Failed to fetch recent registrations")

                # System stats
                try:
                    users_row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
                    data['system_stats']['total_users'] = users_row['cnt'] if users_row else 0
                except Exception:
                    logger.exception("Failed to fetch system stats user count")

                # Financial summary
                try:
                    fin_row = conn.execute(
                        "SELECT SUM(amount) as total FROM payments WHERE status = 'completed'"
                    ).fetchone()
                    data['financial_summary']['total_payments'] = fin_row['total'] if fin_row and fin_row['total'] else 0
                except Exception:
                    logger.exception("Failed to fetch financial summary")

        except Exception as e:
            logger.error(f"Error fetching admin dashboard data: {e}")

        return data

    @staticmethod
    def get_login_analytics():
        """Get user access and login analytics data.

        Returns dict with login trends, failed login analysis,
        user activity patterns, and MFA adoption rates.
        """
        data = {
            'daily_login_trends': [],
            'failed_logins_by_user': [],
            'hourly_activity': [],
            'mfa_adoption': {'enabled': 0, 'disabled': 0, 'total': 0, 'rate_pct': 0.0},
            'top_failed_ips': [],
            'recent_failed_logins': [],
            'success_rate': {'total': 0, 'successful': 0, 'failed': 0, 'rate_pct': 0.0},
            'active_users_24h': 0,
            'active_users_7d': 0,
        }

        try:
            with get_connection() as conn:
                # Daily login trends (last 30 days)
                try:
                    rows = conn.execute(
                        "SELECT DATE(attempt_time) as day, "
                        "SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful, "
                        "SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed, "
                        "COUNT(*) as total "
                        "FROM login_attempts "
                        "WHERE attempt_time >= datetime('now', '-30 days') "
                        "GROUP BY DATE(attempt_time) ORDER BY day"
                    ).fetchall()
                    data['daily_login_trends'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch daily login trends")

                # Top users with failed logins (last 7 days)
                try:
                    rows = conn.execute(
                        "SELECT username, COUNT(*) as fail_count, "
                        "MAX(attempt_time) as last_attempt "
                        "FROM login_attempts "
                        "WHERE success = 0 AND attempt_time >= datetime('now', '-7 days') "
                        "GROUP BY username ORDER BY fail_count DESC LIMIT 15"
                    ).fetchall()
                    data['failed_logins_by_user'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch failed logins by user")

                # Hourly activity pattern (last 7 days)
                try:
                    rows = conn.execute(
                        "SELECT CAST(strftime('%H', attempt_time) AS INTEGER) as hour, "
                        "COUNT(*) as count "
                        "FROM login_attempts "
                        "WHERE attempt_time >= datetime('now', '-7 days') "
                        "GROUP BY hour ORDER BY hour"
                    ).fetchall()
                    data['hourly_activity'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch hourly activity pattern")

                # MFA adoption rates
                try:
                    row = conn.execute(
                        "SELECT "
                        "SUM(CASE WHEN two_fa_enabled = 1 THEN 1 ELSE 0 END) as enabled, "
                        "SUM(CASE WHEN two_fa_enabled = 0 OR two_fa_enabled IS NULL THEN 1 ELSE 0 END) as disabled, "
                        "COUNT(*) as total "
                        "FROM user_accounts WHERE is_active = 1"
                    ).fetchone()
                    if row:
                        enabled = row['enabled'] or 0
                        total = row['total'] or 0
                        data['mfa_adoption'] = {
                            'enabled': enabled,
                            'disabled': row['disabled'] or 0,
                            'total': total,
                            'rate_pct': round((enabled / total) * 100, 1) if total > 0 else 0.0,
                        }
                except Exception:
                    logger.exception("Failed to fetch MFA adoption rates")

                # Top IPs with failed logins
                try:
                    rows = conn.execute(
                        "SELECT ip_address, COUNT(*) as fail_count "
                        "FROM login_attempts "
                        "WHERE success = 0 AND ip_address IS NOT NULL "
                        "AND attempt_time >= datetime('now', '-7 days') "
                        "GROUP BY ip_address ORDER BY fail_count DESC LIMIT 10"
                    ).fetchall()
                    data['top_failed_ips'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch top failed login IPs")

                # Recent failed login attempts
                try:
                    rows = conn.execute(
                        "SELECT username, attempt_time, ip_address "
                        "FROM login_attempts "
                        "WHERE success = 0 ORDER BY attempt_time DESC LIMIT 20"
                    ).fetchall()
                    data['recent_failed_logins'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch recent failed logins")

                # Overall success rate (last 30 days)
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) as total, "
                        "SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful, "
                        "SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed "
                        "FROM login_attempts "
                        "WHERE attempt_time >= datetime('now', '-30 days')"
                    ).fetchone()
                    if row:
                        total = row['total'] or 0
                        successful = row['successful'] or 0
                        data['success_rate'] = {
                            'total': total,
                            'successful': successful,
                            'failed': row['failed'] or 0,
                            'rate_pct': round((successful / total) * 100, 1) if total > 0 else 0.0,
                        }
                except Exception:
                    logger.exception("Failed to calculate login success rate")

                # Active users (24h and 7d)
                try:
                    row = conn.execute(
                        "SELECT COUNT(DISTINCT username) as cnt FROM login_attempts "
                        "WHERE success = 1 AND attempt_time >= datetime('now', '-24 hours')"
                    ).fetchone()
                    data['active_users_24h'] = row['cnt'] if row else 0
                except Exception:
                    logger.exception("Failed to count active users in last 24 hours")

                try:
                    row = conn.execute(
                        "SELECT COUNT(DISTINCT username) as cnt FROM login_attempts "
                        "WHERE success = 1 AND attempt_time >= datetime('now', '-7 days')"
                    ).fetchone()
                    data['active_users_7d'] = row['cnt'] if row else 0
                except Exception:
                    logger.exception("Failed to count active users in last 7 days")

        except Exception as e:
            logger.error(f"Error fetching login analytics: {e}")

        return data

    @staticmethod
    def get_operational_metrics():
        """Get domain-specific operational dashboard metrics.

        Returns dict with course utilization, grade distributions,
        student retention, financial aid funnel, and support ticket stats.
        """
        data = {
            'course_utilization': [],
            'grade_distribution': [],
            'grade_distribution_by_instructor': [],
            'retention_metrics': {
                'total_students': 0, 'active_students': 0,
                'dropped_students': 0, 'retention_rate_pct': 0.0,
            },
            'financial_aid_funnel': {
                'total_applications': 0, 'pending': 0, 'approved': 0,
                'disbursed': 0, 'cancelled': 0,
                'total_awarded': 0.0, 'total_disbursed': 0.0,
            },
            'ticket_stats': {
                'total': 0, 'open': 0, 'in_progress': 0,
                'resolved': 0, 'closed': 0,
                'avg_resolution_hours': None,
            },
            'tickets_by_category': [],
            'tickets_by_priority': [],
        }

        try:
            with get_connection() as conn:
                # Course utilization (enrollment count vs capacity from courses table)
                try:
                    rows = conn.execute(
                        "SELECT c.course_code as module_code, c.course_name as module_name, "
                        "c.max_enrollment as capacity, "
                        "c.current_enrollment as enrolled, "
                        "CASE WHEN c.max_enrollment > 0 "
                        "  THEN ROUND(c.current_enrollment * 100.0 / c.max_enrollment, 1) "
                        "  ELSE 0 END as utilization_pct "
                        "FROM courses c "
                        "ORDER BY utilization_pct DESC"
                    ).fetchall()
                    data['course_utilization'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch course utilization data")

                # Grade distribution (overall)
                try:
                    rows = conn.execute(
                        "SELECT "
                        "CASE "
                        "  WHEN grade >= 90 THEN 'A (90-100)' "
                        "  WHEN grade >= 80 THEN 'B (80-89)' "
                        "  WHEN grade >= 70 THEN 'C (70-79)' "
                        "  WHEN grade >= 60 THEN 'D (60-69)' "
                        "  ELSE 'F (<60)' END as grade_band, "
                        "COUNT(*) as count "
                        "FROM assignment_submissions "
                        "WHERE grade IS NOT NULL "
                        "GROUP BY grade_band ORDER BY grade_band"
                    ).fetchall()
                    data['grade_distribution'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch overall grade distribution")

                # Grade distribution by instructor
                try:
                    rows = conn.execute(
                        "SELECT COALESCE(i.first_name || ' ' || i.last_name, "
                        "  'Instructor #' || ms.instructor_id) as instructor, "
                        "ROUND(AVG(s.grade), 1) as avg_grade, "
                        "COUNT(s.id) as submissions_graded, "
                        "MIN(s.grade) as min_grade, MAX(s.grade) as max_grade "
                        "FROM assignment_submissions s "
                        "JOIN assignments a ON s.assignment_id = a.id "
                        "JOIN module_schedule ms ON a.module_code = ms.module_code "
                        "LEFT JOIN instructors i ON ms.instructor_id = i.id "
                        "WHERE s.grade IS NOT NULL "
                        "GROUP BY ms.instructor_id ORDER BY avg_grade DESC"
                    ).fetchall()
                    data['grade_distribution_by_instructor'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch grade distribution by instructor")

                # Student retention metrics
                try:
                    total_row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM students"
                    ).fetchone()
                    total = total_row['cnt'] if total_row else 0

                    active_row = conn.execute(
                        "SELECT COUNT(DISTINCT student_id) as cnt FROM student_modules "
                        "WHERE status IN ('Enrolled', 'enrolled')"
                    ).fetchone()
                    active = active_row['cnt'] if active_row else 0

                    dropped_row = conn.execute(
                        "SELECT COUNT(DISTINCT student_id) as cnt FROM student_modules "
                        "WHERE status IN ('Dropped', 'dropped', 'Withdrawn', 'withdrawn')"
                    ).fetchone()
                    dropped = dropped_row['cnt'] if dropped_row else 0

                    data['retention_metrics'] = {
                        'total_students': total,
                        'active_students': active,
                        'dropped_students': dropped,
                        'retention_rate_pct': round((active / total) * 100, 1) if total > 0 else 0.0,
                    }
                except Exception:
                    logger.exception("Failed to calculate student retention metrics")

                # Financial aid funnel
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) as total, "
                        "SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending, "
                        "SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved, "
                        "SUM(CASE WHEN status = 'disbursed' THEN 1 ELSE 0 END) as disbursed, "
                        "SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled, "
                        "COALESCE(SUM(awarded_amount), 0) as total_awarded, "
                        "COALESCE(SUM(disbursed_amount), 0) as total_disbursed "
                        "FROM student_financial_aid"
                    ).fetchone()
                    if row:
                        data['financial_aid_funnel'] = {
                            'total_applications': row['total'] or 0,
                            'pending': row['pending'] or 0,
                            'approved': row['approved'] or 0,
                            'disbursed': row['disbursed'] or 0,
                            'cancelled': row['cancelled'] or 0,
                            'total_awarded': row['total_awarded'] or 0.0,
                            'total_disbursed': row['total_disbursed'] or 0.0,
                        }
                except Exception:
                    logger.exception("Failed to fetch financial aid funnel data")

                # Support ticket stats
                try:
                    row = conn.execute(
                        "SELECT COUNT(*) as total, "
                        "SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count, "
                        "SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress, "
                        "SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved, "
                        "SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed "
                        "FROM support_tickets"
                    ).fetchone()
                    if row:
                        data['ticket_stats'] = {
                            'total': row['total'] or 0,
                            'open': row['open_count'] or 0,
                            'in_progress': row['in_progress'] or 0,
                            'resolved': row['resolved'] or 0,
                            'closed': row['closed'] or 0,
                            'avg_resolution_hours': None,
                        }

                    # Average resolution time
                    res_row = conn.execute(
                        "SELECT AVG("
                        "  (julianday(resolved_at) - julianday(created_at)) * 24"
                        ") as avg_hours "
                        "FROM support_tickets "
                        "WHERE resolved_at IS NOT NULL AND created_at IS NOT NULL"
                    ).fetchone()
                    if res_row and res_row['avg_hours'] is not None:
                        data['ticket_stats']['avg_resolution_hours'] = round(res_row['avg_hours'], 1)
                except Exception:
                    logger.exception("Failed to fetch support ticket stats")

                # Tickets by category
                try:
                    rows = conn.execute(
                        "SELECT category, COUNT(*) as count "
                        "FROM support_tickets GROUP BY category ORDER BY count DESC"
                    ).fetchall()
                    data['tickets_by_category'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch tickets by category")

                # Tickets by priority
                try:
                    rows = conn.execute(
                        "SELECT priority, COUNT(*) as count "
                        "FROM support_tickets GROUP BY priority ORDER BY count DESC"
                    ).fetchall()
                    data['tickets_by_priority'] = [dict(r) for r in rows] if rows else []
                except Exception:
                    logger.exception("Failed to fetch tickets by priority")

        except Exception as e:
            logger.error(f"Error fetching operational metrics: {e}")

        return data

    @staticmethod
    def get_system_health_data():
        """Get real-time system health monitoring data.

        Returns dict with active sessions, connection pool status,
        query performance stats, and error rates.
        """
        data = {
            'pool_stats': {},
            'query_stats': {},
            'active_sessions_24h': 0,
            'error_rate': {'total_queries': 0, 'slow_queries': 0, 'error_count': 0},
            'db_size_mb': 0.0,
            'table_row_counts': [],
        }

        # Connection pool metrics
        try:
            from education_system.post_18.university_system.infrastructure.database.pool_metrics import get_pool_metrics
            collector = get_pool_metrics()
            data['pool_stats'] = collector.get_stats()
        except Exception as e:
            logger.debug(f"Pool metrics unavailable: {e}")

        # Query performance stats
        try:
            from education_system.post_18.university_system.infrastructure.database.query_monitor import get_query_monitor
            monitor = get_query_monitor()
            stats = monitor.get_stats()
            data['query_stats'] = stats
            data['error_rate']['total_queries'] = stats.get('total_queries', 0)
            data['error_rate']['slow_queries'] = stats.get('slow_queries', 0)
        except Exception as e:
            logger.debug(f"Query monitor unavailable: {e}")

        try:
            with get_connection() as conn:
                # Active sessions (unique successful logins in 24h)
                try:
                    row = conn.execute(
                        "SELECT COUNT(DISTINCT username) as cnt FROM login_attempts "
                        "WHERE success = 1 AND attempt_time >= datetime('now', '-24 hours')"
                    ).fetchone()
                    data['active_sessions_24h'] = row['cnt'] if row else 0
                except Exception:
                    logger.exception("Failed to count active sessions in last 24 hours")

                # Database file size
                try:
                    row = conn.execute("PRAGMA page_count").fetchone()
                    page_count = row[0] if row else 0
                    row2 = conn.execute("PRAGMA page_size").fetchone()
                    page_size = row2[0] if row2 else 0
                    data['db_size_mb'] = round((page_count * page_size) / (1024 * 1024), 2)
                except Exception:
                    logger.exception("Failed to calculate database file size")

                # Table row counts for key tables
                key_tables = [
                    'users', 'students', 'modules', 'student_modules',
                    'assignments', 'assignment_submissions', 'login_attempts',
                    'support_tickets', 'payments',
                ]
                for table in key_tables:
                    try:
                        safe_table = validate_table_name(table)
                        row = conn.execute("SELECT COUNT(*) as cnt FROM [" + safe_table + "]").fetchone()
                        data['table_row_counts'].append({
                            'table': table, 'rows': row['cnt'] if row else 0
                        })
                    except Exception:
                        logger.exception("Failed to count rows in table %s", table)

        except Exception as e:
            logger.error(f"Error fetching system health data: {e}")

        return data

    @staticmethod
    def get_student_grades_summary(student_id):
        """Get per-module grade averages for dashboard widget."""
        results = []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT a.module_code, m.module_name, "
                    "ROUND(AVG(s.grade), 1) as avg_grade, COUNT(s.id) as graded_count "
                    "FROM assignment_submissions s "
                    "JOIN assignments a ON s.assignment_id = a.id "
                    "JOIN modules m ON a.module_code = m.module_code "
                    "WHERE s.student_id = ? AND s.grade IS NOT NULL "
                    "GROUP BY a.module_code ORDER BY a.module_code",
                    (student_id,),
                ).fetchall()
                results = [dict(r) for r in rows] if rows else []
        except Exception as e:
            logger.error(f"Error fetching student grades summary: {e}")
        return results

    @staticmethod
    def get_student_financial_summary(student_id):
        """Get balance and upcoming payment deadlines for dashboard widget."""
        data = {"balance": 0.0, "upcoming_deadlines": [], "has_overdue": False}
        try:
            with get_connection() as conn:
                try:
                    acct = conn.execute(
                        "SELECT balance FROM student_finance_accounts "
                        "WHERE student_id = ?",
                        (student_id,),
                    ).fetchone()
                    data["balance"] = acct["balance"] if acct else 0.0
                except Exception:
                    logger.exception("Failed to fetch student finance account balance")

                try:
                    today = datetime.now().strftime("%Y-%m-%d")
                    rows = conn.execute(
                        "SELECT description, amount, due_date, "
                        "CASE WHEN due_date < ? THEN 1 ELSE 0 END as is_overdue "
                        "FROM payment_schedule "
                        "WHERE student_id = ? AND status = 'pending' "
                        "ORDER BY due_date LIMIT 5",
                        (today, student_id),
                    ).fetchall()
                    data["upcoming_deadlines"] = [dict(r) for r in rows] if rows else []
                    data["has_overdue"] = any(
                        r.get("is_overdue") for r in data["upcoming_deadlines"]
                    )
                except Exception:
                    logger.exception("Failed to fetch upcoming payment deadlines")
        except Exception as e:
            logger.error(f"Error fetching student financial summary: {e}")
        return data
