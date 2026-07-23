"""DiagnosticsService — features #47–#50.

Sliced verbatim from the original admin_features.py during the package split.
"""
from __future__ import annotations

import csv
import json
import sqlite3
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Optional

from ..context import AdminContext, audit, logger, safe
from ..export_email import (
    _email_admin,
    _export_rows_to_csv,
    _report_window,
    _rows_to_pdf,
    _rows_to_txt,
)
from ..support_tables import _get_setting, _set_setting
from ..ui_dialogs import (
    ModulePicker,
    Prompt,
    StudentPicker,
    _combo_dialog,
    _pick_module,
    _pick_student,
    _show_table,
    pick_date,
    pick_date_range,
)


class DiagnosticsService:
    """Orphan rows, missing sessions, enrolment mismatch, DB health."""

    def __init__(self, ctx: AdminContext) -> None:
        self.ctx = ctx

    # --- #47 ----------------------------------------------------------
    @safe("Orphan rows")
    def show_orphan_attendance_rows(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.id, a.student_id, a.module_code, a.date,
                          CASE WHEN s.student_id IS NULL THEN 'missing student'
                               ELSE '' END,
                          CASE WHEN m.module_code IS NULL THEN 'missing module'
                               ELSE '' END
                   FROM attendance a
                   LEFT JOIN students s ON s.student_id = a.student_id
                   LEFT JOIN modules m  ON m.module_code = a.module_code
                   WHERE s.student_id IS NULL OR m.module_code IS NULL
                   ORDER BY a.date DESC""").fetchall()
        except sqlite3.Error:
            logger.exception("orphan scan failed")
            rows = []
        _show_table(self.ctx.parent, f"Orphan rows ({len(rows)})",
                    ("id", "student_id", "module_code", "date",
                     "student?", "module?"), rows)
        audit(self.ctx, "orphan_scan", "attendance", "", f"n={len(rows)}")

    # --- #48 ----------------------------------------------------------
    @safe("Missing sessions")
    def show_modules_without_attendance(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ms.module_code, ms.day_of_week, ms.start_time,
                          ms.semester
                   FROM module_schedule ms
                   LEFT JOIN attendance a ON a.module_code = ms.module_code
                   WHERE a.id IS NULL
                   ORDER BY ms.module_code""").fetchall()
        except sqlite3.Error:
            logger.exception("missing sessions query failed")
            rows = []
        _show_table(
            self.ctx.parent,
            f"Modules with scheduled sessions but no attendance ({len(rows)})",
            ("module", "day", "start", "semester"), rows)

    # --- #49 ----------------------------------------------------------
    @safe("Enrollment mismatch")
    def show_enrollment_mismatches(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT a.id, a.student_id, a.module_code, a.date
                   FROM attendance a
                   LEFT JOIN student_modules sm
                     ON sm.student_id = a.student_id
                    AND sm.module_code = a.module_code
                   WHERE sm.id IS NULL
                   ORDER BY a.date DESC""").fetchall()
        except sqlite3.Error:
            logger.exception("enrolment mismatch query failed")
            rows = []
        _show_table(self.ctx.parent,
                    f"Enrollment mismatches ({len(rows)})",
                    ("id", "student", "module", "date"), rows)
        audit(self.ctx, "enrollment_mismatch", "attendance", "",
              f"n={len(rows)}")

    # --- #50 ----------------------------------------------------------
    @safe("DB health")
    def show_database_health(self) -> None:
        stats: list[tuple] = []
        for t in ("attendance", "absence_requests", "students", "modules",
                  "student_modules", "instructor_modules", "users",
                  "abs_tracker_audit", "abs_tracker_trash"):
            try:
                n = self.ctx.db.cur.execute(
                    f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                stats.append((t, n, "ok"))
            except sqlite3.Error as e:
                logger.exception("count failed table=%s", t)
                stats.append((t, "?", str(e)))
        try:
            integrity = self.ctx.db.cur.execute(
                "PRAGMA integrity_check").fetchone()[0]
            journal = self.ctx.db.cur.execute(
                "PRAGMA journal_mode").fetchone()[0]
            page_size = self.ctx.db.cur.execute(
                "PRAGMA page_size").fetchone()[0]
            page_count = self.ctx.db.cur.execute(
                "PRAGMA page_count").fetchone()[0]
            size_mb = (page_size * page_count) / 1_048_576
        except sqlite3.Error:
            logger.exception("PRAGMA query failed")
            integrity = journal = "?"
            size_mb = 0.0
        stats.append(("integrity_check", integrity, ""))
        stats.append(("journal_mode", journal, ""))
        stats.append(("size_mb", f"{size_mb:.2f}", ""))
        stats.append(("db_path", getattr(self.ctx.db, "path", "?"), ""))
        _show_table(self.ctx.parent, "Database health",
                    ("metric", "value", "note"), stats,
                    widths=[220, 500, 200])
        audit(self.ctx, "db_health", "db", "",
              f"size_mb={size_mb:.2f}")

