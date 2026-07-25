"""
Tests for Student Affairs Alumni Management Service

Tests cover:
- Alumni registration and profile management
- Event creation and registration
- Donation processing
- Mentorship program
- Alumni directory search
- Job board functionality
- Forum and communication features
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, mock_open

from education_system.systems.university.infrastructure.database.db import get_connection
from education_system.systems.university.domain.learners.alumni import (
    Alumni,
    init_alumni_db,
    setup_alumni_permissions,
    get_db_connection,
    safe_execute,
    set_auth,
)


def _ensure_student(cursor, student_id, first_name='Test', last_name='User', email='test@email.com'):
    """Insert a student record if needed (to satisfy alumni FK constraint)."""
    cursor.execute(
        'INSERT OR IGNORE INTO students (student_id, first_name, last_name, email) VALUES (?, ?, ?, ?)',
        (student_id, first_name, last_name, email),
    )


@pytest.fixture
def setup_alumni_database():
    """Set up test database with alumni tables"""
    # Initialize the database
    init_alumni_db()

    yield

    # Cleanup — use a short timeout to avoid blocking the test suite
    try:
        conn = get_connection(timeout=2)
    except sqlite3.OperationalError:
        return  # DB locked by a leaked connection; skip cleanup

    try:
        cursor = conn.cursor()

        # Delete child tables first to avoid FK constraint violations
        tables = [
            'unified_event_registrations', 'donations', 'mentorships',
            'photo_gallery', 'forum_replies', 'alumni_forum',
            'networking_connections', 'newsletters', 'job_postings',
            'class_reunions', 'regional_chapters', 'business_directory',
            'fundraising_campaigns', 'unified_events', 'alumni',
        ]

        for table in tables:
            try:
                cursor.execute(f'DELETE FROM {table}')
            except (sqlite3.OperationalError, sqlite3.IntegrityError):
                pass  # Table might not exist or FK issue

        conn.commit()
    finally:
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

class TestAlumniClass:
    """Tests for Alumni data class"""

    def test_alumni_initialization(self):
        """Test Alumni object initialization"""
        alumni = Alumni(
            alumni_id='ALU001',
            student_id='S12345',
            email_address='john.doe@email.com',
            title='Mr',
            first_name='John',
            middle_name='',
            last_name='Doe',
            gender='Male',
            dob='1995-05-15',
            graduation_year=2020,
            degree_earned='BSc Computer Science',
            current_employer='TechCorp',
            job_title='Software Engineer',
            industry='Technology',
            address='123 Main St',
            city='London',
            country='UK',
            phone='1234567890',
            linkedin_url='linkedin.com/in/johndoe',
            date_registered='2024-01-01',
            is_donor=False,
            is_mentor=True,
            is_board_member=False
        )

        assert alumni.alumni_id == 'ALU001'
        assert alumni.first_name == 'John'
        assert alumni.graduation_year == 2020
        assert alumni.is_mentor is True
        assert alumni.is_donor is False

class TestDatabaseSetup:
    """Tests for database initialization"""

    def test_init_alumni_db(self, setup_alumni_database):
        """Test database initialization creates required tables"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Check key tables exist
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='alumni'
            """)
            assert cursor.fetchone() is not None

            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='unified_events'
            """)
            assert cursor.fetchone() is not None
        finally:
            conn.close()

    def test_setup_alumni_permissions(self, setup_alumni_database):
        """Test permissions setup"""
        # setup_alumni_permissions() uses get_db_connection() from core module,
        # which has a hardcoded DB_PATH evaluated at import time. We need to
        # patch it so it connects to the same temp DB that conftest provides.
        with patch(
            'education_system.systems.university.domain.learners.alumni.core.get_db_connection',
            side_effect=lambda: get_connection(),
        ):
            setup_alumni_permissions()

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM permissions
                WHERE permission_name IN ('manage_alumni', 'view_alumni', 'make_donation')
            """)
            count = cursor.fetchone()[0]
            assert count >= 3
        finally:
            conn.close()

class TestAlumniRegistration:
    """Tests for alumni registration functionality"""

    def test_register_alumni_basic(self, setup_alumni_database, mock_auth):
        """Test basic alumni registration"""
        # Seed a student record so the FK on alumni.student_id is satisfied.
        conn = get_connection()
        try:
            _ensure_student(conn.cursor(), 'S99999', 'Test', 'User', 'test@email.com')
            conn.commit()
        finally:
            conn.close()

        # The register_alumni function auto-generates the alumni_id (A000001),
        # so no alumni_id input is needed.  The actual input sequence is:
        #   student_id, continue_anyway(y/n), title, first_name, middle_name,
        #   last_name, email, gender(1-4), dob, graduation_year, degree,
        #   employer, job_title, industry, address, city, country, phone,
        #   linkedin, bio, skills, achievements,
        #   is_donor(y/n), is_mentor(y/n), is_board_member(y/n),
        #   is_ambassador(y/n), privacy_level(1/2/3)
        with patch('builtins.input', side_effect=[
            'S99999',          # student_id (exists in DB)
            'Mr',              # title
            'Test',            # first_name
            '',                # middle_name
            'User',            # last_name
            'test@email.com',  # email_address
            '1',               # gender selection (1=Male)
            '1990-01-01',      # dob
            '2020',            # graduation_year
            'BSc Test',        # degree_earned
            'TestCorp',        # current_employer
            'Tester',          # job_title
            'Testing',         # industry
            '123 Test St',     # address
            'TestCity',        # city
            'TestCountry',     # country
            '1234567890',      # phone
            'linkedin.com/test',  # linkedin_url
            '',                # bio
            '',                # skills
            '',                # achievements
            'n',               # is_donor
            'n',               # is_mentor
            'n',               # is_board_member
            'n',               # is_ambassador
            '1',               # privacy_level (1=Public)
        ]):
            with patch('education_system.systems.university.domain.learners.alumni.profiles.auth', mock_auth):
                from education_system.systems.university.domain.learners.alumni import register_alumni
                register_alumni()

                # Verify alumni was created (auto-generated ID is A000001)
                conn = get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute('SELECT * FROM alumni WHERE alumni_id = ?', ('A000001',))
                    result = cursor.fetchone()
                    assert result is not None
                finally:
                    conn.close()

class TestAlumniEvents:
    """Tests for alumni events functionality"""

    def test_create_event_basic(self, setup_alumni_database):
        """Test creating an alumni event"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO unified_events (
                    title, start_datetime, location, description,
                    registration_required, max_capacity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                'Test Event',
                '2025-12-01',
                'Test Venue',
                'Test Description',
                1,
                100,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            event_id = cursor.lastrowid
            conn.commit()

            # Verify event was created
            cursor.execute('SELECT * FROM unified_events WHERE event_id = ?', (event_id,))
            event = cursor.fetchone()

            assert event is not None
            assert event['title'] == 'Test Event'
            assert event['max_capacity'] == 100
        finally:
            conn.close()

    def test_event_registration(self, setup_alumni_database):
        """Test alumni event registration"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # First create an alumni
            _ensure_student(cursor, 'S001', 'John', 'Doe', 'john@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU001', 'S001', 'John', 'Doe', 'john@email.com'))

            # Create an event
            cursor.execute('''
                INSERT INTO unified_events (title, start_datetime, location)
                VALUES (?, ?, ?)
            ''', ('Test Event', '2025-12-01', 'Test Location'))
            event_id = cursor.lastrowid

            # Register for event
            cursor.execute('''
                INSERT INTO unified_event_registrations (event_id, user_id, user_type, registration_date)
                VALUES (?, ?, ?, ?)
            ''', (event_id, 'ALU001', 'alumni', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()

            # Verify registration
            cursor.execute('''
                SELECT * FROM unified_event_registrations
                WHERE event_id = ? AND user_id = ?
            ''', (event_id, 'ALU001'))
            registration = cursor.fetchone()

            assert registration is not None
            assert registration['event_id'] == event_id
        finally:
            conn.close()

class TestDonations:
    """Tests for donation functionality"""

    def test_record_donation(self, setup_alumni_database):
        """Test recording a donation"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create alumni first
            _ensure_student(cursor, 'S002', 'Jane', 'Smith', 'jane@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU002', 'S002', 'Jane', 'Smith', 'jane@email.com'))

            # Record donation
            cursor.execute('''
                INSERT INTO donations (
                    alumni_id, amount, donation_date,
                    campaign, payment_method
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                'ALU002',
                100.00,
                datetime.now().strftime('%Y-%m-%d'),
                'General Fund',
                'Credit Card'
            ))

            donation_id = cursor.lastrowid
            conn.commit()

            # Verify donation
            cursor.execute('SELECT * FROM donations WHERE donation_id = ?', (donation_id,))
            donation = cursor.fetchone()

            assert donation is not None
            assert donation['amount'] == 100.00
            assert donation['alumni_id'] == 'ALU002'
        finally:
            conn.close()

    def test_view_alumni_donations(self, setup_alumni_database):
        """Test viewing donations for an alumni"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create alumni
            _ensure_student(cursor, 'S003', 'Bob', 'Jones', 'bob@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU003', 'S003', 'Bob', 'Jones', 'bob@email.com'))

            # Record multiple donations
            for amt in [50.00, 100.00, 150.00]:
                cursor.execute('''
                    INSERT INTO donations (alumni_id, amount, donation_date, campaign)
                    VALUES (?, ?, ?, ?)
                ''', ('ALU003', amt, datetime.now().strftime('%Y-%m-%d'), 'Test'))

            conn.commit()

            # Query donations
            cursor.execute('''
                SELECT * FROM donations WHERE alumni_id = ? ORDER BY amount
            ''', ('ALU003',))
            donations = cursor.fetchall()

            assert len(donations) == 3
            assert donations[0]['amount'] == 50.00
            assert donations[2]['amount'] == 150.00
        finally:
            conn.close()

class TestMentorship:
    """Tests for mentorship functionality"""

    def test_create_mentorship(self, setup_alumni_database):
        """Test creating a mentorship relationship"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create alumni (mentor)
            _ensure_student(cursor, 'S_MENTOR', 'Mentor', 'Smith', 'mentor@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address, is_mentor)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('ALU_MENTOR', 'S_MENTOR', 'Mentor', 'Smith', 'mentor@email.com', 1))

            # Create student record (mentee)
            _ensure_student(cursor, 'S_MENTEE', 'Student', 'Jones', 'student@email.com')

            # Create mentorship
            cursor.execute('''
                INSERT INTO mentorships (
                    mentor_id, mentee_id, start_date, status, focus_area
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                'ALU_MENTOR',
                'S_MENTEE',
                datetime.now().strftime('%Y-%m-%d'),
                'active',
                'Career Development'
            ))

            mentorship_id = cursor.lastrowid
            conn.commit()

            # Verify mentorship
            cursor.execute('SELECT * FROM mentorships WHERE mentorship_id = ?', (mentorship_id,))
            mentorship = cursor.fetchone()

            assert mentorship is not None
            assert mentorship['status'] == 'active'
            assert mentorship['focus_area'] == 'Career Development'
        finally:
            conn.close()

class TestJobBoard:
    """Tests for job board functionality"""

    def test_post_job(self, setup_alumni_database):
        """Test posting a job opportunity"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create alumni who will post job
            _ensure_student(cursor, 'S_EMP', 'Employer', 'Corp', 'employer@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU_EMPLOYER', 'S_EMP', 'Employer', 'Corp', 'employer@email.com'))

            # Post job
            cursor.execute('''
                INSERT INTO job_postings (
                    job_title, company_name, location, job_description,
                    requirements, salary_range, posted_by, post_date, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                'Software Engineer',
                'TechCorp',
                'London',
                'Great opportunity',
                'Python, JavaScript',
                '50000-70000',
                'ALU_EMPLOYER',
                datetime.now().strftime('%Y-%m-%d'),
                1
            ))

            job_id = cursor.lastrowid
            conn.commit()

            # Verify job posting
            cursor.execute('SELECT * FROM job_postings WHERE job_id = ?', (job_id,))
            job = cursor.fetchone()

            assert job is not None
            assert job['job_title'] == 'Software Engineer'
            assert job['is_active'] == 1
        finally:
            conn.close()

    def test_search_jobs(self, setup_alumni_database):
        """Test searching job board"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create alumni
            _ensure_student(cursor, 'S_POST', 'Post', 'User', 'post@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU_POST', 'S_POST', 'Post', 'User', 'post@email.com'))

            # Post multiple jobs
            jobs = [
                ('Software Engineer', 'TechCorp', 'London'),
                ('Data Scientist', 'DataCo', 'Manchester'),
                ('Web Developer', 'WebCorp', 'London')
            ]

            for title, company, location in jobs:
                cursor.execute('''
                    INSERT INTO job_postings (job_title, company_name, location, posted_by, post_date, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (title, company, location, 'ALU_POST', datetime.now().strftime('%Y-%m-%d'), 1))

            conn.commit()

            # Search for London jobs
            cursor.execute('''
                SELECT * FROM job_postings WHERE location = ? AND is_active = ?
            ''', ('London', 1))
            london_jobs = cursor.fetchall()

            assert len(london_jobs) == 2
        finally:
            conn.close()

class TestAlumniForum:
    """Tests for alumni forum functionality"""

    def test_create_forum_post(self, setup_alumni_database):
        """Test creating a forum post"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create alumni
            _ensure_student(cursor, 'S_FORUM', 'Forum', 'User', 'forum@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU_FORUM', 'S_FORUM', 'Forum', 'User', 'forum@email.com'))

            # Create forum post
            cursor.execute('''
                INSERT INTO alumni_forum (
                    author_id, title, content, category, post_date
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                'ALU_FORUM',
                'Welcome Post',
                'Hello everyone!',
                'General',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            post_id = cursor.lastrowid
            conn.commit()

            # Verify post
            cursor.execute('SELECT * FROM alumni_forum WHERE post_id = ?', (post_id,))
            post = cursor.fetchone()

            assert post is not None
            assert post['title'] == 'Welcome Post'
        finally:
            conn.close()

    def test_forum_replies(self, setup_alumni_database):
        """Test replying to forum posts"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create alumni
            _ensure_student(cursor, 'S_REPLY', 'Reply', 'User', 'reply@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU_REPLY', 'S_REPLY', 'Reply', 'User', 'reply@email.com'))

            # Create post
            cursor.execute('''
                INSERT INTO alumni_forum (author_id, title, content, category, post_date)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU_REPLY', 'Test Post', 'Test Content', 'General', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            post_id = cursor.lastrowid

            # Add reply
            cursor.execute('''
                INSERT INTO forum_replies (post_id, author_id, content, reply_date)
                VALUES (?, ?, ?, ?)
            ''', (post_id, 'ALU_REPLY', 'Test Reply', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()

            # Verify reply
            cursor.execute('SELECT * FROM forum_replies WHERE post_id = ?', (post_id,))
            replies = cursor.fetchall()

            assert len(replies) == 1
            assert replies[0]['content'] == 'Test Reply'
        finally:
            conn.close()

class TestUtilityFunctions:
    """Tests for utility functions"""

    def test_get_db_connection(self):
        """Test database connection utility"""
        conn = get_db_connection()
        try:
            assert conn is not None
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            assert result[0] == 1
        finally:
            conn.close()

    def test_safe_execute_success(self, setup_alumni_database):
        """Test safe_execute with successful query"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            safe_execute(cursor, 'SELECT 1')
            result = cursor.fetchone()

            assert result[0] == 1
        finally:
            conn.close()

    def test_safe_execute_with_params(self, setup_alumni_database):
        """Test safe_execute with parameters"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # Create student then alumni
            _ensure_student(cursor, 'S_SAFE', 'Safe', 'User', 'safe@email.com')
            safe_execute(cursor, '''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?, ?)
            ''', ('ALU_SAFE', 'S_SAFE', 'Safe', 'User', 'safe@email.com'))

            conn.commit()

            # Query with safe_execute
            safe_execute(cursor, 'SELECT * FROM alumni WHERE alumni_id = ?', ('ALU_SAFE',))
            result = cursor.fetchone()

            assert result is not None
            assert result['alumni_id'] == 'ALU_SAFE'
        finally:
            conn.close()

class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_alumni_lifecycle(self, setup_alumni_database):
        """Test complete alumni lifecycle: register, donate, attend event"""
        conn = get_connection()
        try:
            cursor = conn.cursor()

            # 1. Register alumni
            _ensure_student(cursor, 'S_LIFE', 'Life', 'Cycle', 'lifecycle@email.com')
            cursor.execute('''
                INSERT INTO alumni (alumni_id, student_id, first_name, last_name, email_address, graduation_year)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', ('ALU_LIFE', 'S_LIFE', 'Life', 'Cycle', 'lifecycle@email.com', 2020))

            # 2. Make donation
            cursor.execute('''
                INSERT INTO donations (alumni_id, amount, donation_date, campaign)
                VALUES (?, ?, ?, ?)
            ''', ('ALU_LIFE', 250.00, datetime.now().strftime('%Y-%m-%d'), 'Scholarship Fund'))

            # Update alumni donor status
            cursor.execute('UPDATE alumni SET is_donor = 1 WHERE alumni_id = ?', ('ALU_LIFE',))

            # 3. Create and register for event
            cursor.execute('''
                INSERT INTO unified_events (title, start_datetime, location)
                VALUES (?, ?, ?)
            ''', ('Annual Gala', '2025-11-20', 'Grand Hall'))
            event_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO unified_event_registrations (event_id, user_id, user_type, registration_date)
                VALUES (?, ?, ?, ?)
            ''', (event_id, 'ALU_LIFE', 'alumni', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            conn.commit()

            # Verify complete lifecycle
            cursor.execute('SELECT * FROM alumni WHERE alumni_id = ?', ('ALU_LIFE',))
            alumni = cursor.fetchone()

            cursor.execute('SELECT COUNT(*) FROM donations WHERE alumni_id = ?', ('ALU_LIFE',))
            donation_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM unified_event_registrations WHERE user_id = ?', ('ALU_LIFE',))
            event_count = cursor.fetchone()[0]

            assert alumni is not None
            assert alumni['is_donor'] == 1
            assert donation_count == 1
            assert event_count == 1
        finally:
            conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
