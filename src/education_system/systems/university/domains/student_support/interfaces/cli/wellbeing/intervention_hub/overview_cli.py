"""Console Student Overview — one student's support case, Early Warning
interventions, risk, coaching/tutoring and outcomes, with the actions
that link a support case to Early Warning. The CLI side of the window's
Student Overview tab, over ``early_warning.case_links``.
"""
from __future__ import annotations

from typing import Any, Optional

from education_system.systems.university.domains.student_support.domain.early_warning import (
    case_links,
)
from education_system.systems.university.domains.student_support.domain.wellbeing.student_wellbeing.services.intervention_records import (
    InterventionRecordsError, InterventionRecordsService,
)


def _pick(label: str, options: tuple[str, ...], default: str) -> str:
    print(f"{label}:")
    for i, opt in enumerate(options, start=1):
        print(f"  {i}. {opt}")
    raw = input(f"Choose [{default}]: ").strip()
    if not raw:
        return default
    if raw.isdigit() and 1 <= int(raw) <= len(options):
        return options[int(raw) - 1]
    return raw if raw in options else default


def _find_student() -> Optional[str]:
    """Search by ID or name; returns a student ID."""
    text = input("Student ID or name (Enter to cancel): ").strip().lower()
    if not text:
        return None
    matches = [c for c in case_links.student_choices() if text in c["label"].lower()]
    if not matches:
        print("No matching student or support case.")
        return None
    exact = next((c for c in matches if c["student_id"].lower() == text), None)
    if exact:
        return exact["student_id"]
    for i, c in enumerate(matches[:20], start=1):
        print(f"  {i}. {c['label']}")
    if len(matches) > 20:
        print(f"  ... {len(matches) - 20} more — type more of the name to narrow it.")
    raw = input("Number: ").strip()
    if raw.isdigit() and 1 <= int(raw) <= min(len(matches), 20):
        return matches[int(raw) - 1]["student_id"]
    return None


def _day(value: Any) -> str:
    return str(value or "")[:10]


def _print_overview(ov: dict) -> None:
    stu, case, p = ov["student"], ov["case"], ov["profile"]
    name = (f"{stu.get('first_name') or ''} {stu.get('last_name') or ''}".strip() if stu
            else (case or {}).get("name") or "")
    print("\n" + "=" * 70)
    print(f" {name}  ({ov['student_id']})")
    print("=" * 70)
    if not ov["is_student"]:
        print(" ⚠ Not a student record — Early Warning can't link to it.")

    print("\n-- Support Case --")
    if case:
        print(f"  Risk: {case.get('risk')}   Status: {case.get('status')}   "
              f"Intervention: {case.get('intervention')}   Last contact: {case.get('last_contact') or '-'}")
        print("  " + (case.get("notes") or "(no notes)").replace("\n", "\n  "))
    else:
        print("  No support case.")

    print("\n-- Early Warning Interventions --")
    if ov["interventions"]:
        print(f"  {'ID':<5} {'Type':<15} {'Priority':<9} {'Status':<10} {'Created':<10} "
              f"{'Outcome':<20} {'VA':>6}")
        for i in ov["interventions"]:
            va = (ov["outcomes"].get(i["intervention_id"]) or {}).get("value_added")
            print(f"  {i['intervention_id']:<5} {str(i.get('intervention_type'))[:15]:<15} "
                  f"{str(i.get('priority'))[:9]:<9} {str(i.get('status'))[:10]:<10} "
                  f"{_day(i.get('created_at')):<10} {str(i.get('outcome') or '-')[:20]:<20} "
                  f"{va if va is not None else '-':>6}")
    else:
        print("  None.")

    print("\n-- Risk & Indicators --")
    if p:
        print(f"  Overall {p.get('overall_risk_score')} ({p.get('risk_level')}) — "
              f"academic {p.get('academic_risk_score')}, attendance {p.get('attendance_risk_score')}, "
              f"engagement {p.get('engagement_risk_score')}, financial {p.get('financial_risk_score')}")
    else:
        print("  No risk profile.")
    for ind in ov["indicators"][:10]:
        print(f"  #{ind['indicator_id']} {ind.get('indicator_type')}: {ind.get('indicator_value')} "
              f"[{ind.get('severity')}] {'resolved' if ind.get('is_resolved') else 'open'}")

    print("\n-- Coaching & Tutoring --")
    for a in ov["coaching"]:
        print(f"  Coach {a.get('coach_name')} ({a.get('meeting_frequency')}, {a.get('status')})")
    for r in ov["tutoring"]:
        print(f"  Tutoring #{r['recommendation_id']} {r.get('module_code')} "
              f"{r.get('recommendation_type')} — {r.get('status')}")
    if not ov["coaching"] and not ov["tutoring"]:
        print("  None.")

    s = ov["outcome_summary"]
    if s:
        avg = s.get("avg_value_added")
        print("\n-- Outcomes --")
        print(f"  With baseline {s.get('with_baseline', 0)}, with outcome {s.get('with_outcome', 0)}, "
              f"positive value-added {s.get('positive_value_added', 0)}, "
              f"average {avg if avg is not None else 'n/a'}")


def _raise(student_id: str, case: Optional[dict], actor: str) -> None:
    d = case_links.suggest_intervention(case)
    iid = case_links.raise_intervention(
        student_id,
        trigger_type=_pick("Trigger", case_links.TRIGGER_TYPES, d["trigger_type"]),
        intervention_type=_pick("Type", case_links.INTERVENTION_TYPES, d["intervention_type"]),
        priority=_pick("Priority", case_links.PRIORITIES, d["priority"]),
        description=input(f"Description [{d['description']}]: ").strip() or d["description"],
        assigned_to=input("Assigned to (blank=none): ").strip(),
        actor=actor,
    )
    print(f"Intervention #{iid} raised" + (" and noted on the support case." if case else "."))


def _complete(actor: str) -> None:
    raw = input("Intervention ID: ").strip()
    if not raw.isdigit():
        print("Please enter a number.")
        return
    case_links.complete_intervention(
        int(raw), _pick("Outcome", case_links.OUTCOMES, "successful"),
        input("Notes: ").strip(), actor=actor)
    print(f"Intervention #{raw} completed.")


def display_student_overview_menu(auth: Any) -> None:
    user = getattr(auth, "current_user", None) if auth else None
    if not user:
        print("You must be logged in to use the Student Overview.")
        return
    actor = user.get("username") or user.get("email") or str(user.get("id") or "")

    student_id = _find_student()
    while student_id:
        ov = case_links.student_overview(student_id)
        _print_overview(ov)
        print("\n1. Raise Early Warning Intervention")
        print("2. Complete an Intervention")
        print("3. Create Support Case (from student record)" if not ov["case"]
              else "3. Log Contact on Support Case")
        print("4. Choose Another Student")
        print("0. Back")
        choice = input("\nEnter your choice: ").strip()
        try:
            if choice == "0":
                return
            if choice == "1":
                _raise(student_id, ov["case"], actor)
            elif choice == "2":
                _complete(actor)
            elif choice == "3":
                records = InterventionRecordsService(actor=actor)
                if ov["case"]:
                    records.log_contact(student_id)
                    print("Contact has been logged.")
                else:
                    records.add(case_links.case_from_student(student_id))
                    print("Support case created from the student record and risk profile.")
            elif choice == "4":
                student_id = _find_student() or student_id
            else:
                print("Invalid choice.")
        except (case_links.CaseLinkError, InterventionRecordsError) as exc:
            print(f"Error: {exc}")
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as exc:
            print(f"Error: {exc}")
