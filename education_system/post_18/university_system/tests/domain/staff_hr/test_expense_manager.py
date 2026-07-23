"""
Tests for Expense Manager module.
Tests expense claims, approvals, reimbursements, and policy compliance.
"""

import pytest
from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import os
import tempfile

from education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager import ExpenseManager

@pytest.fixture
def test_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Create expense_categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            max_amount REAL,
            requires_receipt BOOLEAN DEFAULT 1,
            requires_approval BOOLEAN DEFAULT 1,
            approval_threshold REAL,
            is_active BOOLEAN DEFAULT 1,
            gl_code TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create expense_claims table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_claims (
            claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'GBP',
            description TEXT NOT NULL,
            expense_date TEXT NOT NULL,
            receipt_path TEXT,
            receipt_number TEXT,
            project_code TEXT,
            cost_center TEXT,
            status TEXT DEFAULT 'draft',
            submitted_date TEXT,
            notes TEXT,
            mileage_miles REAL,
            mileage_rate REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES expense_categories(category_id)
        )
    ''')

    # Create expense_approvals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_approvals (
            approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id INTEGER NOT NULL,
            approver_id TEXT NOT NULL,
            approval_level INTEGER DEFAULT 1,
            decision TEXT,
            comments TEXT,
            decision_date TEXT,
            amount_approved REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
        )
    ''')

    # Create reimbursements table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reimbursements (
            reimbursement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'GBP',
            payment_date TEXT,
            payment_method TEXT,
            reference_number TEXT,
            bank_account_last4 TEXT,
            status TEXT DEFAULT 'pending',
            processed_by TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (claim_id) REFERENCES expense_claims(claim_id)
        )
    ''')

    # Create expense_policies table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expense_policies (
            policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            max_daily_amount REAL,
            max_single_claim REAL,
            requires_pre_approval_above REAL,
            mileage_rate REAL DEFAULT 0.45,
            subsistence_rate REAL,
            applies_to_roles TEXT,
            effective_from TEXT,
            effective_to TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
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
        INSERT INTO expense_categories (name, description, max_amount, requires_receipt)
        VALUES ('Travel', 'Travel expenses', 500.00, 1)
    ''')
    cursor.execute('''
        INSERT INTO expense_categories (name, description, max_amount, requires_receipt)
        VALUES ('Meals', 'Meal expenses', 50.00, 1)
    ''')
    cursor.execute('''
        INSERT INTO expense_categories (name, description, max_amount, requires_receipt)
        VALUES ('Equipment', 'Equipment purchases', 200.00, 1)
    ''')

    # Insert default policy
    cursor.execute('''
        INSERT INTO expense_policies (name, description, max_single_claim, mileage_rate, is_active)
        VALUES ('Standard Policy', 'Default expense policy', 1000.00, 0.45, 1)
    ''')

    conn.commit()
    conn.close()

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)

class TestExpenseClaimCreation:
    """Test expense claim creation functionality."""

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.transaction')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.log_activity')
    def test_create_expense_claim_success(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test successful expense claim creation."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        claim_id = ExpenseManager.create_claim(
            user_id='EMP001',
            category_id=1,
            amount=150.00,
            description='Train ticket to London',
            expense_date='2026-01-15'
        )

        assert claim_id is not None
        assert claim_id > 0

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM expense_claims WHERE claim_id = ?', (claim_id,))
        claim = cursor.fetchone()

        assert claim is not None
        assert claim['user_id'] == 'EMP001'
        assert claim['amount'] == 150.00
        assert claim['status'] == 'draft'
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.transaction')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.log_activity')
    def test_create_mileage_claim(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a mileage expense claim."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        claim_id = ExpenseManager.create_claim(
            user_id='EMP001',
            category_id=1,
            amount=45.00,  # 100 miles * 0.45
            description='Client visit',
            expense_date='2026-01-15',
            mileage_miles=100,
            mileage_rate=0.45
        )

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM expense_claims WHERE claim_id = ?', (claim_id,))
        claim = cursor.fetchone()

        assert claim['mileage_miles'] == 100
        assert claim['mileage_rate'] == 0.45
        conn.close()

class TestExpenseClaimRetrieval:
    """Test expense claim retrieval functionality."""

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_get_user_claims(self, mock_get_conn, test_db):
        """Test retrieving all claims for a user."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test expense 1', '2026-01-10', 'submitted')
        ''')
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 2, 25.00, 'Test expense 2', '2026-01-11', 'approved')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        claims = ExpenseManager.get_user_claims('EMP001')

        assert len(claims) == 2
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_get_claim_by_id(self, mock_get_conn, test_db):
        """Test retrieving a specific claim by ID."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test expense', '2026-01-10', 'submitted')
        ''')
        claim_id = cursor.lastrowid
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        claim = ExpenseManager.get_claim(claim_id)

        assert claim is not None
        assert claim['amount'] == 100.00
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_search_claims_by_status(self, mock_get_conn, test_db):
        """Test searching claims by status."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test 1', '2026-01-10', 'submitted')
        ''')
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP002', 1, 200.00, 'Test 2', '2026-01-11', 'approved')
        ''')
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP003', 1, 300.00, 'Test 3', '2026-01-12', 'submitted')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        claims = ExpenseManager.search_claims(status='submitted')

        assert len(claims) == 2
        conn.close()

class TestExpenseApproval:
    """Test expense approval workflow."""

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.transaction')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.log_activity')
    def test_submit_claim(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test submitting an expense claim for approval."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test expense', '2026-01-10', 'draft')
        ''')
        claim_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        result = ExpenseManager.submit_claim(claim_id)

        assert result is True

        cursor.execute('SELECT status, submitted_date FROM expense_claims WHERE claim_id = ?', (claim_id,))
        claim = cursor.fetchone()
        assert claim['status'] == 'submitted'
        assert claim['submitted_date'] is not None
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.transaction')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.log_activity')
    def test_approve_claim(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test approving an expense claim."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test expense', '2026-01-10', 'submitted')
        ''')
        claim_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        result = ExpenseManager.approve_claim(
            claim_id,
            approver_id='MGR001',
            comments='Approved'
        )

        assert result is True

        cursor.execute('SELECT status FROM expense_claims WHERE claim_id = ?', (claim_id,))
        claim = cursor.fetchone()
        assert claim['status'] == 'approved'

        cursor.execute('SELECT * FROM expense_approvals WHERE claim_id = ?', (claim_id,))
        approval = cursor.fetchone()
        assert approval is not None
        assert approval['decision'] == 'approved'
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.transaction')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.log_activity')
    def test_reject_claim(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test rejecting an expense claim."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 5000.00, 'Over limit', '2026-01-10', 'submitted')
        ''')
        claim_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)
        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        result = ExpenseManager.reject_claim(
            claim_id,
            approver_id='MGR001',
            reason='Amount exceeds policy limit'
        )

        assert result is True

        cursor.execute('SELECT status FROM expense_claims WHERE claim_id = ?', (claim_id,))
        claim = cursor.fetchone()
        assert claim['status'] == 'rejected'
        conn.close()

class TestExpenseCategories:
    """Test expense category functionality."""

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_get_categories(self, mock_get_conn, test_db):
        """Test retrieving expense categories."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        categories = ExpenseManager.get_categories()

        assert len(categories) >= 3  # We inserted 3 default categories
        assert any(c['name'] == 'Travel' for c in categories)
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.transaction')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.log_activity')
    def test_create_category(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test creating a new expense category."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        category_id = ExpenseManager.create_category(
            name='Training',
            description='Training and development expenses',
            max_amount=1000.00,
            requires_receipt=True
        )

        assert category_id is not None

        cursor = conn.cursor()
        cursor.execute('SELECT * FROM expense_categories WHERE category_id = ?', (category_id,))
        category = cursor.fetchone()

        assert category['name'] == 'Training'
        assert category['max_amount'] == 1000.00
        conn.close()

class TestReimbursement:
    """Test reimbursement functionality."""

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.transaction')
    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.log_activity')
    def test_process_reimbursement(self, mock_log, mock_transaction, mock_get_conn, test_db):
        """Test processing a reimbursement."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test expense', '2026-01-10', 'approved')
        ''')
        claim_id = cursor.lastrowid
        conn.commit()

        mock_transaction.return_value.__enter__ = Mock(return_value=conn)
        mock_transaction.return_value.__exit__ = Mock(return_value=False)

        reimbursement_id = ExpenseManager.process_reimbursement(
            claim_id,
            amount=100.00,
            payment_method='bank_transfer',
            processed_by='FIN001'
        )

        assert reimbursement_id is not None

        cursor.execute('SELECT * FROM reimbursements WHERE reimbursement_id = ?', (reimbursement_id,))
        reimbursement = cursor.fetchone()

        assert reimbursement is not None
        assert reimbursement['amount'] == 100.00
        assert reimbursement['payment_method'] == 'bank_transfer'
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_get_pending_reimbursements(self, mock_get_conn, test_db):
        """Test retrieving pending reimbursements."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        # Create approved claims that need reimbursement
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test 1', '2026-01-10', 'approved')
        ''')
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP002', 1, 200.00, 'Test 2', '2026-01-11', 'approved')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        pending = ExpenseManager.get_pending_reimbursements()

        assert len(pending) == 2
        conn.close()

class TestExpenseStatistics:
    """Test expense statistics functionality."""

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_get_expense_statistics(self, mock_get_conn, test_db):
        """Test retrieving expense statistics."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 100.00, 'Test 1', '2026-01-10', 'approved')
        ''')
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP002', 1, 200.00, 'Test 2', '2026-01-11', 'submitted')
        ''')
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP003', 2, 50.00, 'Test 3', '2026-01-12', 'approved')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        stats = ExpenseManager.get_expense_statistics()

        assert stats['total_claims'] >= 3
        assert stats['total_amount'] >= 350.00
        assert 'by_status' in stats
        assert 'by_category' in stats
        conn.close()

class TestExpensePolicy:
    """Test expense policy functionality."""

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_get_active_policy(self, mock_get_conn, test_db):
        """Test retrieving active expense policy."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        policy = ExpenseManager.get_active_policy()

        assert policy is not None
        assert policy['name'] == 'Standard Policy'
        assert policy['mileage_rate'] == 0.45
        conn.close()

    @patch('education_system.post_18.university_system.modules.domain.operations.staff_hr.services.managers.expense_manager.get_connection')
    def test_check_policy_compliance(self, mock_get_conn, test_db):
        """Test policy compliance checking."""
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row

        cursor = conn.cursor()
        # Create a claim that exceeds policy limit
        cursor.execute('''
            INSERT INTO expense_claims (user_id, category_id, amount, description, expense_date, status)
            VALUES ('EMP001', 1, 5000.00, 'Over limit', '2026-01-10', 'submitted')
        ''')
        conn.commit()

        mock_get_conn.return_value.__enter__ = Mock(return_value=conn)
        mock_get_conn.return_value.__exit__ = Mock(return_value=False)

        violations = ExpenseManager.check_policy_compliance()

        assert len(violations) >= 1
        assert any('Over single claim limit' in v['violation_type'] for v in violations)
        conn.close()
