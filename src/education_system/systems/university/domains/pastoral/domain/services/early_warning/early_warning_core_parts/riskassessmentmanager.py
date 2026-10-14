"""Extracted class implementation."""
import logging

logger = logging.getLogger(__name__)

from .. import early_warning_core_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class RiskAssessmentManager:
    """Manages risk assessment and student profiles"""

    @staticmethod
    def calculate_risk_score(student_id: str) -> Tuple[int, str]:
        """
        Calculate overall risk score for a student

        Returns:
            Tuple of (risk_score, risk_level)
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Calculate academic risk (40% weight)
            academic_risk = RiskAssessmentManager._calculate_academic_risk(student_id)

            # Calculate attendance risk (30% weight)
            attendance_risk = RiskAssessmentManager._calculate_attendance_risk(student_id)

            # Calculate engagement risk (20% weight)
            engagement_risk = RiskAssessmentManager._calculate_engagement_risk(student_id)

            # Calculate financial risk (10% weight)
            financial_risk = RiskAssessmentManager._calculate_financial_risk(student_id)

            # Calculate weighted overall risk
            overall_risk = (
                academic_risk * 0.4 +
                attendance_risk * 0.3 +
                engagement_risk * 0.2 +
                financial_risk * 0.1
            )

            # Determine risk level
            if overall_risk >= 70:
                risk_level = 'critical'
            elif overall_risk >= 50:
                risk_level = 'high'
            elif overall_risk >= 30:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            # Update or create risk profile
            cursor.execute('''
                INSERT OR REPLACE INTO early_warning_profiles (
                    student_id, overall_risk_score, risk_level,
                    academic_risk_score, attendance_risk_score,
                    engagement_risk_score, financial_risk_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, int(overall_risk), risk_level, int(academic_risk),
                  int(attendance_risk), int(engagement_risk), int(financial_risk)))

            conn.commit()

            return int(overall_risk), risk_level

        finally:
            conn.close()

    @staticmethod
    def _calculate_academic_risk(student_id: str) -> int:
        """Calculate academic risk score (0-100) from recorded grades.

        Reads ``grades`` and ``student_grades`` — the tables marks are
        actually written to. It previously read ``lms_gradebook``, which is
        empty, so the "no rows" branch defaulted the average to 70 and every
        student scored 0 academic risk regardless of how they were doing.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT AVG(pct) AS avg_grade, COUNT(*) AS n FROM (
                    SELECT COALESCE(
                               percentage,
                               CASE WHEN COALESCE(max_points, 0) > 0
                                    THEN points_earned * 100.0 / max_points END,
                               score
                           ) AS pct
                    FROM grades WHERE student_id = ?
                    UNION ALL
                    SELECT percentage AS pct
                    FROM student_grades WHERE student_id = ?
                )
                WHERE pct IS NOT NULL
            ''', (student_id, student_id))

            result = cursor.fetchone()
            if not result or not result['n']:
                # No marks recorded — no evidence either way, so no risk. This
                # is not the same as scoring well, and it is why a brand-new
                # student sits at 0 rather than being flagged.
                return 0

            avg_grade = result['avg_grade'] or 0

            # Convert grade to risk (lower grade = higher risk)
            if avg_grade >= 70:
                return 0
            elif avg_grade >= 60:
                return 30
            elif avg_grade >= 50:
                return 60
            else:
                return 90

        finally:
            conn.close()

    @staticmethod
    def _calculate_attendance_risk(student_id: str) -> int:
        """Calculate attendance risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Computed from attendance_records, the table check-ins are
            # written to. It previously read attendance_analytics — an empty
            # summary table nothing populates — so this always returned 0.
            cursor.execute('''
                SELECT
                    SUM(CASE WHEN LOWER(status) IN ('present','late','excused')
                             THEN 1 ELSE 0 END) AS attended,
                    COUNT(*) AS total
                FROM attendance_records
                WHERE student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            total = (result['total'] if result else 0) or 0
            if not total:
                return 0  # Never registered anywhere — no evidence of risk.

            avg_attendance = (result['attended'] or 0) * 100.0 / total
            max_consecutive = RiskAssessmentManager._max_consecutive_absences(
                cursor, student_id)

            # Calculate risk based on attendance
            attendance_risk = 0

            if avg_attendance >= 90:
                attendance_risk = 0
            elif avg_attendance >= 75:
                attendance_risk = 20
            elif avg_attendance >= 60:
                attendance_risk = 50
            else:
                attendance_risk = 80

            # Add risk for consecutive absences
            if max_consecutive >= 5:
                attendance_risk += 20
            elif max_consecutive >= 3:
                attendance_risk += 10

            return min(attendance_risk, 100)

        finally:
            conn.close()

    @staticmethod
    def _max_consecutive_absences(cursor, student_id: str) -> int:
        """Longest run of consecutive absences in the student's record."""
        cursor.execute('''
            SELECT status FROM attendance_records
            WHERE student_id = ? ORDER BY date
        ''', (student_id,))
        longest = run = 0
        for row in cursor.fetchall():
            if str(row['status'] or '').strip().lower() == 'absent':
                run += 1
                longest = max(longest, run)
            else:
                run = 0
        return longest

    @staticmethod
    def _calculate_engagement_risk(student_id: str) -> int:
        """Calculate engagement risk score (0-100) from submission behaviour.

        This used to run an LMS query, throw the result away and
        ``return 30`` — a placeholder. Because it was a constant, it was the
        *only* component contributing anything, which is why every student
        scored exactly 6 overall (30 × the 0.2 engagement weight).

        Submission behaviour is the engagement signal this database actually
        has: how much of the work set for a student's modules they have
        handed in, and whether it arrives late.
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT COUNT(*) AS expected FROM assignments
                WHERE module_code IN (
                    SELECT module_code FROM student_modules WHERE student_id = ?
                )
            ''', (student_id,))
            row = cursor.fetchone()
            expected = (row['expected'] if row else 0) or 0
            if not expected:
                # Nothing has been set, so nothing can be missed.
                return 0

            cursor.execute('''
                SELECT COUNT(DISTINCT assignment_id) AS submitted,
                       SUM(CASE WHEN late_submission THEN 1 ELSE 0 END) AS late
                FROM assignment_submissions
                WHERE student_id = ?
            ''', (student_id,))
            row = cursor.fetchone()
            submitted = (row['submitted'] if row else 0) or 0
            late = (row['late'] if row else 0) or 0

            rate = min(submitted / expected, 1.0)
            if rate >= 0.9:
                risk = 0
            elif rate >= 0.7:
                risk = 20
            elif rate >= 0.5:
                risk = 50
            else:
                risk = 80

            if late:
                # Handing work in, but late, is a weaker signal than not
                # handing it in at all — a nudge, not a jump.
                risk += 10

            return min(risk, 100)

        finally:
            conn.close()

    @staticmethod
    def _calculate_financial_risk(student_id: str) -> int:
        """Calculate financial risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Outstanding fees. 'overdue' counts as well as 'unpaid' — only
            # matching 'unpaid' missed the state that actually matters.
            cursor.execute('''
                SELECT COUNT(*) as unpaid_count
                FROM student_fees
                WHERE student_id = ?
                  AND LOWER(COALESCE(status, '')) IN ('unpaid', 'overdue', 'pending')
            ''', (student_id,))
            result = cursor.fetchone()
            unpaid_count = (result['unpaid_count'] if result else 0) or 0

            if unpaid_count == 0:
                risk = 0
            elif unpaid_count <= 2:
                risk = 30
            else:
                risk = 70

            # The finance system raises its own alerts, and they are a far
            # stronger signal than a fee row's status: an active
            # 'payment_overdue' or 'high_risk_student' alert is finance
            # already having decided this student is a concern.
            try:
                cursor.execute('''
                    SELECT COUNT(*) AS active,
                           SUM(CASE WHEN LOWER(COALESCE(priority,'')) IN ('high','critical')
                                    THEN 1 ELSE 0 END) AS urgent
                    FROM financial_alerts
                    WHERE student_id = ?
                      AND LOWER(COALESCE(status, '')) = 'active'
                ''', (student_id,))
                row = cursor.fetchone()
                active = (row['active'] if row else 0) or 0
                urgent = (row['urgent'] if row else 0) or 0
                if urgent:
                    risk = max(risk, 70)
                elif active:
                    risk = max(risk, 40)
            except Exception:
                # financial_alerts is optional — absent on a lean install.
                logger.debug("Suppressed exception", exc_info=True)

            return min(risk, 100)

        finally:
            conn.close()

    @staticmethod
    def get_at_risk_students(risk_level: str = "high") -> List[Dict[str, Any]]:
        """Get list of at-risk students"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            if risk_level == "high":
                condition = "p.risk_level IN ('high', 'critical')"
            elif risk_level == "critical":
                condition = "p.risk_level = 'critical'"
            elif risk_level == "medium":
                condition = "p.risk_level IN ('medium', 'high', 'critical')"
            elif risk_level == "low":
                condition = "p.risk_level = 'low'"
            elif risk_level == "all":
                # Show ALL students with LEFT JOIN to include those without profiles
                cursor.execute('''
                    SELECT s.student_id, s.first_name, s.last_name, s.email_address, s.course,
                           COALESCE(p.overall_risk_score, 0) as overall_risk_score,
                           COALESCE(p.risk_level, 'not assessed') as risk_level,
                           COALESCE(p.academic_risk_score, 0) as academic_risk_score,
                           COALESCE(p.attendance_risk_score, 0) as attendance_risk_score,
                           COALESCE(p.engagement_risk_score, 0) as engagement_risk_score,
                           COALESCE(p.financial_risk_score, 0) as financial_risk_score
                    FROM students s
                    LEFT JOIN early_warning_profiles p ON s.student_id = p.student_id
                    ORDER BY p.overall_risk_score DESC NULLS LAST, s.last_name, s.first_name
                ''')
                return [dict(row) for row in cursor.fetchall()]
            else:
                condition = "1=1"

            cursor.execute('''
                SELECT p.*, s.first_name, s.last_name, s.email_address, s.course
                FROM early_warning_profiles p
                JOIN students s ON p.student_id = s.student_id
                WHERE ''' + condition + '''
                ORDER BY p.overall_risk_score DESC
            ''')

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()
