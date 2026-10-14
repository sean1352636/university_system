#!/usr/bin/env python3
"""Clear down UCAS applicants who are already students here.

"Admit from UCAS" lists everyone the sixth form records as applying to this
university. Until recently nothing ended that application when the applicant
was actually admitted, so anyone imported before the clear-down existed is
still on the list — shown as *Enrolled*, and refused by Admit as an existing
student. New admissions tidy up after themselves; this sweeps the backlog.

An applicant is swept only when the university can *prove* they arrived:

* their admission application carries ``converted_student_id``, **and**
* a student with that id really exists here.

Anything less is left alone and reported:

* **converted, but no such student** — the application and the student record
  disagree. Clearing the UCAS row would destroy the only remaining evidence of
  what was supposed to happen. That needs a human in Admissions.
* **no application at all** — they may simply not have been admitted yet.

What clearing means is defined by
``admissions.domain.ucas.post_admission``: the sixth form's choice row for
this university goes, the parent application goes only if that was its last
choice, and our own link row is archived rather than deleted.

Usage
-----
    python tools/university/sweep_imported_ucas_applicants.py           # report
    python tools/university/sweep_imported_ucas_applicants.py --apply   # clear
    python tools/university/sweep_imported_ucas_applicants.py --student C5588396

``--apply`` backs up **both** databases first (the university's and the sixth
form's — the choice rows live in the latter), and is idempotent: an applicant
already cleared is simply not found again.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from education_system.paths import (  # noqa: E402
    SIXTH_FORM_STUDENTS_DB,
    UNIVERSITY_DEFAULT_DB_PATH,
    maintenance_backup_dir,
)


def _applicants():
    from education_system.systems.university.domains.admissions.domain.ucas import (
        applicants as _applicants_mod,
    )
    return _applicants_mod.list_all_applicants()


def _conversions(student_ids):
    """``{sf_student_id: converted_student_id or None}`` for a cohort.

    Same two-step the import picker uses: journey first, then the admission
    application staged against it.
    """
    out = {sid: None for sid in student_ids}
    if not student_ids:
        return out
    from education_system.platform.cross_system import identity_service
    from education_system.systems.university.domains.admissions.domain import (
        sixthform_intake,
    )

    journeys = identity_service.find_by_students("sixth_form", list(student_ids))
    by_journey = {}
    for sid, journey in journeys.items():
        journey_id = journey.get("journey_id")
        if journey_id:
            by_journey.setdefault(journey_id, []).append(sid)
    if not by_journey:
        return out

    applications = sixthform_intake.find_applications_for_journeys(by_journey.keys())
    for journey_id, application in applications.items():
        for sid in by_journey.get(journey_id, ()):
            out[sid] = application.get("converted_student_id")
    return out


def _student_exists(student_id) -> bool:
    if not student_id:
        return False
    from education_system.systems.university.infrastructure.database.db import (
        get_connection,
    )
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT 1 FROM students WHERE student_id = ?", (str(student_id),)
        ).fetchone() is not None
    finally:
        conn.close()


def classify(only_student=None):
    """Split the UCAS applicant list into sweepable / needs-a-human / not-yet."""
    rows = [a for a in _applicants()
            if not only_student or a.student_id == only_student]
    conversions = _conversions([a.student_id for a in rows])

    sweepable, mismatched, not_admitted = [], [], []
    for applicant in rows:
        converted = conversions.get(applicant.student_id)
        entry = {"applicant": applicant, "converted": converted}
        if not converted:
            not_admitted.append(entry)
        elif _student_exists(converted):
            sweepable.append(entry)
        else:
            mismatched.append(entry)
    return sweepable, mismatched, not_admitted


def backup() -> list[Path]:
    target_dir = maintenance_backup_dir("ucas-applicant-sweep", create=True)
    saved = []
    for source in (UNIVERSITY_DEFAULT_DB_PATH, SIXTH_FORM_STUDENTS_DB):
        source = Path(source)
        if not source.exists():
            continue
        target = target_dir / source.name
        shutil.copy2(source, target)
        saved.append(target)
    return saved


def close_transition(applicant, uni_student_id) -> str:
    """Walk a handover transition to completed for a learner who has arrived.

    The picker merges two sources: the sixth form's UCAS choices *and* the
    cross-system handover transitions. Clearing the UCAS half alone leaves
    the applicant listed by the other half — which is how somebody admitted
    weeks ago is still sitting in the list as "expected".

    ``admit`` stamps the destination enrolment with the university student id
    and ``complete`` activates it, which is the truthful record: they did
    arrive. Best-effort, and reported per applicant.
    """
    transition_id = getattr(applicant, "transition_id", None)
    if not transition_id:
        return "no transition"
    from education_system.platform.cross_system import transitions
    try:
        current = transitions.get_transition(transition_id)
    except Exception as exc:
        return f"transition unreadable: {exc}"
    if current is None:
        return "transition not found"
    if current.get("status") == "completed":
        return "transition already completed"

    try:
        if current.get("status") != "admitted":
            transitions.admit(transition_id, local_student_id=str(uni_student_id))
        transitions.complete(transition_id)
        return "transition completed"
    except Exception as exc:
        return f"transition not completed: {exc}"


def _describe(entry) -> str:
    applicant = entry["applicant"]
    return (f"{applicant.student_id:<12} {(applicant.student_name or '—')[:24]:<26}"
            f"{applicant.course_label[:28]:<30}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="clear the sweepable applicants (default: report)")
    parser.add_argument("--student", help="limit to one sixth-form student id")
    parser.add_argument("--ucas-only", action="store_true",
                        help="clear the UCAS rows but leave the handover "
                             "transition alone (it will keep them listed)")
    args = parser.parse_args()

    sweepable, mismatched, not_admitted = classify(args.student)

    print(f"\nUCAS applicants listed: "
          f"{len(sweepable) + len(mismatched) + len(not_admitted)}")

    if sweepable:
        print(f"\nALREADY STUDENTS HERE ({len(sweepable)}) — will be cleared:")
        for entry in sweepable:
            print(f"  {_describe(entry)} -> student {entry['converted']}")

    if mismatched:
        print(f"\nNEEDS A HUMAN ({len(mismatched)}) — application says enrolled, "
              "but no such student exists:")
        for entry in mismatched:
            print(f"  {_describe(entry)} -> claims student {entry['converted']}")
        print("  Fix these in Admissions; clearing the UCAS row would destroy "
              "the evidence.")

    if not_admitted:
        print(f"\nSTILL APPLICANTS ({len(not_admitted)}) — left alone:")
        for entry in not_admitted:
            print(f"  {_describe(entry)}")

    if not sweepable:
        print("\nNothing to sweep.")
        return 0

    if not args.apply:
        print(f"\nDry run. Re-run with --apply to clear {len(sweepable)} applicant(s).")
        return 0

    for saved in backup():
        print(f"\nBacked up {saved}")

    from education_system.systems.university.services.bus import ucas_bus
    cleared = failed = 0
    for entry in sweepable:
        applicant = entry["applicant"]
        summary = ucas_bus.clear_after_admission(
            applicant.student_id, entry["converted"], actor="ucas sweep")
        detail = ucas_bus.describe(summary)
        ok = summary is not None and not summary.get("errors")
        if not args.ucas_only:
            detail = f"{detail}; {close_transition(applicant, entry['converted'])}"
        if ok:
            cleared += 1
            print(f"  ✓ {applicant.student_id}: {detail}")
        else:
            failed += 1
            print(f"  ✗ {applicant.student_id}: {detail}")

    print(f"\nCleared {cleared} applicant(s)"
          + (f", {failed} problem(s)" if failed else ""))

    remaining, _mismatched, _pending = classify(args.student)
    print(f"Still listed as already-admitted: {len(remaining)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
