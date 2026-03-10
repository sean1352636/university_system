"""University Chatbot GUI package.

This package provides the graphical user interface for the University Chatbot.
It was split from a single large file into modular components using mixins.

Public API (backward-compatible):
    ChatbotGUI                  - Main GUI class
    ChatbotManager              - Interface mode manager
    BackwardCompatibilityWrapper - Compat helper
    create_chatbot_with_gui     - Factory function
    run_enhanced_chatbot        - Main entry point
    test_gui_integration        - Integration test
"""

from .chatbot_gui import ChatbotGUI
from .manager import ChatbotManager
from .compat import BackwardCompatibilityWrapper
from .entry import (
    create_chatbot_with_gui,
    run_enhanced_chatbot,
    test_gui_integration,
)

__all__ = [
    'ChatbotGUI',
    'ChatbotManager',
    'BackwardCompatibilityWrapper',
    'create_chatbot_with_gui',
    'run_enhanced_chatbot',
    'test_gui_integration',
]
