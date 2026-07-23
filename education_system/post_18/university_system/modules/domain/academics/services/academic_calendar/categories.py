import uuid
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.exceptions import CalendarError, ValidationError, PermissionError
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.config import ValidationUtils

logger = configure_logging(name=__name__)


class EventCategoryManager:
    """Manages event categories and tagging system"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_category(self, name: str, color_code: str = None, description: str = None) -> Tuple[bool, str]:
        """Create a new event category"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to manage categories")

        try:
            if not name or not name.strip():
                raise ValidationError("Category name is required")

            name = ValidationUtils.sanitize_string(name, 100)
            description = ValidationUtils.sanitize_string(description or "", 500)

            # Check if category already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM event_categories WHERE name = ?", (name,)
            )
            if existing:
                return False, f"Category '{name}' already exists"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO event_categories (name, color_code, description, date_added)
                       VALUES (?, ?, ?, ?)""",
                    (name, color_code, description, datetime.now().isoformat())
                )

            logger.info(f"Category '{name}' created")
            return True, f"Category '{name}' created successfully"

        except Exception as e:
            logger.error(f"Failed to create category: {e}")
            raise CalendarError(f"Failed to create category: {str(e)}")

    def create_tag(self, name: str, color_code: str = None) -> Tuple[bool, str]:
        """Create a new event tag"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to manage tags")

        try:
            if not name or not name.strip():
                raise ValidationError("Tag name is required")

            name = ValidationUtils.sanitize_string(name, 50)

            # Check if tag already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM event_tags WHERE name = ?", (name,)
            )
            if existing:
                return False, f"Tag '{name}' already exists"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO event_tags (name, color_code, date_added)
                       VALUES (?, ?, ?)""",
                    (name, color_code, datetime.now().isoformat())
                )

            logger.info(f"Tag '{name}' created")
            return True, f"Tag '{name}' created successfully"

        except Exception as e:
            logger.error(f"Failed to create tag: {e}")
            raise CalendarError(f"Failed to create tag: {str(e)}")

    def assign_tags_to_event(self, event_id: str, tag_names: List[str]) -> Tuple[bool, str]:
        """Assign multiple tags to an event"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to assign tags")

        try:
            if not event_id or not str(event_id).strip():
                raise ValidationError("Invalid event ID")

            # Verify event exists
            event_exists = self.db_manager.execute_query(
                "SELECT id FROM academic_calendar_events WHERE id = ?", (event_id,)
            )
            if not event_exists:
                raise ValidationError(f"Event with ID '{event_id}' not found")

            successful_assignments = 0

            with self.db_manager.transaction():
                for tag_name in tag_names:
                    tag_name = ValidationUtils.sanitize_string(tag_name, 50)

                    # Get or create tag
                    tag_rows = self.db_manager.execute_query(
                        "SELECT id FROM event_tags WHERE name = ?", (tag_name,)
                    )

                    if tag_rows:
                        tag_id = tag_rows[0]['id']
                    else:
                        # Create tag if it doesn't exist
                        success, tag_id = self.create_tag(tag_name)
                        if not success:
                            continue

                    # Check if assignment already exists
                    existing_assignment = self.db_manager.execute_query(
                        "SELECT 1 FROM event_tag_assignments WHERE event_id = ? AND tag_id = ?",
                        (event_id, tag_id)
                    )

                    if not existing_assignment:
                        self.db_manager.execute_update(
                            """INSERT INTO event_tag_assignments (event_id, tag_id, date_added)
                               VALUES (?, ?, ?)""",
                            (event_id, tag_id, datetime.now().isoformat())
                        )
                        successful_assignments += 1

            return True, f"Successfully assigned {successful_assignments} tags to event"

        except Exception as e:
            logger.error(f"Failed to assign tags: {e}")
            raise CalendarError(f"Failed to assign tags: {str(e)}")

class CourseManager:
    """Manages courses and their integration with events"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def create_course(self, course_data: Dict) -> Tuple[bool, str]:
        """Create a new course"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create courses")

        try:
            required_fields = ['code', 'name']
            for field in required_fields:
                if field not in course_data or not str(course_data[field]).strip():
                    raise ValidationError(f"Required field '{field}' is missing or empty")

            course_code = ValidationUtils.sanitize_string(course_data['code'], 20)
            course_name = ValidationUtils.sanitize_string(course_data['name'], 200)

            # Check if course code already exists
            existing = self.db_manager.execute_query(
                "SELECT id FROM courses WHERE code = ?", (course_code,)
            )
            if existing:
                return False, f"Course with code '{course_code}' already exists"

            course_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO courses (id, code, name, credits, department, instructor_id,
                       academic_year_id, semester_id, status, date_added)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (course_id, course_code, course_name,
                     course_data.get('credits', 3),
                     ValidationUtils.sanitize_string(course_data.get('department', ''), 100),
                     course_data.get('instructor_id'),
                     course_data.get('academic_year_id'),
                     course_data.get('semester_id'),
                     ValidationUtils.sanitize_string(course_data.get('status', 'active'), 20),
                     datetime.now().isoformat())
                )

            logger.info(f"Course '{course_code}' created with ID: {course_id}")
            return True, f"Course created with ID: {course_id}"

        except Exception as e:
            logger.error(f"Failed to create course: {e}")
            raise CalendarError(f"Failed to create course: {str(e)}")

    def link_event_to_course(self, event_id: str, course_id: str, event_sub_type: str = None) -> Tuple[bool, str]:
        """Link an event to a course"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to link events to courses")

        try:
            # Validate event_id is not empty
            if not event_id or not str(event_id).strip():
                raise ValidationError("Invalid event ID - cannot be empty")

            # Validate course_id is not empty (courses use integer IDs, not UUIDs)
            if not course_id or not str(course_id).strip():
                raise ValidationError("Invalid course ID - cannot be empty")

            # Verify both event and course exist
            event_exists = self.db_manager.execute_query(
                "SELECT id FROM academic_calendar_events WHERE id = ?", (event_id,)
            )
            if not event_exists:
                return False, f"Event with ID '{event_id}' not found"

            course_exists = self.db_manager.execute_query(
                "SELECT id FROM courses WHERE id = ?", (course_id,)
            )
            if not course_exists:
                return False, f"Course with ID '{course_id}' not found"

            # Check if link already exists
            existing_link = self.db_manager.execute_query(
                "SELECT 1 FROM course_events WHERE event_id = ? AND course_id = ?",
                (event_id, course_id)
            )

            if existing_link:
                return False, "Event is already linked to this course"

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO course_events (event_id, course_id, event_sub_type, date_added)
                       VALUES (?, ?, ?, datetime('now'))""",
                    (event_id, course_id, ValidationUtils.sanitize_string(event_sub_type or "", 50))
                )

            logger.info(f"Event {event_id} linked to course {course_id}")
            return True, "Event successfully linked to course"

        except Exception as e:
            logger.error(f"Failed to link event to course: {e}")
            raise CalendarError(f"Failed to link event to course: {str(e)}")
