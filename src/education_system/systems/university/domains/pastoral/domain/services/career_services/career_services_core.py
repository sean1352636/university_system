"""
Career Services Platform Core Service

Job postings, resume management, interview scheduling, career events,
alumni mentorship, and skills tracking.
"""

from __future__ import annotations

import logging

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.infrastructure.sql_safety import escape_like
from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.exceptions import DatabaseError, ValidationError

logger = logging.getLogger("career.emails")


def _send_career_email(template_name: str, recipient: str,
                       vars_: Dict[str, Any]) -> bool:
    """Render ``career/<template_name>`` and dispatch via the shared email
    infrastructure. Best-effort — returns False on any failure."""
    if not recipient:
        return False
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
    subject, body = render_template(f"career/{template_name}", vars_)
    if not subject or not body:
        logger.error("template render failed: career/%s", template_name)
        return False
    try:
        send_email(recipient_email=recipient, subject=subject, body=body)
        logger.info("sent career/%s to %s", template_name, recipient)
        return True
    except Exception:
        logger.exception("send_email failed career/%s recipient=%s",
                         template_name, recipient)
        return False


def _lookup_application_context(application_id: int) -> Optional[Dict[str, Any]]:
    """Join job_applications -> job_postings -> students for email context."""
    try:
        with get_connection() as conn:
            row = conn.execute('''
                SELECT a.application_id, a.student_id, a.status,
                       j.job_title, j.company_name, j.job_type, j.location,
                       j.salary_range,
                       TRIM(COALESCE(s.first_name,'')||' '
                            ||COALESCE(s.last_name,'')) AS student_name,
                       COALESCE(s.email_address,'') AS student_email
                  FROM job_applications a
                  JOIN job_postings    j ON j.job_id      = a.job_id
                  LEFT JOIN students   s ON s.student_id  = a.student_id
                 WHERE a.application_id = ?
            ''', (application_id,)).fetchone()
    except Exception:
        logger.exception("application context lookup failed app_id=%s",
                         application_id)
        return None
    if not row:
        return None
    return dict(row)
from education_system.systems.university.infrastructure.i18n import (
    get_text,
    get_current_language,
)

class JobManager:
    """Manages job postings and applications"""

    @staticmethod
    def create_job_posting(company_name: str, job_title: str, job_type: str,
                          location: str, description: str, requirements: str,
                          salary_range: str = "", application_deadline: str = "",
                          employer_id: Optional[int] = None) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO job_postings (
                        posted_by, job_title, company_name, job_type, location,
                        salary_range, job_description, requirements, expiry_date,
                        post_date, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'), 1)
                ''', (employer_id, job_title, company_name, job_type, location,
                      salary_range, description, requirements, application_deadline))
                job_id = cursor.lastrowid

            # Cross-domain: publish through careers_bus so the chatbot,
            # student-job dashboards and email subscribers see the
            # new posting without needing to poll job_postings.
            try:
                from education_system.systems.university.services.bus import (
                    careers_bus,
                )
                careers_bus._publish(
                    "careers.job.posted",
                    job_id=job_id, employer_id=employer_id,
                    job_title=job_title, company=company_name,
                    job_type=job_type, location=location,
                    deadline=application_deadline,
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            return job_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating job posting: {e}") from e

    @staticmethod
    def apply_for_job(job_id: int, student_id: str, resume_id: Optional[int],
                     cover_letter: str = "") -> int:
        try:
            with transaction() as conn:
                # Both id columns are populated: writes went to applicant_id
                # while _lookup_application_context (and so every applicant
                # email) reads student_id, which left the emails unaddressed.
                # resume_id was accepted and then dropped on the floor.
                cursor = conn.execute('''
                    INSERT INTO job_applications (job_id, applicant_id, student_id,
                                                  resume_id, cover_letter,
                                                  application_date, status)
                    VALUES (?, ?, ?, ?, ?, date('now'), 'pending')
                ''', (job_id, student_id, student_id, resume_id, cover_letter))
                application_id = cursor.lastrowid
                return application_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error applying for job: {e}") from e

    @staticmethod
    def confirm_placement(application_id: int, start_date: str,
                          placement_duration: str = "12 months",
                          employer_contact: str = "(see careers portal)",
                          employer_notes: str = "") -> bool:
        """Mark a job application as 'placed' and email the student a
        placement-confirmation. Best-effort; returns the email-sent flag."""
        try:
            with transaction() as conn:
                conn.execute('''
                    UPDATE job_applications
                       SET status        = 'placed',
                           reviewed_date = date('now')
                     WHERE application_id = ?
                ''', (application_id,))
        except sqlite3.Error as e:
            raise DatabaseError(f"Error confirming placement: {e}") from e
        ctx = _lookup_application_context(application_id) or {}
        return _send_career_email('placement_confirmation', ctx.get('student_email', ''), {
            'student_name':       ctx.get('student_name') or ctx.get('student_id') or 'Student',
            'application_id':     application_id,
            'job_title':          ctx.get('job_title', ''),
            'company_name':       ctx.get('company_name', ''),
            'location':           ctx.get('location') or '(see offer letter)',
            'job_type':           ctx.get('job_type', ''),
            'salary_range':       ctx.get('salary_range') or '(see offer letter)',
            'start_date':         start_date,
            'placement_duration': placement_duration,
            'employer_contact':   employer_contact,
            'employer_notes':     employer_notes or '(none)',
        })

    @staticmethod
    def send_employer_message(application_id: int, message_body: str,
                              message_subject: str = "Update from the employer",
                              employer_contact_name: str = "",
                              employer_contact_role: str = "Recruiting Team",
                              employer_contact_email: str = "",
                              company_website: str = "") -> bool:
        """Forward an employer-to-student message via a templated email.
        Best-effort; returns True on send."""
        ctx = _lookup_application_context(application_id) or {}
        return _send_career_email('employer_message', ctx.get('student_email', ''), {
            'student_name':           ctx.get('student_name') or ctx.get('student_id') or 'Student',
            'application_id':         application_id,
            'job_title':              ctx.get('job_title', ''),
            'company_name':           ctx.get('company_name', ''),
            'employer_contact_name':  employer_contact_name or ctx.get('company_name', 'Recruiter'),
            'employer_contact_role':  employer_contact_role,
            'employer_contact_email': employer_contact_email or '(reply to this email)',
            'company_website':        company_website or '(not provided)',
            'message_subject':        message_subject,
            'message_sent_on':        datetime.now().isoformat(timespec='minutes'),
            'message_body':           message_body or '(no message body provided)',
        })

    @staticmethod
    def get_active_jobs(filters: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            query = "SELECT * FROM job_postings WHERE is_active = 1"
            params = []
            if filters:
                if 'job_type' in filters:
                    query += " AND job_type = ?"
                    params.append(filters['job_type'])
                if 'location' in filters:
                    query += " AND location LIKE ?"
                    params.append(f"%{escape_like(filters['location'])}%")
            query += " ORDER BY post_date DESC"
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def get_job(job_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM job_postings WHERE job_id = ?", (job_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_student_applications(student_id: str) -> List[Dict[str, Any]]:
        """Every application this student has made, newest first, with the
        job it was for and any interview that has been scheduled."""
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT a.application_id, a.status, a.application_date,
                       a.cover_letter, a.resume_id,
                       j.job_id, j.job_title, j.company_name, j.location,
                       j.job_type,
                       i.interview_date, i.interview_time, i.interview_type,
                       i.location AS interview_location, i.meeting_link
                  FROM job_applications a
                  JOIN job_postings j ON j.job_id = a.job_id
             LEFT JOIN interview_schedules i ON i.application_id = a.application_id
                 WHERE COALESCE(a.student_id, a.applicant_id) = ?
              ORDER BY a.application_date DESC, a.application_id DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def has_applied(job_id: int, student_id: str) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM job_applications "
                "WHERE job_id = ? AND COALESCE(student_id, applicant_id) = ? "
                "LIMIT 1",
                (job_id, student_id),
            ).fetchone()
            return row is not None

class ResumeManager:
    """Manages student resumes and CVs"""

    @staticmethod
    def upload_resume(student_id: str, resume_name: str, file_url: str,
                     template_used: str = "", is_primary: bool = False) -> int:
        try:
            with transaction() as conn:
                if is_primary:
                    # Unset other primary resumes
                    conn.execute('''
                        UPDATE student_resumes
                        SET is_primary = 0
                        WHERE student_id = ?
                    ''', (student_id,))

                cursor = conn.execute('''
                    INSERT INTO student_resumes (
                        student_id, resume_name, file_url, template_used, is_primary
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (student_id, resume_name, file_url, template_used, is_primary))
                resume_id = cursor.lastrowid
                return resume_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error uploading resume: {e}") from e

    @staticmethod
    def get_student_resumes(student_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM student_resumes
                WHERE student_id = ?
                ORDER BY is_primary DESC, created_at DESC
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

class InterviewManager:
    """Manages interview scheduling"""

    @staticmethod
    def schedule_interview(application_id: int, interview_type: str,
                          interview_date: str, interview_time: str,
                          duration_minutes: int = 60, location: str = "",
                          meeting_link: str = "", interviewer_name: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO interview_schedules (
                        application_id, interview_type, interview_date, interview_time,
                        duration_minutes, location, meeting_link, interviewer_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (application_id, interview_type, interview_date, interview_time,
                      duration_minutes, location, meeting_link, interviewer_name))
                interview_id = cursor.lastrowid
                # Update application status
                conn.execute('''
                    UPDATE job_applications
                    SET status = 'interview_scheduled'
                    WHERE application_id = ?
                ''', (application_id,))
            ctx = _lookup_application_context(application_id) or {}
            _send_career_email('interview_scheduled', ctx.get('student_email', ''), {
                'student_name':     ctx.get('student_name') or ctx.get('student_id') or 'Student',
                'application_id':   application_id,
                'job_title':        ctx.get('job_title', ''),
                'company_name':     ctx.get('company_name', ''),
                'interview_type':   interview_type,
                'interview_date':   interview_date,
                'interview_time':   interview_time,
                'duration_minutes': duration_minutes,
                'location':         location or '(see meeting link)',
                'meeting_link':     meeting_link or '(not applicable)',
                'interviewer_name': interviewer_name or '(to be confirmed)',
            })
            return interview_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error scheduling interview: {e}") from e

class CareerEventManager:
    """Manages career fairs and events"""

    @staticmethod
    def create_event(event_name: str, event_type: str, event_date: str,
                    event_time: str, location: str, description: str = "",
                    max_attendees: int = 100) -> int:
        try:
            with transaction() as conn:
                start_datetime = f"{event_date} {event_time}" if event_time else event_date
                cursor = conn.execute('''
                    INSERT INTO unified_events (
                        title, event_type, start_datetime,
                        location, description, max_capacity, is_public, source_type
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, 'career')
                ''', (event_name, event_type, start_datetime,
                      location, description, max_attendees))
                event_id = cursor.lastrowid
                return event_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating event: {e}") from e

    @staticmethod
    def register_for_event(event_id: int, student_id: str, num_guests: int = 0) -> int:
        try:
            with transaction() as conn:
                # The table keys registrations by user_id/user_type and stores
                # the timestamp in registration_date — the previous columns
                # (student_id, registered_at) do not exist, so every career
                # event registration failed outright.
                cursor = conn.execute('''
                    INSERT INTO unified_event_registrations (
                        event_id, user_id, user_type, registration_date, num_guests
                    ) VALUES (?, ?, 'student', datetime('now'), ?)
                ''', (event_id, student_id, num_guests))
                registration_id = cursor.lastrowid
                return registration_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error registering for event: {e}") from e

    @staticmethod
    def get_upcoming_events(include_past: bool = False) -> List[Dict[str, Any]]:
        """Career events, soonest first."""
        with get_connection() as conn:
            query = (
                "SELECT event_id, title, event_type, start_datetime, location, "
                "       description, max_capacity "
                "FROM unified_events WHERE source_type = 'career' "
            )
            if not include_past:
                query += "AND (start_datetime IS NULL OR date(start_datetime) >= date('now')) "
            query += "ORDER BY start_datetime"
            return [dict(row) for row in conn.execute(query).fetchall()]

    @staticmethod
    def get_registrations_for(student_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT r.registration_id, r.registration_date, r.num_guests,
                       e.event_id, e.title, e.start_datetime, e.location
                  FROM unified_event_registrations r
                  JOIN unified_events e ON e.event_id = r.event_id
                 WHERE r.user_id = ? AND e.source_type = 'career'
              ORDER BY e.start_datetime
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def is_registered(event_id: int, student_id: str) -> bool:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM unified_event_registrations "
                "WHERE event_id = ? AND user_id = ? LIMIT 1",
                (event_id, student_id),
            ).fetchone()
            return row is not None

class MentorshipManager:
    """Manages alumni mentorship program"""

    @staticmethod
    def register_mentor(alumni_student_id: str, job_title: str, company: str,
                       industry: str, expertise_areas: str, max_mentees: int = 3,
                       bio: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO alumni_mentors (
                        alumni_student_id, job_title, company, industry,
                        expertise_areas, max_mentees, bio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (alumni_student_id, job_title, company, industry,
                      expertise_areas, max_mentees, bio))
                mentor_id = cursor.lastrowid
                return mentor_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error registering mentor: {e}") from e

    @staticmethod
    def create_mentorship_match(mentor_id: int, mentee_student_id: str,
                               meeting_frequency: str = "monthly", notes: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO mentorship_matches (
                        mentor_id, mentee_student_id, meeting_frequency, notes
                    ) VALUES (?, ?, ?, ?)
                ''', (mentor_id, mentee_student_id, meeting_frequency, notes))
                match_id = cursor.lastrowid
                return match_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating mentorship match: {e}") from e

    @staticmethod
    def get_available_mentors(industry: Optional[str] = None) -> List[Dict[str, Any]]:
        """Active mentors who still have room for another mentee."""
        with get_connection() as conn:
            query = '''
                SELECT m.mentor_id, m.alumni_student_id, m.job_title, m.company,
                       m.industry, m.expertise_areas, m.max_mentees, m.bio,
                       COUNT(mm.match_id) AS current_mentees
                  FROM alumni_mentors m
             LEFT JOIN mentorship_matches mm
                    ON mm.mentor_id = m.mentor_id
                   AND LOWER(COALESCE(mm.status, 'active')) = 'active'
                 WHERE COALESCE(m.is_active, 1) = 1
            '''
            params: List[Any] = []
            if industry:
                query += " AND LOWER(m.industry) LIKE ?"
                params.append(f"%{escape_like(industry.lower())}%")
            query += '''
              GROUP BY m.mentor_id
                HAVING COUNT(mm.match_id) < COALESCE(m.max_mentees, 3)
              ORDER BY m.company, m.job_title
            '''
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    @staticmethod
    def get_matches_for(mentee_student_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT mm.match_id, mm.match_date, mm.status, mm.meeting_frequency,
                       mm.notes, m.job_title, m.company, m.industry,
                       m.alumni_student_id
                  FROM mentorship_matches mm
                  JOIN alumni_mentors m ON m.mentor_id = mm.mentor_id
                 WHERE mm.mentee_student_id = ?
              ORDER BY mm.match_date DESC
            ''', (mentee_student_id,))
            return [dict(row) for row in cursor.fetchall()]

class SkillsManager:
    """Manages student skills tracking"""

    @staticmethod
    def add_skill(student_id: str, skill_name: str, skill_category: str,
                 proficiency_level: str, verified: bool = False) -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO student_skills (
                        student_id, skill_name, skill_category, proficiency_level, verified
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (student_id, skill_name, skill_category, proficiency_level, verified))
                skill_id = cursor.lastrowid
                return skill_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error adding skill: {e}") from e

    @staticmethod
    def get_student_skills(student_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM student_skills
                WHERE student_id = ?
                ORDER BY skill_category, skill_name
            ''', (student_id,))
            return [dict(row) for row in cursor.fetchall()]

def display_career_services_menu(auth):
    """Display the Career Services Platform CLI menu"""
    print("\n" + "="*50)
    print(f"      {get_text('career.title', default='CAREER SERVICES PLATFORM')}")
    print("="*50)
    print(f"1. {get_text('career.menu.browse_jobs', default='Browse Job Postings')}")
    print(f"2. {get_text('career.menu.submit_resume', default='Submit Resume')}")
    print(f"3. {get_text('career.menu.mock_interview', default='Schedule Mock Interview')}")
    print(f"4. {get_text('career.menu.career_events', default='View Career Events')}")
    print(f"5. {get_text('career.menu.mentorship', default='Alumni Mentorship Program')}")
    print(f"6. {get_text('career.menu.skills', default='Skills Assessment')}")
    print(f"7. {get_text('career.menu.tracking', default='Job Application Tracking')}")
    print(f"8. {get_text('career.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    from education_system.systems.university.domains.pastoral.domain.services.career_services import (
        career_services_cli as screens,
    )

    student_id = screens._resolve_student_id(auth)
    if student_id is None:
        print(get_text('career.login_required',
                       default='You must be logged in to use Career Services.'))
        return

    actions = {
        '1': screens.browse_job_postings,
        '2': screens.submit_resume,
        '3': screens.schedule_mock_interview,
        '4': screens.view_career_events,
        '5': screens.alumni_mentorship_program,
        '6': screens.skills_assessment,
        '7': screens.job_application_tracking,
    }

    while True:
        try:
            choice = input(f"\n{get_text('career.prompt.choice', default='Enter your choice (1-8)')}: ").strip()
            if choice in actions:
                actions[choice](student_id)
            elif choice == '8':
                print(get_text('career.returning', default='Returning to main menu...'))
                break
            else:
                print(get_text('career.invalid_choice', default='Invalid choice.'))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(get_text('career.error', default='Error: {error}').format(error=e))

# GUI launcher — lazy-loaded via __getattr__ to avoid the circular
# import that happens because career_services_gui imports back from
# this module.  Public surface stays the same: callers can still do
# ``from ...career_services_core import launch_career_services_gui``.
def __getattr__(name):
    if name == "launch_career_services_gui":
        from education_system.systems.university.domains.pastoral.interfaces.gui.career_services.career_services_gui import (
            launch_career_services_gui as _launch,
        )
        return _launch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'JobManager', 'ResumeManager', 'InterviewManager',
    'CareerEventManager', 'MentorshipManager', 'SkillsManager',
    'display_career_services_menu',
    'launch_career_services_gui',  # noqa: F822 — resolved lazily via module __getattr__ (PEP 562)
]
