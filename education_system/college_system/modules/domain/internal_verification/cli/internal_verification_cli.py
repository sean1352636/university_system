"""Internal Verification CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.internal_verification.services.internal_verification_service import InternalVerificationService
from education_system.college_system.infrastructure.auth.core import UserAuth


def internal_verification_menu(auth: UserAuth):
    """Internal Verification management menu."""
    svc = InternalVerificationService(auth._db_path)

    while True:
        print_header("Internal Verification")
        options = [
            ("1", "List Plans"),
            ("2", "View Plan"),
            ("3", "New Plan"),
            ("4", "Update Plan"),
            ("5", "Delete Plan"),
            ("6", "List Samples"),
            ("7", "New Sample"),
            ("8", "Complete Sample"),
            ("9", "Update Sample"),
            ("10", "List Observations"),
            ("11", "New Observation"),
            ("12", "Complete Observation"),
            ("13", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_plans(svc)
        elif choice == "2":
            _view_plan(svc)
        elif choice == "3":
            _new_plan(svc)
        elif choice == "4":
            _update_plan(svc)
        elif choice == "5":
            _delete_plan(svc)
        elif choice == "6":
            _list_samples(svc)
        elif choice == "7":
            _new_sample(svc)
        elif choice == "8":
            _complete_sample(svc)
        elif choice == "9":
            _update_sample(svc)
        elif choice == "10":
            _list_observations(svc)
        elif choice == "11":
            _new_observation(svc)
        elif choice == "12":
            _complete_observation(svc)
        elif choice == "13":
            _show_statistics(svc)
        else:
            print("\n  Invalid option.")


# ── Plans ────────────────────────────────────────────────────────


def _list_plans(svc):
    print_header("IV Plans")
    try:
        status = input("  Filter by status (active/completed/archived) [all]: ").strip() or None
        cid = input("  Filter by course ID [all]: ").strip()
        course_id = int(cid) if cid else None

        plans = svc.list_plans(status=status, course_id=course_id)
        if not plans:
            print("\n  No plans found.")
            return
        print(f"\n  {'ID':<5} {'Course':<8} {'Year':<12} {'Lead IV':<8} {'Strategy':<20} {'%':<5} {'Status'}")
        print(f"  {'-'*68}")
        for p in plans:
            print(f"  {p['id']:<5} {p['course_id']:<8} "
                  f"{(p.get('academic_year') or '-'):<12} "
                  f"{(p.get('lead_iv_id') or '-'):<8} "
                  f"{(p.get('sampling_strategy') or '-'):<20} "
                  f"{p.get('sample_size_pct', 25):<5} "
                  f"{p['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_plan(svc):
    try:
        plan_id = int(input("  Plan ID: ").strip())
        plan = svc.get_plan(plan_id)
        if not plan:
            print("\n  Plan not found.")
            return
        print()
        for k, v in plan.items():
            print(f"  {k}: {v}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_plan(svc):
    print_header("New IV Plan")
    try:
        course_id = int(input("  Course ID: ").strip())
        academic_year = input("  Academic Year (e.g. 2025/26): ").strip() or None
        lead_iv = input("  Lead IV Staff ID: ").strip()
        lead_iv_id = int(lead_iv) if lead_iv else None
        sampling_strategy = input("  Sampling Strategy: ").strip() or None
        pct = input("  Sample Size % [25]: ").strip()
        sample_size_pct = int(pct) if pct else 25

        plan = svc.create_plan(
            course_id,
            academic_year=academic_year,
            lead_iv_id=lead_iv_id,
            sampling_strategy=sampling_strategy,
            sample_size_pct=sample_size_pct,
        )
        print(f"\n  Plan created (ID: {plan['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_plan(svc):
    print_header("Update IV Plan")
    try:
        plan_id = int(input("  Plan ID: ").strip())
        plan = svc.get_plan(plan_id)
        if not plan:
            print("\n  Plan not found.")
            return
        print("  Leave blank to keep current value.")
        updates = {}
        val = input(f"  Academic Year [{plan.get('academic_year', '')}]: ").strip()
        if val:
            updates["academic_year"] = val
        val = input(f"  Lead IV Staff ID [{plan.get('lead_iv_id', '')}]: ").strip()
        if val:
            updates["lead_iv_id"] = int(val)
        val = input(f"  Sampling Strategy [{plan.get('sampling_strategy', '')}]: ").strip()
        if val:
            updates["sampling_strategy"] = val
        val = input(f"  Sample Size % [{plan.get('sample_size_pct', 25)}]: ").strip()
        if val:
            updates["sample_size_pct"] = int(val)
        val = input(f"  Status [{plan.get('status', '')}]: ").strip()
        if val:
            updates["status"] = val

        if not updates:
            print("\n  No changes made.")
            return
        svc.update_plan(plan_id, **updates)
        print("\n  Plan updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_plan(svc):
    try:
        plan_id = int(input("  Plan ID: ").strip())
        confirm = input("  Delete plan and all samples/observations? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_plan(plan_id)
        print("\n  Plan deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Samples ──────────────────────────────────────────────────────


def _list_samples(svc):
    print_header("IV Samples")
    try:
        pid = input("  Filter by Plan ID [all]: ").strip()
        plan_id = int(pid) if pid else None
        status = input("  Filter by status (pending/in_progress/completed/action_required) [all]: ").strip() or None

        samples = svc.list_samples(plan_id=plan_id, status=status)
        if not samples:
            print("\n  No samples found.")
            return
        print(f"\n  {'ID':<5} {'Plan':<6} {'Assignment':<22} {'Assessor':<9} {'Verifier':<9} "
              f"{'Date':<12} {'Agreed':<7} {'Grade':<7} {'Status'}")
        print(f"  {'-'*86}")
        for s in samples:
            agreed = "Yes" if s.get("assessment_decisions_agreed") else "No"
            grading = "Yes" if s.get("grading_accurate") else "No"
            print(f"  {s['id']:<5} {s['plan_id']:<6} "
                  f"{(s.get('assignment_title') or '-'):<22} "
                  f"{(s.get('assessor_id') or '-'):<9} "
                  f"{(s.get('verifier_id') or '-'):<9} "
                  f"{(s.get('sample_date') or '-'):<12} "
                  f"{agreed:<7} {grading:<7} {s['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_sample(svc):
    print_header("New IV Sample")
    try:
        plan_id = int(input("  Plan ID: ").strip())
        assignment_title = input("  Assignment Title: ").strip()
        if not assignment_title:
            print("\n  Assignment title is required.")
            return
        assessor = input("  Assessor Staff ID: ").strip()
        assessor_id = int(assessor) if assessor else None
        verifier = input("  Verifier Staff ID: ").strip()
        verifier_id = int(verifier) if verifier else None
        sample_date = input("  Sample Date (YYYY-MM-DD): ").strip() or None
        student_ids = input("  Student IDs (comma-separated): ").strip() or None

        sample = svc.create_sample(
            plan_id, assignment_title,
            assessor_id=assessor_id,
            verifier_id=verifier_id,
            sample_date=sample_date,
            student_ids=student_ids,
        )
        print(f"\n  Sample created (ID: {sample['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_sample(svc):
    print_header("Complete Sample")
    try:
        sample_id = int(input("  Sample ID: ").strip())
        da = input("  Assessment decisions agreed? (y/n) [y]: ").strip().lower()
        decisions_agreed = 0 if da == "n" else 1
        feedback_quality = input("  Feedback quality (excellent/good/adequate/inadequate) [good]: ").strip() or "good"
        ga = input("  Grading accurate? (y/n) [y]: ").strip().lower()
        grading_accurate = 0 if ga == "n" else 1
        action_required = input("  Action required (leave blank if none): ").strip() or None

        result = svc.complete_sample(
            sample_id,
            decisions_agreed=decisions_agreed,
            feedback_quality=feedback_quality,
            grading_accurate=grading_accurate,
            action_required=action_required,
        )
        print(f"\n  Sample completed (status: {result['status']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_sample(svc):
    print_header("Update Sample")
    try:
        sample_id = int(input("  Sample ID: ").strip())
        sample = svc.get_sample(sample_id)
        if not sample:
            print("\n  Sample not found.")
            return
        print("  Leave blank to keep current value.")
        updates = {}
        val = input(f"  Assignment Title [{sample.get('assignment_title', '')}]: ").strip()
        if val:
            updates["assignment_title"] = val
        val = input(f"  Assessor ID [{sample.get('assessor_id', '')}]: ").strip()
        if val:
            updates["assessor_id"] = int(val)
        val = input(f"  Verifier ID [{sample.get('verifier_id', '')}]: ").strip()
        if val:
            updates["verifier_id"] = int(val)
        val = input(f"  Sample Date [{sample.get('sample_date', '')}]: ").strip()
        if val:
            updates["sample_date"] = val
        val = input(f"  Student IDs [{sample.get('student_ids', '')}]: ").strip()
        if val:
            updates["student_ids"] = val
        val = input(f"  Status [{sample.get('status', '')}]: ").strip()
        if val:
            updates["status"] = val
        val = input(f"  Action Completed (0/1) [{sample.get('action_completed', 0)}]: ").strip()
        if val:
            updates["action_completed"] = int(val)

        if not updates:
            print("\n  No changes made.")
            return
        svc.update_sample(sample_id, **updates)
        print("\n  Sample updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Observations ─────────────────────────────────────────────────


def _list_observations(svc):
    print_header("IV Observations")
    try:
        pid = input("  Filter by Plan ID [all]: ").strip()
        plan_id = int(pid) if pid else None
        status = input("  Filter by status (scheduled/completed/cancelled) [all]: ").strip() or None

        observations = svc.list_observations(plan_id=plan_id, status=status)
        if not observations:
            print("\n  No observations found.")
            return
        print(f"\n  {'ID':<5} {'Plan':<6} {'Assessor':<9} {'Observer':<9} "
              f"{'Date':<12} {'Grade':<8} {'Status'}")
        print(f"  {'-'*58}")
        for o in observations:
            print(f"  {o['id']:<5} {o['plan_id']:<6} "
                  f"{(o.get('assessor_id') or '-'):<9} "
                  f"{(o.get('observer_id') or '-'):<9} "
                  f"{(o.get('observation_date') or '-'):<12} "
                  f"{(o.get('grade') or '-'):<8} "
                  f"{o['status']}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_observation(svc):
    print_header("New Observation")
    try:
        plan_id = int(input("  Plan ID: ").strip())
        assessor = input("  Assessor Staff ID: ").strip()
        assessor_id = int(assessor) if assessor else None
        observer = input("  Observer Staff ID: ").strip()
        observer_id = int(observer) if observer else None
        observation_date = input("  Observation Date (YYYY-MM-DD): ").strip() or None
        assessment_type = input("  Assessment Type: ").strip() or None

        obs = svc.create_observation(
            plan_id,
            assessor_id=assessor_id,
            observer_id=observer_id,
            observation_date=observation_date,
            assessment_type=assessment_type,
        )
        print(f"\n  Observation created (ID: {obs['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_observation(svc):
    print_header("Complete Observation")
    try:
        obs_id = int(input("  Observation ID: ").strip())
        feedback = input("  Feedback: ").strip()
        if not feedback:
            print("\n  Feedback is required.")
            return
        grade = input("  Grade: ").strip()
        if not grade:
            print("\n  Grade is required.")
            return
        actions = input("  Actions (optional): ").strip() or None

        result = svc.complete_observation(obs_id, feedback=feedback, grade=grade, actions=actions)
        print(f"\n  Observation completed (status: {result['status']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Statistics ───────────────────────────────────────────────────


def _show_statistics(svc):
    print_header("IV Statistics")
    try:
        stats = svc.get_stats()
        print(f"\n  Total Plans:              {stats['total_plans']}")
        print(f"  Active Plans:             {stats['active_plans']}")
        print(f"  Total Samples:            {stats['total_samples']}")
        print(f"  Samples Completed:        {stats['samples_completed']}")
        print(f"  Samples With Actions:     {stats['samples_with_actions']}")
        print(f"  Action Completion Rate:   {stats['action_completion_rate']}%")
        print(f"  Total Observations:       {stats['total_observations']}")
        print(f"  Observations Completed:   {stats['observations_completed']}")
        print(f"  Grading Accuracy Rate:    {stats['grading_accuracy_rate']}%")
    except Exception as e:
        print(f"\n  Error: {e}")
