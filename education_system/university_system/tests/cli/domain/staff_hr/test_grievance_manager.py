"""
Tests for Grievance Manager module.
Tests grievance filing, investigation, disciplinary actions, and appeals.
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import os
import tempfile

from education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager import GrievanceManager

@pytest.fixture
def test_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create grievance_categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grievance_categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            severity_level INTEGER DEFAULT 1,
            requires_investigation BOOLEAN DEFAULT 1,
            sla_days INTEGER DEFAULT 30,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create grievances table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grievances (
            grievance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_number TEXT UNIQUE,
            complainant_id TEXT NOT NULL,
            respondent_id TEXT,
            category_id INTEGER,
            category_other TEXT,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            is_anonymous BOOLEAN DEFAULT 0,
            is_confidential BOOLEAN DEFAULT 1,
            status TEXT DEFAULT 'submitted',
            priority TEXT DEFAULT 'normal',
            assigned_to TEXT,
            filed_date TEXT NOT NULL,
            acknowledged_date TEXT,
            investigation_start_date TEXT,
            resolution_date TEXT,
            resolution_type TEXT,
            resolution_summary TEXT,
            outcome TEXT,
            appeal_deadline TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES grievance_categories(category_id)
        )
    ''')

    # Create grievance_actions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grievance_actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grievance_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            action_date TEXT NOT NULL,
            taken_by TEXT NOT NULL,
            details TEXT,
            outcome TEXT,
            next_action TEXT,
            next_action_date TEXT,
            documents_path TEXT,
            is_visible_to_complainant BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
        )
    ''')

    # Create grievance_meetings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grievance_meetings (
            meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
            grievance_id INTEGER NOT NULL,
            meeting_date TEXT NOT NULL,
            meeting_time TEXT,
            location TEXT,
            attendees TEXT,
            purpose TEXT,
            minutes TEXT,
            outcomes TEXT,
            follow_up_actions TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
        )
    ''')

    # Create disciplinary_records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disciplinary_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_number TEXT UNIQUE,
            user_id TEXT NOT NULL,
            offense_type TEXT NOT NULL,
            offense_category TEXT,
            severity TEXT DEFAULT 'minor',
            description TEXT NOT NULL,
            date_occurred TEXT NOT NULL,
            date_reported TEXT,
            reported_by TEXT,
            witnesses TEXT,
            evidence_path TEXT,
            status TEXT DEFAULT 'under_review',
            investigation_notes TEXT,
            is_confidential BOOLEAN DEFAULT 1,
            previous_warnings INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create disciplinary_actions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disciplinary_actions (
            action_id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            action_level TEXT,
            effective_date TEXT NOT NULL,
            end_date TEXT,
            duration_days INTEGER,
            imposed_by TEXT NOT NULL,
            reason TEXT,
            conditions TEXT,
            appeal_deadline TEXT,
            appeal_submitted BOOLEAN DEFAULT 0,
            appeal_outcome TEXT,
            document_path TEXT,
            acknowledged_by_employee BOOLEAN DEFAULT 0,
            acknowledged_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (record_id) REFERENCES disciplinary_records(record_id)
        )
    ''')

    # Create disciplinary_appeals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS disciplinary_appeals (
            appeal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER NOT NULL,
            appellant_id TEXT NOT NULL,
            appeal_date TEXT NOT NULL,
            grounds TEXT NOT NULL,
            supporting_documents TEXT,
            status TEXT DEFAULT 'submitted',
            hearing_date TEXT,
            panel_members TEXT,
            outcome TEXT,
            outcome_date TEXT,
            outcome_details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (action_id) REFERENCES disciplinary_actions(action_id)
        )
    ''')

    # Create activity_log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            entity_type TEXT,
            entity_id TEXT,
            user_id TEXT,
            details TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Insert default categories
    cursor.execute('''
        INSERT INTO grievance_categories (name, description, severity_level, sla_days)
        VALUES ('Harassment', 'Workplace harassment', 3, 14)
    ''')
    cursor.execute('''
        INSERT INTO grievance_categories (name, description, severity_level, sla_days)
        VALUES ('Discrimination', 'Discrimination based on protected characteristics', 3, 14)
    ''')
    cursor.execute('''
        INSERT INTO grievance_categories (name, description, severity_level, sla_days)
        VALUES ('Unfair Treatment', 'Perceived unfair treatment', 2, 21)
    ''')

    conn.commit()
    conn.close()

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)

class TestGrievanceCreation:
    """Test grievance filing functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_create_grievance_success(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test successful grievance creation."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        grievance_id = GrievanceManager.create_grievance(
            complainant_id='EMP001',
            category_id=1,
            subject='Workplace harassment complaint',
            description='Details of the complaint...',
            respondent_id='EMP002'
        )

        assert grievance_id is not None
        assert grievance_id > 0

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM grievances WHERE grievance_id = ?', (grievance_id,))
        grievance = cursor.fetchone()

        assert grievance is not None
        assert grievance['complainant_id'] == 'EMP001'
        assert grievance['status'] == 'submitted'
        assert grievance['reference_number'] is not None
        conn.close()

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_create_anonymous_grievance(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test filing an anonymous grievance."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        grievance_id = GrievanceManager.create_grievance(
            complainant_id='EMP001',
            category_id=1,
            subject='Anonymous complaint',
            description='Details...',
            is_anonymous=True
        )

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM grievances WHERE grievance_id = ?', (grievance_id,))
        grievance = cursor.fetchone()

        assert grievance['is_anonymous'] == 1
        conn.close()

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_create_grievance_with_category_name(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating grievance with category name instead of ID."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        grievance_id = GrievanceManager.create_grievance(
            complainant_id='EMP001',
            category='Harassment',  # Using name instead of ID
            subject='Harassment complaint',
            description='Details...'
        )

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM grievances WHERE grievance_id = ?', (grievance_id,))
        grievance = cursor.fetchone()

        assert grievance['category_id'] == 1  # Harassment category ID
        conn.close()

class TestGrievanceRetrieval:
    """Test grievance retrieval functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    def test_get_user_grievances(self, mock_get_conn, test_db):
        """Test retrieving grievances for a user."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-001', 'EMP001', 1, 'Test 1', 'Details 1', '2026-01-10', 'submitted')
        ''')
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-002', 'EMP001', 2, 'Test 2', 'Details 2', '2026-01-11', 'under_investigation')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        grievances = GrievanceManager.get_user_grievances('EMP001')

        assert len(grievances) == 2
        conn.close()

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    def test_search_grievances_by_status(self, mock_get_conn, test_db):
        """Test searching grievances by status."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-001', 'EMP001', 1, 'Test 1', 'Details', '2026-01-10', 'submitted')
        ''')
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-002', 'EMP002', 1, 'Test 2', 'Details', '2026-01-11', 'resolved')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        grievances = GrievanceManager.search_grievances(status='submitted')

        assert len(grievances) == 1
        assert grievances[0]['reference_number'] == 'GRV-001'
        conn.close()

class TestGrievanceActions:
    """Test grievance action functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_add_action(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test adding an action to a grievance."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-001', 'EMP001', 1, 'Test', 'Details', '2026-01-10', 'submitted')
        ''')
        grievance_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        action_id = GrievanceManager.add_action(
            grievance_id,
            action_type='investigation_started',
            taken_by='HR001',
            details='Investigation commenced'
        )

        assert action_id is not None

        cursor.execute('SELECT * FROM grievance_actions WHERE action_id = ?', (action_id,))
        action = cursor.fetchone()

        assert action['action_type'] == 'investigation_started'
        conn.close()

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_escalate_grievance(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test escalating a grievance."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status, priority)
            VALUES ('GRV-001', 'EMP001', 1, 'Test', 'Details', '2026-01-10', 'submitted', 'normal')
        ''')
        grievance_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        result = GrievanceManager.escalate_grievance(
            grievance_id,
            reason='No response within SLA',
            escalated_by='HR001'
        )

        assert result is True

        cursor.execute('SELECT status, priority FROM grievances WHERE grievance_id = ?', (grievance_id,))
        grievance = cursor.fetchone()

        assert grievance['status'] == 'escalated'
        assert grievance['priority'] == 'high'
        conn.close()

class TestGrievanceResolution:
    """Test grievance resolution functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_resolve_grievance(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test resolving a grievance."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-001', 'EMP001', 1, 'Test', 'Details', '2026-01-10', 'under_investigation')
        ''')
        grievance_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        result = GrievanceManager.resolve_grievance(
            grievance_id,
            resolver_id='HR001',
            resolution_type='mediation',
            resolution_summary='Issue resolved through mediation',
            outcome='upheld'
        )

        assert result is True

        cursor.execute('SELECT status, resolution_type, outcome FROM grievances WHERE grievance_id = ?', (grievance_id,))
        grievance = cursor.fetchone()

        assert grievance['status'] == 'resolved'
        assert grievance['resolution_type'] == 'mediation'
        assert grievance['outcome'] == 'upheld'
        conn.close()

class TestDisciplinaryRecords:
    """Test disciplinary record functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_create_disciplinary_record(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a disciplinary record."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        record_id = GrievanceManager.create_disciplinary_record(
            user_id='EMP001',
            offense_type='misconduct',
            severity='minor',
            description='Late to work multiple times',
            date_occurred='2026-01-15',
            reported_by='MGR001'
        )

        assert record_id is not None

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM disciplinary_records WHERE record_id = ?', (record_id,))
        record = cursor.fetchone()

        assert record['user_id'] == 'EMP001'
        assert record['offense_type'] == 'misconduct'
        assert record['severity'] == 'minor'
        conn.close()

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    def test_get_user_disciplinary_history(self, mock_get_conn, test_db):
        """Test retrieving disciplinary history for a user."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO disciplinary_records (reference_number, user_id, offense_type, severity, description, date_occurred)
            VALUES ('DIS-001', 'EMP001', 'misconduct', 'minor', 'Late to work', '2026-01-10')
        ''')
        cursor.execute('''
            INSERT INTO disciplinary_records (reference_number, user_id, offense_type, severity, description, date_occurred)
            VALUES ('DIS-002', 'EMP001', 'policy_violation', 'moderate', 'Policy breach', '2026-01-15')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        records = GrievanceManager.get_user_disciplinary_history('EMP001')

        assert len(records) == 2
        conn.close()

class TestDisciplinaryActions:
    """Test disciplinary action functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_create_disciplinary_action(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a disciplinary action."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO disciplinary_records (reference_number, user_id, offense_type, severity, description, date_occurred)
            VALUES ('DIS-001', 'EMP001', 'misconduct', 'moderate', 'Repeated lateness', '2026-01-10')
        ''')
        record_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        action_id = GrievanceManager.create_disciplinary_action(
            record_id,
            action_type='written_warning',
            effective_date='2026-01-20',
            imposed_by='HR001',
            reason='Multiple instances of lateness'
        )

        assert action_id is not None

        cursor.execute('SELECT * FROM disciplinary_actions WHERE action_id = ?', (action_id,))
        action = cursor.fetchone()

        assert action['action_type'] == 'written_warning'
        conn.close()

class TestAppeals:
    """Test appeal functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.transaction')
    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.log_activity')
    def test_file_appeal(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test filing an appeal."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO disciplinary_records (reference_number, user_id, offense_type, severity, description, date_occurred)
            VALUES ('DIS-001', 'EMP001', 'misconduct', 'moderate', 'Test', '2026-01-10')
        ''')
        record_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO disciplinary_actions (record_id, action_type, effective_date, imposed_by)
            VALUES (?, 'written_warning', '2026-01-20', 'HR001')
        ''', (record_id,))
        action_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        appeal_id = GrievanceManager.file_appeal(
            action_id,
            appellant_id='EMP001',
            grounds='The decision was made without hearing my side'
        )

        assert appeal_id is not None

        cursor.execute('SELECT * FROM disciplinary_appeals WHERE appeal_id = ?', (appeal_id,))
        appeal = cursor.fetchone()

        assert appeal['appellant_id'] == 'EMP001'
        assert appeal['status'] == 'submitted'
        conn.close()

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    def test_get_pending_appeals(self, mock_get_conn, test_db):
        """Test retrieving pending appeals."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO disciplinary_records (reference_number, user_id, offense_type, severity, description, date_occurred)
            VALUES ('DIS-001', 'EMP001', 'misconduct', 'moderate', 'Test', '2026-01-10')
        ''')
        record_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO disciplinary_actions (record_id, action_type, effective_date, imposed_by)
            VALUES (?, 'written_warning', '2026-01-20', 'HR001')
        ''', (record_id,))
        action_id = cursor.lastrowid
        cursor.execute('''
            INSERT INTO disciplinary_appeals (action_id, appellant_id, appeal_date, grounds, status)
            VALUES (?, 'EMP001', '2026-01-25', 'Unfair decision', 'submitted')
        ''', (action_id,))
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        appeals = GrievanceManager.get_pending_appeals()

        assert len(appeals) == 1
        conn.close()

class TestGrievanceStatistics:
    """Test grievance statistics functionality."""

    @patch('education_system.university_system.modules.domain.staff_comms.staff_hr.services.managers.grievance_manager.get_connection')
    def test_get_grievance_statistics(self, mock_get_conn, test_db):
        """Test retrieving grievance statistics."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-001', 'EMP001', 1, 'Test 1', 'Details', '2026-01-10', 'submitted')
        ''')
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-002', 'EMP002', 2, 'Test 2', 'Details', '2026-01-11', 'resolved')
        ''')
        cursor.execute('''
            INSERT INTO grievances (reference_number, complainant_id, category_id, subject, description, filed_date, status)
            VALUES ('GRV-003', 'EMP003', 1, 'Test 3', 'Details', '2026-01-12', 'under_investigation')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        stats = GrievanceManager.get_grievance_statistics()

        assert stats['total'] >= 3
        assert 'by_status' in stats
        assert 'by_category' in stats
        conn.close()
