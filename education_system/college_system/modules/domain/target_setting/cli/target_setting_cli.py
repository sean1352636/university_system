"""Differentiated Target Setting CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.target_setting.services.target_setting_service import TargetSettingService
from education_system.college_system.infrastructure.auth.core import UserAuth


def _import_prior(svc):
    """Import a single prior attainment record."""
    print_header("Import Prior Attainment")
    try:
        sid = int(input("  Student ID: ").strip())
        qt = input("  Qualification type (gcse/btec): ").strip() or "gcse"
        subj = input("  Subject: ").strip()
        grade = input("  Grade: ").strip()
        pts = float(input("  Points: ").strip())
        ay = input("  Academic year: ").strip()
        if not subj or not grade or not ay:
            print("\n  Error: Subject, grade, and academic year are required.")
            return
        result = svc.import_prior_attainment(sid, qt, subj, grade, pts, ay)
        rid = result if isinstance(result, int) else result
        print(f"\n  Prior attainment #{rid} imported for student {sid}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _bulk_import_prior(svc):
    """Bulk import prior attainment records."""
    print_header("Bulk Import Prior Attainment")
    try:
        records = []
        print("  Enter records (blank student ID to finish):")
        while True:
            sid = input("    Student ID: ").strip()
            if not sid:
                break
            qt = input("    Qualification type (gcse/btec): ").strip() or "gcse"
            subj = input("    Subject: ").strip()
            grade = input("    Grade: ").strip()
            pts = input("    Points: ").strip()
            pts = float(pts) if pts else 0
            ay = input("    Academic year: ").strip()
            records.append({
                "student_id": int(sid),
                "qualification_type": qt,
                "subject": subj,
                "grade": grade,
                "points": pts,
                "academic_year": ay,
            })
        if not records:
            print("\n  No records entered.")
            return
        count = svc.bulk_import_prior_attainment(records)
        print(f"\n  {count} record(s) imported.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_prior(svc):
    """View student prior attainment."""
    print_header("Student Prior Attainment")
    try:
        sid = int(input("  Student ID: ").strip())
        records = svc.get_student_prior_attainment(sid)
        if not records:
            print(f"\n  No prior attainment found for student {sid}.")
        else:
            print(f"\n  {'Subject':<20} {'Grade':<8} {'Points':>8}")
            print("  " + "-" * 40)
            for r in records:
                print(f"  {(r.get('subject') or '')[:20]:<20} "
                      f"{(r.get('grade') or '-'):<8} "
                      f"{r.get('points', 0):>8.1f}")
        avg = svc.calculate_average_points(sid)
        print(f"\n  Average points: {avg:.2f}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _generate_targets(svc):
    """Generate targets for a student."""
    print_header("Generate Targets for Student")
    try:
        sid = int(input("  Student ID: ").strip())
        cid = int(input("  Course ID: ").strip())
        ay = input("  Academic year: ").strip()
        method = input("  Method (alps/custom, default=alps): ").strip() or "alps"
        result = svc.generate_targets(sid, cid, ay, method=method)
        tid = result if isinstance(result, int) else result.get('id', result)
        print(f"\n  Target #{tid} generated for student {sid} on course {cid}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _bulk_generate(svc):
    """Bulk generate targets for a course."""
    print_header("Bulk Generate Targets")
    try:
        cid = int(input("  Course ID: ").strip())
        ay = input("  Academic year: ").strip()
        method = input("  Method (alps/custom, default=alps): ").strip() or "alps"
        count = svc.bulk_generate_targets(cid, ay, method=method)
        print(f"\n  Generated targets for {count} student(s).")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_targets(svc):
    """View targets with filters."""
    print_header("View Targets")
    try:
        sid = input("  Student ID filter (Enter for all): ").strip()
        sid = int(sid) if sid else None
        cid = input("  Course ID filter (Enter for all): ").strip()
        cid = int(cid) if cid else None
        ay = input("  Academic year filter (Enter for all): ").strip() or None
        targets = svc.get_targets(student_id=sid, course_id=cid, academic_year=ay)
        if not targets:
            print("\n  No targets found.")
        else:
            print(f"\n  {'ID':<5} {'Student':>8} {'Course':>7} {'MEG':<5} "
                  f"{'Target':<7} {'Aspir':<6} {'Current':<8} {'VA':>6}")
            print("  " + "-" * 58)
            for t in targets:
                va = t.get('value_added')
                va_str = f"{va:>6.2f}" if va is not None else "     -"
                print(f"  {t['id']:<5} {t.get('student_id', ''):>8} "
                      f"{t.get('course_id', ''):>7} "
                      f"{(t.get('meg_grade') or '-'):<5} "
                      f"{(t.get('target_grade') or '-'):<7} "
                      f"{(t.get('aspirational_grade') or '-'):<6} "
                      f"{(t.get('current_grade') or '-'):<8} "
                      f"{va_str}")
            print(f"\n  Total: {len(targets)} target(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_current(svc):
    """Update current grade for a target."""
    print_header("Update Current Grade")
    try:
        tid = int(input("  Target ID: ").strip())
        grade = input("  Current grade: ").strip()
        if not grade:
            print("\n  Error: Grade is required.")
            return
        svc.update_current_grade(tid, grade)
        print("\n  Current grade updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _calculate_va(svc):
    """Calculate value added for a target."""
    print_header("Calculate Value Added")
    try:
        tid = int(input("  Target ID: ").strip())
        result = svc.calculate_value_added(tid)
        if isinstance(result, dict):
            print(f"\n  Target #{result.get('id', tid)}")
            print(f"  MEG Grade:     {result.get('meg_grade', '-')}")
            print(f"  Current Grade: {result.get('current_grade', '-')}")
            va = result.get('value_added')
            if va is not None:
                print(f"  Value Added:   {va:+.2f}")
            else:
                print("  Value Added:   Not calculable (missing current/MEG grade)")
        else:
            print(f"\n  Value added calculated for target #{tid}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _course_va_report(svc):
    """Course value-added report."""
    print_header("Course Value-Added Report")
    try:
        cid = int(input("  Course ID: ").strip())
        ay = input("  Academic year: ").strip()
        records = svc.get_course_value_added(cid, ay)
        if not records:
            print("\n  No value-added data found.")
        else:
            print(f"\n  {'Student':>8} {'MEG':<5} {'Target':<7} "
                  f"{'Current':<8} {'VA':>6}")
            print("  " + "-" * 40)
            for r in records:
                va = r.get('value_added')
                va_str = f"{va:>+6.2f}" if va is not None else "     -"
                print(f"  {r.get('student_id', ''):>8} "
                      f"{(r.get('meg_grade') or '-'):<5} "
                      f"{(r.get('target_grade') or '-'):<7} "
                      f"{(r.get('current_grade') or '-'):<8} "
                      f"{va_str}")
            print(f"\n  Total: {len(records)} student(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _alps_summary(svc):
    """ALPS summary for an academic year."""
    print_header("ALPS Summary")
    try:
        ay = input("  Academic year: ").strip()
        summary = svc.get_alps_summary(ay)
        if not summary or not summary.get('num_targets'):
            print("\n  No ALPS data found for this academic year.")
        else:
            print(f"\n  {'Metric':<25} {'Value':>12}")
            print("  " + "-" * 40)
            print(f"  {'Total Targets':<25} {summary.get('num_targets', 0):>12}")
            avg_va = summary.get('avg_va')
            avg_va_str = f"{avg_va:>+12.2f}" if avg_va is not None else "           -"
            print(f"  {'Average Value Added':<25} {avg_va_str}")
            avg_alps = summary.get('avg_alps')
            alps_str = f"{avg_alps:>12.2f}" if avg_alps is not None else "           -"
            print(f"  {'Average ALPS Score':<25} {alps_str}")
            print(f"  {'Positive VA':<25} {summary.get('positive_va', 0):>12}")
            print(f"  {'Negative VA':<25} {summary.get('negative_va', 0):>12}")
            print(f"  {'On Target':<25} {summary.get('on_target', 0):>12}")
    except Exception as e:
        print(f"\n  Error: {e}")


def _manage_benchmarks(svc):
    """List or add ALPS benchmarks."""
    print_header("Manage ALPS Benchmarks")
    sub = input("  [1] List benchmarks  [2] Add benchmark: ").strip()
    if sub == "1":
        try:
            qt = input("  Qualification type filter (Enter for all): ").strip() or None
            ay = input("  Academic year filter (Enter for all): ").strip() or None
            benchmarks = svc.list_benchmarks(qualification_type=qt, academic_year=ay)
            if not benchmarks:
                print("\n  No benchmarks found.")
            else:
                print(f"\n  {'ID':<5} {'Type':<8} {'Min':>6} {'Max':>6} "
                      f"{'Group':<12} {'MEG':<5} {'Target':<7} {'Aspir':<6} {'Year':<10}")
                print("  " + "-" * 70)
                for b in benchmarks:
                    print(f"  {b['id']:<5} "
                          f"{(b.get('qualification_type') or '-'):<8} "
                          f"{b.get('prior_points_min', 0):>6.1f} "
                          f"{b.get('prior_points_max', 0):>6.1f} "
                          f"{(b.get('subject_group') or '-')[:12]:<12} "
                          f"{(b.get('meg_grade') or '-'):<5} "
                          f"{(b.get('target_grade') or '-'):<7} "
                          f"{(b.get('aspirational_grade') or '-'):<6} "
                          f"{(b.get('academic_year') or '-'):<10}")
                print(f"\n  Total: {len(benchmarks)} benchmark(s)")
        except Exception as e:
            print(f"\n  Error: {e}")
    elif sub == "2":
        try:
            qt = input("  Qualification type (gcse/btec/alevel): ").strip()
            pmin = float(input("  Prior points min: ").strip())
            pmax = float(input("  Prior points max: ").strip())
            group = input("  Subject group: ").strip()
            meg = input("  MEG grade: ").strip()
            target = input("  Target grade: ").strip()
            aspir = input("  Aspirational grade: ").strip()
            ay = input("  Academic year: ").strip()
            result = svc.set_benchmark(qt, pmin, pmax, group, meg, target, aspir, ay)
            bid = result if isinstance(result, int) else result
            print(f"\n  Benchmark #{bid} added.")
        except Exception as e:
            print(f"\n  Error: {e}")
    else:
        print("\n  Invalid option.")


def target_setting_menu(auth: UserAuth):
    """Differentiated Target Setting management menu."""
    svc = TargetSettingService(auth._db_path)

    while True:
        print_header("Differentiated Target Setting")
        options = [
            ("1", "Import Prior Attainment"),
            ("2", "Bulk Import Prior Attainment"),
            ("3", "View Student Prior Attainment"),
            ("4", "Generate Targets for Student"),
            ("5", "Bulk Generate Targets (Course)"),
            ("6", "View Targets"),
            ("7", "Update Current Grade"),
            ("8", "Calculate Value Added"),
            ("9", "Course Value-Added Report"),
            ("10", "ALPS Summary"),
            ("11", "Manage Benchmarks"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _import_prior(svc)
        elif choice == "2":
            _bulk_import_prior(svc)
        elif choice == "3":
            _view_prior(svc)
        elif choice == "4":
            _generate_targets(svc)
        elif choice == "5":
            _bulk_generate(svc)
        elif choice == "6":
            _view_targets(svc)
        elif choice == "7":
            _update_current(svc)
        elif choice == "8":
            _calculate_va(svc)
        elif choice == "9":
            _course_va_report(svc)
        elif choice == "10":
            _alps_summary(svc)
        elif choice == "11":
            _manage_benchmarks(svc)
        else:
            print("\n  Invalid option.")
