"""CLI interface for To-Do list management."""

from education_system.college_system.modules.shared.cli.cli_main import print_header, print_menu, get_choice
from education_system.college_system.modules.domain.todo.services.todo_service import TodoService
from education_system.college_system.infrastructure.auth.core import UserAuth


def todo_menu(auth: UserAuth):
    """To-Do list management menu."""
    svc = TodoService(auth._db_path)
    user_id = auth.current_user["user_id"]

    while True:
        print_header("To-Do List")
        options = [
            ("1", "View To-Do List"),
            ("2", "Add Task"),
            ("3", "Mark Complete/Incomplete"),
            ("4", "Edit Task"),
            ("5", "Delete Task"),
            ("0", "Back"),
        ]
        print_menu(options)

        choice = get_choice()
        if choice == "1":
            _view_items(svc, user_id)
        elif choice == "2":
            _add_item(svc, user_id)
        elif choice == "3":
            _toggle_item(svc, user_id)
        elif choice == "4":
            _edit_item(svc, user_id)
        elif choice == "5":
            _delete_item(svc, user_id)
        elif choice == "0":
            break


def _view_items(svc, user_id):
    show = input("  Show completed too? (y/n) [n]: ").strip().lower() == "y"
    items = svc.list_items(user_id, show_completed=show)
    if not items:
        print("\n  No to-do items found.")
        return

    print(f"\n  {'ID':<6} {'Title':<30} {'Priority':<10} {'Due Date':<12} {'Status'}")
    print(f"  {'-' * 72}")
    for item in items:
        status = "Done" if item["is_completed"] else "Pending"
        due = item.get("due_date") or ""
        print(f"  {item['id']:<6} {item['title'][:28]:<30} {item['priority']:<10} {due:<12} {status}")


def _add_item(svc, user_id):
    print_header("Add Task")
    title = input("  Title: ").strip()
    if not title:
        print("\n  Title is required.")
        return
    description = input("  Description (optional): ").strip() or None
    priority = input("  Priority (low/medium/high) [medium]: ").strip() or "medium"
    due_date = input("  Due date (YYYY-MM-DD, optional): ").strip() or None

    try:
        item = svc.create_item(user_id, title, description, priority, due_date)
        print(f"\n  Task created (ID: {item['id']})")
    except Exception as e:
        print(f"\n  Error: {e}")


def _toggle_item(svc, user_id):
    item_id = input("  Task ID: ").strip()
    try:
        item = svc.toggle_complete(int(item_id), user_id)
        status = "completed" if item["is_completed"] else "pending"
        print(f"\n  Task '{item['title']}' marked as {status}.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _edit_item(svc, user_id):
    item_id = input("  Task ID: ").strip()
    try:
        item = svc.get_item(int(item_id), user_id)
    except Exception as e:
        print(f"\n  Error: {e}")
        return

    print(f"\n  Current: {item['title']} | {item['priority']} | {item.get('due_date') or 'No due date'}")
    title = input(f"  New title [{item['title']}]: ").strip() or None
    priority = input(f"  New priority [{item['priority']}]: ").strip() or None
    due_date = input(f"  New due date [{item.get('due_date') or ''}]: ").strip() or None

    kwargs = {}
    if title:
        kwargs["title"] = title
    if priority:
        kwargs["priority"] = priority
    if due_date:
        kwargs["due_date"] = due_date

    if not kwargs:
        print("\n  No changes made.")
        return

    try:
        svc.update_item(int(item_id), user_id, **kwargs)
        print("\n  Task updated.")
    except Exception as e:
        print(f"\n  Error: {e}")


def _delete_item(svc, user_id):
    item_id = input("  Task ID: ").strip()
    confirm = input("  Are you sure? (y/n): ").strip().lower()
    if confirm != "y":
        return
    try:
        svc.delete_item(int(item_id), user_id)
        print("\n  Task deleted.")
    except Exception as e:
        print(f"\n  Error: {e}")
