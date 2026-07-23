"""Split from student_features.py — see package __init__.py for public API."""
from __future__ import annotations

import calendar
import csv
import functools
import json
import logging
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.post_18.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.post_18.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.student")
except Exception:
    logger = logging.getLogger("absence_tracker.student")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from ..context import StudentContext, ensure_student_tables
from ..prefs import StudentPrefs
from ..gauge import GaugeThresholds, _load_gauge_thresholds
from ..timeline_filter import _TimelineFilter
from ..widgets.prompt import Prompt
from ..widgets.module_picker import ModulePicker
from ..widgets.calendar_window import _CalendarWindow
from ..widgets.wheel_bind import _bind_wheel, _unbind_wheel
from ..gauge import _GAUGE_LABELS, _GAUGE_COLOURS


_PRESENT_ONLY = {"present"}
_ATTENDED = {"present", "late", "excused"}
_WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DOW_REMAP = {0: 6, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5}


class AttendanceVisibilityService:
    """Read-only views of the student's own attendance (#1–#8)."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs) -> None:
        self.ctx = ctx
        self.prefs = prefs

    # --- #1 calendar -----------------------------------------------------
    @safe("Calendar")
    def show_calendar(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        win = _CalendarWindow(self.ctx, sid)
        win.show()
        audit(self.ctx, "student.calendar", "attendance", sid,
              win.current_month_str())

    # --- #2 gauges -------------------------------------------------------
    @safe("Attendance gauge")
    def show_gauges(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        thresholds = _load_gauge_thresholds(self.ctx.db)
        rows = self._fetch_module_attendance(sid)

        win = tk.Toplevel(self.ctx.parent)
        win.title("Attendance gauge")
        win.geometry("680x520")
        win.transient(self.ctx.parent)

        if not rows:
            tk.Label(win, text="No attendance data yet.",
                     fg="#6b7280", font=("Arial", 11)).pack(pady=40)
            audit(self.ctx, "student.gauge", "attendance", sid, "empty")
            return

        self._build_summary(win, rows, thresholds)
        self._build_module_list(win, rows, thresholds)
        audit(self.ctx, "student.gauge", "attendance", sid,
              f"modules={len(rows)}")

    def _fetch_module_attendance(self, sid: str) -> list[tuple]:
        try:
            return self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE(m.module_name, m.module_code),
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END) AS present,
                          SUM(CASE WHEN a.status='late'    THEN 1 ELSE 0 END) AS late,
                          SUM(CASE WHEN a.status='excused' THEN 1 ELSE 0 END) AS excused,
                          SUM(CASE WHEN a.status='absent'  THEN 1 ELSE 0 END) AS absent,
                          COUNT(a.id) AS total,
                          CASE WHEN COUNT(a.id) = 0 THEN NULL
                               ELSE SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                                    * 100.0 / COUNT(a.id)
                          END AS pct_present,
                          CASE WHEN COUNT(a.id) = 0 THEN NULL
                               ELSE SUM(CASE WHEN a.status IN ('present','late','excused')
                                             THEN 1 ELSE 0 END)
                                    * 100.0 / COUNT(a.id)
                          END AS pct_attended
                   FROM modules m
                   JOIN student_modules sm ON sm.module_code = m.module_code
                   LEFT JOIN attendance a
                     ON a.module_code = m.module_code
                    AND a.student_id  = sm.student_id
                   WHERE sm.student_id = ?
                   GROUP BY m.module_code, m.module_name
                   ORDER BY pct_attended ASC NULLS LAST, m.module_code""",
                (sid,),
            ).fetchall()
        except sqlite3.Error:
            logger.exception("module attendance query failed sid=%s", sid)
            return []

    def _build_summary(self, parent, rows, thresholds: GaugeThresholds) -> None:
        counts = {"good": 0, "warn": 0, "poor": 0, "none": 0}
        for *_, total, _pct_present, pct_attended in rows:
            if not total:
                counts["none"] += 1
            else:
                counts[thresholds.band(pct_attended)] += 1

        bar = tk.Frame(parent, bg="#f8fafc")
        bar.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(bar, text="Summary",
                 font=("Arial", 11, "bold"), bg="#f8fafc").pack(side="left")
        for band in ("good", "warn", "poor"):
            tk.Label(bar, text=f"  {_GAUGE_LABELS[band]}: {counts[band]}",
                     fg="white", bg=_GAUGE_COLOURS[band], padx=8, pady=2,
                     font=("Arial", 10, "bold")).pack(side="left", padx=4)
        if counts["none"]:
            tk.Label(bar, text=f"  No data: {counts['none']}",
                     fg="#6b7280", bg="#f8fafc",
                     padx=8, pady=2).pack(side="left", padx=4)

    def _build_module_list(self, parent, rows,
                           thresholds: GaugeThresholds) -> None:
        outer = tk.Frame(parent)
        outer.pack(fill="both", expand=True, padx=10, pady=(4, 10))
        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        inner = tk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Enter>", lambda _e: _bind_wheel(canvas))
        canvas.bind("<Leave>", lambda _e: _unbind_wheel(canvas))

        for code, name, present, late, excused, absent, total, \
                _pct_present, pct_attended in rows:
            self._render_module_row(inner, code, name, present, late, excused,
                                    absent, total, pct_attended, thresholds)

    def _render_module_row(self, parent, code, name, present, late,
                           excused, absent, total, pct_attended,
                           thresholds: GaugeThresholds) -> None:
        row = tk.Frame(parent, bd=1, relief="solid")
        row.pack(fill="x", pady=3)
        title = tk.Frame(row); title.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(title, text=f"{code} — {name}",
                 font=("Arial", 11, "bold"), anchor="w").pack(side="left")
        if not total:
            tk.Label(title, text="no sessions yet", fg="#6b7280").pack(side="right")
            tk.Frame(row, height=4).pack(fill="x")
            return
        band = thresholds.band(pct_attended)
        colour = _GAUGE_COLOURS[band]
        tk.Label(title, text=f"{pct_attended:.1f}%",
                 fg="white", bg=colour, padx=10, pady=2,
                 font=("Arial", 11, "bold")).pack(side="right")
        bar_wrap = tk.Frame(row, bg="#e5e7eb", height=10)
        bar_wrap.pack(fill="x", padx=8, pady=2)
        bar_wrap.pack_propagate(False)
        fill = tk.Frame(bar_wrap, bg=colour)
        fill.place(relx=0, rely=0,
                   relwidth=max(0.0, min(1.0, pct_attended / 100)), relheight=1)
        breakdown = (f"{total} sessions  ·  present {present}  ·  late {late}  ·  "
                     f"excused {excused}  ·  absent {absent}")
        tk.Label(row, text=breakdown, fg="#6b7280", anchor="w",
                 font=("Arial", 9)).pack(fill="x", padx=8, pady=(0, 6))

    # --- #3 streak -------------------------------------------------------
    @safe("Streak")
    def show_streak(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT date, status FROM attendance
                   WHERE student_id = ? AND status IS NOT NULL
                   ORDER BY date""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("streak query failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return

        if not rows:
            messagebox.showinfo("Streak", "No attendance recorded yet.",
                                parent=self.ctx.parent)
            audit(self.ctx, "student.streak", "attendance", sid, "empty")
            return

        present_now,  present_best,  _ = self._streaks(rows, _PRESENT_ONLY)
        attended_now, attended_best, _ = self._streaks(rows, _ATTENDED)
        last_date, last_status = rows[-1]
        msg = (f"Present-only streak\n"
               f"   current: {present_now}   best: {present_best}\n\n"
               f"Attended streak (present + late + excused)\n"
               f"   current: {attended_now}   best: {attended_best}\n\n"
               f"Last record: {last_date} — {last_status}")
        messagebox.showinfo("Streak", msg, parent=self.ctx.parent)
        audit(self.ctx, "student.streak", "attendance", sid,
              f"present_now={present_now} attended_now={attended_now}")

    @staticmethod
    def _streaks(rows: list[tuple[str, str]],
                 counted: set[str]) -> tuple[int, int, Optional[str]]:
        longest = cur = 0
        last_in_run: Optional[str] = None
        for d, st in rows:
            if st in counted:
                cur += 1
                longest = max(longest, cur)
                last_in_run = d
            else:
                cur = 0
                last_in_run = None
        return cur, longest, last_in_run

    # --- #4 timeline -----------------------------------------------------
    @safe("Timeline")
    def show_timeline(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        flt = self._ask_timeline_filters()
        if flt is None:
            return
        rows = self._fetch_timeline(sid, flt)
        title = f"My timeline ({len(rows)} rows)" + self._filter_suffix(flt)
        _show_table(self.ctx.parent, title,
                    ("date", "module", "status", "reason"), rows,
                    widths=[110, 140, 90, 360])
        audit(self.ctx, "student.timeline", "attendance", sid,
              f"n={len(rows)} status={flt.status or 'all'}")

    def _ask_timeline_filters(self) -> Optional[_TimelineFilter]:
        dlg = tk.Toplevel(self.ctx.parent)
        dlg.title("Timeline filters")
        dlg.transient(self.ctx.parent)
        dlg.grab_set()
        dlg.geometry("420x260")

        tk.Label(dlg, text="Filter my timeline",
                 font=("Arial", 11, "bold")).pack(pady=(10, 6))
        body = tk.Frame(dlg)
        body.pack(padx=14, pady=4, fill="x")

        tk.Label(body, text="Status:").grid(row=0, column=0, sticky="w", pady=4)
        status_var = tk.StringVar(value="(all)")
        ttk.Combobox(body, textvariable=status_var, state="readonly", width=20,
                     values=["(all)", "present", "absent", "late", "excused"]
                     ).grid(row=0, column=1, sticky="w", pady=4)

        tk.Label(body, text="Module:").grid(row=1, column=0, sticky="w", pady=4)
        try:
            enrolments = self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE(m.module_name, m.module_code)
                   FROM modules m
                   JOIN student_modules sm ON sm.module_code = m.module_code
                   WHERE sm.student_id = ?
                   ORDER BY m.module_code""",
                (self.ctx.sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("enrolments lookup failed")
            enrolments = []
        mod_label_to_code = {"(all)": None}
        for code, name in enrolments:
            mod_label_to_code[f"{code} — {name}"] = code
        mod_var = tk.StringVar(value="(all)")
        ttk.Combobox(body, textvariable=mod_var, state="readonly", width=30,
                     values=list(mod_label_to_code)
                     ).grid(row=1, column=1, sticky="w", pady=4)

        range_var = tk.StringVar(value="(no range)")
        tk.Label(body, text="Date range:").grid(row=2, column=0, sticky="w", pady=4)
        tk.Label(body, textvariable=range_var, fg="#374151"
                 ).grid(row=2, column=1, sticky="w", pady=4)
        chosen = {"start": None, "end": None}

        def pick_range():
            rng = pick_date_range(dlg, "Timeline date range")
            if rng:
                chosen["start"], chosen["end"] = rng
                range_var.set(f"{rng[0]}  →  {rng[1]}")

        def clear_range():
            chosen["start"] = chosen["end"] = None
            range_var.set("(no range)")

        btns = tk.Frame(body); btns.grid(row=3, column=0, columnspan=2, pady=6)
        tk.Button(btns, text="Pick…", command=pick_range,
                  relief="flat", bg="#2563eb", fg="white",
                  padx=10, pady=2).pack(side="left", padx=4)
        tk.Button(btns, text="Clear", command=clear_range,
                  relief="flat", bg="#6b7280", fg="white",
                  padx=10, pady=2).pack(side="left", padx=4)

        result: dict = {}

        def ok():
            result["filter"] = _TimelineFilter(
                status=None if status_var.get() == "(all)" else status_var.get(),
                module=mod_label_to_code.get(mod_var.get()),
                start=chosen["start"], end=chosen["end"])
            dlg.destroy()

        foot = tk.Frame(dlg); foot.pack(pady=10)
        tk.Button(foot, text="Apply", command=ok, bg="#2563eb", fg="white",
                  relief="flat", padx=18, pady=4).pack(side="left", padx=6)
        tk.Button(foot, text="Cancel", command=dlg.destroy, bg="#6b7280",
                  fg="white", relief="flat", padx=18, pady=4
                  ).pack(side="left", padx=6)
        dlg.wait_window()
        return result.get("filter")

    def _fetch_timeline(self, sid: str,
                        flt: _TimelineFilter) -> list[tuple]:
        q = ["""SELECT a.date,
                       COALESCE(m.module_name, a.module_code) AS module,
                       a.status,
                       COALESCE(a.reason, '') AS reason
                FROM attendance a
                LEFT JOIN modules m ON m.module_code = a.module_code
                WHERE a.student_id = ?"""]
        p: list = [sid]
        if flt.status: q.append("AND a.status = ?"); p.append(flt.status)
        if flt.module: q.append("AND a.module_code = ?"); p.append(flt.module)
        if flt.start:  q.append("AND a.date >= ?"); p.append(flt.start)
        if flt.end:    q.append("AND a.date <= ?"); p.append(flt.end)
        q.append("ORDER BY a.date DESC")
        try:
            return self.ctx.db.cur.execute(" ".join(q), p).fetchall()
        except sqlite3.Error:
            logger.exception("timeline fetch failed")
            return []

    @staticmethod
    def _filter_suffix(flt: _TimelineFilter) -> str:
        parts = []
        if flt.status: parts.append(flt.status)
        if flt.module: parts.append(flt.module)
        if flt.start or flt.end:
            parts.append(f"{flt.start or '…'}→{flt.end or '…'}")
        return f"  [{', '.join(parts)}]" if parts else ""

    # --- #5 export -------------------------------------------------------
    @safe("Export my data")
    def export_my_data(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        fmt = _combo_dialog(self.ctx.parent, "Export format",
                            "Format:", ["CSV", "JSON"])
        if not fmt:
            return
        try:
            attendance = self.ctx.db.get_absences(student_id=sid)
            requests = self.ctx.db.cur.execute(
                """SELECT id, module_code, date, reason, status, submitted_at
                   FROM absence_requests WHERE student_id = ?
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("export query failed")
            messagebox.showerror("Error", "Could not load your data.",
                                 parent=self.ctx.parent)
            return
        att_hdr = ("id", "student", "module_code", "module_name",
                   "date", "status", "reason")
        req_hdr = ("id", "module_code", "date", "reason", "status", "submitted_at")
        try:
            if fmt == "CSV":
                path = self._write_two_csv(sid, att_hdr, attendance,
                                           req_hdr, requests)
            else:
                path = self._write_json(sid, att_hdr, attendance,
                                        req_hdr, requests)
        except OSError as e:
            messagebox.showerror("Write failed", str(e), parent=self.ctx.parent)
            return
        if not path:
            return
        audit(self.ctx, "student.export", "attendance", sid,
              f"{fmt.lower()} att={len(attendance)} req={len(requests)} -> {path}")
        messagebox.showinfo("Exported",
                            f"{len(attendance)} attendance row(s)\n"
                            f"{len(requests)} request row(s)\n\nSaved to:\n{path}",
                            parent=self.ctx.parent)

    def _write_two_csv(self, sid, att_hdr, att, req_hdr,
                       req) -> Optional[str]:
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".csv",
            initialfile=f"my_attendance_{sid}.csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return None
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["# Attendance"]); w.writerow(att_hdr); w.writerows(att)
            w.writerow([])
            w.writerow(["# Absence requests"]); w.writerow(req_hdr); w.writerows(req)
        return path

    def _write_json(self, sid, att_hdr, att, req_hdr,
                    req) -> Optional[str]:
        path = filedialog.asksaveasfilename(
            parent=self.ctx.parent, defaultextension=".json",
            initialfile=f"my_attendance_{sid}.json",
            filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not path:
            return None
        payload = {
            "student_id": sid,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "attendance": [dict(zip(att_hdr, row)) for row in att],
            "absence_requests": [dict(zip(req_hdr, row)) for row in req],
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)
        return path

    # --- #6 compare-to-module -------------------------------------------
    @safe("Compare to module")
    def compare_to_module_average(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        rows = self._fetch_module_comparison(sid)
        if not rows:
            messagebox.showinfo("Compare to module",
                                "No attendance data to compare yet.",
                                parent=self.ctx.parent)
            return
        table = []
        for code, name, mine, module_avg, my_n, mod_n in rows:
            delta = (mine - module_avg) if mine is not None else None
            table.append((
                code, name,
                "—" if mine is None else f"{mine:.1f}",
                f"{module_avg:.1f}" if module_avg is not None else "—",
                "—" if delta is None else f"{delta:+.1f}",
                f"{my_n}/{mod_n}",
            ))
        _show_table(self.ctx.parent, "Me vs module average",
                    ("module", "name", "my %", "module avg %", "Δ",
                     "my sessions / total"),
                    table, widths=[100, 220, 80, 120, 80, 160])
        audit(self.ctx, "student.compare_module_avg", "attendance", sid,
              f"modules={len(rows)}")

    def _fetch_module_comparison(self, sid: str) -> list[tuple]:
        try:
            return self.ctx.db.cur.execute(
                """SELECT m.module_code,
                          COALESCE(m.module_name, m.module_code) AS name,
                          CASE
                            WHEN SUM(CASE WHEN a.student_id = ? THEN 1 ELSE 0 END) = 0
                            THEN NULL
                            ELSE SUM(CASE WHEN a.student_id = ?
                                           AND a.status IN ('present','late','excused')
                                          THEN 1 ELSE 0 END) * 100.0
                               / SUM(CASE WHEN a.student_id = ? THEN 1 ELSE 0 END)
                          END AS mine,
                          CASE
                            WHEN COUNT(a.id) = 0 THEN NULL
                            ELSE SUM(CASE WHEN a.status IN ('present','late','excused')
                                          THEN 1 ELSE 0 END) * 100.0
                               / COUNT(a.id)
                          END AS module_avg,
                          SUM(CASE WHEN a.student_id = ? THEN 1 ELSE 0 END) AS my_n,
                          COUNT(a.id) AS mod_n
                   FROM modules m
                   JOIN student_modules sm ON sm.module_code = m.module_code
                   LEFT JOIN attendance a  ON a.module_code  = m.module_code
                   WHERE sm.student_id = ?
                   GROUP BY m.module_code, m.module_name
                   HAVING my_n > 0
                   ORDER BY (mine - module_avg) ASC NULLS LAST, m.module_code""",
                (sid, sid, sid, sid, sid)).fetchall()
        except sqlite3.Error:
            logger.exception("module comparison failed")
            return []

    # --- #7 projection ---------------------------------------------------
    @safe("Projection")
    def project_absence_budget(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        threshold = self._ask_projection_threshold(sid)
        if threshold is None:
            return
        rows = self._fetch_module_attendance(sid)
        if not rows:
            messagebox.showinfo("Projection",
                                "No attendance data yet — nothing to project.",
                                parent=self.ctx.parent)
            return
        table = []
        for code, name, present, late, excused, absent, total, \
                _pct_present, pct_attended in rows:
            if not total:
                table.append((code, name, "—", "—", "—", "no sessions yet"))
                continue
            attended = present + late + excused
            budget = self._absence_budget(attended, total, threshold)
            verdict = self._budget_verdict(pct_attended, threshold, budget)
            table.append((
                code, name,
                f"{pct_attended:.1f}%",
                f"{threshold:.0f}%",
                "—" if budget is None else str(budget),
                verdict,
            ))
        _show_table(self.ctx.parent,
                    f"Absence budget (keep ≥ {threshold:.0f}%)",
                    ("module", "name", "current", "target", "can miss", "status"),
                    table, widths=[100, 220, 90, 80, 90, 200])
        audit(self.ctx, "student.projection", "attendance", sid,
              f"threshold={threshold} modules={len(rows)}")

    def _ask_projection_threshold(self, sid: str) -> Optional[float]:
        initial = self.prefs.get_float(sid, "projection.threshold", 80.0)
        val = simpledialog.askfloat(
            "Threshold", "Stay above what %? (1–100)",
            parent=self.ctx.parent,
            initialvalue=initial, minvalue=1.0, maxvalue=100.0)
        if val is None:
            return None
        try:
            self.prefs.set(sid, "projection.threshold", val)
        except sqlite3.Error:
            pass
        return val

    @staticmethod
    def _absence_budget(attended: int, total: int,
                        threshold_pct: float) -> Optional[int]:
        if attended * 100 < threshold_pct * total:
            return None
        if threshold_pct <= 0:
            return 10_000
        k = int((attended * 100) / threshold_pct) - total
        return max(k, 0)

    @staticmethod
    def _budget_verdict(pct_attended: float, threshold: float,
                        budget: Optional[int]) -> str:
        if budget is None:
            return f"already below {threshold:.0f}%"
        if budget == 0:
            return "at the limit"
        if pct_attended < threshold + 5:
            return "tight margin"
        return "comfortable"

    # --- #8 personal heatmap --------------------------------------------
    @safe("Personal heatmap")
    def show_personal_heatmap(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            raw = self.ctx.db.cur.execute(
                """SELECT CAST(strftime('%w', date) AS INTEGER) AS dow,
                          status, COUNT(*)
                   FROM attendance
                   WHERE student_id = ? AND status IS NOT NULL
                   GROUP BY dow, status""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("heatmap query failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return

        buckets: list[dict[str, int]] = [
            {"present": 0, "late": 0, "excused": 0, "absent": 0}
            for _ in _WEEKDAY_NAMES
        ]
        for dow, status, n in raw:
            idx = _DOW_REMAP.get(dow)
            if idx is None or status not in buckets[idx]:
                continue
            buckets[idx][status] = n

        if not any(sum(b.values()) for b in buckets):
            messagebox.showinfo("Personal heatmap",
                                "No attendance records yet.",
                                parent=self.ctx.parent)
            return

        self._show_heatmap_window(buckets)
        audit(self.ctx, "student.heatmap", "attendance", sid,
              f"sessions={sum(sum(b.values()) for b in buckets)}")

    def _show_heatmap_window(self, buckets: list[dict[str, int]]) -> None:
        win = tk.Toplevel(self.ctx.parent)
        win.title("My attendance by day-of-week")
        win.geometry("680x360")
        win.transient(self.ctx.parent)
        tk.Label(win, text="Attendance pattern by day of week",
                 font=("Arial", 12, "bold")).pack(pady=(10, 4))

        worst = self._worst_day(buckets)
        if worst is not None:
            tk.Label(win,
                     text=f"Most absences fall on {_WEEKDAY_NAMES[worst]}.",
                     fg="#6b7280").pack(pady=(0, 8))

        grid = tk.Frame(win); grid.pack(padx=12, pady=4, fill="x")
        headers = ("day", "present", "late", "excused", "absent",
                   "total", "attended %")
        for c, h in enumerate(headers):
            tk.Label(grid, text=h, font=("Arial", 10, "bold"),
                     width=10, anchor="center"
                     ).grid(row=0, column=c, padx=2, pady=2)
        for r, day in enumerate(_WEEKDAY_NAMES, start=1):
            b = buckets[r - 1]
            total = sum(b.values())
            attended = b["present"] + b["late"] + b["excused"]
            pct = (attended / total * 100) if total else None
            absent_rate = (b["absent"] / total) if total else 0
            bg = self._absence_rate_bg(absent_rate, has_data=bool(total))
            tk.Label(grid, text=day, width=10, bg=bg,
                     font=("Arial", 10, "bold")
                     ).grid(row=r, column=0, padx=2, pady=2, sticky="ew")
            for c, key in enumerate(("present", "late", "excused", "absent"),
                                    start=1):
                tk.Label(grid, text=str(b[key]), width=10, bg=bg
                         ).grid(row=r, column=c, padx=2, pady=2, sticky="ew")
            tk.Label(grid, text=str(total) if total else "—",
                     width=10, bg=bg
                     ).grid(row=r, column=5, padx=2, pady=2, sticky="ew")
            tk.Label(grid, text="—" if pct is None else f"{pct:.0f}%",
                     width=10, bg=bg, font=("Arial", 10, "bold")
                     ).grid(row=r, column=6, padx=2, pady=2, sticky="ew")

    @staticmethod
    def _worst_day(buckets: list[dict[str, int]]) -> Optional[int]:
        worst_idx, worst_rate = None, -1.0
        for i, b in enumerate(buckets):
            tot = sum(b.values())
            if not tot:
                continue
            rate = b["absent"] / tot
            if rate > worst_rate:
                worst_rate, worst_idx = rate, i
        return worst_idx if worst_rate > 0 else None

    @staticmethod
    def _absence_rate_bg(rate: float, *, has_data: bool) -> str:
        if not has_data:
            return "#f3f4f6"
        if rate <= 0.05: return "#dcfce7"
        if rate <= 0.15: return "#fef9c3"
        if rate <= 0.30: return "#fed7aa"
        return "#fecaca"


# ===========================================================================
# RequestService — features #9–#16, #51
# ===========================================================================

