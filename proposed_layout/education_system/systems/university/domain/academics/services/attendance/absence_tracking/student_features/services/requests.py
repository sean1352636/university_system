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

from education_system.systems.university.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.systems.university.infrastructure.logging.log_config import configure_logging
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

class RequestService:
    """Submit, attach, withdraw, resubmit, draft, and bulk-request absences."""

    def __init__(self, ctx: StudentContext, prefs: StudentPrefs,
                 picker: ModulePicker) -> None:
        self.ctx = ctx
        self.prefs = prefs
        self.picker = picker

    # internal helpers
    def _existing_active_dates(self, sid: str, module_code: str,
                               iso_dates: Iterable[str]) -> set[str]:
        iso_dates = list(iso_dates)
        if not iso_dates:
            return set()
        try:
            placeholders = ",".join("?" * len(iso_dates))
            rows = self.ctx.db.cur.execute(
                f"""SELECT date FROM absence_requests
                    WHERE student_id=? AND module_code=?
                      AND status NOT IN ('rejected','withdrawn')
                      AND date IN ({placeholders})""",
                [sid, module_code, *iso_dates]).fetchall()
            return {r[0] for r in rows}
        except sqlite3.Error:
            logger.exception("dup-date lookup failed")
            return set()

    # --- #9 quick-submit -------------------------------------------------
    @safe("Quick-submit")
    def quick_submit_from_template(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            templates = self.ctx.db.cur.execute(
                "SELECT name, body FROM abs_tracker_request_templates ORDER BY name"
            ).fetchall()
        except sqlite3.Error:
            logger.exception("template fetch failed")
            messagebox.showerror("Error", "Could not load templates.",
                                 parent=self.ctx.parent)
            return
        if not templates:
            messagebox.showinfo("No templates",
                                "Ask an admin to create request templates first.",
                                parent=self.ctx.parent)
            return
        tmap = {r[0]: r[1] for r in templates}
        tpl = _combo_dialog(self.ctx.parent, "Template",
                            "Pick template:", list(tmap.keys()))
        if not tpl:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        if self._existing_active_dates(sid, mcode, [d]):
            messagebox.showwarning("Duplicate",
                                   f"You already have a request for {mlabel} on {d}.",
                                   parent=self.ctx.parent)
            return
        body = tmap[tpl]
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              f"Submit absence request?\n\nModule: {mlabel}\n"
                              f"Date: {d}\nTemplate: {tpl}\n\n{body[:300]}"):
            return
        try:
            self.ctx.db.submit_request(sid, mcode, d, body)
        except sqlite3.Error as e:
            messagebox.showerror("Failed", f"Could not submit: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.quick_submit", "absence_requests", sid, tpl)
        messagebox.showinfo("Submitted", "Request submitted.",
                            parent=self.ctx.parent)

    # --- #10 attach evidence --------------------------------------------
    @safe("Attach evidence")
    def attach_evidence(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT r.id, r.date, r.module_code, r.status,
                          (SELECT COUNT(*) FROM abs_tracker_request_attachments
                           WHERE request_id=r.id)
                   FROM absence_requests r
                   WHERE r.student_id=? ORDER BY r.id DESC""",
                (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("requests fetch failed")
            messagebox.showerror("Error", "Could not load your requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("No requests", "You have no requests.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]} [{r[3]}] ({r[4]} attached)": r[0]
             for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Request",
                             "Pick request:", list(m.keys()))
        if not pick:
            return
        rid = m[pick]
        path = filedialog.askopenfilename(
            parent=self.ctx.parent,
            filetypes=[("Documents", "*.pdf *.doc *.docx *.txt *.png *.jpg *.jpeg"),
                       ("All files", "*.*")])
        if not path:
            return
        p = Path(path)
        if not p.is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        try:
            size = p.stat().st_size
        except OSError as e:
            messagebox.showerror("Error", f"Cannot read file: {e}",
                                 parent=self.ctx.parent)
            return
        if size > 25 * 1024 * 1024:
            messagebox.showerror("Too large",
                                 f"File is {size/1024/1024:.1f} MB (max 25 MB).",
                                 parent=self.ctx.parent)
            return
        try:
            self.ctx.db.cur.execute(
                "INSERT INTO abs_tracker_request_attachments (request_id, file_path) VALUES (?, ?)",
                (rid, str(p.resolve())))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Could not save attachment: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.attach", "absence_requests", rid, p.name)
        messagebox.showinfo("Attached",
                            f"Attached {p.name} ({size/1024:.0f} KB).",
                            parent=self.ctx.parent)

    # --- #11 status tracker ---------------------------------------------
    @safe("Status tracker")
    def show_status_tracker(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code, status, submitted_at,
                          substr(reason,1,60)
                   FROM absence_requests WHERE student_id=?
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("status tracker fetch failed")
            messagebox.showerror("Error", "Could not load your requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("No requests",
                                "You have no absence requests yet.",
                                parent=self.ctx.parent)
            return
        counts: dict[str, int] = {}
        for r in rows:
            counts[r[3] or "?"] = counts.get(r[3] or "?", 0) + 1
        summary = " | ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
        _show_table(self.ctx.parent,
                    f"My request statuses — {len(rows)} total ({summary})",
                    ("id", "date", "module", "status", "submitted", "reason"),
                    rows, widths=[60, 100, 110, 90, 150, 360])

    # --- #12 withdraw ---------------------------------------------------
    @safe("Withdraw")
    def withdraw_pending(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code FROM absence_requests
                   WHERE student_id=? AND status='pending'
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("pending fetch failed")
            messagebox.showerror("Error", "Could not load pending requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("No pending", "Nothing to withdraw.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]}": r[0] for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Withdraw",
                             "Which?", list(m.keys()))
        if not pick:
            return
        rid = m[pick]
        if not Prompt.confirm(self.ctx.parent, "Confirm withdrawal",
                              f"Withdraw request {pick}?\nThis cannot be undone."):
            return
        try:
            self.ctx.db.cur.execute(
                """UPDATE absence_requests
                   SET status='withdrawn',
                       reason = CASE
                           WHEN reason LIKE '%[withdrawn]%' THEN reason
                           ELSE COALESCE(reason,'') || ' [withdrawn]'
                       END
                   WHERE id=? AND status='pending'""", (rid,))
            changed = self.ctx.db.cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Could not withdraw: {e}",
                                 parent=self.ctx.parent)
            return
        if changed == 0:
            messagebox.showwarning("Already actioned",
                                   "This request is no longer pending.",
                                   parent=self.ctx.parent)
            return
        audit(self.ctx, "student.withdraw", "absence_requests", rid, "")
        messagebox.showinfo("Withdrawn", "Request withdrawn.",
                            parent=self.ctx.parent)

    # --- #13 resubmit ---------------------------------------------------
    @safe("Resubmit")
    def resubmit_rejected(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, date, module_code, reason FROM absence_requests
                   WHERE student_id=? AND status='rejected'
                   ORDER BY submitted_at DESC""", (sid,)).fetchall()
        except sqlite3.Error:
            logger.exception("rejected fetch failed")
            messagebox.showerror("Error", "Could not load rejected requests.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("None", "No rejected requests.",
                                parent=self.ctx.parent)
            return
        m = {f"#{r[0]} {r[1]} {r[2]}": r for r in rows}
        pick = _combo_dialog(self.ctx.parent, "Resubmit",
                             "Which?", list(m.keys()))
        if not pick:
            return
        rid, d, mc, old = m[pick]
        if self._existing_active_dates(sid, mc, [d]):
            messagebox.showwarning("Duplicate",
                                   f"Active request already exists for {mc} on {d}.",
                                   parent=self.ctx.parent)
            return
        new = Prompt.non_empty(self.ctx.parent, "New reason",
                               f"(was: {old or '—'})\n\nNew reason (min 5 chars):",
                               min_len=5)
        if not new:
            return
        try:
            self.ctx.db.submit_request(sid, mc, d, new + " [resubmitted]")
        except sqlite3.Error as e:
            messagebox.showerror("Failed", f"Could not resubmit: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.resubmit", "absence_requests", rid, new[:80])
        messagebox.showinfo("Submitted", "Resubmitted.", parent=self.ctx.parent)

    # --- #14 bulk request -----------------------------------------------
    @safe("Bulk request")
    def bulk_multi_day_request(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        start = Prompt.iso_date(self.ctx.parent, "Start", "Start (YYYY-MM-DD):")
        if not start:
            return
        days = simpledialog.askinteger(
            "Days", "How many consecutive days?",
            parent=self.ctx.parent, minvalue=1, maxvalue=30)
        if not days:
            return
        skip_weekends = Prompt.confirm(self.ctx.parent, "Weekends",
                                       "Skip Saturdays and Sundays?")
        reason = Prompt.non_empty(self.ctx.parent, "Reason",
                                  "Reason (min 5 chars):", min_len=5)
        if not reason:
            return
        d0 = datetime.strptime(start, "%Y-%m-%d").date()
        candidate = [d0 + timedelta(days=k) for k in range(days)]
        if skip_weekends:
            candidate = [d for d in candidate if d.weekday() < 5]
        if not candidate:
            messagebox.showinfo("Nothing to submit",
                                "All selected dates were weekends.",
                                parent=self.ctx.parent)
            return
        iso = [d.isoformat() for d in candidate]
        dupes = self._existing_active_dates(sid, mcode, iso)
        to_submit = [d for d in iso if d not in dupes]
        if not to_submit:
            messagebox.showinfo("All duplicates",
                                "All selected dates already have active requests.",
                                parent=self.ctx.parent)
            return
        msg = (f"Submit {len(to_submit)} request(s) for {mlabel}?\n"
               f"Range: {to_submit[0]} → {to_submit[-1]}")
        if dupes:
            msg += f"\n\nSkipping {len(dupes)} duplicate date(s)."
        if not Prompt.confirm(self.ctx.parent, "Confirm bulk", msg):
            return
        try:
            for d in to_submit:
                self.ctx.db.cur.execute(
                    """INSERT INTO absence_requests
                       (student_id, module_code, date, reason)
                       VALUES (?, ?, ?, ?)""", (sid, mcode, d, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Bulk submit failed:\n{e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.bulk_request", "absence_requests", sid,
              f"{mcode} {to_submit[0]}..{to_submit[-1]} x{len(to_submit)}")
        extra = f" ({len(dupes)} skipped)" if dupes else ""
        messagebox.showinfo("Submitted",
                            f"Submitted {len(to_submit)} request(s){extra}.",
                            parent=self.ctx.parent)

    # --- #15 save draft -------------------------------------------------
    @safe("Save draft")
    def save_draft(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        reason = (simpledialog.askstring("Reason", "Reason (optional):",
                                         parent=self.ctx.parent) or "").strip()
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_student_drafts
                   (student_id, module_code, date, reason) VALUES (?,?,?,?)""",
                (sid, mcode, d, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Could not save draft: {e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.draft", "abs_tracker_student_drafts", sid, mcode)
        messagebox.showinfo("Saved", f"Draft saved for {mlabel} on {d}.",
                            parent=self.ctx.parent)

    # --- #16 history export ---------------------------------------------
    @safe("Request history export")
    def export_request_history(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        try:
            statuses = [r[0] for r in self.ctx.db.cur.execute(
                """SELECT DISTINCT COALESCE(status,'?') FROM absence_requests
                   WHERE student_id=? ORDER BY 1""", (sid,)).fetchall()]
        except sqlite3.Error:
            logger.exception("history status fetch failed")
            messagebox.showerror("Error", "Could not load your history.",
                                 parent=self.ctx.parent)
            return
        if not statuses:
            messagebox.showinfo("Nothing to export", "You have no requests.",
                                parent=self.ctx.parent)
            return
        choice = _combo_dialog(self.ctx.parent, "Filter", "Status:",
                               ["(all)"] + statuses)
        if choice is None:
            return
        try:
            if choice == "(all)":
                rows = self.ctx.db.cur.execute(
                    """SELECT id, date, module_code, status, submitted_at, reason
                       FROM absence_requests WHERE student_id=?
                       ORDER BY submitted_at DESC""", (sid,)).fetchall()
            else:
                rows = self.ctx.db.cur.execute(
                    """SELECT id, date, module_code, status, submitted_at, reason
                       FROM absence_requests
                       WHERE student_id=? AND COALESCE(status,'?')=?
                       ORDER BY submitted_at DESC""", (sid, choice)).fetchall()
        except sqlite3.Error:
            logger.exception("history rows fetch failed")
            messagebox.showerror("Error", "Could not load rows.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Empty", f"No requests with status '{choice}'.",
                                parent=self.ctx.parent)
            return
        path = _export_rows_to_csv(
            rows, ("id", "date", "module", "status", "submitted", "reason"),
            self.ctx.parent)
        if path:
            audit(self.ctx, "student.history_export", "absence_requests", sid,
                  f"{choice}:{len(rows)}:{path}")
            messagebox.showinfo("Saved",
                                f"Exported {len(rows)} row(s) to:\n{path}",
                                parent=self.ctx.parent)

    # --- #51 request time off (date picker) -----------------------------
    @safe("Request time off")
    def request_time_off(self) -> None:
        sid = self.ctx.require_sid()
        if not sid:
            return
        picked = self.picker.pick(sid)
        if not picked:
            return
        mcode, mlabel = picked
        rng = pick_date_range(self.ctx.parent, "Time-off dates")
        if not rng:
            return
        start, end = rng
        reason = Prompt.non_empty(self.ctx.parent, "Reason",
                                  "Reason for time off (min 3 chars):", min_len=3)
        if not reason:
            return
        try:
            d0 = datetime.strptime(start, "%Y-%m-%d").date()
            d1 = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError as e:
            messagebox.showerror("Bad date", str(e), parent=self.ctx.parent)
            return
        if d1 < d0:
            messagebox.showerror("Bad range",
                                 "End date is before start date.",
                                 parent=self.ctx.parent)
            return
        candidate = [(d0 + timedelta(days=k)).isoformat()
                     for k in range((d1 - d0).days + 1)]
        dupes = self._existing_active_dates(sid, mcode, candidate)
        to_submit = [d for d in candidate if d not in dupes]
        if not to_submit:
            messagebox.showinfo("All duplicates",
                                "All selected dates already have active requests.",
                                parent=self.ctx.parent)
            return
        try:
            for d in to_submit:
                self.ctx.db.cur.execute(
                    """INSERT INTO absence_requests
                       (student_id, module_code, date, reason)
                       VALUES (?, ?, ?, ?)""", (sid, mcode, d, reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            messagebox.showerror("Failed", f"Submit failed:\n{e}",
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "student.request_time_off", "absence_requests", sid,
              f"{mcode} {start}..{end} ({len(to_submit)})")
        extra = f" ({len(dupes)} skipped)" if dupes else ""
        messagebox.showinfo("Submitted",
                            f"{len(to_submit)} request(s) submitted{extra}.",
                            parent=self.ctx.parent)


# ===========================================================================
# NotificationService — features #17–#22
# ===========================================================================

