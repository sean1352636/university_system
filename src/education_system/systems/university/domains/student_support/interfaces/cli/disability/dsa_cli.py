"""DSA casework — CLI twin of the portal's DSA tab (``domain/disability/dsa``).

Disability services work every case; a student sees their own, read-only.
"""

from __future__ import annotations

from education_system.systems.university.domains.student_support.domain.disability import (
    access,
    dsa,
)


def _ask(prompt, default=""):
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


def _choose(prompt, options, default=None):
    for i, option in enumerate(options, 1):
        print(f"  {i}. {option}")
    raw = _ask(prompt, str(options.index(default) + 1) if default in options else "")
    try:
        return options[int(raw) - 1]
    except (ValueError, IndexError):
        raise ValueError("Choose one of the numbers shown.") from None


def _yes(prompt) -> bool:
    return _ask(f"{prompt} (y/n)", "n").lower().startswith("y")


def _print_case(case):
    print("\n" + "=" * 70)
    print(f"DSA case #{case['case_id']} — student {case['student_id']}")
    print(f"Funding body: {case['funding_body_label']}   Ref: {case.get('sfe_reference') or '—'}")
    print(f"Status: {case['status_label']}")
    for status, column in dsa.STATUS_DATE_COLUMN.items():
        if case.get(column):
            print(f"  {dsa.STATUS_LABELS[status]}: {case[column]}")
    if case.get("notes"):
        print(f"Notes: {case['notes']}")
    print("\nNeeds assessments:")
    for a in case["assessments"] or [{"id": None}]:
        if a["id"] is None:
            print("  none")
            break
        attended = {1: "attended", 0: "did not attend"}.get(a.get("attended"), "")
        print(f"  #{a['id']} {a['assessment_date']} {a.get('assessment_time') or ''} "
              f"{a.get('assessor') or ''} @ {a.get('centre') or ''} {attended}")
    print("\nRecommendations:")
    for r in case["recommendations"]:
        print(f"  #{r['id']} [{dsa.CATEGORY_LABELS.get(r['category'])}] {r['recommendation']} "
              f"— {r['status']}{' (adjustment #' + str(r['accommodation_id']) + ')' if r['accommodation_id'] else ''}")
    print("\nNon-medical help:")
    for s in case["nmh"]:
        flag = "  ** OVER ALLOCATION **" if s["over_allocation"] else ""
        print(f"  #{s['id']} {s['support_type']} — {s.get('worker_name') or ''} "
              f"{s.get('agency') or ''}: {s['hours_used']}/{s['hours_allocated']} h used, "
              f"{s['hours_remaining']} left ({s['status']}){flag}")
    print("\nEquipment:")
    for e in case["equipment"]:
        print(f"  #{e['id']} {e['item']} ({e.get('supplier') or '—'}) — {e['status']}")
    print("\nExam access arrangements:")
    for x in case["exam_arrangements"]:
        print(f"  #{x['id']} {dsa.arrangement_text(x)} [{x['status']}] "
              f"{x.get('valid_from') or ''}–{x.get('valid_to') or ''}")
    print("\nAdjustments (✔ = linked to this case):")
    for a in case["adjustments"]:
        print(f"  {'✔' if a['linked'] else ' '} #{a['id']} {a['accommodation_type']} — {a['status']}")
    print("=" * 70)


def run(auth):
    """The DSA menu: staff casework, or the student's own case."""
    try:
        staff = access.scope(auth) is None
    except PermissionError as exc:
        print(f"\n❌ {exc}")
        return
    if not staff:
        _student(auth)
        return
    while True:
        print("\n" + "=" * 50)
        print("  DISABLED STUDENTS' ALLOWANCES (DSA)")
        print("=" * 50)
        try:
            stats = dsa.statistics(auth)
            print(f"  Open cases: {stats['open']}   NMH over allocation: "
                  f"{stats['nmh_over_allocation']}")
        except Exception as exc:
            print(f"  ({exc})")
        print("1. List cases\n2. Open a new case\n3. Work on a case\n0. Back")
        choice = input("\nEnter your choice: ").strip()
        try:
            if choice == "1":
                for c in dsa.list_cases(auth, include_closed=_yes("Include closed")):
                    print(f"  #{c['case_id']} {c['student_id']} {c['student_name']:<25} "
                          f"{c['funding_body']:<5} {c['status_label']}")
            elif choice == "2":
                cid = dsa.open_case(
                    auth, _ask("Student number"),
                    funding_body=_choose("Funding body", list(dsa.FUNDING_BODIES), "SFE"),
                    sfe_reference=_ask("Funding body reference (optional)"),
                    notes=_ask("Notes (optional)"))
                print(f"✅ Case #{cid} opened.")
            elif choice == "3":
                _work(auth, int(_ask("Case number")))
            elif choice == "0":
                return
            else:
                print("❌ Invalid choice.")
        except (PermissionError, ValueError) as exc:
            print(f"❌ {exc}")
        except KeyboardInterrupt:
            return


def _student(auth):
    try:
        cases = dsa.my_cases(auth)
    except (PermissionError, ValueError) as exc:
        print(f"\n❌ {exc}")
        return
    if not cases:
        print("\nYou have no DSA case. Ask disability services about applying for "
              "Disabled Students' Allowances.")
    for c in cases:
        _print_case(dsa.case_detail(auth, c["case_id"]))
    input("\nPress Enter to continue...")


_ACTIONS = (
    "Show the case", "Move to next stage", "Edit funding body / reference / notes",
    "Book needs assessment", "Record assessment attendance", "Add recommendation",
    "Set recommendation status", "Make reasonable adjustment from a recommendation",
    "Add non-medical help", "Log NMH hours used", "End NMH support", "Add equipment",
    "Set equipment status", "Recommend exam access arrangements", "Apply exam arrangements",
    "Withdraw exam arrangements", "Link / unlink an existing adjustment",
)


def _work(auth, case_id):
    case = dsa.case_detail(auth, case_id)
    _print_case(case)
    while True:
        print(f"\nCase #{case_id}:")
        for i, label in enumerate(_ACTIONS, 1):
            print(f"  {i:>2}. {label}")
        print("   0. Back")
        choice = input("Choice: ").strip()
        if choice == "0":
            return
        try:
            _act(auth, case_id, int(choice))
        except (PermissionError, ValueError) as exc:
            print(f"❌ {exc}")
        except KeyboardInterrupt:
            return


def _act(auth, case_id, n):  # noqa: C901 - a flat menu dispatch
    if n == 1:
        _print_case(dsa.case_detail(auth, case_id))
    elif n == 2:
        case = dsa.case_detail(auth, case_id)
        labels = [dsa.STATUS_LABELS[s] for s in dsa.next_statuses(case["status"])]
        if not labels:
            raise ValueError("This case is closed.")
        label = _choose("New stage", labels)
        status = next(k for k, v in dsa.STATUS_LABELS.items() if v == label)
        dsa.set_status(auth, case_id, status, on_date=_ask("Date (blank = today)"),
                       note=_ask("Note (optional)"))
    elif n == 3:
        case = dsa.case_detail(auth, case_id)
        dsa.update_case(auth, case_id,
                        funding_body=_choose("Funding body", list(dsa.FUNDING_BODIES),
                                             case["funding_body"]),
                        sfe_reference=_ask("Reference", case.get("sfe_reference") or ""),
                        notes=_ask("Notes", case.get("notes") or ""))
    elif n == 4:
        dsa.book_assessment(auth, case_id, assessment_date=_ask("Date (YYYY-MM-DD)"),
                            assessment_time=_ask("Time (HH:MM)"), centre=_ask("Centre"),
                            assessor=_ask("Assessor"),
                            mode=_choose("Mode", ["in person", "remote (video)", "telephone"],
                                         "in person"), notes=_ask("Notes (optional)"))
    elif n == 5:
        dsa.record_attendance(auth, int(_ask("Assessment #")), _yes("Attended"))
    elif n == 6:
        label = _choose("Category", [dsa.CATEGORY_LABELS[c] for c in dsa.CATEGORIES])
        category = next(k for k, v in dsa.CATEGORY_LABELS.items() if v == label)
        dsa.add_recommendation(auth, case_id, category, _ask("Recommendation"))
    elif n == 7:
        dsa.set_recommendation_status(auth, int(_ask("Recommendation #")),
                                      _choose("Status", list(dsa.RECOMMENDATION_STATUSES)))
    elif n == 8:
        from education_system.systems.university.domains.student_support.domain.disability import (
            portal,
        )
        acc = dsa.adjustment_from_recommendation(
            auth, int(_ask("Recommendation #")),
            _choose("Type of adjustment", list(portal.ACCOMMODATION_TYPES)),
            description=_ask("Description (blank = the recommendation)") or None,
            start_date=_ask("Start (blank = today)"), end_date=_ask("End (optional)"))
        print(f"✅ Adjustment #{acc} approved and applied.")
    elif n == 9:
        dsa.add_nmh_support(auth, case_id,
                            support_type=_choose("Type", list(dsa.NMH_TYPES)),
                            hours_allocated=_ask("Hours allocated"),
                            worker_name=_ask("Support worker"), agency=_ask("Agency"),
                            band=_ask("Band (e.g. Band 3)"), start_date=_ask("Start date"),
                            end_date=_ask("End date"))
    elif n == 10:
        result = dsa.log_hours(auth, int(_ask("Support #")), session_date=_ask("Session date"),
                               hours=_ask("Hours"), notes=_ask("Notes"))
        print(f"✅ Logged. Used {result['used']} h, {result['remaining']} h left.")
        if result["over"]:
            print("⚠️  Over the allocation — ask the funding body to approve more hours.")
    elif n == 11:
        dsa.end_nmh_support(auth, int(_ask("Support #")))
    elif n == 12:
        dsa.add_equipment(auth, case_id, _ask("Item"), supplier=_ask("Supplier"),
                          notes=_ask("Notes"))
    elif n == 13:
        dsa.set_equipment_status(auth, int(_ask("Equipment #")),
                                 _choose("Status", list(dsa.EQUIPMENT_STATUSES)),
                                 on_date=_ask("Date (blank = today)"))
    elif n == 14:
        dsa.recommend_exam_arrangements(
            auth, case_id, extra_percent=_ask("Extra time %", "0"),
            separate_room=_yes("Separate room"), rest_breaks=_yes("Rest breaks"),
            reader=_yes("Reader"), scribe=_yes("Scribe"),
            assistive_technology=_ask("Assistive technology (optional)"),
            other=_ask("Other (optional)"), valid_from=_ask("Valid from"),
            valid_to=_ask("Valid to"))
    elif n == 15:
        acc = dsa.apply_exam_arrangements(auth, int(_ask("Arrangement #")))
        print(f"✅ Applied as adjustment #{acc}; exams pick it up.")
    elif n == 16:
        dsa.withdraw_exam_arrangements(auth, int(_ask("Arrangement #")), _ask("Reason"))
    elif n == 17:
        dsa.link_adjustment(auth, case_id, int(_ask("Adjustment #")), linked=_yes("Link"))
    else:
        raise ValueError("Choose one of the numbers shown.")
    if n != 1:
        print("✅ Done.")
