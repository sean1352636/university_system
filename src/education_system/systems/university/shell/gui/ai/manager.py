from education_system.systems.university.infrastructure.ai.university_chatbot import LIBRARIES_AVAILABLE


class ChatbotManager:
    """Manager class to handle different interface modes"""

    def __init__(self, chatbot_instance):
        self.chatbot = chatbot_instance

    def run_interface(self, mode="auto"):
        """Run the appropriate interface based on mode"""
        available_modes = self.get_available_modes()

        if mode == "auto":
            # Auto-select best available mode
            if "gui" in available_modes and LIBRARIES_AVAILABLE.get('tkinter', False):
                mode = "gui"
            elif "auth-console" in available_modes:
                mode = "auth-console"
            else:
                mode = "console"

        print(f"Starting {mode} interface...")

        if mode == "gui" and "gui" in available_modes:
            self.run_gui()
        elif mode == "auth-console" and "auth-console" in available_modes:
            self.chatbot.run_authenticated_console_interface()
        elif mode == "console":
            self.chatbot.run_console_interface()
        elif mode == "web":
            self.run_web_interface()
        else:
            print(f"Mode '{mode}' not available. Available modes: {', '.join(available_modes)}")
            self.show_mode_selection()

    def get_available_modes(self):
        """Get list of available interface modes"""
        modes = ["console"]

        if LIBRARIES_AVAILABLE.get('tkinter', False):
            modes.append("gui")

        if self.chatbot.auth_system:
            modes.append("auth-console")

        if LIBRARIES_AVAILABLE.get('flask', False):
            modes.append("web")

        return modes

    def show_mode_selection(self):
        """Show interactive mode selection"""
        available_modes = self.get_available_modes()

        print("\nAvailable Interface Modes:")
        for i, mode in enumerate(available_modes, 1):
            description = self.get_mode_description(mode)
            print(f"{i}. {mode.upper()}: {description}")

        while True:
            try:
                choice = input(f"\nSelect interface mode (1-{len(available_modes)}): ").strip()
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(available_modes):
                        selected_mode = available_modes[idx]
                        self.run_interface(selected_mode)
                        break
                print("Invalid selection. Please try again.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

    def get_mode_description(self, mode):
        """Get description for interface mode"""
        descriptions = {
            "gui": "Modern graphical interface with voice support",
            "console": "Text-based console interface",
            "auth-console": "Authenticated console interface with user management",
            "web": "Web-based API interface"
        }
        return descriptions.get(mode, "Interface mode")

    def run_gui(self):
        """Run the GUI interface"""
        if not LIBRARIES_AVAILABLE.get('tkinter', False):
            print("GUI not available - tkinter library missing")
            return

    def run_web_interface(self):
        """Run web interface - not available"""
        print("Web interface not available - API has been removed")
