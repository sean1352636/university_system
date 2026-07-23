"""Unit tests for the housing→finance bridge (``modules.services.housing_finance``).

``housing_finance`` has two kinds of public surface:

* **Delegators** — ``post_rent_charge`` / ``post_deposit_charge`` /
  ``post_damage_charge`` / ``place_arrears_hold`` /
  ``release_arrears_holds_for`` / ``can_assign_room`` route through
  ``finance_bus``. These are tested by monkeypatching the ``finance_bus``
  seam and asserting the arguments passed through and the result shaping.
* **DB-backed readers** — ``check_overdue_assignments`` and
  ``list_housing_charges`` run raw SQL through the shared ``get_connection``.
  These are tested against a per-test temp DB (repoint ``DEFAULT_DB_PATH``)
  seeded with the tables they read.
"""

from __future__ import annotations

import sqlite3

import pytest

from education_system.post_18.university_system.modules.services import (
    finance_bus,
    housing_finance,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def housing_db(tmp_path, monkeypatch):
    """Point the shared DB layer at a temp file (read at call time by get_connection)."""
    db_path = str(tmp_path / "housing.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    return db_path


@pytest.fixture()
def recorder(monkeypatch):
    """Record every finance_bus call so delegators can be asserted at the seam."""
    calls: list[tuple] = []

    def _raise_charge(student_id, amount, *, source, description,
                      reference_id=None, processed_by=None):
        calls.append(("raise_charge", student_id, amount, source,
                      description, reference_id, processed_by))
        return 4242

    def _place_hold(student_id, *, reason, source, amount=0.0,
                    reference_id=None, placed_by=None):
        calls.append(("place_hold", str(student_id), reason, source,
                      amount, reference_id, placed_by))
        return 77

    monkeypatch.setattr(finance_bus, "raise_charge", _raise_charge)
    monkeypatch.setattr(finance_bus, "place_hold", _place_hold)
    return calls


# ---------------------------------------------------------------------------
# post_rent_charge
# ---------------------------------------------------------------------------

class TestPostRentCharge:
    def test_delegates_with_rent_source_and_ref(self, recorder):
        rid = housing_finance.post_rent_charge("S1", 55, 120.0)
        assert rid == 4242
        kind, sid, amount, source, desc, ref, by = recorder[0]
        assert kind == "raise_charge"
        assert sid == "S1"
        assert amount == 120.0
        assert source == "housing_rent"
        assert desc == "Housing rent"           # no period → generic desc
        assert ref == "asg:55"
        assert by == "housing"                   # default processed_by

    def test_period_dates_shape_description(self, recorder):
        housing_finance.post_rent_charge(
            "S1", 55, 120.0, period_start="2026-01-01", period_end="2026-01-31",
            processed_by="warden",
        )
        _, _, _, _, desc, _, by = recorder[0]
        assert desc == "Housing rent 2026-01-01 → 2026-01-31"
        assert by == "warden"

    @pytest.mark.parametrize("amount", [0, 0.0, -5, None])
    def test_non_positive_amount_returns_none_without_delegating(self, recorder, amount):
        assert housing_finance.post_rent_charge("S1", 55, amount) is None
        assert recorder == []


# ---------------------------------------------------------------------------
# post_deposit_charge / post_damage_charge
# ---------------------------------------------------------------------------

class TestPostDepositCharge:
    def test_delegates_with_deposit_source(self, recorder):
        housing_finance.post_deposit_charge("S2", 9, 250.0)
        _, sid, amount, source, desc, ref, _ = recorder[0]
        assert (sid, amount, source, desc, ref) == (
            "S2", 250.0, "housing_deposit", "Housing deposit", "asg:9")

    def test_non_positive_returns_none(self, recorder):
        assert housing_finance.post_deposit_charge("S2", 9, 0) is None
        assert recorder == []


class TestPostDamageCharge:
    def test_uses_supplied_description(self, recorder):
        housing_finance.post_damage_charge("S3", 3, 40.0, "Broken window")
        _, _, amount, source, desc, ref, _ = recorder[0]
        assert (amount, source, desc, ref) == (
            40.0, "housing_damage", "Broken window", "asg:3")

    def test_blank_description_falls_back(self, recorder):
        housing_finance.post_damage_charge("S3", 3, 40.0, "")
        assert recorder[0][4] == "Housing damage charge"

    def test_non_positive_returns_none(self, recorder):
        assert housing_finance.post_damage_charge("S3", 3, -1, "x") is None
        assert recorder == []


# ---------------------------------------------------------------------------
# place_arrears_hold
# ---------------------------------------------------------------------------

class TestPlaceArrearsHold:
    def test_places_new_hold_when_none_active(self, recorder, monkeypatch):
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: [])
        hid = housing_finance.place_arrears_hold("S1", 55, 300.0, placed_by="warden")
        assert hid == 77
        kind, sid, reason, source, amount, ref, by = recorder[0]
        assert kind == "place_hold"
        assert sid == "S1"
        assert source == "housing_arrears"
        assert amount == 300.0
        assert ref == "asg:55"
        assert by == "warden"
        assert "assignment 55" in reason

    def test_idempotent_returns_existing_hold_id(self, recorder, monkeypatch):
        existing = [{
            "hold_id": 12, "source": "housing_arrears", "reference_id": "asg:55",
        }]
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: existing)
        hid = housing_finance.place_arrears_hold("S1", 55, 300.0)
        assert hid == 12
        # No new hold placed.
        assert recorder == []

    def test_different_ref_does_not_match(self, recorder, monkeypatch):
        existing = [{
            "hold_id": 12, "source": "housing_arrears", "reference_id": "asg:99",
        }]
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: existing)
        hid = housing_finance.place_arrears_hold("S1", 55, 300.0)
        assert hid == 77                          # placed fresh
        assert recorder[0][0] == "place_hold"

    def test_none_amount_coerced_to_zero(self, recorder, monkeypatch):
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: [])
        housing_finance.place_arrears_hold("S1", 55, None)
        assert recorder[0][4] == 0.0


# ---------------------------------------------------------------------------
# release_arrears_holds_for
# ---------------------------------------------------------------------------

class TestReleaseArrearsHolds:
    def test_releases_all_arrears_holds(self, monkeypatch):
        holds = [
            {"hold_id": 1, "source": "housing_arrears", "reference_id": "asg:1"},
            {"hold_id": 2, "source": "housing_arrears", "reference_id": "asg:2"},
            {"hold_id": 3, "source": "library", "reference_id": "book:9"},
        ]
        released: list[int] = []
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: holds)
        monkeypatch.setattr(
            finance_bus, "release_hold",
            lambda hid, released_by=None: released.append(hid) or True,
        )
        n = housing_finance.release_arrears_holds_for("S1")
        assert n == 2                             # library hold skipped
        assert set(released) == {1, 2}

    def test_assignment_filter_targets_single_ref(self, monkeypatch):
        holds = [
            {"hold_id": 1, "source": "housing_arrears", "reference_id": "asg:1"},
            {"hold_id": 2, "source": "housing_arrears", "reference_id": "asg:2"},
        ]
        released: list[int] = []
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: holds)
        monkeypatch.setattr(
            finance_bus, "release_hold",
            lambda hid, released_by=None: released.append(hid) or True,
        )
        n = housing_finance.release_arrears_holds_for("S1", 2)
        assert n == 1
        assert released == [2]

    def test_release_failure_not_counted(self, monkeypatch):
        holds = [{"hold_id": 1, "source": "housing_arrears", "reference_id": "asg:1"}]
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: holds)
        monkeypatch.setattr(finance_bus, "release_hold", lambda hid, released_by=None: False)
        assert housing_finance.release_arrears_holds_for("S1") == 0


# ---------------------------------------------------------------------------
# can_assign_room
# ---------------------------------------------------------------------------

class TestCanAssignRoom:
    def test_falsy_student_allowed(self):
        assert housing_finance.can_assign_room("") == (True, None)
        assert housing_finance.can_assign_room(None) == (True, None)

    def test_no_holds_allowed(self, monkeypatch):
        monkeypatch.setattr(finance_bus, "list_active_holds", lambda sid: [])
        assert housing_finance.can_assign_room("S1") == (True, None)

    def test_holds_block_with_sorted_sources(self, monkeypatch):
        monkeypatch.setattr(
            finance_bus, "list_active_holds",
            lambda sid: [{"source": "library"}, {"source": "housing_arrears"}],
        )
        allowed, reason = housing_finance.can_assign_room("S1")
        assert allowed is False
        # Sources are de-duplicated and sorted.
        assert reason == "Active finance hold(s): housing_arrears, library"


# ---------------------------------------------------------------------------
# check_overdue_assignments  (DB-backed)
# ---------------------------------------------------------------------------

def _seed_overdue_tables(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE housing_assignments (
            assignment_id TEXT, student_id TEXT, monthly_rent REAL, status TEXT
        );
        CREATE TABLE payments (
            reference_id TEXT, source_type TEXT, status TEXT, payment_date TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO housing_assignments VALUES (?,?,?,?)",
        [
            ("A1", "S1", 500.0, "Active"),   # no payment → overdue
            ("A2", "S2", 500.0, "Active"),   # payment 40d ago → overdue
            ("A3", "S3", 500.0, "Active"),   # payment today → current
            ("A4", "S4", 500.0, "Ended"),    # inactive → excluded
        ],
    )
    conn.execute(
        "INSERT INTO payments VALUES ('A2','housing','Completed', date('now','-40 days'))"
    )
    conn.execute(
        "INSERT INTO payments VALUES ('A3','housing','Completed', date('now'))"
    )
    conn.commit()
    conn.close()


class TestCheckOverdueAssignments:
    def test_flags_missing_and_stale_payments(self, housing_db):
        _seed_overdue_tables(housing_db)
        rows = housing_finance.check_overdue_assignments(days_overdue=14)
        ids = {r["assignment_id"] for r in rows}
        assert ids == {"A1", "A2"}               # A3 current, A4 inactive

    def test_shorter_window_includes_recent(self, housing_db):
        _seed_overdue_tables(housing_db)
        rows = housing_finance.check_overdue_assignments(days_overdue=1)
        # A3 paid today (0 days) is still current; A1/A2 remain overdue.
        assert {r["assignment_id"] for r in rows} == {"A1", "A2"}

    def test_missing_tables_returns_empty(self, housing_db):
        # No tables created → best-effort swallow → [].
        assert housing_finance.check_overdue_assignments() == []


# ---------------------------------------------------------------------------
# list_housing_charges  (DB-backed)
# ---------------------------------------------------------------------------

def _seed_charges_table(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE student_finance_transactions (
            transaction_id INTEGER, student_id TEXT, amount REAL,
            description TEXT, reference_id TEXT, created_at TEXT,
            transaction_type TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO student_finance_transactions VALUES "
        "(1,'S1',120.0,'Rent','asg:5', date('now'), 'charge')"
    )
    conn.execute(  # payment type → excluded
        "INSERT INTO student_finance_transactions VALUES "
        "(2,'S1',50.0,'Paid','asg:5', date('now'), 'payment')"
    )
    conn.execute(  # non-housing ref → excluded
        "INSERT INTO student_finance_transactions VALUES "
        "(3,'S1',30.0,'Tuition','fee:1', date('now'), 'charge')"
    )
    conn.execute(  # too old → excluded
        "INSERT INTO student_finance_transactions VALUES "
        "(4,'S1',99.0,'Old rent','asg:5', date('now','-400 days'), 'charge')"
    )
    conn.execute(  # other student → excluded
        "INSERT INTO student_finance_transactions VALUES "
        "(5,'S2',77.0,'Rent','asg:8', date('now'), 'charge')"
    )
    conn.commit()
    conn.close()


class TestListHousingCharges:
    def test_falsy_student_returns_empty(self):
        assert housing_finance.list_housing_charges("") == []
        assert housing_finance.list_housing_charges(None) == []

    def test_returns_only_recent_housing_charges(self, housing_db):
        _seed_charges_table(housing_db)
        rows = housing_finance.list_housing_charges("S1")
        assert [r["transaction_id"] for r in rows] == [1]
        assert rows[0]["reference_id"] == "asg:5"

    def test_days_window_filters(self, housing_db):
        _seed_charges_table(housing_db)
        # The old row (400 days) stays excluded even with a 500-day window? It's
        # within 500 days, so it should now appear alongside the recent one.
        rows = housing_finance.list_housing_charges("S1", days=500)
        assert {r["transaction_id"] for r in rows} == {1, 4}

    def test_missing_table_returns_empty(self, housing_db):
        assert housing_finance.list_housing_charges("S1") == []
