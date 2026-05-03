import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import subprocess
import sys

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.attendance_tab")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.attendance_tab")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import path constants
from education_system.university_system.modules.shared.constants.paths import DEFAULT_DB_PATH

# Import main database connection
try:
    from education_system.university_system.infrastructure.database.db import get_db_connection
    MAIN_DB_AVAILABLE = True
except ImportError:
    logger.exception("attendance_tab.py:33 %s", 'except ImportError')
    MAIN_DB_AVAILABLE = False

# Import all original functions and classes
try:
    from education_system.university_system.modules.domain.academics.services.attendance.attendance_tracker import (
        get_modules
    )
    ORIGINAL_FUNCTIONS_AVAILABLE = True
except ImportError:
    logger.exception("attendance_tab.py:42 %s", 'except ImportError')
    ORIGINAL_FUNCTIONS_AVAILABLE = False

# Feature flags
GEOFENCING_SUPPORT = True
FACE_RECOGNITION_SUPPORT = True

# Import window classes
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.attendance_windows import ManualAttendanceWindow, BatchAttendanceWindow, EditAttendanceWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.qr_windows import QRAttendanceWindow
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.face_recognition_windows import FaceRecognitionAttendanceWindow


def _resolve_absence_user(self):
    """Translate auth.current_user into the row shape the absence dashboards expect."""
    user = getattr(self.auth, "current_user", None) if getattr(self, "auth", None) else None
    if not user:
        return None
    try:
        from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking import absence_tracker as at
        db = at.Database()
        try:
            resolved = None
            if user.get("username"):
                resolved = db.lookup_user_by_username(user["username"])
            if not resolved and user.get("id") is not None:
                db.cur.execute(
                    "SELECT id, username, role, first_name, last_name, email, student_id "
                    "FROM users WHERE id = ?",
                    (user["id"],),
                )
                row = db.cur.fetchone()
                if row:
                    uid, uname, role, first, last, email, sid = row
                    resolved = {
                        "id": uid, "username": uname,
                        "role": user.get("role") or role,
                        "name": (f"{first or ''} {last or ''}").strip() or uname,
                        "email": email, "student_id": sid,
                    }
        finally:
            db.close()
        if resolved and user.get("role"):
            resolved["role"] = user["role"]
        return resolved
    except Exception:
        logger.exception("absence-tracker user resolution failed")
        return None

def _absence_user_signature(self):
    """Stable identity key — changes when the signed-in user changes."""
    user = getattr(getattr(self, "auth", None), "current_user", None)
    if not user:
        return None
    return (user.get("username"), user.get("id"))

def create_absence_tracker_tab(self):
    """Add an Absence Tracker tab whose contents are the full role-aware
    dashboard (Admin / Staff / Student).

    Built eagerly during idle time so the user's first click is instant,
    re-built automatically if the signed-in user changes, and exposes a
    role-view selector so admins can preview Staff / Student dashboards.
    """
    tab = ttk.Frame(self.notebook)
    self.notebook.add(tab, text="Absence Tracker")
    self._absence_tab_frame = tab
    self._absence_tab_built = False
    self._absence_tab_user_sig = None
    self._absence_tab_role_view = None  # admin override; None = use real role

    # Pre-build during idle: keeps the first click instant. If auth isn't
    # initialised yet, _maybe_build will re-defer.
    try:
        self.root.after(400, self._maybe_build_absence_tab)
    except Exception:
        pass
    # Re-check on tab selection — this is the cheap path that catches a
    # sign-out / sign-in (identity change) without polling.
    self.notebook.bind("<<NotebookTabChanged>>",
                       lambda _e: self._maybe_build_absence_tab(),
                       add="+")

def _maybe_build_absence_tab(self):
    """Build the absence tab, or rebuild if the active user changed."""
    tab = getattr(self, "_absence_tab_frame", None)
    if tab is None:
        return
    sig = self._absence_user_signature()
    if self._absence_tab_built and sig == self._absence_tab_user_sig:
        return  # already up-to-date
    if sig is None:
        # User signed out — wipe the dashboard and show a placeholder.
        for w in tab.winfo_children():
            w.destroy()
        ttk.Label(tab,
                  text="Please sign in to view the Absence Tracker.",
                  padding=20).pack(expand=True)
        self._absence_tab_built = False
        self._absence_tab_user_sig = None
        self._absence_tab_role_view = None
        return
    if sig != self._absence_tab_user_sig:
        # Different user — drop the previous role override.
        self._absence_tab_role_view = None
    for w in tab.winfo_children():
        w.destroy()
    self._build_absence_tab_contents(tab)
    self._absence_tab_user_sig = sig

def _build_absence_tab_contents(self, tab, role_override=None):
    resolved = self._resolve_absence_user()
    if not resolved:
        ttk.Label(tab,
                  text="Could not resolve your user record.",
                  padding=20).pack(expand=True)
        self._absence_tab_built = False
        return

    actual_role = (resolved.get("role") or "admin").lower()
    role_options = (["admin", "staff", "instructor", "student"]
                    if actual_role == "admin" else [actual_role])
    effective_role = role_override or self._absence_tab_role_view or actual_role
    if effective_role not in role_options:
        effective_role = actual_role

    # Role-switcher bar (only meaningful for admins)
    bar = ttk.Frame(tab)
    bar.pack(fill="x", padx=8, pady=(6, 4))
    ttk.Label(bar, text="View as role:").pack(side="left")
    role_var = tk.StringVar(value=effective_role)
    state = "readonly" if len(role_options) > 1 else "disabled"
    cb = ttk.Combobox(bar, textvariable=role_var, values=role_options,
                      state=state, width=12)
    cb.pack(side="left", padx=6)
    if len(role_options) == 1:
        ttk.Label(bar,
                  text="(your role — admins can switch views)",
                  foreground="#555555").pack(side="left", padx=4)

    def _on_role_change(_event=None):
        new = role_var.get()
        if new == effective_role:
            return
        self._absence_tab_role_view = new
        # Rebuild the body with the new role
        for w in tab.winfo_children():
            w.destroy()
        self._build_absence_tab_contents(tab, role_override=new)
    cb.bind("<<ComboboxSelected>>", _on_role_change)

    # Body that hosts the actual dashboard
    body = ttk.Frame(tab)
    body.pack(fill="both", expand=True)

    resolved_for_view = dict(resolved)
    resolved_for_view["role"] = effective_role

    selected = self.module_var.get() if hasattr(self, "module_var") else ""
    module = selected.split(" - ")[0] if selected else None
    sel_date = self.date_var.get() if hasattr(self, "date_var") else None
    prefill = {"module": module, "date": sel_date or None}

    try:
        from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking import absence_tracker as at
        at.launch_in_frame(body, resolved_for_view, prefill=prefill)
        self._absence_tab_built = True
    except Exception as exc:
        logger.exception("embedded absence tracker failed to build")
        ttk.Label(body,
                  text=f"Could not build Absence Tracker: {exc}",
                  padding=20).pack(expand=True)
        self._absence_tab_built = False

def open_today_dashboard(self):
        try:
            from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.today_dashboard import (  # noqa: E501
                open_today_window,
            )
            open_today_window(self.root)
        except Exception:
            logger.exception("Today dashboard failed to open")
            messagebox.showerror("Today",
                                 "Could not open the Today dashboard "
                                 "(see log).")

def refresh_attendance_data(self):
        """Refresh attendance data for current module"""
        selected = self.module_var.get()
        if selected:
            module_code = selected.split(' - ')[0]
            self.load_module_students(module_code)
        self.refresh_recent_activity()
        self.update_dashboard_stats()

def manual_attendance(self):
        """Open manual attendance entry dialog"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.select_module_first"))
            return

        module_code = selected.split(' - ')[0]
        date = self.date_var.get()

        # Create manual attendance window
        ManualAttendanceWindow(self.root, module_code, date, self.refresh_attendance_data)

def batch_attendance(self):
        """Open batch attendance entry dialog for marking all students at once"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.select_module_first"))
            return

        module_code = selected.split(' - ')[0]
        date = self.date_var.get()

        # Create batch attendance window
        BatchAttendanceWindow(self.root, module_code, date, self.refresh_attendance_data)

def refresh_modules(self):
        """Refresh module combo box"""
        try:
            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                modules = [("CS101", "Introduction to Programming"), ("CS102", "Data Structures")]
            else:
                modules = get_modules()

            module_list = [f"{code} - {name}" for code, name in modules]
            self.module_combo['values'] = module_list

            if module_list:
                self.module_combo.set(module_list[0])

        except Exception as e:
            logger.exception("attendance_tab.py:127 %s", 'except Exception as e')
            print(f"Error refreshing modules: {e}")

def qr_attendance(self):
        """Open QR code attendance dialog"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.select_module_first"))
            return

        if not self.qr_system:
            messagebox.showerror(_("common.error"), _("attendance.messages.qr_system_not_available"))
            return

        module_code = selected.split(' - ')[0]
        date = self.date_var.get()

        QRAttendanceWindow(self.root, self.qr_system, module_code, date, self.refresh_attendance_data)

def edit_attendance_record(self, event):
        """Edit selected attendance record"""
        selection = self.student_tree.selection()
        if not selection:
            return

        item = self.student_tree.item(selection[0])
        student_id, name, current_status, notes, _ = item['values']

        # Create edit dialog
        EditAttendanceWindow(self.root, student_id, name, current_status, notes,
                           self.module_var.get().split(' - ')[0], self.date_var.get(),
                           self.refresh_attendance_data)

def on_module_selected(self, event=None):
        """Handle module selection"""
        selected = self.module_var.get()
        if selected:
            module_code = selected.split(' - ')[0]
            self.load_module_students(module_code)

def load_module_students(self, module_code):
        """Load students for selected module"""
        try:
            # Clear existing items
            for item in self.student_tree.get_children():
                self.student_tree.delete(item)

            if not ORIGINAL_FUNCTIONS_AVAILABLE:
                # Sample data
                sample_attendance = [
                    ("S001", "John Doe", "Present", "", "2024-12-20 09:15"),
                    ("S002", "Jane Smith", "Late", "Traffic delay", "2024-12-20 09:25"),
                    ("S003", "Bob Wilson", "Absent", "", ""),
                ]

                for attendance in sample_attendance:
                    self.student_tree.insert('', 'end', values=attendance)
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            # Get students enrolled in this module
            cursor.execute('''
            SELECT DISTINCT s.student_id, s.first_name || ' ' || s.last_name as name
            FROM students s
            JOIN student_modules sm ON s.student_id = sm.student_id
            WHERE sm.module_code = ?
            ORDER BY s.student_id
            ''', (module_code,))

            students = cursor.fetchall()
            date = self.date_var.get()

            for student_id, name in students:
                # Get attendance for this date
                cursor.execute('''
                SELECT status, notes, recorded_at
                FROM attendance_records
                WHERE student_id = ? AND module_code = ? AND date = ?
                ''', (student_id, module_code, date))

                attendance = cursor.fetchone()

                if attendance:
                    status, notes, recorded_at = attendance
                    last_update = recorded_at.split('T')[1][:5] if 'T' in recorded_at else recorded_at[-8:-3]
                else:
                    status, notes, last_update = "Not Recorded", "", ""

                self.student_tree.insert('', 'end', values=(student_id, name, status, notes or "", last_update))

            conn.close()

        except Exception as e:
            logger.exception("attendance_tab.py:221 %s", 'except Exception as e')
            print(f"Error loading module students: {e}")
            messagebox.showerror(_("common.error"), _("attendance.messages.failed_to_load_students").format(error=e))

def create_attendance_tab(self):
        """Create attendance management tab"""
        attendance_frame = ttk.Frame(self.notebook)
        self.notebook.add(attendance_frame, text=_("attendance.tabs.attendance"))

        # Left panel - Controls with scrollbar
        left_container = ttk.Frame(attendance_frame)
        left_container.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Create scrollable left panel
        left_canvas = tk.Canvas(left_container, width=300, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_panel = ttk.Frame(left_canvas)

        left_panel.bind(
            "<Configure>",
            lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        )

        left_canvas.create_window((0, 0), window=left_panel, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        left_canvas.pack(side="left", fill="y", expand=True)
        left_scrollbar.pack(side="right", fill="y")

        # Module selection
        module_frame = ttk.LabelFrame(left_panel, text=_("attendance.module_selection"), padding=10)
        module_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(module_frame, text=_("attendance.labels.select_module")).pack(anchor=tk.W)
        self.module_var = tk.StringVar()
        self.module_combo = ttk.Combobox(module_frame, textvariable=self.module_var, state="readonly", width=30)
        self.module_combo.pack(fill=tk.X, pady=(5, 0))
        self.module_combo.bind('<<ComboboxSelected>>', self.on_module_selected)

        # Date selection
        date_frame = ttk.LabelFrame(left_panel, text=_("attendance.date_selection"), padding=10)
        date_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(date_frame, text=_("attendance.labels.date")).pack(anchor=tk.W)
        self.date_var = tk.StringVar(value=datetime.date.today().isoformat())
        date_entry = ttk.Entry(date_frame, textvariable=self.date_var, width=30)
        date_entry.pack(fill=tk.X, pady=(5, 0))

        # Attendance methods
        methods_frame = ttk.LabelFrame(left_panel, text=_("attendance.checkin_methods"), padding=10)
        methods_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(methods_frame, text=_("attendance.buttons.manual_entry"),
                  command=self.manual_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(methods_frame, text=_("attendance.buttons.qr_code"),
                  command=self.qr_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(methods_frame, text=_("attendance.buttons.geofencing"),
                  command=self.geo_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(methods_frame, text=_("attendance.buttons.face_recognition"),
                  command=self.face_attendance, style='Primary.TButton').pack(fill=tk.X, pady=2)

        # Quick actions
        actions_frame = ttk.LabelFrame(left_panel, text=_("attendance.quick_actions"), padding=10)
        actions_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(actions_frame, text=_("attendance.buttons.refresh_data"),
                  command=self.refresh_attendance_data, style='Success.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text=_("attendance.buttons.generate_report"),
                  command=self.generate_quick_report, style='Warning.TButton').pack(fill=tk.X, pady=2)
        ttk.Button(actions_frame, text="Today (cross-system)",
                  command=self.open_today_dashboard,
                  style='Primary.TButton').pack(fill=tk.X, pady=2)

        # Right panel - Student list and attendance
        right_panel = ttk.Frame(attendance_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Students frame
        students_frame = ttk.LabelFrame(right_panel, text=_("attendance.students"), padding=10)
        students_frame.pack(fill=tk.BOTH, expand=True)

        # Student treeview
        student_columns = (_("attendance.columns.id"), _("attendance.columns.name"), _("attendance.columns.status"), _("attendance.columns.notes"), _("attendance.columns.last_update"))
        self.student_tree = ttk.Treeview(students_frame, columns=student_columns, show="headings")

        for col in student_columns:
            self.student_tree.heading(col, text=col)
            self.student_tree.column(col, width=120)

        student_scrollbar = ttk.Scrollbar(students_frame, orient=tk.VERTICAL, command=self.student_tree.yview)
        self.student_tree.configure(yscrollcommand=student_scrollbar.set)

        self.student_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        student_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Double-click to edit
        self.student_tree.bind('<Double-1>', self.edit_attendance_record)

def geo_attendance(self):
        """Open geofencing attendance dialog"""
        if not self.geo_system:
            messagebox.showinfo(_("attendance.settings.geofencing"), _("attendance.messages.geofencing_not_available"))
            return

        # Create geofencing attendance window
        geo_window = tk.Toplevel(self.root)
        geo_window.title(_("attendance.geofencing.title"))
        geo_window.geometry("700x600")
        geo_window.transient(self.root)
        geo_window.grab_set()

        # Title
        title_frame = ttk.Frame(geo_window)
        title_frame.pack(fill='x', padx=20, pady=20)
        ttk.Label(title_frame, text=_("attendance.geofencing.header"), style='Title.TLabel').pack()

        # Configuration frame
        config_frame = ttk.LabelFrame(geo_window, text=_("attendance.geofencing.location_config"), padding="15")
        config_frame.pack(fill='x', padx=20, pady=(0, 15))

        # Location settings
        ttk.Label(config_frame, text=_("attendance.geofencing.classroom_location")).grid(row=0, column=0, sticky='w', padx=(0, 10))
        location_var = tk.StringVar(value="University Building A, Room 101")
        ttk.Entry(config_frame, textvariable=location_var, width=40).grid(row=0, column=1, sticky='ew')

        ttk.Label(config_frame, text=_("attendance.geofencing.gps_coordinates")).grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        coords_var = tk.StringVar(value="40.7128, -74.0060")
        ttk.Entry(config_frame, textvariable=coords_var, width=40).grid(row=1, column=1, sticky='ew', pady=(10, 0))

        ttk.Label(config_frame, text=_("attendance.geofencing.radius_meters")).grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        radius_var = tk.StringVar(value="50")
        ttk.Entry(config_frame, textvariable=radius_var, width=40).grid(row=2, column=1, sticky='ew', pady=(10, 0))

        config_frame.grid_columnconfigure(1, weight=1)

        # Current students frame
        students_frame = ttk.LabelFrame(geo_window, text=_("attendance.geofencing.attendance_status"), padding="15")
        students_frame.pack(fill='both', expand=True, padx=20, pady=(0, 15))

        # Students treeview
        columns = (_("attendance.columns.student"), _("attendance.columns.status"), _("attendance.columns.location"), _("attendance.columns.time"))
        students_tree = ttk.Treeview(students_frame, columns=columns, show='headings', height=12)
        for col in columns:
            students_tree.heading(col, text=col)
            students_tree.column(col, width=150)

        students_tree.pack(fill='both', expand=True, pady=(0, 10))

        # Load actual attendance data from database
        try:
            with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
                cursor = conn.cursor()
                # `attendance_records.recorded_at` is the canonical
                # check-in timestamp column — there is no `check_in_time`.
                cursor.execute('''
                    SELECT
                        s.first_name || ' ' || s.last_name || ' (' || s.student_id || ')' as student,
                        CASE
                            WHEN ar.status = 'present' THEN 'Present'
                            WHEN ar.status = 'late' THEN 'Late'
                            ELSE 'Absent'
                        END as status,
                        COALESCE(ar.location_data, 'Unknown') as location,
                        COALESCE(strftime('%I:%M %p', ar.recorded_at), '--') as time
                    FROM students s
                    LEFT JOIN attendance_records ar ON s.student_id = ar.student_id
                        AND ar.date = date('now')
                    ORDER BY s.last_name, s.first_name
                    LIMIT 50
                ''')
                attendance_data = cursor.fetchall()

                for student_data in attendance_data:
                    students_tree.insert('', 'end', values=student_data)

                if not attendance_data:
                    # Show message if no data available
                    students_tree.insert('', 'end', values=(_("attendance.messages.no_students_found"), "", "", ""))
        except Exception as e:
            logger.exception("attendance_tab.py:396 %s", 'except Exception as e')
            students_tree.insert('', 'end', values=(_("attendance.messages.error_loading_data").format(error=e), "", "", ""))

        # Control buttons
        button_frame = ttk.Frame(geo_window)
        button_frame.pack(fill='x', padx=20, pady=(0, 20))

        def start_geofencing():
            messagebox.showinfo(_("attendance.messages.geofencing_started"), _("attendance.messages.geofencing_started_message"))

        def stop_geofencing():
            messagebox.showinfo(_("attendance.messages.geofencing_stopped"), _("attendance.messages.geofencing_stopped_message"))

        def view_map():
            messagebox.showinfo(_("attendance.messages.map_view"), _("attendance.messages.map_view_message"))

        ttk.Button(button_frame, text=_("attendance.geofencing.start"), command=start_geofencing).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_("attendance.geofencing.stop"), command=stop_geofencing).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_("attendance.geofencing.view_map"), command=view_map).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text=_("common.close"), command=geo_window.destroy).pack(side='right')

def face_attendance(self):
        """Open face recognition attendance dialog with live camera feed"""
        selected = self.module_var.get()
        if not selected:
            messagebox.showwarning(_("common.warning"), _("attendance.messages.select_module_first"))
            return

        module_code = selected.split(' - ')[0]
        date = self.date_var.get()

        # Check if face recognition is available
        if not self.face_system:
            # Show installation instructions if libraries not available
            messagebox.showinfo(_("attendance.messages.face_recognition_setup"), _("attendance.messages.face_recognition_not_available"))
            return

        # Create face recognition window
        FaceRecognitionAttendanceWindow(self.root, self.face_system, module_code, date,
                                       self.refresh_attendance_data)

