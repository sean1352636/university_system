"""
Tests for Mental Health & Wellness Portal Core Service

Tests cover:
- CounselorManager (register counselors, get availability)
- AppointmentManager (book, cancel appointments, anonymous appointments)
- ResourceManager (add, search resources)
- WellnessCheckInManager (record check-ins, track trends)
- PeerSupportManager (create matches, log sessions)
- MeditationManager (add sessions, track meditation)
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.student_affairs.services.mental_health.mental_health_core import (
    CounselorManager,
    AppointmentManager,
    ResourceManager,
    WellnessCheckInManager,
    PeerSupportManager,
    MeditationManager,
    display_mental_health_menu,
)

@pytest.fixture
def setup_database():
    """Set up test database with mental health tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create mental_health_counselors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_counselors (
            counselor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            specialization TEXT,
            qualifications TEXT,
            availability_schedule TEXT,
            max_daily_appointments INTEGER DEFAULT 8,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create mental_health_appointments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            counselor_id INTEGER,
            appointment_type TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 50,
            is_anonymous INTEGER DEFAULT 0,
            anonymous_code TEXT,
            mode TEXT DEFAULT 'in-person',
            location TEXT,
            notes TEXT,
            status TEXT DEFAULT 'scheduled',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (counselor_id) REFERENCES mental_health_counselors (counselor_id)
        )
    ''')

    # Create mental_health_resources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            content_type TEXT NOT NULL,
            content_url TEXT,
            tags TEXT,
            view_count INTEGER DEFAULT 0,
            is_published INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create mental_health_checkins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_checkins (
            checkin_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            mood_rating INTEGER NOT NULL,
            stress_level INTEGER NOT NULL,
            sleep_quality INTEGER,
            notes TEXT,
            follow_up_required INTEGER DEFAULT 0,
            checkin_date TEXT DEFAULT (DATE('now')),
            checkin_time TEXT DEFAULT (TIME('now'))
        )
    ''')

    # Create mental_health_peer_support table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_peer_support (
            support_id INTEGER PRIMARY KEY AUTOINCREMENT,
            supporter_student_id TEXT NOT NULL,
            supported_student_id TEXT NOT NULL,
            support_type TEXT NOT NULL,
            notes TEXT,
            session_count INTEGER DEFAULT 0,
            last_session_date TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create mental_health_meditation_sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_meditation_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            audio_url TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            category TEXT NOT NULL,
            difficulty_level TEXT DEFAULT 'beginner',
            play_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create mental_health_meditation_tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mental_health_meditation_tracking (
            tracking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            session_id INTEGER NOT NULL,
            completion_percentage INTEGER DEFAULT 0,
            completed_at TEXT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES mental_health_meditation_sessions (session_id)
        )
    ''')

    # Create students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email_address TEXT
        )
    ''')

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()

    tables = [
        'mental_health_counselors', 'mental_health_appointments',
        'mental_health_resources', 'mental_health_checkins',
        'mental_health_peer_support', 'mental_health_meditation_sessions',
        'mental_health_meditation_tracking'
    ]

    for table in tables:
        cursor.execute(f'DELETE FROM {table}')

    conn.commit()
    conn.close()

@pytest.fixture
def sample_student(setup_database):
    """Create a sample student for testing"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO students (student_id, first_name, last_name, email_address)
        VALUES (?, ?, ?, ?)
    ''', ('S001', 'John', 'Doe', 'john@test.com'))

    conn.commit()
    conn.close()

    return 'S001'

class TestCounselorManager:
    """Tests for CounselorManager"""

    def test_register_counselor(self, setup_database):
        """Test registering a counselor"""
        counselor_id = CounselorManager.register_counselor(
            user_id='USER001',
            name='Dr. Smith',
            specialization='Anxiety and Depression',
            qualifications='PhD in Clinical Psychology',
            availability_schedule='Mon-Fri 9am-5pm',
            max_daily_appointments=8
        )

        assert isinstance(counselor_id, int)

        # Verify counselor
        counselor = CounselorManager.get_counselor_details(counselor_id)
        assert counselor is not None
        assert counselor['name'] == 'Dr. Smith'
        assert counselor['max_daily_appointments'] == 8

    def test_get_available_counselors(self, setup_database):
        """Test getting available counselors"""
        # Register counselor
        CounselorManager.register_counselor(
            user_id='USER002',
            name='Dr. Jones',
            specialization='Stress Management',
            max_daily_appointments=6
        )

        # Get available counselors
        available = CounselorManager.get_available_counselors(
            appointment_date=date.today().isoformat()
        )

        assert len(available) > 0

    def test_get_available_counselors_with_specialization(self, setup_database):
        """Test filtering counselors by specialization"""
        # Register counselors
        CounselorManager.register_counselor('U1', 'Dr. A', specialization='Anxiety')
        CounselorManager.register_counselor('U2', 'Dr. B', specialization='Depression')

        # Get anxiety specialists
        specialists = CounselorManager.get_available_counselors(
            appointment_date=date.today().isoformat(),
            specialization='Anxiety'
        )

        assert len(specialists) >= 1
        assert any(c['specialization'] == 'Anxiety' for c in specialists)

class TestAppointmentManager:
    """Tests for AppointmentManager"""

    def test_book_appointment(self, setup_database, sample_student):
        """Test booking a standard appointment"""
        student_id = sample_student

        # Register counselor
        counselor_id = CounselorManager.register_counselor('USER003', 'Counselor')

        # Book appointment
        appointment_id, anonymous_code = AppointmentManager.book_appointment(
            student_id=student_id,
            counselor_id=counselor_id,
            appointment_type='Individual Counseling',
            appointment_date=date.today().isoformat(),
            appointment_time='10:00',
            duration_minutes=50,
            is_anonymous=False,
            mode='in-person',
            location='Room 101',
            notes='First session'
        )

        assert isinstance(appointment_id, int)
        assert anonymous_code is None  # Not anonymous

        # Verify appointment
        appointments = AppointmentManager.get_student_appointments(student_id)
        assert len(appointments) == 1

    def test_book_anonymous_appointment(self, setup_database, sample_student):
        """Test booking an anonymous appointment"""
        student_id = sample_student

        counselor_id = CounselorManager.register_counselor('USER004', 'Counselor')

        # Book anonymous appointment
        appointment_id, anonymous_code = AppointmentManager.book_appointment(
            student_id=student_id,
            counselor_id=counselor_id,
            appointment_type='Anonymous Support',
            appointment_date=date.today().isoformat(),
            appointment_time='14:00',
            is_anonymous=True
        )

        assert anonymous_code is not None
        assert len(anonymous_code) == 12  # Code is 12 characters

    def test_cancel_appointment(self, setup_database, sample_student):
        """Test cancelling an appointment"""
        student_id = sample_student

        counselor_id = CounselorManager.register_counselor('USER005', 'Counselor')

        # Book appointment
        appointment_id, _ = AppointmentManager.book_appointment(
            student_id=student_id,
            counselor_id=counselor_id,
            appointment_type='Counseling',
            appointment_date=date.today().isoformat(),
            appointment_time='11:00'
        )

        # Cancel it
        result = AppointmentManager.cancel_appointment(appointment_id)
        assert result is True

        # Verify cancellation
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM mental_health_appointments WHERE appointment_id = ?', (appointment_id,))
        status = cursor.fetchone()['status']
        conn.close()

        assert status == 'cancelled'

class TestResourceManager:
    """Tests for ResourceManager"""

    def test_add_resource(self, setup_database):
        """Test adding a mental health resource"""
        resource_id = ResourceManager.add_resource(
            category='Stress Management',
            title='Coping with Exam Stress',
            description='Tips for managing exam-related anxiety',
            content_type='article',
            content_url='https://example.com/stress-tips',
            tags='stress,exam,anxiety'
        )

        assert isinstance(resource_id, int)

    def test_get_resources_by_category(self, setup_database):
        """Test retrieving resources by category"""
        # Add resources
        ResourceManager.add_resource('Anxiety', 'Title 1', 'Desc 1', 'article')
        ResourceManager.add_resource('Anxiety', 'Title 2', 'Desc 2', 'video')
        ResourceManager.add_resource('Depression', 'Title 3', 'Desc 3', 'article')

        # Get anxiety resources
        anxiety_resources = ResourceManager.get_resources_by_category('Anxiety')

        assert len(anxiety_resources) == 2

    def test_search_resources(self, setup_database):
        """Test searching resources"""
        # Add resources
        ResourceManager.add_resource('Test', 'Meditation Guide', 'How to meditate', 'article', tags='meditation,mindfulness')
        ResourceManager.add_resource('Test', 'Breathing Exercises', 'Breathing techniques', 'video', tags='breathing,relaxation')

        # Search for "meditation"
        results = ResourceManager.search_resources('meditation')

        assert len(results) >= 1
        assert any('meditation' in r['title'].lower() or 'meditation' in r.get('tags', '').lower() for r in results)

    def test_increment_view_count(self, setup_database):
        """Test incrementing resource view count"""
        resource_id = ResourceManager.add_resource('Test', 'Resource', 'Description', 'article')

        # Increment view count
        ResourceManager.increment_view_count(resource_id)

        # Verify count
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT view_count FROM mental_health_resources WHERE resource_id = ?', (resource_id,))
        count = cursor.fetchone()['view_count']
        conn.close()

        assert count == 1

class TestWellnessCheckInManager:
    """Tests for WellnessCheckInManager"""

    def test_record_checkin_normal(self, setup_database, sample_student):
        """Test recording a normal wellness check-in"""
        student_id = sample_student

        checkin_id, follow_up_required = WellnessCheckInManager.record_checkin(
            student_id=student_id,
            mood_rating=7,
            stress_level=4,
            sleep_quality=7,
            notes='Feeling good today'
        )

        assert isinstance(checkin_id, int)
        assert follow_up_required is False

    def test_record_checkin_requires_followup(self, setup_database, sample_student):
        """Test check-in that requires follow-up"""
        student_id = sample_student

        # Low mood and high stress should trigger follow-up
        checkin_id, follow_up_required = WellnessCheckInManager.record_checkin(
            student_id=student_id,
            mood_rating=2,
            stress_level=9,
            notes='Feeling overwhelmed'
        )

        assert follow_up_required is True

    def test_get_checkin_history(self, setup_database, sample_student):
        """Test retrieving check-in history"""
        student_id = sample_student

        # Record multiple check-ins
        for i in range(5):
            WellnessCheckInManager.record_checkin(student_id, mood_rating=i+3, stress_level=i+2)

        # Get history
        history = WellnessCheckInManager.get_student_checkin_history(student_id, days=30)

        assert len(history) == 5

    def test_get_wellness_trends(self, setup_database, sample_student):
        """Test getting wellness trends"""
        student_id = sample_student

        # Record check-ins
        WellnessCheckInManager.record_checkin(student_id, 7, 4, 8)
        WellnessCheckInManager.record_checkin(student_id, 6, 5, 7)
        WellnessCheckInManager.record_checkin(student_id, 8, 3, 9)

        # Get trends
        trends = WellnessCheckInManager.get_wellness_trends(student_id)

        assert 'avg_mood' in trends
        assert 'avg_stress' in trends
        assert trends['total_checkins'] == 3

class TestPeerSupportManager:
    """Tests for PeerSupportManager"""

    def test_create_peer_support_match(self, setup_database):
        """Test creating a peer support match"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create students
        cursor.execute('INSERT INTO students (student_id, first_name, last_name, email_address) VALUES (?, ?, ?, ?)',
                      ('S_SUPPORT', 'Supporter', 'Person', 'support@test.com'))
        cursor.execute('INSERT INTO students (student_id, first_name, last_name, email_address) VALUES (?, ?, ?, ?)',
                      ('S_SUPPORTED', 'Supported', 'Person', 'supported@test.com'))
        conn.commit()
        conn.close()

        # Create match
        support_id = PeerSupportManager.create_peer_support_match(
            supporter_student_id='S_SUPPORT',
            supported_student_id='S_SUPPORTED',
            support_type='Mentorship',
            notes='Academic support'
        )

        assert isinstance(support_id, int)

    def test_log_peer_session(self, setup_database):
        """Test logging a peer support session"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create students
        cursor.execute('INSERT INTO students (student_id, first_name, last_name, email_address) VALUES (?, ?, ?, ?)',
                      ('S_SUP2', 'Supporter', 'Two', 'sup2@test.com'))
        cursor.execute('INSERT INTO students (student_id, first_name, last_name, email_address) VALUES (?, ?, ?, ?)',
                      ('S_SUPD2', 'Supported', 'Two', 'supd2@test.com'))
        conn.commit()
        conn.close()

        # Create match
        support_id = PeerSupportManager.create_peer_support_match('S_SUP2', 'S_SUPD2', 'Peer Support')

        # Log session
        PeerSupportManager.log_peer_session(support_id)

        # Verify session count
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT session_count FROM mental_health_peer_support WHERE support_id = ?', (support_id,))
        count = cursor.fetchone()['session_count']
        conn.close()

        assert count == 1

class TestMeditationManager:
    """Tests for MeditationManager"""

    def test_add_meditation_session(self, setup_database):
        """Test adding a meditation session"""
        session_id = MeditationManager.add_meditation_session(
            title='Guided Breathing',
            description='10-minute breathing meditation',
            audio_url='https://example.com/breathing.mp3',
            duration_minutes=10,
            category='Breathing',
            difficulty_level='beginner'
        )

        assert isinstance(session_id, int)

    def test_track_meditation(self, setup_database, sample_student):
        """Test tracking meditation completion"""
        student_id = sample_student

        # Add session
        session_id = MeditationManager.add_meditation_session(
            'Session', 'Description', 'url.mp3', 15, 'Mindfulness'
        )

        # Track completion
        tracking_id = MeditationManager.track_meditation(student_id, session_id, completed=True)

        assert isinstance(tracking_id, int)

        # Verify play count increased
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT play_count FROM mental_health_meditation_sessions WHERE session_id = ?', (session_id,))
        count = cursor.fetchone()['play_count']
        conn.close()

        assert count == 1

    def test_get_meditation_sessions(self, setup_database):
        """Test retrieving meditation sessions"""
        # Add sessions
        MeditationManager.add_meditation_session('Session 1', 'Desc', 'url1', 10, 'Breathing', 'beginner')
        MeditationManager.add_meditation_session('Session 2', 'Desc', 'url2', 20, 'Mindfulness', 'intermediate')

        # Get all sessions
        sessions = MeditationManager.get_meditation_sessions()
        assert len(sessions) >= 2

        # Get by category
        breathing_sessions = MeditationManager.get_meditation_sessions(category='Breathing')
        assert len(breathing_sessions) >= 1

class TestCLIMenu:
    """Tests for CLI menu"""

    def test_display_mental_health_menu_exit(self, setup_database):
        """Test menu display and exit"""
        with patch('builtins.input', return_value='8'):
            with patch('builtins.print'):
                mock_auth = MagicMock()
                display_mental_health_menu(mock_auth)

class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_complete_wellness_workflow(self, setup_database, sample_student):
        """Test complete wellness workflow"""
        student_id = sample_student

        # 1. Record check-in showing need for support
        checkin_id, follow_up_required = WellnessCheckInManager.record_checkin(
            student_id, mood_rating=3, stress_level=8, notes='Very stressed'
        )
        assert follow_up_required is True

        # 2. Book counseling appointment
        counselor_id = CounselorManager.register_counselor('COUNSELOR', 'Dr. Help')
        appointment_id, _ = AppointmentManager.book_appointment(
            student_id, counselor_id, 'Individual Counseling',
            date.today().isoformat(), '10:00'
        )

        # 3. Access resources
        resource_id = ResourceManager.add_resource(
            'Stress', 'Managing Stress', 'Tips', 'article'
        )
        ResourceManager.increment_view_count(resource_id)

        # 4. Start meditation practice
        session_id = MeditationManager.add_meditation_session(
            'Calm Mind', 'Calming meditation', 'url', 15, 'Relaxation'
        )
        MeditationManager.track_meditation(student_id, session_id, completed=True)

        # 5. Follow-up check-in shows improvement
        checkin_id2, follow_up_required2 = WellnessCheckInManager.record_checkin(
            student_id, mood_rating=7, stress_level=4
        )
        assert follow_up_required2 is False

        # Verify trends show improvement
        trends = WellnessCheckInManager.get_wellness_trends(student_id)
        assert trends['total_checkins'] == 2

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
