"""
Comprehensive tests for evaluation/db_schema.py

Tests database schema initialization for Course Evaluation System
"""

import pytest
import sqlite3
import os
import tempfile
from university_system.modules.domain.academics.services.evaluation.db_schema import (
    initialize_evaluation_database
)


class TestEvaluationDatabaseSchema:
    """Test suite for evaluation database schema initialization"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def db_connection(self, temp_db, monkeypatch):
        """Mock database connection for testing"""
        from university_system.infrastructure.database import db

        # Mock transaction context manager to use temp database
        original_transaction = db.transaction

        class MockTransaction:
            def __init__(self):
                self.conn = sqlite3.connect(temp_db)
                self.conn.row_factory = sqlite3.Row

            def __enter__(self):
                return self.conn

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
                self.conn.close()
                return False

        monkeypatch.setattr(db, 'transaction', lambda: MockTransaction())

        yield temp_db

        monkeypatch.setattr(db, 'transaction', original_transaction)

    def test_initialize_evaluation_database(self, db_connection):
        """Test that evaluation database is initialized correctly"""
        # Initialize the database
        initialize_evaluation_database()

        # Connect and verify tables exist
        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Check all expected tables exist
        expected_tables = [
            'evaluation_templates',
            'evaluation_questions',
            'course_evaluations',
            'evaluation_responses',
            'evaluation_answers',
            'evaluation_results'
        ]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

        conn.close()

    def test_evaluation_templates_table_structure(self, db_connection):
        """Test evaluation_templates table has correct columns"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(evaluation_templates)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            'template_id': 'INTEGER',
            'template_name': 'TEXT',
            'template_type': 'TEXT',
            'description': 'TEXT',
            'created_by': 'TEXT',
            'created_at': 'TEXT',
            'is_active': 'INTEGER'
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Column {col_name} not found"
            assert columns[col_name] == col_type, f"Column {col_name} has wrong type"

        conn.close()

    def test_evaluation_questions_table_structure(self, db_connection):
        """Test evaluation_questions table has correct columns and constraints"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(evaluation_questions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            'question_id': 'INTEGER',
            'template_id': 'INTEGER',
            'question_text': 'TEXT',
            'question_type': 'TEXT',
            'question_category': 'TEXT',
            'scale_min': 'INTEGER',
            'scale_max': 'INTEGER',
            'display_order': 'INTEGER',
            'is_required': 'INTEGER'
        }

        for col_name in expected_columns.keys():
            assert col_name in columns, f"Column {col_name} not found"

        conn.close()

    def test_course_evaluations_table_structure(self, db_connection):
        """Test course_evaluations table structure"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(course_evaluations)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'evaluation_id', 'module_code', 'academic_year', 'semester',
            'instructor_id', 'template_id', 'start_date', 'end_date',
            'response_count', 'is_active', 'created_at'
        }

        assert expected_columns.issubset(columns)

        conn.close()

    def test_evaluation_responses_table_structure(self, db_connection):
        """Test evaluation_responses table structure"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(evaluation_responses)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'response_id', 'evaluation_id', 'student_id',
            'is_complete', 'is_anonymous', 'time_taken_minutes',
            'submitted_at'
        }

        assert expected_columns.issubset(columns)

        conn.close()

    def test_evaluation_answers_table_structure(self, db_connection):
        """Test evaluation_answers table structure"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(evaluation_answers)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'answer_id', 'response_id', 'question_id',
            'answer_value', 'numeric_value', 'created_at'
        }

        assert expected_columns.issubset(columns)

        conn.close()

    def test_evaluation_results_table_structure(self, db_connection):
        """Test evaluation_results table structure"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(evaluation_results)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'result_id', 'evaluation_id', 'question_id',
            'average_score', 'response_count', 'calculated_at'
        }

        assert expected_columns.issubset(columns)

        conn.close()

    def test_indexes_created(self, db_connection):
        """Test that all indexes are created correctly"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'idx_eval_module',
            'idx_eval_instructor',
            'idx_response_evaluation'
        ]

        for index in expected_indexes:
            assert index in indexes, f"Index {index} not found"

        conn.close()

    def test_foreign_key_constraints(self, db_connection):
        """Test that foreign key constraints are set up correctly"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Check evaluation_questions foreign key
        cursor.execute("PRAGMA foreign_key_list(evaluation_questions)")
        fks = cursor.fetchall()
        assert len(fks) > 0, "No foreign keys found in evaluation_questions"

        # Check evaluation_responses foreign key
        cursor.execute("PRAGMA foreign_key_list(evaluation_responses)")
        fks = cursor.fetchall()
        assert len(fks) > 0, "No foreign keys found in evaluation_responses"

        conn.close()

    def test_default_values(self, db_connection):
        """Test that default values are set correctly"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Test evaluation_templates defaults
        cursor.execute("PRAGMA table_info(evaluation_templates)")
        for row in cursor.fetchall():
            if row[1] == 'is_active':
                assert row[4] == '1', "is_active default should be 1"

        # Test evaluation_questions defaults
        cursor.execute("PRAGMA table_info(evaluation_questions)")
        for row in cursor.fetchall():
            if row[1] == 'scale_min':
                assert row[4] == '1', "scale_min default should be 1"
            elif row[1] == 'scale_max':
                assert row[4] == '5', "scale_max default should be 5"

        conn.close()

    def test_unique_constraint_on_evaluation_results(self, db_connection):
        """Test unique constraint on evaluation_results"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Get table schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='evaluation_results'")
        schema = cursor.fetchone()[0]

        assert 'UNIQUE' in schema, "UNIQUE constraint not found in evaluation_results"

        conn.close()

    def test_cascade_delete_constraints(self, db_connection):
        """Test ON DELETE CASCADE is set up correctly"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Check evaluation_questions has ON DELETE CASCADE
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='evaluation_questions'")
        schema = cursor.fetchone()[0]
        assert 'ON DELETE CASCADE' in schema, "ON DELETE CASCADE not found"

        conn.close()

    def test_not_null_constraints(self, db_connection):
        """Test NOT NULL constraints are properly set"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Check evaluation_templates NOT NULL columns
        cursor.execute("PRAGMA table_info(evaluation_templates)")
        for row in cursor.fetchall():
            if row[1] in ['template_name', 'template_type', 'created_at']:
                assert row[3] == 1, f"Column {row[1]} should be NOT NULL"

        conn.close()

    def test_multiple_initialization_idempotent(self, db_connection):
        """Test that initializing database multiple times is safe"""
        # Initialize multiple times
        initialize_evaluation_database()
        initialize_evaluation_database()
        initialize_evaluation_database()

        # Should not raise any errors and tables should exist
        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'evaluation_templates' in tables
        assert 'evaluation_questions' in tables

        conn.close()

    def test_primary_keys(self, db_connection):
        """Test that all tables have proper primary keys"""
        initialize_evaluation_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        tables = [
            ('evaluation_templates', 'template_id'),
            ('evaluation_questions', 'question_id'),
            ('course_evaluations', 'evaluation_id'),
            ('evaluation_responses', 'response_id'),
            ('evaluation_answers', 'answer_id'),
            ('evaluation_results', 'result_id')
        ]

        for table_name, pk_column in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            for row in cursor.fetchall():
                if row[1] == pk_column:
                    assert row[5] == 1, f"Column {pk_column} should be primary key"

        conn.close()


class TestEvaluationDatabaseIntegration:
    """Integration tests for evaluation database"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def initialized_db(self, temp_db, monkeypatch):
        """Initialize database and return connection"""
        from university_system.infrastructure.database import db

        class MockTransaction:
            def __init__(self):
                self.conn = sqlite3.connect(temp_db)
                self.conn.row_factory = sqlite3.Row

            def __enter__(self):
                return self.conn

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type is None:
                    self.conn.commit()
                else:
                    self.conn.rollback()
                self.conn.close()
                return False

        monkeypatch.setattr(db, 'transaction', lambda: MockTransaction())
        initialize_evaluation_database()

        yield temp_db

    def test_can_insert_template(self, initialized_db):
        """Test inserting a template into the database"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO evaluation_templates (template_name, template_type, description, created_by)
            VALUES (?, ?, ?, ?)
        ''', ('Course Feedback', 'course', 'Standard course feedback form', 'admin'))

        conn.commit()

        cursor.execute("SELECT * FROM evaluation_templates WHERE template_name = ?", ('Course Feedback',))
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'Course Feedback'
        assert result[2] == 'course'

        conn.close()

    def test_can_insert_question_with_foreign_key(self, initialized_db):
        """Test inserting a question with valid foreign key"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        # First insert a template
        cursor.execute('''
            INSERT INTO evaluation_templates (template_name, template_type)
            VALUES (?, ?)
        ''', ('Test Template', 'course'))
        template_id = cursor.lastrowid

        # Then insert a question
        cursor.execute('''
            INSERT INTO evaluation_questions (template_id, question_text, question_type)
            VALUES (?, ?, ?)
        ''', (template_id, 'How would you rate this course?', 'scale'))

        conn.commit()

        cursor.execute("SELECT * FROM evaluation_questions WHERE template_id = ?", (template_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result[2] == 'How would you rate this course?'

        conn.close()

    def test_cascade_delete_works(self, initialized_db):
        """Test that cascade delete works correctly"""
        conn = sqlite3.connect(initialized_db)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Insert template
        cursor.execute('''
            INSERT INTO evaluation_templates (template_name, template_type)
            VALUES (?, ?)
        ''', ('Test Template', 'course'))
        template_id = cursor.lastrowid

        # Insert question
        cursor.execute('''
            INSERT INTO evaluation_questions (template_id, question_text, question_type)
            VALUES (?, ?, ?)
        ''', (template_id, 'Test Question', 'scale'))

        conn.commit()

        # Delete template
        cursor.execute('DELETE FROM evaluation_templates WHERE template_id = ?', (template_id,))
        conn.commit()

        # Check question was deleted
        cursor.execute('SELECT * FROM evaluation_questions WHERE template_id = ?', (template_id,))
        result = cursor.fetchone()

        assert result is None, "Question should be deleted via cascade"

        conn.close()
