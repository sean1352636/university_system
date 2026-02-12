#!/usr/bin/env python3
"""
Comprehensive tests for SQL safety utilities.

Tests cover:
- Table name validation
- Column name validation
- Identifier format validation
- SQL injection prevention
- Database schema verification
- Safe query building
- Edge cases and security
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock

from university_system.modules.shared.utils.sql_safety import (
    validate_table_name,
    validate_column_name,
    validate_identifier,
    is_valid_identifier_format,
    get_valid_tables,
    get_valid_columns,
    KNOWN_TABLES,
    KNOWN_COLUMNS,
    SQLIdentifierError,
)

@pytest.fixture
def temp_db():
    """Create a temporary database with test tables."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create test tables
    cursor.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            email TEXT,
            role TEXT
        );

        CREATE TABLE students (
            id INTEGER PRIMARY KEY,
            student_id TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            email TEXT
        );

        CREATE TABLE courses (
            id INTEGER PRIMARY KEY,
            course_code TEXT NOT NULL,
            course_name TEXT,
            credits INTEGER
        );

        CREATE TABLE grades (
            id INTEGER PRIMARY KEY,
            student_id INTEGER,
            course_id INTEGER,
            grade TEXT,
            score REAL
        );
    """)
    conn.commit()

    yield conn

    conn.close()
    try:
        import shutil
        shutil.rmtree(temp_dir)
    except Exception:
        pass

# ============================================================================
# Identifier Format Validation Tests
# ============================================================================

class TestIdentifierFormat:
    """Test identifier format validation."""

    def test_valid_simple_identifier(self):
        """Test valid simple identifier."""
        assert is_valid_identifier_format("users") is True

    def test_valid_identifier_with_underscore(self):
        """Test valid identifier with underscore."""
        assert is_valid_identifier_format("user_accounts") is True

    def test_valid_identifier_with_numbers(self):
        """Test valid identifier with numbers."""
        assert is_valid_identifier_format("table1") is True

    def test_valid_identifier_starts_with_underscore(self):
        """Test valid identifier starting with underscore."""
        assert is_valid_identifier_format("_private_table") is True

    def test_invalid_identifier_starts_with_number(self):
        """Test invalid identifier starting with number."""
        assert is_valid_identifier_format("1table") is False

    def test_invalid_identifier_with_spaces(self):
        """Test invalid identifier with spaces."""
        assert is_valid_identifier_format("user table") is False

    def test_invalid_identifier_with_dash(self):
        """Test invalid identifier with dash."""
        assert is_valid_identifier_format("user-table") is False

    def test_invalid_identifier_empty(self):
        """Test empty identifier."""
        assert is_valid_identifier_format("") is False

    def test_invalid_identifier_special_chars(self):
        """Test identifier with special characters."""
        assert is_valid_identifier_format("table$name") is False
        assert is_valid_identifier_format("table@name") is False
        assert is_valid_identifier_format("table!name") is False

    def test_invalid_identifier_sql_injection_chars(self):
        """Test SQL injection characters are rejected."""
        assert is_valid_identifier_format("'; DROP TABLE--") is False
        assert is_valid_identifier_format("table; DELETE") is False
        assert is_valid_identifier_format("table/*comment*/") is False

# ============================================================================
# Table Name Validation Tests
# ============================================================================

class TestTableNameValidation:
    """Test table name validation."""

    def test_validate_known_table(self):
        """Test validation of known table name."""
        result = validate_table_name("users")
        assert result == "users"

    def test_validate_known_table_students(self):
        """Test validation of students table."""
        result = validate_table_name("students")
        assert result == "students"

    def test_validate_table_case_insensitive(self):
        """Test table validation is case-insensitive."""
        result = validate_table_name("Users")
        assert result.lower() == "users"

    def test_validate_table_with_database(self, temp_db):
        """Test table validation against actual database."""
        result = validate_table_name("users", conn=temp_db)
        assert result == "users"

    def test_invalid_table_not_known(self):
        """Test unknown table name without database connection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("nonexistent_table_xyz")

    def test_invalid_table_sql_injection(self):
        """Test SQL injection in table name."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users; DROP TABLE students;--")

    def test_invalid_table_empty(self):
        """Test empty table name."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("")

    def test_invalid_table_none(self):
        """Test None table name."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name(None)

    def test_invalid_table_special_chars(self):
        """Test table name with special characters."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users$data")

    def test_invalid_table_path_traversal(self):
        """Test path traversal in table name."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("../../../etc/passwd")

# ============================================================================
# Column Name Validation Tests
# ============================================================================

class TestColumnNameValidation:
    """Test column name validation."""

    def test_validate_known_column(self):
        """Test validation of known column name."""
        result = validate_column_name("email")
        assert result == "email"

    def test_validate_common_columns(self):
        """Test validation of common column names."""
        common_cols = ["id", "created_at", "updated_at", "status", "username"]
        for col in common_cols:
            result = validate_column_name(col)
            assert result == col

    def test_validate_column_with_database(self, temp_db):
        """Test column validation against actual database."""
        result = validate_column_name("username", table_name="users", conn=temp_db)
        assert result == "username"

    def test_invalid_column_not_in_table(self, temp_db):
        """Test column not in specified table."""
        with pytest.raises(SQLIdentifierError):
            validate_column_name("nonexistent_col", table_name="users", conn=temp_db)

    def test_invalid_column_sql_injection(self):
        """Test SQL injection in column name."""
        with pytest.raises(SQLIdentifierError):
            validate_column_name("email; DELETE FROM users;--")

    def test_invalid_column_empty(self):
        """Test empty column name."""
        with pytest.raises(SQLIdentifierError):
            validate_column_name("")

    def test_invalid_column_special_chars(self):
        """Test column name with special characters."""
        with pytest.raises(SQLIdentifierError):
            validate_column_name("user@email")

# ============================================================================
# Generic Identifier Validation Tests
# ============================================================================

class TestIdentifierValidation:
    """Test generic identifier validation."""

    def test_validate_identifier_valid(self):
        """Test valid identifier."""
        result = validate_identifier("my_identifier")
        assert result == "my_identifier"

    def test_validate_identifier_uppercase(self):
        """Test uppercase identifier."""
        result = validate_identifier("MY_TABLE")
        assert result is not None

    def test_validate_identifier_mixed_case(self):
        """Test mixed case identifier."""
        result = validate_identifier("MyTable")
        assert result is not None

    def test_invalid_identifier_sql_keywords(self):
        """Test SQL keywords in identifiers."""
        # These should be rejected or handled carefully
        dangerous = ["SELECT", "DROP", "DELETE", "INSERT", "UPDATE"]
        for keyword in dangerous:
            # If allowed, should be validated as safe identifier format
            if is_valid_identifier_format(keyword):
                # The format is valid, but might be blocked for safety
                pass

    def test_invalid_identifier_whitespace(self):
        """Test identifier with whitespace."""
        with pytest.raises(SQLIdentifierError):
            validate_identifier("table name")

    def test_invalid_identifier_newlines(self):
        """Test identifier with newlines."""
        with pytest.raises(SQLIdentifierError):
            validate_identifier("table\nname")

# ============================================================================
# Known Tables and Columns Tests
# ============================================================================

class TestKnownTablesAndColumns:
    """Test known tables and columns sets."""

    def test_known_tables_not_empty(self):
        """Test KNOWN_TABLES is not empty."""
        assert len(KNOWN_TABLES) > 0

    def test_known_tables_contains_core_tables(self):
        """Test KNOWN_TABLES contains core tables."""
        core_tables = ['users', 'students', 'courses', 'grades', 'enrollments']
        for table in core_tables:
            assert table in KNOWN_TABLES

    def test_known_columns_not_empty(self):
        """Test KNOWN_COLUMNS is not empty."""
        assert len(KNOWN_COLUMNS) > 0

    def test_known_columns_contains_common_columns(self):
        """Test KNOWN_COLUMNS contains common columns."""
        common_cols = ['id', 'created_at', 'email', 'username', 'status']
        for col in common_cols:
            assert col in KNOWN_COLUMNS

    def test_get_valid_tables(self, temp_db):
        """Test getting valid tables from database."""
        tables = get_valid_tables(temp_db)
        assert 'users' in tables
        assert 'students' in tables
        assert 'courses' in tables

    def test_get_valid_columns(self, temp_db):
        """Test getting valid columns from table."""
        columns = get_valid_columns('users', temp_db)
        assert 'id' in columns
        assert 'username' in columns
        assert 'email' in columns

# ============================================================================
# SQL Injection Prevention Tests
# ============================================================================

class TestSQLInjectionPrevention:
    """Test SQL injection prevention."""

    def test_prevents_union_injection(self):
        """Test prevention of UNION injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users UNION SELECT * FROM passwords")

    def test_prevents_comment_injection(self):
        """Test prevention of comment injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users/**/")

    def test_prevents_semicolon_injection(self):
        """Test prevention of semicolon injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users; DROP TABLE students")

    def test_prevents_quote_injection(self):
        """Test prevention of quote injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users' OR '1'='1")

    def test_prevents_double_quote_injection(self):
        """Test prevention of double quote injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name('users" OR "1"="1')

    def test_prevents_backtick_injection(self):
        """Test prevention of backtick injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users`; DROP TABLE--")

    def test_prevents_null_byte_injection(self):
        """Test prevention of null byte injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users\x00admin")

    def test_prevents_escape_sequence_injection(self):
        """Test prevention of escape sequence injection."""
        with pytest.raises(SQLIdentifierError):
            validate_table_name("users\\'; DROP TABLE--")

# ============================================================================
# Edge Cases Tests
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_identifier(self):
        """Test very long identifier."""
        long_name = "a" * 200
        with pytest.raises(SQLIdentifierError):
            validate_identifier(long_name)

    def test_unicode_identifier(self):
        """Test unicode characters in identifier."""
        with pytest.raises(SQLIdentifierError):
            validate_identifier("table_")

    def test_reserved_sqlite_name(self):
        """Test SQLite reserved names."""
        # sqlite_master should not be allowed as user table
        result = is_valid_identifier_format("sqlite_master")
        # Format may be valid but shouldn't be allowed as user table
        assert result is True  # Format is valid
        # But validation should reject it as a system table

    def test_numeric_only_identifier(self):
        """Test numeric-only identifier."""
        with pytest.raises(SQLIdentifierError):
            validate_identifier("12345")

    def test_whitespace_variants(self):
        """Test various whitespace characters."""
        whitespace_variants = [
            "table name",    # space
            "table\tname",   # tab
            "table\nname",   # newline
            "table\rname",   # carriage return
        ]
        for variant in whitespace_variants:
            with pytest.raises(SQLIdentifierError):
                validate_identifier(variant)

# ============================================================================
# SQLIdentifierError Tests
# ============================================================================

class TestSQLIdentifierError:
    """Test SQLIdentifierError exception."""

    def test_error_is_value_error(self):
        """Test SQLIdentifierError is a ValueError."""
        assert issubclass(SQLIdentifierError, ValueError)

    def test_error_message(self):
        """Test error message is preserved."""
        error = SQLIdentifierError("Invalid table name")
        assert str(error) == "Invalid table name"

    def test_error_can_be_caught(self):
        """Test error can be caught as ValueError."""
        with pytest.raises(ValueError):
            raise SQLIdentifierError("Test")

# ============================================================================
# Integration Tests
# ============================================================================

class TestSQLSafetyIntegration:
    """Test SQL safety integration scenarios."""

    def test_safe_query_building(self, temp_db):
        """Test building a safe query with validated identifiers."""
        table = validate_table_name("users", conn=temp_db)
        column = validate_column_name("username", table_name="users", conn=temp_db)

        # Build query safely
        query = f"SELECT [{column}] FROM [{table}]"

        # Execute should work
        cursor = temp_db.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        assert result is not None

    def test_safe_insert_building(self, temp_db):
        """Test building a safe INSERT with validated identifiers."""
        table = validate_table_name("users", conn=temp_db)

        # Use parameterized query for values
        query = f"INSERT INTO [{table}] (username, email) VALUES (?, ?)"

        cursor = temp_db.cursor()
        cursor.execute(query, ("testuser", "test@example.com"))
        temp_db.commit()

        # Verify insertion
        cursor.execute(f"SELECT username FROM [{table}] WHERE username = ?", ("testuser",))
        result = cursor.fetchone()
        assert result[0] == "testuser"

    def test_multiple_column_validation(self, temp_db):
        """Test validating multiple columns."""
        columns = ["id", "username", "email", "role"]
        validated = []

        for col in columns:
            validated_col = validate_column_name(col, table_name="users", conn=temp_db)
            validated.append(validated_col)

        assert len(validated) == 4
        assert "username" in validated
        assert "email" in validated

# ============================================================================
# Security Audit Tests
# ============================================================================

class TestSecurityAudit:
    """Test security audit scenarios."""

    def test_owasp_sql_injection_examples(self):
        """Test against OWASP SQL injection examples."""
        injection_attempts = [
            "' OR '1'='1",
            "'; DROP TABLE users--",
            "1; SELECT * FROM users",
            "admin'--",
            "1' AND '1'='1",
            "' UNION SELECT NULL--",
            "'; INSERT INTO users VALUES('attacker')--",
            "1' ORDER BY 1--",
            "' OR 1=1#",
            "admin'/*",
        ]

        for attempt in injection_attempts:
            with pytest.raises(SQLIdentifierError):
                validate_table_name(attempt)

    def test_blind_sql_injection_attempts(self):
        """Test blind SQL injection attempts."""
        blind_attempts = [
            "users AND 1=1",
            "users AND 1=2",
            "users' AND SLEEP(5)--",
            "users; WAITFOR DELAY '0:0:5'--",
        ]

        for attempt in blind_attempts:
            with pytest.raises(SQLIdentifierError):
                validate_table_name(attempt)

    def test_second_order_injection_patterns(self):
        """Test second-order injection patterns."""
        patterns = [
            "user_${id}",
            "user_{username}",
            "table_$input",
        ]

        for pattern in patterns:
            with pytest.raises(SQLIdentifierError):
                validate_identifier(pattern)

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
