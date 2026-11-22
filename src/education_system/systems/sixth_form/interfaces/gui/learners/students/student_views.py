"""GUI panels for Sixth Form Student CRUD.

Rendered into ``SixthFormMainGUI.content_frame``. Each public function
takes the main-GUI instance so it can access ``content_frame``,
``status_var``, and the navigation helpers.
"""

from __future__ import annotations

import datetime as _dt
import logging
import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from typing import Any, Callable
from education_system.platform.delivery.gui.date_picker import (
    DatePicker,
    birth_years,
    recent_years,
)
from education_system.systems.sixth_form.domain.learners.students import students as data
from education_system.systems.sixth_form.domain.learners.students import directory
from education_system.systems.sixth_form.domain.learners.students import student_profile
from education_system.systems.sixth_form.domain.learners.students import new_learner
from education_system.systems.sixth_form.domain.governance.user_management import access
from education_system.systems.sixth_form.domain.admissions.enrolments import enrolments as enrolments_data
from education_system.systems.sixth_form.domain.academics.subjects import subjects as subjects_data
from education_system.systems.sixth_form.interfaces.gui.learners.students import (
    student_enrolments_panel as enrol_panel,
)
from education_system.systems.sixth_form.domain.learners.students.students import (
    A_LEVEL_SUBJECTS,
    Student,
    ValidationError,
    generate_sixthform_email,
)


def _active_subjects() -> list[str]:
    """Live list of subjects students can choose from. Falls back to the
    seed list if the subjects module hasn't initialised yet."""
    try:
        names = subjects_data.get_active_names()
        return names or list(A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to seed subject list")
        return list(A_LEVEL_SUBJECTS)

logger = logging.getLogger(__name__)


# ── Internal helpers ────────────────────────────────────────────────

def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))


def _principal(gui) -> access.Principal:
    return getattr(gui, "principal", None) or access.current()


def _may_manage(gui) -> bool:
    return _principal(gui).can(access.STUDENTS_MANAGE)


def _can_manage(gui) -> bool:
    """Gate for Add / Edit / Delete / Change Status. The directory itself
    only needs ``students.view``, so a teacher can open it — and until now
    every one of those buttons worked for them too."""
    if _may_manage(gui):
        return True
    p = _principal(gui)
    logger.warning("Refused a student-record change for %s", p.username)
    messagebox.showwarning(
        "Not available",
        "Your account can view students but not change their records.\n\n"
        "Ask a system administrator if you need to.", parent=gui.root)
    return False


# ── Add / Edit form ─────────────────────────────────────────────────

def _student_form(
    gui,
    *,
    title: str,
    existing: Student | None,
    on_save: Callable[..., Student],
    after_save_message: Callable[[Student], str],
) -> None:
    """*on_save(payload, allow_duplicate=False)* writes the record."""
    frame = _clear(gui)
    _heading(frame, title)

    vars_: dict[str, tk.StringVar] = {
        k: tk.StringVar() for k in (
            "title", "gender",
            "first_name", "middle_name", "last_name",
            "phone", "personal_email",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relation",
            "subject_1", "subject_2", "subject_3",
            "preferred_name", "pronouns", "postcode", "previous_school",
            "address_line1", "address_line2", "town",
            "nationality", "first_language", "ethnicity",
            "upn", "uln", "uci", "candidate_number",
        )
    }
    if existing is not None:
        for key in ("preferred_name", "pronouns", "postcode", "previous_school",
                    "nationality", "first_language", "uln", "uci",
                    "candidate_number"):
            vars_[key].set(getattr(existing, key) or "")
        vars_["ethnicity"].set(existing.ethnicity_label or "")
        vars_["upn"].set(data.get_upn(existing.student_id) or "")
        vars_["title"].set(existing.title or "")
        vars_["gender"].set(student_profile.gender_label(existing.gender))
        for key, value in zip(student_profile.ADDRESS_LINE_FIELDS,
                              student_profile.address_parts(existing)):
            vars_[key].set(value)
        vars_["first_name"].set(existing.first_name)
        vars_["middle_name"].set(existing.middle_name or "")
        vars_["last_name"].set(existing.last_name)
        vars_["phone"].set(existing.phone or "")
        vars_["personal_email"].set(existing.personal_email or "")
        vars_["emergency_contact_name"].set(existing.emergency_contact_name or "")
        vars_["emergency_contact_phone"].set(existing.emergency_contact_phone or "")
        try:
            relation = student_profile.normalise_relationship(
                existing.emergency_contact_relation)
        except ValidationError:  # an over-long legacy value: show it as held
            relation = existing.emergency_contact_relation
        vars_["emergency_contact_relation"].set(relation or "")
        vars_["subject_1"].set(existing.subject_1 or "")
        vars_["subject_2"].set(existing.subject_2 or "")
        vars_["subject_3"].set(existing.subject_3 or "")

    # Two columns side by side, so the longer form still fits a 768-pixel
    # screen: the original fields on the left, the profile on the right.
    columns = ttk.Frame(frame)
    columns.pack(anchor="w", fill="x")
    form = ttk.Frame(columns, padding=(0, 4))
    form.pack(side="left", anchor="n", fill="x", expand=True)
    for col in range(2):
        form.columnconfigure(col, weight=0)
    form.columnconfigure(1, weight=1, minsize=220)
    more = ttk.Frame(columns, padding=(24, 4, 0, 4))
    more.pack(side="left", anchor="n", fill="x", expand=True)
    more.columnconfigure(1, weight=1, minsize=220)

    def row(idx: int, label: str, widget: tk.Widget, *, into=None) -> None:
        ttk.Label(into or form, text=label).grid(
            row=idx, column=0, sticky="e", padx=(0, 8), pady=4)
        widget.grid(row=idx, column=1, sticky="ew", pady=4)

    def entry(var: tk.StringVar, *, show: str | None = None) -> ttk.Entry:
        return ttk.Entry(form, textvariable=var, show=show or "")

    subject_choices = _active_subjects()

    def subject_combo(var: tk.StringVar) -> ttk.Combobox:
        return ttk.Combobox(
            form, textvariable=var, values=subject_choices,
            state="readonly", width=30,
        )

    # Identity section
    ttk.Label(form, text="Identity", font=("", 11, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
    # Title and gender: both columns and both validations already
    # existed — TITLES and GENDERS in the data layer, and the handover's
    # ``_identity()`` reads them — but no screen ever asked for them, so
    # every learner carried NULL and the university's UCAS import had
    # nothing to pre-fill from. Same gap the date of birth had.
    #
    # Blank is offered first and is a real answer. Neither is required,
    # and a readonly list with no way back out of it turns "prefer not to
    # say" into whichever option happened to be first.
    row(1, "Title", ttk.Combobox(
        form, textvariable=vars_["title"], values=["", *data.TITLES],
        state="readonly", width=12))
    row(2, "First name *", entry(vars_["first_name"]))
    row(3, "Middle name", entry(vars_["middle_name"]))
    row(4, "Last name *", entry(vars_["last_name"]))

    # Date of birth. Not decoration: the cross-system identity service
    # matches a person across systems on name + date of birth, so a
    # learner without one cannot be handed over to a university, an FE
    # college or an apprenticeship — the handover stops at "Missing date
    # of birth — the cross-system journey cannot be anchored without
    # them". The column and its validation already existed; there was
    # simply no way to fill it in.
    dob_picker = DatePicker(
        form, years=birth_years(),
        value=(existing.date_of_birth if existing else None))
    row(5, "Date of birth", dob_picker)
    row(6, "Gender", ttk.Combobox(
        form, textvariable=vars_["gender"], values=["", *student_profile.GENDER_OPTIONS],
        state="readonly", width=12))

    # Contact
    ttk.Separator(form, orient="horizontal").grid(
        row=7, column=0, columnspan=2, sticky="ew", pady=(10, 4))
    ttk.Label(form, text="Contact", font=("", 11, "bold")).grid(
        row=8, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row(9, "Phone number", entry(vars_["phone"]))

    # Sixth-form email (auto-generated, read-only)
    sf_email_var = tk.StringVar(
        value=existing.email if existing else "(auto-generated on save)")
    row(10, "Sixth-form email", ttk.Entry(
        form, textvariable=sf_email_var, state="readonly", foreground="#555"))
    row(11, "Personal email", entry(vars_["personal_email"]))

    # Emergency contact
    ttk.Separator(form, orient="horizontal").grid(
        row=12, column=0, columnspan=2, sticky="ew", pady=(10, 4))
    ttk.Label(form, text="Emergency Contact", font=("", 11, "bold")).grid(
        row=13, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row(14, "Name", entry(vars_["emergency_contact_name"]))
    row(15, "Phone number", entry(vars_["emergency_contact_phone"]))
    # A pick list, as on the other systems' forms. A legacy free-text
    # value that maps to nothing on it stays offered so a save keeps it.
    relations = ["", *student_profile.EMERGENCY_RELATIONSHIPS]
    if vars_["emergency_contact_relation"].get() not in relations:
        relations.append(vars_["emergency_contact_relation"].get())
    row(16, "Relationship", ttk.Combobox(
        form, textvariable=vars_["emergency_contact_relation"], values=relations,
        state="readonly", width=18))

    # A-Levels
    ttk.Separator(form, orient="horizontal").grid(
        row=17, column=0, columnspan=2, sticky="ew", pady=(10, 4))
    # The three slots mirror the learner's first three active A-level
    # learning aims; a fourth A level, EPQ, Core Maths, BTEC, T Level or
    # GCSE resit is added under Study Programme. Changing a slot here adds
    # / withdraws the matching aim.
    ttk.Label(form, text="A-Level Subjects (pick up to three)", font=("", 11, "bold")).grid(
        row=18, column=0, columnspan=2, sticky="w", pady=(0, 4))
    row(19, "Subject 1", subject_combo(vars_["subject_1"]))
    row(20, "Subject 2", subject_combo(vars_["subject_2"]))
    row(21, "Subject 3", subject_combo(vars_["subject_3"]))
    ttk.Label(form, foreground="#777", wraplength=420, text=(
        "Other qualifications (4th A level, EPQ, BTEC, T Level, GCSE resits) "
        "are managed under Study Programme.")).grid(
        row=22, column=0, columnspan=2, sticky="w")
    if existing is not None:
        # Status is changed with the directory's "Change Status…" button:
        # leaving and coming back have side effects a form save would skip.
        ttk.Label(form, foreground="#777", wraplength=420, text=(
            f"Record status: {existing.status}  (change it with "
            "\"Change Status…\" in the directory)")).grid(
            row=23, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # ── Right column: personal details, address, previous education ──
    def heading(idx: int, text: str, *, first: bool = False) -> None:
        if not first:
            ttk.Separator(more, orient="horizontal").grid(
                row=idx - 1, column=0, columnspan=2, sticky="ew", pady=(10, 4))
        ttk.Label(more, text=text, font=("", 11, "bold")).grid(
            row=idx, column=0, columnspan=2, sticky="w", pady=(0, 4))

    def more_entry(key: str) -> ttk.Entry:
        return ttk.Entry(more, textvariable=vars_[key])

    heading(0, "Personal details", first=True)
    row(1, "Preferred name", more_entry("preferred_name"), into=more)
    row(2, "Pronouns", ttk.Combobox(
        more, textvariable=vars_["pronouns"],
        values=["", "she/her", "he/him", "they/them"], width=14), into=more)
    row(3, "Ethnicity", ttk.Combobox(
        more, textvariable=vars_["ethnicity"],
        values=["", *(label for _c, label in student_profile.ETHNICITIES)],
        state="readonly"), into=more)
    row(4, "Nationality", more_entry("nationality"), into=more)
    row(5, "First language", more_entry("first_language"), into=more)

    # Line 1 / line 2 / town / postcode, as every other system's form asks.
    heading(7, "Home address")
    row(8, "Address line 1", more_entry("address_line1"), into=more)
    row(9, "Address line 2", more_entry("address_line2"), into=more)
    row(10, "Town", more_entry("town"), into=more)
    row(11, "Postcode", ttk.Entry(more, textvariable=vars_["postcode"], width=10),
        into=more)

    heading(13, "Previous education & identifiers")
    row(14, "Previous school", more_entry("previous_school"), into=more)
    row(15, "UPN", more_entry("upn"), into=more)
    row(16, "ULN", more_entry("uln"), into=more)
    row(17, "UCI", more_entry("uci"), into=more)
    row(18, "Candidate number", more_entry("candidate_number"), into=more)
    start_picker = DatePicker(
        more, years=recent_years(ahead=1, back=4),
        value=(existing.start_date if existing else None)
        or (None if existing else _dt.date.today().isoformat()))
    row(19, "Start date", start_picker, into=more)
    if existing is not None and existing.leaving_date:
        ttk.Label(more, foreground="#777", text=(
            f"Left {existing.leaving_date}"
            + (f": {existing.leaving_reason}" if existing.leaving_reason else ""))
        ).grid(row=20, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # Needs and medical go to the SEND register and the medical profile
    # (new_learner), so they are asked on add only; after that they are
    # kept up to date in SEND and Medical Records.
    heading(22, "Needs, medical & notes")
    lldd_var, ehcp_var = tk.BooleanVar(), tk.BooleanVar()
    send_text = medical_text = None
    if existing is None:
        ticks = ttk.Frame(more)
        ttk.Checkbutton(ticks, text="LLDD", variable=lldd_var).pack(side="left")
        ttk.Checkbutton(ticks, text="EHC Plan", variable=ehcp_var).pack(
            side="left", padx=(12, 0))
        row(23, "Declared", ticks, into=more)
        send_text = tk.Text(more, height=2, width=34, wrap="word")
        row(24, "SEND details", send_text, into=more)
        medical_text = tk.Text(more, height=2, width=34, wrap="word")
        row(25, "Medical notes", medical_text, into=more)
    else:
        ttk.Label(more, foreground="#777", wraplength=360, text=(
            "SEND and medical details are kept under SEND and Medical "
            "Records.")).grid(row=23, column=0, columnspan=2, sticky="w")
    notes_text = tk.Text(more, height=2, width=34, wrap="word")
    if existing is not None and existing.notes:
        notes_text.insert("1.0", existing.notes)
    row(26, "Notes", notes_text, into=more)

    # ── Buttons ──
    button_row = ttk.Frame(frame)
    button_row.pack(anchor="w", pady=(12, 0))

    def check_identifiers(payload: dict[str, Any]) -> dict[str, str]:
        """Validate the ULN / UCI / candidate number before anything is
        written, so a bad one cannot leave a half-saved record."""
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            identifiers,
        )
        out: dict[str, str] = {}
        for key, check in (("uln", identifiers.validate_uln),
                           ("uci", identifiers.validate_uci),
                           ("candidate_number",
                            identifiers.validate_candidate_number)):
            value = payload.pop(key).strip()
            if value == ((getattr(existing, key, None) or "") if existing else ""):
                continue
            try:
                if value:
                    check(value)
            except ValueError as e:
                raise ValidationError(str(e)) from None
            out[key] = value
        return out

    def submit() -> None:
        payload = {k: v.get() for k, v in vars_.items()}
        payload["date_of_birth"] = dob_picker.get()
        payload["start_date"] = start_picker.get()
        payload["notes"] = notes_text.get("1.0", "end").strip()
        if existing is None:
            payload["has_lldd"], payload["has_ehcp"] = lldd_var.get(), ehcp_var.get()
            payload["send_details"] = send_text.get("1.0", "end").strip()
            payload["medical_notes"] = medical_text.get("1.0", "end").strip()
        try:
            student_profile.check_emergency_contact(payload)
            ids = check_identifiers(payload)
            try:
                saved = on_save(payload)
            except data.PossibleDuplicate as dup:
                listed = "\n".join(
                    f"  • {m.student_id}  {m.full_name}  born "
                    f"{m.date_of_birth or '?'}  ({m.status})"
                    for m in dup.matches[:8])
                if not messagebox.askyesno(
                        "Possible duplicate",
                        "These students already on file look like the same "
                        f"person:\n\n{listed}\n\nOpen the existing record "
                        "instead if it is them.\n\nCreate a new record anyway?",
                        parent=gui.root):
                    return
                saved = on_save(payload, allow_duplicate=True)
        except ValidationError as e:
            logger.warning("Student form rejected: %s", e)
            messagebox.showerror("Cannot save", str(e), parent=gui.root)
            return
        except Exception as e:
            logger.exception("Unexpected error saving student form")
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=gui.root)
            return
        logger.info("GUI saved student %s via %s", saved.student_id, title)
        if ids:
            try:
                data.set_identifiers(saved.student_id, **ids)
            except ValidationError as e:
                messagebox.showwarning(
                    "Identifiers not saved",
                    f"The record was saved, but not the identifiers: {e}",
                    parent=gui.root)
        messagebox.showinfo("Saved", after_save_message(saved), parent=gui.root)
        gui.status_var.set(f"Saved student {saved.student_id}")
        open_directory(gui)

    ttk.Button(button_row, text="Save", command=submit).pack(side="left", padx=(0, 8))
    ttk.Button(
        button_row, text="Cancel", command=lambda: open_directory(gui)
    ).pack(side="left")


def open_add_student(gui) -> None:
    if not _can_manage(gui):
        return

    added: dict[str, new_learner.AddedLearner] = {}

    def on_save(payload: dict[str, Any], allow_duplicate: bool = False) -> Student:
        result = new_learner.add_learner(payload, allow_duplicate=allow_duplicate)
        added[result.student.student_id] = result
        return result.student

    def msg(s: Student) -> str:
        result = added[s.student_id]
        needs = "".join(f"\n  {line}" for line in result.needs)
        return (
            f"Created student:\n\n"
            f"  ID:       {s.student_id}\n"
            f"  Name:     {s.full_name}\n"
            f"  Email:    {s.email}\n\n"
            f"Login created in the shared auth database:\n"
            f"  Username: {s.student_id}\n"
            f"  Temporary password: {result.password}\n\n"
            "Note the password now; it won't be shown again. It is also in "
            f"the welcome e-mail to {s.personal_email or s.email}."
            + (f"\n\nNeeds:{needs}" if needs else "")
        )

    _student_form(
        gui, title="Add Student", existing=None,
        on_save=on_save, after_save_message=msg,
    )
    gui.status_var.set("Adding new student")


def open_edit_student(gui, student_id: str) -> None:
    if not _can_manage(gui):
        return
    student = data.get_student(student_id)
    if student is None:
        messagebox.showerror("Not found", f"No student with id {student_id}",
                             parent=gui.root)
        return

    def on_save(payload: dict[str, Any], allow_duplicate: bool = False) -> Student:
        return data.update_student(student_id, payload)

    def msg(s: Student) -> str:
        return f"Updated student {s.student_id} ({s.full_name})."

    _student_form(
        gui, title=f"Edit Student — {student.student_id}",
        existing=student, on_save=on_save, after_save_message=msg,
    )
    gui.status_var.set(f"Editing {student_id}")


# ── Directory (list + actions) ──────────────────────────────────────

_COLUMNS: dict[str, tuple[str, int]] = {
    "student_id": ("Student ID", 95),
    "name":       ("Name", 190),
    "year":       ("Year", 110),
    "tutor":      ("Tutor group", 90),
    "status":     ("Status", 80),
    "email":      ("Sixth-form Email", 210),
    "phone":      ("Phone", 115),
    "subjects":   ("A-Levels", 260),
    "attendance": ("Attendance", 85),
    "flags":      ("Flags", 190),
}


def _row_values(r: directory.DirectoryRow, cols: tuple[str, ...]) -> tuple:
    s = r.student
    vals = {
        "student_id": s.student_id,
        "name":       s.full_name,
        "year":       r.year_label or "—",
        "tutor":      r.tutor_group or "—",
        "status":     s.status,
        "email":      s.email,
        "phone":      s.phone or "—",
        "subjects":   ", ".join(s.subjects) or "—",
        "attendance": "—" if r.attendance_pct is None else f"{r.attendance_pct:.1f}%",
        "flags":      ", ".join(r.flags()),
    }
    return tuple(vals[c] for c in cols)


def _sort_key(r: directory.DirectoryRow, col: str):
    if col == "attendance":
        return (r.attendance_pct is None, r.attendance_pct or 0.0)
    if col == "year":
        return (r.year_group is None, r.year_group or 0)
    if col == "name":
        return (r.student.last_name.lower(), r.student.first_name.lower())
    return str(_row_values(r, (col,))[0]).lower()


def _build_directory_table(
    gui,
    parent: ttk.Frame,
    rows: list[directory.DirectoryRow],
    on_view: Callable[[str], None],
    on_edit: Callable[[str], None],
    on_delete: Callable[[str], None],
    on_refresh: Callable[[], None],
) -> None:
    vis = directory.Visibility.of(_principal(gui))
    cols = tuple(c for c in _COLUMNS
                 if not (c == "attendance" and not vis.attendance)
                 and not (c == "flags" and not (vis.send or vis.medical
                                                or vis.safeguarding)))

    # Pack the action bar first so a tall table never pushes it off a
    # 768-pixel screen.
    bulk = ttk.Frame(parent)
    bulk.pack(side="bottom", anchor="w", pady=(0, 4))
    actions = ttk.Frame(parent)
    actions.pack(side="bottom", anchor="w", pady=(0, 4))

    table_frame = ttk.Frame(parent)
    table_frame.pack(fill="both", expand=True, pady=(8, 8))

    tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=14,
                        selectmode="extended")
    order: dict[str, Any] = {"col": "name", "reverse": False}

    def fill() -> None:
        tree.delete(*tree.get_children())
        ordered = sorted(rows, key=lambda r: _sort_key(r, order["col"]),
                         reverse=order["reverse"])
        for r in ordered:
            tags = ("left",) if r.student.status == "Left" else ()
            tree.insert("", "end", iid=r.student.student_id,
                        values=_row_values(r, cols), tags=tags)

    def sort_by(col: str) -> None:
        order["reverse"] = (not order["reverse"]) if order["col"] == col else False
        order["col"] = col
        for c in cols:
            arrow = (" ▼" if order["reverse"] else " ▲") if c == col else ""
            tree.heading(c, text=_COLUMNS[c][0] + arrow)
        fill()

    for col in cols:
        text, width = _COLUMNS[col]
        tree.heading(col, text=text, command=lambda c=col: sort_by(c))
        tree.column(col, width=width, anchor="w")
    tree.tag_configure("left", foreground="#888")
    vs = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    hs = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
    hs.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")
    sort_by("name")

    def _selected() -> str | None:
        sel = tree.selection()
        return sel[0] if sel else None

    def _require_selection() -> str | None:
        sid = _selected()
        if sid is None:
            messagebox.showinfo(
                "No selection", "Select a student first.", parent=gui.root)
        return sid

    manage_state = "normal" if _may_manage(gui) else "disabled"
    ttk.Button(
        actions, text="View",
        command=lambda: (_require_selection() and on_view(_selected())),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Edit", state=manage_state,
        command=lambda: (_require_selection() and on_edit(_selected())),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Delete", state=manage_state,
        command=lambda: (_require_selection() and on_delete(_selected())),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Change Status…", state=manage_state,
        command=lambda: (_require_selection()
                         and _change_status_dialog(gui, _selected(), on_refresh)),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Study Programme",
        command=lambda: (_require_selection()
                         and _open_study_programme(gui, _selected())),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Add New", state=manage_state,
        command=lambda: open_add_student(gui),
    ).pack(side="left", padx=(12, 6))
    ttk.Button(
        actions, text="Export CSV…",
        command=lambda: _export_rows(gui, rows),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Advanced Search…",
        command=lambda: _open_advanced_search(gui),
    ).pack(side="left", padx=(0, 6))
    ttk.Button(
        actions, text="Refresh",
        command=on_refresh,
    ).pack(side="left")

    tree.bind("<Double-1>", lambda _e: (_selected() and on_view(_selected())))

    # Several learners at once: Ctrl/Shift-click to select.
    count_var = tk.StringVar(value="Selected: 0")
    ttk.Label(bulk, textvariable=count_var, foreground="#555").pack(
        side="left", padx=(0, 10))
    tree.bind("<<TreeviewSelect>>",
              lambda _e: count_var.set(f"Selected: {len(tree.selection())}"),
              add="+")

    def _require_many() -> list[str]:
        ids = list(tree.selection())
        if not ids:
            messagebox.showinfo(
                "No selection",
                "Select one or more students first (Ctrl- or Shift-click).",
                parent=gui.root)
        return ids

    def _export_selected() -> None:
        ids = set(_require_many())
        if ids:
            _export_rows(gui, [r for r in rows if r.student.student_id in ids])

    ttk.Button(bulk, text="Change status (selected)…", state=manage_state,
               command=lambda: (ids := _require_many())
               and _bulk_status_dialog(gui, ids, on_refresh)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bulk, text="Export selected…", command=_export_selected
               ).pack(side="left", padx=(0, 6))
    ttk.Button(bulk, text="Select all",
               command=lambda: tree.selection_set(tree.get_children())
               ).pack(side="left", padx=(0, 6))


def _export_rows(gui, rows: list[directory.DirectoryRow]) -> None:
    from education_system.platform.delivery.gui.parented_dialogs import filedialog
    if not rows:
        messagebox.showinfo("Nothing to export", "No students are listed.",
                            parent=gui.root)
        return
    path = filedialog.asksaveasfilename(
        parent=gui.root, title="Export student directory",
        defaultextension=".csv", initialfile="student_directory.csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
    if not path:
        return
    try:
        n = directory.export_csv(rows, path, principal=_principal(gui))
    except Exception as e:
        logger.exception("Directory export failed")
        messagebox.showerror("Export failed", str(e), parent=gui.root)
        return
    gui.status_var.set(f"Exported {n} student(s) to {path}")
    messagebox.showinfo("Exported", f"{n} student(s) written to\n{path}",
                        parent=gui.root)


def _filter_bar(gui, parent: ttk.Frame, state: dict[str, Any],
                on_change: Callable[[], None], *, with_search: bool) -> None:
    """Status / year / tutor group / subject (and search) controls. *state*
    holds the current values so a refresh keeps them."""
    try:
        opts = directory.filter_options()
    except Exception:
        logger.exception("Could not load directory filter options")
        opts = {"statuses": list(directory.STATUS_FILTERS), "years": [],
                "tutor_groups": [], "subjects": []}
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(4, 0))
    vars_: dict[str, tk.StringVar] = {}

    def combo(label: str, key: str, values: list[str], width: int) -> None:
        ttk.Label(bar, text=label).pack(side="left", padx=(0, 4))
        v = tk.StringVar(value=state.get(key, values[0] if values else ""))
        vars_[key] = v
        cb = ttk.Combobox(bar, textvariable=v, values=values,
                          state="readonly", width=width)
        cb.pack(side="left", padx=(0, 10))
        cb.bind("<<ComboboxSelected>>", lambda _e: apply())

    if with_search:
        ttk.Label(bar, text="Search:").pack(side="left", padx=(0, 4))
        q = tk.StringVar(value=state.get("query", ""))
        vars_["query"] = q
        ent = ttk.Entry(bar, textvariable=q, width=28)
        ent.pack(side="left", padx=(0, 4))
        ent.bind("<Return>", lambda _e: apply())
        ent.focus_set()
        ttk.Button(bar, text="Search", command=lambda: apply()).pack(
            side="left", padx=(0, 4))
        ttk.Button(bar, text="Advanced…",
                   command=lambda: _open_advanced_search(
                       gui, q.get().strip())).pack(side="left", padx=(0, 10))
        ttk.Label(
            parent,
            text="(matches student ID, name, either email, phone, ULN, UCI, "
                 "candidate number or tutor group)",
            foreground="#777",
        ).pack(side="bottom", anchor="w")
    combo("Status", "status", opts["statuses"], 10)
    combo("Year", "year", ["All"] + [str(y) for y in opts["years"]], 5)
    combo("Tutor group", "tutor_group", ["All"] + opts["tutor_groups"], 9)
    combo("Subject", "subject", ["All"] + opts["subjects"], 18)

    def clear() -> None:
        state.clear()
        on_change()

    ttk.Button(bar, text="Clear filters", command=clear).pack(side="left")

    def apply() -> None:
        for k, v in vars_.items():
            state[k] = v.get()
        on_change()


def _query_rows(gui, state: dict[str, Any]) -> list[directory.DirectoryRow]:
    def pick(key: str) -> str | None:
        v = (state.get(key) or "").strip()
        return None if v in ("", "All") else v
    year = pick("year")
    return directory.list_directory(
        status=state.get("status") or directory.DEFAULT_STATUS_FILTER,
        year_group=int(year) if year else None,
        tutor_group=pick("tutor_group"),
        subject=pick("subject"),
        query=pick("query"),
        principal=_principal(gui))


def _filtered_list(gui, title: str, state: dict[str, Any], *,
                   with_search: bool, rerender: Callable[[], None]) -> None:
    frame = _clear(gui)
    _heading(frame, title)
    _filter_bar(gui, frame, state, rerender, with_search=with_search)
    try:
        rows = _query_rows(gui, state)
    except Exception as e:
        logger.exception("Directory query failed")
        messagebox.showerror("Error", f"Could not load students: {e}",
                             parent=gui.root)
        rows = []
    status_label = state.get("status") or directory.DEFAULT_STATUS_FILTER
    narrowed = any((state.get(k) or "All") != "All" and state.get(k)
                   for k in ("year", "tutor_group", "subject", "query"))
    if rows:
        summary = (f"{len(rows)} student(s) on roll."
                   if status_label == "On roll" and not narrowed
                   else f"{len(rows)} student(s) shown ({status_label.lower()}).")
    elif with_search and state.get("query"):
        summary = "No matches."
    else:
        summary = ("No students yet — click 'Add New' to enrol one."
                   if not data.list_students() else
                   "No students match these filters.")
    ttk.Label(frame, text=summary, foreground="#555").pack(anchor="w", pady=(6, 0))
    _build_directory_table(
        gui, frame, rows,
        on_view=lambda sid: open_profile(gui, sid),
        on_edit=lambda sid: open_edit_student(gui, sid),
        on_delete=lambda sid: _delete_with_confirm(gui, sid, after=rerender),
        on_refresh=rerender,
    )
    gui.status_var.set(f"{title}: {len(rows)} student(s)")


def _open_advanced_search(gui, query: str = "") -> None:
    """Hand over to Advanced Search: every area, every student field, and
    saved searches. A typed search is carried across and run."""
    from education_system.systems.sixth_form.interfaces.gui.learners.advanced_search import (
        advanced_search_window,
    )
    advanced_search_window.open_advanced_search_window(
        gui, query=query or None, scopes=["students"] if query else None)


def open_directory(gui) -> None:
    state = getattr(gui, "_student_directory_filters", None)
    if state is None:
        state = {}
        gui._student_directory_filters = state
    _filtered_list(gui, "Student Directory", state, with_search=False,
                   rerender=lambda: open_directory(gui))


def open_search(gui) -> None:
    state = getattr(gui, "_student_search_filters", None)
    if state is None:
        state = {}
        gui._student_search_filters = state
    if not state:
        # Search looks across everyone, leavers included, unless narrowed.
        state["status"] = "All"
    _filtered_list(gui, "Search Students", state, with_search=True,
                   rerender=lambda: open_search(gui))


# ── Profile (read-only detail) ──────────────────────────────────────

def _photo_widget(parent, path: str | None) -> tk.Widget:
    if not path:
        return ttk.Label(parent, text="No photo", foreground="#999",
                         width=14, anchor="center", relief="groove")
    try:
        from PIL import Image, ImageTk
        img = Image.open(path)
        img.thumbnail((120, 150))
        photo = ImageTk.PhotoImage(img)
    except Exception:
        try:
            photo = tk.PhotoImage(file=path)
        except Exception:
            logger.warning("Could not render photo %s", path)
            return ttk.Label(parent, text="Photo on file\n(cannot display)",
                             foreground="#999", relief="groove")
    lbl = ttk.Label(parent, image=photo)
    lbl.image = photo  # keep a reference: Tk does not
    return lbl


def open_profile(gui, student_id: str | None = None) -> None:
    frame = _clear(gui)
    _heading(frame, "Student Profile")

    if student_id is None:
        ttk.Label(
            frame,
            text="Open a profile from the Student Directory or via Search.",
            foreground="#555",
        ).pack(anchor="w")
        return

    try:
        prof = directory.student_profile(student_id, principal=_principal(gui))
    except Exception as e:
        logger.exception("Could not build profile for %s", student_id)
        ttk.Label(frame, text=f"Could not load {student_id}: {e}",
                  foreground="#a33").pack(anchor="w")
        return
    if prof is None:
        ttk.Label(
            frame, text=f"No student found with id {student_id}",
            foreground="#a33",
        ).pack(anchor="w")
        return
    student = prof.student

    # Buttons first (bottom) so the scrolling body never hides them.
    actions = ttk.Frame(frame)
    actions.pack(side="bottom", anchor="w", pady=(8, 0))
    manage_state = "normal" if _may_manage(gui) else "disabled"
    ttk.Button(actions, text="Edit", state=manage_state,
               command=lambda: open_edit_student(gui, student.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Delete", state=manage_state,
               command=lambda: _delete_with_confirm(gui, student.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Change Status…", state=manage_state,
               command=lambda: _change_status_dialog(
                   gui, student.student_id,
                   lambda: open_profile(gui, student.student_id))
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Study Programme",
               command=lambda: _open_study_programme(gui, student.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Enrol…",
               state="normal" if enrolments_data.can_write() else "disabled",
               command=lambda: enrol_panel._enrol_views()
               .open_enrolment_from_student_profile(gui, student.student_id)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Back to Directory",
               command=lambda: open_directory(gui)).pack(side="left")

    # Scrollable body: the profile is now longer than one screen.
    outer = ttk.Frame(frame)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0)
    sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    body = ttk.Frame(canvas)
    body.bind("<Configure>",
              lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=body, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    top = ttk.Frame(body)
    top.pack(anchor="w", fill="x", pady=(8, 0))
    photo_col = ttk.Frame(top)
    photo_col.pack(side="left", anchor="n", padx=(0, 16))
    _photo_widget(photo_col, prof.photo_path).pack(anchor="n")
    ttk.Button(photo_col, text="Change photo…", state=manage_state,
               command=lambda: _change_photo(gui, student.student_id)
               ).pack(fill="x", pady=(6, 0))
    ttk.Button(photo_col, text="Remove photo",
               state=manage_state if prof.photo_path else "disabled",
               command=lambda: _remove_photo(gui, student.student_id)
               ).pack(fill="x", pady=(2, 0))
    grid = ttk.Frame(top)
    grid.pack(side="left", anchor="n")

    def section(title: str, parent=None) -> ttk.Frame:
        ttk.Separator(parent or body, orient="horizontal").pack(
            fill="x", pady=(10, 6))
        ttk.Label(parent or body, text=title,
                  font=("", 11, "bold")).pack(anchor="w", pady=(0, 4))
        f = ttk.Frame(parent or body)
        f.pack(anchor="w", fill="x")
        return f

    def fields(target: ttk.Frame, pairs: list[tuple[str, str]]) -> None:
        for i, (label, value) in enumerate(pairs):
            ttk.Label(target, text=label + ":", foreground="#555",
                      width=22, anchor="e").grid(row=i, column=0, sticky="e",
                                                 pady=2, padx=(0, 8))
            ttk.Label(target, text=value or "—").grid(row=i, column=1, sticky="w",
                                                      pady=2)

    tutor_text = prof.tutor_group or "—"
    if prof.tutor:
        tutor_text += f" (tutor {prof.tutor}" + (f", room {prof.tutor_room}"
                                                 if prof.tutor_room else "") + ")"
    fields(grid, [
        ("Student ID", student.student_id),
        ("Name", student.full_name),
        ("Preferred name", student.preferred_name or "—"),
        ("Pronouns", student.pronouns or "—"),
        ("Status", student.status),
        ("Title", student.title or "—"),
        ("Gender", student_profile.gender_label(student.gender) or "—"),
        ("Date of birth", student.date_of_birth or "—"),
        ("Current year", prof.year_label or "Not enrolled"),
        ("Tutor group", tutor_text),
        ("Sixth-form email", student.email),
        ("Personal email", student.personal_email or "—"),
        ("Phone", student.phone or "—"),
    ])

    enrol_panel.enrolment_section(gui, section("Enrolment"), student.student_id,
                                  after=lambda: open_profile(gui, student.student_id))

    fields(section("Personal Details & Address"), [
        ("Ethnicity", student.ethnicity_label or "—"),
        ("Nationality", student.nationality or "—"),
        ("First language", student.first_language or "—"),
        ("Home address", student.address or "—"),
        ("Postcode", student.postcode or "—"),
    ])

    fields(section("Emergency Contact"), [
        ("Name", student.emergency_contact_name or "—"),
        ("Phone", student.emergency_contact_phone or "—"),
        ("Relation", student.emergency_contact_relation or "—"),
    ])

    if _principal(gui).can_open("Parent Contacts"):
        box = section("Parents & Guardians")
        if prof.contacts:
            for c in prof.contacts:
                bits = [f"{c.first_name} {c.last_name} ({c.relationship})"]
                if c.primary_phone:
                    bits.append(c.primary_phone)
                if c.email:
                    bits.append(c.email)
                marks = [m for m, on in (("primary", c.is_primary),
                                         ("emergency", c.is_emergency_contact),
                                         ("PR", c.has_parental_responsibility),
                                         ("lives with", c.lives_with_student)) if on]
                if marks:
                    bits.append("[" + ", ".join(marks) + "]")
                ttk.Label(box, text=" · ".join(bits)).pack(anchor="w")
        else:
            ttk.Label(box, text="No parent or guardian contacts recorded.",
                      foreground="#777").pack(anchor="w")
        contact_bar = ttk.Frame(box)
        contact_bar.pack(anchor="w", pady=(4, 0))
        ttk.Button(contact_bar, text="Add contact…", state=manage_state,
                   command=lambda: _add_contact(gui, student.student_id)
                   ).pack(side="left", padx=(0, 6))
        ttk.Button(contact_bar, text="Open Parent Contacts",
                   command=lambda: _open_menu(gui, "Parent Contacts")).pack(
            side="left")

    subj = section("A-Level Subjects")
    fields(subj, [(f"Subject {i}", s) for i, s in enumerate(student.subjects, 1)]
           or [("Subjects", "—")])

    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
        )
        aims = learning_aims.active_aims(student.student_id)
        aims_text = "; ".join(a.label for a in aims) or "—"
    except Exception:
        logger.exception("Could not load learning aims for %s", student.student_id)
        aims_text = "(unavailable)"
    fields(section("Study Programme"), [
        ("Learning aims", aims_text),
        ("Previous school", student.previous_school or "—"),
        ("Started", student.start_date or "—"),
        ("Left", (student.leaving_date or "—")
         + (f" ({student.leaving_reason})" if student.leaving_reason else "")),
        ("UPN", data.get_upn(student.student_id) or "—"),
        ("ULN", student.uln or "—"),
        ("UCI", student.uci or "—"),
        ("Candidate number", student.candidate_number or "—"),
    ])
    if student.notes:
        ttk.Label(section("Notes"), text=student.notes, wraplength=640,
                  justify="left").grid(row=0, column=0, sticky="w", pady=2)

    if prof.records:
        rec = section("Records")
        for i, r in enumerate(prof.records):
            ttk.Label(rec, text=r.area + ":", foreground="#555", width=22,
                      anchor="e").grid(row=i, column=0, sticky="e", pady=2,
                                       padx=(0, 8))
            ttk.Label(rec, text=r.summary).grid(row=i, column=1, sticky="w")
            ttk.Button(rec, text="Open",
                       command=lambda lbl=r.menu_label: _open_menu(gui, lbl)
                       ).grid(row=i, column=2, sticky="w", padx=(10, 0))

    if prof.account is not None or _may_manage(gui):
        acc = prof.account
        fields(section("Login"), [
            ("Username", acc["username"] if acc else "—"),
            ("Account", acc["state"] if acc else "No login account"),
            ("Last sign-in", (acc["last_login"] or "Never") if acc else "—"),
        ])

    if prof.contact_log:
        log = section("Contact Log")
        tv = ttk.Treeview(log, columns=("date", "with", "method", "reason", "summary"),
                          show="headings", height=min(6, len(prof.contact_log)))
        for col, text, width in (("date", "Date", 90), ("with", "With", 140),
                                 ("method", "Method", 90), ("reason", "Reason", 140),
                                 ("summary", "Summary", 420)):
            tv.heading(col, text=text)
            tv.column(col, width=width, anchor="w")
        for c in prof.contact_log[:20]:
            who = c.contact_with + (f" ({c.contact_name})" if c.contact_name else "")
            tv.insert("", "end", values=(c.contact_date, who, c.method, c.reason,
                                         c.summary.replace("\n", " ")[:120]))
        tv.pack(anchor="w", fill="x")
        ttk.Button(log, text="Open Contact Log",
                   command=lambda: _open_menu(gui, "Contact Log")).pack(
            anchor="w", pady=(4, 0))

    hist = section("Record History")
    if prof.history:
        tv = ttk.Treeview(hist, columns=("at", "by", "what", "old", "new", "note"),
                          show="headings", height=min(8, len(prof.history)))
        for col, text, width in (("at", "When", 140), ("by", "By", 100),
                                 ("what", "What", 140), ("old", "Was", 160),
                                 ("new", "Now", 160), ("note", "Note", 260)):
            tv.heading(col, text=text)
            tv.column(col, width=width, anchor="w")
        by_id: dict[str, dict[str, Any]] = {}
        for h in prof.history:
            iid = tv.insert("", "end", values=(
                h["at"], h["changed_by"] or "—",
                "Record" if h["field"] == "record" else h["field"],
                h["old_value"] or "", h["new_value"] or "", h["note"] or ""))
            by_id[iid] = h
        tv.pack(anchor="w", fill="x")

        def revert() -> None:
            sel = tv.selection()
            entry = by_id.get(sel[0]) if sel else None
            if entry is None:
                messagebox.showinfo("Revert", "Select a change first.",
                                    parent=gui.root)
                return
            _revert_change(gui, student.student_id, entry)

        ttk.Button(hist, text="Revert selected change", state=manage_state,
                   command=revert).pack(anchor="w", pady=(4, 0))
    else:
        ttk.Label(hist, text="No changes recorded yet.",
                  foreground="#777").pack(anchor="w")

    gui.status_var.set(f"Viewing {student.student_id}")


def _change_photo(gui, student_id: str) -> None:
    if not _can_manage(gui):
        return
    from education_system.platform.delivery.gui.parented_dialogs import filedialog
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks,
    )
    path = filedialog.askopenfilename(
        parent=gui.root, title="Choose a photo",
        filetypes=[("Images", " ".join("*" + e for e in identity_checks.PHOTO_EXTENSIONS)),
                   ("All files", "*.*")])
    if not path:
        return
    try:
        identity_checks.set_photo(student_id, path, by=_principal(gui).username)
    except Exception as e:  # ValidationError and file errors alike
        logger.warning("Photo not set for %s: %s", student_id, e)
        messagebox.showerror("Photo not saved", str(e), parent=gui.root)
        return
    data.record_history(student_id, "Photo", note="Photo changed",
                        changed_by=_principal(gui).username)
    gui.status_var.set(f"Photo updated for {student_id}")
    open_profile(gui, student_id)


def _remove_photo(gui, student_id: str) -> None:
    if not _can_manage(gui):
        return
    if not messagebox.askyesno("Remove photo",
                               "Remove this student's photo?", parent=gui.root):
        return
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        identity_checks,
    )
    if identity_checks.remove_photo(student_id):
        data.record_history(student_id, "Photo", note="Photo removed",
                            changed_by=_principal(gui).username)
        gui.status_var.set(f"Photo removed for {student_id}")
    open_profile(gui, student_id)


def _add_contact(gui, student_id: str) -> None:
    """The Parent Contacts form, already pointed at this student."""
    if not _can_manage(gui):
        return
    from education_system.systems.sixth_form.domains.communications.interfaces.gui.parent_contacts import (
        parent_contacts_views,
    )
    parent_contacts_views.ContactDialog(
        gui.root, existing=None, student_id=student_id,
        on_save=lambda: open_profile(gui, student_id))


def _revert_change(gui, student_id: str, entry: dict[str, Any]) -> None:
    if not _can_manage(gui):
        return
    if not data.can_revert(entry):
        messagebox.showinfo(
            "Cannot revert",
            f"{entry['field']} entries are not field edits and cannot be "
            "reverted here.", parent=gui.root)
        return
    was = entry["old_value"] or "(empty)"
    if not messagebox.askyesno(
            "Revert change",
            f"Put {entry['field']} back to {was!r}?\n\n"
            f"(It was changed to {entry['new_value'] or '(empty)'!r} on "
            f"{entry['at']}.)", parent=gui.root):
        return
    try:
        data.revert_history(entry["history_id"], by=_principal(gui).username)
    except ValidationError as e:
        messagebox.showerror("Cannot revert", str(e), parent=gui.root)
        return
    except Exception as e:
        logger.exception("Revert failed for %s", student_id)
        messagebox.showerror("Error", f"Unexpected error: {e}", parent=gui.root)
        return
    gui.status_var.set(f"Reverted {entry['field']} for {student_id}")
    open_profile(gui, student_id)


def _open_menu(gui, label: str) -> None:
    """Open a sidebar entry by its label. The GUI already replaces the
    handler of any entry this user may not open with an "access denied"
    message, so calling it here cannot get round the menu permissions."""
    from education_system.systems.sixth_form.interfaces.gui.gui_main import NAV_CATEGORIES
    for _group, items in NAV_CATEGORIES:
        for lbl, handler in items:
            if lbl == label:
                getattr(gui, handler)()
                return
    logger.warning("No menu entry called %r", label)


def _open_study_programme(gui, student_id: str) -> None:
    """Learning aims, prior attainment, funding, hours, options, ids."""
    from education_system.systems.sixth_form.interfaces.gui.academics.qualifications import (
        study_programme_views,
    )
    study_programme_views.open_study_programme(gui.root, student_id)


# ── Status changes and delete ───────────────────────────────────────

def _change_status_dialog(gui, student_id: str,
                          after: Callable[[], None] | None = None) -> None:
    if not _can_manage(gui):
        return
    student = data.get_student(student_id)
    if student is None:
        messagebox.showerror("Not found", f"No student with id {student_id}",
                             parent=gui.root)
        return
    win = make_toplevel(gui.root)
    win.title(f"Change status — {student.full_name}")
    win.transient(gui.root)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=f"{student.full_name} ({student.student_id}) is "
                         f"currently {student.status}.").grid(
        row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
    ttk.Label(body, text="New status").grid(row=1, column=0, sticky="e", padx=(0, 8))
    status_var = tk.StringVar(value=student.status)
    ttk.Combobox(body, textvariable=status_var, values=list(data.STATUSES),
                 state="readonly", width=14).grid(row=1, column=1, sticky="w")
    ttk.Label(body, text="Reason").grid(row=2, column=0, sticky="e", padx=(0, 8),
                                        pady=6)
    reason_var = tk.StringVar()
    ttk.Entry(body, textvariable=reason_var, width=44).grid(row=2, column=1,
                                                            sticky="w")
    ttk.Label(body, foreground="#777", wraplength=420, text=(
        "Choosing Left opens the leaving form (enrolment, tutor group and "
        "login are closed; every record is kept). Moving a learner who left "
        "back on roll restores their login and tutor group.")).grid(
        row=3, column=0, columnspan=2, sticky="w", pady=(4, 8))

    def save() -> None:
        new = status_var.get()
        if new == student.status:
            win.destroy()
            return
        if new == "Left":
            win.destroy()
            _mark_left_dialog(gui, student_id, after)
            return
        try:
            data.set_status(student_id, new, reason=reason_var.get().strip() or None,
                            by=_principal(gui).username)
        except (data.ValidationError, access.AccessDenied) as e:
            messagebox.showerror("Cannot change status", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("Status change failed for %s", student_id)
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=win)
            return
        win.destroy()
        gui.status_var.set(f"{student_id} is now {new}")
        then = after or (lambda: open_directory(gui))
        if student.status == "Left":
            if enrol_panel.offer_reinstate_enrolment(
                    gui, student_id, student.full_name, then):
                return
            messagebox.showinfo(
                "Reinstated",
                f"{student.full_name} is back on roll as {new}. Their login and "
                "tutor group have been restored where possible.\n\n"
                "Add this year's enrolment under Enrolment.", parent=gui.root)
        then()

    buttons = ttk.Frame(body)
    buttons.grid(row=4, column=0, columnspan=2, sticky="w")
    ttk.Button(buttons, text="Save", command=save).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="left")
    win.grab_set()


def _bulk_status_dialog(gui, student_ids: list[str],
                        after: Callable[[], None] | None = None) -> None:
    """One status change for several learners, each through the same
    route as a single change (leaving and reinstating keep their side
    effects); failures are listed rather than stopping the rest."""
    if not _can_manage(gui):
        return
    from education_system.systems.sixth_form.domain.learners.alumni.models import (
        LEAVING_REASONS,
    )
    win = make_toplevel(gui.root)
    win.title(f"Change status — {len(student_ids)} students")
    win.transient(gui.root)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=f"{len(student_ids)} selected student(s)",
              font=("", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                          sticky="w", pady=(0, 8))
    status_var = tk.StringVar(value=data.DEFAULT_STATUS)
    reason_var = tk.StringVar()
    ttk.Label(body, text="New status").grid(row=1, column=0, sticky="e", padx=(0, 8))
    ttk.Combobox(body, textvariable=status_var, values=list(data.STATUSES),
                 state="readonly", width=14).grid(row=1, column=1, sticky="w")
    ttk.Label(body, text="Reason").grid(row=2, column=0, sticky="e", padx=(0, 8),
                                        pady=6)
    ttk.Combobox(body, textvariable=reason_var, width=42,
                 values=[r for r in LEAVING_REASONS if r != "Transferred Out"]
                 ).grid(row=2, column=1, sticky="w")
    ttk.Label(body, text="Leaving date").grid(row=3, column=0, sticky="e",
                                              padx=(0, 8))
    picker = DatePicker(body, value=_dt.date.today().isoformat())
    picker.grid(row=3, column=1, sticky="w")
    ttk.Label(body, text="ILR withdrawal reason").grid(row=4, column=0, sticky="e",
                                                       padx=(0, 8), pady=(6, 0))
    ilr = enrol_panel.IlrReasonField(body, reason_var)
    ilr.combo.grid(row=4, column=1, sticky="w", pady=(6, 0))
    ttk.Label(body, foreground="#777", wraplength=440, text=(
        "A reason is required for Left; the leaving date and ILR reason are "
        "used only then (open enrolments are withdrawn with it). Learners "
        "already at the chosen status are left alone.")).grid(
        row=5, column=0, columnspan=2, sticky="w", pady=(8, 8))

    def save() -> None:
        new, reason = status_var.get(), reason_var.get().strip()
        if new == "Left" and not reason:
            messagebox.showerror("Reason needed",
                                 "Give a reason for leaving.", parent=win)
            return
        by = _principal(gui).username
        done, failed = 0, []
        for sid in student_ids:
            try:
                st = data.get_student(sid)
                if st is None or st.status == new:
                    continue
                if new == "Left":
                    data.withdraw_student(sid, reason=reason,
                                          leaving_date=picker.get() or None, by=by,
                                          withdrawal_reason=ilr.code)
                else:
                    data.set_status(sid, new, reason=reason or None, by=by)
                done += 1
            except Exception as e:  # reported per learner
                logger.warning("Bulk status change failed for %s: %s", sid, e)
                failed.append(f"{sid}: {e}")
        win.destroy()
        gui.status_var.set(f"Status changed to {new} for {done} student(s)")
        text = f"{done} student(s) now {new}."
        if failed:
            text += "\n\nNot changed:\n" + "\n".join(failed[:15])
            if len(failed) > 15:
                text += f"\n… and {len(failed) - 15} more"
        messagebox.showinfo("Status changed", text, parent=gui.root)
        (after or (lambda: open_directory(gui)))()

    buttons = ttk.Frame(body)
    buttons.grid(row=6, column=0, columnspan=2, sticky="w")
    ttk.Button(buttons, text="Apply", command=save).pack(side="left", padx=(0, 8))
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="left")
    win.grab_set()


def _mark_left_dialog(gui, student_id: str,
                      after: Callable[[], None] | None = None) -> None:
    if not _can_manage(gui):
        return
    student = data.get_student(student_id)
    if student is None:
        return
    from education_system.systems.sixth_form.domain.learners.alumni.models import (
        LEAVING_REASONS,
    )
    win = make_toplevel(gui.root)
    win.title(f"Mark as left — {student.full_name}")
    win.transient(gui.root)
    body = ttk.Frame(win, padding=12)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text=f"{student.full_name} ({student.student_id})",
              font=("", 11, "bold")).grid(row=0, column=0, columnspan=2,
                                          sticky="w", pady=(0, 8))
    reasons = [r for r in LEAVING_REASONS if r != "Transferred Out"]
    reason_var = tk.StringVar(value="Withdrew")
    detail_var = tk.StringVar()
    ttk.Label(body, text="Reason").grid(row=1, column=0, sticky="e", padx=(0, 8))
    ttk.Combobox(body, textvariable=reason_var, values=reasons, state="readonly",
                 width=22).grid(row=1, column=1, sticky="w")
    ttk.Label(body, text="Details").grid(row=2, column=0, sticky="e", padx=(0, 8),
                                         pady=6)
    ttk.Entry(body, textvariable=detail_var, width=44).grid(row=2, column=1,
                                                            sticky="w")
    ttk.Label(body, text="Leaving date").grid(row=3, column=0, sticky="e",
                                              padx=(0, 8))
    picker = DatePicker(body, value=_dt.date.today().isoformat())
    picker.grid(row=3, column=1, sticky="w")
    ttk.Label(body, text="ILR withdrawal reason").grid(row=4, column=0, sticky="e",
                                                       padx=(0, 8), pady=(6, 0))
    ilr = enrol_panel.IlrReasonField(body, reason_var)
    ilr.combo.grid(row=4, column=1, sticky="w", pady=(6, 0))
    alumni_var = tk.BooleanVar(value=_principal(gui).can_open("Alumni"))
    alumni_cb = ttk.Checkbutton(body, text="Also add them to Alumni",
                                variable=alumni_var)
    alumni_cb.grid(row=5, column=1, sticky="w", pady=(6, 0))
    if not _principal(gui).can_open("Alumni"):
        alumni_cb.state(["disabled"])
    ttk.Label(body, foreground="#777", wraplength=480, text=(
        "Every record is kept. Open enrolments become Withdrawn with the ILR "
        "reason (their learning aims end on the leaving date) — a Year 13 "
        "leaving in the summer term is completed instead — they leave their "
        "tutor group, and their sixth form login is closed. Learners moving "
        "on to the university or an FE college go through Promote to Next "
        "System instead.")).grid(row=6, column=0, columnspan=2,
                                 sticky="w", pady=(8, 8))

    def save() -> None:
        reason = reason_var.get().strip()
        detail = detail_var.get().strip()
        full = f"{reason}: {detail}" if detail else reason
        leaving_date = picker.get() or None
        if not ilr.code:
            messagebox.showerror("Reason needed", "Pick the ILR withdrawal "
                                 "reason.", parent=win)
            return
        since = enrol_panel.history_marker(student_id)
        try:
            data.withdraw_student(student_id, reason=full,
                                  leaving_date=leaving_date,
                                  by=_principal(gui).username,
                                  withdrawal_reason=ilr.code,
                                  withdrawal_detail=detail or None)
        except (data.ValidationError, access.AccessDenied) as e:
            messagebox.showerror("Cannot mark as left", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("Withdraw failed for %s", student_id)
            messagebox.showerror("Error", f"Unexpected error: {e}", parent=win)
            return
        note = ""
        if alumni_var.get():
            try:
                from education_system.systems.sixth_form.domain.learners.alumni import (
                    linking as alumni_linking,
                )
                alumni_linking.archive_student_enriched(
                    student_id, leaving_date=leaving_date, leaving_reason=reason)
                note = "\n\nAdded to Alumni."
            except Exception as e:
                logger.exception("Alumni archive failed for %s", student_id)
                note = f"\n\nCould not add them to Alumni: {e}"
        win.destroy()
        gui.status_var.set(f"{student_id} marked as left")
        outcome = enrol_panel.leaving_outcome(student_id, since)
        done = ("\n\nWhat happened:\n" + "\n".join(f"  • {x}" for x in outcome)
                if outcome else "\n\nThey had no open enrolments.")
        show = (messagebox.showwarning if any(x.startswith("Problem")
                                              for x in outcome)
                else messagebox.showinfo)
        show("Marked as left", f"{student.full_name} is now recorded as Left."
             + done + note, parent=gui.root)
        (after or (lambda: open_directory(gui)))()

    buttons = ttk.Frame(body)
    buttons.grid(row=7, column=0, columnspan=2, sticky="w")
    ttk.Button(buttons, text="Mark as Left", command=save).pack(side="left",
                                                                padx=(0, 8))
    ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="left")
    win.grab_set()


def _delete_with_confirm(gui, student_id: str,
                         after: Callable[[], None] | None = None) -> None:
    if not _can_manage(gui):
        return
    student = data.get_student(student_id)
    if student is None:
        logger.warning("GUI delete: no student with id %s", student_id)
        messagebox.showerror(
            "Not found", f"No student with id {student_id}", parent=gui.root)
        return
    counts = data.linked_record_counts(student_id)
    if counts:
        # Deleting would cascade through every feature's records. Offer
        # the route that keeps them.
        lines = data.describe_linked_records(counts)
        shown = "\n".join("  • " + x for x in lines[:12])
        if len(lines) > 12:
            shown += f"\n  … and {len(lines) - 12} more"
        if student.status == "Left":
            messagebox.showinfo(
                "Cannot delete",
                f"{student.full_name} ({student.student_id}) has records that "
                f"deleting would destroy:\n\n{shown}\n\nThey are already "
                "recorded as Left, which keeps their history.", parent=gui.root)
            return
        if messagebox.askyesno(
                "Cannot delete — mark as left instead?",
                f"{student.full_name} ({student.student_id}) has records that "
                f"deleting would destroy:\n\n{shown}\n\nDelete is only for a "
                "record entered by mistake. Mark them as left instead? Their "
                "records are kept.", parent=gui.root):
            _mark_left_dialog(gui, student_id, after)
        return
    ok = messagebox.askyesno(
        "Delete student",
        f"Permanently delete {student.full_name} ({student.student_id})?\n\n"
        "They have no attendance, enrolment or other records, so this is "
        "treated as a record entered by mistake.",
        parent=gui.root,
    )
    if not ok:
        logger.debug("GUI delete cancelled for %s", student_id)
        return
    try:
        deleted = data.delete_student(student_id)
    except data.StudentHasRecords as e:
        messagebox.showerror("Cannot delete", str(e), parent=gui.root)
        return
    except Exception as e:
        logger.exception("GUI delete failed for %s", student_id)
        messagebox.showerror("Error", f"Could not delete student: {e}",
                             parent=gui.root)
        return
    if deleted:
        gui.status_var.set(f"Deleted {student_id}")
        (after or (lambda: open_directory(gui)))()
    else:
        messagebox.showerror(
            "Error", "Could not delete student.", parent=gui.root)
