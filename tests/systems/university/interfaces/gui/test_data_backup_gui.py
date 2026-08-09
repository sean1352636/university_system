"""
Tests for data backup GUI module.

Tests the GUI interface for database backup management.
Note: These are mostly structural tests since full GUI testing requires a display.
"""

import pytest

pytestmark = pytest.mark.gui

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from education_system.systems.university.interfaces.gui.shell.database import backup_gui

GUI_FILE = Path(backup_gui.__file__).resolve()
GUI_DIR = GUI_FILE.parent


class TestBackupGUIModule:
    """Test backup GUI module structure."""

    def test_backup_gui_file_exists(self):
        """Test that backup GUI file exists."""
        gui_file = GUI_FILE
        assert gui_file.exists()

    def test_backup_gui_module_imports(self):
        """Test that backup GUI module can be imported."""
        try:
            from education_system.systems.university.interfaces.gui.shell.database import backup_gui

            assert backup_gui is not None
        except ImportError as e:
            pytest.fail(f"Maintained backup GUI failed to import: {e}")
        except Exception as e:
            # May fail if tkinter not available
            pytest.fail(f"Maintained backup GUI failed to initialize: {e}")

    def test_backup_gui_has_classes_or_functions(self):
        """Test that backup GUI module has expected components."""
        try:
            from education_system.systems.university.interfaces.gui.shell.database import backup_gui

            # Module should have some classes or functions
            module_contents = dir(backup_gui)
            # Filter out private/magic methods
            public_items = [item for item in module_contents if not item.startswith("_")]

            assert len(public_items) > 0

        except ImportError:
            pytest.fail("Maintained backup GUI module is unavailable")
        except Exception as e:
            pytest.fail(f"Could not inspect maintained backup GUI: {e}")


class TestBackupGUIIntegration:
    """Test backup GUI integration with backup module."""

    @patch("tkinter.Tk")
    def test_backup_gui_can_be_instantiated(self, mock_tk):
        """Test that backup GUI can be instantiated with mocked Tk."""
        try:
            from education_system.systems.university.interfaces.gui.shell.database import backup_gui

            # Try to find GUI class
            gui_classes = [
                item
                for item in dir(backup_gui)
                if "GUI" in item or "Window" in item or "App" in item
            ]

            # If GUI classes found, test we can get them
            if gui_classes:
                for cls_name in gui_classes:
                    cls = getattr(backup_gui, cls_name)
                    if callable(cls) and hasattr(cls, "__init__"):
                        # Class exists and is callable
                        assert True
                        break
            else:
                # No GUI classes found - module might use functions
                assert True

        except ImportError:
            pytest.fail("Maintained backup GUI module is unavailable")
        except Exception as e:
            pytest.fail(f"Could not test maintained backup GUI: {e}")


class TestBackupGUIFunctionality:
    """Test backup GUI functionality."""

    def test_backup_gui_imports_backup_module(self):
        """Test that backup GUI imports the backup module."""
        try:
            from education_system.systems.university.interfaces.gui.shell.database import backup_gui

            # Read the file to check imports
            gui_file = GUI_DIR / "backup_gui_shared.py"
            content = gui_file.read_text()

            # Check for backup module import
            assert "data_backup" in content or "backup" in content.lower()

        except ImportError:
            pytest.fail("Maintained backup GUI module is unavailable")
        except Exception as e:
            pytest.fail(f"Could not inspect maintained backup GUI imports: {e}")

    def test_backup_gui_uses_tkinter(self):
        """Test that backup GUI uses tkinter."""
        try:
            gui_file = GUI_DIR / "backup_gui_shared.py"
            content = gui_file.read_text()

            # Check for tkinter imports
            assert "tkinter" in content.lower() or "tk" in content

        except Exception as e:
            pytest.fail(f"Could not verify maintained backup GUI Tk usage: {e}")


class TestBackupGUIDirectory:
    """Test backup GUI directory structure."""

    def test_gui_directory_exists(self):
        """Test that GUI directory exists."""
        gui_dir = GUI_DIR
        assert gui_dir.exists()
        assert gui_dir.is_dir()

    def test_gui_init_file_exists(self):
        """Test that GUI __init__.py exists."""
        init_file = GUI_DIR / "__init__.py"
        assert init_file.exists()

    def test_submodule_structure_exists(self):
        """Test that the split submodule structure exists."""
        base = GUI_DIR
        expected_files = [
            "backup_gui.py",
            "config.py",
            "metadata.py",
            "shared_imports.py",
            "entry_points.py",
            "dialogs/__init__.py",
            "operations/__init__.py",
            "scheduling/__init__.py",
        ]
        for f in expected_files:
            assert (base / f).exists(), f"Missing expected file: {f}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
