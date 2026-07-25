"""GUI panels for Sixth Form University Offers.

Three tabs:

* Directory  — filterable list of UCAS choices (offers + rejections),
  one row per choice, joined to the student + offer details.
* Editor     — pick a choice → edit offer details (deadline, terms,
  scholarship, accommodation) and the final decision.
* Per-student — pick a student → side-by-side comparison of every
  one of their UCAS choices with predicted grade + required grade.
* Summary    — overall counts (offers, finals, scholarships, upcoming
  deadlines).
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.systems.sixth_form.domain.progression.offers import offers
from education_system.systems.sixth_form.domain.progression.offers import offers as data
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.progression.ucas import ucas as ucas_data
from education_system.systems.sixth_form.domain.progression.offers.offers import (
    OFFER_DECISION_STATUSES,
    OfferRow,
    ValidationError,
)
from education_system.systems.sixth_form.domain.progression.ucas.ucas import (
    DECISION_STATUSES,
    FINAL_DECISIONS,
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
    _heading(frame, "University Offers")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    editor_tab = ttk.Frame(nb, padding=8)
    compare_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(editor_tab,  text="Editor")
    nb.add(compare_tab, text="Per-student compare")
    nb.add(summary_tab, text="Summary")

    _build_directory_tab(gui, dir_tab)
    _build_editor_tab(gui, editor_tab)
    _build_compare_tab(gui, compare_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    uni_var = tk.StringVar()
    decision_var = tk.StringVar()
    final_var = tk.StringVar()
    offers_only_var = tk.BooleanVar(value=False)
    deadline_var = tk.StringVar()

    ttk.Label(filt, text="Student:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="University:").pack(side="left")
    ttk.Entry(filt, textvariable=uni_var, width=18
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Decision:").pack(side="left")
    ttk.Combobox(filt, textvariable=decision_var,
                 values=["", *DECISION_STATUSES], state="readonly",
                 width=22).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Final:").pack(side="left")
    ttk.Combobox(filt, textvariable=final_var,
                 values=["", *FINAL_DECISIONS], state="readonly",
                 width=12).pack(side="left", padx=(4, 12))
    ttk.Checkbutton(filt, text="Offers only",
                    variable=offers_only_var).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Deadline ≤:").pack(side="left")
    ttk.Entry(filt, textvariable=deadline_var, width=12
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
            rows = data.list_offer_rows(
                student_id=sid_var.get().strip() or None,
                university_like=uni_var.get().strip() or None,
                decision_status=decision_var.get().strip() or None,
                final_decision=final_var.get().strip() or None,
                offers_only=offers_only_var.get(),
                deadline_before=deadline_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return
        except Exception as e:
            logger.exception("list_offer_rows failed")
            ttk.Label(table_holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("choice_id", "student", "name", "uni",
                "course", "decision", "terms", "deadline",
                "scholarship", "final", "pred")
        headings = {
            "choice_id":   ("#",        50),
            "student":     ("Student", 100),
            "name":        ("Name",    160),
            "uni":         ("Univ.",   150),
            "course":      ("Course",  170),
            "decision":    ("Decision",170),
            "terms":       ("Terms",   140),
            "deadline":    ("Deadline", 90),
            "scholarship": ("Schol.",  140),
            "final":       ("Final",    80),
            "pred":        ("Pred",     50),
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
            details = r.details
            tree.insert("", "end", iid=str(r.choice_id), values=(
                r.choice_id, r.student_id, r.student_name,
                r.university,
                r.course_name + (f" ({r.course_code})"
                                  if r.course_code else ""),
                r.decision_status,
                r.offer_terms or "—",
                (details.reply_deadline if details and details.reply_deadline
                 else "—"),
                (details.scholarship if details and details.scholarship
                 else "—"),
                r.final_decision or "—",
                r.predicted_grade or "—",
            ))
        summary.configure(text=f"{len(rows)} row(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            cid = _selected()
            if cid is None:
                messagebox.showinfo("No selection",
                                    "Pick a row first.", parent=gui.root)
            return cid

        def _edit() -> None:
            cid = _require()
            if cid is None:
                return
            open_editor(gui, choice_id=cid)

        def _firm() -> None:
            cid = _require()
            if cid is None:
                return
            _set_final(cid, "Firm")

        def _insurance() -> None:
            cid = _require()
            if cid is None:
                return
            _set_final(cid, "Insurance")

        def _decline() -> None:
            cid = _require()
            if cid is None:
                return
            _set_final(cid, "Declined")

        def _clear_final() -> None:
            cid = _require()
            if cid is None:
                return
            _set_final(cid, None)

        def _set_final(cid: int, final: str | None) -> None:
            try:
                data.set_final_decision(cid, final)
            except ValidationError as e:
                messagebox.showerror("Cannot set final",
                                     str(e), parent=gui.root)
                return
            except Exception as e:
                logger.exception("set_final_decision crashed")
                messagebox.showerror("Error", f"Unexpected: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Edit offer",
                   command=_edit).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Firm",
                   command=_firm).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Insurance",
                   command=_insurance).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Decline",
                   command=_decline).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Clear final",
                   command=_clear_final).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left", padx=(12, 0))
        tree.bind("<Double-1>", lambda _e: _edit())
        gui.status_var.set(f"Offers: {len(rows)} row(s)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), uni_var.set(""),
                                decision_var.set(""), final_var.set(""),
                                offers_only_var.set(False),
                                deadline_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


# ─── Editor tab + standalone ────────────────────────────────────────

def _build_editor_tab(gui, parent: ttk.Frame) -> None:
    rows = data.list_offer_rows(offers_only=True)
    if rows:
        _render_editor(gui, parent, rows[0].choice_id)
    else:
        ttk.Label(
            parent,
            text=("No offers yet. Once a UCAS choice has decision status "
                  "'Conditional Offer' or 'Unconditional Offer', it "
                  "appears here."),
            foreground="#555",
        ).pack(anchor="w", pady=8)


def open_editor(gui, *, choice_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Offer Editor — choice #{choice_id}")
    _render_editor(gui, frame, choice_id)
    ttk.Button(frame, text="Back to University Offers",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_editor(gui, parent: ttk.Frame, choice_id: int) -> None:
    row = data.get_offer_row(choice_id)
    if row is None:
        ttk.Label(parent, text=f"No UCAS choice #{choice_id}.",
                  foreground="#a33").pack(anchor="w")
        return
    details = row.details

    head = ttk.Frame(parent)
    head.pack(anchor="w", fill="x", pady=(0, 8))

    def field(parent_, row_idx: int, label: str, value: str) -> None:
        ttk.Label(parent_, text=label + ":", foreground="#555",
                  width=20, anchor="e").grid(row=row_idx, column=0,
                                              sticky="e", pady=2, padx=(0, 8))
        ttk.Label(parent_, text=value or "—").grid(
            row=row_idx, column=1, sticky="w", pady=2)

    field(head, 0, "Student",
          f"{row.student_id} — {row.student_name}")
    field(head, 1, "University", row.university)
    field(head, 2, "Course",
          row.course_name + (f"  ({row.course_code})"
                              if row.course_code else ""))
    field(head, 3, "Entry year",
          str(row.entry_year) if row.entry_year else "—")
    field(head, 4, "Decision status", row.decision_status)
    field(head, 5, "Offer terms (UCAS)", row.offer_terms or "—")
    field(head, 6, "Final decision (UCAS)", row.final_decision or "—")
    field(head, 7, "Predicted grade", row.predicted_grade or "—")

    form = ttk.LabelFrame(parent, text="Offer details", padding=8)
    form.pack(anchor="w", fill="x", pady=(8, 0))
    form.columnconfigure(1, weight=1, minsize=320)

    req_var = tk.StringVar(
        value=(details.grade_requirement or "") if details else "")
    alt_var = tk.StringVar(
        value=(details.grade_alternative or "") if details else "")
    deadline_var = tk.StringVar(
        value=(details.reply_deadline or "") if details else "")
    expiry_var = tk.StringVar(
        value=(details.expiry_date or "") if details else "")
    scholarship_var = tk.StringVar(
        value=(details.scholarship or "") if details else "")
    accom_var = tk.BooleanVar(
        value=bool(details.accommodation_guaranteed) if details else False)

    notes_text = tk.Text(form, height=4, width=60)
    if details and details.notes:
        notes_text.insert("1.0", details.notes)

    def row_(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    row_(0, "Grade requirement",
         ttk.Entry(form, textvariable=req_var, width=42))
    row_(1, "Alternative pathway",
         ttk.Entry(form, textvariable=alt_var, width=42))
    row_(2, "Reply deadline (YYYY-MM-DD)",
         ttk.Entry(form, textvariable=deadline_var, width=14))
    row_(3, "Expiry date (YYYY-MM-DD)",
         ttk.Entry(form, textvariable=expiry_var, width=14))
    row_(4, "Scholarship",
         ttk.Entry(form, textvariable=scholarship_var, width=32))
    row_(5, "Accommodation guaranteed",
         ttk.Checkbutton(form, variable=accom_var))
    ttk.Label(form, text="Notes").grid(
        row=6, column=0, sticky="ne", padx=(0, 8), pady=4)
    notes_text.grid(row=6, column=1, sticky="ew", pady=4)

    # Final-decision selector
    final_row = ttk.Frame(parent)
    final_row.pack(anchor="w", pady=(8, 0))
    ttk.Label(final_row, text="Final decision:",
              font=("", 10, "bold")).pack(side="left")
    final_var = tk.StringVar(value=row.final_decision or "")
    ttk.Combobox(final_row, textvariable=final_var,
                 values=["", *FINAL_DECISIONS], state="readonly",
                 width=14).pack(side="left", padx=(6, 0))

    # Actions
    actions = ttk.Frame(parent)
    actions.pack(anchor="w", pady=(12, 0))

    def save() -> None:
        try:
            data.save_details(choice_id, {
                "grade_requirement": req_var.get(),
                "grade_alternative": alt_var.get(),
                "reply_deadline":    deadline_var.get(),
                "expiry_date":       expiry_var.get(),
                "scholarship":       scholarship_var.get(),
                "accommodation_guaranteed": accom_var.get(),
                "notes":             notes_text.get("1.0", "end-1c").strip(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("save_details crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        try:
            data.set_final_decision(choice_id, final_var.get() or None)
        except ValidationError as e:
            messagebox.showerror("Cannot set final",
                                 str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("set_final_decision crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
            return
        gui.status_var.set(f"Saved offer for choice #{choice_id}")
        messagebox.showinfo("Saved",
                            f"Saved offer details for choice #{choice_id}.",
                            parent=gui.root)
        open_editor(gui, choice_id=choice_id)

    def clear_details() -> None:
        if not details:
            return
        if not messagebox.askyesno(
            "Clear offer details",
            "Remove the offer-details row? (The UCAS choice itself stays.)",
            parent=gui.root,
        ):
            return
        try:
            data.delete_details(choice_id)
        except Exception as e:
            logger.exception("delete_details crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        open_editor(gui, choice_id=choice_id)

    ttk.Button(actions, text="Save",
               command=save).pack(side="left", padx=(0, 6))
    if details:
        ttk.Button(actions, text="Clear offer details",
                   command=clear_details).pack(side="left", padx=(0, 6))


# ─── Per-student compare tab ────────────────────────────────────────

def _build_compare_tab(gui, parent: ttk.Frame) -> None:
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
        rows = data.offers_for_student(sid)
        if not rows:
            ttk.Label(holder, text="No UCAS choices for this student.",
                      foreground="#555").pack(anchor="w")
            return

        student = student_data.get_student(sid)
        ttk.Label(
            holder,
            text=f"{student.student_id}  {student.full_name}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        cols = ("slot", "uni", "course", "decision",
                "required", "alt", "predicted",
                "deadline", "scholarship", "accom", "final")
        headings = {
            "slot":        ("Slot",        40),
            "uni":         ("Univ.",      130),
            "course":      ("Course",     160),
            "decision":    ("Decision",   170),
            "required":    ("Required",   140),
            "alt":         ("Alt path",   120),
            "predicted":   ("Predicted",   80),
            "deadline":    ("Deadline",    90),
            "scholarship": ("Scholarship",140),
            "accom":       ("Accom?",      60),
            "final":       ("Final",       80),
        }
        tree = ttk.Treeview(holder, columns=cols,
                            show="headings", height=8)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for r in rows:
            d = r.details
            tree.insert("", "end", iid=str(r.choice_id), values=(
                r.choice_order, r.university,
                r.course_name + (f" ({r.course_code})"
                                  if r.course_code else ""),
                r.decision_status,
                (d.grade_requirement if d and d.grade_requirement
                 else (r.offer_terms or "—")),
                (d.grade_alternative if d and d.grade_alternative else "—"),
                r.predicted_grade or "—",
                (d.reply_deadline if d and d.reply_deadline else "—"),
                (d.scholarship if d and d.scholarship else "—"),
                ("Yes" if d and d.accommodation_guaranteed else "No"),
                r.final_decision or "—",
            ))

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _edit() -> None:
            cid = _selected()
            if cid is None:
                messagebox.showinfo("No selection",
                                    "Pick a row first.", parent=gui.root)
                return
            open_editor(gui, choice_id=cid)
        tree.bind("<Double-1>", lambda _e: _edit())

        actions = ttk.Frame(holder)
        actions.pack(anchor="w", pady=(8, 0))
        ttk.Button(actions, text="Edit selected offer",
                   command=_edit).pack(side="left", padx=(0, 6))
        gui.status_var.set(f"Compare offers for {sid}: {len(rows)} row(s)")

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
    window_var = tk.StringVar(value="30")
    ttk.Label(bar, text="Deadline window (days):").pack(side="left")
    ttk.Entry(bar, textvariable=window_var, width=6
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            days = int(window_var.get())
        except ValueError:
            ttk.Label(holder, text="Window must be a number.",
                      foreground="#a33").pack(anchor="w")
            return
        try:
            summ = data.summary(deadline_window_days=days)
        except Exception as e:
            logger.exception("summary failed")
            ttk.Label(holder, text=f"Error: {e}",
                      foreground="#a33").pack(anchor="w")
            return

        ttk.Label(
            holder,
            text=f"Choices: {summ.total_choices}  ·  "
                 f"Offers: {summ.total_offers}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(holder, text="By decision status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for st, n in sorted(summ.by_decision.items()):
            ttk.Label(holder, text=f"   {st:<22} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="By final decision:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for st, n in sorted(summ.by_final.items()):
            label = st if st != "(none)" else "Not decided"
            ttk.Label(holder, text=f"   {label:<22} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Extras:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        ttk.Label(holder,
                  text=f"   Scholarships             : {summ.with_scholarship}",
                  foreground="#444").pack(anchor="w")
        ttk.Label(holder,
                  text=f"   Accommodation guaranteed : {summ.with_accommodation}",
                  foreground="#444").pack(anchor="w")
        ttk.Label(holder,
                  text=f"   Upcoming reply deadlines ({days}d, no final yet) : "
                       f"{summ.upcoming_deadlines}",
                  foreground="#a33" if summ.upcoming_deadlines else "#444"
                  ).pack(anchor="w")
        gui.status_var.set("Offer summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
