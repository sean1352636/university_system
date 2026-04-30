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

import json
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta

try:
    from education_system.university_system.infrastructure.database.db import get_connection
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


def _list_upcoming_exams(conn, limit=200):
    today = date.today().isoformat()
    rows = conn.execute(
        """SELECT id, module_code, COALESCE(module_name, module_code), date,
                  start_time, COALESCE(room,''), enrolled_student_ids
           FROM exams
           WHERE date >= ?
           ORDER BY date, start_time
           LIMIT ?""", (today, limit)).fetchall()
    return rows


# ===========================================================================
# At-Risk Audit
# ===========================================================================

class AtRiskTabMixin:

    def create_at_risk_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="At-Risk Audit")

        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            ctrl,
            text=f"Enrolled students with ≥ N absences in the past "
                 f"{ABSENCE_LOOKBACK_DAYS} days, per upcoming exam.",
            style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(ctrl, text="Min absences:").pack(side=tk.LEFT, padx=(20, 4))
        self.at_risk_threshold = tk.IntVar(value=3)
        ttk.Spinbox(ctrl, from_=1, to=30, width=4,
                    textvariable=self.at_risk_threshold,
                    command=self.refresh_at_risk_list).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="Refresh",
                   command=self.refresh_at_risk_list).pack(side=tk.RIGHT)

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

        self.refresh_at_risk_list()

    def refresh_at_risk_list(self):
        if not hasattr(self, "at_risk_tree"):
            return
        for item in self.at_risk_tree.get_children():
            self.at_risk_tree.delete(item)
        if not HAS_DB:
            return
        threshold = max(1, int(self.at_risk_threshold.get() or 1))
        cutoff = (date.today() - timedelta(days=ABSENCE_LOOKBACK_DAYS)).isoformat()
        try:
            with get_connection() as conn:
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

                exams = _list_upcoming_exams(conn)
                for (_eid, mod, mname, dt, _st, _rm, raw_ids) in exams:
                    sids = _enrolled_ids(raw_ids)
                    if not sids:
                        continue
                    placeholders = ",".join("?" * len(sids))
                    rows = conn.execute(
                        f"""SELECT a.student_id,
                                  TRIM(COALESCE(s.first_name,'')||' '
                                       ||COALESCE(s.last_name,'')) AS name,
                                  SUM(CASE WHEN LOWER(a.status)='absent' THEN 1 ELSE 0 END) AS abs_n,
                                  SUM(CASE WHEN LOWER(a.status)='late'   THEN 1 ELSE 0 END) AS late_n,
                                  MAX(a.date)
                           FROM attendance a
                           LEFT JOIN students s ON s.student_id = a.student_id
                           WHERE a.module_code = ?
                             AND a.date >= ?
                             AND a.student_id IN ({placeholders})
                           GROUP BY a.student_id
                           HAVING abs_n >= ?
                           ORDER BY abs_n DESC, late_n DESC""",
                        (mod, cutoff, *sids, threshold)).fetchall()
                    for (sid, name, abs_n, late_n, last) in rows:
                        display = (name or "").strip() or sid
                        risk = feed.get(str(sid), "—")
                        self.at_risk_tree.insert(
                            "", tk.END,
                            values=(dt, mod, display, risk,
                                    abs_n, late_n, last or ""))
        except Exception as exc:
            messagebox.showerror("At-Risk Audit",
                                 f"Failed to load: {exc}", parent=self.root)


# ===========================================================================
# Exam Eligibility
# ===========================================================================

class ExamEligibilityTabMixin:

    def create_eligibility_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Exam Eligibility")

        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            ctrl,
            text="Per-student attendance % on each upcoming exam's module. "
                 "Below threshold = Not Eligible.",
            style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(ctrl, text="Threshold %:").pack(side=tk.LEFT, padx=(20, 4))
        self.eligibility_threshold = tk.DoubleVar(value=ELIGIBILITY_THRESHOLD)
        ttk.Spinbox(ctrl, from_=0, to=100, increment=5, width=5,
                    textvariable=self.eligibility_threshold,
                    command=self.refresh_eligibility_list).pack(side=tk.LEFT)
        ttk.Button(ctrl, text="Refresh",
                   command=self.refresh_eligibility_list).pack(side=tk.RIGHT)

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

        self.refresh_eligibility_list()

    def refresh_eligibility_list(self):
        if not hasattr(self, "eligibility_tree"):
            return
        for item in self.eligibility_tree.get_children():
            self.eligibility_tree.delete(item)
        if not HAS_DB:
            return
        try:
            threshold = float(self.eligibility_threshold.get())
        except (TypeError, tk.TclError):
            threshold = ELIGIBILITY_THRESHOLD

        # Delegate the per-student calculation to the canonical
        # adapter so the verdict gets persisted into ``exam_eligibility``
        # — the Attendance and Absence GUIs read the same row.
        from education_system.university_system.modules.domain.academics.gui._attendance_eligibility import (
            compute_exam_eligibility,
        )

        try:
            with get_connection() as conn:
                exams = _list_upcoming_exams(conn)
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
                    self.eligibility_tree.insert(
                        "", tk.END,
                        values=(dt, mod, name_lookup.get(sid, sid),
                                p, t,
                                f"{pct:.1f}%" if t else "-",
                                verdict),
                        tags=(tag,))
        except Exception as exc:
            messagebox.showerror("Exam Eligibility",
                                 f"Failed to load: {exc}", parent=self.root)
