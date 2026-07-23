"""Unit tests for the cross-domain parking bus (``modules.services.parking_bus``).

Unlike ``cert_bus``, ``parking_bus`` does **not** own/bootstrap its schema — it
reaches the shared DB through ``get_connection`` and expects the campus tables
(``parking_permits``, ``parking_violations``, ``users``,
``student_finance_transactions``) to already exist. So the fixture repoints the
module-level ``DEFAULT_DB_PATH`` at a per-test temp file (``get_connection``
reads it at call time) and seeds minimal stand-in tables with exactly the
columns the bus touches.

The event-bus fan-out (``_publish``) is neutralised, and the three cross-domain
seams — ``finance_bus.raise_charge``, ``finance_bus.place_hold`` and
``cases_bus.open_case`` — are stubbed at the module attribute so writes never
reach the real finance ledger or disciplinary portal.
"""

from datetime import datetime, timedelta

import pytest

from education_system.post_18.university_system.infrastructure.database.db import (
    get_connection,
    sqlite3,
)
from education_system.post_18.university_system.modules.services import (
    cases_bus,
    finance_bus,
    parking_bus,
)


def _date(offset_days: int) -> str:
    return (datetime.now() + timedelta(days=offset_days)).strftime("%Y-%m-%d")


_SEED_SQL = """
CREATE TABLE parking_permits (
    permit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    full_name     TEXT,
    email         TEXT,
    zone          TEXT,
    permit_type   TEXT,
    start_date    TEXT,
    end_date      TEXT,
    active_status INTEGER,
    vehicle_id    TEXT,
    issue_date    TEXT,
    expiry_date   TEXT,
    fee_paid      REAL,
    status        TEXT,
    student_id    TEXT,
    created_at    TEXT,
    updated_at    TEXT
);
CREATE TABLE parking_violations (
    violation_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    license_plate  TEXT,
    violation_type TEXT,
    violation_date TEXT,
    fine_amount    REAL,
    payment_status TEXT,
    location       TEXT,
    officer_id     INTEGER,
    issued_by      TEXT,
    status         TEXT
);
CREATE TABLE users (
    id       INTEGER PRIMARY KEY,
    username TEXT,
    role     TEXT
);
CREATE TABLE student_finance_transactions (
    transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT,
    amount           REAL,
    transaction_type TEXT,
    description      TEXT,
    reference_id     TEXT,
    created_at       TEXT
);
"""


@pytest.fixture()
def parking_db(tmp_path, monkeypatch):
    """Temp DB + seeded stand-in tables; publish and cross-bus seams silenced.

    Returns the db path so tests can inspect rows directly.
    """
    db_path = str(tmp_path / "parking.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    with get_connection() as conn:
        conn.executescript(_SEED_SQL)
        conn.commit()

    monkeypatch.setattr(parking_bus, "_publish", lambda *a, **k: None)
    return db_path


@pytest.fixture()
def stub_finance(monkeypatch):
    """Capture finance_bus.raise_charge / place_hold calls without side effects."""
    charges: list[dict] = []
    holds: list[dict] = []

    def _raise_charge(holder, amount, **kw):
        charges.append({"holder": holder, "amount": amount, **kw})
        return 5000 + len(charges)

    def _place_hold(holder, **kw):
        holds.append({"holder": holder, **kw})
        return 9000 + len(holds)

    monkeypatch.setattr(finance_bus, "raise_charge", _raise_charge)
    monkeypatch.setattr(finance_bus, "place_hold", _place_hold)
    return {"charges": charges, "holds": holds}


@pytest.fixture()
def stub_cases(monkeypatch):
    cases: list[dict] = []

    def _open_case(**kw):
        cases.append(kw)
        return 7000 + len(cases)

    monkeypatch.setattr(cases_bus, "open_case", _open_case)
    return cases


# ---------------------------------------------------------------------------
# issue_permit
# ---------------------------------------------------------------------------

class TestIssuePermit:
    @pytest.mark.parametrize(
        "holder, plate",
        [(None, "AB12CDE"), ("", "AB12CDE"), ("S1", ""), ("S1", None)],
    )
    def test_missing_required_returns_none(self, parking_db, holder, plate):
        assert parking_bus.issue_permit(holder, plate) is None

    def test_numeric_holder_persists_and_returns_id(self, parking_db, stub_finance):
        pid = parking_bus.issue_permit(42, "AB12CDE", zone="north", fee=None)
        assert isinstance(pid, int)
        conn = sqlite3.connect(parking_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT user_id, vehicle_id, zone, status, active_status, student_id "
            "FROM parking_permits WHERE permit_id = ?",
            (pid,),
        ).fetchone()
        conn.close()
        assert row["user_id"] == 42
        assert row["vehicle_id"] == "AB12CDE"
        assert row["zone"] == "north"
        assert row["status"] == "active"
        assert row["active_status"] == 1
        assert row["student_id"] == "42"
        # No fee → no finance charge.
        assert stub_finance["charges"] == []

    def test_fee_raises_finance_charge(self, parking_db, stub_finance):
        pid = parking_bus.issue_permit(42, "AB12CDE", fee=120.0, permit_type="annual")
        assert pid is not None
        assert len(stub_finance["charges"]) == 1
        charge = stub_finance["charges"][0]
        assert charge["amount"] == 120.0
        assert charge["source"] == "parking_permit"
        assert charge["reference_id"] == f"permit:{pid}"

    def test_resolves_username_to_user_id(self, parking_db, stub_finance):
        conn = sqlite3.connect(parking_db)
        conn.execute("INSERT INTO users (id, username) VALUES (7, 'alice')")
        conn.commit()
        conn.close()
        pid = parking_bus.issue_permit("alice", "ZZ99ZZ")
        assert pid is not None
        conn = sqlite3.connect(parking_db)
        uid = conn.execute(
            "SELECT user_id FROM parking_permits WHERE permit_id = ?", (pid,)
        ).fetchone()[0]
        conn.close()
        assert uid == 7

    def test_unresolvable_username_returns_none(self, parking_db, stub_finance):
        # No matching users row and not an int → cannot resolve user_id.
        assert parking_bus.issue_permit("ghost", "ZZ99ZZ") is None


# ---------------------------------------------------------------------------
# suspend_permit
# ---------------------------------------------------------------------------

class TestSuspendPermit:
    def test_falsy_id_returns_false(self, parking_db, stub_finance):
        assert parking_bus.suspend_permit(0) is False

    def test_unknown_permit_returns_false(self, parking_db, stub_finance):
        assert parking_bus.suspend_permit(999999) is False
        assert stub_finance["holds"] == []

    def test_suspends_and_places_hold(self, parking_db, stub_finance):
        pid = parking_bus.issue_permit(42, "AB12CDE")
        assert parking_bus.suspend_permit(pid, reason="unpaid fines") is True
        conn = sqlite3.connect(parking_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT active_status, status FROM parking_permits WHERE permit_id = ?",
            (pid,),
        ).fetchone()
        conn.close()
        assert row["active_status"] == 0
        assert row["status"] == "suspended"
        assert len(stub_finance["holds"]) == 1
        hold = stub_finance["holds"][0]
        assert hold["holder"] == 42
        assert hold["reference_id"] == f"permit:{pid}"
        assert "unpaid fines" in hold["reason"]


# ---------------------------------------------------------------------------
# list_permits_for
# ---------------------------------------------------------------------------

class TestListPermitsFor:
    def test_empty_for_falsy(self, parking_db):
        assert parking_bus.list_permits_for("") == []
        assert parking_bus.list_permits_for(None) == []

    def test_empty_for_unknown(self, parking_db):
        assert parking_bus.list_permits_for(12345) == []

    def test_returns_permits_by_user_id(self, parking_db, stub_finance):
        pid = parking_bus.issue_permit(42, "AB12CDE", zone="south")
        rows = parking_bus.list_permits_for(42)
        assert len(rows) == 1
        assert rows[0]["permit_id"] == pid
        assert rows[0]["plate"] == "AB12CDE"
        assert rows[0]["zone"] == "south"

    def test_returns_permits_by_student_code_fallback(self, parking_db, stub_finance):
        # Permit stored with a non-numeric student_id and matching user_id.
        conn = sqlite3.connect(parking_db)
        conn.execute(
            "INSERT INTO parking_permits "
            "(user_id, vehicle_id, zone, permit_type, start_date, end_date, "
            " fee_paid, status, active_status, student_id) "
            "VALUES (99, 'PL8', 'west', 'annual', ?, ?, 0, 'active', 1, 'S777')",
            (_date(0), _date(365)),
        )
        conn.commit()
        conn.close()
        rows = parking_bus.list_permits_for("S777")
        assert len(rows) == 1
        assert rows[0]["plate"] == "PL8"


# ---------------------------------------------------------------------------
# record_violation
# ---------------------------------------------------------------------------

class TestRecordViolation:
    @pytest.mark.parametrize(
        "plate, kind",
        [("", "no_permit"), ("AB12CDE", ""), (None, "no_permit"), ("AB12CDE", None)],
    )
    def test_missing_required(self, parking_db, plate, kind):
        out = parking_bus.record_violation(plate, kind, 50.0)
        assert out["ok"] is False
        assert "required" in out["reason"]

    def test_logs_violation_and_raises_fine(self, parking_db, stub_finance, stub_cases):
        out = parking_bus.record_violation(
            "AB12CDE", "no_permit", 60.0, holder_id="S1", location="Lot A"
        )
        assert out["ok"] is True
        assert isinstance(out["violation_id"], int)
        assert out["escalated_case_id"] is None
        # Fine routed to finance.
        assert len(stub_finance["charges"]) == 1
        assert stub_finance["charges"][0]["amount"] == 60.0
        assert stub_finance["charges"][0]["source"] == "parking_fine"
        # charge_tx is the id returned by the stubbed raise_charge.
        assert out["charge_tx"] == 5001
        # Row persisted unpaid/open.
        conn = sqlite3.connect(parking_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT payment_status, status, location FROM parking_violations "
            "WHERE violation_id = ?",
            (out["violation_id"],),
        ).fetchone()
        conn.close()
        assert row["payment_status"] == "unpaid"
        assert row["status"] == "open"
        assert row["location"] == "Lot A"

    def test_resolves_holder_by_plate(self, parking_db, stub_finance, stub_cases):
        # A permit ties this plate to user 42; no holder_id supplied.
        parking_bus.issue_permit(42, "AB12CDE")
        out = parking_bus.record_violation("AB12CDE", "expired", 40.0)
        assert out["ok"] is True
        assert len(stub_finance["charges"]) == 1
        assert stub_finance["charges"][0]["holder"] == 42

    def test_no_holder_no_fine_no_escalation(self, parking_db, stub_finance, stub_cases):
        # Unknown plate, no holder → cannot resolve → no charge, no case.
        out = parking_bus.record_violation("UNKNOWN1", "no_permit", 40.0)
        assert out["ok"] is True
        assert out["charge_tx"] is None
        assert out["escalated_case_id"] is None
        assert stub_finance["charges"] == []
        assert stub_cases == []

    def test_third_unpaid_escalates_to_case(self, parking_db, stub_finance, stub_cases):
        # Seed two prior unpaid violations for the same plate.
        conn = sqlite3.connect(parking_db)
        for _ in range(2):
            conn.execute(
                "INSERT INTO parking_violations "
                "(license_plate, violation_type, violation_date, fine_amount, "
                " payment_status, status) "
                "VALUES ('AB12CDE', 'no_permit', ?, 50, 'unpaid', 'open')",
                (_date(-10),),
            )
        conn.commit()
        conn.close()

        out = parking_bus.record_violation("AB12CDE", "no_permit", 50.0, holder_id="S1")
        assert out["escalated_case_id"] is not None
        assert len(stub_cases) == 1
        case = stub_cases[0]
        assert case["kind"] == "disciplinary"
        assert case["subject_id"] == "S1"
        assert "Parking" in case["offense_type"]

    def test_paid_priors_do_not_escalate(self, parking_db, stub_finance, stub_cases):
        # Two PAID priors should not count toward the repeat threshold.
        conn = sqlite3.connect(parking_db)
        for _ in range(2):
            conn.execute(
                "INSERT INTO parking_violations "
                "(license_plate, violation_type, violation_date, fine_amount, "
                " payment_status, status) "
                "VALUES ('AB12CDE', 'no_permit', ?, 50, 'paid', 'closed')",
                (_date(-10),),
            )
        conn.commit()
        conn.close()

        out = parking_bus.record_violation("AB12CDE", "no_permit", 50.0, holder_id="S1")
        assert out["escalated_case_id"] is None
        assert stub_cases == []


# ---------------------------------------------------------------------------
# outstanding_parking_charges
# ---------------------------------------------------------------------------

class TestOutstandingParkingCharges:
    def test_empty_for_falsy(self, parking_db):
        assert parking_bus.outstanding_parking_charges("") == []
        assert parking_bus.outstanding_parking_charges(None) == []

    def test_filters_to_recent_violation_charges(self, parking_db):
        conn = sqlite3.connect(parking_db)
        # Matching: charge, violation ref, recent.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id, created_at) "
            "VALUES ('S1', 60, 'charge', 'Parking fine', 'violation:1', ?)",
            (_date(-5),),
        )
        # Wrong transaction_type.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id, created_at) "
            "VALUES ('S1', 10, 'payment', 'x', 'violation:2', ?)",
            (_date(-5),),
        )
        # Wrong reference prefix.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id, created_at) "
            "VALUES ('S1', 10, 'charge', 'x', 'permit:2', ?)",
            (_date(-5),),
        )
        # Too old (>365 days).
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id, created_at) "
            "VALUES ('S1', 10, 'charge', 'x', 'violation:3', ?)",
            (_date(-400),),
        )
        # Different student.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id, created_at) "
            "VALUES ('S2', 10, 'charge', 'x', 'violation:4', ?)",
            (_date(-5),),
        )
        conn.commit()
        conn.close()

        rows = parking_bus.outstanding_parking_charges("S1")
        assert len(rows) == 1
        assert rows[0]["reference_id"] == "violation:1"
        assert rows[0]["amount"] == 60
