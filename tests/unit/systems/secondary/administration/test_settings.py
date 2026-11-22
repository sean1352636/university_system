"""School settings (modules.administration.domain.settings)."""

from __future__ import annotations

import json

import pytest

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.library.domain import library as LB
from education_system.systems.secondary.modules.administration.domain import settings as ST
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.authentication import accounts
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ADMIN = Principal(username="admin2", role="admin")
ANN = Principal(username="ann", role="teacher")


@pytest.fixture(autouse=True)
def scratch(tmp_path):
    from education_system.platform.identity.auth.schema import initialise_auth_db
    database.use_database(tmp_path / "secondary.db")
    accounts.use_auth_db(tmp_path / "auth.db")
    initialise_auth_db(str(tmp_path / "auth.db"))
    activity_log.use_log_file(tmp_path / "activity.log")
    yield tmp_path
    database.use_database(None)
    accounts.use_auth_db(None)
    activity_log.use_log_file(None)


def _log(tmp_path) -> str:
    return (tmp_path / "activity.log").read_text(encoding="utf-8")


def test_defaults_and_get_setting_for_other_modules():
    assert ST.get_setting("school_name") == "Secondary School"
    assert ST.get_setting("school_name", "X") == "X"          # unset: the caller's default
    assert ST.get_setting("no.such.key") is None
    assert ST.get_setting("no.such.key", 7) == 7
    assert ST.get_setting("attendance.threshold_pct") == 90.0
    assert ST.get_setting("ui.confirm_destructive") is True
    # every old local key is still in the registry
    for key in ("attendance.default_window_days", "attendance.max_lates",
                "attendance.max_absences", "grades.mock_below_pred_gap",
                "grades.min_target_points", "progress.default_period", "fees.default_due_days",
                "fees.overdue_warning_days", "receipts.auto_issue_on_import", "ui.show_advanced",
                "ui.default_year", "reports.export_dir", "reports.default_format"):
        assert ST.get_spec(key)


def test_set_validates_types_and_rules(tmp_path):
    changed = ST.set_many({"school_name": "  Oak   Hill  Academy ", "urn": "123456",
                           "la_number": "201", "dfe_number": "2014001",
                           "postcode": "sw1a1aa", "email": "office@oak.sch.uk",
                           "phone": "+44 (0)20 7946 0000", "attendance.max_lates": "7",
                           "ui.show_advanced": "yes"}, actor=ADMIN)
    assert changed["school_name"] == "Oak Hill Academy"
    assert ST.get_setting("dfe_number") == "201/4001"
    assert ST.get_setting("postcode") == "SW1A 1AA"
    assert ST.get_setting("attendance.max_lates") == 7
    assert ST.get_setting("ui.show_advanced") is True
    with pytest.raises(ST.ValidationError) as e:
        ST.set_many({"urn": "12345", "email": "nope", "attendance.threshold_pct": "120",
                     "reports.default_format": "pdf", "logo_path": "logo.bmp",
                     "unknown": 1}, actor=ADMIN)
    text = " ".join(e.value.problems)
    for bit in ("URN", "e-mail address", "from 0 to 100", "one of csv", "PNG", "Unknown"):
        assert bit in text
    assert ST.get_setting("urn") == "123456"                   # all or nothing
    with pytest.raises(ST.ValidationError, match="start with the LA number"):
        ST.set_setting("dfe_number", "999/1234", actor=ADMIN)
    assert "settings.update" in _log(tmp_path) and "office@oak" not in _log(tmp_path)


def test_only_settings_editors(tmp_path):
    with pytest.raises(ST.PermissionDenied):
        ST.set_setting("school_name", "X", actor=ANN)
    with pytest.raises(ST.PermissionDenied):
        ST.list_settings(actor=ANN)
    with pytest.raises(ST.PermissionDenied):
        ST.reset_all(actor=ANN)
    assert "outcome=denied" in _log(tmp_path)
    assert ST.get_setting("school_name") == "Secondary School"


def test_audit_reset_and_reset_all():
    ST.set_setting("headteacher", "Mrs J Smith", actor=ADMIN)
    ST.set_setting("attendance.max_lates", 9, actor=ADMIN)
    h = ST.history("headteacher")
    assert h[0]["action"] == "set" and h[0]["new"] == "Mrs J Smith" and h[0]["old"] == ""
    rows = {s.spec.key: s for s in ST.list_settings(actor=ADMIN)}
    assert not rows["headteacher"].is_default and rows["headteacher"].updated_by == "admin2"
    assert ST.reset("headteacher", actor=ADMIN) == ""
    assert ST.history("headteacher")[0]["action"] == "reset"
    assert ST.reset_all(actor=ADMIN, category="Attendance") == 1
    assert ST.get_setting("attendance.max_lates") == 5
    assert ST.set_many({"school_name": "Secondary School"}, actor=ADMIN) == {}  # no change


def test_school_values_snapshot_and_import(tmp_path):
    ST.set_many({"school_name": "Oak Hill", "address_line1": "1 High St", "town": "Leeds",
                 "postcode": "LS1 1AA", "headteacher": "Mr B"}, actor=ADMIN)
    v = ST.school_values()
    assert v["school_name"] == "Oak Hill" and v["school_address"] == "1 High St, Leeds, LS1 1AA"
    assert v["email_sender_name"] == "Oak Hill"
    path = tmp_path / "snap.json"
    n = ST.export_json(path, actor=ADMIN)
    snap = json.loads(path.read_text())
    assert n == len(snap) and snap["school_name"] == "Oak Hill"
    assert "linked.attendance.am_start" in snap and "auth.lockout_minutes" in snap
    ST.reset_all(actor=ADMIN)
    assert ST.get_setting("school_name") == "Secondary School"
    ST.import_json(path, actor=ADMIN)
    assert ST.get_setting("school_name") == "Oak Hill"
    assert "Oak Hill" in ST.summary_text(actor=ADMIN)


def test_linked_settings_go_through_their_own_modules():
    vals = ST.linked_values()
    assert vals["attendance.am_start"] == AT.session_times()["am_start"]
    assert ST.set_linked("attendance.am_start", "08:35", actor=ADMIN) == "08:35"
    assert AT.session_times()["am_start"] == "08:35"
    with pytest.raises(ST.ValidationError):              # attendance's own rule
        ST.set_linked("attendance.am_start", "25:00", actor=ADMIN)
    assert ST.set_linked("library.loan_days", 21, actor=ADMIN) == 21
    assert LB.settings()["loan_days"] == 21
    assert ST.history("library.loan_days")[0]["action"] == "linked"
    with pytest.raises(ST.PermissionDenied):
        ST.set_linked("library.loan_days", 7, actor=ANN)


def test_auth_policy_editable_by_editors_and_term_dates_read(tmp_path):
    import sqlite3

    from education_system.platform.identity.auth.policy import policy_int
    pol = ST.auth_policy()
    assert set(pol) == {s.key for s in ST.AUTH_POLICY}
    assert ST.set_auth_policy("max_login_attempts", "7", actor=ADMIN) == 7
    assert ST.auth_policy()["max_login_attempts"] == 7
    with sqlite3.connect(tmp_path / "auth.db") as conn:     # what the platform enforces
        assert policy_int(conn, "max_login_attempts", 3) == 7
    with pytest.raises(ST.ValidationError):
        ST.set_auth_policy("max_login_attempts", "0", actor=ADMIN)
    with pytest.raises(ST.PermissionDenied):
        ST.set_auth_policy("lockout_minutes", 30, actor=ANN)
    assert ST.set_auth_policy("force_password_reset", False, actor=ADMIN) is False
    assert ST.auth_policy()["force_password_reset"] is False
    assert ST.history("auth.max_login_attempts")[0]["action"] == "auth"
    default = {s.key: s.default for s in ST.AUTH_POLICY}
    assert ST.reset_auth_policy("max_login_attempts", actor=ADMIN) == default["max_login_attempts"]
    assert ST.reset_auth_policy("force_password_reset", actor=ADMIN) is not None
    assert "settings.auth_set" in _log(tmp_path)
    td = ST.term_dates()
    assert "terms" in td
