"""AttendanceDataService — features #1–#7.

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


class AttendanceDataService:
    """Bulk import/export, edit, undo-delete, dedupe, audit, lock past."""

    def __init__(self, ctx: AdminContext, module_picker: ModulePicker
                 ) -> None:
        self.ctx = ctx
        self.module_picker = module_picker

    # --- #1 -----------------------------------------------------------
    @safe("Bulk import")
    def bulk_import_csv(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.ctx.parent,
            filetypes=[("CSV", "*.csv"), ("All", "*.*")])
        if not path:
            return
        if not Path(path).is_file():
            messagebox.showerror("Missing", f"File not found:\n{path}",
                                 parent=self.ctx.parent)
            return
        ok = bad = 0
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                required = {"student_id", "module_code", "date", "status"}
                missing = required - set(reader.fieldnames or [])
                if missing:
                    messagebox.showerror(
                        "Bad header",
                        f"Missing column(s): {', '.join(sorted(missing))}",
                        parent=self.ctx.parent)
                    return
                for row in reader:
                    try:
                        self.ctx.db.record_absence(
                            row["student_id"].strip(),
                            row["module_code"].strip(),
                            row["date"].strip(),
                            row["status"].strip(),
                            (row.get("reason") or "").strip())
                        ok += 1
                    except (sqlite3.Error, KeyError, ValueError) as e:
                        logger.warning("import row %s failed: %s", row, e)
                        bad += 1
            self.ctx.db.conn.commit()
        except OSError as e:
            logger.exception("bulk import open failed path=%s", path)
            messagebox.showerror("Read failed", str(e),
                                 parent=self.ctx.parent)
            return
        audit(self.ctx, "bulk_import", "attendance", "",
              f"ok={ok} bad={bad} file={path}")
        messagebox.showinfo("Import complete",
                            f"Imported {ok} rows. {bad} rejected.",
                            parent=self.ctx.parent)

    # --- #2 -----------------------------------------------------------
    @safe("Bulk export")
    def bulk_export_csv(self) -> None:
        try:
            rows = self.ctx.db.get_absences()
        except Exception:
            logger.exception("bulk_export get_absences failed")
            messagebox.showerror("Error", "Could not load attendance.",
                                 parent=self.ctx.parent)
            return
        headers = ("id", "student", "module_code", "module_name",
                   "date", "status", "reason")
        path = _export_rows_to_csv(rows, headers, self.ctx.parent)
        if path:
            audit(self.ctx, "bulk_export", "attendance", "",
                  f"rows={len(rows)} file={path}")
            messagebox.showinfo("Exported",
                                f"Wrote {len(rows)} rows to:\n{path}",
                                parent=self.ctx.parent)

    # --- #3 -----------------------------------------------------------
    @safe("Edit record")
    def edit_attendance_row(self) -> None:
        rid = simpledialog.askinteger("Edit", "Attendance row id:",
                                      parent=self.ctx.parent)
        if rid is None:
            return
        try:
            old = self.ctx.db.cur.execute(
                "SELECT status, reason FROM attendance WHERE id=?",
                (rid,)).fetchone()
        except sqlite3.Error:
            logger.exception("attendance lookup failed rid=%s", rid)
            messagebox.showerror("Error", "Could not load row.",
                                 parent=self.ctx.parent)
            return
        if not old:
            messagebox.showerror("Not found", f"No row {rid}",
                                 parent=self.ctx.parent)
            return
        valid_statuses = ["present", "absent", "late", "excused"]
        new_status = _combo_dialog(
            self.ctx.parent, "Status",
            f"New status (was {old[0]}):",
            valid_statuses) or old[0]
        new_reason = simpledialog.askstring(
            "Reason", f"New reason (was {old[1] or ''}):",
            parent=self.ctx.parent) or old[1]
        try:
            self.ctx.db.cur.execute(
                "UPDATE attendance SET status=?, reason=? WHERE id=?",
                (new_status, new_reason, rid))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("attendance update failed rid=%s", rid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "edit_record", "attendance", rid,
              f"{old[0]}→{new_status}")
        messagebox.showinfo("Saved", "Record updated.",
                            parent=self.ctx.parent)

    # --- #4 -----------------------------------------------------------
    @safe("Undo delete")
    def undo_recent_deletes(self) -> None:
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT id, deleted_at, deleted_by, original_table, payload
                   FROM abs_tracker_trash WHERE deleted_at >= ?
                   ORDER BY deleted_at DESC""", (cutoff,)).fetchall()
        except sqlite3.Error:
            logger.exception("trash fetch failed")
            messagebox.showerror("Error", "Could not load trash.",
                                 parent=self.ctx.parent)
            return
        if not rows:
            messagebox.showinfo("Trash empty",
                                "Nothing deleted in the last 24h.",
                                parent=self.ctx.parent)
            return

        def restore_selected():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Select", "Pick row(s) to restore.",
                                    parent=win)
                return
            restored = 0
            try:
                for item in sel:
                    v = tree.item(item)["values"]
                    p = json.loads(v[4])
                    self.ctx.db.cur.execute(
                        """INSERT INTO attendance
                           (id, student_id, module_code, date, status, reason)
                           VALUES (?,?,?,?,?,?)""",
                        (p["id"], p["student_id"], p["module_code"],
                         p["date"], p["status"], p["reason"]))
                    self.ctx.db.cur.execute(
                        "DELETE FROM abs_tracker_trash WHERE id=?", (v[0],))
                    restored += 1
                self.ctx.db.conn.commit()
            except (sqlite3.Error, json.JSONDecodeError, KeyError) as e:
                self.ctx.db.conn.rollback()
                logger.exception("undo restore failed")
                messagebox.showerror("Failed", str(e), parent=win)
                return
            audit(self.ctx, "undo_delete", "attendance", "",
                  f"rows={restored}")
            messagebox.showinfo("Restored",
                                f"Restored {restored} row(s).", parent=win)
            win.destroy()

        win, tree = _show_table(
            self.ctx.parent, "Trash (24h)",
            ("id", "deleted_at", "deleted_by", "table", "payload"),
            rows, extra_button=("Restore selected", restore_selected))

    # --- #5 -----------------------------------------------------------
    @safe("Merge duplicates")
    def merge_duplicate_rows(self) -> None:
        try:
            dups = self.ctx.db.cur.execute(
                """SELECT student_id, module_code, date, COUNT(*) c,
                          MIN(id), MAX(id)
                   FROM attendance
                   GROUP BY student_id, module_code, date
                   HAVING c > 1""").fetchall()
        except sqlite3.Error:
            logger.exception("dup scan failed")
            messagebox.showerror("Error", "Could not scan for duplicates.",
                                 parent=self.ctx.parent)
            return
        if not dups:
            messagebox.showinfo("No duplicates",
                                "No duplicate rows found.",
                                parent=self.ctx.parent)
            return
        if not Prompt.confirm(
                self.ctx.parent, "Confirm dedupe",
                f"Found {len(dups)} duplicate group(s).\n"
                "Keep the earliest row per (student, module, date) and "
                "delete the rest?"):
            return
        removed = 0
        try:
            for sid, mod, d, _c, keep_id, _max in dups:
                cur = self.ctx.db.cur.execute(
                    """DELETE FROM attendance
                       WHERE student_id=? AND module_code=? AND date=?
                         AND id<>?""", (sid, mod, d, keep_id))
                removed += cur.rowcount
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("dedupe delete failed")
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "merge_duplicates", "attendance", "",
              f"removed={removed}")
        messagebox.showinfo("Merged",
                            f"Removed {removed} duplicate row(s); "
                            "kept earliest per day.",
                            parent=self.ctx.parent)

    # --- #6 -----------------------------------------------------------
    @safe("Audit log")
    def show_correction_audit(self) -> None:
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ts, username, action, target, target_id, details
                   FROM abs_tracker_audit
                   ORDER BY ts DESC LIMIT 500""").fetchall()
        except sqlite3.Error:
            logger.exception("audit fetch failed")
            rows = []
        _show_table(self.ctx.parent, "Audit log (last 500)",
                    ("when", "user", "action", "target", "target_id", "details"),
                    rows, widths=[150, 120, 140, 100, 100, 380])

    # --- #7 -----------------------------------------------------------
    @safe("Lock past dates")
    def lock_past_dates(self) -> None:
        days = simpledialog.askinteger(
            "Lock past dates",
            "Lock edits to records older than how many days?",
            parent=self.ctx.parent, minvalue=0, maxvalue=3650)
        if days is None:
            return
        days = int(days)  # defensive: enforce integer for the trigger DDL
        try:
            _set_setting(self.ctx.db, "lock_days", days)
            self.ctx.db.cur.executescript(f"""
                DROP TRIGGER IF EXISTS abs_lock_update;
                CREATE TRIGGER abs_lock_update
                BEFORE UPDATE ON attendance
                FOR EACH ROW
                WHEN julianday('now') - julianday(OLD.date) > {days}
                BEGIN
                  SELECT RAISE(ABORT, 'Attendance row older than lock window');
                END;
            """)
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("lock trigger install failed days=%s", days)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "lock_past_dates", "settings", "lock_days", str(days))
        messagebox.showinfo("Locked",
                            f"Records older than {days} day(s) "
                            "are now read-only.",
                            parent=self.ctx.parent)

