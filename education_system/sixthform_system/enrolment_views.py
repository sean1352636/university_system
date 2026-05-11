"""GUI panels for Sixth Form Enrolment CRUD.

Rendered into ``SixthFormMainGUI.content_frame``. Mirrors the layout of
``student_views``: a directory with filters + actions, plus an
add/edit form. Error handling: all DB calls live inside try/except
blocks that log via the module logger and surface user-friendly
messages through ``messagebox``.
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk
from typing import Any, Callable

from education_system.sixthform_system import (
    enrolments as data,
    students as student_data,
)
from education_system.sixthform_system.enrolments import (
    DEFAULT_STATUS,
    Enrolment,
    STATUSES,
    ValidationError,
    YEAR_GROUPS,
)

logger = logging.getLogger(__name__)


# ── Internal helpers ────────────────────────────────────────────────

def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _default_academic_year() -> str:
    """Compute the current sixth-form academic year (e.g. '2025/26').

    Rolls over on 1 August (a sensible UK academic-year start).
    """
    today = date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}/{str(start + 1)[-2:]}"


# ── Form (add + edit) ───────────────────────────────────────────────

def _enrolment_form(
    gui,
    *,
    title: str,
    existing: Enrolment | None,
    preselect_student_id: str | None,
    on_save: Callable[[dict[str, Any]], Enrolment],
) -> None:
    frame = _clear(gui)
    _heading(frame, title)

    is_edit = existing is not None

    try:
        students = student_data.list_students()
    except Exception:
        logger.exception("Could not load student list for enrolment form")
        students = []
    if not students and not is_edit:
        ttk.Label(
            frame,
            text="No students on the roll yet — add a student first.",
            foreground="#a33",
        ).pack(anchor="w")
        ttk.Button(
            frame, text="Back to Enrolments",
            command=lambda: open_directory(gui),
        ).pack(anchor="w", pady=(8, 0))
        return

    # ── Variables ──
    student_choices = [f"{s.student_id} — {s.full_name}" for s in students]
    student_lookup = {f"{s.student_id} — {s.full_name}": s.student_id for s in students}

    if is_edit:
        student_disp = next(
            (lbl for lbl, sid in student_lookup.items() if sid == existing.student_id),
            existing.student_id,
        )
    elif preselect_student_id:
        student_disp = next(
            (lbl for lbl, sid in student_lookup.items() if sid == preselect_student_id),
            "",
        )
    else:
        student_disp = ""

    student_var = tk.StringVar(value=student_disp)
    year_var = tk.StringVar(
        value=existing.academic_year if is_edit else _default_academic_year())
    yg_var = tk.StringVar(
        value=str(existing.year_group) if is_edit else str(YEAR_GROUPS[0]))
    tg_var = tk.StringVar(value=(existing.tutor_group or "") if is_edit else "")
    sd_var = tk.StringVar(
        value=(existing.start_date or "") if is_edit else date.today().isoformat())
    status_var = tk.StringVar(
        value=existing.status if is_edit else DEFAULT_STATUS)
    # ── Layout ──
    form = ttk.Frame(frame, padding=(0, 4))
    form.pack(anchor="w", fill="x")
    form.columnconfigure(1, weight=1, minsize=320)

    # `notes_text` must be parented on the grid-managed `form`, not on
    # the pack-managed `frame` — Tk refuses to grid a widget whose
    # parent already has pack-managed children.
    notes_text = tk.Text(form, height=4, width=60)

    def row(idx: int, label: str, widget: tk.Widget) -> None:
        ttk.Label(form, text=label).grid(row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    student_combo = ttk.Combobox(
        form, textvariable=student_var, values=student_choices,
        state=("readonly" if not is_edit else "disabled"), width=42,
    )
    row(0, "Student *", student_combo)

    row(1, "Academic year * (YYYY/YY)", ttk.Entry(form, textvariable=year_var))
    row(2, "Year group *", ttk.Combobox(
        form, textvariable=yg_var, values=[str(y) for y in YEAR_GROUPS],
        state="readonly", width=8))
    row(3, "Tutor group", ttk.Entry(form, textvariable=tg_var))
    row(4, "Start date (YYYY-MM-DD)", ttk.Entry(form, textvariable=sd_var))
    row(5, "Status *", ttk.Combobox(
        form, textvariable=status_var, values=list(STATUSES),
        state="readonly", width=16))
    ttk.Label(form, text="Notes").grid(row=6, column=0, sticky="ne", padx=(0, 8), pady=4)
    notes_text.grid(row=6, column=1, sticky="ew", pady=4)
    if is_edit and existing.notes:
        notes_text.insert("1.0", existing.notes)

    # ── Buttons ──
    bar = ttk.Frame(frame)
    bar.pack(anchor="w", pady=(12, 0))

    def submit() -> None:
        if is_edit:
            sid = existing.student_id
        else:
            sid = student_lookup.get(student_var.get().strip())
            if not sid:
                messagebox.showerror(
                    "Cannot save", "Please choose a student.", parent=gui.root)
                return
        payload = {
            "student_id":    sid,
            "academic_year": year_var.get(),
            "year_group":    yg_var.get(),
            "tutor_group":   tg_var.get(),
            "start_date":    sd_var.get(),
            "status":        status_var.get(),
            "notes":         notes_text.get("1.0", "end").strip(),
        }
        try:
            saved = on_save(payload)
        except ValidationError as e:
            logger.warning("Enrolment form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving enrolment form")
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=gui.root)
            return
        logger.info("GUI saved enrolment #%d via %s", saved.enrolment_id, title)
        messagebox.showinfo(
            "Saved",
            f"Enrolment #{saved.enrolment_id} saved\n"
            f"  Student : {saved.student_id}\n"
            f"  Year    : {saved.academic_year} · Year {saved.year_group}\n"
            f"  Status  : {saved.status}",
            parent=gui.root,
        )
        gui.status_var.set(f"Saved enrolment #{saved.enrolment_id}")
        open_directory(gui)

    ttk.Button(bar, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(bar, text="Cancel",
               command=lambda: open_directory(gui)).pack(side="left")


def open_add_enrolment(gui, preselect_student_id: str | None = None) -> None:
    def on_save(payload: dict[str, Any]) -> Enrolment:
        return data.create_enrolment(payload)
    _enrolment_form(
        gui, title="New Enrolment", existing=None,
        preselect_student_id=preselect_student_id, on_save=on_save,
    )
    gui.status_var.set("New enrolment")


def open_edit_enrolment(gui, enrolment_id: int) -> None:
    try:
        existing = data.get_enrolment(enrolment_id)
    except Exception as e:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not load enrolment: {e}",
                             parent=gui.root)
        return
    if existing is None:
        messagebox.showerror(
            "Not found", f"No enrolment #{enrolment_id}", parent=gui.root)
        return

    def on_save(payload: dict[str, Any]) -> Enrolment:
        return data.update_enrolment(enrolment_id, payload)

    _enrolment_form(
        gui, title=f"Edit Enrolment #{enrolment_id}",
        existing=existing, preselect_student_id=existing.student_id,
        on_save=on_save,
    )
    gui.status_var.set(f"Editing enrolment #{enrolment_id}")


# ── Directory (list + filters + actions) ────────────────────────────

def _student_name_map() -> dict[str, str]:
    try:
        return {s.student_id: s.full_name for s in student_data.list_students()}
    except Exception:
        logger.exception("Could not build student name map")
        return {}


def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "Enrolment Directory")

    # ── Filter bar ──
    filt = ttk.Frame(frame)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    year_var = tk.StringVar()
    yg_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Academic year:").pack(side="left")
    ttk.Entry(filt, textvariable=year_var, width=10).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Year group:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=yg_var,
        values=["", *[str(y) for y in YEAR_GROUPS]],
        state="readonly", width=6,
    ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(
        filt, textvariable=status_var,
        values=["", *STATUSES], state="readonly", width=12,
    ).pack(side="left", padx=(4, 12))

    table_holder = ttk.Frame(frame)
    table_holder.pack(fill="both", expand=True)
    summary = ttk.Label(frame, text="", foreground="#555")
    summary.pack(anchor="w", pady=(4, 8))
    actions_holder = ttk.Frame(frame)
    actions_holder.pack(anchor="w", pady=(0, 4))

    def refresh() -> None:
        for w in table_holder.winfo_children():
            w.destroy()
        for w in actions_holder.winfo_children():
            w.destroy()

        try:
            rows = data.list_enrolments(
                academic_year=year_var.get().strip() or None,
                year_group=int(yg_var.get()) if yg_var.get() else None,
                status=status_var.get().strip() or None,
            )
        except Exception as e:
            logger.exception("Failed to load enrolments")
            ttk.Label(
                table_holder, text=f"Error loading enrolments: {e}",
                foreground="#a33",
            ).pack(anchor="w")
            return

        names = _student_name_map()
        cols = ("enrolment_id", "student_id", "name",
                "academic_year", "year_group", "tutor_group",
                "start_date", "status")
        headings = {
            "enrolment_id":  ("#",         50),
            "student_id":    ("Student ID", 100),
            "name":          ("Name",       200),
            "academic_year": ("Year",        80),
            "year_group":    ("YG",          40),
            "tutor_group":   ("Tutor",       70),
            "start_date":    ("Start",      100),
            "status":        ("Status",     100),
        }
        tree = ttk.Treeview(table_holder, columns=cols, show="headings", height=14)
        for col in cols:
            text, width = headings[col]
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor="w")
        vs = ttk.Scrollbar(table_holder, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        for e in rows:
            tree.insert("", "end", iid=str(e.enrolment_id), values=(
                e.enrolment_id, e.student_id,
                names.get(e.student_id, "—"),
                e.academic_year, e.year_group, e.tutor_group or "—",
                e.start_date or "—", e.status,
            ))

        summary.configure(text=f"{len(rows)} enrolment(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            eid = _selected()
            if eid is None:
                messagebox.showinfo("No selection",
                                    "Pick an enrolment row first.",
                                    parent=gui.root)
            return eid

        actions = actions_holder
        ttk.Button(actions, text="View",
                   command=lambda: (_require() and open_profile(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Edit",
                   command=lambda: (_require() and open_edit_enrolment(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Delete",
                   command=lambda: (_require() and _delete_with_confirm(gui, _selected()))
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="New Enrolment",
                   command=lambda: open_add_enrolment(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions, text="Refresh", command=refresh
                   ).pack(side="left")

        tree.bind("<Double-1>",
                  lambda _e: (_selected() and open_profile(gui, _selected())))

        gui.status_var.set(f"Enrolments: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (year_var.set(""), yg_var.set(""),
                                status_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))

    refresh()


# ── Profile / delete ────────────────────────────────────────────────

def open_profile(gui, enrolment_id: int) -> None:
    frame = _clear(gui)
    _heading(frame, f"Enrolment #{enrolment_id}")

    try:
        e = data.get_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        ttk.Label(frame, text=f"Error: {exc}", foreground="#a33").pack(anchor="w")
        return
    if e is None:
        ttk.Label(frame, text="No such enrolment.", foreground="#a33").pack(anchor="w")
        return

    student = student_data.get_student(e.student_id)

    grid = ttk.Frame(frame)
    grid.pack(anchor="w", pady=(8, 0))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(grid, text=label + ":", foreground="#555",
                  width=20, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(grid, text=value or "—").grid(row=row, column=1, sticky="w", pady=2)

    field(0, "Student", f"{e.student_id} — {student.full_name if student else '(deleted)'}")
    field(1, "Academic year", e.academic_year)
    field(2, "Year group", f"Year {e.year_group}")
    field(3, "Tutor group", e.tutor_group or "—")
    field(4, "Start date", e.start_date or "—")
    field(5, "Status", e.status)
    field(6, "Created", e.created_at)
    if e.notes:
        ttk.Separator(grid, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        ttk.Label(grid, text="Notes:", foreground="#555",
                  width=20, anchor="e").grid(row=8, column=0, sticky="ne", padx=(0, 8))
        ttk.Label(grid, text=e.notes, wraplength=520, justify="left").grid(
            row=8, column=1, sticky="w")

    actions = ttk.Frame(frame)
    actions.pack(anchor="w", pady=(12, 0))
    ttk.Button(actions, text="Edit",
               command=lambda: open_edit_enrolment(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete",
               command=lambda: _delete_with_confirm(gui, e.enrolment_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")
    gui.status_var.set(f"Viewing enrolment #{enrolment_id}")


def _delete_with_confirm(gui, enrolment_id: int) -> None:
    try:
        e = data.get_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("Failed to load enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not load enrolment: {exc}",
                             parent=gui.root)
        return
    if e is None:
        messagebox.showerror("Not found",
                             f"No enrolment #{enrolment_id}", parent=gui.root)
        return
    ok = messagebox.askyesno(
        "Delete enrolment",
        f"Delete enrolment #{e.enrolment_id} for {e.student_id} "
        f"({e.academic_year}, Year {e.year_group})?",
        parent=gui.root,
    )
    if not ok:
        logger.debug("GUI delete cancelled for enrolment #%d", enrolment_id)
        return
    try:
        deleted = data.delete_enrolment(enrolment_id)
    except Exception as exc:
        logger.exception("GUI delete failed for enrolment %d", enrolment_id)
        messagebox.showerror("Error", f"Could not delete: {exc}",
                             parent=gui.root)
        return
    if deleted:
        gui.status_var.set(f"Deleted enrolment #{enrolment_id}")
        open_directory(gui)
    else:
        messagebox.showerror("Error", "Could not delete enrolment.",
                             parent=gui.root)
