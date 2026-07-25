"""Behavioral tests for the Health & Safety data layer (``HSDatabase``).

``HSDatabase`` bootstraps its own ``hs_incidents``/``hs_hazards``/``hs_training``
tables over the shared ``get_connection`` path, so the fixture points
``DEFAULT_DB_PATH`` at an empty **temp** DB (never the live app DB).
``add_incident`` fans out to the event bus and finance_bus, and
``schedule_evacuation_drill`` writes to ``academic_calendar_events`` and the
event bus — all replaced with recorders / seeded temp tables here.
"""

import sqlite3

import pytest

from education_system.systems.university.interfaces.gui.academics import (
    _event_bus as event_bus,
)
from education_system.systems.university.services.bus import finance_bus
from education_system.systems.university.domain.governance.health_safety.health_safety_service import (
    HSDatabase,
)

_DB_PATH_ATTR = (
    "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH"
)

_CALENDAR_SCHEMA = """
CREATE TABLE academic_calendar_events (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    date TEXT,
    description TEXT,
    event_type TEXT DEFAULT 'Academic',
    date_added TEXT NOT NULL,
    last_modified TEXT,
    created_by TEXT
);
"""


@pytest.fixture()
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "hs.db"))
    return HSDatabase()


@pytest.fixture()
def db_with_calendar(tmp_path, monkeypatch):
    """HSDatabase whose temp DB also has the academic_calendar_events table."""
    path = str(tmp_path / "hs_cal.db")
    monkeypatch.setattr(_DB_PATH_ATTR, path)
    conn = sqlite3.connect(path)
    conn.executescript(_CALENDAR_SCHEMA)
    conn.commit()
    conn.close()
    return HSDatabase(), path


@pytest.fixture()
def seams(monkeypatch):
    rec = {"published": [], "charges": []}
    monkeypatch.setattr(
        event_bus, "publish",
        lambda event, **kw: rec["published"].append((event, kw)),
    )
    monkeypatch.setattr(
        finance_bus, "raise_charge",
        lambda subject, amount, **kw: rec["charges"].append((subject, amount, kw)),
    )
    return rec


def _raw(owner, sql, params=()):
    conn = owner._connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_tables_created(self, db):
        names = {
            r["name"]
            for r in _raw(db, "SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"hs_incidents", "hs_hazards", "hs_training"} <= names

    def test_init_idempotent(self, tmp_path, monkeypatch):
        monkeypatch.setattr(_DB_PATH_ATTR, str(tmp_path / "d.db"))
        HSDatabase()
        HSDatabase()  # second bootstrap over same DB must not raise


# ---------------------------------------------------------------------------
# incidents
# ---------------------------------------------------------------------------

class TestIncidents:
    def test_add_persists_and_returns_id(self, db, seams):
        new_id = db.add_incident({
            "ref": "INC-1", "incident_type": "Slip", "location": "Lobby",
            "severity": "Low", "description": "wet floor",
        })
        assert isinstance(new_id, int)
        rows = db.list_incidents()
        assert len(rows) == 1
        assert rows[0]["ref"] == "INC-1"
        assert rows[0]["status"] == "Open"
        assert rows[0]["reported_at"]

    def test_add_publishes_event(self, db, seams):
        new_id = db.add_incident({
            "incident_type": "Fire", "severity": "High", "location": "Lab",
            "department": "Chem",
        })
        assert len(seams["published"]) == 1
        event, kw = seams["published"][0]
        assert event == event_bus.EVENT_INCIDENT_LOGGED
        assert kw["incident_id"] == new_id
        assert kw["domain"] == "hs"
        assert kw["department"] == "Chem"

    def test_list_newest_first(self, db, seams):
        db.add_incident({"incident_type": "A"})
        db.add_incident({"incident_type": "B"})
        rows = db.list_incidents()
        assert [r["id"] for r in rows] == sorted(
            [r["id"] for r in rows], reverse=True
        )

    def test_status_defaults_can_be_overridden(self, db, seams):
        db.add_incident({"incident_type": "X", "status": "Closed"})
        assert db.list_incidents()[0]["status"] == "Closed"

    def test_update_status_sets_status_and_timestamp(self, db, seams):
        new_id = db.add_incident({"incident_type": "X"})
        db.update_incident_status(new_id, "Resolved")
        row = db.list_incidents()[0]
        assert row["status"] == "Resolved"
        assert row["updated_at"]

    def test_publish_failure_does_not_break_add(self, db, monkeypatch):
        monkeypatch.setattr(
            event_bus, "publish",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bus down")),
        )
        new_id = db.add_incident({"incident_type": "X"})
        assert isinstance(new_id, int)


class TestIncidentFinanceLink:
    def test_estimated_cost_raises_charge(self, db, seams):
        new_id = db.add_incident({
            "incident_type": "Damage", "reported_by": "dept-eng",
            "estimated_cost": "150.5",
        })
        assert len(seams["charges"]) == 1
        subject, amount, kw = seams["charges"][0]
        assert subject == "dept-eng"
        assert amount == 150.5
        assert kw["reference_id"] == f"incident:{new_id}"
        assert kw["source"] == "hs_incident"

    def test_cost_key_used_when_no_estimated_cost(self, db, seams):
        db.add_incident({"incident_type": "Damage", "cost": 42})
        assert seams["charges"][0][1] == 42.0

    def test_zero_cost_raises_no_charge(self, db, seams):
        db.add_incident({"incident_type": "Damage", "estimated_cost": 0})
        assert seams["charges"] == []

    def test_negative_cost_raises_no_charge(self, db, seams):
        db.add_incident({"incident_type": "Damage", "estimated_cost": -10})
        assert seams["charges"] == []

    def test_no_cost_raises_no_charge(self, db, seams):
        db.add_incident({"incident_type": "Damage"})
        assert seams["charges"] == []

    def test_non_numeric_cost_is_swallowed(self, db, seams):
        new_id = db.add_incident({
            "incident_type": "Damage", "estimated_cost": "not-a-number",
        })
        assert isinstance(new_id, int)
        assert seams["charges"] == []

    def test_default_subject_when_no_reporter(self, db, seams):
        db.add_incident({"incident_type": "Damage", "cost": 5})
        assert seams["charges"][0][0] == "department"

    def test_finance_failure_is_swallowed(self, db, monkeypatch):
        monkeypatch.setattr(event_bus, "publish", lambda *a, **k: None)
        monkeypatch.setattr(
            finance_bus, "raise_charge",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("finance down")),
        )
        new_id = db.add_incident({"incident_type": "Damage", "cost": 5})
        assert isinstance(new_id, int)


# ---------------------------------------------------------------------------
# hazards
# ---------------------------------------------------------------------------

class TestHazards:
    def test_add_and_list(self, db):
        hid = db.add_hazard({
            "ref": "HAZ-1", "category": "Electrical", "location": "Server room",
            "risk_level": "High", "description": "exposed wiring",
        })
        assert isinstance(hid, int)
        rows = db.list_hazards()
        assert len(rows) == 1
        assert rows[0]["category"] == "Electrical"
        assert rows[0]["status"] == "Active"  # default

    def test_status_override(self, db):
        db.add_hazard({"category": "Trip", "status": "Completed"})
        assert db.list_hazards()[0]["status"] == "Completed"

    def test_list_newest_first(self, db):
        db.add_hazard({"category": "A"})
        db.add_hazard({"category": "B"})
        rows = db.list_hazards()
        assert [r["id"] for r in rows] == sorted(
            [r["id"] for r in rows], reverse=True
        )

    def test_update_status_returns_true_when_found(self, db):
        hid = db.add_hazard({"category": "Trip"})
        assert db.update_hazard_status(hid, "Completed") is True
        assert db.list_hazards()[0]["status"] == "Completed"

    def test_update_status_returns_false_when_missing(self, db):
        assert db.update_hazard_status(999999, "Completed") is False


# ---------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------

class TestTraining:
    def test_add_and_list(self, db):
        tid = db.add_training({
            "user": "u1", "module": "Fire Safety", "department": "Ops",
        })
        assert isinstance(tid, int)
        rows = db.list_training()
        assert len(rows) == 1
        assert rows[0]["user"] == "u1"
        assert rows[0]["module"] == "Fire Safety"
        assert rows[0]["completed_at"]

    def test_department_defaults_to_empty(self, db):
        db.add_training({"user": "u2", "module": "Manual Handling"})
        assert db.list_training()[0]["department"] == ""

    def test_list_newest_first(self, db):
        db.add_training({"user": "a", "module": "M"})
        db.add_training({"user": "b", "module": "M"})
        rows = db.list_training()
        assert [r["id"] for r in rows] == sorted(
            [r["id"] for r in rows], reverse=True
        )


# ---------------------------------------------------------------------------
# schedule_evacuation_drill
# ---------------------------------------------------------------------------

class TestEvacuationDrill:
    def test_success_persists_event_and_returns_id(self, db_with_calendar, seams):
        svc, path = db_with_calendar
        event_id = svc.schedule_evacuation_drill(
            drill_date="2026-09-01", location="Block A",
            description="Termly drill", scheduled_by="hs_admin",
        )
        assert isinstance(event_id, str) and event_id
        rows = _raw(svc, "SELECT * FROM academic_calendar_events")
        assert len(rows) == 1
        assert rows[0]["event_type"] == "evacuation_drill"
        assert rows[0]["date"] == "2026-09-01"
        assert "Block A" in rows[0]["name"]
        # calendar-changed event published
        assert any(
            e == event_bus.EVENT_CALENDAR_CHANGED for e, _ in seams["published"]
        )

    def test_defaults_location_and_description(self, db_with_calendar, seams):
        svc, _ = db_with_calendar
        svc.schedule_evacuation_drill(drill_date="2026-09-02")
        row = _raw(svc, "SELECT * FROM academic_calendar_events")[0]
        assert "campus" in row["name"]
        assert row["description"] == "Scheduled evacuation drill"

    def test_calendar_publish_failure_still_returns_id(
        self, db_with_calendar, monkeypatch
    ):
        svc, _ = db_with_calendar
        monkeypatch.setattr(
            event_bus, "publish",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bus down")),
        )
        event_id = svc.schedule_evacuation_drill(drill_date="2026-09-03")
        assert isinstance(event_id, str) and event_id

    def test_missing_calendar_table_returns_none(self, db, seams):
        # The default fixture DB has no academic_calendar_events table, so the
        # insert fails and the method returns None (logged warning).
        assert db.schedule_evacuation_drill(drill_date="2026-09-04") is None
