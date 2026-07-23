"""GUI panels for Sixth Form UCAS References.

Three tabs:

* Directory  — filterable list of references.
* Editor     — full-screen editor with referee / role / status /
  body / counts / notes.
* Per-student summary — one row per student with their reference counts.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.progression.references import references
from education_system.post_16.sixthform_system.modules.domain.progression.references import references as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.progression.references.references import (
    DEFAULT_STATUS,
    Reference,
    SOFT_CHAR_LIMIT,
    STATUSES,
    StudentRefSummary,
    ValidationError,
    compute_counts,
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
    _heading(frame, "References")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    editor_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(editor_tab,  text="Editor")
    nb.add(summary_tab, text="Per-student summary")

    _build_directory_tab(gui, dir_tab)
    _build_editor_tab(gui, editor_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    referee_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Referee:").pack(side="left")
    ttk.Entry(filt, textvariable=referee_var, width=18
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *STATUSES], state="readonly", width=12
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
        try:
            rows = data.list_references(
                student_id=sid_var.get().strip() or None,
                referee=referee_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_references failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("reference_id", "student", "referee", "role",
                "status", "chars", "submitted_at", "updated_at")
        headings = {
            "reference_id": ("#",        50),
            "student":      ("Student", 100),
            "referee":      ("Referee", 160),
            "role":         ("Role",    140),
            "status":       ("Status",  100),
            "chars":        ("Chars",    60),
            "submitted_at": ("Submitted", 140),
            "updated_at":   ("Updated",   140),
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
            tree.insert("", "end", iid=str(r.reference_id), values=(
                r.reference_id, r.student_id, r.referee,
                r.referee_role or "—", r.status, r.char_count,
                r.submitted_at or "—", r.updated_at,
            ))
        summary.configure(text=f"{len(rows)} reference(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            rid = _selected()
            if rid is None:
                messagebox.showinfo("No selection",
                                    "Pick a reference first.",
                                    parent=gui.root)
            return rid

        def _open() -> None:
            rid = _require()
            if rid is None:
                return
            open_editor(gui, reference_id=rid)

        def _delete() -> None:
            rid = _require()
            if rid is None:
                return
            r = data.get_reference(rid)
            if r is None:
                return
            if not messagebox.askyesno(
                "Delete reference",
                f"Delete reference #{rid} for {r.student_id}?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_reference(rid)
            except Exception as e:
                logger.exception("delete_reference crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Open in editor",
                   command=_open).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_editor(gui, reference_id=None)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _open())
        gui.status_var.set(f"References: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), referee_var.set(""),
                                status_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Editor tab ─────────────────────────────────────────────────────

def _build_editor_tab(gui, parent: ttk.Frame) -> None:
    rows = data.list_references()
    if rows:
        _render_editor(gui, parent, rows[0].reference_id)
    else:
        ttk.Label(
            parent,
            text=("No references yet. Use Directory → New to start one."),
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_editor(gui, *, reference_id: int | None) -> None:
    """Standalone full-page editor."""
    frame = _clear(gui)
    _heading(frame,
             f"Reference #{reference_id}" if reference_id else "New Reference")
    _render_editor(gui, frame, reference_id)
    ttk.Button(frame, text="Back to References",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_editor(gui, parent: ttk.Frame,
                   reference_id: int | None) -> None:
    existing = data.get_reference(reference_id) if reference_id else None

    head = ttk.Frame(parent)
    head.pack(anchor="w", fill="x", pady=(0, 8))

    students = student_data.list_students()
    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}

    if existing:
        ttk.Label(head, text=f"Student: {existing.student_id}",
                  font=("", 11, "bold")).pack(side="left", padx=(0, 12))
        student_var = tk.StringVar(value=existing.student_id)
    else:
        ttk.Label(head, text="Student:",
                  font=("", 11, "bold")).pack(side="left")
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        ttk.Combobox(head, textvariable=student_var, values=student_labels,
                     state="readonly", width=36
                     ).pack(side="left", padx=(4, 12))

    referee_var = tk.StringVar(
        value=existing.referee if existing else "")
    role_var = tk.StringVar(
        value=(existing.referee_role or "") if existing else "")
    status_var = tk.StringVar(
        value=existing.status if existing else DEFAULT_STATUS)

    ttk.Label(head, text="Referee:").pack(side="left")
    ttk.Entry(head, textvariable=referee_var, width=22
              ).pack(side="left", padx=(4, 12))
    ttk.Label(head, text="Role:").pack(side="left")
    ttk.Entry(head, textvariable=role_var, width=22
              ).pack(side="left", padx=(4, 12))
    ttk.Label(head, text="Status:").pack(side="left")
    ttk.Combobox(head, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))

    title_row = ttk.Frame(parent)
    title_row.pack(anchor="w", fill="x", pady=(0, 4))
    title_var = tk.StringVar(value=(existing.title or "") if existing else "")
    ttk.Label(title_row, text="Title:").pack(side="left")
    ttk.Entry(title_row, textvariable=title_var, width=46
              ).pack(side="left", padx=(4, 0))

    # Body
    body_frame = ttk.Frame(parent)
    body_frame.pack(fill="both", expand=True, pady=(4, 4))
    body_text = tk.Text(body_frame, wrap="word", width=82, height=20,
                        font=("TkFixedFont", 10))
    vs = ttk.Scrollbar(body_frame, orient="vertical",
                        command=body_text.yview)
    body_text.configure(yscrollcommand=vs.set)
    body_text.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    if existing and existing.body:
        body_text.insert("1.0", existing.body)

    # Counter line
    counter_var = tk.StringVar(value="")
    counter_label = ttk.Label(parent, textvariable=counter_var,
                              foreground="#555")
    counter_label.pack(anchor="w")

    def _update_counter(*_a) -> None:
        body = body_text.get("1.0", "end-1c")
        words, chars, lines = compute_counts(body)
        warn = (f"⚠ {chars - SOFT_CHAR_LIMIT} over UCAS soft limit"
                if chars > SOFT_CHAR_LIMIT else
                ("⚠ near limit" if chars > SOFT_CHAR_LIMIT - 200 else ""))
        counter_var.set(
            f"  {words} words  ·  {chars}/{SOFT_CHAR_LIMIT} chars  "
            f"·  {lines} lines"
            + (f"   {warn}" if warn else "")
        )
        counter_label.configure(
            foreground=("#a33" if chars > SOFT_CHAR_LIMIT else "#555"))

    body_text.bind("<KeyRelease>", _update_counter)
    _update_counter()

    # Notes
    notes_var = tk.StringVar(
        value=(existing.notes or "") if existing else "")
    notes_row = ttk.Frame(parent)
    notes_row.pack(anchor="w", fill="x", pady=(8, 0))
    ttk.Label(notes_row, text="Notes:").pack(side="left")
    ttk.Entry(notes_row, textvariable=notes_var, width=70
              ).pack(side="left", padx=(4, 0))

    # Actions
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(12, 0))

    def _save() -> Reference | None:
        body = body_text.get("1.0", "end-1c")
        if existing:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=gui.root)
                return None
        payload = {
            "student_id":   sid,
            "referee":      referee_var.get(),
            "referee_role": role_var.get(),
            "title":        title_var.get(),
            "body":         body,
            "status":       status_var.get(),
            "notes":        notes_var.get(),
        }
        try:
            if existing:
                saved = data.update_reference(existing.reference_id, payload)
            else:
                saved = data.create_reference(payload)
        except ValidationError as e:
            logger.warning("save reference rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return None
        except Exception as e:
            logger.exception("save reference crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return None
        gui.status_var.set(f"Saved reference #{saved.reference_id}")
        return saved

    def save() -> None:
        saved = _save()
        if not saved:
            return
        messagebox.showinfo("Saved",
                            f"Saved reference #{saved.reference_id}.",
                            parent=gui.root)
        open_editor(gui, reference_id=saved.reference_id)

    def submit() -> None:
        # Force-mark as Submitted on save; data layer auto-demotes any
        # previously Submitted reference for the same student.
        status_var.set("Submitted")
        saved = _save()
        if not saved:
            return
        messagebox.showinfo(
            "Submitted",
            f"Reference #{saved.reference_id} marked Submitted "
            f"at {saved.submitted_at}.",
            parent=gui.root,
        )
        open_editor(gui, reference_id=saved.reference_id)

    def delete() -> None:
        if not existing:
            return
        if not messagebox.askyesno(
            "Delete reference",
            f"Delete reference #{existing.reference_id}?",
            parent=gui.root,
        ):
            return
        try:
            data.delete_reference(existing.reference_id)
        except Exception as e:
            logger.exception("delete_reference crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set("Deleted reference")
        open_directory(gui)

    ttk.Button(actions, text="Save",
               command=save).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save & mark Submitted",
               command=submit).pack(side="left", padx=(0, 6))
    if existing:
        ttk.Button(actions, text="Delete",
                   command=delete).pack(side="left", padx=(0, 6))


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            rows = data.per_student_summary()
        except Exception as e:
            logger.exception("per_student_summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return
        if not rows:
            ttk.Label(holder, text="No references yet.",
                      foreground="#555").pack(anchor="w")
            return

        cols = ("student_id", "drafts", "latest_status",
                "submitted", "last_referee")
        headings = {
            "student_id":    ("Student",     110),
            "drafts":        ("Drafts",       60),
            "latest_status": ("Latest",      110),
            "submitted":     ("Submitted?",  100),
            "last_referee":  ("Last referee", 180),
        }
        tree = ttk.Treeview(holder, columns=cols,
                            show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for r in rows:
            tree.insert("", "end", iid=r.student_id, values=(
                r.student_id, r.drafts, r.latest_status or "—",
                "Yes" if r.has_submitted else "No",
                r.last_referee or "—",
            ))
        gui.status_var.set(f"Reference summary: {len(rows)} student(s)")

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", pady=(0, 8))
    ttk.Button(bar, text="Refresh", command=render
               ).pack(side="left")
    render()
