# Auto-generated module
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import sys
import subprocess

# Import from gui_imports
from education_system.university_system.modules.shared.gui.main.imports.gui_imports import (
    translate_text,
    _safe_entry_insert,
    _safe_set_combobox,
    PARENT_PORTAL_GUI_AVAILABLE,
    ParentPortalGUI,
    PARENT_PORTAL_GUI_IMPORT_ERROR,
    ALUMNI_PORTAL_GUI_AVAILABLE,
    ALUMNI_GUI_APP_CLASS,
    ALUMNI_PORTAL_IMPORT_ERROR,
    STUDENT_SUPPORT_GUI_AVAILABLE,
    StudentSupportGUI,
    _STUDENT_SUPPORT_GUI_IMPORT_ERROR,
    HELPDESK_GUI_AVAILABLE,
    HelpdeskGUI,
    HELPDESK_CLI_AVAILABLE,
    display_helpdesk_menu,
    launch_mental_health_gui,
    launch_early_warning_gui,
    launch_career_services_gui,
    TRIP_MANAGEMENT_GUI_AVAILABLE,
    TripManagementGUI,
    _TRIP_MGMT_IMPORT_ERROR,
    LEGAL_SERVICES_GUI_AVAILABLE,
    LegalServicesGUI,
    BETTING_SHOP_GUI_AVAILABLE,
    BettingShopGUI,
    MAIL_POST_GUI_AVAILABLE,
    MailPostGUI,
    STAFF_HR_GUI_AVAILABLE,
    StaffHRGUI,
)

logger = logging.getLogger(__name__)

# Alias for translation function
_t = translate_text

def show_student_union_portal(self):
    """Wrapper method to maintain compatibility with navigation buttons"""
    if self.student_union_gui:
        self.student_union_gui.show_student_union_portal()
    else:
        messagebox.showerror(_t("student_affairs.errors.title"), _t("student_affairs.student_union.not_available"))
def open_student_union_portal_gui(self):
    """Open the Student Union GUI in a child window with proper integration"""
    if self.student_union_gui:
        self.student_union_gui.open_student_union_portal_gui()
    else:
        messagebox.showerror(_t("student_affairs.errors.title"), _t("student_affairs.student_union.not_available"))
def open_parent_portal_gui(self):
    """Open the Parent Portal GUI in a child window"""
    if not self.auth or not self.auth.current_user:
        messagebox.showerror(_t("student_affairs.parent_portal.title"), _t("student_affairs.errors.login_required"))
        return

    try:
        if not PARENT_PORTAL_GUI_AVAILABLE:
            messagebox.showerror(_t("student_affairs.parent_portal.title"), _t("student_affairs.parent_portal.not_available").format(error=PARENT_PORTAL_GUI_IMPORT_ERROR))
            # Fallback to CLI
            try:
                display_parent_portal_menu(self.auth)
            except Exception:
                messagebox.showerror(_t("student_affairs.errors.title"), _t("student_affairs.parent_portal.no_fallback"))
            return

        # Create a new window for the Parent Portal GUI
        parent_window = tk.Toplevel(self.root)
        parent_window.title(_t("student_affairs.parent_portal.window_title"))
        parent_window.geometry("1400x900")
        parent_window.minsize(1200, 800)

        # Center the window
        parent_window.update_idletasks()
        x = (parent_window.winfo_screenwidth() - parent_window.winfo_width()) // 2
        y = (parent_window.winfo_screenheight() - parent_window.winfo_height()) // 2
        parent_window.geometry(f"+{x}+{y}")

        try:
            parent_window.transient(self.root)
        except Exception as e:
            logger.debug(f"Could not set parent_window as transient: {e}")

        # Initialize the Parent Portal GUI
        parent_gui = ParentPortalGUI(self.auth)

        # Replace the root window with our new window
        parent_gui.root = parent_window
        parent_gui.setup_layout()
        parent_gui.load_user_data()
        parent_gui.show_dashboard()

        print(_t("student_affairs.parent_portal.opened_success"))

    except Exception as e:
        messagebox.showerror(_t("student_affairs.errors.title"), _t("student_affairs.parent_portal.open_failed").format(error=str(e)))
        print(_t("student_affairs.parent_portal.open_error").format(error=e))
def open_alumni_portal_gui(self):
    """Open the Alumni Management Portal in a child window from the main app."""
    # Require login like the other portals
    if not getattr(self.auth, "current_user", None):
        messagebox.showerror(_t("student_affairs.alumni_portal.title"), _t("student_affairs.errors.login_required"))
        return

    # Verify the GUI import worked
    if not ALUMNI_PORTAL_GUI_AVAILABLE or ALUMNI_GUI_APP_CLASS is None:
        msg = _t("student_affairs.alumni_portal.not_available")
        if ALUMNI_PORTAL_IMPORT_ERROR:
            msg += f"\n{ALUMNI_PORTAL_IMPORT_ERROR}"
        messagebox.showerror(_t("student_affairs.alumni_portal.title"), msg)
        return

    try:
        # Open inside a child window so your main app stays up
        win = tk.Toplevel(self.root)
        win.title(_t("student_affairs.alumni_portal.window_title"))
        win.geometry("1400x900")
        win.minsize(1200, 800)
        try:
            win.transient(self.root)
            win.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Spin up the Alumni GUI on this window
        app = ALUMNI_GUI_APP_CLASS(win)

        # Hand over auth context if the alumni app exposes a slot; harmless if it doesn't
        try:
            setattr(app, "auth", self.auth)
        except Exception as e:
            logger.debug(f"Could not set auth attribute on app: {e}")

        print(_t("student_affairs.alumni_portal.opened_success"))
    except Exception as e:
        messagebox.showerror(_t("student_affairs.alumni_portal.title"), _t("student_affairs.alumni_portal.open_failed").format(error=e))
def open_student_support_portal_gui(self):
    """Open Student Support Portal GUI in a child window"""
    if not self.auth.current_user:
        messagebox.showerror(_t("student_affairs.errors.title"), _t("student_affairs.errors.login_required"))
        return

    try:
        if not STUDENT_SUPPORT_GUI_AVAILABLE:
            messagebox.showerror(_t("student_affairs.student_support.title"), _t("student_affairs.student_support.not_available").format(error=_STUDENT_SUPPORT_GUI_IMPORT_ERROR))
            return

        # Create a new window for the Student Support GUI
        support_window = tk.Toplevel(self.root)
        support_window.title(_t("student_affairs.student_support.window_title"))
        support_window.geometry("1400x900")
        support_window.minsize(1200, 800)

        # Center the window
        support_window.update_idletasks()
        x = (support_window.winfo_screenwidth() - support_window.winfo_width()) // 2
        y = (support_window.winfo_screenheight() - support_window.winfo_height()) // 2
        support_window.geometry(f"+{x}+{y}")

        try:
            support_window.transient(self.root)
        except Exception:
            pass  # Continue if transient fails

        # Initialize the Student Support GUI in the new window with auth system
        support_gui = StudentSupportGUI(support_window, auth_system=self.auth)

        print(_t("student_affairs.student_support.opened_success"))

    except Exception as e:
        messagebox.showerror(_t("student_affairs.errors.title"), _t("student_affairs.student_support.open_failed").format(error=str(e)))
        print(_t("student_affairs.student_support.open_error").format(error=e))
def open_health_portal_gui(self):
    """Open the Health Portal GUI in a child window from the main app."""
    if self.health_portal_gui:
        self.health_portal_gui.open_health_portal_gui()
    else:
        messagebox.showerror(_t("student_affairs.errors.title"), _t("student_affairs.health_portal.not_available"))
def open_helpdesk_gui(self):
    """Open the Helpdesk GUI in a child window; fall back to CLI if import fails."""
    try:
        if not HELPDESK_GUI_AVAILABLE or HelpdeskGUI is None:
            # Fallback to CLI menu if available; otherwise show error
            if display_helpdesk_menu and globals().get("HELPDESK_CLI_AVAILABLE", False):
                try:
                    display_helpdesk_menu(self.auth)
                except Exception as cli_err:
                    messagebox.showerror(_t("student_affairs.helpdesk.title"), _t("student_affairs.helpdesk.cli_fallback_failed").format(error=cli_err))
            else:
                messagebox.showerror(_t("student_affairs.helpdesk.title"), _t("student_affairs.helpdesk.not_available_no_fallback"))
            return

        # Child window
        win = tk.Toplevel(self.root)
        win.title(_t("student_affairs.helpdesk.window_title"))
        win.geometry("1400x900")

        # Modal-ish behavior
        try:
            win.transient(self.root)
            win.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Instantiate GUI
        try:
            helpdesk_gui = HelpdeskGUI(win, auth=self.auth)
            print(_t("student_affairs.helpdesk.opened_success"))
        except Exception as inst_err:
            win.destroy()
            try:
                display_helpdesk_menu(self.auth)
            except Exception as cli_err:
                messagebox.showerror(
                    _t("student_affairs.helpdesk.title"),
                    _t("student_affairs.helpdesk.open_failed_with_cli_error").format(gui_error=inst_err, cli_error=cli_err)
                )

    except Exception as e:
        messagebox.showerror(_t("student_affairs.helpdesk.title"), _t("student_affairs.helpdesk.unexpected_error").format(error=e))
def show_mental_health_gui(self):
    """Launch the Mental Health & Wellness Portal GUI"""
    launch_mental_health_gui(self.root, self.auth)
def show_early_warning_gui(self):
    """Launch the Student Success Early Warning System GUI"""
    launch_early_warning_gui(self.root, self.auth)
def show_career_services_gui(self):
    """Launch the Career Services GUI"""
    launch_career_services_gui(self.root, self.auth)
def open_internship_portal_gui(self):
    """Open the Internship Portal GUI in a child window from the main app."""
    try:
        from education_system.university_system.modules.domain.student_affairs.gui.internship_management_gui import InternshipGUI  # local file you provided
    except Exception as e:
        messagebox.showerror(_t("student_affairs.internship_portal.title"), _t("student_affairs.internship_portal.not_available").format(error=e))
        return
    try:
        win = tk.Toplevel(self.root)
        win.title(_t("student_affairs.internship_portal.window_title"))
        win.geometry("1200x800")
        try:
            win.transient(self.root)
            win.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")
        # Instantiate the GUI and pass current auth
        InternshipGUI(win, self.auth)
        print(_t("student_affairs.internship_portal.opened_success"))
    except Exception as e:
        messagebox.showerror(_t("student_affairs.internship_portal.title"), _t("student_affairs.internship_portal.open_failed").format(error=e))
def show_trip_management_gui(self):
    """Open the Trip Management GUI in a child window (Toplevel)."""
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("student_affairs.trip_management.title"), _t("student_affairs.errors.login_required"))
            return

        if not TRIP_MANAGEMENT_GUI_AVAILABLE:
            messagebox.showerror(_t("student_affairs.trip_management.title"), _t("student_affairs.trip_management.not_available").format(error=_TRIP_MGMT_IMPORT_ERROR))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("student_affairs.trip_management.window_title"))
        top.geometry("1200x800")
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Embed the TripManagementGUI into this window, passing current auth
        TripManagementGUI(auth_instance=self.auth, root=top)

        # No mainloop here; the main GUI already owns it
        print(_t("student_affairs.trip_management.opened_success"))

    except Exception as e:
        messagebox.showerror(_t("student_affairs.trip_management.title"), _t("student_affairs.trip_management.open_failed").format(error=e))
def open_trip_management_gui(self):
    try:
        python = sys.executable
        code = (
            "import sys; "
            "from trip_management_gui import TripManagementGUI; "
            "app = TripManagementGUI(auth=None); "
            "app.run()"
        )
        subprocess.Popen([python, "-c", code], close_fds=True)
    except Exception as e:
        messagebox.showerror(_t("student_affairs.trip_management.title"), _t("student_affairs.trip_management.open_failed").format(error=e))
def show_legal_services_gui(self):
    """Open the Legal Services GUI in a child window."""
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("student_affairs.legal_services.title"), _t("student_affairs.errors.login_required"))
            return

        if not LEGAL_SERVICES_GUI_AVAILABLE:
            messagebox.showerror(_t("student_affairs.legal_services.title"), _t("student_affairs.legal_services.not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("student_affairs.legal_services.window_title"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Legal Services GUI
        LegalServicesGUI(top, self.auth)
        print(_t("student_affairs.legal_services.opened_success"))

    except Exception as e:
        messagebox.showerror(_t("student_affairs.legal_services.title"), _t("student_affairs.legal_services.open_failed").format(error=str(e)))
def show_betting_shop_gui(self):
    """Open the Betting Shop GUI in a child window."""
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("student_affairs.betting_shop.title"), _t("student_affairs.errors.login_required"))
            return

        if not BETTING_SHOP_GUI_AVAILABLE:
            messagebox.showerror(_t("student_affairs.betting_shop.title"), _t("student_affairs.betting_shop.not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("student_affairs.betting_shop.window_title"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Betting Shop GUI
        BettingShopGUI(top, self.auth)
        print(_t("student_affairs.betting_shop.opened_success"))

    except Exception as e:
        messagebox.showerror(_t("student_affairs.betting_shop.title"), _t("student_affairs.betting_shop.open_failed").format(error=str(e)))

def show_mail_post_gui(self):
    """Open the Mail/Post System GUI in a child window."""
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("student_affairs.mail_post.title"), _t("student_affairs.errors.login_required"))
            return

        if not MAIL_POST_GUI_AVAILABLE:
            messagebox.showerror(_t("student_affairs.mail_post.title"), _t("student_affairs.mail_post.not_available"))
            return

        top = tk.Toplevel(self.root)
        top.title(_t("student_affairs.mail_post.window_title"))
        top.geometry("1400x900")
        top.minsize(1200, 800)
        try:
            top.transient(self.root)
            top.grab_set()
        except Exception as e:
            logger.debug(f"Could not set window as transient or grab focus: {e}")

        # Initialize the Mail/Post GUI
        MailPostGUI(top, self.auth)
        print(_t("student_affairs.mail_post.opened_success"))

    except Exception as e:
        messagebox.showerror(_t("student_affairs.mail_post.title"), _t("student_affairs.mail_post.open_failed").format(error=str(e)))

def show_staff_hr_gui(self):
    """Open the Staff HR Management GUI in a child window."""
    try:
        if not self.auth or not self.auth.current_user:
            messagebox.showerror(_t("student_affairs.staff_hr.title"), _t("student_affairs.staff_hr.login_required"))
            return

        if not STAFF_HR_GUI_AVAILABLE:
            messagebox.showerror(_t("student_affairs.staff_hr.title"), _t("student_affairs.staff_hr.not_available"))
            return

        # Launch the Staff HR GUI - it creates its own Toplevel window
        StaffHRGUI(self.root, self.auth)
        print("Staff HR Management GUI opened successfully")

    except Exception as e:
        messagebox.showerror(_t("student_affairs.staff_hr.title"), _t("student_affairs.staff_hr.open_failed", error=str(e)))
