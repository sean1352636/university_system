"""Departments & Groups CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.departments.services.department_service import (
    DepartmentService, GroupService,
)
from education_system.college_system.infrastructure.auth.core import UserAuth


def departments_menu(auth: UserAuth):
    """Departments & Groups management menu."""
    dept_svc = DepartmentService(auth._db_path)
    grp_svc = GroupService(auth._db_path)
    role = auth.current_user.get("role", "student")
    is_admin = role in ("admin", "staff")

    while True:
        print_header("Departments & Groups")
        options = [
            ("1", "List Departments"),
        ]
        if is_admin:
            options.append(("2", "New Department"))
        options.extend([
            ("3", "View Department"),
            ("4", "List Tutor Groups"),
        ])
        if is_admin:
            options.append(("5", "New Tutor Group"))
        options.extend([
            ("6", "List Teaching Groups"),
        ])
        if is_admin:
            options.append(("7", "New Teaching Group"))
        options.extend([
            ("8", "Manage Members"),
            ("0", "Back"),
        ])
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _list_departments(dept_svc)
        elif choice == "2" and is_admin:
            _new_department(dept_svc)
        elif choice == "3":
            _view_department(dept_svc)
        elif choice == "4":
            _list_tutor_groups(grp_svc)
        elif choice == "5" and is_admin:
            _new_tutor_group(grp_svc)
        elif choice == "6":
            _list_teaching_groups(grp_svc)
        elif choice == "7" and is_admin:
            _new_teaching_group(grp_svc)
        elif choice == "8":
            _manage_members(grp_svc)
        elif choice == "0":
            break
        else:
            print("\n  Invalid option.")


def _list_departments(svc):
    print_header("All Departments")
    try:
        depts = svc.list_departments()
        if not depts:
            print("\n  No departments found.")
            return
        print(f"\n  {'ID':<5} {'Code':<10} {'Name':<25} {'Faculty':<20} {'Status':<10}")
        print(f"  {'-'*70}")
        for d in depts:
            print(f"  {d['id']:<5} {d['code']:<10} {d['name']:<25} "
                  f"{(d['faculty'] or '-'):<20} {d['status']:<10}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_department(svc):
    print_header("New Department")
    try:
        code = input("  Code: ").strip()
        name = input("  Name: ").strip()
        faculty = input("  Faculty (optional): ").strip() or None
        curriculum_area = input("  Curriculum Area (optional): ").strip() or None
        description = input("  Description (optional): ").strip() or None

        dept = svc.create_department(code, name, faculty=faculty,
                                     curriculum_area=curriculum_area,
                                     description=description)
        print(f"\n  Department created (ID: {dept['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_department(svc):
    print_header("View Department")
    try:
        dept_id = int(input("  Department ID: ").strip())
        dept = svc.get_department(dept_id)
        if not dept:
            print("\n  Department not found.")
            return
        print(f"\n  ID: {dept['id']}")
        print(f"  Code: {dept['code']}")
        print(f"  Name: {dept['name']}")
        print(f"  Faculty: {dept.get('faculty') or '-'}")
        print(f"  Curriculum Area: {dept.get('curriculum_area') or '-'}")
        print(f"  Status: {dept['status']}")

        courses = svc.get_department_courses(dept_id)
        if courses:
            print(f"\n  Courses ({len(courses)}):")
            for c in courses[:10]:
                print(f"    {c['course_code']} - {c.get('title', '')}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_tutor_groups(svc):
    print_header("Tutor Groups")
    try:
        groups = svc.list_tutor_groups()
        if not groups:
            print("\n  No tutor groups found.")
            return
        print(f"\n  {'ID':<5} {'Name':<15} {'Year':<6} {'Max':<5}")
        print(f"  {'-'*31}")
        for g in groups:
            print(f"  {g['id']:<5} {g['name']:<15} {(g['year_group'] or '-'):<6} {g['max_size']:<5}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_tutor_group(svc):
    print_header("New Tutor Group")
    try:
        name = input("  Name: ").strip()
        year_group = input("  Year Group (optional): ").strip() or None
        max_size_str = input("  Max Size [30]: ").strip()
        max_size = int(max_size_str) if max_size_str else 30

        group = svc.create_tutor_group(name, year_group=year_group, max_size=max_size)
        print(f"\n  Tutor group created (ID: {group['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _list_teaching_groups(svc):
    print_header("Teaching Groups")
    try:
        groups = svc.list_teaching_groups()
        if not groups:
            print("\n  No teaching groups found.")
            return
        print(f"\n  {'ID':<5} {'Name':<20} {'Course':<10} {'Year':<10} {'Max':<5}")
        print(f"  {'-'*50}")
        for g in groups:
            print(f"  {g['id']:<5} {g['name']:<20} {g['course_id']:<10} "
                  f"{(g.get('academic_year') or '-'):<10} {g['max_size']:<5}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_teaching_group(svc):
    print_header("New Teaching Group")
    try:
        name = input("  Name: ").strip()
        course_id = int(input("  Course ID: ").strip())
        academic_year = input("  Academic Year (optional): ").strip() or None
        max_size_str = input("  Max Size [30]: ").strip()
        max_size = int(max_size_str) if max_size_str else 30

        group = svc.create_teaching_group(name, course_id, academic_year=academic_year,
                                           max_size=max_size)
        print(f"\n  Teaching group created (ID: {group['id']}).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _manage_members(svc):
    print_header("Manage Members")
    try:
        group_type = input("  Group type (tutor/teaching): ").strip().lower()
        if group_type not in ("tutor", "teaching"):
            print("\n  Invalid group type.")
            return
        group_id = int(input("  Group ID: ").strip())

        members = svc.list_members(group_id, group_type)
        if members:
            print(f"\n  Current members ({len(members)}):")
            for m in members:
                print(f"    [{m['id']}] {m['sid']} - {m['first_name']} {m['last_name']}")

        action = input("\n  Action (add/remove/back): ").strip().lower()
        if action == "add":
            student_id = int(input("  Student PK: ").strip())
            svc.add_member(group_id, group_type, student_id)
            print("\n  Member added.")
        elif action == "remove":
            member_id = int(input("  Membership ID: ").strip())
            svc.remove_member(member_id)
            print("\n  Member removed.")
    except Exception as e:
        print(f"\n  Error: {e}")
