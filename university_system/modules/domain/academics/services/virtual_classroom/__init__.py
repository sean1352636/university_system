"""
Virtual Classroom Integration Module

Provides comprehensive virtual classroom capabilities including:
- Classroom management (Zoom, Teams, Google Meet integration)
- Session scheduling and management
- Participant tracking and attendance
- Recording management
- Breakout rooms
- Live polling and quizzes
- Chat and Q&A

Managers:
    - VirtualClassroomManager: Create and manage virtual classrooms
    - SessionManager: Schedule and manage sessions
    - ParticipantManager: Track participants and attendance
    - RecordingManager: Manage session recordings
    - BreakoutRoomManager: Create and manage breakout rooms
    - PollManager: Create polls and quizzes
    - ChatManager: Handle chat messages

Example Usage:
    from university_system.modules.domain.academics.services.virtual_classroom import (
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

from .classroom_manager import VirtualClassroomManager
from .session_manager import SessionManager
from .participant_manager import ParticipantManager
from .recording_manager import RecordingManager
from .breakout_room_manager import BreakoutRoomManager
from .poll_manager import PollManager
from .chat_manager import ChatManager
from .schema import create_virtual_classroom_tables

__all__ = [
    'VirtualClassroomManager',
    'SessionManager',
    'ParticipantManager',
    'RecordingManager',
    'BreakoutRoomManager',
    'PollManager',
    'ChatManager',
    'create_virtual_classroom_tables'
]
