import uuid
import json
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from university_system.utils.logging.log_config import configure_logging
from .exceptions import CalendarError, ValidationError
from .config import ValidationUtils

logger = configure_logging(name=__name__)


class AdvancedSearchManager:
    """Provides advanced search and filtering capabilities"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager

    def advanced_search(self, search_criteria: Dict) -> Tuple[bool, List[Dict]]:
        """Perform advanced search with multiple criteria"""
        try:
            base_query = """
                SELECT e.*,
                       GROUP_CONCAT(DISTINCT et.name) as tags,
                       GROUP_CONCAT(DISTINCT c.name) as courses,
                       ec.name as category_name
                FROM academic_calendar_events e
                LEFT JOIN event_tag_assignments eta ON e.id = eta.event_id
                LEFT JOIN event_tags et ON eta.tag_id = et.id
                LEFT JOIN course_events ce ON e.id = ce.event_id
                LEFT JOIN courses c ON ce.course_id = c.id
                LEFT JOIN event_categories ec ON e.event_type = ec.name
            """

            conditions = []
            params = []

            # Text search with sanitization
            if search_criteria.get('text'):
                search_text = ValidationUtils.sanitize_string(search_criteria['text'], 200)
                conditions.append("(e.name LIKE ? OR e.description LIKE ?)")
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern])

            # Date range with validation
            if search_criteria.get('start_date'):
                if ValidationUtils.validate_date(search_criteria['start_date']):
                    conditions.append("(e.date >= ? OR e.date_start >= ?)")
                    params.extend([search_criteria['start_date'], search_criteria['start_date']])

            if search_criteria.get('end_date'):
                if ValidationUtils.validate_date(search_criteria['end_date']):
                    conditions.append("(e.date <= ? OR e.date_end <= ?)")
                    params.extend([search_criteria['end_date'], search_criteria['end_date']])

            # Event type with sanitization
            if search_criteria.get('event_type'):
                event_type = ValidationUtils.sanitize_string(search_criteria['event_type'], 50)
                conditions.append("e.event_type = ?")
                params.append(event_type)

            # Tags with proper parameterization
            if search_criteria.get('tags') and isinstance(search_criteria['tags'], list):
                sanitized_tags = [ValidationUtils.sanitize_string(tag, 50) for tag in search_criteria['tags']]
                if sanitized_tags:
                    placeholders = ','.join(['?' for _ in sanitized_tags])
                    conditions.append(f"et.name IN ({placeholders})")
                    params.extend(sanitized_tags)

            # Course (courses use integer IDs, not UUIDs)
            if search_criteria.get('course_id'):
                course_id_value = str(search_criteria['course_id']).strip()
                if course_id_value:
                    conditions.append("c.id = ?")
                    params.append(course_id_value)

            # Build final query
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)

            base_query += " GROUP BY e.id ORDER BY COALESCE(e.date, e.date_start) LIMIT ?"
            params.append(1000)  # Limit results for performance

            rows = self.db_manager.execute_query(base_query, tuple(params))
            results = [dict(row) for row in rows]

            return True, results

        except Exception as e:
            logger.error(f"Advanced search failed: {e}")
            return False, f"Search failed: {str(e)}"

    def save_search_preset(self, user_id, name: str, filters: Dict) -> Tuple[bool, str]:
        """Save search criteria as a preset"""
        try:
            if user_id is None or str(user_id).strip() == '':
                raise ValidationError("Invalid user ID")

            name = ValidationUtils.sanitize_string(name, 100)
            if not name:
                raise ValidationError("Preset name is required")

            preset_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update(
                    """INSERT INTO search_presets (id, name, user_id, filters, date_added)
                       VALUES (?, ?, ?, ?, ?)""",
                    (preset_id, name, user_id, json.dumps(filters),
                     datetime.now().isoformat())
                )

            return True, f"Search preset '{name}' saved successfully"

        except Exception as e:
            logger.error(f"Failed to save search preset: {e}")
            raise CalendarError(f"Failed to save preset: {str(e)}")
