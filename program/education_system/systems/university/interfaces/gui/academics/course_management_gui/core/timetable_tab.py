"""Feature 6 — Visual timetable / calendar view.

Draws a weekly grid (days × time-of-day) of the section meetings scheduled in
a chosen academic term, so scheduling clashes are obvious at a glance instead
of buried in a list. Also provides a small editor to add / remove meeting
times for a section (the data the grid renders).

Meeting times live in ``section_meetings`` and link to ``course_sections``.
"""

from education_system.systems.university.interfaces.gui.academics.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)
from education_system.systems.university.interfaces.gui.academics.course_management_gui.core._imports import (
    DAYS_OF_WEEK, TIME_SLOTS,
)
from education_system.systems.university.domain.academics.services.timetable_bridge import (
    find_timetable_conflicts,
)

# A stable, readable palette cycled per course so each course's blocks share
# a colour across the grid.
_BLOCK_COLOURS = [
    "#3b82f6", "#16a34a", "#d97706", "#9333ea", "#0891b2",
    "#dc2626", "#65a30d", "#db2777", "#0d9488", "#7c3aed",
]


def _to_minutes(hhmm):
    """Parse 'HH:MM' to minutes since midnight; None on bad input."""
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


class TimetableTabMixin:
    """Weekly timetable view + meeting-time editor."""

    def create_timetable_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.timetable",
                                            default="Timetable"))

            bar = ttk.Frame(frame)
            bar.pack(fill=tk.X, padx=5, pady=5)
            ttk.Label(bar, text="Term:").pack(side=tk.LEFT, padx=5)
            self._tt_term_combo = ttk.Combobox(bar, width=30, state="readonly")
            self._tt_term_combo.pack(side=tk.LEFT, padx=5)
            self._tt_term_combo.bind("<<ComboboxSelected>>", self._draw_timetable)
            if self._ext_can_edit():
                ttk.Button(bar, text="Manage Meeting Times…",
                           command=self._manage_meetings).pack(side=tk.LEFT, padx=10)
            ttk.Button(bar, text=_("common.refresh", default="Refresh"),
                       command=self._reload_timetable).pack(side=tk.LEFT, padx=5)

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

    def _manage_meetings(self):
        if not self._ext_can_edit():
            return
        term_id = self._current_tt_term_id()
        if term_id is None:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a term first.")
            return
        sections = self._term_sections(term_id)
        if not sections:
            messagebox.showinfo(_("common.info", default="Info"),
                                "This term has no course sections yet. Add sections "
                                "in the Terms & Sections tab first.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Meeting Times — {self._tt_term_combo.get()}")
        dlg.geometry("680x460")
        dlg.transient(self.root)
        dlg.grab_set()

        top = ttk.Frame(dlg, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Section:").pack(side=tk.LEFT, padx=5)
        sec_map = {label: sid for sid, label in sections}
        sec_combo = ttk.Combobox(top, width=30, state="readonly",
                                 values=list(sec_map.keys()))
        sec_combo.current(0)
        sec_combo.pack(side=tk.LEFT, padx=5)

        tree = ttk.Treeview(dlg, columns=("ID", "Day", "Start", "End", "Location"),
                            show="headings", height=12)
        for c, w in (("ID", 45), ("Day", 110), ("Start", 80), ("End", 80),
                     ("Location", 200)):
            tree.heading(c, text=c)
            tree.column(c, width=w)
        tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        def load_meetings(*_a):
            self._ext_clear_tree(tree)
            sid = sec_map.get(sec_combo.get())
            if sid is None:
                return
            try:
                with self._ext_db() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT id, day_of_week, start_time, end_time, location "
                        "FROM section_meetings WHERE section_id=? "
                        "ORDER BY day_of_week, start_time", (sid,))
                    rows = cur.fetchall()
                for row in rows:
                    tree.insert("", tk.END, values=row)
            except Exception as exc:
                self._ext_report_error("load meeting times", exc)

        sec_combo.bind("<<ComboboxSelected>>", load_meetings)

        # Real rooms (shared with the module scheduler) so meetings can
        # reference a room_id for precise cross-system clash detection. The
        # free-text Location stays available for rooms not in the table.
        NO_ROOM = "(free text / no room)"
        room_by_label = {}   # label -> (room_id, room_number)
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
        except Exception:
            room_by_label = {}
        room_values = [NO_ROOM] + list(room_by_label.keys())

        def add_meeting():
            sid = sec_map.get(sec_combo.get())
            if sid is None:
                return

            def submit(values):
                start_m = _to_minutes(values.get("start_time"))
                end_m = _to_minutes(values.get("end_time"))
                if start_m is None or end_m is None:
                    messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                         "Times must be in HH:MM format.")
                    return False
                if end_m <= start_m:
                    messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                         "End time must be after start time.")
                    return False
                # Resolve the chosen room; default the free-text location to the
                # room number when a room is picked but no location was typed.
                room_id, room_number = room_by_label.get(values.get("room", ""), (None, ""))
                location = (values.get("location") or "").strip()
                if not location and room_number:
                    location = room_number
                # Cross-system room clash check: precise via room_id, with a
                # location-text fallback. Catches both section and module clashes.
                try:
                    clashes = find_timetable_conflicts(
                        values["day_of_week"], values["start_time"].strip(),
                        values["end_time"].strip(), location=location, room_id=room_id)
                except Exception:
                    clashes = []
                if clashes:
                    detail = "\n".join(f"  • {c}" for c in clashes[:6])
                    if not messagebox.askyesno(
                            _("common.warning", default="Possible room clash"),
                            "This meeting may clash with existing bookings:\n\n"
                            f"{detail}\n\nAdd it anyway?"):
                        return False
                try:
                    with self._ext_db(write=True) as conn:
                        conn.execute(
                            "INSERT INTO section_meetings "
                            "(section_id, day_of_week, start_time, end_time, "
                            " location, room_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (sid, values["day_of_week"], values["start_time"].strip(),
                             values["end_time"].strip(), location, room_id,
                             self._ext_now()))
                except Exception as exc:
                    self._ext_report_error("add meeting time", exc)
                    return False
                self._ext_audit("create", "section_meeting", section_id=sid,
                                day=values["day_of_week"])
                load_meetings()
                self._draw_timetable()
                return True

            ExtFormDialog(
                dlg, self, "Add Meeting Time",
                [("day_of_week", "Day:", {"type": "combo",
                                          "values": list(DAYS_OF_WEEK),
                                          "default": (DAYS_OF_WEEK or ["Monday"])[0]}),
                 ("start_time", "Start (HH:MM):", {"default": "09:00", "width": 12}),
                 ("end_time", "End (HH:MM):", {"default": "10:00", "width": 12}),
                 ("room", "Room:", {"type": "combo", "values": room_values,
                                    "default": NO_ROOM}),
                 ("location", "Location (free text):", {"default": ""})],
                submit, submit_label="Add", geometry="460x340")

        def delete_meeting():
            vals = self._ext_selected_values(tree)
            if not vals:
                messagebox.showwarning(_("common.warning", default="Warning"),
                                       "Select a meeting time to remove.")
                return
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute("DELETE FROM section_meetings WHERE id=?", (vals[0],))
            except Exception as exc:
                self._ext_report_error("remove meeting time", exc)
                return
            self._ext_audit("delete", "section_meeting", meeting_id=vals[0])
            load_meetings()
            self._draw_timetable()

        btns = ttk.Frame(dlg, padding=8)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Add Meeting", command=add_meeting).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_("common.delete", default="Remove"),
                   command=delete_meeting).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_("common.close", default="Close"),
                   command=dlg.destroy).pack(side=tk.RIGHT, padx=5)

        load_meetings()
