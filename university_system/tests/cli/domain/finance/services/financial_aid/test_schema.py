"""
Tests for schema.py module

This module tests the financial aid database schema creation:
- Schema definition validation
- Table creation
- Index creation
- Foreign key constraints
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
import tempfile
import os
from university_system.modules.domain.finance.services.financial_aid.schema import (
    FINANCIAL_AID_SCHEMA,
    create_financial_aid_tables
)

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(temp_fd)
    yield temp_path
    try:
        os.unlink(temp_path)
    except (OSError, IOError):
        pass

class TestSchemaCreation:
    """Test suite for schema creation"""

    def test_create_financial_aid_tables(self, temp_db, capsys):
        """Test creating all financial aid tables"""
        conn = sqlite3.connect(temp_db)

        create_financial_aid_tables(conn)

        captured = capsys.readouterr()
        assert "created successfully" in captured.out.lower()

        conn.close()

    def test_schema_string_not_empty(self):
        """Test that schema string is not empty"""
        assert FINANCIAL_AID_SCHEMA is not None
        assert len(FINANCIAL_AID_SCHEMA) > 0
        assert "CREATE TABLE" in FINANCIAL_AID_SCHEMA

    def test_all_required_tables_in_schema(self):
        """Test that all required tables are defined in schema"""
        required_tables = [
            'financial_aid_applications',
            'fafsa_data',
            'aid_packages',
            'aid_components',
            'scholarships',
            'scholarship_applications',
            'scholarship_awards',
            'disbursements',
            'renewal_requirements',
            'compliance_reports',
            'external_scholarships',
            'payment_schedules'
        ]

        for table in required_tables:
            assert table in FINANCIAL_AID_SCHEMA

class TestTableStructure:
    """Test suite for table structure validation"""

    def test_financial_aid_applications_table(self, temp_db):
        """Test financial_aid_applications table structure"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(financial_aid_applications)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        # Check required columns exist
        assert 'application_id' in columns
        assert 'student_id' in columns
        assert 'academic_year' in columns
        assert 'status' in columns
        assert 'family_income' in columns
        assert 'household_size' in columns

        conn.close()

    def test_fafsa_data_table(self, temp_db):
        """Test fafsa_data table structure"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(fafsa_data)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'fafsa_id' in columns
        assert 'student_id' in columns
        assert 'academic_year' in columns
        assert 'efc' in columns
        assert 'sai' in columns
        assert 'pell_eligible' in columns

        conn.close()

    def test_scholarships_table(self, temp_db):
        """Test scholarships table structure"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(scholarships)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'scholarship_id' in columns
        assert 'name' in columns
        assert 'amount' in columns
        assert 'scholarship_type' in columns
        assert 'eligibility_criteria' in columns

        conn.close()

    def test_aid_packages_table(self, temp_db):
        """Test aid_packages table structure"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(aid_packages)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'package_id' in columns
        assert 'student_id' in columns
        assert 'academic_year' in columns
        assert 'total_aid_amount' in columns
        assert 'package_status' in columns

        conn.close()

    def test_disbursements_table(self, temp_db):
        """Test disbursements table structure"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(disbursements)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        assert 'disbursement_id' in columns
        assert 'student_id' in columns
        assert 'amount' in columns
        assert 'disbursement_date' in columns
        assert 'status' in columns

        conn.close()

class TestIndexes:
    """Test suite for index creation"""

    def test_indexes_created(self, temp_db):
        """Test that all required indexes are created"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_%'
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        # Check that some important indexes exist
        expected_indexes = [
            'idx_fin_aid_apps_student',
            'idx_fafsa_student',
            'idx_aid_packages_student',
            'idx_scholarships_active',
            'idx_disbursements_student'
        ]

        for idx in expected_indexes:
            assert idx in indexes, f"Index {idx} not found"

        conn.close()

    def test_index_on_student_applications(self, temp_db):
        """Test index on financial_aid_applications.student_id"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='financial_aid_applications'
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        assert 'idx_fin_aid_apps_student' in indexes

        conn.close()

class TestConstraints:
    """Test suite for foreign key and unique constraints"""

    def test_foreign_key_enforcement(self, temp_db):
        """Test that foreign keys are properly defined"""
        conn = sqlite3.connect(temp_db)
        conn.execute("PRAGMA foreign_keys = ON")
        create_financial_aid_tables(conn)

        cursor = conn.cursor()

        # Check foreign keys on financial_aid_applications
        cursor.execute("PRAGMA foreign_key_list(financial_aid_applications)")
        fk_list = cursor.fetchall()

        # Should have at least one FK to students
        assert len(fk_list) > 0

        conn.close()

    def test_unique_constraints(self, temp_db):
        """Test unique constraints"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        # Create a minimal students table for testing
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT
            )
        """)
        cursor.execute("INSERT INTO students VALUES (1, 'John', 'Doe')")

        # Test unique constraint on fafsa_data (student_id, academic_year)
        cursor.execute("""
            INSERT INTO fafsa_data (student_id, academic_year, efc, submission_date)
            VALUES (1, '2024-2025', 5000, '2024-01-15')
        """)

        # Trying to insert duplicate should fail
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO fafsa_data (student_id, academic_year, efc, submission_date)
                VALUES (1, '2024-2025', 6000, '2024-01-20')
            """)

        conn.close()

class TestDataInsertion:
    """Test suite for data insertion into created tables"""

    def test_insert_financial_aid_application(self, temp_db):
        """Test inserting a financial aid application"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()

        # Create student first
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY,
                first_name TEXT
            )
        """)
        cursor.execute("INSERT INTO students VALUES (1, 'John')")

        # Insert application
        cursor.execute("""
            INSERT INTO financial_aid_applications
            (student_id, academic_year, family_income, household_size)
            VALUES (1, '2024-2025', 50000.0, 4)
        """)

        # Verify insertion
        cursor.execute("SELECT COUNT(*) FROM financial_aid_applications")
        count = cursor.fetchone()[0]
        assert count == 1

        conn.close()

    def test_insert_scholarship(self, temp_db):
        """Test inserting a scholarship"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scholarships
            (name, amount, scholarship_type, eligibility_criteria, is_active)
            VALUES ('Merit Scholarship', 5000.0, 'merit', 'GPA >= 3.5', 1)
        """)

        cursor.execute("SELECT * FROM scholarships WHERE name = 'Merit Scholarship'")
        scholarship = cursor.fetchone()

        assert scholarship is not None
        # Verify scholarship was inserted (amount is at index 3, after id, name, description)
        assert scholarship[3] == 5000.0  # amount

        conn.close()

    def test_insert_disbursement(self, temp_db):
        """Test inserting a disbursement"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()

        # Create student
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (student_id INTEGER PRIMARY KEY)
        """)
        cursor.execute("INSERT INTO students VALUES (1)")

        # Insert disbursement
        cursor.execute("""
            INSERT INTO disbursements
            (student_id, amount, disbursement_date, disbursement_type, academic_term)
            VALUES (1, 2000.0, '2024-08-15', 'grant', 'Fall 2024')
        """)

        cursor.execute("SELECT COUNT(*) FROM disbursements")
        count = cursor.fetchone()[0]
        assert count == 1

        conn.close()

class TestDefaultValues:
    """Test suite for default values in tables"""

    def test_application_default_status(self, temp_db):
        """Test default status for applications"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (student_id INTEGER PRIMARY KEY)
        """)
        cursor.execute("INSERT INTO students VALUES (1)")

        cursor.execute("""
            INSERT INTO financial_aid_applications (student_id, academic_year)
            VALUES (1, '2024-2025')
        """)

        cursor.execute("""
            SELECT status FROM financial_aid_applications
            WHERE student_id = 1
        """)
        status = cursor.fetchone()[0]
        assert status == 'pending'

        conn.close()

    def test_scholarship_default_active(self, temp_db):
        """Test default is_active for scholarships"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scholarships (name, amount, scholarship_type)
            VALUES ('Test Scholarship', 1000.0, 'merit')
        """)

        cursor.execute("""
            SELECT is_active FROM scholarships
            WHERE name = 'Test Scholarship'
        """)
        is_active = cursor.fetchone()[0]
        assert is_active == 1

        conn.close()

    def test_disbursement_default_status(self, temp_db):
        """Test default status for disbursements"""
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)

        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS students (student_id INTEGER PRIMARY KEY)
        """)
        cursor.execute("INSERT INTO students VALUES (1)")

        cursor.execute("""
            INSERT INTO disbursements (student_id, amount, disbursement_date, disbursement_type)
            VALUES (1, 1000.0, '2024-08-15', 'grant')
        """)

        cursor.execute("SELECT status FROM disbursements WHERE student_id = 1")
        status = cursor.fetchone()[0]
        assert status == 'pending'

        conn.close()

class TestSchemaIdempotency:
    """Test that schema creation is idempotent"""

    def test_create_tables_twice(self, temp_db, capsys):
        """Test creating tables twice doesn't cause errors"""
        conn = sqlite3.connect(temp_db)

        # Create tables first time
        create_financial_aid_tables(conn)

        # Create tables second time (should not error due to IF NOT EXISTS)
        create_financial_aid_tables(conn)

        captured = capsys.readouterr()
        assert "created successfully" in captured.out.lower()

        conn.close()

class TestMainExecution:
    """Test the __main__ execution block"""

    def test_main_execution_with_temp_db(self, temp_db, capsys):
        """Test running schema.py as main script"""
        # Just test that the create function works with a temp database
        conn = sqlite3.connect(temp_db)
        create_financial_aid_tables(conn)
        conn.close()

        captured = capsys.readouterr()
        assert "created successfully" in captured.out.lower()

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
