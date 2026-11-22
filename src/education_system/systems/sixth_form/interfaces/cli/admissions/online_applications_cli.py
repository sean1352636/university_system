"""CLI: online applications awaiting staff verification."""

from __future__ import annotations

from education_system.systems.sixth_form.domain.admissions import (
    online_application as oa,
)
from education_system.systems.sixth_form.interfaces.cli.admissions._common import (
    _input,
    _pause,
    _pick_from,
    _run_submenu,
    _UserAbort,
    _yes,
)
from education_system.systems.sixth_form.interfaces.cli.admissions.entry_requirements_cli import (
    _user,
)


def _pick() -> str:
    rows = oa.pending()
    if not rows:
        print("    No online applications awaiting verification.")
        raise _UserAbort
    label = _pick_from("Online application", [
        f"{a.applicant_id} {s.reference_no} {a.full_name} "
        f"({s.submitted_at[:16]})"
        + (f" possible duplicate of {', '.join(s.duplicates)}"
           if s.duplicates else "") for s, a in rows])
    return label.split()[0]


def list_flow() -> None:
    rows = oa.pending()
    print(f"\n═══ Online applications awaiting verification: {len(rows)} ═══")
    for s, a in rows:
        dupes = [d.applicant_id for d in oa.current_duplicates(a.applicant_id)]
        print(f"  {a.applicant_id:<10} {s.reference_no}  {a.full_name[:26]:<26}"
              f" {a.email or '':<28} {s.submitted_at[:16]}"
              + (f"  DUPLICATE? {', '.join(dupes)}" if dupes else ""))
    _pause()


def verify_flow() -> None:
    aid = _pick()
    dupes = oa.current_duplicates(aid)
    if dupes and not _yes("Possible duplicate of " + ", ".join(
            d.applicant_id for d in dupes) + " — verify as a new applicant?"):
        return
    try:
        a = oa.verify(aid, by=_user(), notes=_input("Notes") or None)
        print(f"  ✓ {a.applicant_id} verified → {a.status}")
    except ValueError as e:
        print(f"  ✗ {e}")
    _pause()


def merge_flow() -> None:
    aid = _pick()
    dupes = oa.current_duplicates(aid)
    if not dupes:
        print("  No existing applicant matches this one.")
        return _pause()
    keep = _pick_from("Merge into", [f"{d.applicant_id} {d.full_name} "
                                     f"[{d.status}]" for d in dupes]).split()[0]
    if _yes(f"Merge {aid} into {keep} (its details move across; the "
            "online record is archived as merged)?"):
        try:
            oa.merge_into(aid, keep, by=_user())
            print(f"  ✓ Merged into {keep}")
        except ValueError as e:
            print(f"  ✗ {e}")
    _pause()


def reject_flow() -> None:
    aid = _pick()
    if _yes(f"Reject {aid} as invalid/spam? Its data is erased."):
        try:
            oa.reject(aid, by=_user(),
                      reason=_input("Reason",
                                    default="Invalid or spam online "
                                    "application"))
            print("  ✓ Rejected and erased (logged in the erasure log)")
        except ValueError as e:
            print(f"  ✗ {e}")
    _pause()


MENU = [
    ("List awaiting verification", list_flow),
    ("Verify (→ Submitted)", verify_flow),
    ("Merge into an existing applicant", merge_flow),
    ("Reject (erase)", reject_flow),
]


def run() -> None:
    _run_submenu("Online Applications", MENU)
