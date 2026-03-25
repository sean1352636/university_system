from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path
from education_system.university_system.infrastructure.database.db import sqlite3
# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']
    
    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

class ModuleSchedulingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(_t("scheduling.window_title"))
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        # Initialize the backend scheduler
        self.scheduler = ModuleScheduler()

        # Run additional migrations for GUI compatibility
        self._migrate_database()

        # Configure styles
        self.setup_styles()

        # Create the main interface
        self.create_main_interface()

        # Status bar
        self.create_status_bar()

        # Load initial data
        self.refresh_all_data()

        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_auth(self, auth):
        """Optional; accept auth context from main app."""
        self._auth = auth

    def get_user_role(self):
        """Get the current user's role from authentication system"""
        try:
            if hasattr(self, '_auth') and self._auth:
                if hasattr(self._auth, 'current_user') and self._auth.current_user:
                    role = self._auth.current_user.get('role', '').lower()
                    return role
                elif hasattr(self._auth, 'user_role'):
                    return self._auth.user_role.lower()
            return None
        except Exception as e:
            print(f"Error getting user role: {e}")
            return None

    def is_admin(self):
        """Check if current user is admin"""
        role = self.get_user_role()
        return role == 'admin'

    def is_staff(self):
        """Check if current user is staff/instructor"""
        role = self.get_user_role()
        return role in ['staff', 'instructor', 'faculty']

    def is_student(self):
        """Check if current user is student"""
        role = self.get_user_role()
        return role == 'student'

    def setup_styles(self):
        """Configure ttk styles for better appearance"""
        style = ttk.Style()
        
        # Configure notebook styles
        style.configure('Main.TNotebook', tabposition='n')
        style.configure('Main.TNotebook.Tab', padding=[20, 8])
        
        # Configure treeview styles
        style.configure('Data.Treeview', rowheight=25)
        style.configure('Data.Treeview.Heading', font=('Arial', 10, 'bold'))
        
        # Configure button styles
        style.configure('Action.TButton', font=('Arial', 9, 'bold'))
        style.configure('Danger.TButton', foreground='red')
        style.configure('Success.TButton', foreground='green')

    def create_main_interface(self):
        """Create the main tabbed interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top toolbar with Return to Home button
        toolbar_frame = ttk.Frame(main_frame)
        toolbar_frame.pack(fill=tk.X, pady=(0, 10))

        # Return to Main Menu button
        home_button = ttk.Button(toolbar_frame, text=_t("scheduling.return_to_main_menu"),
                                command=self.return_to_main_menu, style='Action.TButton')
        home_button.pack(side=tk.LEFT, padx=5)

        # Activity Log button
        activity_button = ttk.Button(toolbar_frame, text=_t("scheduling.activity_log"),
                                     command=self.open_activity_log_window, style='Action.TButton')
        activity_button.pack(side=tk.LEFT, padx=5)

        # Title label
        title_label = ttk.Label(toolbar_frame, text=_t("scheduling.title"),
                               font=('Arial', 14, 'bold'))
        title_label.pack(side=tk.LEFT, padx=20)

        # Language button - shows current language
        lang_text = f"{_t('gui.change_language')} [{get_current_language_name()}]"
        self.language_btn = ttk.Button(toolbar_frame, text=lang_text,
                                       command=self.show_language_selector, style='Action.TButton')
        self.language_btn.pack(side=tk.RIGHT, padx=5)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame, style='Main.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create all tabs
        self.create_dashboard_tab()
        self.create_schedules_tab()
        self.create_rooms_tab()
        self.create_instructors_tab()
        self.create_timetables_tab()
        self.create_analytics_tab()
        self.create_conflicts_tab()
        self.create_management_tab()
        self.create_settings_tab()
        self.create_modules_tab()

        # Menu bar
        self.create_menu_bar()

    def create_menu_bar(self):
        """Create the application menu bar with role-based access"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        is_admin = self.is_admin()
        is_staff = self.is_staff()
        is_student = self.is_student()

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.file"), menu=file_menu)

        # Admin and Staff can import/export
        if is_admin or is_staff:
            file_menu.add_command(label=_t("scheduling.import_csv"), command=self.import_csv)
            file_menu.add_command(label=_t("scheduling.export_all"), command=self.export_all_data)
            file_menu.add_separator()

        # Admin only - Backup/Restore
        if is_admin:
            file_menu.add_command(label=_t("scheduling.backup"), command=self.create_backup)
            file_menu.add_command(label=_t("scheduling.restore"), command=self.restore_backup)
            file_menu.add_separator()

        file_menu.add_command(label=_t("menu.exit"), command=self.on_closing)

        # Staff and Admin can manage modules
        if is_admin or is_staff:
            file_menu.add_separator()
            file_menu.add_command(label=_t("scheduling.manage_modules"), command=self.show_modules_tab)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.view"), menu=view_menu)
        view_menu.add_command(label=_t("scheduling.refresh_all"), command=self.refresh_all_data)
        view_menu.add_command(label=_t("scheduling.grid_view"), command=self.show_grid_view)

        # Admin and Staff get CLI mode
        if is_admin or is_staff:
            view_menu.add_separator()
            view_menu.add_command(label=_t("scheduling.cli_mode"), command=self.launch_cli_mode)

        # Tools menu - Admin and Staff only
        if is_admin or is_staff:
            tools_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("menu.tools"), menu=tools_menu)
            tools_menu.add_command(label=_t("scheduling.scheduling_wizard"), command=self.schedule_module_interactively)
            tools_menu.add_separator()
            tools_menu.add_command(label=_t("scheduling.detect_conflicts"), command=self.detect_all_conflicts)
            tools_menu.add_command(label=_t("scheduling.data_validation"), command=self.validate_data)
            tools_menu.add_command(label=_t("scheduling.generate_reports"), command=self.generate_reports)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("scheduling.user_guide"), command=self.show_help)
        help_menu.add_command(label=_t("scheduling.about"), command=self.show_about)

    def create_status_bar(self):
        """Create the status bar at the bottom"""
        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=2)

        # Status label
        self.status_label = ttk.Label(self.status_bar, text=_t("common.ready"), relief=tk.SUNKEN)
        self.status_label.pack(side=tk.LEFT, padx=2)

        # Database status
        self.db_status_label = ttk.Label(self.status_bar, text=_t("scheduling.database_connected"), relief=tk.SUNKEN)
        self.db_status_label.pack(side=tk.RIGHT, padx=2)

        # CLI button
        ttk.Button(self.status_bar, text=_t("scheduling.cli_mode"), command=self.launch_cli_mode).pack(side=tk.RIGHT, padx=2)

    def update_status(self, message):
        """Update status bar message"""
        self.status_label.config(text=message)
        self.root.update()

    def log_activity(self, message):
        """Alias for update_activity_log for backward compatibility"""
        self.update_activity_log(message)

    def update_activity_log(self, message):
        """Update activity log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # Update dashboard activity
        self.activity_text.config(state=tk.NORMAL)
        self.activity_text.insert(1.0, log_entry)
        # Keep only last 100 lines
        lines = self.activity_text.get(1.0, tk.END).split('\n')
        if len(lines) > 100:
            self.activity_text.delete(1.0, tk.END)
            self.activity_text.insert(1.0, '\n'.join(lines[:100]))
        self.activity_text.config(state=tk.DISABLED)
        
        # Update management log
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(1.0, log_entry)
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 200:
            self.log_text.delete(1.0, tk.END)
            self.log_text.insert(1.0, '\n'.join(lines[:200]))
        self.log_text.config(state=tk.DISABLED)

    def refresh_all_data(self):
        """Refresh all data in the interface"""
        try:
            self.update_status("Refreshing data...")
            self.refresh_dashboard()
            self.refresh_schedules()
            self.refresh_rooms()
            self.refresh_instructors()
            self.refresh_conflicts()
            self.refresh_holidays()
            self.load_settings()
            self.refresh_modules()
            self.update_status("Data refreshed successfully")
        except Exception as e:
            self.update_status(f"Error refreshing data: {str(e)}")
            messagebox.showerror("Error", f"Failed to refresh data: {str(e)}", parent=self.root)

    def return_to_main_menu(self):
        """Return to the main menu/GUI by closing this child window"""
        if messagebox.askyesno("Return to Main Menu", "Do you want to close this window and return to the main menu?", parent=self.root):
            try:
                self.root.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to return to main menu: {str(e)}", parent=self.root)

    def show_help(self):
        """Show user guide"""
        help_window = tk.Toplevel(self.root)
        help_window.title("User Guide")
        help_window.geometry("700x500")
        
        help_text = scrolledtext.ScrolledText(help_window, font=('Arial', 10))
        help_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        guide_content = """
ENHANCED MODULE SCHEDULING SYSTEM - USER GUIDE

OVERVIEW:
This system provides comprehensive module scheduling and timetable management
capabilities with advanced analytics, conflict detection, and reporting features.

MAIN FEATURES:

📊 DASHBOARD:
- View system statistics and overview
- Quick access to common actions
- Recent activity monitoring

📅 SCHEDULES:
- Add, edit, and delete module schedules
- Search and filter schedules
- Automatic conflict detection

🏢 ROOMS:
- Manage room information
- Track room utilization
- Room capacity and equipment details

👨‍🏫 INSTRUCTORS:
- Instructor information management
- Workload tracking and analysis
- Department organization

📋 TIMETABLES:
- Generate student and instructor timetables
- Multiple export formats (PDF, CSV, Excel, iCal)
- Conflict checking for students

📊 ANALYTICS:
- Room utilization reports
- Instructor workload analysis
- Peak usage statistics
- Visual charts and graphs

⚠️ CONFLICTS:
- Automatic conflict detection
- Room and instructor double-booking detection
- Student schedule conflict checking
- Conflict resolution tracking

💾 MANAGEMENT:
- Database backup and restore
- Data validation and repair
- Import/export capabilities
- Schedule templates

⚙️ SETTINGS:
- System configuration
- Holiday management
- Academic calendar
- Email notifications

GETTING STARTED:

1. Start by adding rooms in the Rooms tab
2. Add instructors in the Instructors tab
3. Create module schedules in the Schedules tab
4. Generate timetables in the Timetables tab
5. Use Analytics to monitor system usage
6. Check for conflicts regularly

TIPS:
- Use the search functionality to quickly find information
- Regular backups are recommended
- Check for conflicts after making schedule changes
- Use templates to save and reuse common schedule patterns

For technical support or additional features, refer to the original
command-line interface using the CLI Mode button.
        """
        
        help_text.insert(tk.END, guide_content)
        help_text.config(state=tk.DISABLED)

    def show_about(self):
        """Show about dialog"""
        about_text = """
Enhanced Module Scheduling System - GUI Version

A comprehensive solution for academic scheduling and timetable management.

Features:
• Advanced scheduling with conflict detection
• Analytics and reporting capabilities  
• Multiple export formats
• Data backup and validation
• Template management
• Visual charts and graphs

This GUI version maintains full backward compatibility with the original
command-line interface while providing an intuitive graphical interface.

Version: 2.0
Developer: Academic Systems Team
        """
        
        messagebox.showinfo("About", about_text, parent=self.root)

    def show_language_selector(self):
        """Show language selection dialog"""
        old_lang = get_current_language()

        # Use the centralized GUI language selector
        if GUI_LANG_SELECTOR_AVAILABLE:
            new_lang = show_gui_language_selector(self.root)
        else:
            messagebox.showwarning(
                _t("common.warning"),
                _t("scheduling.language_selector_unavailable"),
                parent=self.root
            )
            return

        # If language changed, notify user and refresh
        if new_lang != old_lang:
            messagebox.showinfo(
                _t("gui.language_changed"),
                _t("gui.restart_required"),
                parent=self.root
            )
            # Restart the GUI to apply language changes
            self.restart_gui()

    def restart_gui(self):
        """Restart the GUI to apply language changes"""
        try:
            self.root.destroy()
            # Re-initialize i18n
            init_i18n()
            # Restart the application
            new_root = tk.Tk()
            app = ModuleSchedulingGUI(new_root)
            new_root.mainloop()
        except Exception as e:
            print(f"Error restarting GUI: {e}")

    def on_closing(self):
        """Handle application closing"""
        if messagebox.askokcancel(_t("common.quit"), _t("scheduling.confirm_quit"), parent=self.root):
            try:
                # Create final backup if auto-backup is enabled
                auto_backup = self.scheduler.get_system_setting('auto_backup', 'True')
                if auto_backup == 'True':
                    self.scheduler.create_backup(description="Application exit backup")

                self.root.destroy()
            except Exception:
                self.root.destroy()

    def get_system_setting(self, key, default=None):
        """Get a system setting value"""
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT value FROM system_settings WHERE key = ?', (key,))
            result = cursor.fetchone()

            return result[0] if result else default

def main():
    """Main function to launch the GUI application"""
    try:
        # Check if the original module is available
        if not os.path.exists('module_scheduling.py'):
            print("Warning: module_scheduling.py not found. Some features may be limited.")
        
        # Create the main window
        root = tk.Tk()
        
        # Set application icon (if available)
        try:
            root.iconbitmap('icon.ico')  # You can add an icon file
        except (FileNotFoundError, Exception):
            pass
        
        # Create and run the application
        app = ModuleSchedulingGUI(root)
        
        # Start the GUI event loop
        root.mainloop()
        
    except Exception as e:
        print(f"Error starting GUI application: {e}")
        print("\nTrying to launch CLI mode instead...")
        
        # Fallback to CLI mode if GUI fails
        try:
            from education_system.university_system.modules.domain.academics.services.module_scheduling import display_enhanced_scheduling_menu
            display_enhanced_scheduling_menu()
        except ImportError:
            print("CLI mode also unavailable. Please check your installation.")

def launch_gui():
    """Alternative launcher function"""
    main()

def launch_cli():
    """Launch CLI mode directly"""
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import display_enhanced_scheduling_menu
        display_enhanced_scheduling_menu()
    except ImportError:
        print("CLI mode not available. Please ensure module_scheduling.py is in the same directory.")

def create_desktop_shortcut():
    """Create a desktop shortcut for the application (Windows)"""
    try:
        import winshell
        from win32com.client import Dispatch
        
        desktop = winshell.desktop()
        path = os.path.join(desktop, "Module Scheduler.lnk")
        target = sys.executable
        wDir = os.path.dirname(os.path.abspath(__file__))
        icon = os.path.join(wDir, "icon.ico")
        
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(path)
        shortcut.Targetpath = target
        shortcut.Arguments = f'"{os.path.abspath(__file__)}"'
        shortcut.WorkingDirectory = wDir
        shortcut.IconLocation = icon if os.path.exists(icon) else target
        shortcut.save()
        
        print(f"Desktop shortcut created: {path}")
        
    except ImportError:
        print("winshell and pywin32 packages required for creating Windows shortcuts.")
    except Exception as e:
        print(f"Error creating desktop shortcut: {e}")

def setup_application():
    """Setup application for first-time use"""
    try:
        # Create necessary directories
        directories = ['timetable_reports', 'backups', 'analytics', 'templates']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
        
        # Initialize database if it doesn't exist
        if not os.path.exists(str(DEFAULT_DB_PATH)):
            print("Initializing database for first-time use...")
            scheduler = ModuleScheduler()
            print("Database initialized successfully.")
        
        print("Application setup complete!")
        
    except Exception as e:
        print(f"Error during application setup: {e}")

def launch_module_scheduling_gui():
    """Launch the Module Scheduling GUI."""
    import tkinter as tk
    root = tk.Tk()
    app = ModuleSchedulingGUI(root)
    root.mainloop()

def run_gui_with_database(db_path=None):
    """Run the GUI with a specific database path for backward compatibility."""
    if db_path:
        import os
        os.environ['MODULE_SCHEDULING_DB_PATH'] = db_path
    launch_module_scheduling_gui()

