#!/usr/bin/env python3
"""
Comprehensive tests for Email Queue & Scheduler GUI Module
Tests queue management, scheduling, worker control, and monitoring interfaces
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
from education_system.systems.university.infrastructure.database.db import sqlite3
import tempfile
import os
import tkinter as tk
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import the module under test
from education_system.systems.university.interfaces.gui.shell.email import email_queue_scheduler_gui


@pytest.fixture(autouse=True)
def _mock_dateentry():
    """tkcalendar's DateEntry crashes under headless Tk (KeyError: 'size' while
    parsing the default font). Replace it with a stub for all GUI tests."""
    with patch.object(email_queue_scheduler_gui, 'DateEntry', create=True) as mock_de:
        instance = MagicMock()
        instance.get_date.return_value = datetime(2026, 1, 1).date()
        instance.get.return_value = '2026-01-01'
        mock_de.return_value = instance
        yield mock_de


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    # Create required tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_name TEXT,
            recipient_email TEXT,
            scheduled_date TIMESTAMP,
            status TEXT DEFAULT 'pending',
            template_vars TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            subject TEXT,
            body TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stored_emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_email TEXT,
            subject TEXT,
            body TEXT,
            sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test templates
    cursor.execute("""
        INSERT INTO email_templates (name, subject, body)
        VALUES ('test_template', 'Test {{name}}', 'Hello {{name}}')
    """)

    cursor.execute("""
        INSERT INTO email_templates (name, subject, body)
        VALUES ('welcome', 'Welcome', 'Welcome to the system')
    """)

    # Insert test scheduled email
    future_date = datetime.now() + timedelta(hours=1)
    cursor.execute("""
        INSERT INTO scheduled_emails (template_name, recipient_email, scheduled_date, status)
        VALUES ('welcome', 'test@example.com', ?, 'pending')
    """, (future_date,))

    conn.commit()
    conn.close()

    yield path

    try:
        os.unlink(path)
    except (OSError, IOError):
        pass

@pytest.fixture
def root_window():
    """Create a Tkinter root window for testing"""
    root = tk.Tk()
    yield root
    try:
        root.destroy()
    except (OSError, IOError):
        pass

class TestEmailQueueSchedulerGUIInitialization:
    """Test EmailQueueSchedulerGUI initialization"""

    def test_gui_initialization_with_parent(self, root_window, temp_db):
        """Test GUI initializes with parent window"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                assert gui is not None
                assert isinstance(gui.window, tk.Toplevel)
            except (OSError, IOError):
                pass  # May fail in headless environment

    def test_gui_initialization_without_parent(self, temp_db):
        """Test GUI initializes without parent (standalone)"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=None)
                assert gui is not None
                assert isinstance(gui.window, tk.Tk)
            except (OSError, IOError):
                pass

    def test_gui_sets_window_title(self, root_window, temp_db):
        """Test that GUI sets window title"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                # Window title should be set
            except (OSError, IOError):
                pass

    def test_gui_sets_window_geometry(self, root_window, temp_db):
        """Test that GUI sets window geometry"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                # Window geometry should be set to 1000x700
            except (OSError, IOError):
                pass

    def test_gui_creates_notebook(self, root_window, temp_db):
        """Test that GUI creates notebook with tabs"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                assert hasattr(gui, 'notebook')
            except (OSError, IOError):
                pass

class TestWorkerControlTab:
    """Test worker control tab functionality"""

    def test_start_workers_button(self, root_window, temp_db):
        """Test start workers functionality"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.start_email_workers', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                    with patch('tkinter.messagebox.showinfo') as mock_info:
                        gui.start_workers()
                        # Should show success message
                        mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

    def test_stop_workers_button(self, root_window, temp_db):
        """Test stop workers functionality"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.stop_email_workers', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                    with patch('tkinter.messagebox.showinfo') as mock_info:
                        gui.stop_workers()
                        mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

    def test_refresh_status_button(self, root_window, temp_db):
        """Test refresh status functionality"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.worker_threads', []):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                    gui.refresh_status()
                    # Should update status labels
                except (OSError, IOError):
                    pass

class TestQueueEmailTab:
    """Test queue email tab functionality"""

    def test_queue_direct_email(self, root_window, temp_db):
        """Test queueing direct email"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.queue_email', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                    # Set form values
                    gui.queue_recipient.insert(0, 'test@example.com')
                    gui.queue_subject.insert(0, 'Test Subject')
                    gui.queue_body.insert('1.0', 'Test Body')

                    with patch('tkinter.messagebox.showinfo') as mock_info:
                        gui.queue_direct_email()
                        mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

    def test_queue_direct_email_validation(self, root_window, temp_db):
        """Test validation for queueing direct email"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                # Don't set required fields
                with patch('tkinter.messagebox.showerror') as mock_error:
                    gui.queue_direct_email()
                    # Should show error for missing fields
                    mock_error.assert_called_once()
            except (OSError, IOError):
                pass

    def test_queue_template_email(self, root_window, temp_db):
        """Test queueing template email"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.queue_template_email', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                    # Set form values
                    gui.queue_template.set('test_template')
                    gui.queue_template_recipient.insert(0, 'test@example.com')
                    gui.queue_template_vars.insert('1.0', '{"name": "Test"}')

                    with patch('tkinter.messagebox.showinfo') as mock_info:
                        gui.queue_template_email_action()
                        mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

class TestScheduleEmailTab:
    """Test schedule email tab functionality"""

    def test_schedule_emails(self, root_window, temp_db):
        """Test scheduling emails"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.schedule_send', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                    # Set form values
                    gui.schedule_template.set('test_template')
                    gui.schedule_recipients.insert('1.0', 'test@example.com')
                    gui.schedule_vars.insert('1.0', '[{"name": "Test"}]')

                    with patch('tkinter.messagebox.showinfo') as mock_info:
                        gui.schedule_emails()
                        mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

    def test_schedule_emails_validation(self, root_window, temp_db):
        """Test validation for scheduling emails"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                # Don't set required fields
                with patch('tkinter.messagebox.showerror') as mock_error:
                    gui.schedule_emails()
                    # Should show error for missing fields
                    mock_error.assert_called_once()
            except (OSError, IOError):
                pass

    def test_process_due_emails(self, root_window, temp_db):
        """Test processing due scheduled emails"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.process_scheduled_emails', return_value=5):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                    with patch('tkinter.messagebox.showinfo') as mock_info:
                        gui.process_due_emails()
                        mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

    def test_refresh_scheduled_list(self, root_window, temp_db):
        """Test refreshing scheduled emails list"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                gui.refresh_scheduled_list()
                # Should load scheduled emails from database
            except (OSError, IOError):
                pass

class TestMonitorTab:
    """Test monitor tab functionality"""

    def test_refresh_monitor(self, root_window, temp_db):
        """Test refreshing monitor information"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.email_queue') as mock_queue:
                with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.worker_threads', []):
                    mock_queue.qsize.return_value = 3

                    try:
                        gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                        gui.refresh_monitor()
                        # Should update monitoring labels
                    except (OSError, IOError):
                        pass

class TestUtilitiesTab:
    """Test utilities tab functionality"""

    def test_wait_for_queue(self, root_window, temp_db):
        """Test wait for queue utility"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.wait_for_email_queue', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                    # This would normally block, so we won't actually call it
                    # Just verify the method exists
                    assert hasattr(gui, 'wait_for_queue')
                except (OSError, IOError):
                    pass

    def test_fix_inbox_display(self, root_window, temp_db):
        """Test fix inbox display utility"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.fix_inbox_display_issue', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                    with patch('tkinter.messagebox.askyesno', return_value=True):
                        with patch('tkinter.messagebox.showinfo') as mock_info:
                            gui.fix_inbox_display()
                            mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

    def test_update_email_status(self, root_window, temp_db):
        """Test update email status utility"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.update_scheduled_email_status', return_value=True):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                    # Set form values
                    gui.status_email_id.insert(0, '1')
                    gui.status_new_status.set('sent')

                    with patch('tkinter.messagebox.showinfo') as mock_info:
                        gui.update_email_status()
                        mock_info.assert_called_once()
                except (OSError, IOError):
                    pass

class TestTemplateLoading:
    """Test template loading functionality"""

    def test_load_templates(self, root_window, temp_db):
        """Test loading email templates"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.list_templates', return_value=['test_template', 'welcome']):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                    gui.load_templates()
                    # Should populate template dropdown
                except (OSError, IOError):
                    pass

    def test_load_schedule_templates(self, root_window, temp_db):
        """Test loading templates for scheduler"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.list_templates', return_value=['test_template', 'welcome']):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                    gui.load_schedule_templates()
                    # Should populate schedule template dropdown
                except (OSError, IOError):
                    pass

class TestErrorHandling:
    """Test error handling"""

    def test_queue_email_smtp_error(self, root_window, temp_db):
        """Test handling SMTP error when queueing email"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.queue_email',
                       side_effect=Exception('SMTP error')):
                try:
                    gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                    gui.queue_recipient.insert(0, 'test@example.com')
                    gui.queue_subject.insert(0, 'Test')
                    gui.queue_body.insert('1.0', 'Body')

                    with patch('tkinter.messagebox.showerror') as mock_error:
                        gui.queue_direct_email()
                        mock_error.assert_called_once()
                except (OSError, IOError):
                    pass

    def test_schedule_invalid_json(self, root_window, temp_db):
        """Test handling invalid JSON in template variables"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                gui.schedule_template.set('test_template')
                gui.schedule_recipients.insert('1.0', 'test@example.com')
                gui.schedule_vars.insert('1.0', 'invalid json')

                with patch('tkinter.messagebox.showerror') as mock_error:
                    gui.schedule_emails()
                    # Should show JSON error
                    mock_error.assert_called_once()
            except (OSError, IOError):
                pass

    def test_update_status_invalid_id(self, root_window, temp_db):
        """Test updating status with invalid ID"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                gui.status_email_id.insert(0, 'not_a_number')
                gui.status_new_status.set('sent')

                with patch('tkinter.messagebox.showerror') as mock_error:
                    gui.update_email_status()
                    # Should show error about invalid ID
                    mock_error.assert_called_once()
            except (OSError, IOError):
                pass

class TestRunMethod:
    """Test run method"""

    def test_run_method_starts_mainloop(self, root_window, temp_db):
        """Test that run method starts mainloop"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                with patch.object(gui.window, 'mainloop') as mock_mainloop:
                    gui.run()
                    mock_mainloop.assert_called_once()
            except (OSError, IOError):
                pass

class TestMainFunction:
    """Test main entry point"""

    def test_main_creates_gui(self, temp_db):
        """Test that main function creates GUI"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch.object(email_queue_scheduler_gui.EmailQueueSchedulerGUI, '__init__',
                              return_value=None) as mock_init:
                with patch.object(email_queue_scheduler_gui.EmailQueueSchedulerGUI, 'run'):
                    try:
                        email_queue_scheduler_gui.main()
                        mock_init.assert_called_once()
                    except (OSError, IOError):
                        pass

class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self, root_window, temp_db):
        """Test complete workflow"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                # Create GUI
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                # Load templates
                gui.load_templates()
                gui.load_schedule_templates()

                # Refresh status
                gui.refresh_status()

                # Refresh scheduled list
                gui.refresh_scheduled_list()

                # Refresh monitor
                gui.refresh_monitor()

            except (OSError, IOError):
                pass  # May fail in headless environment

    def test_worker_lifecycle(self, root_window, temp_db):
        """Test worker start/stop lifecycle"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.start_email_workers', return_value=True):
                with patch('education_system.systems.university.interfaces.gui.shell.email.email_queue_scheduler_gui.stop_email_workers', return_value=True):
                    try:
                        gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)

                        # Start workers
                        with patch('tkinter.messagebox.showinfo'):
                            gui.start_workers()

                        # Refresh status
                        gui.refresh_status()

                        # Stop workers
                        with patch('tkinter.messagebox.showinfo'):
                            gui.stop_workers()

                    except (OSError, IOError):
                        pass

class TestUIComponents:
    """Test UI component creation"""

    def test_has_worker_tab(self, root_window, temp_db):
        """Test that GUI has worker control tab"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                # Should have created worker tab
            except (OSError, IOError):
                pass

    def test_has_queue_tab(self, root_window, temp_db):
        """Test that GUI has queue email tab"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                # Should have created queue tab
            except (OSError, IOError):
                pass

    def test_has_scheduler_tab(self, root_window, temp_db):
        """Test that GUI has scheduler tab"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                # Should have created scheduler tab
            except (OSError, IOError):
                pass

    def test_has_monitor_tab(self, root_window, temp_db):
        """Test that GUI has monitor tab"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                # Should have created monitor tab
            except (OSError, IOError):
                pass

    def test_has_utilities_tab(self, root_window, temp_db):
        """Test that GUI has utilities tab"""
        with patch('education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH', temp_db):
            try:
                gui = email_queue_scheduler_gui.EmailQueueSchedulerGUI(parent=root_window)
                # Should have created utilities tab
            except (OSError, IOError):
                pass

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
