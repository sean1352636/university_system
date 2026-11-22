"""CLI: an applicant's programme choices and their conversion record."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    admissions as adm,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _pick_applicant,
    _pick_from,
    _run_submenu,
)


def _show(aid: str) -> None:
    rows = adm.list_programme_choices(aid)
    print(f"\n  Programme choices for {aid}:")
    for i, c in enumerate(rows, 1):
        print(f"    {i}) {c.qualification_type:<22} {c.subject}")
    if not rows:
        print("    (none)")


def programme_choices_flow() -> None:
    aid = _pick_applicant().applicant_id

    def add() -> None:
        q = _pick_from("Qualification", list(adm.programme_types()),
                       default="A Level")
        s = _input("Subject / course", allow_empty=False)
        try:
            adm.add_programme_choice(aid, q, s)
            print("  ✓ Added")
        except ValueError as e:
            print(f"  ✗ {e}")
        _pause()

    def remove() -> None:
        rows = adm.list_programme_choices(aid)
        if not rows:
            print("  (no choices)")
            return _pause()
        labels = [c.label for c in rows]
        c = rows[labels.index(_pick_from("Remove", labels))]
        adm.remove_programme_choice(aid, c.qualification_type, c.subject)
        print("  ✓ Removed")
        _pause()

    _run_submenu(f"Programme choices — {aid}", [
        ("Show", lambda: (_show(aid), _pause())),
        ("Add a choice", add),
        ("Remove a choice", remove),
    ])


def conversion_record_flow() -> None:
    aid = _pick_applicant().applicant_id
    rec = adm.get_conversion(aid)
    if rec is None:
        print("  Not converted to a student yet.")
        return _pause()
    print(f"\n  {rec.applicant_id} → student {rec.student_id}, converted "
          f"{rec.converted_at} by {rec.converted_by or '—'}")
    print(f"  Year {rec.academic_year or '—'}, enrolment "
          f"#{rec.enrolment_id or '—'}, onboarding #{rec.checklist_id or '—'}")
    for s in rec.steps:
        print(f"    [{s['result']:>6}] {s['step']}: {s['detail']}")
    if rec.carried:
        print("  Kept here (no column on the student record yet):")
        for k, v in rec.carried.items():
            print(f"    {k}: {v}")
    _pause()
