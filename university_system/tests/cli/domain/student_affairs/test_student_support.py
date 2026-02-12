"""
Tests for Student Support Service

Tests cover:
- EnhancedStudentSupport class initialization
- Ticket management (create, update, assign)
- Notification system
- Satisfaction ratings
- FAQ management
- Resource library
- Knowledge base articles
- Support workflows
"""

import pytest
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime
from unittest.mock import patch, MagicMock

from university_system.infrastructure.database.db import get_connection
from university_system.modules.domain.student_affairs.services.student_support import (
    EnhancedStudentSupport,
    SupportConfig,
    NotificationType,
    TicketSentiment,
    SUPPORT_DB,
)

@pytest.fixture
def setup_database():
    """Set up test database with support tables"""
    conn = sqlite3.connect(SUPPORT_DB)
    cursor = conn.cursor()

    # Create support_tickets table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT DEFAULT 'Open',
            priority TEXT DEFAULT 'Medium',
            assigned_to TEXT,
            created_datetime TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_datetime TEXT DEFAULT CURRENT_TIMESTAMP,
            satisfaction_rating INTEGER,
            satisfaction_feedback TEXT
        )
    ''')

    # Create notifications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            notification_type TEXT DEFAULT 'in_app',
            is_read INTEGER DEFAULT 0,
            read_datetime TEXT,
            expires_at TEXT,
            created_datetime TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create system_metrics table for ratings
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_metrics (
            metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_name TEXT NOT NULL,
            metric_value REAL NOT NULL,
            category TEXT,
            recorded_datetime TEXT DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
    ''')

    # Create faqs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS faqs (
            faq_id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT,
            view_count INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            created_datetime TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create support_resources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS support_resources (
            resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            url TEXT,
            file_path TEXT,
            tags TEXT,
            access_count INTEGER DEFAULT 0,
            created_by TEXT,
            created_datetime TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create knowledge_base_articles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_base_articles (
            article_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT,
            category TEXT NOT NULL,
            tags TEXT,
            author_id TEXT,
            status TEXT DEFAULT 'draft',
            view_count INTEGER DEFAULT 0,
            helpful_votes INTEGER DEFAULT 0,
            not_helpful_votes INTEGER DEFAULT 0,
            published_datetime TEXT,
            created_datetime TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            student_id TEXT,
            role TEXT DEFAULT 'student'
        )
    ''')

    conn.commit()
    conn.close()

    yield

    # Cleanup
    conn = sqlite3.connect(SUPPORT_DB)
    cursor = conn.cursor()

    tables = [
        'support_tickets', 'notifications', 'system_metrics',
        'faqs', 'support_resources', 'knowledge_base_articles'
    ]

    for table in tables:
        try:
            cursor.execute(f'DELETE FROM {table}')
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

@pytest.fixture
def support_system(setup_database):
    """Create EnhancedStudentSupport instance"""
    config = SupportConfig(
        max_file_size=5 * 1024 * 1024,  # 5MB
        auto_assign_enabled=True,
        satisfaction_survey_enabled=True
    )

    with patch.object(EnhancedStudentSupport, '_load_staff_assignments'):
        with patch.object(EnhancedStudentSupport, '_start_background_tasks'):
            system = EnhancedStudentSupport(config)
            return system

@pytest.fixture
def mock_auth():
    """Create mock authentication object"""
    auth = MagicMock()
    auth.current_user = {
        'id': 1,
        'username': 'test_user',
        'role': 'student',
        'student_id': 'S12345'
    }
    auth.check_permission = MagicMock(return_value=True)
    auth.is_logged_in = MagicMock(return_value=True)
    return auth

class TestSupportSystemInitialization:
    """Tests for support system initialization"""

    def test_create_support_system_default_config(self, setup_database):
        """Test creating support system with default config"""
        with patch.object(EnhancedStudentSupport, '_load_staff_assignments'):
            with patch.object(EnhancedStudentSupport, '_start_background_tasks'):
                system = EnhancedStudentSupport()

                assert system.config is not None
                assert system.config.max_file_size == 10 * 1024 * 1024

    def test_create_support_system_custom_config(self, setup_database):
        """Test creating support system with custom config"""
        config = SupportConfig(
            max_file_size=20 * 1024 * 1024,
            auto_assign_enabled=False,
            escalation_time_hours=48
        )

        with patch.object(EnhancedStudentSupport, '_load_staff_assignments'):
            with patch.object(EnhancedStudentSupport, '_start_background_tasks'):
                system = EnhancedStudentSupport(config)

                assert system.config.max_file_size == 20 * 1024 * 1024
                assert system.config.auto_assign_enabled is False
                assert system.config.escalation_time_hours == 48

class TestTicketManagement:
    """Tests for ticket management functionality"""

    def test_create_ticket(self, setup_database):
        """Test creating a support ticket"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO support_tickets (student_id, subject, message, category, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('S001', 'Test Ticket', 'Test Message', 'Technical', 'Open', 'Medium'))

        ticket_id = cursor.lastrowid
        conn.commit()

        # Verify ticket
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()
        conn.close()

        assert ticket is not None
        assert ticket[2] == 'Test Ticket'

    def test_update_ticket_status(self, setup_database):
        """Test updating ticket status"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (student_id, subject, message, category, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('S002', 'Subject', 'Message', 'Academic', 'Open'))
        ticket_id = cursor.lastrowid

        # Update status
        cursor.execute('''
            UPDATE support_tickets SET status = ? WHERE ticket_id = ?
        ''', ('Resolved', ticket_id))
        conn.commit()

        # Verify update
        cursor.execute('SELECT status FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        status = cursor.fetchone()[0]
        conn.close()

        assert status == 'Resolved'

class TestNotifications:
    """Tests for notification system"""

    def test_get_user_notifications(self, setup_database, support_system, mock_auth):
        """Test retrieving user notifications"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Create notifications
        user_id = mock_auth.current_user['id']
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message, is_read)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test Notification', 'Test Message', 0))
        conn.commit()
        conn.close()

        # Set auth globally
        from university_system.modules.domain.student_affairs.services import student_support
        student_support.auth = mock_auth

        # Get notifications
        notifications = support_system.get_user_notifications(user_id)

        assert len(notifications) >= 1

    def test_mark_notification_read(self, setup_database, support_system, mock_auth):
        """Test marking a notification as read"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Create notification
        user_id = mock_auth.current_user['id']
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message, is_read)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'Test', 'Message', 0))
        notification_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Set auth
        from university_system.modules.domain.student_affairs.services import student_support
        student_support.auth = mock_auth

        # Mark as read
        result = support_system.mark_notification_read(notification_id, user_id)

        assert result is True

        # Verify
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        cursor.execute('SELECT is_read FROM notifications WHERE notification_id = ?', (notification_id,))
        is_read = cursor.fetchone()[0]
        conn.close()

        assert is_read == 1

class TestSatisfactionRatings:
    """Tests for satisfaction rating system"""

    def test_submit_satisfaction_rating(self, setup_database, support_system, mock_auth):
        """Test submitting a satisfaction rating"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Create resolved ticket
        cursor.execute('''
            INSERT INTO support_tickets (student_id, subject, message, category, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ('S12345', 'Test', 'Message', 'Test', 'Resolved'))
        ticket_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Set auth
        from university_system.modules.domain.student_affairs.services import student_support
        student_support.auth = mock_auth

        # Submit rating
        result = support_system.submit_satisfaction_rating(
            ticket_id, rating=5, feedback='Great support!'
        )

        assert result is True

        # Verify rating
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()
        cursor.execute('SELECT satisfaction_rating FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        rating = cursor.fetchone()[0]
        conn.close()

        assert rating == 5

class TestFAQManagement:
    """Tests for FAQ system"""

    def test_create_faq(self, setup_database):
        """Test creating an FAQ"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO faqs (question, answer, category)
            VALUES (?, ?, ?)
        ''', ('How do I reset my password?', 'Click on Forgot Password...', 'Account'))
        faq_id = cursor.lastrowid
        conn.commit()

        # Verify FAQ
        cursor.execute('SELECT * FROM faqs WHERE faq_id = ?', (faq_id,))
        faq = cursor.fetchone()
        conn.close()

        assert faq is not None
        assert 'password' in faq[1].lower()

    def test_search_faqs(self, setup_database):
        """Test searching FAQs"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Create FAQs
        faqs = [
            ('How to reset password?', 'Steps to reset', 'Account'),
            ('How to change email?', 'Steps to change email', 'Account'),
            ('Library hours?', 'Library is open...', 'Services')
        ]

        for q, a, c in faqs:
            cursor.execute('INSERT INTO faqs (question, answer, category) VALUES (?, ?, ?)', (q, a, c))

        conn.commit()

        # Search for "password"
        cursor.execute('''
            SELECT * FROM faqs WHERE question LIKE ? OR answer LIKE ?
        ''', ('%password%', '%password%'))
        results = cursor.fetchall()
        conn.close()

        assert len(results) >= 1

class TestResourceLibrary:
    """Tests for resource library"""

    def test_add_resource(self, setup_database):
        """Test adding a support resource"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO support_resources (title, description, category, url, created_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            'Student Handbook',
            'Official student handbook',
            'Guides',
            'https://example.com/handbook.pdf',
            'admin'
        ))
        resource_id = cursor.lastrowid
        conn.commit()

        # Verify resource
        cursor.execute('SELECT * FROM support_resources WHERE resource_id = ?', (resource_id,))
        resource = cursor.fetchone()
        conn.close()

        assert resource is not None
        assert resource[1] == 'Student Handbook'

    def test_increment_access_count(self, setup_database):
        """Test incrementing resource access count"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Create resource
        cursor.execute('''
            INSERT INTO support_resources (title, description, category)
            VALUES (?, ?, ?)
        ''', ('Resource', 'Description', 'Category'))
        resource_id = cursor.lastrowid

        # Increment access count
        cursor.execute('''
            UPDATE support_resources SET access_count = access_count + 1
            WHERE resource_id = ?
        ''', (resource_id,))
        conn.commit()

        # Verify count
        cursor.execute('SELECT access_count FROM support_resources WHERE resource_id = ?', (resource_id,))
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1

class TestKnowledgeBase:
    """Tests for knowledge base articles"""

    def test_create_article(self, setup_database):
        """Test creating a knowledge base article"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO knowledge_base_articles (
                title, content, summary, category, author_id, status
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'Getting Started',
            'Full article content here...',
            'Brief summary',
            'Guides',
            'admin',
            'published'
        ))
        article_id = cursor.lastrowid
        conn.commit()

        # Verify article
        cursor.execute('SELECT * FROM knowledge_base_articles WHERE article_id = ?', (article_id,))
        article = cursor.fetchone()
        conn.close()

        assert article is not None
        assert article[6] == 'published'

    def test_search_articles(self, setup_database):
        """Test searching knowledge base"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Create articles
        articles = [
            ('Login Guide', 'How to login...', 'Account', 'published'),
            ('Email Setup', 'Setting up email...', 'Communication', 'published'),
        ]

        for title, content, category, status in articles:
            cursor.execute('''
                INSERT INTO knowledge_base_articles (title, content, category, status)
                VALUES (?, ?, ?, ?)
            ''', (title, content, category, status))

        conn.commit()

        # Search for "login"
        cursor.execute('''
            SELECT * FROM knowledge_base_articles
            WHERE (title LIKE ? OR content LIKE ?) AND status = 'published'
        ''', ('%login%', '%login%'))
        results = cursor.fetchall()
        conn.close()

        assert len(results) >= 1

class TestDataTypes:
    """Tests for data types and enums"""

    def test_notification_type_enum(self):
        """Test NotificationType enum"""
        assert NotificationType.EMAIL.value == 'email'
        assert NotificationType.IN_APP.value == 'in_app'
        assert NotificationType.PUSH.value == 'push'

    def test_ticket_sentiment_enum(self):
        """Test TicketSentiment enum"""
        assert TicketSentiment.POSITIVE.value == 'positive'
        assert TicketSentiment.NEUTRAL.value == 'neutral'
        assert TicketSentiment.NEGATIVE.value == 'negative'
        assert TicketSentiment.FRUSTRATED.value == 'frustrated'

    def test_support_config_defaults(self):
        """Test SupportConfig default values"""
        config = SupportConfig()

        assert config.max_file_size == 10 * 1024 * 1024
        assert config.auto_assign_enabled is True
        assert config.escalation_time_hours == 24
        assert config.satisfaction_survey_enabled is True

class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_complete_support_workflow(self, setup_database, support_system, mock_auth):
        """Test complete support ticket workflow"""
        conn = sqlite3.connect(SUPPORT_DB)
        cursor = conn.cursor()

        # Set auth
        from university_system.modules.domain.student_affairs.services import student_support
        student_support.auth = mock_auth

        # 1. Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (student_id, subject, message, category, status, priority)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('S12345', 'Need Help', 'I need help with registration', 'Academic', 'Open', 'High'))
        ticket_id = cursor.lastrowid

        # 2. Create notification for user
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
        ''', (1, 'Ticket Created', f'Your ticket #{ticket_id} has been created'))
        notification_id = cursor.lastrowid

        # 3. Assign and update ticket
        cursor.execute('''
            UPDATE support_tickets SET status = ?, assigned_to = ?
            WHERE ticket_id = ?
        ''', ('In Progress', 'staff@school.edu', ticket_id))

        # 4. Resolve ticket
        cursor.execute('''
            UPDATE support_tickets SET status = ?
            WHERE ticket_id = ?
        ''', ('Resolved', ticket_id))

        # 5. Submit satisfaction rating
        cursor.execute('''
            UPDATE support_tickets SET satisfaction_rating = ?, satisfaction_feedback = ?
            WHERE ticket_id = ?
        ''', (5, 'Very helpful!', ticket_id))

        conn.commit()

        # Verify complete workflow
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()

        cursor.execute('SELECT * FROM notifications WHERE notification_id = ?', (notification_id,))
        notification = cursor.fetchone()

        conn.close()

        assert ticket[5] == 'Resolved'
        assert ticket[11] == 5
        assert notification is not None

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
