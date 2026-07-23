import uuid
import logging
from datetime import datetime
from typing import Dict, Tuple, Any
from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.exceptions import ValidationError, PermissionError
from education_system.post_18.university_system.modules.domain.academics.services.academic_calendar.config import ValidationUtils

logger = configure_logging(name=__name__)


class AcademicDeadlineManager:
    """Enhanced academic deadline and milestone tracking"""

    def __init__(self, db_manager, auth_manager):
        self.db_manager = db_manager
        self.auth_manager = auth_manager
        self._create_deadline_tables()

    def _create_deadline_tables(self):
        """Create tables for deadline management"""
        try:
            # Project milestones table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS project_milestones (
                id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                milestone_name TEXT NOT NULL,
                due_date TEXT NOT NULL,
                completion_percentage REAL DEFAULT 0.0,
                status TEXT DEFAULT 'pending',
                course_id TEXT,
                student_id TEXT,
                description TEXT,
                created_at TEXT NOT NULL,
                last_updated TEXT,
                FOREIGN KEY (course_id) REFERENCES courses (id),
                FOREIGN KEY (student_id) REFERENCES students (student_id)
            )''')

            # Migration: Add last_updated column if it doesn't exist
            columns = self.db_manager.execute_query(
                "PRAGMA table_info(project_milestones)"
            )
            column_names = [col[1] for col in columns] if columns else []
            if 'last_updated' not in column_names:
                self.db_manager.execute_update(
                    'ALTER TABLE project_milestones ADD COLUMN last_updated TEXT'
                )

            # Graduation requirements table
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS graduation_requirements (
                id TEXT PRIMARY KEY,
                requirement_name TEXT NOT NULL,
                requirement_type TEXT NOT NULL,
                credits_required INTEGER,
                course_category TEXT,
                deadline_date TEXT,
                is_mandatory BOOLEAN DEFAULT TRUE,
                created_at TEXT NOT NULL
            )''')

            # Student requirement tracking
            self.db_manager.execute_update('''
            CREATE TABLE IF NOT EXISTS student_requirement_progress (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                requirement_id TEXT NOT NULL,
                credits_completed REAL DEFAULT 0.0,
                completion_percentage REAL DEFAULT 0.0,
                status TEXT DEFAULT 'in_progress',
                completion_date TEXT,
                notes TEXT,
                FOREIGN KEY (student_id) REFERENCES students (student_id),
                FOREIGN KEY (requirement_id) REFERENCES graduation_requirements (id),
                UNIQUE(student_id, requirement_id)
            )''')

        except Exception as e:
            logger.error(f"Failed to create deadline tables: {e}")

    def create_project_milestone(self, project_name: str, milestone_name: str,
                                due_date: str, course_id: str = None,
                                student_id: str = None, description: str = None) -> Tuple[bool, str]:
        """Create a project milestone"""
        if not self.auth_manager.check_permission('manage_schedules'):
            raise PermissionError("Insufficient permissions to create milestones")

        try:
            if not ValidationUtils.validate_date(due_date):
                raise ValidationError("Invalid due date format")

            milestone_id = str(uuid.uuid4())

            with self.db_manager.transaction():
                self.db_manager.execute_update('''
                INSERT INTO project_milestones
                (id, project_name, milestone_name, due_date, course_id,
                 student_id, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (milestone_id, project_name, milestone_name, due_date,
                     course_id, student_id, description,
                     datetime.now().isoformat()))

            return True, f"Milestone created: {milestone_id}"

        except Exception as e:
            logger.error(f"Failed to create milestone: {e}")
            return False, f"Error creating milestone: {str(e)}"

    def update_milestone_progress(self, milestone_id: str,
                                completion_percentage: float,
                                status: str = None) -> Tuple[bool, str]:
        """Update milestone progress"""
        try:
            if not (0 <= completion_percentage <= 100):
                raise ValidationError("Completion percentage must be between 0 and 100")

            update_data = {
                'completion_percentage': completion_percentage,
                'last_updated': datetime.now().isoformat()
            }

            if status:
                update_data['status'] = status

            if completion_percentage >= 100 and not status:
                update_data['status'] = 'completed'

            # Build update query
            set_clauses = []
            params = []
            for field, value in update_data.items():
                set_clauses.append(f"{field} = ?")
                params.append(value)

            params.append(milestone_id)
            query = f"UPDATE project_milestones SET {', '.join(set_clauses)} WHERE id = ?"

            rows_affected = self.db_manager.execute_update(query, tuple(params))

            if rows_affected > 0:
                return True, "Milestone progress updated"
            else:
                return False, "Milestone not found"

        except Exception as e:
            logger.error(f"Failed to update milestone progress: {e}")
            return False, f"Error updating progress: {str(e)}"

    def track_graduation_requirements(self, student_id: str) -> Dict[str, Any]:
        """Track graduation requirements for a student"""
        try:
            # Get all requirements
            req_rows = self.db_manager.execute_query('''
            SELECT gr.*, srp.credits_completed, srp.completion_percentage,
                   srp.status, srp.completion_date
            FROM graduation_requirements gr
            LEFT JOIN student_requirement_progress srp ON
                gr.id = srp.requirement_id AND srp.student_id = ?
            ORDER BY gr.requirement_type, gr.requirement_name
            ''', (student_id,))

            requirements = []
            total_requirements = len(req_rows)
            completed_requirements = 0

            for row in req_rows:
                req_data = dict(row)
                if req_data['status'] == 'completed':
                    completed_requirements += 1
                requirements.append(req_data)

            # Calculate overall completion percentage
            overall_completion = (completed_requirements / total_requirements * 100) if total_requirements > 0 else 0

            return {
                'student_id': student_id,
                'total_requirements': total_requirements,
                'completed_requirements': completed_requirements,
                'overall_completion_percentage': round(overall_completion, 2),
                'requirements': requirements,
                'graduation_eligible': completed_requirements == total_requirements
            }

        except Exception as e:
            logger.error(f"Failed to track graduation requirements: {e}")
            return {'error': str(e)}
