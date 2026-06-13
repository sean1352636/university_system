"""Tests for PDF export GUI module.

Tests the PDFExportGUI class and related functions.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import tempfile
import os

class TestPDFExportGUI:
    """Test cases for PDFExportGUI class."""

    @pytest.fixture
    def mock_tk(self):
        """Mock tkinter modules."""
        with patch.dict(
            "sys.modules",
            {
                "tkinter": MagicMock(),
                "tkinter.ttk": MagicMock(),
                "tkinter.filedialog": MagicMock(),
                "tkinter.messagebox": MagicMock(),
            },
        ):
            yield

    @pytest.fixture
    def mock_root(self):
        """Create a mock Tk root window."""
        root = MagicMock()
        root.winfo_screenwidth.return_value = 1920
        root.winfo_screenheight.return_value = 1080
        return root

    @pytest.fixture
    def mock_auth(self):
        """Create a mock auth manager."""
        auth = MagicMock()
        auth.current_user = {"id": 1, "username": "admin", "role": "admin"}
        auth.check_permission.return_value = True
        return auth

    def test_initialization(self, mock_tk, mock_root, mock_auth):
        """Test PDFExportGUI initialization."""
        from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

        gui = PDFExportGUI(mock_root, mock_auth)

        assert gui.root == mock_root
        assert gui.auth == mock_auth
        assert gui.export_window is None
        assert gui.is_exporting is False

    def test_show_export_window(self, mock_tk, mock_root, mock_auth):
        """Test showing the export window."""
        from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

        gui = PDFExportGUI(mock_root, mock_auth)

        with patch.object(gui, '_create_widgets'), \
             patch.object(gui, '_load_preview'), \
             patch('education_system.university_system.modules.shared.gui.pdf_export_gui.tk.Toplevel') as mock_toplevel:
            mock_toplevel.return_value = MagicMock()
            gui.show_export_window()

            # Should create a Toplevel window (export_window is set)
            assert gui.export_window is not None
            mock_toplevel.assert_called_once_with(mock_root)

    def test_progress_callback(self, mock_tk, mock_root, mock_auth):
        """Test progress callback updates."""
        from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

        gui = PDFExportGUI(mock_root, mock_auth)

        # Mock the variables
        gui.progress_var = MagicMock()
        gui.status_var = MagicMock()

        gui._update_progress("Test message", 50)

        gui.progress_var.set.assert_called_with(50)
        gui.status_var.set.assert_called_with("Test message")

    def test_export_complete_handling(self, mock_tk, mock_root, mock_auth):
        """Test export completion handling."""
        from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

        gui = PDFExportGUI(mock_root, mock_auth)
        gui.is_exporting = True
        gui.export_btn = MagicMock()
        gui.progress_var = MagicMock()
        gui.status_var = MagicMock()

        with patch("tkinter.messagebox.askyesno", return_value=False):
            gui._export_complete("/path/to/output.pdf")

        assert gui.is_exporting is False
        gui.progress_var.set.assert_called_with(100)
        gui.status_var.set.assert_called_with("Export complete!")

    def test_export_failed_handling(self, mock_tk, mock_root, mock_auth):
        """Test export failure handling."""
        from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

        gui = PDFExportGUI(mock_root, mock_auth)
        gui.is_exporting = True
        gui.export_btn = MagicMock()
        gui.status_var = MagicMock()

        with patch("tkinter.messagebox.showerror"):
            gui._export_failed("Test error message")

        assert gui.is_exporting is False
        gui.status_var.set.assert_called_with("Export failed")

class TestShowPDFExportGUIFunction:
    """Test the convenience function."""

    def test_show_pdf_export_gui_function(self):
        """Test the show_pdf_export_gui function."""
        with patch(
            "education_system.university_system.modules.shared.gui.pdf_export_gui.PDFExportGUI"
        ) as mock_class:
            from education_system.university_system.modules.shared.gui.pdf_export_gui import (
                show_pdf_export_gui,
            )

            mock_root = MagicMock()
            mock_auth = MagicMock()

            show_pdf_export_gui(mock_root, mock_auth)

            mock_class.assert_called_once_with(mock_root, mock_auth)
            mock_class.return_value.show_export_window.assert_called_once()

class TestPDFExportGUIIntegration:
    """Integration tests for PDF export GUI."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary test database."""
        from education_system.university_system.infrastructure.database.db import sqlite3
        fd, db_path = tempfile.mkstemp(suffix=".db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        cursor.execute("INSERT INTO test (id) VALUES (1)")
        conn.commit()
        conn.close()
        os.close(fd)

        yield db_path

        try:
            os.unlink(db_path)
        except Exception:
            pass

    def test_browse_output_sets_path(self):
        """Test that browse dialog sets output path."""
        with patch("tkinter.filedialog.asksaveasfilename") as mock_dialog:
            mock_dialog.return_value = "/path/to/output.pdf"

            from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

            mock_root = MagicMock()
            gui = PDFExportGUI(mock_root)
            gui.output_path_var = MagicMock()

            gui._browse_output()

            gui.output_path_var.set.assert_called_with("/path/to/output.pdf")

    def test_browse_output_cancelled(self):
        """Test browse dialog when cancelled."""
        with patch("tkinter.filedialog.asksaveasfilename") as mock_dialog:
            mock_dialog.return_value = ""  # Empty string = cancelled

            from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

            mock_root = MagicMock()
            gui = PDFExportGUI(mock_root)
            gui.output_path_var = MagicMock()

            gui._browse_output()

            # Should not set path when cancelled
            gui.output_path_var.set.assert_not_called()

    def test_close_window_when_not_exporting(self):
        """Test closing window when no export is running."""
        from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

        mock_root = MagicMock()
        gui = PDFExportGUI(mock_root)
        gui.is_exporting = False
        mock_window = MagicMock()
        gui.export_window = mock_window

        gui._close_window()

        mock_window.destroy.assert_called_once()
        assert gui.export_window is None

    def test_close_window_when_exporting_cancelled(self):
        """Test closing window when export is running and user cancels."""
        with patch("tkinter.messagebox.askyesno", return_value=False):
            from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

            mock_root = MagicMock()
            gui = PDFExportGUI(mock_root)
            gui.is_exporting = True
            gui.export_window = MagicMock()

            gui._close_window()

            # Should not destroy window
            gui.export_window.destroy.assert_not_called()
            assert gui.export_window is not None

    def test_close_window_when_exporting_confirmed(self):
        """Test closing window when export is running and user confirms."""
        with patch("tkinter.messagebox.askyesno", return_value=True):
            from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

            mock_root = MagicMock()
            gui = PDFExportGUI(mock_root)
            gui.is_exporting = True
            mock_window = MagicMock()
            gui.export_window = mock_window

            gui._close_window()

            # Should destroy window
            mock_window.destroy.assert_called_once()

class TestPDFExportGUIValidation:
    """Test input validation in PDF export GUI."""

    def test_start_export_no_output_path(self):
        """Test starting export with no output path."""
        with patch("tkinter.messagebox.showerror") as mock_error:
            from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

            mock_root = MagicMock()
            gui = PDFExportGUI(mock_root)
            gui.output_path_var = MagicMock()
            gui.output_path_var.get.return_value = ""

            gui._start_export()

            mock_error.assert_called_once()
            assert "output file path" in mock_error.call_args[0][1].lower()

    def test_start_export_invalid_max_rows(self):
        """Test starting export with invalid max rows."""
        with patch("tkinter.messagebox.showerror") as mock_error:
            from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

            mock_root = MagicMock()
            gui = PDFExportGUI(mock_root)
            gui.output_path_var = MagicMock()
            gui.output_path_var.get.return_value = "/path/to/output.pdf"
            gui.max_rows_var = MagicMock()
            gui.max_rows_var.get.return_value = "invalid"

            gui._start_export()

            mock_error.assert_called_once()

    def test_start_export_already_exporting(self):
        """Test starting export when one is already running."""
        with patch("tkinter.messagebox.showwarning") as mock_warning:
            from education_system.university_system.modules.shared.gui.pdf_export_gui import PDFExportGUI

            mock_root = MagicMock()
            gui = PDFExportGUI(mock_root)
            gui.is_exporting = True

            gui._start_export()

            mock_warning.assert_called_once()
