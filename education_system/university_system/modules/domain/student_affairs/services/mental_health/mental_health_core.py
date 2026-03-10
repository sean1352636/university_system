"""
Mental Health & Wellness Portal Core Service

This module provides comprehensive mental health support including counseling appointments,
wellness resources, check-ins, peer support matching, and mindfulness resources.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.feature_gui_factory import create_gui_launcher

try:
    from education_system.university_system.infrastructure.email.email_service import send_email
    from education_system.university_system.infrastructure.email.template_utils import render_template
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False
    def send_email(*args, **kwargs):
        print(f"Email would be sent (email service not available)")
    def render_template(template_name, vars):
        return f"Template: {template_name}", "Email body would be here"


class CounselorManager:
    """Manages counselors and their availability"""

    @staticmethod
    def register_counselor(
        user_id: str,
        name: str,
        specialization: str = "",
        qualifications: str = "",
        availability_schedule: str = "",
        max_daily_appointments: int = 8
    ) -> int:
        """Register a new counselor"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO mental_health_counselors (
                    user_id, name, specialization, qualifications,
                    availability_schedule, max_daily_appointments
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, name, specialization, qualifications,
                  availability_schedule, max_daily_appointments))

            counselor_id = cursor.lastrowid
            conn.commit()

            return counselor_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error registering counselor: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_available_counselors(appointment_date: str, specialization: str = "") -> List[Dict[str, Any]]:
        """Get list of available counselors for a specific date"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Base query
            query = '''
                SELECT c.*,
                       (SELECT COUNT(*) FROM mental_health_appointments
                        WHERE counselor_id = c.counselor_id
                        AND appointment_date = ?
                        AND status != 'cancelled') as daily_appointments
                FROM mental_health_counselors c
                WHERE c.is_active = 1
            '''
            params = [appointment_date]

            if specialization:
                query += ' AND c.specialization = ?'
                params.append(specialization)

            cursor.execute(query, params)

            counselors = []
            for row in cursor.fetchall():
                counselor = dict(row)
                # Check if below max daily appointments
                if counselor['daily_appointments'] < counselor['max_daily_appointments']:
                    counselors.append(counselor)

            return counselors

        finally:
            conn.close()

    @staticmethod
    def get_counselor_details(counselor_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a counselor"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM mental_health_counselors
                WHERE counselor_id = ?
            ''', (counselor_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

        finally:
            conn.close()


class AppointmentManager:
    """Manages counseling appointments with anonymous options"""

    @staticmethod
    def book_appointment(
        student_id: str,
        counselor_id: Optional[int],
        appointment_type: str,
        appointment_date: str,
        appointment_time: str,
        duration_minutes: int = 50,
        is_anonymous: bool = False,
        mode: str = "in-person",
        location: str = "",
        notes: str = ""
    ) -> Tuple[int, Optional[str]]:
        """
        Book a counseling appointment

        Returns:
            Tuple of (appointment_id, anonymous_code if anonymous)
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            anonymous_code = None

            if is_anonymous:
                # Generate anonymous code
                code_data = f"{student_id}_{datetime.now().timestamp()}"
                anonymous_code = hashlib.sha256(code_data.encode()).hexdigest()[:12].upper()

            cursor.execute('''
                INSERT INTO mental_health_appointments (
                    student_id, counselor_id, appointment_type, appointment_date,
                    appointment_time, duration_minutes, is_anonymous, anonymous_code,
                    mode, location, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, counselor_id, appointment_type, appointment_date,
                  appointment_time, duration_minutes, is_anonymous, anonymous_code,
                  mode, location, notes))

            appointment_id = cursor.lastrowid
            conn.commit()

            # Send confirmation email
            AppointmentManager._send_appointment_confirmation(appointment_id)

            return appointment_id, anonymous_code

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error booking appointment: {e}")
        finally:
            conn.close()

    @staticmethod
    def _send_appointment_confirmation(appointment_id: int) -> None:
        """Send appointment confirmation email"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT a.*, s.email_address, s.first_name, c.name as counselor_name
                FROM mental_health_appointments a
                JOIN students s ON a.student_id = s.student_id
                LEFT JOIN mental_health_counselors c ON a.counselor_id = c.counselor_id
                WHERE a.appointment_id = ?
            ''', (appointment_id,))

            appt = cursor.fetchone()
            if not appt:
                return

            if appt['is_anonymous']:
                subject, body = render_template('mental_health_appointment_anonymous', {
                    'appointment_type': appt['appointment_type'],
                    'appointment_date': appt['appointment_date'],
                    'appointment_time': appt['appointment_time'],
                    'duration_minutes': appt['duration_minutes'],
                    'mode': appt['mode'],
                    'location': appt['location'] if appt['location'] else 'TBD',
                    'anonymous_code': appt['anonymous_code']
                })
            else:
                subject, body = render_template('mental_health_appointment_named', {
                    'first_name': appt['first_name'],
                    'counselor_name': appt['counselor_name'] if appt['counselor_name'] else 'To be assigned',
                    'appointment_type': appt['appointment_type'],
                    'appointment_date': appt['appointment_date'],
                    'appointment_time': appt['appointment_time'],
                    'duration_minutes': appt['duration_minutes'],
                    'mode': appt['mode'],
                    'location': appt['location'] if appt['location'] else 'TBD'
                })

            send_email(appt['email_address'], subject, body)

        finally:
            conn.close()

    @staticmethod
    def cancel_appointment(appointment_id: int) -> bool:
        """Cancel an appointment"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE mental_health_appointments
                SET status = 'cancelled', updated_at = ?
                WHERE appointment_id = ?
            ''', (datetime.now().isoformat(), appointment_id))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error cancelling appointment: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_student_appointments(student_id: str) -> List[Dict[str, Any]]:
        """Get all appointments for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT a.*, c.name as counselor_name, c.specialization
                FROM mental_health_appointments a
                LEFT JOIN mental_health_counselors c ON a.counselor_id = c.counselor_id
                WHERE a.student_id = ?
                ORDER BY a.appointment_date DESC, a.appointment_time DESC
            ''', (student_id,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()


class ResourceManager:
    """Manages mental health resources library"""

    @staticmethod
    def add_resource(
        category: str,
        title: str,
        description: str,
        content_type: str,
        content_url: str = "",
        tags: str = ""
    ) -> int:
        """Add a mental health resource"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO mental_health_resources (
                    category, title, description, content_type, content_url, tags
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (category, title, description, content_type, content_url, tags))

            resource_id = cursor.lastrowid
            conn.commit()

            return resource_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding resource: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_resources_by_category(category: str) -> List[Dict[str, Any]]:
        """Get all resources in a category"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM mental_health_resources
                WHERE category = ? AND is_published = 1
                ORDER BY created_at DESC
            ''', (category,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    @staticmethod
    def search_resources(search_term: str) -> List[Dict[str, Any]]:
        """Search resources by title, description, or tags"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            search_pattern = f"%{search_term}%"
            cursor.execute('''
                SELECT * FROM mental_health_resources
                WHERE (title LIKE ? OR description LIKE ? OR tags LIKE ?)
                AND is_published = 1
                ORDER BY view_count DESC
            ''', (search_pattern, search_pattern, search_pattern))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    @staticmethod
    def increment_view_count(resource_id: int) -> None:
        """Increment view count for a resource"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE mental_health_resources
                SET view_count = view_count + 1
                WHERE resource_id = ?
            ''', (resource_id,))

            conn.commit()

        finally:
            conn.close()


class WellnessCheckInManager:
    """Manages wellness check-ins and mood tracking"""

    @staticmethod
    def record_checkin(
        student_id: str,
        mood_rating: int,
        stress_level: int,
        sleep_quality: Optional[int] = None,
        notes: str = ""
    ) -> Tuple[int, bool]:
        """
        Record a wellness check-in

        Returns:
            Tuple of (checkin_id, follow_up_required)
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Determine if follow-up required
            follow_up_required = False
            if mood_rating <= 2 or stress_level >= 8:
                follow_up_required = True

            cursor.execute('''
                INSERT INTO mental_health_checkins (
                    student_id, mood_rating, stress_level, sleep_quality, notes, follow_up_required
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_id, mood_rating, stress_level, sleep_quality, notes, follow_up_required))

            checkin_id = cursor.lastrowid
            conn.commit()

            # If follow-up required, notify counselors
            if follow_up_required:
                WellnessCheckInManager._trigger_follow_up(student_id, checkin_id)

            return checkin_id, follow_up_required

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error recording check-in: {e}")
        finally:
            conn.close()

    @staticmethod
    def _trigger_follow_up(student_id: str, checkin_id: int) -> None:
        """Trigger follow-up notification to counseling team"""
        # In real system, this would notify counselors via email or dashboard alert
        print(f"Follow-up triggered for student {student_id} (Check-in ID: {checkin_id})")

    @staticmethod
    def get_student_checkin_history(student_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get check-in history for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()

            cursor.execute('''
                SELECT * FROM mental_health_checkins
                WHERE student_id = ? AND checkin_date >= ?
                ORDER BY checkin_date DESC, checkin_time DESC
            ''', (student_id, cutoff_date))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    @staticmethod
    def get_wellness_trends(student_id: str) -> Dict[str, Any]:
        """Get wellness trends and averages"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT
                    AVG(mood_rating) as avg_mood,
                    AVG(stress_level) as avg_stress,
                    AVG(sleep_quality) as avg_sleep,
                    COUNT(*) as total_checkins
                FROM mental_health_checkins
                WHERE student_id = ? AND checkin_date >= date('now', '-30 days')
            ''', (student_id,))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}

        finally:
            conn.close()


class PeerSupportManager:
    """Manages peer support matching"""

    @staticmethod
    def create_peer_support_match(
        supporter_student_id: str,
        supported_student_id: str,
        support_type: str,
        notes: str = ""
    ) -> int:
        """Create a peer support match"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO mental_health_peer_support (
                    supporter_student_id, supported_student_id, support_type, notes
                )
                VALUES (?, ?, ?, ?)
            ''', (supporter_student_id, supported_student_id, support_type, notes))

            support_id = cursor.lastrowid
            conn.commit()

            return support_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error creating peer support match: {e}")
        finally:
            conn.close()

    @staticmethod
    def log_peer_session(support_id: int) -> None:
        """Log a peer support session"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE mental_health_peer_support
                SET session_count = session_count + 1, last_session_date = ?
                WHERE support_id = ?
            ''', (date.today().isoformat(), support_id))

            conn.commit()

        finally:
            conn.close()

    @staticmethod
    def get_active_peer_supports(student_id: str) -> List[Dict[str, Any]]:
        """Get active peer support relationships for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT ps.*,
                       s1.first_name as supporter_name,
                       s2.first_name as supported_name
                FROM mental_health_peer_support ps
                JOIN students s1 ON ps.supporter_student_id = s1.student_id
                JOIN students s2 ON ps.supported_student_id = s2.student_id
                WHERE (ps.supporter_student_id = ? OR ps.supported_student_id = ?)
                AND ps.status = 'active'
            ''', (student_id, student_id))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()


class MeditationManager:
    """Manages mindfulness and meditation resources"""

    @staticmethod
    def add_meditation_session(
        title: str,
        description: str,
        audio_url: str,
        duration_minutes: int,
        category: str,
        difficulty_level: str = "beginner"
    ) -> int:
        """Add a meditation session"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO mental_health_meditation_sessions (
                    title, description, audio_url, duration_minutes, category, difficulty_level
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, description, audio_url, duration_minutes, category, difficulty_level))

            session_id = cursor.lastrowid
            conn.commit()

            return session_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error adding meditation session: {e}")
        finally:
            conn.close()

    @staticmethod
    def track_meditation(student_id: str, session_id: int, completed: bool = False) -> int:
        """Track a meditation session"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            completion_pct = 100 if completed else 0
            completed_at = datetime.now().isoformat() if completed else None

            cursor.execute('''
                INSERT INTO mental_health_meditation_tracking (
                    student_id, session_id, completion_percentage, completed_at
                )
                VALUES (?, ?, ?, ?)
            ''', (student_id, session_id, completion_pct, completed_at))

            tracking_id = cursor.lastrowid

            # Increment play count
            cursor.execute('''
                UPDATE mental_health_meditation_sessions
                SET play_count = play_count + 1
                WHERE session_id = ?
            ''', (session_id,))

            conn.commit()

            return tracking_id

        except Exception as e:
            conn.rollback()
            raise Exception(f"Error tracking meditation: {e}")
        finally:
            conn.close()

    @staticmethod
    def get_meditation_sessions(category: str = "", difficulty: str = "") -> List[Dict[str, Any]]:
        """Get meditation sessions with optional filters"""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            query = 'SELECT * FROM mental_health_meditation_sessions WHERE 1=1'
            params = []

            if category:
                query += ' AND category = ?'
                params.append(category)

            if difficulty:
                query += ' AND difficulty_level = ?'
                params.append(difficulty)

            query += ' ORDER BY play_count DESC'

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()


def display_mental_health_menu(auth):
    """Display the Mental Health & Wellness Portal CLI menu"""
    print("\n" + "="*50)
    print("    MENTAL HEALTH & WELLNESS PORTAL")
    print("="*50)
    print("1. Schedule Counseling Appointment")
    print("2. Wellness Check-in")
    print("3. Peer Support Matching")
    print("4. Mindfulness & Meditation Resources")
    print("5. Crisis Hotline Information")
    print("6. View Counselor Profiles")
    print("7. Track Wellness Progress")
    print("8. Return to Main Menu")
    print("="*50)

    while True:
        try:
            choice = input("\nEnter your choice (1-8): ").strip()
            if choice in ['1', '2', '3', '4', '5', '6', '7']:
                print(f"\n🧠 Feature available via Mental Health managers")
                print("Use: from education_system.university_system.modules.domain.student_affairs.services.mental_health import CounselorManager")
            elif choice == '8':
                break
            else:
                print("❌ Invalid choice.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")


# Use factory to create GUI launcher
launch_mental_health_gui = create_gui_launcher(
    title="Mental Health & Wellness Portal",
    description="""Comprehensive mental health and wellness support for students.

Features:
• Counseling appointments
• Wellness check-ins
• Peer support matching
• Mindfulness & meditation
• Crisis hotline access
• Progress tracking""",
    cli_instruction="Use CLI: Mental Health & Wellness Portal"
)



__all__ = [
    'CounselorManager',
    'AppointmentManager',
    'ResourceManager',
    'WellnessCheckInManager',
    'PeerSupportManager',
    'MeditationManager',
    'display_mental_health_menu',
    'launch_mental_health_gui',
]
