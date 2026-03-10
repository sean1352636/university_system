"""Study Programmes CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.study_programmes.services.study_programmes_service import (
    StudyProgrammesService,
)
from education_system.college_system.infrastructure.auth.core import UserAuth


def study_programmes_menu(auth: UserAuth):
    """Study Programmes management menu."""
    svc = StudyProgrammesService(auth._db_path)

    while True:
        print_header("Study Programmes")
        options = [
            ("1", "List Programmes"),
            ("2", "View Programme"),
            ("3", "New Programme"),
            ("4", "Update Programme"),
            ("5", "Validate Programme"),
            ("6", "Delete Programme"),
            ("7", "List Components"),
            ("8", "New Component"),
            ("9", "Update Component"),
            ("A", "Delete Component"),
            ("B", "Hours Summary"),
            ("C", "Condition of Funding Check"),
            ("D", "Funding Hours Report"),
            ("E", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice().upper()
        if choice == "0":
            break
        elif choice == "1":
            _list_programmes(svc)
        elif choice == "2":
            _view_programme(svc)
        elif choice == "3":
            _new_programme(svc)
        elif choice == "4":
            _update_programme(svc)
        elif choice == "5":
            _validate_programme(svc)
        elif choice == "6":
            _delete_programme(svc)
        elif choice == "7":
            _list_components(svc)
        elif choice == "8":
            _new_component(svc)
        elif choice == "9":
            _update_component(svc)
        elif choice == "A":
            _delete_component(svc)
        elif choice == "B":
            _hours_summary(svc)
        elif choice == "C":
            _cof_check(svc)
        elif choice == "D":
            _funding_hours_report(svc)
        elif choice == "E":
            _statistics(svc)
        else:
            print("\n  Invalid option.")


# ================================================================
# Programmes
# ================================================================

def _list_programmes(svc):
    print_header("List Programmes")
    try:
        status = input("  Filter by status (active/completed/withdrawn/transferred) [all]: ").strip() or None
        ptype = input("  Filter by type (level3/level2/level1/entry/traineeship/t_level) [all]: ").strip() or None
        year = input("  Filter by academic year [all]: ").strip() or None

        progs = svc.list_programmes(status=status, programme_type=ptype, academic_year=year)
        if not progs:
            print("\n  No programmes found.")
            return

        print(f"\n  {'ID':<5} {'Student':<25} {'Type':<12} {'Year':<10} "
              f"{'Maths':<10} {'English':<10} {'Planned':<8} {'Valid':<6} {'Status'}")
        print(f"  {'-' * 95}")
        for p in progs:
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or f"PK:{p['student_id']}"
            valid = "Yes" if p.get("is_valid") else "No"
            print(f"  {p['id']:<5} {name:<25} {(p.get('programme_type') or '-'):<12} "
                  f"{(p.get('academic_year') or '-'):<10} "
                  f"{(p.get('maths_requirement') or '-'):<10} "
                  f"{(p.get('english_requirement') or '-'):<10} "
                  f"{p.get('total_planned_hours', 0):<8} {valid:<6} "
                  f"{p.get('status') or '-'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_programme(svc):
    try:
        pid = int(input("  Programme ID: ").strip())
        prog = svc.get_programme(pid)
        if not prog:
            print("\n  Programme not found.")
            return

        print(f"\n  Programme #{prog['id']}")
        print(f"  {'=' * 40}")
        print(f"  Student ID:          {prog['student_id']}")
        name = f"{prog.get('first_name', '')} {prog.get('last_name', '')}".strip()
        if name:
            print(f"  Student Name:        {name}")
        print(f"  Academic Year:       {prog.get('academic_year') or '-'}")
        print(f"  Programme Type:      {prog.get('programme_type') or '-'}")
        print(f"  Substantive Qual:    {prog.get('substantive_qualification') or '-'}")
        print(f"  Maths Requirement:   {prog.get('maths_requirement') or '-'}")
        print(f"  English Requirement: {prog.get('english_requirement') or '-'}")
        print(f"  Work Exp Completed:  {'Yes' if prog.get('work_experience_completed') else 'No'}")
        print(f"  Work Exp Hours:      {prog.get('work_experience_hours', 0)}")
        print(f"  Enrichment Hours:    {prog.get('enrichment_hours', 0)}")
        print(f"  Tutorial Hours:      {prog.get('tutorial_hours', 0)}")
        print(f"  Total Planned Hrs:   {prog.get('total_planned_hours', 0)}")
        print(f"  Total Delivered Hrs:  {prog.get('total_delivered_hours', 0)}")
        print(f"  Valid:               {'Yes' if prog.get('is_valid') else 'No'}")
        print(f"  Validation Notes:    {prog.get('validation_notes') or '-'}")
        print(f"  Status:              {prog.get('status') or '-'}")
        print(f"  Created:             {prog.get('created_at') or '-'}")
        print(f"  Updated:             {prog.get('updated_at') or '-'}")

        # Show components
        comps = svc.list_components(programme_id=pid)
        if comps:
            print(f"\n  Components ({len(comps)}):")
            print(f"  {'-' * 60}")
            for c in comps:
                print(f"    [{c['id']}] {c['component_type']}: {c['component_name']} "
                      f"({c.get('planned_hours', 0)}h planned, "
                      f"{c.get('delivered_hours', 0)}h delivered, "
                      f"{c.get('status', '-')})")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_programme(svc):
    print_header("New Study Programme")
    try:
        student_id = int(input("  Student PK: ").strip())
        academic_year = input("  Academic Year (e.g. 2025/26): ").strip() or None
        ptype = input("  Programme Type (level3/level2/level1/entry/traineeship/t_level) [level3]: ").strip() or "level3"
        subst_qual = input("  Substantive Qualification: ").strip() or None
        maths_req = input("  Maths Requirement (not_met/met/exempt/enrolled) [not_met]: ").strip() or "not_met"
        english_req = input("  English Requirement (not_met/met/exempt/enrolled) [not_met]: ").strip() or "not_met"
        maths_enr = input("  Maths Enrollment ID (blank if N/A): ").strip()
        english_enr = input("  English Enrollment ID (blank if N/A): ").strip()
        work_exp = input("  Work Experience Completed (0/1) [0]: ").strip() or "0"
        work_hrs = input("  Work Experience Hours [0]: ").strip() or "0"
        enrichment = input("  Enrichment Hours [0]: ").strip() or "0"
        tutorial = input("  Tutorial Hours [0]: ").strip() or "0"
        planned = input("  Total Planned Hours [0]: ").strip() or "0"

        kwargs = {
            "programme_type": ptype,
            "maths_requirement": maths_req,
            "english_requirement": english_req,
            "work_experience_completed": int(work_exp),
            "work_experience_hours": int(work_hrs),
            "enrichment_hours": int(enrichment),
            "tutorial_hours": int(tutorial),
            "total_planned_hours": int(planned),
        }
        if academic_year:
            kwargs["academic_year"] = academic_year
        if subst_qual:
            kwargs["substantive_qualification"] = subst_qual
        if maths_enr:
            kwargs["maths_enrollment_id"] = int(maths_enr)
        if english_enr:
            kwargs["english_enrollment_id"] = int(english_enr)

        prog = svc.create_programme(student_id, **kwargs)
        print(f"\n  Programme created (ID: {prog['id']}).")
    except ValueError:
        print("\n  Invalid numeric value.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_programme(svc):
    print_header("Update Programme")
    try:
        pid = int(input("  Programme ID: ").strip())
        prog = svc.get_programme(pid)
        if not prog:
            print("\n  Programme not found.")
            return

        print("  Leave blank to keep current value.")
        kwargs = {}

        val = input(f"  Academic Year [{prog.get('academic_year') or ''}]: ").strip()
        if val:
            kwargs["academic_year"] = val

        val = input(f"  Programme Type [{prog.get('programme_type') or ''}]: ").strip()
        if val:
            kwargs["programme_type"] = val

        val = input(f"  Substantive Qualification [{prog.get('substantive_qualification') or ''}]: ").strip()
        if val:
            kwargs["substantive_qualification"] = val

        val = input(f"  Maths Requirement [{prog.get('maths_requirement') or ''}]: ").strip()
        if val:
            kwargs["maths_requirement"] = val

        val = input(f"  English Requirement [{prog.get('english_requirement') or ''}]: ").strip()
        if val:
            kwargs["english_requirement"] = val

        val = input(f"  Maths Enrollment ID [{prog.get('maths_enrollment_id') or ''}]: ").strip()
        if val:
            kwargs["maths_enrollment_id"] = int(val)

        val = input(f"  English Enrollment ID [{prog.get('english_enrollment_id') or ''}]: ").strip()
        if val:
            kwargs["english_enrollment_id"] = int(val)

        val = input(f"  Work Exp Completed (0/1) [{prog.get('work_experience_completed', 0)}]: ").strip()
        if val:
            kwargs["work_experience_completed"] = int(val)

        val = input(f"  Work Exp Hours [{prog.get('work_experience_hours', 0)}]: ").strip()
        if val:
            kwargs["work_experience_hours"] = int(val)

        val = input(f"  Enrichment Hours [{prog.get('enrichment_hours', 0)}]: ").strip()
        if val:
            kwargs["enrichment_hours"] = int(val)

        val = input(f"  Tutorial Hours [{prog.get('tutorial_hours', 0)}]: ").strip()
        if val:
            kwargs["tutorial_hours"] = int(val)

        val = input(f"  Total Planned Hours [{prog.get('total_planned_hours', 0)}]: ").strip()
        if val:
            kwargs["total_planned_hours"] = int(val)

        val = input(f"  Status [{prog.get('status') or ''}]: ").strip()
        if val:
            kwargs["status"] = val

        if not kwargs:
            print("\n  No changes made.")
            return

        svc.update_programme(pid, **kwargs)
        print("\n  Programme updated.")
    except ValueError:
        print("\n  Invalid numeric value.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _validate_programme(svc):
    try:
        pid = int(input("  Programme ID: ").strip())
        result = svc.validate_programme(pid)
        valid = "VALID" if result.get("is_valid") else "INVALID"
        notes = result.get("validation_notes") or "-"
        print(f"\n  Programme #{pid}: {valid}")
        print(f"  Notes: {notes}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_programme(svc):
    try:
        pid = int(input("  Programme ID: ").strip())
        confirm = input(f"  Delete programme #{pid} and all components? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_programme(pid)
        print("\n  Programme deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ================================================================
# Components
# ================================================================

def _list_components(svc):
    print_header("List Components")
    try:
        prog_id_str = input("  Programme ID (blank for all): ").strip()
        prog_id = int(prog_id_str) if prog_id_str else None
        ctype = input("  Component type (blank for all): ").strip() or None

        comps = svc.list_components(programme_id=prog_id, component_type=ctype)
        if not comps:
            print("\n  No components found.")
            return

        print(f"\n  {'ID':<5} {'Prog':<6} {'Type':<18} {'Name':<30} "
              f"{'Planned':<9} {'Delivered':<10} {'Status'}")
        print(f"  {'-' * 85}")
        for c in comps:
            print(f"  {c['id']:<5} {c['programme_id']:<6} "
                  f"{(c.get('component_type') or '-'):<18} "
                  f"{(c.get('component_name') or '-'):<30} "
                  f"{c.get('planned_hours', 0):<9} "
                  f"{c.get('delivered_hours', 0):<10} "
                  f"{c.get('status') or '-'}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_component(svc):
    print_header("New Component")
    try:
        prog_id = int(input("  Programme ID: ").strip())
        ctype = input("  Component Type (qualification/work_experience/enrichment/tutorial/maths_english/pastoral): ").strip()
        if not ctype:
            print("\n  Component type is required.")
            return
        cname = input("  Component Name: ").strip()
        if not cname:
            print("\n  Component name is required.")
            return
        planned = int(input("  Planned Hours [0]: ").strip() or "0")
        delivered = int(input("  Delivered Hours [0]: ").strip() or "0")
        status = input("  Status (active/completed/withdrawn) [active]: ").strip() or "active"

        comp = svc.create_component(prog_id, ctype, cname,
                                    planned_hours=planned,
                                    delivered_hours=delivered,
                                    status=status)
        print(f"\n  Component created (ID: {comp['id']}).")
    except ValueError:
        print("\n  Invalid numeric value.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_component(svc):
    print_header("Update Component")
    try:
        cid = int(input("  Component ID: ").strip())
        comp = svc.get_component(cid)
        if not comp:
            print("\n  Component not found.")
            return

        print("  Leave blank to keep current value.")
        kwargs = {}

        val = input(f"  Component Type [{comp.get('component_type') or ''}]: ").strip()
        if val:
            kwargs["component_type"] = val

        val = input(f"  Component Name [{comp.get('component_name') or ''}]: ").strip()
        if val:
            kwargs["component_name"] = val

        val = input(f"  Planned Hours [{comp.get('planned_hours', 0)}]: ").strip()
        if val:
            kwargs["planned_hours"] = int(val)

        val = input(f"  Delivered Hours [{comp.get('delivered_hours', 0)}]: ").strip()
        if val:
            kwargs["delivered_hours"] = int(val)

        val = input(f"  Status [{comp.get('status') or ''}]: ").strip()
        if val:
            kwargs["status"] = val

        if not kwargs:
            print("\n  No changes made.")
            return

        svc.update_component(cid, **kwargs)
        print("\n  Component updated.")
    except ValueError:
        print("\n  Invalid numeric value.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_component(svc):
    try:
        cid = int(input("  Component ID: ").strip())
        confirm = input(f"  Delete component #{cid}? (y/n): ").strip().lower()
        if confirm != "y":
            print("\n  Cancelled.")
            return
        svc.delete_component(cid)
        print("\n  Component deleted.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ================================================================
# Hours & Reports
# ================================================================

def _hours_summary(svc):
    print_header("Hours Summary")
    try:
        pid = int(input("  Programme ID: ").strip())
        summary = svc.get_hours_summary(pid)
        print(f"\n  Programme #{pid}")
        print(f"  Total Planned Hours:   {summary['total_planned_hours']}")
        print(f"  Total Delivered Hours:  {summary['total_delivered_hours']}")

        by_type = summary.get("by_type", [])
        if by_type:
            print(f"\n  {'Component Type':<20} {'Count':<8} {'Planned':<10} {'Delivered'}")
            print(f"  {'-' * 50}")
            for row in by_type:
                print(f"  {row['component_type']:<20} {row['count']:<8} "
                      f"{row['planned']:<10} {row['delivered']}")

        # Also recalculate delivered hours
        recalc = input("\n  Recalculate delivered hours from components? (y/n) [n]: ").strip().lower()
        if recalc == "y":
            result = svc.update_delivered_hours(pid)
            print(f"  Updated total_delivered_hours to {result['total_delivered_hours']}.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _cof_check(svc):
    print_header("Condition of Funding Check")
    try:
        rows = svc.condition_of_funding_check()
        if not rows:
            print("\n  All active programmes meet maths/english requirements.")
            return

        print(f"\n  {len(rows)} programme(s) with unmet requirements:\n")
        print(f"  {'ID':<5} {'Student':<25} {'Type':<12} {'Maths':<12} {'English':<12} {'Year'}")
        print(f"  {'-' * 75}")
        for r in rows:
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or f"PK:{r['student_id']}"
            print(f"  {r['id']:<5} {name:<25} {r.get('programme_type', '-'):<12} "
                  f"{r.get('maths_requirement', '-'):<12} "
                  f"{r.get('english_requirement', '-'):<12} "
                  f"{r.get('academic_year') or '-'}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _funding_hours_report(svc):
    print_header("Funding Hours Report")
    try:
        year = input("  Academic Year (blank for all): ").strip() or None
        rows = svc.funding_hours_report(academic_year=year)
        if not rows:
            print("\n  No programmes found.")
            return

        print(f"\n  {'ID':<5} {'Student':<25} {'Type':<12} {'Year':<10} "
              f"{'Planned':<9} {'Delivered':<10} {'Valid':<6} {'Status'}")
        print(f"  {'-' * 85}")
        total_planned = 0
        total_delivered = 0
        for r in rows:
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or f"PK:{r['student_id']}"
            planned = r.get("total_planned_hours", 0)
            delivered = r.get("total_delivered_hours", 0)
            total_planned += planned
            total_delivered += delivered
            valid = "Yes" if r.get("is_valid") else "No"
            print(f"  {r['id']:<5} {name:<25} {r.get('programme_type', '-'):<12} "
                  f"{(r.get('academic_year') or '-'):<10} "
                  f"{planned:<9} {delivered:<10} {valid:<6} "
                  f"{r.get('status') or '-'}")
        print(f"  {'-' * 85}")
        print(f"  {'TOTALS':<52} {total_planned:<9} {total_delivered}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _statistics(svc):
    print_header("Study Programme Statistics")
    try:
        stats = svc.get_stats()
        print(f"\n  Total Programmes:     {stats['total_programmes']}")
        print(f"  Active Programmes:    {stats['active_programmes']}")
        print(f"  Valid Programmes:     {stats['valid_programmes']}")
        print(f"  Invalid Programmes:   {stats['invalid_programmes']}")
        print(f"  Avg Planned Hours:    {stats['avg_planned_hours']}")
        print(f"  Avg Delivered Hours:  {stats['avg_delivered_hours']}")
        print(f"  Maths Met/Exempt:     {stats['maths_met_pct']}%")
        print(f"  English Met/Exempt:   {stats['english_met_pct']}%")

        by_type = stats.get("by_type", {})
        if by_type:
            print(f"\n  By Programme Type:")
            for ptype, cnt in by_type.items():
                print(f"    {ptype}: {cnt}")

        by_status = stats.get("by_status", {})
        if by_status:
            print(f"\n  By Status:")
            for st, cnt in by_status.items():
                print(f"    {st}: {cnt}")
    except Exception as e:
        print(f"\n  Error: {e}")
