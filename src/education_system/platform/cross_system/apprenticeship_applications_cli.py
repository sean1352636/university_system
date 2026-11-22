"""Reusable terminal workflow for college apprenticeship applications."""

from __future__ import annotations

from education_system.platform.cross_system import apprenticeship_applications as service


def dashboard(source_system: str) -> None:
    rows = service.list_applications(source_system=source_system)
    print("\n  Apprenticeship progression applications")
    print("  " + "-" * 92)
    print(f"  {'Transition':<38} {'Status':<27} {'Created':<20}")
    for row in rows:
        print(f"  {row['transition_id']:<38} "
              f"{row['application_status']:<27} "
              f"{(row.get('initiated_at') or '—'):<20}")
    if not rows:
        print("  No applications.")


def new_application(source_system: str) -> None:
    print("\n  Progress learner to apprenticeship")
    student_id = input("  Learner ref (e.g. TP000012): " if source_system == "training_provider"
                       else "  College learner ID: ").strip()
    title = input("  Intended programme / standard: ").strip()
    level = input("  Level: ").strip()
    eligibility = input("  Eligibility evidence: ").strip()
    attainment = input("  Prior attainment / English and maths: ").strip()
    careers = input("  Career interest: ").strip()
    vacancy = input("  Preferred vacancy (optional): ").strip()
    employer = input("  Preferred employer (optional): ").strip()
    consent = input("  Consent to SEND/support transfer? [y/N]: ").strip().lower() == "y"
    reason = input("  Reason [Apprenticeship progression]: ").strip() \
        or "Apprenticeship progression"
    fields = {
        "intended_programme": {"title": title, "level": level},
        "eligibility_evidence": eligibility,
        "prior_attainment": attainment,
        "careers_record": careers or None,
        "preferred_vacancy": vacancy or None,
        "employer_details": employer or None,
        "consent": consent,
    }
    preview = service.preview(source_system, student_id, **fields)
    print("\n  Included: " + ", ".join(preview.included))
    print("  Withheld (no consent): "
          + (", ".join(preview.withheld_no_consent) or "none"))
    print("  Restricted: " + (", ".join(preview.withheld_restricted) or "none"))
    if preview.missing_required:
        print("  Cannot submit; missing: " + ", ".join(preview.missing_required))
        return
    if input("  Submit and create Applicant? [y/N]: ").strip().lower() != "y":
        print("  Cancelled.")
        return
    result = service.submit(source_system, student_id, reason=reason, **fields)
    print(f"  Submitted: {result['transition_id']} — {result['application_status']}")


def menu(source_system: str) -> None:
    while True:
        print("\n  1) Application dashboard")
        print("  2) Progress learner to apprenticeship")
        print("  0) Back")
        choice = input("  Select: ").strip()
        if choice == "0":
            return
        try:
            if choice == "1":
                dashboard(source_system)
            elif choice == "2":
                new_application(source_system)
            else:
                print("  Invalid selection.")
        except Exception as exc:
            print(f"  Error: {exc}")


def run(*, db_path: str | None = None, auth=None, source_system: str = "university") -> None:
    """Entry point for the university CLI's cross-system tools.

    Those tools are all called as ``run(db_path=, auth=)``, so this adapts
    that shape to :func:`menu`. The colleges call ``menu(source)`` directly.
    """
    menu(source_system)


__all__ = ["dashboard", "new_application", "menu", "run"]
