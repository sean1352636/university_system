"""Calendar tab of the Sixth Form Academic Year window.

Split out of ``academic_year_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import datetime as _dt
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import filedialog, messagebox
from education_system.systems.sixth_form.domain.academics.academic_year import (
    academic_year as data,
)
from education_system.systems.sixth_form.domain.academics.academic_year.academic_year import (
    ValidationError,
)
from ._widgets import _today


# ══ Calendar tab ═════════════════════════════════════════════════

# Heatmap palette for the month grid.
HEAT_COLOURS: dict[str, str] = {
    "outside":      "#ffffff",
    "teaching":     "#dff3d8",
    "weekend":      "#ececec",
    "Holiday":      "#cfe8ff",
    "Half-Term":    "#b8d9f4",
    "INSET":        "#fff3b0",
    "Bank Holiday": "#ffd5b0",
    "Exam Period":  "#ead0ff",
    "Other":        "#d8d8d8",
}


class CalendarTab:
    """Year-at-a-glance: 12-month grid heatmap + click-to-lookup +
    summary panel + term progress."""

    MONTHS_PER_ROW = 4
    DAY_CELL_W = 26
    DAY_CELL_H = 22
    HEADER_H = 20
    MONTH_TITLE_H = 22
    MONTH_PAD_X = 14
    MONTH_PAD_Y = 18
    WEEKNUM_W = 22

    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Year Grid")
        # Cache: iso date -> (kind, label)
        self._day_kind: dict[str, tuple[str, str]] = {}
        # Cache: (col, row) bounding boxes of day cells -> iso
        self._cell_rects: list[tuple[int, int, int, int, str]] = []
        self._summary_year_id: int | None = None
        self._build()
        self.refresh()

    # ── UI ──────────────────────────────────────────────────────

    def _build(self) -> None:
        # Top bar — year, ◀/▶ year nav, date, today, look up, print.
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="◀", width=2,
                    command=lambda: self._step_year(-1)).pack(side="left")
        ttk.Label(bar, text=" Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=34)
        self.year_cb.pack(side="left", padx=(2, 4))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Button(bar, text="▶", width=2,
                    command=lambda: self._step_year(1)).pack(side="left")

        ttk.Label(bar, text="    Date:").pack(side="left")
        self.date_e = ttk.Entry(bar, width=14)
        self.date_e.insert(0, _today())
        self.date_e.pack(side="left", padx=(2, 4))
        ttk.Button(bar, text="Today",
                    command=self._set_today).pack(side="left", padx=2)
        ttk.Button(bar, text="Look up",
                    command=self._lookup).pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Save as PostScript…",
                    command=self._save_postscript).pack(side="right")
        from education_system.systems.sixth_form.interfaces.gui import popout
        if not isinstance(self.frame.master, popout.FrameBook):
            # Starts on the same year; its own copy of the shared state.
            popout.add_page_button(
                bar, "Year grid",
                lambda book: CalendarTab(book, dict(self.state)), padx=(0, 6))

        # Progress / countdown line
        prog_bar = ttk.Frame(self.frame)
        prog_bar.pack(fill="x", padx=8, pady=(0, 4))
        self.progress = ttk.Progressbar(prog_bar, mode="determinate",
                                            maximum=100, length=200)
        self.progress.pack(side="left")
        self.progress_label = tk.StringVar(value="")
        ttk.Label(prog_bar, textvariable=self.progress_label,
                   anchor="w").pack(side="left", padx=8)

        self.countdown_label = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.countdown_label,
                   anchor="w").pack(fill="x", padx=8)

        # Body — month grid on the left, summary on the right.
        body = ttk.Frame(self.frame)
        body.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        cal_wrap = ttk.LabelFrame(body, text="Year heatmap")
        cal_wrap.pack(side="left", fill="both", expand=True,
                        padx=(0, 6))
        self.cal_canvas = tk.Canvas(cal_wrap, bg="white",
                                       highlightthickness=0)
        cal_vs = ttk.Scrollbar(cal_wrap, orient="vertical",
                                  command=self.cal_canvas.yview)
        self.cal_canvas.configure(yscrollcommand=cal_vs.set)
        self.cal_canvas.pack(side="left", fill="both", expand=True)
        cal_vs.pack(side="right", fill="y")
        self.cal_canvas.bind("<Configure>",
                               lambda _e: self._draw_calendar())
        self.cal_canvas.bind("<Button-1>", self._on_canvas_click)
        self.cal_canvas.bind("<Motion>", self._on_canvas_hover)

        summ = ttk.LabelFrame(body, text="Summary")
        summ.pack(side="left", fill="y")
        self.text = tk.Text(summ, wrap="none", width=46, height=30,
                              font=("TkFixedFont", 10))
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        self.text.configure(state="disabled")

        # Legend strip
        leg = ttk.Frame(self.frame)
        leg.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(leg, text="Heatmap:").pack(side="left")
        for kind in ("teaching", "weekend", "Holiday", "Half-Term",
                       "INSET", "Bank Holiday", "Exam Period", "Other"):
            tk.Label(leg, text=f" {kind} ",
                      bg=HEAT_COLOURS.get(kind, "#ffffff"),
                      fg="#222", relief="solid", borderwidth=1,
                      padx=4).pack(side="left", padx=2)

    # ── Year combo / nav ───────────────────────────────────────

    def _year_options(self) -> list[tuple[int, str]]:
        years = data.list_years()
        return [(y.year_id, f"#{y.year_id} {y.name}"
                            f"{' *' if y.is_current else ''}")
                for y in years]

    def _on_year_change(self) -> None:
        idx = self.year_cb.current()
        if idx < 0:
            return
        self.state["selected_year_id"] = self._year_ids[idx]
        self._render_all()

    def _step_year(self, delta: int) -> None:
        if not self._year_ids:
            return
        try:
            idx = self._year_ids.index(self.state.get("selected_year_id"))
        except (KeyError, ValueError):
            idx = 0
        idx = (idx + delta) % len(self._year_ids)
        self.state["selected_year_id"] = self._year_ids[idx]
        self.year_cb.current(idx)
        self._render_all()

    def _set_today(self) -> None:
        self.date_e.delete(0, "end")
        self.date_e.insert(0, _today())
        self._lookup()

    def refresh(self) -> None:
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels
        if not opts:
            self._write("No academic years configured.")
            self.cal_canvas.delete("all")
            self.progress["value"] = 0
            self.progress_label.set("")
            self.countdown_label.set("")
            return
        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target
        self._render_all()

    # ── Lookup ──────────────────────────────────────────────────

    def _lookup(self) -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            messagebox.showinfo("Lookup", "Pick a year first.")
            return
        s = self.date_e.get().strip()
        try:
            term = data.find_term_on(yid, s)
            brk = data.is_break(yid, s)
            d = _dt.date.fromisoformat(s)
        except (ValidationError, ValueError) as e:
            messagebox.showerror("Lookup", str(e))
            return
        lines: list[str] = []
        lines.append(f"Date    : {s} ({d.strftime('%A')})")
        lines.append(f"Term    : "
                     f"{term.name if term else '— (outside any term)'}")
        if brk:
            lines.append(f"Break   : {brk.name} ({brk.type})")
        elif d.weekday() >= 5:
            lines.append("Status  : Weekend (non-teaching)")
        else:
            lines.append("Status  : Teaching day")
        # Day-N-of-year indicators
        year = data.get_year(yid)
        if year is not None:
            try:
                ys = _dt.date.fromisoformat(year.start_date)
                ye = _dt.date.fromisoformat(year.end_date)
                if ys <= d <= ye:
                    n = (d - ys).days + 1
                    total = (ye - ys).days + 1
                    lines.append(f"Day     : {n} of {total} "
                                  f"(year)")
                    if term is not None:
                        try:
                            ts = _dt.date.fromisoformat(term.start_date)
                            te = _dt.date.fromisoformat(term.end_date)
                            tn = (d - ts).days + 1
                            ttot = (te - ts).days + 1
                            lines.append(f"          {tn} of {ttot} "
                                          f"({term.name})")
                        except ValueError:
                            pass
            except ValueError:
                pass
        lines.append("")
        lines.append("─" * 50)
        self._render_summary(prepend="\n".join(lines))

    # ── Render combinator ──────────────────────────────────────

    def _render_all(self) -> None:
        self._build_day_kind_cache()
        self._render_summary()
        self._draw_calendar()
        self._render_progress_and_countdown()

    def _build_day_kind_cache(self) -> None:
        self._day_kind.clear()
        yid = self.state.get("selected_year_id")
        if yid is None:
            return
        year = data.get_year(yid)
        if year is None:
            return
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return
        breaks = data.list_breaks(year_id=yid)
        # iso -> (type, name)
        bmap: dict[str, tuple[str, str]] = {}
        for b in breaks:
            try:
                bs = _dt.date.fromisoformat(b.start_date)
                be = _dt.date.fromisoformat(b.end_date)
            except ValueError:
                continue
            cur = bs
            one = _dt.timedelta(days=1)
            while cur <= be:
                iso = cur.isoformat()
                # Earlier breaks win — explicit by ORDER BY start_date.
                bmap.setdefault(iso, (b.type, b.name))
                cur += one
        cur = ys
        one = _dt.timedelta(days=1)
        while cur <= ye:
            iso = cur.isoformat()
            if iso in bmap:
                self._day_kind[iso] = bmap[iso]
            elif cur.weekday() >= 5:
                self._day_kind[iso] = ("weekend", "Weekend")
            else:
                self._day_kind[iso] = ("teaching", "Teaching day")
            cur += one

    # ── Calendar drawing ───────────────────────────────────────

    def _draw_calendar(self) -> None:
        self.cal_canvas.delete("all")
        self._cell_rects.clear()
        yid = self.state.get("selected_year_id")
        if yid is None:
            return
        year = data.get_year(yid)
        if year is None:
            return
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return

        # Enumerate months spanning the year (inclusive).
        months: list[_dt.date] = []
        cur = _dt.date(ys.year, ys.month, 1)
        end_of = _dt.date(ye.year, ye.month, 1)
        while cur <= end_of:
            months.append(cur)
            if cur.month == 12:
                cur = _dt.date(cur.year + 1, 1, 1)
            else:
                cur = _dt.date(cur.year, cur.month + 1, 1)

        month_w = self.WEEKNUM_W + 7 * self.DAY_CELL_W
        month_h = (self.MONTH_TITLE_H + self.HEADER_H
                    + 6 * self.DAY_CELL_H)
        cols = max(1, self.MONTHS_PER_ROW)
        rows = (len(months) + cols - 1) // cols
        total_w = cols * month_w + (cols + 1) * self.MONTH_PAD_X
        total_h = rows * month_h + (rows + 1) * self.MONTH_PAD_Y
        self.cal_canvas.configure(
            scrollregion=(0, 0, total_w, total_h))

        today_iso = _today()
        lookup_iso = self.date_e.get().strip()

        for i, m in enumerate(months):
            r, c = divmod(i, cols)
            x0 = self.MONTH_PAD_X + c * (month_w + self.MONTH_PAD_X)
            y0 = self.MONTH_PAD_Y + r * (month_h + self.MONTH_PAD_Y)
            self._draw_month(m, ys, ye, x0, y0, month_w, month_h,
                              today_iso, lookup_iso)

    def _draw_month(self, m: _dt.date, ys: _dt.date, ye: _dt.date,
                     x0: int, y0: int, w: int, h: int,
                     today_iso: str, lookup_iso: str) -> None:
        c = self.cal_canvas
        c.create_rectangle(x0, y0, x0 + w, y0 + h,
                              outline="#bbb", fill="white")
        c.create_rectangle(x0, y0, x0 + w, y0 + self.MONTH_TITLE_H,
                              outline="", fill="#f4f4f4")
        c.create_text(x0 + w // 2, y0 + self.MONTH_TITLE_H // 2,
                         text=m.strftime("%B %Y"),
                         font=("TkDefaultFont", 10, "bold"))

        hy = y0 + self.MONTH_TITLE_H
        # Week-number header
        c.create_text(x0 + self.WEEKNUM_W // 2, hy + self.HEADER_H // 2,
                         text="Wk", fill="#888",
                         font=("TkDefaultFont", 8))
        dow_labels = ("M", "T", "W", "T", "F", "S", "S")
        for i, lbl in enumerate(dow_labels):
            cx = (x0 + self.WEEKNUM_W
                   + i * self.DAY_CELL_W + self.DAY_CELL_W // 2)
            c.create_text(cx, hy + self.HEADER_H // 2,
                             text=lbl,
                             fill="#555" if i < 5 else "#888",
                             font=("TkDefaultFont", 8, "bold"))

        # Days
        first = _dt.date(m.year, m.month, 1)
        # Last day of month
        if m.month == 12:
            nxt = _dt.date(m.year + 1, 1, 1)
        else:
            nxt = _dt.date(m.year, m.month + 1, 1)
        last = nxt - _dt.timedelta(days=1)

        # Start at Monday of the week containing `first`.
        start_cell = first - _dt.timedelta(days=first.weekday())
        gy = hy + self.HEADER_H
        for week in range(6):
            row_y = gy + week * self.DAY_CELL_H
            week_anchor = start_cell + _dt.timedelta(days=7 * week)
            # ISO week number for the Thursday of that week (good enough)
            try:
                wknum = week_anchor.isocalendar()[1]
            except ValueError:
                wknum = 0
            c.create_text(
                x0 + self.WEEKNUM_W // 2,
                row_y + self.DAY_CELL_H // 2,
                text=str(wknum), fill="#999",
                font=("TkDefaultFont", 8))
            for i in range(7):
                d = start_cell + _dt.timedelta(days=7 * week + i)
                cx0 = x0 + self.WEEKNUM_W + i * self.DAY_CELL_W
                cy0 = row_y
                cx1 = cx0 + self.DAY_CELL_W
                cy1 = cy0 + self.DAY_CELL_H
                if d.month != m.month:
                    c.create_rectangle(cx0, cy0, cx1, cy1,
                                          fill="#fafafa", outline="#eee")
                    continue
                iso = d.isoformat()
                if ys <= d <= ye:
                    kind, _name = self._day_kind.get(
                        iso, ("outside", ""))
                else:
                    kind = "outside"
                fill = HEAT_COLOURS.get(kind, "#ffffff")
                outline = "#ddd"
                if iso == today_iso:
                    outline = "#1a73e8"
                if iso == lookup_iso:
                    outline = "#d12d2d"
                c.create_rectangle(cx0, cy0, cx1, cy1,
                                      fill=fill, outline=outline)
                c.create_text(cx0 + self.DAY_CELL_W // 2,
                                 cy0 + self.DAY_CELL_H // 2,
                                 text=str(d.day),
                                 fill="#222",
                                 font=("TkDefaultFont", 9))
                self._cell_rects.append((cx0, cy0, cx1, cy1, iso))

    def _on_canvas_click(self, event: tk.Event) -> None:
        x = self.cal_canvas.canvasx(event.x)
        y = self.cal_canvas.canvasy(event.y)
        for cx0, cy0, cx1, cy1, iso in self._cell_rects:
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                self.date_e.delete(0, "end")
                self.date_e.insert(0, iso)
                self._lookup()
                return

    def _on_canvas_hover(self, event: tk.Event) -> None:
        x = self.cal_canvas.canvasx(event.x)
        y = self.cal_canvas.canvasy(event.y)
        for cx0, cy0, cx1, cy1, _iso in self._cell_rects:
            if cx0 <= x <= cx1 and cy0 <= y <= cy1:
                self.cal_canvas.configure(cursor="hand2")
                return
        self.cal_canvas.configure(cursor="")

    # ── Progress + countdown ───────────────────────────────────

    def _render_progress_and_countdown(self) -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            self.progress["value"] = 0
            self.progress_label.set("")
            self.countdown_label.set("")
            return
        year = data.get_year(yid)
        if year is None:
            return
        today = _dt.date.today()
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return
        # Year countdown
        if today < ys:
            self.countdown_label.set(
                f"📅  Year starts in {(ys - today).days} day(s).")
        elif today > ye:
            self.countdown_label.set(
                f"📅  Year ended {(today - ye).days} day(s) ago.")
        else:
            try:
                taught_so_far = data.teaching_days_in(
                    yid, date_from=year.start_date,
                    date_to=today.isoformat())
                taught_total = data.teaching_days_in(yid)
            except Exception:
                taught_so_far, taught_total = 0, 0
            self.countdown_label.set(
                f"📅  {(ye - today).days} day(s) until end of year   "
                f"·   Teaching day {taught_so_far} of "
                f"{taught_total}")
        # Term progress (current term containing today)
        term = data.find_term_on(yid, today.isoformat())
        if term is None:
            self.progress["value"] = 0
            self.progress_label.set("Not currently in a term.")
            return
        try:
            ts = _dt.date.fromisoformat(term.start_date)
            te = _dt.date.fromisoformat(term.end_date)
        except ValueError:
            return
        elapsed = (today - ts).days + 1
        total = (te - ts).days + 1
        pct = max(0.0, min(100.0, 100.0 * elapsed / max(total, 1)))
        self.progress["value"] = pct
        self.progress_label.set(
            f"{term.name}: day {elapsed} of {total} "
            f"({pct:.0f}%)")

    # ── Summary text ───────────────────────────────────────────

    def _render_summary(self, *, prepend: str = "") -> None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            self._write(prepend or "No year selected.")
            return
        try:
            summ = data.year_summary(yid)
        except ValidationError as e:
            self._write(str(e))
            return
        y = summ.year
        lines: list[str] = []
        if prepend:
            lines.append(prepend)
            lines.append("")
        lines.append(f"#{y.year_id}  {y.name}  "
                     f"({y.start_date} → {y.end_date})")
        lines.append(f"Status            : {y.status}"
                     f"{'  (current)' if y.is_current else ''}")
        lines.append(f"Total days        : {y.day_count}")
        lines.append(f"Teaching days     : {summ.teaching_days}")
        lines.append(f"Non-teaching days : {summ.non_teaching_days}")
        lines.append(f"Weekend days      : {summ.weekend_days}")
        lines.append("")
        lines.append(f"Terms ({len(summ.terms)}):")
        for t in summ.terms:
            lines.append(f"  #{t.term_id:>3}  {t.name:<14}  "
                         f"{t.start_date} → {t.end_date}  "
                         f"({t.day_count} days)")
        lines.append("")
        lines.append(f"Breaks ({len(summ.breaks)}):")
        for b in summ.breaks:
            lines.append(f"  #{b.break_id:>3}  {b.name:<22}  "
                         f"{b.start_date} → {b.end_date}  "
                         f"({b.day_count} days, {b.type})")
        self._write("\n".join(lines))

    def _write(self, text: str) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.text.configure(state="disabled")

    # ── Print / export ─────────────────────────────────────────

    def _save_postscript(self) -> None:
        yid = self.state.get("selected_year_id")
        year = data.get_year(yid) if yid is not None else None
        default = (f"calendar_{year.name.replace('/', '-')}.ps"
                    if year else "calendar.ps")
        path = filedialog.asksaveasfilename(
            parent=self.frame,
            defaultextension=".ps",
            initialfile=default,
            filetypes=[("PostScript", "*.ps"), ("All files", "*.*")])
        if not path:
            return
        # The file dialog pumps the parent's event loop, so the window
        # (and with it the canvas) can be closed while it is open. Tk
        # would then raise a bare "invalid command name .!canvas".
        try:
            alive = bool(self.cal_canvas.winfo_exists())
        except tk.TclError:
            alive = False
        if not alive:
            return
        try:
            self.cal_canvas.postscript(file=path, colormode="color")
        except (OSError, tk.TclError) as e:
            messagebox.showerror("Save failed", str(e))
            return
        messagebox.showinfo(
            "Saved",
            f"Calendar saved to {path}\n\n"
            f"Convert to PDF with:  ps2pdf {path}")


# Sibling names used only at call time; imported last so any import order works.
