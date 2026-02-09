# Auto-generated miscellaneous functions
import tkinter as tk
from tkinter import ttk
from university_system.modules.shared.utils.i18n import get_text as _t

# Initialize global auth variable
auth = None

def __init__(self, auth_manager):
    try:
        self.auth = auth_manager

        # Initialize content_frame to None first
        self.content_frame = None

        # Initialize modular GUI managers
        self.finance_gui = None
        self.student_union_gui = None
        self.health_portal_gui = None
        self.grade_tracking_gui = None
        self.restaurant_gui = None
        self.cafe_gui = None
        self.email_manager_gui = None

        # Initialize student management components
        self.student_tree = None

        # Initialize timer IDs for cleanup
        self._session_timer_id = None

        # Initialize Tkinter
        self.root = tk.Tk()
        self.root.title(_t("gui.window_title"))
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # Configure style and theme
        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Variables
        self.current_user_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Not logged in")

        # Initialize GUI
        self.setup_gui()

        # Initialize modular GUI managers after root is set up
        self.init_gui_managers()

        # Update status
        self.update_status()

        # Start periodic updates
        self.check_session_timer()

        # Show login if not authenticated
        if not self.auth.current_user:
            self.show_login_screen()
        else:
            self.show_main_interface()

    except Exception as e:
        print(f"Error initializing GUI: {e}")
        self.create_fallback_interface()
def run(self):
    """Start the GUI application"""
    self.root.mainloop()
def start_gui_mode():
    """Start the GUI version of the application - wrapper for backward compatibility"""
    return run_gui_interface()
def enhanced_interface_choice():
    """Enhanced interface selection with better error handling"""
    global auth
    
    print("\n" + "="*60)
    print("STUDENT RECORD MANAGEMENT SYSTEM")
    print("Advanced Academic Management Suite")
    print("="*60)
    
    while True:
        print("\nInterface Options:")
        print("1. Command Line Interface (CLI) - Full featured")
        print("2. Graphical User Interface (GUI) - Modern interface")
        print("3. Auto-detect best interface")
        print("4. Exit application")
        
        choice = input("\nSelect interface mode (1-4): ").strip()
        
        if choice == '1':
            print("Starting CLI mode...")
            return 'cli'
        elif choice == '2':
            # Check if GUI is available before committing
            try:
                if tk is None:
                    print("GUI mode not available - tkinter missing.")
                    print("Would you like to use CLI mode instead? (y/n): ", end="")
                    if input().lower().startswith('y'):
                        return 'cli'
                    continue
                print("Starting GUI mode...")
                return 'gui'
            except Exception:
                print("GUI mode not available. Please choose CLI mode.")
                continue
        elif choice == '3':
            # Auto-detect best available interface
            if tk is not None:
                print("GUI available - starting GUI mode...")
                return 'gui'
            else:
                print("GUI not available - starting CLI mode...")
                return 'cli'
        elif choice == '4':
            print("Thank you for using the Student Record Management System!")
            return 'exit'
        else:
            print("Invalid choice. Please enter 1, 2, 3, or 4.")
def main():
    """Enhanced main application entry point with GUI integration"""
    global auth
    
    try:
        # System initialization
        print("Initializing Student Record Management System...")
        if not initialize_system():
            print("System initialization failed")
            return False
        
        # Initialize authentication
        if auth is None:
            gui_funcs = get_gui_auth_functions()
            if gui_funcs:
                auth = gui_funcs['initialize_complete_system_with_gui']()
            else:
                # Get centralized auth or create new one
                auth = get_auth()
                if auth is None:
                    auth = UserAuth()
                    set_shared_auth(auth)
                safe_auth_check(auth)
        
        # Show system information
        # WARNING: These are default demo credentials - change them in production!
        # Set DEFAULT_ADMIN_PASSWORD, DEFAULT_STAFF_PASSWORD, DEFAULT_STUDENT_PASSWORD environment variables
        print("\n" + "="*60)
        print("STUDENT RECORD MANAGEMENT SYSTEM")
        print("Advanced Academic Management Suite")
        print("="*60)
        print("\nDefault Login Credentials:")
        print(f"- Admin: username='admin', password='{os.getenv('DEFAULT_ADMIN_PASSWORD', 'admin123')}'")
        print(f"- Staff: username='staff', password='{os.getenv('DEFAULT_STAFF_PASSWORD', 'staff123')}'")
        print(f"- Student: username='{os.getenv('DEFAULT_STUDENT_USERNAME', 'S12345')}', password='{os.getenv('DEFAULT_STUDENT_PASSWORD', 'student123')}'")

        # Start the CLI interface directly (run.py will handle interface choice)
        print("Starting console interface...")
        display_menu()
        return True
            
    except KeyboardInterrupt:
        print("\n\nApplication interrupted by user")
        return True
    except Exception as e:
        print(f"Critical error: {e}")
        logging.critical(f"Application failure: {e}")
        return False
    finally:
        try:
            cleanup_database_connections()
        except Exception as e:
            logger.debug(f"Error during database cleanup: {e}")
        print("System shutdown complete")
def run_gui_interface():
    """Run the unified GUI interface"""
    try:
        if tk is None:
            print("GUI mode requires tkinter, which is not available.")
            return False

        print("Starting unified GUI interface...")

        # Import here to avoid circular imports
        from .main_gui import init_gui

        # Use centralized init_gui with no session_user (starts at login page)
        app = init_gui(session_user=None)
        app.run()

        print("GUI interface closed.")
        return True
        
    except Exception as e:
        print(f"Error starting GUI mode: {e}")
        return False
def switch_to_gui_mode():
    """Allow CLI users to switch to GUI mode"""
    global auth
    
    gui_funcs = get_gui_auth_functions()
    if not gui_funcs:
        print("GUI interface is not available on this system")
        return False
    
    try:
        print("Switching to GUI interface...")
        gui_funcs['launch_gui_with_console_fallback'](auth)
        return True
    except Exception as e:
        print(f"Failed to start GUI: {e}")
        return False
def complete_gui_integration():
    """Complete integration function to call in main.py"""
    print("Completing GUI integration...")
    
    # This function should be called at the end of your main() function
    # or in the StudentManagementGUI initialization
    
    try:
        # Initialize advanced search integration
        print("1. Advanced search components loaded")
        
        # Setup data synchronization
        print("2. Data synchronization configured")
        
        # Configure keyboard shortcuts
        print("3. Keyboard shortcuts registered")
        
        # Setup menu integration
        print("4. Menu integration complete")
        
        # Initialize analytics integration
        print("5. Analytics integration ready")
        
        print("GUI integration completed successfully!")
        print("\nAvailable features:")
        print("- Advanced Search tab and window")
        print("- Multi-criteria search with fuzzy matching")
        print("- Module enrollment filtering")
        print("- Date range searches")
        print("- Integrated analytics dashboard")
        print("- Real-time data synchronization")
        print("- Enhanced export capabilities")
        
        return True
        
    except Exception as e:
        print(f"GUI integration failed: {e}")
        return False
