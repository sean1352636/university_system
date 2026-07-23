#!/usr/bin/env python3
"""
To-Do List CLI - Task management system
Features: Priorities, Due Dates, Categories, Completion tracking
"""

import json
from pathlib import Path
from datetime import datetime, date

try:
    from education_system.post_18.university_system.core.paths import DATA_DIR
    TODO_FILE = DATA_DIR / "todo_tasks.json"
except ImportError:
    TODO_FILE = Path.home() / ".todo_tasks.json"


class Task:
    """Represents a to-do task."""

    def __init__(self, title, priority="Normal", due_date=None, category="General", notes="", completed=False):
        self.id = datetime.now().strftime('%Y%m%d%H%M%S%f')
        self.title = title
        self.priority = priority
        self.due_date = due_date
        self.category = category
        self.notes = notes
        self.completed = completed
        self.created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'priority': self.priority,
            'due_date': self.due_date,
            'category': self.category,
            'notes': self.notes,
            'completed': self.completed,
            'created_at': self.created_at
        }

    @classmethod
    def from_dict(cls, data):
        task = cls(
            data['title'],
            data.get('priority', 'Normal'),
            data.get('due_date'),
            data.get('category', 'General'),
            data.get('notes', ''),
            data.get('completed', False)
        )
        task.id = data['id']
        task.created_at = data.get('created_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return task


class TodoManager:
    """Manages to-do tasks."""

    def __init__(self):
        self.tasks = []
        self.load_tasks()

    def load_tasks(self):
        """Load tasks from file."""
        if TODO_FILE.exists():
            try:
                with open(TODO_FILE, 'r') as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data]
            except Exception as e:
                print(f"Error loading tasks: {e}")
                self.tasks = []
        else:
            self.tasks = []

    def save_tasks(self):
        """Save tasks to file."""
        try:
            TODO_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TODO_FILE, 'w') as f:
                json.dump([t.to_dict() for t in self.tasks], f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving tasks: {e}")
            return False

    def add_task(self, task):
        """Add a new task."""
        self.tasks.append(task)
        return self.save_tasks()

    def get_task_by_id(self, task_id):
        """Get task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def update_task(self, task_id, **kwargs):
        """Update task fields."""
        task = self.get_task_by_id(task_id)
        if task:
            for key, value in kwargs.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            return self.save_tasks()
        return False

    def delete_task(self, task_id):
        """Delete a task."""
        self.tasks = [t for t in self.tasks if t.id != task_id]
        return self.save_tasks()

    def get_tasks(self, category=None, completed=None, priority=None):
        """Get filtered tasks."""
        filtered = self.tasks

        if category:
            filtered = [t for t in filtered if t.category == category]
        if completed is not None:
            filtered = [t for t in filtered if t.completed == completed]
        if priority:
            filtered = [t for t in filtered if t.priority == priority]

        return filtered

    def get_categories(self):
        """Get list of unique categories."""
        return sorted(set(t.category for t in self.tasks))

    def get_statistics(self):
        """Get task statistics."""
        total = len(self.tasks)
        completed = len([t for t in self.tasks if t.completed])
        pending = total - completed

        by_priority = {}
        for t in self.tasks:
            if not t.completed:
                by_priority[t.priority] = by_priority.get(t.priority, 0) + 1

        overdue = 0
        today_str = date.today().strftime('%Y-%m-%d')
        for t in self.tasks:
            if not t.completed and t.due_date and t.due_date < today_str:
                overdue += 1

        return {
            'total': total,
            'completed': completed,
            'pending': pending,
            'by_priority': by_priority,
            'overdue': overdue
        }


# ==================== CLI Interface ====================

def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_task_summary(task):
    """Print task summary."""
    status = "✓" if task.completed else " "
    priority_symbol = {"High": "‼", "Normal": "•", "Low": "·"}.get(task.priority, "•")
    due = f"Due: {task.due_date}" if task.due_date else "No due date"

    print(f"  [{status}] {priority_symbol} {task.title:<40} | {task.category:<15} | {due}")


def print_task_details(task):
    """Print full task details."""
    status = "Completed" if task.completed else "Pending"
    print(f"\n  ID: {task.id}")
    print(f"  Title: {task.title}")
    print(f"  Priority: {task.priority}")
    print(f"  Category: {task.category}")
    print(f"  Status: {status}")
    print(f"  Due Date: {task.due_date or 'Not set'}")
    print(f"  Created: {task.created_at}")
    if task.notes:
        print(f"  Notes: {task.notes}")


def list_tasks_menu(manager):
    """List all tasks."""
    print_header("To-Do List - All Tasks")

    print("\n  Filter:")
    print("    1. All tasks")
    print("    2. Pending only")
    print("    3. Completed only")
    print("    4. By category")
    print("    5. By priority")

    choice = input("\n  Enter choice (1-5): ").strip()

    tasks = []
    if choice == '1':
        tasks = manager.tasks
    elif choice == '2':
        tasks = manager.get_tasks(completed=False)
    elif choice == '3':
        tasks = manager.get_tasks(completed=True)
    elif choice == '4':
        categories = manager.get_categories()
        if categories:
            print("\n  Categories:")
            for i, cat in enumerate(categories, 1):
                print(f"    {i}. {cat}")
            cat_choice = input("  Select category: ").strip()
            try:
                idx = int(cat_choice) - 1
                if 0 <= idx < len(categories):
                    tasks = manager.get_tasks(category=categories[idx])
            except ValueError:
                pass
    elif choice == '5':
        priority = input("  Enter priority (High/Normal/Low): ").strip()
        tasks = manager.get_tasks(priority=priority)

    if not tasks:
        print("\n  No tasks found.")
        return

    print(f"\n  Total: {len(tasks)} tasks\n")
    for task in sorted(tasks, key=lambda t: (t.completed, t.priority != 'High', t.due_date or '9999-99-99')):
        print_task_summary(task)

    print()


def view_task_menu(manager):
    """View task details."""
    print_header("View Task")

    task_id = input("\n  Enter Task ID (or partial): ").strip()
    if not task_id:
        print("  ❌ Task ID required.")
        return

    # Find task by partial ID match
    matches = [t for t in manager.tasks if t.id.startswith(task_id)]

    if not matches:
        print(f"  ❌ No task found matching '{task_id}'.")
        return

    if len(matches) > 1:
        print("\n  Multiple matches found:")
        for t in matches[:5]:
            print(f"    {t.id}: {t.title}")
        print("  Please be more specific.")
        return

    print_task_details(matches[0])


def add_task_menu(manager):
    """Add a new task."""
    print_header("Add New Task")

    title = input("\n  Task title: ").strip()
    if not title:
        print("  ❌ Title is required.")
        return

    print("\n  Priority:")
    print("    1. Low")
    print("    2. Normal")
    print("    3. High")

    priority_choice = input("  Select priority (1-3, default 2): ").strip() or '2'
    priorities = {'1': 'Low', '2': 'Normal', '3': 'High'}
    priority = priorities.get(priority_choice, 'Normal')

    due_date = input("  Due date (YYYY-MM-DD, optional): ").strip() or None

    categories = manager.get_categories()
    if categories:
        print("\n  Existing categories:")
        for i, cat in enumerate(categories, 1):
            print(f"    {i}. {cat}")
        print(f"    {len(categories)+1}. New category")

        cat_choice = input(f"  Select category (1-{len(categories)+1}, default General): ").strip()
        try:
            idx = int(cat_choice) - 1
            if 0 <= idx < len(categories):
                category = categories[idx]
            else:
                category = input("  Enter new category: ").strip() or "General"
        except ValueError:
            category = "General"
    else:
        category = input("  Category (default General): ").strip() or "General"

    notes = input("  Notes (optional): ").strip()

    task = Task(title, priority, due_date, category, notes)

    if manager.add_task(task):
        print(f"\n  ✅ Task '{title}' added successfully!")
    else:
        print("\n  ❌ Failed to add task.")


def update_task_menu(manager):
    """Update a task."""
    print_header("Update Task")

    task_id = input("\n  Enter Task ID (or partial): ").strip()
    if not task_id:
        print("  ❌ Task ID required.")
        return

    matches = [t for t in manager.tasks if t.id.startswith(task_id)]

    if not matches:
        print(f"  ❌ No task found matching '{task_id}'.")
        return

    if len(matches) > 1:
        print("\n  Multiple matches found. Please be more specific.")
        return

    task = matches[0]
    print_task_details(task)

    print("\n  Update:")
    print("    1. Toggle completion")
    print("    2. Change priority")
    print("    3. Update due date")
    print("    4. Change category")
    print("    5. Update notes")
    print("    0. Cancel")

    choice = input("\n  Enter choice: ").strip()

    if choice == '1':
        new_status = not task.completed
        if manager.update_task(task.id, completed=new_status):
            status_text = "completed" if new_status else "pending"
            print(f"\n  ✅ Task marked as {status_text}.")

    elif choice == '2':
        print("\n  Priority:")
        print("    1. Low")
        print("    2. Normal")
        print("    3. High")

        priority_choice = input("  Select priority (1-3): ").strip()
        priorities = {'1': 'Low', '2': 'Normal', '3': 'High'}
        new_priority = priorities.get(priority_choice)

        if new_priority and manager.update_task(task.id, priority=new_priority):
            print(f"\n  ✅ Priority updated to: {new_priority}")

    elif choice == '3':
        new_date = input("  New due date (YYYY-MM-DD, or blank to clear): ").strip() or None
        if manager.update_task(task.id, due_date=new_date):
            print("\n  ✅ Due date updated.")

    elif choice == '4':
        new_category = input("  New category: ").strip()
        if new_category and manager.update_task(task.id, category=new_category):
            print(f"\n  ✅ Category updated to: {new_category}")

    elif choice == '5':
        new_notes = input("  New notes: ").strip()
        if manager.update_task(task.id, notes=new_notes):
            print("\n  ✅ Notes updated.")


def delete_task_menu(manager):
    """Delete a task."""
    print_header("Delete Task")

    task_id = input("\n  Enter Task ID (or partial): ").strip()
    if not task_id:
        print("  ❌ Task ID required.")
        return

    matches = [t for t in manager.tasks if t.id.startswith(task_id)]

    if not matches:
        print(f"  ❌ No task found matching '{task_id}'.")
        return

    if len(matches) > 1:
        print("\n  Multiple matches found. Please be more specific.")
        return

    task = matches[0]
    print_task_details(task)

    confirm = input("\n  ⚠️  Delete this task? (yes/no): ").strip().lower()
    if confirm == 'yes':
        if manager.delete_task(task.id):
            print(f"\n  ✅ Task '{task.title}' deleted.")
        else:
            print("\n  ❌ Failed to delete task.")


def statistics_menu(manager):
    """Show statistics."""
    print_header("To-Do List Statistics")

    stats = manager.get_statistics()

    print(f"\n  Total Tasks: {stats['total']}")
    print(f"  Completed: {stats['completed']}")
    print(f"  Pending: {stats['pending']}")

    if stats['overdue'] > 0:
        print(f"  ⚠️  Overdue: {stats['overdue']}")

    if stats['by_priority']:
        print("\n  Pending by Priority:")
        for priority, count in sorted(stats['by_priority'].items()):
            print(f"    {priority}: {count}")

    categories = manager.get_categories()
    if categories:
        print(f"\n  Categories: {', '.join(categories)}")

    print()


def todo_menu():
    """Main to-do list CLI menu."""
    manager = TodoManager()

    while True:
        print_header("To-Do List Manager")
        print("\n  1. List Tasks")
        print("  2. View Task Details")
        print("  3. Add New Task")
        print("  4. Update Task")
        print("  5. Delete Task")
        print("  6. View Statistics")
        print("  0. Return to Main Menu")

        choice = input("\n  Enter your choice: ").strip()

        if choice == '1':
            list_tasks_menu(manager)
        elif choice == '2':
            view_task_menu(manager)
        elif choice == '3':
            add_task_menu(manager)
        elif choice == '4':
            update_task_menu(manager)
        elif choice == '5':
            delete_task_menu(manager)
        elif choice == '6':
            statistics_menu(manager)
        elif choice == '0':
            print("\n  Returning to main menu...\n")
            break
        else:
            print("\n  ❌ Invalid choice.")

        if choice != '0':
            input("\n  Press Enter to continue...")


if __name__ == '__main__':
    todo_menu()
