"""Regression tests for CLI authentication integration wiring."""

from unittest.mock import Mock


def test_link_auth_to_student_union_uses_current_module_path(monkeypatch):
    from education_system.systems.university.domains.pastoral.domain.student_life import (
        student_union,
    )
    from education_system.systems.university.shell.cli import auth_manager

    set_auth_all = Mock()
    monkeypatch.setattr(student_union, "set_auth_all", set_auth_all)
    auth = object()

    auth_manager._link_auth_to_student_union(auth)

    set_auth_all.assert_called_once_with(auth)
