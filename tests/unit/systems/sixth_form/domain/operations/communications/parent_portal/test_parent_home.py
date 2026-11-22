"""The parent-facing view of a linked child, and the routing that reaches it.

A parent signing in must land on their own read-only portal, never on the
staff GUI/CLI, and must only ever see the students they are linked to.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.systems.sixth_form.interfaces.cli.operations.communications.parent_portal import (
    parent_home_cli,
)


@pytest.fixture
def parent(feature_db):
    """A portal account linked to S1 (the seeded at-risk student)."""
    pp = feature_db.mods["parent_portal"]
    aid = pp.create_account(username="guardian", password="password1",
                            full_name="Gwen Guardian")
    pp.link_student(aid, "S1", relationship="Mother")
    return pp.account_for_username("guardian")


# ── Account resolution ───────────────────────────────────────────────

def test_account_resolves_from_the_signed_in_username(feature_db, parent):
    assert parent is not None
    assert parent.username == "guardian"
    assert parent.full_name == "Gwen Guardian"


def test_unknown_or_disabled_account_resolves_to_none(feature_db):
    pp = feature_db.mods["parent_portal"]
    assert pp.account_for_username("nobody") is None
    assert pp.account_for_username("") is None

    aid = pp.create_account(username="paused", password="password1", full_name="P P")
    pp.set_active(aid, False)
    assert pp.account_for_username("paused") is None


# ── Authorisation ────────────────────────────────────────────────────

def test_child_detail_refuses_an_unlinked_student(feature_db, parent):
    pp = feature_db.mods["parent_portal"]
    # S2 exists and is perfectly readable via student_snapshot, but this
    # parent is not linked to them.
    assert pp.student_snapshot("S2")["student_id"] == "S2"
    with pytest.raises(pp.ValidationError):
        pp.child_detail(parent.account_id, "S2")


def test_is_linked_tracks_linking(feature_db, parent):
    pp = feature_db.mods["parent_portal"]
    assert pp.is_linked(parent.account_id, "S1")
    assert not pp.is_linked(parent.account_id, "S2")
    pp.unlink_student(parent.account_id, "S1")
    assert not pp.is_linked(parent.account_id, "S1")


# ── Content ──────────────────────────────────────────────────────────

def test_child_detail_carries_attendance_and_behaviour(feature_db, parent):
    pp = feature_db.mods["parent_portal"]
    detail = pp.child_detail(parent.account_id, "S1")

    # The snapshot fields are still there...
    assert detail["full_name"] == "Alex Atrisk"
    assert len(detail["subjects"]) == 3
    # ...plus the detail the parent view adds.
    assert detail["attendance"]["counts"]["Absent"] == 10
    assert detail["attendance"]["counts"]["Present"] == 10
    assert len(detail["attendance"]["absences"]) == 10
    assert {e["type"] for e in detail["behaviour"]} == {"Positive", "Negative"}


def test_attendance_window_matches_the_headline_percentage(feature_db, parent):
    """Two windows would put two different attendance figures on one screen."""
    from education_system.systems.sixth_form.domain.assessment.risk_analytics import (
        risk_analytics,
    )
    pp = feature_db.mods["parent_portal"]
    detail = pp.child_detail(parent.account_id, "S1")
    assert detail["attendance"]["days"] == risk_analytics.DEFAULT_WINDOW_DAYS
    # The counts explain the headline figure: Late counts as attending.
    counts = detail["attendance"]["counts"]
    attending = counts.get("Present", 0) + counts.get("Late", 0)
    counted = attending + counts.get("Absent", 0)
    assert detail["attendance_pct"] == pytest.approx(
        round(100.0 * attending / counted, 1))


def test_behaviour_omits_staff_only_fields(feature_db, parent):
    pp = feature_db.mods["parent_portal"]
    entries = pp.child_detail(parent.account_id, "S1")["behaviour"]
    assert entries
    for e in entries:
        assert set(e) == {"date", "type", "category", "severity", "points",
                          "description", "action_taken"}


def test_attendance_absences_exclude_present_sessions(feature_db, parent):
    pp = feature_db.mods["parent_portal"]
    absences = pp.child_detail(parent.account_id, "S1")["attendance"]["absences"]
    assert absences
    assert all(a["status"] != "Present" for a in absences)


def test_missing_optional_tables_do_not_break_the_view(feature_db, parent):
    """A college that doesn't use behaviour tracking still gets a portal."""
    pp = feature_db.mods["parent_portal"]
    conn = sqlite3.connect(feature_db.db)
    conn.execute("DROP TABLE behaviour_entries")
    conn.commit()
    conn.close()
    assert pp.recent_behaviour("S1") == []


# ── CLI rendering ────────────────────────────────────────────────────

def test_cli_overview_lists_only_linked_children(feature_db, parent, capsys):
    children = parent_home_cli._print_overview(parent)
    assert [c["student_id"] for c in children] == ["S1"]
    out = capsys.readouterr().out
    assert "Alex Atrisk" in out
    assert "Sam Steady" not in out
    assert "Gwen Guardian" in out


def test_cli_child_view_renders_the_sections(feature_db, parent, capsys):
    parent_home_cli._print_child(parent, "S1")
    out = capsys.readouterr().out
    assert "Alex Atrisk" in out
    assert "Subjects" in out
    assert "Attendance —" in out
    assert "Behaviour record" in out
    assert "Repeated lateness" in out


def test_cli_child_view_refuses_an_unlinked_student(feature_db, parent, capsys):
    parent_home_cli._print_child(parent, "S2")
    out = capsys.readouterr().out
    assert "not linked" in out
    assert "Sam Steady" not in out


def test_cli_overview_explains_an_empty_account(feature_db, capsys):
    pp = feature_db.mods["parent_portal"]
    pp.create_account(username="childless", password="password1", full_name="No One")
    assert parent_home_cli._print_overview(
        pp.account_for_username("childless")) == []
    assert "No students are linked" in capsys.readouterr().out


# ── Routing ──────────────────────────────────────────────────────────

def test_parent_role_is_routed_away_from_the_staff_cli(feature_db, parent,
                                                       monkeypatch):
    from education_system.systems.sixth_form.interfaces.cli.operations.communications.parent_portal import (
        parent_home_cli as home,
    )
    from education_system.systems.sixth_form.interfaces.cli import cli_main

    reached = {}

    def _fake_run(auth, account):
        reached["account"] = account
        return 0

    monkeypatch.setattr(home, "run", _fake_run)
    monkeypatch.setattr(cli_main, "run_authenticated",
                        lambda auth: pytest.fail("parent reached the staff menu"))

    class _Auth:
        current_user = {"username": "guardian"}

    cli_main.run(user_info=_Auth.current_user, role="parent", shared_auth=_Auth())
    assert reached["account"].username == "guardian"


def test_parent_without_a_portal_record_is_told_so(feature_db, capsys):
    from education_system.systems.sixth_form.interfaces.cli import cli_main

    class _Auth:
        current_user = {"username": "ghost"}

    rc = cli_main._run_parent_portal(_Auth(), _Auth.current_user)
    assert rc == 0
    assert "no parent portal record" in capsys.readouterr().out.lower()


def test_staff_roles_still_get_the_staff_cli(feature_db, monkeypatch):
    from education_system.systems.sixth_form.interfaces.cli import cli_main

    called = {}

    def _fake_staff(auth):
        called["yes"] = True
        return 0

    monkeypatch.setattr(cli_main, "run_authenticated", _fake_staff)

    class _Auth:
        current_user = {"username": "someone"}

    for role in ("admin", "teacher", "student", None):
        called.clear()
        cli_main.run(user_info=_Auth.current_user, role=role, shared_auth=_Auth())
        assert called.get("yes"), f"role {role!r} did not reach the staff menu"
