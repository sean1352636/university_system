"""Unit tests for the cross-domain commerce bus (``modules.services.commerce_bus``).

``commerce_bus`` owns no tables — it composes ``finance_bus`` + ``loyalty_bus`` +
``student_union_bus`` and does a couple of best-effort DB reads (``resolve_student``,
``customer_tier`` fallback). The DB seams reach ``get_connection`` via the shared
``DEFAULT_DB_PATH``, so the fixture repoints it at a temp file and seeds the few
tables those reads touch (``restaurant_customers``, ``students``, ``users``).

Every collaborating bus is monkeypatched at the module ``commerce_bus`` imports it
from; the pure-pricing helpers (``price_for``/``apply_perk``) are driven by stubbing
``_su_member`` / ``customer_tier`` directly on the module.
"""

import pytest

from education_system.post_18.university_system.infrastructure.database.db import sqlite3
from education_system.post_18.university_system.modules.services import (
    commerce_bus,
    finance_bus,
    loyalty_bus,
    student_union_bus,
)


_SCHEMA = """
CREATE TABLE restaurant_customers (
    customer_id TEXT, student_id TEXT, loyalty_tier TEXT
);
CREATE TABLE students (
    student_id TEXT, email TEXT
);
CREATE TABLE users (
    id INTEGER PRIMARY KEY, student_id TEXT
);
"""


@pytest.fixture()
def commerce_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "commerce.db")
    monkeypatch.setattr(
        "education_system.post_18.university_system.infrastructure.database.db.DEFAULT_DB_PATH",
        db_path,
    )
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# customer_tier
# ---------------------------------------------------------------------------

class TestCustomerTier:
    def test_no_student_is_bronze(self, commerce_db):
        assert commerce_bus.customer_tier(None) == "Bronze"
        assert commerce_bus.customer_tier("") == "Bronze"

    def test_uses_loyalty_bus(self, commerce_db, monkeypatch):
        monkeypatch.setattr(loyalty_bus, "tier", lambda sid: "Gold")
        assert commerce_bus.customer_tier("S1") == "Gold"

    def test_falls_back_to_restaurant_customers(self, commerce_db, monkeypatch):
        def boom(sid):
            raise RuntimeError("loyalty offline")
        monkeypatch.setattr(loyalty_bus, "tier", boom)
        conn = sqlite3.connect(commerce_db)
        conn.execute(
            "INSERT INTO restaurant_customers (customer_id, student_id, loyalty_tier) "
            "VALUES ('S1', 'S1', 'Platinum')"
        )
        conn.commit()
        conn.close()
        assert commerce_bus.customer_tier("S1") == "Platinum"

    def test_default_bronze_when_nothing_found(self, commerce_db, monkeypatch):
        monkeypatch.setattr(loyalty_bus, "tier",
                            lambda sid: (_ for _ in ()).throw(RuntimeError()))
        assert commerce_bus.customer_tier("nobody") == "Bronze"


# ---------------------------------------------------------------------------
# price_for
# ---------------------------------------------------------------------------

class TestPriceFor:
    def test_zero_base_returns_base(self, commerce_db):
        final, bd = commerce_bus.price_for("S1", 0)
        assert final == 0
        assert bd["discounts"] == []

    def test_no_student_returns_base(self, commerce_db):
        final, bd = commerce_bus.price_for(None, 20.0)
        assert final == 20.0
        assert bd["discounts"] == []

    def test_su_member_and_tier_stack(self, commerce_db, monkeypatch):
        monkeypatch.setattr(commerce_bus, "_su_member", lambda sid: True)
        monkeypatch.setattr(commerce_bus, "customer_tier", lambda sid: "Gold")
        final, bd = commerce_bus.price_for("S1", 100.0)
        # 10% SU member + 10% Gold tier = 20% off.
        assert bd["pct"] == pytest.approx(0.20)
        assert final == pytest.approx(80.0)
        kinds = {d["kind"] for d in bd["discounts"]}
        assert kinds == {"su_member", "tier"}

    def test_non_member_no_tier(self, commerce_db, monkeypatch):
        monkeypatch.setattr(commerce_bus, "_su_member", lambda sid: False)
        monkeypatch.setattr(commerce_bus, "customer_tier", lambda sid: "Bronze")
        final, bd = commerce_bus.price_for("S1", 50.0)
        assert final == 50.0
        assert bd["discounts"] == []

    def test_stacked_discount_capped_at_30pct(self, commerce_db, monkeypatch):
        monkeypatch.setattr(commerce_bus, "_su_member", lambda sid: True)
        monkeypatch.setattr(commerce_bus, "customer_tier", lambda sid: "Gold")
        # Inflate the Gold tier discount so SU(0.10)+Gold(0.40)=0.50 exceeds the cap.
        monkeypatch.setitem(commerce_bus._TIER_DISCOUNT, "Gold", 0.40)
        final, bd = commerce_bus.price_for("S1", 100.0)
        assert bd["pct"] == pytest.approx(0.30)
        assert final == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# post_sale
# ---------------------------------------------------------------------------

class TestPostSale:
    def test_walk_in_is_noop(self, commerce_db):
        out = commerce_bus.post_sale(None, source="cinema", amount=12.0,
                                     description="ticket")
        assert out == {"tx_id": None, "points_earned": 0, "kind": "sale"}

    def test_non_positive_amount_is_noop(self, commerce_db):
        out = commerce_bus.post_sale("S1", source="shop", amount=0,
                                     description="x")
        assert out["tx_id"] is None
        assert out["points_earned"] == 0

    def test_paid_sale_records_and_earns_points(self, commerce_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "record_paid_sale", lambda *a, **k: "TX-1")
        pts = []
        monkeypatch.setattr(loyalty_bus, "add_points",
                            lambda sid, **k: pts.append(k.get("points")))
        out = commerce_bus.post_sale("S1", source="cinema", amount=12.5,
                                     description="ticket")
        assert out["tx_id"] == "TX-1"
        assert out["kind"] == "sale"
        assert out["points_earned"] == 12  # int(12.5)
        assert pts == [12]

    def test_invoice_mode_raises_charge(self, commerce_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "raise_charge", lambda *a, **k: "INV-1")
        monkeypatch.setattr(loyalty_bus, "add_points", lambda *a, **k: None)
        out = commerce_bus.post_sale("S1", source="gym", amount=30.0,
                                     description="sub", invoice=True)
        assert out["tx_id"] == "INV-1"
        assert out["kind"] == "invoice"

    def test_earn_points_false_skips_loyalty(self, commerce_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "record_paid_sale", lambda *a, **k: "TX-2")
        called = []
        monkeypatch.setattr(loyalty_bus, "add_points",
                            lambda *a, **k: called.append(1))
        out = commerce_bus.post_sale("S1", source="shop", amount=9.0,
                                     description="x", earn_points=False)
        assert out["points_earned"] == 0
        assert called == []

    def test_loyalty_failure_does_not_break_sale(self, commerce_db, monkeypatch):
        monkeypatch.setattr(finance_bus, "record_paid_sale", lambda *a, **k: "TX-3")

        def boom(*a, **k):
            raise RuntimeError("loyalty down")
        monkeypatch.setattr(loyalty_bus, "add_points", boom)
        out = commerce_bus.post_sale("S1", source="shop", amount=9.0,
                                     description="x")
        assert out["tx_id"] == "TX-3"
        assert out["points_earned"] == 0


# ---------------------------------------------------------------------------
# resolve_student
# ---------------------------------------------------------------------------

class TestResolveStudent:
    def test_customer_id_preferred(self, commerce_db):
        conn = sqlite3.connect(commerce_db)
        conn.execute(
            "INSERT INTO restaurant_customers (customer_id, student_id) "
            "VALUES ('C1', 'S-CUST')"
        )
        conn.commit()
        conn.close()
        assert commerce_bus.resolve_student(customer_id="C1") == "S-CUST"

    def test_email_lookup(self, commerce_db):
        conn = sqlite3.connect(commerce_db)
        conn.execute(
            "INSERT INTO students (student_id, email) VALUES ('S-MAIL', 'a@x.com')"
        )
        conn.commit()
        conn.close()
        assert commerce_bus.resolve_student(email="a@x.com") == "S-MAIL"

    def test_user_id_lookup(self, commerce_db):
        conn = sqlite3.connect(commerce_db)
        conn.execute("INSERT INTO users (id, student_id) VALUES (7, 'S-USER')")
        conn.commit()
        conn.close()
        assert commerce_bus.resolve_student(user_id=7) == "S-USER"

    def test_no_match_returns_none(self, commerce_db):
        assert commerce_bus.resolve_student(email="none@x.com") is None
        assert commerce_bus.resolve_student() is None


# ---------------------------------------------------------------------------
# apply_perk
# ---------------------------------------------------------------------------

class TestApplyPerk:
    def test_no_student(self, commerce_db):
        granted, reason = commerce_bus.apply_perk(None, "cinema_seat_upgrade")
        assert granted is False
        assert reason == "no student"

    def test_unknown_perk(self, commerce_db, monkeypatch):
        monkeypatch.setattr(commerce_bus, "customer_tier", lambda sid: "Gold")
        granted, reason = commerce_bus.apply_perk("S1", "teleport")
        assert granted is False
        assert "unknown perk" in reason

    def test_granted_when_tier_qualifies(self, commerce_db, monkeypatch):
        monkeypatch.setattr(commerce_bus, "customer_tier", lambda sid: "Gold")
        granted, reason = commerce_bus.apply_perk("S1", "cinema_seat_upgrade")
        assert granted is True
        assert "qualifies" in reason

    def test_denied_when_tier_below_threshold(self, commerce_db, monkeypatch):
        monkeypatch.setattr(commerce_bus, "customer_tier", lambda sid: "Silver")
        granted, reason = commerce_bus.apply_perk("S1", "gym_guest_pass")
        assert granted is False
        assert "requires" in reason


# ---------------------------------------------------------------------------
# _su_member (private seam used by price_for)
# ---------------------------------------------------------------------------

class TestSuMember:
    def test_true_when_clubs_present(self, commerce_db, monkeypatch):
        monkeypatch.setattr(student_union_bus, "list_clubs_for", lambda sid: [{"id": 1}])
        assert commerce_bus._su_member("S1") is True

    def test_false_when_no_clubs(self, commerce_db, monkeypatch):
        monkeypatch.setattr(student_union_bus, "list_clubs_for", lambda sid: [])
        assert commerce_bus._su_member("S1") is False

    def test_false_on_error(self, commerce_db, monkeypatch):
        def boom(sid):
            raise RuntimeError("su down")
        monkeypatch.setattr(student_union_bus, "list_clubs_for", boom)
        assert commerce_bus._su_member("S1") is False
