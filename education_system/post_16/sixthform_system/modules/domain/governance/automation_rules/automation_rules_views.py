"""GUI panels for the Sixth Form Automation Rules engine.

Two-tab Notebook:

* Rules — define / enable / delete rules and run the engine.
* Worklist — the actions the engine has raised, with resolve buttons.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk

from education_system.post_16.sixthform_system.modules.domain.governance.automation_rules import (
    automation_rules as data,
)

logger = logging.getLogger(__name__)

_SEV_COLOUR = {"Low": "#2e7d32", "Medium": "#f9a825",
               "High": "#ef6c00", "Critical": "#c62828"}


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(anchor="w", pady=(0, 8))


def open_directory(gui) -> None:
    parent = _clear(gui)
    _heading(parent, "Automation Rules")
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    rules = ttk.Frame(nb, padding=10)
    work = ttk.Frame(nb, padding=10)
    nb.add(rules, text="Rules")
    nb.add(work, text="Action Worklist")
    refresh_work = _build_worklist_tab(gui, work)
    _build_rules_tab(gui, rules, refresh_work)


def _build_rules_tab(gui, parent, refresh_work) -> None:
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))

    cols = ("id", "on", "name", "trigger", "sev", "matches")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
    for c, t, w in (("id", "ID", 40), ("on", "On", 36), ("name", "Name", 160),
                    ("trigger", "Trigger", 260), ("sev", "Severity", 80),
                    ("matches", "Matches", 70)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w" if c in ("name", "trigger") else "center")
    tree.pack(fill="both", expand=True)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for r in data.list_rules():
            tree.insert("", "end", iid=str(r["rule_id"]),
                        values=(r["rule_id"], "✓" if r["enabled"] else "·", r["name"],
                                f"{r['trigger_label']} {r['threshold']:g}",
                                r["severity"], r["last_matches"]))

    def toggle() -> None:
        sel = tree.selection()
        if not sel:
            return
        rules = {str(r["rule_id"]): r for r in data.list_rules()}
        cur = rules[sel[0]]["enabled"]
        data.set_enabled(int(sel[0]), not cur)
        refresh()

    def delete() -> None:
        sel = tree.selection()
        if sel and messagebox.askyesno("Delete", f"Delete rule #{sel[0]}?"):
            data.delete_rule(int(sel[0]))
            refresh()

    def run_engine() -> None:
        res = data.run_rules()
        messagebox.showinfo("Automation",
                            f"{res['rules_run']} rule(s) run, "
                            f"{res.get('matches', 0)} match(es), "
                            f"{res['new_actions']} new action(s).")
        refresh()
        refresh_work()

    ttk.Button(bar, text="Add rule…", command=lambda: _add_dialog(refresh)).pack(side="left")
    ttk.Button(bar, text="Enable/disable", command=toggle).pack(side="left", padx=6)
    ttk.Button(bar, text="Delete", command=delete).pack(side="left")
    ttk.Button(bar, text="Run engine now", command=run_engine).pack(side="right")
    refresh()


def _add_dialog(after) -> None:
    top = tk.Toplevel()
    top.title("New automation rule")
    top.geometry("420x360")
    frm = ttk.Frame(top, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Name:").pack(anchor="w")
    name_var = tk.StringVar()
    ttk.Entry(frm, textvariable=name_var).pack(fill="x")

    ttk.Label(frm, text="Trigger:").pack(anchor="w", pady=(8, 0))
    trig_labels = [f"{t.label} ({t.unit})" for t in data.TRIGGERS]
    trig_var = tk.StringVar(value=trig_labels[0])
    ttk.Combobox(frm, textvariable=trig_var, state="readonly",
                 values=trig_labels).pack(fill="x")

    ttk.Label(frm, text="Threshold:").pack(anchor="w", pady=(8, 0))
    thr_var = tk.StringVar()
    ttk.Entry(frm, textvariable=thr_var).pack(fill="x")

    ttk.Label(frm, text="Action label:").pack(anchor="w", pady=(8, 0))
    act_var = tk.StringVar()
    ttk.Entry(frm, textvariable=act_var).pack(fill="x")

    ttk.Label(frm, text="Severity:").pack(anchor="w", pady=(8, 0))
    sev_var = tk.StringVar(value="Medium")
    ttk.Combobox(frm, textvariable=sev_var, state="readonly",
                 values=list(data.SEVERITIES)).pack(fill="x")

    def save() -> None:
        trig = data.TRIGGERS[trig_labels.index(trig_var.get())]
        try:
            data.create_rule(name=name_var.get(), trigger_key=trig.key,
                             threshold=float(thr_var.get()), action_label=act_var.get(),
                             severity=sev_var.get())
        except (data.ValidationError, ValueError) as e:
            messagebox.showerror("New rule", str(e), parent=top)
            return
        top.destroy()
        after()

    ttk.Button(frm, text="Create", command=save).pack(pady=12)


def _build_worklist_tab(gui, parent):
    bar = ttk.Frame(parent)
    bar.pack(fill="x", pady=(0, 8))
    status_var = tk.StringVar(value="Open")
    ttk.Label(bar, text="Status:").pack(side="left")
    ttk.Combobox(bar, textvariable=status_var, state="readonly", width=12,
                 values=["Open", "Done", "Dismissed"]).pack(side="left", padx=(4, 10))

    cols = ("id", "sev", "rule", "message")
    tree = ttk.Treeview(parent, columns=cols, show="headings", height=16)
    for c, t, w in (("id", "ID", 50), ("sev", "Severity", 80),
                    ("rule", "Rule", 150), ("message", "Detail", 420)):
        tree.heading(c, text=t)
        tree.column(c, width=w, anchor="w" if c in ("rule", "message") else "center")
    for s, col in _SEV_COLOUR.items():
        tree.tag_configure(s, foreground=col)
    tree.pack(fill="both", expand=True)

    def refresh() -> None:
        tree.delete(*tree.get_children())
        for a in data.list_actions(status=status_var.get()):
            tree.insert("", "end", iid=str(a["action_id"]), tags=(a["severity"],),
                        values=(a["action_id"], a["severity"], a["rule_name"], a["message"]))

    def resolve(status: str) -> None:
        sel = tree.selection()
        if not sel:
            return
        try:
            data.resolve_action(int(sel[0]), status=status)
        except data.ValidationError as e:
            messagebox.showerror("Resolve", str(e))
            return
        refresh()

    ttk.Button(bar, text="Mark done", command=lambda: resolve("Done")).pack(side="right")
    ttk.Button(bar, text="Dismiss", command=lambda: resolve("Dismissed")).pack(side="right", padx=6)
    ttk.Button(bar, text="Refresh", command=refresh).pack(side="right")
    status_var.trace_add("write", lambda *_: refresh())
    refresh()
    return refresh
