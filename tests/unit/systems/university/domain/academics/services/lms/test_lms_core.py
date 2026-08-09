"""
Comprehensive tests for lms/lms_core.py

Tests LMS core functionality including course, content, discussion, quiz, and gradebook managers
"""

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock


class _UnclosableConnection:
    """Wrapper that makes close() a no-op so tests can query after production code closes."""
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
    def close(self):
        pass
    def __getattr__(self, name):
        return getattr(self._conn, name)
    def __enter__(self):
        return self._conn.__enter__()
    def __exit__(self, *args):
        return self._conn.__exit__(*args)

def _unclosable_connect(db_path):
    return _UnclosableConnection(db_path)
from education_system.systems.university.domain.academics.services.lms.lms_core import (
    LMSCourseManager,
    LMSContentManager,
    LMSDiscussionManager,
    LMSQuizManager,
    LMSGradebookManager
)

class TestLMSCourseManager:
    """Test suite for LMSCourseManager"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        # Initialize database
        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        # Create tables
        cursor.execute('''
            CREATE TABLE lms_courses (
                lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT NOT NULL,
                instructor_id TEXT NOT NULL,
                course_description TEXT,
                syllabus_url TEXT,
                start_date TEXT,
                end_date TEXT,
                enrollment_limit INTEGER DEFAULT 0,
                is_published INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        ''')
        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.remove(path)

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_create_lms_course(self, mock_get_connection, temp_db):
        """Test creating an LMS course"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        course_id = LMSCourseManager.create_lms_course(
            module_code='CS101',
            instructor_id='INST001',
            course_description='Intro to CS',
            syllabus_url='http://example.com/syllabus',
            start_date='2024-01-01',
            end_date='2024-05-01',
            enrollment_limit=30
        )

        assert course_id > 0

        # Verify course was created
        cursor = mock_conn.cursor()
        cursor.execute("SELECT * FROM lms_courses WHERE lms_course_id = ?", (course_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['module_code'] == 'CS101'
        assert result['instructor_id'] == 'INST001'

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_publish_course(self, mock_get_connection, temp_db):
        """Test publishing a course"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create a course first
        cursor = mock_conn.cursor()
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id, is_published)
            VALUES (?, ?, ?)
        ''', ('CS101', 'INST001', 0))
        course_id = cursor.lastrowid
        mock_conn.commit()

        # Publish it
        result = LMSCourseManager.publish_course(course_id)

        assert result is True

        # Verify it's published
        cursor.execute("SELECT is_published FROM lms_courses WHERE lms_course_id = ?", (course_id,))
        is_published = cursor.fetchone()['is_published']

        assert is_published == 1

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_get_course_details(self, mock_get_connection, temp_db):
        """Test getting course details"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create a course
        cursor = mock_conn.cursor()
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id, course_description)
            VALUES (?, ?, ?)
        ''', ('CS101', 'INST001', 'Test Course'))
        course_id = cursor.lastrowid
        mock_conn.commit()

        # Get details
        details = LMSCourseManager.get_course_details(course_id)

        assert details is not None
        assert details['module_code'] == 'CS101'
        assert details['instructor_id'] == 'INST001'

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_get_course_details_not_found(self, mock_get_connection, temp_db):
        """Test getting details for non-existent course"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        details = LMSCourseManager.get_course_details(99999)

        assert details is None

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_get_instructor_courses(self, mock_get_connection, temp_db):
        """Test getting courses by instructor"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create courses
        cursor = mock_conn.cursor()
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id)
            VALUES (?, ?)
        ''', ('CS101', 'INST001'))
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id)
            VALUES (?, ?)
        ''', ('CS102', 'INST001'))
        cursor.execute('''
            INSERT INTO lms_courses (module_code, instructor_id)
            VALUES (?, ?)
        ''', ('CS103', 'INST002'))
        mock_conn.commit()

        # Get instructor courses
        courses = LMSCourseManager.get_instructor_courses('INST001')

        assert len(courses) == 2
        assert all(c['instructor_id'] == 'INST001' for c in courses)

class TestLMSContentManager:
    """Test suite for LMSContentManager"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        conn = sqlite3.connect(path)
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE lms_courses (
                lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT,
                instructor_id TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_course_content (
                content_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                content_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                content_url TEXT,
                content_order INTEGER DEFAULT 0,
                release_date TEXT,
                is_published INTEGER DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_video_lectures (
                video_id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id INTEGER NOT NULL,
                video_url TEXT NOT NULL,
                duration_minutes INTEGER,
                thumbnail_url TEXT,
                transcript_url TEXT,
                video_quality TEXT DEFAULT '720p',
                view_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (content_id) REFERENCES lms_course_content(content_id)
            )
        ''')

        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.remove(path)

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_add_content(self, mock_get_connection, temp_db):
        """Test adding content to a course"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create a course first
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid
        mock_conn.commit()

        # Add content
        content_id = LMSContentManager.add_content(
            lms_course_id=course_id,
            content_type='lecture',
            title='Week 1 Lecture',
            description='Introduction to programming',
            content_url='http://example.com/lecture1',
            content_order=1
        )

        assert content_id > 0

        # Verify
        cursor.execute("SELECT * FROM lms_course_content WHERE content_id = ?", (content_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['title'] == 'Week 1 Lecture'

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_get_course_content(self, mock_get_connection, temp_db):
        """Test getting course content"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create course and content
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_course_content (lms_course_id, content_type, title, is_published)
            VALUES (?, ?, ?, ?)
        ''', (course_id, 'lecture', 'Week 1', 1))

        cursor.execute('''
            INSERT INTO lms_course_content (lms_course_id, content_type, title, is_published)
            VALUES (?, ?, ?, ?)
        ''', (course_id, 'lecture', 'Week 2', 1))

        mock_conn.commit()

        # Get content
        content = LMSContentManager.get_course_content(course_id)

        assert len(content) == 2

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_add_video_lecture(self, mock_get_connection, temp_db):
        """Test adding a video lecture"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create course and content
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_course_content (lms_course_id, content_type, title)
            VALUES (?, ?, ?)
        ''', (course_id, 'video', 'Lecture 1'))
        content_id = cursor.lastrowid
        mock_conn.commit()

        # Add video
        video_id = LMSContentManager.add_video_lecture(
            content_id=content_id,
            video_url='http://example.com/video1.mp4',
            duration_minutes=45,
            thumbnail_url='http://example.com/thumb.jpg',
            video_quality='1080p'
        )

        assert video_id > 0

        # Verify
        cursor.execute("SELECT * FROM lms_video_lectures WHERE video_id = ?", (video_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['duration_minutes'] == 45
        assert result['video_quality'] == '1080p'

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_increment_video_view(self, mock_get_connection, temp_db):
        """Test incrementing video view count"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create video
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_course_content (lms_course_id, content_type, title)
            VALUES (?, ?, ?)
        ''', (course_id, 'video', 'Lecture 1'))
        content_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_video_lectures (content_id, video_url, duration_minutes, view_count)
            VALUES (?, ?, ?, ?)
        ''', (content_id, 'http://example.com/video.mp4', 45, 0))
        video_id = cursor.lastrowid
        mock_conn.commit()

        # Increment view
        LMSContentManager.increment_video_view(video_id)

        # Verify
        cursor.execute("SELECT view_count FROM lms_video_lectures WHERE video_id = ?", (video_id,))
        view_count = cursor.fetchone()['view_count']

        assert view_count == 1

        # Increment again
        LMSContentManager.increment_video_view(video_id)
        cursor.execute("SELECT view_count FROM lms_video_lectures WHERE video_id = ?", (video_id,))
        view_count = cursor.fetchone()['view_count']

        assert view_count == 2

class TestLMSDiscussionManager:
    """Test suite for LMSDiscussionManager"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE lms_courses (
                lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT,
                instructor_id TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_discussion_forums (
                forum_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                description TEXT,
                created_by TEXT NOT NULL,
                is_pinned INTEGER DEFAULT 0,
                is_locked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_discussion_posts (
                post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                forum_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                parent_post_id INTEGER,
                attachments TEXT,
                likes_count INTEGER DEFAULT 0,
                is_instructor_post INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (forum_id) REFERENCES lms_discussion_forums(forum_id)
            )
        ''')

        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.remove(path)

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_create_forum(self, mock_get_connection, temp_db):
        """Test creating a discussion forum"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create course
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid
        mock_conn.commit()

        # Create forum
        forum_id = LMSDiscussionManager.create_forum(
            lms_course_id=course_id,
            topic='General Discussion',
            description='Discuss course topics here',
            created_by='INST001',
            is_pinned=True
        )

        assert forum_id > 0

        # Verify
        cursor.execute("SELECT * FROM lms_discussion_forums WHERE forum_id = ?", (forum_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['topic'] == 'General Discussion'
        assert result['is_pinned'] == 1

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_add_post(self, mock_get_connection, temp_db):
        """Test adding a post to a forum"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create forum
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_discussion_forums (lms_course_id, topic, created_by)
            VALUES (?, ?, ?)
        ''', (course_id, 'General', 'INST001'))
        forum_id = cursor.lastrowid
        mock_conn.commit()

        # Add post
        post_id = LMSDiscussionManager.add_post(
            forum_id=forum_id,
            user_id='STU001',
            content='This is my first post',
            attachments=''
        )

        assert post_id > 0

        # Verify
        cursor.execute("SELECT * FROM lms_discussion_posts WHERE post_id = ?", (post_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['content'] == 'This is my first post'

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_like_post(self, mock_get_connection, temp_db):
        """Test liking a post"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create post
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_discussion_forums (lms_course_id, topic, created_by)
            VALUES (?, ?, ?)
        ''', (course_id, 'General', 'INST001'))
        forum_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_discussion_posts (forum_id, user_id, content, likes_count)
            VALUES (?, ?, ?, ?)
        ''', (forum_id, 'STU001', 'Test post', 0))
        post_id = cursor.lastrowid
        mock_conn.commit()

        # Like post
        LMSDiscussionManager.like_post(post_id)

        # Verify
        cursor.execute("SELECT likes_count FROM lms_discussion_posts WHERE post_id = ?", (post_id,))
        likes = cursor.fetchone()['likes_count']

        assert likes == 1

class TestLMSQuizManager:
    """Test suite for LMSQuizManager"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE lms_courses (
                lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT,
                instructor_id TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_quizzes (
                quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                duration_minutes INTEGER DEFAULT 60,
                passing_score REAL DEFAULT 70.0,
                max_attempts INTEGER DEFAULT 1,
                available_from TEXT,
                available_until TEXT,
                is_published INTEGER DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_quiz_questions (
                question_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                question_type TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                points INTEGER DEFAULT 1,
                options TEXT,
                explanation TEXT,
                display_order INTEGER DEFAULT 0,
                FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(quiz_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_quiz_submissions (
                submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                score REAL NOT NULL,
                total_points INTEGER NOT NULL,
                time_taken_minutes INTEGER,
                submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (quiz_id) REFERENCES lms_quizzes(quiz_id)
            )
        ''')

        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.remove(path)

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_create_quiz(self, mock_get_connection, temp_db):
        """Test creating a quiz"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create course
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid
        mock_conn.commit()

        # Create quiz
        quiz_id = LMSQuizManager.create_quiz(
            lms_course_id=course_id,
            title='Week 1 Quiz',
            description='Test your knowledge',
            duration_minutes=30,
            passing_score=80.0,
            max_attempts=2
        )

        assert quiz_id > 0

        # Verify
        cursor.execute("SELECT * FROM lms_quizzes WHERE quiz_id = ?", (quiz_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['title'] == 'Week 1 Quiz'
        assert result['passing_score'] == 80.0

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_add_question(self, mock_get_connection, temp_db):
        """Test adding a question to a quiz"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create quiz
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_quizzes (lms_course_id, title)
            VALUES (?, ?)
        ''', (course_id, 'Week 1 Quiz'))
        quiz_id = cursor.lastrowid
        mock_conn.commit()

        # Add question
        question_id = LMSQuizManager.add_question(
            quiz_id=quiz_id,
            question_text='What is 2+2?',
            question_type='multiple_choice',
            correct_answer='4',
            points=5,
            options='1,2,3,4',
            explanation='Basic addition'
        )

        assert question_id > 0

        # Verify
        cursor.execute("SELECT * FROM lms_quiz_questions WHERE question_id = ?", (question_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['question_text'] == 'What is 2+2?'
        assert result['points'] == 5

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_submit_quiz(self, mock_get_connection, temp_db):
        """Test submitting a quiz"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create quiz with questions
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_quizzes (lms_course_id, title)
            VALUES (?, ?)
        ''', (course_id, 'Week 1 Quiz'))
        quiz_id = cursor.lastrowid

        # Add questions
        cursor.execute('''
            INSERT INTO lms_quiz_questions (quiz_id, question_text, question_type, correct_answer, points)
            VALUES (?, ?, ?, ?, ?)
        ''', (quiz_id, 'What is 2+2?', 'multiple_choice', '4', 10))
        q1_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_quiz_questions (quiz_id, question_text, question_type, correct_answer, points)
            VALUES (?, ?, ?, ?, ?)
        ''', (quiz_id, 'What is 3+3?', 'multiple_choice', '6', 10))
        q2_id = cursor.lastrowid

        mock_conn.commit()

        # Submit quiz
        answers = {
            q1_id: '4',   # Correct
            q2_id: '5'    # Incorrect
        }

        submission_id, percentage = LMSQuizManager.submit_quiz(
            quiz_id=quiz_id,
            student_id='STU001',
            answers=answers,
            time_taken_minutes=15
        )

        assert submission_id > 0
        assert percentage == 50.0  # Got 1 out of 2 correct

class TestLMSGradebookManager:
    """Test suite for LMSGradebookManager"""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        conn = sqlite3.connect(path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE lms_courses (
                lms_course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_code TEXT,
                instructor_id TEXT
            )
        ''')

        cursor.execute('''
            CREATE TABLE lms_gradebook (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                lms_course_id INTEGER NOT NULL,
                student_id TEXT NOT NULL,
                assignment_type TEXT NOT NULL,
                assignment_id INTEGER NOT NULL,
                score REAL NOT NULL,
                max_score REAL NOT NULL,
                weight REAL DEFAULT 1.0,
                feedback TEXT,
                graded_by TEXT,
                graded_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (lms_course_id) REFERENCES lms_courses(lms_course_id)
            )
        ''')

        conn.commit()
        conn.close()

        yield path
        if os.path.exists(path):
            os.remove(path)

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_add_grade_entry(self, mock_get_connection, temp_db):
        """Test adding a grade entry"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create course
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid
        mock_conn.commit()

        # Add grade
        entry_id = LMSGradebookManager.add_grade_entry(
            lms_course_id=course_id,
            student_id='STU001',
            assignment_type='quiz',
            assignment_id=1,
            score=85.0,
            max_score=100.0,
            weight=1.0,
            feedback='Good work!',
            graded_by='INST001'
        )

        assert entry_id > 0

        # Verify
        cursor.execute("SELECT * FROM lms_gradebook WHERE entry_id = ?", (entry_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['score'] == 85.0
        assert result['feedback'] == 'Good work!'

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_get_student_grades(self, mock_get_connection, temp_db):
        """Test getting student grades"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create course and grades
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        cursor.execute('''
            INSERT INTO lms_gradebook (lms_course_id, student_id, assignment_type, assignment_id, score, max_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (course_id, 'STU001', 'quiz', 1, 85.0, 100.0))

        cursor.execute('''
            INSERT INTO lms_gradebook (lms_course_id, student_id, assignment_type, assignment_id, score, max_score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (course_id, 'STU001', 'quiz', 2, 90.0, 100.0))

        mock_conn.commit()

        # Get grades
        grades = LMSGradebookManager.get_student_grades(course_id, 'STU001')

        assert len(grades) == 2
        assert all(g['student_id'] == 'STU001' for g in grades)

    @patch('education_system.systems.university.domain.academics.services.lms.lms_core.get_connection')
    def test_calculate_course_grade(self, mock_get_connection, temp_db):
        """Test calculating overall course grade"""
        mock_conn = _unclosable_connect(temp_db)
        mock_get_connection.return_value = mock_conn

        # Create course and grades
        cursor = mock_conn.cursor()
        cursor.execute("INSERT INTO lms_courses (module_code, instructor_id) VALUES (?, ?)",
                      ('CS101', 'INST001'))
        course_id = cursor.lastrowid

        # Add weighted grades
        cursor.execute('''
            INSERT INTO lms_gradebook (lms_course_id, student_id, assignment_type, assignment_id,
                                     score, max_score, weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, 'STU001', 'quiz', 1, 80.0, 100.0, 0.3))

        cursor.execute('''
            INSERT INTO lms_gradebook (lms_course_id, student_id, assignment_type, assignment_id,
                                     score, max_score, weight)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (course_id, 'STU001', 'exam', 1, 90.0, 100.0, 0.7))

        mock_conn.commit()

        # Calculate grade
        grade = LMSGradebookManager.calculate_course_grade(course_id, 'STU001')

        # Expected: (80% * 0.3 + 90% * 0.7) / (0.3 + 0.7) = 87%
        assert abs(grade - 87.0) < 0.01
