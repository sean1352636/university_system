"""Backward-compatible shim (tkinter GUI).

This module re-exports all public symbols from the refactored package so
that existing ``from education_system.university_system.infrastructure.ai.gui.university_chatbot_gui import ...``
statements continue to work unchanged.
"""

from education_system.university_system.infrastructure.ai.gui.chatbot_gui import ChatbotGUI
from education_system.university_system.infrastructure.ai.gui.manager import ChatbotManager
from education_system.university_system.infrastructure.ai.gui.compat import BackwardCompatibilityWrapper
from education_system.university_system.infrastructure.ai.gui.entry import (
    create_chatbot_with_gui,
    run_enhanced_chatbot,
    update_main_execution,
    test_gui_integration,
)

# Preserve original __all__
__all__ = [
    'ChatbotGUI',
    'ChatbotManager',
    'create_chatbot_with_gui',
    'run_enhanced_chatbot',
    'BackwardCompatibilityWrapper',
]

# Preserve original USAGE_EXAMPLES constant
USAGE_EXAMPLES = """
GUI Usage Examples:

# Start with GUI (recommended)
python university_chatbot.py

# Create chatbot with GUI programmatically
from university_chatbot import create_chatbot_with_gui, ChatbotManager

chatbot = create_chatbot_with_gui()
manager = ChatbotManager(chatbot)
manager.run_interface("gui")

# Run specific interface mode
manager.run_interface("console")  # Console only
manager.run_interface("gui")      # GUI only
manager.run_interface("auto")     # Best available

# Backward compatibility - existing code still works
chatbot = UniversityChatbot()
chatbot.run()  # Will now prefer GUI if available

Features:
- Modern GUI with voice support
- Authentication integration
- Real-time chat interface
- Settings and preferences
- Voice recording and playback
- Quick action buttons
- Responsive design
- Error handling and recovery
"""

# Main execution enhancement
if __name__ == "__main__":
    from education_system.university_system.infrastructure.ai.university_chatbot import (
        UniversityChatbot,
        LIBRARIES_AVAILABLE,
    )
    try:
        from education_system.university_system.infrastructure.ai.university_chatbot import AUTH_AVAILABLE
    except ImportError:
        AUTH_AVAILABLE = False

    # Initialize enhanced chatbot with authentication
    try:
        chatbot = UniversityChatbot()

        # Choose interface mode
        if AUTH_AVAILABLE and chatbot.auth_system:
            print("Authentication system available!")
            mode = input("Choose interface mode (console/web/auth-console/both): ").lower()
        else:
            mode = input("Choose interface mode (console/web/both): ").lower()

        if mode == "console":
            chatbot.run_console_interface()
        elif mode == "auth-console" and AUTH_AVAILABLE:
            chatbot.run_authenticated_console_interface()
        elif mode == "web":
            if AUTH_AVAILABLE:
                chatbot.setup_api_routes()
            chatbot.run_web_server()
        elif mode == "both":
            # Run web server in background, console in foreground
            if LIBRARIES_AVAILABLE['flask']:
                import threading
                if AUTH_AVAILABLE:
                    chatbot.setup_enhanced_api_routes()
                web_thread = threading.Thread(target=chatbot.run_web_server)
                web_thread.daemon = True
                web_thread.start()
                print("Web server started on http://localhost:5000")
                if AUTH_AVAILABLE:
                    print("Authentication API endpoints available:")
                    print("- POST /api/auth/login - Authenticate user")
                    print("- POST /api/auth/logout - Logout user")
                    print("- GET /api/auth/status - Check auth status")
                    print("- POST /api/chat/authenticated - Authenticated chat")
                    print("- POST /api/permissions/check - Check permissions")
            else:
                print("Flask not available - web server disabled")

            if AUTH_AVAILABLE and chatbot.auth_system:
                chatbot.run_authenticated_console_interface()
            else:
                chatbot.run_console_interface()
        else:
            print("Invalid mode selected. Starting console interface.")
            if AUTH_AVAILABLE and chatbot.auth_system:
                chatbot.run_authenticated_console_interface()
            else:
                chatbot.run_console_interface()

    except Exception as e:
        print(f"Failed to initialize chatbot: {e}")
        print("Please check your dependencies and try again.")
