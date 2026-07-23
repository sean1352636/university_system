"""GUI panels for Sixth Form Careers Guidance.

Four tabs:

* Sessions    — filterable directory + add/edit/delete for careers sessions.
* Aspirations — per-student aspiration upsert form + filterable list.
* Per-student — every session for one student plus their current
  aspiration.
* Summary     — Gatsby-benchmark counts, pathway breakdown, alerts
  (upcoming scheduled / follow-ups / students with no recent session).
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.post_16.sixthform_system.modules.domain.progression.careers import careers
from education_system.post_16.sixthform_system.modules.domain.progression.careers import careers as data
from education_system.post_16.sixthform_system.modules.domain.students.students import students as student_data
from education_system.post_16.sixthform_system.modules.domain.progression.careers.careers import (
    CareerAspiration,
    CareerSession,
    CareersSummary,
    DEFAULT_PATHWAY,
    DEFAULT_SESSION_STATUS,
    DEFAULT_SESSION_TYPE,
    GATSBY_BENCHMARKS,
    PATHWAYS,
    SESSION_STATUSES,
    SESSION_TYPES,
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


def _benchmark_choices() -> list[str]:
    """Combobox values that show '1 — A stable careers programme', etc."""
    return [""] + [f"{k} — {v}" for k, v in GATSBY_BENCHMARKS.items()]


def _benchmark_from_label(label: str) -> int | None:
    if not label:
        return None
    try:
        return int(label.split("—")[0].strip())
    except (ValueError, IndexError):
        return None


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Careers Guidance")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    sessions_tab = ttk.Frame(nb, padding=8)
    aspir_tab = ttk.Frame(nb, padding=8)
    student_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(sessions_tab, text="Sessions")
    nb.add(aspir_tab,    text="Aspirations")
    nb.add(student_tab,  text="Per-student")
    nb.add(summary_tab,  text="Summary")

    _build_sessions_tab(gui, sessions_tab)
    _build_aspir_tab(gui, aspir_tab)
    _build_student_tab(gui, student_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Sessions tab ──────────────────────────────────────────────────

def _build_sessions_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    advisor_var = tk.StringVar()
    type_var = tk.StringVar()
    bm_var = tk.StringVar()
    status_var = tk.StringVar()
    from_var = tk.StringVar()
    to_var = tk.StringVar()

    ttk.Label(filt, text="Student:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Advisor:").pack(side="left")
    ttk.Entry(filt, textvariable=advisor_var, width=14
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Type:").pack(side="left")
    ttk.Combobox(filt, textvariable=type_var,
                 values=["", *SESSION_TYPES],
                 state="readonly", width=18
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Benchmark:").pack(side="left")
    ttk.Combobox(filt, textvariable=bm_var,
                 values=_benchmark_choices(),
                 state="readonly", width=36
                 ).pack(side="left", padx=(4, 4))

    filt2 = ttk.Frame(parent)
    filt2.pack(anchor="w", fill="x", pady=(0, 8))
    ttk.Label(filt2, text="Status:").pack(side="left")
    ttk.Combobox(filt2, textvariable=status_var,
                 values=["", *SESSION_STATUSES],
                 state="readonly", width=12
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt2, text="From:").pack(side="left")
    ttk.Entry(filt2, textvariable=from_var, width=12
              ).pack(side="left", padx=(4, 8))
    ttk.Label(filt2, text="To:").pack(side="left")
    ttk.Entry(filt2, textvariable=to_var, width=12
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
        bm = _benchmark_from_label(bm_var.get())
        try:
            rows = data.list_sessions_with_detail(
                student_id=sid_var.get().strip() or None,
                advisor_like=advisor_var.get().strip() or None,
                session_type=type_var.get().strip() or None,
                benchmark=bm,
                status=status_var.get().strip() or None,
                date_from=from_var.get().strip() or None,
                date_to=to_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_sessions failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("session_id", "student", "name", "session_date",
                "type", "advisor", "bm", "status",
                "follow_up")
        headings = {
            "session_id":   ("#",         50),
            "student":      ("Student",  100),
            "name":         ("Name",     160),
            "session_date": ("Date",     100),
            "type":         ("Type",     150),
            "advisor":      ("Advisor",  140),
            "bm":           ("BM",        40),
            "status":       ("Status",   100),
            "follow_up":    ("Follow-up",100),
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
            s = r.session
            tree.insert("", "end", iid=str(s.session_id), values=(
                s.session_id, s.student_id, r.student_name,
                s.session_date, s.session_type,
                s.advisor or "—",
                s.gatsby_benchmark if s.gatsby_benchmark else "—",
                s.status, s.follow_up_date or "—",
            ))
        summary.configure(text=f"{len(rows)} session(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            sid = _selected()
            if sid is None:
                messagebox.showinfo("No selection",
                                    "Pick a session first.",
                                    parent=gui.root)
            return sid

        def _edit() -> None:
            sid = _require()
            if sid is None:
                return
            open_session_editor(gui, session_id=sid)

        def _delete() -> None:
            sid = _require()
            if sid is None:
                return
            s = data.get_session(sid)
            if s is None:
                return
            if not messagebox.askyesno(
                "Delete session",
                f"Delete careers session #{sid} ({s.student_id}, "
                f"{s.session_date})?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_session(sid)
            except Exception as e:
                logger.exception("delete_session crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Open in editor",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New session",
                   command=lambda: open_session_editor(gui, session_id=None)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Careers sessions: {len(rows)} match(es)")

    ttk.Button(filt2, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt2, text="Clear",
               command=lambda: (sid_var.set(""), advisor_var.set(""),
                                type_var.set(""), bm_var.set(""),
                                status_var.set(""), from_var.set(""),
                                to_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def open_session_editor(gui, *, session_id: int | None) -> None:
    existing = data.get_session(session_id) if session_id else None
    win = tk.Toplevel(gui.root)
    win.title(f"Careers session #{session_id}"
              if session_id else "New careers session")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    if existing:
        ttk.Label(frm, text=f"Student: {existing.student_id}",
                  foreground="#555").grid(row=0, column=0, columnspan=2,
                                           sticky="w", pady=(0, 8))
        student_var = tk.StringVar(value=existing.student_id)
        student_by_label = {}
    else:
        students = student_data.list_students()
        student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
        student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                            for s in students}
        student_var = tk.StringVar(
            value=student_labels[0] if student_labels else "")
        ttk.Label(frm, text="Student:").grid(row=0, column=0, sticky="e",
                                              padx=(0, 6), pady=2)
        ttk.Combobox(frm, textvariable=student_var,
                     values=student_labels,
                     state="readonly", width=42
                     ).grid(row=0, column=1, sticky="w", pady=2)

    today = _date.today().isoformat()
    date_var = tk.StringVar(
        value=existing.session_date if existing else today)
    advisor_var = tk.StringVar(
        value=(existing.advisor or "") if existing else "")
    type_var = tk.StringVar(
        value=existing.session_type if existing else DEFAULT_SESSION_TYPE)
    duration_var = tk.StringVar(
        value=(str(existing.duration_minutes)
               if existing and existing.duration_minutes else "30"))
    bm_var = tk.StringVar(
        value=(f"{existing.gatsby_benchmark} — "
               f"{GATSBY_BENCHMARKS[existing.gatsby_benchmark]}"
               if existing and existing.gatsby_benchmark
               else ""))
    status_var = tk.StringVar(
        value=existing.status if existing else DEFAULT_SESSION_STATUS)
    follow_up_var = tk.StringVar(
        value=(existing.follow_up_date or "") if existing else "")
    topics_text = tk.Text(frm, width=46, height=3)
    plan_text = tk.Text(frm, width=46, height=3)
    notes_var = tk.StringVar(
        value=(existing.notes or "") if existing else "")
    if existing:
        if existing.topics:
            topics_text.insert("1.0", existing.topics)
        if existing.action_plan:
            plan_text.insert("1.0", existing.action_plan)

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Date (YYYY-MM-DD):",
        ttk.Entry(frm, textvariable=date_var, width=14))
    row(2, "Advisor:",
        ttk.Entry(frm, textvariable=advisor_var, width=24))
    row(3, "Type:",
        ttk.Combobox(frm, textvariable=type_var,
                     values=list(SESSION_TYPES),
                     state="readonly", width=22))
    row(4, "Duration (mins):",
        ttk.Entry(frm, textvariable=duration_var, width=8))
    row(5, "Gatsby benchmark:",
        ttk.Combobox(frm, textvariable=bm_var,
                     values=_benchmark_choices(),
                     state="readonly", width=42))
    row(6, "Status:",
        ttk.Combobox(frm, textvariable=status_var,
                     values=list(SESSION_STATUSES),
                     state="readonly", width=14))
    row(7, "Follow-up date:",
        ttk.Entry(frm, textvariable=follow_up_var, width=14))
    ttk.Label(frm, text="Topics:").grid(row=8, column=0, sticky="ne",
                                         padx=(0, 6), pady=2)
    topics_text.grid(row=8, column=1, sticky="w", pady=2)
    ttk.Label(frm, text="Action plan:").grid(row=9, column=0, sticky="ne",
                                              padx=(0, 6), pady=2)
    plan_text.grid(row=9, column=1, sticky="w", pady=2)
    row(10, "Notes:",
        ttk.Entry(frm, textvariable=notes_var, width=46))

    def save() -> None:
        if existing:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=win)
                return
        payload = {
            "student_id":       sid,
            "session_date":     date_var.get(),
            "advisor":          advisor_var.get(),
            "session_type":     type_var.get(),
            "duration_minutes": duration_var.get(),
            "gatsby_benchmark": _benchmark_from_label(bm_var.get()),
            "topics":           topics_text.get("1.0", "end-1c").strip(),
            "action_plan":      plan_text.get("1.0", "end-1c").strip(),
            "follow_up_date":   follow_up_var.get(),
            "status":           status_var.get(),
            "notes":            notes_var.get(),
        }
        try:
            if existing:
                data.update_session(existing.session_id, payload)
            else:
                data.create_session(payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save session crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        open_directory(gui)

    bar = ttk.Frame(frm)
    bar.grid(row=11, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Aspirations tab ────────────────────────────────────────────────

def _build_aspir_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))
    pathway_var = tk.StringVar()
    career_var = tk.StringVar()

    ttk.Label(filt, text="Pathway:").pack(side="left")
    ttk.Combobox(filt, textvariable=pathway_var,
                 values=["", *PATHWAYS], state="readonly", width=14
                 ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Target career:").pack(side="left")
    ttk.Entry(filt, textvariable=career_var, width=22
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
            rows = data.list_aspirations(
                pathway=pathway_var.get().strip() or None,
                target_career_like=career_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        students_index = {s.student_id: s for s in
                          student_data.list_students()}
        cols = ("student", "name", "pathway", "career",
                "sector", "employer", "course", "updated")
        headings = {
            "student":  ("Student",   100),
            "name":     ("Name",      160),
            "pathway":  ("Pathway",   120),
            "career":   ("Target career", 160),
            "sector":   ("Sector",    140),
            "employer": ("Employer",  120),
            "course":   ("Course",    120),
            "updated":  ("Updated",   140),
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
        for a in rows:
            s = students_index.get(a.student_id)
            tree.insert("", "end", iid=a.student_id, values=(
                a.student_id, s.full_name if s else "(deleted)",
                a.primary_pathway, a.target_career or "—",
                a.target_sector or "—", a.target_employer or "—",
                a.target_course or "—", a.updated_at,
            ))
        summary.configure(text=f"{len(rows)} aspiration(s).")

        def _selected() -> str | None:
            sel = tree.selection()
            return sel[0] if sel else None

        def _edit() -> None:
            sid = _selected()
            if sid is None:
                messagebox.showinfo("No selection",
                                    "Pick a row first.", parent=gui.root)
                return
            open_aspiration_editor(gui, student_id=sid, on_saved=refresh)

        def _delete() -> None:
            sid = _selected()
            if sid is None:
                return
            if not messagebox.askyesno(
                "Clear aspiration",
                f"Remove the aspiration row for {sid}?",
                parent=gui.root,
            ):
                return
            try:
                data.delete_aspiration(sid)
            except Exception as e:
                logger.exception("delete_aspiration crashed")
                messagebox.showerror("Error", str(e), parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Edit",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Clear",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New / Update",
                   command=lambda: open_aspiration_editor(
                       gui, student_id=None, on_saved=refresh)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Aspirations: {len(rows)} row(s)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (pathway_var.set(""), career_var.set(""),
                                refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def open_aspiration_editor(gui, *, student_id: str | None,
                            on_saved: Callable[[], None]) -> None:
    existing = (data.get_aspiration_for_student(student_id)
                if student_id else None)
    win = tk.Toplevel(gui.root)
    win.title(f"Aspiration — {student_id}"
              if student_id else "New / Update Aspiration")
    win.transient(gui.root)
    win.after_idle(win.grab_set)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    if existing:
        ttk.Label(frm, text=f"Student: {existing.student_id}",
                  foreground="#555").grid(row=0, column=0, columnspan=2,
                                           sticky="w", pady=(0, 8))
        student_var = tk.StringVar(value=existing.student_id)
        student_by_label = {}
    else:
        students = student_data.list_students()
        labels = [f"{s.student_id} — {s.full_name}" for s in students]
        student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                            for s in students}
        student_var = tk.StringVar(value=labels[0] if labels else "")
        ttk.Label(frm, text="Student:").grid(row=0, column=0, sticky="e",
                                              padx=(0, 6), pady=2)
        ttk.Combobox(frm, textvariable=student_var,
                     values=labels, state="readonly", width=42
                     ).grid(row=0, column=1, sticky="w", pady=2)

    pathway_var = tk.StringVar(
        value=existing.primary_pathway if existing else DEFAULT_PATHWAY)
    career_var = tk.StringVar(
        value=(existing.target_career or "") if existing else "")
    sector_var = tk.StringVar(
        value=(existing.target_sector or "") if existing else "")
    employer_var = tk.StringVar(
        value=(existing.target_employer or "") if existing else "")
    course_var = tk.StringVar(
        value=(existing.target_course or "") if existing else "")
    notes_var = tk.StringVar(
        value=(existing.notes or "") if existing else "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Primary pathway:",
        ttk.Combobox(frm, textvariable=pathway_var,
                     values=list(PATHWAYS), state="readonly", width=18))
    row(2, "Target career:",
        ttk.Entry(frm, textvariable=career_var, width=42))
    row(3, "Target sector:",
        ttk.Entry(frm, textvariable=sector_var, width=42))
    row(4, "Target employer:",
        ttk.Entry(frm, textvariable=employer_var, width=42))
    row(5, "Target course:",
        ttk.Entry(frm, textvariable=course_var, width=42))
    row(6, "Notes:",
        ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        if existing:
            sid = existing.student_id
        else:
            sid = student_by_label.get(student_var.get())
            if not sid:
                messagebox.showerror("Cannot save",
                                     "Pick a student.", parent=win)
                return
        try:
            data.save_aspiration({
                "student_id":      sid,
                "primary_pathway": pathway_var.get(),
                "target_career":   career_var.get(),
                "target_sector":   sector_var.get(),
                "target_employer": employer_var.get(),
                "target_course":   course_var.get(),
                "notes":           notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save_aspiration crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=7, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


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

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        sid = by_label.get(student_var.get())
        if not sid:
            ttk.Label(holder, text="Pick a student.",
                      foreground="#a33").pack(anchor="w")
            return
        student = student_data.get_student(sid)
        ttk.Label(holder,
                  text=f"{student.student_id}  {student.full_name}"
                       if student else f"{sid} (deleted)",
                  font=("", 12, "bold")).pack(anchor="w", pady=(0, 6))

        asp = data.get_aspiration_for_student(sid)
        asp_frame = ttk.LabelFrame(holder, text="Aspiration",
                                    padding=8)
        asp_frame.pack(anchor="w", fill="x", pady=(0, 8))
        if asp:
            ttk.Label(
                asp_frame,
                text=(f"Pathway: {asp.primary_pathway}    "
                      f"Target career: {asp.target_career or '—'}    "
                      f"Sector: {asp.target_sector or '—'}    "
                      f"Employer: {asp.target_employer or '—'}    "
                      f"Course: {asp.target_course or '—'}"),
                wraplength=860, justify="left",
            ).pack(anchor="w")
            if asp.notes:
                ttk.Label(asp_frame, text=f"Notes: {asp.notes}",
                          foreground="#555",
                          wraplength=860, justify="left"
                          ).pack(anchor="w", pady=(4, 0))
        else:
            ttk.Label(asp_frame, text="(no aspiration recorded)",
                      foreground="#555").pack(anchor="w")
        ttk.Button(asp_frame, text="Edit aspiration",
                   command=lambda: open_aspiration_editor(
                       gui, student_id=sid, on_saved=render)
                   ).pack(anchor="w", pady=(6, 0))

        sessions = data.sessions_for_student(sid)
        sess_frame = ttk.LabelFrame(holder, text=f"Sessions ({len(sessions)})",
                                     padding=8)
        sess_frame.pack(anchor="w", fill="both", expand=True, pady=(0, 4))
        if not sessions:
            ttk.Label(sess_frame, text="(no sessions yet)",
                      foreground="#555").pack(anchor="w")
            return

        cols = ("session_id", "date", "type", "advisor", "bm",
                "status", "follow_up")
        headings = {
            "session_id": ("#",         50),
            "date":       ("Date",     100),
            "type":       ("Type",     150),
            "advisor":    ("Advisor",  140),
            "bm":         ("BM",        40),
            "status":     ("Status",   100),
            "follow_up":  ("Follow-up",100),
        }
        tree = ttk.Treeview(sess_frame, columns=cols,
                            show="headings", height=10)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(sess_frame, orient="vertical",
                            command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for s in sessions:
            tree.insert("", "end", iid=str(s.session_id), values=(
                s.session_id, s.session_date, s.session_type,
                s.advisor or "—",
                s.gatsby_benchmark if s.gatsby_benchmark else "—",
                s.status, s.follow_up_date or "—",
            ))
        tree.bind("<Double-1>", lambda _e: (
            tree.selection() and
            open_session_editor(gui, session_id=int(tree.selection()[0]))
        ))

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
    no_session_var = tk.StringVar(value="180")
    upcoming_var = tk.StringVar(value="14")
    ttk.Label(bar, text="No-session window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=no_session_var, width=6
              ).pack(side="left", padx=(4, 12))
    ttk.Label(bar, text="Upcoming window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=upcoming_var, width=6
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            no_session = int(no_session_var.get())
            upcoming = int(upcoming_var.get())
        except ValueError:
            ttk.Label(holder, text="Windows must be numbers.",
                      foreground="#a33").pack(anchor="w")
            return
        summ = data.summary(
            no_session_window_days=no_session,
            upcoming_window_days=upcoming)

        ttk.Label(
            holder,
            text=f"Total sessions: {summ.total_sessions}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(holder, text="Sessions by Gatsby benchmark:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for k, title in GATSBY_BENCHMARKS.items():
            n = summ.by_benchmark.get(k, 0)
            ttk.Label(holder, text=f"   {k}. {title[:46]:<46} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="By session type:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for t in SESSION_TYPES:
            n = summ.by_type.get(t, 0)
            if n:
                ttk.Label(holder, text=f"   {t:<22} : {n}",
                          foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="By session status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for s in SESSION_STATUSES:
            n = summ.by_status.get(s, 0)
            ttk.Label(holder, text=f"   {s:<14} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Aspirations by pathway:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for p in PATHWAYS:
            n = summ.by_pathway.get(p, 0)
            ttk.Label(holder, text=f"   {p:<16} : {n}",
                      foreground="#444").pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   (students with aspiration recorded: "
                 f"{summ.students_with_aspiration})",
            foreground="#777",
        ).pack(anchor="w")

        ttk.Label(holder, text="Alerts:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        ttk.Label(
            holder,
            text=f"   Students with no completed session in last "
                 f"{no_session}d : {summ.students_no_session}",
            foreground=("#a33" if summ.students_no_session else "#444"),
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Upcoming scheduled sessions ({upcoming}d) : "
                 f"{summ.upcoming_scheduled}",
            foreground=("#a33" if summ.upcoming_scheduled else "#444"),
        ).pack(anchor="w")
        ttk.Label(
            holder,
            text=f"   Upcoming follow-ups ({upcoming}d) : "
                 f"{summ.upcoming_follow_ups}",
            foreground=("#a33" if summ.upcoming_follow_ups else "#444"),
        ).pack(anchor="w")
        gui.status_var.set("Careers summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
