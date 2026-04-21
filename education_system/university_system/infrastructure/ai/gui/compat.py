from education_system.university_system.infrastructure.ai.university_chatbot import LIBRARIES_AVAILABLE


class BackwardCompatibilityWrapper:
    """Ensures backward compatibility with existing code"""

    @staticmethod
    def ensure_compatibility(chatbot_instance):
        """Ensure all original methods are still available"""
        from education_system.university_system.infrastructure.ai.gui.manager import ChatbotManager

        # Add any missing methods for backward compatibility
        if not hasattr(chatbot_instance, 'run_gui'):
            chatbot_instance.run_gui = lambda: print("GUI not available - install tkinter")

        # Ensure original interface methods work
        original_run = chatbot_instance.run
        def enhanced_run():
            """Enhanced run method with GUI fallback"""
            try:
                if LIBRARIES_AVAILABLE.get('tkinter', False):
                    manager = ChatbotManager(chatbot_instance)
                    manager.run_interface("auto")
                else:
                    original_run()
            except Exception:
                original_run()

        chatbot_instance.run = enhanced_run

        return chatbot_instance
