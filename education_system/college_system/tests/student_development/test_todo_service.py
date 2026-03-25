"""Tests for TodoService."""

import pytest
from education_system.college_system.core.exceptions import TodoError


class TestTodoService:
    @pytest.fixture
    def todo_service(self, db_path):
        from education_system.college_system.modules.domain.todo.services.todo_service import TodoService
        return TodoService(db_path)

    def test_create_item(self, todo_service):
        item = todo_service.create_item(
            user_id=1, title="Finish essay",
            description="Complete English lit essay",
            priority="high",
        )
        assert item["title"] == "Finish essay"
        assert item["priority"] == "high"
        assert item["is_completed"] == 0

    def test_create_item_validates_title(self, todo_service):
        with pytest.raises(TodoError, match="Title"):
            todo_service.create_item(user_id=1, title="")

    def test_create_item_validates_priority(self, todo_service):
        with pytest.raises(TodoError, match="Priority"):
            todo_service.create_item(user_id=1, title="Test", priority="urgent")

    def test_list_items(self, todo_service):
        todo_service.create_item(user_id=1, title="Task 1")
        todo_service.create_item(user_id=1, title="Task 2")
        items = todo_service.list_items(user_id=1)
        assert len(items) >= 2

    def test_list_items_excludes_completed(self, todo_service):
        item = todo_service.create_item(user_id=1, title="Complete me")
        todo_service.toggle_complete(item["id"], user_id=1)
        items = todo_service.list_items(user_id=1, show_completed=False)
        assert all(i["is_completed"] == 0 for i in items)

    def test_list_items_includes_completed(self, todo_service):
        item = todo_service.create_item(user_id=1, title="Complete me too")
        todo_service.toggle_complete(item["id"], user_id=1)
        items = todo_service.list_items(user_id=1, show_completed=True)
        completed = [i for i in items if i["is_completed"] == 1]
        assert len(completed) >= 1

    def test_toggle_complete(self, todo_service):
        item = todo_service.create_item(user_id=1, title="Toggle test")
        toggled = todo_service.toggle_complete(item["id"], user_id=1)
        assert toggled["is_completed"] == 1
        toggled_back = todo_service.toggle_complete(item["id"], user_id=1)
        assert toggled_back["is_completed"] == 0

    def test_update_item(self, todo_service):
        item = todo_service.create_item(user_id=1, title="Old title")
        updated = todo_service.update_item(item["id"], user_id=1, title="New title")
        assert updated["title"] == "New title"

    def test_delete_item(self, todo_service):
        item = todo_service.create_item(user_id=1, title="Delete me")
        result = todo_service.delete_item(item["id"], user_id=1)
        assert result is True

    def test_items_scoped_to_user(self, todo_service):
        todo_service.create_item(user_id=1, title="User 1 task")
        todo_service.create_item(user_id=2, title="User 2 task")
        user1_items = todo_service.list_items(user_id=1)
        assert all(i["user_id"] == 1 for i in user1_items)

    def test_priority_ordering(self, todo_service):
        todo_service.create_item(user_id=1, title="Low", priority="low")
        todo_service.create_item(user_id=1, title="High", priority="high")
        todo_service.create_item(user_id=1, title="Medium", priority="medium")
        items = todo_service.list_items(user_id=1)
        assert items[0]["priority"] == "high"
