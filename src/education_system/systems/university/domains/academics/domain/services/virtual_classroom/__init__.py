"""
Virtual Classroom Integration Module

Provides comprehensive virtual classroom capabilities including:
- Classroom management (Zoom, Teams, Google Meet integration)
- Session scheduling and management
- Participant tracking and attendance
- Recording management
- Attendance published to the central attendance records

Chat, polls and breakout rooms were removed: the meeting itself runs on
Zoom/Teams/Meet, which provide all three natively, and nothing synced
them back — the local copies could only ever be a second, emptier record
of what happened in the real meeting.

Managers:
    - VirtualClassroomManager: Create and manage virtual classrooms
    - SessionManager: Schedule and manage sessions
    - ParticipantManager: Track participants and attendance
    - RecordingManager: Manage session recordings

Example Usage:
    from education_system.systems.university.domains.academics.domain.services.virtual_classroom import (
        VirtualClassroomManager,
        SessionManager
    )

    # Create a classroom
    classroom_mgr = VirtualClassroomManager()
    classroom_id = classroom_mgr.create_classroom(
        session_name="Python 101",
        instructor_id=1,
        platform="zoom"
    )

    # Schedule a session
    session_mgr = SessionManager()
    from datetime import datetime, timedelta
    session_id = session_mgr.create_session(
        classroom_id=classroom_id,
        start_time=datetime.now() + timedelta(days=1),
        duration_minutes=90
    )
"""

from education_system.systems.university.domains.academics.domain.services.virtual_classroom.classroom_manager import VirtualClassroomManager
from education_system.systems.university.domains.academics.domain.services.virtual_classroom.session_manager import SessionManager
from education_system.systems.university.domains.academics.domain.services.virtual_classroom.participant_manager import ParticipantManager
from education_system.systems.university.domains.academics.domain.services.virtual_classroom.recording_manager import RecordingManager
from education_system.systems.university.domains.academics.domain.services.virtual_classroom.schema import create_virtual_classroom_tables
from education_system.systems.university.domains.academics.domain.services.virtual_classroom.attendance_sync import sync_session_attendance

__all__ = [
    'VirtualClassroomManager',
    'SessionManager',
    'ParticipantManager',
    'RecordingManager',
    'create_virtual_classroom_tables',
    'sync_session_attendance',
]
