"""Behavioral tests for the First Aid data layer (``IncidentDB``) and the
static ``EMERGENCY_CONTACTS`` directory.

``IncidentDB`` bootstraps its own tables over the shared ``get_connection``
path, so the fixture only points ``DEFAULT_DB_PATH`` at an empty **temp** DB
(never the live app DB). ``add()`` fans out to three cross-domain seams
(event bus, cases_bus, risk_bus); the ``seams`` fixture replaces them with
recorders so branching is observable and deterministic.
"""

from datetime import datetime

import sqlite3

import pytest

from education_system.systems.university.interfaces.gui.academics import (
    _event_bus as event_bus,
)
from education_system.systems.university.services.bus import (
    cases_bus,
    risk_bus,
)
from education_system.systems.university.domain.pastoral.health.first_aid import (
    first_aid_service as mod,
)
from education_system.systems.university.domain.pastoral.health.first_aid.first_aid_service import (
    EMERGENCY_CONTACTS,
    IncidentDB,
)

_DB_PATH_ATTR = (
    "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH"
)


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _report(**over):
    base = {
        "submitted_at": _now(),
        "reporter_name": "Ann Reporter",
        "description": "Sprained ankle on the stairs.",
    }
    base.update(over)
    return base


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "health.db"))
    return IncidentDB()


@pytest.fixture()
def seams(monkeypatch):
    """Replace the three cross-domain seams with recorders."""
    rec = {"published": [], "cases": [], "risks": [], "risk_lookups": []}
    monkeypatch.setattr(
        event_bus, "publish",
        lambda event, **kw: rec["published"].append((event, kw)),
    )
    monkeypatch.setattr(
        cases_bus, "open_case", lambda **kw: rec["cases"].append(kw) or 1
    )
    monkeypatch.setattr(
        risk_bus, "list_risks_for",
        lambda ref: rec["risk_lookups"].append(ref) or [],
    )
    monkeypatch.setattr(
        risk_bus, "raise_risk", lambda **kw: rec["risks"].append(kw) or 1
    )
    return rec


def _raw(db_path_owner, sql, params=()):
    # Read via a fresh connection to the same temp DB the fixture uses.
    conn = db_path_owner._connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# EMERGENCY_CONTACTS
# ---------------------------------------------------------------------------

class TestEmergencyContacts:
    def test_directory_shape(self):
        assert isinstance(EMERGENCY_CONTACTS, list)
        assert len(EMERGENCY_CONTACTS) == 6
        required = {"name", "number", "description", "location", "icon", "color"}
        for entry in EMERGENCY_CONTACTS:
            assert required <= set(entry)
            assert entry["number"]

    def test_includes_emergency_services(self):
        names = {c["name"] for c in EMERGENCY_CONTACTS}
        assert "Emergency Services" in names


# ---------------------------------------------------------------------------
# schema bootstrap + migration
# ---------------------------------------------------------------------------

class TestSchema:
    def test_tables_created(self, db):
        names = {
            r["name"]
            for r in _raw(
                db, "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "first_aid_incidents",
            "first_aid_training_registrations",
        } <= names

    def test_migrates_legacy_table_missing_email_status(self, tmp_path, monkeypatch):
        path = str(tmp_path / "legacy.db")
        # Pre-create an OLD incidents table lacking email/status columns.
        conn = sqlite3.connect(path)
        conn.execute(
            """CREATE TABLE first_aid_incidents (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   submitted_at TEXT NOT NULL,
                   reporter_name TEXT NOT NULL,
                   description TEXT NOT NULL
               )"""
        )
        conn.commit()
        conn.close()

        monkeypatch.setattr(_DB_PATH_ATTR, path)
        instance = IncidentDB()  # _ensure_schema should ALTER in the columns
        cols = {
            r["name"]
            for r in _raw(instance, "PRAGMA table_info(first_aid_incidents)")
        }
        assert "email" in cols
        assert "status" in cols

    def test_has_column_true_and_false(self, db):
        conn = db._connection()
        try:
            assert db._has_column(conn, "first_aid_incidents", "severity") is True
            assert db._has_column(conn, "first_aid_incidents", "nope") is False
        finally:
            conn.close()

    def test_has_column_swallows_error_on_bad_table(self, db):
        conn = db._connection()
        try:
            # PRAGMA on a non-existent table returns no rows (not an error),
            # so this still yields False without raising.
            assert db._has_column(conn, "no_such_table", "x") is False
        finally:
            conn.close()

    def test_has_column_returns_false_on_sqlite_error(self, db):
        conn = db._connection()
        try:
            # An invalid table token makes the PRAGMA a syntax error →
            # sqlite3.Error is swallowed and False returned.
            assert db._has_column(conn, "bad name )( token", "x") is False
        finally:
            conn.close()

    def test_init_reraises_on_connection_import_failure(self, tmp_path, monkeypatch):
        import education_system.systems.university.infrastructure.database.db as dbmod

        monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "x.db"))
        # Remove the symbol so `from ...db import get_connection` raises.
        monkeypatch.delattr(dbmod, "get_connection")
        with pytest.raises(Exception):
            IncidentDB()

    def test_alter_migration_failure_is_swallowed(self, tmp_path, monkeypatch):
        import education_system.systems.university.infrastructure.database.db as dbmod

        path = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(path)
        conn.execute(
            """CREATE TABLE first_aid_incidents (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   submitted_at TEXT NOT NULL,
                   reporter_name TEXT NOT NULL,
                   description TEXT NOT NULL
               )"""
        )
        conn.commit()
        conn.close()
        monkeypatch.setattr(_DB_PATH_ATTR, path)

        class _NoAlterConn:
            def __init__(self, real):
                object.__setattr__(self, "_real", real)

            def __setattr__(self, name, value):
                setattr(self._real, name, value)

            def execute(self, sql, *a, **k):
                if sql.strip().upper().startswith("ALTER"):
                    raise sqlite3.Error("alter blocked")
                return self._real.execute(sql, *a, **k)

            def commit(self):
                return self._real.commit()

            def close(self):
                return self._real.close()

        def _fake_connection(self):
            real = dbmod.get_connection()
            real.row_factory = sqlite3.Row
            return _NoAlterConn(real)

        monkeypatch.setattr(IncidentDB, "_connection", _fake_connection)
        # __init__ runs _ensure_schema; the email/status ALTERs raise and are
        # swallowed rather than propagating.
        IncidentDB()


# ---------------------------------------------------------------------------
# add() — persistence + event broadcast
# ---------------------------------------------------------------------------

class TestAddIncident:
    def test_persists_and_returns_id(self, db, seams):
        new_id = db.add(_report(location="Library", incident_type="Fall",
                                severity="Low"))
        assert isinstance(new_id, int)
        rows = db.fetch_all()
        assert len(rows) == 1
        assert rows[0]["id"] == new_id
        assert rows[0]["reporter_name"] == "Ann Reporter"
        assert rows[0]["status"] == "Open"

    def test_publishes_incident_logged_event(self, db, seams):
        new_id = db.add(_report(location="Gym", incident_type="Cut",
                                severity="Low", reporter_id="R1"))
        assert len(seams["published"]) == 1
        event, kw = seams["published"][0]
        assert event == event_bus.EVENT_INCIDENT_LOGGED
        assert kw["incident_id"] == new_id
        assert kw["domain"] == "first_aid"
        assert kw["incident_type"] == "Cut"

    def test_publish_failure_does_not_break_add(self, db, monkeypatch):
        def _boom(*a, **k):
            raise RuntimeError("bus down")

        monkeypatch.setattr(event_bus, "publish", _boom)
        # silence the other seams so they don't hit real services
        monkeypatch.setattr(cases_bus, "open_case", lambda **k: 1)
        monkeypatch.setattr(risk_bus, "list_risks_for", lambda r: [])
        # low severity + no repeat location => other seams inert anyway
        new_id = db.add(_report(severity="Low"))
        assert isinstance(new_id, int)


# ---------------------------------------------------------------------------
# add() — severe incidents open an hs_incident case
# ---------------------------------------------------------------------------

class TestSevereCase:
    @pytest.mark.parametrize("sev", ["High", "critical", "SEVERE"])
    def test_severe_opens_case(self, db, seams, sev):
        db.add(_report(severity=sev, incident_type="Collapse",
                       location="Lab", reporter_id="R9"))
        assert len(seams["cases"]) == 1
        case = seams["cases"][0]
        assert case["kind"] == "hs_incident"
        assert case["subject_id"] == "R9"
        assert case["offense_type"] == "Collapse"

    def test_non_severe_opens_no_case(self, db, seams):
        db.add(_report(severity="Low"))
        assert seams["cases"] == []

    def test_subject_falls_back_to_reporter_user(self, db, seams):
        db.add(_report(severity="High", reporter_user="staff42"))
        assert seams["cases"][0]["subject_id"] == "staff42"

    def test_subject_falls_back_to_synthetic_id(self, db, seams):
        new_id = db.add(_report(severity="High"))  # no reporter_id/user
        assert seams["cases"][0]["subject_id"] == f"first_aid:{new_id}"

    def test_case_failure_is_swallowed(self, db, monkeypatch):
        monkeypatch.setattr(event_bus, "publish", lambda *a, **k: None)
        monkeypatch.setattr(
            cases_bus, "open_case",
            lambda **k: (_ for _ in ()).throw(RuntimeError("cases down")),
        )
        new_id = db.add(_report(severity="Critical"))
        assert isinstance(new_id, int)


# ---------------------------------------------------------------------------
# add() — location rollup risk
# ---------------------------------------------------------------------------

class TestLocationRollup:
    def test_no_risk_below_threshold(self, db, seams):
        db.add(_report(location="Stairwell", severity="Low"))
        db.add(_report(location="Stairwell", severity="Low"))
        assert seams["risks"] == []

    def test_risk_raised_at_threshold(self, db, seams):
        for _ in range(3):
            db.add(_report(location="Stairwell", severity="Low"))
        assert len(seams["risks"]) == 1
        risk = seams["risks"][0]
        assert "Stairwell" in risk["title"]
        assert risk["category"] == "Safety"
        assert risk["reference_id"] == "location:stairwell"

    def test_idempotent_when_risk_already_exists(self, db, monkeypatch):
        monkeypatch.setattr(event_bus, "publish", lambda *a, **k: None)
        monkeypatch.setattr(cases_bus, "open_case", lambda **k: 1)
        # An existing risk for this ref => raise_risk must NOT fire again.
        raised = []
        monkeypatch.setattr(risk_bus, "list_risks_for", lambda ref: ["existing"])
        monkeypatch.setattr(risk_bus, "raise_risk",
                            lambda **kw: raised.append(kw))
        for _ in range(3):
            db.add(_report(location="Stairwell", severity="Low"))
        assert raised == []

    def test_no_location_skips_rollup(self, db, seams):
        db.add(_report(location="", severity="Low"))
        assert seams["risk_lookups"] == []
        assert seams["risks"] == []

    def test_rollup_failure_is_swallowed(self, db, monkeypatch):
        monkeypatch.setattr(event_bus, "publish", lambda *a, **k: None)
        monkeypatch.setattr(cases_bus, "open_case", lambda **k: 1)
        monkeypatch.setattr(
            risk_bus, "list_risks_for",
            lambda ref: (_ for _ in ()).throw(RuntimeError("risk down")),
        )
        for _ in range(3):
            new_id = db.add(_report(location="Stairwell", severity="Low"))
        assert isinstance(new_id, int)


# ---------------------------------------------------------------------------
# fetch_all / update_status
# ---------------------------------------------------------------------------

class TestFetchAndStatus:
    def _seed(self, db):
        db.add(_report(location="A", severity="Low", incident_type="Cut"))
        db.add(_report(location="B", severity="High", incident_type="Fall"))

    def test_fetch_all_newest_first(self, db, seams):
        self._seed(db)
        rows = db.fetch_all()
        assert [r["id"] for r in rows] == sorted(
            [r["id"] for r in rows], reverse=True
        )
        assert len(rows) == 2

    def test_fetch_filter_by_severity(self, db, seams):
        self._seed(db)
        rows = db.fetch_all(severity="high")
        assert len(rows) == 1
        assert rows[0]["severity"] == "High"

    def test_fetch_filter_by_status(self, db, seams):
        self._seed(db)
        rows = db.fetch_all()
        db.update_status(rows[0]["id"], "Resolved")
        resolved = db.fetch_all(status="resolved")
        assert len(resolved) == 1
        assert resolved[0]["status"] == "Resolved"

    def test_fetch_filter_by_severity_and_status(self, db, seams):
        self._seed(db)
        assert db.fetch_all(severity="low", status="open")[0]["severity"] == "Low"
        assert db.fetch_all(severity="low", status="resolved") == []

    def test_update_status_returns_true_when_found(self, db, seams):
        new_id = db.add(_report(severity="Low"))
        assert db.update_status(new_id, "Resolved") is True

    def test_update_status_returns_false_when_missing(self, db):
        assert db.update_status(999999, "Resolved") is False


# ---------------------------------------------------------------------------
# training registrations
# ---------------------------------------------------------------------------

class TestRegistrations:
    def test_add_and_fetch(self, db):
        rid = db.add_registration({
            "submitted_at": _now(), "course": "Basic First Aid",
            "name": "Bea", "email": "bea@x.test", "phone": "123",
            "preferred_date": "2026-08-01", "notes": "vegetarian lunch",
        })
        assert isinstance(rid, int)
        regs = db.fetch_registrations()
        assert len(regs) == 1
        assert regs[0]["course"] == "Basic First Aid"
        assert regs[0]["name"] == "Bea"

    def test_add_registration_defaults_optional_fields(self, db):
        rid = db.add_registration({
            "submitted_at": _now(), "course": "CPR", "name": "Cy",
        })
        reg = db.fetch_registrations()[0]
        assert reg["id"] == rid
        assert reg["email"] == ""
        assert reg["phone"] == ""

    def test_fetch_registrations_newest_first(self, db):
        for name in ("First", "Second", "Third"):
            db.add_registration({
                "submitted_at": _now(), "course": "CPR", "name": name,
            })
        regs = db.fetch_registrations()
        assert [r["id"] for r in regs] == sorted(
            [r["id"] for r in regs], reverse=True
        )
