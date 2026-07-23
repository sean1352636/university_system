"""Tkinter views for Sixth Form Audit Reports."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date, timedelta as _td
from tkinter import filedialog, messagebox, ttk
from typing import Any

from education_system.shared import branding
from education_system.post_16.sixthform_system.modules.domain.reports.audit_reports import (
    audit_reports as data,
)
from education_system.post_16.sixthform_system.modules.domain.reports.audit_reports.audit_reports import (
    DEFAULT_EXPORT_FORMAT,
    EXPORT_FORMATS,
    REPORT_DESCRIPTIONS,
    REPORT_LABELS,
    REPORT_TYPES,
    ReportResult,
    ValidationError,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_FILTER_KEYS: tuple[tuple[str, str], ...] = (
    ("date_from",    "From (YYYY-MM-DD)"),
    ("date_to",      "To   (YYYY-MM-DD)"),
    ("actor",        "Actor"),
    ("action",       "Action"),
    ("entity_type",  "Entity type"),
    ("entity_id",    "Entity id"),
    ("severity",     "Severity"),
    ("source",       "Source"),
    ("summary_like", "Summary contains"),
    ("limit",        "Row limit"),
)


def open_audit_reports_window(parent=None) -> None:
    data.init_db()
    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"Audit Reports — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)
    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)
    RunTab(nb)
    SavedTab(nb)
    RunsTab(nb)
    OverviewTab(nb)


def _set_text(text: tk.Text, body: str) -> None:
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", body)
    text.configure(state="disabled")


def _render_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "(no rows)"
    widths = [
        max([len(str(h))] + [len(str(r[i])) for r in rows])
        for i, h in enumerate(headers)
    ]
    widths = [min(w, 40) for w in widths]
    lines = [
        "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)),
        "  ".join("-" * w for w in widths),
    ]
    for r in rows:
        lines.append("  ".join(
            str(r[i] if r[i] is not None else "")[:widths[i]].ljust(widths[i])
            for i in range(len(headers))))
    return "\n".join(lines)


# ══ Run tab ════════════════════════════════════════════════════════

class RunTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Run Report")
        self._current: ReportResult | None = None
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Report:").pack(side="left")
        self.type_cb = ttk.Combobox(
            top, values=[f"{REPORT_LABELS[r]} ({r})"
                          for r in REPORT_TYPES],
            state="readonly", width=42)
        self.type_cb.current(0)
        self.type_cb.pack(side="left", padx=(2, 10))
        self.type_cb.bind("<<ComboboxSelected>>",
                          lambda _e: self._update_desc())
        ttk.Button(top, text="Run", command=self._run).pack(
            side="left", padx=4)
        ttk.Button(top, text="Save snapshot",
                    command=self._save_snapshot).pack(side="left", padx=4)
        ttk.Button(top, text="Export…",
                    command=self._export).pack(side="left", padx=4)

        self.desc_var = tk.StringVar()
        ttk.Label(self.frame, textvariable=self.desc_var,
                   foreground="#444", wraplength=1100, anchor="w").pack(
            fill="x", padx=8)

        filt = ttk.LabelFrame(self.frame, text="Filters", padding=6)
        filt.pack(fill="x", padx=8, pady=6)
        self._filter_vars: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate(_FILTER_KEYS):
            row, col = divmod(i, 2)
            cell = ttk.Frame(filt)
            cell.grid(row=row, column=col, sticky="ew", padx=4, pady=2)
            filt.columnconfigure(col, weight=1)
            ttk.Label(cell, text=label, width=20,
                       anchor="e").pack(side="left")
            v = tk.StringVar()
            ttk.Entry(cell, textvariable=v).pack(
                side="left", fill="x", expand=True, padx=4)
            self._filter_vars[key] = v
        # Sensible defaults.
        self._filter_vars["date_from"].set(
            (_date.today() - _td(days=30)).isoformat())
        self._filter_vars["date_to"].set(_date.today().isoformat())
        self._filter_vars["limit"].set("5000")

        out = ttk.LabelFrame(self.frame, text="Result")
        out.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.text = tk.Text(out, wrap="none", font=("TkFixedFont", 10),
                            state="disabled")
        vs = ttk.Scrollbar(out, orient="vertical",
                            command=self.text.yview)
        hs = ttk.Scrollbar(out, orient="horizontal",
                            command=self.text.xview)
        self.text.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        out.rowconfigure(0, weight=1)
        out.columnconfigure(0, weight=1)

        self.status = tk.StringVar(value="Pick a report and Run.")
        ttk.Label(self.frame, textvariable=self.status,
                   foreground="#444", anchor="w").pack(fill="x",
                                                          padx=8)
        self._update_desc()

    def _current_type(self) -> str:
        return REPORT_TYPES[self.type_cb.current()]

    def _update_desc(self) -> None:
        rt = self._current_type()
        self.desc_var.set(REPORT_DESCRIPTIONS.get(rt, ""))

    def _collect_filters(self) -> dict[str, Any]:
        return {k: v.get().strip()
                for k, v in self._filter_vars.items()
                if v.get().strip()}

    def _run(self) -> None:
        rt = self._current_type()
        try:
            result = data.run_report(
                rt, filters=self._collect_filters())
        except ValidationError as e:
            messagebox.showerror("Run report", str(e))
            return
        except Exception as e:
            logger.exception("audit-report run crashed")
            messagebox.showerror("Run report", str(e))
            return
        self._current = result
        meta = (f"{result.label}  ({result.report_type})\n"
                 f"Generated: {result.generated_at}\n")
        if result.filters:
            meta += "Filters: " + ", ".join(
                f"{k}={v}" for k, v in result.filters.items()) + "\n"
        meta += f"Rows: {result.row_count}\n\n"
        body = meta + _render_table(result.headers, result.rows)
        _set_text(self.text, body)
        self.status.set(f"{result.row_count} row(s).")

    def _save_snapshot(self) -> None:
        if self._current is None:
            messagebox.showinfo("Save snapshot", "Run a report first.")
            return
        try:
            data.save_run(self._current)
        except Exception as e:
            logger.exception("save_run crashed")
            messagebox.showerror("Save snapshot", str(e))
            return
        self.status.set("Snapshot saved.")
        messagebox.showinfo("Save snapshot", "Snapshot saved.")

    def _export(self) -> None:
        if self._current is None:
            messagebox.showinfo("Export", "Run a report first.")
            return
        path = filedialog.asksaveasfilename(
            initialfile=(f"audit_{self._current.report_type}_"
                          f"{_date.today().isoformat()}.csv"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("TSV", "*.tsv"),
                       ("JSON", "*.json"), ("Markdown", "*.md"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            res = data.export(self._current, path)
        except ValidationError as e:
            messagebox.showerror("Export", str(e))
            return
        except Exception as e:
            logger.exception("export crashed")
            messagebox.showerror("Export", str(e))
            return
        self.status.set(
            f"Wrote {res['row_count']} row(s) → {res['path']}")
        messagebox.showinfo(
            "Export complete",
            f"{res['row_count']} row(s) written\n{res['path']}")


# ══ Saved tab ══════════════════════════════════════════════════════

class SavedTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Saved Reports")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="New…",
                    command=self._new).pack(side="left")
        ttk.Button(bar, text="Edit…",
                    command=self._edit).pack(side="left", padx=4)
        ttk.Button(bar, text="Run",
                    command=self._run).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)

        cols = ("def_id", "name", "type", "desc", "created_by",
                "updated_at")
        widths = {"def_id": 60, "name": 200, "type": 160,
                   "desc": 320, "created_by": 100,
                   "updated_at": 150}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols,
                                    show="headings", height=20)
        for c, h in zip(cols, ("#", "Name", "Type", "Description",
                                  "Created by", "Updated")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._run())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for d in data.list_defs():
            self.tree.insert("", "end", iid=str(d.def_id), values=(
                d.def_id, d.name, d.type_label,
                d.description or "", d.created_by or "",
                d.updated_at))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _new(self) -> None:
        DefDialog(self.frame, on_save=self._save_new)

    def _save_new(self, payload: dict[str, Any]) -> None:
        try:
            data.create_def(payload)
        except ValidationError as e:
            messagebox.showerror("Save report", str(e))
            return
        self.refresh()

    def _edit(self) -> None:
        did = self._selected_id()
        if did is None:
            messagebox.showinfo("Edit", "Pick a saved report first.")
            return
        existing = data.get_def(did)
        if existing is None:
            messagebox.showerror("Edit", f"No saved report #{did}")
            return
        DefDialog(self.frame, existing=existing,
                  on_save=lambda p: self._save_edit(did, p))

    def _save_edit(self, did: int, payload: dict[str, Any]) -> None:
        try:
            data.update_def(did, payload)
        except ValidationError as e:
            messagebox.showerror("Edit", str(e))
            return
        self.refresh()

    def _run(self) -> None:
        did = self._selected_id()
        if did is None:
            messagebox.showinfo("Run", "Pick a saved report first.")
            return
        try:
            result = data.run_def(did)
        except ValidationError as e:
            messagebox.showerror("Run", str(e))
            return
        ResultViewer(self.frame, result, def_id=did)

    def _delete(self) -> None:
        did = self._selected_id()
        if did is None:
            messagebox.showinfo("Delete", "Pick a saved report first.")
            return
        if not messagebox.askyesno(
                "Delete", f"Delete saved report #{did}?"):
            return
        data.delete_def(did)
        self.refresh()


class DefDialog(tk.Toplevel):
    def __init__(self, master, existing=None, *, on_save) -> None:
        super().__init__(master)
        self.title("Saved Report")
        self.geometry("640x560")
        self.transient(master.winfo_toplevel())
        self.after_idle(self.grab_set)
        self._on_save = on_save
        self._existing = existing
        self._build()

    def _build(self) -> None:
        pad = {"padx": 8, "pady": 4}
        wrap = ttk.Frame(self, padding=10)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="Name:").grid(row=0, column=0,
                                              sticky="e", **pad)
        self.name_e = ttk.Entry(wrap, width=42)
        self.name_e.grid(row=0, column=1, sticky="ew", **pad)

        ttk.Label(wrap, text="Type:").grid(row=1, column=0,
                                              sticky="e", **pad)
        self.type_cb = ttk.Combobox(
            wrap, values=[f"{REPORT_LABELS[r]} ({r})"
                          for r in REPORT_TYPES],
            state="readonly", width=40)
        self.type_cb.grid(row=1, column=1, sticky="ew", **pad)
        self.type_cb.current(0)

        ttk.Label(wrap, text="Description:").grid(row=2, column=0,
                                                      sticky="e", **pad)
        self.desc_e = ttk.Entry(wrap, width=42)
        self.desc_e.grid(row=2, column=1, sticky="ew", **pad)

        ttk.Label(wrap, text="Created by:").grid(row=3, column=0,
                                                     sticky="e", **pad)
        self.by_e = ttk.Entry(wrap, width=42)
        self.by_e.grid(row=3, column=1, sticky="ew", **pad)

        filt = ttk.LabelFrame(wrap, text="Filters", padding=6)
        filt.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        self._filter_vars: dict[str, tk.StringVar] = {}
        for i, (key, label) in enumerate(_FILTER_KEYS):
            row, col = divmod(i, 2)
            cell = ttk.Frame(filt)
            cell.grid(row=row, column=col, sticky="ew", padx=4, pady=2)
            filt.columnconfigure(col, weight=1)
            ttk.Label(cell, text=label, width=20,
                       anchor="e").pack(side="left")
            v = tk.StringVar()
            ttk.Entry(cell, textvariable=v).pack(
                side="left", fill="x", expand=True, padx=4)
            self._filter_vars[key] = v

        wrap.columnconfigure(1, weight=1)

        btns = ttk.Frame(wrap)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=8)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="left", padx=4)

        if self._existing is not None:
            e = self._existing
            self.name_e.insert(0, e.name)
            try:
                self.type_cb.current(REPORT_TYPES.index(e.report_type))
            except ValueError:
                pass
            self.desc_e.insert(0, e.description or "")
            self.by_e.insert(0, e.created_by or "")
            for k, v in self._filter_vars.items():
                if k in e.filters:
                    v.set(str(e.filters[k]))

    def _save(self) -> None:
        payload = {
            "name": self.name_e.get().strip(),
            "report_type":
                REPORT_TYPES[self.type_cb.current()]
                if self.type_cb.current() >= 0 else REPORT_TYPES[0],
            "description": self.desc_e.get().strip(),
            "created_by": self.by_e.get().strip() or None,
            "filters": {k: v.get().strip()
                         for k, v in self._filter_vars.items()
                         if v.get().strip()},
        }
        if not payload["name"]:
            messagebox.showerror("Save", "Name is required.")
            return
        self._on_save(payload)
        self.destroy()


class ResultViewer(tk.Toplevel):
    def __init__(self, master, result: ReportResult, *,
                 def_id: int | None = None) -> None:
        super().__init__(master)
        self.title(f"{result.label} — Run result")
        self.geometry("1200x720")
        self.transient(master.winfo_toplevel())
        self._result = result
        self._def_id = def_id
        self._build()

    def _build(self) -> None:
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text=self._result.label,
                   font=("", 12, "bold")).pack(side="left")
        ttk.Button(top, text="Save snapshot",
                    command=self._save).pack(side="right", padx=4)
        ttk.Button(top, text="Export…",
                    command=self._export).pack(side="right", padx=4)
        meta = (f"Generated: {self._result.generated_at}    "
                f"Rows: {self._result.row_count}")
        if self._result.filters:
            meta += "    Filters: " + ", ".join(
                f"{k}={v}" for k, v in self._result.filters.items())
        ttk.Label(self, text=meta, foreground="#444").pack(
            fill="x", padx=8)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        text = tk.Text(frame, wrap="none", font=("TkFixedFont", 10))
        vs = ttk.Scrollbar(frame, orient="vertical",
                            command=text.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal",
                            command=text.xview)
        text.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        text.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text.insert("1.0", _render_table(
            self._result.headers, self._result.rows))
        text.configure(state="disabled")

    def _save(self) -> None:
        try:
            data.save_run(self._result, def_id=self._def_id)
        except Exception as e:
            messagebox.showerror("Save snapshot", str(e))
            return
        messagebox.showinfo("Save snapshot", "Snapshot saved.")

    def _export(self) -> None:
        path = filedialog.asksaveasfilename(
            initialfile=(f"audit_{self._result.report_type}_"
                          f"{_date.today().isoformat()}.csv"),
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("TSV", "*.tsv"),
                       ("JSON", "*.json"), ("Markdown", "*.md"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            res = data.export(self._result, path)
        except Exception as e:
            messagebox.showerror("Export", str(e))
            return
        messagebox.showinfo(
            "Export complete",
            f"{res['row_count']} row(s) written\n{res['path']}")


# ══ Past runs tab ══════════════════════════════════════════════════

class RunsTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Past Runs")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="View",
                    command=self._view).pack(side="left")
        ttk.Button(bar, text="Delete",
                    command=self._delete).pack(side="left", padx=4)
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)

        cols = ("run_id", "run_at", "report_type", "name",
                "row_count", "run_by")
        widths = {"run_id": 60, "run_at": 160, "report_type": 160,
                   "name": 220, "row_count": 80, "run_by": 120}
        wrap = ttk.Frame(self.frame)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                    height=20)
        for c, h in zip(cols, ("#", "When", "Type", "Name",
                                  "Rows", "Run by")):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=widths[c], anchor="w")
        vs = ttk.Scrollbar(wrap, orient="vertical",
                            command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._view())

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for r in data.list_runs(limit=500):
            self.tree.insert("", "end", iid=str(r.run_id), values=(
                r.run_id, r.run_at,
                REPORT_LABELS.get(r.report_type, r.report_type),
                r.name, r.row_count, r.run_by or ""))

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except ValueError:
            return None

    def _view(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("View", "Pick a run first.")
            return
        r = data.get_run(rid)
        if r is None:
            messagebox.showerror("View", f"No run #{rid}")
            return
        ResultViewer(self.frame, r.as_result(), def_id=r.def_id)

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            messagebox.showinfo("Delete", "Pick a run first.")
            return
        if not messagebox.askyesno("Delete", f"Delete run #{rid}?"):
            return
        data.delete_run(rid)
        self.refresh()


# ══ Overview tab ═══════════════════════════════════════════════════

class OverviewTab:
    def __init__(self, nb: ttk.Notebook) -> None:
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Overview")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left")
        self.text = tk.Text(self.frame, wrap="word",
                             font=("TkFixedFont", 10),
                             state="disabled")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)

    def refresh(self) -> None:
        try:
            o = data.overview()
        except Exception as e:
            _set_text(self.text, f"Error: {e}")
            return
        lines = [
            "═══ Audit Overview ═══",
            "",
            f"  Total events       : {o.total_events}",
            f"  Last 24h           : {o.last_24h}",
            f"  Last 7 days        : {o.last_7d}",
            f"  Last 30 days       : {o.last_30d}",
            f"  Failed logins (24h): {o.failed_logins_24h}",
            f"  Deletes (24h)      : {o.deletes_24h}",
            f"  Saved reports      : {o.saved_report_count}",
            f"  Saved run snapshots: {o.saved_run_count}",
            "",
            "  By severity:",
        ]
        for s, n in o.by_severity.items():
            if n:
                lines.append(f"    {s:<10} : {n}")
        if o.by_action_top:
            lines.append("\n  Top actions:")
            for k, n in o.by_action_top:
                lines.append(f"    {k:<18} : {n}")
        if o.by_actor_top:
            lines.append("\n  Top actors:")
            for k, n in o.by_actor_top:
                lines.append(f"    {k[:30]:<30} : {n}")
        _set_text(self.text, "\n".join(lines))
