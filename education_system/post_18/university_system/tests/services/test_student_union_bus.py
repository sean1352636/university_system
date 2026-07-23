"""Unit tests for the cross-domain Student Union bus (``modules.services.student_union_bus``).

``student_union_bus`` reaches the DB through the shared ``get_connection`` helper,
which resolves its target file from the module-level ``DEFAULT_DB_PATH``. Repointing
that constant at a per-test temp file gives full isolation.

Unlike ``cert_bus`` this module only owns ``su_advocacy_requests`` (created via
``_ensure_schema``) and creates ``gym_day_passes`` on demand. It *reads* several
tables it does not create — ``club_memberships``, ``student_union_clubs``,
``student_finance_transactions``, ``academic_calendar_events``,
``housing_assignments``, ``housing_rooms`` — so the fixture seeds those empty
stand-ins. ``_publish`` (the academics GUI event bus) is neutralised per test, and
cross-bus calls (finance_bus / cases_bus / risk_bus) are stubbed at their seams.
"""

from datetime import datetime

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services import student_union_bus as su


_SEED_SCHEMA = """
CREATE TABLE IF NOT EXISTS student_union_clubs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT,
    category TEXT
);
CREATE TABLE IF NOT EXISTS club_memberships (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    club_id    INTEGER NOT NULL,
    student_id TEXT NOT NULL,
    join_date  TEXT,
    status     TEXT
);
CREATE TABLE IF NOT EXISTS student_finance_transactions (
    transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT,
    amount           REAL,
    description      TEXT,
    reference_id     TEXT,
    created_at       TEXT,
    transaction_type TEXT
);
CREATE TABLE IF NOT EXISTS academic_calendar_events (
    id            TEXT PRIMARY KEY,
    name          TEXT,
    date          TEXT,
    description   TEXT,
    event_type    TEXT,
    date_added    TEXT,
    last_modified TEXT,
    created_by    TEXT
);
CREATE TABLE IF NOT EXISTS housing_assignments (
    student_id TEXT,
    room_id    INTEGER,
    status     TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS housing_rooms (
    room_id     INTEGER PRIMARY KEY,
    building_id TEXT
);
"""


@pytest.fixture()
def su_db(tmp_path, monkeypatch):
    """Point the shared DB layer at a temp file, seed read-only stand-in tables,
    and silence event publishing. Returns the db path for direct inspection."""
    db_path = str(tmp_path / "su.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    conn = sqlite3.connect(db_path)
    conn.executescript(_SEED_SCHEMA)
    conn.commit()
    conn.close()
    monkeypatch.setattr(su, "_publish", lambda *a, **k: None)
    return db_path


def _add_club(db_path, name="Chess", category="Games"):
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO student_union_clubs (name, category) VALUES (?, ?)",
        (name, category),
    )
    club_id = cur.lastrowid
    conn.commit()
    conn.close()
    return club_id


# ---------------------------------------------------------------------------
# Membership: join / list / is_member / leave
# ---------------------------------------------------------------------------

class TestJoinClub:
    def test_persists_membership_and_returns_id(self, su_db):
        club_id = _add_club(su_db)
        mid = su.join_club("S001", club_id)
        assert isinstance(mid, int)
        assert su.is_member_of("S001", club_id) is True
        clubs = su.list_clubs_for("S001")
        assert len(clubs) == 1
        assert clubs[0]["club_id"] == club_id
        assert clubs[0]["name"] == "Chess"

    def test_free_join_does_not_call_finance(self, su_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import finance_bus
        called = []
        monkeypatch.setattr(finance_bus, "has_active_hold",
                            lambda sid: called.append(sid) or True)
        # fee=0 → hold gate skipped entirely.
        club_id = _add_club(su_db)
        assert su.join_club("S001", club_id) is not None
        assert called == []

    def test_fee_join_refused_on_active_hold(self, su_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import finance_bus
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: True)
        club_id = _add_club(su_db)
        assert su.join_club("S001", club_id, fee=10.0) is None
        # No membership row written.
        assert su.is_member_of("S001", club_id) is False

    def test_fee_join_override_ignores_hold_and_charges(self, su_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import finance_bus
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: True)
        charges = []
        monkeypatch.setattr(finance_bus, "raise_charge",
                            lambda *a, **k: charges.append((a, k)) or 42)
        club_id = _add_club(su_db)
        mid = su.join_club("S001", club_id, fee=10.0, ignore_holds=True)
        assert mid is not None
        assert len(charges) == 1

    def test_fee_join_charges_when_no_hold(self, su_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import finance_bus
        monkeypatch.setattr(finance_bus, "has_active_hold", lambda sid: False)
        charges = []
        monkeypatch.setattr(finance_bus, "raise_charge",
                            lambda *a, **k: charges.append(k) or 7)
        club_id = _add_club(su_db)
        assert su.join_club("S001", club_id, fee=25.0) is not None
        assert len(charges) == 1

    def test_fitness_club_grants_gym_day_passes(self, su_db):
        club_id = _add_club(su_db, name="Rowing", category="Sports & Fitness")
        su.join_club("S007", club_id)
        conn = sqlite3.connect(su_db)
        n = conn.execute(
            "SELECT COUNT(*) FROM gym_day_passes WHERE student_id = ?", ("S007",)
        ).fetchone()[0]
        conn.close()
        assert n == 3

    def test_non_fitness_club_no_gym_passes(self, su_db):
        club_id = _add_club(su_db, name="Debate", category="Academic")
        su.join_club("S008", club_id)
        conn = sqlite3.connect(su_db)
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='gym_day_passes'"
        ).fetchone()
        conn.close()
        # Table is only created by the fitness perk path.
        assert exists is None


class TestListClubsFor:
    def test_empty_for_falsy_student(self, su_db):
        assert su.list_clubs_for("") == []
        assert su.list_clubs_for(None) == []

    def test_excludes_inactive_membership(self, su_db):
        club_id = _add_club(su_db)
        su.join_club("S001", club_id)
        assert len(su.list_clubs_for("S001")) == 1
        su.leave_club("S001", club_id)
        assert su.list_clubs_for("S001") == []


class TestIsMemberOf:
    def test_false_for_falsy_args(self, su_db):
        assert su.is_member_of("", 1) is False
        assert su.is_member_of("S001", None) is False

    def test_false_when_not_joined(self, su_db):
        club_id = _add_club(su_db)
        assert su.is_member_of("S001", club_id) is False


class TestLeaveClub:
    def test_marks_inactive_and_returns_true(self, su_db):
        club_id = _add_club(su_db)
        su.join_club("S001", club_id)
        assert su.leave_club("S001", club_id) is True
        assert su.is_member_of("S001", club_id) is False


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

class TestChargeMembershipFee:
    @pytest.mark.parametrize("amount", [0, 0.0, -5])
    def test_non_positive_amount_returns_none(self, su_db, amount):
        assert su.charge_membership_fee("S001", 1, amount) is None

    def test_delegates_to_finance_raise_charge(self, su_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import finance_bus
        captured = {}
        monkeypatch.setattr(
            finance_bus, "raise_charge",
            lambda sid, amt, **k: captured.update(sid=sid, amt=amt, **k) or 99,
        )
        out = su.charge_membership_fee("S001", 3, 12.5)
        assert out == 99
        assert captured["sid"] == "S001"
        assert captured["amt"] == 12.5
        assert captured["reference_id"] == "club:3"
        assert captured["source"] == "su_membership"


class TestListOutstandingSuCharges:
    def test_empty_for_falsy_student(self, su_db):
        assert su.list_outstanding_su_charges("") == []

    def test_returns_recent_club_charges_only(self, su_db):
        conn = sqlite3.connect(su_db)
        conn.executemany(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, description, reference_id, created_at, "
            " transaction_type) VALUES (?, ?, ?, ?, ?, ?)",
            [
                # matching SU club charge, recent
                ("S001", 10.0, "SU club", "club:1",
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "charge"),
                # non-club reference → excluded
                ("S001", 20.0, "Tuition", "tuition:1",
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "charge"),
                # club charge but > 365 days old → excluded
                ("S001", 30.0, "Old", "club:9", "2000-01-01 00:00:00", "charge"),
                # wrong transaction_type → excluded
                ("S001", 40.0, "Refund", "club:2",
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "payment"),
            ],
        )
        conn.commit()
        conn.close()
        rows = su.list_outstanding_su_charges("S001")
        assert len(rows) == 1
        assert rows[0]["reference_id"] == "club:1"


# ---------------------------------------------------------------------------
# Advocacy
# ---------------------------------------------------------------------------

class TestAdvocacy:
    def test_request_persists_and_returns_id(self, su_db):
        rid = su.request_advocacy("S001", 55, "disciplinary", notes="help")
        assert isinstance(rid, int)
        rows = su.list_advocacy_requests_for("S001")
        assert len(rows) == 1
        assert rows[0]["case_id"] == 55
        assert rows[0]["status"] == "pending"

    @pytest.mark.parametrize("sid, cid", [("", 1), ("S001", 0), (None, 1)])
    def test_request_missing_required_returns_none(self, su_db, sid, cid):
        assert su.request_advocacy(sid, cid) is None

    def test_record_claims_pending_request(self, su_db):
        rid = su.request_advocacy("S001", 55)
        assert su.record_advocacy(rid, "REP1", notes="on it") is True
        rows = su.list_advocacy_requests_for("S001")
        assert rows[0]["status"] == "claimed"
        assert rows[0]["su_rep_id"] == "REP1"

    def test_record_does_not_reclaim_non_pending(self, su_db):
        rid = su.request_advocacy("S001", 55)
        su.record_advocacy(rid, "REP1")
        # Second claim is a no-op UPDATE (status already 'claimed') but still True.
        assert su.record_advocacy(rid, "REP2") is True
        rows = su.list_advocacy_requests_for("S001")
        assert rows[0]["su_rep_id"] == "REP1"

    def test_list_only_active_filter(self, su_db):
        rid = su.request_advocacy("S001", 55)
        # Manually close it out of the active statuses.
        conn = sqlite3.connect(su_db)
        conn.execute(
            "UPDATE su_advocacy_requests SET status = 'closed' WHERE request_id = ?",
            (rid,),
        )
        conn.commit()
        conn.close()
        assert su.list_advocacy_requests_for("S001", only_active=True) == []
        assert len(su.list_advocacy_requests_for("S001", only_active=False)) == 1

    def test_list_empty_for_falsy_student(self, su_db):
        assert su.list_advocacy_requests_for("") == []


# ---------------------------------------------------------------------------
# Calendar events
# ---------------------------------------------------------------------------

class TestPublishEvent:
    def test_writes_calendar_row_and_returns_uuid(self, su_db):
        eid = su.publish_event(name="Freshers Fair", when="2026-09-20",
                               location="Union Hall", organizer_id="ORG1")
        assert isinstance(eid, str) and eid
        conn = sqlite3.connect(su_db)
        row = conn.execute(
            "SELECT name, date, event_type, created_by "
            "FROM academic_calendar_events WHERE id = ?", (eid,)
        ).fetchone()
        conn.close()
        assert row == ("Freshers Fair", "2026-09-20", "su_event", "ORG1")

    @pytest.mark.parametrize("name, when", [("", "2026-01-01"), ("Gig", "")])
    def test_missing_required_returns_none(self, su_db, name, when):
        assert su.publish_event(name=name, when=when) is None

    def test_clearance_tags_open_case_and_risk(self, su_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import (
            cases_bus, risk_bus,
        )
        opened = []
        risked = []
        monkeypatch.setattr(cases_bus, "open_case",
                            lambda **k: opened.append(k) or 1)
        monkeypatch.setattr(risk_bus, "raise_event_clearance_risk",
                            lambda *a, **k: risked.append((a, k)) or 2)
        eid = su.publish_event(name="Big Party", when="2026-10-31",
                               tags=["large", "alcohol"], organizer_id="ORG9")
        assert eid is not None
        assert len(opened) == 1
        assert opened[0]["kind"] == "event_clearance"
        assert len(risked) == 1

    def test_plain_tags_no_clearance(self, su_db, monkeypatch):
        from education_system.post_18.university_system.modules.services import (
            cases_bus, risk_bus,
        )
        opened = []
        monkeypatch.setattr(cases_bus, "open_case",
                            lambda **k: opened.append(k) or 1)
        monkeypatch.setattr(risk_bus, "raise_event_clearance_risk",
                            lambda *a, **k: 2)
        eid = su.publish_event(name="Study Group", when="2026-02-02",
                               tags=["academic"])
        assert eid is not None
        assert opened == []


# ---------------------------------------------------------------------------
# Housing <-> SU hall scoping
# ---------------------------------------------------------------------------

class TestHallScoping:
    def _seed_housing(self, db_path, student_id="S001", building_id="B1", room_id=10):
        conn = sqlite3.connect(db_path)
        conn.execute("INSERT INTO housing_rooms (room_id, building_id) VALUES (?, ?)",
                     (room_id, building_id))
        conn.execute(
            "INSERT INTO housing_assignments (student_id, room_id, status, created_at) "
            "VALUES (?, ?, 'Active', ?)",
            (student_id, room_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()

    def test_student_hall_returns_building(self, su_db):
        self._seed_housing(su_db)
        assert su.student_hall("S001") == "B1"

    def test_student_hall_none_without_assignment(self, su_db):
        assert su.student_hall("S001") is None
        assert su.student_hall("") is None

    def test_list_hall_residents(self, su_db):
        self._seed_housing(su_db, "S001", "B1", 10)
        self._seed_housing(su_db, "S002", "B1", 11)
        self._seed_housing(su_db, "S003", "B2", 12)
        residents = su.list_hall_residents("B1")
        assert set(residents) == {"S001", "S002"}
        assert su.list_hall_residents("") == []

    def test_set_and_list_hall_clubs(self, su_db):
        club_id = _add_club(su_db, name="B1 Social", category="Social")
        assert su.set_club_hall(club_id, "B1") is True
        clubs = su.list_hall_clubs("B1")
        assert len(clubs) == 1
        assert clubs[0]["hall_id"] == "B1"
        assert su.list_hall_clubs("") == []

    def test_set_club_hall_falsy_club(self, su_db):
        assert su.set_club_hall(0, "B1") is False

    def test_set_club_hall_clear_scope(self, su_db):
        club_id = _add_club(su_db)
        su.set_club_hall(club_id, "B1")
        assert su.set_club_hall(club_id, None) is True
        assert su.list_hall_clubs("B1") == []

    def test_hall_eligible_open_club(self, su_db):
        club_id = _add_club(su_db)  # no hall_id → open to everyone
        assert su.hall_eligible_for("S001", club_id) is True

    def test_hall_eligible_matching_and_mismatched(self, su_db):
        self._seed_housing(su_db, "S001", "B1", 10)
        club_id = _add_club(su_db, name="B1 Only", category="Social")
        su.set_club_hall(club_id, "B1")
        assert su.hall_eligible_for("S001", club_id) is True   # lives in B1
        assert su.hall_eligible_for("S999", club_id) is False  # no B1 room

    def test_hall_eligible_unknown_club(self, su_db):
        assert su.hall_eligible_for("S001", 123456) is False

    def test_hall_eligible_falsy_args(self, su_db):
        assert su.hall_eligible_for("", 1) is False
        assert su.hall_eligible_for("S001", 0) is False
