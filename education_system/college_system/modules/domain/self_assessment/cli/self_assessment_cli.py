"""Self-Assessment & Ofsted CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.self_assessment.services.self_assessment_service import SelfAssessmentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def self_assessment_menu(auth: UserAuth):
    """Self-Assessment & Ofsted management menu."""
    svc = SelfAssessmentService(auth._db_path)

    while True:
        print_header("Self-Assessment & Ofsted")
        options = [
            ("1", "List SEF Sections"),
            ("2", "View Section"),
            ("3", "New Section"),
            ("4", "Update Section"),
            ("5", "Delete Section"),
            ("6", "List Actions"),
            ("7", "New Action"),
            ("8", "Update Action"),
            ("9", "List Checklist"),
            ("10", "New Checklist Item"),
            ("11", "Toggle Ready"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_sections(svc)
        elif choice == "2":
            _view_section(svc)
        elif choice == "3":
            _new_section(svc)
        elif choice == "4":
            _update_section(svc)
        elif choice == "5":
            _delete_section(svc)
        elif choice == "6":
            _list_actions(svc)
        elif choice == "7":
            _new_action(svc)
        elif choice == "8":
            _update_action(svc)
        elif choice == "9":
            _list_checklist(svc)
        elif choice == "10":
            _new_checklist_item(svc)
        elif choice == "11":
            _toggle_ready(svc)
        elif choice == "12":
            _show_stats(svc)
        else:
            print("\n  Invalid option.")


def _list_sections(svc):
    print_header("SEF Sections")
    try:
        year = input("  Filter by year (blank for all): ").strip() or None
        status = input("  Filter by status (draft/final, blank for all): ").strip() or None
        sections = svc.list_sections(academic_year=year, status=status)
        if not sections:
            print("\n  No SEF sections found.")
            return
        print(f"\n  {'ID':<5} {'Year':<10} {'Section':<30} {'No.':<5} {'Grade':<10} {'Status'}")
        print(f"  {'-'*72}")
        for s in sections:
            print(f"  {s['id']:<5} {(s.get('academic_year') or '-'):<10} "
                  f"{s['section_name'][:28]:<30} {(s.get('section_number') or '-'):<5} "
                  f"{(s.get('self_grade') or '-'):<10} {s.get('status', 'draft')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_section(svc):
    try:
        sec_id = int(input("  Section ID: ").strip())
        section = svc.get_section(sec_id)
        if not section:
            print("\n  Section not found.")
            return
        print(f"\n  Section Name:           {section.get('section_name', '-')}")
        print(f"  Section Number:         {section.get('section_number') or '-'}")
        print(f"  Academic Year:          {section.get('academic_year') or '-'}")
        print(f"  Self Grade:             {section.get('self_grade') or '-'}")
        print(f"  Status:                 {section.get('status') or 'draft'}")
        print(f"  Strengths:              {section.get('strengths') or '-'}")
        print(f"  Areas for Improvement:  {section.get('areas_for_improvement') or '-'}")
        print(f"  Evidence:               {section.get('evidence') or '-'}")
        print(f"  Last Updated:           {section.get('updated_at') or section.get('created_at') or '-'}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_section(svc):
    print_header("New SEF Section")
    try:
        name = input("  Section Name: ").strip()
        if not name:
            print("\n  Section name is required.")
            return
        number = input("  Section Number: ").strip() or None
        year = input("  Academic Year (e.g. 2025/26): ").strip() or None
        grade = input("  Self Grade: ").strip() or None
        status = input("  Status (draft/final) [draft]: ").strip() or "draft"
        strengths = input("  Strengths: ").strip() or None
        afi = input("  Areas for Improvement: ").strip() or None
        evidence = input("  Evidence: ").strip() or None

        section = svc.create_section(
            section_name=name, section_number=number, academic_year=year,
            self_grade=grade, status=status, strengths=strengths,
            areas_for_improvement=afi, evidence=evidence,
        )
        print(f"\n  SEF section created (ID: {section['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_section(svc):
    try:
        sec_id = int(input("  Section ID: ").strip())
        existing = svc.get_section(sec_id)
        if not existing:
            print("\n  Section not found.")
            return
        print("  (Leave blank to keep current value)")
        name = input(f"  Section Name [{existing['section_name']}]: ").strip() or None
        number = input(f"  Section Number [{existing.get('section_number') or ''}]: ").strip() or None
        year = input(f"  Academic Year [{existing.get('academic_year') or ''}]: ").strip() or None
        grade = input(f"  Self Grade [{existing.get('self_grade') or ''}]: ").strip() or None
        status = input(f"  Status [{existing.get('status') or 'draft'}]: ").strip() or None
        strengths = input(f"  Strengths: ").strip() or None
        afi = input(f"  Areas for Improvement: ").strip() or None
        evidence = input(f"  Evidence: ").strip() or None

        kwargs = {}
        if name:
            kwargs["section_name"] = name
        if number:
            kwargs["section_number"] = number
        if year:
            kwargs["academic_year"] = year
        if grade:
            kwargs["self_grade"] = grade
        if status:
            kwargs["status"] = status
        if strengths:
            kwargs["strengths"] = strengths
        if afi:
            kwargs["areas_for_improvement"] = afi
        if evidence:
            kwargs["evidence"] = evidence

        if not kwargs:
            print("\n  No changes provided.")
            return
        svc.update_section(sec_id, **kwargs)
        print("\n  Section updated.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_section(svc):
    try:
        sec_id = int(input("  Section ID: ").strip())
        confirm = input("  This will also delete related actions. Confirm? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_section(sec_id)
        print("\n  Section deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_actions(svc):
    print_header("Improvement Actions")
    try:
        sec_id_str = input("  Filter by section ID (blank for all): ").strip()
        sec_id = int(sec_id_str) if sec_id_str else None
        status = input("  Filter by status (not_started/in_progress/completed, blank for all): ").strip() or None
        actions = svc.list_actions(sef_section_id=sec_id, status=status)
        if not actions:
            print("\n  No improvement actions found.")
            return
        print(f"\n  {'ID':<5} {'Section':<20} {'Action':<30} {'Responsible':<15} {'Target':<12} {'Status'}")
        print(f"  {'-'*85}")
        for a in actions:
            sec_name = (a.get("section_name") or f"Sec {a['sef_section_id']}")[:18]
            desc = a["action_description"][:28]
            responsible = (a.get("responsible_person") or "-")[:13]
            print(f"  {a['id']:<5} {sec_name:<20} {desc:<30} {responsible:<15} "
                  f"{(a.get('target_date') or '-'):<12} {a.get('status', 'not_started')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_action(svc):
    print_header("New Improvement Action")
    try:
        sec_id = int(input("  SEF Section ID: ").strip())
        desc = input("  Action Description: ").strip()
        if not desc:
            print("\n  Description is required.")
            return
        responsible = input("  Responsible Person: ").strip() or None
        start_date = input("  Start Date (YYYY-MM-DD): ").strip() or None
        target_date = input("  Target Date (YYYY-MM-DD): ").strip() or None
        criteria = input("  Success Criteria: ").strip() or None
        cost_str = input("  Cost [0]: ").strip() or "0"
        cost = float(cost_str)
        status = input("  Status (not_started/in_progress/completed) [not_started]: ").strip() or "not_started"

        action = svc.create_action(
            sef_section_id=sec_id, action_description=desc,
            responsible_person=responsible, start_date=start_date,
            target_date=target_date, success_criteria=criteria,
            cost=cost, status=status,
        )
        print(f"\n  Action created (ID: {action['id']}).")
    except ValueError:
        print("\n  Invalid input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_action(svc):
    try:
        act_id = int(input("  Action ID: ").strip())
        existing = svc.get_action(act_id)
        if not existing:
            print("\n  Action not found.")
            return
        print("  (Leave blank to keep current value)")
        desc = input("  Action Description: ").strip() or None
        responsible = input("  Responsible Person: ").strip() or None
        start_date = input("  Start Date (YYYY-MM-DD): ").strip() or None
        target_date = input("  Target Date (YYYY-MM-DD): ").strip() or None
        criteria = input("  Success Criteria: ").strip() or None
        progress = input("  Progress: ").strip() or None
        impact = input("  Impact: ").strip() or None
        cost_str = input("  Cost: ").strip()
        status = input("  Status (not_started/in_progress/completed): ").strip() or None

        kwargs = {}
        if desc:
            kwargs["action_description"] = desc
        if responsible:
            kwargs["responsible_person"] = responsible
        if start_date:
            kwargs["start_date"] = start_date
        if target_date:
            kwargs["target_date"] = target_date
        if criteria:
            kwargs["success_criteria"] = criteria
        if progress:
            kwargs["progress"] = progress
        if impact:
            kwargs["impact"] = impact
        if cost_str:
            kwargs["cost"] = float(cost_str)
        if status:
            kwargs["status"] = status

        if not kwargs:
            print("\n  No changes provided.")
            return
        svc.update_action(act_id, **kwargs)
        print("\n  Action updated.")
    except ValueError:
        print("\n  Invalid input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_checklist(svc):
    print_header("Ofsted Prep Checklist")
    try:
        category = input("  Filter by category (blank for all): ").strip() or None
        items = svc.list_checklist(category=category)
        if not items:
            print("\n  No checklist items found.")
            return
        print(f"\n  {'ID':<5} {'Category':<18} {'Item':<30} {'Responsible':<15} {'Ready':<6} {'Last Checked'}")
        print(f"  {'-'*80}")
        for it in items:
            ready = "Yes" if it.get("is_ready") else "No"
            responsible = (it.get("responsible_person") or "-")[:13]
            print(f"  {it['id']:<5} {it['category'][:16]:<18} {it['item'][:28]:<30} "
                  f"{responsible:<15} {ready:<6} {it.get('last_checked') or '-'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_checklist_item(svc):
    print_header("New Checklist Item")
    try:
        category = input("  Category: ").strip()
        item = input("  Item: ").strip()
        if not category or not item:
            print("\n  Category and item are required.")
            return
        responsible = input("  Responsible Person: ").strip() or None
        doc_location = input("  Document Location: ").strip() or None
        notes = input("  Notes: ").strip() or None

        result = svc.create_checklist_item(
            category=category, item=item, responsible_person=responsible,
            document_location=doc_location, notes=notes,
        )
        print(f"\n  Checklist item created (ID: {result['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _toggle_ready(svc):
    try:
        item_id = int(input("  Checklist Item ID: ").strip())
        result = svc.toggle_ready(item_id)
        status = "Ready" if result.get("is_ready") else "Not Ready"
        print(f"\n  Item marked as {status}.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _show_stats(svc):
    print_header("Self-Assessment Statistics")
    try:
        stats = svc.get_stats()
        print(f"\n  SEF Sections")
        print(f"  {'='*30}")
        print(f"  Total:         {stats['total_sections']}")
        print(f"  Draft:         {stats['draft_count']}")
        print(f"  Final:         {stats['final_count']}")
        print(f"\n  Improvement Actions")
        print(f"  {'='*30}")
        print(f"  Total:         {stats['total_actions']}")
        print(f"  Not Started:   {stats['not_started']}")
        print(f"  In Progress:   {stats['in_progress']}")
        print(f"  Completed:     {stats['completed']}")
        print(f"\n  Ofsted Prep Checklist")
        print(f"  {'='*30}")
        print(f"  Total:         {stats['total_checklist']}")
        print(f"  Ready:         {stats['ready_count']}")
        print(f"  Not Ready:     {stats['not_ready_count']}")
    except Exception as e:
        print(f"\n  Error: {e}")
