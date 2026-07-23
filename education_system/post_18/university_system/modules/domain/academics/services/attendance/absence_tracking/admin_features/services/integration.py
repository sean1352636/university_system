"""IntegrationService — features #31–#37.

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
from .reporting import _parents_of


class IntegrationService:
    """Calendar, schedule, risk feed, grade/wellbeing/discipline/finance."""

    def __init__(self, ctx: AdminContext, student_picker: StudentPicker,
                 module_picker: ModulePicker) -> None:
        self.ctx = ctx
        self.student_picker = student_picker
        self.module_picker = module_picker

    # --- #31 ----------------------------------------------------------
    @safe("Calendar link")
    def show_upcoming_calendar_events(self) -> None:
        # (4) Two-sided window: past events explain absences, future events
        # are useful for planning. Defaults remembered via _get_setting so
        # the user doesn't keep re-typing.
        try:
            back_default = int(_get_setting(
                self.ctx.db, "calendar_link_lookback", "30"))
        except (TypeError, ValueError):
            back_default = 30
        try:
            ahead_default = int(_get_setting(
                self.ctx.db, "calendar_link_lookahead", "30"))
        except (TypeError, ValueError):
            ahead_default = 30
        back = simpledialog.askinteger(
            "Window", "Look back how many days?",
            parent=self.ctx.parent, initialvalue=back_default)
        if back is None:
            return
        ahead = simpledialog.askinteger(
            "Window", "Look ahead how many days?",
            parent=self.ctx.parent, initialvalue=ahead_default)
        if ahead is None:
            return
        try:
            _set_setting(self.ctx.db, "calendar_link_lookback", back)
            _set_setting(self.ctx.db, "calendar_link_lookahead", ahead)
        except sqlite3.Error:
            pass

        start = (date.today() - timedelta(days=back)).isoformat()
        end = (date.today() + timedelta(days=ahead)).isoformat()
        try:
            # (3) Per-row absence count: makes it obvious which calendar
            # entries (e.g. an unmarked holiday or trip day) are driving
            # absence spikes. Correlated subquery keeps the query simple.
            rows = self.ctx.db.cur.execute(
                """SELECT e.date, e.name, e.event_type,
                          COALESCE(
                            (SELECT COUNT(*) FROM attendance a
                             WHERE a.date = e.date
                               AND a.status = 'absent'),
                            0) AS abs_count
                   FROM academic_calendar_events e
                   WHERE e.date BETWEEN ? AND ?
                   ORDER BY e.date""", (start, end)).fetchall()
        except sqlite3.Error:
            logger.exception("calendar fetch failed")
            rows = []

        def _selected():
            try:
                sel = tree.selection()
                if not sel:
                    return None
                vals = tree.item(sel[0], "values")
                # (date, name, type, abs_count)
                return vals
            except Exception:
                return None

        def _open_calendar_gui():
            sel = _selected()
            iso_date = sel[0] if sel else None
            try:
                from education_system.post_18.university_system.modules.domain.academics.gui.academic_calendar.main_gui import (  # noqa: E501
                    CalendarGUI,
                )
                win2 = tk.Toplevel(self.ctx.parent)
                win2.title(f"Academic Calendar — {iso_date}" if iso_date
                           else "Academic Calendar")
                win2.geometry("1400x900")
                gui = CalendarGUI(auth_manager=getattr(self.ctx, "auth", None),
                                  parent_window=win2)
                if iso_date and hasattr(gui, "navigate_to_date"):
                    try:
                        gui.navigate_to_date(iso_date)
                    except Exception:
                        logger.exception("calendar navigate_to_date failed")
            except Exception:
                logger.exception("could not open Academic Calendar GUI")
                messagebox.showerror(
                    "Academic Calendar",
                    "Could not open the Academic Calendar GUI (see log).",
                    parent=self.ctx.parent)

        def _show_absences_on_day():
            # (1) Reverse direction: show attendance rows on the selected
            # event's date, so the calendar is also a diagnostic surface.
            sel = _selected()
            if not sel:
                messagebox.showinfo(
                    "Absences on day", "Select a calendar row first.",
                    parent=self.ctx.parent)
                return
            iso_date = sel[0]
            try:
                abs_rows = self.ctx.db.cur.execute(
                    """SELECT a.student_id, a.module_code, a.status,
                              COALESCE(a.reason, '')
                       FROM attendance a
                       WHERE a.date = ?
                       ORDER BY a.status, a.module_code, a.student_id""",
                    (iso_date,)).fetchall()
            except sqlite3.Error:
                logger.exception("absences-on-day query failed date=%s",
                                 iso_date)
                abs_rows = []
            _show_table(
                self.ctx.parent,
                f"Attendance on {iso_date} ({sel[1]})",
                ("student", "module", "status", "reason"),
                abs_rows, widths=[120, 160, 100, 380])

        def _auto_excuse_for_event():
            # (2) Inline auto-excuse for the selected event's date+type:
            # avoids hopping to feature #17 to do the same job. We update
            # only attendance rows whose date matches the event so we
            # don't accidentally excuse unrelated days that happen to
            # share an event_type elsewhere in the window.
            sel = _selected()
            if not sel:
                messagebox.showinfo(
                    "Auto-excuse", "Select a calendar row first.",
                    parent=self.ctx.parent)
                return
            iso_date, ev_name, ev_type = sel[0], sel[1], sel[2]
            if not ev_type:
                messagebox.showinfo(
                    "Auto-excuse",
                    "Selected event has no event_type to match.",
                    parent=self.ctx.parent)
                return
            if not Prompt.confirm(
                    self.ctx.parent, "Confirm auto-excuse",
                    f"Auto-excuse all absences on {iso_date} for "
                    f"event '{ev_name}' (type='{ev_type}')?\n\n"
                    f"Also adds '{ev_type}' to the standing auto-excuse "
                    f"rules so future entries on these days are handled "
                    f"the same way."):
                return
            try:
                # Standing rule (idempotent).
                self.ctx.db.cur.execute(
                    """INSERT OR IGNORE INTO abs_tracker_auto_excuse_rules
                       (event_type) VALUES (?)""", (ev_type,))
                cur = self.ctx.db.cur.execute(
                    """UPDATE attendance
                       SET status='excused',
                           reason='auto: '||?
                       WHERE date=? AND status='absent'""",
                    (ev_type, iso_date))
                updated = cur.rowcount
                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception(
                    "inline auto-excuse failed date=%s ev=%s",
                    iso_date, ev_type)
                messagebox.showerror("Failed", str(e),
                                     parent=self.ctx.parent)
                return
            audit(self.ctx, "auto_excuse_inline", "attendance",
                  iso_date, f"ev_type={ev_type} updated={updated}")
            # Reflect new (zero) absence count in the calendar table.
            try:
                node = tree.selection()[0]
                vals = list(tree.item(node, "values"))
                if len(vals) >= 4:
                    vals[3] = "0"
                    tree.item(node, values=vals)
            except Exception:
                pass
            messagebox.showinfo(
                "Auto-excused",
                f"Excused {updated} absence(s) on {iso_date}.",
                parent=self.ctx.parent)

        win, tree = _show_table(
            self.ctx.parent, f"Calendar ({start} → {end})",
            ("date", "name", "type", "absences"), rows,
            widths=[110, 440, 130, 90],
            extra_button=("📅  Open Academic Calendar GUI (selected date)",
                          _open_calendar_gui))

        # Secondary action bar — keeps the calendar GUI link as the
        # primary call-to-action while still surfacing the attendance
        # diagnostic + inline auto-excuse.
        extra = tk.Frame(win)
        extra.pack(side="bottom", fill="x")
        tk.Button(extra, text="🔍  Show absences on this day",
                  command=_show_absences_on_day,
                  bg="#0ea5e9", fg="white", relief="flat",
                  padx=10, pady=4).pack(side="left", padx=10, pady=4)
        tk.Button(extra, text="✅  Auto-excuse absences for this event",
                  command=_auto_excuse_for_event,
                  bg="#16a34a", fg="white", relief="flat",
                  padx=10, pady=4).pack(side="left", padx=4, pady=4)

        tree.bind("<Double-1>", lambda _e: _open_calendar_gui())

    # --- #32 ----------------------------------------------------------
    _DAY_NAME_TO_WEEKDAY = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }

    @safe("Pre-generate sessions")
    def show_module_schedule(self) -> None:
        mc = self.module_picker.pick("Sessions for which module?")
        if not mc:
            return
        rows = self._fetch_module_schedule_with_attendance(mc)

        def _open_scheduling_gui(schedule_id: Optional[int] = None) -> None:
            """Launch ModuleSchedulingGUI in a new Toplevel, scoped to this module.

            If ``schedule_id`` is provided, jumps straight to EditScheduleDialog
            for that row instead of just filtering the Schedules tab.
            """
            try:
                from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.main_gui import (
                    ModuleSchedulingGUI,
                )
            except Exception as e:
                logger.exception("module scheduling GUI import failed")
                messagebox.showerror("Module Scheduling",
                                     f"Could not open scheduling GUI: {e}",
                                     parent=self.ctx.parent)
                return
            top = tk.Toplevel(self.ctx.parent)
            top.title(f"Module Scheduling — {mc}")
            try:
                gui = ModuleSchedulingGUI(top)
                auth = getattr(self.ctx, "auth", None)
                if auth is not None and hasattr(gui, "set_auth"):
                    try:
                        gui.set_auth(auth)
                    except Exception:
                        logger.exception("set_auth on scheduling GUI failed")
                try:
                    gui.notebook.select(1)
                except Exception:
                    pass
                try:
                    gui.schedule_search_var.set(mc)
                except Exception:
                    pass
                # (#5) If the caller picked a specific schedule row, open its
                # EditScheduleDialog so they're editing the row they clicked.
                if schedule_id is not None:
                    try:
                        from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.dialogs import (
                            EditScheduleDialog,
                        )
                        EditScheduleDialog(top, gui.scheduler,
                                           int(schedule_id), gui=gui)
                    except Exception:
                        logger.exception("EditScheduleDialog launch failed sid=%s",
                                         schedule_id)
            except Exception as e:
                logger.exception("module scheduling GUI launch failed")
                messagebox.showerror("Module Scheduling", str(e), parent=top)

        def _open_add_schedule_dialog() -> None:
            """(#3) Empty-state shortcut: open AddScheduleDialog directly."""
            try:
                from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.main_gui import (
                    ModuleSchedulingGUI,
                )
                from education_system.post_18.university_system.modules.domain.academics.gui.module_scheduling.dialogs import (
                    AddScheduleDialog,
                )
                from education_system.post_18.university_system.modules.domain.academics.services.module_scheduling import (
                    ModuleScheduler,
                )
            except Exception as e:
                logger.exception("AddScheduleDialog import failed")
                messagebox.showerror("Module Scheduling", str(e),
                                     parent=self.ctx.parent)
                return
            try:
                AddScheduleDialog(self.ctx.parent, ModuleScheduler(), gui=None)
            except Exception as e:
                logger.exception("AddScheduleDialog launch failed")
                messagebox.showerror("Module Scheduling", str(e),
                                     parent=self.ctx.parent)
                return
            # Refresh the popup so newly added rows appear.
            try:
                _refresh()
            except Exception:
                pass

        def _pregenerate() -> None:
            """(#1) Materialise individual session dates from the schedule rows.

            Writes to ``module_sessions`` (separate from ``attendance`` so we
            don't pollute roll-call data with placeholder rows).
            """
            rng = pick_date_range(self.ctx.parent,
                                  "Pre-generate sessions")
            if not rng:
                return
            start, end = rng
            n = self._pregenerate_module_sessions(mc, start, end)
            messagebox.showinfo(
                "Pre-generated",
                f"Generated {n} session date(s) for {mc} between {start} and {end}.",
                parent=self.ctx.parent,
            )
            # Refresh so the attended overlay reflects any side effects.
            try:
                _refresh()
            except Exception:
                pass

        def _populate(tree, rows):
            for r in tree.get_children():
                tree.delete(r)
            tree.tag_configure("ghost", background="#fee2e2",
                               foreground="#991b1b")
            for r in rows:
                sid, day, st, en, room, instr, sem, yr, status, attended = r
                tags = ("ghost",) if (attended or 0) == 0 else ()
                # Use the schedule_id as the tree item iid so the double-click
                # handler can recover it cheaply.
                tree.insert("", "end", iid=str(sid),
                            values=(day, st, en, room, instr, sem, yr,
                                    status, attended),
                            tags=tags)

        def _refresh():
            new_rows = self._fetch_module_schedule_with_attendance(mc)
            _populate(tree, new_rows)
            empty_label_var.set(
                "" if new_rows else
                f"No schedule rows yet for {mc}. Use “Add schedule…” to create one."
            )

        win, tree = _show_table(
            self.ctx.parent, f"Scheduled sessions for {mc}",
            ("day", "start", "end", "room", "instructor",
             "sem", "yr", "status", "attended"),
            [],  # filled by _populate below so iids are set
            extra_button=("Open in Module Scheduling GUI",
                          lambda: _open_scheduling_gui(None)),
        )
        _populate(tree, rows)

        # (#5) Double-click → edit *that* row. Falls back to whole-module
        # filter view if we can't recover an id.
        def _on_double(_e):
            sel = tree.selection()
            if not sel:
                return
            try:
                sid = int(sel[0])
            except (TypeError, ValueError):
                sid = None
            _open_scheduling_gui(sid)
        tree.bind("<Double-1>", _on_double)

        # Extra button row: pre-generate + add-schedule shortcut. Packed with
        # side="bottom" so it sits above the Close button frame from _show_table.
        extra_btns = tk.Frame(win)
        extra_btns.pack(fill="x", pady=(0, 4), side="bottom")
        tk.Button(extra_btns, text="Pre-generate sessions…",
                  command=_pregenerate, bg="#0ea5e9", fg="white",
                  relief="flat", padx=10, pady=4).pack(side="left", padx=10)
        tk.Button(extra_btns, text="Add schedule…",
                  command=_open_add_schedule_dialog, bg="#10b981",
                  fg="white", relief="flat", padx=10, pady=4).pack(side="left",
                                                                    padx=4)

        # (#3) Empty-state hint.
        empty_label_var = tk.StringVar(value="")
        tk.Label(win, textvariable=empty_label_var, fg="#6b7280",
                 anchor="w", padx=10, pady=4).pack(fill="x", side="bottom")
        if not rows:
            empty_label_var.set(
                f"No schedule rows yet for {mc}. Use “Add schedule…” to create one."
            )

    # ---- helpers for #1 / #4 ----------------------------------------------
    def _fetch_module_schedule_with_attendance(self, mc):
        """Return schedule rows for ``mc`` annotated with an attendance count.

        ``attended_n`` counts attendance rows whose date's weekday matches
        the schedule slot's ``day_of_week`` (stored as a name in this DB —
        Monday-Friday). Used to flag "ghost" slots that have never seen a roll.
        """
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT ms.id, ms.day_of_week, ms.start_time, ms.end_time,
                          ms.room_id, ms.instructor_id, ms.semester,
                          ms.year, ms.status,
                          (SELECT COUNT(*) FROM attendance a
                           WHERE a.module_code = ms.module_code
                             AND LOWER(ms.day_of_week) = LOWER(
                               CASE strftime('%w', a.date)
                                 WHEN '0' THEN 'Sunday'
                                 WHEN '1' THEN 'Monday'
                                 WHEN '2' THEN 'Tuesday'
                                 WHEN '3' THEN 'Wednesday'
                                 WHEN '4' THEN 'Thursday'
                                 WHEN '5' THEN 'Friday'
                                 WHEN '6' THEN 'Saturday'
                               END)) AS attended_n
                   FROM module_schedule ms
                   WHERE ms.module_code = ?
                   ORDER BY ms.day_of_week, ms.start_time""",
                (mc,),
            ).fetchall()
            return rows
        except sqlite3.Error:
            logger.exception("schedule fetch failed mc=%s", mc)
            return []

    def _pregenerate_module_sessions(self, mc, start, end) -> int:
        """Expand schedule rows into ``module_sessions`` for the date range.

        Idempotent — UNIQUE(module_code, date, start_time) means re-running
        with overlapping ranges silently skips already-generated dates.
        Returns the number of newly inserted session dates.
        """
        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS module_sessions (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       module_code TEXT NOT NULL,
                       schedule_id INTEGER,
                       date TEXT NOT NULL,
                       start_time TEXT,
                       end_time TEXT,
                       generated_at TEXT DEFAULT (datetime('now')),
                       UNIQUE (module_code, date, start_time)
                   )"""
            )
            sched = self.ctx.db.cur.execute(
                "SELECT id, day_of_week, start_time, end_time "
                "FROM module_schedule WHERE module_code = ?",
                (mc,),
            ).fetchall()
        except sqlite3.Error:
            logger.exception("pre-generate schedule fetch failed mc=%s", mc)
            return 0
        if not sched:
            messagebox.showinfo(
                "No schedule",
                f"{mc} has no schedule rows to expand.",
                parent=self.ctx.parent,
            )
            return 0
        try:
            s = datetime.strptime(start, "%Y-%m-%d").date()
            e = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Bad dates",
                                 "Pre-generate dates were not in YYYY-MM-DD form.",
                                 parent=self.ctx.parent)
            return 0
        inserted = 0
        try:
            cur_d = s
            while cur_d <= e:
                weekday = cur_d.weekday()  # Mon=0 .. Sun=6
                for sid, dow, start_time, end_time in sched:
                    expected = self._DAY_NAME_TO_WEEKDAY.get(
                        (dow or "").strip().lower())
                    if expected != weekday:
                        continue
                    self.ctx.db.cur.execute(
                        "INSERT OR IGNORE INTO module_sessions "
                        "(module_code, schedule_id, date, start_time, end_time) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (mc, sid, cur_d.isoformat(), start_time, end_time),
                    )
                    if self.ctx.db.cur.rowcount:
                        inserted += 1
                cur_d += timedelta(days=1)
            self.ctx.db.conn.commit()
        except sqlite3.Error:
            self.ctx.db.conn.rollback()
            logger.exception("pre-generate write failed mc=%s", mc)
            return 0
        audit(self.ctx, "pregenerate", "module_sessions", mc,
              f"{start}..{end} n={inserted}")
        return inserted

    # --- #33 ----------------------------------------------------------
    @safe("Risk feed")
    def feed_student_risk_assessment(self, quiet: bool = False) -> None:
        """Refresh the student_risk_assessment feed.

        ``quiet=True`` suppresses dialogs and the result table so this
        can be invoked from a scheduled-reports / cron pipeline. Admin
        email on new HIGH crossings still fires in quiet mode.
        """
        today = date.today().isoformat()
        cutoff_60 = (date.today() - timedelta(days=60)).isoformat()

        # (2) Min-attendance-count guard so a student with a single
        # tardy record doesn't get scored at "100 risk" off one row.
        try:
            min_count = int(_get_setting(self.ctx.db,
                                         "risk_min_count", "5"))
        except (TypeError, ValueError):
            min_count = 5

        # (4) Blended signals: attendance %, recent failed grades,
        # pending absence requests. One query so we touch each table
        # exactly once.
        try:
            rows = self.ctx.db.cur.execute(
                """SELECT s.student_id,
                          COALESCE(att.pct, 0)   AS pct,
                          COALESCE(att.cnt, 0)   AS cnt,
                          COALESCE(g.fails, 0)   AS recent_fails,
                          COALESCE(r.pending, 0) AS pending_reqs
                   FROM students s
                   LEFT JOIN (
                       SELECT student_id,
                              SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                                  * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct,
                              COUNT(*) AS cnt
                       FROM attendance GROUP BY student_id
                   ) att ON att.student_id = s.student_id
                   LEFT JOIN (
                       SELECT student_id, COUNT(*) AS fails
                       FROM grades
                       WHERE submission_date >= ?
                         AND (score < 50
                              OR letter_grade IN ('F','D-','D'))
                       GROUP BY student_id
                   ) g ON g.student_id = s.student_id
                   LEFT JOIN (
                       SELECT student_id, COUNT(*) AS pending
                       FROM absence_requests
                       WHERE status='pending'
                       GROUP BY student_id
                   ) r ON r.student_id = s.student_id""",
                (cutoff_60,)).fetchall()
        except sqlite3.Error:
            logger.exception("risk feed read failed")
            if not quiet:
                messagebox.showerror("Error", "Could not read attendance.",
                                     parent=self.ctx.parent)
            return

        # written rows: (sid, level, score, prev_score, delta, cnt,
        #                fails, pending)
        written: list[tuple] = []
        skipped_dupe = 0
        skipped_insufficient = 0
        new_high: list[tuple] = []
        model_tag = "attendance_blend_v1"

        try:
            for sid, pct, cnt, fails, pending in rows:
                if cnt < min_count:
                    skipped_insufficient += 1
                    continue

                # Score: attendance is primary, fails and pending nudge
                # the score upward without dominating it. Capped [0,100].
                base = 100.0 - float(pct or 0)
                score = (base
                         + min(20.0, 5.0 * float(fails or 0))
                         + min(10.0, 2.0 * float(pending or 0)))
                score = round(max(0.0, min(100.0, score)), 2)
                level = ("high" if score >= 30
                         else "medium" if score >= 15
                         else "low")

                # (3) Pull the most recent prior row for this student so
                # we can compute Δ and detect new HIGH crossings.
                prior = self.ctx.db.cur.execute(
                    """SELECT risk_score, risk_level, assessment_date
                       FROM student_risk_assessment
                       WHERE student_id=?
                       ORDER BY assessment_date DESC, id DESC LIMIT 1""",
                    (sid,)).fetchone()
                prev_score = prior[0] if prior else None
                prev_level = prior[1] if prior else None
                prev_date = prior[2] if prior else None

                # (1) Dedupe: if today's row already matches, leave it
                # alone. If today's exists but score moved, UPDATE in
                # place rather than appending another duplicate row.
                if (prev_date == today
                        and prev_score is not None
                        and abs(prev_score - score) < 0.005):
                    skipped_dupe += 1
                elif prev_date == today:
                    self.ctx.db.cur.execute(
                        """UPDATE student_risk_assessment
                           SET risk_score=?, risk_level=?,
                               prediction_model=?, confidence=?
                           WHERE student_id=? AND assessment_date=?""",
                        (score, level, model_tag, 0.85, sid, today))
                else:
                    self.ctx.db.cur.execute(
                        """INSERT INTO student_risk_assessment
                           (student_id, risk_score, risk_level,
                            assessment_date, prediction_model, confidence)
                           VALUES (?,?,?,?,?,?)""",
                        (sid, score, level, today, model_tag, 0.85))

                delta = (round(score - prev_score, 2)
                         if prev_score is not None else None)
                written.append((sid, level, score, prev_score, delta,
                                cnt, fails, pending))

                if level == "high" and prev_level != "high":
                    new_high.append((sid, prev_level, level, score))

            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("risk feed write failed")
            if not quiet:
                messagebox.showerror("Failed", str(e),
                                     parent=self.ctx.parent)
            return

        audit(self.ctx, "risk_feed", "student_risk_assessment", "",
              f"written={len(written) - skipped_dupe} "
              f"dupes={skipped_dupe} "
              f"insufficient={skipped_insufficient} "
              f"new_high={len(new_high)} model={model_tag}")

        # (5) Email admins on HIGH crossings — fires in both interactive
        # and quiet mode so a scheduled run still alerts the team.
        if new_high:
            body = "Newly high-risk students from today's attendance feed:\n\n" + "\n".join(
                f"{sid}: {prev or 'n/a'} → {new} (score {sc:.1f})"
                for sid, prev, new, sc in new_high
            )
            try:
                _email_admin(
                    self.ctx.db,
                    f"[Risk feed] {len(new_high)} student(s) crossed into HIGH",
                    body,
                    sender_username=getattr(self.ctx, "username", "") or "")
            except Exception:
                logger.exception("admin notify failed")

        if quiet:
            return

        # ---- Interactive presentation -----------------------------------
        level_rank = {"high": 0, "medium": 1, "low": 2}
        written.sort(key=lambda r: (level_rank.get(r[1], 9), -r[2]))

        def _row_passes(level: str, current_filter: str) -> bool:
            if current_filter == "all":
                return True
            if current_filter == "high+medium":
                return level in ("high", "medium")
            return level == current_filter

        def _format(rows_iter):
            out = []
            for sid, level, score, prev, delta, cnt, fails, pending in rows_iter:
                if delta is None:
                    delta_s = "—"
                else:
                    delta_s = f"{'+' if delta >= 0 else ''}{delta:.1f}"
                out.append((sid, level, f"{score:.2f}",
                            "—" if prev is None else f"{prev:.2f}",
                            delta_s, str(cnt), str(fails), str(pending)))
            return out

        # (2) Default the filter to high+medium if any exist — matches
        # how an admin actually wants to triage the table.
        initial_filter = ("high+medium"
                          if any(r[1] in ("high", "medium")
                                 for r in written)
                          else "all")

        def _selected_sid():
            try:
                sel = tree.selection()
                if not sel:
                    return None
                vals = tree.item(sel[0], "values")
                return vals[0] if vals else None
            except Exception:
                return None

        def _open_risk_gui():
            # Drive the AnalyticsManager directly with a minimal shim so
            # we get the per-student risk report Toplevel WITHOUT
            # launching the full Grade Management GUI behind it.
            sid = _selected_sid()
            try:
                from types import SimpleNamespace
                from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.analytics_manager.manager import (  # noqa: E501
                    AnalyticsManager,
                )
                shim = SimpleNamespace(
                    root=self.ctx.parent,
                    auth=getattr(self.ctx, "auth", None),
                    conn=None,
                    layout=None,
                )
                analytics = AnalyticsManager(shim)
                if sid and hasattr(analytics,
                                   "_perform_detailed_risk_assessment"):
                    analytics._perform_detailed_risk_assessment(sid)
                elif hasattr(analytics, "student_risk_assessment"):
                    analytics.student_risk_assessment()
            except Exception:
                logger.exception("could not open Student Risk report")
                messagebox.showerror(
                    "Student Risk",
                    "Could not open the Student Risk report (see log).",
                    parent=self.ctx.parent)

        title = (f"Risk feed ({today}) — "
                 f"{len(written) - skipped_dupe} updated, "
                 f"{skipped_dupe} unchanged, "
                 f"{skipped_insufficient} skipped (<{min_count} records)")
        win, tree = _show_table(
            self.ctx.parent, title,
            ("student", "risk_level", "score", "prev", "Δ",
             "att_count", "recent_fails", "pending_reqs"),
            _format(r for r in written
                    if _row_passes(r[1], initial_filter)),
            widths=[120, 100, 80, 80, 60, 90, 110, 110],
            extra_button=("🧠  Open Student Risk Assessment (selected)",
                          _open_risk_gui))
        tree.bind("<Double-1>", lambda _e: _open_risk_gui())

        # (2) Filter combobox above the Close button.
        bar = tk.Frame(win)
        bar.pack(side="bottom", fill="x")
        tk.Label(bar, text="Filter:").pack(side="left", padx=8, pady=4)
        filter_var = tk.StringVar(value=initial_filter)
        filt = ttk.Combobox(
            bar, textvariable=filter_var, state="readonly",
            values=["all", "high+medium", "high", "medium", "low"],
            width=14)
        filt.pack(side="left", pady=4)

        def _apply_filter(_e=None):
            current = filter_var.get()
            for child in tree.get_children():
                tree.delete(child)
            for tup in _format(r for r in written
                               if _row_passes(r[1], current)):
                tree.insert("", "end", values=tup)

        filt.bind("<<ComboboxSelected>>", _apply_filter)

        if new_high:
            tk.Label(
                win,
                text=f"⚠ {len(new_high)} student(s) crossed into HIGH "
                     f"since previous run — admins notified.",
                fg="#b91c1c", anchor="w", padx=10, pady=4
            ).pack(side="bottom", fill="x")

    # --- #34 ----------------------------------------------------------
    @safe("Grade link")
    def show_grade_penalty_candidates(self) -> None:
        # (4) Pull default threshold from settings, ask user, persist back.
        try:
            saved = float(_get_setting(self.ctx.db,
                                       "grade_penalty_threshold", "50"))
        except (TypeError, ValueError):
            saved = 50.0
        threshold = simpledialog.askfloat(
            "Threshold", "Penalty below %:",
            parent=self.ctx.parent, initialvalue=saved) or saved
        try:
            _set_setting(self.ctx.db, "grade_penalty_threshold", threshold)
        except sqlite3.Error:
            pass  # already logged

        try:
            # (3) Left join with attendance_grade_penalties so we can
            # surface which candidates already had a penalty applied and
            # avoid double-penalising on re-runs.
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id, a.module_code, a.pct,
                          CASE WHEN p.id IS NULL THEN '' ELSE '✓' END AS applied
                   FROM (
                       SELECT student_id, module_code,
                              SUM(CASE WHEN status='present' THEN 1 ELSE 0 END)
                                  * 1.0 / NULLIF(COUNT(*),0) * 100 AS pct
                       FROM attendance
                       GROUP BY student_id, module_code
                   ) a
                   LEFT JOIN attendance_grade_penalties p
                       ON p.student_id = a.student_id
                      AND p.module_code = a.module_code
                   WHERE a.pct IS NOT NULL AND a.pct < ?
                   ORDER BY a.pct ASC""",
                (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("grade link failed")
            rows = []

        def _selected_row():
            try:
                sel = tree.selection()
                if not sel:
                    return None
                vals = tree.item(sel[0], "values")
                return (vals[0], vals[1], float(vals[2]),
                        vals[3] if len(vals) > 3 else "")
            except Exception:
                return None

        def _open_grade_manager():
            row = _selected_row()
            sid = row[0] if row else None
            module = row[1] if row else None
            pct = row[2] if row else None
            try:
                from education_system.post_18.university_system.modules.domain.academics.gui.grade_tracking.grade_tracking_app import (  # noqa: E501
                    GradeTrackingApp,
                )
                win = tk.Toplevel(self.ctx.parent)
                win.title(f"Grade Management — {sid}" if sid
                          else "Grade Management")
                win.geometry("1200x750")
                app = GradeTrackingApp(win, auth=getattr(self.ctx, "auth", None))
                # (1) If a row was selected, jump straight into Add Grade
                # with the student/module/comments pre-filled.
                if sid and hasattr(app, "grades") and hasattr(
                        app.grades, "add_grade_dialog"):
                    comments = (f"Attendance penalty: {pct:.1f}% < "
                                f"{threshold:.0f}% threshold") if pct else None
                    try:
                        app.grades.add_grade_dialog(
                            prefill_student_id=sid,
                            prefill_module_code=module,
                            prefill_comments=comments)
                    except TypeError:
                        # Older signature — fall back to plain dialog.
                        app.grades.add_grade_dialog()
            except Exception:
                logger.exception("could not open Grade Management GUI")
                messagebox.showerror(
                    "Grade Management",
                    "Could not open the Grade Management GUI (see log).",
                    parent=self.ctx.parent)

        def _apply_penalty():
            # (2) One-click standard penalty: insert a 0-score grade row
            # against a synthetic "Attendance penalty" assessment, record
            # in attendance_grade_penalties, audit, and notify parents.
            row = _selected_row()
            if not row:
                messagebox.showinfo(
                    "Apply penalty", "Select a candidate row first.",
                    parent=self.ctx.parent)
                return
            sid, module, pct, applied = row
            if applied == "✓":
                messagebox.showinfo(
                    "Already applied",
                    f"A penalty has already been recorded for "
                    f"{sid} / {module}.", parent=self.ctx.parent)
                return
            if not Prompt.confirm(
                    self.ctx.parent, "Confirm penalty",
                    f"Record an attendance penalty for {sid} on "
                    f"{module} (current attendance {pct:.1f}%)?\n\n"
                    f"This inserts a 0-score grade row and notifies "
                    f"linked parents."):
                return
            cur = self.ctx.db.cur
            try:
                # Find or create the synthetic per-module penalty assessment.
                aid_row = cur.execute(
                    """SELECT assessment_id FROM assessments
                       WHERE module_code=? AND assessment_type='attendance_penalty'
                       LIMIT 1""", (module,)).fetchone()
                if aid_row:
                    assessment_id = aid_row[0]
                else:
                    cur.execute(
                        """INSERT INTO assessments
                           (assessment_name, assessment_type, module_code,
                            max_points, weight, description)
                           VALUES (?, 'attendance_penalty', ?,
                                   100, 0,
                                   'Auto-generated for attendance penalties')""",
                        (f"Attendance Penalty — {module}", module))
                    assessment_id = cur.lastrowid

                today = date.today().isoformat()
                comments = (f"Attendance penalty: {pct:.1f}% < "
                            f"{threshold:.0f}% threshold")
                cur.execute(
                    """INSERT INTO grades
                       (student_id, assessment_id, score, letter_grade,
                        submission_date, comments)
                       VALUES (?, ?, 0, 'F', ?, ?)""",
                    (sid, assessment_id, today, comments))
                grade_row_id = cur.lastrowid

                cur.execute(
                    """INSERT OR REPLACE INTO attendance_grade_penalties
                       (student_id, module_code, threshold, pct,
                        applied_at, applied_by, grade_row_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sid, module, threshold, pct,
                     datetime.now().isoformat(timespec="seconds"),
                     getattr(self.ctx, "username", None) or "",
                     grade_row_id))

                # (5) Notify linked parents — same shape as #27.
                parents = _parents_of(self.ctx.db, sid) or [""]
                content = (f"Attendance penalty recorded for {module}: "
                           f"{pct:.1f}% (below {threshold:.0f}%).")
                now = datetime.now().isoformat(timespec="seconds")
                for pid in parents:
                    cur.execute(
                        """INSERT INTO parent_notifications
                           (parent_id, student_id, notification_type,
                            notification_content, created_date, read_status)
                           VALUES (?, ?, 'grade_penalty', ?, ?, 0)""",
                        (pid, sid, content, now))

                self.ctx.db.conn.commit()
            except sqlite3.Error as e:
                self.ctx.db.conn.rollback()
                logger.exception("apply penalty failed sid=%s module=%s",
                                 sid, module)
                messagebox.showerror("Failed", str(e),
                                     parent=self.ctx.parent)
                return

            audit(self.ctx, "grade_penalty_applied", "grades",
                  str(grade_row_id),
                  f"sid={sid} module={module} pct={pct:.1f} "
                  f"threshold={threshold}")
            # Reflect the new state in the visible table.
            try:
                sel = tree.selection()
                if sel:
                    vals = list(tree.item(sel[0], "values"))
                    if len(vals) >= 4:
                        vals[3] = "✓"
                        tree.item(sel[0], values=vals)
            except Exception:
                pass
            messagebox.showinfo(
                "Penalty applied",
                f"Recorded penalty for {sid} on {module} and notified "
                f"{len([p for p in parents if p])} parent(s).",
                parent=self.ctx.parent)

        win, tree = _show_table(
            self.ctx.parent,
            f"Attendance penalty candidates (<{threshold:.0f}%)",
            ("student", "module", "pct", "applied"),
            [(s, m, f"{p:.1f}", a) for s, m, p, a in rows],
            extra_button=("⚖️  Apply standard penalty (selected)",
                          _apply_penalty))

        # Second action button for navigating into Grade Management,
        # alongside the primary Apply Penalty action.
        extra = tk.Frame(win)
        extra.pack(side="bottom", fill="x")
        tk.Button(extra, text="📝  Open Grade Management GUI (selected)",
                  command=_open_grade_manager,
                  bg="#0ea5e9", fg="white", relief="flat",
                  padx=10, pady=4).pack(side="left", padx=10, pady=4)

        # Double-click a row → open grade manager prefilled.
        tree.bind("<Double-1>", lambda _e: _open_grade_manager())

        audit(self.ctx, "grade_link", "attendance", "",
              f"threshold={threshold} n={len(rows)}")

    # --- #35 ----------------------------------------------------------
    @safe("Wellbeing link")
    def show_absences_vs_mood(self) -> None:
        try:
            # Match the canonical schema in
            # infrastructure/database/schemas/health_wellness_schemas.py
            # (column is `mood_rating`, not `mood`).
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS mental_health_checkins (
                    checkin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    mood_rating INTEGER NOT NULL,
                    stress_level INTEGER NOT NULL,
                    sleep_quality INTEGER,
                    notes TEXT,
                    checkin_date TEXT DEFAULT CURRENT_DATE,
                    checkin_time TEXT DEFAULT CURRENT_TIME,
                    follow_up_required BOOLEAN DEFAULT 0)""")
            rows = self.ctx.db.cur.execute(
                """SELECT a.student_id,
                          SUM(CASE WHEN a.status='absent' THEN 1 ELSE 0 END)
                              AS abs_cnt,
                          (SELECT AVG(mood_rating) FROM mental_health_checkins mc
                           WHERE mc.student_id=a.student_id) AS avg_mood
                   FROM attendance a GROUP BY a.student_id
                   ORDER BY abs_cnt DESC LIMIT 50""").fetchall()
        except sqlite3.Error:
            logger.exception("wellbeing link query failed")
            rows = []

        def _open_wellbeing_gui():
            try:
                import tkinter as tk
                from education_system.post_18.university_system.modules.domain.student_affairs.student_wellbeing.gui.wellbeing_gui import (  # noqa: E501
                    WellbeingFrame,
                )
                win = tk.Toplevel(self.ctx.parent)
                win.title("Wellbeing")
                win.geometry("1000x650")
                WellbeingFrame(win, db_path=self.ctx.db.path,
                               auth=getattr(self.ctx, "auth", None)
                               ).pack(fill="both", expand=True)
            except Exception:
                logger.exception("could not open Wellbeing GUI")
                from tkinter import messagebox
                messagebox.showerror(
                    "Wellbeing", "Could not open the Wellbeing GUI "
                    "(see log).", parent=self.ctx.parent)

        _show_table(self.ctx.parent, "Absences vs mood",
                    ("student", "absences", "avg_mood"), rows,
                    extra_button=("📊  Open Wellbeing GUI",
                                  _open_wellbeing_gui))

    # --- #36 ----------------------------------------------------------
    @safe("Disciplinary action")
    def raise_disciplinary_action(self) -> None:
        sid = self.student_picker.pick("Disciplinary action for?")
        if not sid:
            return
        reason = simpledialog.askstring(
            "Reason", "Reason:",
            parent=self.ctx.parent) or "Repeated unjustified absences"
        if not Prompt.confirm(self.ctx.parent, "Confirm",
                              f"Raise written warning for {sid}?"):
            return
        try:
            today = date.today().isoformat()
            now = datetime.now().isoformat(timespec="seconds")
            # disciplinary_actions.record_id is a FK to
            # disciplinary_records(record_id); we must create the parent
            # row first or the FK constraint fails.
            self.ctx.db.cur.execute(
                """INSERT INTO disciplinary_records
                   (user_id, offense_type, description, date_occurred,
                    date_reported, reported_by, severity, status)
                   VALUES (?, 'attendance', ?, ?, ?, ?, 'Minor', 'Under Review')""",
                (sid, reason, today, today, self.ctx.username))
            record_id = self.ctx.db.cur.lastrowid
            self.ctx.db.cur.execute(
                """INSERT INTO disciplinary_actions
                   (record_id, action_type, action_level, effective_date,
                    duration_days, imposed_by, reason, created_at)
                   VALUES (?, 'warning', 'written', ?, 0, ?, ?, ?)""",
                (record_id, today, self.ctx.username, reason, now))
            self.ctx.db.conn.commit()
        except sqlite3.Error as e:
            self.ctx.db.conn.rollback()
            logger.exception("disciplinary insert failed sid=%s", sid)
            messagebox.showerror("Failed", str(e), parent=self.ctx.parent)
            return
        audit(self.ctx, "disciplinary", "disciplinary_actions", sid, reason)

        # Offer to open the full Disciplinary Portal so the admin can
        # add evidence, escalate severity, or attach follow-up actions
        # beyond the one-click written warning we just recorded.
        if Prompt.confirm(
                self.ctx.parent, "Open portal?",
                f"Disciplinary action logged for {sid}.\n\n"
                "Open the Disciplinary Portal to manage the record?"):
            try:
                from education_system.post_18.university_system.modules.domain.operations.legal.disciplinary.disciplinary_portal import (  # noqa: E501
                    DisciplinaryPortal,
                )
                win = tk.Toplevel(self.ctx.parent)
                win.title(f"Disciplinary Portal — {sid}")
                win.geometry("1200x800")
                DisciplinaryPortal(win)
            except Exception:
                logger.exception("could not open Disciplinary Portal")
                messagebox.showerror(
                    "Disciplinary Portal",
                    "Could not open the Disciplinary Portal (see log).",
                    parent=self.ctx.parent)
        else:
            messagebox.showinfo(
                "Recorded",
                f"Disciplinary action logged for {sid}.",
                parent=self.ctx.parent)

    # --- #37 ----------------------------------------------------------
    @safe("Finance link")
    def show_scholarship_attendance_check(self) -> None:
        # (#4) Remember the last threshold so staff don't reset it each run.
        try:
            saved = float(_get_setting(self.ctx.db, "scholarship_threshold", "80"))
        except (TypeError, ValueError):
            saved = 80.0
        threshold = simpledialog.askfloat(
            "Threshold", "Below %:",
            parent=self.ctx.parent, initialvalue=saved) or saved
        try:
            _set_setting(self.ctx.db, "scholarship_threshold", threshold)
        except Exception:
            logger.exception("could not persist scholarship threshold")

        try:
            self.ctx.db.cur.execute(
                """CREATE TABLE IF NOT EXISTS student_scholarships (
                    id INTEGER PRIMARY KEY,
                    student_id TEXT, scholarship_id INTEGER, status TEXT)""")
            # (#2) Add at-risk write-back columns if missing. ALTER TABLE ADD
            # COLUMN is idempotent only via try/except — older DBs predate this.
            for col, ddl in (
                ("at_risk_pct",            "ALTER TABLE student_scholarships ADD COLUMN at_risk_pct REAL"),
                ("at_risk_checked_at",     "ALTER TABLE student_scholarships ADD COLUMN at_risk_checked_at TEXT"),
                ("at_risk_last_notified_at", "ALTER TABLE student_scholarships ADD COLUMN at_risk_last_notified_at TEXT"),
            ):
                try:
                    self.ctx.db.cur.execute(ddl)
                except sqlite3.OperationalError:
                    pass  # column already exists
            self.ctx.db.conn.commit()

            # FIX: original used `HAVING 2 < ?` — same literal-compare bug.
            rows = self.ctx.db.cur.execute(
                """SELECT ss.student_id,
                          SUM(CASE WHEN a.status='present' THEN 1 ELSE 0 END)
                              * 1.0 / NULLIF(COUNT(a.id),0) * 100 AS pct
                   FROM student_scholarships ss
                   LEFT JOIN attendance a ON a.student_id = ss.student_id
                   GROUP BY ss.student_id
                   HAVING pct IS NOT NULL AND pct < ?""",
                (threshold,)).fetchall()
        except sqlite3.Error:
            logger.exception("scholarship check failed")
            rows = []

        # (#5) Schema sanity check — surface ID mismatches between
        # student_scholarships.student_id and the users table.
        sanity_msg = self._scholarship_id_sanity_check()

        # (#2) Write the at-risk pct back so it persists outside this popup.
        # (#3) Email admins, but only once per 24h per student to avoid spam.
        notified_now = self._mark_scholarships_at_risk(rows, threshold)
        if notified_now:
            audit(self.ctx, "notify", "student_scholarships",
                  ",".join(notified_now),
                  f"scholarship_at_risk threshold={threshold}")

        def _open_scholarship_gui(student_id: Optional[str] = None) -> None:
            """Launch the ScholarshipManagerGUI awards view in a new Toplevel."""
            try:
                from education_system.post_18.university_system.modules.domain.finance.gui.financial_aid.scholarship_manager import (
                    ScholarshipManagerGUI,
                )
            except Exception as e:
                logger.exception("scholarship GUI import failed")
                messagebox.showerror("Scholarship GUI",
                                     f"Could not open scholarship manager: {e}",
                                     parent=self.ctx.parent)
                return
            win = tk.Toplevel(self.ctx.parent)
            win.title(
                f"Scholarship Manager — {student_id}" if student_id
                else "Scholarship Manager"
            )
            win.geometry("1200x800")
            container = ttk.Frame(win)
            container.pack(fill="both", expand=True)
            try:
                gui = ScholarshipManagerGUI(container, auth_instance=getattr(
                    self.ctx, "auth", None))
                # Land on the awards table, filtered to the selected student
                # when one was double-clicked / selected.
                gui.show_awards(student_id=student_id)
            except Exception as e:
                logger.exception("scholarship GUI launch failed")
                messagebox.showerror("Scholarship GUI", str(e), parent=win)

        win, tree = _show_table(
            self.ctx.parent, "Scholarship attendance check",
            ("student", "pct"),
            [(s, f"{p:.1f}") for s, p in rows],
            extra_button=("Open Scholarship Manager", lambda: _open_scholarship_gui(
                (tree.item(tree.selection()[0], "values")[0]
                 if tree.selection() else None))),
        )
        # Double-click a row → open the scholarship manager for that student.
        tree.bind("<Double-1>", lambda _e: _open_scholarship_gui(
            (tree.item(tree.selection()[0], "values")[0]
             if tree.selection() else None)))

        # Surface the schema sanity report + notification count below the table.
        footer_bits = []
        if notified_now:
            footer_bits.append(f"Notified admins about {len(notified_now)} student(s).")
        if sanity_msg:
            footer_bits.append(sanity_msg)
        if footer_bits:
            tk.Label(win, text="  ".join(footer_bits),
                     fg="#6b7280", anchor="w", justify="left",
                     wraplength=950, padx=10, pady=4).pack(fill="x", side="bottom")

    # ---- helpers for #2/#3/#5 ---------------------------------------------
    def _mark_scholarships_at_risk(self, rows, threshold) -> list:
        """Persist at-risk pct back to student_scholarships and notify admins.

        ``rows`` is the list of (student_id, pct) tuples from the threshold
        query. Returns the student ids that were freshly notified this run.
        """
        if not rows:
            return []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notified: list = []
        try:
            for sid, pct in rows:
                # Read the existing last-notified-at to enforce a 24h guard.
                existing = self.ctx.db.cur.execute(
                    "SELECT at_risk_last_notified_at FROM student_scholarships "
                    "WHERE student_id = ? LIMIT 1", (sid,)).fetchone()
                last = existing[0] if existing else None
                self.ctx.db.cur.execute(
                    "UPDATE student_scholarships "
                    "SET at_risk_pct = ?, at_risk_checked_at = ? "
                    "WHERE student_id = ?",
                    (pct, now, sid),
                )
                # 24h re-notify guard.
                may_notify = True
                if last:
                    try:
                        last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                        may_notify = (datetime.now() - last_dt).total_seconds() > 86400
                    except ValueError:
                        may_notify = True
                if may_notify:
                    try:
                        n = _email_admin(
                            self.ctx.db,
                            subject=f"Scholarship at-risk: {sid} ({pct:.1f}%)",
                            body=(f"Student {sid} dropped to {pct:.1f}% attendance, "
                                  f"below the {threshold:.1f}% threshold for "
                                  f"continued scholarship eligibility. Review in "
                                  f"the Scholarship Manager."),
                            sender_username=getattr(self.ctx, "username", "") or "",
                        )
                    except Exception:
                        logger.exception("at-risk notification failed sid=%s", sid)
                        n = 0
                    if n:
                        self.ctx.db.cur.execute(
                            "UPDATE student_scholarships "
                            "SET at_risk_last_notified_at = ? "
                            "WHERE student_id = ?", (now, sid),
                        )
                        notified.append(sid)
            self.ctx.db.conn.commit()
        except sqlite3.Error:
            self.ctx.db.conn.rollback()
            logger.exception("at-risk write-back failed")
        return notified

    def _scholarship_id_sanity_check(self) -> str:
        """Return a one-line warning if scholarship student_ids don't link to users.

        The deep-link from awards back to the at-risk view assumes
        student_scholarships.student_id matches users.username (or
        users.student_id). Bad joins silently hide rows; surface a count.
        """
        try:
            row = self.ctx.db.cur.execute(
                """SELECT COUNT(DISTINCT ss.student_id)
                   FROM student_scholarships ss
                   LEFT JOIN users u
                     ON u.username = ss.student_id
                     OR u.student_id = ss.student_id
                   WHERE u.id IS NULL"""
            ).fetchone()
            orphans = (row[0] if row else 0) or 0
        except sqlite3.Error:
            logger.exception("scholarship sanity check failed")
            return ""
        if not orphans:
            return ""
        return (f"⚠ {orphans} scholarship student_id(s) don't match any user — "
                "deep-links from the Scholarship Manager may show no rows.")


# ===========================================================================
# BulkOperationsService — features #38–#41
# ===========================================================================
