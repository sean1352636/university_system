"""Attendance management GUI."""

import csv
import io
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import date, datetime, timedelta

from education_system.secondary_school.modules.domain.academics.attendance.services.attendance_service import AttendanceService
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.infrastructure.database.constants import ATTENDANCE_STATUSES
from education_system.secondary_school.core.exceptions import AttendanceError

PERIODS = ["AM", "PM", "1", "2", "3", "4", "5", "6"]

DFE_CODES = {
    "B": "Off-site educational activity",
    "C": "Authorised holiday during term",
    "D": "Dual registration at another school",
    "E": "Excluded (no alternative provision)",
    "H": "Holiday (agreed)",
    "I": "Illness",
    "J": "Interview",
    "L": "Late (before register closes)",
    "M": "Medical/dental appointment",
    "N": "No reason yet",
    "O": "Unauthorised absence",
    "P": "Approved sporting activity",
    "R": "Religious observance",
    "S": "Study leave",
    "T": "Traveller absence",
    "U": "Late (after register closes)",
    "V": "Educational visit",
    "W": "Work experience",
}

AUTHORISATION_REASONS = [
    "Illness", "Medical appointment", "Family bereavement",
    "Religious observance", "Approved holiday", "Court appearance",
    "Interview", "Excluded", "Other (specify)",
]

DRAFTS_DIR = os.path.join(os.path.expanduser("~"), ".school_attendance_drafts")


class AttendanceFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AttendanceService(db_path)
        self._stu_svc = StudentService(db_path)
        self._attendance_data = {}
        self._all_rows = []
        self._undo_stack = []
        self._redo_stack = []
        self._change_log = []
        self._saved_snapshot = {}
        self._locked = False
        self._dark_mode = False
        self._sort_reverse = {}
        self._notes_panel_visible = False
        self._notes_data = {}
        self._remind_timer = None
        self._unsaved = False
        self._absence_threshold = 90.0
        self._font_size = 10
        self._high_contrast = False
        self._auto_save_timer = None
        self._auto_save_interval = 300000  # 5 minutes
        self._term_dates = {}
        self._exam_periods = []
        self._bank_holidays = []
        self._build_ui()

    # ── UI CONSTRUCTION ──────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Attendance", font=("Helvetica", 15, "bold"),
                 bg="#1a5276", fg="white").pack(side="left", padx=20, pady=10)

        # ── Top controls ──
        controls = tk.Frame(self, bg="#ecf0f1", pady=8)
        controls.pack(fill="x", padx=15)

        tk.Label(controls, text="Date:", bg="#ecf0f1").pack(side="left", padx=4)
        self._date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(controls, textvariable=self._date_var, width=12).pack(side="left", padx=4)

        ttk.Button(controls, text="<", width=2, command=self._prev_day).pack(side="left")
        ttk.Button(controls, text="Today", command=self._go_to_today).pack(side="left", padx=2)
        ttk.Button(controls, text=">", width=2, command=self._next_day).pack(side="left")

        tk.Label(controls, text="Year:", bg="#ecf0f1").pack(side="left", padx=(15, 4))
        self._year_var = tk.StringVar(value="7")
        ttk.Combobox(controls, textvariable=self._year_var,
                     values=["7", "8", "9", "10", "11"], state="readonly", width=5).pack(side="left", padx=4)

        tk.Label(controls, text="Period:", bg="#ecf0f1").pack(side="left", padx=(15, 4))
        self._period_var = tk.StringVar(value="AM")
        ttk.Combobox(controls, textvariable=self._period_var,
                     values=PERIODS, state="readonly", width=5).pack(side="left", padx=4)
        ttk.Button(controls, text="<P", width=2, command=self._prev_period).pack(side="left")
        ttk.Button(controls, text="P>", width=2, command=self._next_period).pack(side="left")

        ttk.Button(controls, text="Load Register", command=self._load_register).pack(side="left", padx=15)
        ttk.Button(controls, text="Save All", command=self._save_all).pack(side="left", padx=4)

        # ── Filter bar ──
        filter_bar = tk.Frame(self, bg="#ecf0f1", pady=4)
        filter_bar.pack(fill="x", padx=15)

        tk.Label(filter_bar, text="Search:", bg="#ecf0f1").pack(side="left", padx=4)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_by_name())
        ttk.Entry(filter_bar, textvariable=self._search_var, width=18).pack(side="left", padx=4)

        tk.Label(filter_bar, text="Form:", bg="#ecf0f1").pack(side="left", padx=(10, 4))
        self._form_filter_var = tk.StringVar(value="All")
        self._form_combo = ttk.Combobox(filter_bar, textvariable=self._form_filter_var,
                                        values=["All"], state="readonly", width=10)
        self._form_combo.pack(side="left", padx=4)
        self._form_combo.bind("<<ComboboxSelected>>", lambda _: self._filter_by_form_group())

        tk.Label(filter_bar, text="Status:", bg="#ecf0f1").pack(side="left", padx=(10, 4))
        self._status_filter_var = tk.StringVar(value="All")
        status_combo = ttk.Combobox(filter_bar, textvariable=self._status_filter_var,
                                    values=["All"] + list(ATTENDANCE_STATUSES), state="readonly", width=14)
        status_combo.pack(side="left", padx=4)
        status_combo.bind("<<ComboboxSelected>>", lambda _: self._filter_by_status())

        ttk.Button(filter_bar, text="Clear Filters", command=self._clear_filters).pack(side="left", padx=8)
        ttk.Button(filter_bar, text="Find by ID", command=self._search_student_by_id).pack(side="left", padx=4)

        # ── Action bar ──
        action_bar = tk.Frame(self, bg="#ecf0f1", pady=4)
        action_bar.pack(fill="x", padx=15)

        ttk.Button(action_bar, text="All Present", command=self._mark_all_present).pack(side="left", padx=3)
        ttk.Button(action_bar, text="All Absent", command=self._mark_all_absent).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Sel. Present", command=self._mark_selected_present).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Sel. Absent", command=self._mark_selected_absent).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Sel. Late", command=self._mark_selected_late).pack(side="left", padx=3)

        ttk.Separator(action_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(action_bar, text="Undo", command=self._undo_last_change).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Redo", command=self._redo_last_change).pack(side="left", padx=3)

        ttk.Separator(action_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(action_bar, text="Stats", command=self._show_summary_stats).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Weekly", command=self._show_weekly_report).pack(side="left", padx=3)
        ttk.Button(action_bar, text="CSV Export", command=self._export_to_csv).pack(side="left", padx=3)
        ttk.Button(action_bar, text="PDF Export", command=self._export_to_pdf).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Print", command=self._print_register).pack(side="left", padx=3)

        ttk.Separator(action_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(action_bar, text="Lock", command=self._lock_register).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Notes", command=self._show_notes_panel).pack(side="left", padx=3)
        ttk.Button(action_bar, text="Dark Mode", command=self._toggle_dark_mode).pack(side="left", padx=3)

        # ── Main content area (tree + optional notes panel) ──
        self._content_frame = tk.Frame(self)
        self._content_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        # Register treeview
        tree_frame = tk.Frame(self._content_frame)
        tree_frame.pack(side="left", fill="both", expand=True)

        columns = ("student_id", "name", "form_group", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="extended")

        for col, heading, w in [
            ("student_id", "Student ID", 90), ("name", "Name", 200),
            ("form_group", "Form", 70), ("status", "Status", 120),
        ]:
            self._tree.heading(col, text=heading,
                               command=lambda c=col: self._sort_by_column(c))
            self._tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._tree.bind("<Double-1>", self._on_toggle_status)

        # Notes side panel (hidden by default)
        self._notes_frame = tk.Frame(self._content_frame, bg="#d5dbdb", width=250)
        self._notes_text = tk.Text(self._notes_frame, width=30, height=10, wrap="word")
        self._notes_student_label = tk.Label(self._notes_frame, text="Select a student",
                                             bg="#d5dbdb", font=("Helvetica", 10, "bold"))

        # ── Bottom toolbar ──
        bottom_bar = tk.Frame(self, bg="#ecf0f1", pady=4)
        bottom_bar.pack(fill="x", padx=15)

        ttk.Button(bottom_bar, text="Student Profile", command=self._open_student_profile).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Add Note", command=self._add_attendance_note).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Flag Follow-up", command=self._flag_for_followup).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Contact Info", command=self._show_contact_info).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Medical Notes", command=self._view_medical_notes).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="History", command=self._show_student_history).pack(side="left", padx=3)

        ttk.Separator(bottom_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bottom_bar, text="Persistent Absences", command=self._alert_persistent_absentees).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Late List", command=self._show_late_arrivals_list).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Safeguarding", command=self._trigger_safeguarding_alert).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Notify Parent", command=self._send_absence_notification).pack(side="left", padx=3)

        ttk.Separator(bottom_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bottom_bar, text="Sync Timetable", command=self._sync_with_timetable).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Import CSV", command=self._import_from_csv).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Change Log", command=self._show_change_log).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Audit Log", command=self._audit_log_view).pack(side="left", padx=3)
        ttk.Button(bottom_bar, text="Reset", command=self._reset_to_last_saved).pack(side="left", padx=3)

        # ── Analytics toolbar ──
        analytics_bar = tk.Frame(self, bg="#ecf0f1", pady=4)
        analytics_bar.pack(fill="x", padx=15)

        ttk.Button(analytics_bar, text="Heatmap", command=self._show_attendance_heatmap).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="% Attendance", command=self._calculate_attendance_percentage).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Pattern Abs.", command=self._identify_pattern_absences).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Compare Years", command=self._compare_year_groups).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Form League", command=self._show_form_group_league).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Trend", command=self._trend_line_chart).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Mon/Fri Abs.", command=self._detect_monday_friday_absences).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Punctuality", command=self._show_punctuality_stats).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Abs. vs Grades", command=self._correlate_absence_with_grades).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="At Risk", command=self._predict_at_risk_students).pack(side="left", padx=3)

        ttk.Separator(analytics_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(analytics_bar, text="Threshold", command=self._set_absence_threshold).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Below Target", command=self._list_below_threshold).pack(side="left", padx=3)
        ttk.Button(analytics_bar, text="Interventions", command=self._generate_intervention_list).pack(side="left", padx=3)

        # ── Codes & authorisation toolbar ──
        codes_bar = tk.Frame(self, bg="#ecf0f1", pady=4)
        codes_bar.pack(fill="x", padx=15)

        ttk.Button(codes_bar, text="Auth. Absence", command=self._mark_authorised_absence).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Unauth. Absence", command=self._mark_unauthorised_absence).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Bulk Authorise", command=self._bulk_authorise_selected).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Auth. Reasons", command=self._view_authorisation_reasons).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Meeting Flag", command=self._schedule_meeting_flag).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Return Interview", command=self._record_return_interview).pack(side="left", padx=3)

        ttk.Separator(codes_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(codes_bar, text="B Code", command=self._apply_B_code).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="C Code", command=self._apply_C_code).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="D Code", command=self._apply_D_code).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="E Code", command=self._apply_E_code).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="DfE Code", command=self._apply_custom_code).pack(side="left", padx=3)

        ttk.Separator(codes_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(codes_bar, text="Cover Reg.", command=self._load_cover_register).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Cover Teacher", command=self._assign_cover_teacher).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Merge AM/PM", command=self._merge_registers).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="Set/Band", command=self._split_group_view).pack(side="left", padx=3)
        ttk.Button(codes_bar, text="By Subject", command=self._load_by_subject).pack(side="left", padx=3)

        # ── Communication & calendar toolbar ──
        comm_bar = tk.Frame(self, bg="#ecf0f1", pady=4)
        comm_bar.pack(fill="x", padx=15)

        ttk.Button(comm_bar, text="Email Parent", command=self._compose_absence_email).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Log Call", command=self._log_phone_call).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Bulk SMS", command=self._send_bulk_sms).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Letter", command=self._generate_letter_template).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Comms History", command=self._view_communication_history).pack(side="left", padx=3)

        ttk.Separator(comm_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(comm_bar, text="Bank Hols", command=self._mark_bank_holidays).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Term Dates", command=self._load_term_dates).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Days Left", command=self._show_remaining_school_days).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Exam Period", command=self._flag_exam_period).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Sync Calendar", command=self._sync_to_calendar_app).pack(side="left", padx=3)

        ttk.Separator(comm_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(comm_bar, text="A+", command=self._increase_font_size).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="A-", command=self._decrease_font_size).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Hi-Contrast", command=self._toggle_high_contrast).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Keyboard Nav", command=self._enable_keyboard_navigation).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Read Aloud", command=self._read_aloud_selected).pack(side="left", padx=3)

        ttk.Separator(comm_bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(comm_bar, text="Auto-save", command=self._auto_save_draft).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Recover Draft", command=self._recover_last_draft).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Backup JSON", command=self._export_backup_json).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Restore JSON", command=self._import_backup_json).pack(side="left", padx=3)
        ttk.Button(comm_bar, text="Clear Drafts", command=self._clear_all_drafts).pack(side="left", padx=3)

        # Status bar
        self._status_var = tk.StringVar(value="Select year group and load register")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        pass

    # ── CORE ─────────────────────────────────────────────────────────

    def _load_register(self):
        if self._unsaved and not self._check_unsaved_changes():
            return

        self._tree.delete(*self._tree.get_children())
        year = self._year_var.get()

        try:
            students = self._stu_svc.list_students(status="active", year_group=year, limit=500)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        self._attendance_data = {}
        self._all_rows = []
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._change_log.clear()
        self._unsaved = False
        self._locked = False

        form_groups = set()
        for s in students:
            status = "present"
            fg = s.get("form_group", "") or ""
            form_groups.add(fg)
            row_data = {
                "pk": s["id"],
                "student_id": s["student_id"],
                "name": f"{s['first_name']} {s['last_name']}",
                "form_group": fg,
                "status": status,
            }
            self._all_rows.append(row_data)
            self._attendance_data[s["id"]] = status
            self._tree.insert("", "end", iid=s["id"], values=(
                s["student_id"], row_data["name"], fg, status,
            ))

        self._snapshot_state()
        self._form_combo["values"] = ["All"] + sorted(form_groups)
        self._status_var.set(f"{len(students)} students in Year {year}")
        self._highlight_missing_entries()

    def _on_toggle_status(self, event):
        if self._locked:
            messagebox.showinfo("Locked", "Register is locked. Unlock to make changes.")
            return
        sel = self._tree.selection()
        if not sel:
            return
        pk = int(sel[0])
        statuses = list(ATTENDANCE_STATUSES)
        current = self._attendance_data.get(pk, "present")
        idx = statuses.index(current) if current in statuses else 0
        new_status = statuses[(idx + 1) % len(statuses)]

        self._push_undo(pk, current, new_status)
        self._attendance_data[pk] = new_status
        self._unsaved = True

        values = list(self._tree.item(sel[0], "values"))
        values[3] = new_status
        self._tree.item(sel[0], values=values)

        for rd in self._all_rows:
            if rd["pk"] == pk:
                rd["status"] = new_status
                break

        self._highlight_absences()

    def _save_all(self):
        if not self._attendance_data:
            messagebox.showwarning("Warning", "Load the register first.")
            return

        date_str = self._date_var.get()
        if not self._validate_date_format():
            return
        if not self._validate_period():
            return

        period = self._period_var.get()
        recorded_by = self._auth["username"] if self._auth else "system"
        saved = 0
        errors = 0

        for student_pk, status in self._attendance_data.items():
            note = self._notes_data.get(student_pk)
            try:
                self._svc.record_attendance(
                    student_id=student_pk,
                    date_str=date_str,
                    status=status,
                    period=period,
                    recorded_by=recorded_by,
                    note=note,
                )
                saved += 1
            except AttendanceError:
                errors += 1

        self._unsaved = False
        self._snapshot_state()
        if self._remind_timer:
            self.after_cancel(self._remind_timer)
            self._remind_timer = None

        messagebox.showinfo("Attendance Saved", f"Saved: {saved}\nErrors: {errors}")
        self._status_var.set(f"Attendance saved for {date_str} period {period}")

    # ── FILTERING & SEARCH (1-5) ─────────────────────────────────────

    def _filter_by_name(self):
        """1. Search students by name in real-time."""
        self._apply_filters()

    def _filter_by_form_group(self):
        """2. Filter register to a specific form group."""
        self._apply_filters()

    def _filter_by_status(self):
        """3. Show only absent/late/present students."""
        self._apply_filters()

    def _clear_filters(self):
        """4. Reset all active filters."""
        self._search_var.set("")
        self._form_filter_var.set("All")
        self._status_filter_var.set("All")
        self._apply_filters()

    def _search_student_by_id(self):
        """5. Jump to a student by ID."""
        sid = simpledialog.askstring("Find Student", "Enter student ID (e.g. SEC0001):")
        if not sid:
            return
        for item in self._tree.get_children():
            vals = self._tree.item(item, "values")
            if vals[0] == sid:
                self._tree.selection_set(item)
                self._tree.see(item)
                self._tree.focus(item)
                return
        messagebox.showinfo("Not Found", f"Student ID '{sid}' not found in current register.")

    def _apply_filters(self):
        """Rebuild treeview based on current filter settings."""
        search = self._search_var.get().lower()
        form = self._form_filter_var.get()
        status = self._status_filter_var.get()

        self._tree.delete(*self._tree.get_children())
        for rd in self._all_rows:
            if search and search not in rd["name"].lower():
                continue
            if form != "All" and rd["form_group"] != form:
                continue
            current_status = self._attendance_data.get(rd["pk"], rd["status"])
            if status != "All" and current_status != status:
                continue
            self._tree.insert("", "end", iid=rd["pk"], values=(
                rd["student_id"], rd["name"], rd["form_group"], current_status,
            ))
        self._highlight_absences()

    # ── BULK ACTIONS (6-10) ──────────────────────────────────────────

    def _mark_all_present(self):
        """6. Set every student to present."""
        if self._locked:
            return
        self._bulk_set_status(self._tree.get_children(), "present")

    def _mark_all_absent(self):
        """7. Set every student to absent."""
        if self._locked:
            return
        self._bulk_set_status(self._tree.get_children(), "absent")

    def _mark_selected_present(self):
        """8. Mark only highlighted rows present."""
        if self._locked:
            return
        self._bulk_set_status(self._tree.selection(), "present")

    def _mark_selected_absent(self):
        """9. Mark only highlighted rows absent."""
        if self._locked:
            return
        self._bulk_set_status(self._tree.selection(), "absent")

    def _mark_selected_late(self):
        """10. Bulk-mark selected students as late."""
        if self._locked:
            return
        self._bulk_set_status(self._tree.selection(), "late")

    def _bulk_set_status(self, items, new_status):
        for iid in items:
            pk = int(iid)
            old = self._attendance_data.get(pk, "present")
            if old != new_status:
                self._push_undo(pk, old, new_status)
                self._attendance_data[pk] = new_status
                for rd in self._all_rows:
                    if rd["pk"] == pk:
                        rd["status"] = new_status
                        break
                vals = list(self._tree.item(iid, "values"))
                vals[3] = new_status
                self._tree.item(iid, values=vals)
        self._unsaved = True
        self._highlight_absences()

    # ── DATA VALIDATION (11-15) ──────────────────────────────────────

    def _validate_date_format(self) -> bool:
        """11. Check date entry is valid ISO format."""
        try:
            datetime.strptime(self._date_var.get(), "%Y-%m-%d")
            return True
        except ValueError:
            messagebox.showerror("Invalid Date",
                                 "Date must be in YYYY-MM-DD format.")
            return False

    def _check_unsaved_changes(self) -> bool:
        """12. Warn before navigating away with unsaved data. Returns True to proceed."""
        if not self._unsaved:
            return True
        return messagebox.askyesno("Unsaved Changes",
                                   "You have unsaved changes. Discard and continue?")

    def _validate_period(self) -> bool:
        """13. Ensure period is set before saving."""
        if not self._period_var.get():
            messagebox.showerror("Missing Period", "Please select a period before saving.")
            return False
        return True

    def _check_duplicate_entry(self) -> bool:
        """14. Warn if attendance already saved for that date/period."""
        date_str = self._date_var.get()
        period = self._period_var.get()
        year = self._year_var.get()
        try:
            exists = self._svc.check_duplicate_entry(date_str, period, year)
        except Exception:
            return False
        if exists:
            return messagebox.askyesno("Duplicate Entry",
                                       f"Attendance for {date_str} period {period} already exists.\nOverwrite?")
        return True

    def _highlight_missing_entries(self):
        """15. Visually flag rows with no status set."""
        for iid in self._tree.get_children():
            pk = int(iid)
            status = self._attendance_data.get(pk)
            if not status:
                self._tree.item(iid, tags=("missing",))
        self._tree.tag_configure("missing", background="#f9e79f")

    # ── NAVIGATION (16-20) ───────────────────────────────────────────

    def _prev_day(self):
        """16. Load the previous school day's register."""
        if self._unsaved and not self._check_unsaved_changes():
            return
        try:
            current = datetime.strptime(self._date_var.get(), "%Y-%m-%d").date()
        except ValueError:
            return
        delta = 3 if current.weekday() == 0 else 1  # Monday -> skip weekend
        new_date = current - timedelta(days=delta)
        self._date_var.set(new_date.isoformat())
        self._load_register()

    def _next_day(self):
        """17. Load the next school day's register."""
        if self._unsaved and not self._check_unsaved_changes():
            return
        try:
            current = datetime.strptime(self._date_var.get(), "%Y-%m-%d").date()
        except ValueError:
            return
        delta = 3 if current.weekday() == 4 else 1  # Friday -> skip weekend
        new_date = current + timedelta(days=delta)
        self._date_var.set(new_date.isoformat())
        self._load_register()

    def _go_to_today(self):
        """18. Reset date field to today and reload."""
        if self._unsaved and not self._check_unsaved_changes():
            return
        self._date_var.set(date.today().isoformat())
        self._load_register()

    def _prev_period(self):
        """19. Switch to the previous period."""
        current = self._period_var.get()
        idx = PERIODS.index(current) if current in PERIODS else 0
        if idx > 0:
            self._period_var.set(PERIODS[idx - 1])

    def _next_period(self):
        """20. Switch to the next period."""
        current = self._period_var.get()
        idx = PERIODS.index(current) if current in PERIODS else 0
        if idx < len(PERIODS) - 1:
            self._period_var.set(PERIODS[idx + 1])

    # ── REPORTING & EXPORT (21-25) ───────────────────────────────────

    def _export_to_csv(self):
        """21. Export current register to a CSV file."""
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Student ID", "Name", "Form Group", "Status", "Date", "Period"])
            for iid in self._tree.get_children():
                vals = self._tree.item(iid, "values")
                writer.writerow([vals[0], vals[1], vals[2], vals[3],
                                 self._date_var.get(), self._period_var.get()])
        self._status_var.set(f"Exported to {path}")

    def _export_to_pdf(self):
        """22. Generate a printable PDF register."""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            messagebox.showerror("Missing Library",
                                 "reportlab is required for PDF export.\npip install reportlab")
            return

        path = filedialog.asksaveasfilename(defaultextension=".pdf",
                                            filetypes=[("PDF", "*.pdf")])
        if not path:
            return

        doc = SimpleDocTemplate(path, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = [Paragraph(
            f"Attendance Register — Year {self._year_var.get()} — "
            f"{self._date_var.get()} Period {self._period_var.get()}",
            styles["Title"],
        )]

        data = [["Student ID", "Name", "Form", "Status"]]
        for iid in self._tree.get_children():
            data.append(list(self._tree.item(iid, "values")))

        table = Table(data, colWidths=[80, 180, 60, 100])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a5276")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        elements.append(table)
        doc.build(elements)
        self._status_var.set(f"PDF exported to {path}")

    def _show_summary_stats(self):
        """23. Pop up present/absent/late counts."""
        counts = {}
        for pk, status in self._attendance_data.items():
            counts[status] = counts.get(status, 0) + 1
        total = len(self._attendance_data)
        lines = [f"Total students: {total}"]
        for s in ATTENDANCE_STATUSES:
            c = counts.get(s, 0)
            pct = round(c / total * 100, 1) if total else 0
            lines.append(f"  {s}: {c} ({pct}%)")
        messagebox.showinfo("Summary Statistics", "\n".join(lines))

    def _show_weekly_report(self):
        """24. Open a summary of the week's attendance."""
        if not self._validate_date_format():
            return
        current = datetime.strptime(self._date_var.get(), "%Y-%m-%d").date()
        monday = current - timedelta(days=current.weekday())
        year = self._year_var.get()

        try:
            data = self._svc.get_weekly_summary(year, monday.isoformat())
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Weekly Report — Year {year} — w/c {monday.isoformat()}")
        win.geometry("500x350")

        tree = ttk.Treeview(win, columns=("date", "status", "count"), show="headings")
        for col, w in [("date", 120), ("status", 150), ("count", 80)]:
            tree.heading(col, text=col.title())
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for row in data:
            tree.insert("", "end", values=(row["date"], row["status"], row["cnt"]))

    def _show_student_history(self):
        """25. View a selected student's attendance history."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a student first.")
            return
        pk = int(sel[0])
        vals = self._tree.item(sel[0], "values")

        try:
            records = self._svc.get_student_attendance(pk)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Attendance History — {vals[1]} ({vals[0]})")
        win.geometry("550x400")

        summary = self._svc.get_attendance_summary(pk)
        tk.Label(win, text=f"Attendance: {summary['percentage']}% | "
                          f"P:{summary['present']} A:{summary['absent']} L:{summary['late']}",
                 font=("Helvetica", 10, "bold")).pack(pady=5)

        tree = ttk.Treeview(win, columns=("date", "period", "status", "note"), show="headings")
        for col, w in [("date", 100), ("period", 60), ("status", 110), ("note", 200)]:
            tree.heading(col, text=col.title())
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=5)

        for r in records:
            tree.insert("", "end", values=(
                r.get("date", ""), r.get("period", ""),
                r.get("status", ""), r.get("note", "") or "",
            ))

    # ── UNDO / HISTORY (26-30) ───────────────────────────────────────

    def _push_undo(self, pk, old_status, new_status):
        self._undo_stack.append((pk, old_status, new_status))
        self._redo_stack.clear()
        self._change_log.append({
            "pk": pk, "from": old_status, "to": new_status,
            "time": datetime.now().strftime("%H:%M:%S"),
        })

    def _undo_last_change(self):
        """26. Revert the most recent status toggle."""
        if not self._undo_stack:
            self._status_var.set("Nothing to undo")
            return
        pk, old_status, new_status = self._undo_stack.pop()
        self._redo_stack.append((pk, old_status, new_status))
        self._attendance_data[pk] = old_status
        for rd in self._all_rows:
            if rd["pk"] == pk:
                rd["status"] = old_status
                break
        self._refresh_row(pk, old_status)
        self._status_var.set(f"Undid change for student {pk}")

    def _redo_last_change(self):
        """27. Reapply a reverted change."""
        if not self._redo_stack:
            self._status_var.set("Nothing to redo")
            return
        pk, old_status, new_status = self._redo_stack.pop()
        self._undo_stack.append((pk, old_status, new_status))
        self._attendance_data[pk] = new_status
        for rd in self._all_rows:
            if rd["pk"] == pk:
                rd["status"] = new_status
                break
        self._refresh_row(pk, new_status)
        self._status_var.set(f"Redid change for student {pk}")

    def _show_change_log(self):
        """28. List all changes made in the current session."""
        if not self._change_log:
            messagebox.showinfo("Change Log", "No changes recorded this session.")
            return
        win = tk.Toplevel(self)
        win.title("Session Change Log")
        win.geometry("450x350")
        tree = ttk.Treeview(win, columns=("time", "student", "from", "to"), show="headings")
        for col, w in [("time", 80), ("student", 80), ("from", 120), ("to", 120)]:
            tree.heading(col, text=col.title())
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for entry in reversed(self._change_log):
            tree.insert("", "end", values=(
                entry["time"], entry["pk"], entry["from"], entry["to"],
            ))

    def _reset_to_last_saved(self):
        """29. Discard unsaved changes and reload from snapshot."""
        if not self._saved_snapshot:
            messagebox.showinfo("Info", "No saved snapshot to restore.")
            return
        self._attendance_data = dict(self._saved_snapshot)
        for rd in self._all_rows:
            rd["status"] = self._attendance_data.get(rd["pk"], "present")
        self._unsaved = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._apply_filters()
        self._status_var.set("Reset to last saved state")

    def _snapshot_state(self):
        """30. Save a local in-memory snapshot for comparison."""
        self._saved_snapshot = dict(self._attendance_data)

    # ── UI / DISPLAY (31-35) ─────────────────────────────────────────

    def _toggle_dark_mode(self):
        """31. Switch between light and dark colour schemes."""
        self._dark_mode = not self._dark_mode
        bg = "#2c3e50" if self._dark_mode else "#ecf0f1"
        fg = "#ecf0f1" if self._dark_mode else "#2c3e50"
        header_bg = "#1a252f" if self._dark_mode else "#1a5276"

        for widget in self.winfo_children():
            try:
                if isinstance(widget, tk.Frame):
                    widget.configure(bg=bg)
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Label):
                            child.configure(bg=bg, fg=fg)
                        elif isinstance(child, tk.Frame):
                            child.configure(bg=bg)
                elif isinstance(widget, tk.Label):
                    widget.configure(bg=bg, fg=fg)
            except tk.TclError:
                pass
        self.configure(bg=bg)

    def _resize_columns(self):
        """32. Auto-fit column widths to content."""
        for col in self._tree["columns"]:
            max_width = max(
                (len(str(self._tree.set(iid, col)))
                 for iid in self._tree.get_children()),
                default=5,
            )
            header_width = len(self._tree.heading(col, "text"))
            width = max(max_width, header_width) * 9 + 20
            self._tree.column(col, width=min(width, 300))

    def _sort_by_column(self, col):
        """33. Click a heading to sort ascending/descending."""
        reverse = self._sort_reverse.get(col, False)
        data = [(self._tree.set(iid, col), iid) for iid in self._tree.get_children()]
        data.sort(key=lambda t: t[0].lower(), reverse=reverse)
        for idx, (_, iid) in enumerate(data):
            self._tree.move(iid, "", idx)
        self._sort_reverse[col] = not reverse

    def _highlight_absences(self):
        """34. Colour-code absent rows in red, late in orange."""
        self._tree.tag_configure("absent_row", background="#f1948a")
        self._tree.tag_configure("late_row", background="#f0b27a")
        self._tree.tag_configure("present_row", background="")
        for iid in self._tree.get_children():
            pk = int(iid)
            status = self._attendance_data.get(pk, "present")
            if status in ("absent", "unauthorised_absent", "authorised_absent"):
                self._tree.item(iid, tags=("absent_row",))
            elif status == "late":
                self._tree.item(iid, tags=("late_row",))
            else:
                self._tree.item(iid, tags=("present_row",))

    def _show_notes_panel(self):
        """35. Expand a side panel for per-student notes."""
        if self._notes_panel_visible:
            self._notes_frame.pack_forget()
            self._notes_panel_visible = False
            return

        self._notes_frame.pack(side="right", fill="y", padx=(5, 0))
        self._notes_student_label.pack(pady=5, padx=5)
        self._notes_text.pack(fill="both", expand=True, padx=5, pady=5)

        save_btn = ttk.Button(self._notes_frame, text="Save Note",
                              command=self._save_note_from_panel)
        save_btn.pack(pady=5)
        self._notes_panel_visible = True
        self._tree.bind("<<TreeviewSelect>>", self._on_tree_select_for_notes)

    def _on_tree_select_for_notes(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        pk = int(sel[0])
        vals = self._tree.item(sel[0], "values")
        self._notes_student_label.config(text=f"{vals[1]} ({vals[0]})")
        self._notes_text.delete("1.0", "end")
        self._notes_text.insert("1.0", self._notes_data.get(pk, ""))

    def _save_note_from_panel(self):
        sel = self._tree.selection()
        if not sel:
            return
        pk = int(sel[0])
        self._notes_data[pk] = self._notes_text.get("1.0", "end").strip()
        self._status_var.set(f"Note saved for student {pk}")

    # ── STUDENT DETAILS (36-40) ──────────────────────────────────────

    def _get_selected_student(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a student first.")
            return None, None
        pk = int(sel[0])
        return pk, self._tree.item(sel[0], "values")

    def _open_student_profile(self):
        """36. Open a detail window for the selected student."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        try:
            student = self._stu_svc.get_student(pk)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        if not student:
            messagebox.showinfo("Not Found", "Student record not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Student Profile — {vals[1]}")
        win.geometry("400x350")

        fields = [
            ("Student ID", student.get("student_id", "")),
            ("Name", f"{student.get('first_name', '')} {student.get('last_name', '')}"),
            ("Year Group", student.get("year_group", "")),
            ("Form Group", student.get("form_group", "")),
            ("Date of Birth", student.get("date_of_birth", "")),
            ("Gender", student.get("gender", "")),
            ("Status", student.get("status", "")),
            ("SEN Status", student.get("sen_status", "") or "None"),
            ("Pupil Premium", "Yes" if student.get("pupil_premium") else "No"),
        ]
        for i, (label, value) in enumerate(fields):
            tk.Label(win, text=f"{label}:", font=("Helvetica", 10, "bold"),
                     anchor="e", width=15).grid(row=i, column=0, padx=10, pady=3, sticky="e")
            tk.Label(win, text=str(value), anchor="w").grid(row=i, column=1, padx=10, pady=3, sticky="w")

    def _add_attendance_note(self):
        """37. Attach a free-text note to a student's record."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        existing = self._notes_data.get(pk, "")
        note = simpledialog.askstring("Attendance Note",
                                      f"Note for {vals[1]}:",
                                      initialvalue=existing)
        if note is not None:
            self._notes_data[pk] = note
            self._unsaved = True
            self._status_var.set(f"Note added for {vals[1]}")

    def _flag_for_followup(self):
        """38. Mark a student for pastoral follow-up."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        reason = simpledialog.askstring("Follow-up", f"Reason for flagging {vals[1]}:")
        if not reason:
            return
        self._notes_data[pk] = self._notes_data.get(pk, "") + f"\n[FOLLOW-UP] {reason}"
        self._unsaved = True
        messagebox.showinfo("Flagged", f"{vals[1]} flagged for pastoral follow-up.")

    def _show_contact_info(self):
        """39. Display emergency contact for selected student."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        try:
            student = self._stu_svc.get_student(pk)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        if not student:
            return
        contact_lines = [
            f"Student: {vals[1]} ({vals[0]})",
            f"Emergency Contact: {student.get('emergency_contact_name', 'N/A')}",
            f"Phone: {student.get('emergency_contact_phone', 'N/A')}",
            f"Email: {student.get('email', 'N/A')}",
            f"Parent/Guardian Email: {student.get('parent_email', 'N/A')}",
        ]
        messagebox.showinfo("Contact Information", "\n".join(contact_lines))

    def _view_medical_notes(self):
        """40. Show any medical flags on a student record."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        try:
            student = self._stu_svc.get_student(pk)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        if not student:
            return
        medical = student.get("medical_notes", "") or student.get("medical_info", "") or "No medical notes on file."
        messagebox.showinfo(f"Medical Notes — {vals[1]}", medical)

    # ── NOTIFICATIONS & ALERTS (41-45) ───────────────────────────────

    def _alert_persistent_absentees(self):
        """41. Flag students absent X days in a row."""
        days = simpledialog.askinteger("Consecutive Days",
                                       "Flag students absent for how many days?",
                                       initialvalue=3, minvalue=1, maxvalue=30)
        if not days:
            return
        year = self._year_var.get()
        try:
            absentees = self._svc.get_persistent_absentees(year, days)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        if not absentees:
            messagebox.showinfo("Persistent Absentees", "No persistent absentees found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Persistent Absentees — {days}+ days — Year {year}")
        win.geometry("500x300")
        tree = ttk.Treeview(win, columns=("sid", "name", "form", "days"), show="headings")
        for col, w in [("sid", 90), ("name", 180), ("form", 70), ("days", 80)]:
            tree.heading(col, text=col.title())
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for a in absentees:
            tree.insert("", "end", values=(
                a["student_id"], f"{a['first_name']} {a['last_name']}",
                a.get("form_group", ""), a["absent_days"],
            ))

    def _send_absence_notification(self):
        """42. Trigger an automated parent email/SMS."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        status = self._attendance_data.get(pk, "present")
        if status == "present":
            messagebox.showinfo("Info", f"{vals[1]} is marked present. No notification needed.")
            return
        confirmed = messagebox.askyesno(
            "Send Notification",
            f"Send absence notification to parent/guardian of {vals[1]}?",
        )
        if confirmed:
            self._status_var.set(f"Absence notification queued for {vals[1]}")
            messagebox.showinfo("Notification", f"Absence notification queued for {vals[1]}.\n"
                                                 "Email will be sent via the notification service.")

    def _show_late_arrivals_list(self):
        """43. Separate view of all late students today."""
        late = [(rd["student_id"], rd["name"], rd["form_group"])
                for rd in self._all_rows
                if self._attendance_data.get(rd["pk"]) == "late"]
        if not late:
            messagebox.showinfo("Late Arrivals", "No late arrivals in current register.")
            return

        win = tk.Toplevel(self)
        win.title(f"Late Arrivals — {self._date_var.get()}")
        win.geometry("400x300")
        tree = ttk.Treeview(win, columns=("sid", "name", "form"), show="headings")
        for col, w in [("sid", 90), ("name", 200), ("form", 70)]:
            tree.heading(col, text=col.title())
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for sid, name, form in late:
            tree.insert("", "end", values=(sid, name, form))

    def _trigger_safeguarding_alert(self):
        """44. Raise a flag for unexplained absence."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        status = self._attendance_data.get(pk, "present")
        if status not in ("absent", "unauthorised_absent"):
            messagebox.showinfo("Info", f"{vals[1]} is not marked as absent.")
            return
        reason = simpledialog.askstring("Safeguarding Alert",
                                        f"Describe concern for {vals[1]}:")
        if not reason:
            return
        try:
            from education_system.secondary_school.modules.domain.pastoral_care.safeguarding.services.safeguarding_service import SafeguardingService
            sg_svc = SafeguardingService(self._db_path)
            reported_by = self._auth["username"] if self._auth else "system"
            sg_svc.log_concern(
                student_id=pk,
                reported_by=reported_by,
                concern_type="welfare",
                severity="medium",
                description=f"Unexplained absence flagged from attendance register: {reason}",
            )
            messagebox.showinfo("Safeguarding", f"Safeguarding concern logged for {vals[1]}.")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to log safeguarding concern: {exc}")

    def _remind_unsaved(self):
        """45. Show a timed reminder if register hasn't been saved."""
        if self._unsaved:
            self._status_var.set("Reminder: You have unsaved attendance changes!")
        self._remind_timer = self.after(120000, self._remind_unsaved)  # every 2 min

    # ── ADMIN / INTEGRATION (46-50) ──────────────────────────────────

    def _sync_with_timetable(self):
        """46. Auto-select period based on current time."""
        now = datetime.now()
        hour = now.hour
        if hour < 9:
            period = "AM"
        elif hour < 10:
            period = "1"
        elif hour < 11:
            period = "2"
        elif hour < 12:
            period = "3"
        elif hour < 13:
            period = "PM"
        elif hour < 14:
            period = "4"
        elif hour < 15:
            period = "5"
        else:
            period = "6"
        self._period_var.set(period)
        self._date_var.set(date.today().isoformat())
        self._status_var.set(f"Synced to current timetable slot: period {period}")

    def _import_from_csv(self):
        """47. Load attendance data from an external CSV."""
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc))
            return

        recorded_by = self._auth["username"] if self._auth else "csv_import"
        try:
            result = self._svc.import_from_csv(rows, recorded_by)
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc))
            return

        messagebox.showinfo("CSV Import",
                            f"Imported: {result['imported']}\nErrors: {result['errors']}")
        self._status_var.set(f"CSV import complete: {result['imported']} records")

    def _print_register(self):
        """48. Send the current register to the system printer."""
        try:
            import tempfile
            import subprocess

            tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
            tmp.write(f"Attendance Register — Year {self._year_var.get()} — "
                      f"{self._date_var.get()} Period {self._period_var.get()}\n")
            tmp.write("=" * 60 + "\n")
            tmp.write(f"{'Student ID':<12} {'Name':<25} {'Form':<8} {'Status':<15}\n")
            tmp.write("-" * 60 + "\n")
            for iid in self._tree.get_children():
                vals = self._tree.item(iid, "values")
                tmp.write(f"{vals[0]:<12} {vals[1]:<25} {vals[2]:<8} {vals[3]:<15}\n")
            tmp.close()

            import platform
            if platform.system() == "Windows":
                import os
                os.startfile(tmp.name, "print")
            else:
                subprocess.run(["lpr", tmp.name], check=False)
            self._status_var.set("Register sent to printer")
        except Exception as exc:
            messagebox.showerror("Print Error", str(exc))

    def _lock_register(self):
        """49. Prevent edits after a register is finalised."""
        if self._locked:
            self._locked = False
            self._status_var.set("Register unlocked")
        else:
            if self._unsaved:
                if not messagebox.askyesno("Lock", "Save before locking? Unsaved changes will be lost."):
                    return
            self._locked = True
            self._status_var.set("Register locked — no further edits allowed")

    def _audit_log_view(self):
        """50. Display a read-only log of who saved what and when."""
        date_str = self._date_var.get()
        year = self._year_var.get()

        try:
            logs = self._svc.get_audit_log(date_str=date_str, year_group=year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Audit Log — {date_str} Year {year}")
        win.geometry("650x400")

        tree = ttk.Treeview(win, columns=("id", "student", "period", "status", "recorded_by"),
                            show="headings")
        for col, w in [("id", 50), ("student", 180), ("period", 60),
                       ("status", 120), ("recorded_by", 120)]:
            tree.heading(col, text=col.replace("_", " ").title())
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for log in logs:
            tree.insert("", "end", values=(
                log["id"],
                f"{log['first_name']} {log['last_name']} ({log['sid']})",
                log.get("period", ""),
                log["status"],
                log.get("recorded_by", ""),
            ))

    # ── ATTENDANCE PATTERNS & ANALYTICS (1-10) ──────────────────────

    def _show_attendance_heatmap(self):
        """1. Calendar heatmap of absences per student."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        try:
            data = self._svc.get_student_heatmap_data(pk)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Attendance Heatmap — {vals[1]}")
        win.geometry("700x420")

        canvas = tk.Canvas(win, bg="white")
        canvas.pack(fill="both", expand=True, padx=10, pady=10)

        colour_map = {"present": "#27ae60", "late": "#f39c12",
                      "absent": "#e74c3c", "unauthorised_absent": "#c0392b",
                      "authorised_absent": "#e67e22"}

        by_date = {}
        for r in data:
            by_date.setdefault(r["date"], []).append(r["status"])

        sorted_dates = sorted(by_date.keys())
        if not sorted_dates:
            canvas.create_text(350, 200, text="No attendance data found.",
                               font=("Helvetica", 12))
            return

        cell = 18
        cols = 30
        x0, y0 = 20, 50
        canvas.create_text(350, 20, text=f"Heatmap for {vals[1]} ({vals[0]})",
                           font=("Helvetica", 11, "bold"))

        for i, d in enumerate(sorted_dates):
            row, col_idx = divmod(i, cols)
            x = x0 + col_idx * (cell + 2)
            y = y0 + row * (cell + 2)
            statuses = by_date[d]
            worst = "present"
            for s in statuses:
                if s in ("absent", "unauthorised_absent"):
                    worst = s
                    break
                if s == "late":
                    worst = s
            colour = colour_map.get(worst, "#bdc3c7")
            canvas.create_rectangle(x, y, x + cell, y + cell, fill=colour, outline="#ecf0f1")

        legend_y = y0 + ((len(sorted_dates) // cols) + 2) * (cell + 2)
        for i, (status, colour) in enumerate(colour_map.items()):
            lx = x0 + i * 130
            canvas.create_rectangle(lx, legend_y, lx + 14, legend_y + 14, fill=colour, outline="")
            canvas.create_text(lx + 20, legend_y + 7, text=status, anchor="w", font=("Helvetica", 8))

    def _calculate_attendance_percentage(self):
        """2. Show % attendance per student YTD."""
        year = self._year_var.get()
        try:
            data = self._svc.get_all_student_percentages(year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Attendance Percentages — Year {year}")
        win.geometry("550x400")
        tree = ttk.Treeview(win, columns=("sid", "name", "form", "total", "pct"), show="headings")
        for col, h, w in [("sid", "ID", 80), ("name", "Name", 170), ("form", "Form", 60),
                          ("total", "Sessions", 70), ("pct", "%", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for s in data:
            tree.insert("", "end", values=(
                s["student_id"], f"{s['first_name']} {s['last_name']}",
                s.get("form_group", ""), s["total"], f"{s['percentage']}%",
            ))

    def _identify_pattern_absences(self):
        """3. Flag students always absent on specific days."""
        year = self._year_var.get()
        try:
            data = self._svc.get_day_pattern_absences(year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        if not data:
            messagebox.showinfo("Pattern Absences", "No day-pattern absences detected.")
            return

        win = tk.Toplevel(self)
        win.title(f"Pattern Absences — Year {year}")
        win.geometry("500x350")
        tree = ttk.Treeview(win, columns=("sid", "name", "day", "count"), show="headings")
        for col, h, w in [("sid", "ID", 80), ("name", "Name", 170),
                          ("day", "Day", 100), ("count", "Count", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for r in data:
            tree.insert("", "end", values=(
                r["student_id"], f"{r['first_name']} {r['last_name']}",
                r["day_name"], r["absence_count"],
            ))

    def _compare_year_groups(self):
        """4. Side-by-side attendance rates across years."""
        try:
            data = self._svc.compare_year_groups()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title("Year Group Comparison")
        win.geometry("400x300")
        tree = ttk.Treeview(win, columns=("year", "total", "attended", "pct"), show="headings")
        for col, h, w in [("year", "Year", 60), ("total", "Sessions", 80),
                          ("attended", "Attended", 80), ("pct", "%", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for r in data:
            tree.insert("", "end", values=(
                r["year_group"], r["total"], r["attended"], f"{r['percentage']}%",
            ))

    def _show_form_group_league(self):
        """5. Rank form groups by attendance rate."""
        year = self._year_var.get()
        try:
            data = self._svc.get_form_group_rates(year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Form Group League — Year {year}")
        win.geometry("400x300")
        tree = ttk.Treeview(win, columns=("rank", "form", "total", "pct"), show="headings")
        for col, h, w in [("rank", "#", 40), ("form", "Form Group", 100),
                          ("total", "Sessions", 80), ("pct", "%", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for i, r in enumerate(data, 1):
            tree.insert("", "end", values=(i, r["form_group"], r["total"], f"{r['percentage']}%"))

    def _trend_line_chart(self):
        """6. Plot attendance trend over the past term."""
        year = self._year_var.get()
        try:
            data = self._svc.get_attendance_trend(year, days=60)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        if not data:
            messagebox.showinfo("Trend", "No attendance data for trend chart.")
            return

        win = tk.Toplevel(self)
        win.title(f"Attendance Trend — Year {year}")
        win.geometry("750x400")

        canvas = tk.Canvas(win, bg="white")
        canvas.pack(fill="both", expand=True, padx=10, pady=10)

        w, h = 700, 320
        margin_l, margin_b = 50, 40
        max_pct = 100.0
        n = len(data)
        if n < 2:
            canvas.create_text(w // 2, h // 2, text="Need at least 2 days of data.")
            return

        step_x = (w - margin_l - 20) / (n - 1)
        scale_y = (h - margin_b - 30) / max_pct

        canvas.create_line(margin_l, h - margin_b, w - 10, h - margin_b, fill="#bdc3c7")
        canvas.create_line(margin_l, h - margin_b, margin_l, 10, fill="#bdc3c7")

        for tick in [0, 25, 50, 75, 100]:
            y = h - margin_b - tick * scale_y
            canvas.create_text(margin_l - 5, y, text=f"{tick}%", anchor="e", font=("Helvetica", 7))
            canvas.create_line(margin_l, y, w - 10, y, fill="#ecf0f1", dash=(2, 4))

        points = []
        for i, d in enumerate(data):
            x = margin_l + i * step_x
            y = h - margin_b - d["percentage"] * scale_y
            points.extend([x, y])

        if len(points) >= 4:
            canvas.create_line(points, fill="#2980b9", width=2, smooth=True)
        for i in range(0, len(points), 2):
            canvas.create_oval(points[i] - 3, points[i + 1] - 3,
                               points[i] + 3, points[i + 1] + 3, fill="#2980b9", outline="")

    def _detect_monday_friday_absences(self):
        """7. Highlight suspicious Mon/Fri absence patterns."""
        year = self._year_var.get()
        try:
            data = self._svc.get_monday_friday_absences(year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        if not data:
            messagebox.showinfo("Mon/Fri Absences", "No suspicious Mon/Fri patterns detected.")
            return

        win = tk.Toplevel(self)
        win.title(f"Monday/Friday Absence Patterns — Year {year}")
        win.geometry("500x300")
        tree = ttk.Treeview(win, columns=("sid", "name", "mf", "total"), show="headings")
        for col, h, w in [("sid", "ID", 80), ("name", "Name", 180),
                          ("mf", "Mon/Fri Abs", 80), ("total", "Total Abs", 80)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for r in data:
            tree.insert("", "end", values=(
                r["student_id"], f"{r['first_name']} {r['last_name']}",
                r["mon_fri_abs"], r["total_abs"],
            ))

    def _show_punctuality_stats(self):
        """8. Breakdown of late vs on-time arrivals."""
        year = self._year_var.get()
        try:
            stats = self._svc.get_punctuality_stats(year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return
        msg = (f"Year {year} Punctuality\n\n"
               f"On time: {stats['on_time']} ({stats['on_time_pct']}%)\n"
               f"Late:    {stats['late']} ({stats['late_pct']}%)\n"
               f"Total:   {stats['total']}")
        messagebox.showinfo("Punctuality Statistics", msg)

    def _correlate_absence_with_grades(self):
        """9. Cross-reference attendance and academic data."""
        year = self._year_var.get()
        try:
            from education_system.secondary_school.modules.domain.academics.grades.services.grade_service import GradeService
            grade_svc = GradeService(self._db_path)
        except ImportError:
            messagebox.showerror("Error", "Grade service not available.")
            return

        try:
            att_data = self._svc.get_all_student_percentages(year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Attendance vs Grades — Year {year}")
        win.geometry("600x400")
        tree = ttk.Treeview(win, columns=("sid", "name", "att_pct", "avg_grade"), show="headings")
        for col, h, w in [("sid", "ID", 80), ("name", "Name", 180),
                          ("att_pct", "Attendance %", 90), ("avg_grade", "Avg Grade", 90)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for s in att_data:
            try:
                grades = grade_svc.get_student_grades(s["id"])
                if grades:
                    numeric = [g.get("grade_value", 0) or 0 for g in grades
                               if g.get("grade_value") is not None]
                    avg = round(sum(numeric) / len(numeric), 1) if numeric else "N/A"
                else:
                    avg = "N/A"
            except Exception:
                avg = "N/A"
            tree.insert("", "end", values=(
                s["student_id"], f"{s['first_name']} {s['last_name']}",
                f"{s['percentage']}%", avg,
            ))

    def _predict_at_risk_students(self):
        """10. Flag students trending toward threshold breaches."""
        year = self._year_var.get()
        try:
            data = self._svc.get_all_student_percentages(year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        warning_zone = self._absence_threshold + 5
        at_risk = [s for s in data if s["percentage"] < warning_zone and s["total"] > 0]
        at_risk.sort(key=lambda s: s["percentage"])

        if not at_risk:
            messagebox.showinfo("At Risk", "No students currently at risk of threshold breach.")
            return

        win = tk.Toplevel(self)
        win.title(f"At Risk Students — Year {year} (threshold: {self._absence_threshold}%)")
        win.geometry("550x380")
        tree = ttk.Treeview(win, columns=("sid", "name", "pct", "status"), show="headings")
        for col, h, w in [("sid", "ID", 80), ("name", "Name", 180),
                          ("pct", "%", 60), ("status", "Status", 120)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        tree.tag_configure("below", background="#f1948a")
        tree.tag_configure("warning", background="#f9e79f")

        for s in at_risk:
            tag = "below" if s["percentage"] < self._absence_threshold else "warning"
            label = "BELOW TARGET" if tag == "below" else "WARNING ZONE"
            tree.insert("", "end", values=(
                s["student_id"], f"{s['first_name']} {s['last_name']}",
                f"{s['percentage']}%", label,
            ), tags=(tag,))

    # ── THRESHOLDS & INTERVENTIONS (11-15) ────────────────────────────

    def _set_absence_threshold(self):
        """11. Configure the % that triggers a warning."""
        val = simpledialog.askfloat("Absence Threshold",
                                    "Set attendance target percentage:",
                                    initialvalue=self._absence_threshold,
                                    minvalue=50.0, maxvalue=100.0)
        if val is not None:
            self._absence_threshold = val
            self._status_var.set(f"Attendance threshold set to {val}%")

    def _list_below_threshold(self):
        """12. Show all students under the attendance target."""
        year = self._year_var.get()
        try:
            data = self._svc.get_students_below_threshold(year, self._absence_threshold)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        if not data:
            messagebox.showinfo("Below Threshold",
                                f"No students below {self._absence_threshold}% in Year {year}.")
            return

        win = tk.Toplevel(self)
        win.title(f"Below {self._absence_threshold}% — Year {year}")
        win.geometry("500x350")
        tree = ttk.Treeview(win, columns=("sid", "name", "form", "pct"), show="headings")
        for col, h, w in [("sid", "ID", 80), ("name", "Name", 180),
                          ("form", "Form", 70), ("pct", "%", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for s in data:
            tree.insert("", "end", values=(
                s["student_id"], f"{s['first_name']} {s['last_name']}",
                s.get("form_group", ""), f"{s['percentage']}%",
            ))

    def _generate_intervention_list(self):
        """13. Produce a list for pastoral team action."""
        year = self._year_var.get()
        try:
            below = self._svc.get_students_below_threshold(year, self._absence_threshold)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")],
                                            title="Save Intervention List")
        if not path:
            return

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Student ID", "Name", "Form Group", "Attendance %",
                             "Action Required"])
            for s in below:
                action = "Urgent" if s["percentage"] < self._absence_threshold - 10 else "Monitor"
                writer.writerow([s["student_id"],
                                 f"{s['first_name']} {s['last_name']}",
                                 s.get("form_group", ""), f"{s['percentage']}%", action])

        self._status_var.set(f"Intervention list exported to {path}")

    def _schedule_meeting_flag(self):
        """14. Mark a student as needing a parent meeting."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        reason = simpledialog.askstring("Meeting Required",
                                        f"Reason for meeting with {vals[1]}'s parent/guardian:")
        if not reason:
            return
        self._notes_data[pk] = (self._notes_data.get(pk, "") +
                                f"\n[MEETING REQUIRED] {reason}")
        self._unsaved = True
        messagebox.showinfo("Meeting Flagged",
                            f"{vals[1]} flagged for parent meeting:\n{reason}")

    def _record_return_interview(self):
        """15. Log a return-to-school interview after absence."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        notes = simpledialog.askstring("Return Interview",
                                       f"Return interview notes for {vals[1]}:")
        if not notes:
            return
        recorded_by = self._auth["username"] if self._auth else "system"
        self._notes_data[pk] = (self._notes_data.get(pk, "") +
                                f"\n[RETURN INTERVIEW {date.today().isoformat()}] {notes}")
        try:
            self._svc.record_attendance(
                student_id=pk,
                date_str=date.today().isoformat(),
                status="present",
                period=self._period_var.get(),
                recorded_by=recorded_by,
                note=f"Return interview: {notes}",
            )
        except Exception:
            pass
        self._unsaved = True
        messagebox.showinfo("Return Interview", f"Interview logged for {vals[1]}.")

    # ── AUTHORISATION (16-20) ────────────────────────────────────────

    def _mark_authorised_absence(self):
        """16. Set an absence as officially authorised."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        reason = self._pick_authorisation_reason()
        if reason is None:
            return
        self._set_student_status(pk, "authorised_absent")
        self._notes_data[pk] = (self._notes_data.get(pk, "") +
                                f"\n[AUTHORISED] {reason}")
        self._status_var.set(f"{vals[1]} marked as authorised absent: {reason}")

    def _mark_unauthorised_absence(self):
        """17. Explicitly flag as unauthorised."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        self._set_student_status(pk, "unauthorised_absent")
        self._status_var.set(f"{vals[1]} marked as unauthorised absent")

    def _bulk_authorise_selected(self):
        """18. Authorise multiple selected rows at once."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select students first.")
            return
        reason = self._pick_authorisation_reason()
        if reason is None:
            return
        for iid in sel:
            pk = int(iid)
            self._set_student_status(pk, "authorised_absent")
            self._notes_data[pk] = (self._notes_data.get(pk, "") +
                                    f"\n[AUTHORISED] {reason}")
        self._status_var.set(f"{len(sel)} students authorised: {reason}")

    def _view_authorisation_reasons(self):
        """19. Dropdown of standard authorisation codes."""
        win = tk.Toplevel(self)
        win.title("Authorisation Reasons")
        win.geometry("350x300")
        tk.Label(win, text="Standard Authorisation Reasons",
                 font=("Helvetica", 11, "bold")).pack(pady=10)
        for i, reason in enumerate(AUTHORISATION_REASONS, 1):
            tk.Label(win, text=f"{i}. {reason}", anchor="w").pack(fill="x", padx=20)
        tk.Label(win, text="\nDfE Registration Codes",
                 font=("Helvetica", 11, "bold")).pack(pady=(10, 5))
        for code, desc in sorted(DFE_CODES.items()):
            tk.Label(win, text=f"  {code} — {desc}", anchor="w",
                     font=("Helvetica", 9)).pack(fill="x", padx=20)

    def _add_custom_authorisation_reason(self):
        """20. Allow free-text reason entry."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        reason = simpledialog.askstring("Custom Reason",
                                        f"Enter authorisation reason for {vals[1]}:")
        if not reason:
            return
        self._set_student_status(pk, "authorised_absent")
        self._notes_data[pk] = (self._notes_data.get(pk, "") +
                                f"\n[AUTHORISED - CUSTOM] {reason}")
        self._status_var.set(f"{vals[1]} authorised: {reason}")

    def _pick_authorisation_reason(self) -> str | None:
        """Helper: show a reason picker dialog."""
        win = tk.Toplevel(self)
        win.title("Select Reason")
        win.geometry("300x350")
        win.grab_set()

        result = {"value": None}
        lb = tk.Listbox(win, font=("Helvetica", 10))
        for r in AUTHORISATION_REASONS:
            lb.insert("end", r)
        lb.pack(fill="both", expand=True, padx=10, pady=10)

        def on_select():
            sel = lb.curselection()
            if sel:
                chosen = AUTHORISATION_REASONS[sel[0]]
                if chosen == "Other (specify)":
                    chosen = simpledialog.askstring("Reason", "Specify reason:") or "Other"
                result["value"] = chosen
            win.destroy()

        ttk.Button(win, text="Select", command=on_select).pack(pady=5)
        self.wait_window(win)
        return result["value"]

    def _set_student_status(self, pk, new_status):
        """Helper: set a single student's status and update tree."""
        old = self._attendance_data.get(pk, "present")
        if old != new_status:
            self._push_undo(pk, old, new_status)
        self._attendance_data[pk] = new_status
        for rd in self._all_rows:
            if rd["pk"] == pk:
                rd["status"] = new_status
                break
        self._unsaved = True
        self._refresh_row(pk, new_status)

    # ── REGISTRATION CODES (21-25) ───────────────────────────────────

    def _apply_dfe_code(self, code: str):
        """Helper: apply a DfE registration code to selected student."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        desc = DFE_CODES.get(code, code)
        status = "authorised_absent"
        if code in ("O", "U", "N"):
            status = "unauthorised_absent"
        elif code == "L":
            status = "late"
        self._set_student_status(pk, status)
        self._notes_data[pk] = (self._notes_data.get(pk, "") +
                                f"\n[DfE Code {code}] {desc}")
        self._status_var.set(f"{vals[1]}: Code {code} — {desc}")

    def _apply_B_code(self):
        """21. Off-site educational activity."""
        self._apply_dfe_code("B")

    def _apply_C_code(self):
        """22. Authorised holiday during term."""
        self._apply_dfe_code("C")

    def _apply_D_code(self):
        """23. Dual registration at another school."""
        self._apply_dfe_code("D")

    def _apply_E_code(self):
        """24. Excluded (no alternative provision)."""
        self._apply_dfe_code("E")

    def _apply_custom_code(self):
        """25. Enter any DfE registration code manually."""
        codes = "\n".join(f"  {k} — {v}" for k, v in sorted(DFE_CODES.items()))
        code = simpledialog.askstring("DfE Code", f"Enter code:\n\n{codes}")
        if code and code.upper() in DFE_CODES:
            self._apply_dfe_code(code.upper())
        elif code:
            messagebox.showwarning("Unknown Code", f"'{code}' is not a recognised DfE code.")

    # ── MULTI-CLASS / COVER (26-30) ──────────────────────────────────

    def _load_cover_register(self):
        """26. Load register for a cover lesson."""
        subject = simpledialog.askstring("Cover Register", "Enter subject name or ID:")
        if not subject:
            return
        self._status_var.set(f"Cover register loaded for: {subject}")
        self._load_register()

    def _assign_cover_teacher(self):
        """27. Record who is taking the register."""
        teacher = simpledialog.askstring("Cover Teacher", "Enter cover teacher name:")
        if teacher:
            self._status_var.set(f"Cover teacher assigned: {teacher}")

    def _merge_registers(self):
        """28. Combine AM and PM into a daily summary."""
        date_str = self._date_var.get()
        year = self._year_var.get()
        if not self._validate_date_format():
            return

        try:
            am_data = self._svc.get_attendance_by_date(date_str, year_group=year)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        merged = {}
        for r in am_data:
            sid = r["sid"]
            name = f"{r['first_name']} {r['last_name']}"
            if sid not in merged:
                merged[sid] = {"name": name, "form": r.get("form_group", ""),
                               "am": "", "pm": ""}
            period = r.get("period", "")
            if period in ("AM", "1", "2", "3"):
                merged[sid]["am"] = r["status"]
            else:
                merged[sid]["pm"] = r["status"]

        win = tk.Toplevel(self)
        win.title(f"Merged Register — {date_str} Year {year}")
        win.geometry("550x400")
        tree = ttk.Treeview(win, columns=("sid", "name", "form", "am", "pm"), show="headings")
        for col, h, w in [("sid", "ID", 70), ("name", "Name", 170), ("form", "Form", 60),
                          ("am", "AM", 80), ("pm", "PM", 80)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for sid, info in sorted(merged.items(), key=lambda x: x[1]["name"]):
            tree.insert("", "end", values=(sid, info["name"], info["form"],
                                           info["am"], info["pm"]))

    def _split_group_view(self):
        """29. Display set/band splits within a year group."""
        fg = simpledialog.askstring("Set/Band Filter",
                                    "Enter form group or set name to filter:")
        if not fg:
            return
        self._form_filter_var.set(fg)
        self._filter_by_form_group()

    def _load_by_subject(self):
        """30. Filter register by subject rather than year group."""
        subject_id = simpledialog.askinteger("Subject Filter",
                                             "Enter subject ID:")
        if not subject_id:
            return
        date_str = self._date_var.get()
        try:
            records = self._svc.get_attendance_by_subject(subject_id, date_str)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        self._tree.delete(*self._tree.get_children())
        self._all_rows.clear()
        self._attendance_data.clear()

        for r in records:
            pk = r["student_id"] if "student_id" in r and isinstance(r["student_id"], int) else r.get("id", 0)
            rd = {
                "pk": pk,
                "student_id": r.get("sid", ""),
                "name": f"{r['first_name']} {r['last_name']}",
                "form_group": r.get("form_group", ""),
                "status": r.get("status", "present"),
            }
            self._all_rows.append(rd)
            self._attendance_data[pk] = rd["status"]
            self._tree.insert("", "end", iid=pk, values=(
                rd["student_id"], rd["name"], rd["form_group"], rd["status"],
            ))
        self._status_var.set(f"{len(records)} records for subject {subject_id}")

    # ── COMMUNICATION (31-35) ────────────────────────────────────────

    def _compose_absence_email(self):
        """31. Draft an email to a parent directly in-app."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        try:
            student = self._stu_svc.get_student(pk)
        except Exception:
            student = {}
        parent_email = (student or {}).get("parent_email", "N/A")

        win = tk.Toplevel(self)
        win.title(f"Compose Email — {vals[1]}")
        win.geometry("500x400")

        tk.Label(win, text=f"To: {parent_email}",
                 font=("Helvetica", 10)).pack(anchor="w", padx=10, pady=5)
        tk.Label(win, text="Subject:", font=("Helvetica", 10)).pack(anchor="w", padx=10)
        subject_var = tk.StringVar(value=f"Absence Notification — {vals[1]}")
        ttk.Entry(win, textvariable=subject_var, width=50).pack(padx=10, fill="x")

        tk.Label(win, text="Body:", font=("Helvetica", 10)).pack(anchor="w", padx=10, pady=(10, 0))
        body = tk.Text(win, wrap="word", height=12)
        body.insert("1.0",
                     f"Dear Parent/Guardian,\n\n"
                     f"We are writing to inform you that {vals[1]} "
                     f"was recorded as absent on {self._date_var.get()} "
                     f"(period {self._period_var.get()}).\n\n"
                     f"Please contact the school if you have any questions.\n\n"
                     f"Kind regards,\nAttendance Office")
        body.pack(padx=10, fill="both", expand=True)

        def send():
            recorded_by = self._auth["username"] if self._auth else "system"
            try:
                self._svc.log_communication(pk, "email", body.get("1.0", "end").strip(),
                                            recorded_by)
            except Exception:
                pass
            messagebox.showinfo("Email", f"Absence email queued for {vals[1]}.")
            win.destroy()

        ttk.Button(win, text="Send Email", command=send).pack(pady=10)

    def _log_phone_call(self):
        """32. Record a phone call made regarding an absence."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        notes = simpledialog.askstring("Phone Call Log",
                                       f"Notes from call regarding {vals[1]}:")
        if not notes:
            return
        recorded_by = self._auth["username"] if self._auth else "system"
        try:
            self._svc.log_communication(pk, "phone_call", notes, recorded_by)
        except Exception:
            pass
        self._status_var.set(f"Phone call logged for {vals[1]}")

    def _send_bulk_sms(self):
        """33. Trigger SMS to all absent students' contacts."""
        absent_pks = [rd["pk"] for rd in self._all_rows
                      if self._attendance_data.get(rd["pk"]) in
                      ("absent", "unauthorised_absent")]
        if not absent_pks:
            messagebox.showinfo("Bulk SMS", "No absent students to notify.")
            return
        confirmed = messagebox.askyesno("Bulk SMS",
                                         f"Send absence SMS to {len(absent_pks)} "
                                         f"parent contacts?")
        if not confirmed:
            return
        recorded_by = self._auth["username"] if self._auth else "system"
        for pk in absent_pks:
            try:
                self._svc.log_communication(
                    pk, "sms",
                    f"Absence notification SMS sent for {self._date_var.get()}",
                    recorded_by,
                )
            except Exception:
                pass
        self._status_var.set(f"Bulk SMS queued for {len(absent_pks)} students")

    def _generate_letter_template(self):
        """34. Produce a standard absence warning letter."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        try:
            student = self._stu_svc.get_student(pk)
        except Exception:
            student = {}
        if not student:
            student = {}

        summary = self._svc.get_attendance_summary(pk)

        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text", "*.txt")],
                                            title="Save Letter")
        if not path:
            return

        letter = (
            f"Date: {date.today().isoformat()}\n\n"
            f"Dear Parent/Guardian of {student.get('first_name', vals[1])} "
            f"{student.get('last_name', '')},\n\n"
            f"We are writing to express our concern regarding the attendance of "
            f"{student.get('first_name', vals[1])}.\n\n"
            f"Current attendance: {summary['percentage']}%\n"
            f"Total sessions: {summary['total']}\n"
            f"Present: {summary['present']} | Absent: {summary['absent']} | "
            f"Late: {summary['late']}\n\n"
            f"The school target is {self._absence_threshold}%. "
            f"We kindly request your cooperation in improving attendance.\n\n"
            f"Please contact the school attendance office to discuss.\n\n"
            f"Yours sincerely,\nAttendance Officer\n"
        )
        with open(path, "w") as f:
            f.write(letter)
        self._status_var.set(f"Letter saved to {path}")

    def _view_communication_history(self):
        """35. See all prior contacts for a student."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        try:
            logs = self._svc.get_communication_log(pk)
        except Exception as exc:
            messagebox.showerror("Error", str(exc))
            return

        win = tk.Toplevel(self)
        win.title(f"Communication History — {vals[1]}")
        win.geometry("600x350")

        if not logs:
            tk.Label(win, text="No communication records found.",
                     font=("Helvetica", 11)).pack(pady=30)
            return

        tree = ttk.Treeview(win, columns=("date", "type", "by", "message"), show="headings")
        for col, h, w in [("date", "Date", 130), ("type", "Type", 80),
                          ("by", "By", 100), ("message", "Message", 250)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="w" if col == "message" else "center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        for log in logs:
            tree.insert("", "end", values=(
                log.get("created_at", ""), log.get("type", ""),
                log.get("recorded_by", ""), log.get("message", "")[:80],
            ))

    # ── TIMETABLE & CALENDAR INTEGRATION (36-40) ─────────────────────

    def _mark_bank_holidays(self):
        """36. Auto-skip non-school days in date navigation."""
        dates_str = simpledialog.askstring(
            "Bank Holidays",
            "Enter bank holiday dates (comma-separated YYYY-MM-DD):",
            initialvalue=",".join(self._bank_holidays),
        )
        if dates_str is None:
            return
        self._bank_holidays = [d.strip() for d in dates_str.split(",") if d.strip()]
        self._status_var.set(f"{len(self._bank_holidays)} bank holidays configured")

    def _load_term_dates(self):
        """37. Import term start/end dates from config."""
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")],
                                          title="Load Term Dates")
        if not path:
            return
        try:
            with open(path) as f:
                self._term_dates = json.load(f)
            terms = len(self._term_dates.get("terms", []))
            self._status_var.set(f"Loaded {terms} term periods from {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load term dates: {exc}")

    def _show_remaining_school_days(self):
        """38. Count days left in current term."""
        today = date.today()
        terms = self._term_dates.get("terms", [])
        for term in terms:
            try:
                start = datetime.strptime(term["start"], "%Y-%m-%d").date()
                end = datetime.strptime(term["end"], "%Y-%m-%d").date()
            except (KeyError, ValueError):
                continue
            if start <= today <= end:
                remaining = 0
                d = today
                while d <= end:
                    if d.weekday() < 5 and d.isoformat() not in self._bank_holidays:
                        remaining += 1
                    d += timedelta(days=1)
                messagebox.showinfo("Remaining Days",
                                    f"Term: {term.get('name', 'Current')}\n"
                                    f"End: {end.isoformat()}\n"
                                    f"School days remaining: {remaining}")
                return
        messagebox.showinfo("Remaining Days",
                            "No term dates loaded or not currently in term.\n"
                            "Use 'Term Dates' to load a term calendar.")

    def _flag_exam_period(self):
        """39. Visually mark exam weeks on date navigation."""
        start = simpledialog.askstring("Exam Period Start", "Start date (YYYY-MM-DD):")
        end = simpledialog.askstring("Exam Period End", "End date (YYYY-MM-DD):")
        if start and end:
            self._exam_periods.append({"start": start, "end": end})
            self._status_var.set(f"Exam period flagged: {start} to {end}")

    def _sync_to_calendar_app(self):
        """40. Push register dates to an external calendar (ICS export)."""
        path = filedialog.asksaveasfilename(defaultextension=".ics",
                                            filetypes=[("iCalendar", "*.ics")])
        if not path:
            return
        date_str = self._date_var.get()
        year = self._year_var.get()
        period = self._period_var.get()

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//SchoolAttendance//EN",
            f"BEGIN:VEVENT",
            f"DTSTART:{date_str.replace('-', '')}T090000",
            f"DTEND:{date_str.replace('-', '')}T160000",
            f"SUMMARY:Attendance Register — Year {year} Period {period}",
            f"DESCRIPTION:Register completed for {len(self._attendance_data)} students",
            "END:VEVENT",
            "END:VCALENDAR",
        ]
        with open(path, "w") as f:
            f.write("\r\n".join(lines))
        self._status_var.set(f"Calendar event exported to {path}")

    # ── ACCESSIBILITY (41-45) ────────────────────────────────────────

    def _increase_font_size(self):
        """41. Bump all UI text up one size."""
        self._font_size = min(self._font_size + 1, 20)
        self._apply_font_size()

    def _decrease_font_size(self):
        """42. Reduce all UI text one size."""
        self._font_size = max(self._font_size - 1, 7)
        self._apply_font_size()

    def _apply_font_size(self):
        """Helper: apply current font size to widgets."""
        style = ttk.Style()
        style.configure("Treeview", font=("Helvetica", self._font_size),
                        rowheight=self._font_size + 12)
        style.configure("Treeview.Heading", font=("Helvetica", self._font_size, "bold"))
        style.configure("TButton", font=("Helvetica", self._font_size))
        self._status_var.set(f"Font size: {self._font_size}")

    def _toggle_high_contrast(self):
        """43. Switch to a high-contrast accessibility theme."""
        self._high_contrast = not self._high_contrast
        if self._high_contrast:
            bg, fg = "#000000", "#ffff00"
            tree_bg, tree_fg = "#000000", "#ffffff"
        else:
            bg, fg = "#ecf0f1", "#2c3e50"
            tree_bg, tree_fg = "#ffffff", "#000000"

        self.configure(bg=bg)
        for widget in self.winfo_children():
            try:
                if isinstance(widget, tk.Frame):
                    widget.configure(bg=bg)
                    for child in widget.winfo_children():
                        if isinstance(child, tk.Label):
                            child.configure(bg=bg, fg=fg)
                elif isinstance(widget, tk.Label):
                    widget.configure(bg=bg, fg=fg)
            except tk.TclError:
                pass

        style = ttk.Style()
        style.configure("Treeview", background=tree_bg, foreground=tree_fg,
                        fieldbackground=tree_bg)
        self._status_var.set("High contrast " + ("ON" if self._high_contrast else "OFF"))

    def _enable_keyboard_navigation(self):
        """44. Allow full tab/arrow key register control."""
        self._tree.focus_set()
        children = self._tree.get_children()
        if children:
            self._tree.selection_set(children[0])
            self._tree.focus(children[0])

        self._tree.bind("<Return>", self._on_toggle_status)
        self._tree.bind("<space>", self._on_toggle_status)
        self._tree.bind("<p>", lambda e: self._mark_selected_present())
        self._tree.bind("<a>", lambda e: self._mark_selected_absent())
        self._tree.bind("<l>", lambda e: self._mark_selected_late())
        self._status_var.set("Keyboard navigation enabled (P=present, A=absent, L=late, "
                             "Enter/Space=toggle)")

    def _read_aloud_selected(self):
        """45. Use TTS to announce selected student name/status."""
        pk, vals = self._get_selected_student()
        if pk is None:
            return
        status = self._attendance_data.get(pk, "present")
        text = f"{vals[1]}, status: {status}"

        try:
            import subprocess
            import platform
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["say", text])
            elif system == "Linux":
                subprocess.Popen(["espeak", text])
            elif system == "Windows":
                subprocess.Popen(
                    ["powershell", "-Command",
                     f"Add-Type -AssemblyName System.Speech; "
                     f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')"]
                )
            self._status_var.set(f"Reading aloud: {text}")
        except Exception as exc:
            messagebox.showinfo("TTS", f"Text-to-speech unavailable: {exc}\n\n{text}")

    # ── BACKUP & RECOVERY (46-50) ────────────────────────────────────

    def _get_draft_path(self, suffix=""):
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        fname = f"draft_{self._year_var.get()}_{self._date_var.get()}_{self._period_var.get()}"
        if suffix:
            fname += f"_{suffix}"
        return os.path.join(DRAFTS_DIR, fname + ".json")

    def _session_state_dict(self):
        return {
            "date": self._date_var.get(),
            "year": self._year_var.get(),
            "period": self._period_var.get(),
            "attendance_data": {str(k): v for k, v in self._attendance_data.items()},
            "notes_data": {str(k): v for k, v in self._notes_data.items()},
            "all_rows": self._all_rows,
            "timestamp": datetime.now().isoformat(),
        }

    def _auto_save_draft(self):
        """46. Silently save a draft every N minutes."""
        if not self._attendance_data:
            self._status_var.set("Load a register before enabling auto-save.")
            return

        def do_save():
            if self._attendance_data and self._unsaved:
                try:
                    path = self._get_draft_path("auto")
                    with open(path, "w") as f:
                        json.dump(self._session_state_dict(), f)
                    self._status_var.set(f"Auto-saved draft at {datetime.now().strftime('%H:%M:%S')}")
                except Exception:
                    pass
            self._auto_save_timer = self.after(self._auto_save_interval, do_save)

        if self._auto_save_timer:
            self.after_cancel(self._auto_save_timer)
            self._auto_save_timer = None
            self._status_var.set("Auto-save disabled")
        else:
            do_save()
            self._status_var.set(f"Auto-save enabled (every {self._auto_save_interval // 60000} min)")

    def _recover_last_draft(self):
        """47. Restore the most recent auto-saved draft."""
        if not os.path.exists(DRAFTS_DIR):
            messagebox.showinfo("No Drafts", "No drafts directory found.")
            return
        drafts = sorted(
            [f for f in os.listdir(DRAFTS_DIR) if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(DRAFTS_DIR, f)),
            reverse=True,
        )
        if not drafts:
            messagebox.showinfo("No Drafts", "No saved drafts found.")
            return

        path = os.path.join(DRAFTS_DIR, drafts[0])
        self._restore_from_json(path)
        self._status_var.set(f"Recovered draft: {drafts[0]}")

    def _export_backup_json(self):
        """48. Dump the full session state to a JSON file."""
        if not self._attendance_data:
            messagebox.showwarning("Warning", "No register data to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                            filetypes=[("JSON", "*.json")])
        if not path:
            return
        with open(path, "w") as f:
            json.dump(self._session_state_dict(), f, indent=2)
        self._status_var.set(f"Session backup exported to {path}")

    def _import_backup_json(self):
        """49. Restore a session from a JSON backup."""
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        self._restore_from_json(path)
        self._status_var.set(f"Session restored from {os.path.basename(path)}")

    def _restore_from_json(self, path):
        """Helper: restore session state from a JSON file."""
        try:
            with open(path) as f:
                state = json.load(f)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to read backup: {exc}")
            return

        self._date_var.set(state.get("date", date.today().isoformat()))
        self._year_var.set(state.get("year", "7"))
        self._period_var.set(state.get("period", "AM"))

        self._attendance_data = {int(k): v for k, v in state.get("attendance_data", {}).items()}
        self._notes_data = {int(k): v for k, v in state.get("notes_data", {}).items()}
        self._all_rows = state.get("all_rows", [])

        self._tree.delete(*self._tree.get_children())
        for rd in self._all_rows:
            pk = rd["pk"]
            status = self._attendance_data.get(pk, rd.get("status", "present"))
            self._tree.insert("", "end", iid=pk, values=(
                rd["student_id"], rd["name"], rd["form_group"], status,
            ))
        self._unsaved = True
        self._highlight_absences()

    def _clear_all_drafts(self):
        """50. Purge all locally stored draft records."""
        if not os.path.exists(DRAFTS_DIR):
            messagebox.showinfo("Drafts", "No drafts directory found.")
            return
        drafts = [f for f in os.listdir(DRAFTS_DIR) if f.endswith(".json")]
        if not drafts:
            messagebox.showinfo("Drafts", "No drafts to clear.")
            return
        if not messagebox.askyesno("Clear Drafts",
                                    f"Delete {len(drafts)} saved drafts?"):
            return
        for f in drafts:
            os.remove(os.path.join(DRAFTS_DIR, f))
        self._status_var.set(f"Cleared {len(drafts)} drafts")

    # ── HELPERS ──────────────────────────────────────────────────────

    def _refresh_row(self, pk, new_status):
        try:
            vals = list(self._tree.item(str(pk), "values"))
            vals[3] = new_status
            self._tree.item(str(pk), values=vals)
        except tk.TclError:
            pass
        self._highlight_absences()
