"""Split from staff_features.py — see package __init__.py for public API."""
from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import tkinter as tk
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable, Iterable, Optional

from education_system.university_system.modules.domain.academics.services.attendance.absence_tracking.admin_features import (
    safe, audit, _combo_dialog, _show_table, _export_rows_to_csv,
    _get_setting, _set_setting, ensure_support_tables,
    pick_date, pick_date_range,
)

try:
    from education_system.university_system.infrastructure.logging.log_config import configure_logging
    logger = configure_logging(name="absence_tracker.staff")
except Exception:
    logger = logging.getLogger("absence_tracker.staff")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)

from ..context import StaffContext, ensure_staff_tables
from ..prefs import StaffPrefs
from ..widgets.prompt import Prompt
from ..widgets.module_picker import ModulePicker
from ..widgets.staff_picker import StaffPicker

class RequestReviewService:
    """Triage queue, evidence preview, decisions, SLA, escalation."""

    def __init__(self, ctx: StaffContext) -> None:
        self.ctx = ctx

    # --- #16 ----------------------------------------------------------
    @safe("Triage queue")
    def show_triage_queue(self) -> None:
        if self.ctx.require_uid() is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT r.id, r.student_id, r.module_code, r.date, r.reason,
                          r.submitted_at
                   FROM absence_requests r
                   JOIN instructor_modules im ON im.module_code = r.module_code
                   WHERE r.status='pending' AND im.instructor_id=?
                   ORDER BY r.submitted_at""",
                (self.ctx.uid,)).fetchall()
        except sqlite3.Error:
            logger.exception("triage queue fetch failed")
            messagebox.showerror("Error", "Could not load triage queue.",
                                 parent=self.ctx.parent)
            return
        _show_table(self.ctx.parent, f"Pending triage ({len(rows)})",
                    ("id", "student", "module", "date", "reason", "submitted"),
                    rows, widths=[60, 120, 110, 100, 320, 160])

    # --- #17 ----------------------------------------------------------
    @safe("Preview evidence")
    def preview_request_evidence(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT file_path, uploaded_at
                   FROM abs_tracker_request_attachments WHERE request_id=?""",
                (rid,)).fetchall()
        except sqlite3.Error:
            logger.exception("evidence fetch failed rid=%s", rid)
            rows = []
        if not rows:
            messagebox.showinfo("None",
                                f"No evidence files for request {rid}.",
                                parent=self.ctx.parent)
            return
        _show_table(self.ctx.parent, f"Evidence for request {rid}",
                    ("path", "uploaded_at"), rows, widths=[560, 200])

    # --- #18 ----------------------------------------------------------
    @safe("Staff comment on decision")
    def decide_with_comment(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        decision = _combo_dialog(self.ctx.parent, "Decision", "Decision:",
                                 ["approved", "rejected"])
        if not decision:
            return
        comment = Prompt.non_empty(self.ctx.parent, "Comment",
                                   "Staff comment:", min_len=3)
        if not comment:
            return
        try:
            self.ctx.db.update_request(rid, decision)
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_request_comments
                   (request_id, author, body) VALUES (?, ?, ?)""",
                (rid, self.ctx.username, comment))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("decision/comment failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.decision_comment", "absence_requests", rid,
              f"{decision}: {comment[:120]}")
        messagebox.showinfo("Done", f"Request {decision}.",
                            parent=self.ctx.parent)

    # --- #19 ----------------------------------------------------------
    @safe("Approve with modification")
    def approve_with_modification(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            req = self.ctx.db.cur.execute(
                """SELECT student_id, module_code, date, reason
                   FROM absence_requests WHERE id=?""", (rid,)).fetchone()
        except sqlite3.Error:
            logger.exception("request fetch failed rid=%s", rid)
            messagebox.showerror("Error", "Could not load request.",
                                 parent=self.ctx.parent)
            return
        if not req:
            messagebox.showerror("Missing", "No such request.",
                                 parent=self.ctx.parent)
            return
        sid, mc, orig_date, reason = req
        new_date = Prompt.iso_date(self.ctx.parent, "Date",
                                   f"Date (was {orig_date}):",
                                   initial=orig_date) or orig_date
        new_status = _combo_dialog(
            self.ctx.parent, "Status", "Record as:",
            ["excused", "absent", "late", "present"]) or "excused"
        try:
            self.ctx.db.update_request(rid, "approved")
            self.ctx.db.record_absence(sid, mc, new_date, new_status,
                                       f"[Approved w/ mod] {reason}")
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("approve-with-mod failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.approve_mod", "absence_requests", rid,
              f"{orig_date}→{new_date} {new_status}")
        messagebox.showinfo("Approved",
                            f"Approved; recorded as {new_status} on {new_date}.",
                            parent=self.ctx.parent)

    # --- #20 ----------------------------------------------------------
    @safe("SLA dashboard")
    def show_sla_dashboard(self) -> None:
        if self.ctx.require_uid() is None:
            return
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT r.id, r.student_id, r.module_code, r.submitted_at,
                          CAST((julianday('now') - julianday(r.submitted_at)) AS INT)
                   FROM absence_requests r
                   JOIN instructor_modules im ON im.module_code = r.module_code
                   WHERE r.status='pending' AND im.instructor_id=?
                   ORDER BY 5 DESC""", (self.ctx.uid,)).fetchall()
        except sqlite3.Error:
            logger.exception("SLA dashboard fetch failed")
            rows = []
        enriched = [
            (r[0], r[1], r[2], r[3], r[4],
             "BREACH" if r[4] >= 3 else "WARN" if r[4] >= 2 else "OK")
            for r in rows
        ]
        _show_table(self.ctx.parent, "Request SLA (target 3 days)",
                    ("id", "student", "module", "submitted", "age", "status"),
                    enriched)

    # --- #21 ----------------------------------------------------------
    @safe("Route to dept head")
    def route_to_department_head(self) -> None:
        rid = simpledialog.askinteger("Request", "Request id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            admins = self.ctx.db.get_users("admin")
        except Exception:
            logger.exception("admin lookup failed")
            admins = []
        if not admins:
            messagebox.showinfo("No admin", "No admin user to route to.",
                                parent=self.ctx.parent)
            return
        m = {f"{r[3] or r[1]} ({r[1]})": r[0] for r in admins}
        pick = _combo_dialog(self.ctx.parent, "Route to",
                             "Route to:", list(m.keys()))
        if not pick:
            return
        reason = Prompt.non_empty(self.ctx.parent, "Reason",
                                  "Why escalate?", min_len=5)
        if not reason:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_request_route
                   (request_id, routed_to, reason) VALUES (?,?,?)""",
                (rid, m[pick], reason))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("route insert failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.route", "absence_requests", rid,
              f"→{m[pick]}: {reason[:80]}")
        messagebox.showinfo("Routed", f"Routed to {pick}.",
                            parent=self.ctx.parent)
