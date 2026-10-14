"""Terminal interface for parallel Year 11 destination applications."""

from __future__ import annotations

from datetime import date

from education_system.platform.cross_system import secondary_post16 as service


def dashboard() -> None:
    rows = service.list_applications()
    print("\n  Post-16 Destinations")
    print(f"  {'Pupil':<12} {'Destination':<18} {'Programme':<28} {'Stage':<26} Confirmed")
    for row in rows:
        print(f"  {row['pupil_id']:<12} {row['destination_system']:<18} "
              f"{str(row.get('programme_label') or '—')[:28]:<28} "
              f"{row['stage']:<26} {'yes' if row['confirmed'] else 'no'}")
    if not rows:
        print("  No applications.")


def create() -> None:
    pupil = input("  Pupil ID: ").strip()
    destination = input("  Destination (sixth_form/fe_college/apprenticeships): ").strip()
    institution = input("  Institution / employer: ").strip()
    programme = input("  Course, comma-separated subjects, or standard: ").strip()
    level = input("  Level: ").strip()
    predicted = input("  Predicted GCSE grades: ").strip()
    achieved = input("  Achieved GCSE results: ").strip()
    attainment = input("  English, maths and prior attainment: ").strip()
    careers = input("  Career intention: ").strip()
    consent = input("  Consent to SEND/support transfer? [y/N]: ").lower() == "y"
    fields = {
        "predicted_grades": predicted, "achieved_gcse_results": achieved or None,
        "prior_attainment": attainment, "careers_intentions": careers or None,
        "consent_record": {"reference": f"POST16-{pupil}",
                           "recorded_at": date.today().isoformat()},
        "consent": consent,
    }
    if destination == "sixth_form":
        fields["subjects"] = [part.strip() for part in programme.split(",")]
    elif destination == "fe_college":
        fields["course_request"] = {"course": programme, "level": level,
                                    "campus": institution}
    elif destination == "apprenticeships":
        fields["intended_programme"] = {"title": programme, "level": level}
        fields["eligibility_evidence"] = input("  Eligibility evidence: ").strip()
        fields["preferred_vacancy"] = institution or None
    result = service.preview(pupil, destination, **fields)
    print("  Included: " + ", ".join(result.included))
    if result.missing_required:
        print("  Missing: " + ", ".join(result.missing_required))
        return
    if input("  Submit? [y/N]: ").lower() == "y":
        service.submit(pupil, destination, destination_label=institution,
                       programme_label=programme, **fields)


def menu() -> None:
    while True:
        print("\n  1) Application dashboard\n  2) Add destination\n  0) Back")
        choice = input("  Select: ").strip()
        if choice == "0":
            return
        if choice == "1":
            dashboard()
        elif choice == "2":
            create()


__all__ = ["dashboard", "create", "menu"]
