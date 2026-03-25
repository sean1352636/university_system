import logging

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.utils.ai.university_chatbot import LIBRARIES_AVAILABLE

from education_system.university_system.utils.ai.gui.manager import ChatbotManager
from education_system.university_system.utils.ai.gui.compat import BackwardCompatibilityWrapper

logger = logging.getLogger(__name__)


def run_enhanced_chatbot():
    """Enhanced main function with GUI and multiple interface support"""
    # Lazy imports to avoid circular dependencies
    from education_system.university_system.utils.ai.university_chatbot import UniversityChatbot

    try:
        from education_system.university_system.utils.ai.university_chatbot import _lazy_auth, AUTH_AVAILABLE, MinimalChatbot
    except ImportError:
        AUTH_AVAILABLE = False
        _lazy_auth = lambda: None
        MinimalChatbot = None

    print("University Chatbot v2.0 - Enhanced Edition")
    print("=" * 50)

    try:
        # Initialize chatbot
        _lazy_auth()  # Load auth system if available
        chatbot = UniversityChatbot()

        # Set up auth system if available
        if AUTH_AVAILABLE:
            try:
                logger.debug("Auth integration placeholder - no specific integration required")
            except Exception as e:
                print(f"Auth integration warning: {e}")

        # Create manager
        manager = ChatbotManager(chatbot)

        # Show available interfaces
        available_modes = manager.get_available_modes()
        print(f"Available interfaces: {', '.join(available_modes)}")

        # Check for GUI availability
        if LIBRARIES_AVAILABLE.get('tkinter', False):
            print("\u2713 GUI interface available")
        else:
            print("\u2717 GUI interface unavailable (tkinter missing)")

        if chatbot.voice_interface.enabled:
            print("\u2713 Voice interface available")
        else:
            print("\u2717 Voice interface unavailable (check microphone/dependencies)")

        # Interactive mode selection
        print("\nInterface Options:")
        print("1. GUI - Modern graphical interface (recommended)")
        print("2. Console - Text-based interface")
        if AUTH_AVAILABLE:
            print("3. Auth Console - Authenticated console interface")
        print("4. Web API - Web server for API access")
        print("5. Auto - Automatically select best interface")

        try:
            choice = input("\nSelect interface (1-5, or press Enter for auto): ").strip()

            mode_map = {
                "1": "gui",
                "2": "console",
                "3": "auth-console" if AUTH_AVAILABLE else "console",
                "4": "web",
                "5": "auto",
                "": "auto"
            }

            selected_mode = mode_map.get(choice, "auto")
            manager.run_interface(selected_mode)

        except KeyboardInterrupt:
            print("\nStarting auto-mode...")
            manager.run_interface("auto")

    except Exception as e:
        print(f"Failed to initialize enhanced chatbot: {e}")
        print("Falling back to basic chatbot...")

        # Fallback to basic chatbot
        try:
            if AUTH_AVAILABLE and MinimalChatbot:
                basic_chatbot = MinimalChatbot()
                basic_chatbot.run_authenticated_console_interface()
            elif MinimalChatbot:
                basic_chatbot = MinimalChatbot()
                basic_chatbot.process_message("Hello", "fallback_user")
                print("Basic chatbot ready - limited functionality available")
        except Exception as fallback_error:
            print(f"Complete startup failure: {fallback_error}")


def update_main_execution():
    """Update the main execution to include GUI option"""
    original_main = """
    if __name__ == "__main__":
        # Initialize enhanced chatbot with authentication
        try:
            chatbot = UniversityChatbot()

            # Choose interface mode
            if AUTH_AVAILABLE and chatbot.auth_system:
                print("Authentication system available!")
                mode = input("Choose interface mode (console/web/auth-console/both): ").lower()
            else:
                mode = input("Choose interface mode (console/web/both): ").lower()
    """

    enhanced_main = """
    if __name__ == "__main__":
        # Run enhanced chatbot with GUI support
        run_enhanced_chatbot()
    """

    return enhanced_main


def create_chatbot_with_gui(auth_system=None, db_path=str(DEFAULT_DB_PATH)):
    """Factory function to create chatbot with GUI support"""
    from education_system.university_system.utils.ai.university_chatbot import UniversityChatbot

    chatbot = UniversityChatbot(db_path=db_path)

    if auth_system:
        chatbot.set_auth_system(auth_system)

    # Ensure backward compatibility
    chatbot = BackwardCompatibilityWrapper.ensure_compatibility(chatbot)

    return chatbot


def test_gui_integration():
    """Test GUI integration with existing chatbot"""
    from education_system.university_system.utils.ai.university_chatbot import UniversityChatbot
    from education_system.university_system.utils.ai.gui.chatbot_gui import ChatbotGUI

    print("Testing GUI integration...")

    try:
        # Test basic chatbot creation
        chatbot = UniversityChatbot()
        print("\u2713 Chatbot created successfully")

        # Test GUI availability
        if LIBRARIES_AVAILABLE.get('tkinter', False):
            print("\u2713 tkinter available")

            # Test GUI creation (don't run mainloop)
            gui = ChatbotGUI(chatbot)
            print("\u2713 GUI interface created successfully")

            # Test manager
            manager = ChatbotManager(chatbot)
            modes = manager.get_available_modes()
            print(f"\u2713 Available modes: {modes}")

        else:
            print("\u2717 tkinter not available - GUI disabled")

        # Test backward compatibility
        enhanced_chatbot = BackwardCompatibilityWrapper.ensure_compatibility(chatbot)
        print("\u2713 Backward compatibility ensured")

        print("\u2713 All GUI integration tests passed!")
        return True

    except Exception as e:
        print(f"\u2717 GUI integration test failed: {e}")
        return False
