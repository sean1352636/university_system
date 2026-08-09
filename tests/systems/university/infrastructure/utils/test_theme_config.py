"""
Test suite for theme_config.py

Tests the ThemeManager singleton, theme toggling, observer pattern,
and theme application functionality.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
import tkinter as tk
from tkinter import ttk
from education_system.systems.university.interfaces.gui.shell.theme_config import ThemeManager, get_theme_manager


@pytest.fixture
def reset_theme_manager():
    """Reset ThemeManager singleton before each test"""
    # Reset the singleton instance
    ThemeManager._instance = None
    ThemeManager._dark_mode = False
    yield
    # Cleanup after test
    ThemeManager._instance = None
    ThemeManager._dark_mode = False


@pytest.fixture
def theme_manager(reset_theme_manager):
    """Provide a fresh ThemeManager instance"""
    return ThemeManager()


@pytest.fixture
def root_window():
    """Provide a Tkinter root window for GUI tests"""
    root = tk.Tk()
    root.withdraw()  # Hide window during tests
    yield root
    try:
        root.destroy()
    except Exception:
        pass


class TestThemeManagerSingleton:
    """Test ThemeManager singleton pattern"""

    def test_singleton_instance(self, reset_theme_manager):
        """Test that ThemeManager is a singleton"""
        manager1 = ThemeManager()
        manager2 = ThemeManager()
        assert manager1 is manager2

    def test_get_instance_method(self, reset_theme_manager):
        """Test get_instance class method"""
        manager1 = ThemeManager.get_instance()
        manager2 = ThemeManager.get_instance()
        assert manager1 is manager2

    def test_get_theme_manager_function(self, reset_theme_manager):
        """Test module-level get_theme_manager function"""
        manager1 = get_theme_manager()
        manager2 = ThemeManager()
        assert manager1 is manager2


class TestThemeColors:
    """Test theme color definitions"""

    def test_light_theme_colors(self, theme_manager):
        """Test light theme has all required colors"""
        light_theme = theme_manager.light_theme
        required_colors = [
            'bg', 'fg', 'select_bg', 'select_fg', 'button_bg', 'button_fg',
            'entry_bg', 'entry_fg', 'frame_bg', 'label_bg', 'label_fg',
            'treeview_bg', 'treeview_fg', 'treeview_selected',
            'scrollbar_bg', 'scrollbar_fg'
        ]
        for color_key in required_colors:
            assert color_key in light_theme
            assert isinstance(light_theme[color_key], str)
            assert light_theme[color_key].startswith('#')

    def test_dark_theme_colors(self, theme_manager):
        """Test dark theme has all required colors"""
        dark_theme = theme_manager.dark_theme
        required_colors = [
            'bg', 'fg', 'select_bg', 'select_fg', 'button_bg', 'button_fg',
            'entry_bg', 'entry_fg', 'frame_bg', 'label_bg', 'label_fg',
            'treeview_bg', 'treeview_fg', 'treeview_selected',
            'scrollbar_bg', 'scrollbar_fg'
        ]
        for color_key in required_colors:
            assert color_key in dark_theme
            assert isinstance(dark_theme[color_key], str)
            assert dark_theme[color_key].startswith('#')

    def test_light_and_dark_themes_different(self, theme_manager):
        """Test that light and dark themes have different colors"""
        assert theme_manager.light_theme['bg'] != theme_manager.dark_theme['bg']
        assert theme_manager.light_theme['fg'] != theme_manager.dark_theme['fg']


class TestThemeToggling:
    """Test theme toggling functionality"""

    def test_initial_theme_is_light(self, theme_manager):
        """Test that initial theme is light mode"""
        assert not theme_manager.is_dark_mode()

    def test_toggle_dark_mode(self, theme_manager):
        """Test toggling to dark mode"""
        theme_manager.toggle_dark_mode()
        assert theme_manager.is_dark_mode()

    def test_toggle_back_to_light_mode(self, theme_manager):
        """Test toggling back to light mode"""
        theme_manager.toggle_dark_mode()  # to dark
        theme_manager.toggle_dark_mode()  # back to light
        assert not theme_manager.is_dark_mode()

    def test_set_dark_mode_true(self, theme_manager):
        """Test setting dark mode explicitly to True"""
        theme_manager.set_dark_mode(True)
        assert theme_manager.is_dark_mode()

    def test_set_dark_mode_false(self, theme_manager):
        """Test setting dark mode explicitly to False"""
        theme_manager.set_dark_mode(True)
        theme_manager.set_dark_mode(False)
        assert not theme_manager.is_dark_mode()

    def test_set_dark_mode_no_change(self, theme_manager):
        """Test that setting to same value doesn't trigger change"""
        observer_called = []

        def observer():
            observer_called.append(True)

        theme_manager.register_observer(observer)
        theme_manager.set_dark_mode(False)  # Already False
        assert len(observer_called) == 0

    def test_get_current_theme_light(self, theme_manager):
        """Test getting current theme when in light mode"""
        current_theme = theme_manager.get_current_theme()
        assert current_theme == theme_manager.light_theme

    def test_get_current_theme_dark(self, theme_manager):
        """Test getting current theme when in dark mode"""
        theme_manager.set_dark_mode(True)
        current_theme = theme_manager.get_current_theme()
        assert current_theme == theme_manager.dark_theme


class TestObserverPattern:
    """Test observer pattern implementation"""

    def test_register_observer(self, theme_manager):
        """Test registering an observer"""
        called = []

        def observer():
            called.append(True)

        theme_manager.register_observer(observer)
        theme_manager.toggle_dark_mode()
        assert len(called) == 1

    def test_multiple_observers(self, theme_manager):
        """Test multiple observers are notified"""
        called1 = []
        called2 = []

        def observer1():
            called1.append(True)

        def observer2():
            called2.append(True)

        theme_manager.register_observer(observer1)
        theme_manager.register_observer(observer2)
        theme_manager.toggle_dark_mode()

        assert len(called1) == 1
        assert len(called2) == 1

    def test_unregister_observer(self, theme_manager):
        """Test unregistering an observer"""
        called = []

        def observer():
            called.append(True)

        theme_manager.register_observer(observer)
        theme_manager.unregister_observer(observer)
        theme_manager.toggle_dark_mode()

        assert len(called) == 0

    def test_observer_not_registered_twice(self, theme_manager):
        """Test that same observer is not registered twice"""
        called = []

        def observer():
            called.append(True)

        theme_manager.register_observer(observer)
        theme_manager.register_observer(observer)  # Register again
        theme_manager.toggle_dark_mode()

        assert len(called) == 1  # Should only be called once

    def test_observer_exception_handling(self, theme_manager, capsys):
        """Test that observer exceptions don't break notification"""
        called_good = []

        def bad_observer():
            raise Exception("Observer error")

        def good_observer():
            called_good.append(True)

        theme_manager.register_observer(bad_observer)
        theme_manager.register_observer(good_observer)
        theme_manager.toggle_dark_mode()

        # Good observer should still be called
        assert len(called_good) == 1

        # Error should be printed
        captured = capsys.readouterr()
        assert "Error notifying observer" in captured.out


class TestStyleApplication:
    """Test theme application to ttk styles"""

    def test_apply_theme_to_style_light(self, theme_manager, root_window):
        """Test applying light theme to ttk.Style"""
        style = ttk.Style(root_window)
        theme_manager.set_dark_mode(False)
        theme_manager.apply_theme_to_style(style)

        # Check some style configurations
        frame_bg = style.lookup('TFrame', 'background')
        assert frame_bg is not None

    def test_apply_theme_to_style_dark(self, theme_manager, root_window):
        """Test applying dark theme to ttk.Style"""
        style = ttk.Style(root_window)
        theme_manager.set_dark_mode(True)
        theme_manager.apply_theme_to_style(style)

        # Check some style configurations
        frame_bg = style.lookup('TFrame', 'background')
        assert frame_bg is not None

    def test_treeview_style_configuration(self, theme_manager, root_window):
        """Test Treeview style configuration"""
        style = ttk.Style(root_window)
        theme_manager.apply_theme_to_style(style)

        # Verify Treeview configuration exists
        tree_bg = style.lookup('Treeview', 'background')
        assert tree_bg is not None


class TestWindowApplication:
    """Test theme application to windows"""

    def test_apply_theme_to_window(self, theme_manager, root_window):
        """Test applying theme to a window"""
        frame = tk.Frame(root_window)
        theme_manager.apply_theme_to_window(root_window)
        # Should not raise exception

    def test_apply_theme_with_canvas(self, theme_manager, root_window):
        """Test applying theme to window with Canvas widget"""
        canvas = tk.Canvas(root_window)
        canvas.pack()
        theme_manager.apply_theme_to_window(root_window)
        # Should not raise exception

    def test_apply_theme_with_text(self, theme_manager, root_window):
        """Test applying theme to window with Text widget"""
        text = tk.Text(root_window)
        text.pack()
        theme_manager.apply_theme_to_window(root_window)
        # Should not raise exception

    def test_apply_theme_with_listbox(self, theme_manager, root_window):
        """Test applying theme to window with Listbox widget"""
        listbox = tk.Listbox(root_window)
        listbox.pack()
        theme_manager.apply_theme_to_window(root_window)
        # Should not raise exception

    def test_apply_theme_with_nested_widgets(self, theme_manager, root_window):
        """Test applying theme to nested widgets"""
        frame = tk.Frame(root_window)
        frame.pack()
        inner_frame = tk.Frame(frame)
        inner_frame.pack()
        text = tk.Text(inner_frame)
        text.pack()

        theme_manager.apply_theme_to_window(root_window)
        # Should not raise exception


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_multiple_toggles(self, theme_manager):
        """Test multiple rapid toggles"""
        for _ in range(10):
            theme_manager.toggle_dark_mode()
        # Should be in light mode (even number of toggles)
        assert not theme_manager.is_dark_mode()

    def test_observer_with_no_toggles(self, theme_manager):
        """Test observer not called when no theme change"""
        called = []

        def observer():
            called.append(True)

        theme_manager.register_observer(observer)
        # Don't toggle
        assert len(called) == 0

    def test_theme_manager_persistence(self, reset_theme_manager):
        """Test that theme state persists across getInstance calls"""
        manager1 = ThemeManager.get_instance()
        manager1.set_dark_mode(True)

        manager2 = ThemeManager.get_instance()
        assert manager2.is_dark_mode()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
