"""GUI panels for Sixth Form Personal Statements.

Three tabs:

* Directory  — filterable list of drafts (filter by student / status).
* Editor     — full-screen text editor with live char / word / line
  counters, UCAS-limit warning, status / reviewer / feedback controls,
  Save / Push to UCAS / Delete actions.
* Per-student — counts per student + latest status.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.systems.sixth_form.domain.progression.personal_statements import personal_statements
from education_system.systems.sixth_form.domain.progression.personal_statements import personal_statements as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.progression.ucas import ucas as ucas_data
from education_system.systems.sixth_form.domain.progression.personal_statements.personal_statements import (
    DEFAULT_STATUS,
    MAX_CHARS,
    MAX_LINES,
    PersonalStatement,
    STATUSES,
    StudentSummary,
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
    _heading(frame, "Personal Statements")

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
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
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
            rows = data.list_statements(
                student_id=sid_var.get().strip() or None,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_statements failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("statement_id", "student", "title", "status",
                "chars", "lines", "reviewer", "updated_at")
        headings = {
            "statement_id": ("#",        50),
            "student":      ("Student", 110),
            "title":        ("Title",   200),
            "status":       ("Status",  100),
            "chars":        ("Chars",    60),
            "lines":        ("Lines",    50),
            "reviewer":     ("Reviewer", 130),
            "updated_at":   ("Updated",  140),
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

        for s in rows:
            tree.insert("", "end", iid=str(s.statement_id), values=(
                s.statement_id, s.student_id, s.title or "—",
                s.status, s.char_count, s.line_count,
                s.reviewer or "—", s.updated_at,
            ))
        summary.configure(text=f"{len(rows)} statement(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            sid = _selected()
            if sid is None:
                messagebox.showinfo("No selection",
                                    "Pick a statement first.",
                                    parent=gui.root)
            return sid

        def _open() -> None:
            sid = _require()
            if sid is None:
                return
            open_editor(gui, statement_id=sid)

        def _delete() -> None:
            sid = _require()
            if sid is None:
                return
            s = data.get_statement(sid)
            if s is None:
                return
            if not messagebox.askyesno(
                "Delete statement",
                f"Delete personal statement #{sid} ({s.student_id})?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_statement(sid)
            except Exception as e:
                logger.exception("delete_statement crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        def _push() -> None:
            sid = _require()
            if sid is None:
                return
            s = data.get_statement(sid)
            if s is None:
                return
            if not messagebox.askyesno(
                "Push to UCAS",
                f"Copy this draft to {s.student_id}'s UCAS application?\n\n"
                f"(The draft will be marked as Submitted.)",
                parent=gui.root,
            ):
                return
            try:
                aid = data.push_to_ucas(sid)
            except ValidationError as e:
                messagebox.showerror("Cannot push", str(e), parent=gui.root)
                return
            except Exception as e:
                logger.exception("push_to_ucas crashed")
                messagebox.showerror("Error", f"Unexpected: {e}",
                                     parent=gui.root)
                return
            messagebox.showinfo(
                "Pushed",
                f"Copied to UCAS application #{aid}.",
                parent=gui.root,
            )
            refresh()

        ttk.Button(actions_holder, text="Open in editor",
                   command=_open).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Push to UCAS",
                   command=_push).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_editor(gui, statement_id=None)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _open())
        gui.status_var.set(f"Personal statements: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), status_var.set(""),
                                refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Editor tab ─────────────────────────────────────────────────────

def _build_editor_tab(gui, parent: ttk.Frame) -> None:
    """Default editor tab — open the most recent draft or a blank one."""
    rows = data.list_statements()
    if rows:
        _render_editor(gui, parent, rows[0].statement_id)
    else:
        ttk.Label(
            parent,
            text=("No personal statements yet. "
                  "Use Directory → New to start one."),
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_editor(gui, *, statement_id: int | None) -> None:
    """Standalone full-page editor."""
    frame = _clear(gui)
    _heading(frame,
             f"Personal Statement #{statement_id}"
             if statement_id else "New Personal Statement")
    _render_editor(gui, frame, statement_id)
    ttk.Button(frame, text="Back to Personal Statements",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_editor(
    gui, parent: ttk.Frame, statement_id: int | None,
) -> None:
    existing = data.get_statement(statement_id) if statement_id else None

    # Header
    head = ttk.Frame(parent)
    head.pack(anchor="w", fill="x", pady=(0, 8))

    students = student_data.list_students()
    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}

    if existing:
        ttk.Label(
            head,
            text=f"Student: {existing.student_id}",
            font=("", 11, "bold"),
        ).pack(side="left", padx=(0, 12))
        student_var = tk.StringVar(value=existing.student_id)
    else:
        ttk.Label(head, text="Student:",
                  font=("", 11, "bold")).pack(side="left")
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        ttk.Combobox(head, textvariable=student_var,
                     values=student_labels,
                     state="readonly", width=36
                     ).pack(side="left", padx=(4, 12))

    title_var = tk.StringVar(
        value=(existing.title or "") if existing else "")
    ttk.Label(head, text="Title:").pack(side="left")
    ttk.Entry(head, textvariable=title_var, width=24
              ).pack(side="left", padx=(4, 12))

    status_var = tk.StringVar(
        value=existing.status if existing else DEFAULT_STATUS)
    ttk.Label(head, text="Status:").pack(side="left")
    ttk.Combobox(head, textvariable=status_var, values=list(STATUSES),
                 state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))

    # Body
    body_frame = ttk.Frame(parent)
    body_frame.pack(fill="both", expand=True, pady=(0, 8))
    body_text = tk.Text(body_frame, wrap="word", width=82, height=22,
                        font=("TkFixedFont", 10))
    vs = ttk.Scrollbar(body_frame, orient="vertical",
                        command=body_text.yview)
    body_text.configure(yscrollcommand=vs.set)
    body_text.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    if existing and existing.body:
        body_text.insert("1.0", existing.body)

    # Counter line (updates live)
    counter_var = tk.StringVar(value="")
    counter_label = ttk.Label(parent, textvariable=counter_var,
                              foreground="#555")
    counter_label.pack(anchor="w")

    def _update_counter(*_a) -> None:
        body = body_text.get("1.0", "end-1c")
        words, chars, lines = compute_counts(body)
        chars_left = MAX_CHARS - chars
        lines_left = MAX_LINES - lines
        warn = []
        if chars > MAX_CHARS:
            warn.append(f"⚠ {chars - MAX_CHARS} over char limit")
        elif chars > MAX_CHARS - 200:
            warn.append("⚠ near char limit")
        if lines > MAX_LINES:
            warn.append(f"⚠ {lines - MAX_LINES} over line limit")
        counter_var.set(
            f"  {words} words  ·  {chars}/{MAX_CHARS} chars  "
            f"({chars_left} left)  ·  "
            f"{lines}/{MAX_LINES} lines ({lines_left} left)"
            + ("   " + " · ".join(warn) if warn else "")
        )
        counter_label.configure(
            foreground=("#a33" if warn and "over" in " ".join(warn)
                        else "#555"))

    body_text.bind("<KeyRelease>", _update_counter)
    _update_counter()

    # Reviewer / feedback
    rev_frame = ttk.Frame(parent)
    rev_frame.pack(anchor="w", fill="x", pady=(8, 0))
    reviewer_var = tk.StringVar(
        value=(existing.reviewer or "") if existing else "")
    ttk.Label(rev_frame, text="Reviewer:").pack(side="left")
    ttk.Entry(rev_frame, textvariable=reviewer_var, width=28
              ).pack(side="left", padx=(4, 12))

    ttk.Label(parent, text="Feedback:").pack(anchor="w", pady=(8, 2))
    feedback_text = tk.Text(parent, wrap="word", width=82, height=4)
    feedback_text.pack(anchor="w")
    if existing and existing.feedback:
        feedback_text.insert("1.0", existing.feedback)

    # Actions
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(12, 0))

    def _save() -> dict[str, Any] | None:
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
            "student_id": sid,
            "title":      title_var.get(),
            "body":       body,
            "status":     status_var.get(),
            "reviewer":   reviewer_var.get(),
            "feedback":   feedback_text.get("1.0", "end-1c").strip(),
        }
        try:
            if existing:
                saved = data.update_statement(existing.statement_id, payload)
            else:
                saved = data.create_statement(payload)
        except ValidationError as e:
            logger.warning("save statement rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return None
        except Exception as e:
            logger.exception("save statement crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return None
        gui.status_var.set(f"Saved personal statement #{saved.statement_id}")
        return {"id": saved.statement_id}

    def save() -> None:
        result = _save()
        if not result:
            return
        messagebox.showinfo("Saved",
                            f"Saved statement #{result['id']}.",
                            parent=gui.root)
        # Re-render with the new id so subsequent saves are updates.
        open_editor(gui, statement_id=result["id"])

    def save_and_push() -> None:
        result = _save()
        if not result:
            return
        if not messagebox.askyesno(
            "Push to UCAS",
            f"Push this statement to "
            f"{student_var.get().split(' — ')[0]}'s UCAS application?",
            parent=gui.root,
        ):
            return
        try:
            aid = data.push_to_ucas(result["id"])
        except ValidationError as e:
            messagebox.showerror("Cannot push", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("push_to_ucas crashed")
            messagebox.showerror("Error", f"Unexpected: {e}",
                                 parent=gui.root)
            return
        messagebox.showinfo(
            "Pushed",
            f"Saved and pushed to UCAS application #{aid}.",
            parent=gui.root,
        )
        open_editor(gui, statement_id=result["id"])

    def delete() -> None:
        if not existing:
            return
        if not messagebox.askyesno(
            "Delete statement",
            f"Delete personal statement #{existing.statement_id}?",
            parent=gui.root,
        ):
            return
        try:
            data.delete_statement(existing.statement_id)
        except Exception as e:
            logger.exception("delete_statement crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        gui.status_var.set("Deleted statement")
        open_directory(gui)

    ttk.Button(actions, text="Save",
               command=save).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Save & push to UCAS",
               command=save_and_push).pack(side="left", padx=(0, 6))
    if existing:
        ttk.Button(actions, text="Delete",
                   command=delete).pack(side="left", padx=(0, 6))


# ─── Per-student summary tab ────────────────────────────────────────

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
            ttk.Label(holder, text="No personal statements yet.",
                      foreground="#555").pack(anchor="w")
            return

        cols = ("student_id", "drafts", "latest_status",
                "latest_chars", "latest_lines", "submitted")
        headings = {
            "student_id":    ("Student",    110),
            "drafts":        ("Drafts",      60),
            "latest_status": ("Latest",     110),
            "latest_chars":  ("Chars",       70),
            "latest_lines":  ("Lines",       60),
            "submitted":     ("Submitted?", 100),
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
        for s in rows:
            tree.insert("", "end", iid=s.student_id, values=(
                s.student_id, s.drafts,
                s.latest_status or "—",
                s.latest_chars, s.latest_lines,
                "Yes" if s.has_submitted else "No",
            ))
        gui.status_var.set(f"PS summary: {len(rows)} student(s)")

    refresh_bar = ttk.Frame(parent)
    refresh_bar.pack(anchor="w", pady=(0, 8))
    ttk.Button(refresh_bar, text="Refresh", command=render
               ).pack(side="left")
    render()
