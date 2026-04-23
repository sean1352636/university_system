"""Canvas-based drag-and-drop weekly timetable.

Replaces the read-only label grid with a Tk Canvas where each schedule block
can be dragged to a new day/time slot. On drop the block snaps to the
nearest 15-minute slot, the new (day, start, end) is computed from the drop
position, and the change goes through ``ModuleScheduler.update_module_schedule``
— which means schedule_history captures the move, conflict checks fire for
published rows, and notifications go out.

Layout is fixed: Mon–Fri columns, configurable hour range. The granularity
constant ``SLOT_MINUTES`` controls snapping.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths

DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH
logger = logging.getLogger(__name__)

_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
SLOT_MINUTES = 15
DAY_START_HOUR = 8
DAY_END_HOUR = 20  # exclusive upper bound

# Pixel sizing
HEADER_H = 32
TIME_COL_W = 70
DAY_COL_W = 180
ROW_H = 14  # height per SLOT_MINUTES slot

# Pleasant categorical palette for blocks. Cycled by module_code hash.
_BLOCK_COLORS = [
    "#4a90e2", "#7ed321", "#f5a623", "#bd10e0", "#50e3c2",
    "#9013fe", "#d0021b", "#417505", "#b8e986", "#f8e71c",
]


def _slot_count() -> int:
    return ((DAY_END_HOUR - DAY_START_HOUR) * 60) // SLOT_MINUTES


def _hhmm_to_minutes(hhmm: str) -> int | None:
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except (TypeError, ValueError, AttributeError):
        return None


def _minutes_to_hhmm(mins: int) -> str:
    h, m = divmod(mins, 60)
    return f"{h:02d}:{m:02d}"


def _color_for(module_code: str) -> str:
    return _BLOCK_COLORS[hash(module_code or "") % len(_BLOCK_COLORS)]


class DragDropTimetableDialog:
    """Drag schedule blocks around a week grid; drops persist via the service."""

    def __init__(self, parent, scheduler, gui=None):
        self.parent = parent
        self.scheduler = scheduler
        self.gui = gui

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Drag-and-Drop Timetable")
        self.dialog.geometry("1100x720")
        self.dialog.transient(parent)

        # Filter state mirrors the schedules tab so the grid scopes the
        # same way (one term, optional status).
        now = datetime.now()
        self.semester_var = tk.StringVar(
            value="Fall" if now.month >= 8 else ("Spring" if now.month <= 5 else "Summer"))
        self.year_var = tk.StringVar(value=str(now.year))
        self.status_var = tk.StringVar(value="published")

        # Per-block bookkeeping; key is the canvas item id of the block rect.
        self._blocks: dict[int, dict] = {}
        self._drag_state: dict | None = None

        self._build_ui()
        self._render()

    def _build_ui(self):
        bar = ttk.Frame(self.dialog, padding=8)
        bar.pack(fill=tk.X)
        ttk.Label(bar, text="Term:").pack(side=tk.LEFT)
        ttk.Combobox(bar, textvariable=self.semester_var,
                     values=["Fall", "Spring", "Summer", "Winter"],
                     width=10, state="readonly"
                     ).pack(side=tk.LEFT, padx=(4, 4))
        now = datetime.now()
        ttk.Combobox(bar, textvariable=self.year_var,
                     values=[str(y) for y in range(now.year - 2, now.year + 4)],
                     width=8, state="readonly"
                     ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(bar, text="Status:").pack(side=tk.LEFT)
        ttk.Combobox(bar, textvariable=self.status_var,
                     values=["published", "draft", "archived", "(all)"],
                     width=10, state="readonly"
                     ).pack(side=tk.LEFT, padx=(4, 12))
        ttk.Button(bar, text="Reload",
                   command=self._render).pack(side=tk.LEFT)
        self.status_text = tk.StringVar(
            value="Click a block and drag to a new slot. "
                  "Hold Esc-mid-drag to cancel.")
        ttk.Label(bar, textvariable=self.status_text,
                  foreground="#444").pack(side=tk.LEFT, padx=20)

        # Canvas scrollable area
        body = ttk.Frame(self.dialog)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        canvas_w = TIME_COL_W + DAY_COL_W * len(_DAYS) + 2
        canvas_h = HEADER_H + ROW_H * _slot_count() + 2
        self.canvas = tk.Canvas(body, bg="white", highlightthickness=1,
                                highlightbackground="#bbb",
                                scrollregion=(0, 0, canvas_w, canvas_h))
        vsb = ttk.Scrollbar(body, orient=tk.VERTICAL,
                            command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(self.dialog, text="Close",
                   command=self.dialog.destroy).pack(pady=8)

    # ----- Geometry helpers -----

    def _x_for_day(self, day: str) -> int:
        try:
            return TIME_COL_W + _DAYS.index(day) * DAY_COL_W
        except ValueError:
            return TIME_COL_W

    def _day_for_x(self, x: float) -> str | None:
        col = int((x - TIME_COL_W) // DAY_COL_W)
        if 0 <= col < len(_DAYS):
            return _DAYS[col]
        return None

    def _y_for_minutes(self, mins: int) -> int:
        offset = mins - DAY_START_HOUR * 60
        return HEADER_H + max(0, offset // SLOT_MINUTES) * ROW_H

    def _minutes_for_y(self, y: float) -> int:
        rel = max(0, y - HEADER_H)
        slot = int(rel // ROW_H)
        slot = max(0, min(_slot_count() - 1, slot))
        return DAY_START_HOUR * 60 + slot * SLOT_MINUTES

    # ----- Render -----

    def _render(self):
        self.canvas.delete("all")
        self._blocks.clear()
        self._draw_grid()
        try:
            rows = self._load_rows()
        except sqlite3.Error as e:
            messagebox.showerror("Error",
                                 f"Failed to load schedule rows: {e}",
                                 parent=self.dialog)
            return
        for row in rows:
            self._draw_block(row)
        # Report the actual rendered count, not the raw row count — rows
        # outside the visible time window or with bad day strings get
        # silently dropped, and the user shouldn't have to guess why.
        rendered = len(self._blocks)
        if rendered == len(rows):
            self.status_text.set(
                f"{rendered} block(s) shown. "
                "Drag any block to a new slot to reschedule it.")
        else:
            self.status_text.set(
                f"{rendered} of {len(rows)} block(s) shown "
                f"(others fall outside {DAY_START_HOUR:02d}:00-{DAY_END_HOUR:02d}:00 "
                "or aren't Mon-Fri). Drag a block to reschedule.")

    def _draw_grid(self):
        # Day headers
        self.canvas.create_rectangle(
            0, 0, TIME_COL_W, HEADER_H,
            fill="#34495e", outline="#34495e",
        )
        for i, day in enumerate(_DAYS):
            x0 = TIME_COL_W + i * DAY_COL_W
            self.canvas.create_rectangle(
                x0, 0, x0 + DAY_COL_W, HEADER_H,
                fill="#34495e", outline="#2c3e50",
            )
            self.canvas.create_text(
                x0 + DAY_COL_W / 2, HEADER_H / 2,
                text=day, fill="white",
                font=("Arial", 10, "bold"),
            )
        # Time labels + horizontal lines
        slots = _slot_count()
        for slot in range(slots + 1):
            mins = DAY_START_HOUR * 60 + slot * SLOT_MINUTES
            y = HEADER_H + slot * ROW_H
            on_hour = (mins % 60) == 0
            color = "#777" if on_hour else "#e6e6e6"
            self.canvas.create_line(
                0, y, TIME_COL_W + DAY_COL_W * len(_DAYS), y, fill=color,
            )
            if on_hour and slot < slots:
                self.canvas.create_text(
                    TIME_COL_W - 6, y + ROW_H,
                    text=_minutes_to_hhmm(mins), anchor=tk.E,
                    font=("Arial", 9), fill="#555",
                )
        # Vertical day separators
        for i in range(len(_DAYS) + 1):
            x = TIME_COL_W + i * DAY_COL_W
            self.canvas.create_line(
                x, 0, x, HEADER_H + slots * ROW_H, fill="#777",
            )

    def _load_rows(self):
        where = []
        params = []
        if self.semester_var.get():
            where.append("ms.semester = ?")
            params.append(self.semester_var.get())
        try:
            params.append(int(self.year_var.get()))
            where.append("ms.year = ?")
        except (TypeError, ValueError):
            pass
        if self.status_var.get() and self.status_var.get() != "(all)":
            where.append("COALESCE(ms.status, 'published') = ?")
            params.append(self.status_var.get())
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT ms.id, ms.module_code, ms.day_of_week, ms.start_time,
                   ms.end_time, COALESCE(r.building, '') || '-' ||
                   COALESCE(r.room_number, '') AS room,
                   ms.session_type, COALESCE(ms.status, 'published') AS status
            FROM module_schedule ms
            LEFT JOIN rooms r ON r.id = ms.room_id
            {where_sql}
            ORDER BY ms.day_of_week, ms.start_time
        """
        with sqlite3.connect(str(DEFAULT_DB_PATH), timeout=15.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            cur = conn.cursor()
            cur.execute(sql, params)
            return cur.fetchall()

    def _draw_block(self, row):
        sid, code, day, start, end, room, stype, status = row
        if day not in _DAYS:
            return
        s_mins = _hhmm_to_minutes(start)
        e_mins = _hhmm_to_minutes(end)
        if s_mins is None or e_mins is None or e_mins <= s_mins:
            return
        # Clamp to grid range so off-screen rows still get a visible handle.
        s_mins = max(s_mins, DAY_START_HOUR * 60)
        e_mins = min(e_mins, DAY_END_HOUR * 60)
        if e_mins <= s_mins:
            return
        x0 = self._x_for_day(day) + 4
        x1 = self._x_for_day(day) + DAY_COL_W - 4
        y0 = self._y_for_minutes(s_mins) + 1
        y1 = self._y_for_minutes(e_mins) - 1
        color = _color_for(code)
        outline = "#999" if status == "draft" else "#222"
        dash = (4, 2) if status == "draft" else None
        rect = self.canvas.create_rectangle(
            x0, y0, x1, y1, fill=color, outline=outline,
            dash=dash, width=1.5,
        )
        label = self.canvas.create_text(
            (x0 + x1) / 2, (y0 + y1) / 2,
            text=f"{code}\n{start}-{end}\n{room}\n{stype or ''}".strip(),
            font=("Arial", 8, "bold"),
            fill="white",
        )
        self._blocks[rect] = {
            "schedule_id": sid, "module_code": code, "day": day,
            "start": start, "end": end, "duration": e_mins - s_mins,
            "label_id": label, "status": status,
        }
        # Bind drag handlers to both shapes so clicking the text also drags.
        for item in (rect, label):
            self.canvas.tag_bind(item, "<ButtonPress-1>",
                                 lambda e, r=rect: self._on_press(e, r))
            self.canvas.tag_bind(item, "<B1-Motion>",
                                 lambda e, r=rect: self._on_drag(e, r))
            self.canvas.tag_bind(item, "<ButtonRelease-1>",
                                 lambda e, r=rect: self._on_release(e, r))

    # ----- Drag handlers -----

    def _on_press(self, event, rect):
        info = self._blocks.get(rect)
        if not info:
            return
        coords = self.canvas.coords(rect)  # [x0, y0, x1, y1]
        self.canvas.tag_raise(rect)
        self.canvas.tag_raise(info["label_id"])
        self._drag_state = {
            "rect": rect,
            "label": info["label_id"],
            "orig_coords": coords,
            "orig_label_xy": self.canvas.coords(info["label_id"]),
            "press_x": event.x,
            "press_y": event.y,
            "info": info,
        }

    def _on_drag(self, event, rect):
        if not self._drag_state or self._drag_state["rect"] != rect:
            return
        ds = self._drag_state
        dx = event.x - ds["press_x"]
        dy = event.y - ds["press_y"]
        ox0, oy0, ox1, oy1 = ds["orig_coords"]
        self.canvas.coords(rect, ox0 + dx, oy0 + dy, ox1 + dx, oy1 + dy)
        lx, ly = ds["orig_label_xy"]
        self.canvas.coords(ds["label"], lx + dx, ly + dy)

    def _on_release(self, event, rect):
        if not self._drag_state or self._drag_state["rect"] != rect:
            return
        ds = self._drag_state
        self._drag_state = None
        info = ds["info"]

        # Compute the new day/time from the rectangle's current position.
        coords = self.canvas.coords(rect)
        cx = (coords[0] + coords[2]) / 2
        new_day = self._day_for_x(cx)
        new_start_mins = self._minutes_for_y(coords[1])
        new_end_mins = new_start_mins + info["duration"]

        # Bounds check: must land in a real day, end must stay within
        # day-end. If not, snap back.
        if (new_day is None
                or new_end_mins > DAY_END_HOUR * 60
                or new_start_mins < DAY_START_HOUR * 60):
            self._snap_back(ds)
            self.status_text.set("Drop ignored: would land outside the grid.")
            return

        new_start = _minutes_to_hhmm(new_start_mins)
        new_end = _minutes_to_hhmm(new_end_mins)

        # No-op detection — small drag that snaps back to same slot.
        if (new_day == info["day"] and new_start == info["start"]
                and new_end == info["end"]):
            self._snap_back(ds)
            return

        # Confirm the move so a fat-finger drag doesn't silently reschedule
        # a class.
        if not messagebox.askyesno(
                "Confirm move",
                f"Move {info['module_code']} from "
                f"{info['day']} {info['start']}-{info['end']} to "
                f"{new_day} {new_start}-{new_end}?",
                parent=self.dialog):
            self._snap_back(ds)
            return

        # Push through the service so schedule_history records the move
        # and the published-row conflict check still runs.
        changed_by = "gui"
        try:
            if self.gui and hasattr(self.gui, "_resolve_changed_by"):
                changed_by = self.gui._resolve_changed_by()
        except Exception:
            pass

        try:
            ok = self.scheduler.update_module_schedule(
                info["schedule_id"],
                day_of_week=new_day,
                start_time=new_start,
                end_time=new_end,
                changed_by=changed_by,
            )
        except Exception as e:
            ok = False
            logger.exception("Drag-drop update failed")
            messagebox.showerror("Error", f"Update failed: {e}",
                                 parent=self.dialog)

        if not ok:
            messagebox.showwarning(
                "Move rejected",
                "Move was rejected (likely a room/instructor conflict). "
                "Snapping back.",
                parent=self.dialog,
            )
            self._snap_back(ds)
            self.status_text.set(
                f"Move of {info['module_code']} rejected — see warning.")
            return

        # Re-render so the canvas reflects the persisted state and any
        # follow-on row positions resolve cleanly.
        self.status_text.set(
            f"Moved {info['module_code']} → {new_day} {new_start}-{new_end}.")
        self._render()

    def _snap_back(self, ds):
        rect = ds["rect"]
        self.canvas.coords(rect, *ds["orig_coords"])
        self.canvas.coords(ds["label"], *ds["orig_label_xy"])
