"""Unit tests for the unified loyalty ledger (``modules.services.loyalty_bus``).

``loyalty_bus`` owns the ``loyalty_ledger`` schema and reaches the DB through the
shared ``get_connection`` helper, which resolves its target file from the
module-level ``DEFAULT_DB_PATH``. Repointing that constant at a per-test temp
file gives full isolation; the bus creates ``loyalty_ledger`` on every call
(``_ensure_schema``).

``points_balance`` *also* opportunistically reads the legacy
``restaurant_customers`` and ``su_points`` tables inside nested try/except
blocks, tolerating their absence — so the base fixture seeds nothing, and a
dedicated test seeds them to exercise the legacy-aggregation path.

``_publish`` (the academics event-bus fan-out) is neutralised per test.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
)
from education_system.systems.university.services.bus import loyalty_bus


@pytest.fixture()
def loyalty_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "loyalty.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    monkeypatch.setattr(loyalty_bus, "_publish", lambda *a, **k: None)
    return db_path


# ---------------------------------------------------------------------------
# add_points
# ---------------------------------------------------------------------------

class TestAddPoints:
    def test_returns_running_balance_and_persists(self, loyalty_db):
        bal = loyalty_bus.add_points("S001", source="cinema", points=100)
        assert bal == 100
        bal2 = loyalty_bus.add_points("S001", source="gym", points=50)
        assert bal2 == 150
        assert loyalty_bus.points_balance("S001") == 150

    def test_negative_points_redeem(self, loyalty_db):
        loyalty_bus.add_points("S001", source="shop", points=200)
        bal = loyalty_bus.add_points("S001", source="shop", points=-75)
        assert bal == 125

    def test_coerces_int_student_id(self, loyalty_db):
        bal = loyalty_bus.add_points(42, source="su", points=10)
        assert bal == 10
        assert loyalty_bus.points_balance("42") == 10

    @pytest.mark.parametrize(
        "sid, pts",
        [(None, 10), ("", 10), ("S001", 0), ("S001", None)],
    )
    def test_missing_args_return_none(self, loyalty_db, sid, pts):
        assert loyalty_bus.add_points(sid, source="cinema", points=pts) is None


# ---------------------------------------------------------------------------
# points_balance
# ---------------------------------------------------------------------------

class TestPointsBalance:
    def test_zero_for_unknown(self, loyalty_db):
        assert loyalty_bus.points_balance("nobody") == 0

    def test_zero_for_falsy(self, loyalty_db):
        assert loyalty_bus.points_balance("") == 0
        assert loyalty_bus.points_balance(None) == 0

    def test_isolated_per_student(self, loyalty_db):
        loyalty_bus.add_points("S001", source="cinema", points=100)
        loyalty_bus.add_points("S002", source="cinema", points=300)
        assert loyalty_bus.points_balance("S001") == 100
        assert loyalty_bus.points_balance("S002") == 300

    def test_includes_legacy_stores(self, loyalty_db):
        loyalty_bus.add_points("S001", source="cinema", points=100)
        # Seed legacy tables the bus opportunistically reads.
        with get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE restaurant_customers (
                    customer_id TEXT, student_id TEXT, loyalty_points INTEGER
                );
                CREATE TABLE su_points (
                    student_id TEXT, points INTEGER
                );
                """
            )
            conn.execute(
                "INSERT INTO restaurant_customers (customer_id, student_id, loyalty_points) "
                "VALUES ('S001', NULL, 40)"
            )
            conn.execute(
                "INSERT INTO su_points (student_id, points) VALUES ('S001', 25)"
            )
            conn.commit()
        # 100 ledger + 40 restaurant + 25 SU
        assert loyalty_bus.points_balance("S001") == 165


# ---------------------------------------------------------------------------
# tier
# ---------------------------------------------------------------------------

class TestTier:
    @pytest.mark.parametrize(
        "points, expected",
        [
            (0, "Bronze"),
            (100, "Bronze"),
            (499, "Bronze"),
            (500, "Silver"),
            (1999, "Silver"),
            (2000, "Gold"),
            (4999, "Gold"),
            (5000, "Platinum"),
            (10000, "Platinum"),
        ],
    )
    def test_thresholds(self, loyalty_db, points, expected):
        if points:
            loyalty_bus.add_points("S001", source="cinema", points=points)
        assert loyalty_bus.tier("S001") == expected


# ---------------------------------------------------------------------------
# list_recent
# ---------------------------------------------------------------------------

class TestListRecent:
    def test_empty_for_falsy(self, loyalty_db):
        assert loyalty_bus.list_recent("") == []
        assert loyalty_bus.list_recent(None) == []

    def test_empty_for_unknown(self, loyalty_db):
        assert loyalty_bus.list_recent("nobody") == []

    def test_newest_first(self, loyalty_db):
        loyalty_bus.add_points("S001", source="cinema", points=10, description="a")
        loyalty_bus.add_points("S001", source="gym", points=20, description="b")
        rows = loyalty_bus.list_recent("S001")
        assert [r["description"] for r in rows] == ["b", "a"]
        assert rows[0]["source"] == "gym"
        assert rows[0]["points"] == 20

    def test_respects_limit(self, loyalty_db):
        for i in range(5):
            loyalty_bus.add_points("S001", source="cinema", points=i + 1)
        rows = loyalty_bus.list_recent("S001", limit=2)
        assert len(rows) == 2
