"""
Tests for Student Affairs Helpdesk Service

Tests cover:
- Ticket creation and management
- Ticket replies and communication
- Ticket assignments and escalations
- SLA policies
- Knowledge base
- Time tracking
- Ticket workflows
"""

import pytest
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.domain.student_affairs.services.helpdesk import (
    init_helpdesk_db,
    init_default_data,
)

@pytest.fixture
def setup_helpdesk_database():
    """Set up test database with helpdesk tables"""
    init_helpdesk_db()

    yield

    # Cleanup
    conn = get_connection()
    cursor = conn.cursor()

    tables = [
        'support_tickets', 'ticket_replies', 'ticket_attachments',
        'ticket_assignments', 'ticket_templates', 'sla_policies',
        'ticket_workflows', 'ticket_time_tracking', 'ticket_escalations',
        'ticket_links', 'ticket_audit_log', 'knowledge_base',
        'departments', 'organizations', 'saved_searches'
    ]

    for table in tables:
        try:
            cursor.execute(f'DELETE FROM {table}')
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

@pytest.fixture
def sample_user(setup_helpdesk_database):
    """Create a sample user for testing"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, role, student_id)
        VALUES (?, ?, ?, ?)
    ''', (1001, 'test_user', 'student', 'S1001'))

    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, role)
        VALUES (?, ?, ?)
    ''', (2001, 'staff_user', 'staff'))

    conn.commit()
    conn.close()

    return 1001

class TestDatabaseSetup:
    """Tests for database initialization"""

    def test_init_helpdesk_db_creates_tables(self, setup_helpdesk_database):
        """Test that all helpdesk tables are created"""
        conn = get_connection()
        cursor = conn.cursor()

        tables_to_check = [
            'support_tickets', 'ticket_replies', 'sla_policies',
            'knowledge_base', 'departments'
        ]

        for table in tables_to_check:
            cursor.execute(f"""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='{table}'
            """)
            assert cursor.fetchone() is not None, f"Table {table} was not created"

        conn.close()

    def test_init_default_data(self, setup_helpdesk_database):
        """Test default data initialization"""
        conn = get_connection()
        cursor = conn.cursor()

        # Check SLA policies
        cursor.execute('SELECT COUNT(*) FROM sla_policies')
        sla_count = cursor.fetchone()[0]
        assert sla_count > 0

        # Check templates
        cursor.execute('SELECT COUNT(*) FROM ticket_templates')
        template_count = cursor.fetchone()[0]
        assert template_count > 0

        # Check departments
        cursor.execute('SELECT COUNT(*) FROM departments')
        dept_count = cursor.fetchone()[0]
        assert dept_count > 0

        conn.close()

class TestTicketManagement:
    """Tests for ticket creation and management"""

    def test_create_basic_ticket(self, setup_helpdesk_database, sample_user):
        """Test creating a basic support ticket"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO support_tickets (
                user_id, subject, message, category, status, priority, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            sample_user,
            'Login Issue',
            'Cannot access my account',
            'Technical Support',
            'open',
            'medium',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        ticket_id = cursor.lastrowid
        conn.commit()

        # Verify ticket creation
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()
        conn.close()

        assert ticket is not None
        assert ticket['subject'] == 'Login Issue'
        assert ticket['status'] == 'open'

    def test_ticket_priority_levels(self, setup_helpdesk_database, sample_user):
        """Test different priority levels"""
        priorities = ['low', 'medium', 'high', 'urgent', 'critical']

        conn = get_connection()
        cursor = conn.cursor()

        ticket_ids = []
        for priority in priorities:
            cursor.execute('''
                INSERT INTO support_tickets (user_id, subject, message, category, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (sample_user, f'Test {priority}', 'Message', 'Test', priority, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            ticket_ids.append(cursor.lastrowid)

        conn.commit()

        # Verify all tickets created
        cursor.execute('SELECT COUNT(*) FROM support_tickets WHERE ticket_id IN ({})'.format(
            ','.join('?' * len(ticket_ids))
        ), ticket_ids)
        count = cursor.fetchone()[0]
        conn.close()

        assert count == len(priorities)

    def test_update_ticket_status(self, setup_helpdesk_database, sample_user):
        """Test updating ticket status"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (user_id, subject, message, category, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (sample_user, 'Test', 'Message', 'Test', 'open', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ticket_id = cursor.lastrowid

        # Update status
        cursor.execute('''
            UPDATE support_tickets
            SET status = ?, updated_at = ?
            WHERE ticket_id = ?
        ''', ('in_progress', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))

        conn.commit()

        # Verify update
        cursor.execute('SELECT status FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        status = cursor.fetchone()['status']
        conn.close()

        assert status == 'in_progress'

class TestTicketReplies:
    """Tests for ticket replies"""

    def test_add_reply_to_ticket(self, setup_helpdesk_database, sample_user):
        """Test adding a reply to a ticket"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (user_id, subject, message, category, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (sample_user, 'Test', 'Message', 'Test', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ticket_id = cursor.lastrowid

        # Add reply
        cursor.execute('''
            INSERT INTO ticket_replies (ticket_id, user_id, message, is_internal, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, 2001, 'Thank you for contacting support', 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        reply_id = cursor.lastrowid
        conn.commit()

        # Verify reply
        cursor.execute('SELECT * FROM ticket_replies WHERE reply_id = ?', (reply_id,))
        reply = cursor.fetchone()
        conn.close()

        assert reply is not None
        assert reply['ticket_id'] == ticket_id
        assert reply['is_internal'] == 0

    def test_internal_notes(self, setup_helpdesk_database, sample_user):
        """Test internal notes on tickets"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (user_id, subject, message, category, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (sample_user, 'Test', 'Message', 'Test', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ticket_id = cursor.lastrowid

        # Add internal note
        cursor.execute('''
            INSERT INTO ticket_replies (ticket_id, user_id, message, is_internal, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (ticket_id, 2001, 'Internal note: escalate to senior staff', 1, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()

        # Verify internal note
        cursor.execute('SELECT * FROM ticket_replies WHERE ticket_id = ? AND is_internal = 1', (ticket_id,))
        internal_notes = cursor.fetchall()
        conn.close()

        assert len(internal_notes) == 1

class TestTicketAssignments:
    """Tests for ticket assignments"""

    def test_assign_ticket(self, setup_helpdesk_database, sample_user):
        """Test assigning a ticket to staff"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (user_id, subject, message, category, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (sample_user, 'Test', 'Message', 'Test', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ticket_id = cursor.lastrowid

        # Assign ticket
        cursor.execute('''
            UPDATE support_tickets SET assigned_to = ? WHERE ticket_id = ?
        ''', (2001, ticket_id))

        # Log assignment
        cursor.execute('''
            INSERT INTO ticket_assignments (ticket_id, assigned_from, assigned_to, created_at)
            VALUES (?, ?, ?, ?)
        ''', (ticket_id, None, 2001, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()

        # Verify assignment
        cursor.execute('SELECT assigned_to FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        assigned_to = cursor.fetchone()['assigned_to']
        conn.close()

        assert assigned_to == 2001

class TestSLAPolicies:
    """Tests for SLA policies"""

    def test_sla_policies_exist(self, setup_helpdesk_database):
        """Test that SLA policies are created"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM sla_policies WHERE is_active = 1')
        policies = cursor.fetchall()
        conn.close()

        assert len(policies) > 0

    def test_sla_response_time(self, setup_helpdesk_database):
        """Test SLA response time thresholds"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM sla_policies WHERE priority = ?', ('high',))
        high_priority_sla = cursor.fetchone()
        conn.close()

        assert high_priority_sla is not None
        assert high_priority_sla['first_response_hours'] < high_priority_sla['resolution_hours']

class TestKnowledgeBase:
    """Tests for knowledge base"""

    def test_create_kb_article(self, setup_helpdesk_database):
        """Test creating a knowledge base article"""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO knowledge_base (
                title, content, category, tags, author_id, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            'How to Reset Password',
            'Step 1: Click Forgot Password...',
            'Account Access',
            'password,reset,login',
            2001,
            'published',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        article_id = cursor.lastrowid
        conn.commit()

        # Verify article
        cursor.execute('SELECT * FROM knowledge_base WHERE article_id = ?', (article_id,))
        article = cursor.fetchone()
        conn.close()

        assert article is not None
        assert article['status'] == 'published'

    def test_search_knowledge_base(self, setup_helpdesk_database):
        """Test searching knowledge base"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create articles
        articles = [
            ('Password Reset Guide', 'How to reset password', 'password,login'),
            ('Email Setup', 'How to setup email', 'email,setup'),
        ]

        for title, content, tags in articles:
            cursor.execute('''
                INSERT INTO knowledge_base (title, content, tags, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (title, content, tags, 'published', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()

        # Search for "password"
        cursor.execute('''
            SELECT * FROM knowledge_base
            WHERE (title LIKE ? OR content LIKE ? OR tags LIKE ?) AND status = 'published'
        ''', ('%password%', '%password%', '%password%'))
        results = cursor.fetchall()
        conn.close()

        assert len(results) == 1
        assert 'Password' in results[0]['title']

class TestTimeTracking:
    """Tests for time tracking"""

    def test_log_time_entry(self, setup_helpdesk_database, sample_user):
        """Test logging time spent on a ticket"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (user_id, subject, message, category, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (sample_user, 'Test', 'Message', 'Test', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ticket_id = cursor.lastrowid

        # Log time
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=2)

        cursor.execute('''
            INSERT INTO ticket_time_tracking (
                ticket_id, user_id, start_time, end_time, duration_minutes,
                description, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            ticket_id,
            2001,
            start_time.isoformat(),
            end_time.isoformat(),
            120,
            'Troubleshooting login issue',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        conn.commit()

        # Verify time entry
        cursor.execute('SELECT SUM(duration_minutes) as total FROM ticket_time_tracking WHERE ticket_id = ?', (ticket_id,))
        total = cursor.fetchone()['total']
        conn.close()

        assert total == 120

class TestTicketEscalations:
    """Tests for ticket escalations"""

    def test_escalate_ticket(self, setup_helpdesk_database, sample_user):
        """Test escalating a ticket"""
        conn = get_connection()
        cursor = conn.cursor()

        # Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (user_id, subject, message, category, escalation_level, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (sample_user, 'Test', 'Message', 'Test', 0, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ticket_id = cursor.lastrowid

        # Escalate
        cursor.execute('''
            UPDATE support_tickets
            SET escalation_level = ?
            WHERE ticket_id = ?
        ''', (1, ticket_id))

        cursor.execute('''
            INSERT INTO ticket_escalations (
                ticket_id, escalation_level, escalated_to, escalated_by,
                escalation_reason, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_id, 1, 2001, 2001, 'SLA breach', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        conn.commit()

        # Verify escalation
        cursor.execute('SELECT escalation_level FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        level = cursor.fetchone()['escalation_level']
        conn.close()

        assert level == 1

class TestIntegrationScenarios:
    """Integration tests for complete workflows"""

    def test_complete_ticket_lifecycle(self, setup_helpdesk_database, sample_user):
        """Test complete ticket workflow from creation to resolution"""
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Create ticket
        cursor.execute('''
            INSERT INTO support_tickets (user_id, subject, message, category, status, priority, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (sample_user, 'Login Issue', 'Cannot login', 'Technical', 'open', 'high', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        ticket_id = cursor.lastrowid

        # 2. Assign to staff
        cursor.execute('UPDATE support_tickets SET assigned_to = ? WHERE ticket_id = ?', (2001, ticket_id))

        # 3. Add reply
        cursor.execute('''
            INSERT INTO ticket_replies (ticket_id, user_id, message, created_at)
            VALUES (?, ?, ?, ?)
        ''', (ticket_id, 2001, 'Working on this', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # 4. Log time
        cursor.execute('''
            INSERT INTO ticket_time_tracking (ticket_id, user_id, duration_minutes, created_at)
            VALUES (?, ?, ?, ?)
        ''', (ticket_id, 2001, 30, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

        # 5. Resolve ticket
        cursor.execute('''
            UPDATE support_tickets
            SET status = ?, resolution = ?, resolved_at = ?
            WHERE ticket_id = ?
        ''', ('resolved', 'Password reset successful', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ticket_id))

        # 6. Add satisfaction rating
        cursor.execute('''
            UPDATE support_tickets
            SET satisfaction_rating = ?
            WHERE ticket_id = ?
        ''', (5, ticket_id))

        conn.commit()

        # Verify complete workflow
        cursor.execute('SELECT * FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
        ticket = cursor.fetchone()

        cursor.execute('SELECT COUNT(*) as count FROM ticket_replies WHERE ticket_id = ?', (ticket_id,))
        reply_count = cursor.fetchone()['count']

        cursor.execute('SELECT SUM(duration_minutes) as total FROM ticket_time_tracking WHERE ticket_id = ?', (ticket_id,))
        time_spent = cursor.fetchone()['total']

        conn.close()

        assert ticket['status'] == 'resolved'
        assert ticket['satisfaction_rating'] == 5
        assert reply_count == 1
        assert time_spent == 30

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
