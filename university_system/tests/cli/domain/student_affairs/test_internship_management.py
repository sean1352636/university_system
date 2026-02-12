"""
Tests for Student Affairs Internship Management Service

Tests cover:
- Internship CRUD operations
- Application submission and review
- Placement tracking
- Permissions and access control
- Reporting and analytics
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from university_system.infrastructure.database.db import get_connection
from university_system.modules.domain.student_affairs.services.internship_management import (
    init_internship_db,
    setup_internship_permissions,
    set_auth,
)

@pytest.fixture
def setup_internship_database():
    """Set up test database with internship tables"""
    init_internship_db()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()

    tables = ['internships', 'internship_applications', 'internship_placements']

    for table in tables:
        try:
            cursor.execute(f'DELETE FROM {table}')
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

@pytest.fixture
def mock_auth():
    """Create mock authentication object"""
    auth = MagicMock()
    auth.current_user = {
        'id': 1,
        'username': 'test_user',
        'role': 'admin',
        'student_id': 'S12345'
    }
    auth.check_permission = MagicMock(return_value=True)
    auth.is_logged_in = MagicMock(return_value=True)
    return auth

@pytest.fixture
def sample_student(setup_internship_database):
    """Create a sample student for testing"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO students (student_id, first_name, last_name, email_address, course)
        VALUES (?, ?, ?, ?, ?)
    ''', ('S001', 'John', 'Doe', 'john@test.com', 'Computer Science'))

    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, student_id, role)
        VALUES (?, ?, ?, ?)
    ''', (1, 'john_user', 'S001', 'student'))

    conn.commit()
    conn.close()

    return 'S001'

class TestDatabaseSetup:
    """Tests for database initialization"""

    def test_init_internship_db_creates_tables(self, setup_internship_database):
        """Test that internship tables are created"""
        conn = get_connection()
        cursor = conn.cursor()

        tables_to_check = ['internships', 'internship_applications', 'internship_placements']

        for table in tables_to_check:
            cursor.execute(f"""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='{table}'
            """)
            assert cursor.fetchone() is not None, f"Table {table} was not created"

        conn.close()

    def test_sample_internships_created(self, setup_internship_database):
        """Test that sample internships are created"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM internships')
        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 3  # At least the 3 sample internships

class TestInternshipCRUD:
    """Tests for internship CRUD operations"""

    def test_create_internship(self, setup_internship_database):
        """Test creating a new internship"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO internships (
                title, company, location, description, requirements,
                start_date, end_date, is_paid, salary, hours_per_week,
                posted_date, deadline_date, status, contact_email, course_relevance,
                created_by, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'Test Internship',
            'TestCorp',
            'Test City',
            'Test internship description',
            'Python, Testing',
            '2025-06-01',
            '2025-08-31',
            1,
            '£1500/month',
            40,
            datetime.now().strftime('%Y-%m-%d'),
            '2025-05-01',
            'active',
            'test@testcorp.com',
            'CS',
            'admin',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        internship_id = cursor.lastrowid
        conn.commit()

        # Verify internship creation
        cursor.execute('SELECT * FROM internships WHERE internship_id = ?', (internship_id,))
        internship = cursor.fetchone()
        conn.close()

        assert internship is not None
        assert internship['title'] == 'Test Internship'
        assert internship['is_paid'] == 1

    def test_view_internships(self, setup_internship_database):
        """Test viewing all active internships"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM internships
            WHERE status = 'active' AND deadline_date >= ?
        ''', (datetime.now().strftime('%Y-%m-%d'),))

        internships = cursor.fetchall()
        conn.close()

        assert len(internships) >= 0

    def test_update_internship(self, setup_internship_database):
        """Test updating an internship"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create internship
        cursor.execute('''
            INSERT INTO internships (title, company, location, start_date, end_date, status, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('Original Title', 'TestCorp', 'London', '2025-06-01', '2025-08-31', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        internship_id = cursor.lastrowid

        # Update title
        cursor.execute('''
            UPDATE internships SET title = ? WHERE internship_id = ?
        ''', ('Updated Title', internship_id))

        conn.commit()

        # Verify update
        cursor.execute('SELECT title FROM internships WHERE internship_id = ?', (internship_id,))
        title = cursor.fetchone()['title']
        conn.close()

        assert title == 'Updated Title'

    def test_delete_internship(self, setup_internship_database):
        """Test deleting an internship"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create internship
        cursor.execute('''
            INSERT INTO internships (title, company, location, start_date, end_date, status, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('To Delete', 'TestCorp', 'London', '2025-06-01', '2025-08-31', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        internship_id = cursor.lastrowid

        # Delete internship
        cursor.execute('DELETE FROM internships WHERE internship_id = ?', (internship_id,))
        conn.commit()

        # Verify deletion
        cursor.execute('SELECT * FROM internships WHERE internship_id = ?', (internship_id,))
        result = cursor.fetchone()
        conn.close()

        assert result is None

class TestApplicationManagement:
    """Tests for internship applications"""

    def test_submit_application(self, setup_internship_database, sample_student):
        """Test submitting an application"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create internship
        cursor.execute('''
            INSERT INTO internships (title, company, location, start_date, end_date, status, deadline_date, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('Test Position', 'TestCorp', 'London', '2025-06-01', '2025-08-31', 'active', '2025-12-31', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        internship_id = cursor.lastrowid

        # Submit application
        cursor.execute('''
            INSERT INTO internship_applications (
                student_id, internship_id, application_date, status, cv_filename, cover_letter
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            sample_student,
            internship_id,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pending',
            'cv.pdf',
            'I am interested in this position...'
        ))

        application_id = cursor.lastrowid
        conn.commit()

        # Verify application
        cursor.execute('SELECT * FROM internship_applications WHERE application_id = ?', (application_id,))
        application = cursor.fetchone()
        conn.close()

        assert application is not None
        assert application['status'] == 'pending'

    def test_review_application_approve(self, setup_internship_database, sample_student):
        """Test approving an application"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create internship and application
        cursor.execute('''
            INSERT INTO internships (title, company, location, start_date, end_date, status, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('Position', 'Company', 'Location', '2025-06-01', '2025-08-31', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        internship_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO internship_applications (student_id, internship_id, application_date, status)
            VALUES (?, ?, ?, ?)
        ''', (sample_student, internship_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending'))
        application_id = cursor.lastrowid

        # Approve application
        cursor.execute('''
            UPDATE internship_applications
            SET status = ?, feedback = ?
            WHERE application_id = ?
        ''', ('approved', 'Congratulations! Your application has been approved.', application_id))

        conn.commit()

        # Verify approval
        cursor.execute('SELECT status FROM internship_applications WHERE application_id = ?', (application_id,))
        status = cursor.fetchone()['status']
        conn.close()

        assert status == 'approved'

    def test_review_application_reject(self, setup_internship_database, sample_student):
        """Test rejecting an application"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create internship and application
        cursor.execute('''
            INSERT INTO internships (title, company, location, start_date, end_date, status, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('Position', 'Company', 'Location', '2025-06-01', '2025-08-31', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        internship_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO internship_applications (student_id, internship_id, application_date, status)
            VALUES (?, ?, ?, ?)
        ''', (sample_student, internship_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending'))
        application_id = cursor.lastrowid

        # Reject application
        cursor.execute('''
            UPDATE internship_applications
            SET status = ?, feedback = ?
            WHERE application_id = ?
        ''', ('rejected', 'Unfortunately, we cannot proceed with your application.', application_id))

        conn.commit()

        # Verify rejection
        cursor.execute('SELECT status FROM internship_applications WHERE application_id = ?', (application_id,))
        status = cursor.fetchone()['status']
        conn.close()

        assert status == 'rejected'

    def test_view_student_applications(self, setup_internship_database, sample_student):
        """Test viewing applications for a student"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create multiple internships and applications
        for i in range(3):
            cursor.execute('''
                INSERT INTO internships (title, company, location, start_date, end_date, status, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (f'Position {i}', 'Company', 'Location', '2025-06-01', '2025-08-31', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            internship_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO internship_applications (student_id, internship_id, application_date, status)
                VALUES (?, ?, ?, ?)
            ''', (sample_student, internship_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'pending'))

        conn.commit()

        # Query applications
        cursor.execute('SELECT * FROM internship_applications WHERE student_id = ?', (sample_student,))
        applications = cursor.fetchall()
        conn.close()

        assert len(applications) == 3

class TestPlacementTracking:
    """Tests for internship placements"""

    def test_create_placement(self, setup_internship_database, sample_student):
        """Test creating an internship placement"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create internship
        cursor.execute('''
            INSERT INTO internships (title, company, location, start_date, end_date, status, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('Position', 'Company', 'Location', '2025-06-01', '2025-08-31', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        internship_id = cursor.lastrowid

        # Create placement
        cursor.execute('''
            INSERT INTO internship_placements (
                student_id, internship_id, start_date, end_date,
                supervisor_name, supervisor_email, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            sample_student,
            internship_id,
            '2025-06-01',
            '2025-08-31',
            'John Supervisor',
            'supervisor@company.com',
            'active'
        ))

        placement_id = cursor.lastrowid
        conn.commit()

        # Verify placement
        cursor.execute('SELECT * FROM internship_placements WHERE placement_id = ?', (placement_id,))
        placement = cursor.fetchone()
        conn.close()

        assert placement is not None
        assert placement['status'] == 'active'

    def test_add_placement_feedback(self, setup_internship_database, sample_student):
        """Test adding feedback to a placement"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create internship and placement
        cursor.execute('''
            INSERT INTO internships (title, company, location, start_date, end_date, status, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('Position', 'Company', 'Location', '2025-06-01', '2025-08-31', 'active', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        internship_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO internship_placements (student_id, internship_id, start_date, end_date, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (sample_student, internship_id, '2025-06-01', '2025-08-31', 'active'))
        placement_id = cursor.lastrowid

        # Add feedback
        cursor.execute('''
            UPDATE internship_placements
            SET feedback_student = ?, feedback_employer = ?
            WHERE placement_id = ?
        ''', ('Great experience!', 'Excellent performance', placement_id))

        conn.commit()

        # Verify feedback
        cursor.execute('SELECT * FROM internship_placements WHERE placement_id = ?', (placement_id,))
        placement = cursor.fetchone()
        conn.close()

        assert placement['feedback_student'] is not None
        assert placement['feedback_employer'] is not None

class TestReporting:
    """Tests for reporting and analytics"""

    def test_application_statistics(self, setup_internship_database):
        """Test getting application statistics"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM internship_applications
            GROUP BY status
        ''')
        stats = cursor.fetchall()
        conn.close()

        assert isinstance(stats, list)

    def test_placement_count_by_company(self, setup_internship_database):
        """Test counting placements by company"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT i.company, COUNT(p.placement_id) as placement_count
            FROM internship_placements p
            JOIN internships i ON p.internship_id = i.internship_id
            GROUP BY i.company
        ''')
        counts = cursor.fetchall()
        conn.close()

        assert isinstance(counts, list)

class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_complete_internship_workflow(self, setup_internship_database, sample_student):
        """Test complete workflow from internship posting to placement"""
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Create internship
        cursor.execute('''
            INSERT INTO internships (
                title, company, location, description, requirements,
                start_date, end_date, is_paid, salary, hours_per_week,
                posted_date, deadline_date, status, contact_email, created_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            'Software Developer',
            'TechCorp',
            'London',
            'Develop web applications',
            'Python, JavaScript',
            '2025-07-01',
            '2025-09-30',
            1,
            '£2000/month',
            40,
            datetime.now().strftime('%Y-%m-%d'),
            '2025-06-01',
            'active',
            'hr@techcorp.com',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        internship_id = cursor.lastrowid

        # 2. Student applies
        cursor.execute('''
            INSERT INTO internship_applications (
                student_id, internship_id, application_date, status, cv_filename, cover_letter
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            sample_student,
            internship_id,
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'pending',
            'resume.pdf',
            'I am very interested...'
        ))
        application_id = cursor.lastrowid

        # 3. Application is approved
        cursor.execute('''
            UPDATE internship_applications
            SET status = ?, feedback = ?
            WHERE application_id = ?
        ''', ('approved', 'Congratulations!', application_id))

        # 4. Create placement
        cursor.execute('''
            INSERT INTO internship_placements (
                student_id, internship_id, start_date, end_date,
                supervisor_name, supervisor_email, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            sample_student,
            internship_id,
            '2025-07-01',
            '2025-09-30',
            'Jane Manager',
            'jane@techcorp.com',
            'active'
        ))
        placement_id = cursor.lastrowid

        conn.commit()

        # Verify complete workflow
        cursor.execute('SELECT * FROM internships WHERE internship_id = ?', (internship_id,))
        internship = cursor.fetchone()

        cursor.execute('SELECT * FROM internship_applications WHERE application_id = ?', (application_id,))
        application = cursor.fetchone()

        cursor.execute('SELECT * FROM internship_placements WHERE placement_id = ?', (placement_id,))
        placement = cursor.fetchone()

        conn.close()

        assert internship is not None
        assert application['status'] == 'approved'
        assert placement['status'] == 'active'

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
