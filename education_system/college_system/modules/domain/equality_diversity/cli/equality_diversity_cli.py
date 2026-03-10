"""Equality & Diversity CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.equality_diversity.services.equality_diversity_service import EqualityDiversityService
from education_system.college_system.infrastructure.auth.core import UserAuth


def equality_diversity_menu(auth: UserAuth):
    """Equality & Diversity management menu."""
    svc = EqualityDiversityService(auth._db_path)

    while True:
        print_header("Equality & Diversity")
        options = [
            ("1", "List Characteristics"),
            ("2", "View Characteristics"),
            ("3", "New Characteristics Record"),
            ("4", "Update Characteristics"),
            ("5", "Delete Characteristics"),
            ("6", "List Impact Assessments"),
            ("7", "New Impact Assessment"),
            ("8", "Update Assessment"),
            ("9", "List Objectives"),
            ("10", "New Objective"),
            ("11", "Update Objective"),
            ("12", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            ptype = input("  Person type (student/staff or Enter): ").strip() or None
            records = svc.list_characteristics(person_type=ptype)
            for r in records:
                print(f"  [{r['id']}] {r.get('person_type', '')} #{r.get('person_id', '')} | "
                      f"Ethnicity: {r.get('ethnicity', '')} | "
                      f"Gender: {r.get('gender_identity', '')} | "
                      f"Disability: {r.get('disability_status', '')}")
            if not records:
                print("  No records found.")

        elif choice == "2":
            try:
                cid = int(input("  Record ID: ").strip())
                rec = svc.get_characteristic(cid)
                if not rec:
                    print("  Record not found.")
                    continue
                print(f"\n  Person Type:        {rec.get('person_type', '')}")
                print(f"  Person ID:          {rec.get('person_id', '')}")
                print(f"  Ethnicity:          {rec.get('ethnicity', '')}")
                print(f"  Religion:           {rec.get('religion', '')}")
                print(f"  Sexual Orientation: {rec.get('sexual_orientation', '')}")
                print(f"  Gender Identity:    {rec.get('gender_identity', '')}")
                print(f"  Disability Status:  {rec.get('disability_status', '')}")
                print(f"  Disability Details: {rec.get('disability_details', '')}")
                print(f"  Marital Status:     {rec.get('marital_status', '')}")
                print(f"  Preg./Maternity:    {rec.get('pregnancy_maternity', '')}")
                print(f"  Pronouns:           {rec.get('preferred_pronouns', '')}")
                print(f"  Consent:            {'Yes' if rec.get('consent_given') else 'No'}")
            except ValueError:
                print("  Invalid ID.")

        elif choice == "3":
            try:
                ptype = input("  Person type (student/staff): ").strip() or "student"
                pid = int(input("  Person ID: ").strip())
                ethnicity = input("  Ethnicity: ").strip() or None
                religion = input("  Religion: ").strip() or None
                gender = input("  Gender Identity: ").strip() or None
                disability = input("  Disability Status: ").strip() or None
                pronouns = input("  Preferred Pronouns: ").strip() or None
                rec = svc.create_characteristic(
                    ptype, pid, ethnicity=ethnicity, religion=religion,
                    gender_identity=gender, disability_status=disability,
                    preferred_pronouns=pronouns)
                print(f"\n  Record #{rec['id']} created.")
            except ValueError:
                print("  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                cid = int(input("  Record ID to update: ").strip())
                rec = svc.get_characteristic(cid)
                if not rec:
                    print("  Record not found.")
                    continue
                print("  (Press Enter to keep current value)")
                kwargs = {}
                for field, label in [
                    ("ethnicity", "Ethnicity"), ("religion", "Religion"),
                    ("gender_identity", "Gender Identity"),
                    ("disability_status", "Disability Status"),
                    ("preferred_pronouns", "Pronouns"),
                ]:
                    val = input(f"  {label} [{rec.get(field, '')}]: ").strip()
                    if val:
                        kwargs[field] = val
                if kwargs:
                    svc.update_characteristic(cid, **kwargs)
                    print("  Record updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                cid = int(input("  Record ID to delete: ").strip())
                confirm = input(f"  Delete record #{cid}? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_characteristic(cid)
                    print("  Record deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            records = svc.list_assessments()
            for r in records:
                print(f"  [{r['id']}] {r.get('policy_or_practice', '')} | "
                      f"{r.get('assessment_date', '')} | "
                      f"Impact: {r.get('impact_type', '')} | "
                      f"{r.get('status', '')}")
            if not records:
                print("  No impact assessments found.")

        elif choice == "7":
            try:
                policy = input("  Policy/Practice: ").strip()
                if not policy:
                    print("  Policy/Practice is required.")
                    continue
                assessor = input("  Assessor: ").strip() or None
                group = input("  Protected Group: ").strip() or None
                impact = input("  Impact type (positive/neutral/negative/mixed) [neutral]: ").strip() or "neutral"
                pi = input("  Potential Impact: ").strip() or None
                ma = input("  Mitigating Actions: ").strip() or None
                rec = svc.create_assessment(
                    policy, assessor=assessor, protected_group=group,
                    impact_type=impact, potential_impact=pi,
                    mitigating_actions=ma)
                print(f"\n  Assessment #{rec['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            try:
                eid = int(input("  Assessment ID to update: ").strip())
                rec = svc.get_assessment(eid)
                if not rec:
                    print("  Assessment not found.")
                    continue
                kwargs = {}
                status = input(f"  Status [{rec.get('status', '')}]: ").strip()
                if status:
                    kwargs["status"] = status
                impact = input(f"  Impact Type [{rec.get('impact_type', '')}]: ").strip()
                if impact:
                    kwargs["impact_type"] = impact
                ma = input(f"  Mitigating Actions: ").strip()
                if ma:
                    kwargs["mitigating_actions"] = ma
                if kwargs:
                    svc.update_assessment(eid, **kwargs)
                    print("  Assessment updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            status = input("  Status filter (active/completed or Enter): ").strip() or None
            records = svc.list_objectives(status=status)
            for r in records:
                print(f"  [{r['id']}] {(r.get('objective', '') or '')[:60]} | "
                      f"Group: {r.get('protected_group', '')} | "
                      f"Year: {r.get('academic_year', '')} | "
                      f"{r.get('status', '')}")
            if not records:
                print("  No objectives found.")

        elif choice == "10":
            try:
                obj = input("  Objective: ").strip()
                if not obj:
                    print("  Objective is required.")
                    continue
                group = input("  Protected Group: ").strip() or None
                target = input("  Target: ").strip() or None
                year = input("  Academic Year: ").strip() or None
                rec = svc.create_objective(
                    obj, protected_group=group, target=target,
                    academic_year=year)
                print(f"\n  Objective #{rec['id']} created.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                oid = int(input("  Objective ID to update: ").strip())
                rec = svc.get_objective(oid)
                if not rec:
                    print("  Objective not found.")
                    continue
                kwargs = {}
                progress = input(f"  Progress: ").strip()
                if progress:
                    kwargs["progress"] = progress
                status = input(f"  Status [{rec.get('status', '')}] (active/completed/on_hold/archived): ").strip()
                if status:
                    kwargs["status"] = status
                if kwargs:
                    svc.update_objective(oid, **kwargs)
                    print("  Objective updated.")
                else:
                    print("  Nothing to update.")
            except ValueError:
                print("  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "12":
            try:
                stats = svc.get_stats()
                print(f"\n  Characteristics Records:  {stats['total_records']}")
                print(f"  Student Records:          {stats['student_records']}")
                print(f"  Staff Records:            {stats['staff_records']}")
                print(f"  Disability Declared:      {stats['disability_declared']}")
                print(f"  Impact Assessments:       {stats['total_assessments']}")
                print(f"  Active Assessments:       {stats['active_assessments']}")
                print(f"  Total Objectives:         {stats['total_objectives']}")
                print(f"  Active Objectives:        {stats['active_objectives']}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
