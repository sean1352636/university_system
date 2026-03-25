"""Calendar GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox
import calendar as cal_mod
from datetime import date

from education_system.college_system.modules.domain.calendar.services.calendar_service import CalendarService
from education_system.college_system.core.i18n import t


class CalendarFrame(tk.Frame):
    """Calendar management screen with monthly grid view."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CalendarService(db_path)

        today = date.today()
        self._current_month = today.month
        self._current_year = today.year

        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("calendar.title"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)
        ttk.Button(header, text=t("calendar.add_event"),
                   command=self._on_add_event).pack(side="right", padx=20, pady=10)

        # Navigation row
        nav_frame = tk.Frame(self, bg="#ecf0f1")
        nav_frame.pack(fill="x", padx=15, pady=(10, 5))

        ttk.Button(nav_frame, text="<", width=3,
                   command=self._prev_month).pack(side="left")
        self._month_label = tk.StringVar()
        tk.Label(nav_frame, textvariable=self._month_label,
                 font=("Helvetica", 13, "bold"), bg="#ecf0f1",
                 width=20, anchor="center").pack(side="left", padx=10)
        ttk.Button(nav_frame, text=">", width=3,
                   command=self._next_month).pack(side="left")
        ttk.Button(nav_frame, text=t("calendar.today"),
                   command=self._go_today).pack(side="left", padx=15)

        # Calendar grid
        self._grid_frame = tk.Frame(self, bg="#ecf0f1")
        self._grid_frame.pack(fill="both", expand=True, padx=15, pady=5)

        # Day headers
        for col, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
            lbl = tk.Label(self._grid_frame, text=day,
                           font=("Helvetica", 10, "bold"), bg="#2c3e50", fg="white",
                           width=14, height=1, relief="ridge")
            lbl.grid(row=0, column=col, sticky="nsew")
            self._grid_frame.columnconfigure(col, weight=1)

        # Day cells (6 rows x 7 cols)
        self._day_cells: list[tk.Label] = []
        for row in range(1, 7):
            self._grid_frame.rowconfigure(row, weight=1)
            for col in range(7):
                cell = tk.Label(self._grid_frame, text="", bg="white",
                                anchor="nw", justify="left",
                                font=("Helvetica", 9), relief="ridge",
                                padx=4, pady=2, cursor="hand2")
                cell.grid(row=row, column=col, sticky="nsew")
                cell.bind("<Button-1>", lambda e, r=row, c=col: self._on_cell_click(r, c))
                self._day_cells.append(cell)

        # Detail pane
        detail_frame = tk.LabelFrame(self, text=t("calendar.events"), bg="#ecf0f1",
                                     font=("Helvetica", 10, "bold"))
        detail_frame.pack(fill="x", padx=15, pady=(5, 10))

        self._detail_text = tk.Text(detail_frame, height=5, wrap="word",
                                    state="disabled", font=("Helvetica", 9))
        self._detail_text.pack(fill="x", padx=5, pady=5)

    def refresh(self):
        self._render_month()

    def _get_user_id(self) -> int:
        if self._auth and self._auth.current_user:
            return self._auth.current_user["user_id"]
        return 0

    def _is_admin(self) -> bool:
        if self._auth and self._auth.current_user:
            return self._auth.current_user.get("role") in ("admin", "staff")
        return False

    def _prev_month(self):
        if self._current_month == 1:
            self._current_month = 12
            self._current_year -= 1
        else:
            self._current_month -= 1
        self._render_month()

    def _next_month(self):
        if self._current_month == 12:
            self._current_month = 1
            self._current_year += 1
        else:
            self._current_month += 1
        self._render_month()

    def _go_today(self):
        today = date.today()
        self._current_month = today.month
        self._current_year = today.year
        self._render_month()

    def _render_month(self):
        self._month_label.set(
            f"{cal_mod.month_name[self._current_month]} {self._current_year}")

        # Get events for this month
        try:
            events = self._svc.list_events(
                user_id=self._get_user_id(),
                month=self._current_month,
                year=self._current_year,
            )
        except Exception:
            events = []

        # Group events by day number
        events_by_day: dict[int, list] = {}
        for ev in events:
            try:
                day = int(ev["event_date"].split("-")[2])
                events_by_day.setdefault(day, []).append(ev)
            except (ValueError, IndexError):
                pass

        # Build calendar grid
        first_weekday, num_days = cal_mod.monthrange(
            self._current_year, self._current_month)

        # Store day mapping for click events
        self._cell_day_map: dict[tuple[int, int], int] = {}

        today = date.today()
        cell_idx = 0
        for row in range(1, 7):
            for col in range(7):
                day_num = cell_idx - first_weekday + 1
                cell = self._day_cells[cell_idx]

                if 1 <= day_num <= num_days:
                    day_events = events_by_day.get(day_num, [])
                    text = str(day_num)
                    if day_events:
                        text += f"\n{len(day_events)} event(s)"
                        for ev in day_events[:2]:
                            text += f"\n  {ev['title'][:15]}"

                    cell.configure(text=text)
                    self._cell_day_map[(row, col)] = day_num

                    # Highlight today
                    if (day_num == today.day and
                            self._current_month == today.month and
                            self._current_year == today.year):
                        cell.configure(bg="#d5f4e6")
                    elif day_events:
                        cell.configure(bg="#ffeaa7")
                    else:
                        cell.configure(bg="white")
                else:
                    cell.configure(text="", bg="#f5f5f5")
                    self._cell_day_map.pop((row, col), None)

                cell_idx += 1

    def _on_cell_click(self, row, col):
        day_num = self._cell_day_map.get((row, col))
        if day_num is None:
            return
        date_str = f"{self._current_year:04d}-{self._current_month:02d}-{day_num:02d}"
        try:
            events = self._svc.get_events_for_date(self._get_user_id(), date_str)
        except Exception:
            events = []

        self._detail_text.configure(state="normal")
        self._detail_text.delete("1.0", "end")
        if events:
            for ev in events:
                time_str = ""
                if ev.get("start_time"):
                    time_str = f" {ev['start_time']}"
                    if ev.get("end_time"):
                        time_str += f"-{ev['end_time']}"
                self._detail_text.insert("end",
                    f"[{ev['event_type']}]{time_str} {ev['title']}\n")
                if ev.get("description"):
                    self._detail_text.insert("end", f"  {ev['description']}\n")
        else:
            self._detail_text.insert("end", f"No events on {date_str}")
        self._detail_text.configure(state="disabled")

    def _on_add_event(self):
        dlg = _EventDialog(self, self._is_admin())
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._svc.create_event(self._get_user_id(), **dlg.result)
                self._render_month()
            except Exception as e:
                messagebox.showerror(t("common.error"), str(e))


class _EventDialog(tk.Toplevel):
    """Add calendar event dialog."""

    def __init__(self, parent, is_admin=False):
        super().__init__(parent)
        self.title(t("calendar.add_event"))
        self.geometry("420x320")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        frame = tk.Frame(self, padx=15, pady=15)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=t("common.title_colon")).grid(row=0, column=0, sticky="w", pady=3)
        self._title_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._title_var, width=30).grid(
            row=0, column=1, pady=3)

        tk.Label(frame, text=t("calendar.date_label")).grid(row=1, column=0, sticky="w", pady=3)
        self._date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(frame, textvariable=self._date_var, width=15).grid(
            row=1, column=1, sticky="w", pady=3)

        tk.Label(frame, text=t("calendar.start_time_label")).grid(row=2, column=0, sticky="w", pady=3)
        self._start_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._start_var, width=10).grid(
            row=2, column=1, sticky="w", pady=3)

        tk.Label(frame, text=t("calendar.end_time_label")).grid(row=3, column=0, sticky="w", pady=3)
        self._end_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self._end_var, width=10).grid(
            row=3, column=1, sticky="w", pady=3)

        tk.Label(frame, text=t("calendar.type_colon")).grid(row=4, column=0, sticky="w", pady=3)
        types = ["personal", "academic", "deadline"]
        if is_admin:
            types.append("college")
        self._type_var = tk.StringVar(value="personal")
        ttk.Combobox(frame, textvariable=self._type_var,
                     values=types, state="readonly", width=12).grid(
            row=4, column=1, sticky="w", pady=3)

        tk.Label(frame, text=t("common.description_colon")).grid(row=5, column=0, sticky="nw", pady=3)
        self._desc_text = tk.Text(frame, width=23, height=3)
        self._desc_text.grid(row=5, column=1, pady=3)

        self._allday_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text=t("calendar.all_day"), variable=self._allday_var).grid(
            row=6, column=1, sticky="w", pady=3)

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(
            side="left", padx=5)

    def _save(self):
        title = self._title_var.get().strip()
        if not title:
            messagebox.showwarning(t("common.input"), t("calendar.title_required"), parent=self)
            return
        event_date = self._date_var.get().strip()
        if not event_date:
            messagebox.showwarning(t("common.input"), t("calendar.date_required"), parent=self)
            return
        self.result = {
            "title": title,
            "event_date": event_date,
            "start_time": self._start_var.get().strip() or None,
            "end_time": self._end_var.get().strip() or None,
            "event_type": self._type_var.get(),
            "description": self._desc_text.get("1.0", "end").strip() or None,
            "is_all_day": self._allday_var.get(),
        }
        self.destroy()
