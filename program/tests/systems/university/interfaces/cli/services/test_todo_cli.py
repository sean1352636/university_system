"""Behavioral tests for the To-Do List CLI (``modules.services.cli.todo_cli``).

This CLI is file-backed rather than DB-backed: ``TodoManager`` persists tasks to the
module-level ``TODO_FILE`` (a JSON path). The menu action functions each take a
``manager`` argument rather than opening storage themselves, so the seam is the
module-level ``TODO_FILE`` constant — repoint it at a per-test temp file and every
manager built afterwards reads/writes there in isolation.

Covered surface:

* the ``Task`` value object (``to_dict``/``from_dict`` roundtrip) and the pure
  print helpers,
* ``TodoManager`` persistence + filtering + statistics,
* the interactive action menus (add / update / delete / view / list / statistics)
  driven with scripted ``input()`` and asserted against the persisted store.
"""

from unittest.mock import patch

import pytest

from education_system.systems.university.interfaces.cli.shell.services import todo_cli


@pytest.fixture()
def todo_file(tmp_path, monkeypatch):
    """Repoint the module's storage path at a temp JSON file."""
    path = tmp_path / "todo_tasks.json"
    monkeypatch.setattr(todo_cli, "TODO_FILE", path)
    return path


@pytest.fixture()
def manager(todo_file):
    """A fresh manager backed by the temp file (starts empty)."""
    return todo_cli.TodoManager()


def _seed(manager, title, priority="Normal", due_date=None, category="General", completed=False):
    """Append a task with a deterministic, unique id (avoids strftime collisions)."""
    task = todo_cli.Task(title, priority, due_date, category, "", completed)
    task.id = f"id-{len(manager.tasks)+1:03d}"
    manager.tasks.append(task)
    manager.save_tasks()
    return task


# ---------------------------------------------------------------------------
# Task value object & pure print helpers
# ---------------------------------------------------------------------------

class TestTask:
    def test_to_from_dict_roundtrip(self):
        t = todo_cli.Task("Write report", "High", "2026-08-01", "Work", "urgent", False)
        d = t.to_dict()
        assert d["title"] == "Write report"
        assert d["priority"] == "High"
        restored = todo_cli.Task.from_dict(d)
        assert restored.id == t.id
        assert restored.title == "Write report"
        assert restored.category == "Work"
        assert restored.due_date == "2026-08-01"

    def test_defaults(self):
        t = todo_cli.Task("x")
        assert t.priority == "Normal"
        assert t.category == "General"
        assert t.completed is False

    @patch("builtins.print")
    def test_print_helpers_run(self, _p):
        t = todo_cli.Task("Task", "High", "2026-08-01", "Cat", "notes")
        todo_cli.print_task_summary(t)
        todo_cli.print_task_details(t)


# ---------------------------------------------------------------------------
# TodoManager persistence, filtering, statistics
# ---------------------------------------------------------------------------

class TestManager:
    def test_add_task_persists_across_reload(self, todo_file, manager):
        _seed(manager, "Buy milk")
        reloaded = todo_cli.TodoManager()
        assert [t.title for t in reloaded.tasks] == ["Buy milk"]

    def test_get_task_by_id(self, manager):
        t = _seed(manager, "Find me")
        assert manager.get_task_by_id(t.id).title == "Find me"
        assert manager.get_task_by_id("nope") is None

    def test_update_task(self, manager):
        t = _seed(manager, "Toggle")
        assert manager.update_task(t.id, completed=True) is True
        assert manager.get_task_by_id(t.id).completed is True

    def test_update_missing_returns_false(self, manager):
        assert manager.update_task("ghost", completed=True) is False

    def test_delete_task(self, manager):
        t = _seed(manager, "Delete")
        assert manager.delete_task(t.id) is True
        assert manager.tasks == []

    def test_get_tasks_filters(self, manager):
        _seed(manager, "A", priority="High", category="Work", completed=False)
        _seed(manager, "B", priority="Low", category="Home", completed=True)
        assert {t.title for t in manager.get_tasks(completed=False)} == {"A"}
        assert {t.title for t in manager.get_tasks(category="Home")} == {"B"}
        assert {t.title for t in manager.get_tasks(priority="High")} == {"A"}

    def test_get_categories_unique_sorted(self, manager):
        _seed(manager, "A", category="Zeta")
        _seed(manager, "B", category="Alpha")
        _seed(manager, "C", category="Alpha")
        assert manager.get_categories() == ["Alpha", "Zeta"]

    def test_statistics_counts_and_overdue(self, manager):
        _seed(manager, "done", completed=True)
        _seed(manager, "late", due_date="2000-01-01", completed=False)
        _seed(manager, "pending", completed=False)
        stats = manager.get_statistics()
        assert stats["total"] == 3
        assert stats["completed"] == 1
        assert stats["pending"] == 2
        assert stats["overdue"] == 1


# ---------------------------------------------------------------------------
# add_task_menu
# ---------------------------------------------------------------------------

class TestAddTaskMenu:
    @patch("builtins.print")
    def test_happy_path_persists(self, _p, manager, todo_file):
        # title, priority(3=High), due date, category (no existing cats -> free text), notes
        script = ["Grade papers", "3", "2026-09-01", "Teaching", "chapter 4"]
        with patch("builtins.input", side_effect=script):
            todo_cli.add_task_menu(manager)

        reloaded = todo_cli.TodoManager()
        assert len(reloaded.tasks) == 1
        t = reloaded.tasks[0]
        assert t.title == "Grade papers"
        assert t.priority == "High"
        assert t.category == "Teaching"
        assert t.due_date == "2026-09-01"

    @patch("builtins.print")
    def test_blank_title_writes_nothing(self, _p, manager, todo_file):
        with patch("builtins.input", side_effect=[""]):
            todo_cli.add_task_menu(manager)
        assert manager.tasks == []
        assert todo_cli.TodoManager().tasks == []


# ---------------------------------------------------------------------------
# update_task_menu
# ---------------------------------------------------------------------------

class TestUpdateTaskMenu:
    @patch("builtins.print")
    def test_toggle_completion(self, _p, manager):
        t = _seed(manager, "Toggle me")
        # full id, then choice 1 (toggle completion)
        with patch("builtins.input", side_effect=[t.id, "1"]):
            todo_cli.update_task_menu(manager)
        assert todo_cli.TodoManager().get_task_by_id(t.id).completed is True

    @patch("builtins.print")
    def test_unknown_id_no_change(self, _p, manager):
        _seed(manager, "Keep")
        with patch("builtins.input", side_effect=["does-not-exist"]):
            todo_cli.update_task_menu(manager)
        assert todo_cli.TodoManager().tasks[0].completed is False


# ---------------------------------------------------------------------------
# delete_task_menu (confirmation guard)
# ---------------------------------------------------------------------------

class TestDeleteTaskMenu:
    @patch("builtins.print")
    def test_confirmed_delete_removes(self, _p, manager):
        t = _seed(manager, "Remove me")
        with patch("builtins.input", side_effect=[t.id, "yes"]):
            todo_cli.delete_task_menu(manager)
        assert todo_cli.TodoManager().tasks == []

    @patch("builtins.print")
    def test_declined_delete_keeps(self, _p, manager):
        t = _seed(manager, "Spared")
        with patch("builtins.input", side_effect=[t.id, "no"]):
            todo_cli.delete_task_menu(manager)
        assert [x.title for x in todo_cli.TodoManager().tasks] == ["Spared"]

    @patch("builtins.print")
    def test_missing_id_guard(self, _p, manager):
        _seed(manager, "Present")
        with patch("builtins.input", side_effect=["zzz"]):
            todo_cli.delete_task_menu(manager)
        assert len(todo_cli.TodoManager().tasks) == 1


# ---------------------------------------------------------------------------
# Read views run cleanly
# ---------------------------------------------------------------------------

class TestReadViews:
    @patch("builtins.print")
    def test_view_task_details(self, _p, manager):
        t = _seed(manager, "Inspect")
        with patch("builtins.input", side_effect=[t.id]):
            assert todo_cli.view_task_menu(manager) is None

    @patch("builtins.print")
    def test_list_all_tasks(self, _p, manager):
        _seed(manager, "One")
        _seed(manager, "Two")
        with patch("builtins.input", side_effect=["1"]):
            assert todo_cli.list_tasks_menu(manager) is None

    @patch("builtins.print")
    def test_list_empty(self, _p, manager):
        with patch("builtins.input", side_effect=["1"]):
            assert todo_cli.list_tasks_menu(manager) is None

    @patch("builtins.print")
    def test_statistics_menu_runs(self, _p, manager):
        _seed(manager, "One", completed=True)
        _seed(manager, "Two")
        assert todo_cli.statistics_menu(manager) is None
