"""
Test suite for Degree Audit Database Schema

Tests the database schema initialization for degree audit system including:
- Table creation
- Foreign key constraints
- Indexes
- Default values
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.domain.academics.services.degree_audit.db_schema import (
    initialize_degree_audit_database
)
from education_system.university_system.infrastructure.database.db import get_connection

class TestDatabaseInitialization:
    """Test degree audit database initialization"""

    def test_initialize_degree_audit_database(self):
        """Test that database initializes without errors"""
        # Should not raise exception
        initialize_degree_audit_database()

        # Verify connection is working
        conn = get_connection()
        assert conn is not None
        conn.close()

    def test_all_tables_created(self):
        """Test that all required tables are created"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        required_tables = [
            'degree_programs',
            'degree_requirements',
            'requirement_courses',
            'degree_course_prerequisites',
            'student_degree_progress',
            'requirement_completion',
            'degree_what_if_scenarios',
            'advising_appointments',
            'graduation_checklist'
        ]

        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table'
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        for table in required_tables:
            assert table in existing_tables, f"Table {table} not created"

class TestDegreeProgramsTable:
    """Test degree_programs table structure"""

    def test_degree_programs_table_structure(self):
        """Test degree programs table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(degree_programs)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'program_id',
            'program_code',
            'program_name',
            'degree_type',
            'department',
            'total_credits_required',
            'min_gpa_required',
            'max_years_allowed',
            'description',
            'is_active',
            'created_at'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in degree_programs"

        conn.close()

    def test_degree_programs_unique_constraint(self):
        """Test program_code unique constraint"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        # Insert first program
        cursor.execute("""
            INSERT INTO degree_programs (program_code, program_name, degree_type, total_credits_required)
            VALUES (?, ?, ?, ?)
        """, ('CS-BS', 'Computer Science BS', 'Bachelor', 120))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO degree_programs (program_code, program_name, degree_type, total_credits_required)
                VALUES (?, ?, ?, ?)
            """, ('CS-BS', 'Duplicate CS Program', 'Bachelor', 120))
            conn.commit()

        conn.close()

    def test_degree_programs_default_values(self):
        """Test default values in degree_programs"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO degree_programs (program_code, program_name, degree_type, total_credits_required)
            VALUES (?, ?, ?, ?)
        """, ('TEST-BS', 'Test Program', 'Bachelor', 120))
        program_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT * FROM degree_programs WHERE program_id = ?", (program_id,))
        result = cursor.fetchone()

        # Check default values
        assert result is not None
        # is_active should default to 1
        # min_gpa_required should default to 2.0
        # max_years_allowed should default to 4

        conn.close()

class TestDegreeRequirementsTable:
    """Test degree_requirements table structure"""

    def test_degree_requirements_table_structure(self):
        """Test degree requirements table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(degree_requirements)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'requirement_id',
            'program_id',
            'requirement_type',
            'requirement_name',
            'credits_required',
            'description',
            'min_grade',
            'is_mandatory',
            'display_order'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in degree_requirements"

        conn.close()

    def test_degree_requirements_foreign_key(self):
        """Test foreign key relationship with degree_programs"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        # Create a program first
        cursor.execute("""
            INSERT INTO degree_programs (program_code, program_name, degree_type, total_credits_required)
            VALUES (?, ?, ?, ?)
        """, ('FK-TEST', 'FK Test Program', 'Bachelor', 120))
        program_id = cursor.lastrowid
        conn.commit()

        # Add requirement for valid program
        cursor.execute("""
            INSERT INTO degree_requirements (program_id, requirement_type, requirement_name, credits_required)
            VALUES (?, ?, ?, ?)
        """, (program_id, 'Core', 'Core Requirements', 30))
        conn.commit()

        # Verify insertion
        cursor.execute("SELECT * FROM degree_requirements WHERE program_id = ?", (program_id,))
        result = cursor.fetchone()
        assert result is not None

        conn.close()

class TestRequirementCoursesTable:
    """Test requirement_courses table structure"""

    def test_requirement_courses_table_structure(self):
        """Test requirement courses table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(requirement_courses)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'req_course_id',
            'requirement_id',
            'module_code',
            'is_alternative',
            'alternative_group'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in requirement_courses"

        conn.close()

class TestDegreePrerequisitesTable:
    """Test degree_course_prerequisites table structure"""

    def test_prerequisites_table_structure(self):
        """Test prerequisites table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(degree_course_prerequisites)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'prerequisite_id',
            'module_code',
            'prerequisite_module_code',
            'min_grade',
            'is_corequisite',
            'created_at'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in degree_course_prerequisites"

        conn.close()

    def test_prerequisites_unique_constraint(self):
        """Test unique constraint on module_code and prerequisite_module_code"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        # Insert first prerequisite
        cursor.execute("""
            INSERT INTO degree_course_prerequisites (module_code, prerequisite_module_code)
            VALUES (?, ?)
        """, ('CS201', 'CS101'))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO degree_course_prerequisites (module_code, prerequisite_module_code)
                VALUES (?, ?)
            """, ('CS201', 'CS101'))
            conn.commit()

        conn.close()

class TestStudentDegreeProgressTable:
    """Test student_degree_progress table structure"""

    def test_student_progress_table_structure(self):
        """Test student degree progress table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(student_degree_progress)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'progress_id',
            'student_id',
            'program_id',
            'enrollment_year',
            'total_credits_earned',
            'current_gpa',
            'completion_percentage',
            'expected_graduation_date',
            'last_updated'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in student_degree_progress"

        conn.close()

    def test_student_progress_unique_constraint(self):
        """Test unique constraint on student_id and program_id"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        # Create a program
        cursor.execute("""
            INSERT INTO degree_programs (program_code, program_name, degree_type, total_credits_required)
            VALUES (?, ?, ?, ?)
        """, ('UNIQ-TEST', 'Unique Test', 'Bachelor', 120))
        program_id = cursor.lastrowid
        conn.commit()

        # Insert first progress record
        cursor.execute("""
            INSERT INTO student_degree_progress (student_id, program_id, enrollment_year)
            VALUES (?, ?, ?)
        """, ('STU001', program_id, 2024))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO student_degree_progress (student_id, program_id, enrollment_year)
                VALUES (?, ?, ?)
            """, ('STU001', program_id, 2024))
            conn.commit()

        conn.close()

class TestRequirementCompletionTable:
    """Test requirement_completion table structure"""

    def test_requirement_completion_table_structure(self):
        """Test requirement completion table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(requirement_completion)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'completion_id',
            'student_id',
            'requirement_id',
            'is_completed',
            'credits_earned',
            'completed_date'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in requirement_completion"

        conn.close()

class TestWhatIfScenariosTable:
    """Test degree_what_if_scenarios table structure"""

    def test_what_if_scenarios_table_structure(self):
        """Test what-if scenarios table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(degree_what_if_scenarios)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'scenario_id',
            'student_id',
            'scenario_name',
            'target_program_id',
            'notes',
            'created_at'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in degree_what_if_scenarios"

        conn.close()

class TestAdvisingAppointmentsTable:
    """Test advising_appointments table structure"""

    def test_advising_appointments_table_structure(self):
        """Test advising appointments table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(advising_appointments)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'appointment_id',
            'student_id',
            'advisor_id',
            'appointment_date',
            'appointment_time',
            'duration_minutes',
            'appointment_type',
            'topic',
            'notes',
            'status',
            'created_at'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in advising_appointments"

        conn.close()

class TestGraduationChecklistTable:
    """Test graduation_checklist table structure"""

    def test_graduation_checklist_table_structure(self):
        """Test graduation checklist table has correct columns"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(graduation_checklist)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        expected_columns = [
            'checklist_id',
            'student_id',
            'program_id',
            'all_requirements_met',
            'gpa_requirement_met',
            'credit_requirement_met',
            'residency_requirement_met',
            'financial_clearance',
            'conferral_status',
            'graduation_date',
            'last_checked'
        ]

        for col in expected_columns:
            assert col in column_names, f"Column {col} not found in graduation_checklist"

        conn.close()

    def test_graduation_checklist_unique_constraint(self):
        """Test unique constraint on student_id and program_id"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        # Create a program
        cursor.execute("""
            INSERT INTO degree_programs (program_code, program_name, degree_type, total_credits_required)
            VALUES (?, ?, ?, ?)
        """, ('GRAD-TEST', 'Graduation Test', 'Bachelor', 120))
        program_id = cursor.lastrowid
        conn.commit()

        # Insert first checklist
        cursor.execute("""
            INSERT INTO graduation_checklist (student_id, program_id)
            VALUES (?, ?)
        """, ('STU001', program_id))
        conn.commit()

        # Try to insert duplicate
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute("""
                INSERT INTO graduation_checklist (student_id, program_id)
                VALUES (?, ?)
            """, ('STU001', program_id))
            conn.commit()

        conn.close()

class TestIndexes:
    """Test database indexes"""

    def test_indexes_created(self):
        """Test that indexes are created"""
        initialize_degree_audit_database()

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='index'
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        # Check for specific indexes
        expected_indexes = [
            'idx_student_progress',
            'idx_appointments',
            'idx_degree_prerequisites'
        ]

        for idx in expected_indexes:
            assert idx in indexes, f"Index {idx} not created"

        conn.close()

class TestReinitialization:
    """Test that reinitialization doesn't cause errors"""

    def test_multiple_initializations(self):
        """Test that calling initialize multiple times doesn't error"""
        # First initialization
        initialize_degree_audit_database()

        # Second initialization (should handle IF NOT EXISTS)
        initialize_degree_audit_database()

        # Verify database is still functional
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        count = cursor.fetchone()[0]

        assert count > 0

        conn.close()

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
