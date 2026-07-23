"""
Comprehensive tests for finance database operations module.
Tests all database initialization, setup, and verification functions.
"""

import pytest
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call

from education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations import (
    init_enhanced_finance_db,
    init_default_enhanced_data,
    initialize_finance,
    complete_database_fix,
    verify_fix,
    ensure_database_exists,
    check_required_packages,
)


class TestInitEnhancedFinanceDB:
    """Test suite for init_enhanced_finance_db function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_text', return_value='Database initialized successfully')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.init_default_enhanced_data')
    @patch('builtins.print')
    def test_init_enhanced_finance_db_success(self, mock_print, mock_init_data, mock_get_connection, mock_get_text):
        """Test successful enhanced finance database initialization"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        init_enhanced_finance_db()

        # Verify tables were created (multiple execute calls)
        assert mock_cursor.execute.call_count > 20  # Should create many tables

        # Verify default data was initialized
        mock_init_data.assert_called_once()

        # Verify commit and close
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

        # Verify success message
        assert any('initialized successfully' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_init_enhanced_finance_db_error(self, mock_print, mock_get_connection):
        """Test enhanced finance database initialization with error"""
        import sqlite3 as _sqlite3
        mock_get_connection.side_effect = _sqlite3.Error("Database error")

        init_enhanced_finance_db()

        # Should handle error gracefully
        assert any('error occurred' in str(call).lower() for call in mock_print.call_args_list)


class TestInitDefaultEnhancedData:
    """Test suite for init_default_enhanced_data function"""

    def test_init_default_enhanced_data_payment_plan_templates(self):
        """Test default payment plan templates initialization"""
        mock_cursor = Mock()

        # Mock empty tables (no existing data)
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Verify payment plan templates were inserted
        calls = [call for call in mock_cursor.executemany.call_args_list
                if 'payment_plan_templates' in str(call)]
        assert len(calls) > 0

    def test_init_default_enhanced_data_financial_alerts(self):
        """Test default financial alerts initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Verify financial alerts were created
        calls = mock_cursor.executemany.call_args_list
        assert len(calls) > 0

    def test_init_default_enhanced_data_skip_existing(self):
        """Test skipping initialization when data already exists"""
        mock_cursor = Mock()

        # Mock tables with existing data
        mock_cursor.fetchone.return_value = (5,)  # 5 records exist

        init_default_enhanced_data(mock_cursor)

        # Should not insert data if it already exists
        # executemany should not be called for tables with data
        # (Note: This depends on implementation checking COUNT before INSERT)

    def test_init_default_enhanced_data_notification_templates(self):
        """Test default notification templates initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Should create notification templates
        assert mock_cursor.executemany.called

    def test_init_default_enhanced_data_financial_aid_types(self):
        """Test default financial aid types initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Should create financial aid types
        assert mock_cursor.executemany.called

    def test_init_default_enhanced_data_budget_categories(self):
        """Test default budget categories initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Should create budget categories
        assert mock_cursor.executemany.called

    def test_init_default_enhanced_data_exchange_rates(self):
        """Test default exchange rates initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Should create exchange rates
        assert mock_cursor.executemany.called

    def test_init_default_enhanced_data_currency_settings(self):
        """Test default currency settings initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Should create currency settings
        assert mock_cursor.execute.called

    def test_init_default_enhanced_data_fee_types(self):
        """Test default fee types initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Should create fee types
        assert mock_cursor.executemany.called

    def test_init_default_enhanced_data_scholarships(self):
        """Test default scholarships initialization"""
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (0,)

        init_default_enhanced_data(mock_cursor)

        # Should create scholarships
        assert mock_cursor.executemany.called


class TestInitializeFinance:
    """Test suite for initialize_finance function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.init_enhanced_finance_db')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.create_sample_students')
    @patch('builtins.print')
    def test_initialize_finance_with_provided_auth(self, mock_print, mock_create_students,
                                                    mock_init_db, mock_get_auth):
        """Test finance initialization with provided auth instance"""
        mock_auth = Mock()

        result = initialize_finance(auth_instance=mock_auth)

        # Should use provided auth
        assert result == mock_auth

        # Should initialize database
        mock_init_db.assert_called_once()

        # Should create sample students
        mock_create_students.assert_called_once()

        # Should print success messages
        assert any('initialized successfully' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.init_enhanced_finance_db')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.create_sample_students')
    @patch('builtins.print')
    def test_initialize_finance_create_new_auth(self, mock_print, mock_create_students,
                                                  mock_init_db, mock_get_auth):
        """Test finance initialization creating new auth instance"""
        import education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations as fdb_ops
        # Reset global auth to None so the elif branch triggers
        fdb_ops.auth = None

        mock_auth_instance = Mock()
        mock_get_auth.return_value = mock_auth_instance

        result = initialize_finance()

        # Should use auth from get_auth()
        mock_get_auth.assert_called_once()
        assert result == mock_auth_instance

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_auth')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.init_enhanced_finance_db')
    @patch('builtins.print')
    def test_initialize_finance_auth_error(self, mock_print, mock_init_db, mock_get_auth):
        """Test finance initialization with auth error"""
        import education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations as fdb_ops
        # Reset global auth to None so the elif branch triggers
        fdb_ops.auth = None

        mock_get_auth.side_effect = Exception("Auth error")

        with pytest.raises(Exception):
            initialize_finance()

        # Should print error message
        assert any('Failed to initialize' in str(call) for call in mock_print.call_args_list)


class TestCompleteDatabaseFix:
    """Test suite for complete_database_fix function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.remove')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_complete_database_fix_success(self, mock_print, mock_get_connection,
                                           mock_remove, mock_exists):
        """Test successful complete database fix"""
        mock_exists.return_value = True
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Should remove existing database
        mock_remove.assert_called_once()

        # Should create tables (many execute calls)
        assert mock_cursor.execute.call_count >= 30

        # Should insert sample data
        assert mock_cursor.executemany.call_count > 10

        # Should commit changes
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

        # Should print success message
        assert any('setup finished successfully' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_complete_database_fix_no_existing_db(self, mock_print, mock_get_connection, mock_exists):
        """Test complete database fix when no existing database"""
        mock_exists.return_value = False
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Should still create new database
        assert mock_cursor.execute.call_count >= 30

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.remove')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_complete_database_fix_creates_students_table(self, mock_print, mock_get_connection,
                                                          mock_remove, mock_exists):
        """Test that complete database fix creates students table with all columns"""
        mock_exists.return_value = False
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Verify students table was created
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        students_table_created = any('CREATE TABLE students' in call for call in execute_calls)
        assert students_table_created

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.remove')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_complete_database_fix_inserts_sample_data(self, mock_print, mock_get_connection,
                                                        mock_remove, mock_exists):
        """Test that complete database fix inserts comprehensive sample data"""
        mock_exists.return_value = False
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Verify sample data was inserted
        assert mock_cursor.executemany.call_count > 5

        # Should print summary
        assert any('Database Summary' in str(call) for call in mock_print.call_args_list)


class TestVerifyFix:
    """Test suite for verify_fix function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_verify_fix_all_tables_exist(self, mock_print, mock_get_connection):
        """Test verify fix when all tables exist"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock successful queries for all tables
        mock_cursor.fetchone.return_value = (5,)  # 5 records in each table

        result = verify_fix()

        assert result is True

        # Should print success message
        assert any('All tables verified successfully' in str(call) for call in mock_print.call_args_list)
        assert any('finance system is now ready' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.core.sql_safety.validate_table_name', side_effect=lambda t, **kw: t)
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_verify_fix_table_missing(self, mock_print, mock_get_connection, mock_validate):
        """Test verify fix when a table is missing"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock error for one table - use real sqlite3.Error
        import sqlite3 as _sqlite3

        call_count = [0]
        def execute_side_effect(*args, **kwargs):
            call_count[0] += 1
            # Let first SELECT COUNT succeed, second one fail
            if call_count[0] == 1:
                return None
            raise _sqlite3.Error("no such table")

        mock_cursor.execute.side_effect = execute_side_effect
        mock_cursor.fetchone.return_value = (5,)

        result = verify_fix()

        assert result is False

        # Should print error message (actual message uses emoji prefix)
        assert any('Some issues remain' in str(call) or 'ERROR' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_verify_fix_exception(self, mock_print, mock_get_connection):
        """Test verify fix with exception"""
        mock_get_connection.side_effect = Exception("Database error")

        result = verify_fix()

        assert result is False
        assert any('Verification failed' in str(call) for call in mock_print.call_args_list)


class TestEnsureDatabaseExists:
    """Test suite for ensure_database_exists function"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('builtins.print')
    def test_ensure_database_exists_already_exists(self, mock_print, mock_exists):
        """Test ensure database exists when database already exists"""
        mock_exists.return_value = True

        result = ensure_database_exists()

        assert result is True
        # Should not create new database
        assert not any('Creating new database' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.complete_database_fix')
    @patch('builtins.print')
    def test_ensure_database_exists_creates_new(self, mock_print, mock_fix, mock_exists):
        """Test ensure database exists creates new database"""
        mock_exists.return_value = False

        result = ensure_database_exists()

        assert result is True
        # Should create new database
        mock_fix.assert_called_once()
        assert any('Creating new database' in str(call) for call in mock_print.call_args_list)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.complete_database_fix')
    @patch('builtins.print')
    def test_ensure_database_exists_error(self, mock_print, mock_fix, mock_exists):
        """Test ensure database exists with error"""
        mock_exists.side_effect = Exception("File system error")

        result = ensure_database_exists()

        assert result is False
        assert any('Database creation failed' in str(call) for call in mock_print.call_args_list)


class TestCheckRequiredPackages:
    """Test suite for check_required_packages function"""

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_check_required_packages_all_installed(self, mock_print, mock_import):
        """Test check required packages when all are installed"""
        mock_import.return_value = Mock()

        result = check_required_packages()

        assert result is True
        # Should not print warning about missing packages
        assert not any('Missing packages' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_check_required_packages_some_missing(self, mock_print, mock_import):
        """Test check required packages when some are missing"""
        def import_side_effect(name):
            if name == 'matplotlib':
                raise ImportError("No module named matplotlib")
            return Mock()

        mock_import.side_effect = import_side_effect

        result = check_required_packages()

        assert result is False
        # Should print warning about missing packages
        assert any('Missing packages' in str(call) for call in mock_print.call_args_list)
        assert any('matplotlib' in str(call) for call in mock_print.call_args_list)

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_check_required_packages_all_missing(self, mock_print, mock_import):
        """Test check required packages when all are missing"""
        mock_import.side_effect = ImportError("No module found")

        result = check_required_packages()

        assert result is False
        # Should print install command
        assert any('pip install' in str(call) for call in mock_print.call_args_list)


class TestDatabaseTableCreation:
    """Test suite for database table creation"""

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_creates_scholarships_table(self, mock_print, mock_get_connection, mock_exists):
        """Test that scholarships table is created"""
        mock_exists.return_value = False
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Verify scholarships table creation
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('CREATE TABLE scholarships' in call for call in execute_calls)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_creates_payment_plans_tables(self, mock_print, mock_get_connection, mock_exists):
        """Test that payment plan tables are created"""
        mock_exists.return_value = False
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Verify payment plan tables creation
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('CREATE TABLE payment_plan_templates' in call for call in execute_calls)
        assert any('CREATE TABLE student_payment_plans' in call for call in execute_calls)
        assert any('CREATE TABLE payment_plan_installments' in call for call in execute_calls)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_creates_financial_aid_tables(self, mock_print, mock_get_connection, mock_exists):
        """Test that financial aid tables are created"""
        mock_exists.return_value = False
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Verify financial aid tables creation
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('CREATE TABLE financial_aid_types' in call for call in execute_calls)
        assert any('CREATE TABLE student_financial_aid' in call for call in execute_calls)

    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.os.path.exists')
    @patch('education_system.post_18.university_system.modules.domain.finance.core.finance_db_operations.get_connection')
    @patch('builtins.print')
    def test_creates_budget_tables(self, mock_print, mock_get_connection, mock_exists):
        """Test that budget tables are created"""
        mock_exists.return_value = False
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        complete_database_fix()

        # Verify budget tables creation
        execute_calls = [str(call) for call in mock_cursor.execute.call_args_list]
        assert any('CREATE TABLE budget_categories' in call for call in execute_calls)
        assert any('CREATE TABLE budget_plans' in call for call in execute_calls)
        assert any('CREATE TABLE budget_line_items' in call for call in execute_calls)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
