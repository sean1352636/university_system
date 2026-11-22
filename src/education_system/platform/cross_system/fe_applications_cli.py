"""Terminal workflow for referrals into FE College (see ``fe_applications``).

Used by the Sixth Form, Apprenticeships, Adult Education and Training Provider to refer a learner, and by the
FE College to work its incoming queue.
"""

from __future__ import annotations

from education_system.platform.cross_system import fe_applications as service


def _yes(prompt: str) -> bool:
    return input(f"  {prompt} [y/N]: ").strip().lower() == "y"


def new_referral(source_system: str) -> None:
    """Refer one learner from ``source_system`` to FE College."""
    label = service.SOURCE_LABELS.get(source_system, source_system)
    print(f"\n  Refer a {label} learner to FE College")
    student_id = input({"adult_education": "  Learner ref (e.g. AE000012): ",
                        "training_provider": "  Learner ref (e.g. TP000012): "}.get(
        source_system, "  Learner ID: ")).strip()
    pathway = input("  FE course / pathway: ").strip()
    reason = input("  Reason for referral: ").strip()
    start = input("  Intended start (YYYY-MM-DD, optional): ").strip() or None
    consent = _yes("Learner consents to sharing support information?")
    try:
        row = service.refer(source_system, student_id, pathway=pathway, reason=reason,
                            intended_start=start, consent=consent)
    except Exception as exc:
        print(f"  Not referred: {exc}")
        return
    print(f"  Referred: {row['transition_id']} ({row['status']}). "
          "FE College admissions will see it in Incoming referrals.")


def dashboard(source_system: str | None = None) -> list[dict]:
    rows = service.incoming_referrals(source_system=source_system)
    print("\n  Referrals into FE College")
    print("  " + "-" * 92)
    for i, row in enumerate(rows, 1):
        src = service.SOURCE_LABELS.get(row["source_system"], row["source_system"])
        print(f"  {i:>2}. {src:<15} {row['status']:<18} {row.get('reason') or ''}")
    if not rows:
        print("  No open referrals.")
    return rows


def work_queue(actor: str = "FE admissions") -> None:
    """FE College: accept and enrol incoming referrals."""
    while True:
        rows = dashboard()
        if not rows:
            return
        pick = input("\n  Number to work on (Enter to go back): ").strip()
        if not pick.isdigit() or not 0 < int(pick) <= len(rows):
            return
        row = rows[int(pick) - 1]
        tid = row["transition_id"]
        try:
            if row["status"] == "offered":
                consent = _yes("Learner consents to sharing support information?")
                service.accept_referral(tid, accepted_by=actor, consent=consent)
                print("  Offer accepted and handover approved.")
            elif row["status"] == "handover_approved":
                src = service.SOURCE_LABELS.get(row["source_system"], "the source")
                concurrent = _yes(f"Keep the learner enrolled at {src} as well (dual enrolment)?")
                service.enrol_referral(tid, concurrent=concurrent)
                print("  Enrolled at FE College.")
            else:
                print(f"  Nothing to do while it is {row['status']}.")
        except Exception as exc:
            print(f"  Error: {exc}")


__all__ = ["new_referral", "dashboard", "work_queue"]
