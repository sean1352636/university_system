"""Shared terminal dashboard for college-to-University applications."""

from __future__ import annotations

from datetime import date

from education_system.platform.cross_system import university_applications as service


def dashboard(source_system: str) -> None:
    rows = service.list_applications(source_system=source_system)
    print("\n  University applications")
    print("  " + "-" * 100)
    print(f"  {'Application':<12} {'Progress':<34} {'University status':<22} {'Created':<20}")
    for row in rows:
        # "Unavailable" is not "—": one says the university could not be
        # read, the other that this learner has no record there.
        status = ("Unavailable" if row.get("university_lookup_failed")
                  else str(row.get("university_status") or "—"))
        print(f"  {str(row.get('university_application_id') or '—'):<12} "
              f"{row['application_status']:<34} "
              f"{status:<22} "
              f"{str(row.get('initiated_at') or '—'):<20}")
    if not rows:
        print("  No applications.")
    if any(r.get("university_lookup_failed") for r in rows):
        print("\n  ! The university's admissions database could not be read — "
              "the statuses above are unknown, not absent.")


def create(source_system: str, *, actor: str | None = None) -> None:
    student = input("  College learner ID: ").strip()
    ucas = input("  UCAS personal ID (10 digits): ").strip()
    default_year = str(date.today().year + 1)

    # UCAS is a five-choice scheme; collecting one made the college
    # re-enter the learner's application rather than record it.
    choices = []
    print(f"  Course choices, in order — blank university ends the list "
          f"(up to {service.MAX_CHOICES}):")
    for rank in range(1, service.MAX_CHOICES + 1):
        university = input(f"    {rank}. University: ").strip()
        if not university:
            break
        choices.append({
            "university": university,
            "course_code": input("       Course code: ").strip(),
            "course_name": input("       Course name: ").strip(),
            "entry_year": input(f"       Entry year [{default_year}]: ").strip()
                          or default_year,
            "rank": rank,
        })

    predicted = input("  Predicted qualifications: ").strip()
    achieved = input("  Achieved qualifications: ").strip()
    statement = input("  Personal statement/reference note: ").strip()

    # The consent record has to name a person and a date, or it documents
    # nothing that can be checked later.
    if input("  Has the learner consented to this handover? [y/N]: ").lower() != "y":
        print("  No consent recorded — nothing submitted.")
        return
    recorded_by = (actor or "").strip() or input("  Consent recorded by: ").strip()
    sensitive = input(
        "  Does that consent cover the reference and support detail? [y/N]: "
    ).lower() == "y"
    scope = ("reference", "support_indicators") if sensitive else ()

    fields = {
        "ucas_application": {"ucas_id": ucas, "status": "Submitted"},
        "choices": choices,
        "handover_consent": service.consent_record(
            recorded_by=recorded_by, scope=scope, ucas_id=ucas or None,
            method="confirmed with the learner before submission"),
        "predicted_qualifications": predicted or None,
        "achieved_qualifications": achieved or None,
        "personal_statement": statement or None,
        "consent": bool(scope),
    }
    preview = service.preview(source_system, student, **fields)
    print("  Included: " + ", ".join(preview.included))
    if preview.withheld_no_consent:
        print("  Withheld: " + ", ".join(preview.withheld_no_consent))
    if preview.missing_required:
        print("  Missing: " + ", ".join(preview.missing_required))
        print("  Not submitted.")
        return
    if input("  Submit application? [y/N]: ").lower() != "y":
        return
    result = service.submit(source_system, student, **fields)
    print(f"  Submitted — {result['application_status']}")


__all__ = ["dashboard", "create"]
