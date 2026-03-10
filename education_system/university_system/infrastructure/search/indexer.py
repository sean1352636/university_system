"""
Real-time search indexer

Hooks into CRUD operations to automatically update search indices
when data changes.
"""

import logging
from typing import Dict, Any, Optional
from functools import wraps

from education_system.university_system.infrastructure.search.search_service import get_search_service

logger = logging.getLogger(__name__)


class SearchIndexer:
    """
    Real-time search indexer

    Provides hooks for automatic index updates on:
    - Create (index new document)
    - Update (update existing document)
    - Delete (remove from index)
    """

    def __init__(self):
        """Initialize search indexer"""
        self.search_service = get_search_service()
        self.enabled = True

    def index_student(self, student_data: Dict[str, Any]) -> bool:
        """
        Index a student record

        Args:
            student_data: Student data dict

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        try:
            student_id = student_data.get('student_id')
            if not student_id:
                logger.warning("Student data missing student_id")
                return False

            # Prepare searchable document
            document = {
                'student_id': student_id,
                'name': f"{student_data.get('first_name', '')} {student_data.get('last_name', '')}".strip(),
                'first_name': student_data.get('first_name'),
                'last_name': student_data.get('last_name'),
                'email': student_data.get('email_address') or student_data.get('email'),
                'major': student_data.get('course') or student_data.get('major'),
                'gpa': student_data.get('gpa'),
                'enrollment_date': student_data.get('enrollment_date'),
                'status': student_data.get('status'),
                'graduation_year': student_data.get('graduation_year'),
            }

            return self.search_service.index_document('students', student_id, document)

        except Exception as e:
            logger.error(f"Error indexing student: {e}")
            return False

    def index_course(self, course_data: Dict[str, Any]) -> bool:
        """Index a course record"""
        if not self.enabled:
            return False

        try:
            course_id = course_data.get('course_id') or course_data.get('id')
            if not course_id:
                logger.warning("Course data missing course_id")
                return False

            document = {
                'course_id': course_id,
                'code': course_data.get('course_code') or course_data.get('code'),
                'name': course_data.get('course_name') or course_data.get('name'),
                'description': course_data.get('description'),
                'department': course_data.get('department'),
                'instructor': course_data.get('instructor'),
                'instructor_id': course_data.get('instructor_id'),
                'credits': course_data.get('credits'),
                'capacity': course_data.get('capacity'),
                'enrolled': course_data.get('enrolled_count') or course_data.get('enrolled'),
                'semester': course_data.get('semester'),
                'year': course_data.get('year'),
            }

            return self.search_service.index_document('courses', course_id, document)

        except Exception as e:
            logger.error(f"Error indexing course: {e}")
            return False

    def index_staff(self, staff_data: Dict[str, Any]) -> bool:
        """Index a staff member record"""
        if not self.enabled:
            return False

        try:
            staff_id = staff_data.get('staff_id') or staff_data.get('id')
            if not staff_id:
                logger.warning("Staff data missing staff_id")
                return False

            document = {
                'staff_id': staff_id,
                'name': staff_data.get('name') or f"{staff_data.get('first_name', '')} {staff_data.get('last_name', '')}".strip(),
                'email': staff_data.get('email'),
                'department': staff_data.get('department'),
                'position': staff_data.get('position') or staff_data.get('role'),
                'hire_date': staff_data.get('hire_date'),
                'phone': staff_data.get('phone'),
            }

            return self.search_service.index_document('staff', staff_id, document)

        except Exception as e:
            logger.error(f"Error indexing staff: {e}")
            return False

    def index_event(self, event_data: Dict[str, Any]) -> bool:
        """Index an event record"""
        if not self.enabled:
            return False

        try:
            event_id = event_data.get('event_id') or event_data.get('id')
            if not event_id:
                logger.warning("Event data missing event_id")
                return False

            document = {
                'event_id': event_id,
                'title': event_data.get('title') or event_data.get('name'),
                'description': event_data.get('description'),
                'location': event_data.get('location'),
                'category': event_data.get('category') or event_data.get('type'),
                'organizer': event_data.get('organizer'),
                'start_date': event_data.get('start_date') or event_data.get('event_date'),
                'end_date': event_data.get('end_date'),
                'capacity': event_data.get('capacity'),
                'registered': event_data.get('registered_count') or event_data.get('registered'),
            }

            return self.search_service.index_document('events', event_id, document)

        except Exception as e:
            logger.error(f"Error indexing event: {e}")
            return False

    def delete_from_index(self, entity_type: str, entity_id: str) -> bool:
        """
        Delete an entity from search index

        Args:
            entity_type: Type of entity (students, courses, etc.)
            entity_id: Entity ID

        Returns:
            True if successful
        """
        if not self.enabled:
            return False

        return self.search_service.delete_document(entity_type, entity_id)

    def reindex_all_students(self) -> Dict[str, int]:
        """Reindex all students"""
        if not self.enabled:
            return {'success': 0, 'errors': 0}

        return self.search_service.reindex_all('students')

    def reindex_all_courses(self) -> Dict[str, int]:
        """Reindex all courses"""
        if not self.enabled:
            return {'success': 0, 'errors': 0}

        return self.search_service.reindex_all('courses')

    def reindex_all_staff(self) -> Dict[str, int]:
        """Reindex all staff"""
        if not self.enabled:
            return {'success': 0, 'errors': 0}

        return self.search_service.reindex_all('staff')

    def reindex_all_events(self) -> Dict[str, int]:
        """Reindex all events"""
        if not self.enabled:
            return {'success': 0, 'errors': 0}

        return self.search_service.reindex_all('events')

    def reindex_all(self) -> Dict[str, Dict[str, int]]:
        """
        Reindex all entity types

        Returns:
            Dict mapping entity types to success/error counts
        """
        results = {}

        logger.info("Starting full reindex...")

        results['students'] = self.reindex_all_students()
        results['courses'] = self.reindex_all_courses()
        results['staff'] = self.reindex_all_staff()
        results['events'] = self.reindex_all_events()

        logger.info("Full reindex complete")

        return results

    def enable(self):
        """Enable automatic indexing"""
        self.enabled = True
        logger.info("Search indexer enabled")

    def disable(self):
        """Disable automatic indexing"""
        self.enabled = False
        logger.info("Search indexer disabled")


# Decorator for automatic indexing
def auto_index_student(func):
    """Decorator to automatically index student after create/update"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        # Try to extract student data and index
        try:
            indexer = get_search_indexer()

            # Handle different return types
            if isinstance(result, dict):
                indexer.index_student(result)
            elif isinstance(result, tuple) and len(result) > 0 and isinstance(result[0], dict):
                indexer.index_student(result[0])

        except Exception as e:
            logger.error(f"Error in auto_index_student: {e}")

        return result

    return wrapper


def auto_index_course(func):
    """Decorator to automatically index course after create/update"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)

        try:
            indexer = get_search_indexer()

            if isinstance(result, dict):
                indexer.index_course(result)
            elif isinstance(result, tuple) and len(result) > 0 and isinstance(result[0], dict):
                indexer.index_course(result[0])

        except Exception as e:
            logger.error(f"Error in auto_index_course: {e}")

        return result

    return wrapper


# Singleton instance
_search_indexer: Optional[SearchIndexer] = None


def get_search_indexer() -> SearchIndexer:
    """Get the global search indexer instance"""
    global _search_indexer
    if _search_indexer is None:
        _search_indexer = SearchIndexer()
    return _search_indexer
