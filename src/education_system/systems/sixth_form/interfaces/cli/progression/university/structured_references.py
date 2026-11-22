"""CLI for three-section UCAS references and their sign-off workflow."""

from __future__ import annotations

import logging

from education_system.systems.sixth_form.domain.progression.university import (
    references as data,
    workflow as workflow_data,
)
from education_system.systems.sixth_form.interfaces.cli.progression import _record_menus as rm

logger = logging.getLogger(__name__)

_COLUMNS = (("reference_id", "#", 4), ("student_name", "Student", 22),
            ("referee", "Referee", 16), ("signoff_stage", "Stage", 22),
            ("n_waiting", "Wait", 4), ("tutor_signed_by", "Tutor", 14),
            ("approved_by", "Approved", 14), ("char_count", "Chars", 5))


def _pick() -> dict | None:
    rows = data.list_structured()
    rm.print_table(rows, _COLUMNS)
    row = rm.pick_row(rows, "reference_id", "Reference #")
    return data.get_structured(row["reference_id"]) if row else None


def list_refs() -> None:
    stage = rm.choose("Stage", data.SIGNOFF_STAGES, allow_blank=True)
    rm.print_table(data.list_structured(stage=stage or None), _COLUMNS)
    rm.pause()


def view() -> None:
    ref = _pick()
    if ref is None:
        return
    words, chars, lines = ref["counts"]
    print(f"\n  Stage {ref.get('signoff_stage') or 'Draft'} · {chars}/{data.SOFT_CHAR_LIMIT} chars"
          f" · tutor {ref.get('tutor_signed_by') or '—'} · approved {ref.get('approved_by') or '—'}")
    if ref.get("returned_reason"):
        print(f"  Returned: {ref['returned_reason']}")
    for col, heading in data.SECTIONS:
        print(f"\n  {heading}")
        for line in (ref.get(col) or "(empty)").splitlines():
            print(f"    {line}")
    print("\n  Predicted grades" + (" (frozen)" if ref["predicted_grades_frozen"] else " (live)"))
    for g in ref["predicted_grades"] or []:
        print(f"    {g['subject']:<28} {g['grade']}")
    print("\n  Contributions")
    for c in ref["contributions"]:
        print(f"    #{c['contribution_id']} {c['subject']} — {c['teacher'] or '?'} [{c['status']}]")
    rm.pause()


def new() -> None:
    sid = rm.pick_student()
    ref = data.start_structured(
        sid, rm.ask("Referee", required=True), referee_role=rm.ask("Referee role"),
        cycle_year=rm.ask_int("Cycle (entry year)", default=workflow_data.default_cycle_year()))
    print(f"  ✓ Started reference #{ref['reference_id']}.")
    rm.pause()


def edit_sections() -> None:
    ref = _pick()
    if ref is None:
        return
    values = rm.form([(col, heading, "longtext") for col, heading in data.SECTIONS], ref)
    data.save_sections(ref["reference_id"], general=values["section_general"],
                       extenuating=values["section_extenuating"],
                       supportive=values["section_supportive"])
    print("  ✓ Saved.")
    rm.pause()


def request() -> None:
    ref = _pick()
    if ref is None:
        return
    print("  Enter 'Subject; Teacher' per line, END to finish (blank = student's subjects).")
    raw = rm.ask_long("Subjects")
    items = [tuple((p.split(";") + [""])[:2]) for p in raw.splitlines() if p.strip()]
    rows = data.request_contributions(ref["reference_id"], items or None)
    print(f"  ✓ {len(rows)} contribution(s) on the reference.")
    rm.pause()


def contribute() -> None:
    rows = data.outstanding_contributions()
    rm.print_table(rows, (("contribution_id", "#", 4), ("student_name", "Student", 22),
                          ("subject", "Subject", 20), ("teacher", "Teacher", 16)))
    row = rm.pick_row(rows, "contribution_id", "Contribution #")
    if row is None:
        return
    if rm.ask_yes("Mark as not required instead?"):
        data.set_contribution_not_required(row["contribution_id"])
    else:
        data.submit_contribution(row["contribution_id"], rm.ask_long("Contribution"),
                                 teacher=rm.ask("Teacher", default=row["teacher"] or ""))
    print("  ✓ Saved.")
    rm.pause()


def _step(fn, label: str, named: bool = True):
    def handler() -> None:
        ref = _pick()
        if ref is None:
            return
        if named:
            fn(ref["reference_id"], rm.ask("Name (blank = signed-in user)") or None)
        else:
            fn(ref["reference_id"])
        print(f"  ✓ {label}.")
        rm.pause()
    return handler


def return_draft() -> None:
    ref = _pick()
    if ref is None:
        return
    data.return_to_draft(ref["reference_id"], rm.ask("Reason", required=True))
    print("  ✓ Returned to draft.")
    rm.pause()


def centre_statement() -> None:
    cycle = rm.ask_int("Cycle (entry year)", default=workflow_data.default_cycle_year())
    current = data.get_centre_statement(cycle)
    data.set_centre_statement(cycle, rm.ask_long("General statement (section 1)",
                                                 current=current))
    print("  ✓ Saved.")
    rm.pause()


MENU = (
    ("List structured references", list_refs),
    ("View one", view),
    ("New three-section reference", new),
    ("Edit sections", edit_sections),
    ("Request subject contributions", request),
    ("Write / waive a subject contribution", contribute),
    ("Ready for tutor review", _step(data.move_to_tutor_review, "Moved to tutor review", False)),
    ("Tutor sign-off", _step(data.tutor_sign_off, "Signed by tutor")),
    ("Head of sixth form approval", _step(data.approve, "Approved")),
    ("Mark sent to UCAS", _step(data.send, "Sent")),
    ("Return to draft", return_draft),
    ("College general statement (section 1)", centre_statement),
)


def run() -> None:
    rm.run_menu("Structured references (2026 entry on)", MENU)


__all__ = ["run", "MENU"]
