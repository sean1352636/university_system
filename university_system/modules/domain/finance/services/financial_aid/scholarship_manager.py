"""
Scholarship Manager
Handles scholarship opportunities, applications, and awards
"""

import sqlite3
import json
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from university_system.modules.shared.constants.paths import DEFAULT_DB_PATH


class ScholarshipManager:
    """Manager for scholarship operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def create_scholarship(
        self,
        name: str,
        amount: float,
        description: Optional[str] = None,
        scholarship_type: str = 'merit',
        amount_type: str = 'fixed',
        eligibility_criteria: Optional[Dict] = None,
        min_gpa: Optional[float] = None,
        deadline: Optional[date] = None,
        renewable: bool = False,
        max_renewals: Optional[int] = None,
        available_count: Optional[int] = None,
        donor_name: Optional[str] = None,
        academic_year: Optional[str] = None,
        criteria: Optional[str] = None
    ) -> Optional[int]:
        """Create a new scholarship"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Use the actual GUI database schema (scholarship_name, criteria, academic_year, etc.)
                cursor.execute("""
                    INSERT INTO scholarships (
                        scholarship_name, description, amount, academic_year,
                        criteria, deadline, is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (name, description, amount, academic_year,
                      criteria, deadline))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error creating scholarship: {e}")
            return None

    def submit_application(
        self,
        scholarship_id: int,
        student_id: int,
        academic_year: Optional[str] = None,
        application_data: Optional[Dict[str, Any]] = None,
        essay_text: Optional[str] = None,
        gpa: Optional[float] = None,
        transcript_url: Optional[str] = None,
        resume_url: Optional[str] = None
    ) -> Optional[int]:
        """
        Submit scholarship application

        Args:
            scholarship_id: ID of scholarship
            student_id: Student ID
            academic_year: Academic year (stored for reference, not in applications table)
            application_data: Dict containing application data (alternative to individual params)
            essay_text: Essay text (or from application_data)
            gpa: Student GPA (or from application_data)
            transcript_url: Transcript URL (or from application_data)
            resume_url: Resume URL (or from application_data)

        Returns:
            Application ID if successful, None otherwise
        """
        try:
            # Extract from application_data if provided
            if application_data:
                essay_text = application_data.get('essay', essay_text)
                gpa = application_data.get('gpa', gpa)
                transcript_url = application_data.get('transcript_url', transcript_url)
                resume_url = application_data.get('resume_url', resume_url)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO scholarship_applications (
                        scholarship_id, student_id, essay_text, gpa,
                        transcript_url, resume_url
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (scholarship_id, student_id, essay_text, gpa, transcript_url, resume_url))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error submitting scholarship application: {e}")
            return None

    def review_application(
        self,
        app_id: int,
        reviewer_id: int,
        status: str,
        review_score: Optional[float] = None,
        review_comments: Optional[str] = None
    ) -> bool:
        """Review a scholarship application"""
        valid_statuses = ['pending', 'under_review', 'awarded', 'denied']
        if status not in valid_statuses:
            return False

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE scholarship_applications
                    SET status = ?, reviewer_id = ?, review_date = CURRENT_TIMESTAMP,
                        review_score = ?, review_comments = ?
                    WHERE app_id = ?
                """, (status, reviewer_id, review_score, review_comments, app_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error reviewing application: {e}")
            return False

    def award_scholarship(
        self,
        scholarship_id: int,
        student_id: int,
        academic_year: str,
        amount: float,
        is_renewable: bool = False
    ) -> Optional[int]:
        """Award a scholarship to a student"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO scholarship_awards (
                        scholarship_id, student_id, academic_year, amount,
                        award_date, is_renewable
                    ) VALUES (?, ?, ?, ?, CURRENT_DATE, ?)
                """, (scholarship_id, student_id, academic_year, amount,
                      1 if is_renewable else 0))

                award_id = cursor.lastrowid

                # Update scholarship total awarded count
                cursor.execute("""
                    UPDATE scholarships
                    SET total_awarded = total_awarded + 1
                    WHERE scholarship_id = ?
                """, (scholarship_id,))

                conn.commit()
                return award_id
        except Exception as e:
            print(f"Error awarding scholarship: {e}")
            return None

    def get_available_scholarships(
        self,
        student_id: Optional[int] = None,
        min_gpa: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Get available scholarships"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT * FROM scholarships
                    WHERE is_active = 1
                    AND (deadline IS NULL OR deadline >= CURRENT_DATE)
                """
                params = []

                if min_gpa:
                    query += " AND (min_gpa IS NULL OR min_gpa <= ?)"
                    params.append(min_gpa)

                query += " ORDER BY amount DESC"

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]

                results = []
                for row in cursor.fetchall():
                    scholarship = dict(zip(columns, row))
                    if scholarship.get('eligibility_criteria'):
                        try:
                            scholarship['eligibility_criteria'] = json.loads(
                                scholarship['eligibility_criteria']
                            )
                        except (ValueError, TypeError):
                            pass
                    results.append(scholarship)

                return results
        except Exception as e:
            print(f"Error getting available scholarships: {e}")
            return []

    def get_student_awards(self, student_id: int) -> List[Dict[str, Any]]:
        """Get all scholarship awards for a student"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT sa.*, s.name as scholarship_name
                    FROM scholarship_awards sa
                    JOIN scholarships s ON sa.scholarship_id = s.scholarship_id
                    WHERE sa.student_id = ?
                    ORDER BY sa.award_date DESC
                """, (student_id,))

                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting student awards: {e}")
            return []

    def add_external_scholarship(
        self,
        student_id: int,
        provider_name: str,
        amount: float,
        academic_year: str,
        scholarship_name: Optional[str] = None,
        is_recurring: bool = False
    ) -> Optional[int]:
        """Record an external scholarship"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO external_scholarships (
                        student_id, provider_name, scholarship_name, amount,
                        academic_year, is_recurring
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, provider_name, scholarship_name, amount,
                      academic_year, 1 if is_recurring else 0))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error adding external scholarship: {e}")
            return None

    def check_renewal_eligibility(
        self,
        award_id: int,
        current_gpa: float,
        credit_hours: int,
        enrollment_status: str
    ) -> Dict[str, Any]:
        """Check if student is eligible for scholarship renewal"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get renewal requirements
                cursor.execute("""
                    SELECT * FROM renewal_requirements
                    WHERE award_id = ?
                    ORDER BY academic_year DESC
                    LIMIT 1
                """, (award_id,))

                row = cursor.fetchone()
                if not row:
                    return {'eligible': True, 'reason': 'No specific requirements'}

                columns = [d[0] for d in cursor.description]
                requirements = dict(zip(columns, row))

                # Check each requirement
                checks = []

                if requirements['gpa_required']:
                    gpa_met = current_gpa >= requirements['gpa_required']
                    checks.append({
                        'requirement': 'GPA',
                        'required': requirements['gpa_required'],
                        'actual': current_gpa,
                        'met': gpa_met
                    })

                if requirements['credit_hours_required']:
                    hours_met = credit_hours >= requirements['credit_hours_required']
                    checks.append({
                        'requirement': 'Credit Hours',
                        'required': requirements['credit_hours_required'],
                        'actual': credit_hours,
                        'met': hours_met
                    })

                if requirements['enrollment_status_required']:
                    status_met = enrollment_status == requirements['enrollment_status_required']
                    checks.append({
                        'requirement': 'Enrollment Status',
                        'required': requirements['enrollment_status_required'],
                        'actual': enrollment_status,
                        'met': status_met
                    })

                eligible = all(check['met'] for check in checks)

                return {
                    'eligible': eligible,
                    'checks': checks,
                    'requirements': requirements
                }
        except Exception as e:
            print(f"Error checking renewal eligibility: {e}")
            return {'eligible': False, 'reason': str(e)}
