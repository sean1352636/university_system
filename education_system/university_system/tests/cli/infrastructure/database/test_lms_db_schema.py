"""
Comprehensive tests for lms/db_schema.py

Tests database schema initialization for Learning Management System (LMS)
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
import os
import tempfile
from education_system.university_system.modules.domain.academics.services.lms.db_schema import (
    initialize_lms_database
)

class TestLMSDatabaseSchema:
    """Test suite for LMS database schema initialization"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def db_connection(self, temp_db, monkeypatch):
        """Mock database connection for testing"""
        from education_system.university_system.infrastructure.database import db

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

    def test_initialize_lms_database(self, db_connection):
        """Test that LMS database is initialized correctly"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        expected_tables = [
            'lms_courses',
            'lms_course_content',
            'lms_video_lectures',
            'lms_discussion_forums',
            'lms_discussion_posts',
            'lms_quizzes',
            'lms_quiz_questions',
            'lms_quiz_submissions',
            'lms_gradebook',
            'lms_student_enrollment'
        ]

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in expected_tables:
            assert table in tables, f"Table {table} not found"

        conn.close()

    def test_lms_courses_table_structure(self, db_connection):
        """Test lms_courses table has correct columns"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_courses)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        expected_columns = {
            'lms_course_id': 'INTEGER',
            'module_code': 'TEXT',
            'instructor_id': 'TEXT',
            'course_description': 'TEXT',
            'syllabus_url': 'TEXT',
            'start_date': 'TEXT',
            'end_date': 'TEXT',
            'enrollment_limit': 'INTEGER',
            'is_published': 'INTEGER',
            'created_at': 'TEXT',
            'updated_at': 'TEXT'
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Column {col_name} not found"
            assert columns[col_name] == col_type, f"Column {col_name} has wrong type"

        conn.close()

    def test_lms_course_content_table_structure(self, db_connection):
        """Test lms_course_content table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_course_content)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'content_id', 'lms_course_id', 'content_type', 'title',
            'description', 'content_url', 'content_order', 'release_date',
            'is_published', 'created_at'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_video_lectures_table_structure(self, db_connection):
        """Test lms_video_lectures table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_video_lectures)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'video_id', 'content_id', 'video_url', 'duration_minutes',
            'thumbnail_url', 'transcript_url', 'video_quality', 'view_count'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_discussion_forums_table_structure(self, db_connection):
        """Test lms_discussion_forums table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_discussion_forums)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'forum_id', 'lms_course_id', 'topic', 'description',
            'created_by', 'is_pinned', 'is_locked', 'created_at'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_discussion_posts_table_structure(self, db_connection):
        """Test lms_discussion_posts table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_discussion_posts)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'post_id', 'forum_id', 'user_id', 'content',
            'parent_post_id', 'attachments', 'likes_count',
            'is_instructor_post', 'created_at'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_quizzes_table_structure(self, db_connection):
        """Test lms_quizzes table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_quizzes)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'quiz_id', 'lms_course_id', 'title', 'description',
            'duration_minutes', 'passing_score', 'max_attempts',
            'available_from', 'available_until', 'is_published'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_quiz_questions_table_structure(self, db_connection):
        """Test lms_quiz_questions table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_quiz_questions)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'question_id', 'quiz_id', 'question_text', 'question_type',
            'correct_answer', 'points', 'options', 'explanation',
            'display_order'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_quiz_submissions_table_structure(self, db_connection):
        """Test lms_quiz_submissions table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_quiz_submissions)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'submission_id', 'quiz_id', 'student_id', 'attempt_number',
            'score', 'total_points', 'time_taken_minutes', 'submitted_at'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_gradebook_table_structure(self, db_connection):
        """Test lms_gradebook table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_gradebook)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'entry_id', 'lms_course_id', 'student_id', 'assignment_type',
            'assignment_id', 'score', 'max_score', 'weight',
            'feedback', 'graded_by', 'graded_at'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_lms_student_enrollment_table_structure(self, db_connection):
        """Test lms_student_enrollment table structure"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_student_enrollment)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'enrollment_id', 'lms_course_id', 'student_id',
            'enrollment_date', 'last_accessed', 'progress_percentage',
            'is_active'
        }

        assert expected_columns.issubset(columns)
        conn.close()

    def test_indexes_created(self, db_connection):
        """Test that all indexes are created correctly"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            'idx_lms_course_instructor',
            'idx_lms_content',
            'idx_lms_forums',
            'idx_lms_gradebook',
            'idx_lms_enrollment'
        ]

        for index in expected_indexes:
            assert index in indexes, f"Index {index} not found"

        conn.close()

    def test_foreign_key_constraints(self, db_connection):
        """Test that foreign key constraints are set up correctly"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Check lms_course_content foreign key
        cursor.execute("PRAGMA foreign_key_list(lms_course_content)")
        fks = cursor.fetchall()
        assert len(fks) > 0, "No foreign keys found in lms_course_content"

        # Check lms_video_lectures foreign key
        cursor.execute("PRAGMA foreign_key_list(lms_video_lectures)")
        fks = cursor.fetchall()
        assert len(fks) > 0, "No foreign keys found in lms_video_lectures"

        conn.close()

    def test_default_values(self, db_connection):
        """Test that default values are set correctly"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        # Test lms_courses defaults
        cursor.execute("PRAGMA table_info(lms_courses)")
        for row in cursor.fetchall():
            if row[1] == 'enrollment_limit':
                assert row[4] == '0', "enrollment_limit default should be 0"
            elif row[1] == 'is_published':
                assert row[4] == '0', "is_published default should be 0"

        conn.close()

    def test_cascade_delete_constraints(self, db_connection):
        """Test ON DELETE CASCADE is set up correctly"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lms_course_content'")
        schema = cursor.fetchone()[0]
        assert 'ON DELETE CASCADE' in schema, "ON DELETE CASCADE not found"

        conn.close()

    def test_unique_constraint_on_enrollment(self, db_connection):
        """Test unique constraint on student enrollment"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lms_student_enrollment'")
        schema = cursor.fetchone()[0]
        assert 'UNIQUE' in schema, "UNIQUE constraint not found in lms_student_enrollment"

        conn.close()

    def test_not_null_constraints(self, db_connection):
        """Test NOT NULL constraints are properly set"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(lms_courses)")
        for row in cursor.fetchall():
            if row[1] in ['module_code', 'instructor_id', 'created_at', 'updated_at']:
                assert row[3] == 1, f"Column {row[1]} should be NOT NULL"

        conn.close()

    def test_multiple_initialization_idempotent(self, db_connection):
        """Test that initializing database multiple times is safe"""
        initialize_lms_database()
        initialize_lms_database()
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        assert 'lms_courses' in tables
        assert 'lms_quizzes' in tables

        conn.close()

    def test_primary_keys(self, db_connection):
        """Test that all tables have proper primary keys"""
        initialize_lms_database()

        conn = sqlite3.connect(db_connection)
        cursor = conn.cursor()

        tables = [
            ('lms_courses', 'lms_course_id'),
            ('lms_course_content', 'content_id'),
            ('lms_video_lectures', 'video_id'),
            ('lms_discussion_forums', 'forum_id'),
            ('lms_discussion_posts', 'post_id'),
            ('lms_quizzes', 'quiz_id'),
            ('lms_quiz_questions', 'question_id'),
            ('lms_quiz_submissions', 'submission_id'),
            ('lms_gradebook', 'entry_id'),
            ('lms_student_enrollment', 'enrollment_id')
        ]

        for table_name, pk_column in tables:
            cursor.execute(f"PRAGMA table_info({table_name})")
            for row in cursor.fetchall():
                if row[1] == pk_column:
                    assert row[5] == 1, f"Column {pk_column} should be primary key"

        conn.close()

class TestLMSDatabaseIntegration:
    """Integration tests for LMS database"""

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
        from education_system.university_system.infrastructure.database import db

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
        initialize_lms_database()
        yield temp_db

    def test_can_insert_course(self, initialized_db):
        """Test inserting a course into the database"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id, course_description)
            VALUES (?, ?, ?)
        ''', ('CS101', 'INST001', 'Introduction to Computer Science'))

        conn.commit()

        cursor.execute("SELECT * FROM lms_courses WHERE module_code = ?", ('CS101',))
        result = cursor.fetchone()

        assert result is not None
        assert result[1] == 'CS101'

        conn.close()

    def test_can_insert_content_with_foreign_key(self, initialized_db):
        """Test inserting content with valid foreign key"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        # First insert a course
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id)
            VALUES (?, ?)
        ''', ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        # Then insert content
        cursor.execute('''
            INSERT INTO lms_course_content (lms_course_id, content_type, title)
            VALUES (?, ?, ?)
        ''', (course_id, 'lecture', 'Week 1 Lecture'))

        conn.commit()

        cursor.execute("SELECT * FROM lms_course_content WHERE lms_course_id = ?", (course_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result[3] == 'Week 1 Lecture'

        conn.close()

    def test_cascade_delete_works(self, initialized_db):
        """Test that cascade delete works correctly"""
        conn = sqlite3.connect(initialized_db)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Insert course
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id)
            VALUES (?, ?)
        ''', ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        # Insert content
        cursor.execute('''
            INSERT INTO lms_course_content (lms_course_id, content_type, title)
            VALUES (?, ?, ?)
        ''', (course_id, 'lecture', 'Week 1'))

        conn.commit()

        # Delete course
        cursor.execute('DELETE FROM lms_courses WHERE lms_course_id = ?', (course_id,))
        conn.commit()

        # Check content was deleted
        cursor.execute('SELECT * FROM lms_course_content WHERE lms_course_id = ?', (course_id,))
        result = cursor.fetchone()

        assert result is None, "Content should be deleted via cascade"

        conn.close()

    def test_can_insert_quiz_and_questions(self, initialized_db):
        """Test inserting quiz with questions"""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.cursor()

        # Insert course
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id)
            VALUES (?, ?)
        ''', ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        # Insert quiz
        cursor.execute('''
            INSERT INTO lms_quizzes (lms_course_id, title, duration_minutes)
            VALUES (?, ?, ?)
        ''', (course_id, 'Week 1 Quiz', 30))
        quiz_id = cursor.lastrowid

        # Insert questions
        cursor.execute('''
            INSERT INTO lms_quiz_questions (quiz_id, question_text, question_type, correct_answer)
            VALUES (?, ?, ?, ?)
        ''', (quiz_id, 'What is 2+2?', 'multiple_choice', '4'))

        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM lms_quiz_questions WHERE quiz_id = ?", (quiz_id,))
        count = cursor.fetchone()[0]

        assert count == 1

        conn.close()
