"""
Academic Progress Dashboard Service

Provides visual degree tracking, GPA simulation, and early warning systems.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
from decimal import Decimal

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

class ProgressService:
    """Service for academic progress tracking and forecasting."""

    def __init__(self):
        """Initialize the Progress Service."""
        self._ensure_tables_exist()

    def _get_program_id(self, program_code: str) -> Optional[int]:
        """Get program_id from program_code."""
        with get_connection() as conn:
            result = conn.execute("""
                SELECT program_id FROM degree_programs
                WHERE program_code = ?
            """, (program_code,)).fetchone()
            return result['program_id'] if result else None

    def _get_program_code(self, program_id: int) -> Optional[str]:
        """Get program_code from program_id."""
        with get_connection() as conn:
            result = conn.execute("""
                SELECT program_code FROM degree_programs
                WHERE program_id = ?
            """, (program_id,)).fetchone()
            return result['program_code'] if result else None

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Note: Using existing degree_program_courses, modules, and module_grades tables
            # for course requirements instead of creating separate tables

            # Ensure degree_program_courses table exists (should already exist)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS degree_program_courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    program_code TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    requirement_type TEXT DEFAULT 'Core',
                    year_level INTEGER DEFAULT 1,
                    semester_offered TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(program_code, course_id)
                )
            """)

            # Student Degree Progress table - uses existing schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_degree_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    program_id INTEGER NOT NULL,
                    enrollment_year INTEGER NOT NULL,
                    total_credits_earned INTEGER DEFAULT 0,
                    current_gpa REAL DEFAULT 0.0,
                    completion_percentage REAL DEFAULT 0.0,
                    expected_graduation_date TEXT,
                    last_updated TEXT NOT NULL DEFAULT (datetime('now')),
                    FOREIGN KEY (program_id) REFERENCES degree_programs(program_id),
                    UNIQUE(student_id, program_id)
                )
            """)

            # Degree Milestones table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS degree_milestones (
                    milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    program_code TEXT NOT NULL,
                    milestone_name TEXT NOT NULL,
                    milestone_type TEXT NOT NULL,
                    required_credits INTEGER DEFAULT 0,
                    required_gpa REAL DEFAULT 0.0,
                    typical_semester INTEGER DEFAULT 1,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Student Milestone Progress table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_milestone_progress (
                    progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    milestone_id INTEGER NOT NULL,
                    achieved BOOLEAN DEFAULT 0,
                    achieved_date TEXT,
                    achieved_semester INTEGER,
                    notes TEXT,
                    FOREIGN KEY (milestone_id) REFERENCES degree_milestones(milestone_id),
                    UNIQUE(student_id, milestone_id)
                )
            """)

            # GPA Simulation History table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gpa_simulations (
                    simulation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    simulation_name TEXT NOT NULL,
                    current_gpa REAL NOT NULL,
                    simulated_courses_json TEXT NOT NULL,
                    projected_gpa REAL NOT NULL,
                    projection_type TEXT DEFAULT 'What-If',
                    credits_simulated INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Academic Warning System table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS academic_warnings (
                    warning_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    warning_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    warning_message TEXT NOT NULL,
                    trigger_metric TEXT,
                    trigger_value TEXT,
                    recommendations_json TEXT,
                    acknowledged BOOLEAN DEFAULT 0,
                    acknowledged_at TEXT,
                    resolved BOOLEAN DEFAULT 0,
                    resolved_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Early Alert Indicators table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS early_alert_indicators (
                    indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    indicator_type TEXT NOT NULL,
                    current_value REAL,
                    threshold_value REAL,
                    risk_level TEXT DEFAULT 'Low',
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    follow_up_date TEXT,
                    status TEXT DEFAULT 'Active',
                    notes TEXT
                )
            """)

            # Progress Snapshots table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS progress_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    overall_gpa REAL DEFAULT 0.0,
                    semester_gpa REAL DEFAULT 0.0,
                    total_credits INTEGER DEFAULT 0,
                    credits_this_semester INTEGER DEFAULT 0,
                    degree_completion_percentage REAL DEFAULT 0.0,
                    class_standing TEXT,
                    academic_status TEXT DEFAULT 'Good Standing',
                    warnings_count INTEGER DEFAULT 0,
                    snapshot_date TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Student Graduation Forecast table (renamed to avoid conflict with existing cohort table)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS student_graduation_forecasts (
                    forecast_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    program_code TEXT NOT NULL,
                    estimated_graduation_date TEXT,
                    estimated_semester TEXT,
                    remaining_credits INTEGER DEFAULT 0,
                    required_semesters INTEGER DEFAULT 0,
                    on_track BOOLEAN DEFAULT 1,
                    delay_reasons_json TEXT,
                    acceleration_options_json TEXT,
                    confidence_level REAL DEFAULT 0.0,
                    last_calculated TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(student_id)
                )
            """)

            # Course Grade Predictions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS grade_predictions (
                    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    current_grade REAL,
                    predicted_final_grade TEXT,
                    confidence_level REAL DEFAULT 0.0,
                    prediction_factors_json TEXT,
                    improvement_suggestions_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            log_activity('create', 'progress_tracking_tables',
                        details={'status': 'Progress tracking tables created'})

    # ========== Degree Progress Tracking ==========

    def get_available_programs(self) -> List[Dict]:
        """
        Get list of programs that have courses configured.

        Returns:
            List of program dictionaries with code, name, and course count
        """
        with get_connection() as conn:
            programs = conn.execute("""
                SELECT
                    dp.program_code,
                    dp.program_name,
                    dp.degree_type,
                    COUNT(DISTINCT dpc.course_id) as course_count,
                    SUM(CASE
                        WHEN COALESCE(m.credits, 0) > 0 THEN m.credits
                        WHEN COALESCE(c.credits, 0) > 0 THEN c.credits
                        WHEN COALESCE(c.credit_hours, 0) > 0 THEN c.credit_hours
                        ELSE 3
                    END) as total_credits
                FROM degree_programs dp
                INNER JOIN degree_program_courses dpc ON dp.program_code = dpc.program_code
                LEFT JOIN modules m ON dpc.course_id = m.module_code OR dpc.course_id = m.module_id
                LEFT JOIN courses c ON dpc.course_id = c.code OR dpc.course_id = c.id
                WHERE (m.module_code IS NOT NULL OR c.code IS NOT NULL)
                GROUP BY dp.program_id, dp.program_code, dp.program_name, dp.degree_type
                HAVING COUNT(DISTINCT dpc.course_id) > 0
                ORDER BY dp.program_code
            """).fetchall()

            return [dict(p) for p in programs]

    def calculate_degree_progress(self, student_id: str, program_code: str) -> Dict:
        """
        Calculate comprehensive degree completion progress.

        Args:
            student_id: Student's ID
            program_code: Program/major code

        Returns:
            Dictionary with detailed progress metrics

        Raises:
            ValueError: If program code doesn't exist or has no courses configured
        """
        # Validate program exists and has courses
        with get_connection() as conn:
            program_check = conn.execute("""
                SELECT
                    dp.program_id,
                    COUNT(DISTINCT dpc.course_id) as course_count
                FROM degree_programs dp
                LEFT JOIN degree_program_courses dpc ON dp.program_code = dpc.program_code
                LEFT JOIN modules m ON dpc.course_id = m.module_code OR dpc.course_id = m.module_id
                LEFT JOIN courses c ON dpc.course_id = c.code OR dpc.course_id = c.id
                WHERE dp.program_code = ?
                AND (m.module_code IS NOT NULL OR c.code IS NOT NULL OR dpc.course_id IS NULL)
                GROUP BY dp.program_id
            """, (program_code,)).fetchone()

            if not program_check:
                raise ValueError(f"Program '{program_code}' does not exist in the database")

            if program_check['course_count'] == 0:
                raise ValueError(f"Program '{program_code}' has no courses configured. Please add courses to this program first.")

            program_id = program_check['program_id']

        with get_connection() as conn:
            # Get all courses for the program from degree_program_courses
            # Only include courses that actually exist in modules or courses tables
            program_courses = conn.execute("""
                SELECT
                    dpc.course_id,
                    dpc.requirement_type,
                    CASE
                        WHEN COALESCE(m.credits, 0) > 0 THEN m.credits
                        WHEN COALESCE(c.credits, 0) > 0 THEN c.credits
                        WHEN COALESCE(c.credit_hours, 0) > 0 THEN c.credit_hours
                        ELSE 3
                    END as credits,
                    dpc.year_level,
                    dpc.semester_offered
                FROM degree_program_courses dpc
                LEFT JOIN modules m ON dpc.course_id = m.module_code OR dpc.course_id = m.module_id
                LEFT JOIN courses c ON dpc.course_id = c.code OR dpc.course_id = c.id
                WHERE dpc.program_code = ?
                AND (m.module_code IS NOT NULL OR c.code IS NOT NULL)
                ORDER BY dpc.requirement_type, dpc.year_level
            """, (program_code,)).fetchall()

            if not program_courses:
                # No courses found for this program - return empty progress
                # Don't create dummy courses
                pass

            # Get student's completed courses - only from actual modules
            completed_courses = conn.execute("""
                SELECT
                    mg.module_code as course_id,
                    CASE WHEN COALESCE(m.credits, 0) > 0 THEN m.credits ELSE 3 END as credits,
                    mg.final_grade as grade
                FROM module_grades mg
                INNER JOIN modules m ON mg.module_code = m.module_code
                WHERE mg.student_id = ?
                AND mg.final_grade IS NOT NULL
                AND mg.final_grade NOT IN ('F', 'W', 'I')
                UNION
                SELECT
                    sg.module_code as course_id,
                    CASE
                        WHEN COALESCE(c.credits, 0) > 0 THEN c.credits
                        WHEN COALESCE(c.credit_hours, 0) > 0 THEN c.credit_hours
                        ELSE 3
                    END as credits,
                    sg.grade
                FROM student_grades sg
                INNER JOIN courses c ON sg.module_code = c.code
                WHERE sg.student_id = ?
                AND sg.grade IS NOT NULL
                AND sg.grade NOT IN ('F', 'W', 'I')
                AND sg.assessment_name LIKE '%Final%'
            """, (student_id, student_id)).fetchall()

            # Get current enrollments - only from actual modules
            current_enrollments = conn.execute("""
                SELECT
                    mg.module_code as course_id,
                    CASE WHEN COALESCE(m.credits, 0) > 0 THEN m.credits ELSE 3 END as credits
                FROM module_grades mg
                INNER JOIN modules m ON mg.module_code = m.module_code
                WHERE mg.student_id = ?
                AND mg.final_grade IS NULL
            """, (student_id,)).fetchall()

            # Group courses by requirement type and calculate progress
            progress_by_category = {}
            total_required = 0
            total_completed = 0
            total_in_progress = 0

            if program_courses:
                # Create a dictionary of required courses by type
                courses_by_type = {}
                for course in program_courses:
                    req_type = course['requirement_type'] or 'Elective'
                    if req_type not in courses_by_type:
                        courses_by_type[req_type] = []
                    courses_by_type[req_type].append(dict(course))

                # Calculate progress for each requirement type
                for req_type, type_courses in courses_by_type.items():
                    # Calculate total required credits for this type
                    required_credits = sum(c['credits'] for c in type_courses)

                    # Calculate completed credits
                    completed_credits = 0
                    for completed in completed_courses:
                        if any(c['course_id'] == completed['course_id'] for c in type_courses):
                            completed_credits += completed['credits']

                    # Calculate in-progress credits
                    in_progress_credits = 0
                    for enrolled in current_enrollments:
                        if any(c['course_id'] == enrolled['course_id'] for c in type_courses):
                            in_progress_credits += enrolled['credits']

                    remaining = max(0, required_credits - completed_credits - in_progress_credits)
                    completion_pct = min(100, (completed_credits / required_credits * 100) if required_credits > 0 else 100)

                    progress_by_category[req_type] = {
                        'required': required_credits,
                        'completed': completed_credits,
                        'in_progress': in_progress_credits,
                        'remaining': remaining,
                        'completion_percentage': round(completion_pct, 1)
                    }

                    total_required += required_credits
                    total_completed += completed_credits
                    total_in_progress += in_progress_credits
            else:
                # No program courses defined - show only student's actual completed courses
                for completed in completed_courses:
                    total_completed += completed['credits']
                for enrolled in current_enrollments:
                    total_in_progress += enrolled['credits']

            # Calculate overall progress
            overall_completion = (total_completed / total_required * 100) if total_required > 0 else 0

            progress_data = {
                'student_id': student_id,
                'program_code': program_code,
                'overall_completion': round(overall_completion, 1),
                'total_credits_required': total_required,
                'total_credits_completed': total_completed,
                'total_credits_in_progress': total_in_progress,
                'total_credits_remaining': total_required - total_completed - total_in_progress,
                'by_category': progress_by_category,
                'last_updated': datetime.now().isoformat()
            }

            # Update progress records
            self._update_progress_records(student_id, program_id, total_completed, overall_completion)

            log_activity('view', 'degree_progress', details={
                'student_id': student_id,
                'completion': overall_completion
            })

            return progress_data

    def get_available_modules(self, search_term: str = None, limit: int = 100) -> List[Dict]:
        """
        Get list of available modules/courses from the database.

        Args:
            search_term: Optional search term to filter by code or name
            limit: Maximum number of results to return

        Returns:
            List of module dictionaries with code, name, and credits
        """
        with get_connection() as conn:
            if search_term:
                modules = conn.execute("""
                    SELECT module_code as code, module_name as name, credits
                    FROM modules
                    WHERE module_code LIKE ? OR module_name LIKE ?
                    AND is_active = 1
                    ORDER BY module_code
                    LIMIT ?
                """, (f'%{search_term}%', f'%{search_term}%', limit)).fetchall()
            else:
                modules = conn.execute("""
                    SELECT module_code as code, module_name as name, credits
                    FROM modules
                    WHERE is_active = 1
                    ORDER BY module_code
                    LIMIT ?
                """, (limit,)).fetchall()

            return [dict(m) for m in modules]

    def get_program_courses(self, program_code: str) -> List[Dict]:
        """
        Get all courses currently in a program's curriculum.

        Args:
            program_code: The program code

        Returns:
            List of course dictionaries with details
        """
        with get_connection() as conn:
            courses = conn.execute("""
                SELECT
                    dpc.course_id,
                    dpc.requirement_type,
                    COALESCE(m.module_name, c.name, c.course_name) as course_name,
                    CASE
                        WHEN COALESCE(m.credits, 0) > 0 THEN m.credits
                        WHEN COALESCE(c.credits, 0) > 0 THEN c.credits
                        WHEN COALESCE(c.credit_hours, 0) > 0 THEN c.credit_hours
                        ELSE 3
                    END as credits,
                    dpc.year_level,
                    dpc.semester_offered
                FROM degree_program_courses dpc
                LEFT JOIN modules m ON dpc.course_id = m.module_code OR dpc.course_id = m.module_id
                LEFT JOIN courses c ON dpc.course_id = c.code OR dpc.course_id = c.id
                WHERE dpc.program_code = ?
                AND (m.module_code IS NOT NULL OR c.code IS NOT NULL)
                ORDER BY dpc.requirement_type, dpc.year_level, dpc.course_id
            """, (program_code,)).fetchall()

            return [dict(c) for c in courses]

    def add_course_to_program(self, program_code: str, course_id: str,
                             requirement_type: str = 'Core', year_level: int = 1,
                             semester_offered: str = None) -> bool:
        """
        Add an existing course/module to a program's curriculum.
        Only allows courses that exist in modules or courses tables.

        Args:
            program_code: The program code
            course_id: The module/course code (must exist in database)
            requirement_type: Type of requirement (Core, Elective, etc.)
            year_level: Year level (1-4)
            semester_offered: Semester when offered (Fall, Spring, etc.)

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If the course/module does not exist in the database
        """
        with get_connection() as conn:
            # Verify the course exists in the database
            course_exists = conn.execute("""
                SELECT 1 FROM modules WHERE module_code = ? OR module_id = ?
                UNION
                SELECT 1 FROM courses WHERE code = ? OR id = ?
                LIMIT 1
            """, (course_id, course_id, course_id, course_id)).fetchone()

            if not course_exists:
                raise ValueError(f"Course/Module '{course_id}' does not exist in the database")

        try:
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO degree_program_courses
                    (program_code, course_id, requirement_type, year_level, semester_offered)
                    VALUES (?, ?, ?, ?, ?)
                """, (program_code, course_id, requirement_type, year_level, semester_offered))
                return True
        except sqlite3.IntegrityError:
            # Course already in program
            return False

    def remove_course_from_program(self, program_code: str, course_id: str) -> bool:
        """
        Remove a course from a program's curriculum.

        Args:
            program_code: The program code
            course_id: The module/course code to remove

        Returns:
            True if removed, False if not found
        """
        with transaction() as conn:
            cursor = conn.execute("""
                DELETE FROM degree_program_courses
                WHERE program_code = ? AND course_id = ?
            """, (program_code, course_id))
            return cursor.rowcount > 0

    def _update_progress_records(self, student_id: str, program_id: int,
                                 total_completed: int, completion_pct: float):
        """Update student progress records in database."""
        if not program_id:
            return

        # Get current year for enrollment_year
        current_year = datetime.now().year

        with transaction() as conn:
            # Update the overall student progress in the existing schema
            conn.execute("""
                INSERT INTO student_degree_progress
                (student_id, program_id, enrollment_year, total_credits_earned,
                 completion_percentage, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(student_id, program_id) DO UPDATE SET
                    total_credits_earned = excluded.total_credits_earned,
                    completion_percentage = excluded.completion_percentage,
                    last_updated = excluded.last_updated
            """, (student_id, program_id, current_year, total_completed,
                  round(completion_pct, 1), datetime.now().isoformat()))

    def get_degree_visualization_data(self, student_id: str, program_code: str) -> Dict:
        """Get formatted data for degree progress visualization."""
        progress = self.calculate_degree_progress(student_id, program_code)

        # Format for visualization (pie chart, progress bars, etc.)
        visualization_data = {
            'overall_progress': progress['overall_completion'],
            'categories': [
                {
                    'name': category,
                    'completed': data['completed'],
                    'in_progress': data['in_progress'],
                    'remaining': data['remaining'],
                    'percentage': data['completion_percentage'],
                    'color': self._get_category_color(category)
                }
                for category, data in progress['by_category'].items()
            ],
            'summary': {
                'total_required': progress['total_credits_required'],
                'total_completed': progress['total_credits_completed'],
                'total_in_progress': progress['total_credits_in_progress'],
                'total_remaining': progress['total_credits_remaining']
            }
        }

        return visualization_data

    def _get_category_color(self, category: str) -> str:
        """Get color code for category visualization."""
        colors = {
            'General Education': '#3498db',
            'Major Core': '#e74c3c',
            'Major Electives': '#f39c12',
            'Free Electives': '#2ecc71',
            'Minor': '#9b59b6'
        }
        return colors.get(category, '#95a5a6')

    # ========== Milestone Tracking ==========

    def track_milestones(self, student_id: str, program_code: str) -> Dict:
        """Track student progress toward degree milestones."""
        with get_connection() as conn:
            # Get program milestones
            milestones = conn.execute("""
                SELECT * FROM degree_milestones
                WHERE program_code = ?
                ORDER BY typical_semester
            """, (program_code,)).fetchall()

            if not milestones:
                # Create default milestones
                self._create_default_milestones(program_code)
                milestones = conn.execute("""
                    SELECT * FROM degree_milestones
                    WHERE program_code = ?
                    ORDER BY typical_semester
                """, (program_code,)).fetchall()

            # Get student's current stats
            student_stats = self._get_student_stats(student_id)

            milestone_progress = []
            for milestone in milestones:
                milestone_dict = dict(milestone)

                # Check if milestone is achieved
                achieved = self._check_milestone_achievement(milestone_dict, student_stats)

                # Get student progress record
                progress = conn.execute("""
                    SELECT * FROM student_milestone_progress
                    WHERE student_id = ? AND milestone_id = ?
                """, (student_id, milestone_dict['milestone_id'])).fetchone()

                milestone_progress.append({
                    'milestone': milestone_dict,
                    'achieved': achieved,
                    'progress_record': dict(progress) if progress else None
                })

            return {
                'student_id': student_id,
                'program_code': program_code,
                'milestones': milestone_progress,
                'student_stats': student_stats
            }

    def _create_default_milestones(self, program_code: str):
        """Create default degree milestones."""
        default_milestones = [
            {
                'name': 'Freshman Year Complete',
                'type': 'Academic',
                'credits': 30,
                'gpa': 2.0,
                'semester': 2
            },
            {
                'name': 'Sophomore Standing',
                'type': 'Academic',
                'credits': 60,
                'gpa': 2.0,
                'semester': 4
            },
            {
                'name': 'Junior Standing',
                'type': 'Academic',
                'credits': 90,
                'gpa': 2.0,
                'semester': 6
            },
            {
                'name': 'Senior Standing',
                'type': 'Academic',
                'credits': 120,
                'gpa': 2.0,
                'semester': 8
            },
            {
                'name': 'Degree Completion',
                'type': 'Graduation',
                'credits': 120,
                'gpa': 2.0,
                'semester': 8
            }
        ]

        with transaction() as conn:
            for milestone in default_milestones:
                conn.execute("""
                    INSERT INTO degree_milestones
                    (program_code, milestone_name, milestone_type,
                     required_credits, required_gpa, typical_semester)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (program_code, milestone['name'], milestone['type'],
                      milestone['credits'], milestone['gpa'], milestone['semester']))

    def _get_student_stats(self, student_id: str) -> Dict:
        """Get current student statistics."""
        with get_connection() as conn:
            # Calculate GPA and credits
            grades = conn.execute("""
                SELECT mg.final_grade as grade, m.credits
                FROM module_grades mg
                LEFT JOIN modules m ON mg.module_code = m.module_code
                WHERE mg.student_id = ?
                AND mg.final_grade NOT IN ('W', 'I')
                AND mg.final_grade IS NOT NULL
                UNION
                SELECT sg.grade, c.credits
                FROM student_grades sg
                LEFT JOIN courses c ON sg.module_code = c.code
                WHERE sg.student_id = ?
                AND sg.grade NOT IN ('W', 'I')
                AND sg.grade IS NOT NULL
                AND sg.assessment_name LIKE '%Final%'
            """, (student_id, student_id)).fetchall()

            total_credits = 0
            total_points = 0
            grade_values = {
                'A+': 4.0, 'A': 4.0, 'A-': 3.7,
                'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                'C+': 2.3, 'C': 2.0, 'C-': 1.7,
                'D+': 1.3, 'D': 1.0, 'F': 0.0
            }

            for grade in grades:
                if grade['grade'] in grade_values:
                    total_credits += grade['credits']
                    total_points += grade_values[grade['grade']] * grade['credits']

            gpa = total_points / total_credits if total_credits > 0 else 0.0

            return {
                'total_credits': total_credits,
                'gpa': round(gpa, 2)
            }

    def _check_milestone_achievement(self, milestone: Dict, student_stats: Dict) -> bool:
        """Check if a milestone has been achieved."""
        credits_met = student_stats['total_credits'] >= milestone['required_credits']
        gpa_met = student_stats['gpa'] >= milestone['required_gpa']
        return credits_met and gpa_met

    # ========== What-If GPA Calculator ==========

    def calculate_what_if_gpa(self, student_id: str, simulation_name: str,
                             simulated_courses: List[Dict]) -> Dict:
        """
        Calculate what-if GPA scenario with hypothetical grades.

        Args:
            student_id: Student's ID
            simulation_name: Name for this simulation
            simulated_courses: List of dicts with 'course_id', 'credits', 'expected_grade'

        Returns:
            Dictionary with current GPA, projected GPA, and impact analysis
        """
        with get_connection() as conn:
            # Get current GPA and credits
            current_stats = self._calculate_current_gpa(student_id)

            # Calculate projected GPA with simulated courses
            grade_values = {
                'A+': 4.0, 'A': 4.0, 'A-': 3.7,
                'B+': 3.3, 'B': 3.0, 'B-': 2.7,
                'C+': 2.3, 'C': 2.0, 'C-': 1.7,
                'D+': 1.3, 'D': 1.0, 'F': 0.0
            }

            total_points = current_stats['total_points']
            total_credits = current_stats['total_credits']

            # Add simulated courses
            simulated_credits = 0
            for course in simulated_courses:
                credits = course['credits']
                grade = course['expected_grade']

                if grade in grade_values:
                    total_points += grade_values[grade] * credits
                    total_credits += credits
                    simulated_credits += credits

            projected_gpa = total_points / total_credits if total_credits > 0 else 0.0
            gpa_change = projected_gpa - current_stats['current_gpa']

            # Save simulation
            with transaction() as conn:
                cursor = conn.execute("""
                    INSERT INTO gpa_simulations
                    (student_id, simulation_name, current_gpa, simulated_courses_json,
                     projected_gpa, credits_simulated)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student_id, simulation_name, current_stats['current_gpa'],
                      json.dumps(simulated_courses), projected_gpa, simulated_credits))

                simulation_id = cursor.lastrowid

            result = {
                'simulation_id': simulation_id,
                'simulation_name': simulation_name,
                'current_gpa': round(current_stats['current_gpa'], 3),
                'projected_gpa': round(projected_gpa, 3),
                'gpa_change': round(gpa_change, 3),
                'credits_simulated': simulated_credits,
                'total_credits_after': total_credits,
                'simulated_courses': simulated_courses,
                'impact_analysis': self._analyze_gpa_impact(gpa_change)
            }

            log_activity('create', 'gpa_simulation',
                        details={'simulation_id': simulation_id, 'student_id': student_id, 'projected_gpa': projected_gpa})

            return result

    def _calculate_current_gpa(self, student_id: str) -> Dict:
        """Calculate student's current GPA and total points."""
        grade_values = {
            'A+': 4.0, 'A': 4.0, 'A-': 3.7,
            'B+': 3.3, 'B': 3.0, 'B-': 2.7,
            'C+': 2.3, 'C': 2.0, 'C-': 1.7,
            'D+': 1.3, 'D': 1.0, 'D-': 0.7, 'F': 0.0
        }

        def pct_to_letter(pct):
            if pct >= 93: return 'A'
            if pct >= 90: return 'A-'
            if pct >= 87: return 'B+'
            if pct >= 83: return 'B'
            if pct >= 80: return 'B-'
            if pct >= 77: return 'C+'
            if pct >= 73: return 'C'
            if pct >= 70: return 'C-'
            if pct >= 67: return 'D+'
            if pct >= 63: return 'D'
            if pct >= 60: return 'D-'
            return 'F'

        with get_connection() as conn:
            # Source 1: module_grades (letter grades)
            module_rows = conn.execute("""
                SELECT mg.module_code, mg.final_grade as grade, COALESCE(m.credits, 1) as credits
                FROM module_grades mg
                LEFT JOIN modules m ON mg.module_code = m.module_code
                WHERE mg.student_id = ?
                AND mg.final_grade NOT IN ('W', 'I')
                AND mg.final_grade IS NOT NULL
            """, (student_id,)).fetchall()

            # Source 2: assignment_submissions (percentage grades, averaged per module)
            assign_rows = conn.execute("""
                SELECT a.module_code, ROUND(AVG(sub.grade), 2) as avg_pct,
                       COALESCE(m.credits, 1) as credits
                FROM assignment_submissions sub
                JOIN assignments a ON sub.assignment_id = a.id
                LEFT JOIN modules m ON a.module_code = m.module_code
                WHERE sub.student_id = ? AND sub.grade IS NOT NULL
                GROUP BY a.module_code
            """, (student_id,)).fetchall()

            # Source 3: grades table (score-based)
            grade_rows = conn.execute("""
                SELECT a.module_code,
                       ROUND(AVG(g.score / a.max_points * 100), 2) as avg_pct,
                       COALESCE(m.credits, 1) as credits
                FROM grades g
                JOIN assessments a ON g.assessment_id = a.assessment_id
                LEFT JOIN modules m ON a.module_code = m.module_code
                WHERE g.student_id = ? AND a.max_points > 0
                GROUP BY a.module_code
            """, (student_id,)).fetchall()

        # Merge: module_grades takes priority
        seen = set()
        total_credits = 0
        total_points = 0.0

        for row in module_rows:
            code = row['module_code']
            if code in seen:
                continue
            seen.add(code)
            grade_str = str(row['grade']).strip()
            # Handle numeric grades stored as strings
            try:
                pct = float(grade_str)
                letter = pct_to_letter(pct)
            except (ValueError, TypeError):
                letter = grade_str

            if letter in grade_values:
                cr = row['credits'] or 1
                total_credits += cr
                total_points += grade_values[letter] * cr

        for row in list(assign_rows) + list(grade_rows):
            code = row['module_code']
            if code in seen:
                continue
            seen.add(code)
            pct = row['avg_pct']
            if pct is not None:
                letter = pct_to_letter(pct)
                if letter in grade_values:
                    cr = row['credits'] or 1
                    total_credits += cr
                    total_points += grade_values[letter] * cr

        current_gpa = total_points / total_credits if total_credits > 0 else 0.0

        return {
            'current_gpa': current_gpa,
            'total_credits': total_credits,
            'total_points': total_points
        }

    def _analyze_gpa_impact(self, gpa_change: float) -> str:
        """Analyze and describe the impact of GPA change."""
        if gpa_change >= 0.5:
            return "Significant positive impact - Excellent improvement!"
        elif gpa_change >= 0.2:
            return "Moderate positive impact - Good progress"
        elif gpa_change > 0:
            return "Slight positive impact - Small improvement"
        elif gpa_change == 0:
            return "Neutral impact - GPA remains unchanged"
        elif gpa_change > -0.2:
            return "Slight negative impact - Minor decline"
        elif gpa_change > -0.5:
            return "Moderate negative impact - Concerning trend"
        else:
            return "Significant negative impact - Requires immediate attention"

    def get_simulation_history(self, student_id: str) -> List[Dict]:
        """Get all GPA simulations for a student."""
        with get_connection() as conn:
            simulations = conn.execute("""
                SELECT * FROM gpa_simulations
                WHERE student_id = ?
                ORDER BY created_at DESC
                LIMIT 20
            """, (student_id,)).fetchall()

            return [dict(sim) for sim in simulations]

    def calculate_target_gpa_requirements(self, student_id: str,
                                         target_gpa: float,
                                         credits_to_take: int) -> Dict:
        """
        Calculate what average grade is needed to reach a target GPA.

        Args:
            student_id: Student's ID
            target_gpa: Desired GPA
            credits_to_take: Number of credits planning to take

        Returns:
            Required average grade and feasibility analysis
        """
        current_stats = self._calculate_current_gpa(student_id)

        # Calculate required grade points
        total_credits_after = current_stats['total_credits'] + credits_to_take
        total_points_needed = target_gpa * total_credits_after
        points_needed = total_points_needed - current_stats['total_points']
        required_avg_grade = points_needed / credits_to_take if credits_to_take > 0 else 0

        # Determine feasibility
        if required_avg_grade > 4.0:
            feasibility = "Impossible - Target GPA cannot be reached with given credits"
            required_grade_letter = "Above A+"
        elif required_avg_grade >= 3.85:
            feasibility = "Very Difficult - Requires near-perfect grades (A/A+)"
            required_grade_letter = "A/A+"
        elif required_avg_grade >= 3.5:
            feasibility = "Challenging - Requires mostly A grades"
            required_grade_letter = "A-/A"
        elif required_avg_grade >= 3.0:
            feasibility = "Achievable - Requires mostly B grades"
            required_grade_letter = "B/B+"
        elif required_avg_grade >= 2.5:
            feasibility = "Easily Achievable - Requires B-/C+ average"
            required_grade_letter = "B-/C+"
        else:
            feasibility = "Very Achievable - Modest grades sufficient"
            required_grade_letter = "C or better"

        return {
            'current_gpa': round(current_stats['current_gpa'], 3),
            'target_gpa': target_gpa,
            'current_credits': current_stats['total_credits'],
            'credits_to_take': credits_to_take,
            'required_average_grade': round(required_avg_grade, 2),
            'required_grade_letter': required_grade_letter,
            'feasibility': feasibility,
            'achievable': required_avg_grade <= 4.0
        }

    # ========== Early Warning System ==========

    def check_early_warnings(self, student_id: str) -> List[Dict]:
        """
        Check for early warning indicators and generate alerts.

        Args:
            student_id: Student's ID

        Returns:
            List of active warnings
        """
        warnings = []

        with get_connection() as conn:
            # Check GPA warnings
            gpa_stats = self._calculate_current_gpa(student_id)
            if gpa_stats['current_gpa'] < 2.0:
                warnings.append({
                    'type': 'Low GPA',
                    'severity': 'High',
                    'message': f"Your GPA ({gpa_stats['current_gpa']:.2f}) is below 2.0. Academic probation risk.",
                    'metric': 'GPA',
                    'value': gpa_stats['current_gpa'],
                    'recommendations': [
                        'Schedule meeting with academic advisor',
                        'Consider tutoring services',
                        'Review study strategies',
                        'Reduce course load if necessary'
                    ]
                })
            elif gpa_stats['current_gpa'] < 2.5:
                warnings.append({
                    'type': 'GPA Warning',
                    'severity': 'Medium',
                    'message': f"Your GPA ({gpa_stats['current_gpa']:.2f}) is below 2.5. Consider improvement strategies.",
                    'metric': 'GPA',
                    'value': gpa_stats['current_gpa'],
                    'recommendations': [
                        'Meet with academic advisor',
                        'Utilize study groups',
                        'Visit office hours regularly'
                    ]
                })

            # Check attendance warnings
            attendance_issues = conn.execute("""
                SELECT module_code, COUNT(*) as absences
                FROM attendance
                WHERE student_id = ? AND status = 'Absent'
                AND date >= date('now', '-30 days')
                GROUP BY module_code
                HAVING absences >= 3
            """, (student_id,)).fetchall()

            for issue in attendance_issues:
                warnings.append({
                    'type': 'Attendance Warning',
                    'severity': 'Medium',
                    'message': f"High absences in {issue['module_code']} ({issue['absences']} in last 30 days)",
                    'metric': 'Attendance',
                    'value': issue['absences'],
                    'recommendations': [
                        'Speak with instructor about absences',
                        'Review attendance policy',
                        'Catch up on missed material'
                    ]
                })

            # Check assignment completion rate
            # Get student's enrolled modules
            student_modules = conn.execute("""
                SELECT DISTINCT module_code FROM module_grades
                WHERE student_id = ?
            """, (student_id,)).fetchall()

            if student_modules:
                module_codes = tuple(m['module_code'] for m in student_modules)
                placeholders = ','.join('?' * len(module_codes))

                assignment_stats = conn.execute(
                    "SELECT"
                    "    COUNT(DISTINCT a.id) as total_assignments,"
                    "    COUNT(DISTINCT CASE WHEN asub.status IS NOT NULL THEN a.id END) as submitted,"
                    "    COUNT(DISTINCT CASE WHEN asub.late_submission = 1 THEN a.id END) as late"
                    " FROM assignments a"
                    " LEFT JOIN assignment_submissions asub"
                    "    ON a.id = asub.assignment_id AND asub.student_id = ?"
                    " WHERE a.module_code IN (" + placeholders + ")"
                    " AND a.due_date >= date('now', '-60 days')"
                    " AND a.is_active = 1",
                    (student_id, *module_codes)).fetchone()

                if assignment_stats and assignment_stats['total_assignments'] > 0:
                    completion_rate = assignment_stats['submitted'] / assignment_stats['total_assignments']
                    if completion_rate < 0.7:
                        warnings.append({
                            'type': 'Low Assignment Completion',
                            'severity': 'High',
                            'message': f"Only {completion_rate*100:.0f}% of assignments submitted in last 60 days",
                            'metric': 'Completion Rate',
                            'value': completion_rate,
                            'recommendations': [
                                'Use planner to track deadlines',
                                'Break assignments into smaller tasks',
                                'Seek help from instructor or TA',
                                'Visit writing center for papers'
                            ]
                        })

            # Check current course grades
            low_grades = conn.execute("""
                SELECT module_code as course_id, final_grade as grade
                FROM module_grades
                WHERE student_id = ?
                AND final_grade IN ('D', 'F')
            """, (student_id,)).fetchall()

            for grade in low_grades:
                warnings.append({
                    'type': 'Failing Grade',
                    'severity': 'High',
                    'message': f"Currently failing or at risk in {grade['course_id']}",
                    'metric': 'Grade',
                    'value': grade['grade'],
                    'recommendations': [
                        'Meet with instructor immediately',
                        'Develop grade recovery plan',
                        'Consider dropping if past deadline',
                        'Increase study time for this course'
                    ]
                })

            # Clear stale warnings that no longer apply, then save new ones
            self._refresh_warning_records(student_id, warnings)

            log_activity('view', 'early_warnings', details={
                'student_id': student_id,
                'warnings_count': len(warnings)
            })

            return warnings

    def _create_warning_record(self, student_id: str, warning: Dict):
        """Create a warning record in the database."""
        with transaction() as conn:
            # Check if similar warning exists
            existing = conn.execute("""
                SELECT warning_id FROM academic_warnings
                WHERE student_id = ? AND warning_type = ?
                AND resolved = 0
                AND created_at >= date('now', '-7 days')
            """, (student_id, warning['type'])).fetchone()

            if not existing:
                conn.execute("""
                    INSERT INTO academic_warnings
                    (student_id, warning_type, severity, warning_message,
                     trigger_metric, trigger_value, recommendations_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (student_id, warning['type'], warning['severity'],
                      warning['message'], warning['metric'],
                      str(warning['value']), json.dumps(warning.get('recommendations', []))))

    def _refresh_warning_records(self, student_id: str, current_warnings: list):
        """Clear stale warnings and save/update current ones."""
        current_types = {w['type'] for w in current_warnings}

        with transaction() as conn:
            # Resolve old warnings whose type is no longer triggered
            conn.execute("""
                UPDATE academic_warnings
                SET resolved = 1, resolved_at = CURRENT_TIMESTAMP,
                    resolution_notes = 'Auto-resolved: condition no longer met'
                WHERE student_id = ? AND resolved = 0
                AND warning_type NOT IN ({})
            """.format(','.join('?' * len(current_types)) if current_types else "'__none__'"),
                (student_id, *current_types) if current_types else (student_id,))

            # Update existing warnings with fresh data, or create new ones
            for warning in current_warnings:
                existing = conn.execute("""
                    SELECT warning_id FROM academic_warnings
                    WHERE student_id = ? AND warning_type = ? AND resolved = 0
                """, (student_id, warning['type'])).fetchone()

                if existing:
                    # Update the message and value in case they changed
                    conn.execute("""
                        UPDATE academic_warnings
                        SET warning_message = ?, trigger_value = ?,
                            severity = ?, recommendations_json = ?
                        WHERE warning_id = ?
                    """, (warning['message'], str(warning['value']),
                          warning['severity'],
                          json.dumps(warning.get('recommendations', [])),
                          existing['warning_id']))
                else:
                    conn.execute("""
                        INSERT INTO academic_warnings
                        (student_id, warning_type, severity, warning_message,
                         trigger_metric, trigger_value, recommendations_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (student_id, warning['type'], warning['severity'],
                          warning['message'], warning['metric'],
                          str(warning['value']),
                          json.dumps(warning.get('recommendations', []))))

    def get_active_warnings(self, student_id: str) -> List[Dict]:
        """Get all active warnings for a student."""
        with get_connection() as conn:
            warnings = conn.execute("""
                SELECT * FROM academic_warnings
                WHERE student_id = ?
                AND resolved = 0
                ORDER BY severity DESC, created_at DESC
            """, (student_id,)).fetchall()

            return [dict(w) for w in warnings]

    def acknowledge_warning(self, warning_id: int) -> bool:
        """Mark a warning as acknowledged."""
        with transaction() as conn:
            conn.execute("""
                UPDATE academic_warnings
                SET acknowledged = 1, acknowledged_at = ?
                WHERE warning_id = ?
            """, (datetime.now().isoformat(), warning_id))

            log_activity('update', 'academic_warning',
                        details={'warning_id': warning_id, 'acknowledged': True})
            return True

    def resolve_warning(self, warning_id: int, notes: Optional[str] = None) -> bool:
        """Mark a warning as resolved."""
        with transaction() as conn:
            conn.execute("""
                UPDATE academic_warnings
                SET resolved = 1, resolved_at = ?
                WHERE warning_id = ?
            """, (datetime.now().isoformat(), warning_id))

            log_activity('update', 'academic_warning',
                        details={'warning_id': warning_id, 'resolved': True, 'notes': notes})
            return True

    # ========== Graduation Forecast ==========

    def forecast_graduation(self, student_id: str, program_code: str) -> Dict:
        """
        Forecast graduation timeline and identify potential delays.

        Args:
            student_id: Student's ID
            program_code: Program/major code

        Returns:
            Graduation forecast with timeline and recommendations
        """
        with get_connection() as conn:
            # Calculate degree progress
            progress = self.calculate_degree_progress(student_id, program_code)

            # Get student's enrollment history to determine pace
            # Since there's no semester column, we'll estimate based on completion dates
            enrollment_history = conn.execute("""
                SELECT
                    strftime('%Y-%m', completion_date) as period,
                    COUNT(DISTINCT module_code) as courses_per_period
                FROM module_grades
                WHERE student_id = ?
                AND final_grade IS NOT NULL
                AND completion_date IS NOT NULL
                GROUP BY strftime('%Y-%m', completion_date)
                ORDER BY completion_date DESC
                LIMIT 4
            """, (student_id,)).fetchall()

            # Calculate average credits per semester
            avg_credits_per_semester = 15  # Default
            if enrollment_history:
                total_courses = sum(row['courses_per_period'] for row in enrollment_history)
                avg_credits_per_semester = (total_courses / len(enrollment_history)) * 3
            else:
                # If no completion dates, estimate from total completed courses
                total_courses = conn.execute("""
                    SELECT COUNT(DISTINCT module_code)
                    FROM module_grades
                    WHERE student_id = ? AND final_grade IS NOT NULL
                """, (student_id,)).fetchone()[0]
                # Assume student has been enrolled for at least 2 semesters if they have courses
                if total_courses > 0:
                    avg_credits_per_semester = max(12, (total_courses * 3) / 2)

            remaining_credits = progress['total_credits_remaining']
            semesters_needed = int(remaining_credits / avg_credits_per_semester) + 1

            # Estimate graduation date
            estimated_date = datetime.now() + timedelta(days=semesters_needed * 120)
            estimated_semester = f"{'Spring' if estimated_date.month <= 6 else 'Fall'} {estimated_date.year}"

            # Check if on track (typical is 4 years = 8 semesters)
            on_track = semesters_needed <= 4

            # Identify potential delays
            delay_reasons = []
            if not on_track:
                if avg_credits_per_semester < 15:
                    delay_reasons.append("Low credit load per semester")
                if progress['overall_completion'] < 25 * (semesters_needed / 8):
                    delay_reasons.append("Behind expected progress")

            # Suggest acceleration options
            acceleration_options = []
            if semesters_needed > 2:
                acceleration_options.append({
                    'option': 'Summer courses',
                    'impact': 'Reduce by 1 semester',
                    'credits': '6-9 credits per summer'
                })
                acceleration_options.append({
                    'option': 'Increased course load',
                    'impact': f'Reduce by {int(semesters_needed * 0.25)} semester(s)',
                    'credits': '18 credits per semester'
                })
                if remaining_credits <= 30:
                    acceleration_options.append({
                        'option': 'Winter session',
                        'impact': 'Reduce by 0.5 semester',
                        'credits': '3-6 credits'
                    })

            forecast_data = {
                'student_id': student_id,
                'program_code': program_code,
                'estimated_graduation_date': estimated_date.strftime('%Y-%m-%d'),
                'estimated_semester': estimated_semester,
                'remaining_credits': remaining_credits,
                'semesters_needed': semesters_needed,
                'avg_credits_per_semester': round(avg_credits_per_semester, 1),
                'on_track': on_track,
                'delay_reasons': delay_reasons,
                'acceleration_options': acceleration_options,
                'confidence_level': 0.8 if len(enrollment_history) >= 3 else 0.6
            }

            # Save forecast
            with transaction() as conn:
                conn.execute("""
                    INSERT INTO student_graduation_forecasts
                    (student_id, program_code, estimated_graduation_date,
                     estimated_semester, remaining_credits, required_semesters,
                     on_track, delay_reasons_json, acceleration_options_json, confidence_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(student_id) DO UPDATE SET
                        estimated_graduation_date = excluded.estimated_graduation_date,
                        estimated_semester = excluded.estimated_semester,
                        remaining_credits = excluded.remaining_credits,
                        required_semesters = excluded.required_semesters,
                        on_track = excluded.on_track,
                        delay_reasons_json = excluded.delay_reasons_json,
                        acceleration_options_json = excluded.acceleration_options_json,
                        confidence_level = excluded.confidence_level,
                        last_calculated = CURRENT_TIMESTAMP
                """, (student_id, program_code, forecast_data['estimated_graduation_date'],
                      forecast_data['estimated_semester'], remaining_credits, semesters_needed,
                      on_track, json.dumps(delay_reasons), json.dumps(acceleration_options),
                      forecast_data['confidence_level']))

            log_activity('view', 'graduation_forecast', details={
                'student_id': student_id,
                'estimated_date': estimated_semester
            })

            return forecast_data

    # ========== Progress Snapshots ==========

    def create_progress_snapshot(self, student_id: str, semester: str) -> int:
        """Create a snapshot of student's academic progress."""
        with transaction() as conn:
            # Calculate current stats
            gpa_stats = self._calculate_current_gpa(student_id)

            # Get semester GPA
            # Since there's no semester column, calculate based on most recent courses
            # The semester parameter is just a label for the snapshot
            semester_grades = conn.execute("""
                SELECT mg.final_grade as grade, m.credits
                FROM module_grades mg
                LEFT JOIN modules m ON mg.module_code = m.module_code
                WHERE mg.student_id = ?
                AND mg.final_grade IS NOT NULL
                AND mg.completion_date IS NOT NULL
                ORDER BY mg.completion_date DESC
                LIMIT 6
            """, (student_id,)).fetchall()

            semester_gpa = self._calculate_semester_gpa(semester_grades)

            # Determine class standing
            class_standing = self._determine_class_standing(gpa_stats['total_credits'])

            # Get warnings count
            warnings_count = conn.execute("""
                SELECT COUNT(*) as count FROM academic_warnings
                WHERE student_id = ? AND resolved = 0
            """, (student_id,)).fetchone()['count']

            # Determine academic status
            academic_status = 'Good Standing'
            if gpa_stats['current_gpa'] < 2.0:
                academic_status = 'Academic Probation'
            elif warnings_count >= 3:
                academic_status = 'At Risk'

            cursor = conn.execute("""
                INSERT INTO progress_snapshots
                (student_id, semester, overall_gpa, semester_gpa, total_credits,
                 class_standing, academic_status, warnings_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, semester, gpa_stats['current_gpa'], semester_gpa,
                  gpa_stats['total_credits'], class_standing, academic_status,
                  warnings_count))

            snapshot_id = cursor.lastrowid

            log_activity('create', 'progress_snapshot',
                        details={'snapshot_id': snapshot_id, 'student_id': student_id, 'semester': semester})

            return snapshot_id

    def _calculate_semester_gpa(self, grades: List[sqlite3.Row]) -> float:
        """Calculate GPA for a specific semester."""
        grade_values = {
            'A+': 4.0, 'A': 4.0, 'A-': 3.7,
            'B+': 3.3, 'B': 3.0, 'B-': 2.7,
            'C+': 2.3, 'C': 2.0, 'C-': 1.7,
            'D+': 1.3, 'D': 1.0, 'F': 0.0
        }

        total_credits = 0
        total_points = 0

        for grade in grades:
            if grade['grade'] in grade_values:
                total_credits += grade['credits']
                total_points += grade_values[grade['grade']] * grade['credits']

        return total_points / total_credits if total_credits > 0 else 0.0

    def _determine_class_standing(self, total_credits: int) -> str:
        """Determine class standing based on credits."""
        if total_credits < 30:
            return 'Freshman'
        elif total_credits < 60:
            return 'Sophomore'
        elif total_credits < 90:
            return 'Junior'
        else:
            return 'Senior'

    def get_progress_history(self, student_id: str) -> List[Dict]:
        """Get historical progress snapshots."""
        with get_connection() as conn:
            snapshots = conn.execute("""
                SELECT * FROM progress_snapshots
                WHERE student_id = ?
                ORDER BY semester DESC
            """, (student_id,)).fetchall()

            return [dict(s) for s in snapshots]

    # ========== Analytics ==========

    def get_progress_analytics(self, student_id: str) -> Dict:
        """Get comprehensive progress analytics for a student."""
        with get_connection() as conn:
            # GPA trend
            gpa_trend = conn.execute("""
                SELECT semester, semester_gpa
                FROM progress_snapshots
                WHERE student_id = ?
                ORDER BY semester
                LIMIT 8
            """, (student_id,)).fetchall()

            # Warning history
            warning_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_warnings,
                    SUM(CASE WHEN resolved = 1 THEN 1 ELSE 0 END) as resolved_count,
                    SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) as high_severity_count
                FROM academic_warnings
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            # Current standings
            current_stats = self._calculate_current_gpa(student_id)

            return {
                'gpa_trend': [dict(t) for t in gpa_trend],
                'current_stats': current_stats,
                'warning_stats': dict(warning_stats) if warning_stats else {},
                'last_updated': datetime.now().isoformat()
            }
