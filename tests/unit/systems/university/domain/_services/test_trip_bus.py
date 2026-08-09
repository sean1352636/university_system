"""Unit tests for the cross-domain trip bus (``modules.services.trip_bus``).

``trip_bus`` treats ``trips`` as the canonical store and reaches the DB through the
shared ``get_connection`` helper, which resolves its target file from the module-level
``DEFAULT_DB_PATH``. Unlike ``cert_bus`` it does **not** create its own schema, so the
fixture seeds the handful of tables its SQL touches (``trips``, ``trip_registrations``,
``academic_calendar_events``, ``users``) into a per-test temp DB.

``_publish`` (the academics GUI event bus) is neutralised per test, and every
cross-bus seam it reaches lazily (``staff_hr_bus``, ``cert_bus``, ``finance_bus``,
``risk_bus``, ``cases_bus``) is monkeypatched at the module it imports from.
"""

from datetime import datetime, timedelta

import pytest

from education_system.systems.university.infrastructure.database.db import sqlite3
from education_system.systems.university.services.bus import (
    trip_bus,
    finance_bus,
    risk_bus,
    cert_bus,
    cases_bus,
    staff_hr_bus,
)


def _date(offset_days: int) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


_SCHEMA = """
CREATE TABLE trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_name TEXT, description TEXT, destination TEXT,
    start_date TEXT, end_date TEXT, max_participants INTEGER,
    cost REAL, status TEXT, created_by INTEGER,
    created_at TEXT, updated_at TEXT
);
CREATE TABLE trip_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id INTEGER, user_id INTEGER,
    registration_date TEXT, status TEXT
);
CREATE TABLE academic_calendar_events (
    id TEXT PRIMARY KEY, name TEXT, date TEXT,
    date_start TEXT, date_end TEXT, description TEXT,
    event_type TEXT, date_added TEXT, last_modified TEXT, created_by TEXT
);
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT, student_id TEXT
);
"""


@pytest.fixture()
def trip_db(tmp_path, monkeypatch):
    """Point the shared DB layer at a temp file, seed the tables trip_bus reads,
    and silence event publishing."""
    db_path = str(tmp_path / "trip.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr(trip_bus, "_publish", lambda *a, **k: None)
    return db_path


def _seed_user(db_path, *, username, uid=None):
    conn = sqlite3.connect(db_path)
    if uid is None:
        cur = conn.execute("INSERT INTO users (username) VALUES (?)", (username,))
        uid = cur.lastrowid
    else:
        conn.execute("INSERT INTO users (id, username) VALUES (?, ?)", (uid, username))
    conn.commit()
    conn.close()
    return uid


# ---------------------------------------------------------------------------
# create_trip
# ---------------------------------------------------------------------------

class TestCreateTrip:
    @pytest.mark.parametrize(
        "kw",
        [
            {"name": "T", "destination": "D", "start_date": _date(5), "kind": "bogus"},
            {"name": "", "destination": "D", "start_date": _date(5)},
            {"name": "T", "destination": "D", "start_date": ""},
        ],
    )
    def test_invalid_input_returns_none(self, trip_db, kw):
        assert trip_bus.create_trip(**kw) is None

    def test_basic_trip_persists_and_returns_id(self, trip_db):
        tid = trip_bus.create_trip(
            name="Museum Visit", destination="London",
            start_date=_date(10), end_date=_date(11), cost=25.0,
        )
        assert isinstance(tid, int)
        trips = trip_bus.list_trips()
        assert len(trips) == 1
        assert trips[0]["trip_name"] == "Museum Visit"
        assert trips[0]["kind"] == "trip"

    def test_creates_calendar_event(self, trip_db):
        trip_bus.create_trip(
            name="Museum Visit", destination="London", start_date=_date(10),
        )
        conn = sqlite3.connect(trip_db)
        n = conn.execute("SELECT COUNT(*) FROM academic_calendar_events").fetchone()[0]
        conn.close()
        assert n == 1

    def test_created_by_username_resolves_to_user_id(self, trip_db):
        uid = _seed_user(trip_db, username="prof")
        tid = trip_bus.create_trip(
            name="Lab Tour", destination="Site", start_date=_date(3),
            created_by="prof",
        )
        conn = sqlite3.connect(trip_db)
        stored = conn.execute(
            "SELECT created_by FROM trips WHERE id = ?", (tid,)
        ).fetchone()[0]
        conn.close()
        assert stored == uid

    def test_leader_unavailable_blocks(self, trip_db, monkeypatch):
        monkeypatch.setattr(staff_hr_bus, "is_available_on", lambda sid, d: False)
        tid = trip_bus.create_trip(
            name="Trip", destination="D", start_date=_date(5),
            leader_staff_id=99,
        )
        assert tid is None

    def test_field_trip_without_first_aid_is_refused(self, trip_db, monkeypatch):
        monkeypatch.setattr(staff_hr_bus, "is_available_on", lambda sid, d: True)
        monkeypatch.setattr(cert_bus, "list_certifications_for", lambda sid: [])
        events = []
        monkeypatch.setattr(trip_bus, "_publish",
                            lambda ev, **kw: events.append((ev, kw)))
        tid = trip_bus.create_trip(
            name="Fieldwork", destination="Coast", start_date=_date(7),
            kind="field_trip", leader_staff_id=42,
        )
        assert tid is None
        assert any(ev == "trip.refused" for ev, _ in events)

    def test_field_trip_with_first_aid_persists_and_raises_risk(self, trip_db, monkeypatch):
        monkeypatch.setattr(staff_hr_bus, "is_available_on", lambda sid, d: True)
        monkeypatch.setattr(
            cert_bus, "list_certifications_for",
            lambda sid: [{"name": "First Aid", "status": "active",
                          "expiry_date": _date(90)}],
        )
        raised = []
        monkeypatch.setattr(risk_bus, "raise_risk",
                            lambda **kw: raised.append(kw) or 1)
        tid = trip_bus.create_trip(
            name="Fieldwork", destination="Coast", start_date=_date(7),
            kind="field_trip", leader_staff_id=42,
        )
        assert isinstance(tid, int)
        assert len(raised) == 1
        assert raised[0]["reference_id"] == f"trip:{tid}"
        assert raised[0]["category"] == "Safety"


# ---------------------------------------------------------------------------
# register_student
# ---------------------------------------------------------------------------

class TestRegisterStudent:
    def test_missing_args(self, trip_db):
        assert trip_bus.register_student(0, "S1")["ok"] is False
        assert trip_bus.register_student(1, "")["ok"] is False

    def test_finance_hold_blocks(self, trip_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: True)
        out = trip_bus.register_student(1, 123)
        assert out["ok"] is False
        assert "hold" in out["reason"].lower()

    def test_numeric_student_registers(self, trip_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: False)
        out = trip_bus.register_student(1, 123)
        assert out["ok"] is True
        assert isinstance(out["registration_id"], int)
        assert out["charge_tx"] is None
        conn = sqlite3.connect(trip_db)
        row = conn.execute(
            "SELECT user_id, status FROM trip_registrations WHERE id = ?",
            (out["registration_id"],),
        ).fetchone()
        conn.close()
        assert row[0] == 123
        assert row[1] == "registered"

    def test_fee_raises_charge(self, trip_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: False)
        monkeypatch.setattr(finance_bus, "raise_charge", lambda *a, **k: "TX-9")
        out = trip_bus.register_student(1, 123, fee=50.0)
        assert out["ok"] is True
        assert out["charge_tx"] == "TX-9"

    def test_username_resolves(self, trip_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: False)
        uid = _seed_user(trip_db, username="S777")
        out = trip_bus.register_student(1, "S777")
        assert out["ok"] is True
        conn = sqlite3.connect(trip_db)
        stored = conn.execute(
            "SELECT user_id FROM trip_registrations WHERE id = ?",
            (out["registration_id"],),
        ).fetchone()[0]
        conn.close()
        assert stored == uid

    def test_unresolvable_username_fails(self, trip_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: False)
        out = trip_bus.register_student(1, "ghost")
        assert out["ok"] is False
        assert "resolve" in out["reason"]


# ---------------------------------------------------------------------------
# cancel_registration
# ---------------------------------------------------------------------------

class TestCancelRegistration:
    def _register(self, db_path, trip_id, user_id):
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO trip_registrations (trip_id, user_id, status) "
            "VALUES (?, ?, 'registered')",
            (trip_id, user_id),
        )
        conn.commit()
        conn.close()

    def test_missing_args(self, trip_db):
        assert trip_bus.cancel_registration(0, "S1")["ok"] is False

    def test_marks_cancelled(self, trip_db):
        self._register(trip_db, 5, 123)
        out = trip_bus.cancel_registration(5, 123)
        assert out["ok"] is True
        conn = sqlite3.connect(trip_db)
        status = conn.execute(
            "SELECT status FROM trip_registrations WHERE trip_id = 5 AND user_id = 123"
        ).fetchone()[0]
        conn.close()
        assert status == "cancelled"

    def test_fee_and_refund_raise_two_charges(self, trip_db, monkeypatch):
        self._register(trip_db, 5, 123)
        calls = []
        monkeypatch.setattr(
            finance_bus, "raise_charge",
            lambda sid, amt, **k: calls.append(amt) or f"tx{len(calls)}",
        )
        out = trip_bus.cancel_registration(
            5, 123, cancellation_fee=10.0, refund_paid_fee=40.0,
        )
        assert out["ok"] is True
        assert out["cancel_tx"] == "tx1"
        assert out["refund_tx"] == "tx2"
        # Refund is posted as a negative (credit) charge.
        assert calls == [10.0, -40.0]

    def test_unresolvable_username_fails(self, trip_db):
        out = trip_bus.cancel_registration(5, "ghost")
        assert out["ok"] is False


# ---------------------------------------------------------------------------
# record_incident
# ---------------------------------------------------------------------------

class TestRecordIncident:
    def test_minor_is_calendar_note_only(self, trip_db, monkeypatch):
        called = []
        monkeypatch.setattr(cases_bus, "open_case", lambda **k: called.append(k) or 1)
        out = trip_bus.record_incident(5, 123, severity="Minor", description="late")
        assert out["ok"] is True
        assert out["case_id"] is None
        assert called == []

    def test_major_opens_case(self, trip_db, monkeypatch):
        monkeypatch.setattr(cases_bus, "open_case", lambda **k: 777)
        out = trip_bus.record_incident(5, 123, severity="Major", kind="safety",
                                       description="injury")
        assert out["ok"] is True
        assert out["case_id"] == 777

    def test_open_case_failure_sets_not_ok(self, trip_db, monkeypatch):
        def boom(**k):
            raise RuntimeError("nope")
        monkeypatch.setattr(cases_bus, "open_case", boom)
        out = trip_bus.record_incident(5, 123, severity="Critical")
        assert out["ok"] is False
        assert "nope" in out["reason"]


# ---------------------------------------------------------------------------
# list_trips
# ---------------------------------------------------------------------------

class TestListTrips:
    def test_empty(self, trip_db):
        assert trip_bus.list_trips() == []

    def test_since_and_kind_filters(self, trip_db):
        trip_bus.create_trip(name="Old", destination="D", start_date=_date(-20))
        trip_bus.create_trip(name="SoonField", destination="D",
                             start_date=_date(10), kind="field_trip")
        # since filters out the old trip.
        recent = trip_bus.list_trips(since=_date(0))
        assert [t["trip_name"] for t in recent] == ["SoonField"]
        # kind filter matches the tagged description.
        only_field = trip_bus.list_trips(kind="field_trip")
        assert [t["trip_name"] for t in only_field] == ["SoonField"]
        assert only_field[0]["kind"] == "field_trip"

    def test_kind_marker_stripped_from_description(self, trip_db):
        trip_bus.create_trip(name="Note", destination="D", start_date=_date(3),
                             description="bring boots")
        (row,) = trip_bus.list_trips()
        assert row["kind"] == "trip"
        assert row["description"] == "bring boots"

    def test_limit(self, trip_db):
        for i in range(3):
            trip_bus.create_trip(name=f"T{i}", destination="D", start_date=_date(i + 1))
        assert len(trip_bus.list_trips(limit=2)) == 2


# ---------------------------------------------------------------------------
# list_registrations_for
# ---------------------------------------------------------------------------

class TestListRegistrationsFor:
    def test_empty_for_falsy(self, trip_db):
        assert trip_bus.list_registrations_for("") == []
        assert trip_bus.list_registrations_for(None) == []

    def test_numeric_student_returns_joined_rows(self, trip_db):
        tid = trip_bus.create_trip(name="Show", destination="D", start_date=_date(4))
        conn = sqlite3.connect(trip_db)
        conn.execute(
            "INSERT INTO trip_registrations (trip_id, user_id, status, registration_date) "
            "VALUES (?, 123, 'registered', ?)",
            (tid, _date(0)),
        )
        conn.commit()
        conn.close()
        rows = trip_bus.list_registrations_for(123)
        assert len(rows) == 1
        assert rows[0]["trip_id"] == tid
        assert rows[0]["trip_name"] == "Show"

    def test_username_resolution(self, trip_db):
        uid = _seed_user(trip_db, username="S321")
        conn = sqlite3.connect(trip_db)
        conn.execute(
            "INSERT INTO trip_registrations (trip_id, user_id, status) "
            "VALUES (1, ?, 'registered')",
            (uid,),
        )
        conn.commit()
        conn.close()
        rows = trip_bus.list_registrations_for("S321")
        assert len(rows) == 1

    def test_unresolvable_username_returns_empty(self, trip_db):
        assert trip_bus.list_registrations_for("ghost") == []
