"""Extracted class implementation."""

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
        """Calculate academic risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get average grades
            cursor.execute('''
                SELECT AVG(CAST(score as REAL) / CAST(max_score as REAL) * 100) as avg_grade
                FROM lms_gradebook
                WHERE student_id = ?
                AND graded_at >= date('now', '-3 months')
            ''', (student_id,))

            result = cursor.fetchone()
            avg_grade = result['avg_grade'] if result and result['avg_grade'] else 70

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
            cursor.execute('''
                SELECT AVG(attendance_percentage) as avg_attendance,
                       MAX(consecutive_absences) as max_consecutive
                FROM attendance_analytics
                WHERE student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()

            if not result or not result['avg_attendance']:
                return 0  # No data, assume no risk

            avg_attendance = result['avg_attendance']
            max_consecutive = result['max_consecutive'] or 0

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
    def _calculate_engagement_risk(student_id: str) -> int:
        """Calculate engagement risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Check LMS engagement
            cursor.execute('''
                SELECT COUNT(*) as video_views
                FROM lms_video_lectures
                WHERE video_id IN (
                    SELECT DISTINCT content_id FROM lms_course_content
                    WHERE lms_course_id IN (
                        SELECT lms_course_id FROM lms_courses WHERE module_code IN (
                            SELECT module_code FROM student_modules WHERE student_id = ?
                        )
                    )
                )
            ''', (student_id,))

            # Simple heuristic: if student has viewed videos recently, lower risk
            # In real system, would track actual student views, discussion participation, etc.

            return 30  # Placeholder

        finally:
            conn.close()

    @staticmethod
    def _calculate_financial_risk(student_id: str) -> int:
        """Calculate financial risk score (0-100)"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Check for outstanding fees
            cursor.execute('''
                SELECT COUNT(*) as unpaid_count
                FROM student_fees
                WHERE student_id = ? AND status = 'unpaid'
            ''', (student_id,))

            result = cursor.fetchone()
            unpaid_count = result['unpaid_count'] if result else 0

            if unpaid_count == 0:
                return 0
            elif unpaid_count <= 2:
                return 30
            else:
                return 70

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
