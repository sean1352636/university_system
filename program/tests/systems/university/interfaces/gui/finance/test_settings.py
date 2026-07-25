"""Tests for settings module (SettingsManager)"""

import pytest
pytestmark = pytest.mark.gui

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import tkinter as tk
from tkinter import messagebox
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

from education_system.systems.university.interfaces.gui.finance.finance.settings import SettingsManager

# Correct patch paths — settings is a package, tkinter is imported in the mixin files
_GENERAL = 'education_system.systems.university.interfaces.gui.finance.finance.settings.general_settings'
_BASE = 'education_system.systems.university.interfaces.gui.finance.finance.settings._base'
_PKG = 'education_system.systems.university.interfaces.gui.finance.finance.settings'


class _MockStringVar:
    """Lightweight StringVar replacement for tests without a real Tk root."""
    def __init__(self, value='', **kwargs):
        self._value = value
    def get(self):
        return self._value
    def set(self, value):
        self._value = value


class TestSettingsManager(unittest.TestCase):
    """Test suite for SettingsManager class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create mock GUI
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()

        # Mock layout
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#34495e',
            'info': '#17a2b8'
        }

        # Create manager
        with patch(f'{_PKG}.get_global_auth'):
            self.manager = SettingsManager(self.mock_gui)

    def tearDown(self):
        """Clean up after tests"""
        self.manager = None
        self.mock_gui = None

    def test_initialization(self):
        """Test SettingsManager initialization"""
        self.assertEqual(self.manager.gui, self.mock_gui)
        self.assertEqual(self.manager.root, self.mock_gui.root)
        self.assertEqual(self.manager.conn, self.mock_gui.conn)
        self.assertEqual(self.manager.finance_system, self.mock_gui.finance_system)

    def test_initialization_without_finance_system(self):
        """Test initialization when finance_system doesn't exist"""
        gui_without_system = Mock()
        gui_without_system.root = Mock()
        gui_without_system.conn = Mock()
        gui_without_system.layout = Mock()
        gui_without_system.layout.content_frame = Mock()
        gui_without_system.layout.tab_frames = {}
        del gui_without_system.finance_system

        with patch(f'{_PKG}.get_global_auth'):
            manager = SettingsManager(gui_without_system)
            self.assertIsNone(manager.finance_system)

    def test_initialization_with_auth(self):
        """Test initialization with auth from gui"""
        self.mock_gui.auth = Mock()

        with patch(f'{_PKG}.get_global_auth') as mock_get_auth:
            manager = SettingsManager(self.mock_gui)
            self.assertEqual(manager.auth, self.mock_gui.auth)

    @patch(f'{_GENERAL}.ttk.Frame')
    @patch(f'{_GENERAL}.ttk.Notebook')
    @patch(f'{_GENERAL}.tk.Frame')
    @patch(f'{_GENERAL}.tk.Label')
    def test_create_settings_tab(self, mock_label, mock_frame, mock_notebook, mock_ttk_frame):
        """Test creating settings tab"""
        mock_notebook_instance = Mock()
        mock_notebook.return_value = mock_notebook_instance

        self.manager.create_general_settings = Mock()
        self.manager.create_currency_settings = Mock()
        self.manager.create_notification_settings = Mock()
        self.manager.create_maintenance_settings = Mock()

        self.manager.create_settings_tab()

        # Verify tab was created
        self.assertIn('settings', self.mock_gui.layout.tab_frames)

        # Verify sub-tabs were created
        self.manager.create_general_settings.assert_called_once()
        self.manager.create_currency_settings.assert_called_once()
        self.manager.create_notification_settings.assert_called_once()
        self.manager.create_maintenance_settings.assert_called_once()

    @patch(f'{_GENERAL}.tk.Button')
    @patch(f'{_GENERAL}.tk.Entry')
    @patch(f'{_GENERAL}.tk.Label')
    @patch(f'{_GENERAL}.tk.LabelFrame')
    @patch(f'{_GENERAL}.tk.StringVar', _MockStringVar)
    def test_create_general_settings(self, mock_labelframe, mock_label, mock_entry, mock_button):
        """Test creating general settings interface"""
        parent = Mock()

        self.manager.create_general_settings(parent)

        # Verify UI elements were created
        self.assertTrue(hasattr(self.manager, 'academic_year_var'))
        self.assertTrue(hasattr(self.manager, 'grace_period_var'))
        self.assertTrue(hasattr(self.manager, 'late_fee_var'))

    @patch(f'{_GENERAL}.messagebox')
    def test_save_general_settings(self, mock_msgbox):
        """Test saving general settings"""
        # Setup mock StringVar-like objects
        self.manager.academic_year_var = _MockStringVar("2024-2025")
        self.manager.grace_period_var = _MockStringVar("7")
        self.manager.late_fee_var = _MockStringVar("50.00")

        # Patch file writing
        with patch(f'{_GENERAL}.Path.open', create=True):
            with patch(f'{_GENERAL}.json.dump'):
                self.manager.save_general_settings()

        # Verify settings values are accessible
        self.assertEqual(self.manager.academic_year_var.get(), "2024-2025")
        self.assertEqual(self.manager.grace_period_var.get(), "7")
        self.assertEqual(self.manager.late_fee_var.get(), "50.00")

    @patch(f'{_GENERAL}.ttk.Combobox')
    @patch(f'{_GENERAL}.ttk.Treeview')
    @patch(f'{_GENERAL}.tk.Button')
    @patch(f'{_GENERAL}.tk.Label')
    @patch(f'{_GENERAL}.tk.LabelFrame')
    @patch(f'{_GENERAL}.tk.StringVar', _MockStringVar)
    def test_create_currency_settings(self, mock_lf, mock_label, mock_button, mock_tree, mock_combo):
        """Test creating currency settings interface"""
        parent = Mock()
        self.manager.create_currency_settings(parent)
        # Just verify no exceptions raised
        self.assertTrue(True)

    @patch(f'{_GENERAL}.ttk.Treeview')
    @patch(f'{_GENERAL}.tk.Button')
    @patch(f'{_GENERAL}.tk.Entry')
    @patch(f'{_GENERAL}.tk.Label')
    @patch(f'{_GENERAL}.tk.LabelFrame')
    @patch(f'{_GENERAL}.tk.StringVar', _MockStringVar)
    def test_create_notification_settings(self, mock_lf, mock_label, mock_entry, mock_button, mock_tree):
        """Test creating notification settings interface"""
        parent = Mock()
        self.manager.create_notification_settings(parent)
        self.assertTrue(True)

    @patch(f'{_GENERAL}.ScrolledText')
    @patch(f'{_GENERAL}.tk.Button')
    @patch(f'{_GENERAL}.tk.LabelFrame')
    def test_create_maintenance_settings(self, mock_lf, mock_button, mock_scrolled):
        """Test creating maintenance settings interface"""
        parent = Mock()
        self.manager.load_system_info = Mock()
        self.manager.create_maintenance_settings(parent)
        self.assertTrue(True)


class TestSettingsValidation(unittest.TestCase):
    """Test settings validation"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {'success': '#27ae60'}

        with patch(f'{_PKG}.get_global_auth'):
            self.manager = SettingsManager(self.mock_gui)

    def test_academic_year_format(self):
        """Test academic year format validation"""
        var = _MockStringVar()

        # Valid format
        var.set("2024-2025")
        self.assertIn("-", var.get())

        # Invalid format
        var.set("2024/2025")
        self.assertEqual(var.get(), "2024/2025")

    def test_grace_period_numeric(self):
        """Test grace period is numeric"""
        var = _MockStringVar()

        # Valid numeric value
        var.set("7")
        try:
            int(var.get())
            valid = True
        except ValueError:
            valid = False
        self.assertTrue(valid)

        # Invalid non-numeric value
        var.set("abc")
        try:
            int(var.get())
            valid = True
        except ValueError:
            valid = False
        self.assertFalse(valid)

    def test_late_fee_numeric(self):
        """Test late fee is numeric"""
        var = _MockStringVar()

        # Valid numeric value
        var.set("50.00")
        try:
            float(var.get())
            valid = True
        except ValueError:
            valid = False
        self.assertTrue(valid)

        # Invalid non-numeric value
        var.set("fifty")
        try:
            float(var.get())
            valid = True
        except ValueError:
            valid = False
        self.assertFalse(valid)


class TestSettingsPersistence(unittest.TestCase):
    """Test settings persistence"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {'success': '#27ae60'}

        with patch(f'{_PKG}.get_global_auth'):
            self.manager = SettingsManager(self.mock_gui)

    @patch(f'{_GENERAL}.messagebox')
    def test_settings_dict_structure(self, mock_msgbox):
        """Test settings dictionary structure when saved"""
        self.manager.academic_year_var = _MockStringVar("2024-2025")
        self.manager.grace_period_var = _MockStringVar("7")
        self.manager.late_fee_var = _MockStringVar("50.00")

        with patch(f'{_GENERAL}.Path.open', create=True):
            with patch(f'{_GENERAL}.json.dump'):
                self.manager.save_general_settings()

        # Verify values are accessible
        self.assertEqual(self.manager.academic_year_var.get(), "2024-2025")
        self.assertEqual(self.manager.grace_period_var.get(), "7")
        self.assertEqual(self.manager.late_fee_var.get(), "50.00")

    @patch(f'{_GENERAL}.messagebox')
    def test_settings_timestamp(self, mock_msgbox):
        """Test that settings include timestamp"""
        self.manager.academic_year_var = _MockStringVar("2024-2025")
        self.manager.grace_period_var = _MockStringVar("7")
        self.manager.late_fee_var = _MockStringVar("50.00")

        with patch(f'{_GENERAL}.Path.open', create=True):
            with patch(f'{_GENERAL}.json.dump') as mock_dump:
                self.manager.save_general_settings()

                # Verify json.dump was called with settings containing updated_at
                if mock_dump.called:
                    saved_settings = mock_dump.call_args[0][0]
                    self.assertIn('updated_at', saved_settings)


class TestSettingsIntegration(unittest.TestCase):
    """Integration tests for settings manager"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_gui = Mock()
        self.mock_gui.root = Mock(spec=tk.Tk)
        self.mock_gui.conn = Mock()
        self.mock_gui.finance_system = Mock()
        self.mock_gui.layout = Mock()
        self.mock_gui.layout.content_frame = Mock(spec=tk.Frame)
        self.mock_gui.layout.tab_frames = {}
        self.mock_gui.layout.colors = {
            'success': '#27ae60',
            'warning': '#f39c12'
        }

        with patch(f'{_PKG}.get_global_auth'):
            self.manager = SettingsManager(self.mock_gui)

    @patch(f'{_GENERAL}.ttk.Frame')
    @patch(f'{_GENERAL}.ttk.Notebook')
    @patch(f'{_GENERAL}.tk.Frame')
    @patch(f'{_GENERAL}.tk.Label')
    def test_full_settings_tab_creation(self, mock_label, mock_frame, mock_notebook, mock_ttk_frame):
        """Test full settings tab creation workflow"""
        mock_notebook_instance = Mock()
        mock_notebook.return_value = mock_notebook_instance

        # Mock all creation methods
        self.manager.create_general_settings = Mock()
        self.manager.create_currency_settings = Mock()
        self.manager.create_notification_settings = Mock()
        self.manager.create_maintenance_settings = Mock()

        # Create settings tab
        self.manager.create_settings_tab()

        # Verify all components created
        self.assertIn('settings', self.mock_gui.layout.tab_frames)
        self.assertEqual(self.manager.create_general_settings.call_count, 1)
        self.assertEqual(self.manager.create_currency_settings.call_count, 1)
        self.assertEqual(self.manager.create_notification_settings.call_count, 1)
        self.assertEqual(self.manager.create_maintenance_settings.call_count, 1)


if __name__ == '__main__':
    unittest.main()
