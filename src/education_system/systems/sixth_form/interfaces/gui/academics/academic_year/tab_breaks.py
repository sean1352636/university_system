"""Breaks tab (bank holidays, ICS import) of the Sixth Form Academic Year window.

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
    Break,
    BREAK_TYPES,
    DEFAULT_BREAK_TYPE,
    Term,
    ValidationError,
)
from education_system.systems.sixth_form.domain.academics.academic_year.planning import (
    _uk_bank_holidays,
    _parse_ics,
)


# ══ Breaks tab ═════════════════════════════════════════════════════

# Break type → swatch colour (matches treeview row tags).
BREAK_COLOURS: dict[str, str] = {
    "INSET":        "#fff7d0",
    "Holiday":      "#eef7ff",
    "Half-Term":    "#cfe8ff",
    "Bank Holiday": "#ffe6d0",
    "Exam Period":  "#ead0ff",
    "Other":        "#e0e0e0",
}


def _dow_label(iso: str) -> str:
    try:
        return _dt.date.fromisoformat(iso).strftime("%a")
    except ValueError:
        return ""


class BreaksTab:
    LAST_TYPE: str = DEFAULT_BREAK_TYPE  # remembered between dialogs

    def __init__(self, nb: ttk.Notebook, state: dict) -> None:
        self.state = state
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Breaks")
        self._grouped: bool = False
        self._breaks: list[Break] = []
        self._terms: list[Term] = []
        self._build()
        self.refresh()

    # ── UI build ────────────────────────────────────────────────

    def _build(self) -> None:
        # Row 1 — year / type filter / refresh.
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 2))
        ttk.Label(bar, text="Year:").pack(side="left")
        self.year_cb = ttk.Combobox(bar, state="readonly", width=40)
        self.year_cb.pack(side="left", padx=(2, 10))
        self.year_cb.bind("<<ComboboxSelected>>",
                           lambda _e: self._on_year_change())
        ttk.Label(bar, text="Type:").pack(side="left")
        self.type_cb = ttk.Combobox(bar, values=("",) + BREAK_TYPES,
                                       state="readonly", width=14)
        self.type_cb.current(0)
        self.type_cb.bind("<<ComboboxSelected>>",
                            lambda _e: self.refresh())
        self.type_cb.pack(side="left", padx=(2, 10))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.group_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Group by type",
                          variable=self.group_var,
                          command=self._toggle_grouped).pack(
            side="left", padx=(10, 0))

        # Row 2 — date range filter.
        rng = ttk.Frame(self.frame)
        rng.pack(fill="x", padx=8, pady=(2, 2))
        ttk.Label(rng, text="Date range:").pack(side="left")
        self.from_e = ttk.Entry(rng, width=12)
        self.from_e.pack(side="left", padx=(2, 4))
        ttk.Label(rng, text="to").pack(side="left")
        self.to_e = ttk.Entry(rng, width=12)
        self.to_e.pack(side="left", padx=(2, 4))
        ttk.Button(rng, text="Apply",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(rng, text="Clear",
                    command=self._clear_range).pack(side="left")

        # Row 3 — colour legend.
        legend = ttk.Frame(self.frame)
        legend.pack(fill="x", padx=8, pady=(2, 4))
        ttk.Label(legend, text="Legend:").pack(side="left")
        for name, colour in BREAK_COLOURS.items():
            sw = tk.Label(legend, text=f" {name} ",
                            bg=colour, fg="#222",
                            relief="solid", borderwidth=1,
                            padx=4, pady=0)
            sw.pack(side="left", padx=2)

        # Table
        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "name", "type", "start", "end", "days", "check")
        self.tree = ttk.Treeview(
            table_frame, columns=cols,
            show="tree headings", selectmode="extended")
        headings = {"id": "ID", "name": "Name", "type": "Type",
                    "start": "Start (Day)", "end": "End (Day)",
                    "days": "Days", "check": "Check"}
        widths = {"id": 60, "name": 220, "type": 110,
                  "start": 130, "end": 130, "days": 70, "check": 140}
        self.tree.heading("#0", text="")
        self.tree.column("#0", width=20, stretch=False)
        for c in cols:
            self.tree.heading(c, text=headings[c])
            anchor = "center" if c == "days" else "w"
            self.tree.column(c, width=widths[c], anchor=anchor)
        vs = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for typ, colour in BREAK_COLOURS.items():
            self.tree.tag_configure(typ, background=colour)
        self.tree.tag_configure("group", background="#dadada",
                                   font=("TkDefaultFont", 9, "bold"))
        self.tree.tag_configure("outside-term", background="#ffe9e9")
        self.tree.bind("<Double-1>", lambda _e: self._edit_selected())

        self.count_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.count_var,
                   anchor="w").pack(fill="x", padx=8)

        # Action row 1 — CRUD
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

        # Action row 2 — quick adds & imports
        more = ttk.Frame(self.frame)
        more.pack(fill="x", padx=8, pady=(2, 8))
        ttk.Button(more, text="Add INSET day…",
                    command=self._quick_inset).pack(side="left")
        ttk.Button(more, text="Import UK bank holidays",
                    command=self._import_bank_holidays).pack(
            side="left", padx=4)
        ttk.Button(more, text="Recurring template…",
                    command=self._recurring_template).pack(
            side="left", padx=4)
        ttk.Button(more, text="Import .ics…",
                    command=self._import_ics).pack(side="left", padx=4)

    # ── year combo helpers ─────────────────────────────────────

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

    def _clear_range(self) -> None:
        self.from_e.delete(0, "end")
        self.to_e.delete(0, "end")
        self.refresh()

    def _toggle_grouped(self) -> None:
        self._grouped = bool(self.group_var.get())
        self.refresh()

    # ── refresh / render ────────────────────────────────────────

    def refresh(self) -> None:
        for i in self.tree.get_children():
            self.tree.delete(i)
        opts = self._year_options()
        self._year_ids = [yid for yid, _ in opts]
        labels = [lbl for _, lbl in opts]
        self.year_cb["values"] = labels

        if not opts:
            self.count_var.set("No academic years configured.")
            self._breaks = []
            self._terms = []
            return

        target = self.state.get("selected_year_id") or self._year_ids[0]
        try:
            idx = self._year_ids.index(target)
        except ValueError:
            idx = 0
            target = self._year_ids[0]
        self.year_cb.current(idx)
        self.state["selected_year_id"] = target

        btype = self.type_cb.get() or None
        try:
            rows = data.list_breaks(year_id=target, type=btype)
        except ValidationError as e:
            messagebox.showerror("Filter error", str(e))
            return

        # Apply date range filter
        frm = self.from_e.get().strip()
        to = self.to_e.get().strip()
        if frm:
            rows = [r for r in rows if r.end_date >= frm]
        if to:
            rows = [r for r in rows if r.start_date <= to]
        self._breaks = rows
        self._terms = data.list_terms(year_id=target)
        term_ranges = [(t.start_date, t.end_date) for t in self._terms]

        def in_any_term(b: Break) -> bool:
            for s, e in term_ranges:
                if not (b.end_date < s or b.start_date > e):
                    return True
            return False

        if self._grouped:
            by_type: dict[str, list[Break]] = {}
            for b in rows:
                by_type.setdefault(b.type, []).append(b)
            for typ in BREAK_TYPES:
                bs = by_type.get(typ, [])
                if not bs:
                    continue
                gid = f"grp:{typ}"
                self.tree.insert(
                    "", "end", iid=gid,
                    text=f"{typ}  ({len(bs)})",
                    values=("", "", "", "", "", "", ""),
                    tags=("group",), open=True)
                for b in bs:
                    self._insert_break_row(b, parent=gid,
                                             outside=not in_any_term(b))
        else:
            for b in rows:
                self._insert_break_row(b, parent="",
                                         outside=not in_any_term(b))

        total_days = sum(b.day_count for b in rows)
        per_type = {}
        for b in rows:
            per_type[b.type] = per_type.get(b.type, 0) + b.day_count
        per_str = "  ".join(f"{k}: {v}d" for k, v in per_type.items())
        outside_n = sum(1 for b in rows if not in_any_term(b))
        outside_str = (f"  ({outside_n} outside any term ⚠)"
                        if outside_n else "")
        self.count_var.set(
            f"{len(rows)} break(s), {total_days} day(s){outside_str}"
            + (f"  —  {per_str}" if per_str else ""))

    def _insert_break_row(self, b: Break, *, parent: str,
                            outside: bool) -> None:
        tags = []
        if b.type in BREAK_COLOURS:
            tags.append(b.type)
        if outside:
            tags.append("outside-term")
        start_lbl = f"{b.start_date} ({_dow_label(b.start_date)})"
        end_lbl = f"{b.end_date} ({_dow_label(b.end_date)})"
        check = "⚠ outside term" if outside else "✓"
        self.tree.insert(parent, "end", iid=str(b.break_id), values=(
            b.break_id, b.name, b.type, start_lbl, end_lbl,
            b.day_count, check,
        ), tags=tuple(tags))

    # ── selection ──────────────────────────────────────────────

    def _selected_id(self) -> int | None:
        for iid in self.tree.selection():
            if iid.startswith("grp:"):
                continue
            try:
                return int(iid)
            except ValueError:
                return None
        return None

    def _selected_ids(self) -> list[int]:
        out: list[int] = []
        for iid in self.tree.selection():
            if iid.startswith("grp:"):
                continue
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
        BreakDialog(self.frame.winfo_toplevel(), year=year,
                     existing=None,
                     default_type=BreaksTab.LAST_TYPE,
                     on_save=self._after_new)

    def _after_new(self, last_type: str | None = None) -> None:
        if last_type:
            BreaksTab.LAST_TYPE = last_type
        self.refresh()

    def _edit_selected(self) -> None:
        bid = self._selected_id()
        if bid is None:
            messagebox.showinfo("Edit", "Select a break first.")
            return
        existing = data.get_break(bid)
        if existing is None:
            return
        year = data.get_year(existing.year_id)
        if year is None:
            return
        BreakDialog(self.frame.winfo_toplevel(), year=year,
                     existing=existing, on_save=self._after_new)

    def _delete_selected(self) -> None:
        bid = self._selected_id()
        if bid is None:
            messagebox.showinfo("Delete", "Select a break first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete break #{bid}? (Soft-delete — Ctrl-Z to undo)"):
            return
        try:
            data.delete_break(bid)
        except Exception as e:
            messagebox.showerror("Delete failed", str(e))
            return
        undo = self.state.get("_undo")
        if undo is not None:
            undo.push(f"delete break #{bid}",
                       lambda i=bid: data.restore_break(i))
        toaster = self.state.get("_toast")
        if toaster:
            toaster(f"Deleted break #{bid} — Ctrl-Z to undo",
                      kind="warn")
        self.refresh()

    def _bulk_delete(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showinfo("Delete",
                                   "Select one or more breaks first.")
            return
        if not messagebox.askyesno(
                "Delete",
                f"Delete {len(ids)} break(s)? "
                "(Soft-delete — Ctrl-Z to undo)"):
            return
        errs: list[str] = []
        deleted: list[int] = []
        for bid in ids:
            try:
                if data.delete_break(bid):
                    deleted.append(bid)
            except Exception as e:
                errs.append(f"#{bid}: {e}")
        if errs:
            messagebox.showerror("Some deletes failed",
                                    "\n".join(errs))
        undo = self.state.get("_undo")
        if undo is not None and deleted:
            def _restore_many(_ids=deleted) -> None:
                for i in _ids:
                    try:
                        data.restore_break(i)
                    except Exception:
                        pass
            undo.push(f"bulk delete {len(deleted)} break(s)",
                       _restore_many)
        toaster = self.state.get("_toast")
        if toaster and deleted:
            toaster(f"Deleted {len(deleted)} break(s) — Ctrl-Z to undo",
                      kind="warn")
        self.refresh()

    # ── Quick adds / imports ────────────────────────────────────

    def _quick_inset(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("INSET", "Pick a year first.")
            return
        QuickInsetDialog(self.frame.winfo_toplevel(), year=year,
                          on_save=self.refresh)

    def _import_bank_holidays(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Bank holidays", "Pick a year first.")
            return
        try:
            ys = _dt.date.fromisoformat(year.start_date)
            ye = _dt.date.fromisoformat(year.end_date)
        except ValueError as e:
            messagebox.showerror("Bank holidays", str(e))
            return
        candidates = _uk_bank_holidays(ys, ye)
        if not candidates:
            messagebox.showinfo(
                "Bank holidays",
                "No bank holidays in the built-in table fall within "
                f"{year.name} ({year.start_date} → {year.end_date}).")
            return
        # Skip ones already present (by name + start date)
        existing = {(b.name, b.start_date)
                     for b in data.list_breaks(year_id=year.year_id)}
        new = [(n, d) for (n, d) in candidates
                if (n, d) not in existing]
        if not new:
            messagebox.showinfo("Bank holidays",
                                   "All bank holidays already exist.")
            return
        preview = "\n".join(f"  • {n}  {d}" for n, d in new[:12])
        more = "" if len(new) <= 12 else f"\n  …and {len(new) - 12} more"
        if not messagebox.askyesno(
                "Bank holidays",
                f"Import {len(new)} UK bank holiday(s) as Bank Holiday "
                f"breaks?\n\n{preview}{more}"):
            return
        errs: list[str] = []
        for name, iso in new:
            try:
                data.create_break({
                    "year_id": year.year_id, "name": name,
                    "type": "Bank Holiday",
                    "start_date": iso, "end_date": iso, "notes": None,
                })
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed", "\n".join(errs))
        self.refresh()

    def _recurring_template(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Recurring", "Pick a year first.")
            return
        RecurringBreakDialog(self.frame.winfo_toplevel(), year=year,
                               on_save=self.refresh)

    def _import_ics(self) -> None:
        year = self._current_year()
        if year is None:
            messagebox.showinfo("Import", "Pick a year first.")
            return
        path = filedialog.askopenfilename(
            filetypes=[("iCalendar", "*.ics"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as e:
            messagebox.showerror("Import", str(e))
            return
        events = _parse_ics(text)
        if not events:
            messagebox.showinfo("Import",
                                   "No usable VEVENTs found.")
            return
        # Filter to year range
        in_range = [(n, s, e) for (n, s, e) in events
                      if not (e < year.start_date
                                or s > year.end_date)]
        if not in_range:
            messagebox.showinfo("Import",
                                   f"No events fall within {year.name}.")
            return
        preview = "\n".join(f"  • {n}  {s} → {e}"
                              for n, s, e in in_range[:10])
        more = ("" if len(in_range) <= 10
                 else f"\n  …and {len(in_range) - 10} more")
        if not messagebox.askyesno(
                "Import",
                f"Import {len(in_range)} event(s) as Holiday breaks?\n\n"
                f"{preview}{more}"):
            return
        errs: list[str] = []
        added = 0
        for name, s, e in in_range:
            try:
                data.create_break({
                    "year_id": year.year_id,
                    "name": name, "type": "Holiday",
                    "start_date": s, "end_date": e, "notes": None,
                })
                added += 1
            except (ValidationError, Exception) as ex:
                errs.append(f"{name}: {ex}")
        if errs:
            messagebox.showerror("Some inserts failed",
                                    f"Added {added}.\n" + "\n".join(errs))
        self.refresh()


# Sibling names used only at call time; imported last so any import order works.
from .dialogs import BreakDialog, QuickInsetDialog, RecurringBreakDialog  # noqa: E402
