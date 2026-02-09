#!/usr/bin/env python3
"""
Exam Scheduling System
A comprehensive GUI application for managing exam schedules, rooms, and courses.
Enhanced with database integration for modules, instructors, and email notifications.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime, timedelta
import json
import csv
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Tuple
import os
import logging
import re

# i18n import
try:
    from university_system.modules.shared.utils.i18n import get_text as _
except ImportError:
    def _(key, **kwargs):
        return key

# Database imports
try:
    from university_system.infrastructure.database.db import get_connection, transaction
    from university_system.modules.shared.constants import paths
    HAS_DB = True
except ImportError:
    HAS_DB = False

# Email imports
try:
    from university_system.infrastructure.email.email_service import send_email
    HAS_EMAIL = True
except ImportError:
    HAS_EMAIL = False

# Academic calendar integration
try:
    from university_system.modules.domain.academics.gui.academic_calendar.database import DatabaseManager as CalendarDB
    HAS_CALENDAR = True
except ImportError:
    HAS_CALENDAR = False

logger = logging.getLogger(__name__)


@dataclass
class Exam:
    """Represents an exam entry."""
    id: int
    module_code: str  # Changed from course_code
    module_name: str  # Changed from course_name
    date: str
    start_time: str
    end_time: str
    room: str
    instructor_id: Optional[int]  # Now stores instructor ID
    instructor_name: str  # Display name
    students_enrolled: int
    enrolled_student_ids: List[str] = field(default_factory=list)  # List of student IDs

    # Legacy field names for backward compatibility
    @property
    def course_code(self):
        return self.module_code

    @property
    def course_name(self):
        return self.module_name

    @property
    def instructor(self):
        return self.instructor_name

    def to_dict(self):
        d = asdict(self)
        # Store enrolled_student_ids as JSON string for compatibility
        d['enrolled_student_ids'] = json.dumps(d.get('enrolled_student_ids', []))
        return d

    @classmethod
    def from_dict(cls, data: dict):
        """Create Exam from dictionary, handling legacy data."""
        # Handle legacy field names
        if 'course_code' in data and 'module_code' not in data:
            data['module_code'] = data.pop('course_code')
        if 'course_name' in data and 'module_name' not in data:
            data['module_name'] = data.pop('course_name')
        if 'instructor' in data and 'instructor_name' not in data:
            data['instructor_name'] = data.pop('instructor')
        # Handle instructor_id
        if 'instructor_id' not in data:
            data['instructor_id'] = None
        # Handle enrolled_student_ids
        if 'enrolled_student_ids' not in data:
            data['enrolled_student_ids'] = []
        elif isinstance(data['enrolled_student_ids'], str):
            try:
                data['enrolled_student_ids'] = json.loads(data['enrolled_student_ids'])
            except json.JSONDecodeError:
                data['enrolled_student_ids'] = []
        return cls(**data)


@dataclass
class Room:
    """Represents an exam room."""
    id: int
    name: str
    building: str
    capacity: int
    has_computers: bool
    has_projector: bool
    
    def to_dict(self):
        return asdict(self)


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
        self._load_instructors()

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
            with get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, module_code, module_name, date, start_time, end_time,
                           room, instructor_id, instructor_name, students_enrolled,
                           enrolled_student_ids
                    FROM exams
                    ORDER BY date, start_time
                """)

                self.exams = []
                for row in cursor.fetchall():
                    exam_id, module_code, module_name, date, start_time, end_time, \
                    room, instructor_id, instructor_name, students_enrolled, enrolled_student_ids = row

                    # Parse enrolled_student_ids
                    if enrolled_student_ids:
                        try:
                            student_ids = json.loads(enrolled_student_ids) if isinstance(enrolled_student_ids, str) else enrolled_student_ids
                        except:
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
                        enrolled_student_ids=student_ids
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
            with get_connection() as conn:
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
                        except:
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
            with get_connection() as conn:
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
            with get_connection() as conn:
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
            with get_connection() as conn:
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
            with get_connection() as conn:
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

    def send_exam_notifications(self, exam: Exam) -> Tuple[int, int]:
        """Send email notifications about an exam to all enrolled students and instructor.

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not HAS_EMAIL:
            logger.warning("Email system not available")
            return (0, 0)

        success_count = 0
        failure_count = 0

        # Get enrolled students
        students = self.get_enrolled_students(exam.module_code)

        # Get instructor
        instructor = self.get_instructor_by_id(exam.instructor_id) if exam.instructor_id else None

        # Render email template for students
        try:
            from university_system.infrastructure.email.template_utils import render_template

            subject, body = render_template('academics/exam_scheduled_student', {
                'module_code': exam.module_code,
                'module_name': exam.module_name,
                'exam_date': exam.date,
                'start_time': exam.start_time,
                'end_time': exam.end_time,
                'room': exam.room,
                'instructor_name': exam.instructor_name
            })

            # Fallback if template not found
            if not subject or not body:
                subject = f"Exam Scheduled: {exam.module_code} - {exam.module_name}"
                body = f"Dear Student/Instructor,\n\nAn exam has been scheduled for {exam.module_code} - {exam.module_name} on {exam.date} from {exam.start_time} to {exam.end_time} in {exam.room}.\n\nBest regards,\nUniversity Examination Office"
        except Exception as e:
            logger.error(f"Error rendering email template: {e}")
            subject = f"Exam Scheduled: {exam.module_code} - {exam.module_name}"
            body = f"Dear Student/Instructor,\n\nAn exam has been scheduled for {exam.module_code} - {exam.module_name} on {exam.date} from {exam.start_time} to {exam.end_time} in {exam.room}.\n\nBest regards,\nUniversity Examination Office"

        # Send to students
        for student in students:
            if student.get('email'):
                try:
                    send_email(student['email'], subject, body)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send exam notification to {student['email']}: {e}")
                    failure_count += 1

        # Send to instructor
        if instructor and instructor.get('email'):
            try:
                from university_system.infrastructure.email.template_utils import render_template

                instructor_subject, instructor_body = render_template('academics/exam_scheduled_instructor', {
                    'instructor_name': instructor['display_name'],
                    'module_code': exam.module_code,
                    'module_name': exam.module_name,
                    'exam_date': exam.date,
                    'start_time': exam.start_time,
                    'end_time': exam.end_time,
                    'room': exam.room,
                    'students_enrolled': exam.students_enrolled
                })

                # Fallback if template not found
                if not instructor_subject or not instructor_body:
                    instructor_subject = f"Exam Scheduled (Instructor): {exam.module_code} - {exam.module_name}"
                    instructor_body = f"Dear {instructor['display_name']},\n\nYou have been assigned as the instructor for an exam on {exam.date} from {exam.start_time} to {exam.end_time} in {exam.room}.\n\nBest regards,\nUniversity Examination Office"

                send_email(instructor['email'], instructor_subject, instructor_body)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send exam notification to instructor {instructor['email']}: {e}")
                failure_count += 1

        return (success_count, failure_count)

    def send_exam_update_notifications(self, exam: Exam) -> Tuple[int, int]:
        """Send email notifications about an exam update to all enrolled students and instructor.

        Returns:
            Tuple of (success_count, failure_count)
        """
        if not HAS_EMAIL:
            logger.warning("Email system not available")
            return (0, 0)

        success_count = 0
        failure_count = 0

        # Get enrolled students
        students = self.get_enrolled_students(exam.module_code)

        # Get instructor
        instructor = self.get_instructor_by_id(exam.instructor_id) if exam.instructor_id else None

        # Render email template for students
        try:
            from university_system.infrastructure.email.template_utils import render_template

            subject, body = render_template('academics/exam_updated_student', {
                'module_code': exam.module_code,
                'module_name': exam.module_name,
                'exam_date': exam.date,
                'start_time': exam.start_time,
                'end_time': exam.end_time,
                'room': exam.room,
                'instructor_name': exam.instructor_name
            })

            # Fallback if template not found
            if not subject or not body:
                subject = f"Exam Updated: {exam.module_code} - {exam.module_name}"
                body = f"Dear Student/Instructor,\n\nIMPORTANT: The exam for {exam.module_code} - {exam.module_name} has been updated.\n\nNew details: {exam.date}, {exam.start_time} - {exam.end_time}, {exam.room}\n\nBest regards,\nUniversity Examination Office"
        except Exception as e:
            logger.error(f"Error rendering email template: {e}")
            subject = f"Exam Updated: {exam.module_code} - {exam.module_name}"
            body = f"Dear Student/Instructor,\n\nIMPORTANT: The exam for {exam.module_code} - {exam.module_name} has been updated.\n\nNew details: {exam.date}, {exam.start_time} - {exam.end_time}, {exam.room}\n\nBest regards,\nUniversity Examination Office"

        # Send to students
        for student in students:
            if student.get('email'):
                try:
                    send_email(student['email'], subject, body)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send exam update notification to {student['email']}: {e}")
                    failure_count += 1

        # Send to instructor
        if instructor and instructor.get('email'):
            try:
                from university_system.infrastructure.email.template_utils import render_template

                instructor_subject, instructor_body = render_template('academics/exam_updated_instructor', {
                    'instructor_name': instructor['display_name'],
                    'module_code': exam.module_code,
                    'module_name': exam.module_name,
                    'exam_date': exam.date,
                    'start_time': exam.start_time,
                    'end_time': exam.end_time,
                    'room': exam.room,
                    'students_enrolled': exam.students_enrolled
                })

                # Fallback if template not found
                if not instructor_subject or not instructor_body:
                    instructor_subject = f"Exam Updated (Instructor): {exam.module_code} - {exam.module_name}"
                    instructor_body = f"Dear {instructor['display_name']},\n\nIMPORTANT: The exam you are supervising has been updated.\n\nNew details: {exam.date}, {exam.start_time} - {exam.end_time}, {exam.room}\n\nBest regards,\nUniversity Examination Office"

                send_email(instructor['email'], instructor_subject, instructor_body)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send exam update notification to instructor {instructor['email']}: {e}")
                failure_count += 1

        return (success_count, failure_count)

    def add_exam_to_calendar(self, exam: Exam) -> bool:
        """Add exam as an event to the academic calendar (events table)."""
        if not HAS_DB:
            logger.warning("Database not available for calendar integration")
            return False

        try:
            import uuid
            event_id = f"EXAM-{exam.module_code}-{uuid.uuid4().hex[:8]}"
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Combine date and time for start/end
            # Note: events table constraint requires EITHER date OR (date_start AND date_end), not both
            start_datetime = f"{exam.date} {exam.start_time}"
            end_datetime = f"{exam.date} {exam.end_time}"

            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO academic_calendar_events
                    (id, name, date_start, date_end, description, event_type, date_added, last_modified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event_id,
                    f"Exam: {exam.module_code} - {exam.module_name}",
                    start_datetime,
                    end_datetime,
                    f"Room: {exam.room}\nInstructor: {exam.instructor_name}\nStudents Enrolled: {exam.students_enrolled}\nTime: {exam.start_time} - {exam.end_time}",
                    'Exam',
                    now,
                    now
                ))
                conn.commit()
            logger.info(f"Added exam {exam.module_code} to academic calendar (events table)")
            return True
        except Exception as e:
            logger.error(f"Failed to add exam to calendar: {e}")
            return False
    
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
                            enrolled_student_ids
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        enrolled_ids_json
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
                        exam.id
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
                with get_connection() as conn:
                    cursor = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM exams")
                    return cursor.fetchone()[0]
            except:
                pass

        # Fallback to in-memory list
        if not self.exams:
            return 1
        return max(e.id for e in self.exams) + 1

    def get_next_room_id(self) -> int:
        if HAS_DB:
            # Get next ID from database
            try:
                with get_connection() as conn:
                    cursor = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM rooms")
                    return cursor.fetchone()[0]
            except:
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
    
    def check_conflict(self, date: str, start_time: str, end_time: str,
                       room: str, exclude_id: Optional[int] = None) -> bool:
        """Check if there's a scheduling conflict."""
        for exam in self.exams:
            if exclude_id and exam.id == exclude_id:
                continue
            if exam.date == date and exam.room == room:
                # Check time overlap
                if not (end_time <= exam.start_time or start_time >= exam.end_time):
                    return True
        return False

    def get_conflicting_exams(self, date: str, start_time: str, end_time: str,
                              room: str, exclude_id: Optional[int] = None) -> List[Exam]:
        """Get list of conflicting exams for a given date/time/room."""
        conflicts = []
        for exam in self.exams:
            if exclude_id and exam.id == exclude_id:
                continue
            if exam.date == date and exam.room == room:
                # Check time overlap
                if not (end_time <= exam.start_time or start_time >= exam.end_time):
                    conflicts.append(exam)
        return conflicts

    def check_instructor_conflict(self, date: str, start_time: str, end_time: str,
                                  instructor_id: Optional[int], exclude_id: Optional[int] = None) -> List[Exam]:
        """Check if instructor has conflicting exams at the same time."""
        if not instructor_id:
            return []

        conflicts = []
        for exam in self.exams:
            if exclude_id and exam.id == exclude_id:
                continue
            if exam.date == date and exam.instructor_id == instructor_id:
                # Check time overlap
                if not (end_time <= exam.start_time or start_time >= exam.end_time):
                    conflicts.append(exam)
        return conflicts

    def get_available_rooms(self, date: str, start_time: str, end_time: str,
                           min_capacity: int = 0, exclude_id: Optional[int] = None) -> List[Room]:
        """Get list of rooms available for a specific date/time with optional capacity filter."""
        available = []
        for room in self.rooms:
            # Check capacity requirement
            if min_capacity > 0 and room.capacity < min_capacity:
                continue

            # Check if room is free during this time
            has_conflict = False
            for exam in self.exams:
                if exclude_id and exam.id == exclude_id:
                    continue
                if exam.date == date and exam.room == room.name:
                    # Check time overlap
                    if not (end_time <= exam.start_time or start_time >= exam.end_time):
                        has_conflict = True
                        break

            if not has_conflict:
                available.append(room)

        return available

    def get_exams_by_date_range(self, start_date: str, end_date: str) -> List[Exam]:
        """Get exams within a date range."""
        filtered = []
        for exam in self.exams:
            if start_date <= exam.date <= end_date:
                filtered.append(exam)
        return sorted(filtered, key=lambda x: (x.date, x.start_time))

    def get_exams_by_instructor(self, instructor_id: int) -> List[Exam]:
        """Get all exams for a specific instructor."""
        return [e for e in self.exams if e.instructor_id == instructor_id]

    def get_exams_by_room(self, room_name: str) -> List[Exam]:
        """Get all exams in a specific room."""
        return [e for e in self.exams if e.room == room_name]
    
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


class ExamSchedulerApp:
    """Main application class for the Exam Scheduling System."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(_("exam_scheduler.title"))
        self.root.geometry("1200x700")
        self.root.minsize(1000, 600)
        
        # Initialize data manager
        self.data_manager = DataManager()
        
        # Configure style
        self.setup_styles()
        
        # Create main layout
        self.create_menu()
        self.create_main_layout()
        
        # Load initial data
        self.refresh_exam_list()
        self.refresh_room_list()
    
    def setup_styles(self):
        """Configure ttk styles for the application."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Title.TLabel', font=('Helvetica', 16, 'bold'))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        style.configure('TNotebook.Tab', padding=[20, 10])
        style.configure('Accent.TButton', font=('Helvetica', 10, 'bold'))
        
        # Treeview styling
        style.configure('Treeview', rowheight=28, font=('Helvetica', 10))
        style.configure('Treeview.Heading', font=('Helvetica', 10, 'bold'))
    
    def create_menu(self):
        """Create the application menu bar."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("exam_scheduler.menu.file"), menu=file_menu)
        file_menu.add_command(label=_("exam_scheduler.menu.export_csv"), command=self.export_schedule)
        file_menu.add_separator()
        file_menu.add_command(label=_("exam_scheduler.menu.exit"), command=self.root.quit)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_("exam_scheduler.menu.help"), menu=help_menu)
        help_menu.add_command(label=_("exam_scheduler.menu.about"), command=self.show_about)
    
    def create_main_layout(self):
        """Create the main application layout with tabs."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text=_("exam_scheduler.title"),
                               style='Title.TLabel')
        title_label.pack(pady=(0, 10))

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.create_schedule_tab()
        self.create_exams_tab()
        self.create_rooms_tab()
        self.create_calendar_tab()
    
    def create_schedule_tab(self):
        """Create the main schedule overview tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.schedule_overview"))

        # Top controls
        controls_frame = ttk.Frame(tab)
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        # Filter by date
        ttk.Label(controls_frame, text=_("exam_scheduler.labels.filter_by_date")).pack(side=tk.LEFT, padx=(0, 5))
        self.filter_date_var = tk.StringVar()
        date_entry = ttk.Entry(controls_frame, textvariable=self.filter_date_var, width=12)
        date_entry.pack(side=tk.LEFT, padx=(0, 10))
        date_entry.insert(0, _("exam_scheduler.placeholders.date_format"))
        date_entry.bind('<FocusIn>', lambda e: date_entry.delete(0, tk.END) if date_entry.get() == _("exam_scheduler.placeholders.date_format") else None)

        ttk.Button(controls_frame, text=_("exam_scheduler.buttons.filter"), command=self.filter_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text=_("exam_scheduler.buttons.clear_filter"), command=self.clear_filter).pack(side=tk.LEFT, padx=5)

        # Advanced filters
        ttk.Button(controls_frame, text="Advanced Filters", command=self.show_advanced_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Export Selected", command=self.export_selected_exams).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Find Conflicts", command=self.find_all_conflicts).pack(side=tk.LEFT, padx=5)

        ttk.Button(controls_frame, text=_("exam_scheduler.buttons.refresh"), command=self.refresh_exam_list).pack(side=tk.RIGHT)
        
        # Schedule treeview
        tree_frame = ttk.Frame(tab)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('id', 'module', 'name', 'date', 'time', 'room', 'instructor', 'students')
        self.schedule_tree = ttk.Treeview(tree_frame, columns=columns, show='headings')

        # Configure columns
        self.schedule_tree.heading('id', text=_("exam_scheduler.columns.id"))
        self.schedule_tree.heading('module', text=_("exam_scheduler.columns.module_code"))
        self.schedule_tree.heading('name', text=_("exam_scheduler.columns.module_name"))
        self.schedule_tree.heading('date', text=_("exam_scheduler.columns.date"))
        self.schedule_tree.heading('time', text=_("exam_scheduler.columns.time"))
        self.schedule_tree.heading('room', text=_("exam_scheduler.columns.room"))
        self.schedule_tree.heading('instructor', text=_("exam_scheduler.columns.instructor"))
        self.schedule_tree.heading('students', text=_("exam_scheduler.columns.students"))
        
        self.schedule_tree.column('id', width=50)
        self.schedule_tree.column('module', width=100)
        self.schedule_tree.column('name', width=200)
        self.schedule_tree.column('date', width=100)
        self.schedule_tree.column('time', width=120)
        self.schedule_tree.column('room', width=100)
        self.schedule_tree.column('instructor', width=150)
        self.schedule_tree.column('students', width=80)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.schedule_tree.yview)
        self.schedule_tree.configure(yscrollcommand=scrollbar.set)
        
        self.schedule_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Statistics frame
        stats_frame = ttk.LabelFrame(tab, text=_("exam_scheduler.frames.statistics"), padding="10")
        stats_frame.pack(fill=tk.X, pady=(10, 0))

        self.stats_label = ttk.Label(stats_frame, text="")
        self.stats_label.pack()
    
    def create_exams_tab(self):
        """Create the exam management tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.manage_exams"))

        # Split into left (form) and right (list)
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left side - Scrollable Form Container
        form_container = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.exam_details"), padding="5")
        paned.add(form_container, weight=1)

        # Create canvas and scrollbar for the form
        form_canvas = tk.Canvas(form_container, highlightthickness=0)
        form_scrollbar = ttk.Scrollbar(form_container, orient=tk.VERTICAL, command=form_canvas.yview)

        # Create frame inside canvas for form content
        form_frame = ttk.Frame(form_canvas, padding="10")

        # Configure canvas scrolling
        form_canvas.configure(yscrollcommand=form_scrollbar.set)

        # Pack scrollbar and canvas
        form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create window in canvas
        canvas_frame = form_canvas.create_window((0, 0), window=form_frame, anchor=tk.NW)

        # Bind mousewheel for scrolling
        def on_mousewheel(event):
            form_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        def on_configure(event):
            # Update scrollregion when content changes
            form_canvas.configure(scrollregion=form_canvas.bbox("all"))
            # Update canvas window width to match canvas width
            canvas_width = event.width
            form_canvas.itemconfig(canvas_frame, width=canvas_width)

        form_canvas.bind('<Configure>', on_configure)
        form_frame.bind('<Configure>', lambda e: form_canvas.configure(scrollregion=form_canvas.bbox("all")))

        # Bind mousewheel to canvas and all children
        def bind_mousewheel(widget):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", lambda e: form_canvas.yview_scroll(-1, "units"))
            widget.bind("<Button-5>", lambda e: form_canvas.yview_scroll(1, "units"))
            for child in widget.winfo_children():
                bind_mousewheel(child)

        bind_mousewheel(form_frame)

        # Configure grid column weights for proper expansion
        form_frame.columnconfigure(1, weight=1)

        self.exam_vars = {}
        current_row = 0

        # Module Search Box
        ttk.Label(form_frame, text=_("exam_scheduler.labels.search_module")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        self.module_search_var = tk.StringVar()
        self.module_search_var.trace('w', lambda *args: self.search_modules())
        search_entry = ttk.Entry(form_frame, textvariable=self.module_search_var, width=30)
        search_entry.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        current_row += 1

        # Module Code Dropdown (replaces manual entry)
        ttk.Label(form_frame, text=_("exam_scheduler.labels.module_code")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        self.module_var = tk.StringVar()
        self.module_combo = ttk.Combobox(form_frame, textvariable=self.module_var, width=27, state='readonly')
        self.module_combo.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.module_combo.bind('<<ComboboxSelected>>', self.on_module_select)
        self.update_module_combo()
        current_row += 1

        # Module Name (auto-filled after selection)
        ttk.Label(form_frame, text=_("exam_scheduler.labels.module_name")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        self.exam_vars['module_name'] = tk.StringVar()
        self.module_name_entry = ttk.Entry(form_frame, textvariable=self.exam_vars['module_name'], width=30, state='readonly')
        self.module_name_entry.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        current_row += 1

        # Date with quick picker
        ttk.Label(form_frame, text=_("exam_scheduler.labels.date")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(form_frame)
        date_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.exam_vars['date'] = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.exam_vars['date'], width=15).pack(side=tk.LEFT)
        ttk.Button(date_frame, text="Today", command=lambda: self.set_date_today(), width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(date_frame, text="+7d", command=lambda: self.set_date_offset(7), width=5).pack(side=tk.LEFT, padx=2)
        current_row += 1

        # Start Time with quick buttons
        ttk.Label(form_frame, text=_("exam_scheduler.labels.start_time")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        start_time_frame = ttk.Frame(form_frame)
        start_time_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.exam_vars['start_time'] = tk.StringVar()
        ttk.Entry(start_time_frame, textvariable=self.exam_vars['start_time'], width=10).pack(side=tk.LEFT)
        ttk.Button(start_time_frame, text="09:00", command=lambda: self.exam_vars['start_time'].set("09:00"), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(start_time_frame, text="14:00", command=lambda: self.exam_vars['start_time'].set("14:00"), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(start_time_frame, text="18:00", command=lambda: self.exam_vars['start_time'].set("18:00"), width=5).pack(side=tk.LEFT, padx=1)
        current_row += 1

        # End Time with duration helpers
        ttk.Label(form_frame, text=_("exam_scheduler.labels.end_time")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        end_time_frame = ttk.Frame(form_frame)
        end_time_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.exam_vars['end_time'] = tk.StringVar()
        ttk.Entry(end_time_frame, textvariable=self.exam_vars['end_time'], width=10).pack(side=tk.LEFT)
        ttk.Button(end_time_frame, text="+1h", command=lambda: self.add_duration(60), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(end_time_frame, text="+2h", command=lambda: self.add_duration(120), width=5).pack(side=tk.LEFT, padx=1)
        ttk.Button(end_time_frame, text="+3h", command=lambda: self.add_duration(180), width=5).pack(side=tk.LEFT, padx=1)
        current_row += 1

        # Instructor Dropdown
        ttk.Label(form_frame, text=_("exam_scheduler.labels.instructor")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        instructor_frame = ttk.Frame(form_frame)
        instructor_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.instructor_var = tk.StringVar()
        self.instructor_combo = ttk.Combobox(instructor_frame, textvariable=self.instructor_var, width=27, state='readonly')
        self.instructor_combo.pack(side=tk.LEFT)
        self.update_instructor_combo()
        ttk.Button(instructor_frame, text="Check", command=self.check_instructor_availability, width=8).pack(side=tk.LEFT, padx=5)
        current_row += 1

        # Room dropdown with helper buttons
        ttk.Label(form_frame, text=_("exam_scheduler.labels.room")).grid(row=current_row, column=0, sticky=tk.W, pady=5)
        room_frame = ttk.Frame(form_frame)
        room_frame.grid(row=current_row, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        self.room_var = tk.StringVar()
        self.room_combo = ttk.Combobox(room_frame, textvariable=self.room_var, width=27, state='readonly')
        self.room_combo.pack(side=tk.LEFT)
        self.update_room_combo()
        current_row += 1

        # Room helper buttons
        room_btns_frame = ttk.Frame(form_frame)
        room_btns_frame.grid(row=current_row, column=1, sticky=tk.W, pady=2, padx=(10, 0))
        ttk.Button(room_btns_frame, text="Suggest Rooms", command=self.suggest_available_rooms, width=13).pack(side=tk.LEFT, padx=1)
        ttk.Button(room_btns_frame, text="Check Available", command=self.check_room_availability, width=13).pack(side=tk.LEFT, padx=1)
        ttk.Button(room_btns_frame, text="Check Capacity", command=self.validate_room_capacity, width=13).pack(side=tk.LEFT, padx=1)
        current_row += 1

        # Students Enrolled Section
        ttk.Label(form_frame, text=_("exam_scheduler.labels.students_enrolled")).grid(row=current_row, column=0, sticky=tk.NW, pady=5)
        students_frame = ttk.Frame(form_frame)
        students_frame.grid(row=current_row, column=1, sticky=tk.NSEW, pady=5, padx=(10, 0))

        # Students count and status
        self.students_count_var = tk.StringVar(value=_("exam_scheduler.labels.students_count", count=0))
        ttk.Label(students_frame, textvariable=self.students_count_var, font=('Helvetica', 9, 'bold')).pack(anchor=tk.W)

        # Students listbox with scrollbar
        students_list_frame = ttk.Frame(students_frame)
        students_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.students_listbox = tk.Listbox(students_list_frame, height=5, width=35, selectmode=tk.EXTENDED)
        students_scrollbar = ttk.Scrollbar(students_list_frame, orient=tk.VERTICAL, command=self.students_listbox.yview)
        self.students_listbox.configure(yscrollcommand=students_scrollbar.set)
        self.students_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        students_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store enrolled student IDs
        self.enrolled_student_ids = []
        current_row += 1

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=current_row, column=0, columnspan=2, pady=15)

        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.add_exam"), command=self.add_exam, style='Accent.TButton').pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.update"), command=self.update_exam).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.duplicate"), command=self.duplicate_exam).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.delete"), command=self.delete_exam).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.clear"), command=self.clear_exam_form).pack(side=tk.LEFT, padx=3)

        # Note about automatic actions
        note_label = ttk.Label(form_frame, text=_("exam_scheduler.labels.auto_notifications_note"),
                              font=('Helvetica', 8, 'italic'), foreground='gray')
        note_label.grid(row=current_row + 1, column=0, columnspan=2, pady=(10, 0))

        self.selected_exam_id = None
        self.selected_instructor_id = None

        # Right side - List
        list_frame = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.exam_list"), padding="10")
        paned.add(list_frame, weight=2)

        # Search
        search_frame = ttk.Frame(list_frame)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(search_frame, text=_("exam_scheduler.labels.search")).pack(side=tk.LEFT)
        self.exam_search_var = tk.StringVar()
        self.exam_search_var.trace('w', lambda *args: self.search_exams())
        ttk.Entry(search_frame, textvariable=self.exam_search_var, width=30).pack(side=tk.LEFT, padx=5)

        # Exam list
        columns = ('id', 'module', 'name', 'date', 'room')
        self.exam_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.exam_tree.heading('id', text=_("exam_scheduler.columns.id"))
        self.exam_tree.heading('module', text=_("exam_scheduler.columns.module"))
        self.exam_tree.heading('name', text=_("exam_scheduler.columns.name"))
        self.exam_tree.heading('date', text=_("exam_scheduler.columns.date"))
        self.exam_tree.heading('room', text=_("exam_scheduler.columns.room"))

        self.exam_tree.column('id', width=40)
        self.exam_tree.column('module', width=80)
        self.exam_tree.column('name', width=150)
        self.exam_tree.column('date', width=90)
        self.exam_tree.column('room', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.exam_tree.yview)
        self.exam_tree.configure(yscrollcommand=scrollbar.set)

        self.exam_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection
        self.exam_tree.bind('<<TreeviewSelect>>', self.on_exam_select)
    
    def create_rooms_tab(self):
        """Create the room management tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.manage_rooms"))

        # Split layout
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left - Form
        form_frame = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.room_details"), padding="15")
        paned.add(form_frame, weight=1)

        # Room form fields
        fields = [
            (_("exam_scheduler.labels.room_name"), "room_name"),
            (_("exam_scheduler.labels.building"), "building"),
            (_("exam_scheduler.labels.capacity"), "capacity"),
        ]

        self.room_form_vars = {}
        for i, (label, var_name) in enumerate(fields):
            ttk.Label(form_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)
            var = tk.StringVar()
            self.room_form_vars[var_name] = var
            ttk.Entry(form_frame, textvariable=var, width=25).grid(row=i, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

        # Checkboxes
        self.has_computers_var = tk.BooleanVar()
        self.has_projector_var = tk.BooleanVar()

        ttk.Checkbutton(form_frame, text=_("exam_scheduler.labels.has_computers"), variable=self.has_computers_var).grid(
            row=len(fields), column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Checkbutton(form_frame, text=_("exam_scheduler.labels.has_projector"), variable=self.has_projector_var).grid(
            row=len(fields)+1, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Buttons
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=len(fields)+2, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.add_room"), command=self.add_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.update"), command=self.update_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.delete"), command=self.delete_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_("exam_scheduler.buttons.clear"), command=self.clear_room_form).pack(side=tk.LEFT, padx=5)

        self.selected_room_id = None

        # Right - List
        list_frame = ttk.LabelFrame(paned, text=_("exam_scheduler.frames.room_list"), padding="10")
        paned.add(list_frame, weight=2)

        columns = ('id', 'name', 'building', 'capacity', 'facilities')
        self.room_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        self.room_tree.heading('id', text=_("exam_scheduler.columns.id"))
        self.room_tree.heading('name', text=_("exam_scheduler.columns.room"))
        self.room_tree.heading('building', text=_("exam_scheduler.columns.building"))
        self.room_tree.heading('capacity', text=_("exam_scheduler.columns.capacity"))
        self.room_tree.heading('facilities', text=_("exam_scheduler.columns.facilities"))
        
        self.room_tree.column('id', width=40)
        self.room_tree.column('name', width=100)
        self.room_tree.column('building', width=120)
        self.room_tree.column('capacity', width=70)
        self.room_tree.column('facilities', width=150)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.room_tree.yview)
        self.room_tree.configure(yscrollcommand=scrollbar.set)
        
        self.room_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.room_tree.bind('<<TreeviewSelect>>', self.on_room_select)
    
    def create_calendar_tab(self):
        """Create a calendar view tab."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("exam_scheduler.tabs.calendar_view"))

        # Week navigation
        nav_frame = ttk.Frame(tab)
        nav_frame.pack(fill=tk.X, pady=(0, 10))

        self.current_week_start = datetime.now() - timedelta(days=datetime.now().weekday())

        ttk.Button(nav_frame, text=_("exam_scheduler.buttons.previous_week"), command=self.prev_week).pack(side=tk.LEFT)
        self.week_label = ttk.Label(nav_frame, text="", font=('Helvetica', 12, 'bold'))
        self.week_label.pack(side=tk.LEFT, expand=True)
        ttk.Button(nav_frame, text=_("exam_scheduler.buttons.next_week"), command=self.next_week).pack(side=tk.RIGHT)
        
        # Calendar grid
        self.calendar_frame = ttk.Frame(tab)
        self.calendar_frame.pack(fill=tk.BOTH, expand=True)
        
        self.update_calendar()
    
    def update_calendar(self):
        """Update the calendar view."""
        # Clear existing
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()

        # Update label
        week_end = self.current_week_start + timedelta(days=6)
        self.week_label.config(text=f"{self.current_week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')}")

        # Create day columns
        days = [
            _("exam_scheduler.days.monday"),
            _("exam_scheduler.days.tuesday"),
            _("exam_scheduler.days.wednesday"),
            _("exam_scheduler.days.thursday"),
            _("exam_scheduler.days.friday"),
            _("exam_scheduler.days.saturday"),
            _("exam_scheduler.days.sunday")
        ]

        for col, day in enumerate(days):
            current_date = self.current_week_start + timedelta(days=col)
            date_str = current_date.strftime('%Y-%m-%d')

            # Day header
            day_frame = ttk.LabelFrame(self.calendar_frame, text=f"{day}\n{current_date.strftime('%m/%d')}")
            day_frame.grid(row=0, column=col, sticky='nsew', padx=2, pady=2)

            # Get exams for this day
            day_exams = [e for e in self.data_manager.exams if e.date == date_str]
            day_exams.sort(key=lambda x: x.start_time)

            if day_exams:
                for exam in day_exams:
                    exam_frame = ttk.Frame(day_frame, relief='raised', borderwidth=1)
                    exam_frame.pack(fill=tk.X, padx=2, pady=2)

                    ttk.Label(exam_frame, text=exam.module_code, font=('Helvetica', 9, 'bold')).pack(anchor='w')
                    ttk.Label(exam_frame, text=f"{exam.start_time}-{exam.end_time}", font=('Helvetica', 8)).pack(anchor='w')
                    ttk.Label(exam_frame, text=exam.room, font=('Helvetica', 8)).pack(anchor='w')
            else:
                ttk.Label(day_frame, text=_("exam_scheduler.labels.no_exams"), foreground='gray').pack(pady=20)

            self.calendar_frame.columnconfigure(col, weight=1)

        self.calendar_frame.rowconfigure(0, weight=1)
    
    def prev_week(self):
        self.current_week_start -= timedelta(days=7)
        self.update_calendar()
    
    def next_week(self):
        self.current_week_start += timedelta(days=7)
        self.update_calendar()
    
    # Exam management methods
    def refresh_exam_list(self):
        """Refresh the exam list in all views."""
        # Clear trees
        for tree in [self.schedule_tree, self.exam_tree]:
            for item in tree.get_children():
                tree.delete(item)

        # Sort exams by date and time
        sorted_exams = sorted(self.data_manager.exams, key=lambda x: (x.date, x.start_time))

        # Populate schedule tree
        for exam in sorted_exams:
            time_str = f"{exam.start_time} - {exam.end_time}"
            self.schedule_tree.insert('', tk.END, values=(
                exam.id, exam.module_code, exam.module_name, exam.date,
                time_str, exam.room, exam.instructor_name, exam.students_enrolled
            ))

        # Populate exam tree
        for exam in sorted_exams:
            self.exam_tree.insert('', tk.END, values=(
                exam.id, exam.module_code, exam.module_name, exam.date, exam.room
            ))

        # Update statistics
        self.update_statistics()

        # Update calendar
        self.update_calendar()
    
    def update_statistics(self):
        """Update the statistics display with enhanced information."""
        total_exams = len(self.data_manager.exams)
        total_students = sum(e.students_enrolled for e in self.data_manager.exams)

        # Count unique dates
        unique_dates = len(set(e.date for e in self.data_manager.exams))

        # Count rooms in use
        rooms_used = len(set(e.room for e in self.data_manager.exams))

        # Count unique instructors
        instructors_used = len(set(e.instructor_id for e in self.data_manager.exams if e.instructor_id))

        # Calculate average students per exam
        avg_students = total_students / total_exams if total_exams > 0 else 0

        # Find busiest day
        busiest_day = ""
        if self.data_manager.exams:
            date_counts = {}
            for exam in self.data_manager.exams:
                date_counts[exam.date] = date_counts.get(exam.date, 0) + 1
            busiest_date = max(date_counts, key=date_counts.get)
            busiest_count = date_counts[busiest_date]
            busiest_day = f"  |  Busiest Day: {busiest_date} ({busiest_count} exams)"

        stats_text = (f"{_('exam_scheduler.stats.total_exams')}: {total_exams}  |  "
                     f"{_('exam_scheduler.stats.total_students')}: {total_students} "
                     f"(Avg: {avg_students:.1f})  |  "
                     f"{_('exam_scheduler.stats.exam_days')}: {unique_dates}  |  "
                     f"Rooms: {rooms_used}  |  "
                     f"Instructors: {instructors_used}"
                     f"{busiest_day}")
        self.stats_label.config(text=stats_text)
    
    def filter_schedule(self):
        """Filter schedule by date."""
        filter_date = self.filter_date_var.get().strip()
        if not filter_date or filter_date == "YYYY-MM-DD":
            return

        for item in self.schedule_tree.get_children():
            self.schedule_tree.delete(item)

        filtered = [e for e in self.data_manager.exams if e.date == filter_date]
        filtered.sort(key=lambda x: x.start_time)

        for exam in filtered:
            time_str = f"{exam.start_time} - {exam.end_time}"
            self.schedule_tree.insert('', tk.END, values=(
                exam.id, exam.module_code, exam.module_name, exam.date,
                time_str, exam.room, exam.instructor_name, exam.students_enrolled
            ))

    def clear_filter(self):
        """Clear the date filter."""
        self.filter_date_var.set("")
        self.refresh_exam_list()

    def search_exams(self):
        """Search exams by module code or name."""
        search_term = self.exam_search_var.get().lower()

        for item in self.exam_tree.get_children():
            self.exam_tree.delete(item)

        for exam in self.data_manager.exams:
            if (search_term in exam.module_code.lower() or
                search_term in exam.module_name.lower() or
                search_term in exam.instructor_name.lower()):
                self.exam_tree.insert('', tk.END, values=(
                    exam.id, exam.module_code, exam.module_name, exam.date, exam.room
                ))
    
    def update_room_combo(self):
        """Update the room dropdown with available rooms."""
        room_names = [f"{r.name} ({r.building}) - Cap: {r.capacity}" for r in self.data_manager.rooms]
        self.room_combo['values'] = room_names

    def update_instructor_combo(self):
        """Update the instructor dropdown with instructors from database."""
        instructors = self.data_manager.get_instructors()
        if instructors:
            instructor_names = [f"{i['display_name']} ({i['department'] or 'N/A'})" for i in instructors]
            self.instructor_combo['values'] = instructor_names
        else:
            # Fallback: allow manual entry if no instructors in DB
            self.instructor_combo['state'] = 'normal'
            self.instructor_combo['values'] = []

    def update_module_combo(self):
        """Update the module dropdown with modules from database."""
        modules = self.data_manager.get_all_modules()
        self.all_modules = modules  # Store for search functionality
        if modules:
            # Format: "MODULE_CODE - Module Name"
            module_options = [f"{m['module_code']} - {m['module_name']}" for m in modules]
            self.module_combo['values'] = module_options
        else:
            self.module_combo['values'] = []

    def search_modules(self, event=None):
        """Search and filter modules in real-time."""
        search_term = self.module_search_var.get().lower()
        if not search_term or not hasattr(self, 'all_modules'):
            # Show all modules if no search term
            if hasattr(self, 'all_modules'):
                module_options = [f"{m['module_code']} - {m['module_name']}" for m in self.all_modules]
                self.module_combo['values'] = module_options
            return

        # Filter modules based on search term
        filtered = [m for m in self.all_modules
                   if search_term in m['module_code'].lower() or
                      search_term in m['module_name'].lower()]

        module_options = [f"{m['module_code']} - {m['module_name']}" for m in filtered]
        self.module_combo['values'] = module_options

    def on_module_select(self, event=None):
        """Handle module selection from dropdown."""
        module_selection = self.module_var.get()
        if not module_selection:
            return

        # Extract module code (format: "MODULE_CODE - Module Name")
        module_code = module_selection.split(' - ')[0]

        # Look up module details
        module = self.data_manager.lookup_module(module_code)
        if module:
            # Auto-fill module name
            self.exam_vars['module_name'].set(module['module_name'] or '')

            # Get enrolled students
            students = self.data_manager.get_enrolled_students(module_code)
            self.populate_students_list(students)

    def populate_students_list(self, students: List[Dict]):
        """Populate the students listbox with enrolled students."""
        self.students_listbox.delete(0, tk.END)
        self.enrolled_student_ids = []

        for student in students:
            self.students_listbox.insert(tk.END, student['display_name'])
            self.enrolled_student_ids.append(student['student_id'])

        self.students_count_var.set(_("exam_scheduler.labels.students_count", count=len(students)))

    def get_selected_instructor_id(self) -> Optional[int]:
        """Get the ID of the selected instructor."""
        instructor_selection = self.instructor_var.get()
        if not instructor_selection:
            return None

        instructors = self.data_manager.get_instructors()
        for inst in instructors:
            if instructor_selection.startswith(inst['display_name']):
                return inst['id']
        return None

    def get_instructor_display_name(self) -> str:
        """Get display name from instructor selection."""
        instructor_selection = self.instructor_var.get()
        if not instructor_selection:
            return ""

        # Extract name before the parenthesis
        if ' (' in instructor_selection:
            return instructor_selection.split(' (')[0]
        return instructor_selection

    def get_selected_module_code(self) -> str:
        """Extract module code from the module dropdown selection."""
        module_selection = self.module_var.get()
        if not module_selection:
            return ""
        # Format: "MODULE_CODE - Module Name"
        return module_selection.split(' - ')[0]

    def validate_exam_form(self) -> bool:
        """Validate the exam form inputs."""
        # Check module selection
        if not self.module_var.get():
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.select_module"))
            return False

        # Check other required fields
        required = ['module_name', 'date', 'start_time', 'end_time']
        for field_name in required:
            if not self.exam_vars[field_name].get().strip():
                messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.fill_required_fields"))
                return False

        if not self.instructor_var.get():
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.select_instructor"))
            return False

        if not self.room_var.get():
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.select_room"))
            return False

        # Validate date format
        try:
            datetime.strptime(self.exam_vars['date'].get(), '%Y-%m-%d')
        except ValueError:
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.invalid_date_format"))
            return False

        # Validate time format
        for time_field in ['start_time', 'end_time']:
            try:
                datetime.strptime(self.exam_vars[time_field].get(), '%H:%M')
            except ValueError:
                messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.invalid_time_format"))
                return False

        return True
    
    def add_exam(self):
        """Add a new exam."""
        if not self.validate_exam_form():
            return

        # Extract module code from dropdown
        module_code = self.get_selected_module_code()

        # Extract room name
        room_selection = self.room_var.get()
        room_name = room_selection.split(' (')[0] if room_selection else ""

        # Check for conflicts
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()

        if self.data_manager.check_conflict(date, start, end, room_name):
            messagebox.showerror(_("exam_scheduler.dialogs.conflict"), _("exam_scheduler.messages.scheduling_conflict"))
            return

        # Get instructor details
        instructor_id = self.get_selected_instructor_id()
        instructor_name = self.get_instructor_display_name()

        exam = Exam(
            id=self.data_manager.get_next_exam_id(),
            module_code=module_code,
            module_name=self.exam_vars['module_name'].get().strip(),
            date=date,
            start_time=start,
            end_time=end,
            room=room_name,
            instructor_id=instructor_id,
            instructor_name=instructor_name,
            students_enrolled=len(self.enrolled_student_ids),
            enrolled_student_ids=self.enrolled_student_ids.copy()
        )

        self.data_manager.add_exam(exam)

        # Automatically add to calendar
        calendar_added = False
        if HAS_CALENDAR:
            calendar_added = self.data_manager.add_exam_to_calendar(exam)

        # Automatically send email notifications
        email_success, email_failed = 0, 0
        if HAS_EMAIL:
            email_success, email_failed = self.data_manager.send_exam_notifications(exam)

        self.refresh_exam_list()
        self.clear_exam_form()

        # Build success message with details
        msg = _("exam_scheduler.messages.exam_added")
        if calendar_added:
            msg += "\n\n✓ " + _("exam_scheduler.messages.added_to_calendar")
        if HAS_EMAIL:
            msg += f"\n✓ {_('exam_scheduler.messages.notifications_sent')}: {email_success}"
            if email_failed > 0:
                msg += f" ({_('exam_scheduler.messages.failed')}: {email_failed})"

        messagebox.showinfo(_("exam_scheduler.dialogs.success"), msg)
    
    def update_exam(self):
        """Update the selected exam."""
        if not self.selected_exam_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_exam_to_update"))
            return

        if not self.validate_exam_form():
            return

        # Extract module code from dropdown
        module_code = self.get_selected_module_code()

        room_selection = self.room_var.get()
        room_name = room_selection.split(' (')[0] if room_selection else ""

        # Check for conflicts (excluding current exam)
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()

        if self.data_manager.check_conflict(date, start, end, room_name, self.selected_exam_id):
            messagebox.showerror(_("exam_scheduler.dialogs.conflict"), _("exam_scheduler.messages.scheduling_conflict"))
            return

        # Get instructor details
        instructor_id = self.get_selected_instructor_id()
        instructor_name = self.get_instructor_display_name()

        exam = Exam(
            id=self.selected_exam_id,
            module_code=module_code,
            module_name=self.exam_vars['module_name'].get().strip(),
            date=date,
            start_time=start,
            end_time=end,
            room=room_name,
            instructor_id=instructor_id,
            instructor_name=instructor_name,
            students_enrolled=len(self.enrolled_student_ids),
            enrolled_student_ids=self.enrolled_student_ids.copy()
        )

        self.data_manager.update_exam(exam)

        # Send email notifications about the update
        email_success, email_failed = 0, 0
        if HAS_EMAIL:
            email_success, email_failed = self.data_manager.send_exam_update_notifications(exam)

        self.refresh_exam_list()
        self.clear_exam_form()

        # Build success message with details
        msg = _("exam_scheduler.messages.exam_updated")
        if HAS_EMAIL:
            msg += f"\n\n✓ {_('exam_scheduler.messages.update_notifications_sent')}: {email_success}"
            if email_failed > 0:
                msg += f" ({_('exam_scheduler.messages.failed')}: {email_failed})"

        messagebox.showinfo(_("exam_scheduler.dialogs.success"), msg)
    
    def delete_exam(self):
        """Delete the selected exam."""
        if not self.selected_exam_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_exam_to_delete"))
            return

        if messagebox.askyesno(_("exam_scheduler.dialogs.confirm_delete"), _("exam_scheduler.messages.confirm_delete_exam")):
            self.data_manager.delete_exam(self.selected_exam_id)
            self.refresh_exam_list()
            self.clear_exam_form()
            messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.exam_deleted"))
    
    def clear_exam_form(self):
        """Clear the exam form."""
        for var in self.exam_vars.values():
            var.set("")
        self.module_var.set("")
        self.room_var.set("")
        self.instructor_var.set("")
        self.students_listbox.delete(0, tk.END)
        self.enrolled_student_ids = []
        self.students_count_var.set(_("exam_scheduler.labels.students_count", count=0))
        self.selected_exam_id = None
        self.selected_instructor_id = None
    
    def on_exam_select(self, event):
        """Handle exam selection in the tree."""
        selection = self.exam_tree.selection()
        if not selection:
            return

        item = self.exam_tree.item(selection[0])
        exam_id = item['values'][0]

        # Find the exam
        exam = next((e for e in self.data_manager.exams if e.id == exam_id), None)
        if not exam:
            return

        self.selected_exam_id = exam_id

        # Set module dropdown
        # Find matching module in dropdown options
        module = self.data_manager.lookup_module(exam.module_code)
        if module:
            module_option = f"{exam.module_code} - {module['module_name']}"
            self.module_var.set(module_option)
        else:
            # Fallback: try to find by code only
            for option in self.module_combo['values']:
                if option.startswith(exam.module_code + ' -'):
                    self.module_var.set(option)
                    break

        # Populate form with other fields
        self.exam_vars['module_name'].set(exam.module_name)
        self.exam_vars['date'].set(exam.date)
        self.exam_vars['start_time'].set(exam.start_time)
        self.exam_vars['end_time'].set(exam.end_time)

        # Set instructor combo
        if exam.instructor_id:
            instructor = self.data_manager.get_instructor_by_id(exam.instructor_id)
            if instructor:
                self.instructor_var.set(f"{instructor['display_name']} ({instructor['department'] or 'N/A'})")
                self.selected_instructor_id = exam.instructor_id
        else:
            # Fallback for legacy data with just instructor name
            for inst in self.data_manager.get_instructors():
                if inst['display_name'] == exam.instructor_name:
                    self.instructor_var.set(f"{inst['display_name']} ({inst['department'] or 'N/A'})")
                    break

        # Set room combo
        for room in self.data_manager.rooms:
            if room.name == exam.room:
                self.room_var.set(f"{room.name} ({room.building}) - Cap: {room.capacity}")
                break

        # Populate enrolled students
        self.enrolled_student_ids = exam.enrolled_student_ids.copy() if exam.enrolled_student_ids else []
        self.students_listbox.delete(0, tk.END)

        if self.enrolled_student_ids:
            # Get student details from database
            students = self.data_manager.get_enrolled_students(exam.module_code)
            for student in students:
                if student['student_id'] in self.enrolled_student_ids:
                    self.students_listbox.insert(tk.END, student['display_name'])
            self.students_count_var.set(_("exam_scheduler.labels.students_count", count=len(self.enrolled_student_ids)))
        else:
            self.students_count_var.set(_("exam_scheduler.labels.students_count", count=exam.students_enrolled))
    
    # Room management methods
    def refresh_room_list(self):
        """Refresh the room list."""
        for item in self.room_tree.get_children():
            self.room_tree.delete(item)

        for room in self.data_manager.rooms:
            facilities = []
            if room.has_computers:
                facilities.append(_("exam_scheduler.facilities.computers"))
            if room.has_projector:
                facilities.append(_("exam_scheduler.facilities.projector"))
            facilities_str = ", ".join(facilities) if facilities else _("exam_scheduler.facilities.none")

            self.room_tree.insert('', tk.END, values=(
                room.id, room.name, room.building, room.capacity, facilities_str
            ))

        self.update_room_combo()
    
    def add_room(self):
        """Add a new room."""
        name = self.room_form_vars['room_name'].get().strip()
        building = self.room_form_vars['building'].get().strip()
        capacity_str = self.room_form_vars['capacity'].get().strip()

        if not all([name, building, capacity_str]):
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.fill_all_fields"))
            return

        try:
            capacity = int(capacity_str)
        except ValueError:
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.capacity_must_be_number"))
            return

        room = Room(
            id=self.data_manager.get_next_room_id(),
            name=name,
            building=building,
            capacity=capacity,
            has_computers=self.has_computers_var.get(),
            has_projector=self.has_projector_var.get()
        )

        self.data_manager.add_room(room)
        self.refresh_room_list()
        self.clear_room_form()
        messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.room_added"))
    
    def update_room(self):
        """Update the selected room."""
        if not self.selected_room_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_room_to_update"))
            return

        name = self.room_form_vars['room_name'].get().strip()
        building = self.room_form_vars['building'].get().strip()
        capacity_str = self.room_form_vars['capacity'].get().strip()

        if not all([name, building, capacity_str]):
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.fill_all_fields"))
            return

        try:
            capacity = int(capacity_str)
        except ValueError:
            messagebox.showerror(_("exam_scheduler.dialogs.validation_error"), _("exam_scheduler.messages.capacity_must_be_number"))
            return

        room = Room(
            id=self.selected_room_id,
            name=name,
            building=building,
            capacity=capacity,
            has_computers=self.has_computers_var.get(),
            has_projector=self.has_projector_var.get()
        )

        self.data_manager.update_room(room)
        self.refresh_room_list()
        self.clear_room_form()
        messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.room_updated"))
    
    def delete_room(self):
        """Delete the selected room."""
        if not self.selected_room_id:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.select_room_to_delete"))
            return

        # Check if room is in use
        room = next((r for r in self.data_manager.rooms if r.id == self.selected_room_id), None)
        if room:
            in_use = any(e.room == room.name for e in self.data_manager.exams)
            if in_use:
                messagebox.showerror(_("exam_scheduler.dialogs.error"), _("exam_scheduler.messages.room_in_use"))
                return

        if messagebox.askyesno(_("exam_scheduler.dialogs.confirm_delete"), _("exam_scheduler.messages.confirm_delete_room")):
            self.data_manager.delete_room(self.selected_room_id)
            self.refresh_room_list()
            self.clear_room_form()
            messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.room_deleted"))
    
    def clear_room_form(self):
        """Clear the room form."""
        for var in self.room_form_vars.values():
            var.set("")
        self.has_computers_var.set(False)
        self.has_projector_var.set(False)
        self.selected_room_id = None
    
    def on_room_select(self, event):
        """Handle room selection in the tree."""
        selection = self.room_tree.selection()
        if not selection:
            return
        
        item = self.room_tree.item(selection[0])
        room_id = item['values'][0]
        
        room = next((r for r in self.data_manager.rooms if r.id == room_id), None)
        if not room:
            return
        
        self.selected_room_id = room_id
        
        self.room_form_vars['room_name'].set(room.name)
        self.room_form_vars['building'].set(room.building)
        self.room_form_vars['capacity'].set(str(room.capacity))
        self.has_computers_var.set(room.has_computers)
        self.has_projector_var.set(room.has_projector)
    
    # Utility methods
    def export_schedule(self):
        """Export the schedule to a CSV file."""
        if not self.data_manager.exams:
            messagebox.showwarning(_("exam_scheduler.dialogs.warning"), _("exam_scheduler.messages.no_exams_to_export"))
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[(_("exam_scheduler.filetypes.csv"), "*.csv"), (_("exam_scheduler.filetypes.all"), "*.*")],
            initialfilename="exam_schedule.csv"
        )

        if filepath:
            self.data_manager.export_to_csv(filepath)
            messagebox.showinfo(_("exam_scheduler.dialogs.success"), _("exam_scheduler.messages.schedule_exported", filepath=filepath))
    
    def show_about(self):
        """Show the about dialog."""
        about_text = _("exam_scheduler.about.text")

        messagebox.showinfo(_("exam_scheduler.menu.about"), about_text)

    # ==================== IMPROVEMENT FUNCTIONS ====================

    def set_date_today(self):
        """Set the date field to today's date."""
        today = datetime.now().strftime('%Y-%m-%d')
        self.exam_vars['date'].set(today)

    def set_date_offset(self, days: int):
        """Set the date field to today + offset days."""
        target_date = datetime.now() + timedelta(days=days)
        self.exam_vars['date'].set(target_date.strftime('%Y-%m-%d'))

    def add_duration(self, minutes: int):
        """Add duration to start time to calculate end time."""
        start_time_str = self.exam_vars['start_time'].get()
        if not start_time_str:
            messagebox.showwarning("Warning", "Please enter a start time first")
            return

        try:
            start_time = datetime.strptime(start_time_str, '%H:%M')
            end_time = start_time + timedelta(minutes=minutes)
            self.exam_vars['end_time'].set(end_time.strftime('%H:%M'))
        except ValueError:
            messagebox.showerror("Error", "Invalid start time format. Use HH:MM")

    def check_room_availability(self):
        """Check if the selected room is available at the selected time."""
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()
        room_selection = self.room_var.get()

        if not all([date, start, end, room_selection]):
            messagebox.showwarning("Incomplete", "Please fill in date, start time, end time, and room")
            return

        room_name = room_selection.split(' (')[0]

        # Get conflicting exams
        conflicts = self.data_manager.get_conflicting_exams(
            date, start, end, room_name,
            exclude_id=self.selected_exam_id
        )

        if conflicts:
            conflict_info = "\n".join([
                f"• {e.module_code} ({e.start_time}-{e.end_time})"
                for e in conflicts
            ])
            messagebox.showwarning(
                "Room Conflict",
                f"Room {room_name} has conflicts:\n\n{conflict_info}"
            )
        else:
            messagebox.showinfo(
                "Available",
                f"✓ Room {room_name} is available on {date} from {start} to {end}"
            )

    def validate_room_capacity(self):
        """Check if room capacity is sufficient for enrolled students."""
        room_selection = self.room_var.get()
        if not room_selection:
            messagebox.showwarning("No Room", "Please select a room first")
            return

        # Find the room
        room_name = room_selection.split(' (')[0]
        room = next((r for r in self.data_manager.rooms if r.name == room_name), None)

        if not room:
            return

        student_count = len(self.enrolled_student_ids)

        if student_count == 0:
            messagebox.showinfo("No Students", "No students enrolled yet")
            return

        if room.capacity < student_count:
            messagebox.showwarning(
                "Insufficient Capacity",
                f"⚠ Room capacity: {room.capacity}\n"
                f"Students enrolled: {student_count}\n"
                f"Shortage: {student_count - room.capacity} seats"
            )
        else:
            spare = room.capacity - student_count
            messagebox.showinfo(
                "Capacity OK",
                f"✓ Room capacity: {room.capacity}\n"
                f"Students enrolled: {student_count}\n"
                f"Spare seats: {spare}"
            )

    def duplicate_exam(self):
        """Duplicate the currently selected exam with a different date/time."""
        if not self.selected_exam_id:
            messagebox.showwarning("No Selection", "Please select an exam to duplicate")
            return

        # Find the exam
        exam = next((e for e in self.data_manager.exams if e.id == self.selected_exam_id), None)
        if not exam:
            return

        # Clear the ID so it will create a new exam
        self.selected_exam_id = None

        # Suggest next day
        try:
            current_date = datetime.strptime(exam.date, '%Y-%m-%d')
            next_date = current_date + timedelta(days=1)
            self.exam_vars['date'].set(next_date.strftime('%Y-%m-%d'))
        except:
            pass

        messagebox.showinfo(
            "Duplicate Mode",
            "Exam details loaded. Change the date/time and click 'Add Exam' to create a duplicate."
        )

    def show_advanced_filters(self):
        """Show advanced filtering dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Advanced Filters")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Date range filter
        ttk.Label(frame, text="Date Range:", font=('Helvetica', 10, 'bold')).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10)
        )

        ttk.Label(frame, text="From:").grid(row=1, column=0, sticky=tk.W, pady=5)
        start_date_var = tk.StringVar()
        ttk.Entry(frame, textvariable=start_date_var, width=15).grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="To:").grid(row=2, column=0, sticky=tk.W, pady=5)
        end_date_var = tk.StringVar()
        ttk.Entry(frame, textvariable=end_date_var, width=15).grid(row=2, column=1, sticky=tk.W, pady=5)

        # Instructor filter
        ttk.Label(frame, text="Instructor:", font=('Helvetica', 10, 'bold')).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(15, 10)
        )

        instructor_var = tk.StringVar()
        instructor_combo = ttk.Combobox(frame, textvariable=instructor_var, state='readonly', width=25)
        instructor_names = ["All"] + [f"{i['display_name']}" for i in self.data_manager.get_instructors()]
        instructor_combo['values'] = instructor_names
        instructor_combo.set("All")
        instructor_combo.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Room filter
        ttk.Label(frame, text="Room:", font=('Helvetica', 10, 'bold')).grid(
            row=5, column=0, columnspan=2, sticky=tk.W, pady=(15, 10)
        )

        room_var = tk.StringVar()
        room_combo = ttk.Combobox(frame, textvariable=room_var, state='readonly', width=25)
        room_names = ["All"] + [r.name for r in self.data_manager.rooms]
        room_combo['values'] = room_names
        room_combo.set("All")
        room_combo.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)

        def apply_filters():
            """Apply the selected filters."""
            # Clear current view
            for item in self.schedule_tree.get_children():
                self.schedule_tree.delete(item)

            # Start with all exams
            filtered_exams = list(self.data_manager.exams)

            # Apply date range filter
            start_date = start_date_var.get().strip()
            end_date = end_date_var.get().strip()
            if start_date and end_date:
                try:
                    filtered_exams = self.data_manager.get_exams_by_date_range(start_date, end_date)
                except:
                    messagebox.showerror("Error", "Invalid date range")
                    return

            # Apply instructor filter
            instructor_sel = instructor_var.get()
            if instructor_sel and instructor_sel != "All":
                instructor_id = None
                for inst in self.data_manager.get_instructors():
                    if inst['display_name'] == instructor_sel:
                        instructor_id = inst['id']
                        break
                if instructor_id:
                    filtered_exams = [e for e in filtered_exams if e.instructor_id == instructor_id]

            # Apply room filter
            room_sel = room_var.get()
            if room_sel and room_sel != "All":
                filtered_exams = [e for e in filtered_exams if e.room == room_sel]

            # Display filtered results
            for exam in sorted(filtered_exams, key=lambda x: (x.date, x.start_time)):
                time_str = f"{exam.start_time} - {exam.end_time}"
                self.schedule_tree.insert('', tk.END, values=(
                    exam.id, exam.module_code, exam.module_name, exam.date,
                    time_str, exam.room, exam.instructor_name, exam.students_enrolled
                ))

            messagebox.showinfo("Filters Applied", f"Showing {len(filtered_exams)} exams")
            dialog.destroy()

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=20)

        ttk.Button(btn_frame, text="Apply", command=apply_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def export_selected_exams(self):
        """Export selected exams from the schedule view."""
        selected_items = self.schedule_tree.selection()

        if not selected_items:
            messagebox.showwarning("No Selection", "Please select exams to export")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfilename="selected_exams.csv"
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Module Code', 'Module Name', 'Date', 'Start Time',
                               'End Time', 'Room', 'Instructor', 'Students'])

                for item in selected_items:
                    values = self.schedule_tree.item(item)['values']
                    exam_id = values[0]
                    exam = next((e for e in self.data_manager.exams if e.id == exam_id), None)
                    if exam:
                        writer.writerow([
                            exam.module_code, exam.module_name, exam.date,
                            exam.start_time, exam.end_time, exam.room,
                            exam.instructor_name, exam.students_enrolled
                        ])

            messagebox.showinfo("Success", f"Exported {len(selected_items)} exams to:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")

    def check_instructor_availability(self):
        """Check if the selected instructor has conflicts."""
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()
        instructor_id = self.get_selected_instructor_id()

        if not all([date, start, end]):
            messagebox.showwarning("Incomplete", "Please fill in date, start time, and end time first")
            return

        if not instructor_id:
            messagebox.showwarning("No Instructor", "Please select an instructor first")
            return

        # Get conflicting exams
        conflicts = self.data_manager.check_instructor_conflict(
            date, start, end, instructor_id,
            exclude_id=self.selected_exam_id
        )

        instructor_name = self.get_instructor_display_name()

        if conflicts:
            conflict_info = "\n".join([
                f"• {e.module_code} in {e.room} ({e.start_time}-{e.end_time})"
                for e in conflicts
            ])
            messagebox.showwarning(
                "Instructor Conflict",
                f"{instructor_name} has conflicts on {date}:\n\n{conflict_info}"
            )
        else:
            messagebox.showinfo(
                "Available",
                f"✓ {instructor_name} is available on {date} from {start} to {end}"
            )

    def suggest_available_rooms(self):
        """Show available rooms based on current date/time/capacity requirements."""
        date = self.exam_vars['date'].get()
        start = self.exam_vars['start_time'].get()
        end = self.exam_vars['end_time'].get()

        if not all([date, start, end]):
            messagebox.showwarning("Incomplete", "Please fill in date, start time, and end time first")
            return

        # Get minimum capacity requirement
        min_capacity = len(self.enrolled_student_ids)

        # Get available rooms
        available_rooms = self.data_manager.get_available_rooms(
            date, start, end, min_capacity,
            exclude_id=self.selected_exam_id
        )

        if not available_rooms:
            messagebox.showinfo(
                "No Rooms Available",
                f"No rooms available on {date} from {start} to {end}\n"
                f"with capacity >= {min_capacity}"
            )
            return

        # Show dialog with available rooms
        dialog = tk.Toplevel(self.root)
        dialog.title("Available Rooms")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"Available rooms on {date} from {start} to {end}:",
            font=('Helvetica', 11, 'bold')
        ).pack(pady=(0, 10))

        # Create treeview for rooms
        columns = ('name', 'building', 'capacity', 'facilities')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)

        tree.heading('name', text='Room')
        tree.heading('building', text='Building')
        tree.heading('capacity', text='Capacity')
        tree.heading('facilities', text='Facilities')

        tree.column('name', width=100)
        tree.column('building', width=120)
        tree.column('capacity', width=80)
        tree.column('facilities', width=180)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate with available rooms
        for room in sorted(available_rooms, key=lambda r: r.capacity, reverse=True):
            facilities = []
            if room.has_computers:
                facilities.append("Computers")
            if room.has_projector:
                facilities.append("Projector")
            facilities_str = ", ".join(facilities) if facilities else "None"

            # Highlight if capacity is just right
            tag = 'suitable' if min_capacity > 0 and room.capacity >= min_capacity and room.capacity < min_capacity * 1.5 else ''

            tree.insert('', tk.END, values=(
                room.name, room.building, room.capacity, facilities_str
            ), tags=(tag,))

        tree.tag_configure('suitable', background='lightgreen')

        def select_room():
            """Select the room from the dialog."""
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a room")
                return

            item = tree.item(selection[0])
            room_name = item['values'][0]
            room = next((r for r in available_rooms if r.name == room_name), None)
            if room:
                self.room_var.set(f"{room.name} ({room.building}) - Cap: {room.capacity}")
                dialog.destroy()

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Select Room", command=select_room).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

        if min_capacity > 0:
            ttk.Label(
                frame,
                text=f"Rooms highlighted in green are suitable for {min_capacity} students",
                font=('Helvetica', 8, 'italic'),
                foreground='darkgreen'
            ).pack(pady=(5, 0))

    def find_all_conflicts(self):
        """Find and display all scheduling conflicts."""
        conflicts_found = []

        # Check for room conflicts
        for i, exam1 in enumerate(self.data_manager.exams):
            for exam2 in self.data_manager.exams[i+1:]:
                # Same room and date
                if exam1.date == exam2.date and exam1.room == exam2.room:
                    # Check time overlap
                    if not (exam2.end_time <= exam1.start_time or exam2.start_time >= exam1.end_time):
                        conflicts_found.append({
                            'type': 'Room',
                            'location': exam1.room,
                            'date': exam1.date,
                            'exam1': f"{exam1.module_code} ({exam1.start_time}-{exam1.end_time})",
                            'exam2': f"{exam2.module_code} ({exam2.start_time}-{exam2.end_time})"
                        })

                # Same instructor and date
                if (exam1.date == exam2.date and
                    exam1.instructor_id and exam2.instructor_id and
                    exam1.instructor_id == exam2.instructor_id):
                    # Check time overlap
                    if not (exam2.end_time <= exam1.start_time or exam2.start_time >= exam1.end_time):
                        conflicts_found.append({
                            'type': 'Instructor',
                            'location': exam1.instructor_name,
                            'date': exam1.date,
                            'exam1': f"{exam1.module_code} in {exam1.room} ({exam1.start_time}-{exam1.end_time})",
                            'exam2': f"{exam2.module_code} in {exam2.room} ({exam2.start_time}-{exam2.end_time})"
                        })

        if not conflicts_found:
            messagebox.showinfo("No Conflicts", "✓ No scheduling conflicts found!")
            return

        # Show conflicts dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Scheduling Conflicts")
        dialog.geometry("700x400")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=f"⚠ Found {len(conflicts_found)} conflict(s):",
            font=('Helvetica', 12, 'bold'),
            foreground='red'
        ).pack(pady=(0, 10))

        # Create treeview for conflicts
        columns = ('type', 'location', 'date', 'exam1', 'exam2')
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=12)

        tree.heading('type', text='Type')
        tree.heading('location', text='Resource')
        tree.heading('date', text='Date')
        tree.heading('exam1', text='Exam 1')
        tree.heading('exam2', text='Exam 2')

        tree.column('type', width=80)
        tree.column('location', width=120)
        tree.column('date', width=100)
        tree.column('exam1', width=180)
        tree.column('exam2', width=180)

        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Populate with conflicts
        for conflict in conflicts_found:
            tree.insert('', tk.END, values=(
                conflict['type'],
                conflict['location'],
                conflict['date'],
                conflict['exam1'],
                conflict['exam2']
            ))

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Export to CSV", command=lambda: self.export_conflicts(conflicts_found)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def export_conflicts(self, conflicts: List[Dict]):
        """Export conflicts to CSV file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfilename="exam_conflicts.csv"
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['type', 'location', 'date', 'exam1', 'exam2'])
                writer.writeheader()
                writer.writerows(conflicts)

            messagebox.showinfo("Success", f"Exported {len(conflicts)} conflicts to:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export: {e}")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = ExamSchedulerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
