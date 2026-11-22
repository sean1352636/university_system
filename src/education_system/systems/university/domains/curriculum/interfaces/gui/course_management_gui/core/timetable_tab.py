"""Feature 6 — Visual timetable / calendar view.

Draws a weekly grid (days × time-of-day) of the section meetings scheduled in
a chosen academic term, so scheduling clashes are obvious at a glance instead
of buried in a list. Also provides a small editor to add / remove meeting
times for a section (the data the grid renders).

Meeting times live in ``section_meetings`` and link to ``course_sections``.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.core.ext_common import (
    ExtFormDialog, grab_when_viewable, tk, ttk, messagebox, _, logger,
)
from education_system.systems.university.infrastructure.event_bus import (
    EVENT_CALENDAR_CHANGED, publish,
)
from education_system.systems.university.infrastructure.ui.field_pickers import time_values
from education_system.systems.university.domains.curriculum.interfaces.gui.course_management_gui.core._imports import (
    DAYS_OF_WEEK, TIME_SLOTS,
)
from education_system.systems.university.domains.teaching.domain.timetable_bridge import (
    find_timetable_conflicts,
)

# A stable, readable palette cycled per course so each course's blocks share
# a colour across the grid.
_BLOCK_COLOURS = [
    "#3b82f6", "#16a34a", "#d97706", "#9333ea", "#0891b2",
    "#dc2626", "#65a30d", "#db2777", "#0d9488", "#7c3aed",
]


def _times_with(current):
    """The 15-minute menu, plus a saved time that falls between its steps."""
    times = time_values()
    if current and current not in times:
        times = sorted({*times, current})
    return times


def _to_minutes(hhmm):
    """Parse 'HH:MM' to minutes since midnight; None on bad input."""
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


class TimetableTabMixin:
    """Weekly timetable view + meeting-time editor."""

    def _open_timetable_manager(self):
        """Open the merged Timetable Manager on its Sections tab."""
        try:
            from education_system.systems.university.domains.teaching.interfaces.gui.timetable_management import (
                TimetableManagementGUI,
            )
            TimetableManagementGUI(self.root, auth=getattr(self, "auth", None),
                                   initial_tab="sections")
        except Exception as exc:
            messagebox.showerror(
                _t('gui.academics.course_management_gui.core.timetable_tab.dialogs.error', default="Error"),
                f"Failed to open Timetable Manager: {exc}")

    def create_timetable_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.timetable",
                                            default="Timetable"))

            bar = ttk.Frame(frame)
            bar.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(bar, text=_t('gui.academics.course_management_gui.core.timetable_tab.labels.term', default="Term:")).pack(side=tk.LEFT, padx=5)
            self._tt_term_combo = ttk.Combobox(bar, width=30, state="readonly")
            self._tt_term_combo.pack(side=tk.LEFT, padx=5)
            self._tt_term_combo.bind("<<ComboboxSelected>>", self._draw_timetable)
            if self._ext_can_edit():
                ttk.Button(bar, text=_t('gui.academics.course_management_gui.core.timetable_tab.buttons.manage_meeting_times', default="Manage Meeting Times…"),
                           command=self._manage_meetings).pack(side=tk.LEFT, padx=10)
            ttk.Button(bar, text=_("common.refresh", default="Refresh"),
                       command=self._reload_timetable).pack(side=tk.LEFT, padx=5)
            # Every timetable view now also lives in one merged window. The
            # section-meeting editor below stays here because it is built on
            # this GUI's own dialog helpers; the merged window links back.
            ttk.Button(bar, text=_t('gui.academics.course_management_gui.core.timetable_tab.buttons.open_timetable_manager', default="Open Timetable Manager…"),
                       command=self._open_timetable_manager).pack(side=tk.RIGHT, padx=5)

            # Scrollable canvas for the grid.
            wrap = ttk.Frame(frame)
            wrap.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            self._tt_canvas = tk.Canvas(wrap, bg="white", highlightthickness=0)
            vsb = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self._tt_canvas.yview)
            self._tt_canvas.configure(yscrollcommand=vsb.set)
            self._tt_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            vsb.pack(side=tk.RIGHT, fill=tk.Y)
            self._tt_canvas.bind("<Configure>", lambda _e: self._draw_timetable())

            self._reload_timetable()
        except Exception as exc:
            self._ext_report_error("build Timetable tab", exc)

    # -- data -----------------------------------------------------------

    def _reload_timetable(self, *_a):
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM academic_terms "
                            "ORDER BY academic_year DESC, name")
                rows = cur.fetchall()
            self._tt_term_map = {name: tid for tid, name in rows}
            self._tt_term_combo["values"] = list(self._tt_term_map.keys())
            if rows and not self._tt_term_combo.get():
                self._tt_term_combo.current(0)
            self._draw_timetable()
        except Exception as exc:
            self._ext_report_error("load terms for timetable", exc)

    def _current_tt_term_id(self):
        return getattr(self, "_tt_term_map", {}).get(self._tt_term_combo.get())

    def _fetch_meetings(self, term_id):
        """Return meeting rows for a term: (course_code, section, day,
        start, end, location)."""
        with self._ext_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT s.course_code, s.section_number, m.day_of_week, "
                "       m.start_time, m.end_time, m.location "
                "FROM section_meetings m "
                "JOIN course_sections s ON m.section_id = s.id "
                "WHERE s.term_id = ? "
                "ORDER BY s.course_code, m.start_time", (term_id,))
            return cur.fetchall()

    # -- rendering ------------------------------------------------------

    def _draw_timetable(self, *_a):
        canvas = getattr(self, "_tt_canvas", None)
        if canvas is None:
            return
        try:
            canvas.delete("all")
            term_id = self._current_tt_term_id()
            days = list(DAYS_OF_WEEK) or ["Monday", "Tuesday", "Wednesday",
                                          "Thursday", "Friday"]
            slots = list(TIME_SLOTS) or [f"{h:02d}:00" for h in range(9, 18)]

            if term_id is None:
                canvas.create_text(20, 20, anchor="nw",
                                   text="Select a term to view its timetable.",
                                   font=("Arial", 11))
                return

            meetings = self._fetch_meetings(term_id)

            # Grid geometry.
            label_w = 60          # width of the time gutter
            header_h = 28         # height of the day header
            row_h = 44            # height per time slot
            width = max(canvas.winfo_width(), label_w + len(days) * 140)
            col_w = (width - label_w) / max(1, len(days))
            grid_start = _to_minutes(slots[0]) or 540
            # Assume hourly slots; total span covers slots + 1 trailing hour.
            total_rows = len(slots)
            height = header_h + total_rows * row_h
            canvas.configure(scrollregion=(0, 0, width, height + 10))

            # Day headers.
            for di, day in enumerate(days):
                x0 = label_w + di * col_w
                canvas.create_rectangle(x0, 0, x0 + col_w, header_h,
                                        fill="#f3f4f6", outline="#d1d5db")
                canvas.create_text(x0 + col_w / 2, header_h / 2, text=day,
                                   font=("Arial", 9, "bold"))
            # Time gutter + horizontal lines.
            for ri, slot in enumerate(slots):
                y0 = header_h + ri * row_h
                canvas.create_text(label_w / 2, y0 + row_h / 2, text=slot,
                                   font=("Arial", 8))
                canvas.create_line(0, y0, width, y0, fill="#e5e7eb")
            canvas.create_line(0, header_h + total_rows * row_h, width,
                               header_h + total_rows * row_h, fill="#e5e7eb")
            # Vertical day separators.
            for di in range(len(days) + 1):
                x0 = label_w + di * col_w
                canvas.create_line(x0, 0, x0, height, fill="#d1d5db")

            # Place meeting blocks.
            colour_for = {}
            placed = 0
            px_per_min = row_h / 60.0
            for code, section, day, start, end, location in meetings:
                if day not in days:
                    continue
                start_m, end_m = _to_minutes(start), _to_minutes(end)
                if start_m is None or end_m is None or end_m <= start_m:
                    logger.debug("Skipping meeting with bad times: %s %s-%s",
                                 code, start, end)
                    continue
                di = days.index(day)
                x0 = label_w + di * col_w + 2
                x1 = label_w + (di + 1) * col_w - 2
                y0 = header_h + (start_m - grid_start) * px_per_min
                y1 = header_h + (end_m - grid_start) * px_per_min
                colour = colour_for.setdefault(
                    code, _BLOCK_COLOURS[len(colour_for) % len(_BLOCK_COLOURS)])
                canvas.create_rectangle(x0, y0, x1, y1, fill=colour,
                                        outline="#111827", width=1)
                label = f"{code}·{section}\n{start}-{end}"
                if location:
                    label += f"\n{location}"
                canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=label,
                                   fill="white", font=("Arial", 8), width=col_w - 8)
                placed += 1

            if not placed:
                canvas.create_text(label_w + 10, header_h + 10, anchor="nw",
                                   text="No meeting times scheduled for this term.\n"
                                        "Use “Manage Meeting Times…” to add some.",
                                   font=("Arial", 10), fill="#6b7280")
            logger.debug("Timetable drew %d meeting block(s)", placed)
        except Exception as exc:
            self._ext_report_error("draw timetable", exc)

    # -- meeting-time editor -------------------------------------------

    def _term_sections(self, term_id):
        """Return [(section_id, 'CODE · section')] for a term."""
        with self._ext_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, course_code, section_number FROM course_sections "
                "WHERE term_id=? ORDER BY course_code, section_number", (term_id,))
            return [(sid, f"{code} · {sec}") for sid, code, sec in cur.fetchall()]

    def _terms_with_sections(self):
        """[(term_name, term_id)] for terms that actually have sections.

        The term combo defaults to the newest term, which is often not where
        the sections are — that mismatch is why "Manage Meeting Times…" could
        look like it did nothing.
        """
        try:
            with self._ext_db() as conn:
                rows = conn.execute(
                    "SELECT t.name, t.id, COUNT(s.id) AS n "
                    "FROM academic_terms t "
                    "JOIN course_sections s ON s.term_id = t.id "
                    "GROUP BY t.id HAVING n > 0 "
                    "ORDER BY t.academic_year DESC, t.name").fetchall()
            return [(r[0], r[1]) for r in rows]
        except Exception:
            logger.debug("could not list terms with sections", exc_info=True)
            return []

    def _manage_meetings(self):
        """Add / edit / view / remove the meeting times of a section.

        Every change is mirrored onto the academic calendar of the people who
        have to attend — see
        ``domains.teaching.domain.section_meeting_calendar``. The
        weekly timetable grid reads ``section_meetings`` directly, so it needs
        no separate sync.
        """
        if not self._ext_can_edit():
            return
        term_id = self._current_tt_term_id()
        if term_id is None:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   _t('gui.academics.course_management_gui.core.timetable_tab.dialogs.select_a_term_first', default="Select a term first."))
            return
        sections = self._term_sections(term_id)
        if not sections:
            # Don't just refuse: the usual cause is that the combo defaulted to
            # the newest term while the sections live in another one. Say which
            # terms actually have sections, and offer to switch.
            other = self._terms_with_sections()
            if other:
                names = ", ".join(name for name, _tid in other[:4])
                if messagebox.askyesno(
                        _("common.info", default="No sections in this term"),
                        f"“{self._tt_term_combo.get()}” has no course sections.\n\n"
                        f"Sections exist in: {names}.\n\n"
                        "Switch to the first of those now?"):
                    self._tt_term_combo.set(other[0][0])
                    self._draw_timetable()
                    self._manage_meetings()
                return
            messagebox.showinfo(_("common.info", default="Info"),
                                _t('gui.academics.course_management_gui.core.timetable_tab.dialogs.this_term_has_no_course_sections_yet_add_sections_in_the_terms_s', default="This term has no course sections yet. Add sections "
                                "in the Terms & Sections tab first."))
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Meeting Times — {self._tt_term_combo.get()}")
        dlg.geometry("860x560")
        dlg.transient(self.root)
        grab_when_viewable(dlg)

        top = ttk.Frame(dlg, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text=_t('gui.academics.course_management_gui.core.timetable_tab.labels.section', default="Section:")).pack(side=tk.LEFT, padx=5)
        sec_map = {label: sid for sid, label in sections}
        sec_combo = ttk.Combobox(top, width=30, state="readonly",
                                 values=list(sec_map.keys()))
        sec_combo.current(0)
        sec_combo.pack(side=tk.LEFT, padx=5)
        status_var = tk.StringVar(value="")
        ttk.Label(top, textvariable=status_var, foreground="#555555").pack(
            side=tk.LEFT, padx=12)

        cols = ("ID", "Day", "Start", "End", "Room", "Location", "Calendar")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", height=13)
        for c, w in (("ID", 45), ("Day", 100), ("Start", 70), ("End", 70),
                     ("Room", 170), ("Location", 150), ("Calendar", 190)):
            tree.heading(c, text=c)
            tree.column(c, width=w, anchor="w")
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Rooms are shared with the module scheduler, so a meeting can carry a
        # room_id for precise cross-system clash detection. Free-text Location
        # stays available for spaces not in the rooms table.
        NO_ROOM = "(free text / no room)"
        room_by_label = {}      # label -> (room_id, room_number)
        label_by_room_id = {}   # room_id -> label
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA table_info(rooms)")
                if cur.fetchall():
                    cur.execute("SELECT id, room_number, building, capacity "
                                "FROM rooms WHERE COALESCE(is_active,1)=1 "
                                "ORDER BY building, room_number")
                    for rid, rnum, bldg, cap in cur.fetchall():
                        label = " — ".join(filter(None, [rnum or f"Room {rid}", bldg]))
                        if cap:
                            label += f" (cap {cap})"
                        room_by_label[label] = (rid, rnum or "")
                        label_by_room_id[rid] = label
        except Exception:
            room_by_label, label_by_room_id = {}, {}
        room_values = [NO_ROOM] + list(room_by_label.keys())

        def _calendar_cell(meeting_id):
            """How many calendar occurrences this meeting currently has."""
            try:
                from education_system.systems.university.domains.teaching.domain.section_meeting_calendar import (
                    calendar_summary,
                )
                info = calendar_summary(meeting_id)
            except Exception:
                logger.debug("calendar summary unavailable", exc_info=True)
                return "—"
            if not info["count"]:
                return "not on calendar"
            return f"{info['count']} × from {info['first']}"

        def load_meetings(*_a):
            self._ext_clear_tree(tree)
            sid = sec_map.get(sec_combo.get())
            if sid is None:
                return
            try:
                with self._ext_db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id, day_of_week, start_time, end_time, "
                        "       location, room_id "
                        "FROM section_meetings WHERE section_id=? "
                        "ORDER BY day_of_week, start_time", (sid,))
                    rows = cur.fetchall()
            except Exception as exc:
                self._ext_report_error("load meeting times", exc)
                return
            for mid, day, start, end, loc, room_id in rows:
                tree.insert("", tk.END, values=(
                    mid, day, start, end,
                    label_by_room_id.get(room_id, "—"),
                    loc or "—",
                    _calendar_cell(mid),
                ))
            status_var.set(
                f"{len(rows)} meeting time(s)" if rows
                else "No meeting times yet — use Add Meeting.")

        sec_combo.bind("<<ComboboxSelected>>", load_meetings)

        def _sync_calendar(meeting_id, removed=False):
            """Mirror one meeting to / from the academic calendar.

            Returns the line to show, for after the meetings list has reloaded.
            """
            try:
                from education_system.systems.university.domains.teaching.domain.section_meeting_calendar import (
                    sync_meeting, unsync_meeting,
                )
                if removed:
                    n = unsync_meeting(meeting_id)
                    note = f"Removed {n} calendar entr(ies)."
                else:
                    n = sync_meeting(meeting_id)
                    note = (f"Added to the academic calendar: {n} class(es)." if n else
                            "Saved, but not on the calendar: this term has already ended.")
                publish(EVENT_CALENDAR_CHANGED, meeting_id=meeting_id)
                return note
            except Exception:
                # A calendar mirror failure must not lose the meeting itself.
                logger.exception("calendar sync failed for meeting %s", meeting_id)
                return "Saved, but the calendar sync failed (see log)."

        def _meeting_form(existing=None):
            """Shared add / edit form. *existing* is a tree row's values."""
            sid = sec_map.get(sec_combo.get())
            if sid is None:
                return
            editing = existing is not None
            meeting_id = int(existing[0]) if editing else None

            def submit(values):
                start_m = _to_minutes(values.get("start_time"))
                end_m = _to_minutes(values.get("end_time"))
                if start_m is None or end_m is None:
                    messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                         _t('gui.academics.course_management_gui.core.timetable_tab.dialogs.times_must_be_in_hh_mm_format', default="Times must be in HH:MM format."))
                    return False
                if end_m <= start_m:
                    messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                         _t('gui.academics.course_management_gui.core.timetable_tab.dialogs.end_time_must_be_after_start_time', default="End time must be after start time."))
                    return False
                room_id, room_number = room_by_label.get(values.get("room", ""), (None, ""))
                location = (values.get("location") or "").strip()
                if not location and room_number:
                    location = room_number
                try:
                    clashes = find_timetable_conflicts(
                        values["day_of_week"], values["start_time"].strip(),
                        values["end_time"].strip(), location=location,
                        room_id=room_id,
                        exclude_section_meeting_id=meeting_id)
                except Exception:
                    clashes = []
                if clashes:
                    detail = "\n".join(f"  • {c}" for c in clashes[:6])
                    if not messagebox.askyesno(
                            _("common.warning", default="Possible room clash"),
                            "This meeting may clash with existing bookings:\n\n"
                            f"{detail}\n\nSave it anyway?"):
                        return False
                try:
                    with self._ext_db(write=True) as conn:
                        if editing:
                            conn.execute(
                                "UPDATE section_meetings SET day_of_week=?, "
                                "start_time=?, end_time=?, location=?, room_id=? "
                                "WHERE id=?",
                                (values["day_of_week"], values["start_time"].strip(),
                                 values["end_time"].strip(), location, room_id,
                                 meeting_id))
                        else:
                            cur = conn.execute(
                                "INSERT INTO section_meetings "
                                "(section_id, day_of_week, start_time, end_time, "
                                " location, room_id, created_at) "
                                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (sid, values["day_of_week"],
                                 values["start_time"].strip(),
                                 values["end_time"].strip(), location, room_id,
                                 self._ext_now()))
                            self._new_meeting_id = cur.lastrowid
                except Exception as exc:
                    self._ext_report_error(
                        "update meeting time" if editing else "add meeting time", exc)
                    return False
                saved_id = meeting_id if editing else getattr(self, "_new_meeting_id", None)
                self._ext_audit("update" if editing else "create",
                                "section_meeting", section_id=sid,
                                day=values["day_of_week"])
                note = _sync_calendar(saved_id) if saved_id else None
                load_meetings()
                if note:
                    status_var.set(note)
                self._draw_timetable()
                return True

            if editing:
                cur_room = existing[4] if existing[4] in room_by_label else NO_ROOM
                defaults = {"day": existing[1], "start": existing[2],
                            "end": existing[3], "room": cur_room,
                            "location": "" if existing[5] == "—" else existing[5]}
                title, label = "Edit Meeting Time", "Save"
            else:
                defaults = {"day": (DAYS_OF_WEEK or ["Monday"])[0],
                            "start": "09:00", "end": "10:00",
                            "room": NO_ROOM, "location": ""}
                title, label = "Add Meeting Time", "Add"

            ExtFormDialog(
                dlg, self, title,
                [("day_of_week", "Day:", {"type": "combo",
                                          "values": list(DAYS_OF_WEEK),
                                          "default": defaults["day"]}),
                 ("start_time", "Start:", {"type": "combo", "width": 12,
                                           "values": _times_with(defaults["start"]),
                                           "default": defaults["start"]}),
                 ("end_time", "End:", {"type": "combo", "width": 12,
                                       "values": _times_with(defaults["end"]),
                                       "default": defaults["end"]}),
                 ("room", "Room:", {"type": "combo", "values": room_values,
                                    "default": defaults["room"]}),
                 ("location", "Location (free text):", {"default": defaults["location"]})],
                submit, submit_label=label, geometry="460x340")

        def add_meeting():
            _meeting_form(None)

        def edit_meeting():
            vals = self._ext_selected_values(tree)
            if not vals:
                messagebox.showwarning(_("common.warning", default="Warning"),
                                       "Select a meeting time to edit.")
                return
            _meeting_form(vals)

        def delete_meeting():
            vals = self._ext_selected_values(tree)
            if not vals:
                messagebox.showwarning(_("common.warning", default="Warning"),
                                       _t('gui.academics.course_management_gui.core.timetable_tab.dialogs.select_a_meeting_time_to_remove', default="Select a meeting time to remove."))
                return
            if not messagebox.askyesno(
                    _("common.confirm", default="Confirm"),
                    f"Remove {vals[1]} {vals[2]}–{vals[3]}?\n\n"
                    "Its entries are removed from the academic calendar too."):
                return
            meeting_id = vals[0]
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute("DELETE FROM section_meetings WHERE id=?", (meeting_id,))
            except Exception as exc:
                self._ext_report_error("remove meeting time", exc)
                return
            self._ext_audit("delete", "section_meeting", meeting_id=meeting_id)
            note = _sync_calendar(meeting_id, removed=True)
            load_meetings()
            status_var.set(note)
            self._draw_timetable()

        def resync_all():
            """Re-mirror every meeting on this section (after enrolment changes)."""
            sid = sec_map.get(sec_combo.get())
            if sid is None:
                return
            try:
                from education_system.systems.university.domains.teaching.domain.section_meeting_calendar import (
                    sync_section,
                )
                total = sync_section(sid)
            except Exception:
                logger.exception("section calendar re-sync failed")
                status_var.set("Calendar re-sync failed (see log).")
                return
            load_meetings()
            status_var.set(f"Re-synced {total} calendar occurrence(s).")
            publish(EVENT_CALENDAR_CHANGED, section_id=sid)

        tree.bind("<Double-1>", lambda _e: edit_meeting())

        btns = ttk.Frame(dlg, padding=8)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text=_t('gui.academics.course_management_gui.core.timetable_tab.buttons.add_meeting', default="Add Meeting"), command=add_meeting).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Edit Meeting", command=edit_meeting).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_("common.delete", default="Remove"),
                   command=delete_meeting).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="Re-sync Calendar",
                   command=resync_all).pack(side=tk.LEFT, padx=15)
        ttk.Button(btns, text=_("common.close", default="Close"),
                   command=dlg.destroy).pack(side=tk.RIGHT, padx=5)

        load_meetings()
