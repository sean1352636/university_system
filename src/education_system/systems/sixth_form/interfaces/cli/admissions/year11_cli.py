"""CLI: Year 11 transition — read a feeder school's CTF into applicants."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    year11_transition as y11,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _yes,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.entry_requirements_cli import (
    _user,
)


def run() -> None:
    print("\n═══ Year 11 transition (Common Transfer File) ═══")
    if not y11.available():
        print("  The CTF reader (operations/integrations) is not available.")
        return _pause()
    path = _input("CTF XML file path", allow_empty=False)
    try:
        pv = y11.preview(path)
    except Exception as e:  # noqa: BLE001 — bad file
        print(f"  ✗ {e}")
        return _pause()
    print(f"\n  {pv.file_name} from {pv.source_school or 'unknown school'}: "
          f"{len(pv.matched)} matched, {len(pv.unmatched)} not matched")
    for p in pv.pupils:
        where = (f"→ {p.applicant_id} (by {p.matched_on})" if p.applicant_id
                 else "→ no applicant")
        print(f"    {p.name:<28} {p.dob or '':<10} {len(p.gcses):>2} GCSE(s) "
              f"{where}")
    if not pv.matched:
        print("\n  Nothing to apply (unmatched pupils are never created as "
              "applicants).")
        return _pause()
    if not _yes("Apply to the matched applicants?"):
        return
    res = y11.apply(path, record_results=_yes(
        "Record KS4 grades as actual GCSE results?", default="yes"),
        entered_by=_user())
    print(f"\n  ✓ {len(res.updated)} applicant(s) updated, "
          f"{res.results_recorded} result(s) recorded")
    for n in res.notes[:40]:
        print(f"    {n}")
    _pause()
