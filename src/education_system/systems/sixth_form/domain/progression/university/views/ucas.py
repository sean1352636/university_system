"""GUI panels for Sixth Form UCAS Applications.

Three tabs:

* Directory  — filterable list of applications, one row per student.
* Application — detail view: app metadata + up to 5 choices, with
  inline add / edit / delete buttons for choices.
* Summary    — cycle stats (status / decision counts).
"""

from __future__ import annotations
from education_system.systems.sixth_form.interfaces.gui._ui import grab_when_viewable

import calendar
import logging
import re
import tkinter as tk
from datetime import date as _date
from tkinter import messagebox, ttk
from typing import Any, Callable
from education_system.systems.sixth_form.domain.learners.students import students as student_data
from education_system.systems.sixth_form.domain.progression import destination_courses
from education_system.systems.sixth_form.domain.progression import university_handover
from education_system.systems.sixth_form.domain.progression.university import ucas as data
from education_system.systems.sixth_form.domain.progression.university.ucas import (
    APP_STATUSES,
    Application,
    Choice,
    DECISION_STATUSES,
    DEFAULT_DECISION_STATUS,
    FINAL_DECISIONS,
    MAX_CHOICES,
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


def _default_cycle_year() -> int:
    today = _date.today()
    # UCAS cycle is the *entry* year; applications open Sept of the
    # previous year. Default to next year's entry from Sept onwards.
    return today.year + 1 if today.month >= 9 else today.year


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class _DateField:
    """A date as three dropdowns rather than a typed ``YYYY-MM-DD``.

    Typing the format by hand is how a submission date ends up as
    ``12/09/2026`` or ``2026-9-1``, both of which the data layer rejects
    with a message about a format the person typing was never shown. A
    year / month / day picker cannot produce either, and cannot produce
    31 February: the day list is rebuilt from the chosen month, and from
    the chosen year, so that February is 29 days long exactly when it
    should be.

    A blank date is a real value here — an unsubmitted application has
    no submission date — so all three dropdowns carry an empty option
    and :meth:`get` returns ``""`` when all three are empty. Only a
    *half*-picked date is an error, and it is reported as one.

    Drops into the surrounding ``row()`` grid helpers because it forwards
    ``grid``/``pack`` to its own frame.
    """

    def __init__(self, parent, *, initial: str | None = None,
                 years_back: int = 6, years_forward: int = 2) -> None:
        today = _date.today()
        self.frame = ttk.Frame(parent)

        years = [str(y) for y in range(today.year - years_back,
                                        today.year + years_forward + 1)]
        # A date already on the record stays selectable even when it falls
        # outside the window offered — otherwise merely opening the dialog
        # would blank a date nobody meant to touch.
        parsed = self._parse(initial)
        if parsed is not None and parsed[0] not in years:
            years = sorted({*years, parsed[0]})

        self.year_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.day_var = tk.StringVar()

        self.year_box = ttk.Combobox(
            self.frame, textvariable=self.year_var,
            values=["", *years], state="readonly", width=6)
        self.month_box = ttk.Combobox(
            self.frame, textvariable=self.month_var,
            values=["", *(f"{m:02d}" for m in range(1, 13))],
            state="readonly", width=4)
        self.day_box = ttk.Combobox(
            self.frame, textvariable=self.day_var,
            values=[""], state="readonly", width=4)

        self.year_box.pack(side="left")
        ttk.Label(self.frame, text="-").pack(side="left", padx=1)
        self.month_box.pack(side="left")
        ttk.Label(self.frame, text="-").pack(side="left", padx=1)
        self.day_box.pack(side="left")
        ttk.Button(self.frame, text="Today", width=7,
                    command=self.set_today).pack(side="left", padx=(8, 0))
        ttk.Button(self.frame, text="Clear", width=7,
                    command=self.clear).pack(side="left", padx=(2, 0))

        self.year_var.trace_add("write", self._sync_days)
        self.month_var.trace_add("write", self._sync_days)
        self._sync_days()
        self.set(initial)

    # ── Layout passthrough ──
    def grid(self, **kw):
        self.frame.grid(**kw)
        return self.frame

    def pack(self, **kw):
        self.frame.pack(**kw)
        return self.frame

    # ── Value ──
    @staticmethod
    def _parse(value: str | None) -> tuple[str, str, str] | None:
        m = _DATE_RE.match((value or "").strip())
        return (m.group(1), m.group(2), m.group(3)) if m else None

    def _sync_days(self, *_args) -> None:
        try:
            month = int(self.month_var.get())
        except ValueError:
            last = 31
        else:
            try:
                year = int(self.year_var.get())
            except ValueError:
                # Year not picked yet: offer the leap-year length so a
                # 29 February selection isn't blocked by the order the
                # two dropdowns happen to be used in.
                year = 2024
            last = calendar.monthrange(year, month)[1]
        self.day_box.configure(
            values=["", *(f"{d:02d}" for d in range(1, last + 1))])
        current = self.day_var.get()
        if current and int(current) > last:
            self.day_var.set(f"{last:02d}")

    def set(self, value: str | None) -> None:
        parsed = self._parse(value)
        if parsed is None:
            self.clear()
            return
        year, month, day = parsed
        self.year_var.set(year)
        self.month_var.set(month)
        self.day_var.set(day)
        # The day is set last, after the traces that rebuild the day list
        # have already fired, so re-run the clamp explicitly. Otherwise a
        # stored impossible date — 29 February in a non-leap year, which
        # the data layer's format check happily stores — would be offered
        # back unchanged and saved again.
        self._sync_days()

    def clear(self) -> None:
        self.year_var.set("")
        self.month_var.set("")
        self.day_var.set("")

    def set_today(self) -> None:
        self.set(_date.today().isoformat())

    def get(self) -> str:
        """``YYYY-MM-DD``, or ``""`` when no date is picked.

        Raises :class:`ValueError` for a half-picked date, which is the
        one combination the dropdowns can still produce and the data
        layer cannot store.
        """
        parts = (self.year_var.get(), self.month_var.get(),
                 self.day_var.get())
        if not any(parts):
            return ""
        if not all(parts):
            raise ValueError(
                "Pick a year, a month and a day — or use Clear to leave "
                "the date blank.")
        return "-".join(parts)

    def trace_add(self, callback) -> None:
        """Run *callback* whenever any part of the date changes."""
        for var in (self.year_var, self.month_var, self.day_var):
            var.trace_add("write", lambda *_a: callback())


def _status_hint(submitted_at: str) -> str:
    """What the derived status will be, said in the dialog that decides it.

    The status dropdown is gone: an application is a Draft until it has a
    submission date and Submitted once it has one. That rule is invisible
    unless the screen says so, and a person who has just removed a date
    should not have to save to find out what it did.
    """
    if submitted_at:
        return ("Status: Submitted — the student is emailed a "
                "confirmation when this is saved.")
    return ("Status: Draft — pick a submission date above to mark this "
            "application Submitted.")


# ── Top-level tabbed view ───────────────────────────────────────────

def open_directory(gui) -> None:
    frame = _clear(gui)
    _heading(frame, "UCAS Applications")

    nb = ttk.Notebook(frame)
    nb.pack(fill="both", expand=True)

    dir_tab = ttk.Frame(nb, padding=8)
    detail_tab = ttk.Frame(nb, padding=8)
    summary_tab = ttk.Frame(nb, padding=8)
    nb.add(dir_tab,     text="Directory")
    nb.add(detail_tab,  text="Application")
    nb.add(summary_tab, text="Summary")

    _build_directory_tab(gui, dir_tab)
    _build_detail_tab(gui, detail_tab)
    _build_summary_tab(gui, summary_tab)


# ─── Directory tab ──────────────────────────────────────────────────

def _build_directory_tab(gui, parent: ttk.Frame) -> None:
    filt = ttk.Frame(parent)
    filt.pack(anchor="w", fill="x", pady=(0, 8))

    sid_var = tk.StringVar()
    cycle_var = tk.StringVar()
    status_var = tk.StringVar()

    ttk.Label(filt, text="Student ID:").pack(side="left")
    ttk.Entry(filt, textvariable=sid_var, width=12
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Cycle year:").pack(side="left")
    ttk.Entry(filt, textvariable=cycle_var, width=6
              ).pack(side="left", padx=(4, 12))
    ttk.Label(filt, text="Status:").pack(side="left")
    ttk.Combobox(filt, textvariable=status_var,
                 values=["", *APP_STATUSES], state="readonly", width=12
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
            yr = int(cycle_var.get()) if cycle_var.get().strip() else None
        except ValueError:
            messagebox.showerror("Bad filter",
                                 "Cycle year must be a number.",
                                 parent=gui.root)
            return
        try:
            rows = data.list_applications_with_detail(
                student_id=sid_var.get().strip() or None,
                cycle_year=yr,
                status=status_var.get().strip() or None,
            )
        except ValidationError as e:
            ttk.Label(table_holder, text=str(e),
                      foreground="#a33").pack(anchor="w")
            return

        cols = ("application_id", "student", "name", "cycle",
                "status", "ucas_id", "submitted", "choices", "final")
        headings = {
            "application_id": ("#",        50),
            "student":        ("Student", 100),
            "name":            ("Name",   200),
            "cycle":          ("Cycle",    60),
            "status":         ("Status",   90),
            "ucas_id":        ("UCAS ID",  90),
            "submitted":      ("Submitted", 100),
            "choices":        ("Choices",   60),
            "final":          ("F / I",     80),
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

        for row in rows:
            a = row.application
            final = []
            if row.has_firm:
                final.append("F")
            if row.has_insurance:
                final.append("I")
            tree.insert("", "end", iid=str(a.application_id), values=(
                a.application_id, a.student_id, row.student_name,
                a.cycle_year, a.status,
                a.ucas_id or "—",
                a.submitted_at or "—",
                row.n_choices,
                "/".join(final) or "—",
            ))
        summary.configure(text=f"{len(rows)} application(s).")

        def _selected() -> int | None:
            sel = tree.selection()
            return int(sel[0]) if sel else None

        def _require() -> int | None:
            aid = _selected()
            if aid is None:
                messagebox.showinfo("No selection",
                                    "Pick an application first.",
                                    parent=gui.root)
            return aid

        def _open() -> None:
            aid = _require()
            if aid is None:
                return
            open_application(gui, aid)

        def _delete() -> None:
            aid = _require()
            if aid is None:
                return
            a = data.get_application(aid)
            if a is None:
                return
            if not messagebox.askyesno(
                "Delete application",
                f"Delete application #{aid} ({a.student_id}, "
                f"cycle {a.cycle_year})? All {len(data.list_choices(aid))} "
                "choice(s) will go with it.",
                parent=gui.root,
            ):
                return
            try:
                data.delete_application(aid)
            except Exception as e:
                logger.exception("delete_application crashed")
                messagebox.showerror("Error", f"Could not delete: {e}",
                                     parent=gui.root)
                return
            refresh()

        ttk.Button(actions_holder, text="Open",
                   command=_open).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="Delete",
                   command=_delete).pack(side="left", padx=(0, 6))
        ttk.Button(actions_holder, text="New",
                   command=lambda: open_new_application(gui)
                   ).pack(side="left", padx=(12, 6))
        ttk.Button(actions_holder, text="Refresh",
                   command=refresh).pack(side="left")
        tree.bind("<Double-1>", lambda _e: _open())
        gui.status_var.set(f"UCAS apps: {len(rows)} match(es)")

    ttk.Button(filt, text="Apply", command=refresh
               ).pack(side="left", padx=(8, 0))
    ttk.Button(filt, text="Clear",
               command=lambda: (sid_var.set(""), cycle_var.set(""),
                                status_var.set(""), refresh())
               ).pack(side="left", padx=(4, 0))
    refresh()


def open_new_application(gui) -> None:
    students = student_data.list_students()
    if not students:
        messagebox.showinfo("No students",
                            "Add a student first.", parent=gui.root)
        return

    win = tk.Toplevel(gui.root)
    win.title("New UCAS Application")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    student_labels = [f"{s.student_id} — {s.full_name}" for s in students]
    student_by_label = {f"{s.student_id} — {s.full_name}": s.student_id
                        for s in students}
    student_var = tk.StringVar(value=student_labels[0])
    cycle_var = tk.StringVar(value=str(_default_cycle_year()))
    ucas_var = tk.StringVar()
    notes_var = tk.StringVar()

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Student:", ttk.Combobox(frm, textvariable=student_var,
                                     values=student_labels,
                                     state="readonly", width=42))
    row(1, "Cycle year:", ttk.Entry(frm, textvariable=cycle_var, width=8))

    # A student gets one application per cycle. That is enforced by a
    # UNIQUE index, which used to announce itself only on Save — after
    # the personal statement had been typed — as an error with nowhere to
    # go. Say it while the cycle year can still be changed, and say which
    # application is in the way.
    clash_label = ttk.Label(frm, text="", wraplength=420, justify="left")
    clash_label.grid(row=2, column=1, sticky="w", pady=(0, 4))

    def _refresh_clash(*_args) -> None:
        sid = student_by_label.get(student_var.get())
        if not sid:
            clash_label.configure(text="")
            return
        try:
            existing = data.list_applications(student_id=sid)
        except Exception:
            logger.debug("Could not list existing applications",
                         exc_info=True)
            clash_label.configure(text="")
            return
        if not existing:
            clash_label.configure(text="No UCAS application on file yet.",
                                  foreground="#777")
            return
        clash = next((a for a in existing
                      if str(a.cycle_year) == cycle_var.get().strip()), None)
        if clash is not None:
            clash_label.configure(
                text=f"{sid} already has a cycle {clash.cycle_year} "
                     f"application (#{clash.application_id}, "
                     f"{clash.status}). Change the cycle year, or Save to "
                     "open that one instead.",
                foreground="#a33")
            return
        clash_label.configure(
            text="Already on file: "
                 + ", ".join(f"cycle {a.cycle_year} (#{a.application_id})"
                             for a in existing),
            foreground="#777")

    student_var.trace_add("write", _refresh_clash)
    cycle_var.trace_add("write", _refresh_clash)
    _refresh_clash()

    row(3, "UCAS personal ID (10 digits):",
        ttk.Entry(frm, textvariable=ucas_var, width=16))

    submitted_field = _DateField(frm)
    row(4, "Submitted at:", submitted_field)

    # No status picker: the status *is* whether a submission date is set,
    # and asking somebody to keep the two consistent by hand is asking
    # them to file Draft applications dated last Tuesday.
    status_label = ttk.Label(frm, text="", foreground="#555")
    status_label.grid(row=5, column=1, sticky="w", pady=(0, 4))

    def _refresh_status_label() -> None:
        try:
            status_label.configure(text=_status_hint(submitted_field.get()))
        except ValueError as e:
            status_label.configure(text=str(e))

    submitted_field.trace_add(_refresh_status_label)
    _refresh_status_label()

    row(6, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    # The personal statement, on the screen that creates the application.
    # It used to exist only behind an Edit personal statement button on a
    # view you could not reach until after saving, so the one field UCAS
    # actually weighs was the one field this dialog never asked for.
    ttk.Label(frm, text="Personal statement:").grid(
        row=7, column=0, sticky="ne", padx=(0, 6), pady=(8, 2))
    ps_text = tk.Text(frm, width=60, height=10, wrap="word")
    ps_text.grid(row=7, column=1, sticky="w", pady=(8, 2))
    ttk.Label(frm, text="Optional now — it can be written or revised later.",
              foreground="#777").grid(row=8, column=1, sticky="w")

    def save() -> None:
        sid = student_by_label.get(student_var.get())
        if not sid:
            messagebox.showerror("Cannot save",
                                 "Pick a student.", parent=win)
            return

        # Caught here rather than left to the UNIQUE index, so the answer
        # is an offer to open the application that already exists instead
        # of an error that ends the task. Still only an offer: the reason
        # for a second one is usually a mistyped cycle year, and that is
        # fixed in this dialog, not the other one.
        clash = _existing_application(sid, cycle_var.get())
        if clash is not None:
            typed_ps = bool(ps_text.get("1.0", "end").strip())
            if messagebox.askyesno(
                "Application already exists",
                f"{sid} already has an application for cycle "
                f"{clash.cycle_year} — #{clash.application_id}, "
                f"{clash.status}.\n\n"
                "Open that application instead?"
                + ("\n\nAnything typed here, including the personal "
                   "statement, will not be carried over." if typed_ps
                   else "")
                + "\n\nChoose No to stay here and change the cycle year.",
                parent=win,
            ):
                win.destroy()
                open_application(gui, clash.application_id)
            return

        try:
            submitted = submitted_field.get()
        except ValueError as e:
            messagebox.showwarning("Submission date", str(e), parent=win)
            return
        try:
            a = data.create_application({
                "student_id":         sid,
                "cycle_year":         cycle_var.get(),
                "ucas_id":            ucas_var.get(),
                "status":             data.derive_status(None, submitted),
                "submitted_at":       submitted,
                "personal_statement": ps_text.get("1.0", "end").strip(),
                "notes":              notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("create_application crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        # Created straight into Submitted — the student is told, exactly
        # as they would be had it been submitted from the detail view.
        _announce_submission(gui, a, previous_status=None)
        open_application(gui, a.application_id)

    bar = ttk.Frame(frm)
    bar.grid(row=9, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _existing_application(student_id: str, cycle_year: str):
    """The application already occupying (student, cycle), if any.

    Returns ``None`` for an unparseable cycle year as well as for a free
    slot: a year that is not a number cannot collide with anything, and
    the data layer gives a better message about it than this would.
    """
    try:
        year = int(str(cycle_year).strip())
    except (TypeError, ValueError):
        return None
    try:
        return data.get_application_for_student(student_id, cycle_year=year)
    except Exception:
        logger.debug("Could not check for an existing application",
                     exc_info=True)
        return None


def _announce_submission(gui, application, *,
                         previous_status: str | None) -> None:
    """Email the student iff this save is what submitted the application.

    Guarded on the *transition* rather than on the current status, so
    editing a submitted application's notes does not re-send the
    confirmation every time somebody clicks Save.
    """
    if application.status != "Submitted" or previous_status == "Submitted":
        return
    from education_system.systems.sixth_form.domain.progression.university import submission_notice
    msg = submission_notice.send_submission_email(application)
    if msg is None:
        # send_submission_email never raises and logs the reason; the
        # submission is saved either way, so this is a notice, not an
        # error the user has to resolve.
        gui.status_var.set(
            f"Application #{application.application_id} submitted "
            "(confirmation email could not be sent — see the log)")
        return
    gui.status_var.set(
        f"Application #{application.application_id} submitted — "
        "confirmation emailed to the student")


# ─── Application detail tab + standalone view ──────────────────────

def _build_detail_tab(gui, parent: ttk.Frame) -> None:
    apps = data.list_applications_with_detail()
    labels = [
        f"#{r.application.application_id}  {r.application.student_id}  "
        f"{r.student_name}  (cycle {r.application.cycle_year}, "
        f"{r.application.status})"
        for r in apps
    ]
    by_label = {lbl: r.application.application_id
                for lbl, r in zip(labels, apps)}

    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))
    app_var = tk.StringVar(value=labels[0] if labels else "")
    ttk.Label(bar, text="Application:").pack(side="left")
    ttk.Combobox(bar, textvariable=app_var, values=labels,
                 state="readonly", width=64
                 ).pack(side="left", padx=(4, 4))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        aid = by_label.get(app_var.get())
        if aid is None:
            ttk.Label(holder, text="Pick an application.",
                      foreground="#a33").pack(anchor="w")
            return
        _render_application_detail(gui, holder, aid, on_changed=render)

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    if labels:
        render()
    else:
        ttk.Label(holder, text="No applications yet.",
                  foreground="#a33").pack(anchor="w")


def open_application(gui, application_id: int) -> None:
    """Standalone view: full-page application detail."""
    frame = _clear(gui)
    _heading(frame, f"UCAS Application #{application_id}")
    holder = ttk.Frame(frame)
    holder.pack(fill="both", expand=True)
    _render_application_detail(gui, holder, application_id,
                               on_changed=lambda: open_application(
                                   gui, application_id))
    ttk.Button(frame, text="Back to UCAS Applications",
               command=lambda: open_directory(gui)
               ).pack(anchor="w", pady=(12, 0))


def _render_application_detail(gui, parent: ttk.Frame,
                               application_id: int,
                               *, on_changed: Callable[[], None]) -> None:
    a = data.get_application(application_id)
    if a is None:
        ttk.Label(parent, text="No such application.",
                  foreground="#a33").pack(anchor="w")
        return

    student = student_data.get_student(a.student_id)

    # Header — student + app metadata
    meta = ttk.Frame(parent)
    meta.pack(anchor="w", fill="x", pady=(0, 8))

    def field(row: int, label: str, value: str) -> None:
        ttk.Label(meta, text=label + ":", foreground="#555",
                  width=22, anchor="e").grid(row=row, column=0, sticky="e",
                                              pady=2, padx=(0, 8))
        ttk.Label(meta, text=value or "—").grid(
            row=row, column=1, sticky="w", pady=2)

    field(0, "Student",
          f"{a.student_id} — {student.full_name if student else '(deleted)'}")
    field(1, "Cycle year", str(a.cycle_year))
    field(2, "UCAS personal ID", a.ucas_id or "—")
    field(3, "Status", a.status)
    field(4, "Submitted", a.submitted_at or "—")
    field(5, "Created", a.created_at)
    field(6, "Last updated", a.updated_at)
    # Shown whether or not there is one. A personal statement that is
    # simply absent from the page reads as a field this system does not
    # have, which is how applications reached submission without one.
    ttk.Separator(meta, orient="horizontal").grid(
        row=7, column=0, columnspan=2, sticky="ew", pady=(10, 6))
    ttk.Label(meta, text="Personal statement:", foreground="#555",
              width=22, anchor="ne").grid(row=8, column=0, sticky="ne",
                                           padx=(0, 8))
    ttk.Label(meta,
              text=(a.personal_statement
                    or "(not written yet — use Edit personal statement)"),
              foreground=("" if a.personal_statement else "#a33"),
              wraplength=520, justify="left").grid(
        row=8, column=1, sticky="w")
    if a.notes:
        ttk.Label(meta, text="Notes:", foreground="#555",
                  width=22, anchor="ne").grid(row=9, column=0, sticky="ne",
                                               padx=(0, 8), pady=(6, 0))
        ttk.Label(meta, text=a.notes, wraplength=520,
                  justify="left").grid(row=9, column=1, sticky="w",
                                       pady=(6, 0))

    app_actions = ttk.Frame(parent)
    app_actions.pack(anchor="w", pady=(0, 12))
    ttk.Button(app_actions, text="Edit application",
               command=lambda: _edit_application_dialog(
                   gui, a.application_id, on_saved=on_changed)
               ).pack(side="left", padx=(0, 6))
    ttk.Button(app_actions, text="Edit personal statement",
               command=lambda: _edit_ps_dialog(
                   gui, a.application_id, on_saved=on_changed)
               ).pack(side="left", padx=(0, 6))
    if a.status == "Draft":
        ttk.Button(app_actions, text="Submit application",
                   command=lambda: _submit_application(
                       gui, a.application_id, on_saved=on_changed)
                   ).pack(side="left", padx=(12, 6))
    elif a.status not in ("Confirmed", "Clearing"):
        # Confirmed and Clearing are the university's to set, alongside
        # the decision and the reply. A college marking a place confirmed
        # could confirm one no university had given — and this status is
        # what releases the handover, so it would release it on nothing.
        ttk.Label(app_actions,
                  text="Confirmed / Clearing are recorded by the "
                       "university, in its own UCAS screen.",
                  foreground="#777").pack(side="left", padx=(12, 0))

    # ── Choices section ──
    choices_section = ttk.LabelFrame(parent, text="Choices (max 5)",
                                      padding=8)
    choices_section.pack(fill="both", expand=True, pady=(8, 0))

    # The action bar sits above the table. It used to sit under it, which
    # on a five-row table with the application metadata stacked overhead
    # meant scrolling past everything on the page to add a choice.
    choice_actions = ttk.Frame(choices_section)
    choice_actions.pack(side="top", anchor="w", fill="x", pady=(0, 6))

    choices = data.list_choices(application_id)

    cols = ("choice_id", "slot", "university", "course_code",
            "course_name", "entry_year", "decision_status",
            "offer_terms", "final_decision")
    headings = {
        "choice_id":       ("#",        50),
        "slot":            ("Slot",     50),
        "university":      ("University", 180),
        "course_code":     ("Code",      80),
        "course_name":     ("Course",   180),
        "entry_year":      ("Year",     60),
        "decision_status": ("Status",  140),
        "offer_terms":     ("Terms",   140),
        "final_decision":  ("Final",   100),
    }
    tree = ttk.Treeview(choices_section, columns=cols,
                        show="headings", height=6)
    for col in cols:
        text, width = headings[col]
        tree.heading(col, text=text)
        tree.column(col, width=width, anchor="w")
    vs = ttk.Scrollbar(choices_section, orient="vertical",
                        command=tree.yview)
    tree.configure(yscrollcommand=vs.set)
    tree.pack(side="left", fill="both", expand=True)
    vs.pack(side="right", fill="y")

    for c in choices:
        tree.insert("", "end", iid=str(c.choice_id), values=(
            c.choice_id, c.choice_order, c.university,
            c.course_code or "—", c.course_name,
            c.entry_year if c.entry_year is not None else "—",
            c.decision_status,
            c.offer_terms or "—",
            c.final_decision or "—",
        ))

    def _selected() -> int | None:
        sel = tree.selection()
        return int(sel[0]) if sel else None

    def _add() -> None:
        if len(data.list_choices(application_id)) >= MAX_CHOICES:
            messagebox.showinfo(
                "At capacity",
                f"This application already has {MAX_CHOICES} choices.",
                parent=gui.root,
            )
            return
        _edit_choice_dialog(gui, application_id, choice_id=None,
                            on_saved=on_changed)

    def _edit() -> None:
        cid = _selected()
        if cid is None:
            messagebox.showinfo("No selection",
                                "Pick a choice first.", parent=gui.root)
            return
        _edit_choice_dialog(gui, application_id, choice_id=cid,
                            on_saved=on_changed)

    def _delete() -> None:
        cid = _selected()
        if cid is None:
            messagebox.showinfo("No selection",
                                "Pick a choice first.", parent=gui.root)
            return
        c = data.get_choice(cid)
        if c is None:
            return
        if not messagebox.askyesno(
            "Delete choice",
            f"Delete slot {c.choice_order}: {c.university} — {c.course_name}?",
            parent=gui.root,
        ):
            return
        try:
            data.delete_choice(cid)
        except Exception as e:
            logger.exception("delete_choice crashed")
            messagebox.showerror("Error", f"Could not delete: {e}",
                                 parent=gui.root)
            return
        on_changed()

    ttk.Button(choice_actions, text="Add choice",
               command=_add).pack(side="left", padx=(0, 6))
    ttk.Button(choice_actions, text="Edit choice",
               command=_edit).pack(side="left", padx=(0, 6))
    ttk.Button(choice_actions, text="Delete choice",
               command=_delete).pack(side="left", padx=(0, 6))
    tree.bind("<Double-1>", lambda _e: _edit())

    gui.status_var.set(f"UCAS application #{application_id} loaded")


def _submit_application(gui, application_id: int, *, on_saved) -> None:
    """Move a Draft application to Submitted and tell the student.

    Submitting is one deliberate action rather than a status somebody
    picks out of a list, because it is the point after which the copy on
    the student's screen is the copy universities are reading. It asks
    first, dates the submission today, and emails the confirmation.
    """
    a = data.get_application(application_id)
    if a is None:
        messagebox.showerror("Not found",
                             f"No application #{application_id}",
                             parent=gui.root)
        return
    if a.status != "Draft":
        messagebox.showinfo("Already submitted",
                            f"This application is already {a.status}.",
                            parent=gui.root)
        return

    n_choices = len(data.list_choices(application_id))
    warnings = []
    if not a.personal_statement:
        warnings.append("· It has no personal statement.")
    if not n_choices:
        warnings.append("· It has no choices on it.")
    if not a.ucas_id:
        warnings.append("· It has no UCAS personal ID.")

    today = _date.today().isoformat()
    prompt = (f"Submit application #{application_id} for {a.student_id}?\n\n"
              f"It will be dated {today}, marked Submitted, and the "
              "student will be emailed a confirmation listing "
              f"{n_choices} choice(s).")
    if warnings:
        prompt += "\n\nBefore you do:\n" + "\n".join(warnings)
    if not messagebox.askyesno("Submit application", prompt,
                               parent=gui.root):
        return

    try:
        updated = data.update_application(application_id, {
            "status":       "Submitted",
            "submitted_at": today,
        })
    except ValidationError as e:
        messagebox.showerror("Cannot submit", str(e), parent=gui.root)
        return
    except Exception as e:
        logger.exception("submit application crashed")
        messagebox.showerror("Error", f"Unexpected: {e}", parent=gui.root)
        return

    _announce_submission(gui, updated, previous_status=a.status)
    on_saved()


def _edit_application_dialog(gui, application_id: int, *, on_saved) -> None:
    a = data.get_application(application_id)
    if a is None:
        messagebox.showerror("Not found", f"No application #{application_id}",
                             parent=gui.root)
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit application #{application_id}")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.grid()
    ttk.Label(frm, text=f"Student: {a.student_id}",
              foreground="#555").grid(row=0, column=0, columnspan=2,
                                       sticky="w", pady=(0, 8))

    cycle_var = tk.StringVar(value=str(a.cycle_year))
    ucas_var = tk.StringVar(value=a.ucas_id or "")
    notes_var = tk.StringVar(value=a.notes or "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(1, "Cycle year:", ttk.Entry(frm, textvariable=cycle_var, width=8))
    row(2, "UCAS ID:", ttk.Entry(frm, textvariable=ucas_var, width=16))

    submitted_field = _DateField(frm, initial=a.submitted_at)
    row(3, "Submitted:", submitted_field)

    # Same rule as the New dialog: the date decides the status. An
    # application already past Submitted (Replied / Confirmed / Clearing)
    # keeps the status the universities put it in — `derive_status` leaves
    # those alone — so the hint says what is really going to happen.
    status_label = ttk.Label(frm, text="", foreground="#555")
    status_label.grid(row=4, column=1, sticky="w", pady=(0, 4))

    def _refresh_status_label() -> None:
        try:
            submitted = submitted_field.get()
        except ValueError as e:
            status_label.configure(text=str(e))
            return
        derived = data.derive_status(a.status, submitted)
        if derived not in data.DERIVED_STATUSES:
            status_label.configure(
                text=f"Status: {derived} — set by the universities' "
                     "replies, not by this date.")
        else:
            status_label.configure(text=_status_hint(submitted))

    submitted_field.trace_add(_refresh_status_label)
    _refresh_status_label()

    row(5, "Notes:", ttk.Entry(frm, textvariable=notes_var, width=42))

    def save() -> None:
        try:
            submitted = submitted_field.get()
        except ValueError as e:
            messagebox.showwarning("Submission date", str(e), parent=win)
            return
        try:
            updated = data.update_application(application_id, {
                "cycle_year":   cycle_var.get(),
                "ucas_id":      ucas_var.get(),
                "status":       data.derive_status(a.status, submitted),
                "submitted_at": submitted,
                "notes":        notes_var.get(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_application crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        _announce_submission(gui, updated, previous_status=a.status)
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=6, column=0, columnspan=2, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _edit_ps_dialog(gui, application_id: int, *, on_saved) -> None:
    a = data.get_application(application_id)
    if a is None:
        return
    win = tk.Toplevel(gui.root)
    win.title(f"Edit personal statement — application #{application_id}")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.grid()
    ttk.Label(frm, text="Personal statement:",
              foreground="#555").grid(row=0, column=0, sticky="w",
                                       pady=(0, 4))
    text = tk.Text(frm, width=70, height=16, wrap="word")
    text.grid(row=1, column=0, sticky="nsew")
    if a.personal_statement:
        text.insert("1.0", a.personal_statement)

    def save() -> None:
        try:
            data.update_application(application_id, {
                "personal_statement": text.get("1.0", "end").strip(),
            })
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("update_application (PS) crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=2, column=0, pady=(10, 0), sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


def _edit_choice_dialog(gui, application_id: int, *,
                         choice_id: int | None,
                         on_saved) -> None:
    existing = data.get_choice(choice_id) if choice_id else None

    win = tk.Toplevel(gui.root)
    win.title("Edit choice" if existing else "Add choice")
    win.transient(gui.root)
    grab_when_viewable(win)
    frm = ttk.Frame(win, padding=12)
    frm.grid()

    # Pre-fill or sensible defaults
    used_slots = {c.choice_order for c in data.list_choices(application_id)
                  if not existing or c.choice_id != existing.choice_id}
    available = [n for n in range(1, MAX_CHOICES + 1) if n not in used_slots]
    if existing:
        # Existing slot stays at the top of the picker
        available = [existing.choice_order] + [
            n for n in available if n != existing.choice_order]

    slot_var = tk.StringVar(
        value=str(existing.choice_order) if existing
              else (str(available[0]) if available else "1"))
    uni_var = tk.StringVar(value=existing.university if existing else "")
    code_var = tk.StringVar(
        value=(existing.course_code or "") if existing else "")
    course_var = tk.StringVar(
        value=existing.course_name if existing else "")
    year_var = tk.StringVar(
        value=(str(existing.entry_year) if existing and existing.entry_year
               else str(_default_cycle_year())))
    decision_var = tk.StringVar(
        value=existing.decision_status if existing else DEFAULT_DECISION_STATUS)
    terms_var = tk.StringVar(
        value=(existing.offer_terms or "") if existing else "")
    notes_var = tk.StringVar(
        value=(existing.notes or "") if existing else "")

    def row(idx, label, w):
        ttk.Label(frm, text=label).grid(row=idx, column=0, sticky="e",
                                         padx=(0, 6), pady=2)
        w.grid(row=idx, column=1, sticky="w", pady=2)

    row(0, "Slot:", ttk.Combobox(frm, textvariable=slot_var,
                                  values=[str(n) for n in available],
                                  state="readonly", width=4))
    row(1, "University:", ttk.Entry(frm, textvariable=uni_var, width=36))

    # A picker for this university's own catalogue, above the free-text
    # fields rather than instead of them. Four of a learner's five choices
    # are at institutions this platform does not run and must still be
    # typed; the one that is *ours* should not be, because a hand-typed
    # code is what makes a handover land on no programme at all.
    #
    # The row is only built when there is a catalogue to show. A sixth form
    # running without the university installed gets the dialog it always
    # had, not a permanently empty dropdown.
    catalogue = destination_courses.home_courses()
    next_row = 2
    if catalogue:
        home_name = destination_courses.home_institution_name()
        pick_var = tk.StringVar(value="")
        picker = ttk.Combobox(
            frm, textvariable=pick_var,
            values=["", *(o.label for o in catalogue)],
            state="readonly", width=36)
        row(next_row,
            f"Course at {home_name}:" if home_name else "Course here:",
            picker)
        next_row += 1

        def _apply_catalogue_choice(_event=None) -> None:
            option = destination_courses.by_label(catalogue, pick_var.get())
            if option is None:
                return
            code_var.set(option.code)
            course_var.set(option.name)
            # A course picked from our catalogue is a choice *here*. Filling
            # a blank institution is the difference between a usable choice
            # and one carrying our course code under nobody's name; an
            # institution already typed is left alone, since overwriting
            # what somebody entered is never the helpful move.
            if home_name and not uni_var.get().strip():
                uni_var.set(home_name)

        picker.bind("<<ComboboxSelected>>", _apply_catalogue_choice)

        # Re-open an existing choice with its course already selected, so
        # the dropdown reflects the record rather than looking unset. Falls
        # back to the course *name* for the rows typed before this picker
        # existed, which often carry a name and no code at all.
        if existing:
            match = destination_courses.resolve(
                catalogue, code=existing.course_code or "",
                name=existing.course_name or "")
            if match is not None:
                pick_var.set(match.label)

    row(next_row, "Course code:",
        ttk.Entry(frm, textvariable=code_var, width=12))
    row(next_row + 1, "Course name:",
        ttk.Entry(frm, textvariable=course_var, width=36))
    row(next_row + 2, "Entry year:",
        ttk.Entry(frm, textvariable=year_var, width=8))
    decision_box = ttk.Combobox(
        frm, textvariable=decision_var, values=list(DECISION_STATUSES),
        state="readonly", width=24)
    row(next_row + 3, "Decision status:", decision_box)
    terms_entry = ttk.Entry(frm, textvariable=terms_var, width=36)
    row(next_row + 4, "Offer terms:", terms_entry)
    # Final decision is *shown* here and set nowhere on this screen. Firm /
    # Insurance / Declined is now recorded against the choice in the
    # university's own UCAS screen, which is where the reply is handled and
    # where the student gets emailed about it. Two places to type it was one
    # place too many: whichever was edited last silently won.
    final_current = (existing.final_decision if existing else None) or "—"
    row(next_row + 5, "Final decision:",
        ttk.Label(frm, text=final_current, foreground="#555"))
    ttk.Label(frm,
              text="Recorded in the university's UCAS screen, not here.",
              foreground="#777", wraplength=320, justify="left").grid(
        row=next_row + 6, column=1, sticky="w")
    row(next_row + 7, "Notes:",
        ttk.Entry(frm, textvariable=notes_var, width=36))

    # The decision on a choice at *our* university is that university's to
    # make: it is written by its admissions team through ``record_decision``
    # and only read here. Locking the two fields is the same rule the data
    # layer enforces, shown before the save rather than after it.
    #
    # Re-evaluated whenever the institution changes, because a choice
    # becomes ours — or stops being ours — by that field being edited.
    # Final decision stays open throughout: Firm / Insurance is the
    # learner's reply, which is the school's to record.
    owned_note = ttk.Label(
        frm, text="", foreground="#555", wraplength=320, justify="left")
    owned_note.grid(row=next_row + 8, column=1, sticky="w", pady=(2, 0))

    def _apply_ownership(*_args) -> None:
        ours = university_handover.is_home_university(uni_var.get())
        if ours:
            # Put back what the university published, so a value typed
            # before the institution was switched onto us is discarded
            # rather than saved and refused.
            decision_var.set(existing.decision_status if existing
                             else DEFAULT_DECISION_STATUS)
            terms_var.set((existing.offer_terms or "") if existing else "")
            decision_box.configure(state="disabled")
            terms_entry.configure(state="readonly")
            owned_note.configure(
                text="Decision and offer terms are set by this "
                     "university's admissions team.")
        else:
            decision_box.configure(state="readonly")
            terms_entry.configure(state="normal")
            owned_note.configure(text="")

    uni_var.trace_add("write", _apply_ownership)
    _apply_ownership()

    buttons_row = next_row + 9

    def save() -> None:
        # Pre-flight: catch empty required fields before they hit the
        # data layer. The data layer would reject these too — but with
        # a stack trace landing in the console because the wrapper
        # logger captures ValidationError as an exception.
        missing: list[str] = []
        if not uni_var.get().strip():
            missing.append("University")
        if not course_var.get().strip():
            missing.append("Course name")
        if missing:
            messagebox.showwarning(
                "Required fields",
                "Please fill in: " + ", ".join(missing),
                parent=win,
            )
            return

        payload = {
            "choice_order":    slot_var.get(),
            "university":      uni_var.get(),
            "course_code":     code_var.get(),
            "course_name":     course_var.get(),
            "entry_year":      year_var.get(),
            "decision_status": decision_var.get(),
            "offer_terms":     terms_var.get(),
            # Carried through untouched. Omitting the key would be the
            # same thing on an update (the data layer falls back to the
            # stored value) but not on a create, where it would have to
            # default — and stating it keeps both paths reading alike.
            "final_decision":  (existing.final_decision
                                if existing else None),
            "notes":           notes_var.get(),
        }
        try:
            if existing:
                data.update_choice(existing.choice_id, payload)
            else:
                data.create_choice(application_id, payload)
        except ValidationError as e:
            messagebox.showerror("Cannot save", str(e), parent=win)
            return
        except Exception as e:
            logger.exception("save choice crashed")
            messagebox.showerror("Error", f"Unexpected: {e}", parent=win)
            return
        win.destroy()
        on_saved()

    bar = ttk.Frame(frm)
    bar.grid(row=buttons_row, column=0, columnspan=2, pady=(10, 0),
             sticky="e")
    ttk.Button(bar, text="Save", command=save).pack(side="left", padx=(0, 6))
    ttk.Button(bar, text="Cancel", command=win.destroy).pack(side="left")


# ─── Summary tab ────────────────────────────────────────────────────

def _build_summary_tab(gui, parent: ttk.Frame) -> None:
    bar = ttk.Frame(parent)
    bar.pack(anchor="w", fill="x", pady=(0, 8))

    cycle_var = tk.StringVar(value=str(_default_cycle_year()))
    ttk.Label(bar, text="Cycle year (blank = all):").pack(side="left")
    ttk.Entry(bar, textvariable=cycle_var, width=6
              ).pack(side="left", padx=(4, 12))

    holder = ttk.Frame(parent)
    holder.pack(fill="both", expand=True)

    def render() -> None:
        for w in holder.winfo_children():
            w.destroy()
        try:
            yr = int(cycle_var.get()) if cycle_var.get().strip() else None
        except ValueError:
            ttk.Label(holder, text="Cycle year must be a number.",
                      foreground="#a33").pack(anchor="w")
            return
        summ = data.cycle_summary(yr)

        ttk.Label(
            holder,
            text=f"Applications: {summ.total_applications}  ·  "
                 f"Choices: {summ.total_choices}",
            font=("", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        if not summ.total_applications:
            return

        ttk.Label(holder, text="Application status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for st in APP_STATUSES:
            n = summ.by_status.get(st, 0)
            ttk.Label(holder, text=f"   {st:<12} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Choice decision status:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for ds in DECISION_STATUSES:
            n = summ.by_decision_status.get(ds, 0)
            ttk.Label(holder, text=f"   {ds:<22} : {n}",
                      foreground="#444").pack(anchor="w")

        ttk.Label(holder, text="Final decisions:",
                  font=("", 10, "bold")).pack(anchor="w", pady=(8, 2))
        for fd in FINAL_DECISIONS:
            n = summ.by_final_decision.get(fd, 0)
            ttk.Label(holder, text=f"   {fd:<12} : {n}",
                      foreground="#444").pack(anchor="w")
        not_decided = summ.by_final_decision.get("", 0)
        if not_decided:
            ttk.Label(holder, text=f"   {'Not decided':<12} : {not_decided}",
                      foreground="#888").pack(anchor="w")
        gui.status_var.set("UCAS summary loaded")

    ttk.Button(bar, text="Show", command=render
               ).pack(side="left", padx=(8, 0))
    render()
