"""
Tests for Contract Manager module.
Tests contract creation, amendments, probation tracking, and renewal alerts.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

from university_system.modules.domain.staff_hr.services.managers.contract_manager import ContractManager


@pytest.fixture
def test_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    # Initialize the database with required tables
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create staff_contracts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff_contracts (
            contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            contract_type TEXT NOT NULL DEFAULT 'permanent',
            start_date TEXT NOT NULL,
            end_date TEXT,
            salary REAL,
            salary_currency TEXT DEFAULT 'GBP',
            pay_frequency TEXT DEFAULT 'monthly',
            terms TEXT,
            status TEXT DEFAULT 'active',
            renewal_date TEXT,
            probation_end_date TEXT,
            notice_period_days INTEGER DEFAULT 30,
            working_hours_per_week REAL DEFAULT 37.5,
            department TEXT,
            job_title TEXT,
            manager_id TEXT,
            document_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT
        )
    ''')

    # Create contract_amendments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contract_amendments (
            amendment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_id INTEGER NOT NULL,
            change_type TEXT NOT NULL,
            field_changed TEXT,
            old_value TEXT,
            new_value TEXT,
            effective_date TEXT NOT NULL,
            reason TEXT,
            approved_by TEXT,
            approved_date TEXT,
            status TEXT DEFAULT 'pending',
            document_path TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
        )
    ''')

    # Create probation_reviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS probation_reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            contract_id INTEGER,
            review_date TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            review_type TEXT DEFAULT 'mid-probation',
            outcome TEXT,
            performance_rating INTEGER,
            strengths TEXT,
            areas_for_improvement TEXT,
            comments TEXT,
            objectives_met TEXT,
            recommendation TEXT,
            next_review_date TEXT,
            probation_extended BOOLEAN DEFAULT 0,
            extension_reason TEXT,
            extension_end_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (contract_id) REFERENCES staff_contracts(contract_id)
        )
    ''')

    # Create activity_log table for logging
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

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_db_connection(test_db):
    """Mock the database connection to use test database."""
    def get_test_connection():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn

    return get_test_connection


class TestContractCreation:
    """Test contract creation functionality."""

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.transaction')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.log_activity')
    def test_create_contract_success(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test successful contract creation."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        contract_id = ContractManager.create_contract(
            user_id='EMP001',
            contract_type='permanent',
            start_date='2026-01-15',
            department='Engineering',
            job_title='Software Developer',
            salary=50000.00
        )

        assert contract_id is not None
        assert contract_id > 0

        # Verify contract was created
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM staff_contracts WHERE contract_id = ?', (contract_id,))
        contract = cursor.fetchone()

        assert contract is not None
        assert contract['user_id'] == 'EMP001'
        assert contract['contract_type'] == 'permanent'
        assert contract['department'] == 'Engineering'
        assert contract['status'] == 'active'
        conn.close()

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.transaction')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.log_activity')
    def test_create_fixed_term_contract(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a fixed-term contract with end date."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        contract_id = ContractManager.create_contract(
            user_id='EMP002',
            contract_type='fixed-term',
            start_date='2026-01-15',
            end_date='2027-01-14',
            department='Marketing',
            job_title='Marketing Specialist'
        )

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM staff_contracts WHERE contract_id = ?', (contract_id,))
        contract = cursor.fetchone()

        assert contract['contract_type'] == 'fixed-term'
        assert contract['end_date'] == '2027-01-14'
        conn.close()

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.transaction')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.log_activity')
    def test_create_contract_with_probation(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a contract with probation period."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        contract_id = ContractManager.create_contract(
            user_id='EMP003',
            contract_type='permanent',
            start_date='2026-01-15',
            probation_end_date='2026-04-15',
            department='HR',
            job_title='HR Assistant'
        )

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM staff_contracts WHERE contract_id = ?', (contract_id,))
        contract = cursor.fetchone()

        assert contract['probation_end_date'] == '2026-04-15'
        conn.close()


class TestContractRetrieval:
    """Test contract retrieval functionality."""

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    def test_get_active_contract(self, mock_get_conn, test_db):
        """Test retrieving active contract for a user."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        # Insert test contract
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status, department, job_title)
            VALUES ('EMP001', 'permanent', '2026-01-01', 'active', 'IT', 'Developer')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        contract = ContractManager.get_active_contract('EMP001')

        assert contract is not None
        assert contract['user_id'] == 'EMP001'
        assert contract['status'] == 'active'
        conn.close()

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    def test_get_active_contract_none_exists(self, mock_get_conn, test_db):
        """Test retrieving active contract when none exists."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        contract = ContractManager.get_active_contract('NONEXISTENT')

        assert contract is None
        conn.close()

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    def test_get_user_contracts_with_history(self, mock_get_conn, test_db):
        """Test retrieving all contracts for a user including inactive."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        # Insert multiple contracts
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status)
            VALUES ('EMP001', 'temporary', '2024-01-01', 'terminated')
        ''')
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status)
            VALUES ('EMP001', 'permanent', '2025-01-01', 'active')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        contracts = ContractManager.get_user_contracts('EMP001', include_inactive=True)

        assert len(contracts) == 2
        conn.close()


class TestContractAmendments:
    """Test contract amendment functionality."""

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.transaction')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.log_activity')
    def test_create_amendment(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a contract amendment."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        # Insert a contract first
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status, salary)
            VALUES ('EMP001', 'permanent', '2026-01-01', 'active', 50000)
        ''')
        contract_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        amendment_id = ContractManager.create_amendment(
            contract_id,
            change_type='salary',
            field_changed='salary',
            old_value='50000',
            new_value='55000',
            effective_date='2026-06-01',
            reason='Annual salary review'
        )

        assert amendment_id is not None
        assert amendment_id > 0

        # Verify amendment was created
        cursor.execute('SELECT * FROM contract_amendments WHERE amendment_id = ?', (amendment_id,))
        amendment = cursor.fetchone()

        assert amendment is not None
        assert amendment['change_type'] == 'salary'
        assert amendment['new_value'] == '55000'
        conn.close()


class TestProbationManagement:
    """Test probation-related functionality."""

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.transaction')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.log_activity')
    def test_create_probation_review(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a probation review."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        # Insert a contract first
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status, probation_end_date)
            VALUES ('EMP001', 'permanent', '2026-01-01', 'active', '2026-04-01')
        ''')
        contract_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        review_id = ContractManager.create_probation_review(
            user_id='EMP001',
            contract_id=contract_id,
            review_date='2026-02-15',
            reviewer_id='MGR001',
            review_type='mid-probation',
            performance_rating=4,
            outcome='pass',
            comments='Good progress'
        )

        assert review_id is not None
        assert review_id > 0

        # Verify review was created
        cursor.execute('SELECT * FROM probation_reviews WHERE review_id = ?', (review_id,))
        review = cursor.fetchone()

        assert review is not None
        assert review['performance_rating'] == 4
        assert review['outcome'] == 'pass'
        conn.close()

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    def test_get_probation_reviews(self, mock_get_conn, test_db):
        """Test retrieving probation reviews for a user."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO probation_reviews (user_id, review_date, reviewer_id, review_type, outcome)
            VALUES ('EMP001', '2026-02-15', 'MGR001', 'mid-probation', 'pass')
        ''')
        cursor.execute('''
            INSERT INTO probation_reviews (user_id, review_date, reviewer_id, review_type, outcome)
            VALUES ('EMP001', '2026-03-15', 'MGR001', 'final', 'pass')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        reviews = ContractManager.get_probation_reviews('EMP001')

        assert len(reviews) == 2
        conn.close()

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.transaction')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.log_activity')
    def test_extend_probation(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test extending probation period."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status, probation_end_date)
            VALUES ('EMP001', 'permanent', '2026-01-01', 'active', '2026-04-01')
        ''')
        contract_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        result = ContractManager.extend_probation(
            contract_id,
            new_end_date='2026-06-01',
            reason='Additional training required',
            extended_by='MGR001'
        )

        assert result is True

        cursor.execute('SELECT probation_end_date FROM staff_contracts WHERE contract_id = ?', (contract_id,))
        contract = cursor.fetchone()
        assert contract['probation_end_date'] == '2026-06-01'
        conn.close()


class TestExpiringContracts:
    """Test contract expiry alert functionality."""

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    def test_get_expiring_contracts(self, mock_get_conn, test_db):
        """Test retrieving contracts expiring within specified days."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        # Insert contracts with various end dates
        cursor = conn.cursor()
        today = datetime.now()

        # Contract expiring in 30 days
        expiring_date = (today + timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, end_date, status)
            VALUES ('EMP001', 'fixed-term', '2025-01-01', ?, 'active')
        ''', (expiring_date,))

        # Contract expiring in 100 days (should not be included in 90-day search)
        far_date = (today + timedelta(days=100)).strftime('%Y-%m-%d')
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, end_date, status)
            VALUES ('EMP002', 'fixed-term', '2025-01-01', ?, 'active')
        ''', (far_date,))

        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        expiring = ContractManager.get_expiring_contracts(days=90)

        assert len(expiring) == 1
        assert expiring[0]['user_id'] == 'EMP001'
        conn.close()


class TestContractStatistics:
    """Test contract statistics functionality."""

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    def test_get_contract_statistics(self, mock_get_conn, test_db):
        """Test retrieving contract statistics."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        today = datetime.now()

        # Insert various contracts
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status)
            VALUES ('EMP001', 'permanent', '2026-01-01', 'active')
        ''')
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status)
            VALUES ('EMP002', 'permanent', '2026-01-01', 'active')
        ''')
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status, probation_end_date)
            VALUES ('EMP003', 'permanent', '2026-01-01', 'active', ?)
        ''', ((today + timedelta(days=30)).strftime('%Y-%m-%d'),))

        # Expiring contract
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, end_date, status)
            VALUES ('EMP004', 'fixed-term', '2025-01-01', ?, 'active')
        ''', ((today + timedelta(days=20)).strftime('%Y-%m-%d'),))

        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        stats = ContractManager.get_contract_statistics()

        assert stats['total_active'] == 4
        assert stats['expiring_30_days'] >= 1
        assert stats['in_probation'] >= 1
        assert 'by_type' in stats
        conn.close()


class TestContractTermination:
    """Test contract termination functionality."""

    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.get_connection')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.transaction')
    @patch('university_system.modules.domain.staff_hr.services.managers.contract_manager.log_activity')
    def test_terminate_contract(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test terminating a contract."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO staff_contracts (user_id, contract_type, start_date, status)
            VALUES ('EMP001', 'permanent', '2026-01-01', 'active')
        ''')
        contract_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        result = ContractManager.terminate_contract(
            contract_id,
            termination_date='2026-06-30',
            reason='Resignation',
            terminated_by='HR001'
        )

        assert result is True

        cursor.execute('SELECT status FROM staff_contracts WHERE contract_id = ?', (contract_id,))
        contract = cursor.fetchone()
        assert contract['status'] == 'terminated'
        conn.close()
