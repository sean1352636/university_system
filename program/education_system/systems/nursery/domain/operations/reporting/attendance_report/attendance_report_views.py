"""Tkinter view for the Attendance Report + register (Nursery System).

Renders into the shared content pane of ``main_gui.NurseryMainGUI`` (the
``host``): a From/To date range, a summary line, a per-child attendance
breakdown (low rates highlighted amber/red) and a Take-Register dialog that
sets a status for each active child for a chosen date.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from education_system.systems.nursery.domain.operations.reporting.attendance_report import (
    attendance_report as data,
)

logger = logging.getLogger(__name__)


def open_attendance_report_window(host) -> None:
    """Open the Attendance Report in the GUI host's content pane."""
    try:
        host._clear_content()
        root = host.content_frame
        ttk.Label(root, text="Attendance Report",
                  font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))

        lo_d, hi_d = data.default_range()
        bar = ttk.Frame(root)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="From:").pack(side="left", padx=(0, 2))
        from_var = tk.StringVar(value=lo_d)
        ttk.Entry(bar, textvariable=from_var, width=12).pack(side="left", padx=2)
        ttk.Label(bar, text="To:").pack(side="left", padx=(8, 2))
        to_var = tk.StringVar(value=hi_d)
        ttk.Entry(bar, textvariable=to_var, width=12).pack(side="left", padx=2)

        summary = ttk.Label(root, foreground="#555")

        cols = ("child", "room", "present", "late", "absent", "sick",
                "holiday", "total", "rate")
        tree = ttk.Treeview(root, columns=cols, show="headings", height=16)

        ttk.Button(bar, text="Refresh",
                   command=lambda: _refresh(tree, summary, from_var, to_var)).pack(
            side="left", padx=(10, 2))
        ttk.Button(bar, text="Export CSV",
                   command=lambda: _export(host, from_var, to_var)).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Take Register…",
                   command=lambda: _take_register(
                       host, tree, summary, from_var, to_var)).pack(
            side="left", padx=2)

        summary.pack(anchor="w", pady=(0, 6))

        for c, label, w in [
            ("child", "Child", 180), ("room", "Room", 140),
            ("present", "Present", 70), ("late", "Late", 60),
            ("absent", "Absent", 70), ("sick", "Sick", 60),
            ("holiday", "Holiday", 70), ("total", "Total", 60),
            ("rate", "Rate", 80),
        ]:
            tree.heading(c, text=label)
            tree.column(c, width=w, anchor="w")
        tree.tag_configure("low", foreground="#c0392b")
        tree.tag_configure("mid", foreground="#b9770e")
        tree.tag_configure("ok", foreground="#1e7e34")
        tree.pack(fill="both", expand=True)

        _refresh(tree, summary, from_var, to_var)
        host.status_var.set("Attendance report loaded")
    except Exception:
        logger.exception("open_attendance_report_window failed")
        try:
            messagebox.showerror(
                "Attendance Report",
                "Could not open the Attendance Report — see logs for details.",
                parent=getattr(host, "root", None))
        except Exception:
            logger.debug("Could not show error dialog", exc_info=True)


def _refresh(tree: ttk.Treeview, summary: ttk.Label,
             from_var: tk.StringVar, to_var: tk.StringVar) -> None:
    for i in tree.get_children():
        tree.delete(i)
    try:
        rep = data.report(from_var.get(), to_var.get())
    except data.ValidationError as e:
        messagebox.showerror("Attendance Report", str(e))
        return
    except Exception:
        logger.exception("Could not refresh attendance report")
        messagebox.showerror("Attendance Report", "Could not load — see logs.")
        return
    for c in rep["per_child"]:
        rate = c["rate"]
        if rate is None:
            tag = "ok"
        elif rate < 75:
            tag = "low"
        elif rate < 90:
            tag = "mid"
        else:
            tag = "ok"
        rr = "-" if rate is None else f"{rate}%"
        tree.insert("", "end", tags=(tag,), values=(
            c["name"], c["room"] or "-", c["present"], c["late"],
            c["absent"], c["sick"], c["holiday"], c["total"], rr))
    rate = "-" if rep["attendance_rate"] is None else f"{rep['attendance_rate']}%"
    arate = "-" if rep["absence_rate"] is None else f"{rep['absence_rate']}%"
    summary.config(
        text=f"Records: {rep['total']}   Attended: {rep['attended']}   "
             f"Attendance: {rate}   Absence: {arate}",
        foreground="#a00" if (rep["attendance_rate"] is not None
                              and rep["attendance_rate"] < 90) else "#555")


def _export(host, from_var: tk.StringVar, to_var: tk.StringVar) -> None:
    path = filedialog.asksaveasfilename(
        parent=getattr(host, "root", None), title="Export Attendance Report",
        defaultextension=".csv", filetypes=[("CSV files", "*.csv")],
        initialfile="attendance_report.csv")
    if not path:
        return
    try:
        res = data.export_csv(from_var.get(), to_var.get(), path=path)
        messagebox.showinfo(
            "Attendance Report",
            f"Wrote {res['row_count']} row(s) to:\n{res['path']}",
            parent=getattr(host, "root", None))
        host.status_var.set(f"Exported attendance report → {res['path']}")
    except data.ValidationError as e:
        messagebox.showerror("Attendance Report", str(e),
                             parent=getattr(host, "root", None))
    except OSError as e:
        messagebox.showerror("Attendance Report", str(e),
                             parent=getattr(host, "root", None))


def _take_register(host, tree: ttk.Treeview, summary: ttk.Label,
                   from_var: tk.StringVar, to_var: tk.StringVar) -> None:
    try:
        children = data.active_children()
    except Exception:
        logger.exception("Could not load children for register")
        messagebox.showerror("Attendance Report", "Could not load children.")
        return
    if not children:
        messagebox.showinfo("Attendance Report", "No active children on roll.",
                            parent=host.root)
        return

    dlg = tk.Toplevel(host.root)
    dlg.title("Take Register")
    dlg.transient(host.root)
    dlg.geometry("420x480")
    try:
        dlg.wait_visibility()
        dlg.grab_set()
    except tk.TclError:
        logger.debug("grab_set skipped", exc_info=True)

    frm = ttk.Frame(dlg, padding=12)
    frm.pack(fill="both", expand=True)
    top = ttk.Frame(frm)
    top.pack(fill="x", pady=(0, 8))
    ttk.Label(top, text="Date:").pack(side="left", padx=(0, 2))
    date_var = tk.StringVar(value=_dt.date.today().isoformat())
    ttk.Entry(top, textvariable=date_var, width=12).pack(side="left")

    canvas = tk.Canvas(frm, highlightthickness=0)
    scroll = ttk.Scrollbar(frm, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner.bind("<Configure>",
               lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)
    canvas.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    status_vars: list[tuple[str, str | None, tk.StringVar]] = []
    for pid, name, room in children:
        row = ttk.Frame(inner)
        row.pack(fill="x", pady=2)
        ttk.Label(row, text=name, width=24).pack(side="left")
        var = tk.StringVar(value="present")
        ttk.Combobox(row, textvariable=var, values=list(data.STATUSES),
                     width=12, state="readonly").pack(side="left")
        status_vars.append((pid, room, var))

    def _save() -> None:
        when = date_var.get()
        saved = 0
        for pid, room, var in status_vars:
            try:
                data.mark_attendance(pid, when, var.get(), room=room)
                saved += 1
            except data.ValidationError as e:
                messagebox.showerror("Attendance Report", str(e), parent=dlg)
                return
        dlg.destroy()
        _refresh(tree, summary, from_var, to_var)
        host.status_var.set(f"Saved {saved} register row(s) for {when}")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="right", padx=4)
    ttk.Button(btns, text="Save", command=_save).pack(side="right")
    dlg.wait_window()


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Attendance Report",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Attendance Report from the navigation menu."
              ).pack(anchor="w")
    return frame
