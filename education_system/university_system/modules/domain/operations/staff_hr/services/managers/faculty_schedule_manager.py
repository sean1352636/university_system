"""
Faculty Schedule Manager

Provides functionality for:
- Weekly schedule block management
- Conflict detection
- Teaching schedule import
- Template management
- Schedule reporting
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.core.activity_logger import log_activity
from education_system.university_system.core.sql_safety import validate_identifier  # nosec B608


class FacultyScheduleManager:
    """Manager for faculty weekly schedule building."""

    # ==================== BLOCK CRUD ====================

    @staticmethod
    def create_block(user_id, day_of_week, start_time, end_time, activity_type='teaching',
                     title=None, description=None, location=None, course_code=None,
                     color=None, is_locked=False, semester=None, academic_year=None) -> int:
        """Create a schedule block. Check for conflicts first via check_conflicts().
        If conflict found, raise ValueError.
        INSERT INTO faculty_schedule_blocks, log_activity, return block_id."""
        # Check for conflicts before inserting
        conflicts = FacultyScheduleManager.check_conflicts(
            user_id, day_of_week, start_time, end_time
        )
        if conflicts:
            raise ValueError(
                f"Schedule conflict detected with {len(conflicts)} existing block(s)"
            )

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO faculty_schedule_blocks (
                    user_id, day_of_week, start_time, end_time, activity_type,
                    title, description, location, course_code,
                    color, is_locked, semester, academic_year,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, day_of_week, start_time, end_time, activity_type,
                title, description, location, course_code,
                color, 1 if is_locked else 0, semester, academic_year,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            block_id = cursor.lastrowid
            log_activity('create', 'faculty_schedule_block', details={
                'block_id': block_id, 'user_id': user_id,
                'day_of_week': day_of_week, 'activity_type': activity_type
            })
            return block_id

    @staticmethod
    def update_block(block_id, **data) -> None:
        """Update a schedule block. Only update provided fields.
        Build SET clause dynamically from data dict keys.
        If day/time changed, check conflicts again (excluding this block_id)."""
        if not data:
            return

        # Get the existing block to know user_id for conflict check
        existing = FacultyScheduleManager.get_block(block_id)
        if not existing:
            raise ValueError(f"Block {block_id} not found")

        allowed_fields = {
            'day_of_week', 'start_time', 'end_time', 'activity_type',
            'title', 'description', 'location', 'course_code', 'color', 'is_locked'
        }

        fields = []
        values = []
        for key, value in data.items():
            if key in allowed_fields:
                fields.append(validate_identifier(key, "column") + ' = ?')
                values.append(value)

        if not fields:
            return

        # If day or time changed, check for conflicts excluding this block
        time_fields_changed = any(
            k in data for k in ('day_of_week', 'start_time', 'end_time')
        )
        if time_fields_changed:
            check_day = data.get('day_of_week', existing['day_of_week'])
            check_start = data.get('start_time', existing['start_time'])
            check_end = data.get('end_time', existing['end_time'])

            conflicts = FacultyScheduleManager.check_conflicts(
                existing['user_id'], check_day, check_start, check_end,
                exclude_block_id=block_id
            )
            if conflicts:
                raise ValueError(
                    f"Schedule conflict detected with {len(conflicts)} existing block(s)"
                )

        fields.append('updated_at = ?')
        values.append(datetime.now().isoformat())
        values.append(block_id)

        with transaction() as conn:
            conn.execute(
                'UPDATE faculty_schedule_blocks SET ' + ', '.join(fields)
                + ' WHERE block_id = ?',
                values
            )
            log_activity('update', 'faculty_schedule_block', details={
                'block_id': block_id, 'updated_fields': list(data.keys())
            })
        if data.get('is_locked'):
            try:
                from education_system.university_system.modules.services.integration_bus import (
                    publish_timetable_locked,
                )
                publish_timetable_locked(
                    [existing['user_id']],
                    academic_year=existing.get('academic_year'),
                    semester=existing.get('semester'),
                )
            except Exception:
                pass

    @staticmethod
    def delete_block(block_id) -> None:
        """Delete a schedule block. Don't allow if is_locked=1 (raise ValueError)."""
        block = FacultyScheduleManager.get_block(block_id)
        if not block:
            raise ValueError(f"Block {block_id} not found")

        if block.get('is_locked'):
            raise ValueError(
                "Cannot delete a locked schedule block. Unlock it first."
            )

        with transaction() as conn:
            conn.execute('''
                DELETE FROM faculty_schedule_blocks WHERE block_id = ?
            ''', (block_id,))
            log_activity('delete', 'faculty_schedule_block', details={
                'block_id': block_id
            })

    @staticmethod
    def get_block(block_id) -> Optional[Dict]:
        """Get a single block by ID."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM faculty_schedule_blocks WHERE block_id = ?
            ''', (block_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_user_schedule(user_id, semester=None, academic_year=None) -> List[Dict]:
        """Get all blocks for a user, optionally filtered by semester/year.
        ORDER BY day_of_week, start_time."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM faculty_schedule_blocks
                WHERE user_id = ?
            '''
            params = [user_id]

            if semester:
                query += ' AND semester = ?'
                params.append(semester)

            if academic_year:
                query += ' AND academic_year = ?'
                params.append(academic_year)

            query += ' ORDER BY day_of_week, start_time'
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== CONFLICT DETECTION ====================

    @staticmethod
    def check_conflicts(user_id, day_of_week, start_time, end_time,
                        exclude_block_id=None) -> List[Dict]:
        """Check for time overlaps on the same day.
        Returns list of conflicting blocks."""
        with get_connection() as conn:
            query = '''
                SELECT * FROM faculty_schedule_blocks
                WHERE user_id = ?
                AND day_of_week = ?
                AND start_time < ?
                AND end_time > ?
            '''
            params = [user_id, day_of_week, end_time, start_time]

            if exclude_block_id is not None:
                query += ' AND block_id != ?'
                params.append(exclude_block_id)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # ==================== TEACHING IMPORT ====================

    @staticmethod
    def import_teaching_schedule(user_id, semester=None, academic_year=None) -> int:
        """Import teaching schedule from module_schedule table.
        1. Try: SELECT * FROM module_schedule WHERE instructor_id=? (or user_id)
        2. For each row, create a locked block with activity_type='teaching'
        3. Map day names to day_of_week integers
        4. Return count of blocks created
        5. If module_schedule doesn't exist, return 0 gracefully."""
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6,
        }

        try:
            with get_connection() as conn:
                # Try instructor_id first, then user_id
                rows = None
                for id_column in ('instructor_id', 'user_id'):
                    try:
                        rows = conn.execute(
                            f'SELECT * FROM module_schedule WHERE {id_column} = ?',
                            (user_id,)
                        ).fetchall()
                        break
                    except Exception:
                        continue

                if not rows:
                    return 0

                count = 0
                for row in rows:
                    row_dict = dict(row)

                    # Map day name to integer
                    day_name = str(row_dict.get('day', row_dict.get('day_of_week', ''))).lower().strip()
                    day_of_week = day_map.get(day_name)
                    if day_of_week is None:
                        # Try parsing as integer directly
                        try:
                            day_of_week = int(day_name)
                        except (ValueError, TypeError):
                            continue

                    start_time = row_dict.get('start_time', row_dict.get('time_start'))
                    end_time = row_dict.get('end_time', row_dict.get('time_end'))

                    if not start_time or not end_time:
                        continue

                    title = row_dict.get('module_name', row_dict.get('title', ''))
                    course_code = row_dict.get('module_code', row_dict.get('course_code', ''))
                    location = row_dict.get('room', row_dict.get('location', ''))

                    try:
                        FacultyScheduleManager.create_block(
                            user_id=user_id,
                            day_of_week=day_of_week,
                            start_time=str(start_time),
                            end_time=str(end_time),
                            activity_type='teaching',
                            title=str(title) if title else None,
                            course_code=str(course_code) if course_code else None,
                            location=str(location) if location else None,
                            is_locked=True,
                            semester=semester,
                            academic_year=academic_year,
                        )
                        count += 1
                    except ValueError:
                        # Skip blocks that conflict
                        continue

                return count

        except Exception:
            # module_schedule table doesn't exist or other DB error
            return 0

    # ==================== TEMPLATE MANAGEMENT ====================

    @staticmethod
    def save_as_template(user_id, name, description=None, is_shared=False) -> int:
        """Save current schedule as template.
        1. Get all blocks for user
        2. Serialize to JSON (list of block dicts, excluding IDs/timestamps)
        3. INSERT INTO faculty_schedule_templates
        4. Return template_id."""
        blocks = FacultyScheduleManager.get_user_schedule(user_id)

        # Serialize blocks, excluding IDs and timestamps
        exclude_keys = {'block_id', 'user_id', 'created_at', 'updated_at'}
        template_blocks = []
        for block in blocks:
            template_block = {
                k: v for k, v in block.items() if k not in exclude_keys
            }
            template_blocks.append(template_block)

        blocks_json = json.dumps(template_blocks)

        with transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO faculty_schedule_templates (
                    user_id, name, description, blocks_json,
                    is_shared, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, name, description, blocks_json,
                1 if is_shared else 0,
                datetime.now().isoformat(), datetime.now().isoformat(),
            ))
            template_id = cursor.lastrowid
            log_activity('create', 'faculty_schedule_template', details={
                'template_id': template_id, 'user_id': user_id,
                'block_count': len(template_blocks)
            })
            return template_id

    @staticmethod
    def get_templates(user_id=None, include_shared=True) -> List[Dict]:
        """Get templates. If user_id provided, get user's templates.
        If include_shared, also get templates where is_shared=1."""
        with get_connection() as conn:
            if user_id:
                if include_shared:
                    query = '''
                        SELECT * FROM faculty_schedule_templates
                        WHERE user_id = ? OR is_shared = 1
                        ORDER BY name
                    '''
                    params = [user_id]
                else:
                    query = '''
                        SELECT * FROM faculty_schedule_templates
                        WHERE user_id = ?
                        ORDER BY name
                    '''
                    params = [user_id]
            else:
                if include_shared:
                    query = '''
                        SELECT * FROM faculty_schedule_templates
                        WHERE is_shared = 1
                        ORDER BY name
                    '''
                    params = []
                else:
                    query = '''
                        SELECT * FROM faculty_schedule_templates
                        ORDER BY name
                    '''
                    params = []

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    @staticmethod
    def load_template(template_id, user_id, clear_existing=False) -> int:
        """Load a template into user's schedule.
        1. Get template, parse blocks_json
        2. If clear_existing, DELETE existing non-locked blocks for user
        3. For each block in template, create_block (skip if conflict)
        4. Return count of blocks created."""
        with get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM faculty_schedule_templates WHERE template_id = ?
            ''', (template_id,)).fetchone()

        if not row:
            raise ValueError(f"Template {template_id} not found")

        template = dict(row)
        blocks = json.loads(template['blocks_json'])

        if clear_existing:
            with transaction() as conn:
                conn.execute('''
                    DELETE FROM faculty_schedule_blocks
                    WHERE user_id = ? AND is_locked = 0
                ''', (user_id,))
                log_activity('delete', 'faculty_schedule_block', details={
                    'user_id': user_id, 'action': 'clear_for_template',
                    'template_id': template_id
                })

        count = 0
        for block in blocks:
            try:
                FacultyScheduleManager.create_block(
                    user_id=user_id,
                    day_of_week=block.get('day_of_week'),
                    start_time=block.get('start_time'),
                    end_time=block.get('end_time'),
                    activity_type=block.get('activity_type', 'teaching'),
                    title=block.get('title'),
                    description=block.get('description'),
                    location=block.get('location'),
                    course_code=block.get('course_code'),
                    color=block.get('color'),
                    is_locked=block.get('is_locked', False),
                    semester=block.get('semester'),
                    academic_year=block.get('academic_year'),
                )
                count += 1
            except ValueError:
                # Skip blocks that conflict
                continue

        return count

    # ==================== REPORTING ====================

    @staticmethod
    def get_weekly_summary(user_id) -> Dict:
        """Get hours breakdown by activity type.
        For each block, calculate duration in hours.
        Return {'total_hours': X, 'by_type': {'teaching': Y, 'research': Z, ...}}."""
        blocks = FacultyScheduleManager.get_user_schedule(user_id)

        total_hours = 0.0
        by_type: Dict[str, float] = {}

        for block in blocks:
            start = block.get('start_time', '')
            end = block.get('end_time', '')

            try:
                # Parse HH:MM format
                start_parts = start.split(':')
                end_parts = end.split(':')
                start_minutes = int(start_parts[0]) * 60 + int(start_parts[1])
                end_minutes = int(end_parts[0]) * 60 + int(end_parts[1])
                duration_hours = (end_minutes - start_minutes) / 60.0
            except (ValueError, IndexError):
                duration_hours = 0.0

            if duration_hours > 0:
                total_hours += duration_hours
                activity = block.get('activity_type', 'other')
                by_type[activity] = by_type.get(activity, 0.0) + duration_hours

        return {
            'total_hours': round(total_hours, 2),
            'by_type': {k: round(v, 2) for k, v in by_type.items()},
        }

    @staticmethod
    def get_activity_types() -> List[Dict]:
        """Get all active schedule activity types from schedule_activity_types table.
        ORDER BY sort_order."""
        with get_connection() as conn:
            try:
                rows = conn.execute('''
                    SELECT * FROM schedule_activity_types
                    WHERE is_active = 1
                    ORDER BY sort_order
                ''').fetchall()
                return [dict(row) for row in rows]
            except Exception:
                # Table may not exist yet; return sensible defaults
                return [
                    {'type_id': 1, 'name': 'teaching', 'label': 'Teaching', 'color': '#4CAF50', 'sort_order': 1},
                    {'type_id': 2, 'name': 'research', 'label': 'Research', 'color': '#2196F3', 'sort_order': 2},
                    {'type_id': 3, 'name': 'office_hours', 'label': 'Office Hours', 'color': '#FF9800', 'sort_order': 3},
                    {'type_id': 4, 'name': 'meeting', 'label': 'Meeting', 'color': '#9C27B0', 'sort_order': 4},
                    {'type_id': 5, 'name': 'admin', 'label': 'Administration', 'color': '#607D8B', 'sort_order': 5},
                    {'type_id': 6, 'name': 'other', 'label': 'Other', 'color': '#795548', 'sort_order': 6},
                ]
