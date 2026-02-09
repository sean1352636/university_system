"""
Tests for Student Affairs Accessibility & Accommodation Tools Service

Tests cover:
- AccessibilityProfileManager (create, read profiles)
- AccommodationRequestManager (submit, review, query requests)
- ExamAccommodationManager (create, retrieve accommodations)
- AssistiveTechManager (request, fulfill assistive technology)
"""

import pytest
import sqlite3
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.domain.student_affairs.services.accessibility_tools import (
    AccessibilityProfileManager,
    AccommodationRequestManager,
    ExamAccommodationManager,
    AssistiveTechManager,
    display_accessibility_menu,
)


@pytest.fixture
def setup_database():
    """Set up test database with required tables"""
    conn = get_connection()
    cursor = conn.cursor()

    # Create accessibility_profiles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accessibility_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            disabilities TEXT,
            accommodations TEXT,
            assistive_technologies TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create accommodation_requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accommodation_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            accommodation_type TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by INTEGER,
            review_date TEXT,
            review_notes TEXT,
            requested_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create accommodation_approvals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accommodation_approvals (
            approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            approved_by INTEGER NOT NULL,
            notes TEXT,
            approval_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES accommodation_requests (request_id)
        )
    ''')

    # Create exam_accommodations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exam_accommodations (
            accommodation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            exam_id INTEGER,
            extended_time INTEGER DEFAULT 0,
            separate_room INTEGER DEFAULT 0,
            assistive_technology TEXT,
            reader_scribe INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create assistive_tech_requests table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assistive_tech_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            technology_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            requested_date TEXT DEFAULT CURRENT_TIMESTAMP,
            fulfilled_date TEXT
        )
    ''')

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM accessibility_profiles')
    cursor.execute('DELETE FROM accommodation_requests')
    cursor.execute('DELETE FROM accommodation_approvals')
    cursor.execute('DELETE FROM exam_accommodations')
    cursor.execute('DELETE FROM assistive_tech_requests')
    conn.commit()
    conn.close()


class TestAccessibilityProfileManager:
    """Tests for AccessibilityProfileManager"""

    def test_create_new_profile(self, setup_database):
        """Test creating a new accessibility profile"""
        user_id = 1001
        disabilities = ['Visual Impairment', 'Dyslexia']
        accommodations = ['Screen Reader', 'Extended Time']
        assistive_tech = ['JAWS', 'Dragon NaturallySpeaking']

        profile_id = AccessibilityProfileManager.create_profile(
            user_id, disabilities, accommodations, assistive_tech
        )

        assert profile_id is not None
        assert isinstance(profile_id, int)

        # Verify profile was created
        profile = AccessibilityProfileManager.get_profile(user_id)
        assert profile is not None
        assert profile['user_id'] == user_id
        assert set(profile['disabilities']) == set(disabilities)
        assert set(profile['accommodations']) == set(accommodations)

    def test_update_existing_profile(self, setup_database):
        """Test updating an existing profile"""
        user_id = 1002

        # Create initial profile
        initial_disabilities = ['Mobility Impairment']
        AccessibilityProfileManager.create_profile(user_id, initial_disabilities, [], [])

        # Update profile
        updated_disabilities = ['Mobility Impairment', 'Chronic Pain']
        updated_accommodations = ['Accessible Seating', 'Elevator Access']

        profile_id = AccessibilityProfileManager.create_profile(
            user_id, updated_disabilities, updated_accommodations, []
        )

        # Verify update
        profile = AccessibilityProfileManager.get_profile(user_id)
        assert profile is not None
        assert len(profile['disabilities']) == 2
        assert 'Chronic Pain' in profile['disabilities']
        assert len(profile['accommodations']) == 2

    def test_get_nonexistent_profile(self, setup_database):
        """Test retrieving a profile that doesn't exist"""
        profile = AccessibilityProfileManager.get_profile(9999)
        assert profile is None

    def test_create_profile_with_empty_lists(self, setup_database):
        """Test creating a profile with empty lists"""
        user_id = 1003
        profile_id = AccessibilityProfileManager.create_profile(user_id, [], [], [])

        assert profile_id is not None
        profile = AccessibilityProfileManager.get_profile(user_id)
        assert profile['disabilities'] == []
        assert profile['accommodations'] == []
        assert profile['assistive_technologies'] == []


class TestAccommodationRequestManager:
    """Tests for AccommodationRequestManager"""

    def test_submit_request(self, setup_database):
        """Test submitting an accommodation request"""
        student_id = 2001
        accommodation_type = 'Exam Accommodation'
        description = 'Need extended time for all exams due to dyslexia'

        request_id = AccommodationRequestManager.submit_request(
            student_id, accommodation_type, description
        )

        assert request_id is not None
        assert isinstance(request_id, int)

        # Verify request was created
        requests = AccommodationRequestManager.get_requests(student_id=student_id)
        assert len(requests) == 1
        assert requests[0]['status'] == 'pending'
        assert requests[0]['accommodation_type'] == accommodation_type

    def test_review_request_approved(self, setup_database):
        """Test approving an accommodation request"""
        student_id = 2002
        request_id = AccommodationRequestManager.submit_request(
            student_id, 'Note-taking Services', 'Need note-taker for lectures'
        )

        reviewer_id = 5001
        review_notes = 'Approved based on medical documentation'

        AccommodationRequestManager.review_request(
            request_id, reviewer_id, 'approved', review_notes
        )

        # Verify status update
        requests = AccommodationRequestManager.get_requests(student_id=student_id)
        assert requests[0]['status'] == 'approved'
        assert requests[0]['reviewed_by'] == reviewer_id
        assert requests[0]['review_notes'] == review_notes

        # Verify approval record created
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM accommodation_approvals WHERE request_id = ?', (request_id,))
        approval = cursor.fetchone()
        conn.close()

        assert approval is not None

    def test_review_request_rejected(self, setup_database):
        """Test rejecting an accommodation request"""
        student_id = 2003
        request_id = AccommodationRequestManager.submit_request(
            student_id, 'Priority Registration', 'Want early registration'
        )

        AccommodationRequestManager.review_request(
            request_id, 5002, 'rejected', 'Insufficient documentation provided'
        )

        requests = AccommodationRequestManager.get_requests(student_id=student_id)
        assert requests[0]['status'] == 'rejected'

    def test_get_requests_by_status(self, setup_database):
        """Test filtering requests by status"""
        # Create multiple requests
        AccommodationRequestManager.submit_request(3001, 'Type A', 'Description A')
        AccommodationRequestManager.submit_request(3002, 'Type B', 'Description B')

        request_id = AccommodationRequestManager.submit_request(3003, 'Type C', 'Description C')
        AccommodationRequestManager.review_request(request_id, 5001, 'approved', 'OK')

        # Test filtering
        pending_requests = AccommodationRequestManager.get_requests(status='pending')
        approved_requests = AccommodationRequestManager.get_requests(status='approved')

        assert len(pending_requests) == 2
        assert len(approved_requests) == 1

    def test_get_requests_by_student(self, setup_database):
        """Test retrieving all requests for a specific student"""
        student_id = 3004

        AccommodationRequestManager.submit_request(student_id, 'Type 1', 'Desc 1')
        AccommodationRequestManager.submit_request(student_id, 'Type 2', 'Desc 2')
        AccommodationRequestManager.submit_request(3005, 'Type 3', 'Desc 3')  # Different student

        requests = AccommodationRequestManager.get_requests(student_id=student_id)
        assert len(requests) == 2
        assert all(r['student_id'] == student_id for r in requests)


class TestExamAccommodationManager:
    """Tests for ExamAccommodationManager"""

    def test_create_exam_accommodation(self, setup_database):
        """Test creating an exam accommodation"""
        student_id = 4001
        exam_id = 101
        extended_time = 50  # 50% extra time
        separate_room = True
        assistive_technology = 'Screen Reader'
        reader_scribe = False

        accommodation_id = ExamAccommodationManager.create_accommodation(
            student_id, exam_id, extended_time, separate_room,
            assistive_technology, reader_scribe
        )

        assert accommodation_id is not None

        # Verify accommodation was created
        accommodations = ExamAccommodationManager.get_accommodations(student_id=student_id)
        assert len(accommodations) == 1
        assert accommodations[0]['extended_time'] == extended_time
        assert accommodations[0]['separate_room'] == 1  # SQLite boolean as int
        assert accommodations[0]['assistive_technology'] == assistive_technology

    def test_create_general_accommodation(self, setup_database):
        """Test creating a general accommodation (not exam-specific)"""
        student_id = 4002

        accommodation_id = ExamAccommodationManager.create_accommodation(
            student_id, None, 30, False, '', True
        )

        assert accommodation_id is not None
        accommodations = ExamAccommodationManager.get_accommodations(student_id=student_id)
        assert len(accommodations) == 1
        assert accommodations[0]['exam_id'] is None
        assert accommodations[0]['reader_scribe'] == 1

    def test_get_all_active_accommodations(self, setup_database):
        """Test retrieving all active accommodations"""
        ExamAccommodationManager.create_accommodation(5001, 201, 25, True, '', False)
        ExamAccommodationManager.create_accommodation(5002, 202, 50, False, 'JAWS', True)

        all_accommodations = ExamAccommodationManager.get_accommodations()
        assert len(all_accommodations) >= 2
        assert all(a['status'] == 'active' for a in all_accommodations)

    def test_multiple_accommodations_per_student(self, setup_database):
        """Test student can have multiple exam accommodations"""
        student_id = 4003

        ExamAccommodationManager.create_accommodation(student_id, 301, 25, True, '', False)
        ExamAccommodationManager.create_accommodation(student_id, 302, 50, True, 'Screen Reader', True)

        accommodations = ExamAccommodationManager.get_accommodations(student_id=student_id)
        assert len(accommodations) == 2


class TestAssistiveTechManager:
    """Tests for AssistiveTechManager"""

    def test_submit_tech_request(self, setup_database):
        """Test submitting an assistive technology request"""
        student_id = 6001
        technology_type = 'Screen Magnifier'

        request_id = AssistiveTechManager.submit_request(student_id, technology_type)

        assert request_id is not None

        # Verify request was created
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM assistive_tech_requests WHERE request_id = ?', (request_id,))
        request = cursor.fetchone()
        conn.close()

        assert request is not None
        assert request['status'] == 'pending'
        assert request['technology_type'] == technology_type

    def test_fulfill_request(self, setup_database):
        """Test fulfilling an assistive technology request"""
        student_id = 6002
        request_id = AssistiveTechManager.submit_request(student_id, 'Dragon Speech Software')

        AssistiveTechManager.fulfill_request(request_id)

        # Verify status update
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM assistive_tech_requests WHERE request_id = ?', (request_id,))
        request = cursor.fetchone()
        conn.close()

        assert request['status'] == 'fulfilled'
        assert request['fulfilled_date'] is not None

    def test_multiple_requests_same_student(self, setup_database):
        """Test student can submit multiple technology requests"""
        student_id = 6003

        request1 = AssistiveTechManager.submit_request(student_id, 'Screen Reader')
        request2 = AssistiveTechManager.submit_request(student_id, 'Ergonomic Keyboard')

        assert request1 != request2

        # Fulfill one
        AssistiveTechManager.fulfill_request(request1)

        # Verify both exist but different statuses
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM assistive_tech_requests WHERE student_id = ?', (student_id,))
        requests = cursor.fetchall()
        conn.close()

        assert len(requests) == 2
        statuses = [r['status'] for r in requests]
        assert 'fulfilled' in statuses
        assert 'pending' in statuses


class TestAccessibilityMenuDisplay:
    """Tests for CLI menu display function"""

    def test_display_menu_exit(self, setup_database):
        """Test displaying menu and exiting"""
        with patch('builtins.input', return_value='6'):
            with patch('builtins.print') as mock_print:
                mock_auth = MagicMock()
                display_accessibility_menu(mock_auth)

                # Verify menu was printed
                assert mock_print.called

    def test_display_menu_feature_selection(self, setup_database):
        """Test selecting menu features"""
        with patch('builtins.input', side_effect=['1', '2', '3', '4', '5', '6']):
            with patch('builtins.print') as mock_print:
                mock_auth = MagicMock()
                display_accessibility_menu(mock_auth)

                # Should print feature availability messages
                assert mock_print.called


class TestErrorHandling:
    """Tests for error handling"""

    def test_create_profile_invalid_user_id(self, setup_database):
        """Test error handling with invalid user ID"""
        with pytest.raises(Exception):
            AccessibilityProfileManager.create_profile(None, [], [], [])

    def test_review_nonexistent_request(self, setup_database):
        """Test reviewing a request that doesn't exist"""
        # This should complete without error but not update anything
        AccommodationRequestManager.review_request(99999, 5001, 'approved', 'Test')

    def test_fulfill_nonexistent_request(self, setup_database):
        """Test fulfilling a request that doesn't exist"""
        # Should complete without error
        AssistiveTechManager.fulfill_request(99999)


class TestIntegration:
    """Integration tests"""

    def test_full_accommodation_workflow(self, setup_database):
        """Test complete workflow from profile to accommodation"""
        student_id = 7001
        user_id = 7001

        # 1. Create accessibility profile
        disabilities = ['Learning Disability']
        accommodations = ['Extended Time', 'Quiet Room']
        profile_id = AccessibilityProfileManager.create_profile(
            user_id, disabilities, accommodations, []
        )

        # 2. Submit accommodation request
        request_id = AccommodationRequestManager.submit_request(
            student_id, 'Exam Accommodation',
            'Need 50% extended time and separate room for exams'
        )

        # 3. Review and approve request
        AccommodationRequestManager.review_request(
            request_id, 8001, 'approved', 'Approved based on profile'
        )

        # 4. Create exam accommodation
        accommodation_id = ExamAccommodationManager.create_accommodation(
            student_id, 401, 50, True, '', False
        )

        # 5. Verify all records exist
        profile = AccessibilityProfileManager.get_profile(user_id)
        requests = AccommodationRequestManager.get_requests(student_id=student_id)
        exam_accommodations = ExamAccommodationManager.get_accommodations(student_id=student_id)

        assert profile is not None
        assert len(requests) == 1
        assert requests[0]['status'] == 'approved'
        assert len(exam_accommodations) == 1

    def test_assistive_tech_request_workflow(self, setup_database):
        """Test complete assistive technology request workflow"""
        student_id = 7002

        # 1. Submit request
        request_id = AssistiveTechManager.submit_request(student_id, 'Screen Reader Software')

        # 2. Verify pending status
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT status FROM assistive_tech_requests WHERE request_id = ?', (request_id,))
        status = cursor.fetchone()['status']
        assert status == 'pending'

        # 3. Fulfill request
        AssistiveTechManager.fulfill_request(request_id)

        # 4. Verify fulfilled
        cursor.execute('SELECT status FROM assistive_tech_requests WHERE request_id = ?', (request_id,))
        status = cursor.fetchone()['status']
        conn.close()

        assert status == 'fulfilled'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
