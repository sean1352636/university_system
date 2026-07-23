"""Console menu for intervention outcomes — pre/post scores and session log."""
from __future__ import annotations

from typing import Any

from education_system.post_18.university_system.modules.domain.student_affairs.services.early_warning.outcomes.intervention_outcomes_service import (
    InterventionOutcomesService,
    InterventionOutcomesError,
)


auth: Any = None


def set_auth(auth_object: Any) -> None:
    global auth
    auth = auth_object


def _require_login() -> bool:
    if not auth or not getattr(auth, "current_user", None):
        print("You must be logged in to access intervention outcomes.")
        return False
    return True


def _set_baseline(svc: InterventionOutcomesService) -> None:
    try:
        iid = int(input("Intervention ID: ").strip())
        pre = float(input("Pre-assessment score: ").strip())
        subj = input("Subject area (blank=skip): ").strip() or None
        total = input("Sessions planned (blank=skip): ").strip()
        date = input("Pre-assessment date YYYY-MM-DD (blank=today): ").strip() or None
        out = svc.set_baseline(iid, pre,
                               subject_area=subj,
                               sessions_total=int(total) if total else None,
                               pre_assessment_date=date)
        print(f"Baseline recorded. Outcome row: {out}")
    except (InterventionOutcomesError, ValueError) as exc:
        print(f"Error: {exc}")


def _record_session(svc: InterventionOutcomesService) -> None:
    try:
        iid = int(input("Intervention ID: ").strip())
        date = input("Session date (YYYY-MM-DD): ").strip()
        dur = input("Duration in minutes (blank=skip): ").strip()
        status = input("Status (attended/missed/cancelled/rescheduled, default=attended): ").strip() or "attended"
        notes = input("Notes (blank=none): ").strip() or None
        rec_by = (auth.current_user.get("username") if auth and getattr(auth, "current_user", None) else None)
        sid = svc.record_session(iid, date,
                                 duration_minutes=int(dur) if dur else None,
                                 status=status, notes=notes, recorded_by=rec_by)
        print(f"Session #{sid} recorded.")
    except (InterventionOutcomesError, ValueError) as exc:
        print(f"Error: {exc}")


def _set_outcome(svc: InterventionOutcomesService) -> None:
    try:
        iid = int(input("Intervention ID: ").strip())
        post = float(input("Post-assessment score: ").strip())
        date = input("Post-assessment date YYYY-MM-DD (blank=today): ").strip() or None
        notes = input("Impact notes (blank=none): ").strip() or None
        out = svc.set_outcome(iid, post, post_assessment_date=date, impact_notes=notes)
        va = out.get("value_added")
        print(f"Outcome recorded. Value-added: {va if va is not None else '(no baseline)'}")
    except (InterventionOutcomesError, ValueError) as exc:
        print(f"Error: {exc}")


def _view_record(svc: InterventionOutcomesService) -> None:
    try:
        iid = int(input("Intervention ID: ").strip())
        rec = svc.get_full_record(iid)
    except (InterventionOutcomesError, ValueError) as exc:
        print(f"Error: {exc}")
        return
    iv = rec["intervention"]
    out = rec["outcome"]
    print(f"\nIntervention #{iv.get('intervention_id')}  student={iv.get('student_id')}  "
          f"type={iv.get('intervention_type')}  status={iv.get('status')}")
    if out:
        print(f"  Subject:    {out.get('subject_area','-')}")
        print(f"  Sessions:   {out.get('sessions_completed', 0)}/{out.get('sessions_total', 0)}")
        print(f"  Pre score:  {out.get('pre_assessment_score','-')} ({out.get('pre_assessment_date','-')})")
        print(f"  Post score: {out.get('post_assessment_score','-')} ({out.get('post_assessment_date','-')})")
        print(f"  Value-added:{out.get('value_added','-')}")
        if out.get("impact_notes"):
            print(f"  Notes: {out['impact_notes']}")
    else:
        print("  (no outcome row yet)")
    sessions = rec["sessions"]
    if sessions:
        print(f"\n  Sessions ({len(sessions)}):")
        for s in sessions:
            print(f"    {s.get('session_date','-')}  {s.get('status','-'):<11} "
                  f"{(str(s.get('duration_minutes') or '-') + ' min'):<8}  "
                  f"{(s.get('notes') or '')[:40]}")


def _list_with_outcomes(svc: InterventionOutcomesService) -> None:
    sid = input("Student ID filter (Enter for all): ").strip() or None
    only = input("Only with outcome row? (y/n, default=n): ").strip().lower() == "y"
    try:
        rows = svc.list_with_outcomes(student_id=sid, only_with_outcome=only)
    except InterventionOutcomesError as exc:
        print(f"Error: {exc}")
        return
    if not rows:
        print("None found.")
        return
    print(f"\n{'ID':<5} {'Student':<10} {'Type':<18} {'Subject':<12} "
          f"{'Sess':<8} {'Pre':>6} {'Post':>6} {'VA':>6} {'Status':<10}")
    print("-" * 90)
    for r in rows:
        sess = f"{r.get('sessions_completed') or 0}/{r.get('sessions_total') or 0}"
        print(f"{r['intervention_id']:<5} "
              f"{(r.get('student_id') or '-')[:10]:<10} "
              f"{(r.get('intervention_type') or '-')[:18]:<18} "
              f"{(r.get('subject_area') or '-')[:12]:<12} "
              f"{sess:<8} "
              f"{(r.get('pre_assessment_score') if r.get('pre_assessment_score') is not None else '-'):>6} "
              f"{(r.get('post_assessment_score') if r.get('post_assessment_score') is not None else '-'):>6} "
              f"{(r.get('value_added') if r.get('value_added') is not None else '-'):>6} "
              f"{(r.get('status') or '-'):<10}")
    print(f"\nTotal: {len(rows)}")


def _summary(svc: InterventionOutcomesService) -> None:
    sid = input("Student ID filter (Enter for all): ").strip() or None
    s = svc.summary(student_id=sid)
    print("\nIntervention Outcomes Summary")
    print(f"  Interventions:           {s.get('interventions', 0)}")
    print(f"  With baseline:           {s.get('with_baseline', 0)}")
    print(f"  With outcome:            {s.get('with_outcome', 0)}")
    print(f"  Positive value-added:    {s.get('positive_value_added', 0)}")
    avg = s.get("avg_value_added")
    print(f"  Average value-added:     {avg if avg is not None else 'n/a'}")
    print(f"  Sessions completed:      {s.get('total_sessions_completed', 0)}"
          f" / {s.get('total_sessions_planned', 0)}")


def display_intervention_outcomes_menu() -> None:
    if not _require_login():
        return
    db_path = getattr(auth, "_db_path", None)
    svc = InterventionOutcomesService(db_path)

    actions = {
        "1": ("Set Baseline (Pre-Score)",  _set_baseline),
        "2": ("Record Session",            _record_session),
        "3": ("Set Outcome (Post-Score)",  _set_outcome),
        "4": ("View Full Record",          _view_record),
        "5": ("List Interventions w/ Outcomes", _list_with_outcomes),
        "6": ("Outcomes Summary",          _summary),
    }
    while True:
        print("\nIntervention Outcomes")
        print("=" * 30)
        for k, (label, _) in actions.items():
            print(f"{k}. {label}")
        print("0. Return to Previous Menu")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        action = actions.get(choice)
        if not action:
            print("Invalid choice.")
            continue
        try:
            action[1](svc)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except InterventionOutcomesError as exc:
            print(f"Error: {exc}")
