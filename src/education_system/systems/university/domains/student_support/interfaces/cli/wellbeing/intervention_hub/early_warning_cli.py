"""Console menu for the Student Success Early Warning System.

The Early Warning area of the Interventions CLI menu. It replaces a stub
whose options only printed "Feature available via Early Warning
managers"; each area here matches a tab of the Early Warning window and
uses the same managers and queries.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from education_system.systems.university.domains.student_support.domain.early_warning import (
    early_warning_queries as queries,
)
from education_system.systems.university.domains.student_support.domain.early_warning.early_warning_core import (
    CoachingManager, IndicatorManager, InterventionManager, RiskAssessmentManager, TutoringManager,
)
from education_system.systems.university.infrastructure.i18n import get_text as _t

RISK_FILTERS = ("All", "Critical", "High", "Medium", "Low")
TRIGGER_TYPES = ("academic", "attendance", "engagement", "financial", "other")
INTERVENTION_TYPES = ("auto_email", "manual_meeting", "coaching", "tutoring", "counseling")
PRIORITIES = ("low", "medium", "high", "critical")
FREQUENCIES = ("weekly", "bi-weekly", "monthly")
OUTCOMES = ("successful", "partially_successful", "unsuccessful", "no_response")
TUTORING_TYPES = ("one-on-one", "group_tutoring", "study_group", "online_resources")
TUTORING_PRIORITIES = ("low", "medium", "high")
INDICATOR_TYPES = ("academic", "attendance", "engagement", "financial", "behavioral", "health")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

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


def _req(label: str) -> Optional[str]:
    value = input(f"{label}: ").strip()
    if not value:
        print("Cancelled — a value is required.")
        return None
    return value


def _int(label: str) -> Optional[int]:
    raw = _req(label)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        print("Please enter a number.")
        return None


def _name(row: dict) -> str:
    return f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()


def _day(value: Any) -> str:
    return str(value or "")[:10]


# ---------------------------------------------------------------------------
# At-Risk Students
# ---------------------------------------------------------------------------

def _at_risk(_user: dict) -> None:
    level = _pick("Risk level", RISK_FILTERS, "All").lower()
    students = RiskAssessmentManager.get_at_risk_students(level)
    if not students:
        print("No students found.")
        return
    print(f"\n{'Student ID':<12} {'Name':<24} {'Score':>5}  {'Level':<13} "
          f"{'Acad':>4} {'Att':>4} {'Eng':>4} {'Fin':>4}")
    print("-" * 80)
    for s in students:
        print(f"{str(s['student_id'])[:12]:<12} {_name(s)[:24]:<24} "
              f"{s.get('overall_risk_score', 0):>5}  {str(s.get('risk_level', 'unknown'))[:13]:<13} "
              f"{s.get('academic_risk_score', 0):>4} {s.get('attendance_risk_score', 0):>4} "
              f"{s.get('engagement_risk_score', 0):>4} {s.get('financial_risk_score', 0):>4}")
    print(f"\nLoaded {len(students)} students")


def _calculate_all(_user: dict) -> None:
    print("Calculating risk scores for every student...")
    print(f"Calculated risk scores for {queries.calculate_all_risks()} students")


def _calculate_one(_user: dict) -> None:
    sid = _req("Student ID")
    if sid:
        score, level = RiskAssessmentManager.calculate_risk_score(sid)
        print(f"Student {sid}\nRisk Score: {score}\nRisk Level: {level}")


def _create_intervention(_user: dict) -> None:
    sid = _req("Student ID")
    if not sid:
        return
    iid = InterventionManager.create_intervention(
        student_id=sid,
        trigger_type=_pick("Trigger type", TRIGGER_TYPES, "academic"),
        intervention_type=_pick("Intervention type", INTERVENTION_TYPES, "coaching"),
        priority=_pick("Priority", PRIORITIES, "high"),
        description=input("Description: ").strip(),
        assigned_to=input("Assigned to (blank=none): ").strip(),
    )
    print(f"Intervention #{iid} created successfully")


def _assign_coach(_user: dict) -> None:
    sid = _req("Student ID")
    if not sid:
        return
    coaches = queries.active_coaches()
    if not coaches:
        print("No active coaches available. Please register a coach first.")
        return
    print("Coaches:")
    for c in coaches:
        print(f"  {c['coach_id']}: {c['name']}")
    coach_id = _int("Coach ID")
    if coach_id is None:
        return
    CoachingManager.assign_student_to_coach(
        student_id=sid, coach_id=coach_id,
        reason=input("Reason: ").strip(),
        meeting_frequency=_pick("Meeting frequency", FREQUENCIES, "weekly"),
    )
    print("Coach assigned successfully")


def _send_alert(_user: dict) -> None:
    sid = _req("Student ID")
    if not sid:
        return
    try:
        email, sent = queries.send_support_alert(sid)
    except LookupError:
        print("Student not found")
        return
    if sent:
        print(f"Alert sent to {email}")
    else:
        print(f"Email service not available. Alert would be sent to: {email}")


# ---------------------------------------------------------------------------
# Interventions
# ---------------------------------------------------------------------------

def _list_interventions(_user: dict) -> list:
    rows = InterventionManager.get_pending_interventions()
    if not rows:
        print("No pending interventions.")
        return rows
    print(f"\n{'ID':<5} {'Student':<10} {'Name':<20} {'Type':<15} {'Priority':<9} "
          f"{'Status':<11} {'Assigned':<12} {'Created':<10} {'Scheduled':<10}")
    print("-" * 108)
    for r in rows:
        print(f"{r['intervention_id']:<5} {str(r['student_id'])[:10]:<10} {_name(r)[:20]:<20} "
              f"{str(r['intervention_type'])[:15]:<15} {str(r['priority'])[:9]:<9} "
              f"{str(r['status'])[:11]:<11} {str(r.get('assigned_to') or '')[:12]:<12} "
              f"{_day(r.get('created_at')):<10} {str(r.get('scheduled_date') or '')[:10]:<10}")
    print(f"\nLoaded {len(rows)} interventions")
    return rows


def _intervention_details(_user: dict) -> None:
    iid = _int("Intervention ID")
    if iid is None:
        return
    match = next((r for r in InterventionManager.get_pending_interventions()
                  if r["intervention_id"] == iid), None)
    if not match:
        print("Intervention not found among pending interventions.")
        return
    print(f"\nID: {match['intervention_id']}\nStudent ID: {match['student_id']}\n"
          f"Student Name: {_name(match)}\nType: {match['intervention_type']}\n"
          f"Priority: {match['priority']}\nStatus: {match['status']}\n"
          f"Assigned To: {match.get('assigned_to') or ''}\n"
          f"Created: {_day(match.get('created_at'))}\nScheduled: {match.get('scheduled_date') or ''}")
    if match.get("description"):
        print(f"Description: {match['description']}")


def _complete_intervention(_user: dict) -> None:
    iid = _int("Intervention ID")
    if iid is None:
        return
    InterventionManager.complete_intervention(
        intervention_id=iid,
        outcome=_pick("Outcome", OUTCOMES, "successful"),
        notes=input("Notes: ").strip(),
    )
    print("Intervention marked as completed")


# ---------------------------------------------------------------------------
# Success Coaching
# ---------------------------------------------------------------------------

def _list_coaches(_user: dict) -> None:
    coaches = queries.coaches_with_load()
    if not coaches:
        print("No coaches registered.")
        return
    print(f"\n{'ID':<5} {'Name':<24} {'Specialization':<24} {'Students':>9}")
    print("-" * 66)
    for c in coaches:
        print(f"{c['coach_id']:<5} {str(c['name'])[:24]:<24} {str(c['specialization'] or '')[:24]:<24} "
              f"{c['current_students']:>4}/{c['max_students']:<4}")


def _register_coach(_user: dict) -> None:
    user_id = _req("Staff user ID")
    name = _req("Name") if user_id else None
    if not name:
        return
    raw = input("Max students [30]: ").strip()
    CoachingManager.register_coach(
        user_id=user_id, name=name,
        specialization=input("Specialization: ").strip(),
        max_students=int(raw) if raw.isdigit() else 30,
    )
    print("Coach registered successfully")


def _list_assignments(_user: dict) -> None:
    rows = queries.active_coach_assignments()
    if not rows:
        print("No active coach assignments.")
        return
    print(f"\n{'Student ID':<12} {'Student':<22} {'Coach':<20} {'Frequency':<10} "
          f"{'Last Meeting':<12} {'Status':<8}")
    print("-" * 88)
    for a in rows:
        print(f"{str(a['student_id'])[:12]:<12} {_name(a)[:22]:<22} {str(a['coach_name'])[:20]:<20} "
              f"{str(a['meeting_frequency'] or '')[:10]:<10} {_day(a.get('last_meeting_date')):<12} "
              f"{str(a['status'])[:8]:<8}")


def _record_progress(_user: dict) -> None:
    sid = _req("Student ID")
    if not sid:
        return
    coach_id = queries.active_assignment_coach(sid)
    if coach_id is None:
        print("Assignment not found")
        return
    CoachingManager.record_progress(
        student_id=sid, coach_id=coach_id,
        academic_progress=input("Academic progress: ").strip(),
        attendance_progress=input("Attendance progress: ").strip(),
        engagement_progress=input("Engagement progress: ").strip(),
        goals_achieved=input("Goals achieved: ").strip(),
        concerns=input("Concerns: ").strip(),
        next_steps=input("Next steps: ").strip(),
    )
    print("Progress recorded successfully")


# ---------------------------------------------------------------------------
# Tutoring Recommendations
# ---------------------------------------------------------------------------

def _list_tutoring(_user: dict) -> None:
    rows = queries.tutoring_recommendations()
    if not rows:
        print("No tutoring recommendations.")
        return
    print(f"\n{'ID':<5} {'Student':<10} {'Name':<20} {'Module':<10} {'Type':<17} "
          f"{'Priority':<8} {'Status':<10} {'Tutor':<14} {'Created':<10}")
    print("-" * 110)
    for r in rows:
        print(f"{r['recommendation_id']:<5} {str(r['student_id'])[:10]:<10} {_name(r)[:20]:<20} "
              f"{str(r['module_code'] or '')[:10]:<10} {str(r['recommendation_type'] or '')[:17]:<17} "
              f"{str(r['priority'] or '')[:8]:<8} {str(r['status'] or '')[:10]:<10} "
              f"{str(r.get('tutor_assigned') or '')[:14]:<14} {_day(r.get('created_at')):<10}")


def _create_tutoring(user: dict) -> None:
    sid = _req("Student ID")
    module = _req("Module code") if sid else None
    if not module:
        return
    default_by = user.get("username", "system")
    TutoringManager.create_tutoring_recommendation(
        student_id=sid, module_code=module,
        recommended_by=input(f"Recommended by [{default_by}]: ").strip() or default_by,
        recommendation_type=_pick("Type", TUTORING_TYPES, "one-on-one"),
        priority=_pick("Priority", TUTORING_PRIORITIES, "medium"),
    )
    print("Tutoring recommendation created successfully")


def _assign_tutor(_user: dict) -> None:
    rid = _int("Recommendation ID")
    tutor = _req("Tutor name") if rid is not None else None
    if tutor:
        TutoringManager.assign_tutor(rid, tutor)
        print("Tutor assigned successfully")


# ---------------------------------------------------------------------------
# Risk Indicators
# ---------------------------------------------------------------------------

def _list_indicators(_user: dict) -> None:
    rows = queries.risk_indicators(500)
    if not rows:
        print("No risk indicators.")
        return
    print(f"\n{'ID':<5} {'Student':<10} {'Name':<20} {'Type':<11} {'Value':<14} "
          f"{'Severity':<8} {'Detected':<10} {'Resolved':<8} Notes")
    print("-" * 110)
    for i in rows:
        print(f"{i['indicator_id']:<5} {str(i['student_id'])[:10]:<10} {_name(i)[:20]:<20} "
              f"{str(i['indicator_type'])[:11]:<11} {str(i['indicator_value'])[:14]:<14} "
              f"{str(i['severity'])[:8]:<8} {_day(i.get('detected_at')):<10} "
              f"{'Yes' if i['is_resolved'] else 'No':<8} {str(i.get('notes') or '')[:30]}")


def _add_indicator(_user: dict) -> None:
    sid = _req("Student ID")
    if not sid:
        return
    if not any(str(s["student_id"]) == sid for s in queries.student_picker()):
        print("Student not found")
        return
    ind_type = _pick("Indicator type", INDICATOR_TYPES, "academic")
    value = _req("Indicator value")
    if not value:
        return
    IndicatorManager.add_indicator(
        student_id=sid, indicator_type=ind_type, indicator_value=value,
        severity=_pick("Severity", PRIORITIES, "medium"),
        notes=input("Notes: ").strip(),
    )
    print("Indicator added successfully")


def _resolve_indicator(_user: dict) -> None:
    iid = _int("Indicator ID")
    notes = _req("Resolution notes") if iid is not None else None
    if notes:
        IndicatorManager.resolve_indicator(iid, notes)
        print("Indicator resolved successfully")


# ---------------------------------------------------------------------------
# Menus
# ---------------------------------------------------------------------------

Action = Callable[[dict], Any]

#: (area, [(label, action)]) — one area per tab of the Early Warning window.
AREAS: tuple[tuple[str, tuple[tuple[str, Action], ...]], ...] = (
    ("At-Risk Students", (
        ("View At-Risk Students", _at_risk),
        ("Calculate All Risk Scores", _calculate_all),
        ("Calculate Risk for a Student", _calculate_one),
        ("Create Intervention", _create_intervention),
        ("Assign Success Coach", _assign_coach),
        ("Send Alert", _send_alert),
    )),
    ("Interventions", (
        ("View Pending Interventions", _list_interventions),
        ("View Intervention Details", _intervention_details),
        ("Complete Intervention", _complete_intervention),
    )),
    ("Success Coaching", (
        ("View Coaches", _list_coaches),
        ("Register Coach", _register_coach),
        ("View Coach Assignments", _list_assignments),
        ("Record Progress", _record_progress),
    )),
    ("Tutoring Recommendations", (
        ("View Recommendations", _list_tutoring),
        ("Create Recommendation", _create_tutoring),
        ("Assign Tutor", _assign_tutor),
    )),
    ("Risk Indicators", (
        ("View Indicators", _list_indicators),
        ("Add Indicator", _add_indicator),
        ("Resolve Indicator", _resolve_indicator),
    )),
)


def _run_area(title: str, actions: tuple[tuple[str, Action], ...], user: dict) -> None:
    while True:
        print(f"\n{title}")
        print("=" * 40)
        for n, (label, _) in enumerate(actions, start=1):
            print(f"{n}. {label}")
        print("0. Back")
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        if not (choice.isdigit() and 1 <= int(choice) <= len(actions)):
            print("Invalid choice.")
            continue
        try:
            actions[int(choice) - 1][1](user)
        except KeyboardInterrupt:
            print("\nCancelled.")
        except Exception as exc:
            print(f"Error: {exc}")


def display_early_warning_menu(auth: Any) -> None:
    """The Early Warning System menu (Interventions CLI, option 1)."""
    user = getattr(auth, "current_user", None) if auth else None
    if not user:
        print(_t("early_warning.errors.login_required",
                 default="You must be logged in to access the Early Warning System."))
        return
    try:
        from education_system.systems.university.infrastructure.database.schemas.attendance_warning_schemas import (
            init_early_warning_system_db,
        )
        init_early_warning_system_db()
    except Exception as exc:
        print(f"Failed to initialize database: {exc}")
        return

    language_option = str(len(AREAS) + 1)
    while True:
        print("\n" + "=" * 50)
        print(f" {_t('early_warning.cli.title', default='STUDENT SUCCESS EARLY WARNING SYSTEM')}")
        print("=" * 50)
        for n, (title, _) in enumerate(AREAS, start=1):
            print(f"{n}. {title}")
        print(f"{language_option}. {_t('early_warning.cli.menu.language', default='Language')}")
        print(f"0. {_t('early_warning.cli.menu.return_main', default='Return to Main Menu')}")
        print("=" * 50)
        choice = input("\nEnter your choice: ").strip()
        if choice == "0":
            return
        if choice == language_option:
            from education_system.systems.university.infrastructure.utils.language_selector import (
                display_language_menu_option,
            )
            display_language_menu_option()
        elif choice.isdigit() and 1 <= int(choice) <= len(AREAS):
            title, actions = AREAS[int(choice) - 1]
            _run_area(title, actions, user)
        else:
            print(_t('early_warning.cli.invalid_choice', default='Invalid choice.'))
