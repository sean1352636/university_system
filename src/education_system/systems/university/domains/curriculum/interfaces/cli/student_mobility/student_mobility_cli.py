"""Student mobility (study abroad / exchange) CLI."""

from __future__ import annotations


def _print_table(rows, columns) -> None:
    """columns is a sequence of (heading, key, width)."""
    if not rows:
        print("\n  (none)")
        return
    header = " ".join(f"{h:<{w}}" for h, _, w in columns)
    print("\n" + header)
    print("-" * len(header))
    for r in rows:
        print(" ".join(f"{str(r.get(k, '') if r.get(k) is not None else ''):<{w}}"[:w].ljust(w)
                       for _, k, w in columns))


def _choose(prompt: str, options) -> str | None:
    print("  " + ", ".join(f"{i + 1}={o}" for i, o in enumerate(options)))
    raw = input(f"{prompt} (Enter to skip): ").strip()
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return None


def display_student_mobility_menu(auth=None):
    from education_system.systems.university.domains.curriculum.domain.student_mobility._db_init import (
        DIRECTIONS, FUNDING_SCHEMES, MOBILITY_TYPES, PLACEMENT_STATUSES,
        RECOGNITION_MODES,
    )
    from education_system.systems.university.domains.curriculum.domain.student_mobility.services.student_mobility_service import (
        MobilityError, StudentMobilityService,
    )

    service = StudentMobilityService()

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("STUDY ABROAD & EXCHANGE".center(70))
        print("=" * 70)
        try:
            s = service.summary()
            print(f"\n  {s['agreements']} agreements · {s['outgoing']} outgoing · "
                  f"{s['incoming']} incoming · {s['away_now']} away now")
            if s["awaiting_recognition"]:
                print(f"  ⚠ {s['awaiting_recognition']} placement(s) awaiting "
                      f"credit recognition")
            if s["unsigned_agreements"]:
                print(f"  ⚠ {s['unsigned_agreements']} placement(s) without a "
                      f"signed learning agreement")
        except Exception as exc:  # noqa: BLE001
            print(f"\n  (summary unavailable: {exc})")

        print("\n  1. Exchange Agreements")
        print("  2. Add Exchange Agreement")
        print("  3. Place Availability")
        print("  4. List Placements")
        print("  5. Create Placement")
        print("  6. Change Placement Status")
        print("  7. Learning Agreement (view / add line / sign)")
        print("  8. Record Credit Recognition")
        print("  9. Awaiting Credit Recognition")
        print(" 10. Unsigned Learning Agreements")
        print(" 11. Who Is Abroad Now")
        print(" 12. Preparation Gaps (insurance / risk assessment)")
        print(" 13. Student Mobility History")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == "0":
            break

        try:
            if choice == "1":
                _print_table(service.list_agreements(active_only=False), (
                    ("ID", "mobility_agreement_id", 5),
                    ("Host", "host_institution", 32),
                    ("Country", "country", 14),
                    ("Subject", "subject_area", 20),
                    ("Out", "places_outgoing", 5),
                    ("In", "places_incoming", 5)))
            elif choice == "2":
                host = input("Host institution: ").strip()
                country = input("Country: ").strip() or None
                subject = input("Subject area: ").strip() or None
                mtype = _choose("Mobility type", MOBILITY_TYPES)
                out = input("Outgoing places [0]: ").strip() or "0"
                inc = input("Incoming places [0]: ").strip() or "0"
                valid_to = input("Valid to (YYYY-MM-DD): ").strip() or None
                aid = service.add_agreement(
                    host, country=country, subject_area=subject,
                    mobility_type=mtype,
                    places_outgoing=int(out) if out.isdigit() else 0,
                    places_incoming=int(inc) if inc.isdigit() else 0,
                    valid_to=valid_to)
                print(f"\n  Agreement added with ID {aid}.")
            elif choice == "3":
                direction = _choose("Direction", DIRECTIONS) or "outgoing"
                rows = service.place_availability(direction)
                _print_table(rows, (
                    ("ID", "mobility_agreement_id", 5),
                    ("Host", "host_institution", 32),
                    ("Country", "country", 14),
                    ("Places", "places", 7),
                    ("Taken", "taken", 6),
                    ("Left", "remaining", 6)))
                over = [r for r in rows if r["over_subscribed"]]
                if over:
                    print(f"\n  ⚠ {len(over)} agreement(s) over-subscribed.")
            elif choice == "4":
                status = _choose("Filter by status", PLACEMENT_STATUSES)
                _print_table(service.list_placements(status=status), (
                    ("ID", "placement_id", 5),
                    ("Student", "student_id", 12),
                    ("Dir", "direction", 9),
                    ("Host", "host_institution", 28),
                    ("Start", "start_date", 11),
                    ("End", "end_date", 11),
                    ("Status", "status", 16),
                    ("Cr", "credits_recognised", 5)))
            elif choice == "5":
                student = input("Student ID: ").strip()
                direction = _choose("Direction", DIRECTIONS) or "outgoing"
                aid = input("Exchange agreement ID (Enter for none): ").strip()
                host = ""
                if not aid:
                    host = input("Host institution: ").strip()
                country = input("Host country: ").strip() or None
                year = input("Academic year (e.g. 2026/27): ").strip() or None
                start = input("Start date (YYYY-MM-DD): ").strip() or None
                end = input("End date (YYYY-MM-DD): ").strip() or None
                funding = _choose("Funding scheme", FUNDING_SCHEMES)
                credits = input("Credits expected: ").strip()
                mode = _choose("Recognition mode", RECOGNITION_MODES)
                pid = service.create_placement(
                    student, host_institution=host or None, direction=direction,
                    mobility_agreement_id=int(aid) if aid.isdigit() else None,
                    host_country=country, academic_year=year, start_date=start,
                    end_date=end, funding_scheme=funding,
                    credits_expected=float(credits) if credits else None,
                    recognition_mode=mode)
                print(f"\n  Placement created with ID {pid}.")
            elif choice == "6":
                pid = int(input("Placement ID: ").strip())
                status = _choose("New status", PLACEMENT_STATUSES)
                if status:
                    service.set_status(pid, status)
                    print("\n  Status updated.")
            elif choice == "7":
                pid = int(input("Placement ID: ").strip())
                _print_table(service.list_learning_agreement(pid), (
                    ("Line", "line_id", 5),
                    ("Host module", "host_module_title", 30),
                    ("Host cr", "host_credits", 8),
                    ("Home module", "home_module_code", 14),
                    ("Home cr", "home_credits", 8),
                    ("State", "state", 22)))
                sub = input("\n(a)dd line, (s)ign all, Enter to go back: ").strip().lower()
                if sub == "a":
                    title = input("Host module title: ").strip()
                    code = input("Host module code: ").strip() or None
                    hcr = input("Host credits: ").strip()
                    home_code = input("Home module code: ").strip() or None
                    home_cr = input("Home credits: ").strip()
                    service.add_learning_agreement_line(
                        pid, title, host_module_code=code,
                        host_credits=float(hcr) if hcr else None,
                        home_module_code=home_code,
                        home_credits=float(home_cr) if home_cr else None)
                    print("  Line added.")
                elif sub == "s":
                    home = input("Approved by (home): ").strip() or None
                    host_sig = input("Approved by (host): ").strip() or None
                    n = service.sign_learning_agreement(
                        pid, approved_by_home=home, approved_by_host=host_sig)
                    print(f"  {n} line(s) signed.")
            elif choice == "8":
                pid = int(input("Placement ID: ").strip())
                host_code = input("Host module code: ").strip() or None
                grade = input("Host grade: ").strip() or None
                hcr = input("Host credits: ").strip()
                home_code = input("Home module code: ").strip() or None
                home_cr = input("Home credits awarded: ").strip()
                mode = _choose("Recognition mode", RECOGNITION_MODES)
                service.record_recognition(
                    pid, host_module_code=host_code, host_grade=grade,
                    host_credits=float(hcr) if hcr else None,
                    home_module_code=home_code,
                    home_credits=float(home_cr) if home_cr else None,
                    mode=mode)
                print("\n  Recognition recorded.")
                print("  " + str(service.credit_shortfall(pid)))
            elif choice == "9":
                days = input("Ended more than N days ago [60]: ").strip() or "60"
                _print_table(service.awaiting_recognition(int(days)), (
                    ("ID", "placement_id", 5),
                    ("Student", "student_id", 12),
                    ("Host", "host_institution", 28),
                    ("Ended", "end_date", 11),
                    ("Exp", "credits_expected", 6),
                    ("Rec", "credits_recognised", 6),
                    ("State", "recognition_state", 20)))
            elif choice == "10":
                _print_table(service.unsigned_learning_agreements(), (
                    ("ID", "placement_id", 5),
                    ("Student", "student_id", 12),
                    ("Host", "host_institution", 28),
                    ("Status", "status", 14),
                    ("Lines", "lines_total", 6),
                    ("Signed", "lines_signed", 7)))
            elif choice == "11":
                _print_table(service.currently_away(), (
                    ("ID", "placement_id", 5),
                    ("Student", "student_id", 12),
                    ("Host", "host_institution", 30),
                    ("Country", "host_country", 14),
                    ("Returns", "end_date", 11)))
            elif choice == "12":
                rows = service.preparation_gaps()
                _print_table(rows, (
                    ("ID", "placement_id", 5),
                    ("Student", "student_id", 12),
                    ("Host", "host_institution", 28),
                    ("Starts", "start_date", 11),
                    ("Insured", "insurance_confirmed", 8),
                    ("Risk", "risk_assessed", 6)))
            elif choice == "13":
                student = input("Student ID: ").strip()
                for p in service.student_history(student):
                    print(f"\n  [{p['status']}] {p['host_institution']} "
                          f"({p.get('start_date') or '?'} → "
                          f"{p.get('end_date') or '?'}) "
                          f"{p.get('credits_recognised') or 0:g}/"
                          f"{p.get('credits_expected') or 0:g} credits")
                    for line in p["learning_agreement"]:
                        print(f"      · {line['host_module_title']} "
                              f"→ {line.get('home_module_code') or '—'} "
                              f"[{line['state']}]")
        except (MobilityError, ValueError) as exc:
            print(f"\n  ✗ {exc}")

        input("\nPress Enter to continue...")
