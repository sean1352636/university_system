"""Security regression tests for student CRUD GUI entry points."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui.authorization import (
    require_student_permission,
)
from education_system.systems.university.services.student_provisioning import (
    default_student_password,
)


def test_permission_guard_fails_closed_without_authenticated_user():
    owner = SimpleNamespace(auth=None, root=None)

    with patch(
        "education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui.authorization.messagebox.showerror"
    ) as showerror:
        assert require_student_permission(owner, "create_student", "create") is False

    showerror.assert_called_once()


def test_permission_guard_uses_current_permission_at_callback_time():
    auth = SimpleNamespace(current_user={"id": 1}, check_permission=Mock(return_value=True))
    owner = SimpleNamespace(auth=auth, root=None)

    assert require_student_permission(owner, "update_any_student", "update") is True
    auth.check_permission.assert_called_once_with("update_any_student")


def test_permission_guard_fails_closed_when_checker_raises():
    auth = SimpleNamespace(
        current_user={"id": 1},
        check_permission=Mock(side_effect=RuntimeError("auth unavailable")),
    )
    owner = SimpleNamespace(auth=auth, root=None)

    with patch(
        "education_system.systems.university.domains.learners.interfaces.gui.students.student_crud_gui.authorization.messagebox.showerror"
    ):
        assert require_student_permission(owner, "delete_any_student", "delete") is False


def test_bootstrap_secret_is_random_and_not_derived_from_student_identity():
    first = default_student_password("Alice", "1234567")
    second = default_student_password("Alice", "1234567")

    assert first != second
    assert "alice" not in first.lower()
    assert "1234567" not in first
    assert len(first) >= 32
