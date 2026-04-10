"""
Career Services Platform Core Service

Job postings, resume management, interview scheduling, career events,
alumni mentorship, and skills tracking.
"""

from __future__ import annotations

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.sql_safety import escape_like
from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.infrastructure.exceptions import DatabaseError, ValidationError
from education_system.university_system.modules.shared.utils.i18n import (
    get_text,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.language_selector import (
    display_language_menu_option,
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
                return job_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error creating job posting: {e}") from e

    @staticmethod
    def apply_for_job(job_id: int, student_id: str, resume_id: Optional[int],
                     cover_letter: str = "") -> int:
        try:
            with transaction() as conn:
                cursor = conn.execute('''
                    INSERT INTO job_applications (job_id, applicant_id, cover_letter,
                                                  application_date, status)
                    VALUES (?, ?, ?, date('now'), 'pending')
                ''', (job_id, student_id, cover_letter))
                application_id = cursor.lastrowid
                return application_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error applying for job: {e}") from e

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
                cursor = conn.execute('''
                    INSERT INTO unified_event_registrations (event_id, student_id, registered_at)
                    VALUES (?, ?, datetime('now'))
                ''', (event_id, student_id))
                registration_id = cursor.lastrowid
                return registration_id
        except sqlite3.Error as e:
            raise DatabaseError(f"Error registering for event: {e}") from e

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
    print(f"8. {get_text('career.menu.language', default='Language')}")
    print(f"9. {get_text('career.menu.return_main', default='Return to Main Menu')}")
    print("="*50)

    while True:
        try:
            choice = input(f"\n{get_text('career.prompt.choice', default='Enter your choice (1-9)')}: ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n{get_text('career.feature_available', default='Feature available via Career Services managers')}")
                print("Use: from education_system.university_system.modules.domain.career.services import JobManager")
            elif choice == '8':
                display_language_menu_option()
            elif choice == '9':
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
        from education_system.university_system.modules.domain.career.gui.career_services_gui import (
            launch_career_services_gui as _launch,
        )
        return _launch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'JobManager', 'ResumeManager', 'InterviewManager',
    'CareerEventManager', 'MentorshipManager', 'SkillsManager',
    'display_career_services_menu',
    'launch_career_services_gui',
]
