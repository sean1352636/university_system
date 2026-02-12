"""
Tests for scholarship_manager.py module

This module tests the ScholarshipManager class including:
- Creating and managing scholarships
- Submitting and reviewing scholarship applications
- Awarding scholarships
- Managing external scholarships
- Checking renewal eligibility
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import tempfile
import os
import json
from datetime import datetime, date, timedelta
from university_system.modules.domain.finance.services.financial_aid.scholarship_manager import ScholarshipManager

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)

    # Create test database schema
    conn = sqlite3.connect(temp_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email TEXT,
            gpa REAL
        );

        CREATE TABLE IF NOT EXISTS scholarships (
            scholarship_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            scholarship_name TEXT,
            description TEXT,
            amount REAL NOT NULL,
            amount_type TEXT DEFAULT 'fixed',
            scholarship_type TEXT DEFAULT 'merit',
            eligibility_criteria TEXT,
            min_gpa REAL,
            required_major TEXT,
            required_class_year TEXT,
            deadline DATE,
            renewable BOOLEAN DEFAULT 0,
            max_renewals INTEGER,
            available_count INTEGER,
            total_awarded INTEGER DEFAULT 0,
            donor_name TEXT,
            is_active BOOLEAN DEFAULT 1,
            academic_year TEXT,
            criteria TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scholarship_applications (
            app_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending',
            essay_text TEXT,
            recommendation_1 TEXT,
            recommendation_2 TEXT,
            transcript_url TEXT,
            resume_url TEXT,
            gpa REAL,
            reviewer_id INTEGER,
            review_date TIMESTAMP,
            review_score REAL,
            review_comments TEXT,
            FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id),
            UNIQUE(scholarship_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS scholarship_awards (
            award_id INTEGER PRIMARY KEY AUTOINCREMENT,
            scholarship_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            amount REAL NOT NULL,
            award_date DATE,
            status TEXT DEFAULT 'active',
            is_renewable BOOLEAN DEFAULT 0,
            renewal_deadline DATE,
            renewal_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (scholarship_id) REFERENCES scholarships(scholarship_id),
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );

        CREATE TABLE IF NOT EXISTS external_scholarships (
            external_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            provider_name TEXT NOT NULL,
            scholarship_name TEXT,
            amount REAL NOT NULL,
            academic_year TEXT NOT NULL,
            disbursement_date DATE,
            is_recurring BOOLEAN DEFAULT 0,
            contact_email TEXT,
            contact_phone TEXT,
            documentation_url TEXT,
            reported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        );

        CREATE TABLE IF NOT EXISTS renewal_requirements (
            requirement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            award_id INTEGER NOT NULL,
            academic_year TEXT NOT NULL,
            gpa_required REAL,
            credit_hours_required INTEGER,
            enrollment_status_required TEXT,
            service_hours_required INTEGER,
            other_requirements TEXT,
            verification_deadline DATE,
            is_met BOOLEAN,
            verified_by INTEGER,
            verified_date TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (award_id) REFERENCES scholarship_awards(award_id) ON DELETE CASCADE
        );
    """)

    # Insert test data
    cursor.executescript("""
        INSERT INTO students (student_id, first_name, last_name, email, gpa)
        VALUES
            (1, 'John', 'Doe', 'john@test.com', 3.8),
            (2, 'Jane', 'Smith', 'jane@test.com', 3.5),
            (3, 'Bob', 'Johnson', 'bob@test.com', 3.2);

        INSERT INTO scholarships (name, scholarship_name, description, amount, min_gpa, deadline, is_active, academic_year, criteria)
        VALUES
            ('Merit Scholarship', 'Merit Scholarship', 'For high-achieving students', 5000.0, 3.5, date('now', '+30 days'), 1, '2024-2025', 'GPA >= 3.5'),
            ('Need-Based Grant', 'Need-Based Grant', 'For students with financial need', 3000.0, NULL, date('now', '+60 days'), 1, '2024-2025', 'Financial need'),
            ('Expired Scholarship', 'Expired Scholarship', 'This one has passed', 2000.0, 3.0, date('now', '-10 days'), 0, '2023-2024', 'GPA >= 3.0');
    """)

    conn.commit()
    conn.close()

    yield temp_path

    # Cleanup
    try:
        os.unlink(temp_path)
    except (OSError, IOError):
        pass

@pytest.fixture
def scholarship_manager(temp_db):
    """Create ScholarshipManager instance with test database"""
    return ScholarshipManager(db_path=temp_db)

class TestScholarshipCreation:
    """Test suite for scholarship creation"""

    def test_create_scholarship(self, scholarship_manager):
        """Test creating a new scholarship"""
        scholarship_id = scholarship_manager.create_scholarship(
            name='Test Scholarship',
            amount=4000.0,
            description='Test scholarship description',
            scholarship_type='merit',
            min_gpa=3.0,
            deadline=date(2024, 12, 31),
            academic_year='2024-2025',
            criteria='Test criteria'
        )

        assert scholarship_id is not None
        assert scholarship_id > 0

    def test_create_scholarship_minimal(self, scholarship_manager):
        """Test creating scholarship with minimal required fields"""
        scholarship_id = scholarship_manager.create_scholarship(
            name='Minimal Scholarship',
            amount=1000.0,
            academic_year='2024-2025',
            criteria='Minimal criteria'
        )

        assert scholarship_id is not None

    def test_create_renewable_scholarship(self, scholarship_manager):
        """Test creating a renewable scholarship"""
        scholarship_id = scholarship_manager.create_scholarship(
            name='Renewable Scholarship',
            amount=3000.0,
            renewable=True,
            max_renewals=3,
            academic_year='2024-2025',
            criteria='Renewable criteria'
        )

        assert scholarship_id is not None

class TestScholarshipApplications:
    """Test suite for scholarship applications"""

    def test_submit_application(self, scholarship_manager):
        """Test submitting a scholarship application"""
        app_id = scholarship_manager.submit_application(
            scholarship_id=1,
            student_id=1,
            essay_text='My scholarship essay...',
            gpa=3.8
        )

        assert app_id is not None
        assert app_id > 0

    def test_submit_application_with_dict(self, scholarship_manager):
        """Test submitting application with application_data dict"""
        application_data = {
            'essay': 'My compelling essay',
            'gpa': 3.5,
            'transcript_url': 'http://example.com/transcript.pdf',
            'resume_url': 'http://example.com/resume.pdf'
        }

        app_id = scholarship_manager.submit_application(
            scholarship_id=2,
            student_id=2,
            application_data=application_data
        )

        assert app_id is not None

    def test_submit_duplicate_application(self, scholarship_manager):
        """Test submitting duplicate application (should fail due to unique constraint)"""
        # First application
        app_id1 = scholarship_manager.submit_application(
            scholarship_id=1,
            student_id=3,
            essay_text='First essay'
        )

        assert app_id1 is not None

        # Duplicate application (same scholarship_id and student_id)
        app_id2 = scholarship_manager.submit_application(
            scholarship_id=1,
            student_id=3,
            essay_text='Second essay - should fail'
        )

        assert app_id2 is None

    def test_review_application(self, scholarship_manager):
        """Test reviewing a scholarship application"""
        # Submit application first
        app_id = scholarship_manager.submit_application(
            scholarship_id=1,
            student_id=1,
            essay_text='Review me'
        )

        # Review it
        result = scholarship_manager.review_application(
            app_id=app_id,
            reviewer_id=1,
            status='awarded',
            review_score=85.5,
            review_comments='Excellent application'
        )

        assert result is True

    def test_review_application_invalid_status(self, scholarship_manager):
        """Test reviewing application with invalid status"""
        app_id = scholarship_manager.submit_application(
            scholarship_id=1,
            student_id=2,
            essay_text='Test'
        )

        result = scholarship_manager.review_application(
            app_id=app_id,
            reviewer_id=1,
            status='invalid_status'
        )

        assert result is False

    def test_review_nonexistent_application(self, scholarship_manager):
        """Test reviewing non-existent application"""
        result = scholarship_manager.review_application(
            app_id=99999,
            reviewer_id=1,
            status='awarded'
        )

        assert result is False

class TestScholarshipAwards:
    """Test suite for scholarship awards"""

    def test_award_scholarship(self, scholarship_manager):
        """Test awarding a scholarship to a student"""
        award_id = scholarship_manager.award_scholarship(
            scholarship_id=1,
            student_id=1,
            academic_year='2024-2025',
            amount=5000.0
        )

        assert award_id is not None
        assert award_id > 0

    def test_award_renewable_scholarship(self, scholarship_manager):
        """Test awarding a renewable scholarship"""
        award_id = scholarship_manager.award_scholarship(
            scholarship_id=1,
            student_id=2,
            academic_year='2024-2025',
            amount=5000.0,
            is_renewable=True
        )

        assert award_id is not None

    def test_award_updates_total_awarded(self, scholarship_manager, temp_db):
        """Test that awarding updates scholarship total_awarded count"""
        # Award scholarship
        scholarship_manager.award_scholarship(
            scholarship_id=1,
            student_id=1,
            academic_year='2024-2025',
            amount=5000.0
        )

        # Check that total_awarded increased
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT total_awarded FROM scholarships WHERE scholarship_id = 1")
        total_awarded = cursor.fetchone()[0]

        assert total_awarded > 0

        conn.close()

class TestScholarshipRetrieval:
    """Test suite for retrieving scholarship data"""

    def test_get_available_scholarships(self, scholarship_manager):
        """Test getting all available scholarships"""
        scholarships = scholarship_manager.get_available_scholarships()

        assert isinstance(scholarships, list)
        assert len(scholarships) > 0

        # Check that expired scholarships are excluded
        for scholarship in scholarships:
            assert scholarship.get('is_active') == 1

    def test_get_available_scholarships_with_gpa(self, scholarship_manager):
        """Test filtering scholarships by GPA"""
        scholarships = scholarship_manager.get_available_scholarships(min_gpa=3.5)

        assert isinstance(scholarships, list)

        # All returned scholarships should have min_gpa <= 3.5 or NULL
        for scholarship in scholarships:
            min_gpa = scholarship.get('min_gpa')
            if min_gpa is not None:
                assert min_gpa <= 3.5

    def test_get_student_awards(self, scholarship_manager):
        """Test getting awards for a specific student"""
        # Award a scholarship first
        scholarship_manager.award_scholarship(
            scholarship_id=1,
            student_id=1,
            academic_year='2024-2025',
            amount=5000.0
        )

        # Get student awards
        awards = scholarship_manager.get_student_awards(student_id=1)

        assert isinstance(awards, list)
        assert len(awards) > 0
        assert awards[0]['student_id'] == 1

    def test_get_student_awards_no_awards(self, scholarship_manager):
        """Test getting awards for student with no awards"""
        awards = scholarship_manager.get_student_awards(student_id=999)

        assert isinstance(awards, list)
        assert len(awards) == 0

class TestExternalScholarships:
    """Test suite for external scholarship management"""

    def test_add_external_scholarship(self, scholarship_manager):
        """Test adding an external scholarship"""
        external_id = scholarship_manager.add_external_scholarship(
            student_id=1,
            provider_name='External Foundation',
            amount=2500.0,
            academic_year='2024-2025',
            scholarship_name='External Scholarship'
        )

        assert external_id is not None
        assert external_id > 0

    def test_add_recurring_external_scholarship(self, scholarship_manager):
        """Test adding a recurring external scholarship"""
        external_id = scholarship_manager.add_external_scholarship(
            student_id=2,
            provider_name='Recurring Foundation',
            amount=3000.0,
            academic_year='2024-2025',
            is_recurring=True
        )

        assert external_id is not None

    def test_add_external_scholarship_minimal(self, scholarship_manager):
        """Test adding external scholarship with minimal fields"""
        external_id = scholarship_manager.add_external_scholarship(
            student_id=3,
            provider_name='Minimal Foundation',
            amount=1000.0,
            academic_year='2024-2025'
        )

        assert external_id is not None

class TestRenewalEligibility:
    """Test suite for scholarship renewal eligibility"""

    def test_check_renewal_eligibility_with_requirements(self, scholarship_manager, temp_db):
        """Test checking renewal eligibility with requirements"""
        # Award scholarship and create renewal requirements
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO scholarship_awards
            (scholarship_id, student_id, academic_year, amount, is_renewable)
            VALUES (1, 1, '2024-2025', 5000.0, 1)
        """)
        award_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO renewal_requirements
            (award_id, academic_year, gpa_required, credit_hours_required, enrollment_status_required)
            VALUES (?, '2025-2026', 3.5, 30, 'full_time')
        """, (award_id,))

        conn.commit()
        conn.close()

        # Check eligibility with passing criteria
        result = scholarship_manager.check_renewal_eligibility(
            award_id=award_id,
            current_gpa=3.8,
            credit_hours=32,
            enrollment_status='full_time'
        )

        assert isinstance(result, dict)
        assert 'eligible' in result
        assert result['eligible'] is True

    def test_check_renewal_eligibility_failing_gpa(self, scholarship_manager, temp_db):
        """Test renewal eligibility when GPA requirement not met"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO scholarship_awards
            (scholarship_id, student_id, academic_year, amount, is_renewable)
            VALUES (1, 2, '2024-2025', 5000.0, 1)
        """)
        award_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO renewal_requirements
            (award_id, academic_year, gpa_required)
            VALUES (?, '2025-2026', 3.5)
        """, (award_id,))

        conn.commit()
        conn.close()

        # Check eligibility with failing GPA
        result = scholarship_manager.check_renewal_eligibility(
            award_id=award_id,
            current_gpa=3.2,  # Below requirement
            credit_hours=30,
            enrollment_status='full_time'
        )

        assert result['eligible'] is False

    def test_check_renewal_eligibility_no_requirements(self, scholarship_manager, temp_db):
        """Test renewal eligibility when no requirements exist"""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO scholarship_awards
            (scholarship_id, student_id, academic_year, amount, is_renewable)
            VALUES (1, 3, '2024-2025', 5000.0, 1)
        """)
        award_id = cursor.lastrowid

        conn.commit()
        conn.close()

        result = scholarship_manager.check_renewal_eligibility(
            award_id=award_id,
            current_gpa=3.0,
            credit_hours=24,
            enrollment_status='part_time'
        )

        assert result['eligible'] is True
        assert 'No specific requirements' in result['reason']

class TestErrorHandling:
    """Test suite for error handling"""

    def test_create_scholarship_invalid_db(self):
        """Test scholarship creation with invalid database"""
        manager = ScholarshipManager(db_path='/invalid/path/db.db')

        scholarship_id = manager.create_scholarship(
            name='Test',
            amount=1000.0,
            academic_year='2024-2025',
            criteria='Test'
        )

        assert scholarship_id is None

    def test_submit_application_invalid_db(self):
        """Test application submission with invalid database"""
        manager = ScholarshipManager(db_path='/invalid/path/db.db')

        app_id = manager.submit_application(
            scholarship_id=1,
            student_id=1
        )

        assert app_id is None

    def test_award_scholarship_invalid_db(self):
        """Test scholarship award with invalid database"""
        manager = ScholarshipManager(db_path='/invalid/path/db.db')

        award_id = manager.award_scholarship(
            scholarship_id=1,
            student_id=1,
            academic_year='2024-2025',
            amount=1000.0
        )

        assert award_id is None

class TestDatabaseIntegrity:
    """Test database operations and integrity"""

    def test_manager_initialization(self, temp_db):
        """Test ScholarshipManager initialization"""
        manager = ScholarshipManager(db_path=temp_db)
        assert manager.db_path == temp_db

    def test_manager_default_db_path(self):
        """Test ScholarshipManager with default database path"""
        manager = ScholarshipManager()
        assert manager.db_path is not None

    def test_connection_method(self, scholarship_manager):
        """Test _get_connection method"""
        conn = scholarship_manager._get_connection()
        assert conn is not None

        # Test connection works
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1

        conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
