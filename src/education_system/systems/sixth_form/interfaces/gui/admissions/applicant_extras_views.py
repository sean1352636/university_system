"""Per-applicant add-ons: programme choices and the conversion record."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from education_system.platform.delivery.gui.parented_dialogs import messagebox

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    _admissions_ui as ui,
)
from education_system.systems.sixth_form.interfaces.gui.admissions import (
    applicant_actions as act,
)


class ProgrammeChoicesDialog:
    """Any qualification mix: A levels, BTEC, T Level, EPQ, resits …"""

    def __init__(self, parent: tk.Misc, applicant_id: str,
                 on_change=None) -> None:
        self.aid = applicant_id
        self.on_change = on_change
        self.win = ui.new_window(parent, f"Programme choices — {applicant_id}",
                                 geometry="760x420", minsize=(640, 340))
        bar = ttk.Frame(self.win)
        bar.pack(fill="x", padx=8, pady=(8, 4))
        ok = act.can_admissions()
        act.gate(ttk.Button(bar, text="Add…", command=self._add), ok).pack(
            side="left")
        act.gate(ttk.Button(bar, text="Remove", command=self._remove),
                 ok).pack(side="left", padx=4)
        act.gate(ttk.Button(bar, text="Move up",
                            command=lambda: self._move(-1)), ok).pack(
            side="left")
        act.gate(ttk.Button(bar, text="Move down",
                            command=lambda: self._move(1)), ok).pack(
            side="left", padx=4)
        ttk.Label(self.win, foreground="#555", text=(
            "The first three A Level / AS choices fill Subject 1–3 on the "
            "application. Every choice becomes a learning aim at enrolment."
        )).pack(fill="x", padx=8)
        holder = ttk.Frame(self.win)
        holder.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree = ui.make_tree(holder, [("n", "#", 40),
                                          ("type", "Qualification", 220),
                                          ("subject", "Subject", 300)])
        self.refresh()

    def _rows(self) -> list[dict]:
        return [{"qualification_type": c.qualification_type,
                 "subject": c.subject, "notes": c.notes}
                for c in adm.list_programme_choices(self.aid)]

    def refresh(self) -> None:
        ui.clear(self.tree)
        for i, c in enumerate(adm.list_programme_choices(self.aid)):
            self.tree.insert("", "end", iid=str(i), values=(
                i + 1, c.qualification_type, c.subject))

    def _run(self, fn, *args) -> None:
        act.attempt(self.win, "Programme choices", fn, *args)
        self.refresh()
        if self.on_change:
            self.on_change()

    def _save(self, rows: list[dict]) -> None:
        self._run(adm.set_programme_choices, self.aid, rows)

    def _add(self) -> None:
        v = ui.ask_form(self.win, "Add choice", [
            ("qualification_type", "Qualification", "readonly",
             adm.programme_types()),
            ("subject", "Subject / course", "entry", None)],
            {"qualification_type": "A Level"})
        if v and v["subject"]:
            self._run(adm.add_programme_choice, self.aid,
                      v["qualification_type"], v["subject"])

    def _remove(self) -> None:
        iid = ui.require_iid(self.tree, "Programme choices")
        if iid is not None:
            row = self._rows()[int(iid)]
            if messagebox.askyesno(
                    "Programme choices",
                    f"Remove {row['qualification_type']}: {row['subject']}?",
                    parent=self.win):
                self._run(adm.remove_programme_choice, self.aid,
                          row["qualification_type"], row["subject"])

    def _move(self, d: int) -> None:
        iid = ui.require_iid(self.tree, "Programme choices")
        if iid is None:
            return
        rows, i = self._rows(), int(iid)
        j = i + d
        if 0 <= j < len(rows):
            rows[i], rows[j] = rows[j], rows[i]
            self._save(rows)
            self.tree.selection_set(str(j))


def show_conversion(parent: tk.Misc, applicant_id: str) -> None:
    ok, rec = act.attempt(parent, "Conversion", adm.get_conversion,
                          applicant_id)
    if not ok:
        return
    if rec is None:
        messagebox.showinfo("Conversion", "This applicant has not been "
                            "converted to a student yet.", parent=parent)
        return
    lines = [f"Applicant {rec.applicant_id} → student {rec.student_id}",
             f"Converted {rec.converted_at} by {rec.converted_by or '—'}",
             f"Academic year {rec.academic_year or '—'} · enrolment "
             f"#{rec.enrolment_id or '—'} · onboarding checklist "
             f"#{rec.checklist_id or '—'}", "", "Steps:"]
    lines += [f"  [{s['result']:>6}] {s['step']}: {s['detail']}"
              for s in rec.steps]
    if rec.carried:
        lines += ["", "Kept here (no column on the student record yet):"]
        lines += [f"  {k}: {v}" for k, v in rec.carried.items()]
    ui.show_text(parent, f"Conversion — {applicant_id}", "\n".join(lines))


def conversion_note(applicant_id: str) -> str:
    """Suffix for the bulk-convert summary when steps need attention."""
    rec = adm.get_conversion(applicant_id)
    bad = [s for s in (rec.steps if rec else []) if s["result"] != "ok"]
    return (f" ({len(bad)} step(s) need attention — see Conversion record)"
            if bad else "")


def add_workflow_footer(win: tk.Misc, applicant_id: str, on_change) -> None:
    """Second button row on the applicant detail dialog."""
    from education_system.systems.sixth_form.interfaces.gui.admissions import (
        entry_requirements_views, references_views,
    )
    bar = ttk.Frame(win)
    bar.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
    for text, cmd in (
        ("Programme choices…", lambda: ProgrammeChoicesDialog(
            win, applicant_id, on_change=on_change)),
        ("GCSEs & conditions…", lambda: entry_requirements_views
         .open_applicant_gcses(win, applicant_id, on_change=on_change)),
        ("References workflow…", lambda: references_views
         .open_applicant_references(win, applicant_id, on_change=on_change)),
        ("Conversion record…", lambda: show_conversion(win, applicant_id)),
    ):
        ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(0, 4))
