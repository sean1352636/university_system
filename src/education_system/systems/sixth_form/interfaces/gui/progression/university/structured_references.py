"""GUI for three-section UCAS references and their sign-off.

Lives beside the existing References directory (Application → References)
rather than replacing it: older single-text references stay where they
were, and this tab is where a 2026-entry reference is written, gathered
from subject teachers, signed by the tutor, approved by the head of sixth
form and sent.
"""

from __future__ import annotations

import logging
from tkinter import ttk

from education_system.systems.sixth_form.domain.progression.university import (
    references as data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.gui.progression import _record_tabs as rt

logger = logging.getLogger(__name__)

_STAGE_TAG = {"Sent": "good", "Approved": "good", "HoSF approval": "warn",
              "Tutor review": "warn"}


def build_tab(gui, parent: ttk.Frame) -> None:
    nb = ttk.Notebook(parent)
    nb.pack(fill="both", expand=True)
    rt.notebook_tab(nb, "References", _references)
    rt.notebook_tab(nb, "Outstanding contributions", _contributions)
    rt.notebook_tab(nb, "General statement", _centre_statement)


def _detail_text(ref: dict) -> str:
    words, chars, lines = ref["counts"]
    out = [f"Reference #{ref['reference_id']} — {ref['student_id']} — referee {ref['referee']}",
           f"Stage: {ref.get('signoff_stage') or 'Draft'}"
           f"   Tutor: {ref.get('tutor_signed_by') or '—'}"
           f"   Approved: {ref.get('approved_by') or '—'}"
           f"   Sent: {ref.get('sent_at') or '—'}",
           f"Length: {chars}/{data.SOFT_CHAR_LIMIT} characters across the sections"]
    if ref.get("returned_reason"):
        out.append(f"Returned: {ref['returned_reason']}")
    for col, heading in data.SECTIONS:
        out += ["", heading, ref.get(col) or "(empty)"]
    out += ["", "Predicted grades" + (" (frozen at approval)" if ref["predicted_grades_frozen"]
                                      else " (live from Predicted Grades)")]
    for g in ref["predicted_grades"] or []:
        out.append(f"  {g['subject']:<28} {g['grade']}  ({g['confidence']})")
    if not ref["predicted_grades"]:
        out.append("  (none recorded)")
    out += ["", "Subject contributions"]
    for c in ref["contributions"]:
        out.append(f"  {c['subject']} — {c['teacher'] or '?'} [{c['status']}]")
        if c["body"]:
            out += [f"     {line}" for line in c["body"].splitlines()]
    if not ref["contributions"]:
        out.append("  (none requested)")
    return "\n".join(out)


def _references(parent: ttk.Frame) -> None:
    def load(f):
        cycle = f.get("cycle") or ""
        return data.list_structured(stage=f.get("stage") or None,
                                    cycle_year=int(cycle) if cycle.isdigit() else None)

    def _ref(table):
        row = table.require()
        ref = data.get_structured(row["reference_id"])
        if ref is None:
            raise ValueError("That reference no longer exists.")
        return ref

    def view(table):
        rt.show_text(table.parent, "Structured reference", _detail_text(_ref(table)))

    def new(table):
        rt.form_dialog(
            table.parent, "New three-section reference",
            (("student", "Student", "choice", rt.student_choices),
             ("referee", "Referee", "text"), ("referee_role", "Referee role", "text"),
             ("cycle_year", "Cycle (entry year)", "number")),
            {"cycle_year": workflow_data.default_cycle_year()},
            lambda v: data.start_structured(
                rt.student_id_of(v["student"]), v["referee"],
                referee_role=v["referee_role"],
                cycle_year=int(v["cycle_year"]) if v["cycle_year"] else None),
            table.refresh)

    def edit(table):
        ref = _ref(table)
        rt.form_dialog(
            table.parent, f"Sections — reference #{ref['reference_id']}",
            [(col, heading, "longtext") for col, heading in data.SECTIONS],
            ref,
            lambda v: data.save_sections(
                ref["reference_id"], general=v["section_general"],
                extenuating=v["section_extenuating"], supportive=v["section_supportive"]),
            table.refresh,
            intro=(f"UCAS limit: {data.SOFT_CHAR_LIMIT} characters across all three. "
                   "Section 3 is required before the tutor can sign."))

    def request(table):
        ref = _ref(table)
        rt.form_dialog(
            table.parent, "Request subject contributions",
            (("items", "Subjects (one per line, 'Subject; Teacher')", "multiline"),),
            {}, lambda v: data.request_contributions(
                ref["reference_id"],
                [tuple((p.split(";") + [""])[:2]) for p in v["items"].splitlines()
                 if p.strip()] or None),
            table.refresh,
            intro="Leave blank to ask for each of the student's subjects.")

    def contribute(table):
        ref = _ref(table)
        waiting = [c for c in ref["contributions"] if c["status"] != "Not required"]
        if not waiting:
            raise ValueError("No contributions have been requested.")
        labels = [f"#{c['contribution_id']} {c['subject']} [{c['status']}]" for c in waiting]
        by = dict(zip(labels, waiting))

        def save(v):
            c = by[v["which"]]
            if v["not_required"]:
                data.set_contribution_not_required(c["contribution_id"])
            else:
                data.submit_contribution(c["contribution_id"], v["body"], teacher=v["teacher"])

        rt.form_dialog(table.parent, "Subject contribution",
                       (("which", "Subject", "choice", labels),
                        ("teacher", "Teacher", "text"),
                        ("body", "Contribution", "longtext"),
                        ("not_required", "Mark not required instead", "bool")),
                       {"which": labels[0]}, save, table.refresh)

    def step(fn, label, needs_name=True):
        def handler(table):
            ref = _ref(table)
            if not needs_name:
                fn(ref["reference_id"])
                table.refresh()
                return
            rt.form_dialog(table.parent, label,
                           (("who", "Name (blank = signed-in user)", "text"),),
                           {}, lambda v: fn(ref["reference_id"], v["who"] or None),
                           table.refresh)
        return handler

    def return_draft(table):
        ref = _ref(table)
        rt.form_dialog(table.parent, "Return to draft", (("reason", "Reason", "multiline"),),
                       {}, lambda v: data.return_to_draft(ref["reference_id"], v["reason"]),
                       table.refresh)

    rt.RecordTable(
        parent,
        (("reference_id", "#", 50), ("student_name", "Student", 170),
         ("referee", "Referee", 140), ("cycle_year", "Cycle", 60),
         ("signoff_stage", "Stage", 120), ("n_contrib", "Contribs", 70),
         ("n_waiting", "Waiting", 60), ("tutor_signed_by", "Tutor", 120),
         ("approved_by", "Approved by", 120), ("char_count", "Chars", 60)),
        load, key="reference_id",
        filters=[("cycle", "Cycle", "text"),
                 ("stage", "Stage", "choice", data.SIGNOFF_STAGES)],
        note=("Draft → subject contributions → tutor review → head of sixth form "
              "approval → approved → sent. The approver cannot be the tutor who signed. "
              "Predicted grades are frozen onto the reference when it is approved."),
        tags=lambda r: _STAGE_TAG.get(r["signoff_stage"]),
        actions=[("New…", new), ("View", view), ("Edit sections…", edit),
                 ("Request contributions…", request), ("Contribution…", contribute),
                 ("Ready for tutor", step(data.move_to_tutor_review, "", needs_name=False)),
                 ("Tutor sign-off…", step(data.tutor_sign_off, "Tutor sign-off")),
                 ("HoSF approve…", step(data.approve, "Head of sixth form approval")),
                 ("Mark sent…", step(data.send, "Sent to UCAS")),
                 ("Return to draft…", return_draft)],
        on_open=view)


def _contributions(parent: ttk.Frame) -> None:
    def submit(table):
        row = table.require()
        rt.form_dialog(table.parent, f"{row['subject']} — {row['student_name']}",
                       (("teacher", "Teacher", "text"), ("body", "Contribution", "longtext")),
                       {"teacher": row["teacher"]},
                       lambda v: data.submit_contribution(row["contribution_id"], v["body"],
                                                          teacher=v["teacher"]),
                       table.refresh)

    rt.RecordTable(
        parent,
        (("student_name", "Student", 180), ("subject", "Subject", 160),
         ("teacher", "Teacher", 140), ("requested_at", "Requested", 140)),
        lambda f: data.outstanding_contributions(f.get("teacher") or None),
        key="contribution_id", filters=[("teacher", "Teacher", "text")],
        actions=[("Write contribution…", submit)], on_open=submit)


def _centre_statement(parent: ttk.Frame) -> None:
    def load(f):
        cycle = f.get("cycle") or ""
        cy = int(cycle) if cycle.isdigit() else workflow_data.default_cycle_year()
        body = data.get_centre_statement(cy)
        return [{"cycle_year": cy, "body": (body or "(not written)")[:200]}]

    def edit(table):
        row = table.require()
        rt.form_dialog(table.parent, f"General statement — cycle {row['cycle_year']}",
                       (("body", "Section 1 text", "longtext"),),
                       {"body": data.get_centre_statement(row["cycle_year"]) or ""},
                       lambda v: data.set_centre_statement(row["cycle_year"], v["body"]),
                       table.refresh)

    rt.RecordTable(
        parent, (("cycle_year", "Cycle", 70), ("body", "Statement (start)", 800)),
        load, key="cycle_year",
        filters=[("cycle", "Cycle", "text", (), workflow_data.default_cycle_year())],
        note=("Section 1 is the same for every applicant: the college, its courses "
              "and context. New structured references start with this text."),
        actions=[("Edit…", edit)], on_open=edit)


__all__ = ["build_tab"]
