"""Deferred Exam Requests tab — surfaces absence requests that landed on a
scheduled exam date so coordinators can resolve them in one place.

Rows come from ``absence_requests`` where ``is_missed_exam = 1``. The flag
is set automatically by the attendance GUI's ``_sync_to_absence_db`` helper
when a recorded Absent matches an entry in the ``exams`` table.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from contextlib import closing
import json
import logging
import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import ttk, messagebox, simpledialog

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
    HAS_DB = True
except ImportError:
    HAS_DB = False

from education_system.systems.university.domains.academics.interfaces.gui.exam_management.tabs import (
    _intel_tools as _tools,
)
from education_system.systems.university.domains.academics.interfaces.gui.exam_management import conflicts as conflict_utils
from education_system.systems.university.domains.academics.interfaces.gui.exam_management import accommodations as accommodations_service

logger = logging.getLogger(__name__)

DEFAULT_RESIT_OFFSET_DAYS = 28


class DeferredExamTabMixin:

    def create_deferred_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=_t('gui.academics.exam_management.tabs.deferred_tab.tabs.deferred_exam_requests', default="Deferred Exam Requests"))

        header = ttk.Frame(tab)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text=_t('gui.academics.exam_management.tabs.deferred_tab.labels.absence_requests_on_exam_dates', default="Absence requests on exam dates"),
                  style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text=_t('gui.academics.exam_management.tabs.deferred_tab.buttons.refresh', default="Refresh"),
                   command=self.refresh_deferred_list).pack(side=tk.RIGHT, padx=4)
        ttk.Button(header, text=_t('gui.academics.exam_management.tabs.deferred_tab.buttons.approve_schedule_resit', default="Approve (schedule resit…)"),
                   command=lambda: self._decide_deferred("approved")).pack(
                       side=tk.RIGHT, padx=4)
        ttk.Button(header, text=_t('gui.academics.exam_management.tabs.deferred_tab.buttons.reject', default="Reject"),
                   command=lambda: self._decide_deferred("rejected")).pack(
                       side=tk.RIGHT, padx=4)

        # Search / status / history row. The list mixes pending requests with
        # everything already decided, and only the pending ones need action —
        # so the default view is now Pending, with the rest a filter away.
        tools = ttk.Frame(tab)
        tools.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.deferred_tab.labels.search',
            default="Search:")).pack(side=tk.LEFT)
        self.deferred_filter_var = tk.StringVar()
        self.deferred_filter_var.trace(
            "w", lambda *_a: self._apply_deferred_filter())
        ttk.Entry(tools, textvariable=self.deferred_filter_var,
                  width=28).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.deferred_tab.labels.status',
            default="Status:")).pack(side=tk.LEFT)
        self.deferred_status_var = tk.StringVar(value=self.STATUS_PENDING)
        status_combo = ttk.Combobox(
            tools, textvariable=self.deferred_status_var, width=14,
            state="readonly", values=list(self.STATUS_CHOICES))
        status_combo.pack(side=tk.LEFT, padx=(4, 12))
        status_combo.bind("<<ComboboxSelected>>",
                          lambda _e: self._apply_deferred_filter())

        ttk.Button(tools, text=_t(
            'gui.academics.exam_management.tabs.deferred_tab.buttons.export_csv',
            default="Export CSV"), command=self._export_deferred).pack(
            side=tk.RIGHT)
        ttk.Button(tools, text=_t(
            'gui.academics.exam_management.tabs.deferred_tab.buttons.student_history',
            default="Student history…"),
            command=self._show_student_history).pack(side=tk.RIGHT, padx=6)

        cols = ("rid", "student", "module", "date", "exam_id", "status", "reason")
        self.deferred_tree = ttk.Treeview(
            tab, columns=cols, show="headings", height=18)
        widths = {"rid": 50, "student": 130, "module": 100, "date": 100,
                  "exam_id": 70, "status": 90, "reason": 320}
        labels = {"rid": "Req#", "student": "Student", "module": "Module",
                  "date": "Date", "exam_id": "Exam#", "status": "Status",
                  "reason": "Reason"}
        for c in cols:
            self.deferred_tree.heading(c, text=labels[c])
            self.deferred_tree.column(c, width=widths[c], minwidth=40)
        self.deferred_tree.tag_configure("pending", background="#fff6e0")
        self.deferred_tree.pack(fill=tk.BOTH, expand=True)

        self._deferred_labels = labels
        _tools.enable_column_sort(self.deferred_tree, numeric=("rid", "exam_id"))
        # Double-click shows the full reason, which the column truncates and
        # which is the thing an approver actually has to read.
        _tools.bind_row_details(self.deferred_tree, self.root,
                                "Deferred exam request", labels)

        self.deferred_summary_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.deferred_summary_var,
                  foreground="#7f8c8d").pack(anchor=tk.W, pady=(6, 0))

        self._deferred_rows = []
        self.refresh_deferred_list()

    #: Status filter options; "Pending" is the default because it is the only
    #: state that needs a decision.
    STATUS_PENDING = "Pending"
    STATUS_ALL = "All"
    STATUS_CHOICES = ("Pending", "Approved", "Rejected", "All")

    def _apply_deferred_filter(self):
        """Re-populate the tree from the cached rows."""
        if not hasattr(self, "deferred_tree"):
            return
        for item in self.deferred_tree.get_children():
            self.deferred_tree.delete(item)

        needle = self.deferred_filter_var.get()
        wanted = self.deferred_status_var.get()
        shown = 0
        for values in self._deferred_rows:
            status = str(values[5] or "").strip().lower()
            if wanted != self.STATUS_ALL and status != wanted.lower():
                continue
            if not _tools.row_matches(values, needle):
                continue
            self.deferred_tree.insert(
                "", tk.END, values=values,
                tags=("pending",) if status == "pending" else ())
            shown += 1

        total = len(self._deferred_rows)
        pending = sum(1 for v in self._deferred_rows
                      if str(v[5] or "").strip().lower() == "pending")
        summary = (f"{shown} of {total} request(s) · {pending} awaiting a "
                   f"decision")
        if total and not shown:
            summary += "  — nothing matches the current filter"
        self.deferred_summary_var.set(summary)

    def _export_deferred(self):
        _tools.export_tree_to_csv(self.deferred_tree, self.root,
                                  "deferred_exam_requests",
                                  getattr(self, "_deferred_labels", {}))

    def _show_student_history(self):
        """Every deferral request by the selected row's student.

        A first deferral and a fifth deferral warrant different decisions, and
        that history was not visible anywhere in this tab.
        """
        selection = self.deferred_tree.selection()
        if not selection:
            messagebox.showinfo(
                _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.deferred_exams',
                   default="Deferred Exams"),
                "Select a request first.", parent=self.root)
            return
        values = self.deferred_tree.item(selection[0], "values")
        student = values[1]

        try:
            with closing(get_connection()) as conn:
                rows = conn.execute(
                    """SELECT r.date, r.module_code, r.status,
                              COALESCE(r.is_missed_exam, 0),
                              COALESCE(r.reason, '')
                       FROM absence_requests r
                       LEFT JOIN students s ON s.student_id = r.student_id
                       WHERE TRIM(COALESCE(s.first_name,'')||' '
                                  ||COALESCE(s.last_name,'')) = ?
                          OR r.student_id = ?
                       ORDER BY r.date DESC""", (student, student)).fetchall()
        except Exception as exc:
            messagebox.showerror(
                _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.deferred_exams',
                   default="Deferred Exams"),
                f"Could not load the student's history: {exc}",
                parent=self.root)
            return

        if not rows:
            messagebox.showinfo(
                _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.deferred_exams',
                   default="Deferred Exams"),
                f"No absence requests on file for {student}.",
                parent=self.root)
            return

        exam_misses = sum(1 for r in rows if r[3])
        lines = [f"{len(rows)} absence request(s), {exam_misses} on exam dates.",
                 ""]
        for dt, module, status, missed_exam, reason in rows:
            marker = "EXAM" if missed_exam else "    "
            lines.append(f"{dt}  {marker}  {module or '—':<10} {status or '—':<10} "
                         f"{reason.strip()[:60]}")
        _tools.show_text_dialog(self.root, f"Absence history — {student}",
                                "\n".join(lines))

    def refresh_deferred_list(self):
        if not hasattr(self, "deferred_tree"):
            return
        for item in self.deferred_tree.get_children():
            self.deferred_tree.delete(item)
        self._deferred_rows = []
        if not HAS_DB:
            return
        try:
            with closing(get_connection()) as conn:
                rows = conn.execute(
                    """SELECT r.id,
                              TRIM(COALESCE(s.first_name,'')||' '
                                   ||COALESCE(s.last_name,'')) AS name,
                              r.student_id,
                              r.module_code,
                              r.date,
                              COALESCE(r.exam_id,'') AS exam_id,
                              r.status,
                              COALESCE(r.reason,'')
                       FROM absence_requests r
                       LEFT JOIN students s ON s.student_id = r.student_id
                       WHERE r.is_missed_exam = 1
                       ORDER BY r.status = 'pending' DESC, r.date DESC,
                                r.id DESC""").fetchall()
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.exam_management.tabs.deferred_tab.dialogs.deferred_exams', default="Deferred Exams"),
                                 f"Failed to load: {exc}", parent=self.root)
            return
        for (rid, name, sid, mod, dt, exam_id, status, reason) in rows:
            display_student = (name or "").strip() or sid
            self._deferred_rows.append(
                (rid, display_student, mod, dt, exam_id, status, reason))
        self._apply_deferred_filter()

    def _decide_deferred(self, decision: str):
        sel = self.deferred_tree.selection()
        if not sel:
            messagebox.showinfo(_t('gui.academics.exam_management.tabs.deferred_tab.dialogs.deferred_exams', default="Deferred Exams"),
                                _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.select_a_request_first', default="Select a request first."), parent=self.root)
            return
        rid = int(self.deferred_tree.item(sel[0])["values"][0])
        if not HAS_DB:
            return
        if decision == "approved":
            # Run the resit step first; if the user cancels it, leave the
            # request in its existing (pending) state untouched.
            if not self._autocreate_resit(rid):
                return
        try:
            with closing(get_connection()) as conn:
                conn.execute(
                    """UPDATE absence_requests
                       SET status = ?,
                           decided_by = COALESCE(decided_by, 'exam_gui'),
                           decided_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (decision, rid))
                conn.commit()
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.exam_management.tabs.deferred_tab.dialogs.deferred_exams', default="Deferred Exams"),
                                 f"Update failed: {exc}", parent=self.root)
            return
        self.refresh_deferred_list()

    # -----------------------------------------------------------------
    # Resit auto-creation
    # -----------------------------------------------------------------
    def _autocreate_resit(self, request_id: int) -> bool:
        """When a missed-exam request is approved, either create a fresh
        resit exam row or attach the student to the existing resit for the
        same original exam.

        Returns True if approval should proceed (resit scheduled or attached,
        or user chose to skip resit creation), False if the user cancelled —
        in which case the caller should leave the request status unchanged.
        """
        if not HAS_DB:
            return True
        try:
            with closing(get_connection()) as conn:
                req = conn.execute(
                    """SELECT student_id, module_code, date, exam_id
                       FROM absence_requests WHERE id = ?""",
                    (request_id,)).fetchone()
                if not req:
                    return False
                student_id, module_code, _miss_date, exam_id = req
                if not exam_id:
                    messagebox.showwarning(
                        _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit', default="Resit"),
                        f"Request #{request_id} has no linked exam — "
                        "schedule the resit manually.",
                        parent=self.root)
                    return True

                original = conn.execute(
                    """SELECT module_code, module_name, date, start_time,
                              end_time, COALESCE(room,''), instructor_id,
                              instructor_name
                       FROM exams WHERE id = ?""", (exam_id,)).fetchone()
                if not original:
                    messagebox.showerror(
                        _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit', default="Resit"),
                        f"Original exam {exam_id} not found.",
                        parent=self.root)
                    return False
                (mod, mname, orig_date, st, et, room, instr_id, instr_name) = original

                # Pull this student's active accommodations from
                # student-support so the resit reflects extended-time and
                # other arrangements without manual data entry.
                acc = accommodations_service.get_active_accommodations(
                    student_id, exam_id=exam_id)
                resit_end = accommodations_service.compute_extended_end_time(
                    st, et, acc)
                acc_bullets = accommodations_service.summarize_accommodations(acc)

                existing = conn.execute(
                    """SELECT id, enrolled_student_ids, students_enrolled, date
                       FROM exams
                       WHERE parent_exam_id = ?
                       ORDER BY date DESC LIMIT 1""", (exam_id,)).fetchone()

                # If a resit already exists, ask: add to it / new sitting / cancel.
                if existing:
                    existing_id, raw_ids, current_n, resit_date = existing
                    ids = self._parse_ids(raw_ids)
                    if str(student_id) in ids:
                        messagebox.showinfo(
                            _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit', default="Resit"),
                            f"Student {student_id} is already on the resit "
                            f"for exam {exam_id} (scheduled {resit_date}).",
                            parent=self.root)
                        return True
                    choice = messagebox.askyesnocancel(
                        _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit_already_scheduled', default="Resit already scheduled"),
                        f"A resit for this exam is already scheduled on "
                        f"{resit_date} ({current_n or 0} student(s)).\n\n"
                        "Yes  → add this student to that sitting\n"
                        "No   → schedule a separate sitting\n"
                        "Cancel → abort approval",
                        parent=self.root)
                    if choice is None:
                        return False
                    if choice:  # Yes — attach
                        ids.append(str(student_id))
                        conn.execute(
                            """UPDATE exams
                               SET enrolled_student_ids = ?,
                                   students_enrolled = ?,
                                   updated_at = CURRENT_TIMESTAMP
                               WHERE id = ?""",
                            (json.dumps(ids), (current_n or 0) + 1, existing_id))
                        conn.commit()
                        # Carry the student's exam-specific accommodations
                        # across to the existing resit row.
                        accommodations_service.clone_exam_accommodation(
                            student_id, exam_id, existing_id)

                        msg = (f"Added student {student_id} to existing "
                               f"resit on {resit_date} (exam #{existing_id}).")
                        if acc_bullets:
                            msg += "\n\nAccommodations applied:\n  • " + \
                                "\n  • ".join(acc_bullets)
                        messagebox.showinfo(_t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit', default="Resit"), msg, parent=self.root)
                        self._refresh_exams_views()
                        return True
                    # No → fall through to schedule a separate sitting

                # Ask for a date, default to original + offset.
                try:
                    default_date = (datetime.strptime(orig_date, "%Y-%m-%d")
                                    + timedelta(days=DEFAULT_RESIT_OFFSET_DAYS)
                                    ).strftime("%Y-%m-%d")
                except ValueError:
                    default_date = (date.today()
                                    + timedelta(days=DEFAULT_RESIT_OFFSET_DAYS)
                                    ).isoformat()

                # Use the accommodation-extended end time when picking the
                # slot so conflict checks reflect the true finish time.
                resit_date = self._prompt_for_resit_date(
                    mod, st, resit_end, room, instr_id, default_date)
                if resit_date is None:
                    return False

                resit_name = (mname or mod)
                if "(Resit)" not in resit_name:
                    resit_name = f"{resit_name} (Resit)"
                cur = conn.execute(
                    """INSERT INTO exams
                       (module_code, module_name, date, start_time, end_time,
                        room, instructor_id, instructor_name,
                        students_enrolled, enrolled_student_ids,
                        parent_exam_id, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?,
                               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
                    (mod, resit_name, resit_date, st, resit_end, room,
                     instr_id, instr_name,
                     json.dumps([str(student_id)]), exam_id))
                conn.commit()
                new_id = cur.lastrowid

                # Carry the student's exam-specific arrangements to the
                # new resit (separate room, scribe, assistive tech, etc.).
                accommodations_service.clone_exam_accommodation(
                    student_id, exam_id, new_id)

                msg = (f"Resit scheduled: {mod} on {resit_date} "
                       f"{st}–{resit_end} in {room or '(no room)'} "
                       f"(exam #{new_id}).")
                if resit_end != et:
                    msg += f"\n\nEnd time extended from {et} to {resit_end} "
                    msg += "for student accommodations."
                if acc_bullets:
                    msg += "\n\nAccommodations applied:\n  • " + \
                        "\n  • ".join(acc_bullets)
                messagebox.showinfo(_t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit', default="Resit"), msg, parent=self.root)
                self._refresh_exams_views()
                return True
        except Exception as exc:
            logger.exception("resit auto-create failed rid=%s", request_id)
            messagebox.showerror(_t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit', default="Resit"), f"Auto-create failed: {exc}",
                                 parent=self.root)
            return False

    def _prompt_for_resit_date(self, mod, start_time, end_time, room,
                               instructor_id, default_date):
        """Prompt for a resit date, validate format, run conflict checks
        against the in-memory exam list, and re-prompt on conflict until
        the user accepts or cancels. Returns the date or None on cancel."""
        prompt = f"Resit date for {mod} (YYYY-MM-DD):"
        suggested = default_date
        while True:
            entered = simpledialog.askstring(
                _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.schedule_resit', default="Schedule resit"), prompt,
                initialvalue=suggested, parent=self.root)
            if entered is None:
                return None
            entered = entered.strip()
            try:
                datetime.strptime(entered, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror(
                    _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit', default="Resit"), f"Invalid date '{entered}'. "
                             "Use YYYY-MM-DD.", parent=self.root)
                suggested = entered or default_date
                continue

            warnings = self._collect_conflicts(
                entered, start_time, end_time, room, instructor_id)
            if not warnings:
                return entered

            choice = messagebox.askyesnocancel(
                _t('gui.academics.exam_management.tabs.deferred_tab.dialogs.resit_conflict', default="Resit conflict"),
                "The chosen slot conflicts with:\n\n  • "
                + "\n  • ".join(warnings)
                + "\n\nYes → schedule anyway\n"
                  "No  → pick a different date\n"
                  "Cancel → abort approval",
                parent=self.root)
            if choice is None:
                return None
            if choice:
                return entered
            suggested = entered

    def _collect_conflicts(self, dt, st, et, room, instructor_id):
        """Return human-readable conflict descriptions for the proposed slot."""
        warnings = []
        try:
            exams = list(getattr(self.data_manager, "exams", []) or [])
        except Exception:
            exams = []
        if room:
            for ex in conflict_utils.get_conflicting_exams(
                    exams, dt, st, et, room):
                warnings.append(
                    f"room {room} occupied by {ex.module_code} "
                    f"({ex.start_time}-{ex.end_time}) [exam #{ex.id}]")
        if instructor_id:
            for ex in conflict_utils.check_instructor_conflict(
                    exams, dt, st, et, instructor_id):
                warnings.append(
                    f"instructor already booked: {ex.module_code} "
                    f"({ex.start_time}-{ex.end_time}) [exam #{ex.id}]")
        return warnings

    @staticmethod
    def _parse_ids(raw):
        if not raw:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw]
        try:
            return [str(x) for x in json.loads(raw)]
        except (ValueError, json.JSONDecodeError):
            return []

    def _refresh_exams_views(self):
        """Reload the exam GUI's in-memory list so the new resit shows up
        immediately on the Manage Exams / Schedule tabs."""
        try:
            self.data_manager.load_data()
        except Exception:
            logger.exception("data_manager reload failed")
        for fn_name in ("refresh_exam_list", "refresh_schedule",
                        "refresh_calendar_view"):
            fn = getattr(self, fn_name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    logger.exception("%s failed", fn_name)
