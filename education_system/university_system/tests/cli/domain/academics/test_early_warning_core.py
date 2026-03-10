"""
Tests for Student Success Early Warning System Core Service

Tests cover:
- RiskAssessmentManager (calculate risk scores, get at-risk students)
- IndicatorManager (add, resolve indicators)
- InterventionManager (create, complete interventions)
- CoachingManager (register coaches, assign students, record progress)
- TutoringManager (create recommendations, assign tutors)
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.student_affairs.services.early_warning.early_warning_core import (
    RiskAssessmentManager,
    IndicatorManager,
    InterventionManager,
    CoachingManager,
    TutoringManager,
    display_early_warning_menu,
)

@pytest.fixture
def setup_database():
    """Set up test database with required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create early_warning_profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            overall_risk_score INTEGER DEFAULT 0,
            risk_level TEXT DEFAULT 'low',
            academic_risk_score INTEGER DEFAULT 0,
            attendance_risk_score INTEGER DEFAULT 0,
            engagement_risk_score INTEGER DEFAULT 0,
            financial_risk_score INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create early_warning_indicators table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_indicators (
            indicator_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            indicator_type TEXT NOT NULL,
            indicator_value TEXT,
            severity TEXT DEFAULT 'medium',
            notes TEXT,
            is_resolved INTEGER DEFAULT 0,
            detected_at TEXT DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT
        )
    ''')

    # Create early_warning_interventions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_interventions (
            intervention_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            intervention_type TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            description TEXT,
            assigned_to TEXT,
            scheduled_date TEXT,
            status TEXT DEFAULT 'pending',
            completed_date TEXT,
            outcome TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create early_warning_coaches table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_coaches (
            coach_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            specialization TEXT,
            qualifications TEXT,
            availability_schedule TEXT,
            max_students INTEGER DEFAULT 30,
            status TEXT DEFAULT 'active',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create early_warning_coaching_assignments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_coaching_assignments (
            assignment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            coach_id INTEGER NOT NULL,
            reason TEXT,
            meeting_frequency TEXT DEFAULT 'weekly',
            assigned_date TEXT DEFAULT CURRENT_TIMESTAMP,
            last_meeting_date TEXT,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (coach_id) REFERENCES early_warning_coaches (coach_id)
        )
    ''')

    # Create early_warning_progress_monitoring table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_progress_monitoring (
            monitoring_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            coach_id INTEGER NOT NULL,
            academic_progress TEXT,
            attendance_progress TEXT,
            engagement_progress TEXT,
            goals_achieved TEXT,
            concerns TEXT,
            next_steps TEXT,
            monitoring_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (coach_id) REFERENCES early_warning_coaches (coach_id)
        )
    ''')

    # Create early_warning_tutoring_recommendations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS early_warning_tutoring_recommendations (
            recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            module_code TEXT NOT NULL,
            recommended_by TEXT NOT NULL,
            recommendation_type TEXT NOT NULL,
            priority TEXT DEFAULT 'medium',
            tutor_assigned TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create supporting tables for risk calculation
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email_address TEXT,
            course TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lms_gradebook (
            grade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            score REAL,
            max_score REAL,
            graded_at TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_analytics (
            analytics_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            attendance_percentage REAL,
            consecutive_absences INTEGER
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_fees (
            fee_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            status TEXT DEFAULT 'unpaid'
        )
    ''')

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()

    tables = [
        'early_warning_profiles', 'early_warning_indicators',
        'early_warning_interventions', 'early_warning_coaches',
        'early_warning_coaching_assignments', 'early_warning_progress_monitoring',
        'early_warning_tutoring_recommendations', 'lms_gradebook',
        'attendance_analytics', 'student_fees'
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

    student_id = 'TEST_STUDENT_001'
    cursor.execute('''
        INSERT INTO students (student_id, first_name, last_name, email_address, course)
        VALUES (?, ?, ?, ?, ?)
    ''', (student_id, 'Test', 'Student', 'test@student.com', 'Computer Science'))

    conn.commit()
    conn.close()

    return student_id

class TestRiskAssessmentManager:
    """Tests for RiskAssessmentManager"""

    def test_calculate_risk_score_low_risk(self, setup_database, sample_student):
        """Test calculating risk score for a low-risk student"""
        student_id = sample_student
        conn = get_connection()
        cursor = conn.cursor()

        # Add good grades
        cursor.execute('''
            INSERT INTO lms_gradebook (student_id, score, max_score, graded_at)
            VALUES (?, ?, ?, ?)
        ''', (student_id, 85, 100, datetime.now().strftime('%Y-%m-%d')))

        # Add good attendance
        cursor.execute('''
            INSERT INTO attendance_analytics (student_id, attendance_percentage, consecutive_absences)
            VALUES (?, ?, ?)
        ''', (student_id, 95.0, 0))

        conn.commit()
        conn.close()

        # Calculate risk
        score, level = RiskAssessmentManager.calculate_risk_score(student_id)

        assert isinstance(score, int)
        assert level in ['low', 'medium', 'high', 'critical']
        assert score < 30  # Should be low risk
        assert level == 'low'

    def test_calculate_risk_score_high_risk(self, setup_database, sample_student):
        """Test calculating risk score for a high-risk student"""
        student_id = sample_student
        conn = get_connection()
        cursor = conn.cursor()

        # Add poor grades
        cursor.execute('''
            INSERT INTO lms_gradebook (student_id, score, max_score, graded_at)
            VALUES (?, ?, ?, ?)
        ''', (student_id, 40, 100, datetime.now().strftime('%Y-%m-%d')))

        # Add poor attendance
        cursor.execute('''
            INSERT INTO attendance_analytics (student_id, attendance_percentage, consecutive_absences)
            VALUES (?, ?, ?)
        ''', (student_id, 50.0, 5))

        # Add unpaid fees
        for _ in range(3):
            cursor.execute('''
                INSERT INTO student_fees (student_id, status)
                VALUES (?, 'unpaid')
            ''', (student_id,))

        conn.commit()
        conn.close()

        # Calculate risk
        score, level = RiskAssessmentManager.calculate_risk_score(student_id)

        assert score >= 50  # Should be high risk
        assert level in ['high', 'critical']

    def test_get_at_risk_students_high(self, setup_database):
        """Test retrieving high-risk students"""
        # Create students with different risk levels
        students = [
            ('HIGH_RISK_1', 'High', 'Risk', 'high@test.com', 75, 'high'),
            ('MEDIUM_RISK', 'Medium', 'Risk', 'medium@test.com', 40, 'medium'),
            ('LOW_RISK', 'Low', 'Risk', 'low@test.com', 20, 'low'),
        ]

        conn = get_connection()
        cursor = conn.cursor()

        for student_id, first, last, email, score, level in students:
            cursor.execute('''
                INSERT INTO students (student_id, first_name, last_name, email_address, course)
                VALUES (?, ?, ?, ?, ?)
            ''', (student_id, first, last, email, 'Test Course'))

            cursor.execute('''
                INSERT INTO early_warning_profiles (student_id, overall_risk_score, risk_level)
                VALUES (?, ?, ?)
            ''', (student_id, score, level))

        conn.commit()
        conn.close()

        # Get high-risk students
        at_risk = RiskAssessmentManager.get_at_risk_students(risk_level='high')

        assert len(at_risk) >= 1
        assert any(s['student_id'] == 'HIGH_RISK_1' for s in at_risk)

class TestIndicatorManager:
    """Tests for IndicatorManager"""

    def test_add_indicator_low_severity(self, setup_database, sample_student):
        """Test adding a low severity indicator"""
        student_id = sample_student

        indicator_id = IndicatorManager.add_indicator(
            student_id,
            'attendance',
            'missed_2_classes',
            'low',
            'Student missed 2 consecutive classes'
        )

        assert isinstance(indicator_id, int)

        # Verify indicator was created
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_indicators WHERE indicator_id = ?', (indicator_id,))
        indicator = cursor.fetchone()
        conn.close()

        assert indicator is not None
        assert indicator['severity'] == 'low'

    def test_add_indicator_high_severity_triggers_intervention(self, setup_database, sample_student):
        """Test that high severity indicators trigger interventions"""
        student_id = sample_student

        with patch.object(InterventionManager, 'create_intervention', return_value=1) as mock_create:
            indicator_id = IndicatorManager.add_indicator(
                student_id,
                'academic',
                'failing_grade',
                'high',
                'Student failing multiple courses'
            )

            # Verify intervention was triggered
            mock_create.assert_called_once()

    def test_resolve_indicator(self, setup_database, sample_student):
        """Test resolving an indicator"""
        student_id = sample_student

        # Create indicator
        indicator_id = IndicatorManager.add_indicator(
            student_id, 'academic', 'test_value', 'medium', 'Test'
        )

        # Resolve it
        result = IndicatorManager.resolve_indicator(indicator_id, 'Issue resolved through tutoring')

        assert result is True

        # Verify resolution
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_indicators WHERE indicator_id = ?', (indicator_id,))
        indicator = cursor.fetchone()
        conn.close()

        assert indicator['is_resolved'] == 1
        assert indicator['resolved_at'] is not None

    def test_get_active_indicators(self, setup_database, sample_student):
        """Test retrieving active indicators for a student"""
        student_id = sample_student

        # Create multiple indicators
        IndicatorManager.add_indicator(student_id, 'academic', 'val1', 'low', 'Note 1')
        IndicatorManager.add_indicator(student_id, 'attendance', 'val2', 'medium', 'Note 2')
        indicator_id = IndicatorManager.add_indicator(student_id, 'engagement', 'val3', 'high', 'Note 3')

        # Resolve one
        IndicatorManager.resolve_indicator(indicator_id, 'Resolved')

        # Get active indicators
        active = IndicatorManager.get_active_indicators(student_id)

        assert len(active) == 2  # Two should still be active

class TestInterventionManager:
    """Tests for InterventionManager"""

    def test_create_intervention(self, setup_database, sample_student):
        """Test creating an intervention"""
        student_id = sample_student

        intervention_id = InterventionManager.create_intervention(
            student_id,
            'academic',
            'tutoring',
            'high',
            'Student needs tutoring for Math course',
            assigned_to='tutor@school.edu',
            scheduled_date=date.today().isoformat()
        )

        assert isinstance(intervention_id, int)

        # Verify intervention
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_interventions WHERE intervention_id = ?', (intervention_id,))
        intervention = cursor.fetchone()
        conn.close()

        assert intervention is not None
        assert intervention['status'] == 'pending'
        assert intervention['priority'] == 'high'

    def test_complete_intervention(self, setup_database, sample_student):
        """Test completing an intervention"""
        student_id = sample_student

        # Create intervention
        intervention_id = InterventionManager.create_intervention(
            student_id, 'academic', 'meeting', 'medium', 'Test intervention'
        )

        # Complete it
        result = InterventionManager.complete_intervention(
            intervention_id,
            'successful',
            'Student showed improvement after intervention'
        )

        assert result is True

        # Verify completion
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_interventions WHERE intervention_id = ?', (intervention_id,))
        intervention = cursor.fetchone()
        conn.close()

        assert intervention['status'] == 'completed'
        assert intervention['outcome'] == 'successful'
        assert intervention['completed_date'] is not None

    def test_get_pending_interventions(self, setup_database):
        """Test retrieving pending interventions"""
        # Create students and interventions
        students = [('S001', 'John', 'Doe'), ('S002', 'Jane', 'Smith')]

        conn = get_connection()
        cursor = conn.cursor()

        for student_id, first, last in students:
            cursor.execute('''
                INSERT INTO students (student_id, first_name, last_name, email_address)
                VALUES (?, ?, ?, ?)
            ''', (student_id, first, last, f'{student_id}@test.com'))

        conn.commit()
        conn.close()

        # Create interventions
        InterventionManager.create_intervention('S001', 'academic', 'tutoring', 'high', 'Test 1')
        InterventionManager.create_intervention('S002', 'attendance', 'meeting', 'medium', 'Test 2')

        # Get pending
        pending = InterventionManager.get_pending_interventions()

        assert len(pending) >= 2

class TestCoachingManager:
    """Tests for CoachingManager"""

    def test_register_coach(self, setup_database):
        """Test registering a success coach"""
        coach_id = CoachingManager.register_coach(
            user_id='COACH001',
            name='Dr. Smith',
            specialization='Academic Success',
            max_students=25
        )

        assert isinstance(coach_id, int)

        # Verify coach
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_coaches WHERE coach_id = ?', (coach_id,))
        coach = cursor.fetchone()
        conn.close()

        assert coach is not None
        assert coach['name'] == 'Dr. Smith'
        assert coach['max_students'] == 25

    def test_assign_student_to_coach(self, setup_database, sample_student):
        """Test assigning a student to a coach"""
        student_id = sample_student

        # Register coach
        coach_id = CoachingManager.register_coach('COACH002', 'Coach Name')

        # Assign student
        assignment_id = CoachingManager.assign_student_to_coach(
            student_id,
            coach_id,
            'Student at risk academically',
            meeting_frequency='weekly'
        )

        assert isinstance(assignment_id, int)

        # Verify assignment
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_coaching_assignments WHERE assignment_id = ?', (assignment_id,))
        assignment = cursor.fetchone()
        conn.close()

        assert assignment is not None
        assert assignment['status'] == 'active'

    def test_record_progress(self, setup_database, sample_student):
        """Test recording progress monitoring"""
        student_id = sample_student

        # Register coach and assign student
        coach_id = CoachingManager.register_coach('COACH003', 'Progress Coach')
        CoachingManager.assign_student_to_coach(student_id, coach_id, 'Test')

        # Record progress
        monitoring_id = CoachingManager.record_progress(
            student_id,
            coach_id,
            academic_progress='Improved from D to C',
            attendance_progress='Attendance at 90%',
            engagement_progress='More engaged in class',
            goals_achieved='Completed tutoring sessions',
            concerns='Still struggling with Math',
            next_steps='Continue tutoring'
        )

        assert isinstance(monitoring_id, int)

        # Verify progress record
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_progress_monitoring WHERE monitoring_id = ?', (monitoring_id,))
        progress = cursor.fetchone()

        # Verify last meeting date was updated
        cursor.execute('SELECT last_meeting_date FROM early_warning_coaching_assignments WHERE student_id = ? AND coach_id = ?',
                      (student_id, coach_id))
        assignment = cursor.fetchone()
        conn.close()

        assert progress is not None
        assert assignment['last_meeting_date'] is not None

class TestTutoringManager:
    """Tests for TutoringManager"""

    def test_create_tutoring_recommendation(self, setup_database, sample_student):
        """Test creating a tutoring recommendation"""
        student_id = sample_student

        recommendation_id = TutoringManager.create_tutoring_recommendation(
            student_id,
            'MATH101',
            'instructor@school.edu',
            'one-on-one',
            priority='high'
        )

        assert isinstance(recommendation_id, int)

        # Verify recommendation
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_tutoring_recommendations WHERE recommendation_id = ?', (recommendation_id,))
        rec = cursor.fetchone()
        conn.close()

        assert rec is not None
        assert rec['module_code'] == 'MATH101'
        assert rec['status'] == 'pending'

    def test_assign_tutor(self, setup_database, sample_student):
        """Test assigning a tutor to a recommendation"""
        student_id = sample_student

        # Create recommendation
        recommendation_id = TutoringManager.create_tutoring_recommendation(
            student_id, 'CS101', 'staff@school.edu', 'group_tutoring'
        )

        # Assign tutor
        result = TutoringManager.assign_tutor(recommendation_id, 'tutor@school.edu')

        assert result is True

        # Verify assignment
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM early_warning_tutoring_recommendations WHERE recommendation_id = ?', (recommendation_id,))
        rec = cursor.fetchone()
        conn.close()

        assert rec['tutor_assigned'] == 'tutor@school.edu'
        assert rec['status'] == 'assigned'

class TestCLIMenu:
    """Tests for CLI menu"""

    def test_display_early_warning_menu_exit(self, setup_database):
        """Test menu display and exit"""
        with patch('builtins.input', return_value='8'):
            with patch('builtins.print'):
                mock_auth = MagicMock()
                display_early_warning_menu(mock_auth)

class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_complete_at_risk_workflow(self, setup_database, sample_student):
        """Test complete workflow from risk detection to intervention"""
        student_id = sample_student

        # 1. Add poor academic data
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lms_gradebook (student_id, score, max_score, graded_at)
            VALUES (?, ?, ?, ?)
        ''', (student_id, 45, 100, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()

        # 2. Calculate risk
        score, level = RiskAssessmentManager.calculate_risk_score(student_id)
        assert level in ['medium', 'high', 'critical']

        # 3. Add indicator
        indicator_id = IndicatorManager.add_indicator(
            student_id, 'academic', 'low_grades', 'high', 'Failing grades detected'
        )

        # 4. Create intervention
        intervention_id = InterventionManager.create_intervention(
            student_id, 'academic', 'tutoring', 'high', 'Provide academic support'
        )

        # 5. Register coach
        coach_id = CoachingManager.register_coach('WORKFLOW_COACH', 'Workflow Coach')

        # 6. Assign student to coach
        assignment_id = CoachingManager.assign_student_to_coach(
            student_id, coach_id, 'At-risk student needs support'
        )

        # 7. Create tutoring recommendation
        tutoring_id = TutoringManager.create_tutoring_recommendation(
            student_id, 'MATH101', 'system', 'one-on-one', 'high'
        )

        # Verify all records exist
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM early_warning_profiles WHERE student_id = ?', (student_id,))
        assert cursor.fetchone() is not None

        cursor.execute('SELECT * FROM early_warning_indicators WHERE indicator_id = ?', (indicator_id,))
        assert cursor.fetchone() is not None

        cursor.execute('SELECT * FROM early_warning_interventions WHERE intervention_id = ?', (intervention_id,))
        assert cursor.fetchone() is not None

        cursor.execute('SELECT * FROM early_warning_coaching_assignments WHERE assignment_id = ?', (assignment_id,))
        assert cursor.fetchone() is not None

        cursor.execute('SELECT * FROM early_warning_tutoring_recommendations WHERE recommendation_id = ?', (tutoring_id,))
        assert cursor.fetchone() is not None

        conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
