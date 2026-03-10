"""
Accessibility & Accommodation Tools Service

Manages accessibility profiles, accommodation requests, exam accommodations,
alternative materials, and assistive technology.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity


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

                log_activity('update', 'accommodation_request', request_id=request_id,
                           details={'status': status, 'reviewer_id': reviewer_id})
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


def display_accessibility_menu(auth):
    """Display CLI menu for accessibility tools"""
    print("\n" + "="*50)
    print("   ACCESSIBILITY & ACCOMMODATION TOOLS")
    print("="*50)
    print("1. Accessibility Profiles")
    print("2. Accommodation Requests")
    print("3. Exam Accommodations")
    print("4. Assistive Technology Requests")
    print("5. Alternative Materials")
    print("6. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-6): ").strip()
            if choice in ['1', '2', '3', '4', '5']:
                print(f"\n♿ Feature available via Accessibility managers")
            elif choice == '6':
                break
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
