"""Terms tab (and term-planning helpers) of the Sixth Form Academic Year window.

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
    AcademicYear,
    Term,
    ValidationError,
)
from ._common import _term_colour
from education_system.systems.sixth_form.domain.academics.academic_year.planning import (
    _shift_iso,
    _iso,
    _classify_terms,
    _STATUS_BADGES,
    _split_even_three,
    _suggest_halfterms,
)


# ══ Terms tab ═════════════════════════════════════════════════════


def _teaching_days_for_term(year_id: int, t: Term) -> int:
    try:
        return data.teaching_days_in(
            year_id, date_from=t.start_date, date_to=t.end_date)
    except Exception:
        return 0


class TermsTab:
    GANTT_H = 64
    GANTT_PAD = 12

    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Terms")
        self._terms: list[Term] = []
        self._status_by_id: dict[int, str] = {}
        self._teaching_by_id: dict[int, int] = {}
        # Gantt drag state
        self._drag_term_id: int | None = None
        self._drag_kind: str | None = None  # 'left' | 'right' | 'move'
        self._drag_orig: tuple[str, str] | None = None
        self._drag_anchor_x: int = 0
        self._build()
        self.refresh()

    # ── UI construction ─────────────────────────────────────────

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.year_cb.pack(side="left", padx=(2, 10))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        from education_system.systems.sixth_form.interfaces.gui import popout
        if not isinstance(self.frame.master, popout.FrameBook):
            # Starts on the same year; its own copy of the shared state.
            popout.add_page_button(
                bar, "Terms timeline",
                lambda book: TermsTab(book, dict(self.state)), padx=(0, 6))

        # Gantt strip
        gantt_frame = ttk.LabelFrame(self.frame, text="Timeline")
        gantt_frame.pack(fill="x", padx=8, pady=(4, 4))
        self.gantt = tk.Canvas(gantt_frame, height=self.GANTT_H,
                                  bg="#fafafa", highlightthickness=0)
        self.gantt.pack(fill="x", padx=4, pady=4)
        self.gantt.bind("<Configure>", lambda _e: self._draw_gantt())
        self.gantt.bind("<Motion>", self._gantt_motion)
        self.gantt.bind("<ButtonPress-1>", self._gantt_press)
        self.gantt.bind("<B1-Motion>", self._gantt_drag)
        self.gantt.bind("<ButtonRelease-1>", self._gantt_release)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "start", "end", "days", "teach", "status")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                    show="headings", selectmode="extended")
        headings = {"id": "ID", "name": "Name", "start": "Start",
                    "end": "End", "days": "Days",
                    "teach": "Teaching", "status": "Check"}
        widths = {"id": 60, "name": 160, "start": 110, "end": 110,
                  "days": 70, "teach": 90, "status": 140}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c in ("days", "teach") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.tag_configure("outside",    background="#ffd6d6")
        self.tree.tag_configure("overlap",    background="#ffe3b0")
        self.tree.tag_configure("gap-before", background="#fff7d0")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())
        self.tree.bind("<<TreeviewSelect>>",
                         lambda _e: self._draw_gantt())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        # Action row 1: CRUD
        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 2))
        ttk.Button(actions, text="New",
                    command=self._new).pack(side="left")
        ttk.Button(actions, text="Edit",
                    command=self._edit_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete",
                    command=self._delete_selected).pack(side="left", padx=4)
        ttk.Button(actions, text="Delete selected (bulk)",
                    command=self._bulk_delete).pack(side="left", padx=4)

        # Action row 2: bulk helpers + export
        more = ttk.Frame(self.frame)
        more.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Button(more, text="Auto-fill 3 terms",
                    command=self._autofill_three).pack(side="left")
        ttk.Button(more, text="Suggest half-terms",
                    command=self._suggest_halfterms).pack(side="left",
                                                              padx=4)
        ttk.Separator(more, orient="vertical").pack(side="left",
                                                       fill="y", padx=8)
        ttk.Label(more, text="Copy from:").pack(side="left")
        self.copy_cb = ttk.Combobox(more, state="readonly", width=28)
        self.copy_cb.pack(side="left", padx=(2, 4))
        ttk.Button(more, text="Copy terms",
                    command=self._copy_from_year).pack(side="left")
        ttk.Separator(more, orient="vertical").pack(side="left",
                                                       fill="y", padx=8)
        ttk.Button(more, text="Export CSV",
                    command=lambda: self._export("csv")).pack(side="left")
        ttk.Button(more, text="Export ICS",
                    command=lambda: self._export("ics")).pack(side="left",
                                                                 padx=4)

    # ── Year combobox / state ───────────────────────────────────

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
        self.refresh()

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels

        if not opts:
            self.count_var.set("No academic years configured.")
            self._terms = []
            self._draw_gantt()
            self.copy_cb["values"] = ()
            return

        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target

        # Copy-from combo lists every *other* year.
        self._copy_ids: list[int] = [yid for yid in self._year_ids
                                          if yid != target]
        self.copy_cb["values"] = [
            lbl for yid, lbl in opts if yid != target]
        if self._copy_ids:
            self.copy_cb.current(0)
        else:
            self.copy_cb.set("")

        year = data.get_year(target)
        if year is None:
            self._terms = []
            self._draw_gantt()
            return
        self._terms = data.list_terms(year_id=target)
        self._status_by_id = _classify_terms(year, self._terms)
        self._teaching_by_id = {
            t.term_id: _teaching_days_for_term(target, t)
            for t in self._terms}

        for t in self._terms:
            status = self._status_by_id.get(t.term_id, "ok")
            tags = (status,) if status != "ok" else ()
            self.tree.insert("", "end", iid=str(t.term_id), values=(
                t.term_id, t.name, t.start_date, t.end_date,
                t.day_count,
                self._teaching_by_id.get(t.term_id, 0),
                _STATUS_BADGES.get(status, status),
            ), tags=tags)

        issues = sum(1 for s in self._status_by_id.values() if s != "ok")
        teach_total = sum(self._teaching_by_id.values())
        self.count_var.set(
            f"{len(self._terms)} term(s) — {teach_total} teaching day(s)"
            + (f", {issues} with warnings" if issues else ""))
        self._draw_gantt()

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _selected_ids(self) -> list[int]:
        out: list[int] = []
        for iid in self.tree.selection():
            try:
                out.append(int(iid))
            except ValueError:
                pass
        return out

    def _current_year(self) -> AcademicYear | None:
        yid = self.state.get("selected_year_id")
        if yid is None:
            return None
        return data.get_year(yid)

    # ── CRUD ────────────────────────────────────────────────────

    def _new(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("New", "Pick a year first.")
            return
        TermDialog(self.frame.winfo_toplevel(), year=year,
                    existing=None, on_save=self.refresh)

    def _edit_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Edit", "Select a term first.")
            return
        existing = data.get_term(tid)
        if existing is None:
            return
        year = data.get_year(existing.year_id)
        if year is None:
            return
        TermDialog(self.frame.winfo_toplevel(), year=year,
                    existing=existing, on_save=self.refresh)

    def _delete_selected(self) -> None:
        tid = self._selected_id()
        if tid is None:
            messagebox.showinfo("Delete", "Select a term first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete term #{tid}? (Soft-delete — Ctrl-Z to undo)"):
            return
        try:
            data.delete_term(tid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        undo = self.state.get("_undo")
        if undo is not None:
            undo.push(f"delete term #{tid}",
                       lambda i=tid: data.restore_term(i))
        toaster = self.state.get("_toast")
        if toaster:
            toaster(f"Deleted term #{tid} — Ctrl-Z to undo", kind="warn")
        self.refresh()

    def _bulk_delete(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Delete", "Select one or more terms first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete {len(ids)} term(s)? "
                "(Soft-delete — Ctrl-Z to undo)"):
            return
        errs: list[str] = []
        deleted: list[int] = []
        for tid in ids:
            try:
                if data.delete_term(tid):
                    deleted.append(tid)
            except Exception as e:
                errs.append(f"#{tid}: {e}")
        if errs:
            messagebox.showerror("Some deletes failed", "\n".join(errs))
        undo = self.state.get("_undo")
        if undo is not None and deleted:
            def _restore_many(_ids=deleted) -> None:
                for i in _ids:
                    try:
                        data.restore_term(i)
                    except Exception:
                        pass
            undo.push(f"bulk delete {len(deleted)} term(s)",
                       _restore_many)
        toaster = self.state.get("_toast")
        if toaster and deleted:
            toaster(f"Deleted {len(deleted)} term(s) — Ctrl-Z to undo",
                      kind="warn")
        self.refresh()

    # ── Bulk helpers ────────────────────────────────────────────

    def _autofill_three(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Auto-fill", "Pick a year first.")
            return
        existing_names = {t.name for t in self._terms}
        if existing_names & {"Autumn", "Spring", "Summer"}:
            if not messagebox.askyesno(
                    "Auto-fill",
                    "This year already has one or more of "
                    "Autumn/Spring/Summer. Skip those and add only "
                    "the missing ones?"):
                return
        plan = _split_even_three(year)
        added = 0
        errs: list[str] = []
        for name, s, e in plan:
            if name in existing_names:
                continue
            try:
                data.create_term({
                    "year_id": year.year_id, "name": name,
                    "start_date": s, "end_date": e, "notes": None,
                })
                added += 1
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Auto-fill issues",
                                    f"Added {added}.\n" + "\n".join(errs))
        else:
            messagebox.showinfo("Auto-fill",
                                   f"Added {added} term(s).")
        self.refresh()

    def _suggest_halfterms(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Half-terms", "Pick a year first.")
            return
        suggestions = _suggest_halfterms(year.year_id, self._terms)
        if not suggestions:
            messagebox.showinfo(
                "Half-terms",
                "No Autumn/Spring/Summer terms to base "
                "suggestions on.")
            return
        # Drop any whose name+start already exist as a break.
        existing = {(b.name, b.start_date)
                     for b in data.list_breaks(year_id=year.year_id)}
        new = [s for s in suggestions if (s[0], s[1]) not in existing]
        if not new:
            messagebox.showinfo("Half-terms",
                                   "All suggestions already exist.")
            return
        preview = "\n".join(f"  • {n}  {s} → {e}" for n, s, e in new)
        if not messagebox.askyesno(
                "Half-terms",
                f"Insert {len(new)} suggested half-term break(s)?\n\n"
                f"{preview}"):
            return
        errs: list[str] = []
        for name, s, e in new:
            try:
                data.create_break({
                    "year_id": year.year_id, "name": name,
                    "type": "Half-Term", "start_date": s, "end_date": e,
                    "notes": None,
                })
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed",
                                    "\n".join(errs))
        self.refresh()

    def _copy_from_year(self) -> None:
        dest = self._current_year()
        if dest is None:
            messagebox.showinfo("Copy", "Pick a destination year first.")
            return
        idx = self.copy_cb.current()
        if idx < 0 or idx >= len(self._copy_ids):
            messagebox.showinfo("Copy", "Pick a source year.")
            return
        src_id = self._copy_ids[idx]
        src = data.get_year(src_id)
        if src is None:
            return
        try:
            shift = (_dt.date.fromisoformat(dest.start_date)
                      - _dt.date.fromisoformat(src.start_date)).days
        except ValueError as e:
            messagebox.showerror("Copy", str(e))
            return
        src_terms = data.list_terms(year_id=src_id)
        if not src_terms:
            messagebox.showinfo("Copy",
                                   f"{src.name!r} has no terms to copy.")
            return
        if not messagebox.askyesno(
                "Copy",
                f"Copy {len(src_terms)} term(s) from {src.name!r}\n"
                f"into {dest.name!r}, shifted by {shift:+d} days?\n"
                f"Existing terms with the same name will be skipped."):
            return
        existing_names = {t.name for t in self._terms}
        added = 0
        errs: list[str] = []
        for t in src_terms:
            if t.name in existing_names:
                continue
            try:
                data.create_term({
                    "year_id": dest.year_id,
                    "name": t.name,
                    "start_date": _shift_iso(t.start_date, shift),
                    "end_date": _shift_iso(t.end_date, shift),
                    "notes": t.notes,
                })
                added += 1
            except (ValidationError, Exception) as ex:
                errs.append(f"{t.name}: {ex}")
        if errs:
            messagebox.showerror("Copy issues",
                                    f"Added {added}.\n" + "\n".join(errs))
        else:
            messagebox.showinfo("Copy",
                                   f"Copied {added} term(s).")
        self.refresh()

    # ── Export ──────────────────────────────────────────────────

    def _export(self, fmt: str) -> None:
        year = self._current_year()
        if year is None or not self._terms:
            messagebox.showinfo("Export", "Nothing to export.")
            return
        default = f"terms_{year.name.replace('/', '-')}.{fmt}"
        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            initialfile=default,
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")])
        if not path:
            return
        try:
            if fmt == "csv":
                self._write_csv(path)
            else:
                self._write_ics(path, year)
        except OSError as e:
            messagebox.showerror("Export failed", str(e))
            return
        messagebox.showinfo("Export",
                               f"Wrote {len(self._terms)} term(s) to "
                               f"{path}")

    def _write_csv(self, path: str) -> None:
        import csv
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["term_id", "year_id", "name",
                          "start_date", "end_date",
                          "calendar_days", "teaching_days",
                          "status", "notes"])
            for t in self._terms:
                w.writerow([
                    t.term_id, t.year_id, t.name,
                    t.start_date, t.end_date,
                    t.day_count,
                    self._teaching_by_id.get(t.term_id, 0),
                    self._status_by_id.get(t.term_id, "ok"),
                    t.notes or "",
                ])

    def _write_ics(self, path: str, year: AcademicYear) -> None:
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//SixthForm//AcademicYear//EN",
            "CALSCALE:GREGORIAN",
        ]
        stamp = _dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        for t in self._terms:
            try:
                s = _dt.date.fromisoformat(t.start_date)
                e = (_dt.date.fromisoformat(t.end_date)
                       + _dt.timedelta(days=1))  # DTEND exclusive
            except ValueError:
                continue
            uid = f"term-{t.term_id}-y{year.year_id}@sixthform"
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f"SUMMARY:{t.name} ({year.name})",
                f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{e.strftime('%Y%m%d')}",
                "END:VEVENT",
            ]
        lines.append("END:VCALENDAR")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\r\n".join(lines) + "\r\n")

    # ── Gantt strip ─────────────────────────────────────────────

    def _gantt_geom(self) -> tuple[AcademicYear, _dt.date, _dt.date,
                                    int, float] | None:
        """Return (year, start, end, width_px, px_per_day) — or None
        if the year span isn't valid."""
        year = self._current_year()
        if year is None:
            return None
        try:
            s = _dt.date.fromisoformat(year.start_date)
            e = _dt.date.fromisoformat(year.end_date)
        except ValueError:
            return None
        total = (e - s).days + 1
        if total <= 0:
            return None
        w = max(self.gantt.winfo_width(), 200) - 2 * self.GANTT_PAD
        ppd = w / total
        return (year, s, e, w, ppd)

    def _date_to_x(self, d: _dt.date, geom) -> float:
        _year, start, _end, _w, ppd = geom
        return self.GANTT_PAD + (d - start).days * ppd

    def _x_to_date(self, x: float, geom) -> _dt.date:
        _year, start, end, _w, ppd = geom
        days = round((x - self.GANTT_PAD) / ppd)
        d = start + _dt.timedelta(days=int(days))
        if d < start:
            return start
        if d > end:
            return end
        return d

    def _draw_gantt(self) -> None:
        self.gantt.delete("all")
        geom = self._gantt_geom()
        if geom is None:
            self.gantt.create_text(
                10, self.GANTT_H // 2, anchor="w",
                text="No academic year selected.",
                fill="#888")
            return
        year, start, end, w, ppd = geom
        # Year bar
        self.gantt.create_rectangle(
            self.GANTT_PAD, 4,
            self.GANTT_PAD + w, 18,
            fill="#eeeeee", outline="#cccccc")
        self.gantt.create_text(
            self.GANTT_PAD + 4, 11, anchor="w",
            text=f"{year.name}   {year.start_date} → {year.end_date}",
            fill="#444", font=("TkDefaultFont", 8))

        # Month gridlines + labels
        cur = _dt.date(start.year, start.month, 1)
        while cur <= end:
            x = self._date_to_x(cur, geom)
            self.gantt.create_line(x, 20, x, self.GANTT_H,
                                       fill="#dddddd", dash=(2, 2))
            self.gantt.create_text(
                x + 2, self.GANTT_H - 4, anchor="sw",
                text=cur.strftime("%b"),
                fill="#999", font=("TkDefaultFont", 7))
            # advance one month
            if cur.month == 12:
                cur = _dt.date(cur.year + 1, 1, 1)
            else:
                cur = _dt.date(cur.year, cur.month + 1, 1)

        selected_ids = set(self._selected_ids())
        for t in self._terms:
            try:
                ts = _dt.date.fromisoformat(t.start_date)
                te = _dt.date.fromisoformat(t.end_date)
            except ValueError:
                continue
            x0 = self._date_to_x(max(ts, start), geom)
            x1 = self._date_to_x(min(te, end), geom)
            if x1 - x0 < 2:
                x1 = x0 + 2
            colour = _term_colour(t.name)
            outline = "#222" if t.term_id in selected_ids else "#666"
            wd = 2 if t.term_id in selected_ids else 1
            self.gantt.create_rectangle(
                x0, 22, x1, self.GANTT_H - 14,
                fill=colour, outline=outline, width=wd,
                tags=(f"term:{t.term_id}", "termbar"))
            # left/right grab handles (4px wide hot zones, drawn faint)
            self.gantt.create_rectangle(
                x0, 22, x0 + 4, self.GANTT_H - 14,
                fill="", outline="",
                tags=(f"term:{t.term_id}", f"handle-left:{t.term_id}"))
            self.gantt.create_rectangle(
                x1 - 4, 22, x1, self.GANTT_H - 14,
                fill="", outline="",
                tags=(f"term:{t.term_id}", f"handle-right:{t.term_id}"))
            if x1 - x0 > 40:
                self.gantt.create_text(
                    (x0 + x1) / 2, (22 + self.GANTT_H - 14) / 2,
                    text=t.name, fill="#222",
                    font=("TkDefaultFont", 8, "bold"))

    def _hit_term(self, x: int, y: int) -> tuple[int, str] | None:
        """Return (term_id, 'left'|'right'|'move') for the canvas hit
        or None."""
        if y < 22 or y > self.GANTT_H - 14:
            return None
        # Order matters: handles first.
        for item in self.gantt.find_overlapping(x - 1, y, x + 1, y):
            tags = self.gantt.gettags(item)
            for tg in tags:
                if tg.startswith("handle-left:"):
                    return (int(tg.split(":", 1)[1]), "left")
                if tg.startswith("handle-right:"):
                    return (int(tg.split(":", 1)[1]), "right")
        for item in self.gantt.find_overlapping(x - 1, y, x + 1, y):
            tags = self.gantt.gettags(item)
            for tg in tags:
                if tg.startswith("term:"):
                    return (int(tg.split(":", 1)[1]), "move")
        return None

    def _gantt_motion(self, event: tk.Event) -> None:
        if self._drag_term_id is not None:
            return
        hit = self._hit_term(event.x, event.y)
        if hit is None:
            self.gantt.configure(cursor="")
        elif hit[1] in ("left", "right"):
            self.gantt.configure(cursor="sb_h_double_arrow")
        else:
            self.gantt.configure(cursor="fleur")

    def _gantt_press(self, event: tk.Event) -> None:
        hit = self._hit_term(event.x, event.y)
        if hit is None:
            return
        tid, kind = hit
        term = next((t for t in self._terms if t.term_id == tid), None)
        if term is None:
            return
        self._drag_term_id = tid
        self._drag_kind = kind
        self._drag_orig = (term.start_date, term.end_date)
        self._drag_anchor_x = event.x
        try:
            self.tree.selection_set(str(tid))
        except tk.TclError:
            pass

    def _gantt_drag(self, event: tk.Event) -> None:
        if self._drag_term_id is None or self._drag_orig is None:
            return
        geom = self._gantt_geom()
        if geom is None:
            return
        _year, start, end, _w, ppd = geom
        delta_days = round((event.x - self._drag_anchor_x) / ppd)
        os_, oe = self._drag_orig
        try:
            so = _dt.date.fromisoformat(os_)
            eo = _dt.date.fromisoformat(oe)
        except ValueError:
            return
        if self._drag_kind == "left":
            ns = so + _dt.timedelta(days=delta_days)
            ne = eo
            if ns < start:
                ns = start
            if ns > ne:
                ns = ne
        elif self._drag_kind == "right":
            ns = so
            ne = eo + _dt.timedelta(days=delta_days)
            if ne > end:
                ne = end
            if ne < ns:
                ne = ns
        else:  # move
            ns = so + _dt.timedelta(days=delta_days)
            ne = eo + _dt.timedelta(days=delta_days)
            if ns < start:
                shift = (start - ns).days
                ns += _dt.timedelta(days=shift)
                ne += _dt.timedelta(days=shift)
            if ne > end:
                shift = (ne - end).days
                ns -= _dt.timedelta(days=shift)
                ne -= _dt.timedelta(days=shift)
        # Live preview without DB write
        for t in self._terms:
            if t.term_id == self._drag_term_id:
                t.start_date = _iso(ns)
                t.end_date = _iso(ne)
                break
        self._draw_gantt()

    def _gantt_release(self, _event: tk.Event) -> None:
        if self._drag_term_id is None:
            return
        tid = self._drag_term_id
        self._drag_term_id = None
        self._drag_kind = None
        self._drag_orig = None
        term = next((t for t in self._terms if t.term_id == tid), None)
        if term is None:
            self.refresh()
            return
        try:
            data.update_term(tid, {
                "start_date": term.start_date,
                "end_date": term.end_date,
            })
        except (ValidationError, Exception) as e:
            messagebox.showerror("Update failed", str(e))
        self.refresh()


# Sibling names used only at call time; imported last so any import order works.
from .dialogs import TermDialog  # noqa: E402
