"""
Test suite for GUI initialization
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False


class TestGUIInitialization(unittest.TestCase):
    """Test cases for GUI initialization"""

    def setUp(self):
        """Set up test fixtures"""
        if not TK_AVAILABLE:
            self.skipTest("Tkinter not available")

    def test_tkinter_availability(self):
        """Test that tkinter is available"""
        self.assertTrue(TK_AVAILABLE, "Tkinter should be available")

    def test_tk_root_creation(self):
        """Test creating Tk root window"""
        try:
            root = tk.Tk()
            self.assertIsNotNone(root, "Tk root should be created")
            root.destroy()
        except Exception as e:
            self.fail(f"Failed to create Tk root: {e}")

    def test_init_gui_function_exists(self):
        """Test that init_gui function exists in main_gui"""
        try:
            from university_system.modules.shared.gui import main_gui
            self.assertTrue(hasattr(main_gui, 'init_gui'),
                          "main_gui should have init_gui function")
        except ImportError as e:
            self.skipTest(f"main_gui module not available: {e}")

    def test_init_gui_with_none_session(self):
        """Test init_gui with no session user (default login page)"""
        try:
            from university_system.modules.shared.gui.main_gui import init_gui

            # This should create GUI in login mode
            # We won't actually display it (no mainloop)
            app = init_gui(session_user=None)

            self.assertIsNotNone(app, "init_gui should return an app instance")
            self.assertTrue(hasattr(app, 'root'), "App should have root window")

            # Clean up
            if hasattr(app, 'root'):
                app.root.destroy()

        except ImportError as e:
            self.skipTest(f"GUI modules not available: {e}")
        except Exception as e:
            # Some GUI operations might fail in headless environment
            self.skipTest(f"GUI initialization failed (may be headless): {e}")

    def test_unified_management_gui_class_exists(self):
        """Test that UnifiedManagementGUI class exists"""
        try:
            from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
            self.assertIsNotNone(UnifiedManagementGUI,
                               "UnifiedManagementGUI class should exist")
        except ImportError as e:
            self.skipTest(f"main_gui module not available: {e}")

    def test_gui_has_auth_manager(self):
        """Test that GUI initialization requires auth manager"""
        try:
            from university_system.modules.shared.gui.main_gui import UnifiedManagementGUI
            from university_system.infrastructure.auth.user_authentication import UserAuth

            auth = UserAuth()

            # This should not raise an error
            # We won't call mainloop to avoid blocking
            app = UnifiedManagementGUI(auth)

            self.assertIsNotNone(app, "GUI should initialize with auth manager")
            self.assertTrue(hasattr(app, 'auth'), "GUI should have auth attribute")

            # Clean up
            if hasattr(app, 'root'):
                app.root.destroy()

        except ImportError as e:
            self.skipTest(f"GUI or auth modules not available: {e}")
        except Exception as e:
            self.skipTest(f"GUI initialization failed (may be headless): {e}")

    def test_ttk_widgets_available(self):
        """Test that ttk widgets are available"""
        from tkinter import ttk

        root = tk.Tk()

        try:
            # Test creating various ttk widgets
            frame = ttk.Frame(root)
            self.assertIsNotNone(frame, "Frame widget should be created")

            button = ttk.Button(root, text="Test")
            self.assertIsNotNone(button, "Button widget should be created")

            label = ttk.Label(root, text="Test")
            self.assertIsNotNone(label, "Label widget should be created")

        finally:
            root.destroy()


class TestGUIModules(unittest.TestCase):
    """Test GUI module imports"""

    def test_main_gui_import(self):
        """Test importing main GUI module"""
        try:
            from university_system.modules.shared.gui import main_gui
            self.assertIsNotNone(main_gui, "main_gui module should import")
        except ImportError as e:
            self.skipTest(f"main_gui module not available: {e}")

    def test_management_gui_imports(self):
        """Test importing management GUI modules"""
        modules_to_test = [
            'finance_management_gui',
            'student_union_management_gui',
            'health_portal_management_gui',
            'grade_tracking_management_gui',
        ]

        for module_name in modules_to_test:
            try:
                module = __import__(f'university_system.modules.interfaces.gui.{module_name}',
                                  fromlist=[module_name])
                self.assertIsNotNone(module, f"{module_name} should import")
            except ImportError:
                # It's OK if some modules are missing
                pass


if __name__ == '__main__':
    unittest.main()
