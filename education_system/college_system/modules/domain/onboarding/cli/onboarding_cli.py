"""Staff Onboarding CLI module."""

from education_system.college_system.modules.shared.cli.cli_main import (
    print_header, print_menu, get_choice,
)
from education_system.college_system.modules.domain.onboarding.services.onboarding_service import OnboardingService
from education_system.college_system.infrastructure.auth.core import UserAuth


def onboarding_menu(auth: UserAuth):
    """Staff Onboarding management menu."""
    svc = OnboardingService(auth._db_path)

    while True:
        print_header("Staff Onboarding")
        options = [
            ("1", "List Checklists"),
            ("2", "View Checklist"),
            ("3", "New Checklist"),
            ("4", "Update Checklist"),
            ("5", "Complete Checklist"),
            ("6", "Delete Checklist"),
            ("7", "List Tasks"),
            ("8", "New Task"),
            ("9", "Complete Task"),
            ("10", "Pending Tasks"),
            ("11", "List Reviews"),
            ("12", "New Review"),
            ("13", "Update Review"),
            ("14", "Statistics"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "0":
            break
        elif choice == "1":
            _list_checklists(svc)
        elif choice == "2":
            _view_checklist(svc)
        elif choice == "3":
            _new_checklist(svc)
        elif choice == "4":
            _update_checklist(svc)
        elif choice == "5":
            _complete_checklist(svc)
        elif choice == "6":
            _delete_checklist(svc)
        elif choice == "7":
            _list_tasks(svc)
        elif choice == "8":
            _new_task(svc)
        elif choice == "9":
            _complete_task(svc)
        elif choice == "10":
            _pending_tasks(svc)
        elif choice == "11":
            _list_reviews(svc)
        elif choice == "12":
            _new_review(svc)
        elif choice == "13":
            _update_review(svc)
        elif choice == "14":
            _show_stats(svc)
        else:
            print("\n  Invalid option.")


# ── Checklists ──────────────────────────────────────────────────

def _list_checklists(svc):
    print_header("List Checklists")
    try:
        status_filter = input("  Filter by status (in_progress/completed/extended/failed) or Enter for all: ").strip()
        status = status_filter if status_filter else None
        items = svc.list_checklists(status=status)
        if not items:
            print("\n  No checklists found.")
            return
        print(
            "\n  "
            + "ID".ljust(6)
            + "Staff ID".ljust(10)
            + "Start Date".ljust(14)
            + "Mentor".ljust(8)
            + "Prob End".ljust(14)
            + "Outcome".ljust(12)
            + "Status".ljust(14)
        )
        print(f"  {'-' * 76}")
        for item in items:
            print(
                "  "
                + str(item.get("id", "")).ljust(6)
                + str(item.get("staff_id", "") or "").ljust(10)
                + str(item.get("start_date", "") or "")[:12].ljust(14)
                + str(item.get("mentor_id", "") or "").ljust(8)
                + str(item.get("probation_end_date", "") or "")[:12].ljust(14)
                + str(item.get("probation_outcome", "") or "").ljust(12)
                + str(item.get("overall_status", "") or "").ljust(14)
            )
        print(f"\n  Total: {len(items)} checklist(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


def _view_checklist(svc):
    print_header("View Checklist")
    try:
        pk = int(input("  Enter Checklist ID: ").strip())
        item = svc.get_checklist(pk)
        if not item:
            print("\n  Checklist not found.")
            return
        print()
        for k, v in item.items():
            print(f"  {k}: {v}")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_checklist(svc):
    print_header("New Checklist")
    try:
        staff_id = int(input("  Staff ID: ").strip())
        data = {}
        for field in ["start_date", "mentor_id", "probation_end_date", "notes"]:
            val = input(f"  {field}: ").strip()
            if val:
                data[field] = val
        if data.get("mentor_id"):
            data["mentor_id"] = int(data["mentor_id"])
        item = svc.create_checklist(staff_id, **data)
        print(f"\n  Checklist created with ID: {item['id']}")
    except ValueError:
        print("\n  Invalid numeric input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_checklist(svc):
    print_header("Update Checklist")
    try:
        pk = int(input("  Enter Checklist ID: ").strip())
        item = svc.get_checklist(pk)
        if not item:
            print("\n  Checklist not found.")
            return
        data = {}
        for field in ["start_date", "mentor_id", "probation_end_date", "notes"]:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data.get("mentor_id"):
            data["mentor_id"] = int(data["mentor_id"])
        if data:
            svc.update_checklist(pk, **data)
            print("\n  Checklist updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid numeric input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_checklist(svc):
    print_header("Complete Checklist")
    try:
        pk = int(input("  Enter Checklist ID: ").strip())
        outcome = input("  Outcome (completed/extended/failed) [completed]: ").strip()
        if not outcome:
            outcome = "completed"
        svc.complete_checklist(pk, outcome=outcome)
        print(f"\n  Checklist marked as '{outcome}'.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_checklist(svc):
    print_header("Delete Checklist")
    try:
        pk = int(input("  Enter Checklist ID: ").strip())
        confirm = input(f"  Delete checklist {pk} and all its tasks/reviews? (y/n): ").strip().lower()
        if confirm == "y":
            svc.delete_checklist(pk)
            print("\n  Checklist deleted.")
        else:
            print("\n  Cancelled.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Tasks ───────────────────────────────────────────────────────

def _list_tasks(svc):
    print_header("List Tasks")
    try:
        kwargs = {}
        cl_id = input("  Checklist ID (or Enter for all): ").strip()
        if cl_id:
            kwargs["checklist_id"] = int(cl_id)
        cat = input("  Category (or Enter for all): ").strip()
        if cat:
            kwargs["category"] = cat
        done = input("  Completed? (y/n or Enter for all): ").strip().lower()
        if done == "y":
            kwargs["completed"] = 1
        elif done == "n":
            kwargs["completed"] = 0
        items = svc.list_tasks(**kwargs)
        if not items:
            print("\n  No tasks found.")
            return
        print(
            "\n  "
            + "ID".ljust(6)
            + "CL".ljust(6)
            + "Task".ljust(25)
            + "Category".ljust(15)
            + "Assigned".ljust(10)
            + "Due".ljust(14)
            + "Done".ljust(6)
        )
        print(f"  {'-' * 80}")
        for item in items:
            done_str = "Yes" if item.get("completed") else "No"
            print(
                "  "
                + str(item.get("id", "")).ljust(6)
                + str(item.get("checklist_id", "")).ljust(6)
                + str(item.get("task_name", "") or "")[:23].ljust(25)
                + str(item.get("category", "") or "").ljust(15)
                + str(item.get("assigned_to", "") or "").ljust(10)
                + str(item.get("due_date", "") or "")[:12].ljust(14)
                + done_str.ljust(6)
            )
        print(f"\n  Total: {len(items)} task(s)")
    except ValueError:
        print("\n  Invalid numeric input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_task(svc):
    print_header("New Task")
    try:
        checklist_id = int(input("  Checklist ID: ").strip())
        task_name = input("  Task Name: ").strip()
        if not task_name:
            print("\n  Task name is required.")
            return
        data = {}
        cat = input("  Category [general]: ").strip()
        if cat:
            data["category"] = cat
        assigned = input("  Assigned To (ID): ").strip()
        if assigned:
            data["assigned_to"] = int(assigned)
        due = input("  Due Date (YYYY-MM-DD): ").strip()
        if due:
            data["due_date"] = due
        notes = input("  Notes: ").strip()
        if notes:
            data["notes"] = notes
        item = svc.create_task(checklist_id, task_name, **data)
        print(f"\n  Task created with ID: {item['id']}")
    except ValueError:
        print("\n  Invalid numeric input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _complete_task(svc):
    print_header("Complete Task")
    try:
        pk = int(input("  Enter Task ID: ").strip())
        svc.complete_task(pk)
        print("\n  Task marked as completed.")
    except ValueError:
        print("\n  Invalid ID.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _pending_tasks(svc):
    print_header("Pending Tasks")
    try:
        items = svc.get_pending_tasks()
        if not items:
            print("\n  No pending tasks.")
            return
        print(
            "\n  "
            + "ID".ljust(6)
            + "CL".ljust(6)
            + "Task".ljust(25)
            + "Category".ljust(15)
            + "Due".ljust(14)
            + "Staff".ljust(8)
        )
        print(f"  {'-' * 72}")
        for item in items:
            print(
                "  "
                + str(item.get("id", "")).ljust(6)
                + str(item.get("checklist_id", "")).ljust(6)
                + str(item.get("task_name", "") or "")[:23].ljust(25)
                + str(item.get("category", "") or "").ljust(15)
                + str(item.get("due_date", "") or "")[:12].ljust(14)
                + str(item.get("staff_id", "") or "").ljust(8)
            )
        print(f"\n  Total: {len(items)} pending task(s)")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Probation Reviews ──────────────────────────────────────────

def _list_reviews(svc):
    print_header("List Reviews")
    try:
        cl_id = input("  Checklist ID (or Enter for all): ").strip()
        checklist_id = int(cl_id) if cl_id else None
        items = svc.list_reviews(checklist_id=checklist_id)
        if not items:
            print("\n  No reviews found.")
            return
        print(
            "\n  "
            + "ID".ljust(6)
            + "CL".ljust(6)
            + "Date".ljust(14)
            + "Reviewer".ljust(10)
            + "Rev#".ljust(6)
            + "Rating".ljust(12)
            + "Recommendation".ljust(16)
        )
        print(f"  {'-' * 68}")
        for item in items:
            print(
                "  "
                + str(item.get("id", "")).ljust(6)
                + str(item.get("checklist_id", "")).ljust(6)
                + str(item.get("review_date", "") or "")[:12].ljust(14)
                + str(item.get("reviewer_id", "") or "").ljust(10)
                + str(item.get("review_number", "") or "").ljust(6)
                + str(item.get("performance_rating", "") or "")[:10].ljust(12)
                + str(item.get("recommendation", "") or "").ljust(16)
            )
        print(f"\n  Total: {len(items)} review(s)")
    except ValueError:
        print("\n  Invalid numeric input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _new_review(svc):
    print_header("New Review")
    try:
        checklist_id = int(input("  Checklist ID: ").strip())
        review_date = input("  Review Date (YYYY-MM-DD): ").strip()
        if not review_date:
            print("\n  Review date is required.")
            return
        data = {}
        reviewer = input("  Reviewer ID: ").strip()
        if reviewer:
            data["reviewer_id"] = int(reviewer)
        rev_num = input("  Review Number [1]: ").strip()
        if rev_num:
            data["review_number"] = int(rev_num)
        rating = input("  Performance Rating: ").strip()
        if rating:
            data["performance_rating"] = rating
        strengths = input("  Areas of Strength: ").strip()
        if strengths:
            data["areas_of_strength"] = strengths
        development = input("  Areas for Development: ").strip()
        if development:
            data["areas_for_development"] = development
        targets = input("  Targets: ").strip()
        if targets:
            data["targets"] = targets
        rec = input("  Recommendation (continue/extend/pass/fail) [continue]: ").strip()
        if rec:
            data["recommendation"] = rec
        item = svc.create_review(checklist_id, review_date, **data)
        print(f"\n  Review created with ID: {item['id']}")
    except ValueError:
        print("\n  Invalid numeric input.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _update_review(svc):
    print_header("Update Review")
    try:
        pk = int(input("  Enter Review ID: ").strip())
        item = svc.get_review(pk)
        if not item:
            print("\n  Review not found.")
            return
        data = {}
        for field in [
            "review_date", "reviewer_id", "review_number",
            "performance_rating", "areas_of_strength",
            "areas_for_development", "targets", "recommendation",
        ]:
            current = item.get(field, "")
            val = input(f"  {field} [{current}]: ").strip()
            if val:
                data[field] = val
        if data.get("reviewer_id"):
            data["reviewer_id"] = int(data["reviewer_id"])
        if data.get("review_number"):
            data["review_number"] = int(data["review_number"])
        if data:
            svc.update_review(pk, **data)
            print("\n  Review updated.")
        else:
            print("\n  No changes made.")
    except ValueError:
        print("\n  Invalid numeric input.")
    except Exception as e:
        print(f"\n  Error: {e}")


# ── Statistics ──────────────────────────────────────────────────

def _show_stats(svc):
    print_header("Onboarding Statistics")
    try:
        stats = svc.get_stats()
        print("\n  Checklists")
        print(f"    Total:       {stats['total_checklists']}")
        print(f"    In Progress: {stats['in_progress']}")
        print(f"    Completed:   {stats['completed']}")
        print(f"    Failed:      {stats['failed']}")
        print("\n  Tasks")
        print(f"    Total:           {stats['total_tasks']}")
        print(f"    Completed:       {stats['tasks_completed']}")
        print(f"    Pending:         {stats['tasks_pending']}")
        print(f"    Completion Rate: {stats['completion_rate']}%")
        print("\n  Probation Reviews")
        print(f"    Total: {stats['total_reviews']}")
        by_rec = stats.get("by_recommendation", {})
        if by_rec:
            print("    By Recommendation:")
            for rec, cnt in by_rec.items():
                print(f"      {rec}: {cnt}")
    except Exception as e:
        print(f"\n  Error: {e}")
