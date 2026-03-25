"""
Course Planning Assistant Service

Helps students plan multi-semester course schedules with prerequisite tracking.
"""

from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
import json
from collections import defaultdict, deque

from education_system.university_system.infrastructure.database.db import get_connection, transaction
from education_system.university_system.modules.shared.utils.activity_logger import log_activity

class PlanningService:
    """Service for intelligent course planning and schedule optimization."""

    def __init__(self):
        """Initialize the Planning Service."""
        self._ensure_tables_exist()

    def _ensure_tables_exist(self):
        """Create database tables if they don't exist."""
        with transaction() as conn:
            # Course Prerequisites table (enhanced)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS course_prerequisites (
                    prerequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    prerequisite_course_id TEXT NOT NULL,
                    prerequisite_type TEXT DEFAULT 'Required',
                    minimum_grade TEXT DEFAULT 'D',
                    can_be_concurrent BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(course_id, prerequisite_course_id)
                )
            """)

            # Add columns that may be missing if table was created by another module
            for col, col_def in [
                ('minimum_grade', "TEXT DEFAULT 'D'"),
                ('can_be_concurrent', "BOOLEAN DEFAULT 0"),
                ('prerequisite_type', "TEXT DEFAULT 'Required'"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE course_prerequisites ADD COLUMN {col} {col_def}")
                except Exception:
                    pass  # Column already exists

            # Course Corequisites table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS course_corequisites (
                    corequisite_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    corequisite_course_id TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(course_id, corequisite_course_id)
                )
            """)

            # Multi-Semester Plans table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS semester_plans (
                    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    plan_name TEXT NOT NULL,
                    program_code TEXT,
                    start_semester TEXT NOT NULL,
                    total_semesters INTEGER DEFAULT 8,
                    credits_per_semester INTEGER DEFAULT 15,
                    include_summer BOOLEAN DEFAULT 0,
                    status TEXT DEFAULT 'Draft',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Planned Courses table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS planned_courses (
                    planned_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    course_id TEXT NOT NULL,
                    semester_number INTEGER NOT NULL,
                    semester_name TEXT NOT NULL,
                    is_locked BOOLEAN DEFAULT 0,
                    priority INTEGER DEFAULT 0,
                    notes TEXT,
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plan_id) REFERENCES semester_plans(plan_id) ON DELETE CASCADE,
                    UNIQUE(plan_id, course_id)
                )
            """)

            # Course Offering Patterns table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS course_offerings (
                    offering_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL,
                    offered_fall BOOLEAN DEFAULT 1,
                    offered_spring BOOLEAN DEFAULT 1,
                    offered_summer BOOLEAN DEFAULT 0,
                    offered_years TEXT DEFAULT 'Every',
                    typical_enrollment INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(course_id)
                )
            """)

            # Schedule Conflicts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plan_schedule_conflicts (
                    conflict_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    conflict_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    description TEXT NOT NULL,
                    affected_courses_json TEXT,
                    affected_semester INTEGER,
                    resolution_suggestions_json TEXT,
                    is_resolved BOOLEAN DEFAULT 0,
                    detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plan_id) REFERENCES semester_plans(plan_id) ON DELETE CASCADE
                )
            """)

            # Course Sequences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS course_sequences (
                    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence_name TEXT NOT NULL,
                    program_code TEXT,
                    sequence_type TEXT DEFAULT 'Linear',
                    courses_json TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Prerequisite Graph Cache table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS prerequisite_graph_cache (
                    cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    course_id TEXT NOT NULL UNIQUE,
                    all_prerequisites_json TEXT NOT NULL,
                    depth_level INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Course Recommendations table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS course_recommendations (
                    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    recommendation_reason TEXT NOT NULL,
                    relevance_score REAL DEFAULT 0.0,
                    semester_recommended TEXT,
                    prerequisites_met BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Time Slot Preferences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS time_slot_preferences (
                    preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    day_of_week TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    preference_level TEXT DEFAULT 'Preferred',
                    reason TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Degree Program Courses table
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

            log_activity('create', 'course_planning_tables',
                        details={'status': 'Course planning tables created'})

    # ========== Multi-Semester Planning ==========

    def create_semester_plan(self, student_id: str, plan_name: str,
                            program_code: Optional[str] = None,
                            start_semester: str = "Fall 2026",
                            total_semesters: int = 8,
                            credits_per_semester: int = 15,
                            include_summer: bool = False) -> int:
        """
        Create a new multi-semester course plan.

        Args:
            student_id: Student's ID
            plan_name: Name for the plan
            program_code: Program/major code
            start_semester: Starting semester (e.g., "Fall 2026")
            total_semesters: Number of semesters to plan
            credits_per_semester: Target credits per semester
            include_summer: Include summer sessions

        Returns:
            Plan ID
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO semester_plans
                (student_id, plan_name, program_code, start_semester,
                 total_semesters, credits_per_semester, include_summer)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (student_id, plan_name, program_code, start_semester,
                  total_semesters, credits_per_semester, include_summer))

            plan_id = cursor.lastrowid

            log_activity('create', 'semester_plan',
                        details={'plan_id': plan_id, 'student_id': student_id, 'name': plan_name})

            return plan_id

    def add_course_to_plan(self, plan_id: int, course_id: str,
                          semester_number: int, semester_name: str,
                          is_locked: bool = False, priority: int = 0,
                          notes: Optional[str] = None) -> int:
        """
        Add a course to a semester plan.

        Args:
            plan_id: Plan ID
            course_id: Course ID
            semester_number: Semester number (1-based)
            semester_name: Semester name (e.g., "Fall 2026")
            is_locked: Whether the course is locked in this semester
            priority: Priority level (higher = more important)
            notes: Optional notes

        Returns:
            Planned course ID
        """
        with transaction() as conn:
            # Verify plan exists to avoid FK constraint errors
            plan_exists = conn.execute(
                "SELECT plan_id FROM semester_plans WHERE plan_id = ?",
                (plan_id,)
            ).fetchone()
            if not plan_exists:
                raise ValueError(f"Plan ID {plan_id} does not exist")

            cursor = conn.execute("""
                INSERT INTO planned_courses
                (plan_id, course_id, semester_number, semester_name,
                 is_locked, priority, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (plan_id, course_id, semester_number, semester_name,
                  is_locked, priority, notes))

            planned_course_id = cursor.lastrowid

            log_activity('create', 'planned_course',
                        details={'planned_course_id': planned_course_id, 'plan_id': plan_id, 'course_id': course_id})

            return planned_course_id

    def get_semester_plan(self, plan_id: int) -> Optional[Dict]:
        """Get a complete semester plan with all courses."""
        with get_connection() as conn:
            plan = conn.execute("""
                SELECT * FROM semester_plans WHERE plan_id = ?
            """, (plan_id,)).fetchone()

            if not plan:
                return None

            # Get all planned courses organized by semester
            courses = conn.execute("""
                SELECT pc.*, c.course_name, c.credits, c.department
                FROM planned_courses pc
                JOIN courses c ON pc.course_id = c.code
                WHERE pc.plan_id = ?
                ORDER BY pc.semester_number, pc.priority DESC
            """, (plan_id,)).fetchall()

            # Organize by semester
            semesters = defaultdict(list)
            for course in courses:
                course_dict = dict(course)
                semesters[course['semester_number']].append(course_dict)

            return {
                'plan': dict(plan),
                'semesters': dict(semesters),
                'total_courses': len(courses)
            }

    def get_student_plans(self, student_id: str) -> List[Dict]:
        """Get all semester plans for a student."""
        with get_connection() as conn:
            plans = conn.execute("""
                SELECT * FROM semester_plans
                WHERE student_id = ?
                ORDER BY created_at DESC
            """, (student_id,)).fetchall()

            return [dict(plan) for plan in plans]

    def generate_auto_plan(self, student_id: str, program_code: str,
                          start_semester: str = "Fall 2026") -> int:
        """
        Automatically generate a semester plan based on degree requirements.

        Args:
            student_id: Student's ID
            program_code: Program/major code
            start_semester: Starting semester

        Returns:
            Plan ID
        """
        # Create the plan
        plan_id = self.create_semester_plan(
            student_id=student_id,
            plan_name=f"Auto-Generated Plan - {program_code}",
            program_code=program_code,
            start_semester=start_semester
        )

        with get_connection() as conn:
            # Get student's completed courses
            completed = conn.execute("""
                SELECT module_code as course_id FROM module_grades
                WHERE student_id = ? AND final_grade IS NOT NULL
                AND final_grade NOT IN ('F', 'W', 'I')
                UNION
                SELECT module_code as course_id FROM student_grades
                WHERE student_id = ? AND grade IS NOT NULL
                AND grade NOT IN ('F', 'W', 'I')
                AND assessment_name LIKE '%Final%'
            """, (student_id, student_id)).fetchall()
            completed_ids = {row['course_id'] for row in completed if row['course_id']}

            # Get required courses for the program
            required_courses = conn.execute("""
                SELECT code as course_id FROM courses
                WHERE department LIKE ? || '%'
                ORDER BY code
            """, (program_code[:3],)).fetchall()

            # Filter out completed courses
            remaining_courses = [
                course['course_id'] for course in required_courses
                if course['course_id'] not in completed_ids
            ]

            # Build prerequisite graph
            prereq_graph = self._build_prerequisite_graph()

            # Topologically sort courses
            sorted_courses = self._topological_sort(remaining_courses, prereq_graph)

            # Distribute courses across semesters
            semester_number = 1
            semester_name = start_semester
            credits_this_semester = 0
            max_credits = 15

            for course_id in sorted_courses:
                # Get course credits
                course_info = conn.execute("""
                    SELECT credits FROM courses WHERE code = ?
                """, (course_id,)).fetchone()

                if not course_info:
                    continue

                credits = course_info['credits']

                # Check if we need to move to next semester
                if credits_this_semester + credits > max_credits:
                    semester_number += 1
                    semester_name = self._get_next_semester(semester_name)
                    credits_this_semester = 0

                # Add course to plan
                self.add_course_to_plan(
                    plan_id=plan_id,
                    course_id=course_id,
                    semester_number=semester_number,
                    semester_name=semester_name
                )

                credits_this_semester += credits

        log_activity('create', 'auto_generated_plan',
                    details={'plan_id': plan_id, 'student_id': student_id, 'program': program_code})

        return plan_id

    def _get_next_semester(self, current_semester: str) -> str:
        """Get the next semester name."""
        parts = current_semester.split()
        season = parts[0]
        year = int(parts[1])

        if season == "Fall":
            return f"Spring {year + 1}"
        elif season == "Spring":
            return f"Fall {year}"
        else:  # Summer
            return f"Fall {year}"

    # ========== Prerequisite Visualization ==========

    def build_prerequisite_tree(self, course_id: str, depth: int = 10) -> Dict:
        """
        Build a complete prerequisite tree for a course.

        Args:
            course_id: Course ID
            depth: Maximum depth to traverse

        Returns:
            Dictionary representing the prerequisite tree
        """
        visited = set()
        prereq_graph = self._build_prerequisite_graph()

        def build_tree_recursive(cid: str, current_depth: int) -> Dict:
            if current_depth > depth or cid in visited:
                return {'course_id': cid, 'prerequisites': []}

            visited.add(cid)

            prerequisites = prereq_graph.get(cid, [])
            prereq_trees = []

            for prereq in prerequisites:
                prereq_trees.append(
                    build_tree_recursive(prereq['prerequisite_course_id'], current_depth + 1)
                )

            return {
                'course_id': cid,
                'prerequisites': prereq_trees,
                'prerequisite_count': len(prereq_trees),
                'total_depth': current_depth
            }

        tree = build_tree_recursive(course_id, 0)

        log_activity('view', 'prerequisite_tree', details={'course_id': course_id})

        return tree

    def get_all_prerequisites(self, course_id: str) -> List[str]:
        """
        Get all prerequisites (direct and indirect) for a course.

        Args:
            course_id: Course ID

        Returns:
            List of all prerequisite course IDs
        """
        with get_connection() as conn:
            # Check cache first
            cached = conn.execute("""
                SELECT all_prerequisites_json FROM prerequisite_graph_cache
                WHERE course_id = ?
                AND last_updated >= date('now', '-7 days')
            """, (course_id,)).fetchone()

            if cached:
                return json.loads(cached['all_prerequisites_json'])

        # Build from scratch
        prereq_graph = self._build_prerequisite_graph()
        all_prereqs = set()
        queue = deque([course_id])
        visited = set()

        while queue:
            current = queue.popleft()
            if current in visited:
                continue

            visited.add(current)
            prerequisites = prereq_graph.get(current, [])

            for prereq in prerequisites:
                prereq_id = prereq['prerequisite_course_id']
                all_prereqs.add(prereq_id)
                queue.append(prereq_id)

        all_prereqs_list = list(all_prereqs)

        # Cache the result (disable FK checks — cache table has FK to courses
        # but course_id may come from modules/course_prerequisites)
        try:
            with transaction() as conn:
                conn.execute("PRAGMA foreign_keys = OFF")
                conn.execute("""
                    INSERT INTO prerequisite_graph_cache
                    (course_id, all_prerequisites_json, depth_level)
                    VALUES (?, ?, ?)
                    ON CONFLICT(course_id) DO UPDATE SET
                        all_prerequisites_json = excluded.all_prerequisites_json,
                        last_updated = CURRENT_TIMESTAMP
                """, (course_id, json.dumps(all_prereqs_list), len(all_prereqs_list)))
                conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass  # Cache failure is non-critical

        return all_prereqs_list

    def _build_prerequisite_graph(self) -> Dict[str, List[Dict]]:
        """Build a graph of all course prerequisites."""
        with get_connection() as conn:
            prereqs = conn.execute("""
                SELECT * FROM course_prerequisites
            """).fetchall()

            graph = defaultdict(list)
            for prereq in prereqs:
                graph[prereq['course_id']].append(dict(prereq))

            return dict(graph)

    def visualize_prerequisite_chain(self, course_id: str) -> List[List[str]]:
        """
        Create a level-based visualization of prerequisites.

        Args:
            course_id: Course ID

        Returns:
            List of levels, each containing course IDs at that level
        """
        prereq_graph = self._build_prerequisite_graph()
        levels = []
        current_level = [course_id]
        visited = set()

        while current_level:
            levels.append(current_level)
            next_level = []

            for cid in current_level:
                if cid in visited:
                    continue
                visited.add(cid)

                prerequisites = prereq_graph.get(cid, [])
                for prereq in prerequisites:
                    prereq_id = prereq['prerequisite_course_id']
                    if prereq_id not in visited:
                        next_level.append(prereq_id)

            current_level = list(set(next_level))

        # Reverse to show from foundation to advanced
        return list(reversed(levels))

    def check_prerequisite_eligibility(self, student_id: str, course_id: str) -> Dict:
        """
        Check if a student is eligible for a course based on prerequisites.

        Args:
            student_id: Student's ID
            course_id: Course ID

        Returns:
            Eligibility status with details
        """
        with get_connection() as conn:
            # Get student's completed courses from module_grades and student_grades
            completed = conn.execute("""
                SELECT module_code as course_id, final_grade as grade FROM module_grades
                WHERE student_id = ? AND final_grade NOT IN ('F', 'W', 'I')
                UNION
                SELECT module_code as course_id, grade FROM student_grades
                WHERE student_id = ? AND grade NOT IN ('F', 'W', 'I')
                AND assessment_name LIKE '%Final%'
            """, (student_id, student_id)).fetchall()
            completed_dict = {row['course_id']: row['grade'] for row in completed}

            # Get course prerequisites
            prerequisites = conn.execute("""
                SELECT * FROM course_prerequisites
                WHERE course_id = ?
            """, (course_id,)).fetchall()

            missing_prerequisites = []
            met_prerequisites = []

            for prereq in prerequisites:
                prereq_id = prereq['prerequisite_course_id']
                try:
                    min_grade = prereq['minimum_grade'] or 'D'
                except (IndexError, KeyError):
                    min_grade = 'D'

                if prereq_id in completed_dict:
                    student_grade = completed_dict[prereq_id]
                    if self._compare_grades(student_grade, min_grade) >= 0:
                        met_prerequisites.append({
                            'course_id': prereq_id,
                            'grade': student_grade,
                            'required_grade': min_grade
                        })
                    else:
                        missing_prerequisites.append({
                            'course_id': prereq_id,
                            'reason': f"Grade too low ({student_grade} < {min_grade})",
                            'status': 'Grade Insufficient'
                        })
                else:
                    missing_prerequisites.append({
                        'course_id': prereq_id,
                        'reason': "Not completed",
                        'status': 'Not Taken'
                    })

            eligible = len(missing_prerequisites) == 0

            return {
                'course_id': course_id,
                'eligible': eligible,
                'met_prerequisites': met_prerequisites,
                'missing_prerequisites': missing_prerequisites,
                'total_prerequisites': len(prerequisites)
            }

    def _compare_grades(self, grade1: str, grade2: str) -> int:
        """Compare two letter grades. Returns 1 if grade1 > grade2, 0 if equal, -1 if less."""
        grade_order = {
            'A+': 13, 'A': 12, 'A-': 11,
            'B+': 10, 'B': 9, 'B-': 8,
            'C+': 7, 'C': 6, 'C-': 5,
            'D+': 4, 'D': 3, 'F': 0
        }

        val1 = grade_order.get(grade1, 0)
        val2 = grade_order.get(grade2, 0)

        if val1 > val2:
            return 1
        elif val1 == val2:
            return 0
        else:
            return -1

    # ========== Conflict Detection ==========

    def detect_plan_schedule_conflicts(self, plan_id: int) -> List[Dict]:
        """
        Detect scheduling conflicts in a semester plan.

        Args:
            plan_id: Plan ID

        Returns:
            List of detected conflicts
        """
        conflicts = []

        with get_connection() as conn:
            # Get the plan
            plan_data = self.get_semester_plan(plan_id)
            if not plan_data:
                return []

            plan = plan_data['plan']
            semesters = plan_data['semesters']

            # Check each semester
            for semester_num, courses in semesters.items():
                semester_conflicts = []

                # 1. Check prerequisite conflicts
                prereq_conflicts = self._check_prerequisite_conflicts(
                    courses, semester_num, semesters
                )
                conflicts.extend(prereq_conflicts)

                # 2. Check credit overload
                total_credits = sum(course['credits'] for course in courses)
                max_credits = plan['credits_per_semester'] + 3  # Allow 3 credit buffer

                if total_credits > max_credits:
                    conflicts.append({
                        'type': 'Credit Overload',
                        'severity': 'High',
                        'semester': semester_num,
                        'description': f"Semester {semester_num} has {total_credits} credits (max: {max_credits})",
                        'affected_courses': [c['course_id'] for c in courses],
                        'suggestions': [
                            f"Move {total_credits - max_credits} credits to another semester",
                            "Consider dropping lower priority courses"
                        ]
                    })

                # 3. Check course offering conflicts
                offering_conflicts = self._check_offering_conflicts(
                    courses, plan_data['plan']['start_semester'], semester_num
                )
                conflicts.extend(offering_conflicts)

                # 4. Check corequisite conflicts
                coreq_conflicts = self._check_corequisite_conflicts(courses)
                conflicts.extend(coreq_conflicts)

            # Save conflicts to database
            for conflict in conflicts:
                self._save_conflict_record(plan_id, conflict)

            log_activity('view', 'plan_schedule_conflicts', details={
                'plan_id': plan_id,
                'conflicts_found': len(conflicts)
            })

            return conflicts

    def _check_prerequisite_conflicts(self, current_courses: List[Dict],
                                     current_semester: int,
                                     all_semesters: Dict) -> List[Dict]:
        """Check for prerequisite conflicts in a semester."""
        conflicts = []
        prereq_graph = self._build_prerequisite_graph()

        # Get all courses scheduled before this semester
        previous_courses = set()
        for sem_num, courses in all_semesters.items():
            if sem_num < current_semester:
                previous_courses.update(c['course_id'] for c in courses)

        # Check each course
        for course in current_courses:
            course_id = course['course_id']
            prerequisites = prereq_graph.get(course_id, [])

            for prereq in prerequisites:
                prereq_id = prereq['prerequisite_course_id']

                # Check if prerequisite is scheduled before
                if prereq_id not in previous_courses:
                    # Check if it's in the same semester (corequisite allowed)
                    same_semester = any(
                        c['course_id'] == prereq_id for c in current_courses
                    )

                    can_concurrent = False
                    try:
                        can_concurrent = prereq.get('can_be_concurrent', False) if isinstance(prereq, dict) else prereq['can_be_concurrent']
                    except (IndexError, KeyError):
                        pass

                    if not same_semester or not can_concurrent:
                        conflicts.append({
                            'type': 'Prerequisite Not Met',
                            'severity': 'High',
                            'semester': current_semester,
                            'description': f"{course_id} requires {prereq_id} which is not scheduled earlier",
                            'affected_courses': [course_id, prereq_id],
                            'suggestions': [
                                f"Add {prereq_id} to an earlier semester",
                                f"Move {course_id} to a later semester"
                            ]
                        })

        return conflicts

    def _check_offering_conflicts(self, courses: List[Dict],
                                  start_semester: str,
                                  semester_number: int) -> List[Dict]:
        """Check if courses are offered in the planned semester."""
        conflicts = []

        # Determine semester type
        semester_info = self._calculate_semester_info(start_semester, semester_number)
        semester_type = semester_info['type']  # Fall, Spring, or Summer

        with get_connection() as conn:
            for course in courses:
                course_id = course['course_id']

                # Get offering pattern
                offering = conn.execute("""
                    SELECT * FROM course_offerings
                    WHERE course_id = ?
                """, (course_id,)).fetchone()

                if offering:
                    offered = False
                    if semester_type == "Fall" and offering['offered_fall']:
                        offered = True
                    elif semester_type == "Spring" and offering['offered_spring']:
                        offered = True
                    elif semester_type == "Summer" and offering['offered_summer']:
                        offered = True

                    if not offered:
                        conflicts.append({
                            'type': 'Course Not Offered',
                            'severity': 'Medium',
                            'semester': semester_number,
                            'description': f"{course_id} is not typically offered in {semester_type}",
                            'affected_courses': [course_id],
                            'suggestions': [
                                f"Move {course_id} to a {self._get_offering_semesters(offering)} semester",
                                "Check with department for exceptions"
                            ]
                        })

        return conflicts

    def _get_offering_semesters(self, offering: sqlite3.Row) -> str:
        """Get human-readable offering pattern."""
        semesters = []
        if offering['offered_fall']:
            semesters.append("Fall")
        if offering['offered_spring']:
            semesters.append("Spring")
        if offering['offered_summer']:
            semesters.append("Summer")
        return "/".join(semesters)

    def _calculate_semester_info(self, start_semester: str, semester_number: int) -> Dict:
        """Calculate semester information."""
        parts = start_semester.split()
        start_season = parts[0]
        start_year = int(parts[1])

        # Calculate which semester this is
        seasons = ["Fall", "Spring"]
        if start_season == "Fall":
            season_index = 0
        else:
            season_index = 1

        current_index = (season_index + semester_number - 1) % 2
        year_offset = (season_index + semester_number - 1) // 2

        semester_type = seasons[current_index]
        year = start_year + year_offset

        return {
            'type': semester_type,
            'year': year,
            'full_name': f"{semester_type} {year}"
        }

    def _check_corequisite_conflicts(self, courses: List[Dict]) -> List[Dict]:
        """Check for corequisite conflicts."""
        conflicts = []
        course_ids = {c['course_id'] for c in courses}

        with get_connection() as conn:
            for course in courses:
                # Get corequisites
                coreqs = conn.execute("""
                    SELECT corequisite_course_id FROM course_corequisites
                    WHERE course_id = ?
                """, (course['course_id'],)).fetchall()

                for coreq in coreqs:
                    coreq_id = coreq['corequisite_course_id']
                    if coreq_id not in course_ids:
                        conflicts.append({
                            'type': 'Corequisite Missing',
                            'severity': 'Medium',
                            'description': f"{course['course_id']} requires corequisite {coreq_id}",
                            'affected_courses': [course['course_id'], coreq_id],
                            'suggestions': [
                                f"Add {coreq_id} to the same semester"
                            ]
                        })

        return conflicts

    def _save_conflict_record(self, plan_id: int, conflict: Dict):
        """Save a conflict record to the database."""
        with transaction() as conn:
            # Check if similar conflict already exists
            existing = conn.execute("""
                SELECT conflict_id FROM plan_schedule_conflicts
                WHERE plan_id = ? AND conflict_type = ?
                AND affected_semester = ? AND is_resolved = 0
                AND detected_at >= date('now', '-1 day')
            """, (plan_id, conflict['type'],
                  conflict.get('semester', 0))).fetchone()

            if not existing:
                conn.execute("""
                    INSERT INTO plan_schedule_conflicts
                    (plan_id, conflict_type, severity, description,
                     affected_courses_json, affected_semester,
                     resolution_suggestions_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (plan_id, conflict['type'], conflict['severity'],
                      conflict['description'],
                      json.dumps(conflict.get('affected_courses', [])),
                      conflict.get('semester', 0),
                      json.dumps(conflict.get('suggestions', []))))

    def get_plan_conflicts(self, plan_id: int) -> List[Dict]:
        """Get all unresolved conflicts for a plan."""
        with get_connection() as conn:
            conflicts = conn.execute("""
                SELECT * FROM plan_schedule_conflicts
                WHERE plan_id = ? AND is_resolved = 0
                ORDER BY severity DESC, detected_at DESC
            """, (plan_id,)).fetchall()

            return [dict(c) for c in conflicts]

    def resolve_conflict(self, conflict_id: int) -> bool:
        """Mark a conflict as resolved."""
        with transaction() as conn:
            conn.execute("""
                UPDATE plan_schedule_conflicts
                SET is_resolved = 1
                WHERE conflict_id = ?
            """, (conflict_id,))

            log_activity('update', 'schedule_conflict',
                        details={'conflict_id': conflict_id, 'resolved': True})
            return True

    # ========== Course Sequencing ==========

    def create_course_sequence(self, sequence_name: str, program_code: str,
                               courses: List[str], sequence_type: str = "Linear") -> int:
        """
        Create a predefined course sequence.

        Args:
            sequence_name: Name of the sequence
            program_code: Program code
            courses: List of course IDs in order
            sequence_type: 'Linear', 'Flexible', or 'Branching'

        Returns:
            Sequence ID
        """
        with transaction() as conn:
            cursor = conn.execute("""
                INSERT INTO course_sequences
                (sequence_name, program_code, sequence_type, courses_json)
                VALUES (?, ?, ?, ?)
            """, (sequence_name, program_code, sequence_type, json.dumps(courses)))

            sequence_id = cursor.lastrowid

            log_activity('create', 'course_sequence',
                        details={'sequence_id': sequence_id, 'name': sequence_name, 'courses': len(courses)})

            return sequence_id

    def get_recommended_sequences(self, program_code: str) -> List[Dict]:
        """Get recommended course sequences for a program."""
        with get_connection() as conn:
            sequences = conn.execute("""
                SELECT * FROM course_sequences
                WHERE program_code = ?
                ORDER BY sequence_name
            """, (program_code,)).fetchall()

            return [dict(seq) for seq in sequences]

    # ========== Topological Sort (for auto-planning) ==========

    def _topological_sort(self, courses: List[str],
                         prereq_graph: Dict[str, List[Dict]]) -> List[str]:
        """
        Perform topological sort on courses based on prerequisites.

        Args:
            courses: List of course IDs to sort
            prereq_graph: Prerequisite graph

        Returns:
            Topologically sorted list of courses
        """
        # Build adjacency list and in-degree count
        in_degree = defaultdict(int)
        adj_list = defaultdict(list)

        # Only consider courses in our list
        course_set = set(courses)

        for course in courses:
            prerequisites = prereq_graph.get(course, [])
            for prereq in prerequisites:
                prereq_id = prereq['prerequisite_course_id']
                if prereq_id in course_set:
                    adj_list[prereq_id].append(course)
                    in_degree[course] += 1

        # Initialize queue with courses having no prerequisites
        queue = deque([c for c in courses if in_degree[c] == 0])
        sorted_courses = []

        while queue:
            current = queue.popleft()
            sorted_courses.append(current)

            # Reduce in-degree for dependent courses
            for dependent in adj_list[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # If not all courses are sorted, there's a cycle
        if len(sorted_courses) != len(courses):
            # Add remaining courses (there's a cycle, but we still need to schedule them)
            remaining = [c for c in courses if c not in sorted_courses]
            sorted_courses.extend(remaining)

        return sorted_courses

    # ========== Course Recommendations ==========

    def recommend_courses(self, student_id: str, semester: str,
                         max_recommendations: int = 10) -> List[Dict]:
        """
        Recommend courses for a student based on progress and interests.

        Args:
            student_id: Student's ID
            semester: Target semester
            max_recommendations: Maximum number of recommendations

        Returns:
            List of recommended courses with scores
        """
        with get_connection() as conn:
            # Get student's completed courses
            completed = conn.execute("""
                SELECT module_code as course_id FROM module_grades
                WHERE student_id = ? AND final_grade NOT IN ('F', 'W', 'I')
                UNION
                SELECT module_code as course_id FROM student_grades
                WHERE student_id = ? AND grade NOT IN ('F', 'W', 'I')
                AND assessment_name LIKE '%Final%'
            """, (student_id, student_id)).fetchall()
            completed_ids = {row['course_id'] for row in completed if row['course_id']}

            # Get student's current enrollments (if lms_student_enrollment exists)
            try:
                current = conn.execute("""
                    SELECT c.code as course_id
                    FROM lms_student_enrollment lse
                    JOIN courses c ON c.id = lse.lms_course_id
                    WHERE lse.student_id = ? AND lse.is_active = 1
                """, (student_id,)).fetchall()
                current_ids = {row['course_id'] for row in current if row['course_id']}
            except Exception:
                current_ids = set()

            # Get student's program
            student = conn.execute("""
                SELECT course FROM students WHERE student_id = ?
            """, (student_id,)).fetchone()

            if not student:
                return []

            program_code = student['course'] or ""

            # Find eligible courses
            all_courses = conn.execute("""
                SELECT code as course_id, course_name, credits, department
                FROM courses
                WHERE department LIKE ? || '%'
            """, (program_code[:3],)).fetchall()

            recommendations = []

            for course in all_courses:
                course_id = course['course_id']

                # Skip if already taken or currently enrolled
                if course_id in completed_ids or course_id in current_ids:
                    continue

                # Check prerequisite eligibility
                eligibility = self.check_prerequisite_eligibility(student_id, course_id)

                if eligibility['eligible']:
                    # Calculate relevance score
                    score = 1.0

                    # Bonus for courses in student's major
                    if course['department'].startswith(program_code[:3]):
                        score += 0.5

                    # Bonus for courses with more prerequisites met (more advanced)
                    score += len(eligibility['met_prerequisites']) * 0.1

                    recommendations.append({
                        'course_id': course_id,
                        'course_name': course['course_name'],
                        'credits': course['credits'],
                        'relevance_score': round(score, 2),
                        'reason': self._generate_recommendation_reason(
                            course, eligibility
                        ),
                        'prerequisites_met': True
                    })

            # Sort by relevance score
            recommendations.sort(key=lambda x: x['relevance_score'], reverse=True)

            # Save recommendations
            for rec in recommendations[:max_recommendations]:
                self._save_recommendation(student_id, rec, semester)

            log_activity('view', 'course_recommendations', details={
                'student_id': student_id,
                'count': len(recommendations[:max_recommendations])
            })

            return recommendations[:max_recommendations]

    def _generate_recommendation_reason(self, course: sqlite3.Row,
                                       eligibility: Dict) -> str:
        """Generate a human-readable recommendation reason."""
        reasons = []

        if course['department']:
            reasons.append(f"Part of {course['department']} curriculum")

        prereq_count = len(eligibility['met_prerequisites'])
        if prereq_count > 0:
            reasons.append(f"You've completed {prereq_count} prerequisite(s)")
        else:
            reasons.append("No prerequisites required")

        return " • ".join(reasons)

    def _save_recommendation(self, student_id: str, recommendation: Dict, semester: str):
        """Save a course recommendation."""
        with transaction() as conn:
            conn.execute("""
                INSERT INTO course_recommendations
                (student_id, course_id, recommendation_reason,
                 relevance_score, semester_recommended, prerequisites_met)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, recommendation['course_id'],
                  recommendation['reason'], recommendation['relevance_score'],
                  semester, recommendation['prerequisites_met']))

    def get_student_recommendations(self, student_id: str) -> List[Dict]:
        """Get saved course recommendations for a student."""
        with get_connection() as conn:
            recommendations = conn.execute("""
                SELECT cr.*, c.course_name, c.credits
                FROM course_recommendations cr
                JOIN courses c ON cr.course_id = c.code
                WHERE cr.student_id = ?
                ORDER BY cr.relevance_score DESC, cr.created_at DESC
                LIMIT 20
            """, (student_id,)).fetchall()

            return [dict(rec) for rec in recommendations]

    # ========== Analytics ==========

    def get_planning_analytics(self, student_id: str) -> Dict:
        """Get comprehensive planning analytics for a student."""
        with get_connection() as conn:
            # Plan statistics
            plan_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_plans,
                    SUM(CASE WHEN status = 'Active' THEN 1 ELSE 0 END) as active_plans
                FROM semester_plans
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            # Conflict statistics
            conflict_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_conflicts,
                    SUM(CASE WHEN is_resolved = 1 THEN 1 ELSE 0 END) as resolved_conflicts,
                    SUM(CASE WHEN severity = 'High' THEN 1 ELSE 0 END) as high_severity_conflicts
                FROM plan_schedule_conflicts sc
                JOIN semester_plans sp ON sc.plan_id = sp.plan_id
                WHERE sp.student_id = ?
            """, (student_id,)).fetchone()

            # Recommendation statistics
            rec_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_recommendations,
                    AVG(relevance_score) as avg_relevance_score
                FROM course_recommendations
                WHERE student_id = ?
            """, (student_id,)).fetchone()

            return {
                'plans': dict(plan_stats) if plan_stats else {},
                'conflicts': dict(conflict_stats) if conflict_stats else {},
                'recommendations': dict(rec_stats) if rec_stats else {}
            }
