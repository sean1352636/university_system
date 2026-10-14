"""Tkinter views for KS5 Destinations.

Single window with three tabs:

* **Records** — filterable table (checkpoint, destination type,
  student-id). Create / edit / delete a destination record. Double-
  click a row to edit. The "Missing" tab focuses on students with no
  capture at a chosen checkpoint.
* **Missing** — students who don't have a record at a chosen
  checkpoint (default LEAVING). Pick one and a save dialog opens
  pre-filled for that student.
* **Summary** — counts of records, students captured / missing at
  LEAVING, positive sustained-destination counts at LEAVING / +6 /
  +12, breakdowns by checkpoint, type and study level.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

from education_system.platform import branding
from education_system.platform.delivery.gui.date_picker import DatePicker
from education_system.systems.sixth_form.domain.progression.destinations import (
    destinations as data,
)
from education_system.systems.sixth_form.domain.progression.destinations.destinations import (
    CHECKPOINTS,
    CHECKPOINT_LABELS,
    CONFIRMED_VIA,
    DEFAULT_CHECKPOINT,
    DEFAULT_DESTINATION_TYPE,
    DESTINATION_TYPES,
    DestinationRecord,
    POSITIVE_TYPES,
    SALARY_BANDS,
    STUDY_LEVELS,
    ValidationError,
)
from education_system.systems.sixth_form.domain.learners.students import (
    students as student_data,
)
from education_system.systems.sixth_form.domain.progression import (
    destination_courses,
)
from education_system.systems.sixth_form.domain.progression.destinations import (
    destinations_links as links,
)

logger = logging.getLogger(__name__)

WIN_GEOMETRY = "1400x900"
WIN_MINSIZE = (1200, 800)

_TYPE_TAGS: dict[str, tuple[str, str]] = {
    "Higher Education":    ("#e6f0ff", "#1a3f8c"),
    "Further Education":   ("#e6f0ff", "#1a3f8c"),
    "Apprenticeship":      ("#e6f7e6", "#0d6b2a"),
    "Employment":          ("#e6f7e6", "#0d6b2a"),
    "Training":            ("#e6f7e6", "#0d6b2a"),
    "Gap Year":            ("#fff7e6", "#7a5800"),
    "NEET":                ("#ffd1d1", "#8c0d0d"),
    "Unknown":             ("#eeeeee", "#666666"),
}


#: The open Destinations window, if there is one. A second copy over the
#: same database is not a second opinion — edits in one leave the other
#: silently stale — so the menu item raises the existing window instead.
_OPEN_WINDOW: tk.Misc | None = None


def _existing_window() -> tk.Misc | None:
    """The live Destinations window, or None if it was closed."""
    win = _OPEN_WINDOW
    if win is None:
        return None
    try:
        return win if win.winfo_exists() else None
    except tk.TclError:
        return None


def open_directory(parent=None) -> None:
    global _OPEN_WINDOW

    existing = _existing_window()
    if existing is not None:
        existing.deiconify()
        existing.lift()
        existing.focus_force()
        return

    try:
        data.init_db()
    except Exception:
        logger.exception("Destinations init_db failed")
        messagebox.showerror(
            "Destinations",
            "Could not initialise the database. Check logs.")
        return

    master = getattr(parent, "root", parent)
    win = tk.Toplevel(master) if master is not None else tk.Tk()
    win.title(f"KS5 Destinations — {branding.SYSTEM_NAME}")
    win.geometry(WIN_GEOMETRY)
    win.minsize(*WIN_MINSIZE)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=10, pady=10)

    records_tab = RecordsTab(nb, win)
    MissingTab(nb, win, records_tab)
    SummaryTab(nb, win, records_tab)

    _OPEN_WINDOW = win

    def _forget(event, w=win):
        global _OPEN_WINDOW
        if event.widget is w:
            _OPEN_WINDOW = None

    win.bind("<Destroy>", _forget, add="+")


def _student_options() -> list[tuple[str, str]]:
    rows = sorted(student_data.list_students(),
                   key=lambda s: s.student_id)
    return [(s.student_id, f"{s.student_id} — {s.full_name}")
            for s in rows]


# ─────────────────────────────────────────────────────────────────
# Records tab
# ─────────────────────────────────────────────────────────────────

class RecordsTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc) -> None:
        self.root = root
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Records")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Checkpoint:").pack(side="left")
        self.f_cp = ttk.Combobox(
            bar, values=("",) + CHECKPOINTS,
            state="readonly", width=10)
        self.f_cp.current(0)
        self.f_cp.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Type:").pack(side="left")
        self.f_type = ttk.Combobox(
            bar, values=("",) + DESTINATION_TYPES,
            state="readonly", width=20)
        self.f_type.current(0)
        self.f_type.pack(side="left", padx=(2, 8))
        ttk.Label(bar, text="Student id:").pack(side="left")
        self.f_student = ttk.Entry(bar, width=12)
        self.f_student.pack(side="left", padx=(2, 8))
        ttk.Button(bar, text="Apply",
                    command=self.refresh).pack(side="left", padx=(8, 4))
        ttk.Button(bar, text="Clear",
                    command=self._clear).pack(side="left")
        ttk.Button(bar, text="New record",
                    command=self._new).pack(side="left", padx=(16, 0))

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("id", "student", "name", "checkpoint", "type",
                "target", "level", "salary", "confirmed")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        widths = {"id": 50, "student": 90, "name": 160,
                   "checkpoint": 90, "type": 150, "target": 280,
                   "level": 90, "salary": 110, "confirmed": 110}
        for c in cols:
            self.tree.heading(c, text=c.replace("_", " ").title())
            self.tree.column(c, width=widths[c],
                              anchor=("center" if c == "id" else "w"))
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for dtype, (bg, fg) in _TYPE_TAGS.items():
            self.tree.tag_configure(dtype, background=bg, foreground=fg)
        self.tree.bind("<Double-Button-1>", lambda _e: self._edit())

        actions = ttk.Frame(self.frame)
        actions.pack(fill="x", padx=8, pady=(4, 8))
        for label, cmd in (
                ("View / Edit", self._edit),
                ("Next step…",  self._next_step),
                ("Delete",       self._delete),
                ("Refresh",      self.refresh),
        ):
            ttk.Button(actions, text=label,
                        command=cmd).pack(side="left", padx=4)
        self.count = ttk.Label(actions, text="")
        self.count.pack(side="right")

    def _clear(self) -> None:
        self.f_cp.current(0)
        self.f_type.current(0)
        self.f_student.delete(0, "end")
        self.refresh()

    def _filters(self) -> dict[str, Any]:
        f: dict[str, Any] = {}
        if self.f_cp.get():
            f["checkpoint"] = self.f_cp.get()
        if self.f_type.get():
            f["destination_type"] = self.f_type.get()
        if self.f_student.get().strip():
            f["student_id"] = self.f_student.get().strip()
        return f

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        try:
            rows = data.list_records_with_detail(**self._filters())
        except ValidationError as e:
            messagebox.showwarning("Destinations", str(e), parent=self.root)
            return
        except Exception as e:
            logger.exception("Records refresh failed")
            messagebox.showerror("Destinations",
                                   f"Could not load records: {e}",
                                   parent=self.root)
            return
        for r in rows:
            d = r.record
            self.tree.insert(
                "", "end", iid=str(d.record_id),
                values=(d.record_id, d.student_id, r.student_name,
                          d.checkpoint, d.destination_type,
                          d.display_target(),
                          d.study_level or "—",
                          d.salary_band or "—",
                          d.confirmed_date or "—"),
                tags=(d.destination_type,),
            )
        self.count.configure(text=f"{len(rows)} record(s)")

    def _selected_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Destinations",
                                 "Select a record first.",
                                 parent=self.root)
            return None
        try:
            return int(sel[0])
        except (TypeError, ValueError):
            return None

    def _new(self) -> None:
        if not student_data.list_students():
            messagebox.showinfo("Destinations",
                                 "Add at least one student first.",
                                 parent=self.root)
            return
        RecordDialog(self.root, on_save=lambda _r: self.refresh())

    def _edit(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        rec = data.get_record(rid)
        if rec is None:
            self.refresh()
            return
        RecordDialog(self.root, record=rec,
                       on_save=lambda _r: self.refresh())

    def _delete(self) -> None:
        rid = self._selected_id()
        if rid is None:
            return
        if not messagebox.askyesno(
                "Destinations", f"Delete record #{rid}?", parent=self.root):
            return
        try:
            data.delete_record(rid)
        except Exception as e:
            logger.exception("delete_record failed")
            messagebox.showerror("Destinations",
                                   f"Delete failed: {e}", parent=self.root)
            return
        self.refresh()

    def _next_step(self) -> None:
        """Offer the receiving system's own intake for this destination."""
        rid = self._selected_id()
        if rid is None:
            return
        rec = data.get_record(rid)
        if rec is None:
            self.refresh()
            return
        step = links.next_step(rec)
        if step is None:
            messagebox.showinfo(
                "Destinations",
                f"{rec.destination_type} has no follow-on step here.\n\n"
                "Employment, a gap year and NEET are destinations in their "
                "own right, not handovers.",
                parent=self.root)
            return

        if step.kind == "external":
            messagebox.showinfo("Destinations",
                                 f"{step.label}\n\n{step.detail}",
                                 parent=self.root)
            return

        if step.kind == "fe_college":
            # The FE referral needs a pathway, a reason and a consent
            # decision, none of which a destination record holds — so the
            # referral form collects them and submits.
            if messagebox.askyesno("Destinations",
                                    f"{step.detail}\n\nOpen the FE referral "
                                    f"form for {rec.student_id}?",
                                    parent=self.root):
                from education_system.systems.sixth_form.domain.progression import (
                    post16_pathway_views,
                )
                post16_pathway_views.open_window(self.root)
            return

        # Preview first: a submission creates a real applicant in another
        # system, so show exactly what will cross the boundary and let the
        # user decide. Nothing is written until they confirm.
        preview = links.perform_handover(rec, dry_run=True)
        if not preview.ok:
            messagebox.showwarning(
                "Handover not ready", preview.detail, parent=self.root)
            return
        if not messagebox.askyesno(
                "Confirm handover",
                f"{preview.detail}\n\nHand {rec.student_id} over now?",
                parent=self.root):
            return

        result = links.perform_handover(rec)
        if result.ok:
            messagebox.showinfo(
                "Handover complete",
                f"{result.summary}"
                + (f"\n\nReference: {result.reference}" if result.reference else ""),
                parent=self.root)
            self.refresh()
        else:
            messagebox.showerror("Handover failed", result.detail,
                                  parent=self.root)

    def open_for(self, student_id: str, checkpoint: str,
                  preset: dict | None = None) -> None:
        """Open the save dialog pre-filled for a (student, cp)."""
        rec = data.get_record_for(student_id, checkpoint)
        if rec is not None:
            RecordDialog(self.root, record=rec,
                           on_save=lambda _r: self.refresh())
        else:
            RecordDialog(self.root,
                           preset_student=student_id,
                           preset_checkpoint=checkpoint,
                           preset=preset,
                           on_save=lambda _r: self.refresh())


# ─────────────────────────────────────────────────────────────────
# Record dialog
# ─────────────────────────────────────────────────────────────────

#: Which optional fields each destination type actually uses.
#:
#: The record table carries every column for every type, so nothing here
#: is enforced by the data layer — but showing a salary band against a
#: university place is noise, and worse, invites someone to fill it in.
#: Anything not listed is hidden, and hidden fields are saved empty so a
#: type change cannot leave a stale employer hanging off a degree.
_TYPE_FIELDS: dict[str, tuple[str, ...]] = {
    "Higher Education":  ("institution", "course", "study_level"),
    "Further Education": ("institution", "course", "study_level"),
    "Apprenticeship":    ("employer", "role", "institution", "course",
                          "study_level", "salary_band"),
    "Employment":        ("employer", "role", "salary_band"),
    "Training":          ("institution", "course", "salary_band"),
    "Gap Year":          (),
    "NEET":              (),
    "Unknown":           (),
}

_FIELD_LABELS: dict[str, str] = {
    "institution": "Institution:",
    "course":      "Course:",
    "employer":    "Employer:",
    "role":        "Role:",
    "study_level": "Study level:",
    "salary_band": "Salary band:",
}

#: Same field, different word depending on where the student went.
_TYPE_FIELD_LABELS: dict[str, dict[str, str]] = {
    "Apprenticeship": {"institution": "Training provider:",
                       "course":      "Standard / framework:"},
    "Training":       {"institution": "Provider:",
                       "course":      "Programme:"},
}


class RecordDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, *,
                 record: DestinationRecord | None = None,
                 preset_student: str | None = None,
                 preset_checkpoint: str | None = None,
                 preset: dict | None = None,
                 on_save) -> None:
        super().__init__(master)
        self.record = record
        self._preset_student = preset_student
        self._preset_checkpoint = preset_checkpoint
        self._preset = preset or {}
        self.on_save = on_save
        # This platform's own university, offered by name alongside the
        # free-text history, with its live course catalogue behind it.
        # Best-effort: a sixth form running without the university
        # installed gets None / [] and the plain suggestion lists.
        self._home_name = destination_courses.home_institution_name()
        self._home_courses = destination_courses.home_courses()
        self.title("Edit Destination" if record else "New Destination")
        self.geometry("760x820")
        self.minsize(680, 640)
        self.transient(master)
        self._rows: dict[str, tuple[ttk.Label, tk.Misc, int]] = {}
        self._build()
        self._apply_preset()
        self._apply_type_visibility()
        # Deliberately *not* grab_set(). A Tk grab is application-modal,
        # not window-modal, so grabbing here froze the main GUI and every
        # other tool for as long as somebody had a record open. Staying
        # transient keeps this above the Destinations window without
        # holding the rest of the application hostage.
        #
        # The trade: two dialogs can be opened on the same record. The
        # save is an upsert keyed on (student, checkpoint), so the last
        # save wins — the same outcome as two people editing from
        # different machines.
        self.after_idle(self.lift)

    @staticmethod
    def _suggestions(field: str) -> list[str]:
        """Values already used for *field*, for the dropdown list."""
        try:
            return list(data.distinct_values(field))
        except Exception:
            logger.debug("Could not load suggestions for %s", field, exc_info=True)
            return []

    def _institution_values(self) -> list[str]:
        """Our own university first, then everywhere used before."""
        seen = self._suggestions("institution")
        if not self._home_name:
            return seen
        return [self._home_name] + [v for v in seen if v != self._home_name]

    def _refresh_courses(self) -> None:
        """Offer the university's catalogue when it is the institution.

        Anywhere else, fall back to course names already typed — we have
        no catalogue for other providers, and guessing one would be worse
        than letting staff type it.
        """
        picked = self.cb_inst.get().strip()
        if self._home_name and picked == self._home_name and self._home_courses:
            values = [o.label for o in self._home_courses]
        else:
            values = self._suggestions("course")
        self.cb_course.configure(values=values)

    def _course_value(self) -> str:
        """The course to store: a catalogue pick saves its plain name.

        ``dest_records`` has no course-code column, so keeping the
        ``"Name (CODE)"`` label would put display furniture in the data
        and break the type-ahead next time the record is opened.
        """
        raw = self.cb_course.get().strip()
        match = destination_courses.by_label(self._home_courses, raw)
        return match.name if match else raw

    def _build(self) -> None:
        record = self.record
        preset_student = self._preset_student
        preset_checkpoint = self._preset_checkpoint

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)
        row = 0

        ttk.Label(frm, text="Student:").grid(
            row=row, column=0, sticky="w", pady=4)
        student_opts = _student_options()
        if record:
            ttk.Label(frm,
                       text=f"{record.student_id}").grid(
                row=row, column=1, sticky="w", pady=4)
            self._student_locked = record.student_id
        else:
            self._student_map = {lbl: sid for sid, lbl in student_opts}
            self.cb_student = ttk.Combobox(
                frm, values=[lbl for _sid, lbl in student_opts],
                state="readonly")
            if preset_student:
                current = next(
                    (lbl for sid, lbl in student_opts
                     if sid == preset_student), "")
                self.cb_student.set(current)
            self.cb_student.grid(row=row, column=1, sticky="ew", pady=4)
            self._student_locked = None
        row += 1

        ttk.Label(frm, text="Checkpoint:").grid(
            row=row, column=0, sticky="w", pady=4)
        if record:
            ttk.Label(frm,
                       text=f"{record.checkpoint}  "
                            f"({CHECKPOINT_LABELS[record.checkpoint]})").grid(
                row=row, column=1, sticky="w", pady=4)
            self._checkpoint_locked = record.checkpoint
        else:
            self.cb_cp = ttk.Combobox(
                frm, values=CHECKPOINTS, state="readonly")
            self.cb_cp.set(preset_checkpoint or DEFAULT_CHECKPOINT)
            self.cb_cp.grid(row=row, column=1, sticky="ew", pady=4)
            self._checkpoint_locked = None
        row += 1

        ttk.Label(frm, text="Destination type:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_type = ttk.Combobox(
            frm, values=DESTINATION_TYPES, state="readonly")
        self.cb_type.set(record.destination_type if record
                          else DEFAULT_DESTINATION_TYPE)
        self.cb_type.grid(row=row, column=1, sticky="ew", pady=4)
        self.cb_type.bind("<<ComboboxSelected>>",
                          lambda _e: self._apply_type_visibility())
        row += 1

        self.hint = ttk.Label(frm, text="", foreground="#666", wraplength=520,
                              justify="left")
        self.hint.grid(row=row, column=1, sticky="w", pady=(0, 6))
        row += 1

        # ── Type-dependent fields ────────────────────────────────
        # Editable comboboxes: pick a value used before, or type a new
        # one. Most of a cohort lands at a handful of places.
        self.cb_inst = ttk.Combobox(frm, values=self._institution_values())
        if record and record.institution:
            self.cb_inst.set(record.institution)
        # Choosing our own university swaps the course list over to its
        # catalogue, which is the whole point of naming it here.
        self.cb_inst.bind("<<ComboboxSelected>>",
                          lambda _e: self._refresh_courses())
        row = self._place(frm, "institution", self.cb_inst, row)

        self.cb_course = ttk.Combobox(frm)
        row = self._place(frm, "course", self.cb_course, row)
        self._refresh_courses()
        if record and record.course:
            # Show the catalogue label when the stored name is one of
            # ours, so the dropdown opens on the right row.
            match = destination_courses.resolve(self._home_courses,
                                                name=record.course)
            self.cb_course.set(match.label if match else record.course)

        for attr, field in (("cb_employer", "employer"),
                            ("cb_role", "role")):
            widget = ttk.Combobox(frm, values=self._suggestions(field))
            current = getattr(record, field, None) if record else None
            if current:
                widget.set(current)
            setattr(self, attr, widget)
            row = self._place(frm, field, widget, row)

        self.cb_level = ttk.Combobox(
            frm, values=("",) + STUDY_LEVELS, state="readonly")
        self.cb_level.set(record.study_level if record
                            and record.study_level else "")
        row = self._place(frm, "study_level", self.cb_level, row)

        self.cb_salary = ttk.Combobox(
            frm, values=("",) + SALARY_BANDS, state="readonly")
        self.cb_salary.set(record.salary_band if record
                            and record.salary_band else "")
        row = self._place(frm, "salary_band", self.cb_salary, row)

        # ── Always shown ─────────────────────────────────────────
        ttk.Label(frm, text="Start date:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.d_start = DatePicker(
            frm, value=record.start_date if record else None)
        self.d_start.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Confirmed via:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.cb_via = ttk.Combobox(
            frm, values=("",) + CONFIRMED_VIA, state="readonly")
        self.cb_via.set(record.confirmed_via if record
                          and record.confirmed_via else "")
        self.cb_via.grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        ttk.Label(frm, text="Confirmed date:").grid(
            row=row, column=0, sticky="w", pady=4)
        self.d_confirmed = DatePicker(
            frm, value=record.confirmed_date if record else None)
        self.d_confirmed.grid(row=row, column=1, sticky="w", pady=4)
        row += 1

        ttk.Label(frm, text="Notes:").grid(
            row=row, column=0, sticky="nw", pady=4)
        self.t_notes = tk.Text(frm, height=5, wrap="word")
        self.t_notes.grid(row=row, column=1, sticky="ew", pady=4)
        if record and record.notes:
            self.t_notes.insert("1.0", record.notes)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2,
                    sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel",
                    command=self.destroy).pack(side="right", padx=4)
        ttk.Button(btns, text="Save",
                    command=self._save).pack(side="right", padx=4)

    def _place(self, frm: ttk.Frame, field: str,
               widget: tk.Misc, row: int) -> int:
        """Grid a type-dependent field and remember how to re-show it."""
        label = ttk.Label(frm, text=_FIELD_LABELS[field])
        label.grid(row=row, column=0, sticky="w", pady=4)
        widget.grid(row=row, column=1, sticky="ew", pady=4)
        self._rows[field] = (label, widget, row)
        return row + 1

    def _apply_type_visibility(self) -> None:
        """Show only the fields the chosen destination type uses."""
        dtype = self.cb_type.get() or DEFAULT_DESTINATION_TYPE
        wanted = _TYPE_FIELDS.get(dtype, ())
        overrides = _TYPE_FIELD_LABELS.get(dtype, {})
        for field, (label, widget, _row) in self._rows.items():
            if field in wanted:
                label.configure(text=overrides.get(field, _FIELD_LABELS[field]))
                label.grid()
                widget.grid()
            else:
                label.grid_remove()
                widget.grid_remove()
        if wanted:
            self.hint.configure(text="")
        else:
            self.hint.configure(
                text=f"{dtype} records capture no placement detail — "
                     "use Notes for anything worth keeping.")

    def _apply_preset(self) -> None:
        """Fill the form from a payload captured elsewhere (e.g. UCAS)."""
        preset = self._preset
        if not preset:
            return
        if preset.get("destination_type"):
            self.cb_type.set(preset["destination_type"])
        if preset.get("institution"):
            self.cb_inst.set(preset["institution"])
            self._refresh_courses()
        if preset.get("course"):
            match = destination_courses.resolve(self._home_courses,
                                                name=preset["course"])
            self.cb_course.set(match.label if match else preset["course"])
        if preset.get("confirmed_via"):
            self.cb_via.set(preset["confirmed_via"])
        if preset.get("confirmed_date"):
            self.d_confirmed.set(preset["confirmed_date"])

    def _payload(self) -> dict[str, Any]:
        sid = (self._student_locked
                or self._student_map.get(self.cb_student.get(), ""))
        cp = self._checkpoint_locked or self.cb_cp.get()
        dtype = self.cb_type.get()
        wanted = _TYPE_FIELDS.get(dtype, ())

        def used(field: str, widget) -> str:
            """Blank for a field this type doesn't use.

            Sending the widget's value regardless would let a record
            edited from Employment to Higher Education keep its old
            employer and salary, invisibly.
            """
            return widget.get() if field in wanted else ""

        return {
            "student_id":       sid,
            "checkpoint":       cp,
            "destination_type": dtype,
            "institution":      used("institution", self.cb_inst),
            "course":           (self._course_value()
                                 if "course" in wanted else ""),
            "employer":         used("employer", self.cb_employer),
            "role":             used("role", self.cb_role),
            "study_level":      used("study_level", self.cb_level),
            "salary_band":      used("salary_band", self.cb_salary),
            "start_date":       self.d_start.get(),
            "confirmed_via":    self.cb_via.get(),
            "confirmed_date":   self.d_confirmed.get(),
            "notes":            self.t_notes.get("1.0", "end").strip(),
        }

    def _save(self) -> None:
        try:
            r = data.save_record(self._payload())
        except ValidationError as e:
            messagebox.showwarning("Destinations", str(e), parent=self)
            return
        except Exception as e:
            logger.exception("Destination save failed")
            messagebox.showerror("Destinations",
                                   f"Save failed: {e}", parent=self)
            return
        # Tell the platform a learner left. Best-effort by design: the
        # destination is recorded either way, and a journey that cannot
        # be opened must not look like a failed save.
        links.record_journey_transition(r)
        self.on_save(r)
        self.destroy()


# ─────────────────────────────────────────────────────────────────
# Missing tab
# ─────────────────────────────────────────────────────────────────

class MissingTab:
    def __init__(self, nb: ttk.Notebook, root: tk.Misc,
                  records_tab: RecordsTab) -> None:
        self.root = root
        self.records_tab = records_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Missing")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ttk.Label(bar, text="Checkpoint:").pack(side="left")
        self.cb_cp = ttk.Combobox(
            bar, values=CHECKPOINTS, state="readonly", width=10)
        self.cb_cp.set(DEFAULT_CHECKPOINT)
        self.cb_cp.pack(side="left", padx=(2, 8))
        self.cb_cp.bind("<<ComboboxSelected>>",
                         lambda _e: self.refresh())
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="left", padx=4)
        ttk.Button(bar, text="Record selected…",
                    command=self._record_selected).pack(
            side="left", padx=(16, 0))
        ttk.Button(bar, text="Capture from UCAS",
                    command=self._from_ucas).pack(side="left", padx=4)
        ttk.Button(bar, text="Careers follow-up…",
                    command=self._careers).pack(side="left", padx=4)

        table_frame = ttk.Frame(self.frame)
        table_frame.pack(fill="both", expand=True, padx=8, pady=4)
        cols = ("student_id", "name")
        self.tree = ttk.Treeview(table_frame, columns=cols,
                                   show="headings",
                                   selectmode="browse")
        self.tree.heading("student_id", text="Student id")
        self.tree.column("student_id", width=150, anchor="w")
        self.tree.heading("name", text="Name")
        self.tree.column("name", width=400, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                              command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-Button-1>",
                         lambda _e: self._record_selected())

        self.count = ttk.Label(self.frame, text="")
        self.count.pack(anchor="e", padx=8, pady=(0, 8))

    def refresh(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        cp = self.cb_cp.get() or DEFAULT_CHECKPOINT
        try:
            missing = data.students_missing_at(cp)
        except ValidationError as e:
            messagebox.showwarning("Destinations", str(e), parent=self.root)
            return
        except Exception as e:
            logger.exception("Missing refresh failed")
            messagebox.showerror("Destinations",
                                   f"Could not load list: {e}",
                                   parent=self.root)
            return
        names = {s.student_id: s.full_name
                  for s in student_data.list_students()}
        for sid in missing:
            self.tree.insert(
                "", "end", iid=sid,
                values=(sid, names.get(sid, "(unknown)")))
        self.count.configure(
            text=f"{len(missing)} student(s) missing at {cp}")

    def _from_ucas(self) -> None:
        """Open the capture form pre-filled from the UCAS firm choice.

        Saves retyping what UCAS already holds, and — more to the point —
        stops the destination and the firm choice disagreeing.
        """
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Destinations",
                                 "Select a student first.",
                                 parent=self.root)
            return
        sid = sel[0]
        preset = links.ucas_prefill(sid)
        if preset is None:
            messagebox.showinfo(
                "Destinations",
                f"{sid} has no firm UCAS choice to capture yet.\n\n"
                "There is nothing to copy until the learner has replied "
                "to their offers.",
                parent=self.root)
            return
        cp = self.cb_cp.get() or DEFAULT_CHECKPOINT
        self.records_tab.open_for(sid, cp, preset=preset)
        self.frame.after(100, self.refresh)

    def _careers(self) -> None:
        """Who needs a careers conversation, and who already had one."""
        rows = links.careers_followups(self.cb_cp.get() or DEFAULT_CHECKPOINT)
        if not rows:
            messagebox.showinfo("Destinations",
                                 "Nobody is missing a destination or recorded "
                                 "NEET at this checkpoint.",
                                 parent=self.root)
            return
        outstanding = [r for r in rows if not r.has_careers_record]
        lines = [f"{r.student_id} — {r.name}: {r.reason}"
                 f"{'' if r.has_careers_record else '  (no careers session)'}"
                 for r in rows]
        messagebox.showinfo(
            "Careers follow-up",
            f"{len(rows)} learner(s) need a destination conversation; "
            f"{len(outstanding)} have no careers session yet.\n\n"
            + "\n".join(lines[:25])
            + ("\n…" if len(lines) > 25 else ""),
            parent=self.root)

    def _record_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Destinations",
                                 "Select a student first.",
                                 parent=self.root)
            return
        sid = sel[0]
        cp = self.cb_cp.get() or DEFAULT_CHECKPOINT
        self.records_tab.open_for(sid, cp)
        # Refresh both tabs after dialog closes.
        self.frame.after(100, self.refresh)


# ─────────────────────────────────────────────────────────────────
# Summary tab
# ─────────────────────────────────────────────────────────────────

class SummaryTab:
    """Headline figures as stat tiles, breakdowns as labelled bars.

    Replaced a monospace text dump. The design rules it follows:

    * the four headline numbers are *stat tiles*, not a chart — a single
      magnitude reads faster as a big number than as a one-bar chart
    * every bar is labelled with its name and count, so identity and
      value never depend on colour alone
    * destination-type bars reuse ``_TYPE_TAGS`` — the same colours the
      Records table uses — so a type looks the same everywhere. Colour
      follows the entity, never its rank or size order
    * everything else uses one neutral accent: these are magnitudes of
      the same quantity, which is a sequential job, not a categorical one
    """

    #: Single accent for non-categorical magnitudes.
    BAR = "#1a3f8c"
    TRACK = "#e3e6ea"
    INK = "#1c2430"
    MUTED = "#5b6672"

    def __init__(self, nb: ttk.Notebook, root: tk.Misc,
                  records_tab: RecordsTab) -> None:
        self.root = root
        self.records_tab = records_tab
        self.frame = ttk.Frame(nb)
        nb.add(self.frame, text="Summary")
        self._build()
        self.refresh()

    def _build(self) -> None:
        bar = ttk.Frame(self.frame)
        bar.pack(fill="x", padx=12, pady=(12, 0))
        ttk.Label(bar, text="Destinations summary",
                   font=("", 15, "bold")).pack(side="left")
        ttk.Button(bar, text="Refresh",
                    command=self.refresh).pack(side="right")

        outer = ttk.Frame(self.frame)
        outer.pack(fill="both", expand=True, padx=12, pady=12)
        self.canvas = tk.Canvas(outer, highlightthickness=0, bg="#ffffff")
        vsb = ttk.Scrollbar(outer, orient="vertical",
                             command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.body = ttk.Frame(self.canvas)
        self._body_id = self.canvas.create_window(
            (0, 0), window=self.body, anchor="nw")
        self.body.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")))
        # Keep the inner frame as wide as the viewport so the bars can
        # stretch rather than sitting in a narrow column.
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfigure(self._body_id, width=e.width))

    # ── pieces ───────────────────────────────────────────────────

    def _tile(self, parent: tk.Misc, value: Any, label: str,
               note: str = "") -> None:
        card = tk.Frame(parent, bg="#f6f8fa", highlightthickness=1,
                         highlightbackground="#dde2e8")
        card.pack(side="left", expand=True, fill="both", padx=4)
        tk.Label(card, text=str(value), font=("", 26, "bold"),
                  bg="#f6f8fa", fg=self.INK).pack(anchor="w", padx=14,
                                                   pady=(12, 0))
        tk.Label(card, text=label, font=("", 9), bg="#f6f8fa",
                  fg=self.MUTED).pack(anchor="w", padx=14, pady=(0, 2))
        tk.Label(card, text=note, font=("", 9), bg="#f6f8fa",
                  fg=self.MUTED).pack(anchor="w", padx=14, pady=(0, 12))

    def _heading(self, text: str) -> None:
        tk.Label(self.body, text=text, font=("", 11, "bold"),
                  fg=self.INK, bg="#ffffff").pack(anchor="w",
                                                   pady=(18, 6))

    def _bar_row(self, label: str, count: int, total: int,
                  colour: str | None = None, note: str = "") -> None:
        """One labelled proportion bar: name, track+fill, value."""
        row = tk.Frame(self.body, bg="#ffffff")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, width=24, anchor="w", font=("", 10),
                  fg=self.INK, bg="#ffffff").pack(side="left")
        tk.Label(row, text=f"{count}", width=5, anchor="e",
                  font=("", 10, "bold"), fg=self.INK,
                  bg="#ffffff").pack(side="right")
        if note:
            tk.Label(row, text=note, width=16, anchor="e", font=("", 9),
                      fg=self.MUTED, bg="#ffffff").pack(side="right")
        track = tk.Canvas(row, height=12, bg="#ffffff",
                           highlightthickness=0)
        track.pack(side="left", fill="x", expand=True, padx=8)

        def draw(_event=None, c=track, n=count, t=total,
                  col=colour or self.BAR) -> None:
            c.delete("all")
            width = max(c.winfo_width(), 1)
            c.create_rectangle(0, 3, width, 11, fill=self.TRACK,
                                outline="")
            if t > 0 and n > 0:
                c.create_rectangle(0, 3, max(int(width * n / t), 3), 11,
                                    fill=col, outline="")

        track.bind("<Configure>", draw)
        draw()

    # ── data ─────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            s = data.summary()
        except Exception as e:
            logger.exception("Destinations summary failed")
            messagebox.showerror("Destinations",
                                   f"Summary failed: {e}",
                                   parent=self.root)
            return

        for child in self.body.winfo_children():
            child.destroy()

        cohort = s.students_with_leaving + s.students_missing_leaving
        captured_pct = (f"{s.students_with_leaving / cohort:.0%} of cohort"
                        if cohort else "no students yet")
        positive_pct = (f"{s.positive_at_leaving / s.students_with_leaving:.0%} "
                        "of those captured"
                        if s.students_with_leaving else "—")

        tiles = tk.Frame(self.body, bg="#ffffff")
        tiles.pack(fill="x", pady=(4, 0))
        self._tile(tiles, s.total_records, "Records held",
                    "across all checkpoints")
        self._tile(tiles, s.students_with_leaving, "Captured at leaving",
                    captured_pct)
        self._tile(tiles, s.students_missing_leaving, "Still missing",
                    "no leaving record")
        self._tile(tiles, s.positive_at_leaving, "Positive at leaving",
                    positive_pct)

        self._heading("Sustained positive destinations")
        base = max(s.positive_at_leaving, s.positive_at_plus_6,
                    s.positive_at_plus_12, 1)
        for cp, n in (("LEAVING", s.positive_at_leaving),
                       ("PLUS_6", s.positive_at_plus_6),
                       ("PLUS_12", s.positive_at_plus_12)):
            self._bar_row(CHECKPOINT_LABELS[cp], n, base)

        self._heading("Records by checkpoint")
        cp_total = max(sum(s.by_checkpoint.values()), 1)
        for cp, n in s.by_checkpoint.items():
            self._bar_row(f"{cp} — {CHECKPOINT_LABELS[cp]}", n, cp_total)

        self._heading("By destination type")
        type_total = max(sum(s.by_destination_type.values()), 1)
        any_type = False
        for d, n in s.by_destination_type.items():
            if not n:
                continue
            any_type = True
            colour = _TYPE_TAGS.get(d, ("", self.BAR))[1]
            self._bar_row(d, n, type_total, colour=colour,
                           note="positive" if d in POSITIVE_TYPES else "")
        if not any_type:
            tk.Label(self.body, text="No records captured yet.",
                      fg=self.MUTED, bg="#ffffff").pack(anchor="w")

        if any(n for n in s.by_level_at_leaving.values()):
            self._heading("Study level at leaving")
            lvl_total = max(sum(s.by_level_at_leaving.values()), 1)
            for lvl, n in s.by_level_at_leaving.items():
                if n:
                    self._bar_row(lvl, n, lvl_total)
