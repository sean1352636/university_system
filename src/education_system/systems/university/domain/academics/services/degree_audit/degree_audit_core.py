"""
Degree Audit & Academic Advising Core Service

This module provides degree progress tracking, prerequisite validation,
what-if scenarios, advising appointments, and graduation audits.
"""

from __future__ import annotations

import json
import logging
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, date

logger = logging.getLogger("degree_audit.emails")


def _send_degree_audit_email(template_name: str, student_id: str,
                             vars_: Dict[str, Any]) -> bool:
    """Look up the student's email and dispatch ``degree_audit/<template_name>``
    via the shared email infrastructure. Best-effort."""
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name,"
                "       COALESCE(email_address,'') AS email"
                "  FROM students WHERE student_id = ?",
                (student_id,),
            ).fetchone()
    except Exception:
        logger.exception("student lookup failed sid=%s", student_id)
        return False
    if not row:
        logger.warning("student %s not found", student_id)
        return False
    recipient = (row['email'] or '').strip()
    if not recipient:
        logger.warning("no email on file for student %s", student_id)
        return False
    full = {
        'student_id':   student_id,
        'student_name': (row['name'] or '').strip() or student_id,
    }
    full.update(vars_)
    subject, body = render_template(f"degree_audit/{template_name}", full)
    if not subject or not body:
        logger.error("template render failed: degree_audit/%s", template_name)
        return False
    try:
        send_email(recipient_email=recipient, subject=subject, body=body)
        logger.info("sent degree_audit/%s to %s", template_name, recipient)
        return True
    except Exception:
        logger.exception("send_email failed degree_audit/%s recipient=%s",
                         template_name, recipient)
        return False
from typing import Any, Dict, List, Optional, Tuple
from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.infrastructure.exceptions import (
    DatabaseError,
    CourseNotFoundError,
    StudentNotFoundError,
    ValidationError,
)
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)
from education_system.systems.university.infrastructure.utils.language_selector import (
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
                SELECT sm.module_code, m.credits
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

            result = {
                'all_requirements_met': all_reqs_met,
                'gpa_requirement_met': gpa_req_met,
                'credit_requirement_met': credit_req_met,
                'total_requirements': total_reqs,
                'completed_requirements': completed_reqs,
                'can_graduate': all_reqs_met and gpa_req_met and credit_req_met
            }

            # Best-effort notification — never let an email failure break the
            # audit itself.
            try:
                prog_row = conn.execute(
                    "SELECT program_name FROM degree_programs WHERE program_id = ?",
                    (program_id,),
                ).fetchone()
                program_name = prog_row['program_name'] if prog_row else f"Programme #{program_id}"

                credits_earned = progress['total_credits_earned'] if progress else 0
                current_gpa    = progress['current_gpa'] if progress else 0

                base_vars = {
                    'program_name':            program_name,
                    'audit_date':              date.today().isoformat(),
                    'credits_earned':          credits_earned,
                    'credits_required':        program['total_credits_required'],
                    'current_gpa':             current_gpa,
                    'gpa_required':            program['min_gpa_required'],
                    'completed_requirements':  completed_reqs,
                    'total_requirements':      total_reqs,
                }
                if result['can_graduate']:
                    base_vars.update({
                        'apply_by':      '(see Student Portal)',
                        'ceremony_date': '(to be confirmed)',
                    })
                    _send_degree_audit_email('graduation_eligibility', student_id, base_vars)
                else:
                    # Build a human-readable list of which checks failed.
                    gaps = []
                    if not credit_req_met:
                        short = max(0, program['total_credits_required'] - (credits_earned or 0))
                        gaps.append(f"  • Credits: short by {short} (have {credits_earned}, need {program['total_credits_required']}).")
                    if not gpa_req_met:
                        gaps.append(f"  • GPA: {current_gpa} is below the required {program['min_gpa_required']}.")
                    if not all_reqs_met:
                        missing = max(0, total_reqs - completed_reqs)
                        gaps.append(f"  • Programme requirements: {missing} of {total_reqs} mandatory item(s) still outstanding.")
                    base_vars.update({
                        'gap_list':            "\n".join(gaps) or "  (no specific gaps recorded — please contact your advisor)",
                        'credits_status':      'OK' if credit_req_met else 'SHORT',
                        'gpa_status':          'OK' if gpa_req_met else 'BELOW',
                        'requirements_status': 'OK' if all_reqs_met else 'INCOMPLETE',
                    })
                    _send_degree_audit_email('requirement_gap_alert', student_id, base_vars)
            except Exception:
                logger.exception("audit notification dispatch failed sid=%s prog=%s",
                                 student_id, program_id)

            return result

        except CourseNotFoundError:
            conn.rollback()
            raise
        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error running graduation audit: {e}") from e
        finally:
            conn.close()

    @staticmethod
    def send_graduation_invitation(student_id: str, program_id: int,
                                   ceremony_date: str, ceremony_time: str,
                                   venue: str, rsvp_by: str,
                                   award: str = "(see student record)",
                                   robing_required: str = "Yes",
                                   robing_window: str = "(see ceremony pack)",
                                   guest_tickets_allowed: str = "2") -> bool:
        """Send the lifecycle 'graduation' invitation to a student.

        Uses the ``student_lifecycle/graduation`` template so the message is
        clearly an *invitation* — the separate ``degree_audit/conferral_notice``
        is used after the Senate signs off."""
        try:
            from education_system.systems.university.infrastructure.email.template_utils import (
                render_template,
            )
            from education_system.systems.university.infrastructure.email.email_service import (
                send_email,
            )
        except Exception:
            logger.exception("email infrastructure unavailable")
            return False
        try:
            with get_connection() as conn:
                stud = conn.execute(
                    "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name,"
                    "       COALESCE(email_address,'') AS email"
                    "  FROM students WHERE student_id = ?",
                    (student_id,),
                ).fetchone()
                prog = conn.execute(
                    "SELECT program_name FROM degree_programs WHERE program_id = ?",
                    (program_id,),
                ).fetchone()
        except Exception:
            logger.exception("graduation invite lookup failed sid=%s", student_id)
            return False
        if not stud or not (stud['email'] or '').strip():
            return False
        program_name = prog['program_name'] if prog else f"Programme #{program_id}"
        subject, body = render_template('student_lifecycle/graduation', {
            'student_id':            student_id,
            'student_name':          (stud['name'] or '').strip() or student_id,
            'award':                 award,
            'program_name':          program_name,
            'ceremony_date':         ceremony_date,
            'ceremony_time':         ceremony_time,
            'venue':                 venue,
            'robing_required':       robing_required,
            'robing_window':         robing_window,
            'guest_tickets_allowed': guest_tickets_allowed,
            'rsvp_by':               rsvp_by,
        })
        if not subject or not body:
            return False
        try:
            send_email(recipient_email=stud['email'].strip(), subject=subject, body=body)
            return True
        except Exception:
            logger.exception("graduation invite send failed sid=%s", student_id)
            return False

    @staticmethod
    def approve_graduation(student_id: str, program_id: int, graduation_date: str,
                           classification: str = "(see transcript)",
                           approved_by: str = "Office of the Registrar",
                           ceremony_date: str = "(to be confirmed)",
                           rsvp_by: str = "(see Student Portal)") -> bool:
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

            # Best-effort conferral notice.
            try:
                prog_row = conn.execute(
                    "SELECT program_name FROM degree_programs WHERE program_id = ?",
                    (program_id,),
                ).fetchone()
                program_name = prog_row['program_name'] if prog_row else f"Programme #{program_id}"
                _send_degree_audit_email('conferral_notice', student_id, {
                    'program_name':    program_name,
                    'graduation_date': graduation_date,
                    'classification':  classification,
                    'approved_by':     approved_by,
                    'ceremony_date':   ceremony_date,
                    'rsvp_by':         rsvp_by,
                })
            except Exception:
                logger.exception("conferral notice dispatch failed sid=%s prog=%s",
                                 student_id, program_id)
            return True

        except sqlite3.Error as e:
            conn.rollback()
            raise DatabaseError(f"Error approving graduation: {e}") from e
        finally:
            conn.close()

# Removed: display_degree_audit_menu() - replaced by comprehensive degree_audit_cli.py
# The placeholder menu has been replaced with a full-featured CLI in:
# university_system/modules/services/cli/degree_audit_cli.py

def launch_degree_audit_gui(root, auth):
    """Launch the degree audit GUI without importing it during service import."""
    try:
        from education_system.systems.university.interfaces.gui.academics.course_management_gui.degree_audit_gui import (
            launch_degree_audit_gui as _launch_degree_audit_gui,
        )
        return _launch_degree_audit_gui(root, auth)
    except ImportError:
        from education_system.systems.university.services.feature_gui_factory import create_gui_launcher
        fallback_launcher = create_gui_launcher(
            title="Degree Audit & Academic Advising",
            description="""Track degree progress, check prerequisites, and plan academic path.

Features:
• Degree progress tracking
• Prerequisite validation
• What-if scenario analysis
• Advising appointments
• Graduation audit
• Degree requirements""",
            cli_instruction="Use CLI: Degree Audit & Academic Advising",
        )
        return fallback_launcher(root, auth)

__all__ = [
    'DegreeProgramManager',
    'DegreeProgressManager',
    'WhatIfScenarioManager',
    'AdvisingAppointmentManager',
    'GraduationAuditManager',
    'launch_degree_audit_gui',
]
