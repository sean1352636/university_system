"""GUI panels for Sixth Form Behaviour Log.

Four tabs:

* Directory  — filterable list (student, type, category, severity,
  date range, follow-up flag).
* Editor     — full add/edit form for a single entry.
* Per-student — pick a student, see their entries + running totals.
* Summary    — by type, severity, top students, follow-up alerts.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.pastoral.behaviour import behaviour
from education_system.post_16.sixthform_system.modules.domain.pastoral.behaviour import behaviour as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.pastoral.behaviour.behaviour import (
    ALL_CATEGORIES,
    BehaviourEntry,
    ENTRY_TYPES,
    NEGATIVE_CATEGORIES,
    POSITIVE_CATEGORIES,
    SEVERITIES,
    ValidationError,
)

logger = logging.getLogger(__name__)


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Behaviour Log")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    editor_tab = ttk.Frame(nb, padding=8)
    student_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(editor_tab,  text="Editor")
    nb.add(student_tab, text="Per-student")
    nb.add(summary_tab, text="Summary")

    _build_directory_tab(gui, dir_tab)
    _build_editor_tab(gui, editor_tab)
    _build_student_tab(gui, student_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    type_var = tk.StringVar()
    category_var = tk.StringVar()
    severity_var = tk.StringVar()
    from_var = tk.StringVar()
    to_var = tk.StringVar()
    follow_up_var = tk.StringVar(value="All")

    ttk.Label(filt, text="Student:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Type:").pack(side="left")
    ttk.Combobox(filt, textvariable=type_var,
                 values=["", *ENTRY_TYPES], state="readonly", width=10
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Category:").pack(side="left")
    ttk.Combobox(filt, textvariable=category_var,
                 values=["", *ALL_CATEGORIES],
                 state="readonly", width=20
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Severity:").pack(side="left")
    ttk.Combobox(filt, textvariable=severity_var,
                 values=["", *SEVERITIES], state="readonly", width=10
                 ).pack(side="left", padx=(4, 4))

    filt2 = ttk.Frame(parent)
    filt2.pack(anchor="w", fill="x", pady=(0, 8))
    ttk.Label(filt2, text="From:").pack(side="left")
    ttk.Entry(filt2, textvariable=from_var, width=12
              ).pack(side="left", padx=(4, 8))
    ttk.Label(filt2, text="To:").pack(side="left")
    ttk.Entry(filt2, textvariable=to_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt2, text="Follow-up:").pack(side="left")
    ttk.Combobox(filt2, textvariable=follow_up_var,
                 values=["All", "Required", "Not required"],
                 state="readonly", width=14
                 ).pack(side="left", padx=(4, 4))

    table_holder = ttk.Frame(parent)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(parent, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(parent)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()
        fu_filter: bool | None = None
        if follow_up_var.get() == "Required":
            fu_filter = True
        elif follow_up_var.get() == "Not required":
            fu_filter = False
        try:
            rows = data.list_entries_with_detail(
                student_id=sid_var.get().strip() or None,
                entry_type=type_var.get().strip() or None,
                category=category_var.get().strip() or None,
                severity=severity_var.get().strip() or None,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
                follow_up_required=fu_filter,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_entries failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("entry_id", "student", "name", "entry_date",
                "type", "category", "severity", "points",
                "follow_up", "parent")
        headings = {
            "entry_id":   ("#",         50),
            "student":    ("Student",  100),
            "name":       ("Name",     150),
            "entry_date": ("Date",     100),
            "type":       ("Type",      80),
            "category":   ("Category", 140),
            "severity":   ("Sev.",      60),
            "points":     ("Pts",       50),
            "follow_up":  ("Follow-up", 90),
            "parent":     ("Parent?",   70),
        }
        tree = ttk.Treeview(table_holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for r in rows:
            e = r.entry
            fu = e.follow_up_date or ("Yes" if e.follow_up_required else "—")
            tree.insert("", "end", iid=str(e.entry_id), values=(
                e.entry_id, e.student_id, r.student_name,
                e.entry_date, e.entry_type, e.category,
                e.severity or "—",
                ("+" if e.points >= 0 else "") + str(e.points),
                fu,
                "Yes" if e.parent_contacted else "No",
            ))
        summary.configure(text=f"{len(rows)} entry/entries.")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            eid = _selected()
            if eid is None:
                messagebox.showinfo("No selection",
                                    "Pick an entry first.",
                                    parent=gui.root)
            return eid

        def _edit() -> None:
            eid = _require()
            if eid is None:
                return
            open_editor(gui, entry_id=eid)

        def _delete() -> None:
            eid = _require()
            if eid is None:
                return
            if not messagebox.askyesno(
                "Delete entry",
                f"Delete behaviour entry #{eid}?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_entry(eid)
            except Exception as e:
                logger.exception("delete_entry crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Open in editor",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_editor(gui, entry_id=None)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Behaviour entries: {len(rows)} match(es)")

    ttk.Button(filt2, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt2, text="Clear",
               command=lambda: (sid_var.set(""), type_var.set(""),
                                category_var.set(""), severity_var.set(""),
                                from_var.set(""), to_var.set(""),
                                follow_up_var.set("All"), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Editor tab + standalone ────────────────────────────────────────

def _build_editor_tab(gui, parent: ttk.Frame) -> None:
    rows = data.list_entries()
    if rows:
        _render_editor(gui, parent, rows[0].entry_id)
    else:
        ttk.Label(
            parent,
            text="No entries yet. Use Directory → New to add one.",
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_editor(gui, *, entry_id: int | None) -> None:
    frame = _clear(gui)
    _heading(frame,
             f"Behaviour Entry #{entry_id}"
             if entry_id else "New Behaviour Entry")
    _render_editor(gui, frame, entry_id)
    ttk.Button(frame, text="Back to Behaviour Log",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_editor(gui, parent: ttk.Frame, entry_id: int | None) -> None:
    existing = data.get_entry(entry_id) if entry_id else None

    form = ttk.Frame(parent)
    form.pack(anchor="w", fill="x", pady=(0, 8))
    form.columnconfigure(1, weight=1, minsize=320)

    if existing:
        ttk.Label(form, text="Student:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=2)
        ttk.Label(form, text=existing.student_id,
                  foreground="#555").grid(
            row=0, column=1, sticky="w", pady=2)
        student_var = tk.StringVar(value=existing.student_id)
        student_by_label = {}
    else:
        students = student_data.list_students()
        student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
        student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                            for s in students}
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        ttk.Label(form, text="Student *:").grid(
            row=0, column=0, sticky="e", padx=(0, 8), pady=2)
        ttk.Combobox(form, textvariable=student_var,
                     values=student_labels,
                     state="readonly", width=42
                     ).grid(row=0, column=1, sticky="w", pady=2)

    today = _date.today().isoformat()
    date_var = tk.StringVar(
        value=existing.entry_date if existing else today)
    type_var = tk.StringVar(
        value=existing.entry_type if existing else "Positive")
    category_var = tk.StringVar(
        value=existing.category if existing else POSITIVE_CATEGORIES[0])
    severity_var = tk.StringVar(
        value=(existing.severity or "") if existing else "")
    points_var = tk.StringVar(
        value=str(existing.points) if existing else "")
    location_var = tk.StringVar(
        value=(existing.location or "") if existing else "")
    recorded_var = tk.StringVar(
        value=(existing.recorded_by or "") if existing else "")
    action_var = tk.StringVar(
        value=(existing.action_taken or "") if existing else "")
    follow_up_var = tk.BooleanVar(
        value=bool(existing.follow_up_required) if existing else False)
    follow_up_date_var = tk.StringVar(
        value=(existing.follow_up_date or "") if existing else "")
    parent_var = tk.BooleanVar(
        value=bool(existing.parent_contacted) if existing else False)

    description_text = tk.Text(form, height=4, width=60)
    if existing and existing.description:
        description_text.insert("1.0", existing.description)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=2)
        widget.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Date *",
        ttk.Entry(form, textvariable=date_var, width=14))

    type_combo = ttk.Combobox(form, textvariable=type_var,
                               values=list(ENTRY_TYPES),
                               state="readonly", width=12)
    row(2, "Type *", type_combo)

    category_combo = ttk.Combobox(form, textvariable=category_var,
                                   state="readonly", width=28)
    row(3, "Category *", category_combo)

    # Switch the category options when the type changes.
    def _on_type_changed(*_a) -> None:
        if type_var.get() == "Positive":
            category_combo["values"] = list(POSITIVE_CATEGORIES)
            if category_var.get() not in POSITIVE_CATEGORIES:
                category_var.set(POSITIVE_CATEGORIES[0])
        else:
            category_combo["values"] = list(NEGATIVE_CATEGORIES)
            if category_var.get() not in NEGATIVE_CATEGORIES:
                category_var.set(NEGATIVE_CATEGORIES[0])
    type_var.trace_add("write", _on_type_changed)
    _on_type_changed()

    row(4, "Severity (Negative only)",
        ttk.Combobox(form, textvariable=severity_var,
                     values=["", *SEVERITIES],
                     state="readonly", width=12))
    row(5, "Points (blank = default)",
        ttk.Entry(form, textvariable=points_var, width=10))
    row(6, "Location",
        ttk.Entry(form, textvariable=location_var, width=32))
    row(7, "Recorded by",
        ttk.Entry(form, textvariable=recorded_var, width=24))
    ttk.Label(form, text="Description *").grid(
        row=8, column=0, sticky="ne", padx=(0, 8), pady=2)
    description_text.grid(row=8, column=1, sticky="w", pady=2)
    row(9, "Action taken",
        ttk.Entry(form, textvariable=action_var, width=42))
    row(10, "Follow-up required",
        ttk.Checkbutton(form, variable=follow_up_var))
    row(11, "Follow-up date (YYYY-MM-DD)",
        ttk.Entry(form, textvariable=follow_up_date_var, width=14))
    row(12, "Parent contacted",
        ttk.Checkbutton(form, variable=parent_var))

    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(12, 0))

    def save() -> None:
        if existing:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=gui.root)
                return
        payload = {
            "student_id":        sid,
            "entry_date":        date_var.get(),
            "entry_type":        type_var.get(),
            "category":          category_var.get(),
            "severity":          severity_var.get(),
            "points":            points_var.get(),
            "location":          location_var.get(),
            "description":       description_text.get("1.0", "end-1c").strip(),
            "recorded_by":       recorded_var.get(),
            "action_taken":      action_var.get(),
            "follow_up_required": follow_up_var.get(),
            "follow_up_date":    follow_up_date_var.get(),
            "parent_contacted":  parent_var.get(),
        }
        try:
            if existing:
                saved = data.update_entry(existing.entry_id, payload)
            else:
                saved = data.create_entry(payload)
        except ValidationError as e:
            logger.warning("save behaviour entry rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save behaviour entry crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set(f"Saved behaviour entry #{saved.entry_id}")
        messagebox.showinfo("Saved",
                            f"Saved entry #{saved.entry_id}.",
                            parent=gui.root)
        open_editor(gui, entry_id=saved.entry_id)

    def delete() -> None:
        if not existing:
            return
        if not messagebox.askyesno(
            "Delete entry",
            f"Delete behaviour entry #{existing.entry_id}?",
            parent=gui.root,
        ):
            return
        try:
            data.delete_entry(existing.entry_id)
        except Exception as e:
            logger.exception("delete_entry crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set("Deleted entry")
        open_directory(gui)

    ttk.Button(actions, text="Save",
               command=save).pack(side="left", padx=(0, 6))
    if existing:
        ttk.Button(actions, text="Delete",
                   command=delete).pack(side="left", padx=(0, 6))


# ─── Per-student tab ────────────────────────────────────────────────

def _build_student_tab(gui, parent: ttk.Frame) -> None:
    students = student_data.list_students()
    labels = [f"{s.student_id} — {s.full_name}" for s in students]
    by_label = {lbl: s.student_id for lbl, s in zip(labels, students)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    student_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Student:").pack(side="left")
    ttk.Combobox(bar, textvariable=student_var, values=labels,
                 state="readonly", width=42
                 ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)
    stats_label = ttk.Label(parent, text="", foreground="#333")
    stats_label.pack(anchor="w", pady=(8, 0))

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        sid = by_label.get(student_var.get())
        if not sid:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            stats_label.configure(text="")
            return
        student = student_data.get_student(sid)
        summ = data.per_student_summary(sid)
        rows = data.entries_for_student(sid)
        ttk.Label(holder,
                  text=f"{student.student_id}  {student.full_name}"
                       if student else f"{sid} (deleted)",
                  font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))

        if not rows:
            ttk.Label(holder, text="(no behaviour entries)",
                      foreground="#555").pack(anchor="w")
            stats_label.configure(text="")
            return

        cols = ("entry_id", "entry_date", "type", "category",
                "severity", "points", "follow_up", "parent")
        headings = {
            "entry_id":   ("#",         50),
            "entry_date": ("Date",     100),
            "type":       ("Type",      80),
            "category":   ("Category", 140),
            "severity":   ("Severity",  80),
            "points":     ("Points",    60),
            "follow_up":  ("Follow-up",100),
            "parent":     ("Parent?",   70),
        }
        tree = ttk.Treeview(holder, columns=cols,
                            show="headings", height=12)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for e in rows:
            fu = (e.follow_up_date or ("Yes" if e.follow_up_required else "—"))
            tree.insert("", "end", iid=str(e.entry_id), values=(
                e.entry_id, e.entry_date, e.entry_type, e.category,
                e.severity or "—",
                ("+" if e.points >= 0 else "") + str(e.points),
                fu,
                "Yes" if e.parent_contacted else "No",
            ))
        tree.bind("<Double-1>", lambda _e: (
            tree.selection() and open_editor(
                gui, entry_id=int(tree.selection()[0]))
        ))

        sign = "+" if summ.net_points >= 0 else ""
        stats_label.configure(text=(
            f"Total: {summ.total_entries}  ·  "
            f"Positive: {summ.positive_count}  ·  "
            f"Negative: {summ.negative_count}  ·  "
            f"Net points: {sign}{summ.net_points}  ·  "
            f"Open follow-ups: {summ.open_follow_ups}"
        ))
        gui.status_var.set(f"Behaviour for {sid}: {summ.total_entries} row(s)")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No students yet.",
                  foreground="#a33").pack(anchor="w")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    upcoming_var = tk.StringVar(value="14")
    top_var = tk.StringVar(value="10")
    ttk.Label(bar, text="Follow-up window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=upcoming_var, width=6
              ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Top N students:").pack(side="left")
    ttk.Entry(bar, textvariable=top_var, width=4
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            upcoming = int(upcoming_var.get())
            top_n = int(top_var.get())
        except ValueError:
            ttk.Label(holder, text="Windows must be numbers.",
                      foreground="#a33").pack(anchor="w")
            return
        summ = data.summary(
            upcoming_window_days=upcoming, top_n=top_n)

        sign = "+" if summ.net_points >= 0 else ""
        ttk.Label(
            holder,
            text=f"Entries: {summ.total}  ·  Net points: {sign}{summ.net_points}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(holder, text="By type:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for t in ENTRY_TYPES:
            n = summ.by_type.get(t, 0)
            ttk.Label(holder, text=f"   {t:<10} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="By severity (negative entries):",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for s in SEVERITIES:
            n = summ.by_severity.get(s, 0)
            ttk.Label(holder, text=f"   {s:<10} : {n}",
                      foreground="#444").pack(anchor="w")

        if summ.by_category:
            ttk.Label(holder, text="Top categories:",
                      font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
            for cat, n in sorted(summ.by_category.items(),
                                  key=lambda kv: -kv[1])[:12]:
                ttk.Label(holder, text=f"   {cat[:24]:<24} : {n}",
                          foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Alerts:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        ttk.Label(
            holder,
            text=f"   Follow-ups open       : {summ.follow_ups_open}",
            foreground=("#a33" if summ.follow_ups_open else "#444"),
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Upcoming ({upcoming}d)       : {summ.upcoming_follow_ups}",
            foreground=("#a33" if summ.upcoming_follow_ups else "#444"),
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Parents contacted     : {summ.parents_contacted}",
            foreground="#444",
        ).pack(anchor="w")

        if summ.top_students_by_count:
            ttk.Label(holder, text=f"Top {top_n} students by entry count:",
                      font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
            names = {s.student_id: s.full_name
                     for s in student_data.list_students()}
            for sid, n in summ.top_students_by_count:
                ttk.Label(
                    holder,
                    text=f"   {sid:<10}  {(names.get(sid, '(unknown)'))[:30]:<30}  : {n}",
                    foreground="#444",
                ).pack(anchor="w")
        gui.status_var.set("Behaviour summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
