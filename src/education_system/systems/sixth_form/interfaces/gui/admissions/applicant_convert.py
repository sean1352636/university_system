"""Convert accepted applicants to students.

One applicant: a dialog showing the pre-conversion checks and the
conversion gates (conditions not confirmed, no ID / right-to-study
check), with mid-year options (academic year, start date, tutor group),
an override reason, and "link to an existing student" when the student
record already holds someone who looks like the applicant.

Several: each applicant is checked, the summary shows who is ready,
who is gated and why, and the run reports each applicant's outcome.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Callable

from education_system.platform.delivery.gui import window_sizing
from education_system.platform.delivery.gui.parented_dialogs import (
    make_toplevel,
    messagebox,
)
from education_system.systems.sixth_form.domain.admissions import (
    admissions as data,
)
from education_system.systems.sixth_form.domain.admissions import (
    conversion,
)

from . import applicant_actions as act

logger = logging.getLogger(__name__)

_NEW = "(create a new student record)"


def _note(aid: str) -> str:
    from . import applicant_extras_views as ext
    try:
        return ext.conversion_note(aid)
    except Exception:  # noqa: BLE001 — note only
        return ""


def possible_students(a: data.Applicant) -> list:
    """Students already on file who look like this applicant."""
    try:
        from education_system.systems.sixth_form.domain.learners.students import (
            students,
        )
        return students.find_possible_duplicates(
            first_name=a.first_name, last_name=a.last_name,
            date_of_birth=a.dob, personal_email=a.email, uln=a.uln,
            upn=a.upn)
    except Exception:  # noqa: BLE001 — the dialog still works without
        logger.debug("duplicate-student search failed", exc_info=True)
        return []


class ConvertDialog:
    def __init__(self, parent: tk.Misc, applicant_id: str,
                 on_done: Callable[[], None]) -> None:
        self.aid = applicant_id
        self.on_done = on_done
        a = data.get_applicant(applicant_id)
        if a is None:
            raise data.ValidationError(f"No applicant {applicant_id!r}")
        self.win = make_toplevel(parent)
        self.win.title(f"Convert to student — {a.applicant_id} "
                       f"{a.full_name}")
        window_sizing.fit(self.win, "760x620", (620, 480))
        bar = ttk.Frame(self.win, padding=(10, 8))
        bar.pack(side="bottom", fill="x")
        self.go = ttk.Button(bar, text="Convert to student",
                             command=self._convert)
        self.go.pack(side="right")
        act.gate(self.go, act.can_convert())
        ttk.Button(bar, text="Cancel", command=self.win.destroy).pack(
            side="right", padx=6)
        if not act.can_convert():
            ttk.Label(bar, foreground="#b00000", text=(
                "Converting needs the admissions and students.manage "
                "permissions.")).pack(side="left")

        frm = ttk.Frame(self.win, padding=10)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text=f"{a.full_name} ({a.applicant_id}) — {a.status}, "
                  f"intake {a.intake_year or '—'}",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        checks = ttk.LabelFrame(frm, text="Checks")
        checks.pack(fill="x", pady=6)
        issues = data.pre_conversion_check(applicant_id)
        self.gates = conversion.conversion_gates(applicant_id)
        if not issues and not self.gates:
            ttk.Label(checks, text="✓ Ready to enrol.",
                      foreground="#2e7d32").pack(anchor="w", padx=6, pady=2)
        for i in issues:
            ttk.Label(checks, text=f"✗ {i}", foreground="#b00000",
                      wraplength=680, justify="left").pack(anchor="w",
                                                           padx=6)
        for g in self.gates:
            ttk.Label(checks, text=f"⚠ Gate: {g}", foreground="#a06000",
                      wraplength=680, justify="left").pack(anchor="w",
                                                           padx=6)

        form = ttk.LabelFrame(frm, text="Enrolment")
        form.pack(fill="x", pady=6)
        self.year = self._row(form, 0, "Academic year",
                              conversion.default_academic_year())
        self.start = self._row(form, 1, "Start date (blank = start of "
                               "year / today)", "")
        self.tutor = self._row(form, 2, "Tutor group (mid-year joiner)", "")
        ttk.Label(form, text="Year group:").grid(row=3, column=0, sticky="e",
                                                 padx=6, pady=3)
        self.year_group = ttk.Combobox(form, values=("12", "13"),
                                       state="readonly", width=6)
        self.year_group.set("12")
        self.year_group.grid(row=3, column=1, sticky="w", padx=6, pady=3)
        ttk.Label(form, foreground="#555", text=(
            "Year 13 is for a transfer-in joining the second year.")).grid(
            row=4, column=1, sticky="w", padx=6)

        link = ttk.LabelFrame(frm, text="Student record")
        link.pack(fill="x", pady=6)
        self._students = possible_students(a)
        labels = [_NEW] + [f"{s.student_id} — {s.full_name} "
                           f"({getattr(s, 'date_of_birth', '') or 'no DOB'})"
                           for s in self._students]
        if self._students:
            ttk.Label(link, foreground="#a06000", wraplength=680,
                      text=f"{len(self._students)} student(s) already on "
                      "file look like this applicant. Link to one instead "
                      "of creating a second record?").pack(anchor="w",
                                                           padx=6)
        self.link = ttk.Combobox(link, values=labels, state="readonly",
                                 width=70)
        self.link.set(_NEW)
        self.link.pack(anchor="w", padx=6, pady=4)
        self._labels = labels

        ov = ttk.LabelFrame(frm, text="Override")
        ov.pack(fill="x", pady=6)
        ttk.Label(ov, wraplength=680, foreground="#555", text=(
            "Only needed when a gate is open: give the reason for enrolling "
            "anyway (recorded on the conversion).")).pack(anchor="w",
                                                          padx=6)
        self.override = ttk.Entry(ov, width=80)
        self.override.pack(anchor="w", padx=6, pady=4)
        if not self.gates:
            self.override.configure(state="disabled")

    @staticmethod
    def _row(parent: tk.Misc, r: int, label: str, value: str) -> ttk.Entry:
        ttk.Label(parent, text=label + ":").grid(row=r, column=0, sticky="e",
                                                 padx=6, pady=3)
        e = ttk.Entry(parent, width=24)
        e.insert(0, value)
        e.grid(row=r, column=1, sticky="w", padx=6, pady=3)
        return e

    def _convert(self) -> None:
        idx = self._labels.index(self.link.get()) if self.link.get() in \
            self._labels else 0
        existing = self._students[idx - 1].student_id if idx > 0 else None
        reason = (self.override.get().strip()
                  if str(self.override.cget("state")) != "disabled" else "")
        try:
            _a, sid = conversion.convert_to_student(
                self.aid,
                academic_year=self.year.get().strip() or None,
                start_date=self.start.get().strip() or None,
                tutor_group=self.tutor.get().strip() or None,
                converted_by=act.username(),
                existing_student_id=existing,
                override_reason=reason or None,
                year_group=int(self.year_group.get() or 12))
        except conversion.ConversionBlocked as e:
            self.override.configure(state="normal")
            self.override.focus_set()
            messagebox.showwarning(
                "Conversion blocked",
                "Cannot enrol yet:\n\n" + "\n".join(f"• {g}" for g in e.gates)
                + "\n\nGive an override reason to enrol anyway.",
                parent=self.win)
            return
        except Exception as e:  # noqa: BLE001 — every refusal is shown
            act.show_error(self.win, "Convert", e)
            return
        self.on_done()
        self.win.destroy()
        if messagebox.askyesno(
                "Converted",
                f"{self.aid} is now student {sid}"
                + (" (linked to the existing record)" if existing else "")
                + f".{_note(self.aid)}\n\nOpen the student record?"):
            from . import detail_student_link
            detail_student_link.open_student(None, sid)


def convert_many(parent: tk.Misc, ids: list[str],
                 on_done: Callable[[], None], *,
                 title: str = "Convert to student") -> None:
    """Check each applicant, then convert the ready ones (and, with an
    override reason, the gated ones). Reports every applicant."""
    if not act.can_convert():
        messagebox.showerror(title, "Converting needs the admissions and "
                             "students.manage permissions.",
                             parent=parent.winfo_toplevel())
        return
    if len(ids) == 1:
        ok, _ = act.attempt(parent, title, ConvertDialog, parent, ids[0],
                            on_done)
        return
    ready, gated, blocked = [], [], []
    for aid in ids:
        try:
            issues = data.pre_conversion_check(aid)
            gates = [] if issues else conversion.conversion_gates(aid)
        except Exception as e:  # noqa: BLE001 — reported
            blocked.append((aid, [act.describe(e).splitlines()[-1]]))
            continue
        if issues:
            blocked.append((aid, issues))
        elif gates:
            gated.append((aid, gates))
        else:
            ready.append(aid)
    lines = [f"Ready: {len(ready)} · Gated: {len(gated)} · "
             f"Not ready: {len(blocked)}", ""]
    lines += [f"  ✓ {aid}" for aid in ready]
    lines += [f"  ⚠ {aid}: {'; '.join(g)}" for aid, g in gated]
    lines += [f"  ✗ {aid}: {'; '.join(i)}" for aid, i in blocked]
    buttons = []
    if ready:
        buttons.append(f"Enrol ready ({len(ready)})")
    if gated:
        buttons.append(f"Enrol ready + gated with override "
                       f"({len(ready) + len(gated)})")
    if not buttons:
        messagebox.showinfo(title, "None can be enrolled yet:\n\n"
                            + "\n".join(lines),
                            parent=parent.winfo_toplevel())
        return
    choice = act.choose_action(parent, title, "\n".join(lines[:40]), buttons)
    if choice is None:
        return
    reason = None
    run = list(ready)
    if choice.startswith("Enrol ready +"):
        reason = act.ask_reason(parent, title, "Override reason for the "
                                "gated applicants (recorded on each):")
        if not reason:
            return
        run += [aid for aid, _g in gated]
    done, failed = [], [f"{aid}: {'; '.join(i)}" for aid, i in blocked]
    if reason is None:
        failed += [f"{aid}: gated — {'; '.join(g)}" for aid, g in gated]
    for aid in run:
        try:
            _a, sid = conversion.convert_to_student(
                aid, converted_by=act.username(),
                override_reason=reason if aid not in ready else None)
            done.append(f"{aid} → {sid}{_note(aid)}")
        except conversion.ConversionBlocked as e:
            failed.append(f"{aid}: gated — {'; '.join(e.gates)}")
        except Exception as e:  # noqa: BLE001 — reported per applicant
            failed.append(f"{aid}: {act.describe(e).splitlines()[-1]}")
    on_done()
    msg = ""
    if done:
        msg += f"Enrolled {len(done)}:\n" + "\n".join(done)
    if failed:
        msg += ("\n\n" if msg else "") + f"Not enrolled ({len(failed)}):\n" \
            + "\n".join(failed)
    from . import _admissions_ui as ui
    ui.show_text(parent.winfo_toplevel(), title, msg or "Nothing to do.")
