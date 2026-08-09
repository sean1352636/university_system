"""Component extracted from the legacy menu router."""
from __future__ import annotations
from ..bootstrap.integrations import ValidationError

def switch_to_gui(auth_instance):
    """Switch from CLI to GUI interface without circular imports"""
    try:
        print("\n🔄 Switching to GUI interface...")
        print("Please wait while the GUI loads...")

        # Dynamic import to avoid circular imports
        import importlib
        gui_module = importlib.import_module('education_system.systems.university.interfaces.gui.shell.main')

        # Get the current user from the authenticated CLI session
        current_user = auth_instance.current_user if hasattr(auth_instance, 'current_user') else None

        # Use the centralized init_gui function with the logged-in user
        init_gui_func = getattr(gui_module, 'init_gui', None)
        if callable(init_gui_func):
            main_gui = init_gui_func(session_user=current_user)
        else:
            # Fallback to old method if init_gui is not available
            print("⚠️ Warning: Using legacy GUI initialization")
            if hasattr(gui_module, 'auth'):
                gui_module.auth = auth_instance
            safe_auth_check = getattr(gui_module, 'safe_auth_check', None)
            if callable(safe_auth_check):
                safe_auth_check(auth_instance)
            main_gui = gui_module.StudentManagementGUI(auth_instance)

        print("✅ GUI interface loaded successfully!")
        print("You can now close this CLI window if desired.")

        # Start the GUI application loop
        if hasattr(main_gui, 'run') and callable(main_gui.run):
            main_gui.run()
        elif hasattr(main_gui, 'root') and hasattr(main_gui.root, 'mainloop'):
            main_gui.root.mainloop()
        else:
            print("⚠️ Unable to determine GUI main loop entry point. Closing GUI instance.")
            return

    except ImportError as e:
        print(f"❌ Error: Could not import GUI module: {e}")
        print("Please ensure the GUI components are properly installed.")
        input("Press Enter to continue with CLI...")
    except (ValueError, TypeError, ValidationError) as e:
        print(f"❌ Error switching to GUI: {e}")
        print("Continuing with CLI interface...")
        input("Press Enter to continue...")
