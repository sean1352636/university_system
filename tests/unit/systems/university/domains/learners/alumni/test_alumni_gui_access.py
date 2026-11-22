"""The alumni window: no fall-back user, and menus built from the
signed-in person's alumni role. The screens' rules are tested in
tests/unit/systems/university/application/test_alumni_office.py.
No display needed: Tk widgets and the rule call are patched."""

from unittest.mock import MagicMock, patch

import pytest

from education_system.systems.university.application.alumni.access import AlumniUser
from education_system.systems.university.domains.learners.interfaces.gui.alumni import (
    main_gui,
)

APP = main_gui.AlumniGUIApp


def _open(who, user=None):
    auth = MagicMock()
    auth.current_user = user if user is not None else (
        {"username": who.username, "role": who.role} if who else None)
    with patch.object(main_gui, "ttk") as ttk, \
            patch.object(main_gui, "init_alumni_db"), \
            patch("education_system.systems.university.infrastructure.ui.record_screens.call",
                  return_value=who), \
            patch.object(APP, "create_widgets") as widgets, \
            patch.object(APP, "show_home"):
        app = APP(MagicMock(), auth)
    return app, ttk, widgets


def _labels(app):
    return {label for items in app._menu_for_role().values() for label, _cmd in items}


def test_no_sign_in_gets_no_fallback_admin():
    app, ttk, widgets = _open(None, user={})
    assert app.who is None
    widgets.assert_not_called()
    assert "Sign in" in ttk.Label.call_args.kwargs["text"]


def test_staff_without_an_alumni_role_get_no_screens():
    app, ttk, widgets = _open(AlumniUser("lecturer", "staff"))
    widgets.assert_not_called()
    assert "alumni office" in ttk.Label.call_args.kwargs["text"]


def test_office_sees_everything():
    app, _ttk, widgets = _open(AlumniUser("admin", "admin"))
    widgets.assert_called_once()
    labels = _labels(app)
    assert {"Alumni records", "Newsletters", "Finance system", "Gifts, Gift Aid & pledges",
            "Mentors, matches & concerns", "Reports, stories & photos"} <= labels
    assert app.has_permission("anything")


def test_alumni_see_their_own_account_and_no_admin_tools():
    who = AlumniUser("G1", "alumni", alumni_id="G1", student_id="G1")
    app, _ttk, _widgets = _open(who)
    labels = _labels(app)
    assert {"My profile", "Privacy & directory listing", "Keep in touch", "My data",
            "My giving", "Alumni directory"} <= labels
    for admin_only in ("Finance system", "Finance status check", "Student validation",
                       "Email manager", "Alumni records", "Newsletters"):
        assert admin_only not in labels
    assert not app.has_permission("manage_alumni")


def test_current_students_only_see_mentoring():
    who = AlumniUser("S1", "student", student_id="S1")
    app, _ttk, _widgets = _open(who)
    assert _labels(app) == {"Mentoring"}


@pytest.mark.parametrize("role, label", [("fundraising", "Gifts, Gift Aid & pledges"),
                                         ("mentoring_coordinator",
                                          "Mentors, matches & concerns"),
                                         ("moderator", "Reports, stories & photos")])
def test_staff_roles_see_their_area_only(role, label):
    who = AlumniUser("someone", "staff", roles=frozenset({role}))
    app, _ttk, _widgets = _open(who)
    labels = _labels(app)
    assert label in labels and "Alumni records" not in labels
