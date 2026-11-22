"""
Accessibility & Accommodation Tools Service

Manages accessibility profiles, accommodation requests, exam accommodations,
alternative materials, and assistive technology.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.activity_logger import log_activity


class AccessibilityProfileManager:
    """Manages student accessibility profiles"""

    @staticmethod
    def create_profile(user_id: int, disabilities: List[str],
                      accommodations: List[str], assistive_technologies: List[str]) -> int:
        """Create or update accessibility profile"""
        try:
            import json
            with transaction() as conn:
                cursor = conn.cursor()

                # Check if profile exists
                cursor.execute('SELECT profile_id FROM accessibility_profiles WHERE user_id = ?', (user_id,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing
                    cursor.execute('''
                        UPDATE accessibility_profiles
                        SET disabilities = ?, accommodations = ?, assistive_technologies = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    ''', (json.dumps(disabilities), json.dumps(accommodations),
                         json.dumps(assistive_technologies), user_id))
                    profile_id = existing['profile_id']
                else:
                    # Create new
                    cursor.execute('''
                        INSERT INTO accessibility_profiles (user_id, disabilities, accommodations, assistive_technologies)
                        VALUES (?, ?, ?, ?)
                    ''', (user_id, json.dumps(disabilities), json.dumps(accommodations),
                         json.dumps(assistive_technologies)))
                    profile_id = cursor.lastrowid

                log_activity('update', 'accessibility_profile', profile_id=profile_id,
                           details={'user_id': user_id})
                return profile_id
        except Exception as e:
            raise Exception(f"Error creating profile: {e}")

    @staticmethod
    def get_profile(user_id: int) -> Optional[Dict[str, Any]]:
        """Get accessibility profile for a user"""
        try:
            import json
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM accessibility_profiles WHERE user_id = ?
                ''', (user_id,))
                row = cursor.fetchone()

                if row:
                    profile = dict(row)
                    # Parse JSON fields
                    profile['disabilities'] = json.loads(profile.get('disabilities', '[]'))
                    profile['accommodations'] = json.loads(profile.get('accommodations', '[]'))
                    profile['assistive_technologies'] = json.loads(profile.get('assistive_technologies', '[]'))
                    return profile
                return None
        except Exception as e:
            raise Exception(f"Error getting profile: {e}")


class AccommodationRequestManager:
    """Manages accommodation requests"""

    @staticmethod
    def submit_request(student_id: int, accommodation_type: str,
                      description: str) -> int:
        """Submit a new accommodation request"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO accommodation_requests
                    (student_id, accommodation_type, description, status)
                    VALUES (?, ?, ?, 'pending')
                ''', (student_id, accommodation_type, description))
                request_id = cursor.lastrowid

                log_activity('create', 'accommodation_request', request_id=request_id,
                           details={'student_id': student_id, 'type': accommodation_type})
                return request_id
        except Exception as e:
            raise Exception(f"Error submitting request: {e}")

    @staticmethod
    def review_request(request_id: int, reviewer_id: int, status: str, notes: str) -> None:
        """Review an accommodation request"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE accommodation_requests
                    SET status = ?, reviewed_by = ?, review_date = CURRENT_TIMESTAMP,
                        review_notes = ?
                    WHERE request_id = ?
                ''', (status, reviewer_id, notes, request_id))

                if status == 'approved':
                    # Create approval record
                    cursor.execute('''
                        INSERT INTO accommodation_approvals (request_id, approved_by, notes)
                        VALUES (?, ?, ?)
                    ''', (request_id, reviewer_id, notes))

                # Pull the request so we can broadcast the decision.
                row = cursor.execute(
                    "SELECT student_id, accommodation_type FROM accommodation_requests "
                    "WHERE request_id = ?",
                    (request_id,),
                ).fetchone()

                log_activity('update', 'accommodation_request', request_id=request_id,
                           details={'status': status, 'reviewer_id': reviewer_id})

            if row:
                try:
                    from education_system.systems.university.services.bus.integration_bus import (
                        publish_accommodation_decision,
                    )
                    publish_accommodation_decision(
                        request_id,
                        student_id=str(row[0]),
                        status=status,
                        accommodation_type=row[1] or "general",
                    )
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
        except Exception as e:
            raise Exception(f"Error reviewing request: {e}")

    @staticmethod
    def get_requests(student_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict]:
        """Get accommodation requests"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                query = 'SELECT * FROM accommodation_requests WHERE 1=1'
                params = []

                if student_id:
                    query += ' AND student_id = ?'
                    params.append(student_id)
                if status:
                    query += ' AND status = ?'
                    params.append(status)

                query += ' ORDER BY requested_date DESC'
                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error getting requests: {e}")


class ExamAccommodationManager:
    """Manages exam accommodations"""

    @staticmethod
    def create_accommodation(student_id: int, exam_id: Optional[int],
                           extended_time: int, separate_room: bool,
                           assistive_technology: str, reader_scribe: bool) -> int:
        """Create exam accommodation"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO exam_accommodations
                    (student_id, exam_id, extended_time, separate_room,
                     assistive_technology, reader_scribe, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'active')
                ''', (student_id, exam_id, extended_time, separate_room,
                     assistive_technology, reader_scribe))
                accommodation_id = cursor.lastrowid

                log_activity('create', 'exam_accommodation',
                           accommodation_id=accommodation_id,
                           details={'student_id': student_id})
            try:
                from education_system.systems.university.services.bus.integration_bus import (
                    publish_accommodation_decision,
                )
                publish_accommodation_decision(
                    accommodation_id,
                    student_id=str(student_id),
                    status="approved",
                    accommodation_type="exam_accommodation",
                    extended_time_pct=int(extended_time or 0),
                    separate_room=bool(separate_room),
                    reader_scribe=bool(reader_scribe),
                    assistive_technology=assistive_technology,
                    exam_id=exam_id,
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
            return accommodation_id
        except Exception as e:
            raise Exception(f"Error creating accommodation: {e}")

    @staticmethod
    def get_accommodations(student_id: Optional[int] = None) -> List[Dict]:
        """Get exam accommodations"""
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                if student_id:
                    cursor.execute('''
                        SELECT * FROM exam_accommodations
                        WHERE student_id = ? AND status = 'active'
                    ''', (student_id,))
                else:
                    cursor.execute('SELECT * FROM exam_accommodations WHERE status = "active"')
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            raise Exception(f"Error getting accommodations: {e}")


class AssistiveTechManager:
    """Manages assistive technology requests"""

    @staticmethod
    def submit_request(student_id: int, technology_type: str) -> int:
        """Submit assistive technology request"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO assistive_tech_requests (student_id, technology_type, status)
                    VALUES (?, ?, 'pending')
                ''', (student_id, technology_type))
                request_id = cursor.lastrowid

                log_activity('create', 'assistive_tech_request', request_id=request_id,
                           details={'student_id': student_id, 'type': technology_type})
                return request_id
        except Exception as e:
            raise Exception(f"Error submitting request: {e}")

    @staticmethod
    def fulfill_request(request_id: int) -> None:
        """Mark assistive tech request as fulfilled"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE assistive_tech_requests
                    SET status = 'fulfilled', fulfilled_date = CURRENT_TIMESTAMP
                    WHERE request_id = ?
                ''', (request_id,))

                log_activity('update', 'assistive_tech_request', request_id=request_id,
                           details={'status': 'fulfilled'})
        except Exception as e:
            raise Exception(f"Error fulfilling request: {e}")


REVIEWER_ROLES = ("admin", "administrator", "superadmin", "staff", "nurse", "doctor",
                  "clinician", "health_admin", "disability_officer", "accessibility_officer")
REQUEST_STATUSES = ("approved", "denied", "more_info_needed")


def _cli_user(auth):
    user = getattr(auth, "current_user", None) or {}
    role = str(user.get("role") or "").lower()
    own = (user.get("student_id") or user.get("username")) if role == "student" else None
    return user, role, own


def _cli_list(title, rows, columns):
    print(f"\n----- {title} -----")
    if not rows:
        print("  (none)")
        return
    for row in rows:
        print("  " + "  |  ".join(f"{label}: {row.get(key) if row.get(key) not in (None, '') else '-'}"
                                  for key, label in columns))


def display_accessibility_menu(auth):
    """Accessibility & accommodation tools for the CLI, over the same managers
    as the Accessibility Tools window. A student works on their own profile
    and requests; reviewers (staff, the health team, disability officers)
    see and decide everyone's."""
    user, role, own = _cli_user(auth)
    if not user:
        print("Sign in to use the accessibility tools.")
        return
    reviewer = role in REVIEWER_ROLES
    if not reviewer and not own:
        print("The accessibility tools are for students and the staff who support them.")
        return

    def ask_student():
        if own:
            return own
        return input("Student ID: ").strip()

    while True:
        print("\n" + "=" * 50)
        print("   ACCESSIBILITY & ACCOMMODATION TOOLS")
        print("=" * 50)
        print("1. View accessibility profile")
        print("2. Create / update accessibility profile")
        print("3. Accommodation requests")
        print("4. Submit an accommodation request")
        if reviewer:
            print("5. Review an accommodation request")
            print("6. Exam accommodations")
            print("7. Add an exam accommodation")
        print("8. Request assistive technology")
        if reviewer:
            print("9. Mark assistive technology request fulfilled")
        print("0. Return")
        choice = input("\nEnter your choice: ").strip()
        try:
            if choice in ("0", ""):
                break
            if choice == "1":
                profile = AccessibilityProfileManager.get_profile(ask_student())
                if not profile:
                    print("No accessibility profile on record.")
                else:
                    for key in ("disabilities", "accommodations", "assistive_technologies"):
                        print(f"{key.replace('_', ' ').title()}: {', '.join(profile[key]) or '-'}")
            elif choice == "2":
                sid = ask_student()
                split = lambda text: [x.strip() for x in text.split(",") if x.strip()]
                pid = AccessibilityProfileManager.create_profile(
                    sid, split(input("Disabilities / conditions (comma separated): ")),
                    split(input("Accommodations needed (comma separated): ")),
                    split(input("Assistive technologies (comma separated): ")))
                print(f"Profile saved (#{pid}).")
            elif choice == "3":
                status = None if own else (input("Status filter (blank for all): ").strip() or None)
                _cli_list("Accommodation requests",
                          AccommodationRequestManager.get_requests(own, status),
                          (("request_id", "#"), ("student_id", "Student"),
                           ("accommodation_type", "Type"), ("status", "Status"),
                           ("requested_date", "Requested"), ("review_notes", "Notes")))
            elif choice == "4":
                sid = ask_student()
                kind = input("Accommodation type (e.g. extra time, note-taker): ").strip()
                description = input("Describe what you need and why: ").strip()
                if not kind or not description:
                    print("A type and a description are required.")
                    continue
                rid = AccommodationRequestManager.submit_request(sid, kind, description)
                print(f"Request #{rid} submitted; it is now pending review.")
            elif choice == "5" and reviewer:
                rid = input("Request number: ").strip()
                status = input(f"Decision ({'/'.join(REQUEST_STATUSES)}): ").strip().lower()
                if not rid.isdigit() or status not in REQUEST_STATUSES:
                    print("Enter a request number and one of the decisions listed.")
                    continue
                notes = input("Notes for the student: ").strip()
                AccommodationRequestManager.review_request(int(rid), user.get("id"), status, notes)
                print(f"Request #{rid} marked {status}.")
            elif choice == "6" and reviewer:
                sid = input("Student ID (blank for all): ").strip() or None
                _cli_list("Exam accommodations", ExamAccommodationManager.get_accommodations(sid),
                          (("accommodation_id", "#"), ("student_id", "Student"),
                           ("exam_id", "Exam"), ("extended_time", "Extra time %"),
                           ("separate_room", "Separate room"), ("reader_scribe", "Reader/scribe"),
                           ("assistive_technology", "Technology")))
            elif choice == "7" and reviewer:
                sid = input("Student ID: ").strip()
                exam = input("Exam ID (blank for all exams): ").strip()
                extra = input("Extended time (%): ").strip()
                aid = ExamAccommodationManager.create_accommodation(
                    sid, int(exam) if exam.isdigit() else None, int(extra) if extra.isdigit() else 0,
                    input("Separate room? (y/N): ").strip().lower() == "y",
                    input("Assistive technology (blank for none): ").strip(),
                    input("Reader / scribe? (y/N): ").strip().lower() == "y")
                print(f"Exam accommodation #{aid} added.")
            elif choice == "8":
                sid = ask_student()
                tech = input("Technology needed (e.g. screen reader): ").strip()
                if not tech:
                    print("Say which technology is needed.")
                    continue
                rid = AssistiveTechManager.submit_request(sid, tech)
                print(f"Assistive technology request #{rid} submitted.")
            elif choice == "9" and reviewer:
                rid = input("Request number: ").strip()
                if rid.isdigit():
                    AssistiveTechManager.fulfill_request(int(rid))
                    print(f"Request #{rid} marked fulfilled.")
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


__all__ = [
    'AccessibilityProfileManager',
    'AccommodationRequestManager',
    'ExamAccommodationManager',
    'AssistiveTechManager',
    'display_accessibility_menu',
]
