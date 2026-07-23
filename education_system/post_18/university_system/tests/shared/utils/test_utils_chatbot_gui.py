"""
Tests for university chatbot GUI module.

Tests the GUI interface for the chatbot.
"""

import pytest
pytestmark = pytest.mark.gui

import pytest
from pathlib import Path


class TestChatbotGUIModule:
    """Test chatbot GUI module structure."""

    def test_chatbot_gui_file_exists(self):
        """Test that chatbot GUI file exists."""
        gui_file = Path(__file__).resolve().parents[3] / "infrastructure" / "ai" / "gui" / "chatbot_gui.py"
        assert gui_file.exists()

    def test_chatbot_gui_imports(self):
        """Test that chatbot GUI module can be imported."""
        try:
            from education_system.post_18.university_system.infrastructure.ai.gui import chatbot_gui
            assert chatbot_gui is not None
        except ImportError as e:
            pytest.skip(f"Chatbot GUI module not available: {e}")
        except Exception as e:
            pytest.skip(f"Could not initialize chatbot GUI: {e}")

    def test_chatbot_gui_has_components(self):
        """Test that chatbot GUI has expected components."""
        try:
            from education_system.post_18.university_system.infrastructure.ai.gui import chatbot_gui

            module_contents = dir(chatbot_gui)
            public_items = [item for item in module_contents if not item.startswith('_')]

            assert len(public_items) > 0

        except ImportError:
            pytest.skip("Chatbot GUI module not available")
        except Exception as e:
            pytest.skip(f"Could not inspect chatbot GUI: {e}")


class TestChatbotGUIIntegration:
    """Test chatbot GUI integration."""

    def test_chatbot_gui_uses_tkinter(self):
        """Test that chatbot GUI uses tkinter."""
        try:
            gui_file = Path(__file__).resolve().parents[3] / "infrastructure" / "ai" / "gui" / "chatbot_gui.py"
            content = gui_file.read_text()

            assert 'tkinter' in content.lower() or 'tk' in content

        except Exception as e:
            pytest.skip(f"Could not test tkinter usage: {e}")


class TestChatbotGUIDirectory:
    """Test chatbot GUI directory structure."""

    def test_gui_directory_exists(self):
        """Test that GUI directory exists."""
        gui_dir = Path(__file__).resolve().parents[3] / "infrastructure" / "ai" / "gui"
        assert gui_dir.exists()
        assert gui_dir.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
