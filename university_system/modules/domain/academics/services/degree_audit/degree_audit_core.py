"""
Degree Audit & Academic Advising Core Service

This module provides degree progress tracking, prerequisite validation,
what-if scenarios, advising appointments, and graduation audits.
"""

from __future__ import annotations

import json
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple
from university_system.infrastructure.database.db import get_connection
from university_system.infrastructure.exceptions import (
    DatabaseError,
    CourseNotFoundError,
    StudentNotFoundError,
    ValidationError,
)
from university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
)

class DegreeProgramManager:
    """Manages degree programs and requirements"""

    @staticmethod
    def create_program(
        program_code: str,
        program_name: str,
        degree_type: str,
        total_credits_required: int,
        department: str = "",
        min_gpa_required: float = 2.0,
        max_years_allowed: int = 4,
        description: str = ""
    ) -> int:
        """Create a new degree program"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO degree_programs (
                    program_code, program_name, degree_type, department,
                    total_credits_required, min_gpa_required, max_years_allowed, description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (program_code, program_name, degree_type, department,
                  total_credits_required, min_gpa_required, max_years_allowed, description))

            program_id = cursor.lastrowid
            conn.commit()
            return program_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating degree program: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def add_requirement(
        program_id: int,
        requirement_type: str,
        requirement_name: str,
        credits_required: int,
        description: str = "",
        min_grade: str = "",
        is_mandatory: bool = True
    ) -> int:
        """Add a requirement to a degree program"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO degree_requirements (
                    program_id, requirement_type, requirement_name, credits_required,
                    description, min_grade, is_mandatory
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (program_id, requirement_type, requirement_name, credits_required,
                  description, min_grade, is_mandatory))

            requirement_id = cursor.lastrowid
            conn.commit()
            return requirement_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding requirement: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def add_required_course(
        requirement_id: int,
        module_code: str,
        is_alternative: bool = False,
        alternative_group: Optional[int] = None
    ) -> int:
        """Add a required course to a requirement"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO requirement_courses (
                    requirement_id, module_code, is_alternative, alternative_group
                )
                VALUES (?, ?, ?, ?)
            ''', (requirement_id, module_code, is_alternative, alternative_group))

            req_course_id = cursor.lastrowid
            conn.commit()
            return req_course_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding required course: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def add_prerequisite(
        module_code: str,
        prerequisite_module_code: str,
        min_grade: str = "",
        is_corequisite: bool = False
    ) -> int:
        """Add a prerequisite for a course"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO degree_course_prerequisites (
                    module_code, prerequisite_module_code, min_grade, is_corequisite
                )
                VALUES (?, ?, ?, ?)
            ''', (module_code, prerequisite_module_code, min_grade, is_corequisite))

            prerequisite_id = cursor.lastrowid
            conn.commit()
            return prerequisite_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error adding prerequisite: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_program_requirements(program_id: int) -> List[Dict[str, Any]]:
        """Get all requirements for a degree program"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM degree_requirements
                WHERE program_id = ?
                ORDER BY display_order, requirement_name
            ''', (program_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

class DegreeProgressManager:
    """Manages student degree progress tracking"""

    @staticmethod
    def initialize_student_progress(
        student_id: str,
        program_id: int,
        enrollment_year: int
    ) -> int:
        """Initialize degree progress tracking for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO student_degree_progress (
                    student_id, program_id, enrollment_year
                )
                VALUES (?, ?, ?)
            ''', (student_id, program_id, enrollment_year))

            progress_id = cursor.lastrowid
            conn.commit()
            return progress_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error initializing progress: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def update_progress(student_id: str, program_id: int) -> None:
        """Update student's degree progress"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Calculate total credits earned
            cursor.execute('''
                SELECT SUM(m.credits) as total_credits, AVG(
                    CASE
                        WHEN sm.grade = 'A' THEN 4.0
                        WHEN sm.grade = 'B' THEN 3.0
                        WHEN sm.grade = 'C' THEN 2.0
                        WHEN sm.grade = 'D' THEN 1.0
                        ELSE 0.0
                    END
                ) as gpa
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                WHERE sm.student_id = ?
            ''', (student_id,))

            result = cursor.fetchone()
            total_credits = result['total_credits'] or 0
            gpa = result['gpa'] or 0

            # Get program requirements
            cursor.execute('''
                SELECT total_credits_required
                FROM degree_programs
                WHERE program_id = ?
            ''', (program_id,))

            program = cursor.fetchone()
            if not program:
                raise CourseNotFoundError(f"Program {program_id}")

            completion_pct = (total_credits / program['total_credits_required'] * 100) if program['total_credits_required'] > 0 else 0

            # Update progress
            cursor.execute('''
                UPDATE student_degree_progress
                SET total_credits_earned = ?,
                    current_gpa = ?,
                    completion_percentage = ?,
                    last_updated = ?
                WHERE student_id = ? AND program_id = ?
            ''', (total_credits, gpa, completion_pct, datetime.now().isoformat(), student_id, program_id))

            conn.commit()

        except (CourseNotFoundError, StudentNotFoundError):
            conn.rollback()
            raise
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error updating progress: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_student_progress(student_id: str) -> Optional[Dict[str, Any]]:
        """Get student's degree progress"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT sp.*, dp.program_name, dp.total_credits_required
                FROM student_degree_progress sp
                JOIN degree_programs dp ON sp.program_id = dp.program_id
                WHERE sp.student_id = ?
            ''', (student_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

        finally:
            conn.close()

    @staticmethod
    def check_prerequisite_completion(
        student_id: str,
        module_code: str
    ) -> Tuple[bool, List[str]]:
        """Check if student has completed prerequisites for a course"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get prerequisites
            cursor.execute('''
                SELECT prerequisite_module_code, min_grade
                FROM degree_course_prerequisites
                WHERE module_code = ? AND is_corequisite = 0
            ''', (module_code,))

            prerequisites = cursor.fetchall()
            missing_prerequisites = []

            for prereq in prerequisites:
                # Check if student has completed this prerequisite
                cursor.execute('''
                    SELECT grade FROM student_modules
                    WHERE student_id = ? AND module_code = ?
                ''', (student_id, prereq['prerequisite_module_code']))

                result = cursor.fetchone()
                if not result:
                    missing_prerequisites.append(prereq['prerequisite_module_code'])
                elif prereq['min_grade'] and result['grade'] < prereq['min_grade']:
                    missing_prerequisites.append(f"{prereq['prerequisite_module_code']} (grade {prereq['min_grade']} required)")

            return len(missing_prerequisites) == 0, missing_prerequisites

        finally:
            conn.close()

class WhatIfScenarioManager:
    """Manages what-if degree planning scenarios"""

    @staticmethod
    def create_scenario(
        student_id: str,
        scenario_name: str,
        target_program_id: int,
        notes: str = ""
    ) -> int:
        """Create a what-if scenario"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO degree_what_if_scenarios (
                    student_id, scenario_name, target_program_id, notes
                )
                VALUES (?, ?, ?, ?)
            ''', (student_id, scenario_name, target_program_id, notes))

            scenario_id = cursor.lastrowid
            conn.commit()
            return scenario_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error creating scenario: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def analyze_scenario(student_id: str, target_program_id: int) -> Dict[str, Any]:
        """Analyze what-if scenario for switching programs"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get current courses completed
            cursor.execute('''
                SELECT module_code, credits
                FROM student_modules sm
                JOIN modules m ON sm.module_code = m.module_code
                WHERE sm.student_id = ?
            ''', (student_id,))

            completed_courses = [dict(row) for row in cursor.fetchall()]

            # Get target program requirements
            cursor.execute('''
                SELECT * FROM degree_requirements
                WHERE program_id = ?
            ''', (target_program_id,))

            requirements = cursor.fetchall()

            # Calculate how many requirements are already met
            requirements_met = 0
            total_requirements = len(requirements)

            for req in requirements:
                # Get required courses for this requirement
                cursor.execute('''
                    SELECT module_code FROM requirement_courses
                    WHERE requirement_id = ?
                ''', (req['requirement_id'],))

                required_courses = [row['module_code'] for row in cursor.fetchall()]
                completed_codes = [c['module_code'] for c in completed_courses]

                if any(code in completed_codes for code in required_courses):
                    requirements_met += 1

            return {
                'target_program_id': target_program_id,
                'total_requirements': total_requirements,
                'requirements_met': requirements_met,
                'completion_percentage': (requirements_met / total_requirements * 100) if total_requirements > 0 else 0,
                'completed_courses_count': len(completed_courses)
            }

        finally:
            conn.close()

class AdvisingAppointmentManager:
    """Manages academic advising appointments"""

    @staticmethod
    def schedule_appointment(
        student_id: str,
        advisor_id: str,
        appointment_date: str,
        appointment_time: str,
        appointment_type: str,
        duration_minutes: int = 30,
        topic: str = "",
        notes: str = ""
    ) -> int:
        """Schedule an advising appointment"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO advising_appointments (
                    student_id, advisor_id, appointment_date, appointment_time,
                    duration_minutes, appointment_type, topic, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, advisor_id, appointment_date, appointment_time,
                  duration_minutes, appointment_type, topic, notes))

            appointment_id = cursor.lastrowid
            conn.commit()
            return appointment_id

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error scheduling appointment: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def get_student_appointments(student_id: str) -> List[Dict[str, Any]]:
        """Get all appointments for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM advising_appointments
                WHERE student_id = ?
                ORDER BY appointment_date DESC, appointment_time DESC
            ''', (student_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

class GraduationAuditManager:
    """Manages graduation audits and conferral"""

    @staticmethod
    def run_graduation_audit(student_id: str, program_id: int) -> Dict[str, Any]:
        """Run a comprehensive graduation audit"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Get program requirements
            cursor.execute('''
                SELECT total_credits_required, min_gpa_required
                FROM degree_programs
                WHERE program_id = ?
            ''', (program_id,))

            program = cursor.fetchone()
            if not program:
                raise CourseNotFoundError(f"Program {program_id}")

            # Get student progress
            cursor.execute('''
                SELECT total_credits_earned, current_gpa
                FROM student_degree_progress
                WHERE student_id = ? AND program_id = ?
            ''', (student_id, program_id))

            progress = cursor.fetchone()

            # Check requirements
            credit_req_met = progress and progress['total_credits_earned'] >= program['total_credits_required']
            gpa_req_met = progress and progress['current_gpa'] >= program['min_gpa_required']

            # Check all course requirements
            cursor.execute('''
                SELECT COUNT(*) as total_reqs
                FROM degree_requirements
                WHERE program_id = ? AND is_mandatory = 1
            ''', (program_id,))

            total_reqs = cursor.fetchone()['total_reqs']

            # Check completed requirements
            cursor.execute('''
                SELECT COUNT(*) as completed_reqs
                FROM requirement_completion
                WHERE student_id = ? AND is_completed = 1
            ''', (student_id,))

            completed_reqs = cursor.fetchone()['completed_reqs']

            all_reqs_met = completed_reqs >= total_reqs

            # Create or update checklist
            cursor.execute('''
                INSERT OR REPLACE INTO graduation_checklist (
                    student_id, program_id, all_requirements_met,
                    gpa_requirement_met, credit_requirement_met,
                    residency_requirement_met, financial_clearance
                )
                VALUES (?, ?, ?, ?, ?, 0, 0)
            ''', (student_id, program_id, all_reqs_met, gpa_req_met, credit_req_met))

            conn.commit()

            return {
                'all_requirements_met': all_reqs_met,
                'gpa_requirement_met': gpa_req_met,
                'credit_requirement_met': credit_req_met,
                'total_requirements': total_reqs,
                'completed_requirements': completed_reqs,
                'can_graduate': all_reqs_met and gpa_req_met and credit_req_met
            }

        except CourseNotFoundError:
            conn.rollback()
            raise
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error running graduation audit: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def approve_graduation(student_id: str, program_id: int, graduation_date: str) -> bool:
        """Approve student for graduation"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE graduation_checklist
                SET conferral_status = 'approved', graduation_date = ?
                WHERE student_id = ? AND program_id = ?
            ''', (graduation_date, student_id, program_id))

            conn.commit()
            return True

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error approving graduation: {e}") from e
        finally:
            conn.close()

# Removed: display_degree_audit_menu() - replaced by comprehensive degree_audit_cli.py
# The placeholder menu has been replaced with a full-featured CLI in:
# university_system/modules/services/cli/degree_audit_cli.py

# Import GUI launcher from the actual GUI module
try:
    from university_system.modules.domain.academics.gui.degree_audit_gui import launch_degree_audit_gui
except ImportError:
    # Fallback if GUI not available
    from university_system.modules.shared.feature_gui_factory import create_gui_launcher
    launch_degree_audit_gui = create_gui_launcher(
        title="Degree Audit & Academic Advising",
        description="""Track degree progress, check prerequisites, and plan academic path.

Features:
• Degree progress tracking
• Prerequisite validation
• What-if scenario analysis
• Advising appointments
• Graduation audit
• Degree requirements""",
        cli_instruction="Use CLI: Degree Audit & Academic Advising"
    )

__all__ = [
    'DegreeProgramManager',
    'DegreeProgressManager',
    'WhatIfScenarioManager',
    'AdvisingAppointmentManager',
    'GraduationAuditManager',
    'launch_degree_audit_gui',
]
