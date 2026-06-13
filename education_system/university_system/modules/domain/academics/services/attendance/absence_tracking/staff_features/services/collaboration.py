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

class CollaborationService:
    """Co-teacher grants, TA handoff notes, peer observations."""

    def __init__(self, ctx: StaffContext, picker: ModulePicker,
                 staff_picker: StaffPicker) -> None:
        self.ctx = ctx
        self.picker = picker
        self.staff_picker = staff_picker

    # --- #43 ----------------------------------------------------------
    @safe("Co-teacher")
    def grant_co_teacher_access(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        sp = self.staff_picker.pick("Co-teacher", "Grant to:")
        if not sp:
            return
        co_uid, co_label = sp
        try:
            self.ctx.db.cur.execute(
                """INSERT OR IGNORE INTO abs_tracker_co_teachers
                   (module_code, user_id) VALUES (?,?)""", (mc, co_uid))
            # Mirror into instructor_modules so the rest of the tracker
            # respects the grant.
            self.ctx.db.cur.execute(
                """INSERT OR IGNORE INTO instructor_modules
                   (instructor_id, module_code) VALUES (?,?)""",
                (co_uid, mc))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("co-teacher grant failed mc=%s uid=%s",
                             mc, co_uid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.co_teacher", "abs_tracker_co_teachers",
              mc, str(co_uid))
        messagebox.showinfo("Granted",
                            f"{co_label} can now take roll on {mc}.",
                            parent=self.ctx.parent)

    # --- #44 ----------------------------------------------------------
    @safe("TA handoff")
    def leave_ta_handoff_note(self) -> None:
        picked = self.picker.pick()
        if not picked:
            return
        mc, _ = picked
        sp = self.staff_picker.pick("TA", "TA:")
        if not sp:
            return
        ta_uid, _ = sp
        note = Prompt.non_empty(self.ctx.parent, "Handoff",
                                "Note to TA:", min_len=2)
        if not note:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_ta_handoff
                   (staff_id, ta_id, module_code, note) VALUES (?,?,?,?)""",
                (self.ctx.uid, ta_uid, mc, note))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("ta handoff insert failed mc=%s ta=%s",
                             mc, ta_uid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.ta_handoff", "abs_tracker_ta_handoff",
              mc, note[:80])
        messagebox.showinfo("Saved", "TA handoff saved.",
                            parent=self.ctx.parent)

    # --- #45 ----------------------------------------------------------
    @safe("Peer observation")
    def log_peer_observation(self) -> None:
        sp = self.staff_picker.pick("Observed", "Who did you observe?")
        if not sp:
            return
        sub_uid, _ = sp
        mc = Prompt.non_empty(self.ctx.parent, "Module",
                              "Module code:", min_len=1)
        if not mc:
            return
        d = Prompt.iso_date(self.ctx.parent)
        if not d:
            return
        notes = Prompt.non_empty(self.ctx.parent, "Notes",
                                 "Notes:", min_len=10)
        if not notes:
            return
        try:
            self.ctx.db.cur.execute(
                """INSERT INTO abs_tracker_peer_observations
                   (observer_id, subject_id, module_code, date, notes)
                   VALUES (?,?,?,?,?)""",
                (self.ctx.uid, sub_uid, mc, d, notes))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("peer obs insert failed sub=%s mc=%s",
                             sub_uid, mc)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "staff.peer_obs", "abs_tracker_peer_observations",
              sub_uid, f"{mc} {d}")
        messagebox.showinfo("Saved", "Peer observation recorded.",
                            parent=self.ctx.parent)
