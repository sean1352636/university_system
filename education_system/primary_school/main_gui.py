"""Main GUI application for the Primary School Management System.

Provides login, dashboard, and sidebar navigation to all modules.
"""

import logging
import traceback
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.core.logs import setup_logging
from education_system.primary_school.core.paths import DB_FILE
from education_system.primary_school.infrastructure.database.schema import initialise_database, seed_default_users
from education_system.primary_school.infrastructure.auth.core import UserAuth
from education_system.primary_school.seed_subjects import seed_subjects

logger = logging.getLogger(__name__)

# ── Colour scheme ─────────────────────────────────────────────────────────
HEADER_BG = "#1a5276"
SIDEBAR_BG = "#2c3e50"
MAIN_BG = "#ecf0f1"
ACCENT = "#2980b9"


# ══════════════════════════════════════════════════════════════════════════
#  Login window
# ══════════════════════════════════════════════════════════════════════════

class LoginWindow(tk.Toplevel):
    """Modal login dialog."""

    def __init__(self, parent, db_path):
        super().__init__(parent)
        self.title("Primary School - Login")
        self.geometry("380x280")
        self.resizable(False, False)
        self.configure(bg=MAIN_BG)
        self._db_path = db_path
        self._auth = UserAuth(db_path)
        self.user = None

        # Centre on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 380) // 2
        y = (self.winfo_screenheight() - 280) // 2
        self.geometry(f"+{x}+{y}")

        # Header
        hdr = tk.Frame(self, bg=HEADER_BG, height=50)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Primary School Management System",
                 bg=HEADER_BG, fg="white", font=("Helvetica", 13, "bold")).pack(expand=True)

        # Form
        frm = tk.Frame(self, bg=MAIN_BG, pady=15)
        frm.pack(expand=True)

        tk.Label(frm, text="Username:", bg=MAIN_BG, font=("Helvetica", 11)).grid(
            row=0, column=0, sticky="e", padx=10, pady=8)
        self._username = tk.Entry(frm, width=22, font=("Helvetica", 11))
        self._username.grid(row=0, column=1, pady=8)

        tk.Label(frm, text="Password:", bg=MAIN_BG, font=("Helvetica", 11)).grid(
            row=1, column=0, sticky="e", padx=10, pady=8)
        self._password = tk.Entry(frm, width=22, show="*", font=("Helvetica", 11))
        self._password.grid(row=1, column=1, pady=8)
        self._password.bind("<Return>", lambda e: self._login())

        tk.Button(frm, text="Login", command=self._login, width=14,
                  font=("Helvetica", 10, "bold"), bg=ACCENT, fg="white").grid(
            row=2, column=0, columnspan=2, pady=12)

        tk.Label(frm, text="Default: admin / Admin@123", bg=MAIN_BG,
                 fg="#7f8c8d", font=("Helvetica", 9)).grid(row=3, column=0, columnspan=2)

        self._username.focus_set()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.transient(parent)
        self.deiconify()
        self.grab_set()

    def _login(self):
        username = self._username.get().strip()
        password = self._password.get()
        if not username or not password:
            messagebox.showwarning("Login", "Please enter both username and password.", parent=self)
            return
        user = self._auth.login(username, password)
        if user:
            self.user = user
            self.user["_auth"] = self._auth
            self.destroy()
        else:
            messagebox.showerror("Login Failed",
                                 "Invalid credentials or account is locked.", parent=self)
            self._password.delete(0, tk.END)

    def _on_close(self):
        self.user = None
        self.master.destroy()


# ══════════════════════════════════════════════════════════════════════════
#  Dashboard
# ══════════════════════════════════════════════════════════════════════════

class DashboardFrame(tk.Frame):
    """Welcome dashboard with summary statistics."""

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent, bg=MAIN_BG)
        self._db_path = db_path
        self._auth = auth

        # Welcome
        user_name = auth.current_user["display_name"] if auth and auth.current_user else "User"
        role = auth.current_user["role"] if auth and auth.current_user else ""
        tk.Label(self, text=f"Welcome, {user_name}",
                 font=("Helvetica", 18, "bold"), bg=MAIN_BG).pack(pady=(25, 2))
        tk.Label(self, text=f"Role: {role.title()}",
                 font=("Helvetica", 11), bg=MAIN_BG, fg="#7f8c8d").pack()
        tk.Label(self, text="Primary School Management System",
                 font=("Helvetica", 12), bg=MAIN_BG, fg="#34495e").pack(pady=(2, 20))

        # Stats cards
        self._cards_frame = tk.Frame(self, bg=MAIN_BG)
        self._cards_frame.pack(fill="x", padx=30)
        self._build_stats()

    def _build_stats(self):
        for w in self._cards_frame.winfo_children():
            w.destroy()

        from education_system.primary_school.modules.domain.academics.pupils.services.pupil_service import PupilService
        svc = PupilService(self._db_path)

        cards = []
        try:
            total = svc.count_pupils()
            cards.append(("Total Pupils", str(total), "#2ecc71"))
            from education_system.primary_school.core.defaults import YEAR_GROUPS
            for yg in YEAR_GROUPS:
                cnt = svc.count_pupils(year_group=yg)
                if cnt > 0:
                    cards.append((yg, str(cnt), "#3498db"))
        except Exception:
            cards.append(("Total Pupils", "0", "#2ecc71"))

        for idx, (label, value, colour) in enumerate(cards):
            row, col = divmod(idx, 4)
            card = tk.Frame(self._cards_frame, bg=colour, padx=15, pady=10)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            tk.Label(card, text=value, font=("Helvetica", 22, "bold"),
                     bg=colour, fg="white").pack()
            tk.Label(card, text=label, font=("Helvetica", 10),
                     bg=colour, fg="white").pack()
            self._cards_frame.columnconfigure(col, weight=1)

    def refresh(self):
        self._build_stats()


# ══════════════════════════════════════════════════════════════════════════
#  Main application
# ══════════════════════════════════════════════════════════════════════════

class MainApplication(tk.Tk):
    """Root window with sidebar navigation and dynamic content area."""

    def __init__(self, user: dict, db_path: str):
        super().__init__()
        self._db_path = db_path
        self._user = user
        self._auth = user.get("_auth")
        self._frames: dict[str, tk.Frame] = {}
        self._nav_buttons: dict[str, tk.Button] = {}

        self.title("Primary School Management System")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(bg=MAIN_BG)

        self._build_ui()
        self._show_module("Dashboard")

    # ── Layout ────────────────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        top = tk.Frame(self, bg=HEADER_BG, height=44)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="Primary School Management System",
                 bg=HEADER_BG, fg="white", font=("Helvetica", 13, "bold")).pack(side="left", padx=15)
        tk.Label(top, text=f"{self._user['display_name']} ({self._user['role']})",
                 bg=HEADER_BG, fg="#d5dbdb", font=("Helvetica", 10)).pack(side="right", padx=15)

        # Body
        body = tk.Frame(self, bg=MAIN_BG)
        body.pack(fill="both", expand=True)

        # Sidebar (outer container)
        sidebar_outer = tk.Frame(body, bg=SIDEBAR_BG, width=180)
        sidebar_outer.pack(side="left", fill="y")
        sidebar_outer.pack_propagate(False)

        # Bottom bar — pack FIRST so it claims space before the canvas
        bottom = tk.Frame(sidebar_outer, bg=SIDEBAR_BG)
        bottom.pack(side="bottom", fill="x")
        ttk.Separator(bottom).pack(fill="x")

        tk.Button(bottom, text="Switch to CLI", font=("Helvetica", 9),
                  bg="#1a252f", fg="white", bd=0, pady=8,
                  activebackground="#34495e", activeforeground="white",
                  command=self._switch_to_cli).pack(fill="x")
        tk.Button(bottom, text="Switch System", font=("Helvetica", 9),
                  bg="#1a252f", fg="white", bd=0, pady=8,
                  activebackground="#34495e", activeforeground="white",
                  command=self._switch_system).pack(fill="x")
        tk.Button(bottom, text="Logout", font=("Helvetica", 9),
                  bg="#1a252f", fg="white", bd=0, pady=8,
                  activebackground="#34495e", activeforeground="white",
                  command=self._logout).pack(fill="x")
        tk.Button(bottom, text="Shutdown", font=("Helvetica", 9),
                  bg="#78281f", fg="white", bd=0, pady=8,
                  activebackground="#943126", activeforeground="white",
                  command=self._shutdown).pack(fill="x")

        # Scrollable sidebar
        sidebar_canvas = tk.Canvas(sidebar_outer, bg=SIDEBAR_BG, highlightthickness=0, width=164)
        sidebar_scrollbar = tk.Scrollbar(sidebar_outer, orient="vertical", command=sidebar_canvas.yview)
        sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        sidebar_scrollbar.pack(side="right", fill="y")
        sidebar_canvas.pack(side="left", fill="both", expand=True)

        sidebar = tk.Frame(sidebar_canvas, bg=SIDEBAR_BG)
        sidebar_canvas.create_window((0, 0), window=sidebar, anchor="nw", width=164)
        sidebar.bind("<Configure>", lambda e: sidebar_canvas.configure(scrollregion=sidebar_canvas.bbox("all")))

        # Cross-platform mousewheel
        def _on_mousewheel(event):
            sidebar_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_mousewheel_linux(event):
            sidebar_canvas.yview_scroll(-3 if event.num == 4 else 3, "units")

        sidebar_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        sidebar_canvas.bind_all("<Button-4>", _on_mousewheel_linux)
        sidebar_canvas.bind_all("<Button-5>", _on_mousewheel_linux)

        # Content area
        self._content = tk.Frame(body, bg=MAIN_BG)
        self._content.pack(side="left", fill="both", expand=True)

        # ── Module definitions ────────────────────────────────────────
        role = self._user.get("role", "")
        try:
            modules = self._get_modules_for_role(role)
        except Exception as e:
            logger.error("Failed to load module definitions: %s", e, exc_info=True)
            traceback.print_exc()
            modules = [("Dashboard", DashboardFrame)]

        # Create sidebar buttons
        for name, _ in modules:
            btn = tk.Button(
                sidebar, text=name, font=("Helvetica", 10),
                bg=SIDEBAR_BG, fg="white", bd=0, pady=10,
                activebackground="#34495e", activeforeground="white",
                anchor="w", padx=18,
                command=lambda n=name: self._show_module(n),
            )
            btn.pack(fill="x")
            self._nav_buttons[name] = btn

        # Instantiate frames
        for name, frame_cls in modules:
            try:
                frame = frame_cls(self._content, self._db_path, auth=self._auth)
                self._frames[name] = frame
            except Exception as e:
                logger.error("Failed to load module %s: %s", name, e, exc_info=True)
                traceback.print_exc()
                err_frame = tk.Frame(self._content, bg=MAIN_BG)
                tk.Label(err_frame, text=f"Failed to load {name}:\n{e}",
                         bg=MAIN_BG, fg="red", font=("Helvetica", 11)).pack(expand=True)
                self._frames[name] = err_frame

    def _get_modules_for_role(self, role: str):
        """Return list of (name, FrameClass) tuples visible to the given role."""
        # Lazy imports to avoid circular imports and speed up startup
        from education_system.primary_school.modules.domain.academics.pupils.gui.pupil_gui import PupilFrame
        from education_system.primary_school.modules.domain.academics.subjects.gui.subject_gui import SubjectFrame
        from education_system.primary_school.modules.domain.academics.classes.gui.class_gui import ClassFrame
        from education_system.primary_school.modules.domain.academics.assessment.gui.assessment_gui import AssessmentFrame
        from education_system.primary_school.modules.domain.academics.attendance.gui.attendance_gui import AttendanceFrame
        from education_system.primary_school.modules.domain.academics.timetable.gui.timetable_gui import TimetableFrame
        from education_system.primary_school.modules.domain.academics.homework.gui.homework_gui import HomeworkFrame
        from education_system.primary_school.modules.domain.academics.sats.gui.sats_gui import SATsFrame
        from education_system.primary_school.modules.domain.academics.phonics.gui.phonics_gui import PhonicsFrame
        from education_system.primary_school.modules.domain.academics.reading_records.gui.reading_record_gui import ReadingRecordFrame
        from education_system.primary_school.modules.domain.academics.progress.gui.progress_gui import ProgressFrame
        from education_system.primary_school.modules.domain.pastoral_care.behaviour.gui.behaviour_gui import BehaviourFrame
        from education_system.primary_school.modules.domain.pastoral_care.rewards.gui.rewards_gui import RewardsFrame
        from education_system.primary_school.modules.domain.pastoral_care.safeguarding.gui.safeguarding_gui import SafeguardingFrame
        from education_system.primary_school.modules.domain.pastoral_care.send.gui.send_gui import SENDFrame
        from education_system.primary_school.modules.domain.pastoral_care.pastoral.gui.pastoral_gui import PastoralFrame
        from education_system.primary_school.modules.domain.staff.hr.gui.hr_gui import HRFrame
        from education_system.primary_school.modules.domain.staff.cpd.gui.cpd_gui import CPDFrame
        from education_system.primary_school.modules.domain.staff.cover.gui.cover_gui import CoverFrame
        from education_system.primary_school.modules.domain.staff.staff_directory.gui.staff_directory_gui import StaffDirectoryFrame
        from education_system.primary_school.modules.domain.admin.users.gui.user_gui import UserFrame
        from education_system.primary_school.modules.domain.admin.settings.gui.settings_gui import SettingsFrame
        from education_system.primary_school.modules.domain.admin.admissions.gui.admissions_gui import AdmissionsFrame
        from education_system.primary_school.modules.domain.admin.finance.gui.finance_gui import FinanceFrame
        from education_system.primary_school.modules.domain.admin.data_export.gui.data_export_gui import DataExportFrame
        from education_system.primary_school.modules.domain.admin.audit_log.gui.audit_log_gui import AuditLogFrame
        from education_system.primary_school.modules.domain.admin.policies.gui.policy_gui import PolicyFrame
        from education_system.primary_school.modules.domain.admin.documents.gui.document_gui import DocumentFrame
        from education_system.primary_school.modules.domain.pupil_life.clubs.gui.club_gui import ClubFrame
        from education_system.primary_school.modules.domain.pupil_life.meals.gui.meal_gui import MealFrame
        from education_system.primary_school.modules.domain.pupil_life.transport.gui.transport_gui import TransportFrame
        from education_system.primary_school.modules.domain.pupil_life.trips.gui.trip_gui import TripFrame
        from education_system.primary_school.modules.domain.pupil_life.library.gui.library_gui import LibraryFrame
        from education_system.primary_school.modules.domain.pupil_life.medical.gui.medical_gui import MedicalFrame
        from education_system.primary_school.modules.domain.pupil_life.class_groups.gui.class_group_gui import ClassGroupFrame
        from education_system.primary_school.modules.domain.pupil_life.consent.gui.consent_gui import ConsentFrame
        from education_system.primary_school.modules.domain.communication.email.gui.email_gui import EmailFrame
        from education_system.primary_school.modules.domain.communication.notifications.gui.notification_gui import NotificationFrame
        from education_system.primary_school.modules.domain.communication.announcements.gui.announcement_gui import AnnouncementFrame
        from education_system.primary_school.modules.domain.communication.calendar.gui.calendar_gui import CalendarFrame
        from education_system.primary_school.modules.domain.communication.parents_evening.gui.parents_evening_gui import ParentsEveningFrame
        from education_system.primary_school.modules.domain.communication.communication_log.gui.communication_log_gui import CommunicationLogFrame
        from education_system.primary_school.modules.domain.facilities.room_booking.gui.room_booking_gui import RoomBookingFrame
        from education_system.primary_school.modules.domain.facilities.assets.gui.asset_gui import AssetFrame
        from education_system.primary_school.modules.domain.facilities.visitors.gui.visitor_gui import VisitorFrame
        from education_system.primary_school.modules.domain.facilities.incidents.gui.incident_gui import IncidentFrame

        # All modules in display order
        all_modules = [
            # ── Core ──────────────────────
            ("Dashboard", DashboardFrame),
            # ── Academics ─────────────────
            ("Pupils", PupilFrame),
            ("Subjects", SubjectFrame),
            ("Classes", ClassFrame),
            ("Assessment", AssessmentFrame),
            ("Attendance", AttendanceFrame),
            ("Timetable", TimetableFrame),
            ("Homework", HomeworkFrame),
            ("SATs", SATsFrame),
            ("Phonics", PhonicsFrame),
            ("Reading Records", ReadingRecordFrame),
            ("Progress", ProgressFrame),
            # ── Pastoral care ─────────────
            ("Behaviour", BehaviourFrame),
            ("Rewards", RewardsFrame),
            ("Safeguarding", SafeguardingFrame),
            ("SEND", SENDFrame),
            ("Pastoral", PastoralFrame),
            # ── Staff ─────────────────────
            ("Staff Directory", StaffDirectoryFrame),
            ("HR", HRFrame),
            ("CPD", CPDFrame),
            ("Cover", CoverFrame),
            # ── Pupil life ────────────────
            ("Class Groups", ClassGroupFrame),
            ("Clubs", ClubFrame),
            ("Meals", MealFrame),
            ("Library", LibraryFrame),
            ("Medical", MedicalFrame),
            ("Transport", TransportFrame),
            ("Trips", TripFrame),
            ("Consent", ConsentFrame),
            # ── Communication ─────────────
            ("Announcements", AnnouncementFrame),
            ("Calendar", CalendarFrame),
            ("Notifications", NotificationFrame),
            ("Email", EmailFrame),
            ("Parents Evening", ParentsEveningFrame),
            ("Communication Log", CommunicationLogFrame),
            # ── Admin ─────────────────────
            ("Admissions", AdmissionsFrame),
            ("Finance", FinanceFrame),
            ("Policies", PolicyFrame),
            ("Documents", DocumentFrame),
            ("Users", UserFrame),
            ("Settings", SettingsFrame),
            ("Audit Log", AuditLogFrame),
            ("Data Export", DataExportFrame),
            # ── Facilities ────────────────
            ("Room Bookings", RoomBookingFrame),
            ("Assets", AssetFrame),
            ("Visitors", VisitorFrame),
            ("Incidents", IncidentFrame),
        ]

        # Role-based filtering
        admin_only = {
            "HR", "CPD", "Cover", "Finance", "Users", "Settings",
            "Audit Log", "Data Export", "Safeguarding", "Policies",
            "Assets", "Visitors",
        }
        staff_modules = {
            "Dashboard", "Pupils", "Subjects", "Classes", "Assessment",
            "Attendance", "Timetable", "Homework", "SATs", "Phonics",
            "Reading Records", "Progress", "Behaviour", "Rewards",
            "SEND", "Pastoral", "Staff Directory", "Class Groups",
            "Clubs", "Meals", "Library", "Medical", "Transport", "Trips",
            "Consent", "Announcements", "Calendar", "Notifications",
            "Email", "Parents Evening", "Communication Log",
            "Admissions", "Documents", "Room Bookings", "Incidents",
        }
        parent_modules = {
            "Dashboard", "Announcements", "Calendar", "Notifications",
        }

        if role == "admin":
            return all_modules
        elif role in ("teacher", "teaching_assistant"):
            return [(n, c) for n, c in all_modules if n in staff_modules]
        elif role == "parent":
            return [(n, c) for n, c in all_modules if n in parent_modules]
        else:
            return [("Dashboard", DashboardFrame)]

    # ── Navigation ────────────────────────────────────────────────────

    def _show_module(self, name: str):
        for frame in self._frames.values():
            frame.pack_forget()

        for btn_name, btn in self._nav_buttons.items():
            btn.configure(bg="#34495e" if btn_name == name else SIDEBAR_BG)

        if name in self._frames:
            frame = self._frames[name]
            frame.pack(fill="both", expand=True)
            if hasattr(frame, "refresh"):
                try:
                    frame.refresh()
                except Exception as e:
                    logger.error("Error refreshing %s: %s", name, e, exc_info=True)
                    traceback.print_exc()

    # ── Actions ───────────────────────────────────────────────────────

    def _switch_to_cli(self):
        """Switch to the Primary School CLI interface."""
        if messagebox.askyesno("Switch to CLI", "Switch to the command-line interface?"):
            from education_system.switch import request_switch
            request_switch("primary", "cli")
            if self._auth:
                self._auth.logout()
            self.destroy()

    def _switch_system(self):
        """Show a system picker and switch to the chosen system."""
        picker = tk.Toplevel(self)
        picker.title("Switch System")
        picker.resizable(False, False)
        picker.grab_set()
        picker.transient(self)

        body = tk.Frame(picker, padx=30, pady=20)
        body.pack(fill=tk.BOTH, expand=True)
        tk.Label(body, text="Switch to:", font=("Helvetica", 14, "bold")).pack(pady=(0, 15))

        btn_style = {"font": ("Helvetica", 12), "fg": "white", "relief": tk.FLAT,
                     "cursor": "hand2", "width": 30, "height": 2}

        tk.Button(body, text="University Management System",
                  bg="#2980b9", activebackground="#3498db", activeforeground="white",
                  command=lambda: self._do_switch(picker, "university"), **btn_style).pack(pady=5)
        tk.Button(body, text="Sixth Form College System",
                  bg="#27ae60", activebackground="#2ecc71", activeforeground="white",
                  command=lambda: self._do_switch(picker, "college"), **btn_style).pack(pady=5)
        tk.Button(body, text="Secondary School System",
                  bg="#8e44ad", activebackground="#9b59b6", activeforeground="white",
                  command=lambda: self._do_switch(picker, "school"), **btn_style).pack(pady=5)
        tk.Button(body, text="Cancel", font=("Helvetica", 12), relief=tk.FLAT,
                  padx=20, pady=4, cursor="hand2", command=picker.destroy).pack(pady=(10, 0))

    def _do_switch(self, picker, system_key):
        picker.destroy()
        from education_system.switch import request_switch
        request_switch(system_key, "gui")
        if self._auth:
            self._auth.logout()
        self.destroy()

    def _logout(self):
        if self._auth:
            self._auth.logout()
        from education_system.switch import request_logout
        request_logout()
        self.destroy()

    def _shutdown(self):
        if messagebox.askyesno("Shutdown", "Are you sure you want to exit?"):
            if self._auth:
                self._auth.logout()
            self.destroy()


# ══════════════════════════════════════════════════════════════════════════
#  Application entry
# ══════════════════════════════════════════════════════════════════════════

def _restart():
    """Re-launch the login flow."""
    run()


def _tk_exception_handler(exc_type, exc_value, exc_tb):
    """Global handler so tkinter callback errors print to terminal."""
    traceback.print_exception(exc_type, exc_value, exc_tb)
    logger.error("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


def run(user_info=None, role=None, shared_auth=None):
    """Launch the Primary School Management System GUI.

    If *user_info* and *role* are provided (from universal login), the
    login dialog is skipped.
    """
    setup_logging()
    db_path = str(DB_FILE)

    try:
        # Initialise database
        initialise_database(db_path)
        seed_default_users(db_path)
        seed_subjects(db_path)
    except Exception as e:
        logger.error("Failed to initialise database: %s", e, exc_info=True)
        traceback.print_exc()
        return

    try:
        if user_info and role:
            # Pre-authenticated via universal login
            auth = shared_auth or UserAuth(db_path)
            user = {
                "id": user_info.get("user_id"),
                "username": user_info.get("username"),
                "role": role,
                "display_name": user_info.get("display_name", user_info.get("username")),
                "_auth": auth,
            }
            # Set current_user on the auth object so property checks work
            auth._current_user = user
            app = MainApplication(user, db_path)
            app.report_callback_exception = _tk_exception_handler
            app.mainloop()
            return

        # Standard login flow
        root = tk.Tk()
        root.report_callback_exception = _tk_exception_handler
        root.withdraw()

        login = LoginWindow(root, db_path)
        root.wait_window(login)

        if login.user:
            root.destroy()
            app = MainApplication(login.user, db_path)
            app.report_callback_exception = _tk_exception_handler
            app.mainloop()
        else:
            try:
                root.destroy()
            except tk.TclError:
                pass
    except Exception as e:
        logger.error("Application error: %s", e, exc_info=True)
        traceback.print_exc()


if __name__ == "__main__":
    run()
