# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox
import logging

# Import PDF export functionality
try:
    from education_system.university_system.modules.shared.gui.pdf_export_gui import show_pdf_export_gui as _pdf_export_gui_func
    PDF_EXPORT_GUI_AVAILABLE = True
except ImportError:
    _pdf_export_gui_func = None
    PDF_EXPORT_GUI_AVAILABLE = False

# Alias for translation function (underscore names not exported by import *)
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Import GUI availability flags and launcher functions
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    ADVANCED_SEARCH_GUI_AVAILABLE,
    AdvancedSearchGUI,
    ACTIVITY_LOGGER_GUI_AVAILABLE,
    DOCUMENT_MANAGER_GUI_AVAILABLE,
    DocumentManagerGUI,
    start_document_manager_gui,
    display_document_management_menu,
    ENHANCED_REPORTING_GUI_AVAILABLE,
    ReportingSystemGUI,
    start_enhanced_reporting_gui,
    launch_admissions_crm_gui,
    launch_predictive_analytics_gui,
    launch_business_intelligence_gui,
    launch_ai_features_gui,
    launch_integration_marketplace_gui,
    launch_mobile_app_pwa_gui,
    launch_blockchain_credentials_gui,
    EXTRAS_LAUNCHER_AVAILABLE,
    launch_extras_gui,
)

logger = logging.getLogger(__name__)

def show_document_manager(self):
    """Open the Document Management GUI (with fallbacks)."""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_document_manager"))
        return

    user = self.auth.current_user
    perms = user.get('permissions', [])
    role = user.get('role', '')

    # Be generous but safe: admin/staff or explicit perms
    allowed = (
        role in ('admin', 'staff') or
        any(p in perms for p in ['manage_documents', 'system_config', 'view_documents'])
    )
    if not allowed:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.no_permission_document_manager"))
        return

    try:
        if DOCUMENT_MANAGER_GUI_AVAILABLE and DocumentManagerGUI:
            win = tk.Toplevel(self.root)
            win.title(_t("extras_gui.titles.document_manager"))
            win.geometry("1400x900")
            try:
                win.transient(self.root)
                win.grab_set()
            except Exception as e:
                logger.debug(f"Could not set window as transient or grab focus: {e}")

            # Embed the full GUI with auth
            DocumentManagerGUI(win, auth=self.auth)
            print(_t("extras_gui.messages.document_manager_opened"))
            return

        # If import flag says unavailable, try the standalone launcher first
        if start_document_manager_gui:
            start_document_manager_gui()
            return

        raise RuntimeError(_t("extras_gui.errors.document_manager_not_available"))

    except Exception as e:
        # Final fallback: original CLI menu you already ship
        try:
            display_document_management_menu()
        except Exception as cli_err:
            messagebox.showerror(
                _t("extras_gui.titles.document_manager_short"),
                _t("extras_gui.errors.document_manager_failed").format(error=e, cli_error=cli_err)
            )
def show_enhanced_reporting_dashboard(self):
    """Open the Enhanced Reporting GUI as a child window, with safe fallbacks."""
    try:
        if not ENHANCED_REPORTING_GUI_AVAILABLE or ReportingSystemGUI is None:
            messagebox.showerror(
                _t("extras_gui.titles.enhanced_reporting"),
                _t("extras_gui.errors.enhanced_reporting_not_available")
            )
            return

        # Prefer embedding into a Toplevel to avoid creating a second Tk root
        try:
            top = tk.Toplevel(self.root)
            top.title(_t("extras_gui.titles.enhanced_reporting_dashboard"))
            top.geometry("1200x800")
            try:
                top.transient(self.root)
                top.grab_set()
            except Exception as e:
                logger.debug(f"Could not set window as transient or grab focus: {e}")

            # Instantiate the GUI into the Toplevel container
            app = ReportingSystemGUI(top)

            # If the reporting GUI supports auth injection, pass it
            try:
                if hasattr(app, "set_auth"):
                    app.set_auth(self.auth)
            except Exception as e:
                logger.debug(f"Could not set auth on app: {e}")

            print(_t("extras_gui.messages.enhanced_reporting_opened"))

        except Exception as embed_err:
            # Fallback to its own launcher (may create its own Tk root)
            try:
                if start_enhanced_reporting_gui:
                    start_enhanced_reporting_gui()
                else:
                    raise RuntimeError(_t("extras_gui.errors.enhanced_reporting_launcher_not_available"))
            except Exception as launch_err:
                messagebox.showerror(
                    _t("extras_gui.titles.enhanced_reporting"),
                    _t("extras_gui.errors.enhanced_reporting_launch_failed").format(error=launch_err)
                )
                print(_t("extras_gui.messages.enhanced_reporting_error").format(launch_err=launch_err, embed_err=embed_err))

    except Exception as e:
        messagebox.showerror(_t("extras_gui.titles.enhanced_reporting"), _t("extras_gui.errors.unexpected_error").format(error=e))
        print(_t("extras_gui.messages.unexpected_enhanced_reporting_error").format(error=e))
def show_pdf_export_gui(self):
    """Launch the PDF Database Export GUI"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_export"))
        return

    if not (self.auth.check_permission('export_data') or
            self.auth.check_permission('backup_restore') or
            self.auth.current_user.get('role') == 'admin'):
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.no_permission_export"))
        return

    try:
        if PDF_EXPORT_GUI_AVAILABLE and _pdf_export_gui_func is not None:
            _pdf_export_gui_func(self.root, self.auth)
            print(_t("extras_gui.messages.pdf_export_opened"))
        else:
            messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.pdf_export_not_available"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.pdf_export_failed").format(error=str(e)))
        logger.error(f"PDF Export GUI error: {e}")
def show_advanced_search_gui(self):
    """Open Advanced Search GUI in a new window"""
    if not ADVANCED_SEARCH_GUI_AVAILABLE:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.advanced_search_not_available"))
        return

    try:
        # Create a new window for the Advanced Search GUI
        search_window = tk.Toplevel(self.root)
        search_window.title(_t("extras_gui.titles.advanced_search"))
        search_window.geometry("1200x800")
        search_window.transient(self.root)

        # Center the window
        search_window.update_idletasks()
        x = (search_window.winfo_screenwidth() - search_window.winfo_width()) // 2
        y = (search_window.winfo_screenheight() - search_window.winfo_height()) // 2
        search_window.geometry(f"+{x}+{y}")

        # Initialize the Advanced Search GUI in the new window
        self.advanced_search_gui = AdvancedSearchGUI(search_window, auth=self.auth)

        # Store reference for data refresh
        self.advanced_search_refresh_callback = self.advanced_search_gui.refresh_data

        print(_t("extras_gui.messages.advanced_search_opened"))

    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.advanced_search_failed").format(error=str(e)))
        print(_t("extras_gui.messages.advanced_search_error").format(error=e))
def refresh_advanced_search(self):
    """Refresh the Advanced Search GUI if it's open"""
    if hasattr(self, 'advanced_search_refresh_callback') and self.advanced_search_refresh_callback:
        try:
            # Check if the Advanced Search window still exists before refreshing
            if (hasattr(self, 'advanced_search_gui') and
                    hasattr(self.advanced_search_gui, 'master') and
                    self.advanced_search_gui.master.winfo_exists()):
                self.advanced_search_refresh_callback()
                print(_t("extras_gui.messages.advanced_search_refreshed"))
            else:
                # Window was closed, clear the stale callback
                self.advanced_search_refresh_callback = None
        except tk.TclError:
            # Window was destroyed, clear the callback
            self.advanced_search_refresh_callback = None
        except Exception as e:
            print(_t("extras_gui.messages.advanced_search_refresh_warning").format(error=e))
def show_communication_dashboard_gui(self):
    """Launch the full Communication Dashboard GUI"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_communication"))
        return

    if not (self.auth.check_permission('send_emails') or
            self.auth.check_permission('access_communication_dashboard')):
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.no_permission_communication"))
        return

    try:
        # Create communication window
        comm_window = tk.Toplevel(self.root)
        comm_window.title(_t("extras_gui.titles.communication_dashboard"))
        comm_window.geometry("1400x900")
        comm_window.minsize(1200, 700)

        try:
            comm_window.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set comm_window as transient: {e}")

        # Initialize communication dashboard
        from education_system.university_system.modules.shared.gui.email.email_gui import EmailManagerGUI
        comm_gui = EmailManagerGUI(comm_window, auth=self.auth)

        print(_t("extras_gui.messages.communication_dashboard_opened"))

    except ImportError:
        # Fallback to existing email manager
        try:
            self.show_email_manager()
        except Exception:
            messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.communication_not_available"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.communication_dashboard_failed").format(error=str(e)))
def show_email_sms_gui(self):
    """Launch the Email & SMS Communication Hub"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_communication_hub"))
        return

    try:
        # Open the email manager GUI which now includes SMS
        from education_system.university_system.modules.shared.gui.email.email_manager_management_gui import EmailManagerManagementGUI

        email_gui = EmailManagerManagementGUI(self.root, self.auth)
        email_gui.show_email_manager()

        print(_t("extras_gui.messages.communication_hub_opened"))

    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.communication_hub_failed").format(error=str(e)))
        print(_t("extras_gui.messages.communication_hub_error").format(error=e))
def show_admissions_crm_gui(self):
    """Launch the Admissions Crm GUI"""
    launch_admissions_crm_gui(self.root, self.auth)
def show_predictive_analytics_gui(self):
    """Launch the Predictive Analytics GUI"""
    launch_predictive_analytics_gui(self.root, self.auth)
def show_business_intelligence_gui(self):
    """Launch the Business Intelligence GUI"""
    launch_business_intelligence_gui(self.root, self.auth)
def show_ai_features_gui(self):
    """Launch the Ai Features GUI"""
    launch_ai_features_gui(self.root, self.auth)
def show_integration_marketplace_gui(self):
    """Launch the Integration Marketplace GUI"""
    launch_integration_marketplace_gui(auth=self.auth, parent=self.root)
def show_mobile_app_pwa_gui(self):
    """Launch the Mobile App (PWA) Infrastructure GUI"""
    launch_mobile_app_pwa_gui(auth=self.auth)
def show_accessibility_tools_gui(self):
    """Launch the Accessibility & Accommodation Tools GUI"""
    try:
        from education_system.university_system.modules.domain.student_affairs.gui.accessibility_tools_gui import (
            launch_accessibility_tools_gui
        )
        launch_accessibility_tools_gui(self.root, self.auth)
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.accessibility_tools_failed").format(error=str(e)))
        print(_t("extras_gui.messages.accessibility_tools_error").format(error=e))
def show_blockchain_credentials_gui(self):
    """Launch the Blockchain Credentials & Digital Badges GUI"""
    launch_blockchain_credentials_gui(auth=self.auth)
def show_extras_launcher(self):
    """Launch the Extras & Tools Launcher (games, utilities, mini-projects)"""
    if not EXTRAS_LAUNCHER_AVAILABLE:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.extras_launcher_not_available"))
        return

    try:
        launch_extras_gui(self.root)
        print(_t("extras_gui.messages.extras_launcher_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.extras_launcher_failed").format(error=str(e)))
        print(_t("extras_gui.messages.extras_launcher_error").format(error=e))
def _show_feature_gui(self, title, description, cli_instruction):
    """Generic method to show feature GUI window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.login_required_feature").format(title=title))
        return

    try:
        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("900x600")
        window.minsize(800, 500)

        main_frame = ttk.Frame(window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=title, font=('Arial', 16, 'bold')).pack(pady=10)
        ttk.Label(main_frame, text=description, justify=tk.LEFT, wraplength=800).pack(pady=10)

        info_frame = ttk.LabelFrame(main_frame, text=_t("extras_gui.labels.how_to_access"), padding="15")
        info_frame.pack(fill=tk.X, pady=20)
        ttk.Label(info_frame, text=cli_instruction, font=('Arial', 11)).pack()

        ttk.Button(main_frame, text=_t("extras_gui.buttons.close"), command=window.destroy).pack(pady=10)

        print(_t("extras_gui.messages.feature_opened").format(title=title))

    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.feature_failed").format(title=title, error=str(e)))
        print(_t("extras_gui.messages.feature_error").format(title=title, error=e))

def show_police_station_gui(self):
    """Launch the Police Station Management GUI"""
    try:
        from education_system.university_system.modules.domain.campus.gui.security.police_station_gui import PoliceStationApp
        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.police_station"))
        window.geometry("1100x700")
        try:
            window.transient(self.root)
        except Exception:
            pass
        PoliceStationApp(window)
        print(_t("extras_gui.messages.police_station_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.police_station_failed").format(error=str(e)))
        print(_t("extras_gui.messages.police_station_error").format(error=e))

def show_security_desk_gui(self):
    """Launch the Security Desk GUI"""
    try:
        from education_system.university_system.modules.domain.campus.gui.security.security_desk_gui import SecurityDesk
        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.security_desk"))
        window.geometry("1000x700")
        try:
            window.transient(self.root)
        except Exception:
            pass
        SecurityDesk(window)
        print(_t("extras_gui.messages.security_desk_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.security_desk_failed").format(error=str(e)))
        print(_t("extras_gui.messages.security_desk_error").format(error=e))

def show_academic_misconduct_gui(self):
    """Launch the Academic Misconduct Panel GUI"""
    try:
        from education_system.shared.academic_misconduct.academic_misconduct_gui import AcademicMisconductPanel
        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.academic_misconduct"))
        window.geometry("1200x800")
        try:
            window.transient(self.root)
        except Exception:
            pass
        AcademicMisconductPanel(window, system_key='university')
        print(_t("extras_gui.messages.academic_misconduct_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.academic_misconduct_failed").format(error=str(e)))
        print(_t("extras_gui.messages.academic_misconduct_error").format(error=e))

def show_todo_app_gui(self):
    """Launch the To-Do List GUI"""
    try:
        from education_system.university_system.modules.shared.gui.tools.todo_app_gui import TodoApp
        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.todo_list"))
        window.geometry("500x600")
        try:
            window.transient(self.root)
        except Exception:
            pass
        TodoApp(window)
        print(_t("extras_gui.messages.todo_list_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.todo_list_failed").format(error=str(e)))
        print(_t("extras_gui.messages.todo_list_error").format(error=e))

def show_church_management_gui(self):
    """Launch the Church Management System GUI"""
    try:
        from education_system.university_system.modules.domain.campus.gui.community.church_management_gui import ChurchManagementSystem
        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.church_management"))
        window.geometry("1200x800")
        try:
            window.transient(self.root)
        except Exception:
            pass
        ChurchManagementSystem(window)
        print(_t("extras_gui.messages.church_management_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.church_management_failed").format(error=str(e)))
        print(_t("extras_gui.messages.church_management_error").format(error=e))

def show_bank_app_gui(self):
    """Launch the Bank Application GUI with Student Finance integration"""
    try:
        from education_system.university_system.modules.domain.finance.gui.bank_app import BankApp
        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.university_bank"))
        window.geometry("900x700")
        window.minsize(800, 600)
        try:
            window.transient(self.root)
        except Exception:
            pass
        # Pass auth for student finance integration
        BankApp(window, auth=self.auth)
        print(_t("extras_gui.messages.bank_app_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.bank_app_failed").format(error=str(e)))
        print(_t("extras_gui.messages.bank_app_error").format(error=e))

def show_exam_scheduler_gui(self):
    """Launch the Exam Scheduler GUI - student gets read-only viewer, staff/admin gets full app"""
    try:
        # Determine user role
        role = None
        if self.auth and self.auth.current_user:
            role = self.auth.current_user.get('role')

        window = tk.Toplevel(self.root)
        window.title(_t("extras_gui.titles.exam_scheduler"))
        window.geometry("1100x700")
        try:
            window.transient(self.root)
        except Exception:
            pass

        if role == 'student':
            # Students get read-only exam viewer
            from education_system.university_system.modules.domain.academics.gui.exam_scheduler import StudentExamViewer
            StudentExamViewer(window, auth=self.auth)
        else:
            # Staff/admin get full exam scheduler
            from education_system.university_system.modules.domain.academics.gui.exam_scheduler import ExamSchedulerApp
            ExamSchedulerApp(window)

        print(_t("extras_gui.messages.exam_scheduler_opened"))
    except Exception as e:
        messagebox.showerror(_t("extras_gui.errors.error"), _t("extras_gui.errors.exam_scheduler_failed").format(error=str(e)))
        print(_t("extras_gui.messages.exam_scheduler_error").format(error=e))

def show_student_analytics_gui(self):
    """Launch the Student Analytics GUI"""
    if not self.auth.current_user:
        messagebox.showerror(_t("extras_gui.errors.error"), "Please log in to access Student Analytics.")
        return

    try:
        from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
            STUDENT_ANALYTICS_GUI_AVAILABLE, GUIStudentAnalytics
        )
        if not STUDENT_ANALYTICS_GUI_AVAILABLE or GUIStudentAnalytics is None:
            messagebox.showerror("Student Analytics", "Student Analytics GUI is not available.")
            return

        window = tk.Toplevel(self.root)
        window.title("Student Analytics")
        window.geometry("1400x900")
        try:
            window.transient(self.root)
        except Exception:
            pass
        GUIStudentAnalytics(root=window, auth_manager=self.auth)
        print("Student Analytics GUI opened")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open Student Analytics: {e}")
        logger.error(f"Student Analytics GUI error: {e}")
