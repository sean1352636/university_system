#!/usr/bin/env python3
"""
Comprehensive tests for Financial Core Module
Tests database initialization, auth setup, and menu functionality
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from education_system.university_system.modules.domain.finance.core import financial_core

@pytest.fixture
def temp_db():
    """Create a temporary database"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except (OSError, IOError):
        pass

@pytest.fixture
def mock_auth():
    """Mock authentication object"""
    auth = MagicMock()
    auth.current_user = {"username": "test_admin"}
    auth.check_permission = MagicMock(return_value=True)
    return auth

class TestDatabaseInitialization:
    """Test database initialization"""

    def test_init_enhanced_finance_db(self, temp_db):
        """Test enhanced finance database initialization"""
        with patch('university_system.modules.domain.finance.core.financial_core.get_connection') as mock_conn:
            conn = sqlite3.connect(temp_db)
            mock_conn.return_value = conn

            financial_core.init_enhanced_finance_db()

            # Verify tables were created
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            assert 'student_fees' in tables, "student_fees table should be created"
            assert 'payments' in tables, "payments table should be created"
            assert 'scholarships' in tables, "scholarships table should be created"
            assert 'exchange_rates' in tables, "exchange_rates table should be created"

            conn.close()

    def test_warn_if_table_empty(self, temp_db):
        """Test empty table warning functionality"""
        with patch('university_system.modules.domain.finance.core.financial_core.get_connection') as mock_conn:
            conn = sqlite3.connect(temp_db)
            mock_conn.return_value = conn

            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY)")
            conn.commit()

            # Should log warning for empty table
            financial_core.warn_if_table_empty(cursor, 'test_table', 'Test warning')

            conn.close()

class TestAuthSetup:
    """Test authentication setup"""

    def test_set_finance_auth(self, mock_auth):
        """Test setting finance authentication"""
        financial_core.set_finance_auth(mock_auth)
        # Should set auth without errors

class TestInitialization:
    """Test finance system initialization"""

    def test_initialize_finance(self, temp_db):
        """Test complete finance system initialization"""
        with patch('university_system.modules.domain.finance.core.financial_core.get_connection') as mock_conn, \
             patch('university_system.modules.domain.finance.core.financial_core.get_auth') as mock_get_auth, \
             patch('university_system.modules.domain.finance.core.financial_core.init_enhanced_finance_db'):

            conn = sqlite3.connect(temp_db)
            mock_conn.return_value = conn
            mock_get_auth.return_value = MagicMock()

            financial_core.initialize_finance()

            conn.close()

class TestFinanceMenu:
    """Test finance menu functionality"""

    def test_display_enhanced_finance_menu_exits(self, mock_auth):
        """Test finance menu exit"""
        with patch('university_system.modules.domain.finance.core.financial_core.auth', mock_auth), \
             patch('builtins.input', side_effect=['29']):

            financial_core.display_enhanced_finance_menu()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
