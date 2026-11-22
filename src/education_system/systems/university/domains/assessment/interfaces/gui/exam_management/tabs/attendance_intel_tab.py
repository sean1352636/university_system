"""At-Risk audit + Exam Eligibility tabs.

Both tabs combine data the exam GUI already owns (the ``exams`` table and
its ``enrolled_student_ids``) with attendance signals from the attendance
and absence-tracking systems:

  • At-Risk Audit shows, per upcoming exam, enrolled students with high
    absence counts in the run-up window.
  • Exam Eligibility shows, per upcoming exam, each enrolled student's
    attendance percentage and a pass/fail badge against a configurable
    threshold (defaults to 75%).
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from contextlib import closing
import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime, timedelta

from education_system.systems.university.domains.assessment.interfaces.gui.exam_management.tabs import (
    _intel_tools as _tools,
)

try:
    from education_system.systems.university.infrastructure.database.db import get_connection
    HAS_DB = True
except ImportError:
    HAS_DB = False

ABSENCE_LOOKBACK_DAYS = 60
ELIGIBILITY_THRESHOLD = 75.0  # %


def _enrolled_ids(raw):
    """Exam.enrolled_student_ids may be a JSON string or a list."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x) for x in raw]
    try:
        return [str(x) for x in json.loads(raw)]
    except (ValueError, json.JSONDecodeError):
        return []


#: Which exams a tab considers. Both tabs used to be hard-wired to
#: "upcoming", which quietly emptied them the day the last exam passed — the
#: tab looked broken when it was simply out of scope. Auditing attendance
#: *after* an exam is legitimate ("who should not have sat this?"), so the
#: window is now a control.
SCOPE_UPCOMING = "Upcoming exams"
SCOPE_RECENT = "Past 90 days"
SCOPE_ALL = "All exams"
SCOPE_CHOICES = (SCOPE_UPCOMING, SCOPE_RECENT, SCOPE_ALL)

RECENT_WINDOW_DAYS = 90


def _absence_window(exam_date):
    """``(start, end)`` — the ABSENCE_LOOKBACK_DAYS running up to an exam.

    Falls back to a window ending today when the exam's date is unparseable,
    so a malformed row degrades to the old behaviour instead of raising.
    """
    try:
        end = datetime.strptime(str(exam_date)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        end = date.today()
    start = end - timedelta(days=ABSENCE_LOOKBACK_DAYS)
    return start.isoformat(), end.isoformat()


def _list_exams(conn, scope=SCOPE_UPCOMING, limit=200):
    """Exams within *scope*, oldest first."""
    today = date.today()
    if scope == SCOPE_ALL:
        where, params = "", []
    elif scope == SCOPE_RECENT:
        since = (today - timedelta(days=RECENT_WINDOW_DAYS)).isoformat()
        where, params = "WHERE date >= ?", [since]
    else:
        where, params = "WHERE date >= ?", [today.isoformat()]

    # db-audit: ignore[DBW001] - literal WHERE fragment chosen from a fixed set
    return conn.execute(
        f"""SELECT id, module_code, COALESCE(module_name, module_code), date,
                   start_time, COALESCE(room,''), enrolled_student_ids
            FROM exams
            {where}
            ORDER BY date, start_time
            LIMIT ?""", (*params, limit)).fetchall()


# ===========================================================================
# At-Risk Audit
# ===========================================================================

class AtRiskTabMixin:

    def create_at_risk_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=_t('gui.academics.exam_management.tabs.attendance_intel_tab.tabs.at_risk_audit', default="At-Risk Audit"))

        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            ctrl,
            text=f"Enrolled students with ≥ N absences in the "
                 f"{ABSENCE_LOOKBACK_DAYS} days before each exam.",
            style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(ctrl, text=_t('gui.academics.exam_management.tabs.attendance_intel_tab.labels.min_absences', default="Min absences:")).pack(side=tk.LEFT, padx=(20, 4))
        self.at_risk_threshold = tk.IntVar(value=3)
        ttk.Spinbox(ctrl, from_=1, to=30, width=4,
                    textvariable=self.at_risk_threshold,
                    command=self.refresh_at_risk_list).pack(side=tk.LEFT)
        ttk.Button(ctrl, text=_t('gui.academics.exam_management.tabs.attendance_intel_tab.buttons.refresh', default="Refresh"),
                   command=self.refresh_at_risk_list).pack(side=tk.RIGHT)

        # Search / export row. The tab could previously only be read top to
        # bottom: no way to find one student, narrow to one module, or take
        # the list anywhere.
        tools = ttk.Frame(tab)
        tools.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.labels.search',
            default="Search:")).pack(side=tk.LEFT)
        self.at_risk_filter_var = tk.StringVar()
        self.at_risk_filter_var.trace("w", lambda *_a: self._apply_at_risk_filter())
        ttk.Entry(tools, textvariable=self.at_risk_filter_var,
                  width=28).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.labels.module',
            default="Module:")).pack(side=tk.LEFT)
        self.at_risk_module_var = tk.StringVar(value=self.ALL_MODULES)
        self.at_risk_module_combo = ttk.Combobox(
            tools, textvariable=self.at_risk_module_var, width=18,
            state="readonly", values=[self.ALL_MODULES])
        self.at_risk_module_combo.pack(side=tk.LEFT, padx=(4, 12))
        self.at_risk_module_combo.bind(
            "<<ComboboxSelected>>", lambda _e: self._apply_at_risk_filter())

        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.labels.exams',
            default="Exams:")).pack(side=tk.LEFT)
        self.at_risk_scope_var = tk.StringVar(value=SCOPE_UPCOMING)
        at_risk_scope = ttk.Combobox(
            tools, textvariable=self.at_risk_scope_var, width=16,
            state="readonly", values=list(SCOPE_CHOICES))
        at_risk_scope.pack(side=tk.LEFT, padx=(4, 12))
        at_risk_scope.bind("<<ComboboxSelected>>",
                           lambda _e: self.refresh_at_risk_list())

        ttk.Button(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.buttons.export_csv',
            default="Export CSV"), command=self._export_at_risk).pack(side=tk.RIGHT)

        # Added "risk_feed" column so the persisted student_risk_assessment
        # output (what the Absence Tracker's Risk Feed writes) is visible
        # alongside this tab's own absence-count signal. Two views, one
        # decision: gate exam entry only when both signals agree.
        cols = ("date", "module", "student", "risk_feed",
                "absences", "lates", "last_absence")
        self.at_risk_tree = ttk.Treeview(
            tab, columns=cols, show="headings", height=18)
        labels = {"date": "Exam date", "module": "Module",
                  "student": "Student",
                  "risk_feed": "Risk (feed)",
                  "absences": "Absences", "lates": "Lates",
                  "last_absence": "Last absence"}
        widths = {"date": 100, "module": 100, "student": 200,
                  "risk_feed": 120,
                  "absences": 80, "lates": 70, "last_absence": 110}
        for c in cols:
            self.at_risk_tree.heading(c, text=labels[c])
            self.at_risk_tree.column(c, width=widths[c], minwidth=50)
        self.at_risk_tree.pack(fill=tk.BOTH, expand=True)

        self._at_risk_labels = labels
        # Sort by clicking a heading; absences/lates numerically, so 10 sorts
        # above 9 rather than between 1 and 2.
        _tools.enable_column_sort(self.at_risk_tree, numeric=("absences", "lates"))
        _tools.bind_row_details(self.at_risk_tree, self.root,
                                "At-risk student", labels)

        self.at_risk_summary_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.at_risk_summary_var,
                  foreground="#7f8c8d").pack(anchor=tk.W, pady=(6, 0))

        # Rows are held so filtering can re-populate without re-running the
        # N+1 attendance query.
        self._at_risk_rows = []

        # The N+1 attendance query lands after the tab paints.
        self.root.after_idle(self.refresh_at_risk_list)

    #: Sentinel for "don't filter by module".
    ALL_MODULES = "(all modules)"

    def _apply_at_risk_filter(self):
        """Re-populate the tree from the cached rows."""
        if not hasattr(self, "at_risk_tree"):
            return
        for item in self.at_risk_tree.get_children():
            self.at_risk_tree.delete(item)

        needle = self.at_risk_filter_var.get()
        module = self.at_risk_module_var.get()
        shown = 0
        for values in self._at_risk_rows:
            if module != self.ALL_MODULES and values[1] != module:
                continue
            if not _tools.row_matches(values, needle):
                continue
            self.at_risk_tree.insert("", tk.END, values=values)
            shown += 1

        total = len(self._at_risk_rows)
        students = len({v[2] for v in self._at_risk_rows})
        exams = len({(v[0], v[1]) for v in self._at_risk_rows})
        summary = (f"{shown} of {total} row(s) · {students} student(s) "
                   f"across {exams} exam(s)")
        if total and not shown:
            summary += "  — nothing matches the current filter"
        self.at_risk_summary_var.set(summary)

    def _export_at_risk(self):
        _tools.export_tree_to_csv(self.at_risk_tree, self.root,
                                  "at_risk_audit",
                                  getattr(self, "_at_risk_labels", {}))

    def refresh_at_risk_list(self):
        if not hasattr(self, "at_risk_tree"):
            return
        for item in self.at_risk_tree.get_children():
            self.at_risk_tree.delete(item)
        self._at_risk_rows = []
        if not HAS_DB:
            return
        threshold = max(1, int(self.at_risk_threshold.get() or 1))
        try:
            with closing(get_connection()) as conn:
                # Pull the most-recent risk feed row per student once,
                # up front, so we don't re-query for every exam-row in
                # the loop below.
                feed: dict[str, str] = {}
                try:
                    for sid, level, score in conn.execute(
                        """SELECT r.student_id, r.risk_level, r.risk_score
                           FROM student_risk_assessment r
                           WHERE r.id = (SELECT MAX(id)
                                         FROM student_risk_assessment
                                         WHERE student_id = r.student_id)"""
                    ):
                        if level is None:
                            continue
                        feed[str(sid)] = (
                            f"{level}"
                            + (f" ({score:.0f})" if score is not None
                               else "")
                        )
                except Exception:
                    # Table may not exist on a freshly-initialised DB.
                    feed = {}

                exams = _list_exams(conn, self.at_risk_scope_var.get())
                for (_eid, mod, mname, dt, _st, _rm, raw_ids) in exams:
                    sids = _enrolled_ids(raw_ids)
                    if not sids:
                        continue
                    # Window the absences on the run-up to *this exam*, not on
                    # the last 60 days of wall-clock time. Anchored on today,
                    # a past exam counted absences that happened after it was
                    # sat, and an exam more than 60 days out counted none.
                    window_start, window_end = _absence_window(dt)
                    placeholders = ",".join("?" * len(sids))
                    # attendance_records, not `attendance`: the latter has the
                    # same shape but is the abandoned copy and holds no rows,
                    # which is why this tab was always empty. The eligibility
                    # calculator already reads attendance_records.
                    # db-audit: ignore[DBW001] - join of placeholders
                    rows = conn.execute(
                        f"""SELECT a.student_id,
                                  TRIM(COALESCE(s.first_name,'')||' '
                                       ||COALESCE(s.last_name,'')) AS name,
                                  SUM(CASE WHEN LOWER(a.status)='absent' THEN 1 ELSE 0 END) AS abs_n,
                                  SUM(CASE WHEN LOWER(a.status)='late'   THEN 1 ELSE 0 END) AS late_n,
                                  MAX(a.date)
                           FROM attendance_records a
                           LEFT JOIN students s ON s.student_id = a.student_id
                           WHERE a.module_code = ?
                             AND a.date >= ?
                             AND a.date <= ?
                             AND a.student_id IN ({placeholders})
                           GROUP BY a.student_id
                           HAVING abs_n >= ?
                           ORDER BY abs_n DESC, late_n DESC""",
                        (mod, window_start, window_end, *sids,
                         threshold)).fetchall()
                    for (sid, name, abs_n, late_n, last) in rows:
                        display = (name or "").strip() or sid
                        risk = feed.get(str(sid), "—")
                        self._at_risk_rows.append(
                            (dt, mod, display, risk,
                             abs_n, late_n, last or ""))
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.exam_management.tabs.attendance_intel_tab.dialogs.at_risk_audit', default="At-Risk Audit"),
                                 f"Failed to load: {exc}", parent=self.root)
            return

        # Offer only the modules actually present, so the filter can never
        # select something with no rows behind it.
        modules = sorted({values[1] for values in self._at_risk_rows})
        try:
            self.at_risk_module_combo["values"] = [self.ALL_MODULES] + modules
            if self.at_risk_module_var.get() not in ([self.ALL_MODULES] + modules):
                self.at_risk_module_var.set(self.ALL_MODULES)
        except tk.TclError:
            pass
        self._apply_at_risk_filter()


# ===========================================================================
# Exam Eligibility
# ===========================================================================

class ExamEligibilityTabMixin:

    def create_eligibility_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text=_t('gui.academics.exam_management.tabs.attendance_intel_tab.tabs.exam_eligibility', default="Exam Eligibility"))

        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            ctrl,
            text=_t('gui.academics.exam_management.tabs.attendance_intel_tab.labels.per_student_attendance_on_each_upcoming_exam_s_module_below_thre', default="Per-student attendance % on each upcoming exam's module. "
                 "Below threshold = Not Eligible."),
            style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(ctrl, text=_t('gui.academics.exam_management.tabs.attendance_intel_tab.labels.threshold', default="Threshold %:")).pack(side=tk.LEFT, padx=(20, 4))
        self.eligibility_threshold = tk.DoubleVar(value=ELIGIBILITY_THRESHOLD)
        ttk.Spinbox(ctrl, from_=0, to=100, increment=5, width=5,
                    textvariable=self.eligibility_threshold,
                    command=self.refresh_eligibility_list).pack(side=tk.LEFT)
        ttk.Button(ctrl, text=_t('gui.academics.exam_management.tabs.attendance_intel_tab.buttons.refresh', default="Refresh"),
                   command=self.refresh_eligibility_list).pack(side=tk.RIGHT)

        # Search / show / export row. "Not eligible only" is the view that
        # actually gets acted on — those are the students someone has to
        # contact before the exam — and it was previously buried in a list of
        # everyone.
        tools = ttk.Frame(tab)
        tools.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.labels.search',
            default="Search:")).pack(side=tk.LEFT)
        self.eligibility_filter_var = tk.StringVar()
        self.eligibility_filter_var.trace(
            "w", lambda *_a: self._apply_eligibility_filter())
        ttk.Entry(tools, textvariable=self.eligibility_filter_var,
                  width=28).pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.labels.show',
            default="Show:")).pack(side=tk.LEFT)
        self.eligibility_show_var = tk.StringVar(value=self.SHOW_ALL)
        show_combo = ttk.Combobox(
            tools, textvariable=self.eligibility_show_var, width=18,
            state="readonly",
            values=[self.SHOW_ALL, self.SHOW_ELIGIBLE, self.SHOW_NOT_ELIGIBLE])
        show_combo.pack(side=tk.LEFT, padx=(4, 12))
        show_combo.bind("<<ComboboxSelected>>",
                        lambda _e: self._apply_eligibility_filter())

        ttk.Label(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.labels.exams',
            default="Exams:")).pack(side=tk.LEFT)
        self.eligibility_scope_var = tk.StringVar(value=SCOPE_UPCOMING)
        elig_scope = ttk.Combobox(
            tools, textvariable=self.eligibility_scope_var, width=16,
            state="readonly", values=list(SCOPE_CHOICES))
        elig_scope.pack(side=tk.LEFT, padx=(4, 12))
        elig_scope.bind("<<ComboboxSelected>>",
                        lambda _e: self.refresh_eligibility_list())

        ttk.Button(tools, text=_t(
            'gui.academics.exam_management.tabs.attendance_intel_tab.buttons.export_csv',
            default="Export CSV"), command=self._export_eligibility).pack(
            side=tk.RIGHT)

        cols = ("date", "module", "student", "present", "total", "pct", "verdict")
        self.eligibility_tree = ttk.Treeview(
            tab, columns=cols, show="headings", height=18)
        labels = {"date": "Exam date", "module": "Module",
                  "student": "Student", "present": "Present",
                  "total": "Sessions", "pct": "Attend %",
                  "verdict": "Verdict"}
        widths = {"date": 100, "module": 100, "student": 200,
                  "present": 80, "total": 80, "pct": 90, "verdict": 110}
        for c in cols:
            self.eligibility_tree.heading(c, text=labels[c])
            self.eligibility_tree.column(c, width=widths[c], minwidth=50)
        self.eligibility_tree.tag_configure("ok", background="#e9fce9")
        self.eligibility_tree.tag_configure("bad", background="#fde4e4")
        self.eligibility_tree.pack(fill=tk.BOTH, expand=True)

        self._eligibility_labels = labels
        _tools.enable_column_sort(self.eligibility_tree,
                                  numeric=("present", "total", "pct"))
        _tools.bind_row_details(self.eligibility_tree, self.root,
                                "Exam eligibility", labels)

        self.eligibility_summary_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.eligibility_summary_var,
                  foreground="#7f8c8d").pack(anchor=tk.W, pady=(6, 0))

        # Cached so filtering never re-runs compute_exam_eligibility(), which
        # is per-student *and* persists a row each time.
        self._eligibility_rows = []

        # Per-student compute_exam_eligibility() persists writes — push it
        # past the first paint so the tab opens before the work runs.
        self.root.after_idle(self.refresh_eligibility_list)

    #: Verdict filter options.
    SHOW_ALL = "All students"
    SHOW_ELIGIBLE = "Eligible only"
    SHOW_NOT_ELIGIBLE = "Not eligible only"

    def _apply_eligibility_filter(self):
        """Re-populate the tree from the cached rows."""
        if not hasattr(self, "eligibility_tree"):
            return
        for item in self.eligibility_tree.get_children():
            self.eligibility_tree.delete(item)

        needle = self.eligibility_filter_var.get()
        show = self.eligibility_show_var.get()
        shown = 0
        for values, tag, eligible in self._eligibility_rows:
            if show == self.SHOW_ELIGIBLE and not eligible:
                continue
            if show == self.SHOW_NOT_ELIGIBLE and eligible:
                continue
            if not _tools.row_matches(values, needle):
                continue
            self.eligibility_tree.insert("", tk.END, values=values,
                                         tags=(tag,))
            shown += 1

        total = len(self._eligibility_rows)
        blocked = sum(1 for _v, _t, ok in self._eligibility_rows if not ok)
        summary = (f"{shown} of {total} row(s) · {blocked} not eligible "
                   f"({(blocked / total * 100) if total else 0:.0f}%)")
        if total and not shown:
            summary += "  — nothing matches the current filter"
        self.eligibility_summary_var.set(summary)

    def _export_eligibility(self):
        _tools.export_tree_to_csv(self.eligibility_tree, self.root,
                                  "exam_eligibility",
                                  getattr(self, "_eligibility_labels", {}))

    def refresh_eligibility_list(self):
        if not hasattr(self, "eligibility_tree"):
            return
        for item in self.eligibility_tree.get_children():
            self.eligibility_tree.delete(item)
        self._eligibility_rows = []
        if not HAS_DB:
            return
        try:
            threshold = float(self.eligibility_threshold.get())
        except (TypeError, tk.TclError):
            threshold = ELIGIBILITY_THRESHOLD

        # Delegate the per-student calculation to the canonical
        # adapter so the verdict gets persisted into ``exam_eligibility``
        # — the Attendance and Absence GUIs read the same row.
        from education_system.systems.university.domains.assessment.interfaces.gui._attendance_eligibility import (
            compute_exam_eligibility,
        )

        try:
            with closing(get_connection()) as conn:
                exams = _list_exams(conn, self.eligibility_scope_var.get())
                # Pre-fetch student names once to avoid one SELECT per
                # row in the per-exam loop below.
                name_lookup: dict[str, str] = {}
                names = conn.execute(
                    "SELECT student_id, "
                    "       TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) "
                    "FROM students"
                ).fetchall()
                for sid, label in names:
                    name_lookup[sid] = (label or "").strip() or sid

            for (eid, mod, _mname, dt, _st, _rm, raw_ids) in exams:
                sids = _enrolled_ids(raw_ids)
                if not sids:
                    continue
                for sid in sids:
                    res = compute_exam_eligibility(
                        sid, mod, exam_id=eid,
                        threshold=threshold, cutoff_date=dt, persist=True,
                    )
                    p = res["attended"]
                    t = res["total_sessions"]
                    pct = res["percentage"]
                    verdict = res["verdict"]
                    eligible = res["eligible"]
                    tag = "ok" if eligible else ("" if not t else "bad")
                    self._eligibility_rows.append((
                        (dt, mod, name_lookup.get(sid, sid),
                         p, t,
                         f"{pct:.1f}%" if t else "-",
                         verdict),
                        tag, bool(eligible)))
        except Exception as exc:
            messagebox.showerror(_t('gui.academics.exam_management.tabs.attendance_intel_tab.dialogs.exam_eligibility', default="Exam Eligibility"),
                                 f"Failed to load: {exc}", parent=self.root)
            return

        self._apply_eligibility_filter()
