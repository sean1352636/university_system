"""Baseline Assessment CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.baseline_assessment.services.baseline_assessment_service import BaselineAssessmentService
from education_system.college_system.infrastructure.auth.core import UserAuth


def baseline_assessment_menu(auth: UserAuth):
    """Baseline Assessment management menu."""
    svc = BaselineAssessmentService(auth._db_path)

    while True:
        print_header("Baseline Assessment")
        options = [
            ("1", "List Baselines"),
            ("2", "View Baseline"),
            ("3", "New Baseline"),
            ("4", "Update Baseline"),
            ("5", "Delete Baseline"),
            ("6", "List Checkpoints"),
            ("7", "New Checkpoint"),
            ("8", "Update Checkpoint"),
            ("9", "Delete Checkpoint"),
            ("10", "Student Progress"),
            ("11", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break

        elif choice == "1":
            year = input("  Academic year (or Enter for all): ").strip() or None
            atype = input("  Assessment type (or Enter for all): ").strip() or None
            search = input("  Search name (or Enter for all): ").strip() or None
            rows = svc.list_baselines(academic_year=year,
                                      assessment_type=atype, search=search)
            if not rows:
                print("\n  No baselines found.")
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                print(f"  [{r['id']}] {name} | {r.get('academic_year', '')} | "
                      f"{r.get('assessment_type', '')} | E:{r.get('english_score', '')} "
                      f"M:{r.get('maths_score', '')} I:{r.get('ict_score', '')} | "
                      f"Overall: {r.get('overall_baseline', '')}")

        elif choice == "2":
            try:
                bid = int(input("  Baseline ID: ").strip())
                record = svc.get_baseline(bid)
                if not record:
                    print("\n  Baseline not found.")
                else:
                    print()
                    for k, v in record.items():
                        print(f"  {k}: {v}")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "3":
            try:
                sid = int(input("  Student ID: ").strip())
                kwargs = {}
                val = input("  Academic Year: ").strip()
                if val:
                    kwargs["academic_year"] = val
                val = input("  Assessment Type (initial/mid-year/end-of-year/diagnostic): ").strip()
                if val:
                    kwargs["assessment_type"] = val
                val = input("  Assessment Date (YYYY-MM-DD, Enter for today): ").strip()
                if val:
                    kwargs["assessment_date"] = val
                val = input("  English Score: ").strip()
                if val:
                    kwargs["english_score"] = float(val)
                val = input("  Maths Score: ").strip()
                if val:
                    kwargs["maths_score"] = float(val)
                val = input("  ICT Score: ").strip()
                if val:
                    kwargs["ict_score"] = float(val)
                val = input("  Learning Style (visual/auditory/kinesthetic/read-write): ").strip()
                if val:
                    kwargs["learning_style"] = val
                val = input("  Prior Attainment: ").strip()
                if val:
                    kwargs["prior_attainment"] = val
                val = input("  GCSE English Grade: ").strip()
                if val:
                    kwargs["gcse_english_grade"] = val
                val = input("  GCSE Maths Grade: ").strip()
                if val:
                    kwargs["gcse_maths_grade"] = val
                val = input("  Overall Baseline: ").strip()
                if val:
                    kwargs["overall_baseline"] = val
                val = input("  Additional Needs Identified: ").strip()
                if val:
                    kwargs["additional_needs_identified"] = val
                val = input("  Assessor ID: ").strip()
                if val:
                    kwargs["assessor_id"] = int(val)
                val = input("  Notes: ").strip()
                if val:
                    kwargs["notes"] = val
                result = svc.create_baseline(sid, **kwargs)
                print(f"\n  Baseline #{result['id']} created.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "4":
            try:
                bid = int(input("  Baseline ID: ").strip())
                record = svc.get_baseline(bid)
                if not record:
                    print("\n  Baseline not found.")
                    continue
                print("  (Press Enter to keep current value)")
                kwargs = {}
                val = input(f"  Academic Year [{record.get('academic_year', '')}]: ").strip()
                if val:
                    kwargs["academic_year"] = val
                val = input(f"  Assessment Type [{record.get('assessment_type', '')}]: ").strip()
                if val:
                    kwargs["assessment_type"] = val
                val = input(f"  English Score [{record.get('english_score', '')}]: ").strip()
                if val:
                    kwargs["english_score"] = float(val)
                val = input(f"  Maths Score [{record.get('maths_score', '')}]: ").strip()
                if val:
                    kwargs["maths_score"] = float(val)
                val = input(f"  ICT Score [{record.get('ict_score', '')}]: ").strip()
                if val:
                    kwargs["ict_score"] = float(val)
                val = input(f"  Overall Baseline [{record.get('overall_baseline', '')}]: ").strip()
                if val:
                    kwargs["overall_baseline"] = val
                val = input(f"  Notes [{record.get('notes', '')}]: ").strip()
                if val:
                    kwargs["notes"] = val
                if kwargs:
                    svc.update_baseline(bid, **kwargs)
                    print("  Baseline updated.")
                else:
                    print("  No changes made.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "5":
            try:
                bid = int(input("  Baseline ID to delete: ").strip())
                confirm = input("  Confirm delete? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_baseline(bid)
                    print("  Baseline deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "6":
            sid_str = input("  Student ID (or Enter for all): ").strip()
            cid_str = input("  Course ID (or Enter for all): ").strip()
            sid = int(sid_str) if sid_str else None
            cid = int(cid_str) if cid_str else None
            rows = svc.list_checkpoints(student_id=sid, course_id=cid)
            if not rows:
                print("\n  No checkpoints found.")
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip() or str(r.get("student_id", ""))
                att = f"{r['attendance_pct']:.0f}%" if r.get("attendance_pct") is not None else "N/A"
                print(f"  [{r['id']}] {name} | CP#{r.get('checkpoint_number', '')} "
                      f"| {r.get('checkpoint_date', '')} | Current: {r.get('current_grade', '')} "
                      f"Target: {r.get('target_grade', '')} | Effort: {r.get('effort_grade', '')} "
                      f"| Att: {att}")

        elif choice == "7":
            try:
                sid = int(input("  Student ID: ").strip())
                cp_date = input("  Checkpoint Date (YYYY-MM-DD): ").strip()
                if not cp_date:
                    print("\n  Checkpoint date is required.")
                    continue
                kwargs = {}
                val = input("  Course ID: ").strip()
                if val:
                    kwargs["course_id"] = int(val)
                val = input("  Checkpoint Number: ").strip()
                if val:
                    kwargs["checkpoint_number"] = int(val)
                val = input("  Current Grade: ").strip()
                if val:
                    kwargs["current_grade"] = val
                val = input("  Target Grade: ").strip()
                if val:
                    kwargs["target_grade"] = val
                val = input("  Effort Grade (1-5): ").strip()
                if val:
                    kwargs["effort_grade"] = val
                val = input("  Attendance %: ").strip()
                if val:
                    kwargs["attendance_pct"] = float(val)
                val = input("  Concerns: ").strip()
                if val:
                    kwargs["concerns"] = val
                val = input("  Actions: ").strip()
                if val:
                    kwargs["actions"] = val
                val = input("  Reviewer ID: ").strip()
                if val:
                    kwargs["reviewer_id"] = int(val)
                result = svc.create_checkpoint(sid, cp_date, **kwargs)
                print(f"\n  Checkpoint #{result['id']} created.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "8":
            try:
                cpid = int(input("  Checkpoint ID: ").strip())
                record = svc.get_checkpoint(cpid)
                if not record:
                    print("\n  Checkpoint not found.")
                    continue
                print("  (Press Enter to keep current value)")
                kwargs = {}
                val = input(f"  Current Grade [{record.get('current_grade', '')}]: ").strip()
                if val:
                    kwargs["current_grade"] = val
                val = input(f"  Target Grade [{record.get('target_grade', '')}]: ").strip()
                if val:
                    kwargs["target_grade"] = val
                val = input(f"  Effort Grade [{record.get('effort_grade', '')}]: ").strip()
                if val:
                    kwargs["effort_grade"] = val
                val = input(f"  Attendance % [{record.get('attendance_pct', '')}]: ").strip()
                if val:
                    kwargs["attendance_pct"] = float(val)
                val = input(f"  Concerns [{record.get('concerns', '')}]: ").strip()
                if val:
                    kwargs["concerns"] = val
                val = input(f"  Actions [{record.get('actions', '')}]: ").strip()
                if val:
                    kwargs["actions"] = val
                if kwargs:
                    svc.update_checkpoint(cpid, **kwargs)
                    print("  Checkpoint updated.")
                else:
                    print("  No changes made.")
            except ValueError:
                print("\n  Invalid input.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "9":
            try:
                cpid = int(input("  Checkpoint ID to delete: ").strip())
                confirm = input("  Confirm delete? (y/n): ").strip().lower()
                if confirm == "y":
                    svc.delete_checkpoint(cpid)
                    print("  Checkpoint deleted.")
                else:
                    print("  Cancelled.")
            except ValueError:
                print("\n  Invalid ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "10":
            try:
                sid = int(input("  Student ID: ").strip())
                progress = svc.get_student_progress(sid)
                baselines = progress["baselines"]
                checkpoints = progress["checkpoints"]
                if baselines:
                    name = f"{baselines[0].get('first_name', '')} {baselines[0].get('last_name', '')}".strip()
                    print(f"\n  Student: {name or sid}")
                else:
                    print(f"\n  Student ID: {sid}")
                print(f"\n  --- Baselines ({len(baselines)}) ---")
                for b in baselines:
                    print(f"    [{b['id']}] {b.get('assessment_type', '')} "
                          f"| {b.get('assessment_date', '')} "
                          f"| E:{b.get('english_score', '')} M:{b.get('maths_score', '')} "
                          f"I:{b.get('ict_score', '')} | Overall: {b.get('overall_baseline', '')}")
                if not baselines:
                    print("    No baselines recorded.")
                print(f"\n  --- Checkpoints ({len(checkpoints)}) ---")
                for c in checkpoints:
                    att = f"{c['attendance_pct']:.0f}%" if c.get("attendance_pct") is not None else "N/A"
                    print(f"    [{c['id']}] CP#{c.get('checkpoint_number', '')} "
                          f"| {c.get('checkpoint_date', '')} "
                          f"| Current: {c.get('current_grade', '')} "
                          f"Target: {c.get('target_grade', '')} "
                          f"| Effort: {c.get('effort_grade', '')} | Att: {att}")
                if not checkpoints:
                    print("    No checkpoints recorded.")
            except ValueError:
                print("\n  Invalid Student ID.")
            except Exception as e:
                print(f"\n  Error: {e}")

        elif choice == "11":
            try:
                stats = svc.get_stats()
                print(f"\n  Total Baselines:   {stats['total_baselines']}")
                print(f"  Total Checkpoints: {stats['total_checkpoints']}")
                print(f"\n  Average Scores:")
                print(f"    English: {stats['avg_english'] or 'N/A'}")
                print(f"    Maths:   {stats['avg_maths'] or 'N/A'}")
                print(f"    ICT:     {stats['avg_ict'] or 'N/A'}")
                print(f"\n  Baselines by Type:")
                for t, cnt in stats.get("by_type", {}).items():
                    print(f"    {t or 'unspecified':20s} {cnt}")
            except Exception as e:
                print(f"\n  Error: {e}")

        else:
            print("\n  Invalid option.")
