"""Unit tests for the restaurant / dining bus (``modules.services.restaurant_bus``).

``restaurant_bus`` doesn't own a schema — money flows through ``finance_bus`` and
menus persist as ``academic_calendar_events`` rows. The fixture repoints the
shared ``DEFAULT_DB_PATH`` at a temp file (read by ``get_connection`` at call
time) and seeds the stand-in tables the bus reads directly
(``student_finance_transactions``, ``staff``, ``academic_calendar_events``).

``_publish`` is neutralised and the two seams — ``finance_bus.raise_charge`` and
``student_union_bus.list_clubs_for`` — are stubbed at the module attribute.
"""

import pytest

from education_system.systems.university.infrastructure.database.db import (
    get_connection,
    sqlite3,
)
from education_system.systems.university.services.bus import (
    finance_bus,
    restaurant_bus,
    student_union_bus,
)

_SEED_SQL = """
CREATE TABLE student_finance_transactions (
    transaction_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id       TEXT,
    amount           REAL,
    transaction_type TEXT,
    description      TEXT,
    reference_id     TEXT,
    created_at       TEXT
);
CREATE TABLE staff (
    id       INTEGER PRIMARY KEY,
    username TEXT,
    status   TEXT
);
CREATE TABLE academic_calendar_events (
    id            TEXT PRIMARY KEY,
    name          TEXT,
    date          TEXT,
    description   TEXT,
    event_type    TEXT,
    date_added    TEXT,
    last_modified TEXT,
    created_by    TEXT
);
"""


@pytest.fixture()
def restaurant_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "restaurant.db")
    monkeypatch.setattr(
        "education_system.systems.university.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    with get_connection() as conn:
        conn.executescript(_SEED_SQL)
        conn.commit()
    monkeypatch.setattr(restaurant_bus, "_publish", lambda *a, **k: None)
    return db_path


@pytest.fixture()
def stub_finance(monkeypatch):
    charges: list[dict] = []

    def _raise_charge(student, amount, **kw):
        charges.append({"student": student, "amount": amount, **kw})
        return 4000 + len(charges)

    monkeypatch.setattr(finance_bus, "raise_charge", _raise_charge)
    return charges


# ---------------------------------------------------------------------------
# top_up_meal_plan
# ---------------------------------------------------------------------------

class TestTopUpMealPlan:
    @pytest.mark.parametrize("student, amount", [(None, 10), ("", 10), ("S1", 0), ("S1", -5)])
    def test_invalid_returns_none(self, restaurant_db, stub_finance, student, amount):
        assert restaurant_bus.top_up_meal_plan(student, amount) is None
        assert stub_finance == []

    def test_posts_negative_charge_and_returns_tx(self, restaurant_db, stub_finance):
        tx = restaurant_bus.top_up_meal_plan("S1", 50.0)
        assert tx == 4001
        assert len(stub_finance) == 1
        assert stub_finance[0]["amount"] == -50.0  # credit = negative charge
        assert stub_finance[0]["source"] == "meal_plan_topup"


# ---------------------------------------------------------------------------
# record_pos_transaction
# ---------------------------------------------------------------------------

class TestRecordPosTransaction:
    @pytest.mark.parametrize("student, amount", [(None, 10), ("S1", 0), ("S1", -1)])
    def test_invalid_returns_none(self, restaurant_db, stub_finance, student, amount):
        assert restaurant_bus.record_pos_transaction(student, amount) is None
        assert stub_finance == []

    def test_posts_positive_charge(self, restaurant_db, stub_finance):
        tx = restaurant_bus.record_pos_transaction(
            "S1", 12.5, items=["Coffee", "Sandwich"], location="Cafe"
        )
        assert tx == 4001
        assert stub_finance[0]["amount"] == 12.5
        assert stub_finance[0]["source"] == "restaurant_pos"
        assert "Coffee" in stub_finance[0]["description"]
        assert "Cafe" in stub_finance[0]["description"]


# ---------------------------------------------------------------------------
# meal_plan_balance
# ---------------------------------------------------------------------------

class TestMealPlanBalance:
    def test_zero_for_falsy(self, restaurant_db):
        assert restaurant_bus.meal_plan_balance("") == 0.0

    def test_zero_when_no_rows(self, restaurant_db):
        assert restaurant_bus.meal_plan_balance("S1") == 0.0

    def test_nets_topups_minus_pos(self, restaurant_db):
        conn = sqlite3.connect(restaurant_db)
        # Top-up stored as negative charge (-50) → contributes +50 to balance.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id) "
            "VALUES ('S1', -50, 'charge', 'Meal-plan top-up of £50.00', 'topup:a')"
        )
        # POS spend stored as +20 → contributes -20.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id) "
            "VALUES ('S1', 20, 'charge', 'Restaurant POS — Coffee', 'pos:b')"
        )
        # Unrelated description → excluded.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id) "
            "VALUES ('S1', 999, 'charge', 'Tuition fee', 'fee:c')"
        )
        # Empty reference_id → excluded.
        conn.execute(
            "INSERT INTO student_finance_transactions "
            "(student_id, amount, transaction_type, description, reference_id) "
            "VALUES ('S1', -30, 'charge', 'Meal-plan top-up of £30.00', '')"
        )
        conn.commit()
        conn.close()
        assert restaurant_bus.meal_plan_balance("S1") == 30.0


# ---------------------------------------------------------------------------
# apply_su_discount
# ---------------------------------------------------------------------------

class TestApplySuDiscount:
    def test_falsy_returns_unchanged(self, restaurant_db):
        assert restaurant_bus.apply_su_discount("", 10) == (10.0, False)
        assert restaurant_bus.apply_su_discount("S1", 0) == (0.0, False)

    def test_member_gets_discount(self, restaurant_db, monkeypatch):
        monkeypatch.setattr(student_union_bus, "list_clubs_for", lambda sid: [{"club": "Chess"}])
        discounted, applied = restaurant_bus.apply_su_discount("S1", 10.0)
        assert applied is True
        assert discounted == 9.0  # 10% off

    def test_non_member_unchanged(self, restaurant_db, monkeypatch):
        monkeypatch.setattr(student_union_bus, "list_clubs_for", lambda sid: [])
        assert restaurant_bus.apply_su_discount("S1", 10.0) == (10.0, False)


# ---------------------------------------------------------------------------
# apply_staff_subsidy
# ---------------------------------------------------------------------------

class TestApplyStaffSubsidy:
    def test_falsy_returns_unchanged(self, restaurant_db):
        assert restaurant_bus.apply_staff_subsidy("", 10) == (10.0, False)
        assert restaurant_bus.apply_staff_subsidy("S1", None) == (0.0, False)

    def test_active_staff_gets_subsidy(self, restaurant_db):
        conn = sqlite3.connect(restaurant_db)
        conn.execute("INSERT INTO staff (id, username, status) VALUES (3, 'jdoe', 'active')")
        conn.commit()
        conn.close()
        discounted, applied = restaurant_bus.apply_staff_subsidy("jdoe", 10.0)
        assert applied is True
        assert discounted == 8.0  # 20% off

    def test_non_staff_unchanged(self, restaurant_db):
        assert restaurant_bus.apply_staff_subsidy("nobody", 10.0) == (10.0, False)

    def test_inactive_staff_not_subsidised(self, restaurant_db):
        conn = sqlite3.connect(restaurant_db)
        conn.execute("INSERT INTO staff (id, username, status) VALUES (4, 'gone', 'inactive')")
        conn.commit()
        conn.close()
        assert restaurant_bus.apply_staff_subsidy("gone", 10.0) == (10.0, False)


# ---------------------------------------------------------------------------
# publish_menu_for / menu_for
# ---------------------------------------------------------------------------

class TestMenu:
    def test_missing_date_or_items_returns_none(self, restaurant_db):
        assert restaurant_bus.publish_menu_for(on_date="", menu_items=["a"]) is None
        assert restaurant_bus.publish_menu_for(on_date="2026-07-22", menu_items=None) is None

    def test_publish_persists_calendar_event(self, restaurant_db):
        eid = restaurant_bus.publish_menu_for(
            on_date="2026-07-22", location="Main Hall", menu_items=["Soup", "Curry"]
        )
        assert isinstance(eid, str) and eid
        conn = sqlite3.connect(restaurant_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT event_type, date, name FROM academic_calendar_events WHERE id = ?",
            (eid,),
        ).fetchone()
        conn.close()
        assert row["event_type"] == "menu"
        assert row["date"] == "2026-07-22"
        assert "Main Hall" in row["name"]

    def test_menu_for_reads_back_parsed_body(self, restaurant_db):
        restaurant_bus.publish_menu_for(
            on_date="2026-07-22", location="Main Hall", menu_items=["Soup", "Curry"]
        )
        rows = restaurant_bus.menu_for("2026-07-22")
        assert len(rows) == 1
        assert rows[0]["body"]["items"] == ["Soup", "Curry"]
        assert rows[0]["body"]["location"] == "Main Hall"

    def test_menu_for_filters_by_date(self, restaurant_db):
        restaurant_bus.publish_menu_for(on_date="2026-07-22", menu_items=["Soup"])
        assert restaurant_bus.menu_for("2026-07-23") == []

    def test_menu_for_location_filter(self, restaurant_db):
        restaurant_bus.publish_menu_for(
            on_date="2026-07-22", location="Main Hall", menu_items=["Soup"]
        )
        restaurant_bus.publish_menu_for(
            on_date="2026-07-22", location="Annex", menu_items=["Salad"]
        )
        rows = restaurant_bus.menu_for("2026-07-22", location="annex")
        assert len(rows) == 1
        assert rows[0]["body"]["location"] == "Annex"
