"""Internal Quality Review Manager CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.iqr_manager.services.iqr_manager_service import IQRManagerService
from education_system.college_system.infrastructure.auth.core import UserAuth


def iqr_manager_menu(auth: UserAuth):
    """Internal Quality Review Manager menu."""
    svc = IQRManagerService(auth._db_path)

    while True:
        print_header("Internal Quality Review Manager")
        options = [
            ("1", "List Review Cycles"),
            ("2", "Create New Cycle"),
            ("3", "View Cycle Details"),
            ("4", "Schedule Visit"),
            ("5", "List Visits"),
            ("6", "Complete Visit"),
            ("7", "Create Action Plan"),
            ("8", "List Action Plans"),
            ("9", "Update Action Progress"),
            ("10", "Review Action"),
            ("11", "Cycle Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_cycles(svc)
        elif choice == "2":
            _create_cycle(svc)
        elif choice == "3":
            _view_cycle(svc)
        elif choice == "4":
            _schedule_visit(svc)
        elif choice == "5":
            _list_visits(svc)
        elif choice == "6":
            _complete_visit(svc)
        elif choice == "7":
            _create_action_plan(svc)
        elif choice == "8":
            _list_action_plans(svc)
        elif choice == "9":
            _update_action_progress(svc)
        elif choice == "10":
            _review_action(svc)
        elif choice == "11":
            _cycle_stats(svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_cycles(svc):
    print_header("Review Cycles")
    try:
        ay = input("  Filter by academic year (blank=all): ").strip() or None
        cycles = svc.list_cycles(academic_year=ay)
        if not cycles:
            print("\n  No review cycles found.")
            return
        print(f"\n  {'ID':<5} {'Year':<12} {'Name':<25} {'Start':<12} {'End':<12} {'Status'}")
        print(f"  {'-'*75}")
        for c in cycles:
            print(f"  {c['id']:<5} {(c.get('academic_year') or '-'):<12} "
                  f"{(c.get('cycle_name') or '-'):<25} {(c.get('start_date') or '-'):<12} "
                  f"{(c.get('end_date') or '-'):<12} {(c.get('status') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_cycle(svc):
    print_header("Create New Cycle")
    try:
        ay = input("  Academic year: ").strip()
        name = input("  Cycle name: ").strip()
        sd = input("  Start date (YYYY-MM-DD): ").strip()
        ed = input("  End date (YYYY-MM-DD): ").strip()
        focus = input("  Focus areas (blank=none): ").strip() or None
        cby = input("  Created by (user ID, blank=none): ").strip()
        cby = int(cby) if cby else None
        result = svc.create_cycle(ay, name, sd, ed, focus, cby)
        print(f"\n  Cycle created (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_cycle(svc):
    print_header("Cycle Details")
    try:
        cid = int(input("  Cycle ID: ").strip())
        c = svc.get_cycle(cid)
        print(f"\n  ID:            {c['id']}")
        print(f"  Academic Year: {c.get('academic_year', '-')}")
        print(f"  Name:          {c.get('cycle_name', '-')}")
        print(f"  Start Date:    {c.get('start_date', '-')}")
        print(f"  End Date:      {c.get('end_date', '-')}")
        print(f"  Focus Areas:   {c.get('focus_areas') or '-'}")
        print(f"  Status:        {c.get('status', '-')}")
        print(f"  Created By:    {c.get('created_by') or '-'}")
        print(f"  Created:       {c.get('created_at', '-')}")
        print(f"  Updated:       {c.get('updated_at', '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _schedule_visit(svc):
    print_header("Schedule Visit")
    try:
        cid = int(input("  Cycle ID: ").strip())
        dept = input("  Department: ").strip()
        vd = input("  Visit date (YYYY-MM-DD): ").strip()
        reviewer = input("  Reviewer ID (blank=none): ").strip()
        reviewer = int(reviewer) if reviewer else None
        vt = input("  Visit type (learning_walk/deep_dive/work_scrutiny/student_voice/staff_interview): ").strip()
        result = svc.schedule_visit(cid, dept, vd, reviewer, vt)
        print(f"\n  Visit scheduled (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_visits(svc):
    print_header("Visits")
    try:
        cid = input("  Filter by cycle ID (blank=all): ").strip()
        cid = int(cid) if cid else None
        dept = input("  Filter by department (blank=all): ").strip() or None
        status = input("  Filter by status (blank=all): ").strip() or None
        visits = svc.list_visits(cycle_id=cid, department=dept, status=status)
        if not visits:
            print("\n  No visits found.")
            return
        print(f"\n  {'ID':<5} {'Cycle':<6} {'Department':<18} {'Date':<12} {'Type':<16} {'Judgement':<20} {'Status'}")
        print(f"  {'-'*85}")
        for v in visits:
            print(f"  {v['id']:<5} {v.get('cycle_id', '-'):<6} "
                  f"{(v.get('department') or '-'):<18} {(v.get('visit_date') or '-'):<12} "
                  f"{(v.get('visit_type') or '-'):<16} "
                  f"{(v.get('overall_judgement') or '-'):<20} {(v.get('status') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_visit(svc):
    print_header("Complete Visit")
    try:
        vid = int(input("  Visit ID: ").strip())
        findings = input("  Findings: ").strip()
        strengths = input("  Strengths: ").strip()
        afi = input("  Areas for improvement: ").strip()
        judge = input("  Judgement (outstanding/good/requires_improvement/inadequate): ").strip()
        svc.complete_visit(vid, findings, strengths, afi, judge)
        print(f"\n  Visit {vid} completed with judgement: {judge}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _create_action_plan(svc):
    print_header("Create Action Plan")
    try:
        vid = int(input("  Visit ID: ").strip())
        desc = input("  Action description: ").strip()
        responsible = input("  Responsible person: ").strip()
        target = input("  Target date (YYYY-MM-DD): ").strip()
        criteria = input("  Success criteria: ").strip()
        result = svc.create_action_plan(vid, desc, responsible, target, criteria)
        print(f"\n  Action plan created (ID: {result}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_action_plans(svc):
    print_header("Action Plans")
    try:
        vid = input("  Filter by visit ID (blank=all): ").strip()
        vid = int(vid) if vid else None
        status = input("  Filter by status (not_started/in_progress/completed/overdue, blank=all): ").strip() or None
        plans = svc.list_action_plans(visit_id=vid, status=status)
        if not plans:
            print("\n  No action plans found.")
            return
        print(f"\n  {'ID':<5} {'Visit':<6} {'Description':<35} {'Responsible':<18} {'Target':<12} {'Status'}")
        print(f"  {'-'*90}")
        for p in plans:
            desc = (p.get('action_description') or '-')
            if len(desc) > 33:
                desc = desc[:30] + "..."
            print(f"  {p['id']:<5} {p.get('visit_id', '-'):<6} "
                  f"{desc:<35} {(p.get('responsible_person') or '-'):<18} "
                  f"{(p.get('target_date') or '-'):<12} {(p.get('status') or '-')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_action_progress(svc):
    print_header("Update Action Progress")
    try:
        aid = int(input("  Action plan ID: ").strip())
        progress = input("  Progress update: ").strip()
        evidence = input("  Evidence (blank=none): ").strip() or None
        status = input("  New status (not_started/in_progress/completed/overdue, blank=unchanged): ").strip() or None
        svc.update_action_progress(aid, progress, evidence=evidence, status=status)
        print(f"\n  Action plan {aid} updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _review_action(svc):
    print_header("Review Action")
    try:
        aid = int(input("  Action plan ID: ").strip())
        rby = input("  Reviewed by (user ID): ").strip()
        rby = int(rby) if rby else None
        svc.review_action(aid, rby)
        print(f"\n  Action plan {aid} marked as reviewed.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _cycle_stats(svc):
    print_header("Cycle Statistics")
    try:
        cid = int(input("  Cycle ID: ").strip())
        stats = svc.get_cycle_stats(cid)
        print(f"\n  Cycle ID:       {stats['cycle_id']}")
        print(f"  Total Visits:   {stats['total_visits']}")
        visit_status = stats.get('visit_status', {})
        if visit_status:
            print(f"\n  Visit Status Breakdown:")
            for status, count in visit_status.items():
                print(f"    {(status or 'unknown'):<22} {count}")
        judgement_dist = stats.get('judgement_distribution', {})
        if judgement_dist:
            print(f"\n  Judgement Distribution:")
            for judge, count in judgement_dist.items():
                print(f"    {(judge or 'ungraded'):<22} {count}")
        print(f"\n  Total Actions:  {stats['total_actions']}")
        action_status = stats.get('action_status', {})
        if action_status:
            print(f"\n  Action Plan Status:")
            for status, count in action_status.items():
                print(f"    {(status or 'unknown'):<22} {count}")
    except Exception as e:
        print(f"\n  Error: {e}")
