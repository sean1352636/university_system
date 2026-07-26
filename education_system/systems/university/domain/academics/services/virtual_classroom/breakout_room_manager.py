"""
Breakout Room Manager
Handles breakout room creation and management
"""

from education_system.systems.university.infrastructure.database.db import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from education_system.systems.university.infrastructure.paths import DEFAULT_DB_PATH

class BreakoutRoomManager:
    """Manager for breakout room operations"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_DB_PATH

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def create_breakout_room(
        self,
        session_id: int,
        room_name: str,
        room_number: int,
        participants: List[int],
        facilitator_id: Optional[int] = None,
        max_capacity: int = 10,
        topic: Optional[str] = None,
        duration_minutes: int = 15
    ) -> Optional[int]:
        """Create a breakout room"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                participants_json = json.dumps(participants)

                cursor.execute("""
                    INSERT INTO breakout_rooms (
                        session_id, room_name, room_number, participants,
                        facilitator_id, max_capacity, topic, duration
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, room_name, room_number, participants_json,
                      facilitator_id, max_capacity, topic, duration_minutes))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            print(f"Error creating breakout room: {e}")
            return None

    def start_breakout_room(self, room_id: int) -> bool:
        """Start a breakout room"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE breakout_rooms
                    SET is_active = 1, start_time = CURRENT_TIMESTAMP
                    WHERE room_id = ?
                """, (room_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error starting breakout room: {e}")
            return False

    def end_breakout_room(self, room_id: int) -> bool:
        """End a breakout room"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE breakout_rooms
                    SET is_active = 0, end_time = CURRENT_TIMESTAMP
                    WHERE room_id = ?
                """, (room_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error ending breakout room: {e}")
            return False

    def add_participant_to_room(self, room_id: int, user_id: int) -> bool:
        """Add a participant to a breakout room"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT participants, max_capacity FROM breakout_rooms
                    WHERE room_id = ?
                """, (room_id,))

                row = cursor.fetchone()
                if not row:
                    return False

                participants = json.loads(row[0]) if row[0] else []
                max_capacity = row[1]

                if len(participants) >= max_capacity:
                    print("Breakout room is at max capacity")
                    return False

                if user_id not in participants:
                    participants.append(user_id)

                    cursor.execute("""
                        UPDATE breakout_rooms
                        SET participants = ?
                        WHERE room_id = ?
                    """, (json.dumps(participants), room_id))
                    conn.commit()
                    return True

                return False
        except Exception as e:
            print(f"Error adding participant to room: {e}")
            return False

    def remove_participant_from_room(self, room_id: int, user_id: int) -> bool:
        """Remove a participant from a breakout room"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT participants FROM breakout_rooms
                    WHERE room_id = ?
                """, (room_id,))

                row = cursor.fetchone()
                if not row:
                    return False

                participants = json.loads(row[0]) if row[0] else []

                if user_id in participants:
                    participants.remove(user_id)

                    cursor.execute("""
                        UPDATE breakout_rooms
                        SET participants = ?
                        WHERE room_id = ?
                    """, (json.dumps(participants), room_id))
                    conn.commit()
                    return True

                return False
        except Exception as e:
            print(f"Error removing participant from room: {e}")
            return False

    def get_breakout_room(self, room_id: int) -> Optional[Dict[str, Any]]:
        """Get breakout room details"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM breakout_rooms
                    WHERE room_id = ?
                """, (room_id,))

                row = cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    result = dict(zip(columns, row))
                    if result.get('participants'):
                        result['participants'] = json.loads(result['participants'])
                    return result
                return None
        except Exception as e:
            print(f"Error getting breakout room: {e}")
            return None

    def get_session_breakout_rooms(
        self,
        session_id: int,
        active_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all breakout rooms for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM breakout_rooms WHERE session_id = ?"
                params = [session_id]

                if active_only:
                    query += " AND is_active = 1"

                query += " ORDER BY room_number ASC"

                cursor.execute(query, params)
                columns = [d[0] for d in cursor.description]

                results = []
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    if result.get('participants'):
                        result['participants'] = json.loads(result['participants'])
                    results.append(result)

                return results
        except Exception as e:
            print(f"Error getting session breakout rooms: {e}")
            return []

    def get_user_breakout_room(
        self,
        session_id: int,
        user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Find which breakout room a user is in"""
        try:
            rooms = self.get_session_breakout_rooms(session_id, active_only=True)
            for room in rooms:
                if user_id in room.get('participants', []):
                    return room
            return None
        except Exception as e:
            print(f"Error finding user's breakout room: {e}")
            return None

    def auto_assign_breakout_rooms(
        self,
        session_id: int,
        user_ids: List[int],
        num_rooms: int,
        room_name_prefix: str = "Room"
    ) -> List[int]:
        """Automatically assign users to breakout rooms"""
        try:
            # Distribute users evenly across rooms
            rooms_per_group = len(user_ids) // num_rooms
            room_ids = []

            for i in range(num_rooms):
                start_idx = i * rooms_per_group
                if i == num_rooms - 1:
                    # Last room gets any remaining users
                    room_participants = user_ids[start_idx:]
                else:
                    room_participants = user_ids[start_idx:start_idx + rooms_per_group]

                room_id = self.create_breakout_room(
                    session_id=session_id,
                    room_name=f"{room_name_prefix} {i + 1}",
                    room_number=i + 1,
                    participants=room_participants
                )

                if room_id:
                    room_ids.append(room_id)

            return room_ids
        except Exception as e:
            print(f"Error auto-assigning breakout rooms: {e}")
            return []
