"""
Comprehensive test suite for communication_manager.py

Tests all classes, functions, and functionality including:
- CommunicationManager class
- Email management (queue_email, send_bulk_email)
- SMS management (queue_sms)
- Push notifications (send_push_notification)
- Announcements (create_announcement, get_active_announcements)
- Emergency alerts (send_emergency_alert)
- Message templates (create_template, render_template)
- Communication preferences (update_preferences, get_preferences)
"""

import pytest
import os
import json
import tempfile
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from education_system.university_system.modules.shared.services.communication.communication_manager import (
    CommunicationManager
)

@pytest.fixture
def temp_db():
    """Create a temporary test database with required tables."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create all required tables
    cursor.executescript("""
        -- Email Queue
        CREATE TABLE IF NOT EXISTS email_queue (
            queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_address TEXT NOT NULL,
            cc_addresses TEXT,
            bcc_addresses TEXT,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            html_body TEXT,
            attachments TEXT,
            scheduled_time TIMESTAMP,
            priority INTEGER DEFAULT 5,
            status TEXT DEFAULT 'queued',
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            sent_at TIMESTAMP,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- SMS Queue
        CREATE TABLE IF NOT EXISTS sms_queue (
            sms_id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT NOT NULL,
            message_text TEXT NOT NULL,
            scheduled_time TIMESTAMP,
            status TEXT DEFAULT 'queued',
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3,
            sent_at TIMESTAMP,
            message_id TEXT,
            error_message TEXT,
            cost REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Push Notifications
        CREATE TABLE IF NOT EXISTS push_notifications (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            data TEXT,
            icon TEXT,
            click_action TEXT,
            status TEXT DEFAULT 'pending',
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Announcements
        CREATE TABLE IF NOT EXISTS announcements (
            announcement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            target_audience TEXT,
            priority TEXT DEFAULT 'normal',
            start_date DATE,
            end_date DATE,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Message Templates
        CREATE TABLE IF NOT EXISTS message_templates (
            template_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            subject TEXT,
            body TEXT NOT NULL,
            variables TEXT,
            template_type TEXT DEFAULT 'email',
            category TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Communication Preferences
        CREATE TABLE IF NOT EXISTS communication_preferences (
            pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            email_enabled BOOLEAN DEFAULT 1,
            sms_enabled BOOLEAN DEFAULT 0,
            push_enabled BOOLEAN DEFAULT 1,
            announcement_enabled BOOLEAN DEFAULT 1,
            marketing_enabled BOOLEAN DEFAULT 0,
            emergency_only BOOLEAN DEFAULT 0,
            preferred_method TEXT DEFAULT 'email',
            quiet_hours_start TIME,
            quiet_hours_end TIME,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Emergency Alerts
        CREATE TABLE IF NOT EXISTS emergency_alerts (
            alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'moderate',
            affected_locations TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            sent_by INTEGER NOT NULL,
            total_recipients INTEGER DEFAULT 0
        );
    """)

    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except (OSError, IOError):
        pass

@pytest.fixture
def comm_manager(temp_db):
    """Create a CommunicationManager instance with test database."""
    return CommunicationManager(db_path=temp_db)

class TestCommunicationManagerInit:
    """Test CommunicationManager initialization."""

    def test_initialization_with_default_path(self):
        """Test initialization with default database path."""
        with patch('university_system.modules.shared.services.communication.communication_manager.DEFAULT_DB_PATH', '/tmp/test.db'):
            manager = CommunicationManager()
            assert manager.db_path is not None

    def test_initialization_with_custom_path(self, temp_db):
        """Test initialization with custom database path."""
        manager = CommunicationManager(db_path=temp_db)
        assert manager.db_path == temp_db

    def test_get_connection(self, comm_manager):
        """Test _get_connection method."""
        conn = comm_manager._get_connection()
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

class TestEmailManagement:
    """Test email management functionality."""

    def test_queue_email_basic(self, comm_manager):
        """Test queuing a basic email."""
        email_id = comm_manager.queue_email(
            to_address="test@example.com",
            subject="Test Subject",
            body="Test body content"
        )
        assert email_id is not None
        assert isinstance(email_id, int)

    def test_queue_email_with_html(self, comm_manager):
        """Test queuing an email with HTML body."""
        email_id = comm_manager.queue_email(
            to_address="test@example.com",
            subject="Test Subject",
            body="Plain text body",
            html_body="<html><body>HTML body</body></html>"
        )
        assert email_id is not None

    def test_queue_email_with_cc_bcc(self, comm_manager):
        """Test queuing an email with CC and BCC addresses."""
        email_id = comm_manager.queue_email(
            to_address="test@example.com",
            subject="Test Subject",
            body="Test body",
            cc_addresses=["cc1@example.com", "cc2@example.com"],
            bcc_addresses=["bcc@example.com"]
        )
        assert email_id is not None

    def test_queue_email_with_scheduled_time(self, comm_manager):
        """Test queuing an email with scheduled time."""
        scheduled_time = datetime.now() + timedelta(hours=1)
        email_id = comm_manager.queue_email(
            to_address="test@example.com",
            subject="Test Subject",
            body="Test body",
            scheduled_time=scheduled_time
        )
        assert email_id is not None

    def test_queue_email_with_priority(self, comm_manager):
        """Test queuing an email with custom priority."""
        email_id = comm_manager.queue_email(
            to_address="test@example.com",
            subject="Test Subject",
            body="Test body",
            priority=10
        )
        assert email_id is not None

    def test_queue_email_error_handling(self, comm_manager, capsys):
        """Test error handling when queuing email fails."""
        # Create a manager with invalid database path to trigger error
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.queue_email(
            to_address="test@example.com",
            subject="Test",
            body="Test"
        )
        assert result is None
        captured = capsys.readouterr()
        assert "Error queuing email:" in captured.out

    def test_send_bulk_email(self, comm_manager):
        """Test sending bulk emails."""
        recipients = [
            "user1@example.com",
            "user2@example.com",
            "user3@example.com"
        ]
        count = comm_manager.send_bulk_email(
            recipients=recipients,
            subject="Bulk Email",
            body="Bulk email body"
        )
        assert count == 3

    def test_send_bulk_email_with_html(self, comm_manager):
        """Test sending bulk emails with HTML."""
        recipients = ["user1@example.com", "user2@example.com"]
        count = comm_manager.send_bulk_email(
            recipients=recipients,
            subject="Bulk Email",
            body="Plain text",
            html_body="<html><body>HTML</body></html>"
        )
        assert count == 2

    def test_send_bulk_email_empty_list(self, comm_manager):
        """Test sending bulk emails with empty recipient list."""
        count = comm_manager.send_bulk_email(
            recipients=[],
            subject="Test",
            body="Test"
        )
        assert count == 0

class TestSMSManagement:
    """Test SMS management functionality."""

    def test_queue_sms_basic(self, comm_manager):
        """Test queuing a basic SMS."""
        sms_id = comm_manager.queue_sms(
            phone_number="+1234567890",
            message_text="Test SMS message"
        )
        assert sms_id is not None
        assert isinstance(sms_id, int)

    def test_queue_sms_with_scheduled_time(self, comm_manager):
        """Test queuing an SMS with scheduled time."""
        scheduled_time = datetime.now() + timedelta(hours=1)
        sms_id = comm_manager.queue_sms(
            phone_number="+1234567890",
            message_text="Scheduled SMS",
            scheduled_time=scheduled_time
        )
        assert sms_id is not None

    def test_queue_sms_error_handling(self, comm_manager, capsys):
        """Test error handling when queuing SMS fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.queue_sms(
            phone_number="+1234567890",
            message_text="Test"
        )
        assert result is None
        captured = capsys.readouterr()
        assert "Error queuing SMS:" in captured.out

class TestPushNotifications:
    """Test push notification functionality."""

    def test_send_push_notification_basic(self, comm_manager):
        """Test sending a basic push notification."""
        notif_id = comm_manager.send_push_notification(
            user_id=1,
            title="Test Notification",
            body="Test notification body"
        )
        assert notif_id is not None
        assert isinstance(notif_id, int)

    def test_send_push_notification_with_data(self, comm_manager):
        """Test sending a push notification with additional data."""
        notif_id = comm_manager.send_push_notification(
            user_id=1,
            title="Test Notification",
            body="Test body",
            data={"key": "value", "count": 42}
        )
        assert notif_id is not None

    def test_send_push_notification_with_click_action(self, comm_manager):
        """Test sending a push notification with click action."""
        notif_id = comm_manager.send_push_notification(
            user_id=1,
            title="Test Notification",
            body="Test body",
            click_action="/dashboard"
        )
        assert notif_id is not None

    def test_send_push_notification_error_handling(self, comm_manager, capsys):
        """Test error handling when sending push notification fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.send_push_notification(
            user_id=1,
            title="Test",
            body="Test"
        )
        assert result is None
        captured = capsys.readouterr()
        assert "Error sending push notification:" in captured.out

class TestAnnouncements:
    """Test announcement functionality."""

    def test_create_announcement_basic(self, comm_manager):
        """Test creating a basic announcement."""
        ann_id = comm_manager.create_announcement(
            title="Test Announcement",
            content="Test announcement content",
            created_by=1
        )
        assert ann_id is not None
        assert isinstance(ann_id, int)

    def test_create_announcement_with_target_audience(self, comm_manager):
        """Test creating an announcement with target audience."""
        ann_id = comm_manager.create_announcement(
            title="Test Announcement",
            content="Test content",
            created_by=1,
            target_audience={"role": ["student"], "department": ["CS"]}
        )
        assert ann_id is not None

    def test_create_announcement_with_priority(self, comm_manager):
        """Test creating an announcement with priority."""
        ann_id = comm_manager.create_announcement(
            title="Test Announcement",
            content="Test content",
            created_by=1,
            priority="high"
        )
        assert ann_id is not None

    def test_create_announcement_with_dates(self, comm_manager):
        """Test creating an announcement with start and end dates."""
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days=7)
        ann_id = comm_manager.create_announcement(
            title="Test Announcement",
            content="Test content",
            created_by=1,
            start_date=start_date,
            end_date=end_date
        )
        assert ann_id is not None

    def test_create_announcement_error_handling(self, comm_manager, capsys):
        """Test error handling when creating announcement fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.create_announcement(
            title="Test",
            content="Test",
            created_by=1
        )
        assert result is None
        captured = capsys.readouterr()
        assert "Error creating announcement:" in captured.out

    def test_get_active_announcements(self, comm_manager):
        """Test getting active announcements."""
        # Create some announcements
        comm_manager.create_announcement(
            title="Active Announcement 1",
            content="Content 1",
            created_by=1
        )
        comm_manager.create_announcement(
            title="Active Announcement 2",
            content="Content 2",
            created_by=1,
            priority="high"
        )

        announcements = comm_manager.get_active_announcements()
        assert isinstance(announcements, list)
        assert len(announcements) == 2

    def test_get_active_announcements_with_dates(self, comm_manager):
        """Test getting active announcements with date filtering."""
        # Create announcement with current dates
        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now() + timedelta(days=1)
        comm_manager.create_announcement(
            title="Current Announcement",
            content="Content",
            created_by=1,
            start_date=start_date,
            end_date=end_date
        )

        # Create announcement with past dates
        past_start = datetime.now() - timedelta(days=10)
        past_end = datetime.now() - timedelta(days=5)
        comm_manager.create_announcement(
            title="Past Announcement",
            content="Content",
            created_by=1,
            start_date=past_start,
            end_date=past_end
        )

        announcements = comm_manager.get_active_announcements()
        # Should only get current announcement (past one is filtered by date)
        assert isinstance(announcements, list)

    def test_get_active_announcements_empty(self, comm_manager):
        """Test getting active announcements when none exist."""
        announcements = comm_manager.get_active_announcements()
        assert isinstance(announcements, list)
        assert len(announcements) == 0

    def test_get_active_announcements_error_handling(self, comm_manager, capsys):
        """Test error handling when getting announcements fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.get_active_announcements()
        assert isinstance(result, list)
        assert len(result) == 0
        captured = capsys.readouterr()
        assert "Error getting announcements:" in captured.out

class TestEmergencyAlerts:
    """Test emergency alert functionality."""

    def test_send_emergency_alert_basic(self, comm_manager):
        """Test sending a basic emergency alert."""
        alert_id = comm_manager.send_emergency_alert(
            alert_type="security",
            message="Test emergency alert",
            severity="high",
            sent_by=1
        )
        assert alert_id is not None
        assert isinstance(alert_id, int)

    def test_send_emergency_alert_with_locations(self, comm_manager):
        """Test sending an emergency alert with affected locations."""
        alert_id = comm_manager.send_emergency_alert(
            alert_type="weather",
            message="Severe weather alert",
            severity="critical",
            sent_by=1,
            affected_locations=["Building A", "Building B", "Parking Lot"]
        )
        assert alert_id is not None

    def test_send_emergency_alert_error_handling(self, comm_manager, capsys):
        """Test error handling when sending emergency alert fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.send_emergency_alert(
            alert_type="test",
            message="Test",
            severity="low",
            sent_by=1
        )
        assert result is None
        captured = capsys.readouterr()
        assert "Error sending emergency alert:" in captured.out

class TestMessageTemplates:
    """Test message template functionality."""

    def test_create_template_email(self, comm_manager):
        """Test creating an email template."""
        template_id = comm_manager.create_template(
            name="welcome_email",
            body="Welcome to our system, {name}!",
            subject="Welcome {name}",
            template_type="email"
        )
        assert template_id is not None
        assert isinstance(template_id, int)

    def test_create_template_with_variables(self, comm_manager):
        """Test creating a template with variables."""
        template_id = comm_manager.create_template(
            name="notification_template",
            body="Hello {name}, your {item} is ready.",
            subject="Notification for {name}",
            variables=["name", "item"],
            created_by=1
        )
        assert template_id is not None

    def test_create_template_sms(self, comm_manager):
        """Test creating an SMS template."""
        template_id = comm_manager.create_template(
            name="sms_notification",
            body="Hi {name}, your code is {code}",
            template_type="sms"
        )
        assert template_id is not None

    def test_create_template_error_handling(self, comm_manager, capsys):
        """Test error handling when creating template fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.create_template(
            name="test",
            body="test"
        )
        assert result is None
        captured = capsys.readouterr()
        assert "Error creating template:" in captured.out

    def test_render_template(self, comm_manager):
        """Test rendering a template with variables."""
        # Create template
        template_id = comm_manager.create_template(
            name="test_template",
            subject="Hello {name}",
            body="Welcome {name}, you have {count} messages."
        )

        # Render template
        rendered = comm_manager.render_template(
            template_id=template_id,
            variables={"name": "John", "count": "5"}
        )

        assert rendered is not None
        assert isinstance(rendered, dict)
        assert "subject" in rendered
        assert "body" in rendered
        assert "John" in rendered["subject"]
        assert "John" in rendered["body"]
        assert "5" in rendered["body"]

    def test_render_template_nonexistent(self, comm_manager):
        """Test rendering a template that doesn't exist."""
        rendered = comm_manager.render_template(
            template_id=99999,
            variables={"name": "Test"}
        )
        assert rendered is None

    def test_render_template_no_subject(self, comm_manager):
        """Test rendering a template without subject."""
        template_id = comm_manager.create_template(
            name="no_subject_template",
            body="Message for {name}"
        )

        rendered = comm_manager.render_template(
            template_id=template_id,
            variables={"name": "John"}
        )

        assert rendered is not None
        assert "body" in rendered

    def test_render_template_error_handling(self, comm_manager, capsys):
        """Test error handling when rendering template fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.render_template(
            template_id=1,
            variables={"name": "Test"}
        )
        assert result is None
        captured = capsys.readouterr()
        assert "Error rendering template:" in captured.out

class TestCommunicationPreferences:
    """Test communication preferences functionality."""

    def test_update_preferences_new_user(self, comm_manager):
        """Test updating preferences for a new user."""
        result = comm_manager.update_preferences(
            user_id=1,
            email_enabled=True,
            sms_enabled=False,
            push_enabled=True
        )
        assert result is True

    def test_update_preferences_existing_user(self, comm_manager):
        """Test updating preferences for an existing user."""
        # Create initial preferences
        comm_manager.update_preferences(
            user_id=2,
            email_enabled=True,
            sms_enabled=False
        )

        # Update preferences
        result = comm_manager.update_preferences(
            user_id=2,
            sms_enabled=True,
            push_enabled=False
        )
        assert result is True

    def test_update_preferences_with_preferred_method(self, comm_manager):
        """Test updating preferences with preferred method."""
        result = comm_manager.update_preferences(
            user_id=3,
            preferred_method="sms"
        )
        assert result is True

    def test_update_preferences_partial_update(self, comm_manager):
        """Test partial preference update."""
        # Create initial preferences
        comm_manager.update_preferences(
            user_id=4,
            email_enabled=True,
            sms_enabled=True,
            push_enabled=True
        )

        # Update only email preference
        result = comm_manager.update_preferences(
            user_id=4,
            email_enabled=False
        )
        assert result is True

    def test_update_preferences_error_handling(self, comm_manager, capsys):
        """Test error handling when updating preferences fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.update_preferences(
            user_id=1,
            email_enabled=True
        )
        assert result is False
        captured = capsys.readouterr()
        assert "Error updating preferences:" in captured.out

    def test_get_preferences(self, comm_manager):
        """Test getting user preferences."""
        # Create preferences
        comm_manager.update_preferences(
            user_id=5,
            email_enabled=True,
            sms_enabled=False,
            push_enabled=True,
            preferred_method="email"
        )

        # Get preferences
        prefs = comm_manager.get_preferences(user_id=5)
        assert prefs is not None
        assert isinstance(prefs, dict)
        assert "user_id" in prefs
        assert prefs["user_id"] == 5

    def test_get_preferences_nonexistent_user(self, comm_manager):
        """Test getting preferences for nonexistent user."""
        prefs = comm_manager.get_preferences(user_id=99999)
        assert prefs is None

    def test_get_preferences_error_handling(self, comm_manager, capsys):
        """Test error handling when getting preferences fails."""
        bad_manager = CommunicationManager(db_path="/nonexistent/path/db.db")
        result = bad_manager.get_preferences(user_id=1)
        assert result is None
        captured = capsys.readouterr()
        assert "Error getting preferences:" in captured.out

class TestIntegration:
    """Integration tests for complex workflows."""

    def test_full_email_workflow(self, comm_manager):
        """Test complete email workflow."""
        # Create template
        template_id = comm_manager.create_template(
            name="full_workflow_template",
            subject="Welcome {name}",
            body="Hello {name}, welcome to {system}!"
        )

        # Render template
        rendered = comm_manager.render_template(
            template_id=template_id,
            variables={"name": "John", "system": "University System"}
        )

        # Queue email with rendered content
        email_id = comm_manager.queue_email(
            to_address="john@example.com",
            subject=rendered["subject"],
            body=rendered["body"]
        )

        assert email_id is not None

    def test_bulk_notification_workflow(self, comm_manager):
        """Test bulk notification workflow."""
        # Send bulk emails
        email_count = comm_manager.send_bulk_email(
            recipients=["user1@example.com", "user2@example.com"],
            subject="System Update",
            body="System will be down for maintenance"
        )

        # Send push notifications to same users
        notif_id1 = comm_manager.send_push_notification(
            user_id=1,
            title="System Update",
            body="System will be down for maintenance"
        )
        notif_id2 = comm_manager.send_push_notification(
            user_id=2,
            title="System Update",
            body="System will be down for maintenance"
        )

        assert email_count == 2
        assert notif_id1 is not None
        assert notif_id2 is not None

    def test_announcement_with_preferences(self, comm_manager):
        """Test creating announcement and checking preferences."""
        # Set user preferences
        comm_manager.update_preferences(
            user_id=1,
            email_enabled=True,
            push_enabled=True
        )

        # Create announcement
        ann_id = comm_manager.create_announcement(
            title="Important Update",
            content="System update scheduled",
            created_by=1,
            priority="high"
        )

        # Get active announcements
        announcements = comm_manager.get_active_announcements()

        # Get preferences
        prefs = comm_manager.get_preferences(user_id=1)

        assert ann_id is not None
        assert len(announcements) > 0
        assert prefs is not None

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
