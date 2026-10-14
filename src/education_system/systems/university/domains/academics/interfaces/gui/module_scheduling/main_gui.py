
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.systems.university.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.systems.university.infrastructure.utils.gui_language_selector import (
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
from tkinter import ttk, filedialog, scrolledtext
from education_system.systems.university.domains.academics.interfaces.gui.module_scheduling._dialogs import messagebox
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path
from education_system.systems.university.infrastructure.database.db import sqlite3
# This ensures full backward compatibility
try:
    from education_system.systems.university.domains.academics.domain.services.module_scheduling import (
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
        from education_system.systems.university.domains.academics.domain.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

class ModuleSchedulingGUI:
    def __init__(self, root, auth=None):
        self.root = root
        # Accepted here as well as via set_auth: most callers construct this
        # GUI directly and never called set_auth, so the Open menu launched
        # Grade Tracking and Exam Management with no credentials at all.
        self._auth = auth
        self.root.title(_t("scheduling.window_title"))
        self.root.geometry("1400x900+%d+%d" % ((self.root.winfo_screenwidth() - 1400) // 2, (self.root.winfo_screenheight() - 900) // 2))
        self.root.minsize(1200, 800)

        # Bind the close handler early — if any later init step errors and
        # the window survives, we still want the X button to behave. Guard
        # against the Toplevel already being gone (see logout race).
        try:
            if self.root.winfo_exists():
                self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        except tk.TclError:
            pass

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

        # ── Defer the heavy initial population to after first paint ──
        # Pre-8.117.30 ``refresh_all_data`` (8 sequential DB-hitting
        # refresh methods) ran synchronously inside __init__, so the
        # window didn't appear until every tab's data was loaded —
        # the user perceived "Module Scheduling takes ages to load".
        # Schedule it via ``after(0, ...)`` so the empty window paints
        # first and Tk's event loop fills the data on the next idle
        # tick. Same trick used for the bus subscriptions below
        # (those touch ttk widget identities that don't need to exist
        # before the window is visible).
        try:
            self.root.after(0, self._deferred_initial_load)
        except tk.TclError:
            # Window already gone (very fast logout race); fall back
            # to synchronous load so we don't silently leave the GUI
            # empty.
            self._deferred_initial_load()
            return

    def _deferred_initial_load(self):
        """Initial data + bus subscriptions, deferred to first idle
        tick so the window can paint before doing the slow work."""
        # Flush pending redraws before blocking. after(0) fires on the next
        # trip round the event loop, which is not necessarily after the window
        # has actually been drawn — so the load could start while the window
        # was still an unpainted rectangle, and block until it finished.
        # update_idletasks() runs the pending redraws and nothing else (unlike
        # update(), which would also re-enter user event handlers here).
        try:
            self.root.update_idletasks()
        except tk.TclError:
            return  # window closed before the load started
        try:
            self.refresh_all_data()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

        # Live refresh: course list / enrolments / exam / grade events
        # in sibling windows can invalidate this view's data, so re-pull.
        try:
            from education_system.systems.university.infrastructure.event_bus import (
                subscribe_tk,
                EVENT_COURSE_CHANGED,
                EVENT_ENROLMENT_CHANGED,
                EVENT_EXAM_CHANGED,
            )

            def _on_external_change(**_payload):
                if hasattr(self, "refresh_all_data"):
                    self.refresh_all_data()

            for evt in (EVENT_COURSE_CHANGED, EVENT_ENROLMENT_CHANGED, EVENT_EXAM_CHANGED):
                subscribe_tk(evt, self.root, _on_external_change)

            # Term changes refilter all four scheduling GUIs together.
            from education_system.systems.university.infrastructure.event_bus import (
                EVENT_TERM_CHANGED,
            )
            subscribe_tk(EVENT_TERM_CHANGED, self.root, _on_external_change)

            # Calendar + staff availability changes affect what's
            # eligible to schedule, so refresh on those too.
            from education_system.systems.university.infrastructure.event_bus import (
                EVENT_CALENDAR_CHANGED, EVENT_STAFF_AVAILABILITY_CHANGED,
            )
            subscribe_tk(EVENT_CALENDAR_CHANGED, self.root, _on_external_change)
            subscribe_tk(EVENT_STAFF_AVAILABILITY_CHANGED, self.root, _on_external_change)

        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

    def _pick_module_for_timeline(self):
        """Choose a module from a list, then show its timeline.

        This used to be ``simpledialog.askstring("Module code:")``, so any
        text at all was accepted and a typo produced an empty timeline with
        no indication that the code did not exist.
        """
        from education_system.systems.university.domains.academics.interfaces.gui._cross_dialogs import (
            show_module_timeline_dialog,
        )

        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                rows = conn.execute(
                    "SELECT module_code, module_name FROM modules "
                    " WHERE COALESCE(TRIM(module_code), '') <> '' "
                    " ORDER BY module_code").fetchall()
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.module_scheduling.main.dialogs.error', default="Error"),
                                 f"Could not load modules: {exc}")
            return
        if not rows:
            messagebox.showinfo(_t('gui.academics.module_scheduling.main.dialogs.module_timeline', default="Module timeline"),
                                "There are no modules to show a timeline for.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.module_scheduling.main.dialogs.module_timeline', default="Module timeline"))
        dialog.geometry("440x160")
        dialog.transient(self.root)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text=_t('gui.academics.module_scheduling.main.labels.module', default="Module:")).pack(anchor=tk.W)

        codes = [r[0] for r in rows]
        combo = ttk.Combobox(
            frame, width=48, state="readonly",
            values=[f"{code} - {name}" if name else code for code, name in rows])
        combo.current(0)
        combo.pack(fill=tk.X, pady=(4, 12))

        def _show():
            index = combo.current()
            if index < 0:
                return
            code = codes[index]
            dialog.destroy()
            show_module_timeline_dialog(self.root, code)

        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text=_t('gui.academics.module_scheduling.main.buttons.show', default="Show"),
                   command=_show).pack(side=tk.LEFT)
        ttk.Button(buttons, text=_t('gui.academics.module_scheduling.main.buttons.cancel', default="Cancel"),
                   command=dialog.destroy).pack(side=tk.LEFT, padx=6)
        combo.bind("<Return>", lambda _e: _show())

    def set_auth(self, auth):
        """Optional; accept auth context from main app."""
        self._auth = auth

    @property
    def auth(self):
        """The signed-in session.

        ``set_auth`` stores ``_auth``, but the Open menu read ``self.auth``
        — a name nothing ever set — so it always handed ``None`` to the GUIs
        it launched. Grade Tracking then fell back to a guest with student
        privileges and Exam Management refused access, both while an admin
        was signed in. Exposing the one attribute under both names removes
        the mismatch.
        """
        session = getattr(self, "_auth", None)
        if isinstance(getattr(session, "current_user", None), dict):
            return session
        # Nothing was passed in: fall back to the process-wide session rather
        # than launching a sibling GUI as nobody.
        try:
            from education_system.systems.university.infrastructure.shared_context import (
                get_auth,
            )
            fallback = get_auth()
        except Exception:
            logger.debug("shared-context auth unavailable", exc_info=True)
            return session
        if isinstance(getattr(fallback, "current_user", None), dict):
            return fallback
        return session or fallback

    @auth.setter
    def auth(self, value):
        self._auth = value

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

        # Risks button — pops the risk-register entries linked to a
        # module, fed by cases_bus / attendance_bus / slot_writer
        # conflict detection.
        def _show_module_risks():
            from education_system.systems.university.services.bus.risks_panel import (
                show_risks_for,
            )

            try:
                modules = self.scheduler.get_all_modules() or []
            except Exception:
                modules = []
            options = [""] + [
                f"{m['code']} — {m['name']}" if m.get('name') else m['code']
                for m in modules if m.get('code')
            ]

            dlg = tk.Toplevel(self.root)
            dlg.title(_t('gui.academics.module_scheduling.main.windows.module_risks', default="Module risks"))
            dlg.transient(self.root)
            dlg.resizable(False, False)
            ttk.Label(dlg,
                      text=_t('gui.academics.module_scheduling.main.labels.select_a_module_leave_blank_to_view_all_module_risks', default="Select a module (leave blank to view all "
                           "module risks):")).pack(padx=15, pady=(15, 5))
            selected = tk.StringVar()
            cb = ttk.Combobox(dlg, textvariable=selected, values=options,
                              state="readonly", width=50)
            cb.pack(padx=15, pady=5)
            if options:
                cb.current(0)

            result = {"code": None, "ok": False}

            def _ok():
                val = selected.get().strip()
                result["code"] = val.split(" — ")[0] if val else ""
                result["ok"] = True
                dlg.destroy()

            def _cancel():
                dlg.destroy()

            btns = ttk.Frame(dlg)
            btns.pack(pady=(5, 15))
            ttk.Button(btns, text=_t('gui.academics.module_scheduling.main.buttons.ok', default="OK"), command=_ok).pack(side=tk.LEFT, padx=5)
            ttk.Button(btns, text=_t('gui.academics.module_scheduling.main.buttons.cancel', default="Cancel"),
                       command=_cancel).pack(side=tk.LEFT, padx=5)
            dlg.grab_set()
            self.root.wait_window(dlg)

            if not result["ok"]:
                return
            mc = result["code"]
            ref = f"module:{mc}" if mc else "module:"
            show_risks_for(self.root, ref,
                           title=f"Risks for {mc or 'all modules'}")
        risks_button = ttk.Button(toolbar_frame, text=_t('gui.academics.module_scheduling.main.buttons.risks', default="Risks"),
                                  command=_show_module_risks,
                                  style='Action.TButton')
        risks_button.pack(side=tk.LEFT, padx=5)

        # Title label
        title_label = ttk.Label(toolbar_frame, text=_t("scheduling.title"),
                               font=('Arial', 14, 'bold'))
        title_label.pack(side=tk.LEFT, padx=20)

        # Embedded period strip (#11). Always-visible context: term,
        # week-of-term, exam window status. Reads the calendar via the
        # cross-services helper, refreshes on bus events.
        try:
            from education_system.systems.university.domains.academics.interfaces.gui._cross_dialogs import (
                AcademicPeriodPanel,
            )
            AcademicPeriodPanel(main_frame).pack(fill=tk.X, padx=10, pady=(0, 4))
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)

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
        # Lesson planning: content attached to the slots above, replacing the
        # standalone Lesson Planner and its parallel lesson_plans timetable.
        self.create_lesson_plans_tab()
        self.create_management_tab()
        self.create_settings_tab()
        # Modules are managed in the Module Management window, not a tab here.

        # Menu bar
        self.create_menu_bar()

    def open_module_management(self):
        """Open the Module Management window, where modules are now edited."""
        try:
            from education_system.systems.university.domains.academics.interfaces.gui.module_management import (
                ModuleManagementGUI,
            )
            from education_system.platform.delivery.gui.window_sizing import center

            window = tk.Toplevel(self.root)
            window.withdraw()
            window.title(_t("academic_launchers.titles.module", default="Module Management"))
            center(window, 1400, 900, minsize=(1200, 800))
            window.transient(self.root)
            ModuleManagementGUI(window, auth=getattr(self, "auth", None))
            window.deiconify()
        except Exception as e:
            logger.exception("Failed to open Module Management")
            messagebox.showerror(_t('gui.academics.module_scheduling.main.dialogs.error', default="Error"),
                                 f"Failed to open Module Management: {e}", parent=self.root)

    def quick_add_module(self):
        """Dashboard quick action: the shared add-module form."""
        from education_system.systems.university.domains.academics.interfaces.gui._module_dialog import (
            open_module_dialog,
        )
        open_module_dialog(self.root, mode="add",
                           on_saved=lambda code: self.log_activity(f"Module added: {code}"))

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
            self._bind_shortcut(file_menu, _t("scheduling.import_csv"),
                                self.import_csv,
                                accelerator="Ctrl+I", sequence="<Control-i>")
            self._bind_shortcut(file_menu, _t("scheduling.export_all"),
                                self.export_all_data,
                                accelerator="Ctrl+E", sequence="<Control-e>")
            file_menu.add_separator()

        # Admin only - Backup/Restore
        if is_admin:
            file_menu.add_command(label=_t("scheduling.backup"), command=self.create_backup)
            file_menu.add_command(label=_t("scheduling.restore"), command=self.restore_backup)
            file_menu.add_separator()

        self._bind_shortcut(file_menu, _t("menu.exit", default="Exit"), self.on_closing,
                            accelerator="Ctrl+Q", sequence="<Control-q>")

        # Staff and Admin can manage modules
        if is_admin or is_staff:
            file_menu.add_separator()
            file_menu.add_command(label=_t("scheduling.manage_modules"), command=self.open_module_management)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.view"), menu=view_menu)
        self._bind_shortcut(view_menu, _t("scheduling.refresh_all"),
                            self.refresh_all_data,
                            accelerator="F5", sequence="<F5>")
        view_menu.add_command(label=_t("scheduling.grid_view"), command=self.show_grid_view)
        view_menu.add_command(
            label=_t("scheduling.drag_drop_grid", default="Drag-and-Drop Grid"),
            command=self._show_drag_drop_grid,
        )

        # Admin and Staff get CLI mode
        if is_admin or is_staff:
            view_menu.add_separator()
            view_menu.add_command(label=_t("scheduling.cli_mode"), command=self.launch_cli_mode)

        # Tools menu - Admin and Staff only
        if is_admin or is_staff:
            tools_menu = tk.Menu(menubar, tearoff=0)
            menubar.add_cascade(label=_t("menu.tools"), menu=tools_menu)
            self._bind_shortcut(
                tools_menu,
                _t("scheduling.new_schedule", default="New Schedule…"),
                self.show_add_schedule_dialog,
                accelerator="Ctrl+N", sequence="<Control-n>",
            )
            tools_menu.add_command(label=_t("scheduling.scheduling_wizard"), command=self.schedule_module_interactively)
            tools_menu.add_separator()
            tools_menu.add_command(
                label=_t("scheduling.auto_scheduler", default="Auto-Scheduler (What-If)…"),
                command=self.show_auto_scheduler_dialog)
            tools_menu.add_command(
                label=_t("scheduling.back_to_back_report", default="Back-to-Back & Travel Report…"),
                command=self.show_back_to_back_report)
            tools_menu.add_separator()
            tools_menu.add_command(label=_t("scheduling.detect_conflicts"), command=self.detect_all_conflicts)
            tools_menu.add_command(label=_t("scheduling.data_validation"), command=self.validate_data)
            tools_menu.add_command(label=_t("scheduling.generate_reports"), command=self.generate_reports)

        # Tree-scoped Delete: only fires when the schedules tree owns focus,
        # so pressing Delete inside an entry doesn't nuke a row by accident.
        # Bind after the tab+tree have been created.
        def _bind_delete_on_tree():
            tree = getattr(self, "schedules_tree", None)
            if tree:
                tree.bind("<Delete>",
                          lambda _e: self.delete_selected_schedule())
        self.root.after(100, _bind_delete_on_tree)

        # Open — cross-launch sibling academic GUIs in their own Toplevels.
        from education_system.systems.university.domains.academics.interfaces.gui._cross_launchers import (
            open_exam_gui, open_grade_gui, open_course_gui,
        )
        open_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t('gui.academics.module_scheduling.main.menus.open', default="Open"), menu=open_menu)
        open_menu.add_command(
            label=_t('gui.academics.module_scheduling.main.menus.exam_scheduler', default="Exam Management"),
            command=lambda: open_exam_gui(self.root, self.auth),
        )
        open_menu.add_command(
            label=_t('gui.academics.module_scheduling.main.menus.grade_tracking', default="Grade Tracking"),
            command=lambda: open_grade_gui(self.root, self.auth),
        )
        open_menu.add_command(
            label=_t('gui.academics.module_scheduling.main.menus.course_management', default="Course Management"),
            command=lambda: open_course_gui(self.root, self.auth),
        )

        # Cross-domain tools (instructor workload, at-risk, module timeline)
        from education_system.systems.university.domains.academics.interfaces.gui._cross_dialogs import (
            show_instructor_workload_dialog, show_at_risk_dialog,
            show_module_timeline_dialog,
        )
        from tkinter import simpledialog as _simpledialog
        cross_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t('gui.academics.module_scheduling.main.menus.cross_domain', default="Cross-Domain"), menu=cross_menu)
        cross_menu.add_command(
            label=_t('gui.academics.module_scheduling.main.menus.instructor_workload', default="Instructor workload…"),
            command=lambda: show_instructor_workload_dialog(self.root),
        )
        cross_menu.add_command(
            label=_t('gui.academics.module_scheduling.main.menus.at_risk_students_unified', default="At-risk students (unified)…"),
            command=lambda: show_at_risk_dialog(self.root),
        )
        cross_menu.add_command(
            label=_t('gui.academics.module_scheduling.main.menus.module_timeline', default="Module timeline…"),
            command=self._pick_module_for_timeline,
        )

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label=_t("menu.help"), menu=help_menu)
        help_menu.add_command(label=_t("scheduling.user_guide"), command=self.show_help)
        help_menu.add_command(label=_t("scheduling.about"), command=self.show_about)

    def _bind_shortcut(self, menu, label, command, accelerator=None, sequence=None):
        """Add a menu command + matching root key binding in one call.

        Going through one helper keeps the cosmetic accelerator label and
        the actual key binding from drifting apart.
        """
        kwargs = {"label": label, "command": command}
        if accelerator:
            kwargs["accelerator"] = accelerator
        menu.add_command(**kwargs)
        if sequence:
            self.root.bind_all(sequence, lambda _e, c=command: c())

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

        # Update dashboard activity. The panel is a table over ``activity_log``
        # now, with this window's own messages listed above the stored history;
        # keep the newest 100 of them.
        session = getattr(self, "_session_activity", None)
        if session is not None:
            session.insert(0, (timestamp, message))
            del session[100:]
            refresh = getattr(self, "load_recent_activity", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception:
                    logger.debug("could not refresh the activity table", exc_info=True)

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
        from education_system.systems.university.infrastructure.database.db import reuse_connection
        try:
            self.update_status("Refreshing data...")
            # These eight refreshes opened 11 separate connections between
            # them, and a fresh connection to student_records.db costs ~97ms
            # (the first statement opens the file and parses the schema) —
            # ~1.1s of pure setup before the window showed any data. Sharing
            # one connection for the burst pays that once. The refresh methods
            # are unchanged; their `with get_connection() as conn:` calls
            # transparently receive the shared connection inside this block.
            with reuse_connection():
                self.refresh_dashboard()
                self.refresh_schedules()
                self.refresh_rooms()
                self.refresh_instructors()
                self.refresh_conflicts()
                self.refresh_holidays()
                self.load_settings()
            self.update_status("Data refreshed successfully")
        except Exception as e:
            self.update_status(f"Error refreshing data: {str(e)}")
            messagebox.showerror(_t('gui.academics.module_scheduling.main.dialogs.error', default="Error"), f"Failed to refresh data: {str(e)}", parent=self.root)

    def return_to_main_menu(self):
        """Return to the main menu/GUI by closing this child window"""
        if messagebox.askyesno(_t('gui.academics.module_scheduling.main.dialogs.return_to_main_menu', default="Return to Main Menu"), _t('gui.academics.module_scheduling.main.dialogs.do_you_want_to_close_this_window_and_return_to_the_main_menu', default="Do you want to close this window and return to the main menu?"), parent=self.root):
            try:
                self.root.destroy()
            except Exception as e:
                messagebox.showerror(_t('gui.academics.module_scheduling.main.dialogs.error', default="Error"), f"Failed to return to main menu: {str(e)}", parent=self.root)

    #: The user guide, as (section, accent, [(action, what it does), ...]).
    #: Data rather than one long string, so it renders as cards and can be
    #: edited without touching layout code.
    _USER_GUIDE = [
        ("Dashboard", "#3498db", [
            ("Overview", "Live counts for schedules, rooms, instructors and open conflicts."),
            ("Recent activity", "The recorded activity log, with anything this window has done listed above it."),
        ]),
        ("Schedules", "#16a34a", [
            ("Add a session", "Pick the course first — the module list narrows to that course's modules. Rooms are listed on open and filter by building."),
            ("Edit or delete", "Select a row, or press Delete on the list."),
            ("Drag and drop", "Timetables → drag a session to a new slot. Confirming emails every student on the module and the instructor."),
        ]),
        ("Rooms and instructors", "#9b59b6", [
            ("Rooms", "Capacity, type and equipment; used by conflict detection and by Suggest Free Rooms."),
            ("Instructors", "Records, availability and maximum hours, which drive the workload report."),
        ]),
        ("Conflicts", "#dc2626", [
            ("Detect all", "Finds room double-bookings, instructor and student clashes, and over-capacity rooms."),
            ("Resolve selected", "Room and capacity conflicts are fixed by moving the session to a free, large-enough room. Instructor and student clashes need a person and are left with a note."),
            ("Resolve all", "Applies that fix to every conflict it can, then reports what it changed and what it left."),
        ]),
        ("Analytics", "#d97706", [
            ("Reports", "Room utilisation, instructor workload, peak usage and the comprehensive report."),
            ("Save", "Every report saves anywhere as PDF, CSV or TXT, or emails to an administrator."),
            ("Charts", "Generate charts, then save a copy where you want it."),
        ]),
        ("Settings and data", "#7f8c8d", [
            ("System settings", "Institution name comes from Branding & Customization and the semester dates from the academic calendar. Both are shown read-only here — change them where they are owned, so every screen agrees."),
            ("Holidays", "Adding a holiday also puts it on the academic calendar."),
            ("Backups", "Backup, restore and validate under Management."),
        ]),
    ]

    def show_help(self):
        """User guide, as titled cards rather than one block of text."""
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui import (
            report_widgets as _report,
        )
        window, surface = _report.report_window(
            self.root, _t('gui.academics.module_scheduling.main.windows.user_guide', default="User Guide"),
            "780x660")
        _report.banner(surface, "Module Scheduling — user guide",
                       "How to do the common jobs in this window")
        for title, accent, entries in self._USER_GUIDE:
            body = _report.card(surface, title, accent=accent)
            _report.kv_grid(body, entries, cols=1)
        window.lift()

    def show_about(self):
        """About window.

        Was a messagebox holding "Version: 2.0 … maintains full backward
        compatibility with the original command-line interface" — it named
        none of the eleven tabs that exist and was several major versions out
        of date. A messagebox also sizes to its text, which pushed its button
        out of view; this uses the same window style as the user guide, whose
        close button is anchored to the bottom.
        """
        from education_system.systems.university.domains.academics.interfaces.gui.course_management_gui import (
            report_widgets as _report,
        )
        try:
            from importlib.metadata import version as _dist_version
            version = _dist_version("education-system")
        except Exception:
            version = "unknown"

        window, surface = _report.report_window(
            self.root, _t('gui.academics.module_scheduling.main.dialogs.about', default="About"),
            "720x620")
        _report.banner(surface, "Module Scheduling",
                       f"Part of the University System · version {version}")
        _report.stat_strip(surface, [
            (self._about_count("module_schedule"), "Scheduled sessions"),
            (self._about_count("rooms"), "Rooms"),
            (self._about_count("modules"), "Modules"),
            (self._about_count("schedule_conflicts", "resolved = 0"), "Open conflicts"),
        ])

        body = _report.card(surface, "What this window does", accent="#3498db")
        tk.Label(body,
                 text="Builds and maintains the teaching timetable: sessions, "
                      "rooms, instructors and lesson plans, with conflict "
                      "detection, utilisation and workload reporting, and "
                      "bulk tools for rollover and cloning.",
                 bg=_report.CARD, fg=_report.VALUE, font=(_report.FONT, 9),
                 wraplength=620, justify="left").pack(anchor="w")

        body = _report.card(surface, "Tabs", accent="#9b59b6")
        _report.kv_grid(body, [
            ("Dashboard", "Counts and recorded activity"),
            ("Schedules", "Add, edit and delete sessions"),
            ("Rooms", "Room records and capacity"),
            ("Instructors", "Instructor records and availability"),
            ("Timetables", "Grid views, including drag-and-drop"),
            ("Analytics", "Utilisation, workload, peak usage, charts"),
            ("Conflicts", "Detect and resolve clashes"),
            ("Lesson plans", "Per-session teaching plans"),
            ("Management", "Backup, restore, validation, bulk reports"),
            ("Settings", "System settings and holidays"),
            ("Modules", "Module records"),
        ], cols=1)

        body = _report.card(surface, "Related screens", accent="#16a34a")
        _report.kv_grid(body, [
            ("Open menu", "Exam Management, Grade Tracking, Course Management"),
            ("Cross-domain", "Instructor workload, at-risk students, module timeline"),
        ], cols=1)

        tk.Label(surface, text="Python · Tkinter · SQLite",
                 bg=_report.BG, fg=_report.MUTED,
                 font=(_report.FONT, 8)).pack(anchor="w", padx=12, pady=(4, 10))
        window.lift()

    def _about_count(self, table, where=""):
        """Row count for the About panel, or an em dash."""
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                clause = f" WHERE {where}" if where else ""
                return conn.execute(f"SELECT COUNT(*) FROM {table}{clause}").fetchone()[0]
        except Exception:
            return "\u2014"

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
            from education_system.systems.university.domains.academics.domain.services.module_scheduling import display_enhanced_scheduling_menu
            display_enhanced_scheduling_menu()
        except ImportError:
            print("CLI mode also unavailable. Please check your installation.")

def launch_gui():
    """Alternative launcher function"""
    main()

def launch_cli():
    """Launch CLI mode directly"""
    try:
        from education_system.systems.university.domains.academics.domain.services.module_scheduling import display_enhanced_scheduling_menu
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
        # Create necessary directories under the project's data tree
        from education_system.paths import (
            UNIVERSITY_REPORTS_DIR,
            UNIVERSITY_BACKUP_DIR,
            UNIVERSITY_ANALYTICS_DIR,
            UNIVERSITY_TEMPLATES_DIR,
        )
        directories = [
            UNIVERSITY_REPORTS_DIR / 'timetable_reports',
            UNIVERSITY_BACKUP_DIR,
            UNIVERSITY_ANALYTICS_DIR,
            UNIVERSITY_TEMPLATES_DIR / 'ui' / 'scheduling',
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

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
