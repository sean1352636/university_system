"""Curriculum Specification CLI — programme specs, module descriptors, change control."""


def display_curriculum_specification_menu(auth):
    from education_system.post_18.university_system.modules.domain.academics.curriculum_specification.services.curriculum_specification_service import (
        CurriculumSpecificationService,
    )
    service = CurriculumSpecificationService()
    user = (auth.current_user.get("username") if getattr(auth, "current_user", None) else None) or "system"

    while True:
        print("\033[2J\033[H", end="")
        print("\n" + "=" * 70)
        print("CURRICULUM SPECIFICATION".center(70))
        print("(Programme Specs, Module Descriptors & Change Control)".center(70))
        print("=" * 70)
        print("\n  1. List Programmes")
        print("  2. Add Programme")
        print("  3. Programme Summary")
        print("  4. Manage Module Descriptors")
        print("  5. Manage Learning Outcomes")
        print("  6. Manage Assessment Strategy")
        print("  7. Validate Module Assessment")
        print("  8. Change Control (propose / approve)")
        print("  9. Approve Programme")
        print(" 10. New Programme Version")
        print(" 11. Generate Course Handbook")
        print(" 12. Examiner Findings")
        print(" 13. Export Handbook to file")
        print("\n  0. Back")
        print("=" * 70)

        choice = input("\nSelect: ").strip()
        if choice == "0":
            break
        try:
            if choice == "1":
                rows = service.list_programmes()
                print(f"\n{'ID':<5} {'Code':<10} {'Ver':<6} {'Title':<35} {'Status':<12}")
                print("-" * 70)
                for p in rows:
                    print(f"{p['id']:<5} {p['code']:<10} {p['version']:<6} "
                          f"{(p['title'] or '')[:33]:<35} {p['status']:<12}")
                input("\nPress Enter…")
            elif choice == "2":
                code = input("Code: ").strip()
                title = input("Title: ").strip()
                award = input("Award (e.g. BSc Hons): ").strip()
                level = input("Level (e.g. 6): ").strip()
                credits = input("Total credits: ").strip()
                dept = input("Department: ").strip()
                aims = input("Educational aims: ").strip()
                pid = service.create_programme(
                    code=code, title=title, award=award, level=level,
                    credits=int(credits) if credits else None,
                    department=dept, educational_aims=aims, created_by=user,
                )
                print(f"\nProgramme created with ID: {pid}")
                input("Press Enter…")
            elif choice == "3":
                pid = int(input("Programme ID: ").strip())
                s = service.programme_summary(pid)
                if not s:
                    print("Not found.")
                else:
                    p = s["programme"]
                    print(f"\n{p['code']} v{p['version']} — {p['title']}")
                    print(f"  Status: {p['status']}    Department: {p.get('department') or 'n/a'}")
                    print(f"  Modules: {s['module_count']} ({s['core_modules']} core, "
                          f"{s['optional_modules']} optional) — {s['total_credits']} credits")
                    print(f"  Programme LOs: {s['programme_los']}")
                    print(f"  Pending changes: {s['pending_changes']}")
                input("\nPress Enter…")
            elif choice == "4":
                _module_descriptors_submenu(service, user)
            elif choice == "5":
                _learning_outcomes_submenu(service)
            elif choice == "6":
                _assessment_submenu(service)
            elif choice == "7":
                mid = int(input("Module Descriptor ID: ").strip())
                v = service.validate_assessment_strategy(mid)
                print(f"\nValid: {v['valid']}    Total weight: {v['total']:.2f}%")
                for issue in v["issues"]:
                    print(f"  • {issue}")
                input("\nPress Enter…")
            elif choice == "8":
                _change_control_submenu(service, user)
            elif choice == "9":
                pid = int(input("Programme ID: ").strip())
                service.approve_programme(pid, user)
                print("Programme approved.")
                input("Press Enter…")
            elif choice == "10":
                pid = int(input("Programme ID: ").strip())
                ver = input("New version (e.g. 2.0): ").strip()
                new_id = service.new_programme_version(pid, ver, user)
                print(f"New version created with ID: {new_id}")
                input("Press Enter…")
            elif choice == "11":
                pid = int(input("Programme ID: ").strip())
                handbook = service.generate_handbook(pid)
                print("\n" + handbook)
                input("\nPress Enter…")
            elif choice == "12":
                mid = int(input("Module Descriptor ID: ").strip())
                md = service.get_module_descriptor(mid)
                if not md:
                    print("Descriptor not found.")
                else:
                    rows = service.examiner_findings_for_module(mid)
                    print(f"\nExaminer findings referencing {md['module_code']} ({len(rows)}):")
                    if not rows:
                        print("  (none)")
                    for r in rows:
                        print(f"  [{r.get('visit_date') or ''}] {r.get('examiner') or ''} — "
                              f"{r.get('department') or ''} — {r.get('overall_rating') or 'N/A'}")
                        if r.get("findings"):
                            print(f"      {r['findings'][:80]}")
                input("\nPress Enter…")
            elif choice == "13":
                pid = int(input("Programme ID: ").strip())
                handbook = service.generate_handbook(pid)
                path = input("Output file path: ").strip()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(handbook)
                print(f"Handbook saved to {path}")
                input("Press Enter…")
        except Exception as e:
            print(f"\nError: {e}")
            input("Press Enter…")


def _module_descriptors_submenu(service, user):
    pid_in = input("Filter by Programme ID (blank for all): ").strip()
    pid = int(pid_in) if pid_in else None
    rows = service.list_module_descriptors(pid)
    print(f"\n{'ID':<5} {'Code':<10} {'Ver':<5} {'Title':<30} {'Cr':<4} {'Core':<5}")
    print("-" * 60)
    for m in rows:
        print(f"{m['id']:<5} {m['module_code']:<10} {m['version']:<5} "
              f"{(m['title'] or '')[:28]:<30} {(m.get('credits') or 0):<4} "
              f"{'Y' if m.get('is_core') else 'N':<5}")
    sub = input("\n(a)dd, (e)dit, Enter to back: ").strip().lower()
    if sub == "a":
        prog_in = input("Programme ID (blank=none): ").strip()
        code = input("Module code: ").strip()
        title = input("Title: ").strip()
        credits = input("Credits: ").strip()
        level = input("Level: ").strip()
        is_core = input("Core? (y/n): ").strip().lower() == "y"
        aims = input("Aims: ").strip()
        new_id = service.create_module_descriptor(
            programme_id=int(prog_in) if prog_in else None,
            module_code=code, title=title,
            credits=int(credits) if credits else None,
            level=level, is_core=1 if is_core else 0,
            aims=aims, created_by=user,
        )
        print(f"Descriptor created with ID: {new_id}")
        input("Press Enter…")
    elif sub == "e":
        mid = int(input("Descriptor ID: ").strip())
        field = input("Field to update: ").strip()
        value = input("New value: ").strip()
        if field == "is_core":
            value = 1 if value.lower() in ("y", "yes", "1", "true") else 0
        elif field in ("credits", "contact_hours", "independent_study_hours", "programme_id"):
            value = int(value) if value else None
        service.update_module_descriptor(mid, **{field: value})
        print("Updated.")
        input("Press Enter…")


def _learning_outcomes_submenu(service):
    parent_type = input("Parent type (programme/module): ").strip()
    parent_id = int(input(f"{parent_type} ID: ").strip())
    rows = service.list_learning_outcomes(parent_type, parent_id)
    print(f"\n{'ID':<5} {'Code':<6} {'Domain':<14} {'Bloom':<10} Description")
    print("-" * 70)
    for lo in rows:
        print(f"{lo['id']:<5} {(lo.get('code') or ''):<6} "
              f"{(lo.get('domain') or ''):<14} {(lo.get('bloom_level') or ''):<10} "
              f"{lo['description'][:40]}")
    sub = input("\n(a)dd, (d)elete, Enter to back: ").strip().lower()
    if sub == "a":
        code = input("Code (e.g. LO1): ").strip()
        domain = input("Domain (knowledge/skills/professional/transferable): ").strip()
        bloom = input("Bloom level (e.g. apply, evaluate): ").strip()
        desc = input("Description: ").strip()
        service.add_learning_outcome(parent_type, parent_id, desc, code or None,
                                     domain or None, bloom or None)
        print("Added.")
        input("Press Enter…")
    elif sub == "d":
        lo_id = int(input("LO ID: ").strip())
        service.delete_learning_outcome(lo_id)
        print("Deleted.")
        input("Press Enter…")


def _assessment_submenu(service):
    mid = int(input("Module Descriptor ID: ").strip())
    rows = service.list_assessment_components(mid)
    print(f"\n{'ID':<5} {'Name':<25} {'Type':<14} {'Weight':<8} {'LOs':<10}")
    print("-" * 65)
    for c in rows:
        w = f"{c.get('weighting_pct') or 0:.1f}%"
        print(f"{c['id']:<5} {(c.get('name') or '')[:23]:<25} "
              f"{(c.get('assessment_type') or ''):<14} {w:<8} "
              f"{(c.get('learning_outcomes_assessed') or ''):<10}")
    total = service.assessment_weighting_total(mid)
    print(f"\nTotal weighting: {total:.2f}%")
    sub = input("\n(a)dd, (d)elete, Enter to back: ").strip().lower()
    if sub == "a":
        name = input("Name: ").strip()
        a_type = input("Type (exam/coursework/presentation/practical/dissertation/portfolio/lab_report/other): ").strip()
        weight = input("Weighting %: ").strip()
        los = input("LOs assessed (e.g. LO1,LO2): ").strip()
        feedback = input("Feedback method: ").strip()
        service.add_assessment_component(
            mid, name=name, assessment_type=a_type or None,
            weighting_pct=float(weight) if weight else None,
            learning_outcomes_assessed=los or None,
            feedback_method=feedback or None,
        )
        print("Added.")
        input("Press Enter…")
    elif sub == "d":
        cid = int(input("Component ID: ").strip())
        service.delete_assessment_component(cid)
        print("Deleted.")
        input("Press Enter…")


def _change_control_submenu(service, user):
    print("\n  1. List proposed changes")
    print("  2. Propose change")
    print("  3. Approve change")
    print("  4. Reject change")
    sub = input("\nSelect: ").strip()
    if sub == "1":
        status = input("Filter by status (proposed/approved/rejected, blank=all): ").strip() or None
        rows = service.list_changes(status=status)
        print(f"\n{'ID':<5} {'Type':<10} {'Parent':<12} {'Status':<10} Summary")
        print("-" * 75)
        for c in rows:
            print(f"{c['id']:<5} {(c.get('change_type') or ''):<10} "
                  f"{c['parent_type']}#{c['parent_id']:<6} {c['status']:<10} "
                  f"{(c['summary'] or '')[:40]}")
        input("\nPress Enter…")
    elif sub == "2":
        ptype = input("Parent type (programme/module): ").strip()
        pid = int(input(f"{ptype} ID: ").strip())
        ctype = input("Change type (minor/major/cosmetic): ").strip()
        from_v = input("From version: ").strip()
        to_v = input("To version: ").strip()
        summary = input("Summary: ").strip()
        rationale = input("Rationale: ").strip()
        impact = input("Impact (students/staff/resources): ").strip()
        new_id = service.propose_change(ptype, pid, summary, from_v or None, to_v or None,
                                        ctype or None, rationale or None, impact or None,
                                        proposed_by=user)
        print(f"Change proposed with ID: {new_id}")
        input("Press Enter…")
    elif sub == "3":
        cid = int(input("Change ID: ").strip())
        service.approve_change(cid, user)
        print("Approved.")
        input("Press Enter…")
    elif sub == "4":
        cid = int(input("Change ID: ").strip())
        reason = input("Reason: ").strip()
        service.reject_change(cid, user, reason or None)
        print("Rejected.")
        input("Press Enter…")
