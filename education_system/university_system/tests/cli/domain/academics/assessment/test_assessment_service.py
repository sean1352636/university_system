"""
Comprehensive tests for Assessment Service
Tests the unified assessment and assignment data service
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from education_system.university_system.modules.domain.academics.services.assessment_service import (
    AssessmentAssignmentService
)
from education_system.university_system.modules.shared.constants import paths
from education_system.university_system.infrastructure.database.db import get_connection, transaction

@pytest.fixture
def setup_test_db():
    """Setup test database with sample data"""
    with transaction() as conn:
        cursor = conn.cursor()

        # Create test modules
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS modules (
                module_code TEXT PRIMARY KEY,
                module_name TEXT NOT NULL
            )
        """)

        # Delete existing test data in correct order
        cursor.execute("DELETE FROM student_modules WHERE student_id = 'TEST_STUDENT_001'")
        cursor.execute("DELETE FROM assessments WHERE module_code LIKE 'TEST%'")
        cursor.execute("DELETE FROM assignments WHERE module_code LIKE 'TEST%'")
        cursor.execute("DELETE FROM modules WHERE module_code LIKE 'TEST%'")

        cursor.execute("INSERT INTO modules (module_code, module_name) VALUES ('TEST101', 'Test Module 1')")
        cursor.execute("INSERT INTO modules (module_code, module_name) VALUES ('TEST102', 'Test Module 2')")

        # Create test assessments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assessments (
                assessment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                assessment_name TEXT NOT NULL,
                assessment_type TEXT,
                module_code TEXT NOT NULL,
                max_points INTEGER,
                weight REAL,
                due_date TEXT,
                description TEXT,
                rubric TEXT
            )
        """)

        cursor.execute("DELETE FROM assessments WHERE module_code LIKE 'TEST%'")
        cursor.execute("""
            INSERT INTO assessments (assessment_name, assessment_type, module_code, max_points, weight, due_date, description, rubric)
            VALUES
                ('Midterm Exam', 'Exam', 'TEST101', 100, 0.3, ?, 'Midterm examination', ''),
                ('Final Project', 'Project', 'TEST101', 100, 0.5, ?, 'Final project submission', ''),
                ('Quiz 1', 'Quiz', 'TEST102', 50, 0.2, ?, 'First quiz', '')
        """, (
            (datetime.now() + timedelta(days=30)).isoformat(),
            (datetime.now() + timedelta(days=60)).isoformat(),
            (datetime.now() + timedelta(days=7)).isoformat()
        ))

        # Create test assignments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                due_date TEXT NOT NULL,
                max_marks INTEGER DEFAULT 100,
                created_by INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                assignment_type TEXT DEFAULT 'individual'
            )
        """)

        cursor.execute("DELETE FROM assignments WHERE module_code LIKE 'TEST%'")
        now = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO assignments (module_code, title, description, due_date, max_marks, created_by, created_at, updated_at, is_active, assignment_type)
            VALUES
                ('TEST101', 'Assignment 1', 'First assignment', ?, 100, 1, ?, ?, 1, 'individual'),
                ('TEST101', 'Assignment 2', 'Second assignment', ?, 100, 1, ?, ?, 1, 'group'),
                ('TEST102', 'Lab Report', 'Lab report submission', ?, 50, 1, ?, ?, 1, 'individual')
        """, (
            (datetime.now() + timedelta(days=14)).isoformat(), now, now,
            (datetime.now() + timedelta(days=28)).isoformat(), now, now,
            (datetime.now() + timedelta(days=21)).isoformat(), now, now
        ))

        # Create student_modules table for filtering
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_modules (
                student_id TEXT,
                module_code TEXT,
                PRIMARY KEY (student_id, module_code)
            )
        """)

        cursor.execute("DELETE FROM student_modules WHERE student_id = 'TEST_STUDENT_001'")
        cursor.execute("INSERT INTO student_modules (student_id, module_code) VALUES ('TEST_STUDENT_001', 'TEST101')")
        cursor.execute("INSERT INTO student_modules (student_id, module_code) VALUES ('TEST_STUDENT_001', 'TEST102')")

    yield

    # Cleanup - delete in correct order to avoid foreign key constraints
    with transaction() as conn:
        cursor = conn.cursor()
        # First delete child records
        cursor.execute("DELETE FROM student_modules WHERE student_id = 'TEST_STUDENT_001'")
        cursor.execute("DELETE FROM assessments WHERE module_code LIKE 'TEST%'")
        cursor.execute("DELETE FROM assignments WHERE module_code LIKE 'TEST%'")
        # Then delete parent records
        cursor.execute("DELETE FROM modules WHERE module_code LIKE 'TEST%'")

class TestAssessmentAssignmentService:
    """Test suite for AssessmentAssignmentService"""

    def test_get_all_assessments_without_filter(self, setup_test_db):
        """Test retrieving all assessments without filtering"""
        assessments = AssessmentAssignmentService.get_all_assessments()

        # Should get at least the test assessments
        test_assessments = [a for a in assessments if a['module_code'].startswith('TEST')]
        assert len(test_assessments) >= 3

        # Check structure
        assert all('assessment_id' in a for a in test_assessments)
        assert all('assessment_name' in a for a in test_assessments)
        assert all('module_code' in a for a in test_assessments)

    def test_get_all_assessments_with_module_filter(self, setup_test_db):
        """Test retrieving assessments filtered by module"""
        assessments = AssessmentAssignmentService.get_all_assessments(module_code='TEST101')

        assert len(assessments) >= 2
        assert all(a['module_code'] == 'TEST101' for a in assessments)

        # Check specific assessments
        names = [a['assessment_name'] for a in assessments]
        assert 'Midterm Exam' in names
        assert 'Final Project' in names

    def test_get_all_assignments_without_filter(self, setup_test_db):
        """Test retrieving all assignments without filtering"""
        assignments = AssessmentAssignmentService.get_all_assignments()

        # Should get at least the test assignments
        test_assignments = [a for a in assignments if a['module_code'].startswith('TEST')]
        assert len(test_assignments) >= 3

        # Check structure
        assert all('id' in a for a in test_assignments)
        assert all('title' in a for a in test_assignments)
        assert all('module_code' in a for a in test_assignments)
        assert all('is_active' in a for a in test_assignments)

    def test_get_all_assignments_with_module_filter(self, setup_test_db):
        """Test retrieving assignments filtered by module"""
        assignments = AssessmentAssignmentService.get_all_assignments(module_code='TEST101')

        assert len(assignments) >= 2
        assert all(a['module_code'] == 'TEST101' for a in assignments)

        # Check specific assignments
        titles = [a['title'] for a in assignments]
        assert 'Assignment 1' in titles
        assert 'Assignment 2' in titles

    def test_get_all_assignments_with_student_filter(self, setup_test_db):
        """Test retrieving assignments filtered by student enrollment"""
        assignments = AssessmentAssignmentService.get_all_assignments(student_id='TEST_STUDENT_001')

        # Student is enrolled in TEST101 and TEST102
        assert len(assignments) >= 3
        assert all(a['module_code'] in ['TEST101', 'TEST102'] for a in assignments)

    def test_get_all_assignments_with_student_and_module_filter(self, setup_test_db):
        """Test retrieving assignments with both filters"""
        assignments = AssessmentAssignmentService.get_all_assignments(
            module_code='TEST101',
            student_id='TEST_STUDENT_001'
        )

        assert len(assignments) >= 2
        assert all(a['module_code'] == 'TEST101' for a in assignments)

    def test_get_assessment_by_id(self, setup_test_db):
        """Test retrieving a specific assessment by ID"""
        # First get all assessments to get a valid ID
        assessments = AssessmentAssignmentService.get_all_assessments(module_code='TEST101')
        assert len(assessments) > 0

        assessment_id = assessments[0]['assessment_id']

        # Retrieve by ID
        assessment = AssessmentAssignmentService.get_assessment_by_id(assessment_id)

        assert assessment is not None
        assert assessment['assessment_id'] == assessment_id
        assert 'assessment_name' in assessment
        assert 'module_code' in assessment

    def test_get_assessment_by_invalid_id(self, setup_test_db):
        """Test retrieving assessment with invalid ID"""
        assessment = AssessmentAssignmentService.get_assessment_by_id(999999)
        assert assessment is None

    def test_get_assignment_by_id(self, setup_test_db):
        """Test retrieving a specific assignment by ID"""
        # First get all assignments to get a valid ID
        assignments = AssessmentAssignmentService.get_all_assignments(module_code='TEST101')
        assert len(assignments) > 0

        assignment_id = assignments[0]['id']

        # Retrieve by ID
        assignment = AssessmentAssignmentService.get_assignment_by_id(assignment_id)

        assert assignment is not None
        assert assignment['id'] == assignment_id
        assert 'title' in assignment
        assert 'module_code' in assignment

    def test_get_assignment_by_invalid_id(self, setup_test_db):
        """Test retrieving assignment with invalid ID"""
        assignment = AssessmentAssignmentService.get_assignment_by_id(999999)
        assert assignment is None

    def test_sync_assignment_to_assessment(self, setup_test_db):
        """Test creating an assessment from an assignment"""
        # Get a test assignment
        assignments = AssessmentAssignmentService.get_all_assignments(module_code='TEST101')
        assignment_id = assignments[0]['id']

        # Sync to assessment
        assessment_id = AssessmentAssignmentService.sync_assignment_to_assessment(assignment_id)

        assert assessment_id is not None

        # Verify the assessment was created
        assessment = AssessmentAssignmentService.get_assessment_by_id(assessment_id)
        assert assessment is not None
        assert assessment['module_code'] == assignments[0]['module_code']
        assert assessment['assessment_name'] == assignments[0]['title']

    def test_sync_assignment_to_assessment_duplicate(self, setup_test_db):
        """Test syncing same assignment twice returns existing assessment"""
        assignments = AssessmentAssignmentService.get_all_assignments(module_code='TEST101')
        assignment_id = assignments[0]['id']

        # First sync
        assessment_id_1 = AssessmentAssignmentService.sync_assignment_to_assessment(assignment_id)

        # Second sync should return same ID
        assessment_id_2 = AssessmentAssignmentService.sync_assignment_to_assessment(assignment_id)

        assert assessment_id_1 == assessment_id_2

    def test_sync_assignment_to_assessment_invalid_id(self, setup_test_db):
        """Test syncing invalid assignment ID"""
        assessment_id = AssessmentAssignmentService.sync_assignment_to_assessment(999999)
        assert assessment_id is None

    def test_sync_assessment_to_assignment(self, setup_test_db):
        """Test creating an assignment from an assessment"""
        # Get a test assessment
        assessments = AssessmentAssignmentService.get_all_assessments(module_code='TEST102')
        assessment_id = assessments[0]['assessment_id']

        # Sync to assignment
        assignment_id = AssessmentAssignmentService.sync_assessment_to_assignment(
            assessment_id,
            created_by=1
        )

        assert assignment_id is not None

        # Verify the assignment was created
        assignment = AssessmentAssignmentService.get_assignment_by_id(assignment_id)
        assert assignment is not None
        assert assignment['module_code'] == assessments[0]['module_code']
        assert assignment['title'] == assessments[0]['assessment_name']

    def test_sync_assessment_to_assignment_duplicate(self, setup_test_db):
        """Test syncing same assessment twice returns existing assignment"""
        assessments = AssessmentAssignmentService.get_all_assessments(module_code='TEST102')
        assessment_id = assessments[0]['assessment_id']

        # First sync
        assignment_id_1 = AssessmentAssignmentService.sync_assessment_to_assignment(assessment_id, 1)

        # Second sync should return same ID
        assignment_id_2 = AssessmentAssignmentService.sync_assessment_to_assignment(assessment_id, 1)

        assert assignment_id_1 == assignment_id_2

    def test_sync_assessment_to_assignment_invalid_id(self, setup_test_db):
        """Test syncing invalid assessment ID"""
        assignment_id = AssessmentAssignmentService.sync_assessment_to_assignment(999999, 1)
        assert assignment_id is None

    def test_get_modules(self, setup_test_db):
        """Test retrieving all modules"""
        modules = AssessmentAssignmentService.get_modules()

        # Should get at least the test modules
        test_modules = [(code, name) for code, name in modules if code.startswith('TEST')]
        assert len(test_modules) >= 2

        # Check structure
        module_codes = [code for code, _ in test_modules]
        assert 'TEST101' in module_codes
        assert 'TEST102' in module_codes

    def test_assessments_ordered_by_due_date(self, setup_test_db):
        """Test that assessments are ordered by due date descending"""
        assessments = AssessmentAssignmentService.get_all_assessments(module_code='TEST101')

        # Extract due dates
        due_dates = [a['due_date'] for a in assessments if a['due_date']]

        # Check they're in descending order
        assert due_dates == sorted(due_dates, reverse=True)

    def test_assignments_ordered_by_due_date(self, setup_test_db):
        """Test that assignments are ordered by due date descending"""
        assignments = AssessmentAssignmentService.get_all_assignments(module_code='TEST101')

        # Extract due dates
        due_dates = [a['due_date'] for a in assignments if a['due_date']]

        # Check they're in descending order
        assert due_dates == sorted(due_dates, reverse=True)

    def test_only_active_assignments_returned(self, setup_test_db):
        """Test that only active assignments are returned"""
        # Create an inactive assignment
        with transaction() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO assignments
                (module_code, title, description, due_date, max_marks, created_by, created_at, updated_at, is_active)
                VALUES ('TEST101', 'Inactive Assignment', 'Should not appear', ?, 100, 1, ?, ?, 0)
            """, ((datetime.now() + timedelta(days=14)).isoformat(), now, now))

        # Get assignments
        assignments = AssessmentAssignmentService.get_all_assignments(module_code='TEST101')

        # Verify inactive assignment is not returned
        titles = [a['title'] for a in assignments]
        assert 'Inactive Assignment' not in titles

        # Cleanup
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM assignments WHERE title = 'Inactive Assignment'")

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
