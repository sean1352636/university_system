"""Data persistence and database integration for the Exam Scheduling System."""

import csv
import json
import logging
from contextlib import closing
from typing import List, Dict, Optional, Tuple

from education_system.post_18.university_system.modules.domain.academics.gui.exam_management.models import Exam, Room
from education_system.post_18.university_system.modules.domain.academics.gui.exam_management import conflicts as conflict_utils
from education_system.post_18.university_system.modules.domain.academics.gui.exam_management import notifications as notification_utils
from education_system.post_18.university_system.modules.domain.academics.gui.exam_management import room_booking as room_booking_utils
from education_system.post_18.university_system.modules.domain.academics.gui.exam_management import external_examiners_link as ee_link

logger = logging.getLogger(__name__)

# Database imports
try:
    from education_system.post_18.university_system.infrastructure.database.db import get_connection, transaction
    from education_system.post_18.university_system.core import paths
    HAS_DB = True
except ImportError:
    HAS_DB = False

# Academic calendar integration
try:
    from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.database import DatabaseManager as CalendarDB
    HAS_CALENDAR = True
except ImportError:
    HAS_CALENDAR = False


class DataManager:
    """Handles data persistence for exams and rooms with database integration."""

    def __init__(self, data_dir: str = None):
        # Legacy parameter kept for backward compatibility
        # All data is now stored in the database
        self.exams: List[Exam] = []
        self.rooms: List[Room] = []
        self._instructors_cache: List[Dict] = []
        self._modules_cache: Dict[str, Dict] = {}
        self._ensure_database_tables()
        self.load_data()
        # _load_instructors() is invoked lazily by get_instructors() — skipping
        # the extra round trip here keeps GUI startup snappy.

    def _ensure_database_tables(self):
        """Ensure the exams table exists in the database."""
        if not HAS_DB:
            return

        try:
            with transaction() as conn:
                # Create exams table if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS exams (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        module_code TEXT NOT NULL,
                        module_name TEXT,
                        date TEXT NOT NULL,
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        room TEXT,
                        instructor_id INTEGER,
                        instructor_name TEXT,
                        students_enrolled INTEGER DEFAULT 0,
                        enrolled_student_ids TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (instructor_id) REFERENCES instructors(id)
                    )
                """)
                # Migration: parent_exam_id links resits to their original exam.
                cols = {r[1] for r in conn.execute(
                    "PRAGMA table_info(exams)").fetchall()}
                if "parent_exam_id" not in cols:
                    try:
                        conn.execute(
                            "ALTER TABLE exams ADD COLUMN parent_exam_id INTEGER")
                    except Exception:
                        logger.exception("exams.parent_exam_id ALTER skipped")
                if "overflow_room" not in cols:
                    try:
                        conn.execute(
                            "ALTER TABLE exams ADD COLUMN overflow_room TEXT")
                    except Exception:
                        logger.exception("exams.overflow_room ALTER skipped")
        except Exception as e:
            logger.warning(f"Failed to create exams table: {e}")

    def load_data(self):
        """Load exams and rooms from database."""
        # Load exams from database
        self._load_exams_from_db()

        # Load rooms from database (shared with facilities management)
        self._load_rooms_from_db()

    def _load_exams_from_db(self):
        """Load exams from database."""
        if not HAS_DB:
            logger.warning("Database not available, cannot load exams")
            return

        try:
            with closing(get_connection()) as conn:
                cursor = conn.execute("""
                    SELECT id, module_code, module_name, date, start_time, end_time,
                           room, instructor_id, instructor_name, students_enrolled,
                           enrolled_student_ids, overflow_room
                    FROM exams
                    ORDER BY date, start_time
                """)

                self.exams = []
                for row in cursor.fetchall():
                    (exam_id, module_code, module_name, date, start_time, end_time,
                     room, instructor_id, instructor_name, students_enrolled,
                     enrolled_student_ids, overflow_room) = row

                    # Parse enrolled_student_ids
                    if enrolled_student_ids:
                        try:
                            student_ids = json.loads(enrolled_student_ids) if isinstance(enrolled_student_ids, str) else enrolled_student_ids
                        except (ValueError, json.JSONDecodeError):
                            student_ids = []
                    else:
                        student_ids = []

                    exam = Exam(
                        id=exam_id,
                        module_code=module_code,
                        module_name=module_name or '',
                        date=date,
                        start_time=start_time,
                        end_time=end_time,
                        room=room or '',
                        instructor_id=instructor_id,
                        instructor_name=instructor_name or '',
                        students_enrolled=students_enrolled or 0,
                        enrolled_student_ids=student_ids,
                        overflow_room=overflow_room,
                    )
                    self.exams.append(exam)

        except Exception as e:
            logger.error(f"Failed to load exams from database: {e}")
            self.exams = []

    def _load_rooms_from_db(self):
        """Load rooms from database (shared table with facilities management)."""
        if not HAS_DB:
            logger.warning("Database not available, cannot load rooms")
            return

        try:
            with closing(get_connection()) as conn:
                cursor = conn.execute("""
                    SELECT
                        id,
                        COALESCE(room_name, room_number) as name,
                        building,
                        capacity,
                        equipment,
                        features
                    FROM rooms
                    WHERE is_active = 1 OR status = 'available'
                    ORDER BY building, name
                """)

                self.rooms = []
                for row in cursor.fetchall():
                    room_id, name, building, capacity, equipment, features = row

                    # Parse equipment/features to determine has_computers and has_projector
                    has_computers = False
                    has_projector = False

                    # Check equipment field
                    if equipment:
                        equipment_lower = str(equipment).lower()
                        has_computers = 'computer' in equipment_lower
                        has_projector = 'projector' in equipment_lower

                    # Check features field (might be JSON)
                    if features:
                        try:
                            features_data = json.loads(features) if isinstance(features, str) else features
                            if isinstance(features_data, dict):
                                has_computers = has_computers or features_data.get('computers', False)
                                has_projector = has_projector or features_data.get('projector', False)
                            elif isinstance(features_data, list):
                                features_lower = [str(f).lower() for f in features_data]
                                has_computers = has_computers or any('computer' in f for f in features_lower)
                                has_projector = has_projector or any('projector' in f for f in features_lower)
                        except (ValueError, json.JSONDecodeError):
                            pass

                    room = Room(
                        id=room_id,
                        name=name or f"Room {room_id}",
                        building=building or "Unknown",
                        capacity=capacity or 0,
                        has_computers=has_computers,
                        has_projector=has_projector
                    )
                    self.rooms.append(room)

        except Exception as e:
            logger.error(f"Failed to load rooms from database: {e}")
            self.rooms = []

    def _load_instructors(self):
        """Load instructors from database."""
        if not HAS_DB:
            return
        try:
            with closing(get_connection()) as conn:
                cursor = conn.execute("""
                    SELECT id, first_name, last_name, email, department
                    FROM instructors
                    WHERE is_active = 1 OR status = 'Active'
                    ORDER BY last_name, first_name
                """)
                self._instructors_cache = [
                    {
                        'id': row[0],
                        'first_name': row[1],
                        'last_name': row[2],
                        'email': row[3],
                        'department': row[4],
                        'display_name': f"{row[1]} {row[2]}"
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.warning(f"Failed to load instructors from DB: {e}")
            self._instructors_cache = []

    def get_instructors(self) -> List[Dict]:
        """Get list of instructors for dropdown."""
        if not self._instructors_cache:
            self._load_instructors()
        return self._instructors_cache

    def get_instructor_by_id(self, instructor_id: int) -> Optional[Dict]:
        """Get instructor details by ID."""
        for inst in self._instructors_cache:
            if inst['id'] == instructor_id:
                return inst
        return None

    def get_all_modules(self) -> List[Dict]:
        """Get list of all modules from database."""
        if not HAS_DB:
            return []

        try:
            with closing(get_connection()) as conn:
                cursor = conn.execute("""
                    SELECT module_code, module_name, credits, description, semester
                    FROM modules
                    ORDER BY module_code
                """)
                modules = []
                for row in cursor.fetchall():
                    module_data = {
                        'module_code': row[0],
                        'module_name': row[1] or '',
                        'credits': row[2],
                        'description': row[3] or '',
                        'semester': row[4] or ''
                    }
                    modules.append(module_data)
                    # Cache the module
                    self._modules_cache[row[0]] = module_data
                return modules
        except Exception as e:
            logger.warning(f"Failed to get modules from database: {e}")
            return []

    def lookup_module(self, module_code: str) -> Optional[Dict]:
        """Look up module details from database."""
        if not HAS_DB:
            return None

        # Check cache first
        if module_code in self._modules_cache:
            return self._modules_cache[module_code]

        try:
            with closing(get_connection()) as conn:
                cursor = conn.execute("""
                    SELECT module_code, module_name, credits, description, semester
                    FROM modules
                    WHERE module_code = ?
                """, (module_code,))
                row = cursor.fetchone()
                if row:
                    module_data = {
                        'module_code': row[0],
                        'module_name': row[1],
                        'credits': row[2],
                        'description': row[3],
                        'semester': row[4]
                    }
                    self._modules_cache[module_code] = module_data
                    return module_data
        except Exception as e:
            logger.warning(f"Failed to lookup module {module_code}: {e}")
        return None

    def get_enrolled_students(self, module_code: str) -> List[Dict]:
        """Get list of students enrolled in a module."""
        if not HAS_DB:
            return []

        try:
            with closing(get_connection()) as conn:
                cursor = conn.execute("""
                    SELECT sm.student_id, s.first_name, s.last_name, s.email_address
                    FROM student_modules sm
                    LEFT JOIN students s ON sm.student_id = s.student_id
                    WHERE sm.module_code = ? AND LOWER(sm.status) = 'enrolled'
                    ORDER BY s.last_name, s.first_name
                """, (module_code,))
                students = []
                for row in cursor.fetchall():
                    students.append({
                        'student_id': row[0],
                        'first_name': row[1] or '',
                        'last_name': row[2] or '',
                        'email': row[3] or '',
                        'display_name': f"{row[1] or ''} {row[2] or ''} ({row[0]})"
                    })
                return students
        except Exception as e:
            logger.warning(f"Failed to get enrolled students for {module_code}: {e}")
            return []

    # --- Notification delegates ---

    def send_exam_notifications(self, exam: Exam) -> Tuple[int, int]:
        """Send email notifications about an exam to all enrolled students and instructor."""
        return notification_utils.send_exam_notifications(
            exam, self.get_enrolled_students, self.get_instructor_by_id
        )

    def send_exam_update_notifications(self, exam: Exam) -> Tuple[int, int]:
        """Send email notifications about an exam update."""
        return notification_utils.send_exam_update_notifications(
            exam, self.get_enrolled_students, self.get_instructor_by_id
        )

    def send_exam_cancellation_notifications(self, exam: Exam) -> Tuple[int, int]:
        """Email + in-app notify recipients that an exam was cancelled."""
        return notification_utils.send_exam_cancellation_notifications(
            exam, self.get_enrolled_students, self.get_instructor_by_id
        )

    def add_exam_to_calendar(self, exam: Exam) -> bool:
        """Add or update the calendar event for *exam* (idempotent upsert)."""
        return notification_utils.add_exam_to_calendar(exam)

    def update_exam_in_calendar(self, exam: Exam) -> bool:
        """Update the calendar event for *exam*. Same as add (upsert)."""
        return notification_utils.add_exam_to_calendar(exam)

    def remove_exam_from_calendar(self, exam_id) -> bool:
        """Remove the calendar event linked to *exam_id*."""
        return notification_utils.remove_exam_from_calendar(exam_id)

    # --- Room booking integration ---

    def reserve_room_for_exam(self, exam: Exam) -> bool:
        """Reserve the room for *exam* in the shared room_bookings table.

        Idempotent — calling again for the same exam updates the existing
        reservation. Returns False if the room can't be matched in the
        rooms catalog (e.g. free-text room name) or the DB is unavailable.
        """
        return room_booking_utils.reserve_room_for_exam(exam)

    def release_room_for_exam(self, exam_id) -> bool:
        """Release the shared room booking owned by *exam_id*."""
        return room_booking_utils.release_room_for_exam(exam_id)

    def find_external_room_conflicts(self, date: str, start_time: str,
                                     end_time: str, room_name: str,
                                     exclude_exam_id: Optional[int] = None
                                     ) -> List[Tuple[str, str]]:
        """Return external (non-exam) bookings that overlap this slot."""
        return room_booking_utils.find_external_conflicts(
            date, start_time, end_time, room_name, exclude_exam_id,
        )

    # --- External examiner integration ---

    def list_active_examiners(self) -> List[Dict]:
        """Active examiners from the sibling external_examiners module."""
        return ee_link.list_active_examiners()

    def list_examiners_for_exam(self, exam_id: int) -> List[Dict]:
        return ee_link.list_examiners_for_exam(exam_id)

    def attach_external_examiner(self, exam_id: int, examiner_id: int,
                                 role: str = "") -> bool:
        return ee_link.attach_examiner(exam_id, examiner_id, role)

    def detach_external_examiner(self, exam_id: int,
                                 examiner_id: int) -> bool:
        return ee_link.detach_examiner(exam_id, examiner_id)

    # --- Data persistence ---

    def save_exams(self):
        """Save exams (deprecated - now saves to database)."""
        # This method is kept for backward compatibility but does nothing
        # Exams are now saved to database in add_exam/update_exam/delete_exam
        pass

    def save_rooms(self):
        """Save rooms (deprecated - now saves to database)."""
        # This method is kept for backward compatibility but does nothing
        # Rooms are now saved to database in add_room/update_room/delete_room
        pass

    def _save_exam_to_db(self, exam: Exam, is_new: bool = False):
        """Save an exam to the database."""
        if not HAS_DB:
            logger.error("Database not available, cannot save exam")
            raise RuntimeError("Database not available")

        # Calendar period gate (#4) — exam dates must fall in the
        # active exam_window and must not land on a holiday. Soft-fails
        # open if the calendar table is empty so first-run installs
        # aren't blocked.
        try:
            from education_system.post_18.university_system.modules.domain.academics.gui._cross_services import (
                current_period, is_holiday,
            )
            if exam.date:
                window = current_period("exam_window", on_date=exam.date)
                if window is None and current_period("exam_window") is not None:
                    raise RuntimeError(
                        f"Exam date {exam.date} is outside the active "
                        f"exam window. Update the calendar's exam_window "
                        f"or pick a date inside it."
                    )
                if is_holiday(exam.date):
                    raise RuntimeError(
                        f"Exam date {exam.date} falls on a holiday "
                        f"(see Academic Calendar). Pick a different date."
                    )
        except RuntimeError:
            raise
        except Exception as gate_err:
            logger.debug("exam date gate skipped: %s", gate_err)

        try:
            # Serialize enrolled_student_ids to JSON
            enrolled_ids_json = json.dumps(exam.enrolled_student_ids)

            with transaction() as conn:
                if is_new or exam.id == 0:
                    # Insert new exam
                    cursor = conn.execute("""
                        INSERT INTO exams (
                            module_code, module_name, date, start_time, end_time,
                            room, instructor_id, instructor_name, students_enrolled,
                            enrolled_student_ids, overflow_room
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        exam.module_code,
                        exam.module_name,
                        exam.date,
                        exam.start_time,
                        exam.end_time,
                        exam.room,
                        exam.instructor_id,
                        exam.instructor_name,
                        exam.students_enrolled,
                        enrolled_ids_json,
                        getattr(exam, 'overflow_room', None),
                    ))
                    exam.id = cursor.lastrowid
                else:
                    # Update existing exam
                    conn.execute("""
                        UPDATE exams SET
                            module_code = ?,
                            module_name = ?,
                            date = ?,
                            start_time = ?,
                            end_time = ?,
                            room = ?,
                            instructor_id = ?,
                            instructor_name = ?,
                            students_enrolled = ?,
                            enrolled_student_ids = ?,
                            overflow_room = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (
                        exam.module_code,
                        exam.module_name,
                        exam.date,
                        exam.start_time,
                        exam.end_time,
                        exam.room,
                        exam.instructor_id,
                        exam.instructor_name,
                        exam.students_enrolled,
                        enrolled_ids_json,
                        getattr(exam, 'overflow_room', None),
                        exam.id,
                    ))

        except Exception as e:
            logger.error(f"Failed to save exam to database: {e}")
            raise

    def _save_room_to_db(self, room: Room, is_new: bool = False):
        """Save a room to the database."""
        if not HAS_DB:
            logger.error("Database not available, cannot save room")
            raise RuntimeError("Database not available")

        try:
            # Build equipment list
            equipment_list = []
            if room.has_computers:
                equipment_list.append('Computers')
            if room.has_projector:
                equipment_list.append('Projector')
            equipment_str = ', '.join(equipment_list) if equipment_list else None

            # Build features JSON
            features = json.dumps({
                'computers': room.has_computers,
                'projector': room.has_projector
            })

            with transaction() as conn:
                if is_new or room.id == 0:
                    # Insert new room
                    cursor = conn.execute("""
                        INSERT INTO rooms (
                            room_number, room_name, building, capacity, room_type,
                            equipment, features, is_active, status
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'available')
                    """, (
                        room.name,  # room_number
                        room.name,  # room_name
                        room.building,
                        room.capacity,
                        'Exam Room',  # room_type
                        equipment_str,
                        features
                    ))
                    room.id = cursor.lastrowid
                else:
                    # Update existing room
                    conn.execute("""
                        UPDATE rooms SET
                            room_number = ?,
                            room_name = ?,
                            building = ?,
                            capacity = ?,
                            equipment = ?,
                            features = ?
                        WHERE id = ?
                    """, (
                        room.name,
                        room.name,
                        room.building,
                        room.capacity,
                        equipment_str,
                        features,
                        room.id
                    ))

        except Exception as e:
            logger.error(f"Failed to save room to database: {e}")
            raise

    def get_next_exam_id(self) -> int:
        if HAS_DB:
            # Get next ID from database
            try:
                with closing(get_connection()) as conn:
                    cursor = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM exams")
                    return cursor.fetchone()[0]
            except Exception:
                pass

        # Fallback to in-memory list
        if not self.exams:
            return 1
        return max(e.id for e in self.exams) + 1

    def get_next_room_id(self) -> int:
        if HAS_DB:
            # Get next ID from database
            try:
                with closing(get_connection()) as conn:
                    cursor = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM rooms")
                    return cursor.fetchone()[0]
            except Exception:
                pass

        # Fallback to in-memory list
        if not self.rooms:
            return 1
        return max(r.id for r in self.rooms) + 1

    def add_exam(self, exam: Exam):
        """Add a new exam to the database."""
        self._save_exam_to_db(exam, is_new=True)
        self.exams.append(exam)

    def update_exam(self, exam: Exam):
        """Update an existing exam in the database."""
        self._save_exam_to_db(exam, is_new=False)
        for i, e in enumerate(self.exams):
            if e.id == exam.id:
                self.exams[i] = exam
                return

    def delete_exam(self, exam_id: int):
        """Delete an exam from the database."""
        if HAS_DB:
            try:
                with transaction() as conn:
                    conn.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
            except Exception as e:
                logger.error(f"Failed to delete exam from database: {e}")
                raise

        self.exams = [e for e in self.exams if e.id != exam_id]

    def add_room(self, room: Room):
        """Add a new room to the database."""
        self._save_room_to_db(room, is_new=True)
        self.rooms.append(room)

    def update_room(self, room: Room):
        """Update an existing room in the database."""
        self._save_room_to_db(room, is_new=False)
        for i, r in enumerate(self.rooms):
            if r.id == room.id:
                self.rooms[i] = room
                return

    def delete_room(self, room_id: int):
        """Delete a room (marks as inactive in database for data integrity)."""
        if HAS_DB:
            try:
                with transaction() as conn:
                    # Soft delete: mark as inactive instead of hard delete
                    # This maintains referential integrity with other tables
                    conn.execute("""
                        UPDATE rooms
                        SET is_active = 0, status = 'inactive'
                        WHERE id = ?
                    """, (room_id,))
            except Exception as e:
                logger.error(f"Failed to delete room from database: {e}")
                raise

        self.rooms = [r for r in self.rooms if r.id != room_id]

    # --- Conflict detection delegates ---

    def check_conflict(self, date: str, start_time: str, end_time: str,
                       room: str, exclude_id: Optional[int] = None) -> bool:
        """Check if there's a scheduling conflict."""
        return conflict_utils.check_conflict(self.exams, date, start_time, end_time, room, exclude_id)

    def get_conflicting_exams(self, date: str, start_time: str, end_time: str,
                              room: str, exclude_id: Optional[int] = None) -> List[Exam]:
        """Get list of conflicting exams for a given date/time/room."""
        return conflict_utils.get_conflicting_exams(self.exams, date, start_time, end_time, room, exclude_id)

    def check_instructor_conflict(self, date: str, start_time: str, end_time: str,
                                  instructor_id: Optional[int], exclude_id: Optional[int] = None) -> List[Exam]:
        """Check if instructor has conflicting exams at the same time."""
        return conflict_utils.check_instructor_conflict(self.exams, date, start_time, end_time, instructor_id, exclude_id)

    def get_available_rooms(self, date: str, start_time: str, end_time: str,
                           min_capacity: int = 0, exclude_id: Optional[int] = None) -> List[Room]:
        """Get list of rooms available for a specific date/time with optional capacity filter."""
        return conflict_utils.get_available_rooms(self.exams, self.rooms, date, start_time, end_time, min_capacity, exclude_id)

    def get_exams_by_date_range(self, start_date: str, end_date: str) -> List[Exam]:
        """Get exams within a date range."""
        return conflict_utils.get_exams_by_date_range(self.exams, start_date, end_date)

    def get_exams_by_instructor(self, instructor_id: int) -> List[Exam]:
        """Get all exams for a specific instructor."""
        return conflict_utils.get_exams_by_instructor(self.exams, instructor_id)

    def get_exams_by_room(self, room_name: str) -> List[Exam]:
        """Get all exams in a specific room."""
        return conflict_utils.get_exams_by_room(self.exams, room_name)

    def export_to_csv(self, filepath: str):
        """Export exam schedule to CSV."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Module Code', 'Module Name', 'Date', 'Start Time',
                           'End Time', 'Room', 'Instructor', 'Students'])
            for exam in sorted(self.exams, key=lambda x: (x.date, x.start_time)):
                writer.writerow([exam.module_code, exam.module_name, exam.date,
                               exam.start_time, exam.end_time, exam.room,
                               exam.instructor_name, exam.students_enrolled])
